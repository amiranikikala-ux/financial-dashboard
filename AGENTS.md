# Financial Dashboard — Agent Instructions

## სესიის დაწყება
1. **წაიკითხე HANDOFF.md** — პროექტის სტატუსი, ბოლო სესიის ცვლილებები, ფაილების რუკა, შემდეგი ნაბიჯები
2. **წაიკითხე PLAN.md** — რა ფაზებია დასრულებული, რა რჩება
3. **გაუშვი ტესტები**: `python -m pytest tests/ -q` (125 pass expected)
4. **გაუშვი ბილდი**: `cd rs-dashboard && npx vite build` (0 errors expected)
5. მომხმარებლის ენა: **ქართული**, კოდი + commit: **ინგლისური**

## Stack
- **Backend**: Python 3 + FastAPI + pandas + openpyxl + APScheduler
- **Frontend**: React 19 + Vite, 14 lazy-loaded tabs, Recharts charts, xlsx export
- **Data**: Excel → `generate_dashboard_data.py` → `data.json` → `/api/data`
- **Server**: `server.py` (:8000), dev UI: `:5173`

## წესები
- სესიის ბოლოს **აუცილებლად** განაახლე HANDOFF.md სესიის ნომრით და ცვლილებების ჩამონათვალით
- ტესტები არ წაშალო/შეასუსტო მომხმარებლის მკაფიო მითითების გარეშე
- ყველა ახალი ფუნქციის შემდეგ: ბილდის ვერიფიკაცია (`npx vite build`)

## ⚠️ კონტექსტის მართვა (სავალდებულო)
როცა ხვდები რომ ჩატი ხანგრძლივია (ბევრი tool call, ბევრი ფაილის კითხვა/რედაქტირება, 15+ მოქმედება):
1. **შეაჩერე მიმდინარე მუშაობა** მიმდინარე ნაბიჯის დასრულების შემდეგ
2. **გაუშვი ტესტები და ბილდი** — დარწმუნდი რომ კოდი მუშა მდგომარეობაშია
3. **განაახლე HANDOFF.md** — სესიის ნომერი, რა გაკეთდა, რა დარჩა, ფაილების რუკა
4. **განაახლე PLAN.md** — თუ ფაზის სტატუსი შეიცვალა
5. **შეინახე Memory** — სესიის შეჯამება
6. **აცნობე მომხმარებელს**: "⚠️ კონტექსტი ივსება. HANDOFF.md განახლებულია. გთხოვ გახსენი ახალი ჩატი და დაწერე 'განაგრძე'."
7. **ნუ დაიწყებ ახალ თასქს** — მხოლოდ handoff მოამზადე

<!-- gitnexus:start -->
## GitNexus — Code Intelligence

Indexed as **financial-dashboard** (827 symbols, 65 execution flows). Stale index? `npx gitnexus analyze`

### GitNexus Rules

- Run `impact({target, direction: "upstream"})` before editing any function/class. Warn user on HIGH/CRITICAL risk.
- Run `detect_changes()` before committing.
- Use `query()` to find execution flows, `context()` for symbol details.
- Rename with `rename()`, never find-and-replace. Preview with `dry_run: true`.
- After refactor: `detect_changes({scope: "all"})`.

### Risk: d=1 WILL BREAK | d=2 likely affected | d=3 may need testing

### Resources

- `gitnexus://repo/financial-dashboard/context` — overview
- `gitnexus://repo/financial-dashboard/processes` — execution flows
- `gitnexus://repo/financial-dashboard/process/{name}` — step-by-step trace

### Index: `npx gitnexus analyze` (add `--embeddings` if needed)
<!-- gitnexus:end -->