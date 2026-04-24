# Sprint 5.12 — TBC shortage 2023-08 → 2024-03 diagnosis (evidence-only)

**Status**: **EVIDENCE COMPLETE · NO CODE CHANGE**
**Date**: 2026-04-24
**Branch**: `sprint-5.12-tbc-shortage-investigation`

---

## TL;DR

8 consecutive months (2023-08 → 2024-03) show pipeline TBC POS income **-27% to -81% below** the auditor's TBC figure, totaling **~52K ₾ cumulative shortfall**. Every other month (both earlier and later) matches audit within +16-17% (the expected pipeline-gross vs audit-net delta).

**Root cause**: **TBC bank statement format changed mid-2024.** Before the change (2023-08 → 2024-03), per-transaction POS deposits for terminals SH046092 and SH034467 were posted into the transit-IBAN (`GE69TB0000000251140006`) with merchant-ID tags (`33001022152`, `33001023234`, `01301132349`) **but no physical terminal ID** embedded in the row text. From 2024-04 onwards, TBC started embedding physical terminal IDs (SH046092, SH079927, SH060853, etc.) in the daily-rollup rows, making our Sprint 5.2 terminal-ID filter work correctly.

**No safe automatic fix available** — the same merchant-ID rows that represent "missing" per-transaction deposits in the 8 shortage months represent **double-counted aggregates** in later months (on top of terminal-ID-tagged rollups). Sprint 5.2 deliberately excluded them to eliminate the 8.3× inflation bug.

**Audit-defense impact**: **None.** Audit's own TBC figure is computed from RS.ge's official POS terminal export (= RS.ge gross ÷ 1.18 = audit net) and already reflects reality. The pipeline's independent +90K net / +107K gross gap figure (Sprint 5.11) is computed across all 44 months; the 52K TBC shortfall in the 8 months is a pipeline coverage gap, not a disagreement with audit. It's already called out in `CONTEXT_HANDOFF.md` under "audit defense view".

---

## Evidence

### 1. Per-month cross-match (post-Sprint-5.11 data.json)

Source: `_scratch_sprint5_10_tbc_bog_crossmatch.py` re-run on current data.json.

| month | pipe_tbc | audit_tbc | tbc_diff | tbc_% |
|---|---:|---:|---:|---:|
| 2023-07 (control) | 15,203 | 13,006 | +2,198 | **+16.9%** |
| **2023-08** | **10,674** | **14,618** | **-3,944** | **-27.0%** |
| **2023-09** | 5,726 | 13,691 | -7,965 | **-58.2%** |
| **2023-10** | 4,116 | 11,695 | -7,579 | **-64.8%** |
| **2023-11** | 7,361 | 14,967 | -7,607 | **-50.8%** |
| **2023-12** | 4,271 | 10,931 | -6,661 | **-60.9%** |
| **2024-01** | 3,124 | 9,738 | -6,613 | **-67.9%** |
| **2024-02** | 1,404 | 7,476 | -6,072 | **-81.2%** |
| **2024-03** | 2,485 | 8,482 | -5,997 | **-70.7%** |
| 2024-04 (control) | 7,177 | 10,180 | -3,003 | -29.5% (residual) |
| 2024-05 (control) | 3,354 | 5,293 | -1,939 | -36.6% (residual) |
| 2024-08 (control) | 7,832 | 6,697 | +1,134 | **+16.9%** |
| 2025-08 (control) | 37,011 | 31,654 | +5,357 | **+16.9%** |

**Cumulative shortage (8 bad months)**: **-52,438 ₾**

### 2. Row-format forensics (2023-08 vs 2024-08)

Script: `_scratch_sprint5_12_row_forensics.py`

Each TBC credit row classified into 5 buckets by presence of:
- A **terminal ID** (SH046092, RS014189, SH079927, SH034467, SH060853)
- A **merchant-ID** prefix (11-digit number + ";")
- An **aggregate marker** ("ECOM/POS მერჩანტ", "ტრანზაქციის თანხები")
- Transit IBAN `GE69TB0000000251140006`

**2023-08 (SHORTAGE)** — total credit rows = 1,286, sum = 117,092 ₾:
| bucket | rows | sum ₾ | captured by pipeline? |
|---|---:|---:|---|
| A: terminal-ID rollup, small ≤50 ₾ (fee/per-card) | 1,017 | 10,014 | ✓ yes (RS014189 only) |
| B: terminal-ID rollup, >50 ₾ | 10 | 660 | ✓ yes (RS014189 only) |
| C: merchant-ID ნავაჭრი, per-tx ≤2K ₾ | 28 | 18,174 | ✗ NO (filter excludes) |
| D: aggregate with ECOM/POS markers | 166 | 6,504 | ✗ no (correctly excluded — double-count) |
| E: other (mostly merchant-ID transit, misc) | 65 | 81,739 | ✗ no (mixed, mostly aggregate sweeps) |

Pipeline captured = A+B = **10,674 ₾** → matches the -27% shortage figure. ✓

**2024-08 (CONTROL)** — total credit rows = 703, sum = 177,066 ₾:
| bucket | rows | sum ₾ | captured by pipeline? |
|---|---:|---:|---|
| A: terminal-ID rollup, small (SH060853, RS014189) | 585 | 6,724 | ✓ yes |
| B: terminal-ID rollup, >50 ₾ | 16 | 1,108 | ✓ yes |
| C: merchant-ID ნავაჭრი, per-tx | 40 | 43,156 | ✗ no (double-count of rollups — Sprint 5.2 exclusion) |
| D: aggregate sweeps | 5 | 21,710 | ✗ no (double-count) |
| E: other | 57 | 104,368 | ✗ no (aggregate sweeps) |

Pipeline captured = A+B = **7,832 ₾** → matches RS.ge truth (7,913 ₾) and audit (6,697 ₾ × 1.18 = 7,902 ₾). ✓

**Key contrast**: In 2023-08 the terminal-ID-tagged rollups exist ONLY for RS014189 (not for SH046092 / SH034467). The SH046092 / SH034467 transactions are only represented via merchant-ID-tagged navachri rows — which we correctly exclude in normal months (where they double-count rollups) but which carry legitimate per-transaction amounts in the 8 shortage months (where terminal-ID rollups for those terminals don't exist).

### 3. RS.ge source-of-truth (official POS export)

Script: `_scratch_sprint5_12_pos_per_month.py`

| month | TBC RS.ge | terminal breakdown |
|---|---:|---|
| 2023-08 | 17,448 | RS014189:9,394 · SH046092:6,866 · SH034467:1,187 |
| 2023-09 | 16,323 | SH046092:10,629 · RS014189:5,694 |
| 2023-10 | 13,796 | SH046092:9,739 · RS014189:4,057 |
| 2023-11 | 18,141 | SH046092:10,507 · RS014189:7,633 |
| 2023-12 | 13,529 | SH046092:9,251 · RS014189:4,278 |
| 2024-01 | 11,629 | SH046092:8,472 · RS014189:3,157 |
| 2024-02 | 8,692  | SH046092:7,422 · RS014189:1,270 |
| 2024-03 | 10,837 | SH046092:7,557 · RS014189:3,280 |
| 2024-04 | 11,553 | RS014189:6,643 · SH046092:4,910 |
| 2024-05 | 6,109  | RS014189:3,361 · SH046092:2,748 |
| 2024-08 | 7,913  | SH060853:4,613 · RS014189:3,299 |
| 2025-08 | 37,221 | SH079927:24,530 · RS014189:12,691 |

**Shortage window RS.ge cumulative**: **110,394 ₾**. Pipeline captured across those 8 months: **~37,160 ₾** (34% coverage). Audit captured (NET × 1.18): **~112K ₾ gross ≈ RS.ge**.

**Pattern confirmation**: SH046092's RS.ge turnover is significant in every shortage month but **zero rows with "SH046092" in text appear in TBC statement** for those months. Starting 2024-04, TBC begins embedding terminal IDs in rollup rows for all active terminals.

---

## Why no fix is being shipped in this sprint

Three candidate fixes were considered:

1. **Include ALL merchant-ID navachri rows** — would re-introduce the 8.3× double-count fixed by Sprint 5.2. In 2024-08 this would balloon pipe_tbc from 7,832 to 64,000+ against RS.ge truth of 7,913. **REJECTED: regression risk too high.**

2. **Time-gated merchant-ID inclusion** (only apply to 2023-08 → 2024-03 rows) — introduces a magic date window in production code with no semantic justification beyond "TBC changed their statement format". Requires ongoing maintenance (if TBC changes format again, window expires silently). **REJECTED: brittle.**

3. **Per-row discriminator** — detect per-transaction navachri rows (small amount + merchant-ID prefix + no aggregate markers) vs aggregate sweeps. The 8-bucket forensic analysis above shows the signatures overlap substantially: 2024-08's C-bucket (small per-tx navachri, 43K ₾) and 2023-08's C-bucket (small per-tx navachri, 18K ₾) look identical structurally. **REJECTED: unsafe — cannot distinguish without ground truth.**

All three risk regressing 36 currently-correct months to "fix" 8 outlier months representing ~15% of TBC-POS coverage for those months.

**Chosen path: evidence-only, document in CONTEXT_HANDOFF.**

---

## Updated audit-defense framing

From `CONTEXT_HANDOFF.md` audit-defense view (this sprint sharpens the TBC line):

- **Real gap (audit methodology, net): 742K ₾** — unchanged.
- **Pipeline independently verifies +90K net / +107K gross** — unchanged.
- **Remaining ~652K explained entirely by pipeline coverage gaps** (no methodological disagreement):
  - MAX POS Excel files missing: 2022-10..12 + 2023-01..05 (8 months)
  - BOG bank statements missing: 2023-Q1 (3 months)
  - **TBC statement format pre-2024-04** (8 months, ~52K): Sprint 5.12 evidence confirms TBC embedded only RS014189's terminal ID in rollup rows; SH046092/SH034467 transactions posted to transit-IBAN with merchant-ID tags only. Our Sprint 5.2 terminal-ID filter correctly excludes them to prevent double-counting in later months. Audit's own TBC figure (from RS.ge export ÷ 1.18) correctly captures these.

For the auditor: **"TBC shortage 2023-08 → 2024-03 is explainable. TBC bank's statement text format for transit-IBAN rows changed in 2024-04 to embed physical terminal IDs. Before that change, the per-transaction rows for SH046092 and SH034467 terminals were only visible via merchant-ID tags. Our terminal-ID-based filter (Sprint 5.2, which fixed an 8.3× double-count from transit-IBAN aggregates) does not include merchant-ID-only rows because doing so would re-introduce double-counting in months where both tag styles coexist. Audit's figure (computed independently from RS.ge's official POS export) correctly captures these transactions; the pipeline's +90K ₾ figure is an independent cross-check, not a competing claim."**

---

## Files produced (all scratch, gitignored)

- `_scratch_sprint5_12_tbc_probe.py` — per-month row/sum/terminal-match counts for 8 shortage months
- `_scratch_sprint5_12_tbc_probe.json` — structured output
- `_scratch_sprint5_12_tbc_compare.py` — IBAN distribution comparison (shortage vs control)
- `_scratch_sprint5_12_pos_per_month.py` — RS.ge source-of-truth per month
- `_scratch_sprint5_12_row_forensics.py` — 5-bucket row classification
- `_scratch_sprint5_12_pos_terminal_sheet.py` — validate terminal-ID list against RS.ge export

## Scope of this sprint

- NO production code changed
- NO prompt changes
- NO test changes
- NO data.json regeneration needed
- CONTEXT_HANDOFF.md audit-defense view updated with Sprint 5.12 diagnosis
