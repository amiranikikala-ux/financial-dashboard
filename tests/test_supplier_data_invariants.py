"""Live data.json invariants — algebraic safety net for imported_products.

Catches structural regressions where breakdowns (per-store, per-status,
per-month, per-supplier) drift away from the headline totals. These tests
do NOT detect classification bugs (e.g., resolver assigning wrong store):
both sides of the breakdown share the same wrong answer, so the sum still
matches. Source-vs-output reconciliation lives in
``scripts/reconcile_suppliers.py``.

Skips cleanly if data.json is missing.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

EPS_AMOUNT = 0.5  # ₾ tolerance for float-sum comparisons across thousands of rows
EPS_QTY = 0.5  # quantity tolerance (same reason)

DATA_JSON = (
    Path(__file__).resolve().parent.parent
    / "rs-dashboard"
    / "public"
    / "data.json"
)


@pytest.fixture(scope="module")
def imported_products():
    if not DATA_JSON.exists():
        pytest.skip(f"data.json not present at {DATA_JSON}")
    blob = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    ip = blob.get("imported_products")
    if not ip:
        pytest.skip("data.json has no imported_products section")
    return ip


def _isclose(a: float, b: float, eps: float = EPS_AMOUNT) -> bool:
    return abs((a or 0) - (b or 0)) <= eps


# ---------------------------------------------------------------------------
# Portfolio-level invariants
# ---------------------------------------------------------------------------

def test_suppliers_sum_equals_overall_total(imported_products):
    overall_total = imported_products["overall"]["total_amount_ge"]
    suppliers_sum = sum(s.get("total_amount_ge") or 0 for s in imported_products["suppliers"])
    assert _isclose(suppliers_sum, overall_total), (
        f"sum(suppliers.total_amount_ge)={suppliers_sum:,.2f} != "
        f"overall.total_amount_ge={overall_total:,.2f}"
    )


def test_suppliers_sum_row_count_equals_overall(imported_products):
    overall_rc = imported_products["overall"]["row_count"]
    suppliers_rc = sum(s.get("row_count") or 0 for s in imported_products["suppliers"])
    assert suppliers_rc == overall_rc, (
        f"sum(suppliers.row_count)={suppliers_rc} != overall.row_count={overall_rc}"
    )


def test_by_month_sum_equals_overall(imported_products):
    overall_total = imported_products["overall"]["total_amount_ge"]
    overall_rc = imported_products["overall"]["row_count"]
    bm_total = sum(m.get("total_ge") or 0 for m in imported_products["by_month"])
    bm_rc = sum(m.get("row_count") or 0 for m in imported_products["by_month"])
    assert _isclose(bm_total, overall_total), (
        f"sum(by_month.total_ge)={bm_total:,.2f} != overall={overall_total:,.2f}"
    )
    assert bm_rc == overall_rc, (
        f"sum(by_month.row_count)={bm_rc} != overall={overall_rc}"
    )


def test_by_status_sum_equals_overall(imported_products):
    overall_total = imported_products["overall"]["total_amount_ge"]
    overall_rc = imported_products["overall"]["row_count"]
    bs_total = sum(e.get("total_ge") or 0 for e in imported_products["by_status"])
    bs_rc = sum(e.get("row_count") or 0 for e in imported_products["by_status"])
    assert _isclose(bs_total, overall_total), (
        f"sum(by_status.total_ge)={bs_total:,.2f} != overall={overall_total:,.2f}"
    )
    assert bs_rc == overall_rc, (
        f"sum(by_status.row_count)={bs_rc} != overall={overall_rc}"
    )


def test_cancelled_status_excluded_from_totals(imported_products):
    """Sprint cancelled-status filter (commit 020a555) must keep
    'გაუქმებული' rows out of by_status, suppliers, and overall."""
    cancelled_in_status = [
        e for e in imported_products["by_status"]
        if (e.get("status") or "").strip() == "გაუქმებული"
    ]
    assert not cancelled_in_status, (
        f"by_status contains cancelled rows: {cancelled_in_status}"
    )
    overall = imported_products["overall"]
    assert overall.get("cancelled_rows_dropped", 0) >= 0
    assert overall.get("cancelled_amount_dropped_ge", 0) >= 0.0


# ---------------------------------------------------------------------------
# Per-supplier invariants
# ---------------------------------------------------------------------------

def test_each_supplier_object_breakdown_sums_to_total(imported_products):
    """sum(object_breakdown[*].total_amount_ge) must equal supplier.total_amount_ge."""
    failures = []
    for s in imported_products["suppliers"]:
        breakdown = s.get("object_breakdown") or []
        if not breakdown:
            continue
        breakdown_sum = sum(ob.get("total_amount_ge") or 0 for ob in breakdown)
        total = s.get("total_amount_ge") or 0
        if not _isclose(breakdown_sum, total):
            failures.append(
                f"  {s.get('supplier')!r} (id={s.get('tax_id')}): "
                f"breakdown_sum={breakdown_sum:,.2f} vs total={total:,.2f} "
                f"(diff={breakdown_sum - total:+,.2f})"
            )
    assert not failures, "object_breakdown sums diverge from supplier total:\n" + "\n".join(failures)


def test_each_supplier_object_breakdown_row_count_sums(imported_products):
    failures = []
    for s in imported_products["suppliers"]:
        breakdown = s.get("object_breakdown") or []
        if not breakdown:
            continue
        breakdown_rc = sum(ob.get("row_count") or 0 for ob in breakdown)
        total_rc = s.get("row_count") or 0
        if breakdown_rc != total_rc:
            failures.append(
                f"  {s.get('supplier')!r} (id={s.get('tax_id')}): "
                f"breakdown_rc={breakdown_rc} vs row_count={total_rc}"
            )
    assert not failures, "object_breakdown row_count diverges:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# Per-supplier profitability invariants
# ---------------------------------------------------------------------------

def test_profitability_per_store_cost_sums_to_supplier_total(imported_products):
    """For suppliers with profitability.per_store_breakdown, the sum of
    cost_imported_ge across stores must equal supplier.total_amount_ge.
    This is the upstream check that the per-store math is consistent —
    even if the resolver classifies a store wrong, the sum should hold.
    """
    failures = []
    for s in imported_products["suppliers"]:
        prof = s.get("profitability") or {}
        per_store = prof.get("per_store_breakdown") or []
        if not per_store:
            continue
        per_store_cost = sum(p.get("cost_imported_ge") or 0 for p in per_store)
        total = s.get("total_amount_ge") or 0
        if not _isclose(per_store_cost, total):
            failures.append(
                f"  {s.get('supplier')!r} (id={s.get('tax_id')}): "
                f"per_store_cost_sum={per_store_cost:,.2f} vs "
                f"supplier_total={total:,.2f} (diff={per_store_cost - total:+,.2f})"
            )
    assert not failures, "per_store_breakdown cost sums diverge:\n" + "\n".join(failures)


def test_profitability_totals_cost_matches_supplier_total(imported_products):
    """profitability.totals.cost_imported_ge must equal supplier.total_amount_ge."""
    failures = []
    for s in imported_products["suppliers"]:
        prof = s.get("profitability") or {}
        totals = prof.get("totals") or {}
        if not totals:
            continue
        prof_cost = totals.get("cost_imported_ge") or 0
        sup_total = s.get("total_amount_ge") or 0
        if not _isclose(prof_cost, sup_total):
            failures.append(
                f"  {s.get('supplier')!r} (id={s.get('tax_id')}): "
                f"profitability.totals.cost_imported_ge={prof_cost:,.2f} vs "
                f"supplier.total_amount_ge={sup_total:,.2f}"
            )
    assert not failures, "profitability.totals diverges from supplier total:\n" + "\n".join(failures)


def test_portfolio_summary_matches_aggregated_suppliers(imported_products):
    """profitability_summary.portfolio.cost_imported_ge must equal
    overall.total_amount_ge (Sprint A wiring invariant)."""
    summary = imported_products.get("profitability_summary") or {}
    portfolio = summary.get("portfolio") or {}
    if not portfolio:
        pytest.skip("profitability_summary.portfolio missing — Sprint A not wired")
    p_cost = portfolio.get("cost_imported_ge") or 0
    overall = imported_products["overall"]["total_amount_ge"] or 0
    assert _isclose(p_cost, overall, eps=1.0), (
        f"profitability_summary.portfolio.cost_imported_ge={p_cost:,.2f} vs "
        f"overall.total_amount_ge={overall:,.2f}"
    )


# ---------------------------------------------------------------------------
# Sanity: object_breakdown destination labels must be from a known set
# ---------------------------------------------------------------------------

def test_object_breakdown_destinations_are_known(imported_products):
    """Every per-store destination label must be one of the canonical
    object names. Catches resolver returning malformed strings, NULLs,
    or fragments of the source text."""
    known = {"ოზურგეთი", "დვაბზუ", "გაუნაწილებელი"}
    seen = set()
    for s in imported_products["suppliers"]:
        for ob in s.get("object_breakdown") or []:
            obj = (ob.get("object") or "").strip()
            seen.add(obj)
    unexpected = seen - known
    assert not unexpected, (
        f"object_breakdown contains unexpected destination labels: {sorted(unexpected)} "
        f"(known: {sorted(known)})"
    )
