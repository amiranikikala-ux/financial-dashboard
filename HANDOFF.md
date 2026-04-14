# HANDOFF

> Updated: 2026-04-14 (session #32)

## ⚡ ახალი სესიის ინსტრუქცია
1. წაიკითხე PLAN.md — დასრულებული ფაზები + შემდეგი ნაბიჯი
2. წაიკითხე ეს ფაილი მთლიანად — არქიტექტურა + ფაილები + Known Issues
3. შეამოწმე ტესტები: `python -m pytest tests/ -q` (უნდა იყოს 125/125)
4. შეამოწმე ბილდი: `cd rs-dashboard && npx vite build` (0 errors)
5. შეამოწმე E2E: `cd rs-dashboard && npx playwright test` (63 pass)
6. ფაზა 1-7 დასრულებულია. პროექტი production-ready.
7. Bundle ანალიზი: `cd rs-dashboard && npm run build:analyze` (opens treemap)
8. ნებისმიერი ცვლილებისას: `impact({target, direction: "upstream"})` GitNexus-ით

## Current Status
- Pipeline works: Excel -> data.json -> FastAPI -> React dashboard
- 11 pipeline modules in dashboard_pipeline/ (all verified)
- 125 unit tests passing (waybill_amounts + supplier_matching + bank_reconciliation)
- 63 E2E tests passing (Playwright: dashboard, navigation, mobile, refresh, errors, export, supplier-modal)
- 4 audit scripts passing (audit_all, full_audit, audit_bog_rs_id, verify_supplier)
- Frontend: 14 tabs, lazy-loaded components, Vite build clean (gzip ~87KB initial)
- API rate limiting: slowapi 60/min per IP on /api/data
- API auth: X-API-Key middleware (optional, env: DASHBOARD_API_KEY)
- CSS organized: 4698-line index.css → 7 files in styles/
- Backend scheduling: APScheduler auto-refresh every 30min + /api/status + /api/refresh
- Export: universal ExportButton on 11/14 tabs (was 4)
- Mobile: bottom nav bar, tab sheet, 44px touch targets, safe area insets
- PWA: manifest.json + Service Worker + PNG icons 192/512 (stale-while-revalidate + network-first API)
- Bundle optimization: manualChunks (vendor-react 190KB, vendor-recharts 432KB), esnext target, app core 17KB

## Session #32 ფაილები
```
rs-dashboard/e2e/export.spec.js               # NEW — 9 tests: ExportButton on 7 tabs (suppliers, analytics, ratios, forecast, budget, working_capital, retail_sales)
rs-dashboard/e2e/supplier-modal.spec.js       # NEW — 16 tests: open/close/content/keyboard/backdrop/truth/imported
rs-dashboard/e2e/helpers/mock-data.js         # UPD — proper supplier fields (ორგანიზაცია, debt, aging), retail_sales structure, imported_supplier_detail
```

## Session #31 ფაილები
```
rs-dashboard/vite.config.js                   # +manualChunks, +esnext target, +visualizer
rs-dashboard/package.json                     # +build:analyze script, +rollup-plugin-visualizer
```

## Session #30 ფაილები
```
rs-dashboard/public/icons/icon-192.png         # NEW — PWA icon 192x192
rs-dashboard/public/icons/icon-512.png         # NEW — PWA icon 512x512
rs-dashboard/scripts/generate-icons.mjs        # NEW — icon generation script (sharp)
rs-dashboard/index.html                        # apple-touch-icon → PNG
```

## Phase 5 ფაილების რუკა (ახალი/შეცვლილი)
```
server.py                                  # +ApiKeyMiddleware, +hmac auth
rs-dashboard/src/lib/api.js                # +withAuthHeaders (X-API-Key)
rs-dashboard/index.html                    # +manifest, +theme-color, +SW registration
rs-dashboard/playwright.config.js          # NEW — Playwright config
rs-dashboard/e2e/dashboard.spec.js         # NEW — 8 tests: load, header, default tab
rs-dashboard/e2e/navigation.spec.js        # NEW — 18 tests: all 14 tabs + hash + groups
rs-dashboard/e2e/mobile.spec.js            # NEW — 7 tests: bottom nav, sheet, overlay
rs-dashboard/e2e/refresh.spec.js           # NEW — 3 tests: button, POST trigger, age
rs-dashboard/e2e/api-error.spec.js         # NEW — 2 tests: error banner, retry
rs-dashboard/e2e/helpers/mock-data.js      # NEW — mock API responses
rs-dashboard/e2e/helpers/api-mock.js       # NEW — route interceptors
rs-dashboard/public/manifest.json          # NEW — PWA web app manifest
rs-dashboard/public/sw.js                  # NEW — Service Worker
rs-dashboard/.env.example                  # NEW — VITE_API_KEY template
rs-dashboard/package.json                  # +@playwright/test, +test:e2e scripts
```

## Phase 4 ფაილების რუკა (ახალი/შეცვლილი)
```
server.py                                  # +/api/status, /api/refresh, APScheduler
requirements.txt                           # +apscheduler>=3.10
rs-dashboard/index.html                    # viewport-fit=cover
rs-dashboard/src/App.jsx                   # +RefreshButton, +MobileNav, +useDataStatus
rs-dashboard/src/lib/exportXlsx.js         # NEW — shared xlsx load + multi-sheet export
rs-dashboard/src/hooks/useDataStatus.js    # NEW — polls /api/status every 15s
rs-dashboard/src/components/RefreshButton.jsx  # NEW — refresh button + data age
rs-dashboard/src/components/ExportButton.jsx   # NEW — reusable Excel export
rs-dashboard/src/components/MobileNav.jsx      # NEW — mobile bottom nav + sheet
rs-dashboard/src/Analytics.jsx             # +ExportButton
rs-dashboard/src/WorkingCapital.jsx        # +ExportButton
rs-dashboard/src/Ratios.jsx                # +ExportButton
rs-dashboard/src/Forecast.jsx              # +ExportButton
rs-dashboard/src/Budget.jsx                # +ExportButton
rs-dashboard/src/RetailSales.jsx           # +ExportButton
rs-dashboard/src/styles/utilities.css      # +refresh button + header-right-controls CSS
rs-dashboard/src/styles/components.css     # +tab-hero .btn-download-xlsx
rs-dashboard/src/styles/responsive.css     # +mobile bottom nav CSS (≤768px)
rs-dashboard/src/styles/base.css           # +touch targets, tap-highlight, text-size-adjust
```

## Session #32 - E2E Tests: Export + Supplier Modal
1. export.spec.js: 9 tests — ExportButton visibility on suppliers, analytics, ratios, forecast, budget, working_capital, retail_sales tabs; CSV button state
2. supplier-modal.spec.js: 16 tests — row click opens modal, supplier name/taxID display, 3 KPIs, payment split, aging, ratio gauge, close (✕/button/Escape/backdrop), second supplier, imported products reference, truth section
3. mock-data.js: suppliers now have ორგანიზაცია/waybills_count/total_effective/bank_paid/payment_scope; retail_sales has overall/by_month/by_object/top_products; added MOCK_IMPORTED_SUPPLIER_DETAIL
4. 63/63 E2E tests pass, 125/125 unit tests, Vite build clean

## Session #31 - Performance Optimization: Bundle Size
1. Analyzed bundle: xlsx (415KB), recharts (375KB), index (199KB) as top chunks
2. Already good: lazy loading on all 15 tabs, dynamic xlsx import
3. manualChunks: separated vendor-react (190KB) and vendor-recharts (432KB)
4. App core chunk: 199KB → 17KB (gzip 5.8KB)
5. Build target: esnext for modern browser optimization
6. Added rollup-plugin-visualizer + `npm run build:analyze` script
7. Initial page load (gzip): ~87KB (react 60KB + app 5.8KB + CSS 13KB + components ~8KB)
8. 125/125 unit tests pass, Vite build clean

## Session #30 - PWA Icons
1. Generated PNG icons (192x192, 512x512) from favicon.svg using sharp
2. apple-touch-icon in index.html updated: SVG → PNG for iOS compatibility
3. Icon generation script: scripts/generate-icons.mjs (reusable)
4. 125/125 unit tests pass, Vite build clean

## Session #29 - Phase 5: E2E Tests, API Auth, PWA
1. Playwright E2E: 38 tests across 5 spec files (dashboard, navigation, mobile, refresh, errors)
2. Mock API layer: mock-data.js + api-mock.js for backend-independent testing
3. API auth: ApiKeyMiddleware in server.py, hmac.compare_digest, public /api/status
4. Frontend auth: withAuthHeaders() in api.js, VITE_API_KEY env var
5. PWA: manifest.json (standalone, theme #863bff), sw.js (stale-while-revalidate assets + network-first API)
6. index.html: manifest link, theme-color, apple-mobile-web-app, SW registration
7. 125/125 unit tests + 38/38 E2E tests pass, Vite build clean

## Session #28 - Phase 4: Scheduling, Export, Mobile
1. Backend: `/api/status` (data freshness) + `/api/refresh` (manual trigger) + APScheduler (30min auto)
2. Frontend: RefreshButton + useDataStatus hook in header, shows pipeline state + data age
3. Shared `lib/exportXlsx.js` + reusable `ExportButton` component
4. Excel export added to: WorkingCapital, Analytics, Ratios, Forecast, Budget, RetailSales (6 tabs)
5. Mobile bottom nav: 4 quick tabs + "more" sheet with all 14 tabs, hidden on desktop
6. Touch: 44px min targets, font-size: 16px inputs (no iOS zoom), viewport-fit=cover, safe-area-inset
7. requirements.txt: apscheduler>=3.10 added
8. 125/125 tests pass, Vite build clean

## Session #27 - Tests, Rate Limiting, CSS Split
1. Added 105 unit tests: test_supplier_matching.py (62) + test_bank_reconciliation.py (43)
2. API rate limiting via slowapi: 60 req/min per IP on /api/data, 120/min global default
3. CSS split: index.css (4698 lines) → 7 files in src/styles/ (base, tables, pages, executive, components, responsive, utilities)
4. requirements.txt updated: fastapi, uvicorn, slowapi added
5. 125/125 tests pass, Vite build clean

## Session #26 - run() RS Processing Split
1. Extracted _read_and_parse_rs (82 lines) — RS Excel reading, column detection, amounts, org aggregation
2. Extracted _process_rs_suppliers (283 lines) — bank reconciliation, supplier enrichment, aging, excel writes
3. Extracted _build_base_meta (58 lines) — deduplicated 29 shared meta keys between empty/filled RS paths
4. run() reduced from ~625 to 211 lines (total: 8 helpers)
5. 20/20 tests pass, Vite build clean

## Session #25 - Build Test + run() Splitting
1. Suppliers.jsx + Waybills.jsx Vite build verified OK
2. Extracted 5 helpers from run(): _load_pipeline_config, _collect_income_bundles, _enrich_meta, _build_analytics, _write_outputs
3. run() reduced from 1024 to ~625 lines (RS processing remains, further split possible)
4. 20/20 tests pass, Vite build clean

## Architecture
`
Excel (Financial_Analysis/) -> generate_dashboard_data.py -> data.json + tab-data/*.json
server.py (FastAPI :8000) -> GET /api/data?tab=...
rs-dashboard/ (React+Vite :5173) -> browser
`

## Pipeline Modules (dashboard_pipeline/)
constants, file_utils, config_loaders, bank_unmatched, bank_income,
manual_payments, analytics_builders, supplier_matching, bank_reconciliation,
imported_products, retail_sales + api_contracts, config_validation,
sources, truth_boundary, export_artifacts, logging_config, waybill_amounts

## Key Files
- generate_dashboard_data.py - orchestrator (imports + run())
- server.py - FastAPI, single endpoint /api/data
- rs-dashboard/src/App.jsx - main React (357 lines)
- Cashflow.jsx, Suppliers.jsx, Waybills.jsx - extracted components

## Known Issues
- _verify_all_audit.py: 1 FAIL - BOG ID 415117929 not in RS (data quality, not code bug)
- run() function is ~211 lines (well-structured with 8 helpers)
- APScheduler default 30min (env: DASHBOARD_REFRESH_MINUTES)
- PWA icons: SVG + PNG 192/512 generated ✓
- Bundle: vendor-react 190KB, vendor-recharts 432KB, xlsx 425KB (all deferred except react)

## Next Steps (priority order)
1. Deploy to production

## Run
`
python generate_dashboard_data.py   # 3-15 min
python server.py                     # :8000
cd rs-dashboard && npm run dev       # :5173
# Or: Run_Dashboard.bat
`
