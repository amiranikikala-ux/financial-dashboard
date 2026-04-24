# Financial Dashboard — Agent Instructions

## სესიის დაწყება
1. ჯერ წაიკითხე `CONTEXT_HANDOFF.md` (ცოცხალი სტატუსი — canonical)
2. მერე წაიკითხე `AGENTS.md` (ეს ფაილი — session rules)
3. Phase overview გჭირდება? → `PHASE_STATUS_MATRIX.md`
4. Closed milestone log / stack ref → `PLAN.md`
5. Master roadmap (v2.1) → `AI_GENIUS_PARTNER_PLAN.md`
6. Historical evidence (commit X-ის დეტალი) → `HANDOFF.md` (index) → `HANDOFF_ARCHIVE/`
7. მომხმარებლის ენა: **ქართული**, კოდი + commit: **ინგლისური**
8. onboarding-ის გამო თავიდანვე ნუ უშვებ ყველა ტესტს ან build-ს; გაუშვი მხოლოდ task-ის საჭიროების მიხედვით

## Stack
- **Backend**: Python 3 + FastAPI + pandas + openpyxl + APScheduler
- **Frontend**: React + Vite
- **Data flow**: Excel -> `generate_dashboard_data.py` -> `data.json` -> `/api/data`
- **Server/UI**: `server.py` (`:8000`), `rs-dashboard` (`:5173` dev)

## სამუშაო წესები
- `CONTEXT_HANDOFF.md` განაახლე goal-ის დახურვისას (per-session ერთადერთი ფაილი რომელიც ცოცხლად განაახლდება)
- `PLAN.md` / `PHASE_STATUS_MATRIX.md` განაახლე მხოლოდ **phase-ის ან sprint-ის დახურვისას**, არა ყოველ commit-ზე
- `HANDOFF.md` განაახლე მხოლოდ როცა არქივში რამეს გადაიტან (commit SHA → archive pointer)
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
- სრული ისტორია და დეტალური evidence დატოვე `HANDOFF_ARCHIVE/`-ში (ახალი preview-ები: `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_XX_NAME_PREVIEW.md`)

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
- `CONTEXT_HANDOFF.md` — განაახლე მხოლოდ მიმდინარე goal-ის დახურვისას, არა ყოველ commit-ზე
- `/restart-session` command-ით ახალი session-ი, თუ იგივე შეცდომა 2-ჯერ გაკეთდა (Rule 25 ქვემოთ)

## Correction Escalation (Phase 4B.3 Rule 25 — `code.claude.com`)
- User-მა **იგივე შეცდომა** 2-ჯერ გამისწორა ერთ session-ში → **restart**. context ძალიან დაბინძურდა, fix-ების კასკადი აღარ მუშაობს
- restart = ახალი ჩატი + `CONTEXT_HANDOFF.md`-ის ცოცხალი წაკითხვა + განმეორება user-ის ბოლო ცხადი მოთხოვნის
- 3-ჯერ იგივე შეცდომა **არასოდეს** — restart 2-ზე

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **financial-dashboard** (4862 symbols, 13012 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/financial-dashboard/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/financial-dashboard/context` | Codebase overview, check index freshness |
| `gitnexus://repo/financial-dashboard/clusters` | All functional areas |
| `gitnexus://repo/financial-dashboard/processes` | All execution flows |
| `gitnexus://repo/financial-dashboard/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
