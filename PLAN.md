# გეგმა

## სტეკი
Python (pandas) + FastAPI (`server.py`) | React 19 + Vite (`rs-dashboard/`) | Excel → `data.json` → UI

## დასრულებული: ფაზა 1-2
აუდიტი, logging, DRY refactor, dead code cleanup, Cashflow.jsx გამოტანა.

## ფაზა 3: კოდის ხარისხი (დასრულებული)
- [x] `App.jsx` → Suppliers.jsx, Waybills.jsx build ტესტი OK
- [x] `run()` — 5 helper ამოღებული (1024→625 ხაზი)
- [x] `run()` — RS processing: +3 helper (625→211 ხაზი, ჯამი 8 helper)
- [x] CSS ორგანიზება: 4698 ხაზი → 7 ფაილი `src/styles/`-ში
- [x] 105 ახალი unit ტესტი (supplier_matching + bank_reconciliation)
- [x] API rate limiting (slowapi 60/min per IP)

## ფაზა 4: ახალი ფუნქციონალი (დასრულებული)
- [x] APScheduler 30წთ auto-refresh + /api/status + /api/refresh
- [x] RefreshButton + useDataStatus hook header-ში
- [x] ExportButton კომპონენტი + exportXlsx.js utility (11/14 ტაბზე)
- [x] მობილური bottom nav (4 quick tabs + "სხვა" sheet)
- [x] Touch: 44px targets, iOS zoom fix, viewport-fit=cover, safe-area

## ფაზა 5: ტესტირება და deploy (დასრულებული)
- [x] E2E ტესტები (Playwright) — 38 ტესტი 5 spec ფაილში
- [x] API auth — ApiKeyMiddleware (DASHBOARD_API_KEY env), X-API-Key header
- [x] PWA offline — manifest.json + sw.js (stale-while-revalidate + network-first API)

## შემდეგი (არასავალდებულო)
- [x] PNG იკონები PWA-სთვის (192x192, 512x512) — session #30
- [ ] Performance optimization (bundle size ანალიზი)
- [ ] Production deploy
- [ ] დამატებითი E2E ტესტები (export, supplier modal)

## წესი: სესიის ბოლოს HANDOFF.md განახლება
