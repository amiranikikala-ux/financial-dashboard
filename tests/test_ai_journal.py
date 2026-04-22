"""Regression tests for Phase 0B Sprint 4 — Decision Journal.

Pins the stable contract exposed to Anthropic + the LLM:

* Three new ``TOOL_SCHEMAS`` entries (``journal_add_entry`` /
  ``journal_list_entries`` / ``journal_update_entry``) sit between
  ``save_memory`` (index 5) and the investigator tools.
* Schema shape: required fields, enums, bounds, ``additionalProperties``
  off — these are part of the Anthropic API contract.
* Input coercion: title length, kind/status enums, ``due_date``
  YYYY-MM-DD + optional-empty.
* CRUD behaviour: add returns fresh ``entry_id``, list filters by
  status/kind/overdue + sorts overdue-first, update transitions status,
  delete removes the entry.
* Journal entries live in the same ChromaDB ``chat_memory`` collection
  as ``save_memory``, so ``recall_context`` still surfaces them via the
  ``journal`` tag (round-trip test below).
* ``today_context.build_today_context`` surfaces the ``open_promises``
  dict; ``format_today_block`` renders the overdue + newest_open lists
  under an ⏳ header.
* ``ToolDispatcher.dispatch`` routes the three new tool names through
  the lazy ``journal`` import.
* Prompt wiring: ``SYSTEM_PROMPT_KA`` gained a 📋 journal section with
  trigger / anti-trigger guidance; the investigator prompt stays
  untouched.

Uses an in-process fake ``chromadb`` stub + no-op embedding function so
tests run in milliseconds and never touch disk.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from dashboard_pipeline.ai import journal as journal_mod
from dashboard_pipeline.ai import memory as mem
from dashboard_pipeline.ai import prompts as prompts_mod
from dashboard_pipeline.ai import today_context as today_mod
from dashboard_pipeline.ai.journal import (
    DEFAULT_LIST_LIMIT,
    DEFAULT_STATUS,
    JOURNAL_ID_PREFIX,
    JOURNAL_KINDS,
    JOURNAL_STATUSES,
    MAX_LIST_LIMIT,
    MAX_TITLE_CHARS,
    META_DUE_DATE_KEY,
    META_ENTRY_TYPE_KEY,
    META_ENTRY_TYPE_VALUE,
    META_KIND_KEY,
    META_STATUS_KEY,
    META_TITLE_KEY,
    MIN_LIST_LIMIT,
    MIN_TITLE_CHARS,
    _build_journal_where,
    _coerce_due_date,
    _coerce_kind,
    _coerce_list_limit,
    _coerce_status,
    _coerce_title,
    _coerce_today,
    _hit_to_entry,
    _normalise_extra_tags,
    _sort_entries,
    add_journal_entry,
    collect_today_journal_highlights,
    delete_journal_entry,
    list_journal_entries,
    update_journal_entry,
)
from dashboard_pipeline.ai.tools import (
    JOURNAL_ADD_ENTRY_TOOL,
    JOURNAL_LIST_ENTRIES_TOOL,
    JOURNAL_UPDATE_ENTRY_TOOL,
    TOOL_SCHEMAS,
    ToolDispatcher,
)


# ---------------------------------------------------------------------------
# Fake in-process ChromaDB
# ---------------------------------------------------------------------------


class _FakeCollection:
    def __init__(self, name: str) -> None:
        self.name = name
        self._docs: Dict[str, Tuple[str, Dict[str, Any]]] = {}

    def upsert(
        self,
        *,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> None:
        for i, mid in enumerate(ids):
            self._docs[mid] = (documents[i], dict(metadatas[i]))

    def add(self, **kwargs: Any) -> None:
        self.upsert(**kwargs)

    def query(
        self,
        *,
        query_texts: List[str],
        n_results: int,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        items = [
            (mid, doc, meta)
            for mid, (doc, meta) in self._docs.items()
            if _fake_matches(meta, where)
        ]
        items = items[:n_results]
        return {
            "ids": [[mid for mid, _, _ in items]],
            "documents": [[doc for _, doc, _ in items]],
            "metadatas": [[meta for _, _, meta in items]],
            "distances": [[0.0 for _ in items]],
        }

    def get(
        self,
        *,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        if ids is not None:
            rows = [
                (mid, self._docs[mid][0], self._docs[mid][1])
                for mid in ids
                if mid in self._docs
            ]
        else:
            rows = [
                (mid, doc, meta)
                for mid, (doc, meta) in self._docs.items()
                if _fake_matches(meta, where)
            ]
        if limit and limit > 0:
            rows = rows[:limit]
        return {
            "ids": [mid for mid, _, _ in rows],
            "documents": [doc for _, doc, _ in rows],
            "metadatas": [meta for _, _, meta in rows],
        }

    def count(self) -> int:
        return len(self._docs)

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
        drop = [
            mid for mid, (_doc, meta) in self._docs.items()
            if _fake_matches(meta, where)
        ]
        for mid in drop:
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
        for chroma_op, py_cmp in (
            ("$lt", lambda a, b: a < b),
            ("$lte", lambda a, b: a <= b),
            ("$gt", lambda a, b: a > b),
            ("$gte", lambda a, b: a >= b),
        ):
            if chroma_op in op:
                expected = op[chroma_op]
                if actual is None:
                    return False
                try:
                    if not py_cmp(actual, expected):
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
        self._collections.setdefault(name, _FakeCollection(name))
        return self._collections[name]


class _FakeChromaDB:
    def __init__(self) -> None:
        self._clients: Dict[str, _FakeClient] = {}

    def PersistentClient(self, *, path: str) -> _FakeClient:
        self._clients.setdefault(path, _FakeClient(path))
        return self._clients[path]


class _NoopEmbeddingFunction:
    def __call__(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] * 8 for _ in texts]


@pytest.fixture(autouse=True)
def _isolated_journal_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Reset the singleton + install the fake chromadb module per-test."""
    fake_module = _FakeChromaDB()
    fake_ef = _NoopEmbeddingFunction()
    monkeypatch.setattr(mem, "_load_chromadb", lambda: fake_module)
    monkeypatch.setattr(mem, "_load_embedding_function", lambda: fake_ef)
    monkeypatch.setattr(mem, "_default_project_root", lambda: tmp_path)
    mem.reset_memory_store()
    yield
    mem.reset_memory_store()


# ---------------------------------------------------------------------------
# Tool schema registration
# ---------------------------------------------------------------------------


class TestJournalToolSchemas:
    def test_three_new_tools_registered(self):
        names = [t["name"] for t in TOOL_SCHEMAS]
        assert "journal_add_entry" in names
        assert "journal_list_entries" in names
        assert "journal_update_entry" in names

    def test_positions_after_save_memory(self):
        assert TOOL_SCHEMAS[6]["name"] == "journal_add_entry"
        assert TOOL_SCHEMAS[7]["name"] == "journal_list_entries"
        assert TOOL_SCHEMAS[8]["name"] == "journal_update_entry"

    def test_propose_feature_is_last(self):
        """Cache prefix now ends with `propose_feature` (Phase 3.1).

        Investigator tools remain clustered at 11-14; Phase 3.1 appended
        ``propose_feature`` at the tail so the cache-control marker
        shifts to it without disturbing journal / investigator indices.
        """
        assert TOOL_SCHEMAS[-1]["name"] == "propose_feature"

    def test_total_count_is_21(self):
        """Phase 4A grew TOOL_SCHEMAS 17 → 18; Phase 2.1 grew 18 → 19
        (+ compute_cash_flow_projection); Phase 2.2 grew 19 → 20
        (+ simulate_scenario); Phase 2.5 grew 20 → 21
        (+ analyze_product_profitability); Phase 2.6 grew 21 → 22
        (+ find_promotion_candidates); Phase 5.1 grew 22 → 25
        (+ 3 VAT reconciliation tools)."""
        assert len(TOOL_SCHEMAS) == 25

    def test_add_schema_shape(self):
        props = JOURNAL_ADD_ENTRY_TOOL["input_schema"]["properties"]
        assert "title" in props
        assert "kind" in props
        assert "due_date" in props
        assert "tags" in props
        assert set(JOURNAL_ADD_ENTRY_TOOL["input_schema"]["required"]) == {
            "title", "kind",
        }
        assert (
            JOURNAL_ADD_ENTRY_TOOL["input_schema"]["additionalProperties"]
            is False
        )
        assert props["kind"]["enum"] == list(JOURNAL_KINDS)

    def test_list_schema_shape(self):
        props = JOURNAL_LIST_ENTRIES_TOOL["input_schema"]["properties"]
        assert "status" in props
        assert "kind" in props
        assert "overdue" in props
        assert "limit" in props
        assert JOURNAL_LIST_ENTRIES_TOOL["input_schema"]["required"] == []
        assert props["status"]["enum"] == list(JOURNAL_STATUSES)
        assert props["kind"]["enum"] == list(JOURNAL_KINDS)
        assert props["limit"]["minimum"] == 1
        assert props["limit"]["maximum"] == 100

    def test_update_schema_shape(self):
        props = JOURNAL_UPDATE_ENTRY_TOOL["input_schema"]["properties"]
        assert "entry_id" in props
        assert "status" in props
        assert set(
            JOURNAL_UPDATE_ENTRY_TOOL["input_schema"]["required"]
        ) == {"entry_id", "status"}
        assert props["status"]["enum"] == list(JOURNAL_STATUSES)

    def test_descriptions_mention_todays_block(self):
        assert "TODAY" in JOURNAL_ADD_ENTRY_TOOL["description"]

    def test_descriptions_warn_against_abuse(self):
        desc = JOURNAL_ADD_ENTRY_TOOL["description"]
        assert "idle" in desc.lower() or "chit-chat" in desc.lower()


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


class TestJournalConstants:
    def test_kinds_tuple(self):
        """Phase 3.1 added ``proposal`` (Co-Designer), Phase 4A added
        ``repayment_plan`` (autonomous debt strategist)."""
        assert JOURNAL_KINDS == (
            "promise", "ai_commitment", "recommendation", "reminder",
            "proposal", "repayment_plan",
        )

    def test_statuses_tuple(self):
        assert JOURNAL_STATUSES == ("open", "done", "cancelled")

    def test_default_status_is_open(self):
        assert DEFAULT_STATUS == "open"

    def test_limit_bounds(self):
        assert MIN_LIST_LIMIT == 1
        assert MAX_LIST_LIMIT == 100
        assert MIN_LIST_LIMIT < DEFAULT_LIST_LIMIT < MAX_LIST_LIMIT

    def test_title_bounds(self):
        assert MIN_TITLE_CHARS >= 1
        assert MAX_TITLE_CHARS <= 2_000


# ---------------------------------------------------------------------------
# Input coercion
# ---------------------------------------------------------------------------


class TestCoerceTitle:
    def test_none_errors(self):
        text, err = _coerce_title(None)
        assert text is None and err

    def test_non_string_errors(self):
        text, err = _coerce_title(42)
        assert text is None and err

    def test_too_short_errors(self):
        text, err = _coerce_title("ab")
        assert text is None and err

    def test_happy_path_strips(self):
        text, err = _coerce_title("  Alpha-ს ვალის გადამოწმება  ")
        assert err is None
        assert text == "Alpha-ს ვალის გადამოწმება"

    def test_oversized_truncated(self):
        big = "ა" * (MAX_TITLE_CHARS + 10)
        text, err = _coerce_title(big)
        assert err is None
        assert text is not None
        assert len(text) <= MAX_TITLE_CHARS + 1  # +1 for ellipsis


class TestCoerceKind:
    def test_none_errors(self):
        kind, err = _coerce_kind(None)
        assert kind is None and err

    def test_unknown_errors(self):
        kind, err = _coerce_kind("task")
        assert kind is None and err

    @pytest.mark.parametrize("value", JOURNAL_KINDS)
    def test_known_roundtrips(self, value):
        kind, err = _coerce_kind(value)
        assert err is None
        assert kind == value

    def test_case_insensitive(self):
        kind, err = _coerce_kind("Promise")
        assert err is None
        assert kind == "promise"


class TestCoerceStatus:
    def test_none_errors(self):
        status, err = _coerce_status(None)
        assert status is None and err

    def test_unknown_errors(self):
        status, err = _coerce_status("archived")
        assert status is None and err

    @pytest.mark.parametrize("value", JOURNAL_STATUSES)
    def test_known_roundtrips(self, value):
        status, err = _coerce_status(value)
        assert err is None
        assert status == value

    def test_case_insensitive(self):
        status, err = _coerce_status("DONE")
        assert err is None
        assert status == "done"


class TestCoerceDueDate:
    def test_none_returns_empty(self):
        value, err = _coerce_due_date(None)
        assert value == "" and err is None

    def test_empty_string_returns_empty(self):
        value, err = _coerce_due_date("")
        assert value == "" and err is None

    def test_valid_iso_passes(self):
        value, err = _coerce_due_date("2026-05-14")
        assert err is None
        assert value == "2026-05-14"

    def test_invalid_format_errors(self):
        value, err = _coerce_due_date("14/05/2026")
        assert value is None and err

    def test_impossible_date_errors(self):
        value, err = _coerce_due_date("2026-02-30")
        assert value is None and err

    def test_non_string_non_date_errors(self):
        value, err = _coerce_due_date(42)
        assert value is None and err

    def test_datetime_coerced(self):
        value, err = _coerce_due_date(_dt.datetime(2026, 5, 14, 9, 0, 0))
        assert err is None
        assert value == "2026-05-14"

    def test_date_coerced(self):
        value, err = _coerce_due_date(_dt.date(2026, 5, 14))
        assert err is None
        assert value == "2026-05-14"


class TestCoerceListLimit:
    def test_none_default(self):
        assert _coerce_list_limit(None) == DEFAULT_LIST_LIMIT

    def test_garbage_falls_back(self):
        assert _coerce_list_limit("xx") == DEFAULT_LIST_LIMIT

    def test_below_min_clamped(self):
        assert _coerce_list_limit(-5) == MIN_LIST_LIMIT

    def test_above_max_clamped(self):
        assert _coerce_list_limit(9_999) == MAX_LIST_LIMIT

    def test_in_range_passes(self):
        assert _coerce_list_limit(7) == 7


class TestCoerceToday:
    def test_none_returns_today(self):
        assert _coerce_today(None) == _dt.date.today()

    def test_date_passthrough(self):
        assert _coerce_today(_dt.date(2026, 4, 19)) == _dt.date(2026, 4, 19)

    def test_iso_string_parsed(self):
        assert _coerce_today("2026-04-19") == _dt.date(2026, 4, 19)

    def test_garbage_falls_back_today(self):
        assert _coerce_today("not-a-date") == _dt.date.today()


class TestNormaliseExtraTags:
    def test_structural_tags_added_first(self):
        tags = _normalise_extra_tags(None, kind="promise", status="open")
        assert tags[:3] == ["journal", "kind:promise", "status:open"]

    def test_user_tags_preserved(self):
        tags = _normalise_extra_tags(
            ["supplier:alpha"], kind="promise", status="open",
        )
        assert "supplier:alpha" in tags

    def test_user_supplied_kind_status_stripped(self):
        tags = _normalise_extra_tags(
            ["kind:wrong", "status:wrong", "topic:waybills"],
            kind="promise", status="open",
        )
        assert "kind:wrong" not in tags
        assert "status:wrong" not in tags
        assert "kind:promise" in tags
        assert "status:open" in tags
        assert "topic:waybills" in tags

    def test_dedup(self):
        tags = _normalise_extra_tags(
            ["supplier:alpha", "supplier:alpha", "journal"],
            kind="promise", status="open",
        )
        assert tags.count("journal") == 1
        assert tags.count("supplier:alpha") == 1


# ---------------------------------------------------------------------------
# Where-clause builder
# ---------------------------------------------------------------------------


class TestBuildJournalWhere:
    def test_base_always_filters_entry_type(self):
        where = _build_journal_where(today=_dt.date(2026, 4, 19))
        assert where == {META_ENTRY_TYPE_KEY: {"$eq": META_ENTRY_TYPE_VALUE}}

    def test_status_filter_ands(self):
        where = _build_journal_where(
            status="open", today=_dt.date(2026, 4, 19),
        )
        assert "$and" in where
        assert {META_STATUS_KEY: {"$eq": "open"}} in where["$and"]

    def test_overdue_enforces_open_status_only(self):
        # ChromaDB 1.5.x cannot range-filter string metadata, so the
        # overdue date check is applied in Python after fetch. The where
        # clause therefore includes only the $eq status=open guard;
        # the date comparison NEVER appears as a ChromaDB clause.
        where = _build_journal_where(
            overdue=True, today=_dt.date(2026, 4, 19),
        )
        assert "$and" in where
        sub = where["$and"]
        assert {META_STATUS_KEY: {"$eq": "open"}} in sub
        # No date comparison clauses leak into the ChromaDB where.
        date_keys = [c for c in sub if META_DUE_DATE_KEY in c]
        assert date_keys == [], (
            "date comparisons must be Python-side, not ChromaDB-side"
        )

    def test_overdue_with_explicit_status_skips_auto_open(self):
        # When caller supplies ``status`` explicitly, the overdue branch
        # must not add a second (duplicate) status clause.
        where = _build_journal_where(
            status="open", overdue=True, today=_dt.date(2026, 4, 19),
        )
        status_clauses = [
            c for c in where["$and"] if META_STATUS_KEY in c
        ]
        assert len(status_clauses) == 1


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------


class TestSortEntries:
    def test_overdue_before_future(self):
        entries = [
            {"status": "open", "due_date": "2026-05-01", "overdue_days": -12, "created_at": "2026-04-01"},
            {"status": "open", "due_date": "2026-04-10", "overdue_days": 9, "created_at": "2026-03-01"},
        ]
        ordered = _sort_entries(entries)
        assert ordered[0]["overdue_days"] == 9  # overdue first

    def test_most_overdue_first(self):
        entries = [
            {"status": "open", "due_date": "2026-04-15", "overdue_days": 4, "created_at": ""},
            {"status": "open", "due_date": "2026-04-05", "overdue_days": 14, "created_at": ""},
        ]
        ordered = _sort_entries(entries)
        assert ordered[0]["overdue_days"] == 14

    def test_done_bucket_newest_first(self):
        entries = [
            {"status": "done", "due_date": "", "overdue_days": None, "created_at": "2026-01-01"},
            {"status": "done", "due_date": "", "overdue_days": None, "created_at": "2026-03-01"},
        ]
        ordered = _sort_entries(entries)
        assert ordered[0]["created_at"] == "2026-03-01"


# ---------------------------------------------------------------------------
# add_journal_entry
# ---------------------------------------------------------------------------


class TestAddEntry:
    def test_happy_path(self):
        result = add_journal_entry(
            "Alpha-ს ვალის გადამოწმება",
            "promise",
            due_date="2026-05-01",
            tags=["supplier:alpha"],
        )
        assert result["ok"] is True
        assert result["kind"] == "promise"
        assert result["status"] == DEFAULT_STATUS
        assert result["due_date"] == "2026-05-01"
        assert result["title"] == "Alpha-ს ვალის გადამოწმება"
        assert result["entry_id"].startswith(f"{JOURNAL_ID_PREFIX}_")
        assert "journal" in result["tags"]
        assert "kind:promise" in result["tags"]
        assert "status:open" in result["tags"]
        assert "supplier:alpha" in result["tags"]

    def test_ai_commitment_without_due_date(self):
        result = add_journal_entry(
            "შემდეგ ჩატში POS-ის დამოკიდებულება გადავამოწმებ",
            "ai_commitment",
        )
        assert result["ok"] is True
        assert result["due_date"] == ""
        assert result["kind"] == "ai_commitment"

    def test_bad_title_error(self):
        result = add_journal_entry("  ", "promise")
        assert "error" in result

    def test_bad_kind_error(self):
        result = add_journal_entry("valid title here", "task")
        assert "error" in result

    def test_bad_due_date_error(self):
        result = add_journal_entry(
            "valid title here", "promise", due_date="14/05/2026",
        )
        assert "error" in result

    def test_every_kind_registers(self):
        """Each ``JOURNAL_KINDS`` entry registers successfully.

        Phase 3.1 note: ``proposal`` requires the six structured payload
        fields; all other kinds accept the plain ``(title, kind)`` form.
        """
        proposal_extras = {
            "problem": "test proposal problem description",
            "benefit": "test proposal benefit description",
            "mvp_scope": "test proposal MVP scope description",
            "data_needed": "test proposal data need description",
            "time_estimate": "1-2 days",
            "risk_critique": "test proposal risk critique description",
        }
        created_ids = []
        for kind in JOURNAL_KINDS:
            if kind == "proposal":
                r = add_journal_entry(
                    f"test {kind} entry", kind, **proposal_extras,
                )
            else:
                r = add_journal_entry(f"test {kind} entry", kind)
            assert r["ok"] is True, r
            created_ids.append(r["entry_id"])
        assert len(set(created_ids)) == len(JOURNAL_KINDS)


# ---------------------------------------------------------------------------
# list_journal_entries
# ---------------------------------------------------------------------------


class TestListEntries:
    def _seed(self, today: _dt.date) -> Dict[str, str]:
        """Populate a handful of entries with known statuses / dates."""
        ids: Dict[str, str] = {}

        r = add_journal_entry(
            "Alpha-ს ვალის გადამოწმება",
            "promise",
            due_date=(today - _dt.timedelta(days=9)).isoformat(),
        )
        ids["alpha_overdue"] = r["entry_id"]

        r = add_journal_entry(
            "VAT დეკლარაცია",
            "reminder",
            due_date=(today + _dt.timedelta(days=7)).isoformat(),
        )
        ids["vat_future"] = r["entry_id"]

        r = add_journal_entry(
            "Beta-სთან ფასის ვაჭრობა",
            "recommendation",
        )
        ids["beta_no_date"] = r["entry_id"]

        r = add_journal_entry(
            "POS ტერმინალის შეცვლა",
            "promise",
            due_date=today.isoformat(),
        )
        ids["pos_today"] = r["entry_id"]
        return ids

    def test_all_statuses_returned_by_default(self):
        today = _dt.date(2026, 4, 19)
        ids = self._seed(today)
        result = list_journal_entries(today=today)
        assert result["count"] == 4
        returned_ids = {e["entry_id"] for e in result["entries"]}
        assert set(ids.values()) == returned_ids

    def test_overdue_only(self):
        today = _dt.date(2026, 4, 19)
        ids = self._seed(today)
        result = list_journal_entries(overdue=True, today=today)
        assert result["count"] == 1
        assert result["entries"][0]["entry_id"] == ids["alpha_overdue"]
        assert result["entries"][0]["overdue_days"] == 9

    def test_status_filter(self):
        today = _dt.date(2026, 4, 19)
        self._seed(today)
        update_journal_entry(
            add_journal_entry("DONE commitment", "promise")["entry_id"],
            status="done",
        )
        result = list_journal_entries(status="done", today=today)
        assert result["count"] == 1
        assert result["entries"][0]["status"] == "done"

    def test_kind_filter(self):
        today = _dt.date(2026, 4, 19)
        self._seed(today)
        result = list_journal_entries(kind="reminder", today=today)
        assert result["count"] == 1
        assert result["entries"][0]["kind"] == "reminder"

    def test_sort_puts_overdue_first(self):
        today = _dt.date(2026, 4, 19)
        self._seed(today)
        result = list_journal_entries(today=today)
        first = result["entries"][0]
        assert first["overdue_days"] == 9

    def test_limit_respected(self):
        today = _dt.date(2026, 4, 19)
        self._seed(today)
        result = list_journal_entries(limit=2, today=today)
        assert result["count"] == 2

    def test_limit_clamped_to_max(self):
        today = _dt.date(2026, 4, 19)
        self._seed(today)
        # Request above MAX_LIST_LIMIT — should be clamped, no error.
        result = list_journal_entries(limit=MAX_LIST_LIMIT + 10, today=today)
        assert result["count"] <= MAX_LIST_LIMIT

    def test_non_boolean_overdue_rejected(self):
        today = _dt.date(2026, 4, 19)
        self._seed(today)
        result = list_journal_entries(overdue="yes", today=today)
        assert "error" in result

    def test_bad_status_rejected(self):
        result = list_journal_entries(status="archived")
        assert "error" in result

    def test_empty_when_nothing_added(self):
        result = list_journal_entries(today=_dt.date(2026, 4, 19))
        assert result["count"] == 0
        assert result["entries"] == []

    def test_entry_has_overdue_days(self):
        today = _dt.date(2026, 4, 19)
        ids = self._seed(today)
        result = list_journal_entries(today=today)
        by_id = {e["entry_id"]: e for e in result["entries"]}
        assert by_id[ids["alpha_overdue"]]["overdue_days"] == 9
        assert by_id[ids["pos_today"]]["overdue_days"] == 0
        assert by_id[ids["vat_future"]]["overdue_days"] == -7
        assert by_id[ids["beta_no_date"]]["overdue_days"] is None

    def test_today_echoed_in_response(self):
        today = _dt.date(2026, 4, 19)
        self._seed(today)
        result = list_journal_entries(today=today)
        assert result["today"] == "2026-04-19"


# ---------------------------------------------------------------------------
# update_journal_entry
# ---------------------------------------------------------------------------


class TestUpdateEntry:
    def test_transition_to_done(self):
        created = add_journal_entry("Alpha check", "promise")
        result = update_journal_entry(created["entry_id"], status="done")
        assert result["ok"] is True
        assert result["status"] == "done"
        assert result["previous_status"] == "open"
        assert "status:done" in result["tags"]
        assert "status:open" not in result["tags"]

    def test_transition_to_cancelled(self):
        created = add_journal_entry("POS battery swap", "promise")
        result = update_journal_entry(
            created["entry_id"], status="cancelled",
        )
        assert result["ok"] is True
        assert result["status"] == "cancelled"

    def test_rollback_to_open(self):
        created = add_journal_entry("rollback check", "promise")
        update_journal_entry(created["entry_id"], status="done")
        rollback = update_journal_entry(created["entry_id"], status="open")
        assert rollback["ok"] is True
        assert rollback["status"] == "open"
        assert rollback["previous_status"] == "done"

    def test_unknown_id_errors(self):
        result = update_journal_entry("journal_nonexistent", status="done")
        assert "error" in result

    def test_bad_entry_id_type_errors(self):
        result = update_journal_entry(None, status="done")
        assert "error" in result

    def test_bad_status_errors(self):
        created = add_journal_entry("status check", "promise")
        result = update_journal_entry(
            created["entry_id"], status="archived",
        )
        assert "error" in result

    def test_status_persists_for_list_query(self):
        today = _dt.date(2026, 4, 19)
        created = add_journal_entry("persist test", "promise")
        update_journal_entry(created["entry_id"], status="done")
        open_list = list_journal_entries(status="open", today=today)
        assert all(
            e["entry_id"] != created["entry_id"] for e in open_list["entries"]
        )
        done_list = list_journal_entries(status="done", today=today)
        assert any(
            e["entry_id"] == created["entry_id"] for e in done_list["entries"]
        )

    def test_save_memory_entries_rejected(self):
        """Plain save_memory rows (no journal metadata) cannot be updated."""
        mem.save_memory(
            "regular memory summary — unrelated to journal",
            tags=["kind:observation"],
            source="chat",
        )
        # Grab the id of the non-journal entry.
        all_chat = mem.get_memory_store().get_entries("chat")
        non_journal = [
            hit for hit in all_chat
            if (hit.get("metadata") or {}).get(META_ENTRY_TYPE_KEY) != META_ENTRY_TYPE_VALUE
        ]
        assert non_journal, "fixture should have produced one non-journal entry"
        result = update_journal_entry(non_journal[0]["id"], status="done")
        assert "error" in result


# ---------------------------------------------------------------------------
# delete_journal_entry
# ---------------------------------------------------------------------------


class TestDeleteEntry:
    def test_delete_removes_entry(self):
        created = add_journal_entry("to be deleted", "promise")
        delete_journal_entry(created["entry_id"])
        result = list_journal_entries(today=_dt.date(2026, 4, 19))
        assert result["count"] == 0

    def test_delete_unknown_returns_existed_false(self):
        result = delete_journal_entry("journal_nonexistent")
        assert result["ok"] is True
        assert result["existed"] is False

    def test_bad_entry_id_errors(self):
        assert "error" in delete_journal_entry(None)


# ---------------------------------------------------------------------------
# collect_today_journal_highlights
# ---------------------------------------------------------------------------


class TestCollectTodayHighlights:
    def _seed(self, today: _dt.date) -> None:
        add_journal_entry(
            "Alpha-ს ვალის გადამოწმება",
            "promise",
            due_date=(today - _dt.timedelta(days=9)).isoformat(),
        )
        add_journal_entry(
            "POS ტერმინალის ბატარეის შეცვლა",
            "promise",
            due_date=today.isoformat(),
        )
        add_journal_entry(
            "ყველაზე ახალი დაპირება",
            "ai_commitment",
        )
        done_id = add_journal_entry(
            "closed thing",
            "recommendation",
        )["entry_id"]
        update_journal_entry(done_id, status="done")

    def test_overdue_bucket_populated(self):
        today = _dt.date(2026, 4, 19)
        self._seed(today)
        highlights = collect_today_journal_highlights(today=today)
        assert len(highlights["overdue"]) == 1
        assert highlights["overdue"][0]["overdue_days"] == 9

    def test_newest_open_excludes_overdue_and_done(self):
        today = _dt.date(2026, 4, 19)
        self._seed(today)
        highlights = collect_today_journal_highlights(today=today)
        titles = {e["title"] for e in highlights["newest_open"]}
        assert "ყველაზე ახალი დაპირება" in titles
        # Done entries must not appear in newest_open.
        assert "closed thing" not in titles

    def test_newest_open_limit_respected(self):
        today = _dt.date(2026, 4, 19)
        for i in range(5):
            add_journal_entry(f"promise {i}", "promise")
        highlights = collect_today_journal_highlights(
            today=today, newest_open_limit=2,
        )
        assert len(highlights["newest_open"]) == 2

    def test_notes_non_failing_empty(self):
        highlights = collect_today_journal_highlights(
            today=_dt.date(2026, 4, 19),
        )
        assert isinstance(highlights["overdue"], list)
        assert isinstance(highlights["newest_open"], list)
        assert isinstance(highlights["notes"], list)


# ---------------------------------------------------------------------------
# today_context integration
# ---------------------------------------------------------------------------


class TestTodayContextIntegration:
    def _data_stub(self) -> Dict[str, Any]:
        return {"retail_sales": {"rows_preview": []}, "aging_summary": {
            "current": 0.0, "overdue_30": 0.0, "overdue_60": 0.0,
            "overdue_90": 0.0, "overdue_180": 0.0, "overdue_180_plus": 0.0,
        }}

    def test_open_promises_present_in_context(self):
        today = _dt.date(2026, 4, 19)
        add_journal_entry(
            "Alpha overdue",
            "promise",
            due_date=(today - _dt.timedelta(days=3)).isoformat(),
        )
        add_journal_entry(
            "Beta fresh",
            "recommendation",
        )
        ctx = today_mod.build_today_context(
            lambda: self._data_stub(), today=today,
        )
        assert "open_promises" in ctx
        promises = ctx["open_promises"]
        assert len(promises["overdue"]) == 1
        assert len(promises["newest_open"]) == 1

    def test_format_block_renders_open_promises_header(self):
        today = _dt.date(2026, 4, 19)
        add_journal_entry(
            "VAT reminder",
            "reminder",
            due_date=(today - _dt.timedelta(days=2)).isoformat(),
        )
        block = today_mod.build_today_block(
            lambda: self._data_stub(), today=today,
        )
        assert "ღია დაპირებები" in block
        assert "ვადა გადაცილებული" in block
        assert "VAT reminder" in block

    def test_format_block_shows_today_due_tag(self):
        today = _dt.date(2026, 4, 19)
        add_journal_entry(
            "POS swap",
            "promise",
            due_date=today.isoformat(),
        )
        block = today_mod.build_today_block(
            lambda: self._data_stub(), today=today,
        )
        assert "POS swap" in block
        assert "დღეს ვადა" in block

    def test_empty_journal_skips_header(self):
        today = _dt.date(2026, 4, 19)
        block = today_mod.build_today_block(
            lambda: self._data_stub(), today=today,
        )
        assert "ღია დაპირებები" not in block


# ---------------------------------------------------------------------------
# Dispatcher routing
# ---------------------------------------------------------------------------


class TestDispatcherRouting:
    def _dispatcher(self) -> ToolDispatcher:
        return ToolDispatcher(data_loader=lambda: {})

    def test_add_routed(self):
        disp = self._dispatcher()
        result = disp.dispatch(
            "journal_add_entry",
            {"title": "dispatcher add test", "kind": "promise"},
        )
        assert result["ok"] is True
        assert result["kind"] == "promise"

    def test_list_routed(self):
        disp = self._dispatcher()
        disp.dispatch(
            "journal_add_entry",
            {"title": "dispatcher list test", "kind": "promise"},
        )
        result = disp.dispatch("journal_list_entries", {"status": "open"})
        assert "entries" in result
        assert result["count"] >= 1

    def test_update_routed(self):
        disp = self._dispatcher()
        created = disp.dispatch(
            "journal_add_entry",
            {"title": "dispatcher update test", "kind": "promise"},
        )
        result = disp.dispatch(
            "journal_update_entry",
            {"entry_id": created["entry_id"], "status": "done"},
        )
        assert result["ok"] is True
        assert result["status"] == "done"

    def test_call_trace_carries_journal_keys(self):
        disp = self._dispatcher()
        disp.dispatch(
            "journal_add_entry",
            {"title": "trace test", "kind": "promise"},
        )
        call = disp.calls[-1]
        summary = call["result_summary"]
        assert summary.get("ok") is True
        assert "entry_id" in summary
        assert "kind" in summary


# ---------------------------------------------------------------------------
# Prompt wiring
# ---------------------------------------------------------------------------


class TestPromptWiring:
    def test_chat_prompt_has_journal_section(self):
        prompt = prompts_mod.SYSTEM_PROMPT_KA
        assert "📋" in prompt
        assert "დაპირებების ჟურნალი" in prompt
        assert "journal_add_entry" in prompt
        assert "journal_list_entries" in prompt
        assert "journal_update_entry" in prompt

    def test_chat_prompt_lists_triggers(self):
        prompt = prompts_mod.SYSTEM_PROMPT_KA
        assert "promise" in prompt
        assert "ai_commitment" in prompt
        assert "recommendation" in prompt
        assert "reminder" in prompt

    def test_chat_prompt_has_anti_triggers(self):
        prompt = prompts_mod.SYSTEM_PROMPT_KA
        assert "chit-chat" in prompt or "chit chat" in prompt.lower()

    def test_investigator_prompt_untouched(self):
        inv = prompts_mod.SYSTEM_PROMPT_KA_INVESTIGATOR
        # Journal section is chat-only — must NEVER leak into investigator.
        assert "journal_add_entry" not in inv
        assert "journal_list_entries" not in inv
        assert "journal_update_entry" not in inv
        assert "დაპირებების ჟურნალი" not in inv


# ---------------------------------------------------------------------------
# Round-trip sanity — hit_to_entry
# ---------------------------------------------------------------------------


class TestHitToEntry:
    def test_overdue_days_computed(self):
        hit = {
            "id": "journal_xyz",
            "summary": "Alpha check",
            "tags": ["journal", "kind:promise", "status:open"],
            "source": "chat",
            "created_at": "2026-04-10T00:00:00+00:00",
            "metadata": {
                META_ENTRY_TYPE_KEY: META_ENTRY_TYPE_VALUE,
                META_KIND_KEY: "promise",
                META_STATUS_KEY: "open",
                META_DUE_DATE_KEY: "2026-04-15",
                META_TITLE_KEY: "Alpha check",
            },
        }
        entry = _hit_to_entry(hit, today=_dt.date(2026, 4, 19))
        assert entry["overdue_days"] == 4
        assert entry["title"] == "Alpha check"
        assert entry["kind"] == "promise"
        assert entry["status"] == "open"

    def test_undated_entry_has_none_overdue_days(self):
        hit = {
            "id": "journal_abc",
            "summary": "Beta",
            "tags": [],
            "source": "chat",
            "created_at": "",
            "metadata": {
                META_ENTRY_TYPE_KEY: META_ENTRY_TYPE_VALUE,
                META_KIND_KEY: "recommendation",
                META_STATUS_KEY: "open",
                META_DUE_DATE_KEY: "",
                META_TITLE_KEY: "Beta",
            },
        }
        entry = _hit_to_entry(hit, today=_dt.date(2026, 4, 19))
        assert entry["overdue_days"] is None

    def test_bad_due_date_gracefully_none(self):
        hit = {
            "id": "journal_broken",
            "summary": "X",
            "tags": [],
            "source": "chat",
            "created_at": "",
            "metadata": {
                META_ENTRY_TYPE_KEY: META_ENTRY_TYPE_VALUE,
                META_KIND_KEY: "promise",
                META_STATUS_KEY: "open",
                META_DUE_DATE_KEY: "not-a-date",
                META_TITLE_KEY: "X",
            },
        }
        entry = _hit_to_entry(hit, today=_dt.date(2026, 4, 19))
        assert entry["overdue_days"] is None


# ---------------------------------------------------------------------------
# Semantic recall interop — journal rows surface via `recall_context(tags=["journal"])`
# ---------------------------------------------------------------------------


class TestSemanticRecallInterop:
    def test_journal_entries_recallable_via_tag(self):
        add_journal_entry(
            "Alpha-ს ვალის გადამოწმება 50% წინასწარი",
            "promise",
            tags=["supplier:alpha"],
            due_date="2026-05-01",
        )
        hits = mem.recall_context(
            "Alpha ვალი",
            tags=["journal"],
            limit=5,
        )
        ids = {h["id"] for h in hits.get("results") or []}
        assert any(mid.startswith(JOURNAL_ID_PREFIX) for mid in ids)

    def test_non_journal_memories_excluded_by_journal_tag(self):
        mem.save_memory(
            "Free-form summary with no journal commitment",
            tags=["kind:observation", "topic:cashflow"],
            source="chat",
        )
        add_journal_entry(
            "Alpha concrete promise",
            "promise",
        )
        hits = mem.recall_context(
            "Alpha",
            tags=["journal"],
            limit=5,
        )
        ids = [h["id"] for h in hits.get("results") or []]
        assert all(mid.startswith(JOURNAL_ID_PREFIX) for mid in ids)
