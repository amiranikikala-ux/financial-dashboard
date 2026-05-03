# Supplier_profitability "Absence" — Diagnostic

**თარიღი**: 2026-05-03 · **ცალკე ფაილი** PRODUCTS_FRAGMENTATION-ისგან · **STRICT SCOPE — read-only diagnostic** · არც code edit, არც commit, არც push.

---

## 0. ცხრება (one-liner verdict)

**Supplier_profitability data არსებობს data.json-ში.** **PRODUCTS_FRAGMENTATION §12-ის "absent" flag — false alarm**, ჩემი misread-ი იყო — top-level key-ს ვეძებდი (`data["supplier_profitability"]`), მაგრამ მონაცემი ნესტ-ად ჩაწერილია `imported_products.suppliers[*].profitability` (220/220 supplier) + `imported_products.profitability_summary` (overall portfolio). ეს იყო **architectural choice** ორიგინალური wire-up-დან (commit `8455486`, 2026-04-26) — არასოდეს ყოფილა top-level key, frontend-ი (`SupplierModal.jsx`) **მართებულად კითხულობს** nested location-დან.

**არ არის regression. არ არის broken. არ არის stale.**

---

## 1. Top-level key inventory (31 keys)

| # | key | size |
|---|---|---|
| 1 | aging_summary | dict[5] |
| 2 | ap_monthly_trend | list[47] |
| 3 | bank_reconciliation_audit | dict[29] |
| 4 | bank_unmatched_analysis | dict[14] |
| 5 | bog_expenses | dict[7] |
| 6 | budget | dict[4] |
| 7 | category_anomalies | dict[2] |
| 8 | company_valuation | dict[7] |
| 9 | download_files | list[13] |
| 10 | download_zip_file | str |
| 11 | executive_summary | dict[2] |
| 12 | financial_ratios | dict[4] |
| 13 | forecast | dict[3] |
| 14 | **imported_products** | **dict[38]** ← profitability nested here |
| 15 | megaplus_live | dict[1] |
| 16 | meta | dict[62] |
| 17 | monthly_pnl | list[45] |
| 18 | pos_terminal_income | dict[10] |
| 19 | retail_sales | dict[29] |
| 20 | source_manifest | list[6] |
| 21 | supplier_aging | list[193] |
| 22 | supplier_concentration | dict[11] |
| 23 | suppliers | list[259] |
| 24 | tax_flow | dict[15] |
| 25 | tbc_card_income | dict[5] |
| 26 | tbc_expenses | dict[7] |
| 27 | tbc_foodmart_cashback | dict[5] |
| 28 | tbc_samurneo | dict[16] |
| 29 | vat_reconciliation | dict[12] |
| 30 | waybill_reconciliation | dict[10] |
| 31 | waybills | list[21,799] |

**Keys containing "supplier" / "profit" (case-insensitive)**:

| key | რა არის | profitability data? |
|---|---|---|
| `suppliers` (list[259]) | AP/payment data per supplier (waybills_count, total_paid, total_debt, ...) | ❌ არ აქვს |
| `supplier_aging` (list[193]) | Payment-aging buckets per supplier | ❌ არ აქვს |
| `supplier_concentration` (dict[11]) | High-spend supplier analysis | ❌ არ აქვს |

**არც ერთ top-level key-ს არ ჰქვია "supplier_profitability".** ეს იყო ჩემი §12-ის misread-ის ფესვი.

---

## 2. რეალური მდებარეობა — `imported_products` ხეში

**`data["imported_products"]`** (38 top-level fields) შეიცავს ორ profitability-რელევანტურ entry-ს:

### 2a. `imported_products.profitability_summary` (overall portfolio)

```json
{
  "supplier_counts": {
    "verified": 64, "partial": 51, "unverified": 102,
    "protected": 3, "empty": 0
  },
  "portfolio": {
    "cost_imported_ge": 4,864,119.28 ₾,
    "cost_matched_ge": 3,156,059.65 ₾,
    "cost_ambiguous_ge": 1,798.72 ₾,
    "revenue_sold_ge": 2,164,485.41 ₾,
    "profit_ge": 299,971.53 ₾,
    "margin_pct": 13.86,
    "coverage_cost_pct": 64.88,
    "ambiguous_cost_pct": 0.04,
    ...
  },
  "alias_count": 0,
  "today": "2026-05-02"
}
```

**ცოცხალი ციფრები** (4-წლიანი portfolio-ზე):
- 220 supplier total (64 verified + 51 partial + 102 unverified + 3 protected)
- 4.86M ₾ cost imported
- 3.16M ₾ cost matched (64.88% coverage)
- 2.16M ₾ revenue from matched
- 300K ₾ profit @ 13.86% margin

### 2b. `imported_products.suppliers[*].profitability` (per-supplier)

**220 supplier-დან 220-ვე-ს** აქვს ცოცხალი `profitability` object. სამპლი (პირველი supplier — protected status):

```json
{
  "status": "protected",
  "minimal_display": false,
  "totals": {
    "products_imported": 98, "products_matched": 60,
    "products_ambiguous": 0, "products_unmatched": 38,
    "cost_imported_ge": 861,045.90, "cost_matched_ge": 385,585.30,
    "revenue_sold_ge": 388,792.40, "cost_sold_ge": 362,059.32,
    "profit_ge": 26,733.08, "margin_pct": 6.88
  },
  "coverage": {
    "cost_pct": 44.78, "product_pct": 61.22,
    "ambiguous_cost_pct": 0.0,
    "protected_cost_share_pct": 100.0,
    ...
  },
  "per_store_breakdown": [
    {"object": "ოზურგეთი", "cost_imported_ge": 404,792.45, "revenue_sold_ge": 179,920.10, "profit_ge": 12,287.80, "margin_pct": 6.83},
    {"object": "დვაბზუ", ...}
  ]
}
```

---

## 3. Production trace — pipeline call chain

**`generate_dashboard_data.py:1849-1857`** (commit `a6c68915`, 2026-05-01 — current):

```python
prof = build_supplier_profitability(data, aliases=safe_aliases)

# ჩაწერე profitability უკან თითოეულ supplier-ზე (tax_id-ით lookup)
per_sup_by_taxid = {row["tax_id"]: row["profitability"] for row in prof["per_supplier"]}
for sup_entry in (data.get("imported_products") or {}).get("suppliers") or []:
    tx = sup_entry.get("tax_id") or ""
    if tx in per_sup_by_taxid:
        sup_entry["profitability"] = per_sup_by_taxid[tx]   # ← embed per-supplier

# summary ცალკე გასცეს — DataQualityPage-ი წაიკითხავს
data.setdefault("imported_products", {})["profitability_summary"] = prof["summary"]   # ← summary nest-ი
```

**Architectural pattern**: function returns `prof = {"per_supplier": [...], "summary": {...}}`, code DOES NOT write `data["supplier_profitability"] = prof`. Instead:
1. Iterates `prof["per_supplier"]`, joins by `tax_id` to existing `imported_products.suppliers` entries, writes `profitability` field per supplier
2. Writes `prof["summary"]` to `imported_products.profitability_summary`

Try/except wraps it (line 1872): `except Exception as exc: logger.warning("პროდუქციული მოგება — ვერ აშენდა: %s", exc)` — **silent fail-back**: if function throws, only a warning, no traceback.

### Was it ever different? Git blame check

```
$ git log -S 'data["supplier_profitability"]' --oneline
(empty — no commit ever assigned this top-level key)

$ git blame -L 1845,1875 generate_dashboard_data.py
a6c68915 (2026-05-01)  prof = build_supplier_profitability(...)
a6c68915 (2026-05-01)  for sup_entry in ... ['imported_products']['suppliers']:
a6c68915 (2026-05-01)      sup_entry["profitability"] = per_sup_by_taxid[tx]
a6c68915 (2026-05-01)  data.setdefault("imported_products", {})["profitability_summary"] = prof["summary"]
```

Original wire-up commit (`8455486`, **2026-04-26**, ნახეთ commit message excerpt):

> "Plugged after `build_supplier_concentration` (line ~1624), before `_write_outputs`. Loads + validates `Financial_Analysis/product_aliases.json`, calls `build_supplier_profitability(data, aliases=safe_aliases)`, **writes the per-supplier `profitability` object back onto each [supplier]**"

ე.ი. **არასოდეს ყოფილა top-level key** — embed-ი intentional design იყო day 1-დან.

---

## 4. Frontend impact — SupplierModal.jsx ცოცხალი წაკითხავა

**`rs-dashboard/src/SupplierModal.jsx:405-740+`** აქტიურად კითხულობს nested profitability-ს:

| ხაზი | რა აკეთებს |
|---|---|
| 405-407 | `const profitability = importedEntry?.profitability || null;` — supplier object-დან field-ის წამოღება |
| 412-413 | `Array.isArray(profitability?.per_store_breakdown)` — per-store rendering |
| 439-459 | `profitability.totals` — KPI cards |
| 658+ | conditional render-ი status-ის მიხედვით (verified/partial/unverified/protected/empty) |
| 670-680 | `profitability.coverage.cost_pct` — coverage percentage display |
| 691-740 | `profitability.unmatched_preview` — unmatched products list |

**Frontend ცოცხალია.** არ არის broken, არ არის cache-ზე, არ არის stale.

`tabConfig.js` ხსოვს `imported_products` tab-ს (`📦 პროდუქცია`) — ცალკე `supplier_profitability` tab-ი არ არსებობს და არ უნდა არსებობდეს current architecture-ით.

---

## 5. Cache + intermediate files

**`_megaplus_live.json`** cache-ი (per-store ZIP backup state) მონაცემს ცალკე არ ინახავს ფაილური cache-ში — `megaplus_backup.process_all_stores()` returns dict in-memory რომელიც pipeline-ში deep-merge-ით data.json-ში ხვდება.

`_megaplus_live.json` მხოლოდ ZIP processing state ცხოვრობს (which ZIP last restored), არა supplier_profitability cache.

**არანაირი intermediate cache-ი არ ფარავს ცარიელ ცხრილს stale data-ით.**

---

## 6. Verification — current data.json snapshot ციფრები ცოცხალია

| რა | მნიშვნელობა |
|---|---|
| `imported_products.suppliers` რაოდენობა | 220 |
| Suppliers with non-empty `profitability` field | **220 / 220** ✓ |
| `imported_products.profitability_summary.today` | **2026-05-02** (yesterday's pipeline run) |
| `imported_products.profitability_summary.portfolio.cost_imported_ge` | 4,864,119.28 ₾ |
| `imported_products.profitability_summary.portfolio.profit_ge` | 299,971.53 ₾ |

ციფრები ცოცხალია (yesterday's ETL output), არ არის stale.

---

## 7. ცხრება (plain Georgian summary)

**`supplier_profitability` data.json-ში არის თუ არა?**

✅ **არის** — სრულად ცოცხალი 220 supplier-ისთვის. უბრალოდ **სხვა key-ის ქვეშ** (`imported_products.suppliers[*].profitability` + `imported_products.profitability_summary`), არა top-level `supplier_profitability` key-ში.

**როგორ გავარკვიე:**
1. პირველად მხოლოდ top-level keys ვათვალიერე → ვერ ვიპოვე `supplier_profitability` (PRODUCTS_FRAGMENTATION §12-ის misread)
2. დღეს — ღრმა inspection: `imported_products.suppliers[*]` სტრუქტურის გადათვლა → 220/220 supplier-ს ჰქონდა nested `profitability` field
3. Production code path verified: `generate_dashboard_data.py:1851-1857` explicitly writes nested
4. Git blame: ეს pattern-ი intentional იყო day 1-დან (`8455486`, 2026-04-26 wire-up commit)
5. Frontend (`SupplierModal.jsx:405-740+`) მართებულად კითხულობს nested location-დან

**§12-ის "supplier_profitability section absent" claim — ბოდიში, ჩემი misread.** Architectural pattern (nest under imported_products) ცოცხალი და მართებული — არც არ არის regression, არც არ არის broken.

---

## 8. ცხადი ღია question (no fix proposal)

ფაქტობრივი finding: **არცერთი real issue.** Supplier profitability data ცოცხალია, frontend-ი მართებულად რენდერავს, pipeline-ი ნორმალურად მუშაობს.

**შენი გადაწყვეტილება:**

1. **დავხუროთ ეს diagnostic** — false alarm, არცერთი action საჭიროა
2. **დავუბრუნდეთ original (a) deliverable-ის fix-path discussion-ს** — TYPING_DUP merge (~3K ₾, 12 barcode), Type B preventive workflow, Phase 1 (b) PRODUCTS orphans, etc.
3. **სხვა მიმართულება** — შენი არჩევანი

⚠️ **PRODUCTS_FRAGMENTATION §12-ის "🚨 Surprise finding" highlight მოსაცილებელია** (ან რეპორტში დავამატოთ correction note რომ ეს false alarm იყო) — შენი არჩევანი ცალკე update-ის ფარგლებში.

---

**Generated**: 2026-05-03 (Claude Code, Opus 4.7) · **STRICT SCOPE — diagnostic only, no fix proposed, no code touched. Issue resolved as misread by previous section. No regression detected.**
