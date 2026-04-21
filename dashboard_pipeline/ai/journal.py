"""Phase 0B Sprint 4 — Decision Journal.

Structured CRUD over the same ChromaDB ``chat_memory`` collection used
by :mod:`dashboard_pipeline.ai.memory`. Journal entries are semantically
searchable through the regular ``recall_context`` path (they carry the
``journal`` tag) *and* queryable by structured filters (status / kind /
due_date) through :func:`list_journal_entries`, which calls
:meth:`MemoryStore.get_entries` directly and skips the embedding model
entirely.

Public API
----------

::

    add_journal_entry(title, kind, *, due_date=None, tags=None,
                      source_memory_id=None, project_root=None)
    list_journal_entries(*, status=None, kind=None, overdue=None,
                         due_before=None, due_after=None,
                         limit=None, today=None, project_root=None)
    update_journal_entry(entry_id, *, status, project_root=None)
    delete_journal_entry(entry_id, *, project_root=None)

Return contracts
----------------

``add_journal_entry`` success::

    {
        "ok": True,
        "entry_id": "journal_<uuid>",
        "title": "<echoed>",
        "kind": "promise" | "ai_commitment" | "recommendation" | "reminder",
        "status": "open",
        "due_date": "YYYY-MM-DD" | "",
        "created_at": "<iso>",
        "tags": ["journal", "kind:promise", "status:open", ...],
    }

``list_journal_entries`` success::

    {
        "count": N,
        "entries": [
            {
                "entry_id": "journal_<uuid>",
                "title": "<text>",
                "kind": "...",
                "status": "...",
                "due_date": "YYYY-MM-DD" | "",
                "created_at": "<iso>",
                "overdue_days": int | None,  # positive = overdue, None = no due date
                "tags": [...],
            },
            ...
        ],
    }

``update_journal_entry`` success::

    {
        "ok": True,
        "entry_id": "...",
        "status": "done" | "cancelled",
        "previous_status": "open",
        "tags": [...],
    }

``delete_journal_entry`` success::

    {"ok": True, "entry_id": "...", "existed": True}

Failure (any function)::

    {"error": "<Georgian message>", "hint": "<usage / install hint>"}
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


from dashboard_pipeline.ai import memory as _memory


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public contract constants
# ---------------------------------------------------------------------------

#: Allowed ``kind`` values. These are authoritative — any other value is
#: rejected at add / update time.
JOURNAL_KINDS: Tuple[str, ...] = (
    "promise",           # user committed ("მე ვიკისრებ")
    "ai_commitment",     # AI committed ("შემდეგ ჩატში გადავამოწმებ")
    "recommendation",    # AI suggested + outcome-tracked
    "reminder",          # dated, externally-triggered (VAT, bank, etc.)
    "proposal",          # Phase 3.1 Co-Designer — AI-generated feature proposal
    "repayment_plan",    # Phase 4A Debt Plan — user-approved payment schedule
)

JOURNAL_STATUSES: Tuple[str, ...] = ("open", "done", "cancelled")

#: Phase 3.1 Co-Designer — proposal kind requires these six fields. All six
#: must be populated by the AI via ``propose_feature`` / ``add_journal_entry``
#: with ``kind='proposal'``. They land as flat ChromaDB metadata keys so the
#: existing ``MemoryStore.get_entries`` path returns them without extra work.
PROPOSAL_KIND = "proposal"

#: Auto-cleanup threshold — open proposals older than this many days are
#: transitioned to ``status='cancelled'`` on the next
#: ``list_journal_entries(kind='proposal')`` call so the journal doesn't
#: bloat when the user ignores or defers a batch of suggestions.
PROPOSAL_AUTO_CLEANUP_DAYS = 30

DEFAULT_STATUS = "open"

MIN_TITLE_CHARS = 3
MAX_TITLE_CHARS = 500

#: Per-field length bounds for the six structured proposal payload fields.
#: ``time_estimate`` can be compact ("2-3 დღე"); the rest need room to breathe.
MIN_PROPOSAL_FIELD_CHARS = 5
MAX_PROPOSAL_FIELD_CHARS = 1000

DEFAULT_LIST_LIMIT = 20
MIN_LIST_LIMIT = 1
MAX_LIST_LIMIT = 100

#: Metadata discriminator — separates journal entries from regular
#: ``save_memory`` summaries (both land in ``chat_memory``).
META_ENTRY_TYPE_KEY = "journal_entry_type"
META_ENTRY_TYPE_VALUE = "journal"

META_KIND_KEY = "journal_kind"
META_STATUS_KEY = "journal_status"
META_DUE_DATE_KEY = "journal_due_date"
META_TITLE_KEY = "journal_title"
META_SOURCE_MEMORY_ID_KEY = "journal_source_memory_id"

#: Phase 3.1 — structured 6-field proposal payload metadata keys.
META_PROPOSAL_PROBLEM_KEY = "proposal_problem"
META_PROPOSAL_BENEFIT_KEY = "proposal_benefit"
META_PROPOSAL_MVP_KEY = "proposal_mvp"
META_PROPOSAL_DATA_KEY = "proposal_data_needed"
META_PROPOSAL_TIME_KEY = "proposal_time_estimate"
META_PROPOSAL_RISK_KEY = "proposal_risk_critique"

_PROPOSAL_META_KEYS: Tuple[str, ...] = (
    META_PROPOSAL_PROBLEM_KEY,
    META_PROPOSAL_BENEFIT_KEY,
    META_PROPOSAL_MVP_KEY,
    META_PROPOSAL_DATA_KEY,
    META_PROPOSAL_TIME_KEY,
    META_PROPOSAL_RISK_KEY,
)

#: Ordered field names mirroring ``_PROPOSAL_META_KEYS`` for kwarg-to-metadata
#: translation in ``add_journal_entry`` + LLM-facing error messages.
_PROPOSAL_FIELD_NAMES: Tuple[str, ...] = (
    "problem",
    "benefit",
    "mvp_scope",
    "data_needed",
    "time_estimate",
    "risk_critique",
)

#: Tag marker every journal entry carries. Makes the semantic recall path
#: (``recall_context(tags=["journal"])``) surface them without needing to
#: know the internal metadata schema.
JOURNAL_TAG_MARKER = "journal"

#: ID prefix so journal entries are visually distinct from free-form
#: ``save_memory`` summaries.
JOURNAL_ID_PREFIX = "journal"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------


def _coerce_title(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """Validate + trim a journal title. Returns ``(text, error)``."""
    if raw is None:
        return None, "`title` სავალდებულოა — რამდენიმე სიტყვით აღწერე."
    if not isinstance(raw, str):
        return None, "`title` უნდა იყოს ტექსტი."
    text = raw.strip()
    if len(text) < MIN_TITLE_CHARS:
        return None, (
            f"`title` ძალიან მოკლეა (მინიმუმ {MIN_TITLE_CHARS} სიმბოლო)."
        )
    if len(text) > MAX_TITLE_CHARS:
        text = text[:MAX_TITLE_CHARS].rstrip() + "…"
    return text, None


def _coerce_kind(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """Strict enum coercion for ``kind``."""
    if raw is None:
        return None, (
            f"`kind` სავალდებულოა — დასაშვებია: {list(JOURNAL_KINDS)}."
        )
    if not isinstance(raw, str):
        return None, f"`kind` უნდა იყოს ტექსტი ({list(JOURNAL_KINDS)})."
    value = raw.strip().lower()
    if value not in JOURNAL_KINDS:
        return None, (
            f"`kind`='{raw}' უცნობია. დასაშვებია: {list(JOURNAL_KINDS)}."
        )
    return value, None


def _coerce_status(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """Strict enum coercion for ``status``."""
    if raw is None:
        return None, (
            f"`status` სავალდებულოა — დასაშვებია: {list(JOURNAL_STATUSES)}."
        )
    if not isinstance(raw, str):
        return None, f"`status` უნდა იყოს ტექსტი ({list(JOURNAL_STATUSES)})."
    value = raw.strip().lower()
    if value not in JOURNAL_STATUSES:
        return None, (
            f"`status`='{raw}' უცნობია. დასაშვებია: {list(JOURNAL_STATUSES)}."
        )
    return value, None


def _coerce_due_date(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """Validate a due date. Returns ``(iso_or_empty, error)``.

    Accepts ``None`` / empty string → ``""`` (no due date). Accepts a
    ``datetime.date`` or ``datetime.datetime`` instance and coerces to
    ISO. Accepts a string that parses as ``YYYY-MM-DD``.
    """
    if raw is None:
        return "", None
    if isinstance(raw, _dt.datetime):
        return raw.date().isoformat(), None
    if isinstance(raw, _dt.date):
        return raw.isoformat(), None
    if not isinstance(raw, str):
        return None, "`due_date` უნდა იყოს YYYY-MM-DD ან ცარიელი."
    text = raw.strip()
    if not text:
        return "", None
    if not _DATE_RE.match(text):
        return None, (
            f"`due_date`='{raw}' არასწორი ფორმატია. გამოიყენე YYYY-MM-DD."
        )
    try:
        _dt.date.fromisoformat(text)
    except ValueError:
        return None, f"`due_date`='{raw}' არავალიდური თარიღია."
    return text, None


def _coerce_list_limit(raw: Any) -> int:
    if raw is None:
        return DEFAULT_LIST_LIMIT
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LIST_LIMIT
    return max(MIN_LIST_LIMIT, min(value, MAX_LIST_LIMIT))


def _coerce_proposal_field(
    raw: Any, *, field_name: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Validate one of the six structured proposal-payload fields.

    Returns ``(trimmed_text, None)`` on success or ``(None, error_ka)`` on
    rejection. Truncates silently at ``MAX_PROPOSAL_FIELD_CHARS`` so the AI
    never OOM-s our ChromaDB metadata row.
    """
    if raw is None:
        return None, (
            f"`{field_name}` სავალდებულოა proposal-ისთვის — რამდენიმე წინადადებით "
            "აღწერე."
        )
    if not isinstance(raw, str):
        return None, f"`{field_name}` უნდა იყოს ტექსტი."
    text = raw.strip()
    if len(text) < MIN_PROPOSAL_FIELD_CHARS:
        return None, (
            f"`{field_name}` ძალიან მოკლეა (მინიმუმ {MIN_PROPOSAL_FIELD_CHARS} "
            "სიმბოლო) — მიეცი AI-ს საკმარისი კონტექსტი."
        )
    if len(text) > MAX_PROPOSAL_FIELD_CHARS:
        text = text[:MAX_PROPOSAL_FIELD_CHARS].rstrip() + "…"
    return text, None


def _coerce_today(raw: Any) -> _dt.date:
    """Accept a ``date`` / ``datetime`` / ISO string / None."""
    if raw is None:
        return _dt.date.today()
    if isinstance(raw, _dt.datetime):
        return raw.date()
    if isinstance(raw, _dt.date):
        return raw
    if isinstance(raw, str) and _DATE_RE.match(raw.strip()):
        try:
            return _dt.date.fromisoformat(raw.strip())
        except ValueError:
            pass
    return _dt.date.today()


def _normalise_extra_tags(raw: Any, *, kind: str, status: str) -> List[str]:
    """Ensure the three structural journal tags + any user-supplied tags.

    User tags are normalised through :func:`memory._normalise_tags`. Any
    supplied ``kind:*`` or ``status:*`` tokens are dropped — the canonical
    values come from ``kind`` and ``status`` arguments so they can never
    drift from the metadata record.
    """
    base = _memory._normalise_tags(raw)
    stripped = [
        t for t in base
        if not t.startswith("kind:") and not t.startswith("status:") and t != JOURNAL_TAG_MARKER
    ]
    canonical = [
        JOURNAL_TAG_MARKER,
        f"kind:{kind}",
        f"status:{status}",
    ]
    merged = list(canonical)
    for t in stripped:
        if t not in merged:
            merged.append(t)
    return merged


def _store_or_error() -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
    """Resolve the memory store singleton or return a Georgian error dict."""
    try:
        return _memory.get_memory_store(), None
    except _memory.MemoryStoreUnavailable as exc:
        return None, {
            "error": str(exc),
            "hint": (
                "ChromaDB ან sentence-transformers ბიბლიოთეკა ვერ ჩაიტვირთა; "
                "parent venv-ში გაუშვი: pip install chromadb sentence-transformers"
            ),
        }
    except Exception as exc:  # pragma: no cover — defensive
        return None, {"error": f"ჟურნალის ბაზა ვერ გაიხსნა: {exc}"}


# ---------------------------------------------------------------------------
# add_journal_entry
# ---------------------------------------------------------------------------


def add_journal_entry(
    title: Any,
    kind: Any,
    *,
    due_date: Any = None,
    tags: Any = None,
    source_memory_id: Any = None,
    # Phase 3.1 Co-Designer — all six required when ``kind='proposal'``.
    # Passing any of these with a non-proposal ``kind`` is rejected so
    # the journal schema stays clean.
    problem: Any = None,
    benefit: Any = None,
    mvp_scope: Any = None,
    data_needed: Any = None,
    time_estimate: Any = None,
    risk_critique: Any = None,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Persist a new journal entry in the chat memory collection.

    When ``kind='proposal'`` the six ``problem`` / ``benefit`` / ``mvp_scope``
    / ``data_needed`` / ``time_estimate`` / ``risk_critique`` kwargs are
    mandatory and stored as flat ChromaDB metadata keys (see
    ``_PROPOSAL_META_KEYS``). All other ``kind`` values MUST leave those
    kwargs as ``None`` — mixing proposal fields into a non-proposal entry
    is rejected with a Georgian error.
    """
    text, err = _coerce_title(title)
    if err:
        return {"error": err}
    assert text is not None
    canonical_kind, err = _coerce_kind(kind)
    if err:
        return {"error": err}
    assert canonical_kind is not None
    canonical_due, err = _coerce_due_date(due_date)
    if err:
        return {"error": err}
    assert canonical_due is not None

    # Phase 3.1 — validate proposal fields against kind.
    proposal_raw: Dict[str, Any] = {
        "problem": problem,
        "benefit": benefit,
        "mvp_scope": mvp_scope,
        "data_needed": data_needed,
        "time_estimate": time_estimate,
        "risk_critique": risk_critique,
    }
    any_proposal_field = any(v is not None for v in proposal_raw.values())
    canonical_proposal: Dict[str, str] = {}
    if canonical_kind == PROPOSAL_KIND:
        # Every proposal field is mandatory — no partial entries.
        for field_name in _PROPOSAL_FIELD_NAMES:
            coerced, err = _coerce_proposal_field(
                proposal_raw[field_name], field_name=field_name,
            )
            if err:
                return {"error": err}
            assert coerced is not None
            canonical_proposal[field_name] = coerced
    elif any_proposal_field:
        return {
            "error": (
                "proposal_* ველები (`problem`, `benefit`, `mvp_scope`, "
                "`data_needed`, `time_estimate`, `risk_critique`) მხოლოდ "
                "`kind='proposal'`-ზე არის დაშვებული."
            )
        }

    merged_tags = _normalise_extra_tags(
        tags, kind=canonical_kind, status=DEFAULT_STATUS,
    )
    extra_metadata: Dict[str, Any] = {
        META_ENTRY_TYPE_KEY: META_ENTRY_TYPE_VALUE,
        META_KIND_KEY: canonical_kind,
        META_STATUS_KEY: DEFAULT_STATUS,
        META_DUE_DATE_KEY: canonical_due,
        META_TITLE_KEY: text,
    }
    if isinstance(source_memory_id, str) and source_memory_id.strip():
        extra_metadata[META_SOURCE_MEMORY_ID_KEY] = source_memory_id.strip()
    if canonical_proposal:
        extra_metadata[META_PROPOSAL_PROBLEM_KEY] = canonical_proposal["problem"]
        extra_metadata[META_PROPOSAL_BENEFIT_KEY] = canonical_proposal["benefit"]
        extra_metadata[META_PROPOSAL_MVP_KEY] = canonical_proposal["mvp_scope"]
        extra_metadata[META_PROPOSAL_DATA_KEY] = canonical_proposal["data_needed"]
        extra_metadata[META_PROPOSAL_TIME_KEY] = canonical_proposal["time_estimate"]
        extra_metadata[META_PROPOSAL_RISK_KEY] = canonical_proposal["risk_critique"]

    store, error = _store_or_error()
    if error is not None:
        return error
    assert store is not None

    entry_id = f"{JOURNAL_ID_PREFIX}_{uuid.uuid4().hex}"

    try:
        result = store.save(
            text,
            tags=merged_tags,
            source="chat",
            extra_metadata=extra_metadata,
            memory_id=entry_id,
        )
    except Exception as exc:
        logger.warning("add_journal_entry save failed: %s", exc)
        return {"error": f"ჟურნალში ჩაწერა ვერ მოხერხდა: {exc}"}

    payload: Dict[str, Any] = {
        "ok": True,
        "entry_id": result.get("memory_id") or entry_id,
        "title": text,
        "kind": canonical_kind,
        "status": DEFAULT_STATUS,
        "due_date": canonical_due,
        "created_at": _memory._now_iso(),
        "tags": list(merged_tags),
    }
    if canonical_proposal:
        payload["proposal"] = dict(canonical_proposal)
    return payload


# ---------------------------------------------------------------------------
# list_journal_entries
# ---------------------------------------------------------------------------


def _build_journal_where(
    *,
    status: Optional[str] = None,
    kind: Optional[str] = None,
    overdue: Optional[bool] = None,
    due_before: Optional[str] = None,
    due_after: Optional[str] = None,
    today: _dt.date,
) -> Dict[str, Any]:
    """Compose a ChromaDB ``where`` clause for journal CRUD queries.

    IMPORTANT: ChromaDB 1.5.x ``$lt`` / ``$gt`` / ``$lte`` / ``$gte``
    operators work only on **numeric** metadata values. Our ``due_date``
    is stored as an ISO **string** (``YYYY-MM-DD``), which means any
    comparison operator silently returns zero rows against the real
    backend. We therefore emit only ``$eq`` / ``$ne`` clauses here and
    apply the ``overdue`` / ``due_before`` / ``due_after`` filters in
    Python after the fetch — see :func:`list_journal_entries` and
    :func:`collect_today_journal_highlights`.
    """
    clauses: List[Dict[str, Any]] = [
        {META_ENTRY_TYPE_KEY: {"$eq": META_ENTRY_TYPE_VALUE}},
    ]
    if status:
        clauses.append({META_STATUS_KEY: {"$eq": status}})
    if kind:
        clauses.append({META_KIND_KEY: {"$eq": kind}})
    if overdue is True and status is None:
        # Overdue implies open; filtering by date happens Python-side.
        clauses.append({META_STATUS_KEY: {"$eq": "open"}})
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _apply_python_date_filters(
    entries: List[Dict[str, Any]],
    *,
    overdue: Optional[bool],
    due_before: Optional[str],
    due_after: Optional[str],
) -> List[Dict[str, Any]]:
    """Apply date-range filters in Python (ChromaDB string ``$lt`` is NOOP).

    ``overdue=True`` keeps only entries with a non-empty ``due_date`` and
    a positive ``overdue_days``. ``due_before`` / ``due_after`` use
    lexicographic ``YYYY-MM-DD`` comparison and skip undated entries.
    """
    result = entries
    if overdue is True:
        result = [
            e for e in result
            if (e.get("due_date") or "")
            and isinstance(e.get("overdue_days"), int)
            and e["overdue_days"] > 0
        ]
    if due_before:
        result = [
            e for e in result
            if (e.get("due_date") or "") and e["due_date"] < due_before
        ]
    if due_after:
        result = [
            e for e in result
            if (e.get("due_date") or "") and e["due_date"] > due_after
        ]
    return result


def _hit_to_entry(hit: Dict[str, Any], *, today: _dt.date) -> Dict[str, Any]:
    """Convert a ``MemoryStore.get_entries`` hit into the public entry shape."""
    meta = hit.get("metadata") or {}
    due_date = meta.get(META_DUE_DATE_KEY) or ""
    overdue_days: Optional[int] = None
    if due_date:
        try:
            parsed = _dt.date.fromisoformat(due_date)
            overdue_days = (today - parsed).days
        except ValueError:
            overdue_days = None
    title = meta.get(META_TITLE_KEY) or hit.get("summary") or ""
    entry: Dict[str, Any] = {
        "entry_id": hit.get("id") or "",
        "title": title,
        "kind": meta.get(META_KIND_KEY) or "",
        "status": meta.get(META_STATUS_KEY) or "",
        "due_date": due_date,
        "created_at": hit.get("created_at") or "",
        "overdue_days": overdue_days,
        "tags": list(hit.get("tags") or []),
    }
    # Phase 3.1 — surface proposal payload when any of the six keys is present.
    if any(meta.get(key) for key in _PROPOSAL_META_KEYS):
        entry["proposal"] = {
            "problem": meta.get(META_PROPOSAL_PROBLEM_KEY, "") or "",
            "benefit": meta.get(META_PROPOSAL_BENEFIT_KEY, "") or "",
            "mvp_scope": meta.get(META_PROPOSAL_MVP_KEY, "") or "",
            "data_needed": meta.get(META_PROPOSAL_DATA_KEY, "") or "",
            "time_estimate": meta.get(META_PROPOSAL_TIME_KEY, "") or "",
            "risk_critique": meta.get(META_PROPOSAL_RISK_KEY, "") or "",
        }
    return entry


def _sort_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Overdue (most days overdue first) → upcoming → everything else.

    Buckets:

    * ``overdue``  — status == open, ``overdue_days`` > 0; sorted by
      ``overdue_days`` descending (most-overdue first).
    * ``upcoming`` — status == open, has ``due_date`` but not yet past;
      sorted by ``due_date`` ascending (earliest first).
    * ``rest``     — everything else (done / cancelled / open + undated);
      sorted by ``created_at`` descending (newest first).
    """
    overdue: List[Dict[str, Any]] = []
    upcoming: List[Dict[str, Any]] = []
    rest: List[Dict[str, Any]] = []
    for e in entries:
        status = e.get("status") or ""
        due = e.get("due_date") or ""
        overdue_days = e.get("overdue_days")
        if status == "open" and isinstance(overdue_days, int) and overdue_days > 0:
            overdue.append(e)
        elif status == "open" and due:
            upcoming.append(e)
        else:
            rest.append(e)
    overdue.sort(key=lambda e: -(e.get("overdue_days") or 0))
    upcoming.sort(key=lambda e: e.get("due_date") or "")
    rest.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return overdue + upcoming + rest


def list_journal_entries(
    *,
    status: Any = None,
    kind: Any = None,
    overdue: Any = None,
    due_before: Any = None,
    due_after: Any = None,
    limit: Any = None,
    today: Any = None,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return a structured list of journal entries matching the filters."""
    canonical_status: Optional[str] = None
    if status is not None:
        canonical_status, err = _coerce_status(status)
        if err:
            return {"error": err}
    canonical_kind: Optional[str] = None
    if kind is not None:
        canonical_kind, err = _coerce_kind(kind)
        if err:
            return {"error": err}
    canonical_before: Optional[str] = None
    if due_before is not None:
        canonical_before, err = _coerce_due_date(due_before)
        if err:
            return {"error": err}
        if not canonical_before:
            canonical_before = None
    canonical_after: Optional[str] = None
    if due_after is not None:
        canonical_after, err = _coerce_due_date(due_after)
        if err:
            return {"error": err}
        if not canonical_after:
            canonical_after = None

    if overdue is not None and not isinstance(overdue, bool):
        return {"error": "`overdue` უნდა იყოს true/false."}

    canonical_today = _coerce_today(today)
    canonical_limit = _coerce_list_limit(limit)

    store, error = _store_or_error()
    if error is not None:
        return error
    assert store is not None

    where = _build_journal_where(
        status=canonical_status,
        kind=canonical_kind,
        overdue=bool(overdue) if overdue is not None else None,
        due_before=canonical_before,
        due_after=canonical_after,
        today=canonical_today,
    )

    try:
        # Over-fetch broadly because the date filters are applied in
        # Python (ChromaDB 1.5.x can't range-filter string metadata).
        # Up to 500 journal rows covers realistic business use — the
        # structured ``$eq`` clauses already narrow the set before we
        # post-filter.
        raw = store.get_entries(
            "chat",
            where=where,
            limit=500,
        )
    except Exception as exc:
        logger.warning("list_journal_entries failed: %s", exc)
        return {"error": f"ჟურნალის წაკითხვა ვერ მოხერხდა: {exc}"}

    entries = [_hit_to_entry(h, today=canonical_today) for h in raw]
    entries = _apply_python_date_filters(
        entries,
        overdue=bool(overdue) if overdue is not None else None,
        due_before=canonical_before,
        due_after=canonical_after,
    )
    entries = _sort_entries(entries)[:canonical_limit]
    return {
        "count": len(entries),
        "entries": entries,
        "today": canonical_today.isoformat(),
    }


# ---------------------------------------------------------------------------
# update_journal_entry
# ---------------------------------------------------------------------------


def update_journal_entry(
    entry_id: Any,
    *,
    status: Any,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Transition a journal entry's status. Returns the new state or error."""
    if not isinstance(entry_id, str) or not entry_id.strip():
        return {"error": "`entry_id` სავალდებულოა."}
    target_id = entry_id.strip()

    canonical_status, err = _coerce_status(status)
    if err:
        return {"error": err}
    assert canonical_status is not None

    store, error = _store_or_error()
    if error is not None:
        return error
    assert store is not None

    # Fetch current state so we can echo ``previous_status`` + retag.
    existing = store.get_entries("chat", ids=[target_id])
    if not existing:
        return {
            "error": f"ჟურნალის ჩანაწერი `{target_id}` ვერ მოიძებნა.",
            "hint": "გადაამოწმე `entry_id` — ფორმა 'journal_<32-hex>'.",
        }

    current = existing[0]
    meta = current.get("metadata") or {}
    if meta.get(META_ENTRY_TYPE_KEY) != META_ENTRY_TYPE_VALUE:
        return {
            "error": f"ჩანაწერი `{target_id}` ჟურნალის ჩანაწერი არ არის.",
        }
    previous_status = meta.get(META_STATUS_KEY) or ""
    current_kind = meta.get(META_KIND_KEY) or ""

    # Re-normalise tags so "status:<old>" is replaced with "status:<new>".
    extra_tags = [
        t for t in (current.get("tags") or [])
        if not t.startswith("status:")
    ]
    new_tags = _normalise_extra_tags(
        extra_tags, kind=current_kind, status=canonical_status,
    )

    patch: Dict[str, Any] = {
        META_STATUS_KEY: canonical_status,
        "tags": _memory._tags_to_metadata(new_tags),
    }

    updated = store.update_metadata(target_id, "chat", patch=patch)
    if updated is None:
        return {"error": f"სტატუსის განახლება ვერ მოხერხდა (`{target_id}`)."}

    return {
        "ok": True,
        "entry_id": target_id,
        "status": canonical_status,
        "previous_status": previous_status,
        "tags": new_tags,
    }


# ---------------------------------------------------------------------------
# delete_journal_entry
# ---------------------------------------------------------------------------


def delete_journal_entry(
    entry_id: Any,
    *,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Remove a journal entry. Exposed for completeness; not LLM-callable."""
    if not isinstance(entry_id, str) or not entry_id.strip():
        return {"error": "`entry_id` სავალდებულოა."}
    target_id = entry_id.strip()

    store, error = _store_or_error()
    if error is not None:
        return error
    assert store is not None

    existed = store.delete_entry(target_id, "chat")
    return {
        "ok": True,
        "entry_id": target_id,
        "existed": existed,
    }


# ---------------------------------------------------------------------------
# today_context helper — thin wrapper returning a compact shape
# ---------------------------------------------------------------------------


def collect_today_journal_highlights(
    *,
    today: Optional[_dt.date] = None,
    newest_open_limit: int = 3,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return the subset of entries shown in the ``<TODAY>`` block.

    Two buckets:

    * ``overdue`` — every open entry with a past ``due_date``, sorted
      oldest-first.
    * ``newest_open`` — up to ``newest_open_limit`` open entries that are
      NOT overdue, sorted by creation time descending.

    Both buckets are capped so the ``<TODAY>`` block stays short. On
    failure returns ``{"overdue": [], "newest_open": [], "notes": [...]}``
    with a Georgian breadcrumb so the caller can surface the degradation
    to the LLM without crashing the chat turn.
    """
    today = today or _dt.date.today()
    notes: List[str] = []
    overdue: List[Dict[str, Any]] = []
    newest_open: List[Dict[str, Any]] = []

    store, error = _store_or_error()
    if error is not None:
        notes.append(
            "ჟურნალი ვერ ჩაიტვირთა (ChromaDB unavailable) — "
            "ღია დაპირებები გამოტოვებულია."
        )
        return {"overdue": overdue, "newest_open": newest_open, "notes": notes}
    assert store is not None

    try:
        # Single fetch of all open journal entries; overdue split happens
        # in Python because ChromaDB 1.5.x can't range-filter strings.
        where_open = _build_journal_where(status="open", today=today)
        raw_open = store.get_entries("chat", where=where_open, limit=500)
        open_entries = [_hit_to_entry(h, today=today) for h in raw_open]
    except Exception as exc:
        logger.info("today open lookup failed: %s", exc)
        notes.append("ღია დაპირებები ვერ ჩამოვტვირთე.")
        return {"overdue": overdue, "newest_open": newest_open, "notes": notes}

    overdue_raw = [
        e for e in open_entries
        if isinstance(e.get("overdue_days"), int) and e["overdue_days"] > 0
    ]
    overdue = _sort_entries(overdue_raw)

    overdue_ids = {e["entry_id"] for e in overdue}
    non_overdue = [e for e in open_entries if e["entry_id"] not in overdue_ids]
    non_overdue.sort(
        key=lambda e: (e.get("created_at") or ""), reverse=True,
    )
    newest_open = non_overdue[: max(0, int(newest_open_limit))]

    return {"overdue": overdue, "newest_open": newest_open, "notes": notes}


def cleanup_stale_proposals(
    *,
    today: Optional[_dt.date] = None,
    older_than_days: int = PROPOSAL_AUTO_CLEANUP_DAYS,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Auto-cancel open proposals older than ``older_than_days``.

    Returns ``{"ok": True, "cancelled_count": N, "cancelled_ids": [...],
    "cutoff": "YYYY-MM-DD"}`` on success. This is a best-effort helper —
    failures log and return ``{"error": ...}`` without raising so the
    caller (``list_journal_entries``) can continue.
    """
    today = today or _dt.date.today()
    if older_than_days < 1:
        older_than_days = PROPOSAL_AUTO_CLEANUP_DAYS
    cutoff = today - _dt.timedelta(days=older_than_days)
    cutoff_iso = cutoff.isoformat()

    store, error = _store_or_error()
    if error is not None:
        return error
    assert store is not None

    where = _build_journal_where(
        status="open", kind=PROPOSAL_KIND, today=today,
    )
    try:
        raw = store.get_entries("chat", where=where, limit=500)
    except Exception as exc:
        logger.info("cleanup_stale_proposals fetch failed: %s", exc)
        return {"error": f"stale-proposal lookup failed: {exc}"}

    cancelled_ids: List[str] = []
    for hit in raw:
        created = (hit.get("created_at") or "").split("T")[0]
        if not created or created >= cutoff_iso:
            continue
        target_id = hit.get("id") or ""
        if not target_id:
            continue
        result = update_journal_entry(
            target_id, status="cancelled", project_root=project_root,
        )
        if result.get("ok"):
            cancelled_ids.append(target_id)
    return {
        "ok": True,
        "cancelled_count": len(cancelled_ids),
        "cancelled_ids": cancelled_ids,
        "cutoff": cutoff_iso,
    }


__all__ = [
    "JOURNAL_KINDS",
    "JOURNAL_STATUSES",
    "PROPOSAL_KIND",
    "PROPOSAL_AUTO_CLEANUP_DAYS",
    "DEFAULT_STATUS",
    "MIN_TITLE_CHARS",
    "MAX_TITLE_CHARS",
    "MIN_PROPOSAL_FIELD_CHARS",
    "MAX_PROPOSAL_FIELD_CHARS",
    "DEFAULT_LIST_LIMIT",
    "MIN_LIST_LIMIT",
    "MAX_LIST_LIMIT",
    "META_ENTRY_TYPE_KEY",
    "META_ENTRY_TYPE_VALUE",
    "META_KIND_KEY",
    "META_STATUS_KEY",
    "META_DUE_DATE_KEY",
    "META_TITLE_KEY",
    "META_SOURCE_MEMORY_ID_KEY",
    "META_PROPOSAL_PROBLEM_KEY",
    "META_PROPOSAL_BENEFIT_KEY",
    "META_PROPOSAL_MVP_KEY",
    "META_PROPOSAL_DATA_KEY",
    "META_PROPOSAL_TIME_KEY",
    "META_PROPOSAL_RISK_KEY",
    "JOURNAL_TAG_MARKER",
    "JOURNAL_ID_PREFIX",
    "add_journal_entry",
    "list_journal_entries",
    "update_journal_entry",
    "delete_journal_entry",
    "cleanup_stale_proposals",
    "collect_today_journal_highlights",
]
