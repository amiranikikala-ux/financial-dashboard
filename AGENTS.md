# Financial Dashboard — Agent Instructions

## სესიის დაწყება
1. ჯერ წაიკითხე `CONTEXT_HANDOFF.md` (ცოცხალი სტატუსი — canonical)
2. მერე წაიკითხე `AGENTS.md` (ეს ფაილი — session rules)
3. Phase overview გჭირდება? → `PHASE_STATUS_MATRIX.md`
4. Historical evidence (commit X-ის დეტალი) → `HANDOFF.md` (index) → `HANDOFF_ARCHIVE/`
5. მომხმარებლის ენა: **ქართული**, კოდი + commit: **ინგლისური**

## Stack
- **Backend**: Python 3 + FastAPI + pandas + openpyxl + APScheduler
- **Frontend**: React + Vite
- **Data flow**: Excel -> `generate_dashboard_data.py` -> `data.json` -> `/api/data`
- **Server/UI**: `server.py` (`:8000`), `rs-dashboard` (`:5173` dev)

## სამუშაო წესები
- `CONTEXT_HANDOFF.md` განაახლე მხოლოდ მიმდინარე goal-ის დახურვისას, არა ყოველ commit-ზე (per-session ერთადერთი ცოცხალი ფაილი)
- `PHASE_STATUS_MATRIX.md` განაახლე მხოლოდ **phase-ის ან sprint-ის დახურვისას**
- `HANDOFF.md` განაახლე მხოლოდ როცა არქივში რამეს გადაიტან (commit SHA → archive pointer)
- ტესტები არ წაშალო/შეასუსტო მომხმარებლის მკაფიო მითითების გარეშე
- build/test ვერიფიკაცია გააკეთე მხოლოდ შესაბამისი ცვლილების შემდეგ, არა onboarding-ის გამო
- ახალი task-ის დაწყებამდე ნუ კითხულობ ზედმეტ ფაილებს, თუ მოთხოვნა ამას არ საჭიროებს
- **Surgical edits** — ცვლილება უნდა უკავშირდებოდეს task-ს. სტილი, ფორმატირება, "უკეთესად დავწერდი" რეფაქტორი — არ შეეხო
- **Task-ის გარე bug** — თუ შემთხვევით ნახე რეალური შეცდომა, რომელიც task-ს არ ეხება, ცალკე აცნობე user-ს და იკითხე "გავასწორო ახლავე თუ ცალკე?". ნუ გაასწორებ ჩუმად იმავე commit-ში

## მომხმარებელთან საუბრის ენა (CRITICAL)
- მომხმარებელი **არ არის პროგრამისტი** — plain ქართული, არასდროს technical jargon ახსნის გარეშე
- ფაილის/ფუნქციის სახელი ახსენე მხოლოდ მაშინ, როცა user თვითონ ცალკე იხსენიებს
- ყოველი feature ახსენი **სამ ფენაში**: რას აკეთებს + რატომ გჭირდება + შედეგი რა იქნება
- ტექნიკური ცნება (pipeline, tool, cache, deploy, commit, embedding, RAG, schema, endpoint) — ჯერ მაგალითი/ახსნა, მერე სახელი (optional)
- ცხრილი / bullet list / emoji — თვალსაჩინოდ
- კოდის block გამოიყენე მხოლოდ: (ა) user-მა თვითონ იხსენია, (ბ) business value ცხადი diff-ია
- გაგზავნის წინ თავი ჰკითხე: **"თუ user პროგრამისტი არ იყო, გასაგები იქნებოდა?"** — თუ არა, გადაწერე

## Session Pacing (Phase 4B.3 Rule 23 — updated 2026-04-24)
- **~60% context usage ceiling** — სანამ context 60%-ს არ მიუახლოვდება, რამდენი goal-იც ეტევა იმდენი გავაკეთოთ ერთ session-ში; 60%-ზე მისვლისას შევთავაზო handoff
- *(ძველი "one sprint per session" / "no kitchen-sink" წესი გაუქმებულია 2026-04-24 — context window არის ცოცხალი ზღვარი, არა artificial sprint-count)*
- scope creep = bug. silent "ოჰ, ესეც გავაკეთო" ⇒ ჯერ ვკითხო user-ს, არ შევცვალო უთქმელად
- `/restart-session` — თუ იგივე შეცდომა 2-ჯერ გაკეთდა (Rule 25 ქვემოთ)

## Prompt Hygiene (Phase 4B.3 Rule 22)
- **Ruthlessly prune.** თუ prompt-ი სწორად მუშაობს მოცემული ინსტრუქციის გარეშე — წაშალე. >1000-line CLAUDE.md/system prompt half-ignored ხდება
- ახალი წესის დამატებამდე ჯერ ნახე, ხომ არ ვრცელდება უკვე არსებულ წესით
- დუბლიკატი section-ები აკრძალულია — consolidate
- verbose narrative intro ⇒ table or 2-line rule
- ყოველი rule-ს უნდა ჰქონდეს grep-assertion `test_ai_prompts_phase*.py`-ში, სხვაგვარად refactor-ის დროს silently ქრება

## Correction Escalation (Phase 4B.3 Rule 25)
- User-მა **იგივე შეცდომა** 2-ჯერ გამისწორა ერთ session-ში → **restart**. context დაბინძურდა, fix-ების კასკადი აღარ მუშაობს
- restart = ახალი ჩატი + `CONTEXT_HANDOFF.md`-ის ცოცხალი წაკითხვა + user-ის ბოლო ცხადი მოთხოვნის განმეორება
- 3-ჯერ იგივე შეცდომა **არასოდეს** — restart 2-ზე

## GitNexus — მოკლე წესები
- უცნობ კოდზე navigation-ისთვის გამოიყენე `query` / `context`
- shared symbol-ის შეცვლამდე შეამოწმე impact
- commit-მდე გადაამოწმე ცვლილებების scope
- თუ index stale-ა, მხოლოდ მაშინ განაახლე
- სრული წესები → `CLAUDE.md`
