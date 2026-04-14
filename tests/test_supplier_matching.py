"""
Unit tests for dashboard_pipeline.supplier_matching

Covers pure functions: normalize_name, extract helpers, matching logic,
BOG receiver mapping, truth layer lookups.
"""
import pytest

from dashboard_pipeline.supplier_matching import (
    _extract_candidate_name_segments,
    _extract_tax_ids_from_text,
    _extract_waybill_refs_from_text,
    _infer_truth_source_label_from_scored_candidate,
    _layers_for_truth_source_label,
    _normalize_account_hint,
    _normalize_waybill_ref,
    _supplier_truth_context,
    canonical_tax_id_from_bog_receiver,
    match_partner_to_id,
    match_partner_to_id_legacy,
    normalize_name,
    skip_name_only_supplier_match,
)


# ── normalize_name ──────────────────────────────────────────────────

class TestNormalizeName:
    def test_basic_lowercase(self):
        assert normalize_name("HELLO WORLD") == "hello world"

    def test_strip_quotes(self):
        assert normalize_name('შპს „ტესტი"') == "ტესტი"

    def test_strip_prefix_shps(self):
        assert normalize_name("შპს ელიტფუდი") == "ელიტფუდი"

    def test_strip_prefix_ss(self):
        assert normalize_name("სს ბანკი") == "ბანკი"

    def test_strip_prefix_im(self):
        assert normalize_name("ი/მ გიორგი") == "გიორგი"

    def test_strip_prefix_im_dot(self):
        assert normalize_name("ი.მ ნინო") == "ნინო"

    def test_collapse_spaces(self):
        assert normalize_name("  a   b  c  ") == "a b c"

    def test_strip_dghg_suffix(self):
        assert normalize_name("ელიტფუდი-დღგ") == "ელიტფუდი"

    def test_empty(self):
        assert normalize_name("") == ""

    def test_none(self):
        assert normalize_name(None) == "none"

    def test_number_input(self):
        assert normalize_name(12345) == "12345"

    def test_brackets_removed(self):
        assert normalize_name("test (123)") == "test 123"


# ── _extract_tax_ids_from_text ──────────────────────────────────────

class TestExtractTaxIds:
    def test_nine_digit(self):
        assert _extract_tax_ids_from_text("id: 123456789 end") == ["123456789"]

    def test_eleven_digit(self):
        assert _extract_tax_ids_from_text("01025003711") == ["01025003711"]

    def test_multiple(self):
        result = _extract_tax_ids_from_text("a 111111111 b 222222222 c")
        assert result == ["111111111", "222222222"]

    def test_no_match_short(self):
        assert _extract_tax_ids_from_text("12345678") == []

    def test_no_match_long(self):
        assert _extract_tax_ids_from_text("123456789012") == []

    def test_dedup(self):
        result = _extract_tax_ids_from_text("111111111 111111111")
        assert result == ["111111111"]

    def test_empty(self):
        assert _extract_tax_ids_from_text("") == []

    def test_none(self):
        assert _extract_tax_ids_from_text(None) == []


# ── _normalize_account_hint ─────────────────────────────────────────

class TestNormalizeAccountHint:
    def test_basic(self):
        assert _normalize_account_hint("GE60 BG00 0000") == "GE60BG000000"

    def test_uppercase(self):
        assert _normalize_account_hint("ge60bg") == "GE60BG"

    def test_none(self):
        assert _normalize_account_hint(None) == ""

    def test_empty(self):
        assert _normalize_account_hint("") == ""

    def test_whitespace_only(self):
        assert _normalize_account_hint("   ") == ""


# ── _normalize_waybill_ref ──────────────────────────────────────────

class TestNormalizeWaybillRef:
    def test_basic(self):
        assert _normalize_waybill_ref("WB-123/A") == "WB123A"

    def test_uppercase(self):
        assert _normalize_waybill_ref("abc123") == "ABC123"

    def test_none(self):
        assert _normalize_waybill_ref(None) == ""

    def test_empty(self):
        assert _normalize_waybill_ref("") == ""

    def test_special_chars_stripped(self):
        assert _normalize_waybill_ref("WB_123-456/X") == "WB123456X"


# ── _extract_candidate_name_segments ────────────────────────────────

class TestExtractCandidateNameSegments:
    def test_single_name(self):
        result = _extract_candidate_name_segments("შპს ელიტფუდი")
        assert "ელიტფუდი" in result

    def test_comma_separated(self):
        result = _extract_candidate_name_segments("ტესტი, მეორე სახელი")
        assert len(result) >= 2

    def test_pipe_separated(self):
        result = _extract_candidate_name_segments("ტესტი|მეორე")
        assert len(result) >= 2

    def test_short_segments_excluded(self):
        result = _extract_candidate_name_segments("ab")
        assert result == []

    def test_empty(self):
        assert _extract_candidate_name_segments("") == []

    def test_none(self):
        assert _extract_candidate_name_segments(None) == []

    def test_iban_like_filtered_in_tokens(self):
        """IBAN-like tokens filtered in split, but whole string still appended."""
        result = _extract_candidate_name_segments("ტესტი,GE60BG0000000667583800")
        # The IBAN token is filtered in the comma-split loop,
        # but the whole normalized string is always appended.
        assert "ტესტი" in result


# ── _extract_waybill_refs_from_text ─────────────────────────────────

class TestExtractWaybillRefs:
    def test_known_ref_found(self):
        known = {"WB001", "WB002"}
        result = _extract_waybill_refs_from_text("payment for WB001 done", known)
        assert result == ["WB001"]

    def test_unknown_ref_ignored(self):
        known = {"WB001"}
        result = _extract_waybill_refs_from_text("payment for WB999 done", known)
        assert result == []

    def test_empty_known_set(self):
        assert _extract_waybill_refs_from_text("WB001", set()) == []

    def test_empty_text(self):
        assert _extract_waybill_refs_from_text("", {"WB001"}) == []

    def test_none_text(self):
        assert _extract_waybill_refs_from_text(None, {"WB001"}) == []

    def test_multiple_refs(self):
        known = {"WB001", "WB002", "WB003"}
        result = _extract_waybill_refs_from_text("WB001 and WB003", known)
        assert "WB001" in result
        assert "WB003" in result

    def test_dedup(self):
        known = {"WB001"}
        result = _extract_waybill_refs_from_text("WB001 WB001 WB001", known)
        assert result == ["WB001"]


# ── match_partner_to_id ─────────────────────────────────────────────

class TestMatchPartnerToId:
    def test_exact_legal_name(self):
        name_map = {"ელიტფუდი": "412761097"}
        assert match_partner_to_id("შპს ელიტფუდი", name_map) == "412761097"

    def test_alias_match(self):
        name_map = {}
        alias_map = {"ტესტ ალიასი": "999999999"}
        assert match_partner_to_id("ტესტ ალიასი", name_map, alias_map) == "999999999"

    def test_no_match(self):
        name_map = {"ელიტფუდი": "412761097"}
        assert match_partner_to_id("არააღწერილი კომპანია", name_map) is None

    def test_empty_name(self):
        assert match_partner_to_id("", {}) is None

    def test_legal_name_priority_over_alias(self):
        name_map = {"ტესტი": "111111111"}
        alias_map = {"ტესტი": "222222222"}
        assert match_partner_to_id("ტესტი", name_map, alias_map) == "111111111"


# ── canonical_tax_id_from_bog_receiver ──────────────────────────────

class TestCanonicalTaxId:
    def test_mapped_receiver(self):
        receiver_map = {"999888777": "123456789"}
        assert canonical_tax_id_from_bog_receiver("999888777", receiver_map) == "123456789"

    def test_unmapped_passthrough(self):
        receiver_map = {}
        assert canonical_tax_id_from_bog_receiver("555555555", receiver_map) == "555555555"

    def test_none_receiver(self):
        assert canonical_tax_id_from_bog_receiver(None, {}) is None

    def test_empty_receiver(self):
        assert canonical_tax_id_from_bog_receiver("", {}) == ""


# ── skip_name_only_supplier_match ───────────────────────────────────

class TestSkipNameOnlyMatch:
    def test_normal_text_not_skipped(self):
        assert skip_name_only_supplier_match("ელიტფუდი 2") is False

    def test_none_not_skipped(self):
        assert skip_name_only_supplier_match(None) is False

    def test_nan_not_skipped(self):
        assert skip_name_only_supplier_match(float("nan")) is False


# ── _layers_for_truth_source_label ──────────────────────────────────

class TestLayersForTruthSourceLabel:
    def test_bank_tax_id(self):
        layers = _layers_for_truth_source_label("bank_tax_id")
        assert "bank.raw_tax_id" in layers

    def test_registry_iban(self):
        layers = _layers_for_truth_source_label("registry_iban")
        assert "supplier_matching_registry.iban" in layers

    def test_unknown_label(self):
        assert _layers_for_truth_source_label("nonexistent") == []

    def test_empty_label(self):
        assert _layers_for_truth_source_label("") == []

    def test_none_label(self):
        assert _layers_for_truth_source_label(None) == []


# ── _infer_truth_source_label_from_scored_candidate ─────────────────

class TestInferTruthSourceLabel:
    def _master_with_supplier(self, tid, **kwargs):
        supplier = {
            "tax_id": tid,
            "official_names": set(),
            "registry_official_names": set(),
            "rs_official_names": set(),
            "aliases": set(),
            "person_aliases": set(),
            "ibans": set(),
            "account_hints": set(),
            "force_non_supplier_keywords": set(),
        }
        supplier.update(kwargs)
        return {"suppliers_by_id": {tid: supplier}}

    def test_waybill_ref(self):
        cand = {"tax_id": "111", "reasons": ["waybill_ref:WB001"]}
        master = self._master_with_supplier("111")
        assert _infer_truth_source_label_from_scored_candidate(cand, master) == "waybill_reference"

    def test_tax_id_in_text(self):
        cand = {"tax_id": "111", "reasons": ["tax_id_in_text"]}
        master = self._master_with_supplier("111")
        assert _infer_truth_source_label_from_scored_candidate(cand, master) == "bank_tax_id"

    def test_alias_reason(self):
        cand = {"tax_id": "111", "reasons": ["alias:ტესტი"]}
        master = self._master_with_supplier("111")
        assert _infer_truth_source_label_from_scored_candidate(cand, master) == "registry_alias"

    def test_person_alias_reason(self):
        cand = {"tax_id": "111", "reasons": ["person_alias:გიორგი"]}
        master = self._master_with_supplier("111")
        assert _infer_truth_source_label_from_scored_candidate(cand, master) == "registry_person_alias"

    def test_legal_name_registry(self):
        cand = {"tax_id": "111", "reasons": ["legal_name:ტესტი"]}
        master = self._master_with_supplier(
            "111", registry_official_names={"ტესტი"}
        )
        assert _infer_truth_source_label_from_scored_candidate(cand, master) == "registry_legal_name"

    def test_legal_name_rs_backstop(self):
        cand = {"tax_id": "111", "reasons": ["legal_name:ტესტი"]}
        master = self._master_with_supplier("111", rs_official_names={"ტესტი"})
        assert _infer_truth_source_label_from_scored_candidate(cand, master) == "rs_legal_name_backstop"

    def test_no_reasons(self):
        cand = {"tax_id": "111", "reasons": []}
        master = self._master_with_supplier("111")
        assert _infer_truth_source_label_from_scored_candidate(cand, master) == ""

    def test_none_candidate(self):
        assert _infer_truth_source_label_from_scored_candidate(None, {}) == ""


# ── _supplier_truth_context ─────────────────────────────────────────

class TestSupplierTruthContext:
    def test_empty_tax_id(self):
        ctx = _supplier_truth_context("", {})
        assert ctx["truth_source_label"] == ""
        assert ctx["truth_sources"] == []

    def test_with_label(self):
        ctx = _supplier_truth_context("111", {}, truth_source_label="bank_tax_id")
        assert ctx["truth_source_label"] == "bank_tax_id"
        assert "bank.raw_tax_id" in ctx["truth_sources"]
