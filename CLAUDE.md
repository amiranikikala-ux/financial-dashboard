# financial-dashboard — Agent Brief

> ეს ფაილი ავტომატურად იტვირთება Claude Code-ში სესიის დასაწყისში.
> სრული წესები: `AGENTS.md` · ცოცხალი სტატუსი: `CONTEXT_HANDOFF.md`

---

## 🔴 CRITICAL — მომხმარებელთან კომუნიკაცია

**მთავარი წესი: მოკლე წინადადებები. მარტივი ქართული. გრძელი პასუხი = შეცდომა.**

- **მომხმარებელი არ არის პროგრამისტი.** ტექნიკური სიტყვა — მხოლოდ თუ აუცილებელია, და მაშინაც ერთი წინადადებით უნდა ახსნა.
- **ერთი აზრი — ერთი წინადადება.** რთული წინადადება (ორ-სამ ნაწილად) → დაანაწევრე.
- **ცხრილი / bullet — მინიმუმამდე.** გამოიყენე მხოლოდ თუ მართლა ცხრილია (მონაცემთა შედარება). ჩვეულებრივ ტექსტი = ჩვეულებრივი წინადადებები.
- ფაილის/ფუნქციის სახელი ახსენე მხოლოდ თუ user-მა თვითონ იხსენია.
- კოდის block მხოლოდ თუ: (ა) user-მა მოითხოვა, (ბ) ცხადი value-ია.
- გაგზავნამდე ჰკითხე თავს: **„არაპროგრამისტი 5 წამში გაიგებს?"** — თუ არა, გადაწერე უფრო მოკლედ.
- Code, commit message, PR title = **ინგლისური**. User-თან საუბარი = **ქართული**.

## 🔴 CRITICAL — მონაცემის ჩუმად ჩამოგდება აკრძალულია

**წესი (set 2026-05-07): parser/pipeline/script-მა თუ რაიმე row, ფაილი, ან ფაქტი გამოტოვა — owner-ს ცხადად ეცნობოს, ციფრი მარტო არასაკმარისია.**

- "16 skipped" გადმოცემა და გაგრძელება — **აკრძალულია**. უნდა დაერთოს: რა ხასიათის სტრიქონებია (sample), რატომ გამოტოვა (root cause), და კითხვა „გადავამოწმოთ რა არის ამ სტრიქონებში?".
- ეს ვრცელდება ყველაზე: parser-ი, file reader, validation filter, dedup logic, status filter — ყველგან, სადაც მონაცემი იცრიცება.
- სრულყოფილი ანალიზი ნიშნავს — ცარიელი slot-ი არასოდეს silent არ ხდება. არც skipped row, არც unparsed file, არც ignored field.
- "no silent gap" Proof Gate Layer 3 (`AGENTS.md`) უკვე არსებობდა — ეს მისი გაძლიერებაა skipped data-ზე. memory: `feedback_no_silent_data_drops.md`.

## 🔴 CRITICAL — Aggregate ციფრი ცოცხალ წყაროს უნდა ემთხვეოდეს

**წესი (set 2026-05-13): ნებისმიერი headline / KPI / summary ციფრი, რომელიც კოდი ანგარიშობს, უნდა შემოწმდეს ცოცხალ წყაროსთან 1:1. სხვაგვარად — silent drift.**

- **რა მოხდა 2026-05-13:** Home გვერდის „ბანკში შემოვიდა" სათაურს ეწერა 86,361 ₾ აპრილში, ცოცხალ ბანკში იყო 163,918 ₾. ე.ი. 77,556 ₾ (90%!) დაიკარგა, რადგან კოდი headline-ს ცარიელი category subset-ით თვლიდა. იგივე ბაგ-ი OUT-ზე — 35,899 ₾ გამოტოვებული. **ვერც კოდმა, ვერც AI-მ ვერ შემოწმდა.** Owner-მა შენიშნა.
- **წესი ხელახლა:** headline = raw accumulator (loop-ში += ხაზობრივად). categories = display only. ყოველ დღეს raw vs categorized_sum შემოწმდება — diff > 0.01 → წითელი badge UI-ში + log error.
- **სად ვრცელდება:** ნებისმიერი pipeline/aggregator (sum, count, average); ნებისმიერი KPI ცხრილი; per-period/per-store/per-supplier breakdown — aggregate-ი row-ების ჯამს უნდა შეესაბამებოდეს.
- **„ფუნქცია სავარაუდოდ მუშაობს" = ცრუ ვარაუდი.** ცოცხალი წყაროდან გადამოწმების გარეშე ციფრი არ უნდა გადავცე owner-ს. memory: `feedback_aggregate_vs_source_verification.md` + `feedback_proactive_verification.md`.

## 🔴 CRITICAL — სესიის წესები

- **სესიის დაწყების სავალდებულო read** (SessionStart hook აიძულებს): 3 ფაილი თანმიმდევრობით — `CONTEXT_HANDOFF.md` (ცოცხალი state) → `docs/MASTER_PLAN.md` (roadmap) → `AGENTS.md` (წესები).
- **Context ~60%-ზე**: შესთავაზე handoff (CONTEXT_HANDOFF.md განახლება + ახალი სესია). არასოდეს გააგრძელო silently "კიდევ ერთი goal".
- **იგივე შეცდომა 2-ჯერ ერთ სესიაში → STOP.** შესთავაზე restart, არ გააგრძელო გასწორების ციკლი (context უკვე დაბინძურდა). 3-ჯერ — არასოდეს.
- **Scope creep = bug.** "ოჰ, ესეც გავაკეთო" — ჯერ ჰკითხე user-ს.
- ტესტები არ წაშალო/შეასუსტო user-ის მკაფიო მითითების გარეშე.
- Build/test ვერიფიკაცია მხოლოდ რეალური ცვლილების შემდეგ — არა "onboarding"-ისთვის.

## Stack (1-წუთიანი ცოდნა)

- **Backend**: Python 3 + FastAPI + pandas + openpyxl + APScheduler · service `FinancialDashboardBackend` (NSSM, port `8000`)
- **Frontend**: React + Vite (`rs-dashboard/`, dev port `5173`)
- **Data flow**: Excel → `generate_dashboard_data.py` → `data.json` → `/api/data`
- **Python interpreter**: parent venv ONLY (`...\AI აგენტი\venv\Scripts\python.exe`). NEVER `.venv` / system Python.
- **Service restart for new prompt/code**: `Restart-Service FinancialDashboardBackend` (admin/UAC). In-process tests — `_scratch_dogfood_*.py` pattern.

## დოკუმენტების რუკა

> ცოცხალი governance = 4 ფაილი. CLAUDE.md (ეს) auto-loaded entry point-ია — pointer-ები + GitNexus მინი-ბლოკი.

| # | ფაილი | რისთვის | როდის |
|---|------|--------|------|
| 1 | **`CONTEXT_HANDOFF.md`** | ცოცხალი state — ახლა სად ვართ + verified facts + open work + do-not-touch | **session-start** (ყოველთვის) |
| 2 | **`docs/MASTER_PLAN.md`** | ერთადერთი 18-სექციის roadmap (A→F sequence, 6-step sprint cycle, data inventory, VAT cross-cutting) | მხოლოდ roadmap/sprint მუშაობისას |
| 3 | **`AGENTS.md`** | სრული წესები — 3-ფენიანი proof gate, ენა, scope, escalation, GitNexus scope, prompt hygiene | მხოლოდ proof gate / scope / წესის გაურკვევლობისას |
| 4 | `HANDOFF.md` | commit SHA → archive evidence pointer index | მხოლოდ წარსული commit-ის drill-down |
| — | `HANDOFF_ARCHIVE/` | ისტორიული evidence + superseded roadmaps (მათ შორის ძველი `PHASE_STATUS_MATRIX`) | ღრმა არქივის წაკითხვა |
| — | `README.md` | GitHub-ის სტუმრებისთვის (არ არის agent governance) | არასოდეს agent მუშაობისას |

---

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **financial-dashboard** (5654 symbols, 15371 relationships, 300 execution flows). Use GitNexus MCP tools (`gitnexus_query` / `gitnexus_context` / `gitnexus_impact` / `gitnexus_rename` / `gitnexus_detect_changes`) to navigate code safely.

**Scope (per `AGENTS.md`)**: `gitnexus_impact` is required only for **shared / load-bearing function, class, or method edits**. JSON mapping updates, docs changes, constant changes, and isolated frontend tweaks are **EXEMPT** from impact-analysis overhead.

**Index freshness**: if a GitNexus tool warns the index is stale, run `npx gitnexus analyze` (add `--embeddings` if `.gitnexus/meta.json` shows existing embeddings — running without that flag deletes them). A PostToolUse hook handles this automatically after `git commit` / `git merge`.

## CLI — detailed knowledge in skill files

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
