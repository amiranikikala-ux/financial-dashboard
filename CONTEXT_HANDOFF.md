# CONTEXT HANDOFF — short brief

> **განახლდა**: 2026-04-22 (Sprint 4B.0 prune + git history consolidation)
> **სტატუსი**: Phase 4A **FULLY CLOSED** + Phase 1-4A code committed to git (10 commits ahead of `f7b0899`); Sprint 4B.0 prompt prune **DONE** (`SYSTEM_PROMPT_KA` 1,290 → 1,100 ხაზი, Anthropic target hit).

---

## რომელი დოკუმენტი რისთვისაა

| ფაილი | გამოყენება |
|---|---|
| **`CONTEXT_HANDOFF.md`** (ეს) | ახალი ჩატის startup — verified facts + do-not-touch + next step |
| **`AI_GENIUS_PARTNER_PLAN.md`** | authoritative roadmap v2.1 (Phase 0A–4A done, 4B+ remaining) |
| **`PHASE_STATUS_MATRIX.md`** | ერთი ცხრილი ყველა phase-ის სტატუსით |
| **`PLAN.md`** | live status tracker + full technical plan |
| **`PHASE_4B_PROMPT_TUNING_PREVIEW.md`** | მხოლოდ აქტიური preview root-ში (Sprint 4B.1 awaits approval) |
| **`AGENTS.md`** | session-start checklist + GitNexus rules + Windows-venv caveats |
| **`HANDOFF.md`** | full evidence log (open only for per-phase drill-down) |
| **`HANDOFF_ARCHIVE/`** | 12 per-phase preview drafts + legacy roadmap (historical only) |

**ახალი ჩატის read order**: ეს ფაილი → `AGENTS.md` → (თუ საჭიროა phase-specific context) `PHASE_STATUS_MATRIX.md`.

---

## Canonical paths & services

- **Workspace root**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი`
- **Project**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\financial-dashboard`
- **Python interpreter** (canonical, parent venv): `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe`
- **Backend**: Windows Service **`FinancialDashboardBackend`** (NSSM 2.24, `C:\tools\nssm\nssm.exe`) — auto-starts on boot, auto-restarts 2s after crash, `AI_ENABLE_THINKING=true` + `PYTHONUTF8=1` persisted, logs rotate 10MB/24h in `logs/backend_{stdout,stderr}.log`
- **Backend control**: `services.msc` → "Financial Dashboard Backend" OR `Restart-Service FinancialDashboardBackend` OR `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit} FinancialDashboardBackend`
- **Tool surface**: 18 tools live (`compute_waybill_total`, `compute`, `forecast_revenue`, `save_memory`, `recall_context`, `journal_add_entry`/`list_entries`/`update_entry`, `read_data_json`, `read_excel_source`, `read_source_code`, `grep_code`, `validate_vs_source`, `analyze_dead_stock`, `prepare_supplier_brief`, `compute_cash_runway`, `build_debt_repayment_plan` @ idx 12, `propose_feature` @ idx 17)

---

## Verified facts (from git history)

| თარიღი | commit | მოცულობა |
|---|---|---|
| 2026-04-22 | `07780bf` | scratch cleanup — 2 helpers kept, 26 files dropped |
| 2026-04-22 | `5b60e75` | `.mcp.json` + `.claude/commands/` + gitignore refinements |
| 2026-04-22 | `71db708` | docs consolidated (AGENTS/PLAN/HANDOFF/master plan/phase matrix/archive) |
| 2026-04-22 | `13e54e7` | launcher scripts → parent-venv + `_api-dev.bat` |
| 2026-04-22 | `825af3b` | Packet F calendar migration + SW cache-bust |
| 2026-04-22 | `5922566` | fix: missing `date_filters.py` |
| 2026-04-22 | `cc33b4e` | frontend Packet G propagation + Suppliers widget |
| 2026-04-22 | `55045d6` | pipeline period-aware + AI analytics builders |
| 2026-04-22 | `c0fd63d` | frontend AI chat UI + Phase 3.5/4A pages |
| 2026-04-22 | `0f3793e` | server AI endpoints + period-aware query params |
| 2026-04-22 | `7ef3451` | AI Advisor module (13 py + 20 tests) + **Sprint 4B.0 prune** (1,290→1,100) |

**pytest baseline**: **1,443/1,443 green**, run in ~16s on the parent venv.

---

## Do-not-touch rules (carry forward)

1. **Backend interpreter = parent venv only** (`...\AI აგენტი\venv\Scripts\python.exe`). Never `.venv` / project-local / system Python. Windows Service already targets this.
2. **Windows venv verification** = `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` (NOT `Get-Process <pid> | Select Path` — stub artifact always shows base interpreter).
3. **Env propagation** = verify `usage.thinking=true` in a real SSE call after any backend restart. CommandLine match alone is insufficient (silent-degrade risk, proven 2026-04-20).
4. **Investigator prompt** (`SYSTEM_PROMPT_KA_INVESTIGATOR`) stays marker-free for chat-mode sections. Any Phase-N prompt addition must land only in `SYSTEM_PROMPT_KA`. Asserted by per-phase do-not-touch tests.
5. **GitNexus index** is regenerated via `npx gitnexus analyze` after commits; hooks may automate. If a GitNexus tool flags stale, re-analyze before making impact/detect_changes decisions.
6. **ChromaDB 1.5.x `$lt`/`$gt`** don't work on string metadata (`journal_due_date`). Python post-fetch filter is mandatory; `journal.py::_build_journal_where` must emit only `$eq`/`$ne`.
7. **Excel Georgian path**: `tools.py::_resolve_safe_path` uses `Path.absolute()` (lexical), NOT `Path.resolve()` (follows OneDrive junctions across non-ASCII ancestors). Traversal protection: explicit `..` segment reject.
8. **Prompt editing**: 432 grep-style assertions pin `SYSTEM_PROMPT_KA`. Before any edit, grep tests for asserted Georgian phrases. Section headers + trigger/anti-trigger tables + asserted rule phrases are load-bearing.

---

## Active packet

**Phase 4B.0 Prune**: ✅ DONE (this session — Anthropic ≤1,100 lines target achieved).
**Sprint 4B.1 Tier 1 (9 rules)**: 📋 PLANNED, awaits user approval on 7 Open Questions in `PHASE_4B_PROMPT_TUNING_PREVIEW.md §12`. Scope: ~1.5 days, ~$0.25 API cost, requires live dog-food. Open Questions defaults recommended:

1. Emoji policy → functional labels stay (🟢🟡🟠⚪)
2. Financial-advisor disclaimer → no
3. XML vs Markdown → hybrid (new blocks XML)
4. Sprint order → 4B.0 first (done), then 4B.1
5. Oververbosity default → `3` (strategic `7`)
6. STOP-CHECK vs partial-completion → financial-critical decisions only clarify; everything else partial-completion
7. 4B vs 4C → sequential (4B first)

---

## Next recommended steps

1. **`git push`** — 11 local commits ahead of `origin/main`; nothing critical pending.
2. **Sprint 4B.1 start** — needs user confirmation on the 7 Open Questions defaults above + budget approval for live dog-food.
3. **HANDOFF.md prune** — still 1,106 lines; same disease as prompt. Low-priority hygiene.
4. **Parking Lot** — ~40 features in `AI_GENIUS_PARTNER_PLAN.md` v2.1.

---

## `მოამზადე ახალი ჩატისთვის` — rule

- განაახლე ეს ფაილი (verified facts + do-not-touch + next step only).
- **არ შეაყრო ისტორია** — ისტორია `HANDOFF.md`-ში, evidence `HANDOFF_ARCHIVE/`-ში, git log-ში.
- Short brief-ის target: **~150 lines or under**. If you're about to write a third "წინა-სტატუსი" block, stop — move it to `HANDOFF.md` instead.
