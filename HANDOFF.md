# HANDOFF — Evidence index

> **ცოცხალი სტატუსისთვის ეს ფაილი არ გახსნა** → `CONTEXT_HANDOFF.md`
> **Roadmap** → `docs/MASTER_PLAN.md` · **Rules** → `AGENTS.md`
>
> ეს ფაილი მხოლოდ **commit SHA → archive pointer** index-ია.

---

## Commit SHA → archive lookup

### Master Plan §1 (ზედნადები) — 4-store mapping

| commit | სპრინტი | თარიღი | evidence |
|---|---|---|---|
| `666edd3` | Tbilisi (closed store) bucket | 2026-04-29 | `tests/test_supplier_data_invariants.py` + git log |
| `a318a91` | resolver fix + 3-tier safety net | 2026-04-28 | `scripts/reconcile_suppliers.py` + git log |
| `3d3ac07` | `data_quality_guard` AI tool | 2026-04-28 | git log |
| `020a555` | cancelled-status filter | 2026-04-27 | `tests/test_imported_products_cancelled_filter.py` |

### Master Plan §2 (მომწოდებლები) — Supplier Profitability (strict barcode JOIN)

| commit | სპრინტი | evidence |
|---|---|---|
| `a6d2beb` + `9f73254` | Sprint A/B PROOFED + KPI scope clarifier | `HANDOFF_ARCHIVE/PREVIEWS/ELIZI_252K_PROOF_2026-04-26.md` |
| `c61f19f` | Sprint B UI + UNVERIFIED workflow + Hook Rules fix | git log |
| `da03514` | name-in-PROTECTED rule (cigarettes/alcohol auto-merge) | git log |
| `2e685dc` | x-suffix + name candidate hints | git log |
| `1018900` | per-store breakdown via destination tracking | git log |
| `3a80cd1` + `8455486` + `97e7330` | Sprint A module + wiring + alias seed | git log |
| `b57ed2d` | Sprint A preview | `HANDOFF_ARCHIVE/PREVIEWS/SUPPLIER_PROFITABILITY_STRICT_PREVIEW.md` |

### Master Plan §18 (VAT & აუდიტი) — Phase 5 closed

| sprint | commit | evidence |
|---|---|---|
| 5.12 | `684eab8` | `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_5_12_TBC_SHORTAGE_EVIDENCE.md` |
| 5.11 | `bfeeee5` + `3d41819` | git log |
| 5.10 | `f876012` | `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_5_10_UNIT_ERROR_PREVIEW.md` |
| 5.1–5.9 | see `git log --grep="Sprint 5"` | commit messages |

### Tier 2 — Pipeline cache (per-file series complete)

| commit | sprint | თარიღი |
|---|---|---|
| `a1763a3` | 3f foodmart cashback | 2026-04-24 |
| `89338e4` | 3e POS terminal income + `sum()` precision fix | 2026-04-24 |
| `7404af6` | 3d tax_flow (cross-bank, 561× hot) | 2026-04-24 |
| `0a81b86` | 3c expense_categories | 2026-04-24 |
| `8bd01e8` | 3b samurneo | 2026-04-24 |
| `efcc79a` | 3a cache slim-down (864→207 MB) | 2026-04-23 |
| `481e474` | 2 retail_sales per-file | 2026-04-22 |

### Phase 2.3 + Phase 3.8 — Category / Margin AI tools

| commit | tool | evidence |
|---|---|---|
| `5dfbf19` + `3942bb2` | `margin_radar` | `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_3_8_MARGIN_RADAR_PREVIEW.md` |
| `533c02f` | `mix_analyzer` | `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_2_3_MIX_ANALYZER_PREVIEW.md` |

### Phase 4C.1 — Tool Schema Poka-yoke

| part | commit |
|---|---|
| 4C.1 Part B | `3d13e8b` |
| 4C.1 Part A | `eacc59b` |

### Earlier (pre-2026-04-22 historical narrative)

- Full evidence log: `HANDOFF_ARCHIVE/HANDOFF_2026-04-22.md`
- Packet H: `HANDOFF_ARCHIVE/2026-04-packet-h.md`
- AI roadmap v1.0 (superseded): `HANDOFF_ARCHIVE/AI_ADVISOR_ROADMAP_v1.0_superseded_2026-04-18.md`
- AI roadmap v2.1 (superseded by Master Plan): `HANDOFF_ARCHIVE/AI_GENIUS_PARTNER_PLAN_v2.1_superseded_2026-04-25.md`
- Phase tracker (superseded by Master Plan): `HANDOFF_ARCHIVE/PHASE_STATUS_MATRIX_v2.1_superseded_2026-04-29.md`
- Phase 4B prompt tuning preview: `HANDOFF_ARCHIVE/PREVIEWS/PHASE_4B_PROMPT_TUNING_PREVIEW.md`

---

## მომავალი evidence

ახალი preview-ები → `HANDOFF_ARCHIVE/PREVIEWS/SECTION_X_NAME_PREVIEW.md` (Master Plan section-ის ნომრით).
