# Phase 2.3 — Mix Analyzer (evidence-only preview)

**Status**: **PREVIEW · NO CODE CHANGE**
**Date**: 2026-04-24
**Target sprint**: Phase 2.3 (implementation in fresh session)
**Template**: `project_business_targets.md` memory · `product_profitability.py` (Phase 2.5) tool pattern

---

## TL;DR

Phase 2.3 was originally scoped in `AI_GENIUS_PARTNER_PLAN.md:183` as **"📊 Industry Benchmark"** using external data. The user explicitly rejected this framing on 2026-04-22: "no Georgian retail data source, not actionable." The memory `project_business_targets.md` reframes it to **`mix_analyzer`** — a tool that answers "how do I move portfolio gross margin from current level to 20% by tilting category mix, holding cigarettes constant?" This preview scopes the reframed tool.

The data source is ready: `retail_sales.by_category` (645 entries) already carries `revenue_ge / cost_ge / profit_ge / gross_margin_pct / object_breakdown`. Portfolio margin computation is a 10-line weighted average; target-gap math is a constrained optimization the user can reason about in plain terms ("hold cigarettes at current share, tilt 3% revenue from low-margin bread into drinks"). No external data. No new pipeline stage.

**Risk**: MED-HIGH. Not cache-style mechanical refactor — this ships strategic recommendations to a user who trusts them. Mis-categorizing cigarettes (they appear as 3 separate rows in `by_category`!) or mis-computing "required lift" would erode trust per `user_project_meaning.md`.

**Scope recommendation**: DO the tool in one session, but **explicitly punt two sub-pieces** — the `user_targets.json` config (hardcode in constants for v1) and any frontend surface. Text-mode AI-tool only. Frontend and config persistence are a follow-up.

---

## 1. Inventory — what lives where today

### 1.1 Data source (ready, no pipeline change)

`rs-dashboard/public/data.json` → `retail_sales.by_category` (645 entries):

```json
{
  "category": "0804 | სიგარეტი",
  "normalized_category": "0804 | სიგარეტი",
  "row_count": 129089,
  "total_quantity": 126176.0,
  "revenue_ge": 833634.82,
  "cost_ge": 750830.74,
  "profit_ge": 82804.08,
  "gross_margin_pct": 9.93,
  "distinct_product_count": 223,
  "distinct_month_count": 33,
  "date_range": {"min": "2023-06-14", "max": "2026-02-27"},
  "object_breakdown": [
    {"object": "ოზურგეთი", "revenue_ge": 828828.32, "gross_margin_pct": 9.95, ...},
    {"object": "დვაბზუ",   "revenue_ge":   4806.50, "gross_margin_pct": 7.46, ...}
  ]
}
```

**Live numbers (post-Sprint 3f regen, data.json commit 22c5ac5-ish era):**
- Portfolio GM (weighted avg): **14.96%** — memory says 10% (stale; likely pre-Sprint 5.5 revenue fix)
- Portfolio revenue: 4,336,426 ₾
- Portfolio profit: 648,932 ₾

**Cigarette detection anomaly (IMPORTANT):**
3 separate `by_category` rows match `"სიგარეტ"`:
- `"0804 | სიგარეტი"`: 833,635 ₾ (9.9% margin)
- `"სიგარეტი"` (unlabeled code): 633,672 ₾ (11.3% margin)
- A third smaller variant

Combined: **1,468,578 ₾ = 33.9% of portfolio revenue at 10.53% blended margin.** `normalized_category` is the raw label; 0 normalization rules deduplicate cigarette variants today. The tool must detect and merge by label-substring before applying "protected" rule — otherwise mix rec will propose cutting one cigarette label while preserving another.

### 1.2 User targets (no config file exists yet)

Per memory `project_business_targets.md`:
- Overall GM target: **20%** (current 14.96% → gap **+5.04pp**)
- AP per shop: **~2,000 ₾** (separate tool scope, not mix_analyzer)
- Protected category: **cigarettes** (hold revenue/share constant)
- Per-category approx margins memory provided: პური 10%, ნაყინი 20%, სასმელი 30%, ჩიფსები 15-25%, სიგარეტი 6%

**Note:** memory's stated margins drift from live data (live cigarette = 10.53%, not 6%; live ice-cream category = 18.1%, memory said 20%). Live numbers are authoritative; memory is the *direction* user cares about. Tool MUST cite live numbers, not memory's approximations.

No `user_targets.json` exists in `Financial_Analysis/`. For Phase 2.3 v1: **hardcode targets in `dashboard_pipeline/constants.py`** as `USER_TARGET_GROSS_MARGIN_PCT = 20.0` + `PROTECTED_CATEGORY_SUBSTRINGS = ("სიგარეტ", ...)`. Config-file externalization is a later sprint once the targets settle.

### 1.3 Tool-surface registration (mechanical, ~40 lines new)

`dashboard_pipeline/ai/tools.py`:
- Line 2375-2402: `TOOL_SCHEMAS` list — currently 26 entries. Append `MIX_ANALYZER_TOOL`. Add `cache_control` lands via `get_cached_tool_schemas()` automatically (last entry gets the marker).
- Tool-dispatcher `elif name == "mix_analyzer":` block near line 2788-2820 style.
- Schema block itself — mirror `PRODUCT_PROFITABILITY_XRAY_TOOL` (line 1883-1970): Triggers, Anti-triggers, Returns, Honesty rule, input_schema with `top_n`, `store`, optional `protected_override`.

`dashboard_pipeline/ai/prompts.py`:
- `SYSTEM_PROMPT_KA` has per-tool sections. Cross-reference existing tool listings near lines 342-344 + 978-982 (analyze_product_profitability / find_promotion_candidates / detect_trends already cross-reference each other). Add mix_analyzer to that cross-reference set so the AI disambiguates correctly.

### 1.4 Existing Phase 2.5 pattern (authoritative reference)

`dashboard_pipeline/ai/product_profitability.py` (470 lines) is the exact shape for a Phase 2.x tool:
- Public constants at top (thresholds, flag labels, SOURCE_LABEL)
- `_portfolio_margin_pct(qualified)` helper — already computes what mix_analyzer needs
- `summary_ka` always surfaced verbatim
- `notes` list for caveats
- `error` / `hint` fallback contract
- Input validation via `_validate_*` helpers
- Returns a plain JSON-safe dict

**Reuse target**: mix_analyzer imports `_portfolio_margin_pct` if exposed, or copies the 3-line function. No need to touch Phase 2.5 code.

### 1.5 sector_benchmarks.json — decision

`Financial_Analysis/sector_benchmarks.json` exists with `gross_margin_pct: {low: 15, median: 25, high: 40}`. This is the OLD Phase 2.3 framing's data source.

**Decision for reframed mix_analyzer:**
- DO NOT pivot analysis on sector numbers (they're unreliable per user).
- DO reference them in `summary_ka` as *context* after the user's-target-driven recommendation, e.g. `"თქვენი მიზანი 20% — ქართულ სექტორში მედიანა ~25%, ორიენტირად მისაღებია"`. That way the external benchmark isn't the driver, but it isn't wasted either.

---

## 2. Output-shape contract (proposed)

Return on success:

```python
{
    "source": "data.json:retail_sales.by_category",
    "as_of_date": "YYYY-MM-DD",
    "store": "total" | "ოზურგეთი" | "დვაბზუ",
    "top_n": int,  # how many categories to surface in each bucket

    # Current portfolio state
    "portfolio": {
        "revenue_ge": float,
        "profit_ge": float,
        "gross_margin_pct": float,  # weighted average
        "category_count": int,
    },

    # Target state
    "target": {
        "gross_margin_pct": 20.0,
        "gap_pp": float,            # target − current (signed)
        "gap_profit_ge": float,     # absolute profit uplift needed at current revenue
    },

    # Categorized by role in mix optimization
    "protected_categories": [
        # e.g. cigarettes — canonicalized (cigarette variants combined)
        {
            "canonical_label": "სიგარეტი",
            "raw_labels": ["0804 | სიგარეტი", "სიგარეტი", ...],
            "revenue_ge": float,
            "profit_ge": float,
            "gross_margin_pct": float,
            "portfolio_share_pct": float,
            "reason_ka": "მომხმარებლის გადაწყვეტილება — კარგად გასაყიდი, უცვლელი რჩება",
        },
    ],
    "drag_categories": [       # low margin × significant share; dilute portfolio GM
        {"category": str, "revenue_ge": float, "gross_margin_pct": float,
         "portfolio_share_pct": float, "flag": "🔴 DRAG"},
    ],
    "lift_categories": [       # high margin × under-indexed; mix tilt target
        {"category": str, "revenue_ge": float, "gross_margin_pct": float,
         "portfolio_share_pct": float, "flag": "🟢 LIFT"},
    ],

    # Actionable recommendation (what to do)
    "recommended_shifts": [
        {
            "action_ka": "გაზარდე X კატეგორიის წილი Y%-ით",
            "from_category": str,       # drag (e.g. bread)
            "to_category": str,         # lift (e.g. drinks)
            "revenue_shift_ge": float,  # how many ₾ of revenue to tilt
            "gm_impact_pp": float,      # expected portfolio GM lift
        },
    ],
    "projected_portfolio": {
        "if_all_recommendations_applied": {
            "gross_margin_pct": float,
            "delta_pp": float,
            "reaches_target": bool,
        },
    },

    "summary_ka": str,     # 3-5 Georgian sentences — ALWAYS verbatim surfaced
    "notes": [str, ...],   # caveats (canonicalization, stale data, etc.)
}
```

On failure:

```python
{"error": "<Georgian message>", "hint": "<actionable hint>"}
```

---

## 3. Algorithm — what the tool computes

1. **Read** `retail_sales.by_category` from data.json (via existing `read_data_json` helper pattern).
2. **Canonicalize protected categories** — for each `PROTECTED_CATEGORY_SUBSTRINGS` substring, merge all matching `by_category` rows into one canonical entry (sum revenue, profit, weighted margin). Store original labels in `raw_labels`.
3. **Compute portfolio totals** — Σ revenue, Σ profit, weighted GM.
4. **Compute target gap** — `target_gm − current_gm` (in percentage points) and `needed_profit_lift_ge = (target_gm − current_gm)/100 × current_revenue` (assuming revenue held constant).
5. **Rank categories** (excluding protected) by:
   - **DRAG** = margin_pct < (portfolio_gm − 3pp) AND portfolio_share_pct ≥ 1%. Sorted by `-share_pct` (biggest drag first).
   - **LIFT** = margin_pct > (portfolio_gm + 3pp) AND portfolio_share_pct ≥ 0.5%. Sorted by `-margin_pct` (highest headroom first).
6. **Generate recommended shifts** — top 3-5 pairs of `(drag → lift)`. For each pair, compute `revenue_shift_ge` such that tilting that amount moves portfolio GM by `gm_impact_pp`. Stop when cumulative `gm_impact_pp ≥ target gap` OR 5 pairs enumerated.
7. **Project outcome** — apply all recommended shifts; compute new portfolio GM.
8. **Build summary_ka** — "Currently 14.96% GM. Target 20%. Gap +5pp. Biggest drag: X (share 15%, margin 8%). Biggest lift: Y (share 3%, margin 30%). Hold cigarettes (share 34%, margin 10.5%, protected). Suggest: shift 2-3% of bread revenue into drinks — projected portfolio GM ~18%."

**Math precision note:** all sums via Python `sum()` (per Sprint 3e convention — no `+=` drift).

---

## 4. Protected-category canonicalization — decision

**Option A: substring merge inside mix_analyzer** (recommended for v1)
- Hardcoded `PROTECTED_CATEGORY_SUBSTRINGS = ("სიგარეტ",)` in constants.
- In-tool: scan `by_category` for rows where `raw_label` contains substring; merge them client-side.
- Pros: no pipeline change; tool is self-contained; reversible.
- Cons: other tools (product_profitability, detect_trends) still see separate cigarette rows.

**Option B: upstream category normalization in `retail_sales.py`**
- Add canonical mapping in pipeline; all tools downstream see merged rows.
- Pros: consistent across all tools; cleaner long-term.
- Cons: touches retail_sales pipeline (larger blast radius); invalidates the 2,114 tests that already pass with the current 645-row shape.

**Choice**: A for Phase 2.3. Note in `summary_ka` that cigarette variants are merged for mix analysis. File Option B as a follow-up once user confirms the canonical-set is right.

---

## 5. Fingerprint inputs (none — not a cache tool)

Mix_analyzer is a stateless AI tool (like `analyze_product_profitability`). No cache, no fingerprint. Per-run it reads fresh data.json each time. `data.json` itself is regenerated by the per-file cache pipeline; mix_analyzer benefits transitively.

---

## 6. Risks / pitfalls (MED-HIGH)

1. **Cigarette-not-merged regression** — if I forget canonicalization, the tool will recommend reducing "0804 | სიგარეტი" while ignoring "სიგარეტი" (both real cigarette revenue). That's the exact failure mode memory warns against. Pre-commit assertion must check that no recommended shift's `from_category` matches any protected substring.
2. **Stale memory margins** — memory says cigarettes 6%, data.json shows 10.53%. If user sees AI say "cigarettes are 6%", they'll lose trust. Tool MUST cite live data.json numbers, not memory's historical approximations.
3. **Sprint 5.5 revenue formula** — per memory `project_prompt_test_density.md` + handoff, retail_sales revenue = `unit_price × quantity` (pinned in `tests/test_retail_sales_revenue_formula.py`). mix_analyzer must not accidentally re-implement revenue; reuse `retail_sales.by_category.revenue_ge` as-is.
4. **Zero-revenue category division** — when computing `portfolio_share_pct` or `margin_pct`, guard against zero divisor (edge case: new category with 0 revenue but >0 cost).
5. **Target gap is already small (+5pp, not +10pp)** — memory's "half of target" framing is stale. Tool output must not imply "huge gap" when reality is "moderate gap". Summary tone matters.
6. **Protected-category override** — schema should expose `protected_categories_override: list[str]` so user can test "what if cigarettes weren't protected?" without code change. Safety: default is the hardcoded list; override requires explicit param.
7. **Per-store breakdown complexity** — `by_category[i].object_breakdown` lets us compute per-store portfolio GM. But mix decisions are typically portfolio-wide. Scope: v1 supports `store="total" | "ოზურგეთი" | "დვაბზუ"`, per-store mode computes portfolio from that store's object_breakdown entries only.
8. **Recommendation realism** — telling the user "shift 30% of bread revenue into drinks" is not realistic retail. Cap suggested `revenue_shift_ge` at 20% of source category revenue. Add note if cumulative shifts insufficient to close gap at realistic caps.

---

## 7. Scope recommendation (one session)

**DO in session:**
- New file `dashboard_pipeline/ai/mix_analyzer.py` (~450 lines, mirror product_profitability.py):
  - Public constants (targets, protected substrings, DRAG/LIFT thresholds, flag labels)
  - `_canonicalize_protected(categories, protected_substrings)` helper
  - `_compute_portfolio(categories)` → `{revenue, profit, gm_pct}`
  - `_rank_drag_lift(categories, portfolio_gm)` → `(drag_list, lift_list)`
  - `_suggest_shifts(drag, lift, target_gap_pp, portfolio_revenue)` → `list[shift]`
  - `_project_outcome(shifts, portfolio)` → `{if_applied_gm, delta_pp, reaches_target}`
  - `_build_summary_ka(...)` — always-surfaced Georgian summary
  - Public entry `analyze_category_mix(store, top_n, protected_override)` → result dict
- `dashboard_pipeline/constants.py` additions:
  - `USER_TARGET_GROSS_MARGIN_PCT = 20.0`
  - `PROTECTED_CATEGORY_SUBSTRINGS = ("სიგარეტ",)` (tuple, extensible)
  - `MIX_ANALYZER_MIN_SHARE_PCT = 0.5` (min share for lift candidates)
  - `MIX_ANALYZER_MIN_DRAG_SHARE_PCT = 1.0` (drag must be ≥1% share)
  - `MIX_ANALYZER_MARGIN_BAND_PP = 3.0` (DRAG = below portfolio_gm − 3; LIFT = above + 3)
  - `MIX_ANALYZER_MAX_SHIFT_PCT = 20.0` (realism cap per category)
- `dashboard_pipeline/ai/tools.py` additions:
  - `MIX_ANALYZER_TOOL` schema block (~80 lines, mirror PRODUCT_PROFITABILITY_XRAY_TOOL)
  - Append to `TOOL_SCHEMAS` list (now 27)
  - Dispatcher case for `"mix_analyzer"` (~15 lines)
- `dashboard_pipeline/ai/prompts.py` → `SYSTEM_PROMPT_KA`:
  - Add `mix_analyzer` to the tool cross-reference cluster (lines 342-344 + 978-982 areas)
  - Add Triggers/Anti-triggers language reinforcing "mix questions → mix_analyzer; margin per SKU → analyze_product_profitability"
- `tests/test_ai_mix_analyzer.py` — 10 unit tests (see §8)
- `_scratch_sprint2_3_mix_analyzer_dogfood.py` — 3 live scenarios against real data.json + Sonnet 4.6 think=True (mirror Phase 2.5/2.6 dogfood pattern)

**DEFER (explicitly NOT in this sprint):**
- Frontend dashboard tab for mix visualization (current: 15 tabs; this would be 16th — separate UI sprint)
- `user_targets.json` config file externalization
- Upstream category canonicalization in retail_sales.py (Option B above)
- Per-month mix trend (time-series layer) — detect_trends already covers category-level decomposition
- Sector benchmark integration — cited in summary, not drive the analysis

**Rationale**: mix_analyzer is one well-scoped text tool. Frontend + config + canonicalization each warrants its own session with its own evidence pass. Bundling would turn a tight ~800-line sprint into a ~2000-line "refactor" that's hard to review.

---

## 8. Test plan (`tests/test_ai_mix_analyzer.py` — 10 tests)

| # | name | assertion |
|---|---|---|
| 1 | `test_basic_portfolio_computation` | Given fixture by_category with known values, portfolio GM % matches hand-computed weighted average to 0.01pp |
| 2 | `test_cigarette_variants_canonicalized` | Fixture has 3 cigarette rows (diff labels); output has 1 protected entry with `raw_labels` = all 3 |
| 3 | `test_protected_never_recommended_for_reduction` | Fixture with cigarettes at 10% margin (below portfolio); no recommended_shift has `from_category` matching protected substring |
| 4 | `test_drag_category_identified` | Fixture with large low-margin category → surfaces in drag_categories with 🔴 flag |
| 5 | `test_lift_category_identified` | Fixture with small high-margin category → surfaces in lift_categories with 🟢 flag |
| 6 | `test_target_gap_computed_correctly` | Portfolio 15% + target 20% → gap_pp=5.0; gap_profit_ge = 5% × portfolio_revenue |
| 7 | `test_summary_ka_cites_live_numbers` | summary_ka string contains the actual portfolio_gm_pct value (not memory's 10%) |
| 8 | `test_per_store_mode` | store="ოზურგეთი" uses object_breakdown, portfolio totals reflect single-store |
| 9 | `test_realism_cap_enforced` | No recommended_shift's revenue_shift_ge exceeds MIX_ANALYZER_MAX_SHIFT_PCT × source category revenue |
| 10 | `test_empty_categories_returns_error` | by_category = [] → result has "error" key with Georgian message + hint |

**Total expected test count after Phase 2.3**: `2,114 + 10 = 2,124` pytest green.

**Live dog-food** (separate scratch, not in pytest):
- Scenario 1: "რა არის ჩვენი ახლანდელი მარჟა? როგორ ავიდე 20%-მდე?" — expect AI to call mix_analyzer, surface summary_ka verbatim
- Scenario 2: "სიგარეტის წილი შევცვალო?" — expect AI to refuse and cite protected rule via tool output
- Scenario 3: "ოზურგეთის მაღაზიის მიქსი როგორია?" — expect `store="ოზურგეთი"` call path, per-store portfolio

---

## 9. Files expected to change

| file | change |
|---|---|
| `dashboard_pipeline/ai/mix_analyzer.py` | **NEW** — core tool module (~450 lines) |
| `dashboard_pipeline/constants.py` | **ADD** `USER_TARGET_GROSS_MARGIN_PCT`, `PROTECTED_CATEGORY_SUBSTRINGS`, 3 threshold constants (~8 lines) |
| `dashboard_pipeline/ai/tools.py` | **ADD** `MIX_ANALYZER_TOOL` schema (~80 lines), append to TOOL_SCHEMAS, add dispatcher case (~15 lines) |
| `dashboard_pipeline/ai/prompts.py` | **ADD** mix_analyzer Triggers/Anti-triggers in existing tool cross-reference blocks (~20 lines) |
| `tests/test_ai_mix_analyzer.py` | **NEW** — 10 unit tests (~400 lines) |
| `_scratch_sprint2_3_mix_analyzer_dogfood.py` | **NEW, scratch** — 3-scenario live verify against Sonnet 4.6 |
| `CONTEXT_HANDOFF.md` | **UPDATE** — move Phase 2.3 from open-work to Recently CLOSED; pin commit SHA |

**No changes to:**
- `data.json` shape (read-only consumer)
- `retail_sales.py` pipeline (category canonicalization stays in-tool for v1)
- Any frontend file (`rs-dashboard/src/*`)
- `Financial_Analysis/sector_benchmarks.json` (cited in summary, not loaded)
- Any other AI tool's logic

---

## 10. Pre-commit self-check (before Phase 2.3 closes)

- [ ] `gitnexus_impact({target: "analyze_category_mix", direction: "upstream"})` — LOW (new symbol)
- [ ] `gitnexus_impact({target: "TOOL_SCHEMAS", direction: "upstream"})` — track callers
- [ ] 2,124/2,124 pytest green (was 2,114, +10 new)
- [ ] Cigarette canonicalization: assert all 3 variants land in `raw_labels`; no shift recommendation targets any
- [ ] summary_ka cites live portfolio_gm_pct (not hardcoded 10% or 14.96% string — computed from current data)
- [ ] 3/3 live dog-food pass with Sonnet 4.6 think=True
- [ ] sector_benchmarks.json NOT imported into mix_analyzer.py (verified via grep)
- [ ] `PROTECTED_CATEGORY_SUBSTRINGS` is a tuple (immutable), not a list
- [ ] Tool count in CONTEXT_HANDOFF.md updated 26 → 27

---

## 11. Config resolution (user-approved 2026-04-24)

User rejected the "answer these upfront" framing — explicit guidance: *"tool უნდა იყოს data-driven, არა config-driven; ცოცხალი მონაცემებიდან უნდა გაერკვეს"*. The sales file already carries per-SKU cost + sale price + margin, so the tool operates on live numbers exclusively.

**v1 defaults (no config required):**

| question | v1 default | how it becomes changeable |
|---|---|---|
| Protected categories | `PROTECTED_CATEGORY_SUBSTRINGS = ("სიგარეტ",)` — only cigarettes (the one category user stated explicitly) | Schema exposes `protected_override: list[str]`; AI can pass at runtime if conversation surfaces another protected |
| Target GM % | `USER_TARGET_GROSS_MARGIN_PCT = 20.0` | Schema exposes `target_gross_margin_pct: number` (default pulled from constant); AI can probe "what if 18%?" without code change |
| "უცნობი კატეგორია" | Treated as a normal category — DRAG/LIFT math handles it | No special-casing needed; if it surfaces as drag (low margin + high share), user sees it flagged and can act |
| Per-store mode | Both supported via `store: "total" \| "ოზურგეთი" \| "დვაბზუ"` | AI picks based on question phrasing ("ოზურგეთის მიქსი…" → per-store) |

**What the AI does at runtime, not config-time:**
- If the tool surfaces a new pattern the user hasn't named (e.g. "პური is your second-largest drag"), the AI asks the user whether to treat it as protected before making a recommendation.
- Target can be revised in a follow-up prompt ("რა ხდება 18%-ზე?") — tool re-runs with new param, no code change.
- Canonicalization merges `"სიგარეტ"` variants (3 rows → 1 protected entry). If user later notices another category is fragmented, the substring list extends in a 3-line constants edit — no architectural change.

Implementation proceeds with these defaults. No blocking questions.

---

## Evidence sources

- `rs-dashboard/public/data.json` — `retail_sales.by_category` (645 rows), `retail_sales.overall` (portfolio totals) — regenerated by Sprint 3f `a1763a3`
- `dashboard_pipeline/ai/product_profitability.py` — Phase 2.5 pattern reference (470 lines, authoritative shape)
- `dashboard_pipeline/ai/tools.py:1883-1970` — `PRODUCT_PROFITABILITY_XRAY_TOOL` schema block template
- `dashboard_pipeline/ai/tools.py:2375-2402` — `TOOL_SCHEMAS` registry (26 entries)
- `dashboard_pipeline/ai/tools.py:2788-2820` — dispatcher pattern
- `dashboard_pipeline/retail_sales.py:150-220` — `_category_month_margin_pct` + `by_category` builder
- `Financial_Analysis/sector_benchmarks.json` — external benchmark file (cited, not loaded)
- `AI_GENIUS_PARTNER_PLAN.md:183` — OLD Phase 2.3 scope ("Industry Benchmark") — superseded by this preview
- Memory `project_business_targets.md` — user's hard targets + protected categories + reframe rationale
- Memory `feedback_consultative_proactivity.md` — AI must lead strategic conversations on margin/growth topics
- Memory `user_project_meaning.md` — project has deep personal significance, mistakes are costly
