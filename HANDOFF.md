# HANDOFF — Evidence index

> **ცოცხალი სტატუსისთვის ეს ფაილი არ გახსნა.** → `CONTEXT_HANDOFF.md` · Phase overview → `PHASE_STATUS_MATRIX.md` · Historical roadmap → `HANDOFF_ARCHIVE/AI_GENIUS_PARTNER_PLAN_v2.1_superseded_2026-04-25.md`.
> ეს ფაილი მხოლოდ **evidence pointer**-ია: commit SHA → archive location.

---

## რისთვის არის ეს ფაილი

`CONTEXT_HANDOFF.md` ცოცხალი სტატუსის ჩანაწერია — აქ **არასდროს არ ინახება ისტორია**. როცა გჭირდება ძველი phase-ის სრული evidence, არქივი + git log-ი არის authoritative.

---

## Commit SHA → archive lookup

### Tier 2 Pipeline Cache (Sprint 2 / 3a / 3b / 3c / 3d / 3e / 3f — **per-file cache series COMPLETE**)

| commit | sprint | თარიღი | evidence |
|---|---|---|---|
| `a1763a3` | 3f foodmart cashback | 2026-04-24 | `tests/test_foodmart_cashback_incremental.py` + git log |
| `89338e4` | 3e POS terminal income + `sum()` precision fix | 2026-04-24 | `tests/test_pos_terminal_income_incremental.py` + git log |
| `7404af6` | 3d tax_flow (cross-bank) | 2026-04-24 | `tests/test_tax_flow_incremental.py` + git log |
| `0a81b86` | 3c expense_categories | 2026-04-24 | `CONTEXT_HANDOFF.md` commit-history + git log |
| `8bd01e8` | 3b samurneo | 2026-04-24 | `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_3B_BANK_PREVIEW.md` |
| `efcc79a` | 3a cache slim-down | 2026-04-23 | git log + `CONTEXT_HANDOFF.md` |
| `481e474` | 2 retail_sales per-file | 2026-04-22 | `tests/test_retail_sales_incremental.py` |

### Phase 2.3 & Phase 3.8 — Category / Margin AI tools

| commit | phase | evidence |
|---|---|---|
| `5dfbf19` + `3942bb2` | Phase 3.8 `margin_radar` (time-series GM compression) | `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_3_8_MARGIN_RADAR_PREVIEW.md` |
| `533c02f` | Phase 2.3 `mix_analyzer` (category mix / DRAG-LIFT) | `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_2_3_MIX_ANALYZER_PREVIEW.md` |

### Phase 5 VAT / Tax Audit (Sprint 5.1 → 5.12)

| sprint | commit | evidence |
|---|---|---|
| 5.12 | `684eab8` | `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_5_12_TBC_SHORTAGE_EVIDENCE.md` |
| 5.11 | `bfeeee5` + `3d41819` | `CONTEXT_HANDOFF.md` commit-history |
| 5.10 | `f876012` | `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_5_10_UNIT_ERROR_PREVIEW.md` |
| 5.1–5.9 | see `CONTEXT_HANDOFF.md:51-68` | git log + commit messages |

### Phase 4C.1 — Tool Schema Poka-yoke

| part | commit | evidence |
|---|---|---|
| 4C.1 Part B | `3d13e8b` | live dog-food 4/4 PASS in `CONTEXT_HANDOFF.md:81-85` |
| 4C.1 Part A | `eacc59b` | live dog-food 4/4 PASS in `CONTEXT_HANDOFF.md:81-85` |

### Earlier (Packet H, Phase 0–4B) — pre-2026-04-22 historical narrative

- Full evidence log (1,106 ხაზი): **`HANDOFF_ARCHIVE/HANDOFF_2026-04-22.md`**
- Packet H foundations: `HANDOFF_ARCHIVE/2026-04-packet-h.md`
- Superseded AI roadmap v1.0: `HANDOFF_ARCHIVE/AI_ADVISOR_ROADMAP_v1.0_superseded_2026-04-18.md`
- Phase 4B prompt tuning preview: `HANDOFF_ARCHIVE/PREVIEWS/PHASE_4B_PROMPT_TUNING_PREVIEW.md`

---

## როდის დაუბრუნდე არქივს

| სცენარი | სად |
|---|---|
| "რატომ `_resolve_safe_path`-ში `Path.absolute()` და არა `resolve()`?" | `HANDOFF_ARCHIVE/HANDOFF_2026-04-22.md` + commit message |
| "რა იყო Phase 1 Part D-ის acceptance criteria?" | `HANDOFF_ARCHIVE/HANDOFF_2026-04-22.md` Section 5 |
| "რა მოხდა Sprint 5.12 TBC shortage-ში?" | `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_5_12_TBC_SHORTAGE_EVIDENCE.md` |
| "რა ცვლილება იყო Sprint 3b cache-ში?" | `git show 8bd01e8` + `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_3B_BANK_PREVIEW.md` |

---

## მომავალი evidence

ახალი preview-ები → `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_XX_NAME_PREVIEW.md` (Sprint 3b-ს pattern-ი).
არც ერთი ახალი evidence არ ემატება ამ ფაილს — ეს უბრალოდ index-ია.
