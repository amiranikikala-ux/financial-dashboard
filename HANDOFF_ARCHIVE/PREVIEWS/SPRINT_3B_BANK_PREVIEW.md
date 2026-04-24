# Sprint 3b — Bank section cache extension (evidence-only preview)

**Status**: **PREVIEW · NO CODE CHANGE**
**Date**: 2026-04-24
**Target sprint**: Tier 2 Sprint 3b (implementation in fresh session)
**Template**: `project_pipeline_cache_pattern.md` memory · commit `481e474` (Sprint 2 retail_sales)

---

## TL;DR

Bank section has **9 collector functions** called from `_collect_income_bundles()` in `generate_dashboard_data.py:349-459`. Unlike retail_sales (1 collector, many files), bank is **many collectors reading the same few files** — each TBC yearly xlsx (~2MB) is opened 4 times per run. Applying the Sprint 2 per-file cache template **per-collector** requires 9 refactors but gives each collector the same incremental-read behavior retail_sales already has. **Chosen minimal-diff path**: one cache key per `(file, collector)` pair, following the exact retail_sales shape — no unified reader refactor.

**Risk**: MED. Regression surface = totals, line counts, per-month summaries across 9 bundles. Mitigated by mirroring `tests/test_retail_sales_incremental.py` per collector.

**Scope recommendation**: start with **2 collectors only** (`collect_tbc_samurneo_flow` + `collect_bog_samurneo_flow`) — smallest, cleanest pair, samurneo merge is the simplest downstream step. Use that as proving ground before extending to the other 7.

---

## 1. Bank section inventory (entry points called from `generate_dashboard_data.py`)

| # | function | file input(s) | config input(s) | object_mapping? |
|---|---|---|---|---|
| 1 | `collect_tbc_card_income` | TBC yearly xlsx (5 files) | `tbc_card_income_patterns.json` (terminal_ids, label_ka) | **yes** |
| 2 | `collect_bog_pos_terminal_income` | BOG yearly xlsx | `bog_pos_terminal_income_patterns.json` | **yes** |
| 3 | `merge_pos_terminal_income` | — (merge) | `object_mapping` | yes |
| 4 | `collect_tbc_expense_categories` | TBC yearly xlsx | `tbc_expense_categories.json` | yes |
| 5 | `collect_bog_expense_categories` | BOG yearly xlsx | BOG expense categories config | yes |
| 6 | `collect_tbc_samurneo_flow` | TBC yearly xlsx | `tbc_samurneo_patterns.json` | no |
| 7 | `collect_bog_samurneo_flow` | BOG yearly xlsx | `tbc_samurneo_patterns.json` (shared) | no |
| 8 | `merge_samurneo_flows` | — (merge) | — | no |
| 9 | `collect_tax_flow` | **BOTH** TBC + BOG yearly xlsx | `tax_flow_patterns.json` + hardcoded `treasury_in_markers` | no |
| 10 | `collect_tbc_foodmart_cashback` | TBC yearly xlsx | hardcoded patterns (check source) | no |

**File-reader count**: 8 (merge_* excluded). Each TBC yearly xlsx is opened **4 times** per run (card_income + expense + samurneo + tax_flow + cashback — check cashback).

**Caching target**: 8 × ~5 yearly files = ~40 cache entries per run.

---

## 2. Output-shape fidelity audit (JSON-serializability)

All 8 collector bundles return plain dicts of `str`, `float`, `int`, `list[dict]`. No `pd.Timestamp`, no `set()`, no lambda/functools objects. **JSON-safe out of the box** — no shape-conversion refactor needed (big win vs retail_sales Sprint 2 which had to serialize dates as ISO strings).

Verified:
- Date fields (`"თარიღი"`) routed through `_excel_cell(row, date_col)` in `dashboard_pipeline/file_utils.py:175-181` which returns `str(v).strip()`. All values are strings.
- Amount fields (`"თანხა"`, `"expense_total_ge"`, etc.) are `float(pd.to_numeric(...))`. Plain Python floats.
- Line counts (`"expense_line_count"`) are `len(list)`. Plain ints.
- Preview lists (`"expense_rows_preview"`) are `list[dict[str, Union[str, float]]]`. Plain.
- Monthly summaries (`_monthly_summary(rows)` from `constants.py`) return dicts keyed by `YYYY-MM` string.

**Per-file payload shape** (proposed — identical to collector return shape, no conversion):

```python
# e.g. payload for (TBC 2023.xlsx, collect_tbc_samurneo_flow)
{
  "expense_total_ge": 12345.67,
  "return_total_ge": 4567.89,
  "net_ge": -7777.78,
  "expense_line_count": 42,
  "return_line_count": 8,
  "expense_rows_preview": [...full list at per-file fidelity...],
  "return_rows_preview": [...full list...],
  "expense_monthly_summary": {"2023-01": 1000.0, ...},
  "return_monthly_summary": {...},
}
```

**Pitfall** (per memory): `expense_rows_preview[:300]` truncation happens in the collector. For cache payload, store **full rows** (no truncation), then truncate at merge time. Same pattern as retail_sales `rows_preview`. This is the one real shape change.

---

## 3. Fingerprint inputs per collector

| collector | non-file inputs in fingerprint |
|---|---|
| `collect_tbc_card_income` | `tbc_card_income_patterns.json` (terminal_ids, label_ka) + `object_mapping` |
| `collect_bog_pos_terminal_income` | `bog_pos_terminal_income_patterns.json` + `object_mapping` |
| `collect_tbc_expense_categories` | `tbc_expense_categories.json` + `object_mapping` |
| `collect_bog_expense_categories` | BOG expense categories config + `object_mapping` |
| `collect_tbc_samurneo_flow` | `tbc_samurneo_patterns.json` |
| `collect_bog_samurneo_flow` | `tbc_samurneo_patterns.json` **(bug-worthy: shared config — BOG reads the TBC file)** |
| `collect_tax_flow` | `tax_flow_patterns.json` + hardcoded `default_patterns` list + `treasury_in_markers` list + `TAX_TREASURY_CLUSTER_NOTE_KA` constant |
| `collect_tbc_foodmart_cashback` | (inspect source for config) |

**Fingerprint helper** (proposed pattern mirroring `retail_sales._content_fingerprint`):

```python
def _content_fingerprint_bank_samurneo(patterns, include_all):
    return hashlib.sha1(json.dumps(
        {"patterns": sorted(patterns), "include_all": include_all},
        sort_keys=True, ensure_ascii=False
    ).encode()).hexdigest()
```

One fingerprint helper per collector. Each has a distinct seed so a config change for one bundle does NOT invalidate the cache entries of another.

**Noted for follow-up (not Sprint 3b scope)**: `collect_bog_samurneo_flow:166` reads `tbc_samurneo_patterns.json` (not a `bog_samurneo_patterns.json`). This may be intentional — shared pattern file — or a misnomer bug. Worth a separate inspection before Sprint 3b wires fingerprints, to avoid freezing a potential bug into the cache-invalidation model.

---

## 4. Merge-time vs per-file decisions

| aspect | per-file payload | merge-time logic |
|---|---|---|
| row list | full (no truncation) | truncate to `[:300]` for preview |
| totals | file-level sum | bundle-level sum = Σ file totals |
| line_count | file row count | bundle = Σ file counts |
| monthly_summary | per-file dict | merge month-keys, sum values per month |
| label_ka / ledger_note_ka | — (constants, merge-time only) | set at merge |

**Samurneo merge** (`merge_samurneo_flows`) already does this correctly at bundle level; per-file adds one more aggregation layer.

**Tax flow cross-bank nuance**: `collect_tax_flow` produces ONE bundle from BOTH TBC+BOG files but tags each row with `"ბანკი": "BOG"` or `"ბანკი": "TBC"`. Per-file cache works fine — the bank tag is row-level, not file-level. Each cached file payload is bank-homogeneous by construction (because `list_bog_bank_statement_xlsx()` and `list_tbc_bank_statement_xlsx()` return disjoint file sets).

---

## 5. Pitfalls (Sprint 3b-specific, beyond memory's generic list)

1. **Shared config path** — `collect_bog_samurneo_flow` currently reads `tbc_samurneo_patterns.json`. Fingerprint both collectors with the same config file sha. If the shared-file assumption is wrong, audit before wiring.
2. **`collect_tax_flow` is the only cross-bank collector** — it iterates `list_bog_bank_statement_xlsx()` AND `list_tbc_bank_statement_xlsx()`. Cache key must be the file path (which is already disjoint by directory), not the collector alone. Retail_sales pattern already handles this via normalized absolute paths.
3. **Sprint 5.12 sensitivity** — `collect_tbc_card_income` is the function that drives the 2023-08→2024-03 TBC shortage. Any change to its implementation (even a cache-refactor-only change) must produce byte-identical totals and line counts to the current output, or the 90K pipeline-independent gap number in `CONTEXT_HANDOFF.md` audit-defense view shifts. **Add a pin test** (`tests/test_tbc_card_income_cache_equivalence.py`) that asserts pre-cache vs post-cache output is dict-identical on the current `Financial_Analysis/თბს ბანკი ამონაწერი/` corpus.
4. **`_excel_cell` returns empty string `""` for NaN** — when reconstructing dates from cache, `""` is a valid cached value, not a bug. `_monthly_summary()` handles empty strings via its date-parsing guard.
5. **Yearly-file re-read on mid-year edit** — if 2023.xlsx gets one row appended mid-year, the entire file's fingerprint changes and all 4-5 collector payloads for that file re-run. This is fine (we want re-read on any change) but means cache-hit ratio is **per-file, not per-row**. For 5 yearly files at steady state, expect 1-2 files/week changing during the current year and 0 files/week for prior years.

---

## 6. Scope recommendation for Sprint 3b (one session)

**Do in session**:
- Refactor `collect_tbc_samurneo_flow` + `collect_bog_samurneo_flow` only (2 collectors)
- Add `_process_tbc_samurneo_file(path, patterns, include_all) → dict`
- Add `_process_bog_samurneo_file(path, patterns, include_all) → dict`
- Shared `_content_fingerprint_samurneo(patterns, include_all)` helper
- Wire `use_cache=True` at `_collect_income_bundles()` call site, **only** for these two collectors
- Add `tests/test_samurneo_incremental.py` mirroring `test_retail_sales_incremental.py` (7 tests: cold-equiv-hot, selective-re-read, new-file, deleted-file, corrupt-cache, fingerprint-invalidation, period-filter-bypass-if-applicable)
- Live-verify: adapt `_scratch_sprint2_cache_verify.py` to measure samurneo cold vs hot run-time

**Deferred to Sprint 3c / 3d / 3e**:
- `collect_tax_flow` (cross-bank, most complex fingerprint)
- `collect_tbc_card_income` + `collect_bog_pos_terminal_income` (Sprint 5.12-sensitive; needs extra pin test)
- Expense categories × 2 (largest config fingerprint, most noise during development)
- Foodmart cashback (smallest; easy follow-up)

**Rationale**: samurneo is the smallest bundle (fewest fields, no object_mapping dep, simplest merge). Proving the pattern on the lowest-risk pair means the remaining 6 collectors copy a known-good template rather than inventing + debugging in parallel. Also means Sprint 3b ends with real value delivered even if the session runs long — not an "abandoned half-refactor" footprint.

---

## 7. Test plan (mirror retail_sales pattern — 7 tests)

File: `tests/test_samurneo_incremental.py`

| # | name | assertion |
|---|---|---|
| 1 | `test_cold_equals_hot` | collect_*_samurneo_flow(use_cache=False) output == collect_*_samurneo_flow(use_cache=True) output for both TBC and BOG, 1st run matches 2nd run |
| 2 | `test_selective_reread` | mtime-touch one file, re-run with cache; only that file's `_process_*_samurneo_file` was called (assert via mock/side_effect) |
| 3 | `test_new_file_appended` | add synthetic xlsx to tmp fixture dir, re-run; cache grows by one entry with matching payload |
| 4 | `test_deleted_file_dropped` | remove a file from fixture dir, re-run; cache shrinks — no stale entry |
| 5 | `test_corrupt_cache_falls_back` | write garbage JSON to cache path; collector runs cold, regenerates cache |
| 6 | `test_fingerprint_change_invalidates` | mutate `tbc_samurneo_patterns.json` (change `include_all`), re-run; all cache entries regenerate |
| 7 | `test_period_filter_bypasses_cache` | if samurneo supports period filter, verify filtered call doesn't touch cache (if no period filter support, drop this test) |

**Total expected test count after Sprint 3b**: `2,073 + 7 = 2,080` pytest green.

---

## 8. Self-check before Sprint 3b implementation closes

Pre-commit checklist:
- [ ] `gitnexus_impact({target: "collect_tbc_samurneo_flow", direction: "upstream"})` — confirm no HIGH/CRITICAL risk
- [ ] `gitnexus_impact({target: "collect_bog_samurneo_flow", direction: "upstream"})` — same
- [ ] Cold vs cache-hit totals match to 0.00 ₾ (not just "close")
- [ ] Samurneo bundle Excel export unchanged (download_dir .xlsx has identical rows)
- [ ] `gitnexus_detect_changes({scope: "staged"})` shows only expected symbols touched
- [ ] 2,080/2,080 pytest green
- [ ] `_scratch_sprint3b_cache_verify.py` confirms hot is ≥2× faster than cold on the current corpus

---

## 9. Files expected to change in Sprint 3b (bank-samurneo-only scope)

| file | change |
|---|---|
| `dashboard_pipeline/bank_income.py` | add `_process_tbc_samurneo_file`, `_process_bog_samurneo_file`, `_content_fingerprint_samurneo`; refactor `collect_tbc_samurneo_flow` + `collect_bog_samurneo_flow` to accept `use_cache`, `cache_path` kwargs and use per-file cache path |
| `generate_dashboard_data.py:409-411` | pass `use_cache=True, cache_path=...` to both samurneo calls |
| `tests/test_samurneo_incremental.py` | NEW — 7 integration tests |
| `_scratch_sprint3b_cache_verify.py` | NEW — adapts Sprint 2's cache_verify pattern |

**No changes to**:
- `pipeline_cache.py` (template is already correct — reuse as-is)
- Other bank collectors (Sprint 3c/3d/3e scope)
- `data.json` shape (per-file cache is internal; bundle output unchanged)
- Any AI tool, frontend, prompt, or test outside the samurneo pair

---

## Evidence sources

- `dashboard_pipeline/bank_income.py` — collector function bodies (lines 111-533)
- `generate_dashboard_data.py:349-459` — `_collect_income_bundles` orchestration
- `dashboard_pipeline/retail_sales.py:241-258` + `:1120+` — `_content_fingerprint` + cache wiring pattern
- `dashboard_pipeline/pipeline_cache.py` — generic cache utility (used as-is)
- `dashboard_pipeline/file_utils.py:175-181` — `_excel_cell` confirms all date fields are stringified
- `tests/test_retail_sales_incremental.py` — 8 existing tests to mirror
- `_scratch_sprint2_cache_verify.py` — live-verify script template
- `project_pipeline_cache_pattern.md` memory — authoritative template
