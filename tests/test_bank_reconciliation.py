"""
Unit tests for dashboard_pipeline.bank_reconciliation

Covers pure functions: display name, reconciliation line building,
exact matching (tax_id, IBAN, names), scoring, skip/force logic.
"""
import pytest

from dashboard_pipeline.bank_reconciliation import (
    _build_reconciliation_line,
    _candidate_preview_list,
    _line_has_explicit_skip,
    _line_force_non_supplier_for_supplier,
    _line_to_row_for_category,
    _match_by_exact_iban,
    _match_by_exact_names,
    _match_by_exact_tax_id,
    _score_supplier_candidates,
    _supplier_display_name,
)


# ── Fixtures ────────────────────────────────────────────────────────

def _make_supplier_master(suppliers=None, **extra):
    """Build a minimal supplier_master dict for testing."""
    master = {"suppliers_by_id": suppliers or {}}
    master.update(extra)
    return master


def _make_supplier(
    tax_id,
    official_name_raw="",
    official_names=None,
    aliases=None,
    person_aliases=None,
    ibans=None,
    account_hints=None,
    force_non_supplier_keywords=None,
    registry_official_names=None,
    rs_official_names=None,
):
    return {
        "tax_id": tax_id,
        "official_name_raw": official_name_raw,
        "official_names": official_names or set(),
        "aliases": aliases or set(),
        "person_aliases": person_aliases or set(),
        "ibans": ibans or set(),
        "account_hints": account_hints or set(),
        "force_non_supplier_keywords": force_non_supplier_keywords or set(),
        "registry_official_names": registry_official_names or set(),
        "rs_official_names": rs_official_names or set(),
        "official_name_truth_source": "",
        "source": set(),
        "notes": [],
        "legacy_truth_assist_ibans": set(),
        "registry_aliases": set(),
        "registry_person_aliases": set(),
        "registry_ibans": set(),
        "registry_account_hints": set(),
    }


# ── _supplier_display_name ──────────────────────────────────────────

class TestSupplierDisplayName:
    def test_official_name_raw(self):
        master = _make_supplier_master(
            {"111": _make_supplier("111", official_name_raw="ელიტფუდი 2")}
        )
        assert _supplier_display_name("111", master) == "ელიტფუდი 2"

    def test_fallback_to_official_names(self):
        master = _make_supplier_master(
            {"222": _make_supplier("222", official_names={"ტესტი", "abc"})}
        )
        # sorted, first alphabetically
        name = _supplier_display_name("222", master)
        assert name in ("abc", "ტესტი")

    def test_unknown_supplier_fallback_name(self):
        master = _make_supplier_master()
        assert _supplier_display_name("999", master, "ფოლბეკი") == "ფოლბეკი"

    def test_unknown_supplier_fallback_tax_id(self):
        master = _make_supplier_master()
        assert _supplier_display_name("999", master) == "999"

    def test_empty_tax_id(self):
        master = _make_supplier_master()
        assert _supplier_display_name("", master) == ""


# ── _build_reconciliation_line ──────────────────────────────────────

class TestBuildReconciliationLine:
    def test_basic_fields(self):
        line = _build_reconciliation_line(
            bank="BOG",
            file_name="test.xlsx",
            row_date="2025-01-15",
            amount=500.0,
            raw_tax_id="123456789",
        )
        assert line["source_bank"] == "BOG"
        assert line["file_name"] == "test.xlsx"
        assert line["row_date"] == "2025-01-15"
        assert line["amount"] == 500.0
        assert line["raw_tax_id"] == "123456789"
        assert "123456789" in line["extracted_tax_ids"]

    def test_tax_id_extracted_from_purpose(self):
        line = _build_reconciliation_line(
            bank="TBC",
            file_name="f.xlsx",
            row_date="2025-01-01",
            amount=100.0,
            purpose_text="payment for 987654321",
        )
        assert "987654321" in line["extracted_tax_ids"]

    def test_none_values_handled(self):
        line = _build_reconciliation_line(
            bank="BOG",
            file_name="f.xlsx",
            row_date="",
            amount=0,
        )
        assert line["amount"] == 0.0
        assert line["raw_tax_id"] == ""
        assert line["raw_receiver_name"] == ""

    def test_blob_text_contains_all_fields(self):
        line = _build_reconciliation_line(
            bank="BOG",
            file_name="f.xlsx",
            row_date="",
            amount=100,
            receiver_name="receiver",
            partner_name="partner",
            purpose_text="purpose",
            description_text="desc",
            account_text="account",
            raw_tax_id="111222333",
        )
        assert "receiver" in line["blob_text"]
        assert "partner" in line["blob_text"]
        assert "purpose" in line["blob_text"]
        assert "desc" in line["blob_text"]
        assert "account" in line["blob_text"]


# ── _line_to_row_for_category ───────────────────────────────────────

class TestLineToRowForCategory:
    def test_basic_conversion(self):
        line = {
            "source_bank": "BOG",
            "file_name": "test.xlsx",
            "row_date": "2025-01-15",
            "amount": 500.0,
            "raw_tax_id": "111",
            "raw_receiver_name": "მიმღები",
            "raw_description": "აღწერა",
            "raw_purpose": "დანიშნულება",
        }
        row = _line_to_row_for_category(line, reason="test reason")
        assert row["ბანკი"] == "BOG"
        assert row["თანხა"] == 500.0
        assert row["მიმღები_სახელი"] == "მიმღები"
        assert row["მიზეზი"] == "test reason"

    def test_fallback_to_partner_name(self):
        line = {
            "source_bank": "TBC",
            "raw_receiver_name": "",
            "raw_partner_name": "პარტნიორი",
        }
        row = _line_to_row_for_category(line)
        assert row["მიმღები_სახელი"] == "პარტნიორი"


# ── _match_by_exact_tax_id ──────────────────────────────────────────

class TestMatchByExactTaxId:
    def test_single_match(self):
        master = _make_supplier_master(
            {"123456789": _make_supplier("123456789")}
        )
        line = {"extracted_tax_ids": ["123456789"]}
        tid, status, reason, truth = _match_by_exact_tax_id(line, master)
        assert tid == "123456789"
        assert status == "matched_exact_id"

    def test_no_match(self):
        master = _make_supplier_master(
            {"123456789": _make_supplier("123456789")}
        )
        line = {"extracted_tax_ids": ["999999999"]}
        tid, status, reason, truth = _match_by_exact_tax_id(line, master)
        assert tid is None
        assert status == ""

    def test_ambiguous(self):
        master = _make_supplier_master({
            "111111111": _make_supplier("111111111"),
            "222222222": _make_supplier("222222222"),
        })
        line = {"extracted_tax_ids": ["111111111", "222222222"]}
        tid, status, reason, truth = _match_by_exact_tax_id(line, master)
        assert tid is None
        assert status == "ambiguous"

    def test_empty_extracted(self):
        master = _make_supplier_master()
        line = {"extracted_tax_ids": []}
        tid, status, reason, truth = _match_by_exact_tax_id(line, master)
        assert tid is None
        assert status == ""


# ── _match_by_exact_iban ────────────────────────────────────────────

class TestMatchByExactIban:
    def test_single_iban_match(self):
        master = _make_supplier_master(
            iban_to_id={"GE60BG0000000667583800": "111111111"},
            account_hint_to_id={},
        )
        line = {"extracted_ibans": ["GE60BG0000000667583800"], "extracted_account_hints": []}
        tid, status, reason, truth = _match_by_exact_iban(line, master)
        assert tid == "111111111"
        assert status == "matched_exact_iban"

    def test_no_iban_match(self):
        master = _make_supplier_master(iban_to_id={}, account_hint_to_id={})
        line = {"extracted_ibans": ["GE99XX0000000000000000"], "extracted_account_hints": []}
        tid, status, reason, truth = _match_by_exact_iban(line, master)
        assert tid is None
        assert status == ""

    def test_ambiguous_iban(self):
        master = _make_supplier_master(
            iban_to_id={
                "GE60BG0000000667583800": "111111111",
                "GE78BG0000000269727500": "222222222",
            },
            account_hint_to_id={},
        )
        line = {
            "extracted_ibans": ["GE60BG0000000667583800", "GE78BG0000000269727500"],
            "extracted_account_hints": [],
        }
        tid, status, reason, truth = _match_by_exact_iban(line, master)
        assert tid is None
        assert status == "ambiguous"

    def test_empty_ibans(self):
        master = _make_supplier_master(iban_to_id={}, account_hint_to_id={})
        line = {"extracted_ibans": [], "extracted_account_hints": []}
        tid, status, reason, truth = _match_by_exact_iban(line, master)
        assert tid is None
        assert status == ""


# ── _match_by_exact_names ──────────────────────────────────────────

class TestMatchByExactNames:
    def test_registry_legal_name_match(self):
        master = _make_supplier_master(
            registry_legal_name_to_id={"ელიტფუდი 2": "412761097"},
            rs_legal_name_to_id={},
            alias_to_id={},
            person_alias_to_id={},
        )
        line = {"raw_receiver_name": "შპს ელიტფუდი 2", "raw_partner_name": "", "raw_purpose": "", "raw_description": ""}
        tid, status, reason, truth = _match_by_exact_names(line, master)
        assert tid == "412761097"
        assert status == "matched_exact_name"

    def test_alias_match(self):
        master = _make_supplier_master(
            registry_legal_name_to_id={},
            rs_legal_name_to_id={},
            alias_to_id={"ტესტ ალიასი": "999999999"},
            person_alias_to_id={},
        )
        line = {"raw_receiver_name": "ტესტ ალიასი", "raw_partner_name": "", "raw_purpose": "", "raw_description": ""}
        tid, status, reason, truth = _match_by_exact_names(line, master)
        assert tid == "999999999"
        assert status == "matched_alias"

    def test_no_match(self):
        master = _make_supplier_master(
            registry_legal_name_to_id={},
            rs_legal_name_to_id={},
            alias_to_id={},
            person_alias_to_id={},
        )
        line = {"raw_receiver_name": "უცნობი", "raw_partner_name": "", "raw_purpose": "", "raw_description": ""}
        tid, status, reason, truth = _match_by_exact_names(line, master)
        assert tid is None
        assert status == ""


# ── _line_has_explicit_skip ─────────────────────────────────────────

class TestLineHasExplicitSkip:
    def test_skip_keyword_found(self):
        master = _make_supplier_master(explicit_skip_keywords={"skip_me"})
        line = {"blob_lower": "this has skip_me in it"}
        found, reason = _line_has_explicit_skip(line, master)
        assert found is True
        assert "skip_me" in reason

    def test_no_skip(self):
        master = _make_supplier_master(explicit_skip_keywords={"skip_me"})
        line = {"blob_lower": "normal payment text"}
        found, reason = _line_has_explicit_skip(line, master)
        assert found is False
        assert reason == ""

    def test_empty_keywords(self):
        master = _make_supplier_master(explicit_skip_keywords=set())
        line = {"blob_lower": "anything"}
        found, reason = _line_has_explicit_skip(line, master)
        assert found is False


# ── _line_force_non_supplier_for_supplier ───────────────────────────

class TestLineForceNonSupplier:
    def test_keyword_match(self):
        master = _make_supplier_master({
            "111": _make_supplier("111", force_non_supplier_keywords={"გარანტია"})
        })
        line = {"blob_lower": "გარანტია და სხვა"}
        found, reason = _line_force_non_supplier_for_supplier(line, "111", master)
        assert found is True

    def test_no_keyword_match(self):
        master = _make_supplier_master({
            "111": _make_supplier("111", force_non_supplier_keywords={"გარანტია"})
        })
        line = {"blob_lower": "ჩვეულებრივი გადახდა"}
        found, reason = _line_force_non_supplier_for_supplier(line, "111", master)
        assert found is False

    def test_unknown_supplier(self):
        master = _make_supplier_master()
        line = {"blob_lower": "anything"}
        found, reason = _line_force_non_supplier_for_supplier(line, "999", master)
        assert found is False


# ── _score_supplier_candidates ──────────────────────────────────────

class TestScoreSupplierCandidates:
    def test_legal_name_match_scores(self):
        master = _make_supplier_master(
            suppliers={
                "111": _make_supplier("111", official_names={"ელიტფუდი"}),
            },
            token_to_tax_ids={"ელიტფუდი": {"111"}},
        )
        line = {
            "raw_receiver_name": "ელიტფუდი",
            "raw_partner_name": "",
            "raw_purpose": "",
            "raw_description": "",
            "blob_text": "ელიტფუდი",
            "blob_lower": "ელიტფუდი",
            "extracted_tax_ids": [],
        }
        scored = _score_supplier_candidates(line, master, waybill_index=None)
        assert len(scored) >= 1
        assert scored[0]["tax_id"] == "111"
        assert scored[0]["score"] >= 36.0

    def test_no_candidates(self):
        master = _make_supplier_master(token_to_tax_ids={})
        line = {
            "raw_receiver_name": "x",
            "raw_partner_name": "",
            "raw_purpose": "",
            "raw_description": "",
            "blob_text": "x",
            "blob_lower": "x",
            "extracted_tax_ids": [],
        }
        scored = _score_supplier_candidates(line, master, waybill_index=None)
        assert scored == []

    def test_tax_id_in_text_boost(self):
        master = _make_supplier_master(
            suppliers={"111": _make_supplier("111")},
            token_to_tax_ids={},
        )
        line = {
            "raw_receiver_name": "",
            "raw_partner_name": "",
            "raw_purpose": "",
            "raw_description": "",
            "blob_text": "111",
            "blob_lower": "111",
            "extracted_tax_ids": ["111"],
        }
        # Tax ID alone won't generate tokens (len < 4 Georgian chars),
        # but extracted_tax_ids check still fires if candidate is found
        scored = _score_supplier_candidates(line, master, waybill_index=None)
        # No token >= 4 chars matches, so no candidates gathered
        assert scored == []


# ── _candidate_preview_list ─────────────────────────────────────────

class TestCandidatePreviewList:
    def test_basic_preview(self):
        master = _make_supplier_master({
            "111": _make_supplier("111", official_name_raw="ტესტი")
        })
        candidates = [
            {"tax_id": "111", "score": 45.0, "reasons": ["tax_id_in_text"]},
        ]
        preview = _candidate_preview_list(candidates, master)
        assert len(preview) == 1
        assert preview[0]["tax_id"] == "111"
        assert preview[0]["supplier_name"] == "ტესტი"
        assert preview[0]["score"] == 45.0

    def test_max_five(self):
        master = _make_supplier_master()
        candidates = [{"tax_id": str(i), "score": float(i), "reasons": []} for i in range(10)]
        preview = _candidate_preview_list(candidates, master)
        assert len(preview) == 5

    def test_empty(self):
        preview = _candidate_preview_list([], _make_supplier_master())
        assert preview == []
