# Supplier Alias UI + retail_sales display redesign — DEFERRED

**Date proposed**: 2026-05-05
**Status**: 🟡 Decision captured · scope locked · implementation deferred to future Sprint
**Decided by**: user (live feedback during alias UI smoke-test, 2026-05-05)

---

## Problem discovered (2026-05-05 smoke-test)

Alias confirmation UI in `SupplierModal.jsx` is functionally unreachable for the
intended user flow:

| Layer | Finding |
|---|---|
| `imported_products.suppliers` | 224 suppliers · 19 alias-matchable products across all of them |
| `unmatched_preview` | top-10 by cost per supplier — only 7/1404 entries (across all suppliers) populate `name_candidate` |
| Status gate | alias UI section was originally rendered only for `status === 'unverified'` |
| Visible buttons | 0/104 unverified suppliers had a clickable `✓ დადასტურდი ალიასი` button |
| Path 2 patch (this session) | Lifted gate so `partial`/`verified` suppliers also surface candidates → 5 suppliers now show buttons (კორიდა, აროშიძე, თისო, ექსტრამითი, გი-შო+) |
| Live API test | `კორიდა / გორილა` rejected with `retail_code_or_barcode '4860103357229' ცოცხალ retail_sales-ში ვერ მოიძებნა` — barcode IS valid, but lives outside the truncated `retail_sales.by_product` slice |

### Root cause
`retail_sales.by_product` is truncated to top 1000 (out of `products_total_count = 8460`).
`/api/aliases/confirm` validates `retail_code_or_barcode` against this truncated slice
via `_build_retail_known_keys`. Any alias targeting a product outside the top-1000
is rejected even though the product genuinely exists in the underlying retail
data and was sold by the supplier.

User's intuition was correct: "ენერგეტიკული სასმელი გორილა შემოიტანა კორიდამ,
რაც შემოვიდა გაიყიდა, რა პრობლემაა?" — there is no real-world problem; the
problem is purely a dashboard truncation artefact.

---

## User's proposed redesign (architectural direction)

> "ამ ცხრილში უნდა გვქონდა მხოლოდ 20-30 საუკეთესო გაყიდული პროდუქცია.
> კომპანიის ყველა პროდუქციის სანახავად და გაყიდვებს გავაკეთებთ ცალკე,
> ან დავყვეწოთ გაყიდვების სექციაში."

### Three layers

1. **Main dashboard "top products" tile** — curated top 20-30 best sellers only.
   Reduces signal noise. Currently 1000 rows is too dense for a top-line view.
2. **Per-supplier drill-down** — every product the supplier ever delivered,
   matched + unmatched + alias-confirmable. Lives either in the supplier modal
   (expanded section) or in a new "Supplier Products" tab.
3. **Alias confirmation** — moves to layer 2. Validates against the **full**
   retail product universe (all 8460 entries), not the truncated dashboard slice.

### Architectural invariant
> Display layer truncation MUST NOT bleed into validation layer logic.
> The alias API must consult full retail data regardless of what the
> dashboard chooses to show.

---

## Sprint scope (deferred)

| Item | Estimate | Risk |
|---|---|---|
| Reduce `retail_sales.by_product` rendered rows to top 20-30 (UI side) | ~30 min | LOW |
| New per-supplier products drill-down view (modal expansion or new tab) | ~1 session | MEDIUM |
| Decouple `/api/aliases/confirm` retail validation from `data.json.retail_sales.by_product` slice → full retail universe | ~2 hours | LOW |
| Move alias confirmation UI from inline modal section into the drill-down view | ~30 min | LOW |
| Adjust `unmatched_preview` strategy — surface alias-matchable candidates regardless of cost rank | ~1-2 hours | LOW |
| Tests | ~1-2 hours | LOW |

**Total**: 1-2 sessions.

---

## What was changed in this session (uncommitted)

- `rs-dashboard/src/SupplierModal.jsx` — Path 2 cosmetic patch lifting the alias
  candidates section out of the `unverified`-only gate, so it now also renders
  for `partial`/`verified` suppliers when at least one preview entry has a
  `name_candidate`. **Reverted** at session close because the full redesign
  supersedes it.
- `rs-dashboard/dist/*` — rebuilt to reflect the patch above; reverted with
  the source.

No commit. main branch unchanged on the alias UI front.

---

## Companion request: Orphan products dashboard tab (added 2026-05-05, same session)

User added a related request after walking through the SOAP-resolved orphan list:

> "მინდა ყველა პროდუქცია და კომპანიები რომლებიც არ არის შეყვანილი
> [MegaPlus-ში მომწოდებლის ველში] ცალკე ყოფილიყო."

### Scope

A new dashboard tab — proposed name **„შეუსაბამო პროდუქცია"** — surfacing every
PRODUCTS row in MegaPlus whose supplier link is empty / zero-UUID / ghost,
alongside the resolver's best-guess supplier (RS_CODES → GET → SOAP fallback).

### Columns

| Column | Source |
|---|---|
| store | orphan_resolver `store` |
| product name (P_NAME) | orphan_resolver |
| best supplier (proposed) | orphan_resolver `best_supplier_name` |
| evidence source | orphan_resolver `resolution_method` (RS_CODES / SOAP / NO MATCH) |
| lifetime revenue | orphan_resolver `lifetime_revenue` |
| sale lines | orphan_resolver `sale_lines` |
| last sale date | orphan_resolver `last_sale_at` |
| user status | NEW field — "გასასწორებელი" / "გაკეთებულია" / "უგულებელყოფილი" |

### Filters

store · supplier · evidence source · user status · revenue range

### Why combine with alias redesign

Both features address the same underlying problem: **MegaPlus product↔supplier
linkage gaps**. The alias UI confirms a product code mapping; this view exposes
the upstream truth (which products lack supplier linkage at all). Implementing
them together avoids duplicating data plumbing — one shared `orphan_status`
section in `data.json` powers both views.

### Combined Sprint scope

Add to the table in the "Sprint scope (deferred)" section above:

| Item | Estimate | Risk |
|---|---|---|
| Pipeline integration: orphan_resolver writes summary to `data.json` (not just Excel) | ~1 hour | LOW |
| New tab "შეუსაბამო პროდუქცია" with filterable table | ~1 session | LOW |
| User-status persistence (mark as fixed/ignored) | ~30 min | LOW |
| Combine entry-point with alias confirmation flow (single MegaPlus mapping workspace) | ~1 hour | MEDIUM |

**Combined total** (alias redesign + orphan view): 2-3 sessions.

---

## Carryover note for future Sprint

Before implementing the redesign, re-read this preview AND verify the truncation
assumption — if `products_total_count` has changed or the pipeline has been
re-tuned, scope may have shifted.

The 5 suppliers with currently-visible candidates (კორიდა, აროშიძე, თისო,
ექსტრამითი, გი-შო+) are useful smoke-test targets:

- **თისო** has 2 candidates (`ბემბი` code 1050, `ბაჭია` code 1066) that **are**
  inside the top-1000 retail slice — these will succeed against the current
  endpoint. Use them to verify the redesigned flow doesn't regress the
  happy path.
- The other 4 suppliers' candidates point at products outside the top-1000 —
  use them to verify that the redesigned API hits the full retail universe.
