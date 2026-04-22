"""Regression tests for Phase 3.1 — Co-Designer Mode.

Pins the stable contract exposed to Anthropic + the LLM:

* ``JOURNAL_KINDS`` extended with ``proposal`` (Phase 3.1 grew 4→5) and
  later with ``repayment_plan`` (Phase 4A grew 5→6).
* Six new metadata keys (``META_PROPOSAL_*``) for the structured proposal payload.
* ``_coerce_proposal_field`` bounds (5-char min, 1000-char max, truncation).
* ``add_journal_entry(kind='proposal', problem, benefit, mvp_scope, data_needed,
  time_estimate, risk_critique)`` validates all six required fields and rejects
  partial / mis-matched input.
* Proposal fields on non-proposal kinds are rejected (schema isolation).
* ``_hit_to_entry`` surfaces ``proposal`` dict when metadata present.
* ``cleanup_stale_proposals`` auto-cancels open proposals older than N days.
* ``PROPOSE_FEATURE_TOOL`` schema shape: 7 required fields, ``additionalProperties`` off.
* ``TOOL_SCHEMAS`` length = 18 after Phase 4A; ``propose_feature`` at the tail (index 17).
* ``ToolDispatcher.dispatch("propose_feature", ...)`` routes through the lazy
  ``journal.add_journal_entry`` import.
* ``SYSTEM_PROMPT_KA`` gained 🎨 Co-Designer section with pull-only trigger list,
  anti-trigger rules, 6-field mandatory structure, critic hat mandate, and ID
  citation requirement.
* ``SYSTEM_PROMPT_KA_INVESTIGATOR`` has **zero** Co-Designer markers
  (do-not-touch rule extends Sprint 1/2/3/4 + Part A/B/C/D + Phase 2.11/2.12).

Uses the same in-process fake ``chromadb`` stub as ``test_ai_journal.py``.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from dashboard_pipeline.ai import journal as journal_mod
from dashboard_pipeline.ai import memory as mem
from dashboard_pipeline.ai import prompts as prompts_mod
from dashboard_pipeline.ai.journal import (
    JOURNAL_KINDS,
    MAX_PROPOSAL_FIELD_CHARS,
    MIN_PROPOSAL_FIELD_CHARS,
    META_PROPOSAL_BENEFIT_KEY,
    META_PROPOSAL_DATA_KEY,
    META_PROPOSAL_MVP_KEY,
    META_PROPOSAL_PROBLEM_KEY,
    META_PROPOSAL_RISK_KEY,
    META_PROPOSAL_TIME_KEY,
    PROPOSAL_AUTO_CLEANUP_DAYS,
    PROPOSAL_KIND,
    _PROPOSAL_FIELD_NAMES,
    _PROPOSAL_META_KEYS,
    _coerce_proposal_field,
    _hit_to_entry,
    add_journal_entry,
    cleanup_stale_proposals,
    list_journal_entries,
)
from dashboard_pipeline.ai.tools import (
    PROPOSE_FEATURE_TOOL,
    TOOL_SCHEMAS,
    ToolDispatcher,
)


# ---------------------------------------------------------------------------
# Fake in-process ChromaDB (mirrors test_ai_journal.py)
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
        ][:n_results]
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
    """Install in-process fake chromadb + isolated persist dir per test."""
    fake_module = _FakeChromaDB()
    fake_ef = _NoopEmbeddingFunction()
    monkeypatch.setattr(mem, "_load_chromadb", lambda: fake_module)
    monkeypatch.setattr(mem, "_load_embedding_function", lambda: fake_ef)
    monkeypatch.setattr(mem, "_default_project_root", lambda: tmp_path)
    mem.reset_memory_store()
    yield
    mem.reset_memory_store()


VALID_PROPOSAL = {
    "title": "Dead Stock Dashboard გვერდი",
    "problem": "dead stock-ის შესახებ user-ი 3-ჯერ დაუბრუნდა ერთ კვირაში",
    "benefit": "15-20 წთ/კვირაში, ადრეული გაფრთხილება gaunaaynad stock-ზე",
    "mvp_scope": "Top-10 ცხრილი + warning ფერადი სტატუსი + ერთი ღილაკი dealer return",
    "data_needed": "უკვე არსებული imported_products + retail_sales",
    "time_estimate": "2-3 დღე",
    "risk_critique": "barcode drift 30.3% — ზუსტი ციფრები ვერ გვექნება; უწევს dataset cleanup-ს",
}


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


class TestCoDesignerConstants:
    def test_proposal_kind_in_journal_kinds(self):
        assert "proposal" in JOURNAL_KINDS
        assert PROPOSAL_KIND == "proposal"

    def test_journal_kinds_has_six_entries(self):
        """Phase 3.1 grew 4→5 (+ proposal); Phase 4A grew 5→6 (+ repayment_plan)."""
        assert len(JOURNAL_KINDS) == 6

    def test_auto_cleanup_days_is_30(self):
        assert PROPOSAL_AUTO_CLEANUP_DAYS == 30

    def test_proposal_meta_keys_exactly_six(self):
        assert len(_PROPOSAL_META_KEYS) == 6

    def test_proposal_meta_keys_match_field_names(self):
        """Ordered tuples must align 1-to-1."""
        assert len(_PROPOSAL_META_KEYS) == len(_PROPOSAL_FIELD_NAMES)

    def test_proposal_field_names_ordered(self):
        assert _PROPOSAL_FIELD_NAMES == (
            "problem",
            "benefit",
            "mvp_scope",
            "data_needed",
            "time_estimate",
            "risk_critique",
        )

    def test_proposal_meta_key_strings_unique(self):
        assert len(set(_PROPOSAL_META_KEYS)) == 6

    def test_proposal_field_char_bounds(self):
        assert MIN_PROPOSAL_FIELD_CHARS >= 1
        assert MAX_PROPOSAL_FIELD_CHARS > MIN_PROPOSAL_FIELD_CHARS
        assert MAX_PROPOSAL_FIELD_CHARS <= 2000


# ---------------------------------------------------------------------------
# _coerce_proposal_field
# ---------------------------------------------------------------------------


class TestCoerceProposalField:
    def test_none_rejected(self):
        text, err = _coerce_proposal_field(None, field_name="problem")
        assert text is None
        assert err and "problem" in err

    def test_non_string_rejected(self):
        text, err = _coerce_proposal_field(42, field_name="benefit")
        assert text is None
        assert err

    def test_too_short_rejected(self):
        text, err = _coerce_proposal_field("hi", field_name="mvp_scope")
        assert text is None
        assert err and "მოკლეა" in err

    def test_strip_whitespace(self):
        text, err = _coerce_proposal_field(
            "   realistic-benefit-description  ", field_name="benefit"
        )
        assert err is None
        assert text == "realistic-benefit-description"

    def test_happy_path(self):
        text, err = _coerce_proposal_field(
            "კონკრეტული sales team-ის პრობლემა", field_name="problem"
        )
        assert err is None
        assert text == "კონკრეტული sales team-ის პრობლემა"

    def test_oversized_truncated(self):
        big = "ა" * (MAX_PROPOSAL_FIELD_CHARS + 50)
        text, err = _coerce_proposal_field(big, field_name="mvp_scope")
        assert err is None
        assert len(text) <= MAX_PROPOSAL_FIELD_CHARS + 1  # +1 ellipsis


# ---------------------------------------------------------------------------
# add_journal_entry with kind="proposal"
# ---------------------------------------------------------------------------


class TestAddProposalEntry:
    def test_happy_path_returns_proposal(self):
        result = add_journal_entry(
            VALID_PROPOSAL["title"],
            "proposal",
            **{k: VALID_PROPOSAL[k] for k in _PROPOSAL_FIELD_NAMES},
        )
        assert result.get("ok") is True
        assert result["kind"] == "proposal"
        assert result["status"] == "open"
        assert "proposal" in result
        for field in _PROPOSAL_FIELD_NAMES:
            assert result["proposal"][field] == VALID_PROPOSAL[field]

    def test_missing_problem_rejected(self):
        result = add_journal_entry(
            VALID_PROPOSAL["title"],
            "proposal",
            benefit=VALID_PROPOSAL["benefit"],
            mvp_scope=VALID_PROPOSAL["mvp_scope"],
            data_needed=VALID_PROPOSAL["data_needed"],
            time_estimate=VALID_PROPOSAL["time_estimate"],
            risk_critique=VALID_PROPOSAL["risk_critique"],
        )
        assert "error" in result
        assert "problem" in result["error"]

    def test_missing_risk_critique_rejected(self):
        result = add_journal_entry(
            VALID_PROPOSAL["title"],
            "proposal",
            problem=VALID_PROPOSAL["problem"],
            benefit=VALID_PROPOSAL["benefit"],
            mvp_scope=VALID_PROPOSAL["mvp_scope"],
            data_needed=VALID_PROPOSAL["data_needed"],
            time_estimate=VALID_PROPOSAL["time_estimate"],
        )
        assert "error" in result
        assert "risk_critique" in result["error"]

    def test_too_short_field_rejected(self):
        result = add_journal_entry(
            VALID_PROPOSAL["title"],
            "proposal",
            **{**{k: VALID_PROPOSAL[k] for k in _PROPOSAL_FIELD_NAMES}, "problem": "x"},
        )
        assert "error" in result
        assert "problem" in result["error"]

    def test_proposal_fields_on_promise_rejected(self):
        """Schema isolation — proposal fields on non-proposal kind must fail."""
        result = add_journal_entry(
            "Alpha-ს ვალის გადამოწმება",
            "promise",
            problem="random problem text",
        )
        assert "error" in result
        assert "proposal" in result["error"].lower()

    def test_proposal_fields_on_recommendation_rejected(self):
        result = add_journal_entry(
            "ოზურგეთის აუდიტი",
            "recommendation",
            benefit="15 წთ/კვირაში",
        )
        assert "error" in result
        assert "proposal" in result["error"].lower()

    def test_plain_promise_without_proposal_fields_still_works(self):
        """Regression guard — Phase 3.1 must not break the old 4 kinds."""
        result = add_journal_entry(
            "Alpha-ს ვალის გადამოწმება",
            "promise",
            due_date="2026-05-01",
        )
        assert result.get("ok") is True
        assert result["kind"] == "promise"
        assert "proposal" not in result

    def test_tags_auto_add_kind_proposal(self):
        result = add_journal_entry(
            VALID_PROPOSAL["title"],
            "proposal",
            **{k: VALID_PROPOSAL[k] for k in _PROPOSAL_FIELD_NAMES},
        )
        assert "kind:proposal" in result["tags"]
        assert "journal" in result["tags"]
        assert "status:open" in result["tags"]

    def test_user_topic_tags_preserved(self):
        result = add_journal_entry(
            VALID_PROPOSAL["title"],
            "proposal",
            tags=["topic:dead_stock", "feature:dashboard_page"],
            **{k: VALID_PROPOSAL[k] for k in _PROPOSAL_FIELD_NAMES},
        )
        assert "topic:dead_stock" in result["tags"]
        assert "feature:dashboard_page" in result["tags"]

    def test_unknown_kind_still_rejected(self):
        result = add_journal_entry("foo", "task")
        assert "error" in result


# ---------------------------------------------------------------------------
# list_journal_entries with proposal kind
# ---------------------------------------------------------------------------


class TestListProposalEntries:
    def _seed_proposal(self, title_suffix: str = "") -> str:
        result = add_journal_entry(
            VALID_PROPOSAL["title"] + title_suffix,
            "proposal",
            **{k: VALID_PROPOSAL[k] for k in _PROPOSAL_FIELD_NAMES},
        )
        return result["entry_id"]

    def test_list_proposal_kind_returns_payload(self):
        self._seed_proposal()
        out = list_journal_entries(kind="proposal")
        assert out["count"] >= 1
        first = out["entries"][0]
        assert first["kind"] == "proposal"
        assert "proposal" in first
        assert first["proposal"]["problem"] == VALID_PROPOSAL["problem"]
        assert first["proposal"]["risk_critique"] == VALID_PROPOSAL["risk_critique"]

    def test_list_all_includes_proposals(self):
        self._seed_proposal()
        add_journal_entry(
            "Alpha-ს ვალი", "promise", due_date="2026-05-10",
        )
        out = list_journal_entries()
        kinds = {e["kind"] for e in out["entries"]}
        assert "proposal" in kinds
        assert "promise" in kinds

    def test_filter_kind_promise_excludes_proposals(self):
        self._seed_proposal()
        add_journal_entry("Alpha", "promise", due_date="2026-05-10")
        out = list_journal_entries(kind="promise")
        assert all(e["kind"] == "promise" for e in out["entries"])
        assert all("proposal" not in e for e in out["entries"])

    def test_filter_status_open_with_kind_proposal(self):
        self._seed_proposal()
        out = list_journal_entries(kind="proposal", status="open")
        assert out["count"] == 1
        assert out["entries"][0]["status"] == "open"


# ---------------------------------------------------------------------------
# _hit_to_entry proposal surface
# ---------------------------------------------------------------------------


class TestHitToEntryProposalSurface:
    def test_proposal_fields_surface_when_present(self):
        fake_hit = {
            "id": "journal_abc",
            "summary": "foo",
            "created_at": "2026-04-20T15:00:00",
            "tags": ["journal", "kind:proposal"],
            "metadata": {
                "journal_title": "T",
                "journal_kind": "proposal",
                "journal_status": "open",
                "journal_due_date": "",
                META_PROPOSAL_PROBLEM_KEY: "p1",
                META_PROPOSAL_BENEFIT_KEY: "b1",
                META_PROPOSAL_MVP_KEY: "m1",
                META_PROPOSAL_DATA_KEY: "d1",
                META_PROPOSAL_TIME_KEY: "2 days",
                META_PROPOSAL_RISK_KEY: "r1",
            },
        }
        entry = _hit_to_entry(fake_hit, today=_dt.date(2026, 4, 20))
        assert "proposal" in entry
        assert entry["proposal"]["problem"] == "p1"
        assert entry["proposal"]["risk_critique"] == "r1"

    def test_no_proposal_fields_no_proposal_key(self):
        fake_hit = {
            "id": "journal_xyz",
            "summary": "foo",
            "created_at": "2026-04-20T15:00:00",
            "tags": ["journal", "kind:promise"],
            "metadata": {
                "journal_title": "Alpha",
                "journal_kind": "promise",
                "journal_status": "open",
                "journal_due_date": "2026-05-01",
            },
        }
        entry = _hit_to_entry(fake_hit, today=_dt.date(2026, 4, 20))
        assert "proposal" not in entry
        assert entry["kind"] == "promise"

    def test_partial_proposal_still_surfaced_safely(self):
        """Degenerate row (shouldn't happen in practice) still returns strings."""
        fake_hit = {
            "id": "journal_partial",
            "summary": "foo",
            "created_at": "2026-04-20T15:00:00",
            "tags": [],
            "metadata": {
                "journal_title": "half-proposal",
                "journal_kind": "proposal",
                "journal_status": "open",
                META_PROPOSAL_PROBLEM_KEY: "only-problem",
            },
        }
        entry = _hit_to_entry(fake_hit, today=_dt.date(2026, 4, 20))
        assert "proposal" in entry
        assert entry["proposal"]["problem"] == "only-problem"
        # Missing fields coerce to empty strings, not None.
        assert entry["proposal"]["benefit"] == ""
        assert entry["proposal"]["risk_critique"] == ""


# ---------------------------------------------------------------------------
# cleanup_stale_proposals
# ---------------------------------------------------------------------------


class TestCleanupStaleProposals:
    def _seed_proposal(self) -> str:
        result = add_journal_entry(
            VALID_PROPOSAL["title"],
            "proposal",
            **{k: VALID_PROPOSAL[k] for k in _PROPOSAL_FIELD_NAMES},
        )
        return result["entry_id"]

    def test_no_proposals_returns_zero(self):
        out = cleanup_stale_proposals()
        assert out["ok"] is True
        assert out["cancelled_count"] == 0
        assert out["cancelled_ids"] == []

    def test_fresh_proposal_not_cancelled(self):
        self._seed_proposal()
        out = cleanup_stale_proposals()
        assert out["cancelled_count"] == 0

    def test_future_today_never_cancels_present_proposals(self):
        """If today is BEFORE the proposal's created_at, cutoff is even earlier."""
        self._seed_proposal()
        future = _dt.date.today() + _dt.timedelta(days=1)
        out = cleanup_stale_proposals(today=future)
        assert out["cancelled_count"] == 0

    def test_old_proposal_gets_cancelled(self):
        """Seed a proposal then call cleanup with today=created_at + 31 days."""
        entry_id = self._seed_proposal()
        # Directly patch the row's created_at to 45 days ago to simulate age.
        store = mem.get_memory_store()
        col = store.collection("chat")
        doc, meta = col._docs[entry_id]
        old = _dt.date.today() - _dt.timedelta(days=45)
        meta["created_at"] = old.isoformat() + "T09:00:00"
        col._docs[entry_id] = (doc, meta)

        out = cleanup_stale_proposals()
        assert out["cancelled_count"] == 1
        assert entry_id in out["cancelled_ids"]
        # Verify status actually flipped
        refreshed = list_journal_entries(kind="proposal")
        assert any(
            e["entry_id"] == entry_id and e["status"] == "cancelled"
            for e in refreshed["entries"]
        )

    def test_non_proposal_entries_untouched(self):
        # Seed a promise that's 45 days old — cleanup must NOT touch it.
        result = add_journal_entry("Old promise", "promise")
        promise_id = result["entry_id"]
        store = mem.get_memory_store()
        col = store.collection("chat")
        doc, meta = col._docs[promise_id]
        old = _dt.date.today() - _dt.timedelta(days=60)
        meta["created_at"] = old.isoformat() + "T09:00:00"
        col._docs[promise_id] = (doc, meta)

        out = cleanup_stale_proposals()
        assert out["cancelled_count"] == 0

        # Promise still open
        refreshed = list_journal_entries(kind="promise")
        assert refreshed["entries"][0]["status"] == "open"

    def test_custom_older_than_days(self):
        entry_id = self._seed_proposal()
        store = mem.get_memory_store()
        col = store.collection("chat")
        doc, meta = col._docs[entry_id]
        old = _dt.date.today() - _dt.timedelta(days=10)
        meta["created_at"] = old.isoformat() + "T09:00:00"
        col._docs[entry_id] = (doc, meta)

        # 30-day cutoff → NOT cancelled
        out = cleanup_stale_proposals(older_than_days=30)
        assert out["cancelled_count"] == 0

        # 5-day cutoff → cancelled
        out = cleanup_stale_proposals(older_than_days=5)
        assert out["cancelled_count"] == 1


# ---------------------------------------------------------------------------
# PROPOSE_FEATURE_TOOL schema
# ---------------------------------------------------------------------------


class TestProposeFeatureToolSchema:
    def test_tool_name(self):
        assert PROPOSE_FEATURE_TOOL["name"] == "propose_feature"

    def test_required_fields_present(self):
        required = set(PROPOSE_FEATURE_TOOL["input_schema"]["required"])
        assert required == {
            "title",
            "problem",
            "benefit",
            "mvp_scope",
            "data_needed",
            "time_estimate",
            "risk_critique",
        }

    def test_all_seven_fields_in_properties(self):
        props = PROPOSE_FEATURE_TOOL["input_schema"]["properties"]
        for name in ["title", "problem", "benefit", "mvp_scope",
                     "data_needed", "time_estimate", "risk_critique"]:
            assert name in props
            assert props[name]["type"] == "string"

    def test_tags_optional_array(self):
        props = PROPOSE_FEATURE_TOOL["input_schema"]["properties"]
        assert props["tags"]["type"] == "array"
        assert "tags" not in PROPOSE_FEATURE_TOOL["input_schema"]["required"]

    def test_additional_properties_off(self):
        assert (
            PROPOSE_FEATURE_TOOL["input_schema"]["additionalProperties"] is False
        )

    def test_description_mentions_pull_only(self):
        desc = PROPOSE_FEATURE_TOOL["description"]
        assert "Pull-only" in desc or "pull-only" in desc.lower()

    def test_description_lists_anti_triggers(self):
        desc = PROPOSE_FEATURE_TOOL["description"]
        assert "Anti-triggers" in desc or "NEVER" in desc

    def test_description_mentions_critic_mandate(self):
        desc = PROPOSE_FEATURE_TOOL["description"]
        assert "SELF-critique" in desc or "risk_critique" in desc

    def test_description_lists_six_mandatory_fields(self):
        desc = PROPOSE_FEATURE_TOOL["description"]
        assert "problem" in desc
        assert "benefit" in desc
        assert "mvp_scope" in desc
        assert "data_needed" in desc
        assert "time_estimate" in desc
        assert "risk_critique" in desc

    def test_propose_feature_is_last_in_schemas(self):
        assert TOOL_SCHEMAS[-1]["name"] == "propose_feature"

    def test_propose_feature_at_tail(self):
        # Tail index shifts as new tools insert before the investigator block:
        # Phase 4A: 17; Phase 2.1: 18; Phase 2.2: 19; Phase 2.5: 20;
        # Phase 2.6: 21; Phase 5.1: 24 (+3 VAT tools).
        assert TOOL_SCHEMAS[-1]["name"] == "propose_feature"
        assert TOOL_SCHEMAS[24]["name"] == "propose_feature"


# ---------------------------------------------------------------------------
# ToolDispatcher routing
# ---------------------------------------------------------------------------


class TestProposeFeatureDispatch:
    def test_dispatch_happy_path(self):
        disp = ToolDispatcher(lambda: {})
        result = disp.dispatch(
            "propose_feature",
            {"title": VALID_PROPOSAL["title"],
             "problem": VALID_PROPOSAL["problem"],
             "benefit": VALID_PROPOSAL["benefit"],
             "mvp_scope": VALID_PROPOSAL["mvp_scope"],
             "data_needed": VALID_PROPOSAL["data_needed"],
             "time_estimate": VALID_PROPOSAL["time_estimate"],
             "risk_critique": VALID_PROPOSAL["risk_critique"]},
        )
        assert result.get("ok") is True
        assert result["kind"] == "proposal"
        assert "proposal" in result

    def test_dispatch_missing_field_surfaces_error(self):
        disp = ToolDispatcher(lambda: {})
        result = disp.dispatch(
            "propose_feature",
            {"title": VALID_PROPOSAL["title"]},  # missing all six fields
        )
        assert "error" in result

    def test_dispatch_unknown_tool_rejected(self):
        disp = ToolDispatcher(lambda: {})
        result = disp.dispatch("propose_weapon", {})
        assert "error" in result

    def test_dispatch_with_tags(self):
        disp = ToolDispatcher(lambda: {})
        result = disp.dispatch(
            "propose_feature",
            {"title": VALID_PROPOSAL["title"],
             "problem": VALID_PROPOSAL["problem"],
             "benefit": VALID_PROPOSAL["benefit"],
             "mvp_scope": VALID_PROPOSAL["mvp_scope"],
             "data_needed": VALID_PROPOSAL["data_needed"],
             "time_estimate": VALID_PROPOSAL["time_estimate"],
             "risk_critique": VALID_PROPOSAL["risk_critique"],
             "tags": ["topic:dashboard"]},
        )
        assert result.get("ok") is True
        assert "topic:dashboard" in result["tags"]


# ---------------------------------------------------------------------------
# SYSTEM_PROMPT_KA Co-Designer section presence
# ---------------------------------------------------------------------------


class TestCoDesignerPromptWiring:
    def test_section_header_present(self):
        assert "🎨 Co-Designer რეჟიმი" in prompts_mod.SYSTEM_PROMPT_KA

    def test_phase_3_1_tag(self):
        assert "Phase 3.1" in prompts_mod.SYSTEM_PROMPT_KA

    def test_pull_only_emphasized(self):
        assert "PULL-ONLY" in prompts_mod.SYSTEM_PROMPT_KA

    def test_trigger_phrases_listed(self):
        prompt = prompts_mod.SYSTEM_PROMPT_KA
        assert "რას შემომთავაზებდი" in prompt
        assert "შემომთავაზე" in prompt
        assert "co-designer" in prompt

    def test_anti_trigger_section_present(self):
        assert "Anti-triggers" in prompts_mod.SYSTEM_PROMPT_KA

    def test_anti_trigger_rejects_strategic_questions(self):
        """Strategic questions (like today's sales dog-food) must NOT trigger proposals."""
        prompt = prompts_mod.SYSTEM_PROMPT_KA
        assert "სტრატეგიული კითხვა" in prompt
        # NO proposal in response for strategic questions — explicit rule.
        assert "NO `propose_feature`" in prompt

    def test_anti_trigger_rejects_crisis_auto_propose(self):
        """Crisis (e.g. −80% margin) must NOT auto-trigger a proposal."""
        prompt = prompts_mod.SYSTEM_PROMPT_KA
        assert "კრიზისული ანალიზი" in prompt
        assert "auto-propose" in prompt

    def test_anti_trigger_rejects_frequency_auto_trigger(self):
        """3+ questions on the same topic must NOT auto-trigger."""
        prompt = prompts_mod.SYSTEM_PROMPT_KA
        assert "3+ ჯერ" in prompt or "3+ ჯერ გამოცდილი" in prompt

    def test_six_mandatory_fields_listed(self):
        prompt = prompts_mod.SYSTEM_PROMPT_KA
        for name in _PROPOSAL_FIELD_NAMES:
            assert name in prompt

    def test_critic_hat_mandate_present(self):
        assert "კრიტიკოსი მანდატი" in prompts_mod.SYSTEM_PROMPT_KA

    def test_critic_hat_forbids_empty_risk(self):
        """`"რისკი არ არის"` must be explicitly forbidden."""
        assert "რისკი არ არის" in prompts_mod.SYSTEM_PROMPT_KA
        assert "აკრძალულია" in prompts_mod.SYSTEM_PROMPT_KA

    def test_id_citation_mandate_present(self):
        assert "ID-citation" in prompts_mod.SYSTEM_PROMPT_KA

    def test_three_proposal_limit_specified(self):
        prompt = prompts_mod.SYSTEM_PROMPT_KA
        assert "მაქსიმუმ 3" in prompt or "1-3" in prompt

    def test_propose_feature_tool_referenced(self):
        assert "propose_feature" in prompts_mod.SYSTEM_PROMPT_KA

    def test_section_topology_after_phase_2_12(self):
        """🎨 Co-Designer must appear AFTER 📞 Phase 2.12 and BEFORE 🔄 Part D."""
        prompt = prompts_mod.SYSTEM_PROMPT_KA
        idx_212 = prompt.find("📞 მომწოდებელთან")
        idx_co = prompt.find("🎨 Co-Designer")
        idx_part_d = prompt.find("საკუთარი თავის გასწორების")
        assert idx_212 > 0
        assert idx_co > idx_212
        assert idx_part_d > idx_co


# ---------------------------------------------------------------------------
# SYSTEM_PROMPT_KA_INVESTIGATOR do-not-touch
# ---------------------------------------------------------------------------


class TestInvestigatorPromptUntouched:
    @pytest.mark.parametrize(
        "marker",
        [
            "🎨 Co-Designer რეჟიმი",
            "PULL-ONLY",
            "Trigger ფრაზები",
            "Anti-triggers — არცერთ შემთხვევაში",
            "propose_feature",
            "კრიტიკოსი მანდატი",
            "ID-citation მანდატი",
            "Phase 3.1",
            "რას შემომთავაზებდი",
        ],
    )
    def test_investigator_prompt_has_no_co_designer_marker(self, marker):
        assert marker not in prompts_mod.SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_investigator_still_investigator(self):
        """Sanity — investigator prompt still has its own identity."""
        assert "investigator" in prompts_mod.SYSTEM_PROMPT_KA_INVESTIGATOR.lower() \
            or "detective" in prompts_mod.SYSTEM_PROMPT_KA_INVESTIGATOR.lower() \
            or "🔍" in prompts_mod.SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_investigator_does_not_expose_propose_feature(self):
        assert "propose_feature" not in prompts_mod.SYSTEM_PROMPT_KA_INVESTIGATOR
