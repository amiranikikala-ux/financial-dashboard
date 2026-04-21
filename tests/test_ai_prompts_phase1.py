"""Prompt-guard tests for Phase 1 Part A — strategic-partner rewrite.

These tests pin the Phase 1 Part A additions to ``SYSTEM_PROMPT_KA`` so a
future refactor can't silently drop the 5-hat / confidence / source-hierarchy
/ data-skepticism / anti-hallucination v2 / strict-tone contracts that make
the AI behave like a partner instead of a database bot.

The investigator prompt must stay **untouched** through Phase 1 (per the
do-not-touch rule carried over from Sprint 1/2/3/4) — two assertions at the
bottom of this module guard that.
"""

from __future__ import annotations

import datetime as _dt

from dashboard_pipeline.ai.prompts import (
    SYSTEM_PROMPT_KA,
    SYSTEM_PROMPT_KA_INVESTIGATOR,
    build_system_prompt,
)
from dashboard_pipeline.ai.today_context import (
    _DEADLINE_APPROACHING_DAYS,
    _DEADLINE_HORIZON_DAYS,
    _DEADLINE_URGENT_DAYS,
    _FIXED_MONTHLY_DEADLINES,
    _WEEKDAY_CONTEXT,
    _clamp_day,
    _next_monthly_anchor,
    _upcoming_deadlines,
    build_today_block,
    build_today_context,
)


# ---------------------------------------------------------------------------
# 🎯 Role contract (strategic partner persona + tone rules)
# ---------------------------------------------------------------------------

class TestStrategicPartnerPersona:
    def test_prompt_opens_with_strategic_partner(self):
        opening = SYSTEM_PROMPT_KA.splitlines()[0]
        assert "სტრატეგიული" in opening
        assert "პარტნიორი" in opening

    def test_prompt_rejects_database_bot_label(self):
        assert "არა database-bot" in SYSTEM_PROMPT_KA

    def test_prompt_rejects_polite_assistant_label(self):
        assert "polite assistant" in SYSTEM_PROMPT_KA  # used in "არა polite assistant"

    def test_prompt_mentions_outcome_based_focus(self):
        # Role contract declares outcome-based recommendations.
        assert "outcome" in SYSTEM_PROMPT_KA.lower()

    def test_role_contract_heading_present(self):
        assert "🎯 როლის კონტრაქტი" in SYSTEM_PROMPT_KA


class TestStrictToneContract:
    def test_forbidden_flattery_phrase_genial(self):
        assert "გენიალური იდეაა" in SYSTEM_PROMPT_KA

    def test_forbidden_flattery_phrase_mshvenieri(self):
        assert "მშვენიერი კითხვაა" in SYSTEM_PROMPT_KA

    def test_forbidden_soft_pedal_shesadzloa(self):
        assert "შესაძლოა ცოტა" in SYSTEM_PROMPT_KA

    def test_risks_first_rule(self):
        # Risks must be surfaced in the opening paragraph, not buried.
        assert "რისკებს" in SYSTEM_PROMPT_KA
        assert "პირველივე აბზაცში" in SYSTEM_PROMPT_KA

    def test_strict_tone_reinforced_in_format_section(self):
        # Tone rule also appears inside "ენა და ფორმატი" for redundancy.
        assert "მკაცრი და პირდაპირი" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🗺️ Project map (business + data layer)
# ---------------------------------------------------------------------------

class TestProjectMap:
    def test_map_header_present(self):
        assert "🗺️ პროექტის რუკა" in SYSTEM_PROMPT_KA

    def test_map_mentions_both_stores(self):
        assert "ოზურგეთი" in SYSTEM_PROMPT_KA
        assert "დვაბზუ" in SYSTEM_PROMPT_KA

    def test_map_mentions_pos_counts(self):
        # Ozurgeti 3 POS + Dvabzu 2 POS — baseline business DNA.
        assert "3 POS" in SYSTEM_PROMPT_KA
        assert "2 POS" in SYSTEM_PROMPT_KA

    def test_map_mentions_franchise_and_regulation(self):
        assert "ფრენჩაიზი" in SYSTEM_PROMPT_KA
        assert "RS.ge" in SYSTEM_PROMPT_KA
        assert "VAT 18%" in SYSTEM_PROMPT_KA

    def test_map_references_data_layer_artifacts(self):
        assert "data.json" in SYSTEM_PROMPT_KA
        assert "Financial_Analysis/" in SYSTEM_PROMPT_KA
        assert "ChromaDB" in SYSTEM_PROMPT_KA
        assert "<TODAY>" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# ⚖️ Source hierarchy
# ---------------------------------------------------------------------------

class TestSourceHierarchy:
    def test_hierarchy_header_present(self):
        assert "⚖️ წყაროების იერარქია" in SYSTEM_PROMPT_KA

    def test_excel_is_priority_one(self):
        block = SYSTEM_PROMPT_KA.split("⚖️ წყაროების იერარქია", 1)[1]
        # Priority-1 row must mention Excel as the ground truth.
        first_priority_chunk = block.split("| 2 |", 1)[0]
        assert "Excel" in first_priority_chunk
        assert "Financial_Analysis" in first_priority_chunk

    def test_ai_memory_excludes_numeric_authority(self):
        # Row 4 (AI's "head") must carry the "❌ **არა ციფრი**" guardrail.
        assert "არა ციფრი" in SYSTEM_PROMPT_KA

    def test_conflict_resolution_rule_declared(self):
        assert "კონფლიქტის შემთხვევაში" in SYSTEM_PROMPT_KA
        assert "Excel სწორია" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🕵 Data skepticism
# ---------------------------------------------------------------------------

class TestDataSkepticism:
    def test_skepticism_header_present(self):
        assert "🕵 Data-ზე სკეპტიციზმი" in SYSTEM_PROMPT_KA

    def test_manual_payments_freshness_warning(self):
        assert "manual_payments.csv" in SYSTEM_PROMPT_KA
        assert "ყოველთვის ძველია" in SYSTEM_PROMPT_KA

    def test_rows_preview_lag_warning(self):
        assert "retail_sales.rows_preview" in SYSTEM_PROMPT_KA
        assert "ბოლო 1-2 დღე" in SYSTEM_PROMPT_KA

    def test_skepticism_rule_cites_bank_cross_check(self):
        # Example rule tells the AI to recommend a bank statement cross-check
        # BEFORE acting on manual_payments data.
        assert "ბანკის ამონაწერი" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🎭 5 hats (multi-role)
# ---------------------------------------------------------------------------

class TestFiveHats:
    def test_hats_header_present(self):
        assert "🎭 5 ქუდი" in SYSTEM_PROMPT_KA

    def test_financial_hat_label(self):
        assert "💼 **ფინანსური**" in SYSTEM_PROMPT_KA

    def test_operations_hat_label(self):
        assert "🔧 **ოპერაციული**" in SYSTEM_PROMPT_KA

    def test_strategist_hat_label(self):
        assert "🎯 **სტრატეგი**" in SYSTEM_PROMPT_KA

    def test_risk_hat_label(self):
        assert "⚠️ **რისკის**" in SYSTEM_PROMPT_KA

    def test_critic_hat_label(self):
        assert "🪞 **კრიტიკოსი**" in SYSTEM_PROMPT_KA

    def test_hats_skipped_on_simple_factual_questions(self):
        # Explicit carve-out: "რამდენი მომწოდებელია?" does NOT require hats.
        assert "რამდენი მომწოდებელია?" in SYSTEM_PROMPT_KA
        assert "ქუდი **არ** გამოიცვას" in SYSTEM_PROMPT_KA

    def test_complex_question_requires_multiple_hats(self):
        # Complex questions (decision / strategy / risk / cause / scenario)
        # trigger 2-3 hats minimum.
        assert "მინიმუმ 2-3 ქუდი" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🎯 Confidence labels
# ---------------------------------------------------------------------------

class TestConfidenceLabels:
    def test_confidence_header_present(self):
        assert "🎯 Confidence ნიშნები" in SYSTEM_PROMPT_KA

    def test_confidence_levels_declared(self):
        # All 5 levels: ✅ / 🟢 / 🟡 / 🟠 / ⚪
        assert "✅ **დარწმუნებული**" in SYSTEM_PROMPT_KA
        assert "🟢 **საიმედო**" in SYSTEM_PROMPT_KA
        assert "🟡 **ვარაუდი**" in SYSTEM_PROMPT_KA
        assert "🟠 **სუსტი ვარაუდი**" in SYSTEM_PROMPT_KA
        assert "⚪ **არ ვიცი**" in SYSTEM_PROMPT_KA

    def test_factual_questions_skip_confidence(self):
        # "270 მომწოდებელია?" — Confidence label NOT required.
        assert "ფაქტობრივი კითხვა" in SYSTEM_PROMPT_KA
        assert "არ გამოიყენო" in SYSTEM_PROMPT_KA

    def test_nonfactual_questions_require_confidence(self):
        # რჩევა / პროგნოზი / hypothesis → Confidence mandatory.
        assert "სავალდებულოა" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 📌 Assumption vs fact mark (Anti-Hallucination v2)
# ---------------------------------------------------------------------------

class TestAssumptionMark:
    def test_assumption_header_present(self):
        assert "📌 ვარაუდი vs ფაქტი" in SYSTEM_PROMPT_KA

    def test_forbidden_mental_estimate_phrases(self):
        # "ალბათ", "დაახლოებით", "ჩვეულებრივ" — all flagged with ❌.
        assert "**ალბათ**" in SYSTEM_PROMPT_KA
        assert "**დაახლოებით**" in SYSTEM_PROMPT_KA
        assert "**ჩვეულებრივ**" in SYSTEM_PROMPT_KA

    def test_assumption_mark_requires_confidence_label(self):
        # The 📌 mark alone isn't enough — a confidence label must accompany.
        passage_start = SYSTEM_PROMPT_KA.find("📌 ვარაუდი vs ფაქტი")
        passage = SYSTEM_PROMPT_KA[passage_start:]
        assert "Confidence ნიშანი" in passage


# ---------------------------------------------------------------------------
# Backwards-compat: investigator prompt must stay untouched
# ---------------------------------------------------------------------------

class TestInvestigatorPromptUntouched:
    """Phase 1 Part A must NOT leak into the investigator prompt — the
    discrepancy-hunter persona has its own cached prefix and its own
    contract (Cascade-ready fix briefs, not 5-hat strategy)."""

    def test_investigator_prompt_has_no_five_hats(self):
        # None of the Phase 1 Part A hats leak into investigator mode.
        assert "🎭 5 ქუდი" not in SYSTEM_PROMPT_KA_INVESTIGATOR
        assert "💼 **ფინანსური**" not in SYSTEM_PROMPT_KA_INVESTIGATOR
        assert "🔧 **ოპერაციული**" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_investigator_prompt_has_no_role_contract(self):
        # Persona upgrade text also absent.
        assert "🎯 როლის კონტრაქტი" not in SYSTEM_PROMPT_KA_INVESTIGATOR
        assert "outcome-based" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_investigator_prompt_retains_cascade_brief_contract(self):
        # The Cascade brief contract still lives on.
        assert "Cascade-ისთვის" in SYSTEM_PROMPT_KA_INVESTIGATOR


# ---------------------------------------------------------------------------
# build_system_prompt integration with Phase 1 Part A blocks
# ---------------------------------------------------------------------------

class TestBuildSystemPromptWiring:
    def test_chat_mode_ships_phase1_blocks(self):
        rendered = build_system_prompt(mode="chat")
        # Sanity: all major Phase 1 Part A headers survive the wiring.
        assert "🎯 როლის კონტრაქტი" in rendered
        assert "🗺️ პროექტის რუკა" in rendered
        assert "🎭 5 ქუდი" in rendered
        assert "🎯 Confidence ნიშნები" in rendered
        assert "⚖️ წყაროების იერარქია" in rendered

    def test_investigate_mode_skips_phase1_blocks(self):
        rendered = build_system_prompt(mode="investigate")
        assert "🎭 5 ქუდი" not in rendered
        assert "🎯 როლის კონტრაქტი" not in rendered


# ---------------------------------------------------------------------------
# Today-context extensions — weekday hint + upcoming deadlines
# ---------------------------------------------------------------------------

class TestWeekdayContext:
    def test_seven_weekday_hints_defined(self):
        assert len(_WEEKDAY_CONTEXT) == 7

    def test_all_hints_are_nonempty_strings(self):
        for hint in _WEEKDAY_CONTEXT:
            assert isinstance(hint, str) and hint.strip()

    def test_friday_hint_mentions_weekend(self):
        assert "weekend" in _WEEKDAY_CONTEXT[4].lower()

    def test_saturday_and_sunday_mention_retail_peak(self):
        assert "retail peak" in _WEEKDAY_CONTEXT[5]
        assert "retail peak" in _WEEKDAY_CONTEXT[6]

    def test_weekday_hint_appears_in_today_block_header(self):
        # 2026-04-17 = Friday; hint = "კვირის ბოლო — weekend-ის წინ".
        friday = _dt.date(2026, 4, 17)
        block = build_today_block(lambda: {}, today=friday)
        first_line_with_date = next(
            line for line in block.splitlines() if line.startswith("თარიღი")
        )
        assert "2026-04-17" in first_line_with_date
        assert "პარასკევი" in first_line_with_date
        assert "weekend-ის წინ" in first_line_with_date


class TestUpcomingDeadlines:
    def test_two_fixed_monthly_deadlines(self):
        labels = [label for label, _day in _FIXED_MONTHLY_DEADLINES]
        assert any("VAT" in l for l in labels)
        assert any("საპენსიო" in l for l in labels)
        assert len(_FIXED_MONTHLY_DEADLINES) == 2

    def test_thresholds_are_strictly_ordered(self):
        assert _DEADLINE_URGENT_DAYS < _DEADLINE_APPROACHING_DAYS
        assert _DEADLINE_APPROACHING_DAYS <= _DEADLINE_HORIZON_DAYS

    def test_upcoming_returns_both_deadlines_when_in_horizon(self):
        # 2026-05-10 → both May 15 deadlines are 5 days away.
        today = _dt.date(2026, 5, 10)
        out = _upcoming_deadlines(today)
        assert len(out) == 2
        for entry in out:
            assert entry["due_date"] == "2026-05-15"
            assert entry["days_until"] == 5
            assert entry["severity"] == "approaching"

    def test_urgent_severity_within_three_days(self):
        today = _dt.date(2026, 5, 13)  # 2 days before May 15
        out = _upcoming_deadlines(today)
        assert all(entry["severity"] == "urgent" for entry in out)

    def test_today_is_deadline_renders_urgent(self):
        today = _dt.date(2026, 5, 15)
        out = _upcoming_deadlines(today)
        assert all(entry["days_until"] == 0 for entry in out)
        assert all(entry["severity"] == "urgent" for entry in out)

    def test_past_anchor_rolls_forward_to_next_month(self):
        # 2026-04-20 → April 15 already passed → next anchor = May 15 →
        # 25 days away → outside the 10-day horizon → empty list.
        today = _dt.date(2026, 4, 20)
        out = _upcoming_deadlines(today)
        assert out == []

    def test_block_contains_deadlines_section_when_near(self):
        # 2026-05-12 → 3 days to deadline → urgent.
        today = _dt.date(2026, 5, 12)
        block = build_today_block(lambda: {}, today=today)
        assert "⏰ უახლოესი ვადები" in block
        assert "VAT" in block
        assert "საპენსიო" in block
        # "3 დღეში" humanized form appears twice (one per deadline).
        assert "3 დღეში" in block

    def test_block_omits_deadlines_when_far(self):
        # 2026-04-20 → deadlines are 25 days away → section suppressed.
        today = _dt.date(2026, 4, 20)
        block = build_today_block(lambda: {}, today=today)
        assert "⏰ უახლოესი ვადები" not in block


class TestMonthArithmetic:
    def test_next_monthly_anchor_keeps_day_when_future(self):
        assert _next_monthly_anchor(_dt.date(2026, 5, 10), 15) == _dt.date(
            2026, 5, 15
        )

    def test_next_monthly_anchor_rolls_when_past(self):
        assert _next_monthly_anchor(_dt.date(2026, 5, 16), 15) == _dt.date(
            2026, 6, 15
        )

    def test_next_monthly_anchor_rolls_december_to_january(self):
        assert _next_monthly_anchor(_dt.date(2026, 12, 20), 15) == _dt.date(
            2027, 1, 15
        )

    def test_next_monthly_anchor_rejects_invalid_day(self):
        assert _next_monthly_anchor(_dt.date(2026, 5, 10), 0) is None
        assert _next_monthly_anchor(_dt.date(2026, 5, 10), 32) is None

    def test_clamp_day_handles_february_short_month(self):
        # Day 31 in February → clamps to Feb 28 (or 29 for leap year).
        result = _clamp_day(2026, 2, 31)
        assert result == _dt.date(2026, 2, 28)

    def test_clamp_day_preserves_valid_day(self):
        result = _clamp_day(2026, 3, 15)
        assert result == _dt.date(2026, 3, 15)


class TestTodayContextCtxShape:
    """The ctx dict must include the new Phase 1 Part A keys so callers
    (agent / tests / debug scripts) can rely on them."""

    def test_ctx_includes_weekday_context_key(self):
        ctx = build_today_context(lambda: {}, today=_dt.date(2026, 4, 17))
        assert "weekday_context" in ctx
        assert isinstance(ctx["weekday_context"], str)
        assert ctx["weekday_context"]  # non-empty for Friday

    def test_ctx_includes_upcoming_deadlines_key(self):
        ctx = build_today_context(lambda: {}, today=_dt.date(2026, 5, 12))
        assert "upcoming_deadlines" in ctx
        assert isinstance(ctx["upcoming_deadlines"], list)
        assert len(ctx["upcoming_deadlines"]) == 2

    def test_ctx_upcoming_deadlines_empty_list_when_far(self):
        ctx = build_today_context(lambda: {}, today=_dt.date(2026, 4, 20))
        assert ctx["upcoming_deadlines"] == []

    def test_ctx_broken_loader_still_has_weekday_context(self):
        def _broken():
            raise RuntimeError("boom")

        ctx = build_today_context(_broken, today=_dt.date(2026, 4, 17))
        assert ctx["weekday_context"]  # still present on the defensive path
        assert ctx["upcoming_deadlines"] == []  # no deadlines near April 17
