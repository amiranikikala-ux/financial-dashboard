"""Regression tests for Phase 0B Sprint 3 — semantic memory + project RAG.

Pins the stable contract exposed to Anthropic + the LLM:

* `TOOL_SCHEMAS` registration + position + count (8 → 10 → 13 in Sprint 4).
* `RECALL_CONTEXT_TOOL` + `SAVE_MEMORY_TOOL` schema shape: query/summary
  required, limit bounds, source enums, additionalProperties off.
* Tag normalisation + summary/query coercion edge cases.
* `_build_where_filter` AND-clauses for source + tags.
* `_chunk_text` boundary behaviour (empty / overlap / oversized).
* Round-trip save → recall against a fake in-process ChromaDB stub
  (the real client + sentence-transformers wheel are too heavy for unit
  tests; the fake mirrors the subset of the public API we use).
* `index_project_files` chunking, replace=True semantics, on_progress hook.
* `ToolDispatcher.dispatch("recall_context"/"save_memory", ...)` routes
  through the lazy import without crashing.
* Prompt wiring: chat prompt mentions both new tools + 🔎 section, while
  the investigator prompt is unchanged (Sprint 3 lives in chat mode only).

Tests use a `monkeypatch`-installed fake `chromadb` module + a no-op
embedding function so they run in milliseconds and require zero on-disk
persistence (every store flows through `tmp_path`).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from dashboard_pipeline.ai import memory as mem
from dashboard_pipeline.ai import prompts as prompts_mod
from dashboard_pipeline.ai.memory import (
    ALLOWED_SOURCES,
    CHAT_COLLECTION_NAME,
    DEFAULT_CHUNK_CHARS,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_RECALL_LIMIT,
    MAX_INDEX_CHUNKS_PER_FILE,
    MAX_QUERY_CHARS,
    MAX_RECALL_LIMIT,
    MAX_SUMMARY_CHARS,
    MIN_RECALL_LIMIT,
    MIN_SUMMARY_CHARS,
    PROJECT_COLLECTION_NAME,
    _build_where_filter,
    _chunk_text,
    _coerce_limit,
    _coerce_query,
    _coerce_source,
    _coerce_summary,
    _normalise_tag,
    _normalise_tags,
    _tags_from_metadata,
    _tags_to_metadata,
    get_memory_store,
    index_project_files,
    recall_context,
    reset_memory_store,
    resolve_persist_dir,
    save_memory,
)
from dashboard_pipeline.ai.tools import (
    RECALL_CONTEXT_TOOL,
    SAVE_MEMORY_TOOL,
    TOOL_SCHEMAS,
    ToolDispatcher,
)


# ---------------------------------------------------------------------------
# Fake ChromaDB module + embedding function
# ---------------------------------------------------------------------------


class _FakeCollection:
    """Minimal stand-in for a `chromadb` Collection.

    Implements just enough of the API surface to satisfy
    :class:`MemoryStore`. Distances are computed deterministically from
    keyword overlap so we can reason about ranking without invoking a
    real embedding model.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._docs: Dict[str, Tuple[str, Dict[str, Any]]] = {}

    # -- ChromaDB compatibility --------------------------------------------

    def upsert(
        self,
        *,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> None:
        for i, mid in enumerate(ids):
            self._docs[mid] = (documents[i], dict(metadatas[i]))

    def add(self, **kwargs: Any) -> None:  # pragma: no cover — alias
        self.upsert(**kwargs)

    def query(
        self,
        *,
        query_texts: List[str],
        n_results: int,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        query = (query_texts or [""])[0].lower()
        words = [w for w in re.split(r"\W+", query) if w]
        items: List[Tuple[str, str, Dict[str, Any]]] = [
            (mid, doc, meta)
            for mid, (doc, meta) in self._docs.items()
            if _fake_matches(meta, where)
        ]

        def _distance(doc: str) -> float:
            doc_lower = doc.lower()
            hits = sum(1 for w in words if w and w in doc_lower)
            if not words:
                return 0.5
            return max(0.0, 1.0 - hits / len(words))

        scored = [(mid, doc, meta, _distance(doc)) for mid, doc, meta in items]
        scored.sort(key=lambda t: (t[3], t[0]))  # tie-break on id for stability
        scored = scored[:n_results]
        return {
            "ids": [[mid for mid, _, _, _ in scored]],
            "documents": [[doc for _, doc, _, _ in scored]],
            "metadatas": [[meta for _, _, meta, _ in scored]],
            "distances": [[dist for _, _, _, dist in scored]],
        }

    def count(self) -> int:
        return len(self._docs)

    def get(
        self,
        *,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Direct metadata lookup — used by MemoryStore.get_entries."""
        if ids is not None:
            candidates = [
                (mid, self._docs[mid][0], self._docs[mid][1])
                for mid in ids
                if mid in self._docs
            ]
        else:
            candidates = [
                (mid, doc, meta)
                for mid, (doc, meta) in self._docs.items()
                if _fake_matches(meta, where)
            ]
        if limit and limit > 0:
            candidates = candidates[:limit]
        return {
            "ids": [mid for mid, _, _ in candidates],
            "documents": [doc for _, doc, _ in candidates],
            "metadatas": [meta for _, _, meta in candidates],
        }

    def delete(
        self,
        *,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> None:
        if ids:
            for mid in ids:
                self._docs.pop(mid, None)
            return
        if not where:
            self._docs.clear()
            return
        to_drop = [
            mid for mid, (_doc, meta) in self._docs.items()
            if _fake_matches(meta, where)
        ]
        for mid in to_drop:
            self._docs.pop(mid, None)


def _fake_matches(meta: Dict[str, Any], where: Optional[Dict[str, Any]]) -> bool:
    if not where:
        return True
    if "$and" in where:
        return all(_fake_matches(meta, sub) for sub in where["$and"])
    if "$or" in where:
        return any(_fake_matches(meta, sub) for sub in where["$or"])
    for key, op in where.items():
        actual = meta.get(key)
        if not isinstance(op, dict):
            if actual != op:
                return False
            continue
        if "$eq" in op and actual != op["$eq"]:
            return False
        if "$ne" in op and actual == op["$ne"]:
            return False
        if "$contains" in op:
            needle = op["$contains"]
            if not isinstance(actual, str) or needle not in actual:
                return False
        if "$lt" in op:
            expected = op["$lt"]
            if actual is None:
                return False
            try:
                if not (actual < expected):
                    return False
            except TypeError:
                return False
        if "$lte" in op:
            expected = op["$lte"]
            if actual is None:
                return False
            try:
                if not (actual <= expected):
                    return False
            except TypeError:
                return False
        if "$gt" in op:
            expected = op["$gt"]
            if actual is None:
                return False
            try:
                if not (actual > expected):
                    return False
            except TypeError:
                return False
        if "$gte" in op:
            expected = op["$gte"]
            if actual is None:
                return False
            try:
                if not (actual >= expected):
                    return False
            except TypeError:
                return False
    return True


class _FakeClient:
    def __init__(self, path: str) -> None:
        self.path = path
        self._collections: Dict[str, _FakeCollection] = {}

    def get_or_create_collection(
        self,
        *,
        name: str,
        embedding_function: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> _FakeCollection:
        if name not in self._collections:
            self._collections[name] = _FakeCollection(name)
        return self._collections[name]


class _FakeChromaDB:
    def __init__(self) -> None:
        self._clients: Dict[str, _FakeClient] = {}

    def PersistentClient(self, *, path: str) -> _FakeClient:
        if path not in self._clients:
            self._clients[path] = _FakeClient(path)
        return self._clients[path]


class _NoopEmbeddingFunction:
    def __call__(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] * 8 for _ in texts]


@pytest.fixture(autouse=True)
def _isolated_memory_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Reset the singleton + install the fake chromadb module per-test."""
    fake_module = _FakeChromaDB()
    fake_ef = _NoopEmbeddingFunction()
    monkeypatch.setattr(mem, "_load_chromadb", lambda: fake_module)
    monkeypatch.setattr(mem, "_load_embedding_function", lambda: fake_ef)
    monkeypatch.setattr(mem, "_default_project_root", lambda: tmp_path)
    reset_memory_store()
    yield
    reset_memory_store()


# ---------------------------------------------------------------------------
# Tool schema registration
# ---------------------------------------------------------------------------


class TestMemoryToolSchemas:
    def test_recall_context_registered(self):
        names = [t["name"] for t in TOOL_SCHEMAS]
        assert "recall_context" in names

    def test_save_memory_registered(self):
        names = [t["name"] for t in TOOL_SCHEMAS]
        assert "save_memory" in names

    def test_tool_count_is_21(self):
        """Phase 4A grew TOOL_SCHEMAS 17 → 18; Phase 2.1 grew 18 → 19
        (+ compute_cash_flow_projection); Phase 2.2 grew 19 → 20
        (+ simulate_scenario); Phase 2.5 grew 20 → 21
        (+ analyze_product_profitability); Phase 2.6 grew 21 → 22
        (+ find_promotion_candidates); Phase 5.1 grew 22 → 25
        (+ 3 VAT reconciliation tools)."""
        assert len(TOOL_SCHEMAS) == 28  # Phase 3.8: +margin_radar

    def test_recall_context_position(self):
        # Sits right after forecast_revenue (index 3) — both are
        # context-fetching tools the chat prompt references together.
        assert TOOL_SCHEMAS[4]["name"] == "recall_context"

    def test_save_memory_position(self):
        assert TOOL_SCHEMAS[5]["name"] == "save_memory"

    def test_recall_context_schema_shape(self):
        props = RECALL_CONTEXT_TOOL["input_schema"]["properties"]
        assert "query" in props
        assert "limit" in props
        assert "source" in props
        assert "tags" in props
        assert RECALL_CONTEXT_TOOL["input_schema"]["required"] == ["query"]
        assert (
            RECALL_CONTEXT_TOOL["input_schema"]["additionalProperties"] is False
        )
        assert props["limit"]["minimum"] == 1
        assert props["limit"]["maximum"] == 50
        assert props["source"]["enum"] == ["chat", "excel"]

    def test_save_memory_schema_shape(self):
        props = SAVE_MEMORY_TOOL["input_schema"]["properties"]
        assert "summary" in props
        assert "tags" in props
        assert "source" in props
        assert SAVE_MEMORY_TOOL["input_schema"]["required"] == ["summary"]
        assert (
            SAVE_MEMORY_TOOL["input_schema"]["additionalProperties"] is False
        )
        # Tool-level save is restricted to chat (project_index entries
        # only get written by the offline indexing script).
        assert SAVE_MEMORY_TOOL["input_schema"]["properties"]["source"]["enum"] == ["chat"]

    def test_recall_description_lists_triggers(self):
        desc = RECALL_CONTEXT_TOOL["description"]
        assert "გახსოვს" in desc or "recall" in desc.lower()
        assert "data.json" in desc

    def test_save_description_distinguishes_when_to_call(self):
        desc = SAVE_MEMORY_TOOL["description"]
        assert "When to call" in desc or "When NOT to call" in desc
        assert "memory_id" in desc

    def test_module_exports_contain_new_helpers(self):
        for name in (
            "save_memory",
            "recall_context",
            "index_project_files",
            "MemoryStore",
            "MemoryStoreUnavailable",
            "get_memory_store",
            "reset_memory_store",
            "resolve_persist_dir",
        ):
            assert hasattr(mem, name), name


# ---------------------------------------------------------------------------
# Tag + input coercion
# ---------------------------------------------------------------------------


class TestNormaliseTags:
    def test_none_returns_empty(self):
        assert _normalise_tags(None) == []

    def test_list_input_dedupes_and_sorts(self):
        assert _normalise_tags(["B", "a", "b"]) == ["a", "b"]

    def test_string_input_split_on_comma(self):
        assert _normalise_tags("alpha,Beta, gamma") == ["alpha", "beta", "gamma"]

    def test_unsafe_chars_collapsed(self):
        assert _normalise_tags(["Topic: Cash Flow!"]) == ["topic:cash_flow"]

    def test_garbage_silently_dropped(self):
        # bad shapes (dict) collapse to a printable string then get
        # cleaned. The point of the test is "no exception".
        assert isinstance(_normalise_tags({"k": "v"}), list)

    def test_normalise_tag_strips_outer_underscores(self):
        assert _normalise_tag("___decision___") == "decision"

    def test_normalise_tag_returns_none_on_empty(self):
        assert _normalise_tag("") is None
        assert _normalise_tag("   ") is None


class TestCoerceSummary:
    def test_none_errors(self):
        text, err = _coerce_summary(None)
        assert text is None and err

    def test_non_string_errors(self):
        text, err = _coerce_summary(123)
        assert text is None and err

    def test_too_short_errors(self):
        text, err = _coerce_summary("abc")
        assert text is None and err
        assert str(MIN_SUMMARY_CHARS) in err

    def test_oversized_truncated(self):
        big = "x" * (MAX_SUMMARY_CHARS + 100)
        text, err = _coerce_summary(big)
        assert err is None
        assert text is not None
        assert len(text) <= MAX_SUMMARY_CHARS + 1  # +1 for the ellipsis char

    def test_happy_path(self):
        text, err = _coerce_summary("  Alpha-ს ვალი 23K, შევთანხმდით 50% წინასწარი  ")
        assert err is None
        assert text == "Alpha-ს ვალი 23K, შევთანხმდით 50% წინასწარი"


class TestCoerceQuery:
    def test_none_errors(self):
        q, err = _coerce_query(None)
        assert q is None and err

    def test_empty_errors(self):
        q, err = _coerce_query("   ")
        assert q is None and err

    def test_oversized_truncated(self):
        big = "ა" * (MAX_QUERY_CHARS + 50)
        q, err = _coerce_query(big)
        assert err is None
        assert q is not None and len(q) == MAX_QUERY_CHARS

    def test_happy_path(self):
        q, err = _coerce_query("გახსოვს Alpha-ს ვალი?")
        assert err is None
        assert q == "გახსოვს Alpha-ს ვალი?"


class TestCoerceLimit:
    def test_none_default(self):
        assert _coerce_limit(None) == DEFAULT_RECALL_LIMIT

    def test_garbage_falls_back_to_default(self):
        assert _coerce_limit("xyz") == DEFAULT_RECALL_LIMIT

    def test_below_min_clamped(self):
        assert _coerce_limit(-3) == MIN_RECALL_LIMIT

    def test_above_max_clamped(self):
        assert _coerce_limit(9999) == MAX_RECALL_LIMIT

    def test_in_range_passes_through(self):
        assert _coerce_limit(7) == 7


class TestCoerceSource:
    def test_none_keeps_default(self):
        src, err = _coerce_source(None, default="chat")
        assert src == "chat" and err is None

    def test_known_source_canonicalised(self):
        src, err = _coerce_source("EXCEL", default="chat")
        assert src == "excel" and err is None

    def test_unknown_errors(self):
        src, err = _coerce_source("notebook", default="chat")
        assert src is None and err

    def test_non_string_errors(self):
        src, err = _coerce_source(42, default="chat")
        assert src is None and err

    def test_empty_keeps_default(self):
        src, err = _coerce_source("   ", default="chat")
        assert src == "chat" and err is None

    def test_allowed_sources_immutable(self):
        assert ALLOWED_SOURCES == ("chat", "excel", "code", "doc")


# ---------------------------------------------------------------------------
# Where-filter + chunking
# ---------------------------------------------------------------------------


class TestBuildWhereFilter:
    def test_no_filters_returns_none(self):
        assert _build_where_filter(source=None, tags=None) is None

    def test_source_only(self):
        assert _build_where_filter(source="chat", tags=None) == {
            "source": {"$eq": "chat"}
        }

    def test_single_tag_only(self):
        assert _build_where_filter(source=None, tags=["alpha"]) == {
            "tags": {"$contains": "alpha"}
        }

    def test_multiple_tags_anded(self):
        result = _build_where_filter(source=None, tags=["alpha", "beta"])
        assert result is not None
        assert "$and" in result
        sub = result["$and"]
        assert {"tags": {"$contains": "alpha"}} in sub
        assert {"tags": {"$contains": "beta"}} in sub

    def test_source_plus_tags_anded(self):
        result = _build_where_filter(source="chat", tags=["alpha"])
        assert result is not None
        assert "$and" in result
        assert {"source": {"$eq": "chat"}} in result["$and"]
        assert {"tags": {"$contains": "alpha"}} in result["$and"]


class TestChunkText:
    def test_empty_input(self):
        assert _chunk_text("") == []

    def test_short_text_single_chunk(self):
        text = "abc"
        assert _chunk_text(text, chunk_chars=10, overlap=0) == ["abc"]

    def test_chunk_chars_zero_returns_single(self):
        text = "abc def"
        assert _chunk_text(text, chunk_chars=0) == [text]

    def test_long_text_splits_with_overlap(self):
        text = "ABCDEFGHIJKLMNOP"  # 16 chars
        chunks = _chunk_text(text, chunk_chars=8, overlap=2)
        assert len(chunks) >= 2
        assert chunks[0] == "ABCDEFGH"
        # second chunk starts with the last 2 chars of the first (overlap).
        assert chunks[1].startswith("GH")

    def test_overlap_clamped_when_too_large(self):
        text = "x" * 20
        chunks = _chunk_text(text, chunk_chars=4, overlap=99)
        assert all(len(c) <= 4 for c in chunks)


# ---------------------------------------------------------------------------
# Round-trip save → recall
# ---------------------------------------------------------------------------


class TestSaveMemoryHappyPath:
    def test_save_returns_memory_id_and_metadata(self):
        result = save_memory(
            "Alpha-ს ვალი 23,000 ₾ — 45 დღე გადაცილებული; შევთანხმდით 50% წინასწარი",
            tags=["kind:decision", "supplier:alpha"],
        )
        assert result["ok"] is True
        assert result["memory_id"].startswith("chat_")
        assert result["source"] == "chat"
        assert result["collection"] == CHAT_COLLECTION_NAME
        assert "kind:decision" in result["tags"]
        assert "supplier:alpha" in result["tags"]
        assert result["stored_chars"] > 0

    def test_save_then_recall_roundtrip(self):
        save_memory(
            "Beta-ს ფასდაკლების მოთხოვნა — 2026-04-15 დაუთანხმდა -3% მომდევნო კვარტალში",
            tags=["kind:agreement", "supplier:beta"],
        )
        result = recall_context("Beta-ს ფასდაკლება")
        assert "error" not in result
        assert result["result_count"] >= 1
        first = result["results"][0]
        assert first["rank"] == 1
        assert "Beta" in first["summary"]
        assert "supplier:beta" in first["tags"]

    def test_recall_filter_by_tag(self):
        save_memory("Alpha-ზე გადაწყვეტილება", tags=["supplier:alpha"])
        save_memory("Beta-ზე გადაწყვეტილება", tags=["supplier:beta"])
        result = recall_context("გადაწყვეტილება", tags=["supplier:alpha"])
        assert result["result_count"] == 1
        assert "Alpha" in result["results"][0]["summary"]

    def test_recall_filter_by_source_chat(self):
        save_memory("only chat memory entry here", tags=["kind:observation"])
        result = recall_context("chat memory entry", source="chat")
        assert result["source"] == f"ai_memory:{CHAT_COLLECTION_NAME}"
        assert result["result_count"] == 1

    def test_recall_empty_collection_returns_zero(self):
        result = recall_context("nothing saved yet")
        assert result["result_count"] == 0
        assert result["results"] == []

    def test_recall_limit_clamped(self):
        for i in range(7):
            save_memory(
                f"observation number {i} about supplier X" + "x" * 5,
                tags=["kind:observation"],
            )
        result = recall_context("observation supplier", limit=3)
        assert result["limit"] == 3
        assert result["result_count"] == 3
        ranks = [r["rank"] for r in result["results"]]
        assert ranks == [1, 2, 3]

    def test_recall_default_limit_is_5(self):
        for i in range(8):
            save_memory(
                f"placeholder entry {i} about cashflow" + "y" * 5,
                tags=["topic:cashflow"],
            )
        result = recall_context("cashflow placeholder")
        assert result["limit"] == DEFAULT_RECALL_LIMIT
        assert result["result_count"] == DEFAULT_RECALL_LIMIT

    def test_save_idempotent_with_explicit_id(self):
        store = get_memory_store()
        store.save(
            "first version of the same memory",
            tags=["kind:observation"],
            source="chat",
            memory_id="fixed_id_123",
        )
        store.save(
            "second version replaces the first",
            tags=["kind:observation"],
            source="chat",
            memory_id="fixed_id_123",
        )
        counts = store.counts()
        assert counts[CHAT_COLLECTION_NAME] == 1


class TestSaveMemoryErrorPaths:
    def test_summary_required(self):
        result = save_memory(None)
        assert "error" in result

    def test_summary_too_short_blocked(self):
        result = save_memory("ok")
        assert "error" in result

    def test_unknown_source_blocked(self):
        result = save_memory("a long enough summary", source="dropbox")
        assert "error" in result

    def test_chromadb_unavailable_propagates(self, monkeypatch):
        monkeypatch.setattr(mem, "_load_chromadb", lambda: None)
        reset_memory_store()
        result = save_memory("a long enough summary")
        assert "error" in result and "chromadb" in result["error"].lower()
        assert "hint" in result

    def test_embedding_unavailable_propagates(self, monkeypatch):
        monkeypatch.setattr(mem, "_load_embedding_function", lambda: None)
        reset_memory_store()
        result = save_memory("a long enough summary")
        assert "error" in result
        assert "hint" in result


class TestRecallContextErrorPaths:
    def test_query_required(self):
        result = recall_context(None)
        assert "error" in result

    def test_unknown_source_rejected(self):
        result = recall_context("anything", source="dropbox")
        assert "error" in result

    def test_chromadb_unavailable_propagates(self, monkeypatch):
        monkeypatch.setattr(mem, "_load_chromadb", lambda: None)
        reset_memory_store()
        result = recall_context("anything")
        assert "error" in result
        assert "hint" in result


# ---------------------------------------------------------------------------
# Project indexing
# ---------------------------------------------------------------------------


class TestIndexProjectFiles:
    def test_empty_specs_returns_zero(self):
        result = index_project_files([])
        assert result == {"ok": True, "files": 0, "chunks": 0, "results": []}

    def test_indexes_chunks_and_reports_counts(self):
        big_text = "row data " * 400  # ~3200 chars → multiple chunks
        result = index_project_files([
            {
                "path": "Financial_Analysis/რს ზედნადები/01--2025.xls",
                "text": big_text,
                "tags": ["excel", "year:2025"],
            }
        ])
        assert result["ok"] is True
        assert result["files"] == 1
        assert result["chunks"] >= 2
        store = get_memory_store()
        assert store.counts()[PROJECT_COLLECTION_NAME] == result["chunks"]

    def test_replace_true_drops_old_chunks(self):
        spec_v1 = {
            "path": "Financial_Analysis/test.xls",
            "text": "first content " * 200,
            "tags": ["excel"],
        }
        index_project_files([spec_v1])
        first_count = get_memory_store().counts()[PROJECT_COLLECTION_NAME]

        spec_v2 = {
            "path": "Financial_Analysis/test.xls",
            "text": "shorter",
            "tags": ["excel"],
        }
        result = index_project_files([spec_v2], replace=True)
        assert result["ok"] is True
        # After replace, only the (single) v2 chunk remains.
        assert get_memory_store().counts()[PROJECT_COLLECTION_NAME] == 1
        assert first_count >= 1

    def test_on_progress_called_per_file(self):
        seen: List[Dict[str, Any]] = []
        index_project_files(
            [
                {"path": "a.xls", "text": "alpha " * 50, "tags": []},
                {"path": "b.xls", "text": "beta " * 50, "tags": []},
            ],
            on_progress=lambda evt: seen.append(evt),
        )
        assert len(seen) == 2
        assert {evt["path"] for evt in seen} == {"a.xls", "b.xls"}

    def test_empty_text_is_skipped_with_error(self):
        result = index_project_files([
            {"path": "empty.xls", "text": "", "tags": []},
        ])
        assert result["ok"] is True
        assert result["files"] == 1
        assert result["chunks"] == 0
        assert result["results"][0]["ok"] is False

    def test_chunks_capped_at_max(self):
        # 5_000_000 chars / DEFAULT_CHUNK_CHARS would exceed the cap.
        huge = "x" * (DEFAULT_CHUNK_CHARS * (MAX_INDEX_CHUNKS_PER_FILE + 5))
        result = index_project_files([
            {"path": "huge.xls", "text": huge, "tags": []},
        ])
        # Effective indexed chunks must respect the safety cap.
        assert result["chunks"] <= MAX_INDEX_CHUNKS_PER_FILE

    def test_recall_finds_indexed_excel_chunk(self):
        index_project_files([
            {
                "path": "Financial_Analysis/რს ზედნადები/10--2025.xls",
                "text": "Beta-ს 2025 ოქტომბრის ზედნადები ჯამი 14,300 ₾ — 12 ცალი",
                "tags": ["excel", "year:2025", "supplier:beta"],
            }
        ])
        result = recall_context(
            "Beta 2025 ოქტომბერი ზედნადები",
            source="excel",
        )
        assert "error" not in result
        assert result["result_count"] >= 1
        assert "Beta" in result["results"][0]["summary"]
        assert result["source"] == f"ai_memory:{PROJECT_COLLECTION_NAME}"


# ---------------------------------------------------------------------------
# Dispatcher routing
# ---------------------------------------------------------------------------


class TestDispatcherRouting:
    def _make_dispatcher(self) -> ToolDispatcher:
        # Minimal data loader — recall/save don't read data.json, but the
        # dispatcher requires a callable.
        return ToolDispatcher(data_loader=lambda: {})

    def test_save_then_recall_via_dispatcher(self):
        d = self._make_dispatcher()
        save_result = d.dispatch(
            "save_memory",
            {
                "summary": "POS terminal Ozurgeti #2 ჩაიხშო 6 აპრ. 4 საათი — სავარაუდოდ -7,000 ₾ lost sales",
                "tags": ["kind:observation", "topic:pos"],
            },
        )
        assert save_result["ok"] is True
        recall_result = d.dispatch(
            "recall_context",
            {"query": "POS Ozurgeti ჩაიხშო", "limit": 3},
        )
        assert "error" not in recall_result
        assert recall_result["result_count"] >= 1
        assert "POS" in recall_result["results"][0]["summary"]

    def test_dispatcher_records_calls(self):
        d = self._make_dispatcher()
        d.dispatch("save_memory", {"summary": "alpha decision long enough text"})
        d.dispatch("recall_context", {"query": "alpha"})
        names = [c["tool"] for c in d.calls]
        assert names == ["save_memory", "recall_context"]
        assert all(c["result_summary"]["ok"] for c in d.calls)


# ---------------------------------------------------------------------------
# Prompt + module wiring
# ---------------------------------------------------------------------------


class TestPromptWiring:
    def test_chat_prompt_mentions_memory_section(self):
        prompt = prompts_mod.SYSTEM_PROMPT_KA
        assert "🔎" in prompt
        assert "recall_context" in prompt
        assert "save_memory" in prompt
        assert "გახსოვს" in prompt

    def test_investigator_prompt_unchanged(self):
        # Sprint 3 lives in chat mode only; do not regress investigator.
        inv = prompts_mod.SYSTEM_PROMPT_KA_INVESTIGATOR
        assert "recall_context" not in inv
        assert "save_memory" not in inv

    def test_chat_prompt_warns_when_recall_fails(self):
        prompt = prompts_mod.SYSTEM_PROMPT_KA
        assert "ცრუ recall" in prompt or "ვერ ვიპოვე" in prompt


class TestModuleConstants:
    def test_resolve_persist_dir_under_project_root(self, tmp_path: Path):
        path = resolve_persist_dir(tmp_path)
        assert path.parent == tmp_path
        assert path.name == "ai_vectors"

    def test_chat_collection_constant(self):
        assert CHAT_COLLECTION_NAME == "chat_memory"

    def test_project_collection_constant(self):
        assert PROJECT_COLLECTION_NAME == "project_index"

    def test_chunk_overlap_smaller_than_chunk(self):
        assert DEFAULT_CHUNK_OVERLAP < DEFAULT_CHUNK_CHARS

    def test_min_summary_below_max(self):
        assert MIN_SUMMARY_CHARS < MAX_SUMMARY_CHARS

    def test_get_memory_store_caches(self):
        first = get_memory_store()
        second = get_memory_store()
        assert first is second

    def test_reset_memory_store_drops_cache(self):
        first = get_memory_store()
        reset_memory_store()
        second = get_memory_store()
        assert first is not second


# ---------------------------------------------------------------------------
# Tag round-trip helpers
# ---------------------------------------------------------------------------


class TestTagMetadataRoundtrip:
    def test_encode_decode_roundtrip(self):
        encoded = _tags_to_metadata(["alpha", "beta", "gamma"])
        decoded = _tags_from_metadata(encoded)
        assert decoded == ["alpha", "beta", "gamma"]

    def test_decode_handles_missing(self):
        assert _tags_from_metadata(None) == []
        assert _tags_from_metadata("") == []

    def test_decode_handles_non_string(self):
        assert _tags_from_metadata(42) == []
