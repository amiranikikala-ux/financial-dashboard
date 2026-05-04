# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-05-04 საღამო (rolling from 2026-05-04 დღე — **🎉 TBC DBI Stage 1a + 1b + 2 PROOFED ერთი session-ში: 100% parity vs manual XLSX for window 2026-03-01 → 2026-03-03 (104 rows, debit 9,641.40 / credit 9,994.94 — match to the cent, 4/5 random documentNumber spot-checks exact, 1 spot-check artifact from documentNumber duplication on TBC side — non-blocking)**). NO production code change yet — only scratch artifacts (gitignored).
>
> Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`. სრული ისტორია (აპრილი 18 → მაისი 2) → `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-04_2026-05-02.md`.

---

## 0. დღევანდელი session-ი (2026-05-04 — Sprint A + Sprint A addon + BOG Stage 1-3 PROOFED + TBC DBI Stage 1a/1b PROOFED)

### 0f. TBC DBI (Direct Bank Integration) — Stage 0/1a/1b/2 PROOFED საღამოს session-ში

**Status**: ✅ end-to-end PROOFED — Stage 0 (research) + Stage 1a (password change) + Stage 1b (auth verification) + Stage 2 (XLSX parity 100% to the cent). Stage 3 (production connector module) ღია — separate sprint.

**Source materials (user-provided + research, 2026-05-04 evening):**
- `New folder/WSDL_XSD_and_Single_WSDL.zip` (TBC DBI WSDL/XSD v1.14, 2017-2023) — user-მა მოიტანა
- Official docs: `developers.tbcbank.ge/docs/dbi-overview` + sub-pages (test environment, password change, account movement, digital certificate, go-live)
- Official .NET SDK: `github.com/TBCBank/TBC.OpenAPI.SDK.DBI` (verified C# source — auth scheme + WS-Security pattern)

**Verified facts (source-1:1):**

| ფაქტი | მნიშვნელობა |
|---|---|
| **Production endpoint** | `https://dbi.tbconline.ge/dbi/dbiService` (Standard tier, NO certificate) |
| Test endpoints | `https://test.tbconline.ge/dbi/dbiService` (no cert, requires TBCRootCer.cer locally — Python SSL handshake failed) · `https://secdbitst.tbconline.ge/dbi/dbiService` (with cert) |
| Standard+ production | `https://secdbi.tbconline.ge/dbi/dbiService` (requires .pfx client cert) |
| **Username** | `FOODTIME_TBC` (uppercase, with FOOD not FUD) |
| **IBAN** | `GE90TB7793336020100005` (GEL) |
| **Auth scheme** | WS-Security `UsernameToken` — **plain text** Username + Password + Nonce (verified from SDK `src/TBC.OpenAPI.SDK.DBI/Models/SecurityConfig.cs` — NO PasswordDigest, NO wsu:Created, NO Type attribute) |
| **Nonce semantics** | DigiPass-generated 9-digit OTP (PIN: 0777, 9-digit code shown) — validity window ~5-15 min (one code reused successfully across 2 calls then expired on 3rd) |
| **Password complexity** | 8+ chars · 1+ uppercase · 1+ lowercase · 1+ digit · 1+ symbol · cannot match username/old · `&` and `<` forbidden |
| **5 services available** | StatementService (aggregates) · MovementService (per-transaction, paged 700 max) · PaymentService · PostboxService · ChangePasswordService |
| **Statement vs Movement** | StatementService = aggregates only (opening/closing balance + debit/credit sums) · MovementService = per-transaction detail (40+ fields, BOG analog) |
| **Movement field richer than BOG** | 40+ fields incl. partnerTaxCode · taxpayerCode · treasuryCode · operationCode · exchangeRate · partnerPersonalNumber/DocumentType (cash withdrawal) |
| **DateTime format in requests** | `yyyy-MM-dd'T'HH:mm:ss.SSS` (e.g. `2026-03-01T00:00:00.000` — milliseconds REQUIRED) |
| **Response wrapping** | `<accountMovement>` per-row (NOT `<movement>`) · `<result><pager><totalCount>` block |

**Stage 1a — password change PROOFED (2026-05-04 evening):**
- SMS one-time temporary password → user-chosen permanent (16 chars, satisfies complexity rules)
- SOAP `ChangePasswordService.ChangePassword` returned: `<message>Credentials have been successfully changed!</message>`
- Server response: HTTP 200, 383 bytes
- Test artifact: `_scratch_tbc_chpwd.py`

**Stage 1b — auth verification PROOFED (2026-05-04 evening):**
- SOAP `StatementService.GetAccountStatement` for week 2026-04-27 → 2026-05-03
- HTTP 200, real account data returned:

| | მნიშვნელობა |
|---|---|
| openingDate | 2026-04-27 |
| openingBalance | 571.12 ₾ |
| closingDate | 2026-05-03 |
| closingBalance | 322.64 ₾ |
| creditSum | 27,319.82 ₾ |
| debitSum | 27,568.30 ₾ |

- Test artifact: `_scratch_tbc_auth.py` + `_scratch_tbc_auth_response.xml`

**Stage 2 — XLSX parity PROOFED (2026-05-04 evening, 3rd run with fresh DigiPass `050570513`):**

| | XLSX | SOAP | match |
|---|---|---|---|
| Record count | 104 | 104 | ✓ |
| Sum debits | 9,641.40 ₾ | 9,641.40 ₾ | ✓ to the cent |
| Sum credits | 9,994.94 ₾ | 9,994.94 ₾ | ✓ to the cent |
| 5 random documentNumber spot-checks | 4/5 exact | — | ✓ amounts + partner names |

**1 spot-check artifact (non-blocking):** documentNumber `1772438632` appeared multiple times on the TBC side (one fee row + one principal row sharing the same docNum). Spot-check's dict-keyed-by-docNum collapsed them, so XLSX side picked the -1.00 fee row while SOAP side picked the -480.00 principal row. Aggregate sums still match to the cent → both sides have all 104 rows. Resolution: production connector should key on a composite (docNum + amount + counterparty) when joining, not docNum alone.

**Earlier debug iterations (now fixed in `_scratch_tbc_statement.py`):**
- Filter element: `<accountMovementFilterIo>` (was `<filter>`)
- Response element: `<accountMovement>` (was `<movement>`)
- DateTime: added milliseconds `.000` / `.999`
- DigiPass per-call validity: ~5-15 min — code `050570513` worked first try after fresh PIN entry

**Live discovery — XLSX file naming convention:**
- `03.2026.xlsx` actually contains **12 months** of data: 2025-03 → 2026-03 (NOT just March 2026)
- 19,919 rows total for IBAN `GE90TB7793336020100005`
- Per-month volume: ~1,500 rows/month, total debit/credit ~95K-140K ₾/month

**Files added this session (all gitignored, all `_scratch_tbc_*` prefix):**

| ფაილი | სტატუსი | რას აკეთებს |
|---|---|---|
| `_scratch_tbc_probe.py` | DONE (delete OK) | endpoint discovery probe (was used to find production URL) |
| `_scratch_tbc_chpwd.py` | DONE | Stage 1a password change (one-shot, success) |
| `_scratch_tbc_chpwd_request.xml` | DONE (delete OK) | debug — passwords redacted |
| `_scratch_tbc_chpwd_response.xml` | DONE (delete OK) | server "successfully changed" message |
| `_scratch_tbc_auth.py` | DONE | Stage 1b — fetches StatementService aggregates |
| `_scratch_tbc_auth_response.xml` | DONE | live week aggregates response |
| `_scratch_tbc_statement.py` | DONE | Stage 2 — MovementService + XLSX parity (PROOFED 2026-05-04 evening) |
| `_scratch_tbc_statement_response.xml` | DONE | live 104-movement response, all pages concatenated |

**.env additions (gitignored):**
```
TBC_DBI_ENDPOINT=https://dbi.tbconline.ge/dbi/dbiService
TBC_USERNAME=FOODTIME_TBC
TBC_PASSWORD=<set>
TBC_NONCE=<requires fresh DigiPass code each run>
TBC_ACCOUNT_NUMBER=GE90TB7793336020100005
TBC_ACCOUNT_CURRENCY=GEL
```

**🆕 Critical operational finding — DigiPass automation limit:**
- Hardware DigiPass token: PIN 0777 → 9-digit OTP, no USB/Bluetooth, NO automation path
- Bank confirmed (separate phone call by user): DigiPass cannot be bypassed for DBI
- Practical workflow: **interactive prompt** at sync time — user runs script, script asks "enter DigiPass code", user types 9 digits, script proceeds
- One DigiPass code valid ~5-15 min window → enough for full backfill OR daily sync in single call
- Daily friction: ~10 seconds of human input

**Open for next session — priority order:**

1. **Stage 3 design** — `dashboard_pipeline/tbc_bank_connector.py` (analog `rs_waybill_connector.py`):
   - `TBCBankConnector(username, password)` with auto-load `.env`
   - `fetch_movements(start, end, nonce)` with internal paging (700 max per page per docs)
   - `to_xls_dataframe(movements)` matching the 24-column XLSX schema (`თარიღი / დანიშნულება / ტრანზაქციის ტიპი / თანხა / ვალუტა / ანგარიშის ნომერი / ...`) for drop-in replacement
   - **Interactive Nonce prompt** OR `nonce` parameter (user-supplied per run)
   - Composite join key (docNum + amount + counterparty) — single docNum collision verified Stage 2
2. **Wire-in to pipeline** (separate sprint, user approval needed) — replace `Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx` consumption in `bank_reconciliation.py` with live SOAP fetch
3. **Cleanup pending**: 8 `_scratch_tbc_*` files (all gitignored) — delete after Stage 3 connector module is committed

**Decision points for user:**
- Wire-in strategy: live SOAP only (no XLSX), OR augment (SOAP writes daily XLSX into existing folder, pipeline unchanged), OR SOAP for current period + XLSX preserved for history (recommended — analog rs.ge Sprint A finalization)
- Whether to also add Standard+ certificate path (for future redundancy / if TBC requires migration to Standard+)
- Whether to wire-in BOG production module first (already PROOFED Stage 3 in §0e) before TBC

---

## 0. დღევანდელი session-ი (2026-05-04 დღე — Sprint A + Sprint A addon + BOG Stage 1-3 PROOFED)

### 0e. BOG Business Online API — Stages 0/1/2/3 closed in single session

**Status**: ✅ end-to-end PROOFED (auth + live statement fetch + 100% parity vs manual XLSX). NO production code change yet.

**Stage 0 (registration — closed in earlier web Claude session 2026-05-04 day):**
- App registered at bonline.bog.ge as **`GeoFoodTime bog`** (Client Credentials flow)
- Account: **GE15BG0000000537419534GEL** (GEL current account, READ-ONLY)
- Permissions: "View details" + "All operations" (no transfer/no edit — least-privilege)
- Client ID + Client Secret stored in `.env` (gitignored)

**Stage 1a — auth (token endpoint):**
- `https://account.bog.ge/auth/realms/bog/protocol/openid-connect/token`
- POST + Basic header (base64 of `client_id:client_secret`) + `grant_type=client_credentials`
- Returns Bearer token (942 chars), `expires_in=1800` seconds, `scope=cib-scope`
- Test file: `_scratch_bog_token.py` (gitignored)

**Stage 1b — statement endpoint discovery:**
- ⚠️ docs page says `GET /api/statement/{account}/{currency}/{startDate}/{endDate}` but doesn't state the host
- ⚠️ `api.bog.ge` is the docs/marketing site, NOT the production API
- ✅ **Production API host: `https://api.businessonline.ge`** (verified by probing 6 candidates)
- Auth: `Authorization: Bearer <token>`
- Date format: `YYYY-MM-DD`
- Test file: `_scratch_bog_statement.py` (gitignored)

**Stage 2 — spot-check vs manual XLSX (2026-05-04):**

Source: `Financial_Analysis/ბოგ ბანკი ამონაწერი/03,2026.xlsx` (March 2026, 5,075 records, headers on row 12).

Comparison window: 2026-03-01 → 2026-03-03 (3 days, fits under 1000-record API limit).

| | API | XLSX | match |
|---|---|---|---|
| Record count | 453 | 453 | ✓ |
| Common operation IDs | 453 | 453 | ✓ (0 missing on either side) |
| Sum debits | 3,891.84 ₾ | 3,891.84 ₾ | ✓ to the cent |
| Sum credits | 5,336.42 ₾ | 5,336.42 ₾ | ✓ to the cent |
| Spot-check 5 random IDs (amount + beneficiary) | 5/5 | — | ✓ all |

**🎉 Stage 3 PROOFED** — same equivalence-class as rs.ge Stage 3 (2026-05-03 ღამე).

**Field mapping (API ↔ XLSX columns):**

| API field | XLSX column | notes |
|---|---|---|
| `EntryDate` | `თარიღი` | datetime |
| `EntryId` | `ოპერაციის იდ` | unique transaction ID — primary join key |
| `EntryAmount` | `თანხა` | signed amount (debit negative, credit positive) |
| `EntryAmountDebit` | `დებეტი` | unsigned debit |
| `EntryAmountCredit` | `კრედიტი` | unsigned credit |
| `EntryComment` | `ოპერაციის შინაარსი` | description |
| `DocumentProductGroup` | `ოპერაციის ტიპი` | TRN/PMD/COM/etc. |
| `SenderDetails.Name` | `გამგზავნის დასახელება` | nested object in API |
| `BeneficiaryDetails.Name` | `მიმღების დასახელება` | nested object |
| `BeneficiaryDetails.AccountNumber` | `მიმღების ანგარიშის ნომერი` | IBAN |

**Open gaps for next session:**

1. **1000-record per-call limit** — confirmed real (March 2026 has 5,075 records, single call returns first 1000). No pagination param documented. Strategy: date-window slicing per day or per-week, then concatenate. Smart slicer can use `Count` field to detect when to narrow.
2. **Max historical range** — not yet tested. Try 2023 or earlier to confirm rs.ge-style 4-year retention.
3. **Rate limits / daily quota** — not yet hit during testing (a few dozen calls). Production backfill (~5 years × ~365 days = ~1,825 daily slices) needs rate-limit testing.
4. **Other currencies** (USD/EUR/POS accounts) — separate registration cycle in bonline.bog.ge needed; current scope is GEL-only.
5. **TBC API integration** — deferred per Stage 0 plan (BOG-first, then TBC).

**Files added this session (BOG part, all gitignored):**
- `_scratch_bog_token.py` — Stage 1a OAuth token test
- `_scratch_bog_statement.py` — Stage 1b/2 statement fetch + spot-check
- `_scratch_bog_token_response.json` — cached Bearer token (token rotates every 30 min)
- `_scratch_bog_statement_response.json` — raw 30-day API response (last 30 days, 1000 of 6,152 records)

**Production wire-in plan (DEFERRED — separate sprint, user approval required):**
- Build `dashboard_pipeline/bog_bank_connector.py` (analogous to `rs_waybill_connector.py`):
  - `BOGBankConnector(client_id, client_secret)` with auto-load `.env`
  - `fetch_statement(start, end)` with internal date-window slicing for the 1000-limit
  - `to_xls_dataframe(records)` matching the 26-column XLSX schema for drop-in replacement
- Then update `bank_reconciliation.py` to consume BOG API output instead of `Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx`
- Cleanup pending: 4 `_scratch_bog_*` files after wire-in.

---

## 0. დღევანდელი session-ი (2026-05-04 დღე — Sprint A + Sprint A addon)

### 0a. Sprint A — rs.ge connector PROOFED + production module created

**Status**: ✅ PROOFED end-to-end (offline parser parity + live SOAP smoke test).

**File written**: `dashboard_pipeline/rs_waybill_connector.py` — production-quality SOAP client.
- `RSWaybillConnector(user, password)` — thin SOAP client, env vars `RS_USER` + `RS_PASS` (or pass to ctor)
- `check_auth()` — verifies sub-user via `chek_service_user`
- `fetch_buyer_waybills(start, end)` — returns `list[Waybill]` with 26 fields
- `get_name_from_tin(tin)` / `is_vat_payer_tin(tin)` — TIN lookup helpers
- `to_xls_dataframe(waybills, vat_payer_tins)` — converts to **the same 21-column Georgian-named DataFrame** the existing pipeline reads from manual `*.xls` exports (drop-in source replacement when wired in)

**Verified mappings** (cross-correlated 480 IDs against `Financial_Analysis/რს ზედნადები/04,2026.xls`):
- STATUS codes: 1=აქტიური · 2=დასრულებული · -2=გაუქმებული
- TYPE codes: 2=ტრანსპორტირებით · 3=ტრანსპორტირების გარეშე · 5=უკან დაბრუნება · 6=ქვე-ზედნადები
- SELLER_ST: 0=გამყიდველი (1=მყიდველი — not yet seen in sample data; pipeline does not consume this field)

**Parity test** — pipeline-equivalent aggregate amounts identical SOAP vs XLS for 480 common IDs:

| | nominal | effective | returned |
|---|---|---|---|
| SOAP | 151,725.79 ₾ | 151,059.79 ₾ | -4,224.62 ₾ |
| XLS  | 151,725.79 ₾ | 151,059.79 ₾ | -4,224.62 ₾ |

**Non-blocking cosmetic mismatches found**:
- Date precision — SOAP gives second precision (`09:56:11`), XLS rounds to minute (`09:56:00`). Pipeline reconciles at day-level, irrelevant.
- `უკან დაბრუნება` amount sign — SOAP returns `+18.5`, XLS shows `-18.5`. **FIXED** in `to_xls_dataframe` (negates `FULL_AMOUNT` for TYPE=5 to match XLS convention; pipeline's `get_returned` reads raw `თანხა` directly).
- `ტრანსპორტირების ხარჯი` — `get_buyer_waybills` summary endpoint always returns `SELLER_ST=0`; XLS sometimes shows `მყიდველი`. **Non-blocking** — pipeline does not consume this column. Per-waybill detail (`get_waybill(id)`) may have the proper field, TBD.

**Live smoke test** (`_scratch_rs_connector_smoke.py`, end-to-end through new module):
- AUTH OK · 531 waybills fetched · 170,676.74 ₾ · DataFrame 531 rows × 21 cols · 480 common IDs vs 04,2026.xls
- Aggregate parity confirmed live (same numbers as offline parser test)

**Pipeline integration NOT yet wired in** (deferred to separate sprint, deliberate scope):
- `list_rs_waybill_files()` still reads `Financial_Analysis/რს ზედნადები/*.xls` only
- `generate_dashboard_data.py` unchanged — pipeline output identical to before
- Connector standalone, ready to plug in when user approves

### 0b. Sprint A addon — PRODUCTS orphan resolver DELIVERED (read-only)

**Status**: ✅ Excel review file written: `Financial_Analysis/orphan_resolver_review_2026-05-04.xlsx`.

**File written**: `dashboard_pipeline/orphan_resolver.py` — read-only utility, NEVER writes to MegaPlus DB.
- Identifies 3 categories of orphans: NULL/empty supplier · zero-UUID placeholder · "ghost" UUID (FK points to missing DISTRIBUTORS row)
- Resolves via 2 evidence sources, ranked by confidence:
  1. **`RS_CODES`** (MegaPlus's own product↔TIN ledger, 189K rows) → JOIN to `DISTRIBUTORS` by TIN — **bypasses ghost-UUID problem entirely** (key insight)
  2. **`GET`** (receipt history) — secondary evidence (most receipt UUIDs also ghost — limited usefulness)
  3. **SOAP fallback** (`get_name_from_tin`) for TINs unknown to `DISTRIBUTORS`
- Output: 4-tab Excel (`summary` · `all_orphans` · `multi_candidate` · `no_match`)

**🆕 Surprise finding — chat-history claim was wrong** (per Phase 1 (a) lesson, anchor numbers from chat are unverified):

| | chat-history (DEFLATED) | source-first re-derivation (verified) |
|---|---|---|
| Orphan products (active) | 3,046 | **4,918** |
| Lifetime revenue at risk | 231K ₾ | **685,804 ₾** |

Real picture is **2x bigger** than CONTEXT_HANDOFF.md §4 #4 (a) claimed. The chat-history number was likely a partial slice of one orphan category only (cleanup deleted the original SQL — could not recover origin).

**Per-category breakdown** (verified via independent SQL query, both stores):

| კატეგორია | აქტიური P_ID | ბრუნვა (lifetime) |
|---|---|---|
| ცარიელი (P_DAFAULTSUPPLIER null/empty) | 164 | ~5,400 ₾ |
| ნულოვანი ID (`00000000-0000-0000-0000-000000000000`) | ~62 | ~14,000 ₾ |
| **მოჩვენების ID (FK to missing DISTRIBUTORS row)** | **~4,692** | **~666,000 ₾** |

The "ghost UUID" category dominates — it's a **schema-migration artifact**: PRODUCTS rows still hold legacy numeric supplier IDs (`'8502'`, `'8296'`, `'1810'`...) padded to char(36) where DISTRIBUTORS now uses real UUIDs.

**Resolution rate** (both stores combined):

| | რაოდენობა | % |
|---|---|---|
| ✅ Auto-resolved (RS_CODES → DISTRIBUTORS by TIN) | **4,647** | **94.5%** |
| ⏳ SOAP_PENDING (TIN known to RS_CODES, not in DISTRIBUTORS — 5-10 unique TINs) | 26 | 0.5% |
| ❌ NO_MATCH (no RS_CODES entry — ~200 are promo barcodes / internal codes, not real orphans) | 245 | 5.0% |

**Per-store**:
- დვაბზუ: 2,478 orphans / 379,918 ₾ → 2,427 resolved (97.9%) · 3 SOAP_PENDING · 48 NO_MATCH
- ოზურგეთი: 2,440 orphans / 305,886 ₾ → 2,220 resolved (91.0%) · 23 SOAP_PENDING · 197 NO_MATCH

**Spot-check verification** (top 10 highest-revenue orphans, evidence chain re-queried live):
- 8/8 working rows verified — recommendations align with live `RS_CODES` + `DISTRIBUTORS` cross-source data
- 1 multi-candidate case (P_ID 87932 — შაქარი 50კგ) — both 206335223 ("ჯიბე შპს") AND 33001015885 ("თ. ხ", individual) have 2 RS_CODES rows each, both registered in DISTRIBUTORS — **resolver flagged in `multi_candidate` tab, user picks**
- 1 SOAP-fallback case (P_ID 88539 — HELL ENERGY, TIN 406203638) — TIN not in DISTRIBUTORS, marked SOAP_PENDING

**Independent SQL verification of 271 breakdown** (separate session check, both stores cross-counted):
- NO_MATCH = 245 (SQL: orphans with `NOT EXISTS` in RS_CODES)
- SOAP_PENDING = 26 (SQL: orphans with RS_CODES TINs but `LEFT JOIN DISTRIBUTORS` all-NULL)
- Sum = 271 ✓

**Confidence guarantee**: 0 false recommendations. Every auto-resolved row has cross-source evidence (RS_CODES TIN match + DISTRIBUTORS lookup). Multi-candidate cases (~221 orphans, ~5%) are honestly flagged with all alternatives in `all_candidate_TINs` column — user picks.

### 0c. Open for next session (Sprint A addon optional follow-up + carried forward)

1. **SOAP run for 26 SOAP_PENDING** (5-min addon, only ~5-10 unique TINs to resolve):
   ```powershell
   $env:RS_USER = "dashboard_api:400333858"
   $env:RS_PASS = "<password>"
   & "C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe" -m dashboard_pipeline.orphan_resolver
   ```
   Output overwrites `Financial_Analysis/orphan_resolver_review_<date>.xlsx` with names filled in.

2. **User reviews `Financial_Analysis/orphan_resolver_review_2026-05-04.xlsx`** and applies 4,647 mappings via MegaPlus UI (NOT auto-write — risk control, deliberate). After mappings applied + next backup → resolver rerun should show ~0 orphans for resolved categories.

3. **Pipeline integration of rs_waybill_connector** (separate Sprint, user approval needed):
   - Option A: Replace `list_rs_waybill_files()` with SOAP fetch (live, no XLS files)
   - Option B: Augment — connector writes daily XLS into `Financial_Analysis/რს ზედნადები/` for pipeline to consume (zero pipeline change)
   - Option C: SOAP for current period, XLS preserved for history (recommended — past data immutable, going forward auto)
   - Note: pipeline does NOT currently dedupe by ID across XLS files (verified — 22,338 rows / 22,338 unique IDs); integration must add explicit dedup or non-overlapping period semantics.

4. **Cleanup pending after user reviews orphans Excel**: 6 `_scratch_rs_*` + `_scratch_orphans_*` + `_scratch_rs_connector_smoke.py` files (test artifacts + 485 KB live financial data) — gitignored, can delete after Sprint A integration.

### 0d. Files added this session (no commits yet — Push pending decision)

| ფაილი | სტატუსი | რას აკეთებს |
|---|---|---|
| `dashboard_pipeline/rs_waybill_connector.py` | NEW | rs.ge SOAP client + XLS-equivalent DataFrame producer |
| `dashboard_pipeline/orphan_resolver.py` | NEW | PRODUCTS orphan resolver (read-only review file generator) |
| `Financial_Analysis/orphan_resolver_review_2026-05-04.xlsx` | NEW (output) | 4-tab review file (summary · all_orphans · multi_candidate · no_match) |
| `_scratch_rs_connector_smoke.py` | NEW (gitignored) | Live smoke test for new connector module |
| `_scratch_orphans_count.py` | NEW (gitignored) | Source-first orphan count verification (one-shot) |

---

## 1. ბოლო სამუშაო session-ი (2026-05-03)

### 1a. ღამე-მერე — Phase A + Phase B exploratory research (READ-ONLY)

**Scope:** ბუღალტრული ცდომილებების catalog-ი (Phase A) + 4 detector-ის შემოწმება მონაცემზე (Phase B). **არცერთი production კოდი არ შეცვლილა, არცერთი commit, არცერთი push.** მთლიანი work in-process scratch-ფაილებში — ყველა წაშლილი ფინალურ რეპორტთან ერთად. რეპორტები chat-ში დარჩა.

**Phase A — 34-ცდომილების catalog (chat-ში, no .md per scope):**
- 6 ბლოკში დაიყო: დოკუმენტური · VAT · cross-source · რაოდენობა/ნაშთი · ფასი/მარჟა · სპეციფიკური
- 6 უკვე ვიჭერთ (waybill_reconciliation tab — missing/wrong_store/amount_mismatch/ghost_ap/returns/stale)
- 25 ახალი detector კანდიდატი + 3 ნახევრად ღია
- წყაროები: `SHPS_RETAIL_TAX_GUIDE_KA.md` · საგ. კოდექსი მუხ. 286 · #84/#86/#996 ბრძანებები · eaudit.ge · matsne #5389341

**Phase B — 4 detector შემოწმდა:**

| # | detector | ვერდიქტი | რა აღმოჩნდა |
|---|---|---|---|
| 5  | ფაქტურის გვიანი გამოწერა (>2 დღე) | ❌ NO VALUE | 99.6% ხაზი ±2 დღეში; MegaPlus G_TIME თითქოს ფაქტურის ქაღალდიდან კრეფს — ვერ აკონტროლებს |
| 20 | არააღრიცხული პროდუქცია | ⚠️ DATA QUALITY FIRST | 6,656 candidate / 572K ₾ — დომინირებს PRODUCTS ფრაგმენტაცია + ობოლი მომწოდებლები |
| 21 | უარყოფითი ნაშთი | ⚠️ DATA QUALITY FIRST | 2,408 product / 149K ცალი deficit — დომინირებს consumables (პარკი/ჭიქა/რეზინი) + 38% trivial timing |
| 25 | უარყოფითი მარჟა | 🚨 ცხადი სიგნალი + ახალი ცოდნა | 57,048 row (4.13% with-cost) / **95,682 ₾ loss** 4 წელში — დომინირებს packaging-unit cost confusion |

**🆕 ახალი ცოდნა — 3 ფესვიანი findings (Phase B-ის მთავარი ღირებულება):**

**1. Packaging-unit cost confusion** (Detector #25) — ოპერატორები POS-ში cost-ად აკრეფენ **ბლოკის ფასს**, მაგრამ ცალი იყიდება ცალკე-ცალკე. შედეგი: სისტემა ცრუ-უარყოფით მარჟას აჩვენებს. ცნობილი მომწოდებლები:
   - **ELIZI ჯგუფი** (Sobranie/Vinston: cost 72-89 ₾ per pack while sale 7-9 ₾) — 290 row / 15,913 ₾
   - **ჯიდიაი** (Marlboro: იგივე pattern)
   - **კრიკეტ სანთებელა** (cost 30 ₾ per piece while sale 0.25 ₾) — 95 row / 2,709 ₾
   - **ჰიგიენური საფენი ბენგული** (cost 10 ₾ vs sale 0.30 ₾) — 74 row / 2,056 ₾
   - **ზედაზენი 2012 ლუდი** (highest row count — 6,502 row / 14,101 ₾ false-loss)
   - **ეს განამტკიცებს `AGENTS.md`-ის PROTECTED cigarette წესს** — არა მხოლოდ მარჟისთვის. ცალკე workflow აშკარად საჭიროა (POS cost-entry validation, ან known packaging-factor table per supplier+category).

**2. PRODUCTS table ფრაგმენტაცია** (Detectors #20/#21) — **1,299 barcode** ერთდროულად ფიქსირდება ორივე მაღაზიის "უარყოფით" სიაში; **252 dual-store P_ID ფრაგმენტი**. იგივე ფიზიკური barcode სხვადასხვა P_ID-ს ეძახიან per-store. შედეგი: receipt ერთ P_ID-ს მიენიჭება, sale მეორეს, აგრეგატი არასწორი.

**3. ობოლი მომწოდებლები** (Detector #20) — **3,046 product** (~24% სრული catalog-ის) PRODUCTS ცხრილში default supplier-ის გარეშე (`P_DAFAULTSUPPLIER` ცარიელი). 4-წლიანი revenue 231K ₾. ბევრს რეალურად აქვს მომწოდებელი rs.ge-ზე, უბრალოდ PRODUCTS-ში ცარიელადაა.

**Phase B გადაწყვეტილება:** **ვაჩერებთ #25-ზე**. ❌ არ ვაშენებთ ცალკე ტაბებს — სამივე detector (#20/#21/#25) იმავე ფესვის გამო ცრუ-დადებითს იჭერს, ცალ-ცალკე ფილტრების კასკადი ცხადობას არ მოცემს. ✅ ჯერ data quality unified sprint (იხ. §3.4 ქვემოთ), მერე detector-ების ხელახლა აშენება უფრო ცხადი ნიადაგზე.

**6 detector ცხრილში გადადგმული** (Phase A-დან, არ შემოწმდა — ხელმისაწვდომია მომავალი sprint-ისთვის post-cleanup):
- #23 — ერთი პროდუქტი, რამდენიმე barcode (overlap with PRODUCTS cleanup)
- #24 — duplicate ფაქტურის ნომერი (rs.ge same zed_base, multiple active rows)
- #26 — ფასის უცაბედი ცვლილება (>30% jump per-product per-month)
- #28 — 0 ფასი ან 0 რაოდენობა per-line
- #32 — დაბრუნების შებრუნებული თარიღი (GACERA date < GET date)
- #34 — ერთი თანხა, ორი მომწოდებელი (split fraud, წარმ. 1% ლიმიტის გვერდის ავლა)

### 1b. ღამე-ადრე — cleanup + MegaPlus layout migration (`61ffe93` + `e8dc73f`)

**🧹 `61ffe93` chore(cleanup): trim CONTEXT_HANDOFF + remove obsolete archives + scratch artifacts**

- CONTEXT_HANDOFF.md — 110 KB / 576 ხაზი → **12 KB / 88 ხაზი**; სრული ისტორია არქივში გადავიდა (`HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-04_2026-05-02.md`).
- HANDOFF_ARCHIVE — 18 ფაილი წაიშალა: 3 superseded planning doc + 15 pre-MASTER_PLAN preview. HANDOFF.md-ის pointer block განახლდა.
- 47 `_scratch_*.py / .json` root-ში წაიშალა · `__pycache__` წაიშალა.
- **`_to_delete_2026-04-29\` ფოლდერი parent-ში permanent წაიშალა** (994 MB / 16,021 ფაილი) — dashboard ცოცხალი დარჩა, disk free 259 GB.

**🟢 `e8dc73f` feat(megaplus): discover backup folders under მეგაპლიუსის არქიტექტურა layout**

- User-მა PLUS_*.zip backup-ები ძველი `მეგა პლუს backup*` sibling ფოლდერებიდან ახალ `Financial_Analysis/მეგაპლიუსის არქიტექტურა/<store>/` სტრუქტურაში გადააწყო.
- **Fix**: `megaplus_backup._discover_watch_folders` ახლა ორივე layout-ს პოულობს (legacy glob + ახალი arch parent + PLUS_*.zip presence check). `generate_dashboard_data.py` inline glob შეიცვალა helper-ის import-ით.
- Pipeline run end-to-end: 18.6 წთ / 0 errors / 0 warnings. data.json 106 MB.
- **Live numbers**: დვაბზუ 282 supplier / 2,229,889 ₾ rev / 12.34% margin; ოზურგეთი 308 supplier / 2,631,008 ₾ rev / 12.17% margin. ჯამი 4.86 მლნ ₾ rev / 595K ₾ profit / 8,456 პროდუქტი / 37 თვე.
- **ხვალინდელი backup**: PLUS_*_MEGA_20260503.zip ჩავარდნისთანავე pipeline ავტომატურად აიღებს.

---

## 2. დღის შუა + საღამოს session-ი (2026-05-03 afternoon + evening — research + rs.ge admin setup)

**Scope:** research-only session, **არც code change, არც commit, არც push.** Phase 1 (a) PRODUCTS fragmentation deliverable-ის source-first re-derivation + Type A subtype split + pipeline aggregation trace + supplier_profitability false-alarm diagnostic. 2 preview ფაილი დაიწერა, არც ერთი commit-ში არ შესულა.

### 2a. Phase 1 (a) PRODUCTS fragmentation — CLOSED as phantom

- გუშინდელი chat-ის anchor numbers (**1,299 / 252**) **არ გადარჩა** fresh source-first re-derivation-ს — გუშინდელი exact SQL ფაილზე არ შენახულა (cleanup-ში წაიშალა, §1a documents), მხოლოდ chat-ში დარჩა
- რეალური fragmentation (TRIMMED for trailing whitespace): **2,210 union dual-store barcode** (intra-store P_BARCODE → multiple P_ID), **1,190 ორივე მაღაზიაში ერთდროულად**
- Subtype split (1,190-დან): **TYPING_DUP 12** (~3,325 ₾, real cosmetic damage) + **SKU_VARIANT 33** (~20,097 ₾ revenue but pipeline handles correctly per-P_ID — false damage) + **BORDERLINE 4** (~4,731 ₾) + Type B 769 (catalog noise, **0.80 ₾ active in 12 months** — virtually dead)
- Pipeline aggregation traced ცოცხალ კოდში:
  - **Per-P_ID** at source rollup: `dashboard_pipeline/megaplus_backup.py:417-418` — `GROUP BY p.P_ID, p.P_CODE, p.P_BARCODE, p.P_NAME, p.P_UNIT, p.P_GROUP, ...`
  - **Per-barcode** at retail_sales cross-store merge: `dashboard_pipeline/retail_sales.py:451-462` — `key = barcode or code or pid_*`
  - **Cosmetic name-pick only** (line 461-465 `setdefault` never updates name; first-encountered variant wins display)
  - **Sums correct linearly** (lines 478-482 — revenue/cost/profit/qty)
  - **`object_totals` preserves per-store-per-P_ID granularity** (lines 484-492 — multi-entry per store)
- ფინალური fix scope: **~3,325 ₾ TYPING_DUP cosmetic merge**, low priority, შეიძლება existing category_anomalies tab pattern-ით ჩავახვიოთ მისი შემდეგი sprint-ის დროს

### 2b. supplier_profitability "absent" surprise finding — FALSE ALARM

- §12-ში მისრიდი: top-level `data.json["supplier_profitability"]` key-ი ვეძებდი → ვერ ვიპოვე → claim "section არ ცოცხლდება data.json-ში"
- რეალობა: ცოცხალი მონაცემი **nested location-ში** — `imported_products.suppliers[*].profitability` (**220/220 supplier**) + `imported_products.profitability_summary` (overall: **4.86M ₾ cost / 300K ₾ profit / 13.86% margin / 64.88% coverage**)
- Active usage: `rs-dashboard/src/SupplierModal.jsx:405-740+` — UI არ არის broken, არ არის regression, არ არის stale
- Pattern intentional ორიგინალური wire-up-დან (commit `8455486`, **2026-04-26**) — never was top-level key. Verified via git blame `generate_dashboard_data.py:1849-1857` და `git log -S 'data["supplier_profitability"]'` (empty result)

### 2c. Two preview files written this session (no commit)

- `HANDOFF_ARCHIVE/PREVIEWS/PRODUCTS_FRAGMENTATION_2026-05-03.md` — **1,348 ხაზი**, §4–§12 (definition + count + Type A/B/Ambig + 12mo activity + Type A drill-down + subtype split + pipeline trace clarification)
- `HANDOFF_ARCHIVE/PREVIEWS/SUPPLIER_PROFITABILITY_ABSENCE_2026-05-03.md` — **247 ხაზი**, diagnostic only

### 2d. Lesson logged

როცა Claude (terminal) ანონსირებს „surprise out-of-scope finding" — **ერთი fresh query-თ verify-ი მანამდე სანამ actionable-ად მოვექცე**. დღევანდელი supplier_profitability detour ~30 წთ false alarm იყო, რადგან misread fact-ად გადავაქციე და ცალკე diagnostic-ზე ენერგია წავიდა.

### 2e. Open for next session (priority order)

1. **Phase 1 (b) PRODUCTS orphans** — გუშინდელი chat-ის claim **3,046 product / 231K ₾** **NOT verified in source**. შემდეგი session-ი source-first scratch-დან უნდა derive-ს, **არა გუშინდელი ციფრს დაუბრუნდეს** (per Phase 1 (a) lesson — anchor numbers from chat are unverified)
2. **Phase 1 (c) packaging-unit cost confusion** — გუშინდელი **95,682 ₾** claim same caveat. ELIZI/ჯიდიაი/სიგარეტი/სანთებელა/საფენი/ლუდი pattern — fresh source-first re-derivation needed
3. **TYPING_DUP cosmetic merge** (~3,325 ₾, 12 barcode) — low priority, შეიძლება existing `category_anomalies` tab pattern-ით ჩავახვიოთ category_anomalies-ის შემდეგი sprint-ის დროს
4. **Type B catalog cleanup** (769 dormant SKUs, 0.80 ₾ active in 12 months) — preventive only (zero current financial signal), ცალკე sprint, MegaPlus-side POS uniqueness-check workflow

### 2f. Pending push state (2026-05-03 afternoon)

- **3 local-only commits** (origin/main-დან 3 ahead): `61ffe93` (cleanup) + `e8dc73f` (MegaPlus layout migration) + `aef42c9` (yesterday's handoff close from morning session)
- ⚠️ Note: მომხმარებლის დღის initial assumption-ში 2 commit იყო ნახსენები; მე-3 (`aef42c9`) დაემატა გუშინდელი მორნინგ session-ის handoff close-ით — ჯერ ისევ local
- `CONTEXT_HANDOFF.md` modified (today's update — uncommitted)
- 2 ახალი preview ფაილი untracked (`HANDOFF_ARCHIVE/PREVIEWS/PRODUCTS_FRAGMENTATION_2026-05-03.md` + `SUPPLIER_PROFITABILITY_ABSENCE_2026-05-03.md`)
- 1 untracked folder: `Financial_Analysis/მეგაპლიუსის არქიტექტურა/` (MegaPlus backup folder structure — see §1b)
- **Push არ მოხდა — user-ის ნება**

### 2g. საღამო — rs.ge ქვე-ანგარიშის შექმნა (DONE — Stage 3 unblocker)

**ღია სამუშაო closed:** rs.ge ქვე-ანგარიშის შექმნა — **DONE**.

- შეიქმნა sub-user **`dashboard_api`** კომპანიის **400333858** ქვეშ
- პირადი ნომერი: **62005030272** (ა. კ., ბუღალტერი)
- მხოლოდ წაკითხვის უფლებები: ზედნადები / ფაქტურა (მიღებული + გაცემული) / ნდობით აღჭურვილი პირები / კონტრაგენტი / ზოგადი ინფორმაცია (18 ქვე-ერთეული — დეკლარაციები, სალარო, ბრუნვა, სამართალდარღვევები, etc.)
- შესვლა გადამოწმებული: `dashboard_api` + ცალკე პაროლი (განსხვავებული მთავარი 400333858 ანგარიშის პაროლისგან)
- **Login format**: `dashboard_api:400333858` (colon-separated, single auth string — rs.ge ცნობს sub-user-ს ერთიანი string-ით)
- პაროლი user-თან ლოკალურად — **არც chat-ში გადაცემული, არც repo-ში** (Stage 3 implementation-ში env var ან runtime prompt გამოვიყენებთ)

**შემდეგი ნაბიჯი — Stage 3 START:**
1. rs.ge SOAP web-service endpoint URL + WSDL კვლევა
2. ერთი minimal test ფაილი `rs_test.py` (project root-ზე ან `dashboard_pipeline/`-ში)
3. ერთი ცოცხალი ზედნადების fetch API-დან → შედარება eservices.rs.ge UI-თან
4. თუ ემთხვევა → კონექტორის სრული დიზაინი

**User context:** web chat-ში დღეს ბევრი UI guidance მოხდა (4 rs.ge UI guess corrected). ტერმინალურ Claude-ს უფრო ცხადი თავი ექნება Stage 3-ში — assumptions რეალურ API response-ით გადავამოწმდება, არა UI guess-ით.

**User preference reminder:** plain ქართული, არა-პროგრამისტი, 3-ფენიანი feature explanation (რას აკეთებს + რატომ გჭირდება + რა შედეგი იქნება), სცენარს თვითონ მართავს.

### 2h. Stage 3 — PROOFED (2026-05-04 ღამე-ადრე, terminal Claude)

**🎉 STATUS: STAGE 3 PROOFED — production connector design ready to start.**

**Verified facts (source-1:1, official rs.ge WSDL + live API call + UI cross-check):**

| რა | მნიშვნელობა |
|---|---|
| **Endpoint URL** | `https://services.rs.ge/WayBillService/WayBillService.asmx` |
| **WSDL** | `https://services.rs.ge/WayBillService/WayBillService.asmx?WSDL` |
| **Auth scheme** | `su` (service username) + `sp` (service password) — every authenticated method |
| **Auth verification method** | `chek_service_user(su, sp)` — returns `true`/`false` + `un_id` + `s_user_id` |
| **Auth credentials** | `su=dashboard_api:400333858` (colon-separated, single string), `sp=<password>` — UI sub-user **works as SOAP service-user** (no separate `create_service_user` registration needed) |
| **Read methods (read-only sub-user)** | `get_waybill(id)` · `get_waybill_by_number(number)` · `get_waybills(filters)` · `get_buyer_waybills(filters)` |
| **Date format** | ISO 8601 — `2026-04-04T08:46:22` |
| **Empty params handling** | Skip empty/None values from envelope entirely — .NET parser rejects empty string for typed (DateTime/decimal) fields with SOAP fault `"The string '' is not a valid AllXsd value"` |
| **Method choice for retail dashboard** | **`get_buyer_waybills`** (incoming receipts from suppliers) — not `get_waybills` (outgoing, retail does not emit waybills, returns STATUS -1064 empty) |
| **Live data sample (30 days, 2026-04-04 → 2026-05-04)** | 531 waybills · 170,677 ₾ total · 70% closed (STATUS=2) / 29% active (STATUS=1) / 1% deactivated (STATUS=-2) |
| **Top sellers by count** | ვასაძის პური (121) · იფქლი (100) · ზახარ (34) · კოკა-კოლა გურია (18) · ჯიდიაი (17) · შრომა-2023 (16) · ზედაზენი (15) · ლაქტალის (15) |
| **Top sellers by amount** | ELIZI ჯგუფი dominates top 5 (4 of top 5: 4,754 + 4,665 + 3,544 + 2,517 ₾) — **confirms Phase B finding** (2026-05-03 ღამე): packaging-unit cost confusion driver |

**Spot-check (AGENTS.md proof gate, 9/9 checkpoints — UI verified by user via main 400333858 account):**

Sample waybill `0969812911/3` (2026-04-04, შპს იფქლი → შპს ჯეო ფუდთაიმი, 54 ₾):
- ✓ ზედნადების ნომერი · ✓ გაცემის თარიღი · ✓ გამყიდველი (TIN+name) · ✓ მყიდველი (TIN+name) · ✓ გასაგზავნი მისამართი (სუფსა) · ✓ მიმღები მისამართი (ოზურგეთი, სოფ, ოზურგეთი) · ✓ მძღოლი (როლანდი ანდღულაძე) · ✓ ავტომანქანის ნომერი (WW857GW) · ✓ ჯამური თანხა (54 ₾)

**🆕 Non-obvious finding — UI/SOAP permission asymmetry:**

`dashboard_api` sub-user-ი **UI-ში "ზედნადები" tab ვერ ხსნის** (UI restriction enforced even though ცხადი UI permission-ი მინიჭებულია), **მაგრამ SOAP-ით სრულ read-access აქვს**. რეალური ცოცხალი 531 waybills მისი credentials-ით ცოცხლა fetch-დება. ე.ი. **rs.ge-ის UI permission model ≠ SOAP permission model**:
- **UI**: more restrictive (sub-user UI access partial / შეიძლება buggy)
- **SOAP**: full read on configured sections per UI permission grant

**Implication for connector design**: არ გვადარდებს UI-ის სცენარი. Production pipeline SOAP-ი იქნება, არა UI scraping. Sub-user-ის UI access incidental ფაქტია.

**Files written this session (test artifacts, all `_scratch_*` gitignored):**
- `_scratch_rs_test.py` — minimal SOAP fetch test (production refactor candidate for Sprint A — clean up to `dashboard_pipeline/rs_waybill_connector.py`)
- `_scratch_rs_ip_response.xml` (378 bytes) — what_is_my_ip diagnostic
- `_scratch_rs_auth_response.xml` — chek_service_user response
- `_scratch_rs_seller_waybills.xml` (462 bytes) — empty (retail does not emit) — diagnostic only
- `_scratch_rs_buyer_waybills.xml` (485,178 bytes) — **live 531 waybills, contains TINs/sellers/drivers/addresses/amounts** — privacy: gitignored, plan to delete after connector design Sprint A

**Open for next session — Sprint A connector design (priority 1):**

1. **Architecture decision**: standalone `dashboard_pipeline/rs_waybill_connector.py` module vs integrate into existing `rs_waybill_loader.py` (current logic loads from manual XLS exports — connector swaps source from XLS → live SOAP)
2. **Credentials handling**: env var (`RS_USER` + `RS_PASS`) + `.env` file gitignored, OR runtime prompt cached for service lifetime
3. **Pagination/incremental sync**: 531 waybills/30 days = ~17/day; safe to do daily full-month rolling pull, or incremental by `last_update_date_s/e` (`get_waybills_v1` method available)
4. **Schema mapping**: 531 waybills XML → flatten to canonical CSV/parquet matching existing `rs_waybill_loader.py` output schema
5. **Goods list / line items**: `get_buyer_waybills` returns `<GOODS_LIST>` block per-waybill (not yet inspected this session — TBD verify in Sprint A start)
6. **Adjustment chain**: `<PAR_ID>` parent waybill ID + `get_adjusted_waybills(id)` → corrected waybill chain (need policy: keep latest only or full audit trail)
7. **Service user IP whitelist**: rs.ge sometimes binds service-user to IP (dimakura doc); sub-user `dashboard_api` did not require IP — confirmed working from sandbox IP `212.58.103.103` (= user-machine IP via shared egress) — production NSSM service IP TBD, test before deploying

**Cleanup pending after Sprint A complete:**
- 5 `_scratch_rs_*` files delete (test artifacts + 485 KB live financial data)
- Replace manual XLS download workflow → automated daily SOAP pull

**არცერთი code change production-ში, არცერთი commit, არცერთი push** — only test artifacts under `_scratch_*` (gitignored).

### 2i. Counterparty TIN lookup — PROOFED (2026-05-04 ღამე-ადრე, terminal Claude)

**ცხადი**: PRODUCTS orphan resolution path unblocked for LLC suppliers (the bulk of 3,046 / 24% catalog orphans). Individual entrepreneur TINs need separate strategy.

**Test (Step 4 in `_scratch_rs_test.py`, 5-TIN probe):**

| TIN | Type | get_name_from_tin | is_vat_payer_tin | Verdict |
|---|---|---|---|---|
| 200179118 | LLC | `'შპს იფქლი'` ✓ exact | `'true'` | ✅ |
| 237077961 | LLC | `'შპს ვასაძის პური'` ✓ exact | `'true'` | ✅ |
| 33001062062 | Individual | `'კ. ა.'` (initials only) | `'true'` | ⚠️ privacy-redacted |
| 405152953 | LLC | `'შპს კოკა-კოლა გურია'` ✓ exact | `'true'` | ✅ |
| 999999999 | Unknown (control) | `'null'` | `'false'` | ✅ correct fallback |

**🆕 Non-obvious finding — rs.ge privacy-redacts individual entrepreneur names:**
- LLC (იურიდიული პირი): full registered name returned
- Individual (ფიზიკური პირი, 11-digit personal ID): only **initials** returned (`კ. ა.` not `კახაბერ აროშიძე`)
- Unknown: `'null'` string (not XML nil) + VAT-payer `false`

**Implication for PRODUCTS orphan resolution (Phase A finding 3,046 orphans / 231K ₾):**
- LLC orphans → auto-resolved via `get_name_from_tin` + manual review (~majority of cases)
- Individual orphans → `get_name_from_tin` insufficient; need TIN-based join against in-house records (because rs.ge returns initials only). Acceptable, just different strategy
- Sprint design: orphan-resolver script reads PRODUCTS where `P_DAFAULTSUPPLIER` is empty → groups receipts by TIN from waybills → calls `get_name_from_tin` for unknowns → writes back. Individual TIN cases flagged for manual review.

**Cumulative scratch artifacts (all `_scratch_*` gitignored):**
- `_scratch_rs_test.py` (~150 lines, now 4-step: ip + auth + waybills + counterparty) — Sprint A starting point
- `_scratch_rs_ip_response.xml` (378 bytes)
- `_scratch_rs_auth_response.xml`
- `_scratch_rs_seller_waybills.xml` (462 bytes, empty — diagnostic)
- `_scratch_rs_buyer_waybills.xml` (485 KB, **live 531 waybills with TINs/sellers/drivers/addresses/amounts**)

**Open for next session — priority refresh after counterparty PROOFED:**
1. **Sprint A — rs.ge connector implementation** (replace manual XLS workflow with automated SOAP pull) — primary
2. **Sprint A optional addon — orphan resolver utility** — runs once after connector, attempts to fill 3,046 PRODUCTS orphans via `get_name_from_tin`. Estimated ~1 day. ROI: 24% catalog cleanup
3. **e-invoices SOAP service** (different endpoint `webserv.rs.ge/specinvoices`) — VAT cross-source detection (Phase A backbone) — Sprint B
4. **Cash register `სალარო` cross-check** — POS upload reconciliation — Sprint C
5. **Goods list per-waybill drill-down** (`get_waybill_goods_list`) — bonus, no immediate dashboard need

---

## 3. ჯერ-ჯერობით წინა session-ი (2026-05-02 evening)

**`e5ee7ea` feat(waybill-reconciliation): wrong-store category** — ზედნადებების შედარებაში ცალკე გამოჩნდა „🔄 არასწორი მაღაზია" ჯგუფი (4-წლიან 3,978 active rs.ge-ზე: 28 wrong_store / ₾13,237). Spot-check-ით 26 false-positive class დაიჭირა — fix `ACTIVE_STORE_KEYWORDS["1329"]` `"დვაბზუ"` → prefix `"დვაბზ"`.

**`6d45dd7` feat(pwa): soft update banner** — საიტი მუშაობის შუაში თვითონ აღარ რეფრეშდება. ახლა მარცხნივ-ქვემოთ მწვანე ბანერი „განახლება" ღილაკით. **One-time activation cost**: ძველი sw.js-ით გახსნილი tab-ებს ერთხელ ავტო-რეფრეში მოუვათ, მერე ბანერი ცოცხლდება.

---

## 4. შემდეგი session-ის OPEN list (priority order)

1. **🟢 MegaPlus cleanup workflow გაგრძელდება** — user აქტიურად იყენებს ტაბს, pattern-ი ცოცხლდება: „MegaPlus-ში ერთი batch ჩავასწორებ, ხვალ PLUS_*.zip backup ჩამოვწერ, pipeline ცვლილებას აიღებს, რიგი ცხრილიდან გაქრება". **არაპროაქტიულად კონკრეტულ რიგებზე ხელი არ გავიწიოთ**; user თვითონ გამოიტანს. როცა გამოიტანს — D&L / Partnyori / Lactalis-ისებური line-by-line drill-down (GET vs rs.ge xls diff, plain-ქართული explanation).
2. **🟢 Browser smoke-check pending** — `6d45dd7` (PWA banner) GitHub-ზეა მაგრამ user-ს ჯერ არ გადაუხედავს. პირველი F5-ი ერთხელ ავტო-რეფრეშს გამოიწვევს (ძველი sw.js cache-ში); მერე ბანერი ცოცხლდება. პრობლემის შემთხვევაში: dist bundle hash უნდა იყოს `index-hfmLnxUb.js`.
3. **🟢 ცვლილებების push origin/main-ზე** — `61ffe93` + `e8dc73f` ჯერ origin-ზე არ აიტვირთა (local main 2 ahead). user-მა „push" როცა მოითხოვოს — ერთად აიგზავნება.
4. **🚨 Data Quality Unified Sprint — DECISION READY (post-Phase-B)** — Phase B-ის (2026-05-03) მთავარი დასკვნა: **3 detector ერთი ფესვს ეჯახება**. ფუნდამენტი 3 ნაწილია:
   - **(a) PRODUCTS orphan resolution** — 3,046 product (~24% catalog) / 231K ₾ revenue / `P_DAFAULTSUPPLIER` ცარიელი. ბევრს რეალურად აქვს მომწოდებელი rs.ge-ზე.
   - **(b) P_ID dual-store fragmentation** — 252 barcode / per-store სხვადასხვა P_ID. Receipt ერთს, sale მეორეს, აგრეგატი ფრაგმენტული. Manual mapping ან automated barcode-based unification.
   - **(c) Packaging-unit cost-entry workflow** — POS-ში cost ბლოკის ფასით იწერება, ცალით იყიდება. სისტემური ELIZI/ჯიდიაი/სიგარეტი/სანთებელა/საფენი/ლუდი მიმართულებით (იხ. §1a finding #1). საჭიროა: cost validation rule, ან known packaging-factor table per supplier+category, ან POS workflow change.
   - **Blocks**: detectors #19, #20, #21, #22, #24, #26 — ყველა საჭიროებს ცხად per-product per-store მონაცემს.
   - **Path forward**: user-ის გადაწყვეტილება — (1) data quality cleanup ერთიანი sprint-ით (1-2 კვირა, ფესვი იხსნება ერთხელ), ან (2) #25-ის ფილტრიანი detector-ი ცალკე (~1 sprint, partial signal), ან (3) სხვა მიმართულება.
5. **🟢 Carryover (არა-blocking)**:
   - RS_CODES-based product matching (189,015 rs.ge↔Megaplus mappings MegaPlus DB-ში — name-fuzzy-ის ჩანაცვლება exact JOIN-ით; ~1 sprint). შესაძლოა (a)/(b) cleanup-ის ფარგლებში გადაიჭრას.
   - Auto-sync OneDrive↔C:\ — drift-ი მეორდება; post-commit/post-merge hook ან scheduled task.
   - `retail_sales_top_products` SQLite export bug (`dashboard_pipeline/export_sqlite.py:111` reads `top_products`, schema-ში `top_products_by_revenue` / `_by_profit`).
   - ოზურგეთი DB 234 orders dated 2009 (0.026% / 661 ₾, optional date filter) — Phase B-ში დადასტურდა (#21-ში 117 product first_neg_year=2009).
   - rs.ge automation deferred — user-მა manual download აირჩია.
6. **🟢 Category-anomalies UI follow-ups (deferred)** — deep-link / severity scoring / Excel export — **მხოლოდ user-ის მოთხოვნით**.

---

## 5. Verified facts (cross-check ვიდრე action)

| მაჩვენებელი | მნიშვნელობა |
|---|---|
| pytest (key suites) | **39/39** waybill_reconciliation + 50/50 supplier_profitability + retail_sales_revenue_formula |
| Tool surface | 29 (incl. `data_quality_guard`) |
| Dashboard tabs | 16 (waybill_reconciliation tab-ში "🔄 არასწორი მაღაზია" group) |
| `data.json` | **106 MB** (post-MegaPlus-rediscovery, 2026-05-03 02:36) |
| Local branch | `main` 2 ahead of `origin/main` (`61ffe93` + `e8dc73f` — push pending) |
| MegaPlus DB integration | LIVE — 53 tables / 282+308 suppliers across 2 stores / 720K active orders / 2024-03 → 2026-04 |
| MegaPlus watch folder layout | `Financial_Analysis/მეგაპლიუსის არქიტექტურა/{დვაბზუ,ოზურგეთი}/` (legacy `მეგა პლუს backup*` glob still supported) |
| **Phase B exploratory data (2026-05-03)** | POS active rows 1,552,457 (4yr); with-cost 89.1%; **negative-margin 4.13% / 95,682 ₾ loss** (dom. by packaging-unit confusion); negative-inventory 2,408 product / 149K unit deficit; unrecorded products 6,656 / 572K ₾; PRODUCTS orphans 3,046 / 231K ₾; dual-store P_ID fragments 252 |
| MCP servers | gitnexus · playwright · filesystem · github · sqlite · sequential-thinking · memory · brave-search · time · fetch · context7 |

---

## 6. Active open work

| # | task | size | risk | რატომ |
|---|---|---|---|---|
| **🟡 0a CODE COMPLETE — smoke-test pending** | **Sprint C alias UI** browser smoke-test — endpoint LIVE post-restart, 8 tests green, just need user-side click. Steps: (1) `_vite-dev.bat` → http://127.0.0.1:5173, (2) მომწოდებლები ტაბი → ვასაძის პური → modal → ალიასის კანდიდატები, (3) „✓ დადასტურდი ალიასი" → toast + product_aliases.json write + pipeline rerun. | ~30 წთ | LOW |
| **🚨 0c — DECISION READY** | **MAX vendor-tag file integration** (ELIZI / შრომა / etc. KPI gaps) — file landed at `Financial_Analysis/მეგა პლუს/კომპანიების გაყიდვა მოგება.xls` (45 KB, 116 suppliers, **დვაბზუ store only**). 3 paths: **(A)** read-only side-by-side (~1 session, low risk); **(B)** soft replacement when MAX matches by tax_id (~2 sessions, medium); **(C)** file loader only (~30 წთ, low value alone). User picks A/B/C. ოზურგეთი analog file ⏳. | A=1 / B=2 / C=0.5 sessions | **HIGH** |
| **🚧 CAL** | calendar heatmap supplier modal-ში — Step 3 (spot-check) ღიაა. `supplier.profitability.daily_breakdown[]` sparse aggregation საჭიროა. | ~1 session | LOW |
| **🆕 0f Sprint D candidate** | **Cross-source revenue gap** — MAX vendor-tag vs RS waybill (ვასაძე@დვაბზუ Q1 2026: pipeline 3,888 ₾ vs MAX 11,477 ₾ ground-truth, 7,589 ₾ gap). Sprint C alias UI არ წყვეტს. Investigation paths: (1) MAX-ის per-supplier sales report direct export, (2) MAX-vendor-tag column retail_sales pipeline-ში, (3) KPI banner caveat. | 2-3 investigation + 1-2 impl | MEDIUM |
| 1 | Supplier Profitability Sprint C UI extensions — render `ambiguous_preview` (46 invisible candidates) + bulk-confirm + DELETE endpoint | ~1 session | LOW |
| 2 | AI tool wrapper `analyze_supplier_profitability(tax_id)` (TOOL_SCHEMAS 29 → 30) | ~1 session | LOW |
| **🧹 1-week-pending** | OneDrive `financial-dashboard\` copy retire (NSSM service mirror მხოლოდ C:\\-ზე; OneDrive working-tree-ში divergence იზრდება) | ~30-45 წთ mini-sprint | MEDIUM |
| 🛡 0b | Safety net follow-ups (Pandera ანალიზის შემდეგ) — vulture dead-code, jsonschema config, golden snapshot, reconcile_suppliers spread, Pandera RS.ge CSV reader | 1-2 sessions | LOW |

---

## 7. Canonical paths & services (do-not-touch)

⚠️ **Source ფაილების canonical path — symlink სტრუქტურა (2026-04-29 verified):**
- **pipeline view**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\financial-dashboard\Financial_Analysis\`
  - 15 JSON config (real, canonical) — `cash_outflow_journal.csv`, `product_aliases.json`, etc.
  - 5 symlink target ფოლდერი → `..\Financial_Analysis\` (parent):
    - `ბოგ ბანკი ამონაწერი`, `გაყიდული პროდუქტები სოფ დვაბზუ`, `გაყიდული პროდუქტები სოფ ოზურგეთი`, `თბს ბანკი ამონაწერი`, `რს ზედნადები`
  - **`მეგაპლიუსის არქიტექტურა/`** — MegaPlus daily backup ZIPs (per-store sub-folder); pipeline auto-discovers.
  - ⚠️ **`შემოტანილი პროდუქცია\` ფოლდერი** — pipeline 0 errors-ით სრულდება, მაგრამ folder absent verified (2026-04-30 evening). შემდეგ session-ში გადასამოწმებელი — `dashboard_pipeline/imported_products.py` რომელ path-ს კითხულობს და რა ხდება როცა აკლია.
- **parent's `Financial_Analysis\`**: 5 ცოცხალი data ფოლდერი (symlink target — **NEVER touch**); top-level JSON-ები ძველად parent-ში იყო, ახლა გასუფთავდა (`_to_delete_2026-04-29\` permanent წაშლილია 2026-05-03-ზე).

ცხრილი:
- **Workspace root**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი`
- **Project**: `...\financial-dashboard`
- **Python interpreter**: `...\AI აგენტი\venv\Scripts\python.exe` (parent venv only — NEVER `.venv` / project-local / system Python)
- **Backend**: Windows Service `FinancialDashboardBackend` (NSSM, auto-start + auto-restart, `AI_ENABLE_THINKING=true` + `PYTHONUTF8=1`)
- **Service control**: `Restart-Service FinancialDashboardBackend` (admin/UAC) · `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit}`
- **⚠️ Service-restart-for-new-code**: prompt module-import time-ზე იტვირთება. Prompt change-ის შემდეგ — `Restart-Service`. Pipeline subprocess-ი ცალკე იქმნება, კოდის ცვლილებას ავტომატურად აიღებს. In-process AI test = `_scratch_dogfood_*.py` pattern (no service)
- **Backend interpreter verification**: `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` (NOT `Get-Process`)
- **SQL Server Express**: `localhost\SQLEXPRESS` (instance), `MEGAPLUS_<storeID>` databases — restore via `megaplus_backup._restore` from PLUS_*.bak

---

## 8. Workspace cleanup status

| რა | status |
|---|---|
| `_to_delete_2026-04-29\` (994 MB / 16,021 ფაილი parent root-დან) | ✅ permanent წაიშალა 2026-05-03 |
| OneDrive `financial-dashboard\` copy | NSSM service mirror მხოლოდ C:\\-ზე; OneDrive working-tree-ი ცოცხალი მაგრამ divergence იზრდება |
| **2026-05-03 cleanup** | 47 `_scratch_*` ფაილი + `__pycache__\` წაიშალა · CONTEXT_HANDOFF.md ისტორია არქივში · 18 obsolete archive ფაილი წაიშალა · MegaPlus discovery layout ახალი |
