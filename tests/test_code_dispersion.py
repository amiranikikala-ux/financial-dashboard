"""Tests for dashboard_pipeline.code_dispersion.

Pure-Python tests — no SQL connection, no AI API call. The AI client is
exercised only indirectly via synthesized AICall objects passed to
`assemble_group`.

Live-DB and live-AI behavior is covered separately by `_scratch_*` spot-check
scripts (see CONTEXT_HANDOFF.md verification commands).
"""
from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from dashboard_pipeline.code_dispersion import (
    AICall,
    AIVerdict,
    DispersionGroup,
    Product,
    _aggregate_confidence,
    _cache_key,
    _strip_code_fence,
    assemble_group,
    first_content_stem,
    normalize,
    write_excel,
)


# ─────────────────────────── normalize ─────────────────────────────────────

def test_normalize_lowercases_and_collapses_whitespace():
    assert normalize("  ფეირი   ლიმონი 21x450მლ  ") == "ფეირი ლიმონი 21x450მლ"


def test_normalize_handles_none_and_empty():
    assert normalize(None) == ""
    assert normalize("") == ""


# ─────────────────────────── first_content_stem ────────────────────────────

def test_first_content_stem_fairy_lemon():
    assert first_content_stem("ფეირი ლიმონი 21x450მლ") == "ფეირ"


def test_first_content_stem_skips_generic_prefix_min_water():
    # "მინ წყალი /საირმე /2ლ" → skip "მინ", "წყალი" → first content = "საირმე" → stem "საირ"
    assert first_content_stem("მინ წყალი /საირმე /2ლ") == "საირ"


def test_first_content_stem_skips_generic_cigarette():
    # "სიგარეტი/ფილიპ მორისი/ექსპერტ რედი" → skip "სიგარეტი" → "ფილიპ" → "ფილი"
    assert first_content_stem("სიგარეტი/ფილიპ მორისი/ექსპერტ რედი") == "ფილი"


def test_first_content_stem_skips_numeric_only():
    # "0.150ლ კოკა-კოლა" → "0.150ლ" starts with digit → skip → "კოკა"
    assert first_content_stem("0.150ლ კოკა-კოლა (12ც)ქილა") == "კოკა"


def test_first_content_stem_handles_inflection_via_prefix():
    # "ლიმონი" and "ლიმონის" share 4-char prefix "ლიმო"
    assert first_content_stem("ლიმონი 450მლ") == first_content_stem("ლიმონის 450 მლ")


def test_first_content_stem_returns_empty_for_unmatched():
    assert first_content_stem("") == ""
    assert first_content_stem("123 456 7") == ""


# ─────────────────────────── _aggregate_confidence ─────────────────────────

def _v(p_id: int, same: bool, confidence: str = "high") -> AIVerdict:
    return AIVerdict(p_id=p_id, same=same, confidence=confidence, reason_ka="")


def test_aggregate_confidence_no_siblings():
    assert _aggregate_confidence([]) == "no_match"


def test_aggregate_confidence_all_high():
    assert _aggregate_confidence([_v(1, True, "high"), _v(2, True, "high")]) == "high"


def test_aggregate_confidence_any_medium_downgrades():
    assert _aggregate_confidence([_v(1, True, "high"), _v(2, True, "medium")]) == "medium"


def test_aggregate_confidence_any_low_dominates():
    assert _aggregate_confidence([_v(1, True, "high"), _v(2, True, "low")]) == "low"


# ─────────────────────────── _strip_code_fence ─────────────────────────────

def test_strip_code_fence_with_json_label():
    assert _strip_code_fence("```json\n{\"a\":1}\n```") == '{"a":1}'


def test_strip_code_fence_unlabeled():
    assert _strip_code_fence("```\n{\"a\":1}\n```") == '{"a":1}'


def test_strip_code_fence_no_fence():
    assert _strip_code_fence('  {"a":1}  ') == '{"a":1}'


# ─────────────────────────── _cache_key ────────────────────────────────────

def _p(pid: int, qty: float = 0.0, name: str = "x") -> Product:
    return Product(p_id=pid, barcode="", name=name, qty=qty, supplier_uuid="")


def test_cache_key_deterministic_regardless_of_candidate_order():
    a = _p(100)
    cands_a = [_p(1), _p(2), _p(3)]
    cands_b = [_p(3), _p(1), _p(2)]
    assert _cache_key(a, cands_a) == _cache_key(a, cands_b)


def test_cache_key_distinguishes_anchors():
    cands = [_p(1), _p(2)]
    assert _cache_key(_p(100), cands) != _cache_key(_p(101), cands)


# ─────────────────────────── assemble_group ────────────────────────────────

def _fairy_lemon_setup() -> tuple[Product, list[Product], AICall]:
    """The flagship validation case: 3 codes, math closes at +28."""
    anchor = Product(
        p_id=20754, barcode="5413149798946", name="ფეირი ლიმონი 21x450მლ",
        qty=-350.0, supplier_uuid="8502", qty_in=76.0, qty_out=426.0,
    )
    sib1 = Product(
        p_id=89755, barcode="8001090931191", name="ფეირი (1) ლიმონი 0.450მლ ყ*21",
        qty=336.0, supplier_uuid="8502", qty_in=374.0, qty_out=38.0,
    )
    sib2 = Product(
        p_id=93297, barcode="4038", name="ფეირი ლიმონის 450 მლ 21ც",
        qty=42.0, supplier_uuid="8240", qty_in=42.0, qty_out=0.0,
    )
    other = Product(
        p_id=43244, barcode="4084500213029", name="ფეირი ფორთოხალი 21x450მლ",
        qty=0.0, supplier_uuid="8502", qty_in=0.0, qty_out=0.0,
    )
    candidates = [sib1, sib2, other]
    ai_call = AICall(
        anchor_pid=20754,
        verdicts=[
            AIVerdict(p_id=89755, same=True, confidence="high", reason_ka="ფეირი ლიმონი 450მლ"),
            AIVerdict(p_id=93297, same=True, confidence="high", reason_ka="ფეირი ლიმონი 450მლ"),
            AIVerdict(p_id=43244, same=False, confidence="high", reason_ka="ფორთოხალი ≠ ლიმონი"),
        ],
        input_tokens=900, output_tokens=200,
    )
    return anchor, candidates, ai_call


def test_assemble_group_fairy_lemon_balance_closes():
    anchor, candidates, ai_call = _fairy_lemon_setup()
    grp = assemble_group("1329", "დვაბზუ", anchor, candidates, ai_call)
    assert len(grp.siblings) == 2
    assert {s.p_id for s in grp.siblings} == {89755, 93297}
    assert len(grp.rejected) == 1
    assert grp.rejected[0][0].p_id == 43244
    # math closure: -350 + 336 + 42 = 28; in 76+374+42 = 492; out 426+38+0 = 464
    assert grp.family_qty_now == pytest.approx(28.0)
    assert grp.family_qty_in == pytest.approx(492.0)
    assert grp.family_qty_out == pytest.approx(464.0)
    assert grp.balance_check == pytest.approx(28.0)
    assert grp.balance_consistent is True
    assert grp.economic_score == pytest.approx(1.0)
    assert grp.confidence == "high"


def test_assemble_group_no_siblings_when_ai_rejects_all():
    anchor = _p(100, qty=-50.0)
    cand = _p(200, qty=10.0)
    ai_call = AICall(
        anchor_pid=100,
        verdicts=[AIVerdict(p_id=200, same=False, confidence="high", reason_ka="diff")],
        input_tokens=10, output_tokens=10,
    )
    grp = assemble_group("1329", "დვაბზუ", anchor, [cand], ai_call)
    assert grp.siblings == []
    assert grp.confidence == "no_match"
    assert grp.family_qty_now == pytest.approx(-50.0)


def test_assemble_group_economic_score_penalizes_open_groups():
    """When the 'closed group' assumption breaks (real loss/theft), score < 1."""
    anchor = Product(
        p_id=10, barcode="", name="anchor", qty=-100.0, supplier_uuid="",
        qty_in=50.0, qty_out=200.0,  # net = -150 (real shortage of 50 beyond sibling)
    )
    sib = Product(
        p_id=20, barcode="", name="sibling", qty=50.0, supplier_uuid="",
        qty_in=50.0, qty_out=0.0,
    )
    ai_call = AICall(
        anchor_pid=10,
        verdicts=[AIVerdict(p_id=20, same=True, confidence="high", reason_ka="same")],
        input_tokens=10, output_tokens=10,
    )
    grp = assemble_group("1329", "დვაბზუ", anchor, [sib], ai_call)
    # qty_now sum = -50; in_total = 100; out_total = 200; balance_check = -100
    # diff with qty_now sum = |-100 - (-50)| = 50; flow basis = max(100, 200, 50) = 200
    # economic_score = 1 - 50/200 = 0.75
    assert grp.economic_score == pytest.approx(0.75)
    assert grp.balance_consistent is False


# ─────────────────────────── write_excel ──────────────────────────────────

def test_write_excel_produces_two_sheets_with_expected_headers(tmp_path: Path):
    anchor, candidates, ai_call = _fairy_lemon_setup()
    grp = assemble_group("1329", "დვაბზუ", anchor, candidates, ai_call)
    out = tmp_path / "out.xlsx"
    write_excel([grp], out)
    wb = openpyxl.load_workbook(out, read_only=True)
    assert set(wb.sheetnames) == {"ჯგუფები", "დეტალები"}

    summary_rows = list(wb["ჯგუფები"].iter_rows(values_only=True))
    assert summary_rows[0][0] == "მაღაზია"
    assert summary_rows[0][1] == "გატეხილი P_ID"
    assert "გადაწყვეტილება" in summary_rows[0][-1]
    # one data row for our one group
    assert summary_rows[1][1] == 20754

    detail_rows = list(wb["დეტალები"].iter_rows(values_only=True))
    # 1 anchor + 2 siblings + 1 rejected = 4 data rows
    assert len(detail_rows) == 1 + 4
    roles = [r[3] for r in detail_rows[1:]]
    assert "გატეხილი" in roles
    assert roles.count("იგივე-პროდუქტი") == 2
    assert roles.count("უარყოფილი") == 1


def test_write_excel_skips_empty_groups(tmp_path: Path):
    """Groups without siblings shouldn't appear in summary sheet body."""
    anchor = _p(1, qty=-10.0)
    grp = DispersionGroup(
        store_id="1329", store_label="დვაბზუ", anchor=anchor,
        siblings=[], rejected=[], confidence="no_match",
        family_qty_now=-10.0, family_qty_in=0.0, family_qty_out=10.0,
        balance_check=-10.0, balance_consistent=True, economic_score=1.0,
        ai_input_tokens=0, ai_output_tokens=0,
    )
    out = tmp_path / "out.xlsx"
    write_excel([grp], out)
    wb = openpyxl.load_workbook(out, read_only=True)
    summary_rows = list(wb["ჯგუფები"].iter_rows(values_only=True))
    # only header row, no data row (siblings empty → skipped)
    assert len(summary_rows) == 1
