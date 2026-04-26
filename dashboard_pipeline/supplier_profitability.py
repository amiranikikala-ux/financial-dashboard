"""Supplier-level profitability via strict barcode JOIN.

Cross-references imported_products (RS.ge waybills — who delivered what at
what cost) with retail_sales.by_product (MAX POS — what was sold at what
price and margin). The two systems use different internal product codes;
the only safe linker is barcode/code numerical match.

Foundational rules (memory: feedback_perfect_or_silent +
project_product_match_barcode_only):

* JOIN by barcode/code only; never by product_name (Borjomi glass and
  plastic share the same name but are different SKUs with different cost
  and margin).
* No fuzzy/normalized name matching anywhere in this module.
* Each supplier carries an explicit ``status`` so downstream UI can show
  a 100% verified analysis or an explicit "ჯერ უცნობია" state — never a
  silent partial result with confidence-% disclaimer.

Match precedence:

1. imported.product_code == retail_sales.barcode  (EAN-13 in code field)
2. imported.product_code == retail_sales.product_code (MAX internal code)
3. user-vetted alias from product_aliases.json

The output object lives at ``data["imported_products"]["suppliers"][i]
["profitability"]`` so SupplierModal can read it without an extra fetch.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

#: Days since last retail sale beyond which a product counts as dead stock
#: per supplier. Aligns with `analyze_dead_stock` tool default so the UI
#: signal matches what the AI tool reports for the same product.
DEAD_STOCK_THRESHOLD_DAYS = 120

#: Minimum revenue (₾) for a product to qualify for top/bottom margin
#: lists. Filters out long-tail noise — a product with 20 ₾ revenue and
#: −80% margin is a data artefact, not a strategic signal.
MIN_REVENUE_FOR_MARGIN_LIST_GE = 100.0

#: Below this many products imported, the supplier renders as "minimal
#: display" (KPI only, no top/bottom lists). 1–2-product suppliers do not
#: have enough mass for ranking to be meaningful.
MIN_PRODUCTS_FOR_FULL_DISPLAY = 5

#: Coverage thresholds (cost-weighted) for status decision.
COVERAGE_VERIFIED_PCT = 80.0
COVERAGE_UNVERIFIED_PCT = 5.0

#: If this fraction of matched cost falls in PROTECTED categories, the
#: supplier is itself marked PROTECTED — UI suppresses bottom-margin
#: recommendations because cigarette/alcohol margins are structurally
#: low and not actionable via "stop ordering this".
PROTECTED_DOMINANT_PCT = 80.0

#: Category-name substrings whose products are PROTECTED — bottom-margin
#: lists exclude them, supplier-level rollup detects "mostly protected"
#: distributors. Broader than mix_analyzer's cigarette-only set because
#: alcohol distributors (lower-margin by structure) appear at supplier
#: level too. Kept local — mix_analyzer's PROTECTED_CATEGORY_SUBSTRINGS
#: is intentionally narrower (category-mix recommendations).
SUPPLIER_PROFITABILITY_PROTECTED_SUBSTRINGS: Tuple[str, ...] = (
    "სიგარეტ",      # cigarettes (any variant)
    "ლუდი",         # beer
    "ღვინ",         # wine (ღვინო, ღვინის)
    "არაყ",         # vodka (არაყი, არაყის)
    "კონიაკ",       # cognac
    "ვისკ",         # whisky
    "შამპან",       # champagne
    "ჭაჭ",          # chacha
    "აპერიტ",       # aperitif
    "ლიქიორ",       # liqueur
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm_code(value: Any) -> str:
    """Strip whitespace and stringify; empty string for None or unusable."""
    if value is None:
        return ""
    return str(value).strip()


def _safe_div(numer: float, denom: float) -> float:
    return (numer / denom) if denom else 0.0


def _is_protected_category(category: str) -> bool:
    if not category:
        return False
    for sub in SUPPLIER_PROFITABILITY_PROTECTED_SUBSTRINGS:
        if sub in category:
            return True
    return False


def _parse_iso_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Index construction
# ---------------------------------------------------------------------------

def _build_retail_indices(
    by_product: List[Dict[str, Any]],
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    """Build two lookup dicts on retail_sales.by_product:

    * ``by_barcode``: barcode (EAN-13 typically) → list of rows
    * ``by_product_code``: MAX internal code → list of rows

    Lists rather than single values because the live retail_sales export
    has ~1,000 collisions where the same code points to multiple physical
    products (some are renamed-variant duplicates, others are MAX
    internal-code reuse for unrelated SKUs). Caller treats a 1-row hit
    as a clean match and a 2+-row hit as ambiguous (excluded from totals
    until a user-vetted alias disambiguates).
    """
    by_bc: Dict[str, List[Dict[str, Any]]] = {}
    by_pc: Dict[str, List[Dict[str, Any]]] = {}
    for row in by_product:
        bc = _norm_code(row.get("barcode"))
        pc = _norm_code(row.get("product_code"))
        if bc:
            by_bc.setdefault(bc, []).append(row)
        if pc:
            by_pc.setdefault(pc, []).append(row)
    return by_bc, by_pc


def _build_alias_lookup(
    aliases: Optional[List[Dict[str, Any]]],
) -> Dict[str, str]:
    """Convert validated alias entries to a flat
    ``imported_code -> retail_code_or_barcode`` map. Validation is the
    caller's responsibility — this just flattens.
    """
    if not aliases:
        return {}
    lookup: Dict[str, str] = {}
    for entry in aliases:
        src = _norm_code(entry.get("imported_code"))
        dst = _norm_code(entry.get("retail_code_or_barcode"))
        if src and dst:
            lookup[src] = dst
    return lookup


# ---------------------------------------------------------------------------
# Match logic
# ---------------------------------------------------------------------------

def _match_product(
    imported_code: str,
    by_barcode: Dict[str, List[Dict[str, Any]]],
    by_product_code: Dict[str, List[Dict[str, Any]]],
    alias_lookup: Dict[str, str],
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Return ``(retail_row, match_kind)``.

    ``match_kind`` is one of:

    * ``"barcode"`` — direct barcode hit, exactly 1 retail row
    * ``"product_code"`` — MAX internal code hit, exactly 1 retail row
    * ``"alias"`` — user-vetted alias hit (alias points at a single
      retail key, so by definition unambiguous)
    * ``"ambiguous"`` — code hits 2+ retail rows; without a user alias to
      pick the right one, we cannot trust either match → caller treats
      it as unmatched and surfaces it as an alias candidate
    * ``"none"`` — no match at all

    Aliases override the ambiguous case: a user-vetted alias is the
    explicit signal "this imported code maps to *this specific* retail
    row", which resolves the ambiguity intentionally.
    """
    if not imported_code:
        return None, "none"

    # Aliases take precedence (user explicitly said "this is the right pick")
    if imported_code in alias_lookup:
        target = alias_lookup[imported_code]
        if target in by_barcode and len(by_barcode[target]) == 1:
            return by_barcode[target][0], "alias"
        if target in by_product_code and len(by_product_code[target]) == 1:
            return by_product_code[target][0], "alias"
        # Alias points at an ambiguous-or-missing target; treat as no match
        return None, "none"

    if imported_code in by_barcode:
        rows = by_barcode[imported_code]
        if len(rows) == 1:
            return rows[0], "barcode"
        return None, "ambiguous"

    if imported_code in by_product_code:
        rows = by_product_code[imported_code]
        if len(rows) == 1:
            return rows[0], "product_code"
        return None, "ambiguous"

    return None, "none"


# ---------------------------------------------------------------------------
# Per-supplier aggregation
# ---------------------------------------------------------------------------

def _aggregate_supplier(
    supplier_entry: Dict[str, Any],
    by_barcode: Dict[str, Dict[str, Any]],
    by_product_code: Dict[str, Dict[str, Any]],
    alias_lookup: Dict[str, str],
    today: date,
) -> Dict[str, Any]:
    """Compute the profitability payload for one supplier."""

    products = supplier_entry.get("top_products") or []
    total_products = len(products)

    matched_rows: List[Dict[str, Any]] = []
    unmatched_rows: List[Dict[str, Any]] = []
    ambiguous_rows: List[Dict[str, Any]] = []

    cost_imported_total_ge = 0.0
    cost_matched_ge = 0.0
    cost_ambiguous_ge = 0.0
    cost_protected_ge = 0.0

    for prod in products:
        imp_code = _norm_code(prod.get("product_code"))
        cost_paid = float(prod.get("total_amount_ge") or 0)
        qty_bought = float(prod.get("total_quantity") or 0)
        cost_imported_total_ge += cost_paid

        retail_row, kind = _match_product(
            imp_code, by_barcode, by_product_code, alias_lookup
        )

        if retail_row is None:
            entry = {
                "imported_code": imp_code,
                "imported_name": prod.get("product_name", ""),
                "imported_unit": prod.get("unit", ""),
                "cost_imported_ge": round(cost_paid, 2),
                "quantity_imported": qty_bought,
            }
            if kind == "ambiguous":
                ambiguous_rows.append(entry)
                cost_ambiguous_ge += cost_paid
            else:
                unmatched_rows.append(entry)
            continue

        cost_matched_ge += cost_paid

        rev_ge = float(retail_row.get("revenue_ge") or 0)
        cost_sold_ge = float(retail_row.get("cost_ge") or 0)
        profit_ge = rev_ge - cost_sold_ge
        margin_pct = _safe_div(profit_ge, rev_ge) * 100.0 if rev_ge > 0 else 0.0
        category = retail_row.get("category", "") or ""
        is_protected = _is_protected_category(category)
        if is_protected:
            cost_protected_ge += cost_paid

        last_sale = _parse_iso_date((retail_row.get("date_range") or {}).get("max"))
        days_since_sale = (today - last_sale).days if last_sale else None
        is_dead = (
            rev_ge <= 0
            or (days_since_sale is not None and days_since_sale > DEAD_STOCK_THRESHOLD_DAYS)
        )

        matched_rows.append(
            {
                "imported_code": imp_code,
                "imported_name": prod.get("product_name", ""),
                "retail_product_code": _norm_code(retail_row.get("product_code")),
                "retail_barcode": _norm_code(retail_row.get("barcode")),
                "retail_name": retail_row.get("product_name", ""),
                "category": category,
                "match_kind": kind,
                "cost_imported_ge": round(cost_paid, 2),
                "quantity_imported": qty_bought,
                "revenue_sold_ge": round(rev_ge, 2),
                "cost_sold_ge": round(cost_sold_ge, 2),
                "profit_ge": round(profit_ge, 2),
                "margin_pct": round(margin_pct, 2),
                "quantity_sold": float(retail_row.get("total_quantity") or 0),
                "last_sale_date": last_sale.isoformat() if last_sale else None,
                "days_since_last_sale": days_since_sale,
                "is_protected": is_protected,
                "is_dead_stock": is_dead,
            }
        )

    # ---- supplier-level rollups ------------------------------------------
    revenue_sold_total_ge = sum(m["revenue_sold_ge"] for m in matched_rows)
    cost_sold_total_ge = sum(m["cost_sold_ge"] for m in matched_rows)
    profit_total_ge = revenue_sold_total_ge - cost_sold_total_ge
    margin_total_pct = (
        round((profit_total_ge / revenue_sold_total_ge) * 100.0, 2)
        if revenue_sold_total_ge > 0
        else 0.0
    )

    coverage_cost_pct = (
        round((cost_matched_ge / cost_imported_total_ge) * 100.0, 2)
        if cost_imported_total_ge > 0
        else 0.0
    )
    coverage_product_pct = (
        round((len(matched_rows) / total_products) * 100.0, 2)
        if total_products > 0
        else 0.0
    )
    ambiguous_cost_pct = (
        round((cost_ambiguous_ge / cost_imported_total_ge) * 100.0, 2)
        if cost_imported_total_ge > 0
        else 0.0
    )
    protected_cost_share_pct = (
        round((cost_protected_ge / cost_matched_ge) * 100.0, 2)
        if cost_matched_ge > 0
        else 0.0
    )

    # ---- status decision -------------------------------------------------
    # Order matters: protected dominance overrides verified status because
    # bottom-margin recommendations are unsafe even at high coverage.
    if total_products == 0:
        status = "empty"
    elif coverage_cost_pct < COVERAGE_UNVERIFIED_PCT:
        status = "unverified"
    elif protected_cost_share_pct >= PROTECTED_DOMINANT_PCT:
        status = "protected"
    elif coverage_cost_pct >= COVERAGE_VERIFIED_PCT:
        status = "verified"
    else:
        status = "partial"

    minimal_display = total_products < MIN_PRODUCTS_FOR_FULL_DISPLAY

    # ---- top / bottom margin rankings -----------------------------------
    # Top: highest margin, revenue >= noise floor (no protected filter — a
    # high-margin protected SKU is informative, not a recommendation).
    # Bottom: lowest margin, revenue >= noise floor, NOT protected (we do
    # not surface "cut your low-margin cigarettes" as advice).
    eligible_for_lists = [
        m for m in matched_rows
        if m["revenue_sold_ge"] >= MIN_REVENUE_FOR_MARGIN_LIST_GE
    ]
    top_margin = sorted(
        eligible_for_lists, key=lambda m: m["margin_pct"], reverse=True
    )[:3]
    bottom_margin = sorted(
        [m for m in eligible_for_lists if not m["is_protected"]],
        key=lambda m: m["margin_pct"],
    )[:3]

    # ---- dead stock list (top-5 by imported cost wasted) ----------------
    dead_stock = sorted(
        [m for m in matched_rows if m["is_dead_stock"]],
        key=lambda m: m["cost_imported_ge"],
        reverse=True,
    )[:5]

    # ---- unmatched + ambiguous previews (top-5 by cost — alias candidates) -
    unmatched_top = sorted(
        unmatched_rows, key=lambda r: r["cost_imported_ge"], reverse=True
    )[:5]
    ambiguous_top = sorted(
        ambiguous_rows, key=lambda r: r["cost_imported_ge"], reverse=True
    )[:5]

    return {
        "status": status,
        "minimal_display": minimal_display,
        "totals": {
            "products_imported": total_products,
            "products_matched": len(matched_rows),
            "products_ambiguous": len(ambiguous_rows),
            "products_unmatched": len(unmatched_rows),
            "cost_imported_ge": round(cost_imported_total_ge, 2),
            "cost_matched_ge": round(cost_matched_ge, 2),
            "cost_ambiguous_ge": round(cost_ambiguous_ge, 2),
            "revenue_sold_ge": round(revenue_sold_total_ge, 2),
            "cost_sold_ge": round(cost_sold_total_ge, 2),
            "profit_ge": round(profit_total_ge, 2),
            "margin_pct": margin_total_pct,
        },
        "coverage": {
            "cost_pct": coverage_cost_pct,
            "product_pct": coverage_product_pct,
            "ambiguous_cost_pct": ambiguous_cost_pct,
            "protected_cost_share_pct": protected_cost_share_pct,
        },
        "top_margin": top_margin,
        "bottom_margin": bottom_margin,
        "dead_stock": dead_stock,
        "unmatched_preview": unmatched_top,
        "ambiguous_preview": ambiguous_top,
        "rules": {
            "dead_stock_threshold_days": DEAD_STOCK_THRESHOLD_DAYS,
            "min_revenue_for_margin_list_ge": MIN_REVENUE_FOR_MARGIN_LIST_GE,
            "min_products_for_full_display": MIN_PRODUCTS_FOR_FULL_DISPLAY,
            "coverage_verified_pct": COVERAGE_VERIFIED_PCT,
            "coverage_unverified_pct": COVERAGE_UNVERIFIED_PCT,
            "protected_dominant_pct": PROTECTED_DOMINANT_PCT,
            "protected_substrings": list(SUPPLIER_PROFITABILITY_PROTECTED_SUBSTRINGS),
        },
    }


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def build_supplier_profitability(
    data: Dict[str, Any],
    today: Optional[date] = None,
    aliases: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compute per-supplier profitability and a portfolio-level summary.

    Returns a dict with two top-level keys:

    * ``per_supplier`` — list of ``{tax_id, supplier, profitability}`` for
      every entry in ``data["imported_products"]["suppliers"]``. The
      caller writes ``profitability`` back onto each supplier entry.
    * ``summary`` — counts by status + portfolio totals for the data-quality
      page.

    ``aliases`` is a pre-validated list (validator runs separately so a
    bad alias file doesn't crash the pipeline; the caller passes ``[]``
    if validation failed and logs the reason).
    """
    today = today or date.today()
    imported = (data or {}).get("imported_products") or {}
    suppliers = imported.get("suppliers") or []
    by_product = ((data or {}).get("retail_sales") or {}).get("by_product") or []

    by_bc, by_pc = _build_retail_indices(by_product)
    alias_lookup = _build_alias_lookup(aliases)

    per_supplier: List[Dict[str, Any]] = []
    counts = {
        "verified": 0,
        "partial": 0,
        "unverified": 0,
        "protected": 0,
        "empty": 0,
    }
    portfolio_cost_imported = 0.0
    portfolio_cost_matched = 0.0
    portfolio_cost_ambiguous = 0.0
    portfolio_revenue = 0.0
    portfolio_profit = 0.0

    for s in suppliers:
        prof = _aggregate_supplier(s, by_bc, by_pc, alias_lookup, today)
        per_supplier.append(
            {
                "tax_id": s.get("tax_id") or "",
                "supplier": s.get("supplier") or "",
                "profitability": prof,
            }
        )
        counts[prof["status"]] = counts.get(prof["status"], 0) + 1
        portfolio_cost_imported += prof["totals"]["cost_imported_ge"]
        portfolio_cost_matched += prof["totals"]["cost_matched_ge"]
        portfolio_cost_ambiguous += prof["totals"].get("cost_ambiguous_ge", 0)
        portfolio_revenue += prof["totals"]["revenue_sold_ge"]
        portfolio_profit += prof["totals"]["profit_ge"]

    portfolio_coverage_cost_pct = (
        round((portfolio_cost_matched / portfolio_cost_imported) * 100.0, 2)
        if portfolio_cost_imported > 0
        else 0.0
    )
    portfolio_margin_pct = (
        round((portfolio_profit / portfolio_revenue) * 100.0, 2)
        if portfolio_revenue > 0
        else 0.0
    )

    portfolio_ambiguous_cost_pct = (
        round((portfolio_cost_ambiguous / portfolio_cost_imported) * 100.0, 2)
        if portfolio_cost_imported > 0
        else 0.0
    )

    summary = {
        "supplier_counts": counts,
        "portfolio": {
            "cost_imported_ge": round(portfolio_cost_imported, 2),
            "cost_matched_ge": round(portfolio_cost_matched, 2),
            "cost_ambiguous_ge": round(portfolio_cost_ambiguous, 2),
            "revenue_sold_ge": round(portfolio_revenue, 2),
            "profit_ge": round(portfolio_profit, 2),
            "margin_pct": portfolio_margin_pct,
            "coverage_cost_pct": portfolio_coverage_cost_pct,
            "ambiguous_cost_pct": portfolio_ambiguous_cost_pct,
        },
        "alias_count": len(alias_lookup),
        "today": today.isoformat(),
    }

    return {"per_supplier": per_supplier, "summary": summary}


__all__ = [
    "build_supplier_profitability",
    "DEAD_STOCK_THRESHOLD_DAYS",
    "MIN_REVENUE_FOR_MARGIN_LIST_GE",
    "MIN_PRODUCTS_FOR_FULL_DISPLAY",
    "COVERAGE_VERIFIED_PCT",
    "COVERAGE_UNVERIFIED_PCT",
    "PROTECTED_DOMINANT_PCT",
    "SUPPLIER_PROFITABILITY_PROTECTED_SUBSTRINGS",
]
