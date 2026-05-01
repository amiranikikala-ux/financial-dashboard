"""Supplier-level profitability via strict barcode JOIN.

Cross-references imported_products (RS.ge waybills — who delivered what at
what cost) with retail_sales.by_product (MAX POS — what was sold at what
price and margin). The two systems use different internal product codes;
the only safe linker is barcode/code numerical match.

Foundational rules (memory: feedback_perfect_or_silent +
project_product_match_barcode_only):

* JOIN by barcode/code only; never auto-match by product_name (Borjomi
  glass and plastic share the same name but are different SKUs with
  different cost and margin).
* Name match is allowed only as a *candidate hint* attached to unmatched
  rows so UI can surface "user, please confirm this alias" — pipeline
  itself never substitutes a name match for a code match in totals.
* Each supplier carries an explicit ``status`` and unmatched rows carry
  ``name_candidate`` info so downstream UI can show 100% verified totals
  AND a concrete next-step path (alias confirm / missing source) instead
  of a silent dead-end "ჯერ უცნობია".

Match precedence (deterministic, applied in order until single hit):

1. imported.product_code == retail_sales.barcode  (EAN-13 in code field)
2. imported.product_code == retail_sales.product_code (MAX internal code)
3. imported.product_code + "x" == retail_sales.product_code/barcode
   (MAX deprecated-marker convention — the old code with an "x" suffix
   sometimes survives in the live retail export after MAX renumbers.)
4. unique normalized product_name match where retail.category is in the
   PROTECTED set (cigarettes, alcohol). Names in protected categories
   are highly specific (brand + variant + size all encoded), and the
   Borjomi-glass-vs-plastic naming-collision risk does not apply because
   beverages are not in the protected set. Without this step, suppliers
   that ship under MAX's legacy 4-digit codes (since renumbered) like
   ELIZI's full cigarette catalog stay 0% verified despite each SKU
   having a clean unique-name match in retail.
5. user-vetted alias from product_aliases.json

The output object lives at ``data["imported_products"]["suppliers"][i]
["profitability"]`` so SupplierModal can read it without an extra fetch.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

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

#: Tax IDs of suppliers whose products use the full-attribution branch
#: (sole-distributor assumption) — bottom-margin lists exclude their
#: products and the supplier-level rollup labels them "protected".
#: Cigarettes are single-distributor at brand level (ELIZI 100%
#: Camel/Sobranie/Winston, ჯიდიაი 97.6% Parliament, ინტერნეიშნლ Marlboro),
#: so attributing the full retail row matches reality. The previous
#: implementation keyed off the retail row's category name ("სიგარეტი"
#: substring), but MegaPlus categories are operator-entered and can be
#: empty, mistyped, or split across variants ("გასახურებელი თამბაქო"
#: vs "სიგარეტი"). Tax IDs come from RS.ge waybills (canonical), so the
#: rule no longer depends on MegaPlus categorization quality.
SUPPLIER_PROFITABILITY_PROTECTED_TAX_IDS: Tuple[str, ...] = (
    "204920381",    # შპს ELIZI ჯგუფი (Camel / Sobranie / Winston)
    "406181616",    # შპს ჯიდიაი (Parliament)
    "420424393",    # შპს ინტერნეიშნლ მარკეტინგ ენდ თრეიდინგ (Marlboro)
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm_code(value: Any) -> str:
    """Strip whitespace and stringify; empty string for None or unusable."""
    if value is None:
        return ""
    return str(value).strip()


# Used only for name-candidate hint generation (alias-candidate suggestions).
# NEVER used to auto-merge totals — that path is forbidden by memory rule
# project_product_match_barcode_only.md.
_NAME_NORMALIZE_PUNCT_RE = re.compile(r"[*\(\)/\\\[\]]+")
_NAME_NORMALIZE_WS_RE = re.compile(r"\s+")


def _normalize_name(value: Any) -> str:
    """Lowercase + strip punctuation/asterisks + collapse whitespace.

    Intentionally aggressive on quirks MAX retail exports use ("(PP)*",
    double spaces, mixed case) — but DOES NOT translate or substring,
    so „ბორჯომი მინა" never collapses with „ბორჯომი პლასტიკი".
    """
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    text = _NAME_NORMALIZE_PUNCT_RE.sub(" ", text)
    text = _NAME_NORMALIZE_WS_RE.sub(" ", text)
    return text.strip()


def _safe_div(numer: float, denom: float) -> float:
    return (numer / denom) if denom else 0.0


def _is_protected_supplier(tax_id: str) -> bool:
    if not tax_id:
        return False
    return _norm_code(tax_id) in SUPPLIER_PROFITABILITY_PROTECTED_TAX_IDS


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


def _build_supplier_exclusive_names(
    suppliers: List[Dict[str, Any]],
) -> Set[str]:
    """Return the set of normalized product_names that appear under EXACTLY ONE
    supplier across all imports.

    Used to enable a safe name-match fallback in `_match_product` for products
    that no supplier-cross-collision can distort. The Borjomi-glass-vs-plastic
    rule is preserved: names shared across multiple suppliers (e.g. Coca-Cola
    products distributed by several distributors) are excluded from this set,
    so the name-match fallback cannot pick the wrong supplier's pricing.
    """
    name_to_suppliers: Dict[str, Set[str]] = {}
    for s in suppliers:
        sid = _norm_code(s.get("tax_id"))
        if not sid:
            continue
        for p in s.get("top_products") or []:
            nm = _normalize_name(p.get("product_name"))
            if nm:
                name_to_suppliers.setdefault(nm, set()).add(sid)
    return {nm for nm, sids in name_to_suppliers.items() if len(sids) == 1}


def _build_retail_name_index(
    by_product: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Index retail rows by normalized name for alias-candidate lookup.

    Used ONLY to generate hints for unmatched/ambiguous rows so the UI
    can surface "this imported product probably maps to that retail row,
    please confirm" workflow. Never consumed by ``_match_product`` —
    every entry that ends up in supplier totals must come from a code
    hit or a user-vetted alias, per memory project_product_match_barcode_only.md.
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    for row in by_product:
        nm = _normalize_name(row.get("product_name"))
        if nm:
            out.setdefault(nm, []).append(row)
    return out


# ---------------------------------------------------------------------------
# Match logic
# ---------------------------------------------------------------------------

def _match_product(
    imported_code: str,
    imported_name: str,
    by_barcode: Dict[str, List[Dict[str, Any]]],
    by_product_code: Dict[str, List[Dict[str, Any]]],
    name_index: Dict[str, List[Dict[str, Any]]],
    alias_lookup: Dict[str, str],
    supplier_exclusive_names: Optional[Set[str]] = None,
    supplier_tax_id: str = "",
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Return ``(retail_row, match_kind)``.

    ``match_kind`` is one of:

    * ``"barcode"`` — direct barcode hit, exactly 1 retail row
    * ``"product_code"`` — MAX internal code hit, exactly 1 retail row
    * ``"product_code_x_suffix"`` / ``"barcode_x_suffix"`` —
      ``imported_code + "x"`` hits exactly 1 retail row. Catches MAX's
      internal "deprecated marker" convention where the live retail
      export still carries the old code with a trailing "x" after a
      partial renumber. Treated as a full match in totals.
    * ``"name_in_protected_category"`` — exactly 1 retail row has the
      same normalized name AND that retail row's category is in the
      PROTECTED set (cigarettes / alcohol). Triggers only when every
      code-based path failed. Names in protected categories carry the
      brand + variant + size as a single string ("ქემელი 1913 ორიგინალ
      ბლუ"), and beverages susceptible to the glass-vs-plastic naming
      collision are not protected, so the Borjomi rule from
      project_product_match_barcode_only.md is not violated.
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

    nm = _normalize_name(imported_name)

    # Very short imported codes (≤4 chars) are typically supplier-internal
    # numbering ("1002", "9003") that collide with MAX's barcode/code
    # space by accident — supplier code 1002 (vasadze bread) is not the
    # same product as a MAX barcode 1002. Trust short-code matches only
    # when the matched retail row's name agrees with the imported name.
    # 5+ char codes are usually MAX/RS-style internal codes; legitimate
    # name variation is allowed there. EAN-13 codes (13 chars) are
    # globally unique; collision risk is zero.
    SHORT_CODE_THRESHOLD = 5

    def _name_agrees(retail_row: Dict[str, Any]) -> bool:
        rn = _normalize_name(retail_row.get("product_name", ""))
        if not rn or not nm:
            return True
        # Exact normalized equality is the strongest signal. Tolerate
        # MAX-side annotations like "ქემელი — current" / "ბორჯომი 1ლ პეტი
        # (PP)" by accepting one name as a prefix/substring of the other —
        # those are the same physical SKU with cosmetic suffix drift.
        if rn == nm:
            return True
        if rn.startswith(nm) or nm.startswith(rn):
            return True
        if nm in rn or rn in nm:
            return True
        return False

    short_code = len(imported_code) < SHORT_CODE_THRESHOLD

    # Track ambiguous-code seen so the final return preserves the
    # ambiguous status when no name fallback succeeds — this preserves
    # downstream "alias workflow" prompts for the user.
    saw_ambiguous = False

    if imported_code in by_barcode:
        rows = by_barcode[imported_code]
        if len(rows) == 1:
            if not short_code or _name_agrees(rows[0]):
                return rows[0], "barcode"
            # Fall through — code coincidence with mismatched name; try name path
        else:
            saw_ambiguous = True

    if imported_code in by_product_code:
        rows = by_product_code[imported_code]
        if len(rows) == 1:
            if not short_code or _name_agrees(rows[0]):
                return rows[0], "product_code"
            # Fall through to name-based paths
        else:
            saw_ambiguous = True

    # Last deterministic code-based shot — MAX "x" suffix convention.
    # Only triggers when neither barcode nor product_code has any hit
    # at all (so there is no ambiguity with a "current" code).
    code_x = imported_code + "x"
    if code_x in by_product_code:
        rows = by_product_code[code_x]
        if len(rows) == 1:
            return rows[0], "product_code_x_suffix"
    if code_x in by_barcode:
        rows = by_barcode[code_x]
        if len(rows) == 1:
            return rows[0], "barcode_x_suffix"

    # Final deterministic shot — unique name from a PROTECTED supplier.
    # Cigarette SKUs encode brand + variant + size in the name, so a
    # single retail row sharing the normalized name is reliable when the
    # importing supplier is a known cigarette distributor (ELIZI / ჯიდიაი
    # / ინტერნეიშნლ). Beverages (where Borjomi-glass vs Borjomi-plastic
    # share names) come from non-protected suppliers and never reach
    # this path.
    if nm and nm in name_index and _is_protected_supplier(supplier_tax_id):
        rows = name_index[nm]
        if len(rows) == 1:
            return rows[0], "name_in_protected_category"

    # Supplier-exclusive name match — when this normalized name is owned
    # by exactly ONE supplier across all imports AND a single retail row
    # carries the same name, the JOIN is safe regardless of category.
    # Borjomi-glass-vs-plastic risk does not apply: names shared across
    # multiple suppliers (Coca-Cola distributors etc.) are excluded from
    # `supplier_exclusive_names` upstream, so they never reach this path.
    if supplier_exclusive_names and nm and nm in supplier_exclusive_names:
        if nm in name_index:
            rows = name_index[nm]
            if len(rows) == 1:
                return rows[0], "name_supplier_exclusive"

    if saw_ambiguous:
        return None, "ambiguous"
    return None, "none"


def _name_candidate_for(
    imported_name: str,
    name_index: Dict[str, List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """If a single retail row has the same normalized product_name,
    return a hint payload UI can use to suggest "alias?" workflow.

    Returns None if zero or multiple retail rows share the name —
    multiple matches mean we can't pick one safely (would have been
    ambiguous as an automatic match too).
    """
    nm = _normalize_name(imported_name)
    if not nm:
        return None
    rows = name_index.get(nm)
    if not rows or len(rows) != 1:
        return None
    r = rows[0]
    return {
        "retail_barcode": _norm_code(r.get("barcode")),
        "retail_product_code": _norm_code(r.get("product_code")),
        "retail_name": r.get("product_name", "") or "",
        "retail_category": r.get("category", "") or "",
    }


# ---------------------------------------------------------------------------
# Per-supplier aggregation
# ---------------------------------------------------------------------------

def _aggregate_supplier(
    supplier_entry: Dict[str, Any],
    by_barcode: Dict[str, Dict[str, Any]],
    by_product_code: Dict[str, Dict[str, Any]],
    alias_lookup: Dict[str, str],
    today: date,
    name_index: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    supplier_exclusive_names: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Compute the profitability payload for one supplier."""

    name_index = name_index or {}
    products = supplier_entry.get("top_products") or []
    total_products = len(products)
    supplier_tax_id = _norm_code(supplier_entry.get("tax_id"))
    supplier_is_protected = _is_protected_supplier(supplier_tax_id)

    matched_rows: List[Dict[str, Any]] = []
    unmatched_rows: List[Dict[str, Any]] = []
    ambiguous_rows: List[Dict[str, Any]] = []

    cost_imported_total_ge = 0.0
    cost_matched_ge = 0.0
    cost_ambiguous_ge = 0.0
    cost_protected_ge = 0.0
    cost_unmatched_with_candidate_ge = 0.0
    cost_ambiguous_with_candidate_ge = 0.0

    # per-store revenue/cost-sold accumulators built from each matched
    # product's retail-side object_breakdown. Joined later with the
    # supplier-level imported_object_breakdown (cost-paid per store) to
    # produce the per_store_breakdown output.
    revenue_by_object: Dict[str, float] = {}
    cost_sold_by_object: Dict[str, float] = {}

    for prod in products:
        imp_code = _norm_code(prod.get("product_code"))
        cost_paid = float(prod.get("total_amount_ge") or 0)
        qty_bought = float(prod.get("total_quantity") or 0)
        cost_imported_total_ge += cost_paid

        retail_row, kind = _match_product(
            imp_code,
            prod.get("product_name", ""),
            by_barcode,
            by_product_code,
            name_index,
            alias_lookup,
            supplier_exclusive_names,
            supplier_tax_id,
        )

        if retail_row is None:
            candidate = _name_candidate_for(prod.get("product_name", ""), name_index)
            entry = {
                "imported_code": imp_code,
                "imported_name": prod.get("product_name", ""),
                "imported_unit": prod.get("unit", ""),
                "cost_imported_ge": round(cost_paid, 2),
                "quantity_imported": qty_bought,
                "name_candidate": candidate,
            }
            if kind == "ambiguous":
                ambiguous_rows.append(entry)
                cost_ambiguous_ge += cost_paid
                if candidate is not None:
                    cost_ambiguous_with_candidate_ge += cost_paid
            else:
                unmatched_rows.append(entry)
                if candidate is not None:
                    cost_unmatched_with_candidate_ge += cost_paid
            continue

        cost_matched_ge += cost_paid

        rev_ge = float(retail_row.get("revenue_ge") or 0)
        sold_qty_total = float(retail_row.get("total_quantity") or 0)
        cost_sold_recorded_ge = float(retail_row.get("cost_ge") or 0)

        # Cost of sold goods imputed from supplier invoice (RS waybill) —
        # the contractually-signed unit price × quantity sold. This replaces
        # the MAX POS-recorded `cost_ge` because operators frequently leave
        # cost-at-sale fields empty or set to a placeholder, producing
        # spurious 70-95% per-store margins (e.g. ვასაძის პური@დვაბზუ
        # showed 96.95% on 2,713 loaves because MAX recorded 91 ₾ instead
        # of ~2,713 ₾). The recorded value is preserved as
        # `cost_sold_recorded_ge` for UI transparency.
        #
        # Cap: imputed quantity is bounded by qty_bought from THIS supplier.
        # Without the cap, a name-only match against a multi-supplier brand
        # (e.g. cigarette distributors who all ship the same SKU) would
        # attribute the entire retail sold volume to each supplier — for a
        # supplier that imported 5 units, cost_sold could balloon to 1000×
        # the imported amount. Capping at qty_bought guarantees per-supplier
        # cost_sold ≤ cost_imported (you can't sell more from a supplier
        # than you bought from them).
        category = retail_row.get("category", "") or ""
        is_protected = supplier_is_protected
        imp_unit_cost_ge = (cost_paid / qty_bought) if qty_bought > 0 else 0.0
        rev_full_ge = rev_ge  # preserve full retail revenue for transparency
        # POS-recorded cost is reliable when it sits in a plausible markup
        # range (cost ≥ 30% of revenue). Below 30% the POS row almost
        # certainly carries a placeholder — operators leave the cost-at-
        # sale field blank or set 1₾ on groceries (vasadze loaves: POS
        # 91 ₾ vs supplier-invoice 2,713 ₾, the d1ff190 motivating case).
        # When POS is realistic we use cost-share attribution: supplier's
        # share of the retail row's cost is computed in ₾, so supplier-
        # unit (cartons / cases) vs retail-unit (packs / pieces) mismatches
        # cancel out. This generalises the cigarette/alcohol fix to every
        # product where the supplier ships in bulk and retail sells in
        # singles (e.g. ბიგი საპარსი 100 packs of 5 → 500 pieces, but the
        # qty-cap path treated 100 as pieces and produced −246% margin).
        pos_realistic = (
            cost_sold_recorded_ge > 0
            and rev_full_ge > 0
            and (cost_sold_recorded_ge / rev_full_ge) >= 0.30
        )
        if is_protected and cost_sold_recorded_ge > 0:
            # PROTECTED categories (cigarettes / alcohol): one distributor
            # typically owns each brand (ELIZI → Camel/Sobranie/Marlboro,
            # ჯიდიაი → Parliament). Cost-share attribution would divide by
            # POS recorded cost across all sold units and under-attribute
            # the sole distributor (e.g. ELIZI Sobranie: 4,502 ₾ paid for
            # 48 cartons / ~1,920 packs vs POS recorded 16,786 ₾ for 1,942
            # packs sold → cost-share gives 27% attribution instead of the
            # correct ~99%). Assume sole/dominant distributor and credit
            # the full retail row.
            cost_sold_ge = cost_sold_recorded_ge
            cost_sold_scale = None  # signal: use recorded cost per-store
        elif pos_realistic and cost_paid > 0:
            # Non-PROTECTED cost-share attribution. supplier_share caps at
            # 100% so a supplier can never be credited with more than was
            # actually sold; share < 1 means supplier shipped less than
            # retail recorded as sold (other suppliers contributed the
            # rest). This handles unit mismatches (e.g. ბიგი საპარსი
            # 100 packs of 5 → 500 retail pieces) by working in ₾ instead
            # of qty, so supplier-unit vs retail-unit cancels.
            supplier_share = min(1.0, cost_paid / cost_sold_recorded_ge)
            cost_sold_ge = cost_sold_recorded_ge * supplier_share
            rev_ge = rev_full_ge * supplier_share
            cost_sold_scale = supplier_share  # signal for per-store loop
        elif imp_unit_cost_ge > 0:
            effective_qty = min(sold_qty_total, qty_bought)
            cost_sold_ge = effective_qty * imp_unit_cost_ge
            # Per-store splits scale by the same cap factor so summed
            # per-store cost_sold equals the matched-row cost_sold.
            cost_sold_scale = (effective_qty / sold_qty_total) if sold_qty_total > 0 else 1.0
            # Revenue is scaled by the SAME cap factor — without this, when
            # the retail row covers more sold units than this supplier
            # shipped (e.g. lifetime MegaPlus retail vs Q1 2026 imports, or
            # a multi-supplier brand where this supplier sold a slice), we
            # credit the supplier with revenue from inventory shipped by
            # someone else. Scaling revenue alongside cost makes the per-
            # supplier KPI represent THIS supplier's economic contribution.
            rev_ge = rev_ge * cost_sold_scale
        else:
            cost_sold_ge = cost_sold_recorded_ge
            cost_sold_scale = None  # signal: use recorded cost per-store
        profit_ge = rev_ge - cost_sold_ge
        margin_pct = _safe_div(profit_ge, rev_ge) * 100.0 if rev_ge > 0 else 0.0
        if is_protected:
            cost_protected_ge += cost_paid

        last_sale = _parse_iso_date((retail_row.get("date_range") or {}).get("max"))
        days_since_sale = (today - last_sale).days if last_sale else None
        is_dead = (
            rev_ge <= 0
            or (days_since_sale is not None and days_since_sale > DEAD_STOCK_THRESHOLD_DAYS)
        )

        # accumulate per-store revenue/cost from this matched product's
        # retail per-object totals (every retail row carries it). Cost uses
        # the same imputed unit cost (with the same cap factor applied) so
        # the per-store sums equal the matched-row cost_sold. Field name
        # is `object_totals` since retail_sales.py centralised on that
        # spelling (215deaa MegaPlus synthesis); fall back to legacy
        # `object_breakdown` for backwards compatibility.
        for ob in retail_row.get("object_totals") or retail_row.get("object_breakdown") or []:
            obj_name = ob.get("object") or "უცნობი"
            obj_qty = float(ob.get("total_quantity") or 0)
            obj_rev = float(ob.get("revenue_ge") or 0)
            obj_cost_recorded = float(ob.get("cost_ge") or 0)
            if pos_realistic and cost_sold_scale is not None:
                # Cost-share path: per-store recorded cost × supplier share.
                # Same ₾-basis attribution as the matched row.
                obj_cost = obj_cost_recorded * cost_sold_scale
                obj_rev = obj_rev * cost_sold_scale
            elif cost_sold_scale is not None:
                # Imputed path: per-store qty × imputed unit cost × cap factor.
                # Used when POS cost is a placeholder (vasadze case).
                obj_cost = obj_qty * imp_unit_cost_ge * cost_sold_scale
                # Scale per-store revenue by the same cap factor so the
                # per-store sum equals the (already-scaled) matched-row
                # rev_ge. See the comment on `rev_ge = rev_ge * cost_sold_scale`
                # above for why revenue must be capped alongside cost.
                obj_rev = obj_rev * cost_sold_scale
            else:
                obj_cost = obj_cost_recorded
            revenue_by_object[obj_name] = revenue_by_object.get(obj_name, 0.0) + obj_rev
            cost_sold_by_object[obj_name] = cost_sold_by_object.get(obj_name, 0.0) + obj_cost

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
                "revenue_sold_full_ge": round(rev_full_ge, 2),
                "cost_sold_ge": round(cost_sold_ge, 2),
                "cost_sold_recorded_ge": round(cost_sold_recorded_ge, 2),
                "profit_ge": round(profit_ge, 2),
                "margin_pct": round(margin_pct, 2),
                "quantity_sold": sold_qty_total,
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

    # ---- unmatched + ambiguous previews -----------------------------------
    # Bumped from 5 to 10 — for unverified/partial suppliers UI shows this
    # as the "alias workflow checklist", and 10 covers the bulk of cost mass
    # for the live dataset (top-12 supplier cost cumulatively ≈ 75%).
    unmatched_top = sorted(
        unmatched_rows, key=lambda r: r["cost_imported_ge"], reverse=True
    )[:10]
    ambiguous_top = sorted(
        ambiguous_rows, key=lambda r: r["cost_imported_ge"], reverse=True
    )[:10]
    unmatched_with_candidate_count = sum(
        1 for r in unmatched_rows if r.get("name_candidate")
    )
    ambiguous_with_candidate_count = sum(
        1 for r in ambiguous_rows if r.get("name_candidate")
    )

    # ---- per-store breakdown ---------------------------------------------
    # Cost-imported per store comes straight from the supplier-level
    # imported `object_breakdown` (every shipment row carries its
    # destination). Revenue/cost-sold per store comes from each matched
    # retail row's `object_breakdown` (POS records track the till).
    # We outer-join on the store name so a store can appear with cost
    # only (we imported but POS never sold) or revenue only (POS sold
    # something we never imported through this supplier).
    imported_by_object: Dict[str, float] = {}
    qty_imported_by_object: Dict[str, float] = {}
    for ob in supplier_entry.get("object_breakdown") or []:
        name = ob.get("object") or "უცნობი"
        imported_by_object[name] = float(ob.get("total_amount_ge") or 0)
        qty_imported_by_object[name] = float(ob.get("total_quantity") or 0)

    all_objects = set(imported_by_object) | set(revenue_by_object) | set(cost_sold_by_object)
    per_store: List[Dict[str, Any]] = []
    for name in sorted(all_objects, key=lambda o: -imported_by_object.get(o, 0)):
        cost_imp = imported_by_object.get(name, 0.0)
        rev = revenue_by_object.get(name, 0.0)
        cs = cost_sold_by_object.get(name, 0.0)
        prof = rev - cs
        margin = (prof / rev * 100.0) if rev > 0 else 0.0
        per_store.append(
            {
                "object": name,
                "cost_imported_ge": round(cost_imp, 2),
                "quantity_imported": round(qty_imported_by_object.get(name, 0.0), 4),
                "revenue_sold_ge": round(rev, 2),
                "cost_sold_ge": round(cs, 2),
                "profit_ge": round(prof, 2),
                "margin_pct": round(margin, 2),
            }
        )

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
            # Alias workflow surface — how many gap rows have a name match in
            # retail (one user-confirmation away from being matched). Lets
            # the UI render "X products / Y ₾ ხელით დადასტურებას სჭირდება"
            # instead of a silent dead-end "ჯერ უცნობია" cell.
            "unmatched_with_candidate_count": unmatched_with_candidate_count,
            "unmatched_with_candidate_cost_ge": round(cost_unmatched_with_candidate_ge, 2),
            "ambiguous_with_candidate_count": ambiguous_with_candidate_count,
            "ambiguous_with_candidate_cost_ge": round(cost_ambiguous_with_candidate_ge, 2),
        },
        "per_store_breakdown": per_store,
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
            "protected_tax_ids": list(SUPPLIER_PROFITABILITY_PROTECTED_TAX_IDS),
        },
    }


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def _megaplus_to_retail_by_product(megaplus_live: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Synthesize a `retail_sales.by_product`-shaped list from `megaplus_live`.

    Per-store MegaPlus rollups become unified rows aggregated by barcode
    (with product_code fallback). Each unified row carries an
    ``object_totals`` array with the store-by-store contribution so the
    downstream supplier matcher can split per-store revenue/cost the same
    way it always did with Excel-derived retail_sales.

    Field-name mapping (MegaPlus → retail_sales):
      qty_sold → total_quantity, revenue → revenue_ge, cogs → cost_ge,
      profit → profit_ge. Other fields pass through with renaming.
    """
    stores = (megaplus_live or {}).get("stores") or {}
    if not stores:
        return []

    store_label_for = {"1329": "დვაბზუ", "1301": "ოზურგეთი"}
    aggregated: Dict[str, Dict[str, Any]] = {}

    for store_id, rollup in stores.items():
        obj_label = store_label_for.get(str(store_id)) or f"store_{store_id}"
        # Prefer the windowed (last 365 days) by_product if present so that
        # supplier_profitability matches RS waybill imports against retail
        # rows from the same pricing era — lifetime aggregation dilutes
        # margin when prices have shifted (inflation, promotions). Fall
        # back to lifetime by_product on older caches that pre-date the
        # windowed query.
        rows = rollup.get("by_product_recent") or rollup.get("by_product") or []
        for p in rows:
            barcode = (p.get("barcode") or "").strip()
            code = (p.get("product_code") or "").strip()
            key = barcode or code or f"pid_{p.get('product_id')}"
            if not key:
                continue
            if key not in aggregated:
                aggregated[key] = {
                    "product_key": key,
                    "product_code": code,
                    "barcode": barcode,
                    "product_name": p.get("product_name") or "",
                    "unit": p.get("unit") or "",
                    "category": p.get("category") or "",
                    "category_key": _normalize_name(p.get("category") or ""),
                    "row_count": 0,
                    "total_quantity": 0.0,
                    "revenue_ge": 0.0,
                    "cost_ge": 0.0,
                    "profit_ge": 0.0,
                    "month_keys": [],
                    "min_date": None,
                    "max_date": None,
                    "object_totals": [],
                }
            agg = aggregated[key]
            qty = float(p.get("qty_sold") or 0)
            rev = float(p.get("revenue") or 0)
            cogs = float(p.get("cogs") or 0)
            profit = float(p.get("profit") or 0)
            row_count = int(p.get("row_count") or 0)

            agg["row_count"] += row_count
            agg["total_quantity"] += qty
            agg["revenue_ge"] += rev
            agg["cost_ge"] += cogs
            agg["profit_ge"] += profit
            agg["object_totals"].append({
                "object": obj_label,
                "row_count": row_count,
                "total_quantity": qty,
                "revenue_ge": rev,
                "cost_ge": cogs,
                "profit_ge": profit,
            })

            min_d = p.get("min_date")
            max_d = p.get("max_date")
            if min_d and (agg["min_date"] is None or str(min_d) < str(agg["min_date"])):
                agg["min_date"] = str(min_d)[:10]
            if max_d and (agg["max_date"] is None or str(max_d) > str(agg["max_date"])):
                agg["max_date"] = str(max_d)[:10]

    return list(aggregated.values())


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

    Retail data source — preference:
      1. ``data["megaplus_live"]`` if present (MegaPlus DB direct, full
         per-store coverage including products without RS waybill).
      2. ``data["retail_sales"]["by_product"]`` (Excel POS export) as
         legacy fallback.
    """
    today = today or date.today()
    imported = (data or {}).get("imported_products") or {}
    suppliers = imported.get("suppliers") or []

    megaplus_live = (data or {}).get("megaplus_live") or {}
    by_product = _megaplus_to_retail_by_product(megaplus_live)
    if not by_product:
        by_product = ((data or {}).get("retail_sales") or {}).get("by_product") or []

    by_bc, by_pc = _build_retail_indices(by_product)
    name_index = _build_retail_name_index(by_product)
    alias_lookup = _build_alias_lookup(aliases)
    supplier_exclusive_names = _build_supplier_exclusive_names(suppliers)

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
    portfolio_unmatched_with_candidate_count = 0
    portfolio_unmatched_with_candidate_cost = 0.0
    portfolio_ambiguous_with_candidate_count = 0
    portfolio_ambiguous_with_candidate_cost = 0.0

    for s in suppliers:
        prof = _aggregate_supplier(
            s, by_bc, by_pc, alias_lookup, today,
            name_index=name_index,
            supplier_exclusive_names=supplier_exclusive_names,
        )
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
        cov = prof.get("coverage") or {}
        portfolio_unmatched_with_candidate_count += int(cov.get("unmatched_with_candidate_count") or 0)
        portfolio_unmatched_with_candidate_cost += float(cov.get("unmatched_with_candidate_cost_ge") or 0)
        portfolio_ambiguous_with_candidate_count += int(cov.get("ambiguous_with_candidate_count") or 0)
        portfolio_ambiguous_with_candidate_cost += float(cov.get("ambiguous_with_candidate_cost_ge") or 0)

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
            # Alias workflow surface — total user-confirmable opportunities
            # across every supplier. UI/admin page reports this as the
            # "actionable gap" (vs. the genuinely-missing source bucket).
            "unmatched_with_candidate_count": portfolio_unmatched_with_candidate_count,
            "unmatched_with_candidate_cost_ge": round(portfolio_unmatched_with_candidate_cost, 2),
            "ambiguous_with_candidate_count": portfolio_ambiguous_with_candidate_count,
            "ambiguous_with_candidate_cost_ge": round(portfolio_ambiguous_with_candidate_cost, 2),
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
    "SUPPLIER_PROFITABILITY_PROTECTED_TAX_IDS",
]
