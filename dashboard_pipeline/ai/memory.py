"""Phase 0B Sprint 3 — Local semantic memory + project RAG layer.

Two collections live in a single local ChromaDB store:

* ``chat_memory``  — short summaries the AI writes at the end of each
  meaningful chat (decisions, recommendations, observations, promises).
* ``project_index`` — chunked content of project Excel files (and any
  other allowlisted source we choose to index later).

Both share the same embedding function — a multilingual MiniLM model from
``sentence-transformers`` that runs locally (no API roundtrip, ~80-85%
quality on Georgian, free).

Design constraints (mirrors :mod:`dashboard_pipeline.ai.forecasting`)
---------------------------------------------------------------------
* Every heavy import is **lazy** (``chromadb`` and ``sentence_transformers``
  pull in big binary wheels). When either install is broken the rest of
  the AI pipeline keeps working — tools just return a clear Georgian
  error with a ``pip install`` hint.
* Storage is **local-only**. The ChromaDB persist directory defaults to
  ``ai_vectors/`` under the project root (already gitignored).
* Public functions return **flat, JSON-safe dicts** so the tool
  dispatcher can serialise them straight into a ``tool_result`` content
  block.
* Every operation is **bounded**: query length ≤ 500 chars, recall limit
  ≤ 50, summary length ≤ 8000 chars.
* No background threads, no global state. The caller owns the lifecycle
  via :func:`get_memory_store`; the dispatcher creates one store per
  process and reuses it.

Public API
----------

::

    save_memory(summary, *, tags=None, source="chat", project_root=None)
    recall_context(query, *, limit=5, source=None, tags=None,
                   project_root=None)
    index_project_files(file_paths, *, project_root=None,
                         on_progress=None, replace=False)
    get_memory_store(project_root=None) -> MemoryStore
    reset_memory_store()        # primarily for tests

Return contracts
----------------

``save_memory`` success::

    {
        "ok": True,
        "memory_id": "<uuid>",
        "stored_chars": int,
        "tags": ["chat", "decision", ...],
        "source": "chat",
        "collection": "chat_memory",
    }

``recall_context`` success::

    {
        "source": "ai_memory:chat_memory" | "...:project_index" | "both",
        "query": "<echoed>",
        "limit": int,
        "result_count": int,
        "results": [
            {
                "id": "<uuid>",
                "rank": 1..N,
                "distance": float,        # 0=perfect, 1=opposite (cosine)
                "summary": "<text>",
                "tags": [...],
                "source": "chat" | "excel" | ...,
                "created_at": "YYYY-MM-DDTHH:MM:SS",
                "metadata": {...},
            },
            ...
        ],
    }

Failure (any tool)::

    {"error": "<Georgian message>", "hint": "<install / usage hint>"}
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public contract constants
# ---------------------------------------------------------------------------

#: Persist directory under the project root. Already covered by the
#: top-level ``.gitignore`` (``ai_vectors/``).
DEFAULT_MEMORY_DIRNAME = "ai_vectors"

CHAT_COLLECTION_NAME = "chat_memory"
PROJECT_COLLECTION_NAME = "project_index"

#: Multilingual model — handles Georgian + English with the same vector
#: space. ~120 MB download on first use, cached in the HuggingFace cache
#: directory after that.
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

#: Tool-level bounds.
MIN_SUMMARY_CHARS = 10
MAX_SUMMARY_CHARS = 8_000
MAX_QUERY_CHARS = 500
DEFAULT_RECALL_LIMIT = 5
MIN_RECALL_LIMIT = 1
MAX_RECALL_LIMIT = 50

#: Allowed values for the ``source`` metadata field. Anything else gets
#: rejected at save-time so a typo can't fragment the recall index.
ALLOWED_SOURCES: Tuple[str, ...] = ("chat", "excel", "code", "doc")

#: Indexing chunk size (characters per chunk). Tuned for Excel-like CSV
#: rows — small enough to keep the embedding focused, big enough to keep
#: the chunk count manageable on a 27 MB CSV.
DEFAULT_CHUNK_CHARS = 1_200
DEFAULT_CHUNK_OVERLAP = 150
MAX_INDEX_CHUNKS_PER_FILE = 5_000

#: Tag normalisation: lowercase, snake_case, alpha-num + ``:`` (used for
#: namespaced tags like ``year:2025`` or ``supplier:alpha``).
_TAG_SAFE_RE = re.compile(r"[^a-z0-9_:\-]+")

#: ChromaDB stores tags as a comma-separated string in metadata to stay
#: compatible with ``where`` filters (Chroma rejects list-typed metadata).
_TAG_JOIN = ","


# ---------------------------------------------------------------------------
# Lazy loaders for heavy deps
# ---------------------------------------------------------------------------


def _load_chromadb():
    """Return the ``chromadb`` module or ``None`` if unavailable."""
    try:
        import chromadb  # type: ignore
        return chromadb
    except Exception as exc:  # ImportError + sub-dep issues
        logger.info("chromadb unavailable: %s", exc)
        return None


def _load_embedding_function():
    """Return a ChromaDB-compatible embedding function or ``None``.

    Uses the multilingual MiniLM model from ``sentence-transformers`` so
    Georgian and English queries land in the same vector space.
    """
    try:
        from chromadb.utils import embedding_functions  # type: ignore
    except Exception as exc:
        logger.info("chromadb.utils.embedding_functions unavailable: %s", exc)
        return None

    try:
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL_NAME,
        )
    except Exception as exc:
        logger.warning("SentenceTransformer embedding init failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Project-root + persist-dir resolution
# ---------------------------------------------------------------------------


def _default_project_root() -> Path:
    """Repository root — same convention as :mod:`tools`.

    Layout assumption: ``financial-dashboard/dashboard_pipeline/ai/memory.py``
    → repo root is three levels up.
    """
    return Path(__file__).resolve().parent.parent.parent


def resolve_persist_dir(project_root: Optional[Path] = None) -> Path:
    """Return the canonical local ChromaDB directory."""
    root = (project_root or _default_project_root()).resolve()
    return root / DEFAULT_MEMORY_DIRNAME


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """ISO-8601 UTC timestamp without microseconds."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalise_tag(raw: Any) -> Optional[str]:
    """Lowercase + collapse whitespace + drop unsafe chars. Returns None on empty.

    Cosmetic post-processing: collapse runs of underscores into one and
    drop underscores that sit directly next to a ``:`` separator, so a
    natural input like ``"Topic: Cash Flow!"`` becomes ``"topic:cash_flow"``
    instead of the noisier ``"topic:_cash_flow_"``.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        try:
            raw = str(raw)
        except Exception:
            return None
    cleaned = _TAG_SAFE_RE.sub("_", raw.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.replace(":_", ":").replace("_:", ":")
    cleaned = cleaned.strip("_")
    return cleaned or None


def _normalise_tags(raw_tags: Any) -> List[str]:
    """Accept a list / tuple / comma-string of tags. De-dupe + sort.

    Bad shapes silently degrade to ``[]`` rather than raising — the LLM
    sometimes passes ``None`` or a plain string and we'd rather store the
    memory tagless than reject the whole call.
    """
    if raw_tags is None:
        return []
    if isinstance(raw_tags, str):
        candidates: Iterable[Any] = raw_tags.split(",")
    elif isinstance(raw_tags, (list, tuple, set)):
        candidates = raw_tags
    else:
        candidates = [raw_tags]
    seen: List[str] = []
    for c in candidates:
        n = _normalise_tag(c)
        if n and n not in seen:
            seen.append(n)
    return sorted(seen)


def _tags_to_metadata(tags: Sequence[str]) -> str:
    """Encode tags as a comma-separated string (Chroma rejects list metadata)."""
    return _TAG_JOIN.join(tags)


def _tags_from_metadata(value: Any) -> List[str]:
    """Decode the comma-separated tag string back into a list."""
    if not value or not isinstance(value, str):
        return []
    return [t for t in value.split(_TAG_JOIN) if t]


def _coerce_summary(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """Validate + trim a summary. Return ``(text, error)``."""
    if raw is None:
        return None, "`summary` სავალდებულოა — წერე მოკლე ტექსტი."
    if not isinstance(raw, str):
        return None, "`summary` უნდა იყოს ტექსტი."
    text = raw.strip()
    if len(text) < MIN_SUMMARY_CHARS:
        return None, (
            f"`summary` ძალიან მოკლეა (მინიმუმ {MIN_SUMMARY_CHARS} სიმბოლო)."
        )
    if len(text) > MAX_SUMMARY_CHARS:
        text = text[:MAX_SUMMARY_CHARS].rstrip() + "…"
    return text, None


def _coerce_query(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """Validate + trim a recall query string."""
    if raw is None:
        return None, "`query` სავალდებულოა — დაწერე სათხოვი ტექსტი."
    if not isinstance(raw, str):
        return None, "`query` უნდა იყოს ტექსტი."
    text = raw.strip()
    if not text:
        return None, "`query` ცარიელია — გადაწერე უფრო კონკრეტულად."
    if len(text) > MAX_QUERY_CHARS:
        text = text[:MAX_QUERY_CHARS]
    return text, None


def _coerce_limit(raw: Any) -> int:
    """Clamp ``limit`` into ``[MIN_RECALL_LIMIT, MAX_RECALL_LIMIT]``."""
    if raw is None:
        return DEFAULT_RECALL_LIMIT
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_RECALL_LIMIT
    return max(MIN_RECALL_LIMIT, min(value, MAX_RECALL_LIMIT))


def _coerce_source(raw: Any, default: str) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(source, error)``. ``None`` keeps the default."""
    if raw is None:
        return default, None
    if not isinstance(raw, str):
        return None, (
            f"`source` უნდა იყოს ტექსტი ({list(ALLOWED_SOURCES)})."
        )
    src = raw.strip().lower()
    if not src:
        return default, None
    if src not in ALLOWED_SOURCES:
        return None, (
            f"`source`='{raw}' უცნობია. დასაშვებია: {list(ALLOWED_SOURCES)}."
        )
    return src, None


def _build_where_filter(
    source: Optional[str] = None,
    tags: Optional[Sequence[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Translate filters into ChromaDB ``where`` syntax.

    Tag filters use a substring contains check on the encoded tag string
    (``$contains`` operator). Multiple tags are AND-ed.
    """
    clauses: List[Dict[str, Any]] = []
    if source:
        clauses.append({"source": {"$eq": source}})
    if tags:
        for t in tags:
            clauses.append({"tags": {"$contains": t}})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _chunk_text(
    text: str,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[str]:
    """Split a long string into overlapping chunks.

    Naive char-based chunking — fine for tabular CSV content where row
    boundaries map roughly to commas/newlines. Empty input returns ``[]``.
    """
    if not text:
        return []
    if chunk_chars <= 0:
        return [text]
    if overlap < 0:
        overlap = 0
    if overlap >= chunk_chars:
        overlap = chunk_chars // 4
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


#: Georgian labels for the four auto-inferred file categories. Used only
#: for the human-readable chunk header (embedding-friendly); metadata
#: still carries the canonical English token via ``tags``.
_CATEGORY_GEORGIAN_LABELS = {
    "bank": "ბანკი",
    "waybills": "ზედნადები",
    "sales": "გაყიდვები",
    "products": "პროდუქცია",
}

#: Latin-script hints appended to the keyword line for folders whose
#: Georgian name is a short abbreviation (e.g. "ბოგ"/"თბს"). The
#: multilingual MiniLM embedding tokenises Latin strings much more
#: reliably than 3-letter Cyrillic-style Georgian abbreviations, so
#: these hints give the model a distinctive signal to separate, say,
#: BOG bank chunks from TBC bank chunks on a query like "ბოგ ბანკი 2023".
_FOLDER_LATIN_HINTS = {
    "ბოგ ბანკი ამონაწერი": "BOG bank Bank of Georgia statement",
    "თბს ბანკი ამონაწერი": "TBC bank statement",
    "რს ზედნადები": "RS waybill Revenue Service invoice",
    "შემოტანილი პროდუქცია": "imported products purchases inventory",
    "გაყიდული პროდუქტები სოფ ოზურგეთი": "Ozurgeti sales sold products",
    "გაყიდული პროდუქტები სოფ დვაბზუ": "Dvabzu sales sold products",
}


def _build_chunk_header(path: str, tags: Sequence[str]) -> str:
    """Return a short Georgian header prepended to every Excel chunk.

    Excel cell content is often purely numeric (dates, amounts, codes) so
    the multilingual embedding model can't match a natural-language query
    like ``"ბოგ ბანკი 2023"`` to the chunk body alone. The header has two
    lines:

    1. **Keyword line** — condensed tokens (folder stem + year + category
       label) designed to dominate the embedding similarity signal.
    2. **Structured line** — full file path + year/month/category in
       human-readable form, useful when the chunk is shown to a user.
    """
    path = (path or "").strip()
    year: Optional[str] = None
    month: Optional[str] = None
    category: Optional[str] = None
    for raw in tags or ():
        token = str(raw).strip().lower()
        if token.startswith("year:") and not year:
            year = token.split(":", 1)[1].strip()
        elif token.startswith("month:") and not month:
            month = token.split(":", 1)[1].strip()
        elif token.startswith("category:") and not category:
            category = token.split(":", 1)[1].strip()

    # Folder stem — immediate parent directory of the file. In this
    # project that reliably names the bank / waybill / sales source in
    # Georgian (e.g. ``"ბოგ ბანკი ამონაწერი"``, ``"თბს ბანკი ამონაწერი"``,
    # ``"რს ზედნადები"``).
    folder_stem = ""
    if path:
        norm = path.replace("\\", "/")
        components = [c for c in norm.split("/") if c]
        if len(components) >= 2:
            folder_stem = components[-2]

    keyword_parts: List[str] = []
    if folder_stem:
        keyword_parts.append(folder_stem)
        latin_hint = _FOLDER_LATIN_HINTS.get(folder_stem)
        if latin_hint:
            keyword_parts.append(latin_hint)
    if year:
        keyword_parts.append(year)
    if month:
        keyword_parts.append(month)
    if category:
        keyword_parts.append(_CATEGORY_GEORGIAN_LABELS.get(category, category))

    structured_parts: List[str] = []
    if path:
        structured_parts.append(f"ფაილი: {path}")
    if year:
        structured_parts.append(f"წელი {year}")
    if month:
        structured_parts.append(f"თვე {month}")
    if category:
        label = _CATEGORY_GEORGIAN_LABELS.get(category, category)
        structured_parts.append(f"კატეგორია {label}")

    lines: List[str] = []
    if keyword_parts:
        lines.append(" ".join(keyword_parts))
    if structured_parts:
        lines.append(f"[{' — '.join(structured_parts)}]")
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# MemoryStore — thin wrapper around ChromaDB collections
# ---------------------------------------------------------------------------


class MemoryStoreUnavailable(RuntimeError):
    """Raised when ChromaDB or the embedding function cannot be loaded."""


class MemoryStore:
    """Owns a ChromaDB ``PersistentClient`` plus the two collections.

    The store is intentionally cheap to construct *as long as* the heavy
    deps load — it doesn't pre-warm the embedding model (that happens on
    first encode call).
    """

    def __init__(
        self,
        persist_dir: Path,
        chromadb_module: Any,
        embedding_function: Any,
    ):
        self._persist_dir = persist_dir
        self._chromadb = chromadb_module
        self._embedding_function = embedding_function
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb_module.PersistentClient(path=str(persist_dir))
        self._chat = self._client.get_or_create_collection(
            name=CHAT_COLLECTION_NAME,
            embedding_function=embedding_function,
            metadata={"hnsw:space": "cosine"},
        )
        self._project = self._client.get_or_create_collection(
            name=PROJECT_COLLECTION_NAME,
            embedding_function=embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

    # -- accessors ----------------------------------------------------------

    @property
    def persist_dir(self) -> Path:
        return self._persist_dir

    def collection(self, source: str):
        """Pick the right collection for ``source``."""
        if source == "chat":
            return self._chat
        return self._project

    # -- save ---------------------------------------------------------------

    def save(
        self,
        summary: str,
        *,
        tags: Sequence[str],
        source: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
        memory_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        collection = self.collection(source)
        mid = memory_id or f"{source}_{uuid.uuid4().hex}"
        metadata: Dict[str, Any] = {
            "source": source,
            "tags": _tags_to_metadata(tags),
            "created_at": _now_iso(),
        }
        if extra_metadata:
            for k, v in extra_metadata.items():
                if k in metadata:
                    continue
                # ChromaDB only accepts scalar metadata.
                if isinstance(v, (str, int, float, bool)):
                    metadata[k] = v
                else:
                    metadata[k] = str(v)
        collection.upsert(
            documents=[summary],
            metadatas=[metadata],
            ids=[mid],
        )
        return {
            "ok": True,
            "memory_id": mid,
            "stored_chars": len(summary),
            "tags": list(tags),
            "source": source,
            "collection": collection.name,
        }

    # -- recall -------------------------------------------------------------

    def recall(
        self,
        query: str,
        *,
        limit: int,
        source: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        where = _build_where_filter(source=source, tags=tags)

        collections = []
        if source == "chat":
            collections.append(("chat_memory", self._chat))
        elif source in ("excel", "code", "doc"):
            collections.append(("project_index", self._project))
        else:
            collections.append(("chat_memory", self._chat))
            collections.append(("project_index", self._project))

        # Per-collection capacity guard: ChromaDB ``query`` requires
        # ``n_results <= count(collection)``. Asking for more on an empty
        # collection raises; we silently shrink instead.
        merged: List[Dict[str, Any]] = []
        for coll_name, coll in collections:
            try:
                count = coll.count()
            except Exception:
                count = 0
            if count <= 0:
                continue
            n = min(limit, count)
            try:
                raw = coll.query(
                    query_texts=[query],
                    n_results=n,
                    where=where,
                )
            except Exception as exc:
                logger.info("recall failed on %s: %s", coll_name, exc)
                continue
            merged.extend(_flatten_query_result(raw, coll_name))

        # Sort by distance (lower = more relevant) and trim to the global
        # limit — important when both collections returned hits.
        merged.sort(key=lambda h: h.get("distance", 1.0))
        merged = merged[:limit]
        for i, hit in enumerate(merged, start=1):
            hit["rank"] = i

        if source == "chat":
            source_label = f"ai_memory:{CHAT_COLLECTION_NAME}"
        elif source in ("excel", "code", "doc"):
            source_label = f"ai_memory:{PROJECT_COLLECTION_NAME}"
        else:
            source_label = "ai_memory:both"

        return {
            "source": source_label,
            "query": query,
            "limit": limit,
            "result_count": len(merged),
            "results": merged,
        }

    # -- counts (helper for tests + status endpoint) -----------------------

    def counts(self) -> Dict[str, int]:
        try:
            chat_count = self._chat.count()
        except Exception:
            chat_count = 0
        try:
            project_count = self._project.count()
        except Exception:
            project_count = 0
        return {
            CHAT_COLLECTION_NAME: chat_count,
            PROJECT_COLLECTION_NAME: project_count,
        }

    # -- direct metadata lookup (non-semantic) ------------------------------

    def get_entries(
        self,
        source: str,
        *,
        where: Optional[Dict[str, Any]] = None,
        ids: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Structured lookup bypassing the embedding model.

        Used by :mod:`dashboard_pipeline.ai.journal` for CRUD queries that
        filter by metadata (``journal_entry_type`` / ``journal_status`` /
        ``journal_kind`` / ``journal_due_date``) rather than by semantic
        similarity. Returns a flat list of hit dicts mirroring the shape
        produced by :func:`_flatten_query_result`, minus the ``distance``
        and ``rank`` fields (which are meaningless for non-semantic
        queries).
        """
        collection = self.collection(source)
        kwargs: Dict[str, Any] = {}
        if ids:
            kwargs["ids"] = list(ids)
        if where:
            kwargs["where"] = where
        if limit and limit > 0:
            kwargs["limit"] = int(limit)
        try:
            raw = collection.get(**kwargs)
        except Exception as exc:
            logger.info("get_entries failed on %s: %s", collection.name, exc)
            return []
        if not isinstance(raw, dict):
            return []
        got_ids = raw.get("ids") or []
        docs = raw.get("documents") or []
        metas = raw.get("metadatas") or []
        out: List[Dict[str, Any]] = []
        for i, mid in enumerate(got_ids):
            meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
            doc = docs[i] if i < len(docs) else ""
            out.append({
                "id": str(mid),
                "summary": doc if isinstance(doc, str) else str(doc),
                "tags": _tags_from_metadata(meta.get("tags")),
                "source": meta.get("source") or "",
                "created_at": meta.get("created_at") or "",
                "collection": collection.name,
                "metadata": {
                    k: v for k, v in meta.items()
                    if k not in {"tags", "source", "created_at"}
                },
            })
        return out

    def update_metadata(
        self,
        entry_id: str,
        source: str,
        *,
        patch: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Shallow-merge ``patch`` into the stored metadata for ``entry_id``.

        Re-uses the existing document + tags + created_at so semantic
        embeddings stay stable across status toggles. Returns the merged
        metadata on success, ``None`` if the entry does not exist.
        """
        collection = self.collection(source)
        try:
            raw = collection.get(ids=[entry_id])
        except Exception as exc:
            logger.info("update_metadata lookup failed: %s", exc)
            return None
        if not isinstance(raw, dict):
            return None
        ids = raw.get("ids") or []
        docs = raw.get("documents") or []
        metas = raw.get("metadatas") or []
        if not ids:
            return None
        existing_doc = docs[0] if docs else ""
        existing_meta = (
            dict(metas[0]) if metas and isinstance(metas[0], dict) else {}
        )
        for k, v in patch.items():
            if isinstance(v, (str, int, float, bool)):
                existing_meta[k] = v
            elif v is None:
                existing_meta[k] = ""
            else:
                existing_meta[k] = str(v)
        try:
            collection.upsert(
                documents=[existing_doc],
                metadatas=[existing_meta],
                ids=[entry_id],
            )
        except Exception as exc:
            logger.info("update_metadata upsert failed: %s", exc)
            return None
        return existing_meta

    def delete_entry(self, entry_id: str, source: str) -> bool:
        """Delete a single entry by id. Returns ``True`` if it existed."""
        collection = self.collection(source)
        try:
            raw = collection.get(ids=[entry_id])
        except Exception:
            return False
        existed = bool((raw or {}).get("ids"))
        if not existed:
            return False
        try:
            collection.delete(ids=[entry_id])
        except TypeError:
            # Fake collection may not accept ``ids`` kwarg in ``delete``.
            try:
                collection.delete(where={"__id__": {"$eq": entry_id}})
            except Exception:
                return False
        except Exception:
            return False
        return True


def _flatten_query_result(
    raw: Any,
    collection_name: str,
) -> List[Dict[str, Any]]:
    """Convert ChromaDB's nested query result into a flat hit list.

    ChromaDB returns ``{ids: [[..]], documents: [[..]], metadatas: [[..]],
    distances: [[..]]}`` — one outer list per query text. We always pass
    a single query so we read index 0.
    """
    if not isinstance(raw, dict):
        return []
    ids = (raw.get("ids") or [[]])[0]
    docs = (raw.get("documents") or [[]])[0]
    metas = (raw.get("metadatas") or [[]])[0]
    dists = (raw.get("distances") or [[]])[0]
    out: List[Dict[str, Any]] = []
    for i, mid in enumerate(ids):
        meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
        doc = docs[i] if i < len(docs) else ""
        dist = dists[i] if i < len(dists) else None
        try:
            distance = float(dist) if dist is not None else None
        except (TypeError, ValueError):
            distance = None
        out.append({
            "id": str(mid),
            "rank": 0,  # filled in by the caller after merging
            "distance": distance if distance is not None else 1.0,
            "summary": doc if isinstance(doc, str) else str(doc),
            "tags": _tags_from_metadata(meta.get("tags")),
            "source": meta.get("source") or "",
            "created_at": meta.get("created_at") or "",
            "collection": collection_name,
            "metadata": {
                k: v for k, v in meta.items()
                if k not in {"tags", "source", "created_at"}
            },
        })
    return out


# ---------------------------------------------------------------------------
# Process-level singleton (one store per project root)
# ---------------------------------------------------------------------------

_STORE_LOCK = threading.Lock()
_STORE_CACHE: Dict[str, MemoryStore] = {}


def get_memory_store(
    project_root: Optional[Path] = None,
    *,
    chromadb_module: Optional[Any] = None,
    embedding_function: Optional[Any] = None,
) -> MemoryStore:
    """Return (and cache) the :class:`MemoryStore` for ``project_root``.

    Tests can pass an explicit ``chromadb_module`` and ``embedding_function``
    to bypass the lazy loaders (useful for an in-memory / fake client).
    """
    persist_dir = resolve_persist_dir(project_root)
    cache_key = str(persist_dir)
    with _STORE_LOCK:
        cached = _STORE_CACHE.get(cache_key)
        if cached is not None:
            return cached

        cdb = chromadb_module or _load_chromadb()
        if cdb is None:
            raise MemoryStoreUnavailable(
                "`chromadb` ვერ ჩაიტვირთა — გაუშვი parent venv-ში: "
                "pip install chromadb sentence-transformers"
            )
        ef = embedding_function or _load_embedding_function()
        if ef is None:
            raise MemoryStoreUnavailable(
                "`sentence-transformers` embedding model ვერ ჩაიტვირთა — "
                "გაუშვი: pip install sentence-transformers"
            )
        store = MemoryStore(persist_dir, cdb, ef)
        _STORE_CACHE[cache_key] = store
        return store


def reset_memory_store() -> None:
    """Drop the cached store (tests + reload scenarios)."""
    with _STORE_LOCK:
        _STORE_CACHE.clear()


# ---------------------------------------------------------------------------
# Public tool entry points
# ---------------------------------------------------------------------------


def save_memory(
    summary: Any,
    *,
    tags: Any = None,
    source: Any = None,
    project_root: Optional[Path] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist a short text into the chat / project memory.

    Errors return ``{"error": ..., "hint": ...}`` so the agent loop can
    keep going.
    """
    text, err = _coerce_summary(summary)
    if err:
        return {"error": err}
    canonical_source, src_err = _coerce_source(source, default="chat")
    if src_err:
        return {"error": src_err}
    assert canonical_source is not None
    tag_list = _normalise_tags(tags)

    try:
        store = get_memory_store(project_root)
    except MemoryStoreUnavailable as exc:
        return {
            "error": str(exc),
            "hint": (
                "ChromaDB ან sentence-transformers ბიბლიოთეკა ვერ ჩაიტვირთა; "
                "parent venv-ში გაუშვი: pip install chromadb sentence-transformers"
            ),
        }
    except Exception as exc:  # pragma: no cover — defensive
        return {"error": f"მეხსიერების ბაზა ვერ გაიხსნა: {exc}"}

    try:
        result = store.save(
            text,
            tags=tag_list,
            source=canonical_source,
            extra_metadata=extra_metadata,
        )
    except Exception as exc:
        logger.warning("save_memory failed: %s", exc)
        return {"error": f"მეხსიერებაში ჩაწერა ვერ მოხერხდა: {exc}"}
    return result


def _render_recall_summary_ka(recall_result: Dict[str, Any]) -> str:
    """One-sentence Georgian summary of a ``recall_context`` payload.

    The AI's preferred surface — faster than narrating the raw JSON each turn.
    Distance is cosine (0 = perfect, 1 = unrelated); a close top hit should
    be called out so the AI can cite it.
    """
    query = str(recall_result.get("query") or "").strip()
    query_label = f"„{query}”" if query else "მოთხოვნა"
    count = int(recall_result.get("result_count") or 0)
    results = recall_result.get("results") or []

    if count == 0:
        return f"მეხსიერებაში {query_label}-ზე **შედეგი არ ვიპოვე**."

    top = results[0] if isinstance(results, list) and results else {}
    top_id = str(top.get("id") or "?")
    try:
        top_dist = float(top.get("distance", 1.0))
    except (TypeError, ValueError):
        top_dist = 1.0
    top_created = str(top.get("created_at") or "").strip()
    created_hint = f", {top_created}" if top_created else ""

    return (
        f"**{count} შედეგი** {query_label}-ზე. Top match: `{top_id}` "
        f"(distance {top_dist:.2f}{created_hint})."
    )


def recall_context(
    query: Any,
    *,
    limit: Any = None,
    source: Any = None,
    tags: Any = None,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Top-K semantic recall across chat memory and the project index."""
    text, err = _coerce_query(query)
    if err:
        return {"error": err}
    requested_limit = _coerce_limit(limit)

    canonical_source: Optional[str]
    if source is None:
        canonical_source = None
    else:
        canonical_source, src_err = _coerce_source(source, default="chat")
        if src_err:
            return {"error": src_err}

    tag_list = _normalise_tags(tags) or None

    try:
        store = get_memory_store(project_root)
    except MemoryStoreUnavailable as exc:
        return {
            "error": str(exc),
            "hint": (
                "ChromaDB ან sentence-transformers ბიბლიოთეკა ვერ ჩაიტვირთა; "
                "parent venv-ში გაუშვი: pip install chromadb sentence-transformers"
            ),
        }
    except Exception as exc:  # pragma: no cover — defensive
        return {"error": f"მეხსიერების ბაზა ვერ გაიხსნა: {exc}"}

    try:
        result = store.recall(
            text,
            limit=requested_limit,
            source=canonical_source,
            tags=tag_list,
        )
    except Exception as exc:
        logger.warning("recall_context failed: %s", exc)
        return {"error": f"მეხსიერებაში ძიება ვერ მოხერხდა: {exc}"}

    result["summary_ka"] = _render_recall_summary_ka(result)
    return result


# ---------------------------------------------------------------------------
# Bulk indexing helper (used by index_project_files.py and tests)
# ---------------------------------------------------------------------------


def index_project_files(
    file_specs: Sequence[Dict[str, Any]],
    *,
    project_root: Optional[Path] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    replace: bool = False,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> Dict[str, Any]:
    """Index a batch of files into the project_index collection.

    ``file_specs`` is a list of dicts with at least::

        {
            "path": "Financial_Analysis/.../1--2025.xls",
            "text": "<the full pre-extracted text>",
            "tags": ["excel", "year:2025", "category:waybills"],
        }

    Pre-extracting text outside this function keeps ``memory.py`` free of
    pandas / openpyxl coupling — :mod:`index_project_files` (the script)
    handles the Excel→text conversion.

    When ``replace=True`` the existing entries for each ``path`` are
    deleted before the new chunks are upserted (handy when re-indexing
    after a file change).
    """
    if not file_specs:
        return {"ok": True, "files": 0, "chunks": 0, "results": []}

    try:
        store = get_memory_store(project_root)
    except MemoryStoreUnavailable as exc:
        return {
            "error": str(exc),
            "hint": (
                "ChromaDB ან sentence-transformers ბიბლიოთეკა ვერ ჩაიტვირთა; "
                "parent venv-ში გაუშვი: pip install chromadb sentence-transformers"
            ),
        }

    project_collection = store.collection("excel")
    file_results: List[Dict[str, Any]] = []
    total_chunks = 0

    for spec in file_specs:
        path = str(spec.get("path") or "").strip()
        text = spec.get("text") or ""
        tags = _normalise_tags(spec.get("tags"))
        source = "excel"  # project_index source bucket
        if not path or not isinstance(text, str) or not text.strip():
            file_results.append({
                "path": path,
                "ok": False,
                "error": "ცარიელი ტექსტი ან path",
                "chunks": 0,
            })
            continue

        if replace:
            try:
                project_collection.delete(where={"path": {"$eq": path}})
            except Exception as exc:
                logger.info("delete-before-replace failed for %s: %s", path, exc)

        chunks = _chunk_text(text, chunk_chars, chunk_overlap)
        if len(chunks) > MAX_INDEX_CHUNKS_PER_FILE:
            chunks = chunks[:MAX_INDEX_CHUNKS_PER_FILE]

        header = _build_chunk_header(path, tags)
        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        # Unicode-safe identifier: a fixed-length SHA256 digest over the
        # full path (including Georgian characters). The previous
        # ``re.sub(r"[^a-z0-9]+", ..., path.lower())`` approach stripped every
        # Georgian character, collapsing e.g. ``ბოგ ბანკი ამონაწერი/2023.xlsx``
        # and ``თბს ბანკი ამონაწერი/2023.xlsx`` into the same
        # ``financial_analysis_2023_xlsx`` token and causing chunks from one
        # file to silently overwrite another on ``upsert``.
        path_token = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
        for idx, chunk in enumerate(chunks):
            ids.append(f"excel::{path_token}::{idx}")
            # Prepend the header so the embedding picks up the file name,
            # year, and Georgian category even when the chunk body is
            # mostly numeric cell values.
            documents.append(f"{header}{chunk}" if header else chunk)
            metadatas.append({
                "source": source,
                "path": path,
                "chunk_index": idx,
                "chunk_total": len(chunks),
                "tags": _tags_to_metadata(tags),
                "created_at": _now_iso(),
            })
        if not ids:
            file_results.append({
                "path": path,
                "ok": True,
                "chunks": 0,
                "tags": tags,
            })
            if on_progress:
                on_progress({"path": path, "chunks": 0, "ok": True})
            continue

        try:
            project_collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
        except Exception as exc:
            logger.warning("index upsert failed for %s: %s", path, exc)
            file_results.append({
                "path": path,
                "ok": False,
                "error": str(exc),
                "chunks": 0,
            })
            if on_progress:
                on_progress({"path": path, "ok": False, "error": str(exc)})
            continue

        total_chunks += len(ids)
        file_results.append({
            "path": path,
            "ok": True,
            "chunks": len(ids),
            "tags": tags,
        })
        if on_progress:
            on_progress({"path": path, "ok": True, "chunks": len(ids)})

    return {
        "ok": True,
        "files": len(file_results),
        "chunks": total_chunks,
        "results": file_results,
    }


__all__ = [
    "DEFAULT_MEMORY_DIRNAME",
    "CHAT_COLLECTION_NAME",
    "PROJECT_COLLECTION_NAME",
    "EMBEDDING_MODEL_NAME",
    "MIN_SUMMARY_CHARS",
    "MAX_SUMMARY_CHARS",
    "MAX_QUERY_CHARS",
    "DEFAULT_RECALL_LIMIT",
    "MAX_RECALL_LIMIT",
    "ALLOWED_SOURCES",
    "DEFAULT_CHUNK_CHARS",
    "DEFAULT_CHUNK_OVERLAP",
    "MAX_INDEX_CHUNKS_PER_FILE",
    "MemoryStore",
    "MemoryStoreUnavailable",
    "resolve_persist_dir",
    "get_memory_store",
    "reset_memory_store",
    "save_memory",
    "recall_context",
    "index_project_files",
]
