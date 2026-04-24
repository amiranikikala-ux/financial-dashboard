# Sprint 3.8 — 📉 Margin Compression Radar — PREVIEW

**Status**: `PREVIEW · NO CODE CHANGE`
**Date**: 2026-04-25
**Target sprint**: Phase 3.8 (per `AI_GENIUS_PARTNER_PLAN.md:233`)
**Companion to**: Phase 2.3 `mix_analyzer` (`533c02f`), Phase 2.9 `detect_trends` (`84faa43`)

---

## TL;DR

`mix_analyzer`-მა გვითხრა **"სად ვართ ახლა"** (snapshot DRAG/LIFT), `detect_trends`-მა გვითხრა **"რა შეიცვალა მხოლოდ წინა თვე vs ახლა"** (single-period decomposition). მესამე კითხვაზე — **"რომელი კატეგორიის მარჟა კარგავს სიმაღლეს თანმიმდევრულად რამდენიმე თვის განმავლობაში?"** — პასუხი არცერთს არ აქვს.

`margin_radar` წაიკითხავს `retail_sales.by_category_by_month` (10,882 row, 645 category, 2024-07 → 2026-02) → window ბოლო 6 თვე → per-canonical-category Δgm_pp slope → revenue-weighted compression score → top-N 🔴 COMPRESSING / 🟢 EXPANDING / 🔒 PROTECTED-INFO.

ცოცხალი მონაცემი ადასტურებს რომ tool საჭიროა: 6-month window-ში **10 კატეგორია** გადის filter-ებს, ყველაზე მძიმე compression: სიგარეტი **−6.29pp** (protected → informational), მინერალური წყალი **−6.69pp**, ენერგეტიკული **−4.62pp**, წყალი **−3.74pp**, ლუდი **−2.44pp**.

Single session-ში მოთავსება შესაძლებელია: ~450 line code + ~450 line test, mix_analyzer-ის template ზუსტად მუშაობს. Per-store mode გადადის v2-ში (pipeline change საჭიროა — by_category_by_month-ს object_breakdown არ აქვს).

---

## Inventory — რა წავიკითხე, რა ვიპოვე

### 1. Data shape (live evidence)

`rs-dashboard/public/data.json` → `retail_sales.by_category_by_month`:
- **10,882 row, 645 unique category, periods 2024-07 → 2026-02**
- per-row fields: `month`, `category`, `normalized_category`, `revenue_ge`, `cost_ge`, `profit_ge`, `gross_margin_pct`, `total_quantity`, `row_count`
- ❗ **`object_breakdown` ვერ მოიპოვება per-month rows-ში** — only in `by_category` snapshot. Per-store margin radar v1-ში ვერ შემოვა (v2 deferred — pipeline regen საჭიროა).

### 2. Live margin compression candidates (window 2025-09 → 2026-02, 6 months)

```
category                              gm_2025-09  gm_2026-02       Δpp     rev_now  comp_score
─────────────────────────────────────  ──────────  ──────────  ────────  ──────────  ──────────
სიგარეტი                                   15.55        9.26     -6.29      30,560     192,276 🔒 PROTECTED
კოლა                                       14.32       12.54     -1.78       5,351       9,500
0904 | მინერალური წყალი                    12.57        5.88     -6.69       1,417       9,482
ენერგეტიკული სასმელი                       17.72       13.10     -4.62       1,485       6,854
0105 | ლუდი ქართული                        12.35        9.91     -2.44       2,276       5,560
წყალი მინერალური                           18.15       14.42     -3.74       1,366       5,104
უცნობი კატეგორია                           20.08       18.66     -1.42       2,709       3,848
0905 | წვენი                               13.37       12.59     -0.78       1,335       1,039
1302 | ყავა ნალექიანი                      13.71       13.73     +0.01       1,092           0  (expanding)
ჩიფსი                                      12.36       13.93     +1.57       1,384           0  (expanding)
```

Filter criteria რომელიც გამოვიყენე:
- ≥4 of 6 months ბოლოში მონაცემები (skipping spotty categories)
- gross_margin_pct ∈ [-5%, 90%] (mirror `trend_detector.SUSPICIOUS_MARGIN_PCT_*` band)
- current-period revenue ≥ 1,000 ₾ (noise floor)

**Verdict**: სიგნალი ცოცხალია. Cigarettes-ის −6.29pp ყველაზე მძიმე ღონეა, magnitudes-ით 20× მეორე ადგილზე. Protected handling ერთადერთი გზაა — სხვაგვარად AI შესთავაზებს cigarettes-ის შემცირებას.

### 3. Existing modules studied

| File | რა წავიკითხე | რას ვიყენებ template-ად |
|---|---|---|
| `dashboard_pipeline/ai/mix_analyzer.py` (755 line) | `_canonicalize_protected`, `_compute_portfolio`, argument coercion, summary_ka builder | full structural template + REUSE `_canonicalize_protected` |
| `dashboard_pipeline/ai/trend_detector.py` (375 line) | `_index_by_period`, `_prev_period`, `_safe_div`, `SUSPICIOUS_MARGIN_PCT_*`, `MIN_REVENUE_FOR_COMPARISON_GE` | window/period helpers + suspicious filter |
| `dashboard_pipeline/ai/tools.py:2375-2483` (`MIX_ANALYZER_TOOL`) | schema structure: triggers, anti-triggers, returns, honesty rule | tool schema template |
| `dashboard_pipeline/ai/tools.py:2912-2923` (dispatcher branch) | `analyze_category_mix` dispatcher pattern | dispatcher branch template |
| `dashboard_pipeline/constants.py:125-153` | `USER_TARGET_GROSS_MARGIN_PCT`, `PROTECTED_CATEGORY_SUBSTRINGS`, `MIX_ANALYZER_*` | new constants pattern |
| `tests/test_ai_mix_analyzer.py` (504 line) | 21-test pattern — fixtures, _make_loader, hand-computed assertions | full test template |
| `tests/test_ai_trend_detector.py` (304 line) | period-based fixture pattern + suspicious filter tests | secondary test template |

### 4. Blast radius (grep-based; gitnexus index stale post-533c02f)

**Files importing/calling `analyze_category_mix`** (the "what does mix_analyzer talk to" baseline):
- `dashboard_pipeline/ai/tools.py` (dispatcher only)
- `tests/test_ai_mix_analyzer.py` (tests only)

**Files importing/calling `detect_trends`**:
- `dashboard_pipeline/ai/tools.py` (schema + dispatcher)
- `tests/test_ai_trend_detector.py`, `tests/test_ai_agent.py`, `tests/test_ai_co_designer.py`, `tests/test_ai_tools.py`
- doc files (`CONTEXT_HANDOFF.md`, `PHASE_STATUS_MATRIX.md`, `PLAN.md`)

**Files importing `PROTECTED_CATEGORY_SUBSTRINGS`**:
- `dashboard_pipeline/constants.py` (definition)
- `dashboard_pipeline/ai/mix_analyzer.py` (only consumer today)
- `tests/test_ai_mix_analyzer.py`
- `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_2_3_MIX_ANALYZER_PREVIEW.md`

**`_canonicalize_protected` callers**: only `mix_analyzer.analyze_category_mix` itself. Currently module-private (`_` prefix), not in `__all__`.

**`retail_sales.by_category_by_month` consumers**: `trend_detector.detect_trends` only.

**Risk verdict**: **LOW**. New file, new test file, additive constants, additive tool slot. No modifications to existing tool behavior. Two existing modules need read-only inspection (constants + canonicalization helper); no signatures change.

---

## Architecture decision

### File structure

```
dashboard_pipeline/ai/margin_radar.py              # NEW ~450 lines
tests/test_ai_margin_radar.py                       # NEW ~450 lines, ~16 tests
dashboard_pipeline/constants.py                     # +5 constants
dashboard_pipeline/ai/tools.py                      # +MARGIN_RADAR_TOOL schema + dispatcher branch
dashboard_pipeline/ai/mix_analyzer.py               # +1 line: add `_canonicalize_protected` to __all__ (publish for reuse)
```

### Public function

```python
def analyze_margin_compression(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    window_months: Any = None,        # default 6, range 3..12
    top_n: Any = None,                # default 5, range 3..15
    target_gross_margin_pct: Any = None,  # optional — informational target line
    protected_override: Any = None,   # same semantics as mix_analyzer
    today: Optional[date] = None,
) -> Dict[str, Any]: ...
```

### Compression score formula

For each canonicalized category with ≥`MIN_MONTHS_IN_WINDOW` (=3) data points:

```
gm_first  = gm at earliest available month in window
gm_last   = gm at latest available month in window
delta_pp  = gm_last - gm_first                       # negative = compression
rev_recent = avg revenue over latest 2 months in window  (smoothing)
score     = abs(min(delta_pp, 0)) * rev_recent         # only compression contributes
```

Rationale: revenue-weighting prevents tiny-revenue noise from dominating ("a 30pp drop on 100₾ ≪ a 2pp drop on 100K₾"). Two-month average for `rev_recent` smooths December/January seasonality.

Categories sorted by `score` desc → top-N go into `compressing_categories[]`. Categories with `delta_pp > +1pp` AND meeting share floor → `expanding_categories[]` (sorted by `delta_pp` desc).

### Protected handling (key safety rule)

Same `_canonicalize_protected` used by mix_analyzer. After canonicalization, protected entries computed separately and surfaced in `protected_info[]` field — they are **visible** (compression score shown) but **never** appear in `compressing_categories[]`. AI sees them as informational signal ("cigarettes margin is compressing −6.29pp — known protected business decision; flag to user but don't recommend reduction").

### Return contract

```python
{
    "source": "data.json:retail_sales.by_category_by_month",
    "as_of_date": "YYYY-MM-DD",
    "window": {
        "months": int,                       # actual window size
        "start_period": "YYYY-MM",
        "end_period": "YYYY-MM",
    },
    "categories_evaluated": int,
    "categories_skipped_thin_data": int,     # < MIN_MONTHS_IN_WINDOW
    "categories_skipped_suspicious": int,
    "target_gross_margin_pct": float | None,
    "compressing_categories": [
        {
            "category": str,
            "raw_label": str,
            "gm_first_pct": float,
            "gm_last_pct": float,
            "delta_pp": float,                # negative
            "revenue_recent_ge": float,
            "compression_score": float,
            "months_in_window": int,
            "flag": "🔴 COMPRESSING",
        }, ...
    ],
    "expanding_categories": [
        # same shape, delta_pp positive, flag = "🟢 EXPANDING"
    ],
    "protected_info": [
        {
            "canonical_label": str,
            "raw_labels": [str, ...],
            "gm_first_pct": float,
            "gm_last_pct": float,
            "delta_pp": float,
            "revenue_recent_ge": float,
            "compression_score": float,
            "reason_ka": str,
            "flag": "🔒 PROTECTED",
        }, ...
    ],
    "summary_ka": str,
    "notes": [str, ...],
}
```

Failure path: `{"error": "<Georgian>", "hint": "<actionable>"}` — same convention as mix_analyzer.

### Anti-triggers (in tool schema description)

- snapshot mix rebalance → `mix_analyzer`
- single-period MoM/YoY decomposition → `detect_trends`
- per-SKU margin drill → `analyze_product_profitability`
- promotion candidate list → `find_promotion_candidates`
- future scenario simulation → `simulate_scenario`

---

## Constants to add (`dashboard_pipeline/constants.py`)

```python
# Margin Compression Radar (Phase 3.8)
MARGIN_RADAR_DEFAULT_WINDOW_MONTHS = 6
MARGIN_RADAR_MIN_WINDOW_MONTHS = 3
MARGIN_RADAR_MAX_WINDOW_MONTHS = 12
MARGIN_RADAR_MIN_MONTHS_IN_WINDOW = 3       # need ≥3 data points to call it a trend
MARGIN_RADAR_MIN_REVENUE_FOR_TRACKING_GE = 1000.0  # noise floor on rev_recent
MARGIN_RADAR_EXPANSION_THRESHOLD_PP = 1.0    # delta_pp > +1pp → "expanding" (avoid noise)
```

---

## Risks / pitfalls (5)

| # | რისკი | რა ხდება | მიტიგაცია |
|---|---|---|---|
| 1 | **Zero-floor / negative-margin extrapolation** | კატეგორია 5% → -2% → -10% sequence არსებობს — extrapolate ვერ შეიძლება (loss-making business model არ არის "მარჟის შემცირება") | არ ვაკეთებ slope projection — მხოლოდ raw delta_pp (gm_first - gm_last). `notes_ka`-ში ვაფრთხილებ რომ delta_pp არის historical, არ არის forecast. |
| 2 | **Protected cigarettes ცოცხალი მონაცემით ყველაზე მძიმე compression-ს გვიჩვენებს (−6.29pp)** | Without canonicalization, AI იტყვის "cut cigarettes" — user-ის protected business rule-ის ანტისიგნალია | `_canonicalize_protected` reuse + protected entries `protected_info[]`-ში ცალკე bucket-ში; `summary_ka` ცალკე უხსნის "🔒 cigarettes compressing −Xpp — protected, informational only" |
| 3 | **Per-store mode v1-ში არ შემოვა** | mix_analyzer-ს store=ოზურგეთი/დვაბზუ აქვს, radar-ს არ ექნება — UX inconsistency | `by_category_by_month`-ს object_breakdown არ აქვს. Honest about it: tool schema-ში ცალსახად ვიწერ "portfolio-level only (per-store გადავიდა v2-ში — pipeline change required)". v2 = სცალკე sprint, აქ არ ვცადოთ. |
| 4 | **Spotty data — short categories (≤2 months)** | 645 category-დან მხოლოდ 10 გადის filter-ებს (≥4 months) — არჩევნი short-tail-ისგან protect | `MARGIN_RADAR_MIN_MONTHS_IN_WINDOW=3` constant + `categories_skipped_thin_data` count return-ში; `summary_ka` ცალკე იტყვის "X კატეგორია გამოტოვდა მონაცემთა სიმცირის გამო" |
| 5 | **Window-ის arbitrary არჩევანი** | 6 months default — წინა წლის ანალოგიური თვე ერთი წერტილიც არ ჩავა, sustainable trend missed | window range 3..12 + tool schema-ში `window_months` parameter exposed; default 6 (კვარტალური ციკლის ნახევარი). `summary_ka`-ში ვიწერ რომელ window-ზეა output. |

---

## Scope recommendation

**DO IN SESSION:**
- `dashboard_pipeline/ai/margin_radar.py` (~450 line)
- `tests/test_ai_margin_radar.py` (~450 line, ~16 test)
- `dashboard_pipeline/constants.py` — 5 new constants
- `dashboard_pipeline/ai/tools.py` — MARGIN_RADAR_TOOL schema + dispatcher branch + TOOL_SCHEMAS slot 16 (after MIX_ANALYZER_TOOL, before PRODUCT_PROFITABILITY_XRAY_TOOL)
- `dashboard_pipeline/ai/mix_analyzer.py` — 1 line: add `_canonicalize_protected` to `__all__`
- live dog-food 1-2 scenarios (Sonnet 4.6 think=True): "რომელი კატეგორიის მარჟა კლებულობს?" + "ბოლო 3 თვის compression?"

**DEFER (separate sprint):**
- **v2 per-store mode** — requires pipeline change to add `object_breakdown_by_month` to `retail_sales.by_category_by_month` rows (touch `dashboard_pipeline/retail_sales.py` + regen data.json + per-store regression). Standalone risk-MED sprint.
- **v3 frontend "📉 Margin Health" tab** — combines mix_analyzer + margin_radar + detect_trends in one UI page. Separate UI sprint, requires React work — not appropriate for AI tool sprint.
- **SYSTEM_PROMPT_KA edits** — adding "margin_radar" to tool list reference. Done as final step ONLY if the live dog-food shows AI doesn't pick the new tool from schema description alone (mix_analyzer didn't need a prompt edit).

**Estimated session size**: ~1 session (1.5-2.5 hours focused work + dog-food). Comparable to Phase 2.3 mix_analyzer (533c02f) which was also single-session.

---

## Test plan (16 tests, mirror mix_analyzer's 21)

```python
# tests/test_ai_margin_radar.py

# ── Basic mechanics ──
1.  test_basic_compression_score_matches_handcomputed
2.  test_window_default_6_months_when_arg_omitted
3.  test_window_override_3_clamped_in_range
4.  test_window_override_99_clamped_to_max_12
5.  test_top_n_clamped_to_min_max_range

# ── Canonicalization & protected ──
6.  test_protected_cigarette_3_variants_merged_in_window
7.  test_protected_visible_in_protected_info_not_in_compressing
8.  test_no_compressing_entry_matches_protected_substring
9.  test_protected_override_empty_runs_unconstrained

# ── Compression / expansion classification ──
10. test_compressing_sorted_by_score_desc
11. test_expanding_only_when_delta_above_threshold
12. test_categories_with_fewer_than_min_months_skipped_and_counted
13. test_suspicious_margin_categories_excluded_and_counted

# ── Output contract & summary ──
14. test_summary_ka_cites_live_compression_score_not_memory
15. test_error_path_empty_by_category_by_month
16. test_error_path_missing_retail_sales_section

# ── Tool registry & dispatcher ──
(covered by extending tests/test_ai_tools.py:
 - tool count assertion 27 → 28
 - MARGIN_RADAR_TOOL present in TOOL_SCHEMAS
 - dispatcher routes "margin_radar" name to analyze_margin_compression)
```

Pattern reference: `tests/test_ai_mix_analyzer.py:1-504`.

---

## Files expected to change

| File | Change type | Lines (est.) |
|---|---|---|
| `dashboard_pipeline/ai/margin_radar.py` | **NEW** | ~450 |
| `tests/test_ai_margin_radar.py` | **NEW** | ~450 |
| `dashboard_pipeline/constants.py` | EDIT (+5 constants) | +12 |
| `dashboard_pipeline/ai/tools.py` | EDIT (+MARGIN_RADAR_TOOL + dispatcher branch + TOOL_SCHEMAS slot) | +110 |
| `dashboard_pipeline/ai/mix_analyzer.py` | EDIT (+1 entry in `__all__`) | +1 |
| `tests/test_ai_tools.py` | EDIT (tool count 27 → 28; presence assertion) | +5 |

**Untouched (verified)**: `generate_dashboard_data.py`, `retail_sales.py`, all VAT modules, all bank modules, all React/JSX, `SYSTEM_PROMPT_KA` (defer until dog-food shows need), all other AI tools.

---

## Self-check checklist (pre-commit)

- [ ] `npx gitnexus analyze` ჩატარდა (533c02f-ის შემდეგ index stale)
- [ ] `gitnexus_impact({target: "analyze_margin_compression", direction: "upstream"})` LOW დადასტურებული (NEW symbol — should be empty)
- [ ] `gitnexus_impact({target: "_canonicalize_protected", direction: "upstream"})` MED-ზე ქვემოთ (now 2 callers: mix_analyzer + margin_radar; verify mix_analyzer behavior unchanged)
- [ ] `gitnexus_detect_changes({scope: "staged"})` confirms only the 6 files above changed
- [ ] `pytest -q tests/test_ai_margin_radar.py tests/test_ai_mix_analyzer.py tests/test_ai_trend_detector.py tests/test_ai_tools.py` — all green
- [ ] `pytest -q` — full suite green (target 2,150/2,150 = 2,134 + 16 new)
- [ ] Live dog-food 1-2 scenarios on Sonnet 4.6 `think=True` (`_scratch_dogfood_*.py` pattern, no service restart needed)
- [ ] `protected_info[]` shows cigarettes with non-zero compression_score in live data — proves protected canonicalization works on real corpus
- [ ] `summary_ka` cites live numbers (not test fixtures) when run against real data.json
- [ ] **No `SYSTEM_PROMPT_KA` edit unless dog-food shows the new tool isn't being picked** (Phase 2.3 mix_analyzer was discoverable from schema alone)
- [ ] Two-commit SHA pin pattern if HANDOFF/PHASE_STATUS_MATRIX gets updated (per `feedback_sha_pin_two_commit_pattern.md`)

---

## Evidence sources

| What | Where |
|---|---|
| `mix_analyzer` template | `dashboard_pipeline/ai/mix_analyzer.py` (commit `533c02f`) |
| `detect_trends` template | `dashboard_pipeline/ai/trend_detector.py` (commit `84faa43`) |
| Constants pattern | `dashboard_pipeline/constants.py:125-153` |
| Tool schema pattern | `dashboard_pipeline/ai/tools.py:2375-2483` (MIX_ANALYZER_TOOL) |
| Dispatcher pattern | `dashboard_pipeline/ai/tools.py:2912-2923` |
| Test pattern (full) | `tests/test_ai_mix_analyzer.py` (504 line, 21 tests) |
| Test pattern (period helpers) | `tests/test_ai_trend_detector.py` (304 line) |
| Live data shape | `rs-dashboard/public/data.json` → `retail_sales.by_category_by_month` (10,882 rows × 645 categories × 2024-07..2026-02) |
| Live compression candidates | `_scratch` Python computation in this session — 10 categories pass filters, top: სიგარეტი −6.29pp (protected), მინერალური წყალი −6.69pp |
| Phase 3 plan slot | `AI_GENIUS_PARTNER_PLAN.md:233` |
| Companion preview (Phase 2.3) | `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_2_3_MIX_ANALYZER_PREVIEW.md` |

---

## Open questions for user

1. **Window default** — 6 months (default ჩემი წინადადება) საკმარისი იქნება, თუ 3 (კვარტალური) უფრო ბუნებრივი? სანამ კოდს დავიწყებ.
2. **Expansion threshold** — `EXPANSION_THRESHOLD_PP = +1pp` (above noise) ნორმალურია, თუ +2pp გვინდა (უფრო strict — only material expansion)?
3. **Tool name** — `margin_radar` სუფთაა, vs `analyze_margin_compression` (verb form, mix_analyzer-ის style). რომელი სახელი user-ისთვის?
4. **Dog-food scope** — 1 scenario საკმარისია მინიმალური დადასტურებისთვის, თუ 3 მინდა (compression / expansion / protected-info) Phase 2.3-ის სტილით?
