# Financial Dashboard — Agent Instructions

## სესიის დაწყება
1. ჯერ წაიკითხე `PLAN.md`
2. მერე წაიკითხე root `AGENTS.md`
3. შემდეგ წაიკითხე `CONTEXT_HANDOFF.md`
4. `HANDOFF.md` გახსენი მხოლოდ თუ საჭიროა ბოლო ცვლილებები, ზუსტი ისტორია, file-level evidence ან runtime caveat-ები
5. მომხმარებლის ენა: **ქართული**, კოდი + commit: **ინგლისური**
6. onboarding-ის გამო თავიდანვე ნუ უშვებ ყველა ტესტს ან build-ს; გაუშვი მხოლოდ task-ის საჭიროების მიხედვით

## Stack
- **Backend**: Python 3 + FastAPI + pandas + openpyxl + APScheduler
- **Frontend**: React + Vite
- **Data flow**: Excel -> `generate_dashboard_data.py` -> `data.json` -> `/api/data`
- **Server/UI**: `server.py` (`:8000`), `rs-dashboard` (`:5173` dev)

## სამუშაო წესები
- `HANDOFF.md` განაახლე მხოლოდ მაშინ, როცა რეალურად შეიცვალა სტატუსი, caveat-ი ან ბოლო სესიის summary
- `PLAN.md` განაახლე მხოლოდ მაღალი დონის სტატუსის ცვლილებისას
- ტესტები არ წაშალო/შეასუსტო მომხმარებლის მკაფიო მითითების გარეშე
- build/test ვერიფიკაცია გააკეთე მხოლოდ შესაბამისი ცვლილების შემდეგ, არა onboarding-ის გამო

## მომხმარებელთან საუბრის ენა (CRITICAL)
- მომხმარებელი **არ არის პროგრამისტი** — plain ქართული, არასდროს technical jargon ახსნის გარეშე
- ფაილის/ფუნქციის სახელი ახსენე მხოლოდ მაშინ, როცა user თვითონ ცალკე იხსენიებს
- ყოველი feature ახსენი **სამ ფენაში**: რას აკეთებს + რატომ გჭირდება + შედეგი რა იქნება
- ტექნიკური ცნება (pipeline, tool, cache, deploy, commit, embedding, RAG, schema, endpoint) — ჯერ მაგალითი/ახსნა, მერე სახელი (optional)
- ცხრილი / bullet list / emoji — თვალსაჩინოდ
- კოდის block გამოიყენე მხოლოდ: (ა) user-მა თვითონ იხსენია, (ბ) business value ცხადი diff-ია
- გაგზავნის წინ თავი ჰკითხე: **"თუ user პროგრამისტი არ იყო, გასაგები იქნებოდა?"** — თუ არა, გადაწერე

## კონტექსტის მართვა
- თუ ჩატი იზრდება, დაასრულე მიმდინარე ნაბიჯი და მოამზადე მოკლე handoff
- ახალი ჩატისთვის default წყარო იყოს `CONTEXT_HANDOFF.md`; ნუ აგროვებ ვრცელ session history-ს
- ახალი task-ის დაწყებამდე ნუ კითხულობ ზედმეტ ფაილებს, თუ მოთხოვნა ამას არ საჭიროებს

## `მოამზადე ახალი ჩატისთვის` — სავალდებულო contract
- ჯერ განაახლე `CONTEXT_HANDOFF.md`
- მერე ჩატში დააბრუნე იგივე მოკლე copy/paste brief
- brief-ში აუცილებლად იყოს:
  - canonical project path
  - active packet/status
  - ამ ჩატში რა შეიცვალა
  - verified facts only
  - do-not-touch rules
  - next recommended step
  - authoritative files
  - verification pending / not run
- სრული ისტორია და დეტალური evidence დატოვე `HANDOFF.md`-ში

## GitNexus — მოკლე წესები
- უცნობ კოდზე navigation-ისთვის გამოიყენე `query` / `context`
- shared symbol-ის შეცვლამდე შეამოწმე impact
- commit-მდე გადაამოწმე ცვლილებების scope
- თუ index stale-ა, მხოლოდ მაშინ განაახლე

## Prompt Hygiene (Phase 4B.3 Rule 22 — `code.claude.com`)
- **Ruthlessly prune.** If the prompt does something correctly without a given instruction, delete the instruction. >1000-line CLAUDE.md / system prompt gets half-ignored.
- ახალი წესის დამატებამდე ჯერ ნახე, ხომ არ ვრცელდება უკვე არსებულ წესით
- dublicate section-ები (მაგ. "ენა და ფორმატი" ორჯერ) აკრძალულია — consolidate
- verbose narrative intro ⇒ table or 2-line rule
- ყოველი rule-ს უნდა ჰქონდეს grep-assertion `test_ai_prompts_phase*.py`-ში, სხვაგვარად refactor-ის დროს silently ქრება

## Session Boundaries (Phase 4B.3 Rule 23 — `code.claude.com`)
- **No kitchen-sink sessions.** ერთი session = ერთი logical goal (მაგ. "Sprint 4B.2 + tests + commit")
- scope creep = bug. თუ გზაში "ოჰ, ესეც გავაკეთო" მომიტყდა — ახალი task რომ გავაკეთო, ამ session-ის goal უნდა დავასრულო ჯერ
- HANDOFF.md / CONTEXT_HANDOFF.md — განაახლე მხოლოდ მიმდინარე goal-ის დახურვისას, არა ყოველ commit-ზე
- `/restart-session` command-ით ახალი session-ი, თუ იგივე შეცდომა 2-ჯერ გაკეთდა (Rule 25 ქვემოთ)

## Correction Escalation (Phase 4B.3 Rule 25 — `code.claude.com`)
- User-მა **იგივე შეცდომა** 2-ჯერ გამისწორა ერთ session-ში → **restart**. context ძალიან დაბინძურდა, fix-ების კასკადი აღარ მუშაობს
- restart = ახალი ჩატი + `CONTEXT_HANDOFF.md`-ის ცოცხალი წაკითხვა + განმეორება user-ის ბოლო ცხადი მოთხოვნის
- 3-ჯერ იგივე შეცდომა **არასოდეს** — restart 2-ზე
