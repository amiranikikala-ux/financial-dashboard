# Supplier Attribution v2 — Phase 1 Verification

**Date**: 2026-05-01
**Files**: `supplier_attribution_v2_prototype.py` + `supplier_attribution_v2_verification.csv`

## Goal
Replace the import-driven supplier_profitability matching with a **retail-driven**
model so per-supplier numbers come within 1-2% of the MAX MEgaplus rollup
oracle (`Financial_Analysis/მეგა პლუს/კომპანიების გაყიდვა მოგება.xls`).

The MAX file is a **verification oracle only** — pipeline must compute its own
numbers from primary sources (retail per-row + RS waybills).

## Approach
Iterate over retail per-row sales (not imports). For each row, attribute to a
supplier via a 4-tier ladder:

1. **`code_unique`** — code or barcode is in exactly one supplier's imports
2. **`multi_recent`** — code in multiple suppliers; pick most-recent past-dated
3. **`multi_dominant`** — multi-supplier with no past candidate; pick supplier with biggest historical qty share
4. **`brand_rule`** — fallback by product-name regex per supplier (cigarettes, vasadze bread)
5. **`unattributed`** — surfaced honestly as a coverage gap

## Result (vs MAX rollup, dvabzu store, 73 suppliers compared)

| Bucket | Count |
|---|---|
| ✓ within 2% | **26** |
| 🟢 within 5% | 9 (cum. 35) |
| 🟡 within 15% | 15 (cum. 50) |
| 🔴 over 15% | 23 |

vs current production pipeline: only **4 suppliers** within 2% — so this is a
**6.5× accuracy improvement** for the within-2% bucket.

## Top 20 by revenue (dvabzu)

7 ✓, 5 🟢, 4 🟡, 4 🔴 — **12/20 within 5%**, **16/20 within 15%**.

The 4 problem cases:
- **ELIZI +20%**: brand-rule overshoots; per-row vs rollup cost-basis difference
- **ჯიბე -35%**: multi-supplier resolution swings between over/under
- **ზედაზენი +22%**: similar multi-supplier issue
- **თამილა ხარაბაძე +53,598%**: tiny supplier wins multi_dominant for popular codes; needs supplier-size guard

## Coverage
- **დვაბზუ**: 80,313 retail rows → 7.1% unattributed revenue (was 38% with 2026-only imports)
- **ოზურგეთი**: 68,912 retail rows → 7.1% unattributed revenue

The 7.1% gap is items whose codes never appeared in any import (cash purchases,
samurneo items, internal store SKUs).

## Remaining work for production swap

1. **Supplier-size guard** for multi_dominant (fix თამილა-type wild over-attribution)
2. **Refine brand rules** — ELIZI overshoot suggests cost-basis / refund handling
3. **More brand rules** for the 23 🔴 suppliers as needed
4. **Per-store splitting** — current prototype only sums per supplier; production
   needs per-store columns matching `imported_products.suppliers[].profitability.per_store_breakdown`
5. **Replace `dashboard_pipeline/supplier_profitability.py`** matching ladder
   (~885 lines, careful test pass needed)
6. **Move BRAND_RULES to a config file** (e.g., `Financial_Analysis/brand_supplier_map.json`)
   so user can edit without code changes

Estimated 2-3 sessions to land production swap.

## How to re-run
```bash
"venv/Scripts/python.exe" HANDOFF_ARCHIVE/supplier_attribution_v2_prototype.py
```
Output: console summary + CSV at `HANDOFF_ARCHIVE/supplier_attribution_v2_verification.csv`.
