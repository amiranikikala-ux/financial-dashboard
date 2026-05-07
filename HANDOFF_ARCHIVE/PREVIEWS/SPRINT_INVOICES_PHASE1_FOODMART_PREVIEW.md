# SPRINT — rs.ge Invoices Integration · Phase 1 (Foodmart 360°)

> **Status**: PREVIEW · NO CODE CHANGE
> **Date**: 2026-05-07
> **Owner ask**: ფაქტურები წამოვიღოთ rs.ge-დან, ფუდმარტის შემთხვევა გადავამოწმოთ (ფაქტურები vs TBC), მერე ყველა მომწოდებელზე გავავრცელოთ. გამოვიყენოთ ყველა მონაცემი — buyer/seller invoices, ბუღალტრის რეესტრი, TBC cashback, waybills, supplier_aging.
> **Trigger**: 2026-05-07 conversation — owner discovered rs.ge SOAP `chek_in` returns `false / sui=-3` (existing `dashboard_api:400333858` sub-user lacks invoice permission). Owner pointed to manually-downloaded CSV/XLS in `Financial_Analysis/რს ფაქტურები/`. We have full data offline; SOAP automation deferred.

---

## TL;DR

ფუდმარტის verification ცხადყოფს ჩვენი aging-ის 109,308 ₾-ის შეუსაბამობას ფაქტურებთან — ეს არის PRIMARY proof case. Phase 1: ფუდმარტი 360° view (1 supplier-ის სრული 4-side cross-check — buyer/seller invoices, TBC, waybills, aging). Phase 2: pattern-ი ყველა 260 მომწოდებელზე გავრცელდეს. Phase 3: VAT input-side reconciliation (extends `vat_reconciliation.py`). Phase 4: rs.ge SOAP automation (when owner grants section permission). Phases ცალცალკე session-ებშია, NOT all-at-once.

---

## Inventory — რა წავიკითხე და რა ვიპოვე

### Source files (verified 2026-05-07)

| ფაილი | რა აქვს | სიდიდე |
|---|---|---|
| `Financial_Analysis/რს ფაქტურები/ფაქტურები მყიდველი.csv` | 7,418 buyer invoice rows (incoming — supplier issued to us). 19 columns. UTF-8 BOM. | 2.4 MB |
| `Financial_Analysis/რს ფაქტურები/ფაქტურები მყიდველი რეესტრი.xls` | ~7,410 rows, single sheet "Grid", same columns as CSV. Bookkeeper's declaration registry snapshot. | 2.6 MB |
| `Financial_Analysis/რს ფაქტურები/ფაქტურები გამყიდველი.csv` | 99 line items per individual product (NOT per invoice — exploded). 15 columns. ~46 unique invoice IDs. | 34 KB |
| `Financial_Analysis/რს ფაქტურები/ფაქტურები გამყიდველი 1.csv` | Smaller variant of seller invoices. 15 KB. Likely older snapshot or different filter. | 15 KB |

### Verified counts (buyer side, 7,418 rows)

| Metric | Value | Notes |
|---|---|---|
| Valid rows | 7,402 | 16 rows have CSV-malformed amounts (>10M ₾, parser misalignment) |
| Total amount | **6,713,741 ₾** | 4-year aggregate, valid rows only |
| Total VAT | **~1,019,327 ₾** | dgg-ის თანხა column |
| Unique suppliers | **260** | by გამყიდველი TIN |
| Top supplier (by count) | ჯიდიაი 406181616 — 631 invoices | ELIZI 344 #2, საქ. დისტრიბუცია 223 #3 |
| Linked to waybills | **97.7%** (7,244 / 7,418) | column `ზედნადები` — comma-separated waybill numbers |
| **No waybill link** | **2.3%** (170) | ⚠️ drill-down needed (services? cancelled? excluded by date?) |
| Pending status `დასადასტურებელი` | 26 | bookkeeper action required |
| Status `დადასტურებული` | 6,366 | confirmed |
| `პირველადი` (primary) | 740 | not yet finalized |
| `კორექტირებული` | 276 | corrected |
| `გაუქმებული` | 2 | cancelled |

### Foodmart specific (tax_id 404460187)

| Source | Count | Amount | Direction |
|---|---|---|---|
| **Buyer invoices** (foodmart→us) | 60, all დადასტურებული | **163,082 ₾** | foodmart sells to us (water? drinks?) |
| **Seller invoices** (us→foodmart) | 46 unique IDs | **508,573 ₾** | we sell to foodmart (cigarettes? merchandise?) |
| **TBC cashback** (foodmart→us) | 36 lines | **335,202 ₾** | foodmart pays us via TBC, 2022-09 to 2026-05 |
| **supplier_aging** (foodmart→us) | from waybills | **53,774 ₾** ბრუნვა | computed from `effective_amount` of waybills |

**The 109,308 ₾ gap** (`163,082 invoices - 53,774 waybill-derived aging`) is the headline reconciliation finding for Phase 1.

### Existing pipeline plumbing (already in repo, verified)

| Component | File | Role |
|---|---|---|
| Waybill connector (live SOAP) | `dashboard_pipeline/rs_waybill_connector.py` | Pulls 531 waybills/30d via `services.rs.ge` |
| supplier_aging builder | `dashboard_pipeline/api_contracts.py:1859` | Computes `total_effective` from waybill `effective_amount` |
| analytics_builders supplier rows | `dashboard_pipeline/analytics_builders.py:294,424,585` | Reads `total_effective` from contracts; passes to UI |
| VAT reconciliation (output side) | `dashboard_pipeline/vat_reconciliation.py` | Already covers `bank_card + cashreg_in + invoices` (we-as-seller). **Input side (we-as-buyer) is NOT yet present.** |
| TBC foodmart cashback | `data.json::tbc_foodmart_cashback` | Already computed: 335,202 ₾, 36 lines, monthly summary |
| supplier_aging in modal | `rs-dashboard/src/SupplierModal.jsx` | Already shows total_effective, total_paid, total_debt, payment lines, waybill lines |

### rs.ge SOAP invoice service (verified 2026-05-07)

| Fact | Value |
|---|---|
| Endpoint | `https://webserv.rs.ge/specinvoices/SpecInvoicesService.asmx` |
| WSDL | accessible (107 KB, 2308 lines), 45+ methods |
| Right method for our use | `get_buyer_invoices_n` (params: `user_id`, `un_id`, `s_dt/e_dt`, `op_s_dt/op_e_dt`, optional filters) |
| Auth method | `chek_in(su, sp, user_id, log_text)` — returns `un_id` |
| **Current sub-user permission** | ❌ `dashboard_api:400333858` returns `chek_in: false / sui: -3` for invoice service (waybill service still works) |
| Permission grant path | rs.ge UI by main account owner — add „ანგარიშფაქტურა" section to `dashboard_api` sub-user |

---

## Output-shape audit (data.json contract)

New fields to add to `data.json`:

| Key | Shape | Source | Notes |
|---|---|---|---|
| `supplier_invoices` | `{[tax_id]: [{id, series, date_issued, date_op, amount, vat, status, decl_period, waybills: [string]}]}` | `ფაქტურები მყიდველი.csv` parsed | Keyed by supplier tax_id; arrays per supplier; JSON-safe primitives only |
| `supplier_invoices_summary` | `{[tax_id]: {invoice_count, total_amount, total_vat, status_counts: {[status]: int}, last_invoice_date}}` | derived from above | Lightweight summary for tables/KPIs |
| `our_seller_invoices` | `[{id, series, customer_tin, customer_name, date_issued, date_op, amount, vat, items: [...]}]` | `ფაქტურები გამყიდველი.csv` parsed | We as seller; ~46 invoices total |
| `invoice_waybill_match` | `[{invoice_id, supplier_tax_id, invoice_amount, matched_waybills: [waybill_no], waybill_amount_sum, gap}]` | JOIN buyer_invoices.ზედნადები ↔ waybills table | Per-invoice gap analysis |
| `supplier_invoices_meta` | `{generated_at, source_file, declaration_period_min, declaration_period_max, gap_alerts: [...]}` | metadata + cross-cutting alerts | Drives "26 დასადასტურებელი" KPI badge |

JSON-safety: Decimals → float (rounded to 2dp); dates → ISO `YYYY-MM-DD` string; status → Georgian string verbatim; waybill numbers → string array (preserve leading-zero numbers).

---

## Phase 1 — Foodmart 360° view (this sprint)

**Goal**: prove the data flow on a single supplier (foodmart 404460187) where the discrepancy is concrete and visible. Output is one new modal section + one verification panel; pipeline plumbing minimal.

**Implementation scope (1 session):**

1. **CSV parser** — new module `dashboard_pipeline/rs_invoice_csv.py`:
   - Read `ფაქტურები მყიდველი.csv` with proper UTF-8 BOM + comma-in-string handling (16 malformed rows → log + skip, no silent drop)
   - Normalize: parse `(TIN-დღგ) name` into `tax_id` + `name`; parse dates `DD-mmm-YYYY HH:MM:SS` (Georgian month abbrevs); parse `ზედნადები` comma-separated to list
   - Read `ფაქტურები გამყიდველი.csv` with line-item grouping by `ID` → invoice-level rows
   - Output: two pandas DataFrames

2. **Pipeline integration** — `generate_dashboard_data.py`:
   - Read parsed invoice DataFrames
   - Build `supplier_invoices` dict (keyed by `gamyidveli` tax_id), `supplier_invoices_summary` map, `our_seller_invoices` list
   - Single supplier focus: build `invoice_waybill_match` ONLY for foodmart (404460187) in Phase 1; full cross-supplier in Phase 2

3. **UI — SupplierModal new section** — `rs-dashboard/src/SupplierModal.jsx`:
   - New collapsible section „📋 ფაქტურები (rs.ge)"
   - Table: ID | სერია | თარიღი | თანხა | დღგ | სტატუსი | ზედნადები (linked count)
   - Status chip with color (დადასტურებული green, დასადასტურებელი yellow, etc.)
   - Footer KPIs: invoice count, total amount, total VAT, gap-vs-aging

4. **UI — Foodmart 360° verification panel** (NEW page or tab):
   - One-screen view: 4 cards
     - „ფუდმარტი → ჩვენ" (buyer invoices: 60, 163K)
     - „ჩვენ → ფუდმარტი" (seller invoices: 46, 509K)
     - „TBC ფუდმარტიდან" (cashback: 335K)
     - „Aging-ის ბრუნვა" (53,774)
   - Below: 109K gap explanation table — per-invoice list of foodmart's incoming invoices, with checkboxes „ზედნადებში ჩანს?" / „aging-ში ჩანს?"
   - Below that: monthly timeline (line chart) — invoice issue dates × waybill-coverage status

5. **Status KPI** in main dashboard:
   - Card: „26 ფაქტურა ბუღალტრის ხელში — 'დასადასტურებელი'"
   - Click → list of those 26 invoices with supplier names

---

## Roadmap — Phase 2/3/4 (separate sprints)

### Phase 2 — All-suppliers invoice integration (1-2 sessions)

- Extend `invoice_waybill_match` to all 260 suppliers
- New SupplierModal column: „ფაქტურა vs ზედნადები gap"
- New aggregate page: „რეკონცილიაცია" — top 20 suppliers ranked by `|invoice_total - waybill_aging|`
- Per-month gap trend chart
- Drill-down: click row → 360° view for that supplier (reuse Phase 1 panel as template)

### Phase 3 — VAT input-side reconciliation (1-2 sessions)

- Extend `dashboard_pipeline/vat_reconciliation.py`:
  - Add input VAT (purchases): sum of `dgg-ის თანხა` per declaration period from buyer invoices
  - Add net VAT position: output_vat - input_vat per month
  - Cross-check vs bookkeeper's declaration: declared_input_vat (from bookkeeper Excel) vs our_input_vat (computed)
- New §18 panel section: „დღგ ჩასათვლელი (purchases)"
- Red badge if our computed input VAT diverges >1% from bookkeeper's declared

### Phase 4 — rs.ge SOAP automation (1 session, when permission granted)

- New module `dashboard_pipeline/rs_invoice_connector.py` (mirror `rs_waybill_connector.py`):
  - `chek_in(su, sp, user_id=0)` → returns `un_id`
  - `get_buyer_invoices_n(user_id, un_id, s_dt, e_dt, op_s_dt, op_e_dt)` → invoice list
  - `get_seller_invoices_n(...)` symmetric
  - Map response XML to same shape as CSV parser output (drop-in replacement)
- Replace CSV-source path with SOAP-source path; CSV stays as fallback
- Daily scheduled refresh (APScheduler — already in stack)

---

## Risks / pitfalls

1. **CSV column 16 (`ზედნადები`) is comma-separated string with trailing space** — first row example: `'0962583623, 0966670470, 0966670471, 0970130475, '` (trailing comma+space). Must `.strip()` per-element AND drop empty trailing element. Test against trailing-comma + trailing-space + multi-space variants.

2. **Georgian month abbreviation parsing** — `01-აგვ-2026` (აგვისტო), `15-იან-2026` (იანვარი), `07-მაი-2026` (მაისი). Need explicit map (12 entries). 16 rows have malformed dates parsed as numbers (e.g. `90.78`) — these correlate with the 16 malformed amount rows; same root-cause CSV escape failure. Skip+log, don't infer.

3. **TIN extraction from `(TIN-დღგ) name`** — pattern `^\((\d+)-დღგ\)\s+(.+)$` for VAT-payer suppliers. But some suppliers are non-VAT and have format `(TIN) name` without `-დღგ` — second format must also work. Test against both. Empty `(NUMBER-დღგ)` (just code + no name) should also be allowed.

4. **Same invoice in both CSV files for status update** — `კორექტირებული` (corrected) means a new invoice replaces an old one with same series. Need dedup by ID; latest wins (use `გამოწერის თარ.` or status precedence). Existing data has 276 corrections — non-trivial.

5. **The 109K gap is a finding, not a bug** — possible legitimate causes:
   - Service invoices (no waybill) — e.g. delivery service, ad placement
   - Cancelled waybills with active invoice
   - Mid-period cutoff: invoice in 2026-05, waybill covered 2026-04-01..04-30
   - Returns: invoice issued, then return waybill issued separately
   - We must NOT auto-classify; surface for owner verification

6. **VAT computation edge cases** — some invoices have VAT=0 (non-VAT-payer suppliers, exempt items, exports). Some have aqcizi (excise) which is separate. Cannot blindly multiply `amount × 0.1525` (= 18/118) — must use the column.

7. **Privacy in CSV** — column `ქვე-მომხმარებელი` contains operator initials (e.g. `'ნ. მ.'`) — already privacy-redacted by rs.ge. Don't expose in UI without explicit reason.

8. **`ფაქტურები გამყიდველი.csv` is line-item-exploded** — 99 rows = ~46 invoices, multiple product lines per invoice. Group by ID; each invoice has 1+ items. Don't sum-as-invoice — sum-per-ID.

9. **Date parsing edge case** — some rows have `გამოწერის თარ.` filled but `ოპერაციის თარ.` empty (operation date is set later when invoice is approved). Use `გამოწერის თარ.` as primary, `ოპერაციის თარ.` as secondary.

10. **`ფაქტურები გამყიდველი 1.csv` (15 KB)** — likely an old snapshot or different period filter. Inspect before merging; might just be the 99-row file's older sibling. Skip in Phase 1; revisit in Phase 2 if non-redundant.

---

## Scope recommendation

**Do in this session (Phase 1 only):**
- CSV parser module
- Pipeline plumbing — add `supplier_invoices`, `supplier_invoices_summary`, `our_seller_invoices` to data.json
- SupplierModal — invoice section (read-only table, no actions)
- Foodmart 360° view as a new tab/page

**Defer (Phase 2/3/4):**
- All-suppliers gap analysis
- VAT input-side reconciliation (extends existing module — significant)
- rs.ge SOAP integration (blocked on permission grant)

**Owner action (out-of-band, not gating Phase 1):**
- rs.ge UI: grant `dashboard_api` sub-user the „ანგარიშფაქტურა" section permission. Phase 4 starts when this is done. Phases 1-3 work fully on local CSV/XLS.

---

## Test plan (Phase 1)

Mirror existing pattern (`tests/test_samurneo_incremental.py`, `tests/test_supplier_data_invariants.py`):

1. **`test_rs_invoice_csv_parser_basic`** — fixture CSV with 5 well-formed rows + 2 malformed rows; assert: 5 parsed, 2 skipped+logged, columns present, types correct.

2. **`test_rs_invoice_tin_extraction`** — feed `(400132192-დღგ) შპს პარტნიორი`, `(400132192) ი.მ. გიორგი`, `() empty`, `(non-numeric) bad`. Assert: TIN+name extracted correctly OR row marked invalid (not silent default).

3. **`test_rs_invoice_georgian_date_parsing`** — feed all 12 Georgian month abbreviations + `'90.78'` malformed. Assert: 12 parse to correct datetime, malformed → None + logged.

4. **`test_rs_invoice_waybill_split`** — feed `'1234, 5678, 9012, '` (trailing comma+space) + `''` + `'1234'`. Assert: 3 / 0 / 1 elements, no empty strings in result, all stripped.

5. **`test_supplier_invoices_summary_aggregation`** — feed 10 invoices for 3 suppliers, mixed statuses. Assert: per-supplier counts, totals, status_counts match hand-computed values.

6. **`test_invoice_seller_line_item_grouping`** — feed 5 line items across 2 invoice IDs. Assert: result has 2 invoice rows with grouped item arrays, amounts summed correctly.

7. **`test_foodmart_360_gap_calculation`** — feed mock foodmart data: 5 buyer invoices (sum 100K) + 3 waybills (sum 60K). Assert: gap=40K computed, gap_alert flagged when >1% threshold.

8. **`test_data_json_contract_invoices`** — run pipeline against fixture; assert `data["supplier_invoices"]` has expected keys, `data["supplier_invoices_summary"]["404460187"]["invoice_count"] == expected`, JSON.dumps roundtrip succeeds.

---

## Files expected to change

| Path | Change | Purpose |
|---|---|---|
| `dashboard_pipeline/rs_invoice_csv.py` | **NEW** | CSV parser for buyer/seller invoices |
| `generate_dashboard_data.py` | edit (insert ~30 lines around §1900) | Hook into pipeline; populate 3 new data.json keys |
| `dashboard_pipeline/api_contracts.py` | edit | Add `supplier_invoices`, `supplier_invoices_summary`, `our_seller_invoices` to contract; JSON-safety |
| `rs-dashboard/src/SupplierModal.jsx` | edit (new section ~80 lines) | Invoice table per supplier |
| `rs-dashboard/src/Foodmart360.jsx` | **NEW** | 4-card panel + gap timeline |
| `rs-dashboard/src/App.jsx` | edit | Route `/foodmart-360` tab; pass invoice data to SupplierModal |
| `rs-dashboard/src/components/DashboardTabs.jsx` | edit | Add tab entry |
| `tests/test_rs_invoice_csv_parser.py` | **NEW** | tests 1-4, 6 above |
| `tests/test_supplier_invoices_pipeline.py` | **NEW** | tests 5, 7, 8 above |
| `tests/fixtures/rs_invoice_sample.csv` | **NEW** | small fixture for tests |

---

## Self-check checklist (pre-commit)

- [ ] `rs_invoice_csv.py` parses real `ფაქტურები მყიდველი.csv` to 7,402 valid rows (assert exact count)
- [ ] Foodmart count: 60 buyer invoices + 46 seller invoices (unique IDs) — match this preview's spec
- [ ] No CSV row silently dropped — every skip is logged with reason + row index
- [ ] data.json size grows by acceptable amount (~3-5 MB max — 7,402 invoices × small object)
- [ ] supplier_invoices_summary aggregate equals raw sum (no float drift > 0.01 ₾)
- [ ] `npm run build` clean
- [ ] All 8 new tests pass
- [ ] Existing tests unchanged (no regressions in `test_supplier_data_invariants.py`)
- [ ] SupplierModal renders foodmart's 60 invoices without freezing (perf check — virtualize if >100)
- [ ] Foodmart 360° tab loads <500ms after data.json fetch
- [ ] Owner can manually verify on UI: foodmart row has "ფაქტურა vs aging" gap visible

---

## Evidence sources

- Source files (verified file-stat 2026-05-07):
  - `Financial_Analysis/რს ფაქტურები/ფაქტურები მყიდველი.csv` (2,468,334 bytes)
  - `Financial_Analysis/რს ფაქტურები/ფაქტურები მყიდველი რეესტრი.xls` (2,691,072 bytes)
  - `Financial_Analysis/რს ფაქტურები/ფაქტურები გამყიდველი.csv` (34,096 bytes)
- Existing pipeline anchors:
  - `dashboard_pipeline/api_contracts.py:1859` — `total_effective` from waybill effective_amount
  - `dashboard_pipeline/vat_reconciliation.py` — output-side VAT (header comment lines 1-37)
  - `dashboard_pipeline/rs_waybill_connector.py:29` — SOAP endpoint pattern
- rs.ge SOAP probe (this session, scratch file deleted):
  - `webserv.rs.ge/specinvoices/SpecInvoicesService.asmx?WSDL` — HTTP 200, 107,268 bytes
  - `chek_in` response with `dashboard_api:400333858` — `chek_inResult: false`, `sui: -3`
- Memory:
  - `feedback_proactive_verification.md` (2026-05-07) — verify before claiming
  - `project_rsge_soap_api.md` (2026-05-04, partially stale — invoice service URL was wrong; correct URL verified this session)
- Recent commits:
  - `d380a89` (2026-05-07) — live overlay across tables (most recent)
  - `87b1bfe` (2026-05-07) — negative debt / drop browser localStorage
  - `4e56e0f` (2026-05-07) — manual payments server-side
