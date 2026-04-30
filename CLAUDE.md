# financial-dashboard — Agent Brief

> ეს ფაილი ავტომატურად იტვირთება Claude Code-ში სესიის დასაწყისში.
> სრული წესები: `AGENTS.md` · ცოცხალი სტატუსი: `CONTEXT_HANDOFF.md`

---

## 🔴 CRITICAL — მომხმარებელთან კომუნიკაცია

- **მომხმარებელი არ არის პროგრამისტი.** ლაპარაკი მხოლოდ ქართულად. ტექნიკური ჟარგონი — მხოლოდ ახსნით.
- ფაილის/ფუნქციის სახელი ახსენე მხოლოდ თუ user-მა თვითონ იხსენია.
- ყოველი feature 3 ფენაში: **რას აკეთებს + რატომ გჭირდება + რა შედეგი იქნება**.
- კოდის block მხოლოდ თუ: (ა) user-მა მოითხოვა, (ბ) business value ცხადი diff-ია.
- გაგზავნამდე ჰკითხე თავს: **"არაპროგრამისტი გაიგებდა?"** — თუ არა, გადაწერე.
- Code, commit message, PR title = **ინგლისური**. User-თან საუბარი = **ქართული**.

## 🔴 CRITICAL — სესიის წესები

- **სესიის დაწყების სავალდებულო read**: მხოლოდ `CONTEXT_HANDOFF.md` (ცოცხალი state — ახლა სად ვართ + verified facts + ღია სამუშაო).

  - `docs/MASTER_PLAN.md` წაიკითხე **მხოლოდ მაშინ**, როცა roadmap-ის/sprint-ის მითითება მოხდება ან კონკრეტული სექციის სამუშაო დაიწყება.
  - `AGENTS.md` წაიკითხე **მხოლოდ მაშინ**, როცა proof gate / scope / წესის გაურკვევლობა გაჩნდება.

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
