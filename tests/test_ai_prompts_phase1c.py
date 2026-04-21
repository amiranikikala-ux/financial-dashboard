"""Prompt-guard tests for Phase 1 Part C — Multi-Store DNA.

Pins the new 🏪 section in ``SYSTEM_PROMPT_KA`` so future refactors cannot
silently drop the store differentiation contracts that make the advisor reason
about Ozurgeti (urban flagship) and Dvabzu (rural local) as two distinct
businesses instead of a single averaged franchise.

Investigator prompt must stay **untouched** through Phase 1 (carry-over
do-not-touch rule from Sprint 1/2/3/4 AND Phase 1 Part A AND Phase 1 Part B) —
final guard at the bottom of this module asserts that.
"""

from __future__ import annotations

from dashboard_pipeline.ai.prompts import (
    SYSTEM_PROMPT_KA,
    SYSTEM_PROMPT_KA_INVESTIGATOR,
    build_system_prompt,
)


# ---------------------------------------------------------------------------
# 🏪 Section anchor + sub-headings + topological position
# ---------------------------------------------------------------------------

class TestMultiStoreDnaSection:
    def test_section_header_present(self):
        assert "🏪 მაღაზიების DNA" in SYSTEM_PROMPT_KA

    def test_section_tagged_phase_1_part_c(self):
        assert "Phase 1 Part C" in SYSTEM_PROMPT_KA

    def test_section_intro_declares_two_distinct_businesses(self):
        # The opening sentence is the anti-uniform-advice contract.
        assert "ორი სხვადასხვა ბიზნესი" in SYSTEM_PROMPT_KA

    def test_both_store_profile_headings_present(self):
        for heading in (
            "🏪 ოზურგეთი — Urban Flagship",
            "🏡 დვაბზუ — Rural Local",
        ):
            assert heading in SYSTEM_PROMPT_KA, heading

    def test_four_subsections_present(self):
        for heading in (
            "🌅 სეზონური რიტმი",
            "🎯 DNA-ს გამოყენება",
            "📋 Baseline facts — store-level",
            "⚠️ DNA-ს over-apply",
        ):
            assert heading in SYSTEM_PROMPT_KA, heading

    def test_section_placed_after_monthly_rhythm_before_source_hierarchy(self):
        # Business-context cluster stays contiguous:
        # 🗺️ project map → 🇬🇪 regulation → 🏪 store DNA → ⚖️ source hierarchy.
        pos_regulation = SYSTEM_PROMPT_KA.index("🇬🇪 ქართული რეგულაცია")
        pos_rhythm = SYSTEM_PROMPT_KA.index("🌅 ქართული თვის რიტმი")
        pos_dna = SYSTEM_PROMPT_KA.index("🏪 მაღაზიების DNA")
        pos_hierarchy = SYSTEM_PROMPT_KA.index("⚖️ წყაროების იერარქია")
        assert pos_regulation < pos_rhythm < pos_dna < pos_hierarchy


# ---------------------------------------------------------------------------
# 🏪 Ozurgeti DNA profile
# ---------------------------------------------------------------------------

class TestOzurgetiDna:
    def test_urban_label(self):
        # "Urban" label distinguishes Ozurgeti from Dvabzu rural profile.
        assert "Urban" in SYSTEM_PROMPT_KA

    def test_three_pos_terminals(self):
        assert "3 ტერმინალი" in SYSTEM_PROMPT_KA

    def test_twelve_hour_operation(self):
        assert "12-საათიანი" in SYSTEM_PROMPT_KA

    def test_mixed_tourist_local_customer(self):
        assert "ტურისტი" in SYSTEM_PROMPT_KA
        assert "ადგილობრივი" in SYSTEM_PROMPT_KA

    def test_evening_peak_20_22(self):
        # Evening rush window is the staffing anchor.
        assert "20:00-22:00" in SYSTEM_PROMPT_KA

    def test_premium_mix_tilt(self):
        assert "Premium drinks" in SYSTEM_PROMPT_KA

    def test_fast_promotion_response(self):
        # Elastic segment → promotion trial-friendly.
        assert "Fast & high pass-through" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🏡 Dvabzu DNA profile
# ---------------------------------------------------------------------------

class TestDvabzuDna:
    def test_rural_label(self):
        assert "Rural" in SYSTEM_PROMPT_KA

    def test_two_pos_terminals(self):
        assert "2 ტერმინალი" in SYSTEM_PROMPT_KA

    def test_eight_hour_operation(self):
        assert "8-საათიანი" in SYSTEM_PROMPT_KA

    def test_local_loyal_customer(self):
        # Loyalty + habit are the anti-promotion DNA markers.
        assert "loyal" in SYSTEM_PROMPT_KA

    def test_payday_peak_10_25(self):
        # Pay-day-driven spending anchors cash-planning rules.
        assert "10 + 25" in SYSTEM_PROMPT_KA

    def test_basics_bulk_mix_tilt(self):
        assert "Basics, bulk" in SYSTEM_PROMPT_KA

    def test_slow_promotion_response_and_low_elasticity(self):
        assert "Slow & low pass-through" in SYSTEM_PROMPT_KA
        # Low price elasticity → discount wasteful on Dvabzu.
        assert "Low" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🌅 Seasonal rhythm (soft hint — NOT hardcoded calendar)
# ---------------------------------------------------------------------------

class TestSeasonality:
    def test_tourist_summer_window_6_9(self):
        # Ozurgeti summer peak (months 6-9) is the tourism anchor.
        assert "6-9 ზაფხული" in SYSTEM_PROMPT_KA

    def test_dvabzu_payday_and_easter(self):
        assert "payday" in SYSTEM_PROMPT_KA
        assert "Easter" in SYSTEM_PROMPT_KA

    def test_new_year_common_peak(self):
        # Both stores spike on 31 December.
        assert "31 დეკემბერი" in SYSTEM_PROMPT_KA

    def test_seasonality_marked_as_soft_hint_not_hardcoded(self):
        # Phase 1 Part C preview option 🔵 α — soft context only.
        # AI must defer to forecast_revenue for precise numbers.
        assert "soft hint" in SYSTEM_PROMPT_KA
        assert "forecast_revenue(store=...)" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🎯 Strategic guidance — when DNA matters per question type
# ---------------------------------------------------------------------------

class TestStrategicGuidance:
    def test_promotion_discount_dimension_present(self):
        assert "Promotion / discount" in SYSTEM_PROMPT_KA

    def test_supplier_strategy_dimension_present(self):
        assert "Supplier strategy" in SYSTEM_PROMPT_KA

    def test_staffing_dimension_present(self):
        # Evening staff is the concrete Ozurgeti action.
        assert "Staffing" in SYSTEM_PROMPT_KA
        assert "evening staff CRITICAL" in SYSTEM_PROMPT_KA

    def test_pricing_dimension_present(self):
        assert "Pricing change" in SYSTEM_PROMPT_KA

    def test_cash_planning_dimension_present(self):
        # Dvabzu payday spike is a store-specific cash-flow signal.
        assert "Cash planning" in SYSTEM_PROMPT_KA
        assert "payday spike" in SYSTEM_PROMPT_KA

    def test_store_comparison_dimension_present(self):
        # Cross-store margin drift must start with DNA hypothesis.
        assert "Store comparison" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 📋 Baseline facts — store-level (auto-journal placeholder mechanism)
# ---------------------------------------------------------------------------

class TestBaselineFactsPartC:
    def test_baseline_section_header_present(self):
        assert "📋 Baseline facts — store-level" in SYSTEM_PROMPT_KA

    def test_four_baseline_facts_enumerated(self):
        for fact_marker in (
            "ტურისტული თვეების ფანჯარა",
            "ხელფასის days",
            "Top-3 supplier per store",
            "Evening : Daytime revenue ratio",
        ):
            assert fact_marker in SYSTEM_PROMPT_KA, fact_marker

    def test_store_dna_topic_tag_convention(self):
        # Part B pattern carried forward — topic:store_dna tag.
        assert "topic:store_dna" in SYSTEM_PROMPT_KA

    def test_reminder_kind_for_store_dna_placeholders(self):
        assert "kind:reminder" in SYSTEM_PROMPT_KA
        # journal_add_entry call example uses kind="reminder".
        assert 'kind="reminder"' in SYSTEM_PROMPT_KA

    def test_generic_dna_numbers_marked_as_assumption(self):
        # The 2-3× traffic ratio, 50-60% comparison, 20-22 peak window are
        # generic — must remain 📌 ვარაუდი until user-specific data lands.
        assert "📌 ვარაუდი" in SYSTEM_PROMPT_KA

    def test_saimedo_upgrade_path_documented(self):
        # When user supplies journal fact, confidence upgrades to 🟢 საიმედო.
        assert "🟢 საიმედო" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# ⚠️ Over-apply guardrails — DNA stays out of simple lookups
# ---------------------------------------------------------------------------

class TestOverApplyGuardrails:
    def test_over_apply_section_present(self):
        assert "⚠️ DNA-ს over-apply" in SYSTEM_PROMPT_KA

    def test_simple_lookup_rejection_examples(self):
        # Simple counts / POS reads / waybill sums must NOT trigger DNA essays.
        assert "რამდენი მომწოდებელია ოზურგეთში?" in SYSTEM_PROMPT_KA
        assert "POS income" in SYSTEM_PROMPT_KA

    def test_strategic_only_rule(self):
        assert "მხოლოდ სტრატეგიულ/რეკომენდაციულ" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# build_system_prompt wiring + mode isolation
# ---------------------------------------------------------------------------

class TestBuildSystemPromptWiring:
    def test_chat_mode_exposes_part_c_section(self):
        text = build_system_prompt(mode="chat")
        assert "🏪 მაღაზიების DNA" in text
        assert "Phase 1 Part C" in text

    def test_chat_mode_exposes_both_store_profiles(self):
        text = build_system_prompt(mode="chat")
        assert "🏪 ოზურგეთი — Urban Flagship" in text
        assert "🏡 დვაბზუ — Rural Local" in text

    def test_chat_mode_exposes_seasonality_and_guidance_and_baseline(self):
        text = build_system_prompt(mode="chat")
        assert "🌅 სეზონური რიტმი" in text
        assert "🎯 DNA-ს გამოყენება" in text
        assert "📋 Baseline facts — store-level" in text

    def test_investigate_mode_hides_part_c_section(self):
        text = build_system_prompt(mode="investigate")
        assert "🏪 მაღაზიების DNA" not in text
        assert "Phase 1 Part C" not in text


# ---------------------------------------------------------------------------
# 🛡️ Do-not-touch — Investigator prompt stays Phase-1-free
# ---------------------------------------------------------------------------

class TestInvestigatorPromptUntouched:
    def test_investigator_prompt_has_no_part_c_marker(self):
        assert "Phase 1 Part C" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_investigator_prompt_has_no_store_dna_section(self):
        assert "🏪 მაღაზიების DNA" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_investigator_prompt_has_no_ozurgeti_urban_flagship_label(self):
        assert "🏪 ოზურგეთი — Urban Flagship" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_investigator_prompt_has_no_dvabzu_rural_local_label(self):
        assert "🏡 დვაბზუ — Rural Local" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_investigator_prompt_has_no_store_dna_baseline_heading(self):
        assert "📋 Baseline facts — store-level" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_investigator_prompt_has_no_strategic_guidance_table(self):
        # The "DNA-ს გამოყენება" heading must never leak into investigator.
        assert "🎯 DNA-ს გამოყენება" not in SYSTEM_PROMPT_KA_INVESTIGATOR


# ---------------------------------------------------------------------------
# 🔄 Phase 1 Part A + Part B markers still present (regression guard)
# ---------------------------------------------------------------------------

class TestPhase1PriorPartsStillPresent:
    def test_part_a_persona_marker_still_present(self):
        # Phase 1 Part A role-contract anchor must survive Part C edits.
        assert "🎯 როლის კონტრაქტი" in SYSTEM_PROMPT_KA

    def test_part_a_five_hats_still_present(self):
        # 🎭 five-hats cluster is a Part A do-not-touch.
        assert "🎭 5 ქუდი" in SYSTEM_PROMPT_KA

    def test_part_b_regulation_section_still_present(self):
        assert "🇬🇪 ქართული რეგულაცია" in SYSTEM_PROMPT_KA

    def test_part_b_monthly_rhythm_still_present(self):
        assert "🌅 ქართული თვის რიტმი" in SYSTEM_PROMPT_KA

    def test_part_b_baseline_facts_still_present(self):
        # Part B's "Baseline facts" heading (income tax + VAT status) lives
        # under 🇬🇪 regulation section; Part C adds a separate "Baseline facts
        # — store-level" heading. Both must coexist.
        positions = [
            i
            for i in range(len(SYSTEM_PROMPT_KA))
            if SYSTEM_PROMPT_KA.startswith("Baseline facts", i)
        ]
        assert len(positions) >= 2, (
            "Expected at least 2 'Baseline facts' headings (Part B + Part C), "
            f"found {len(positions)}."
        )
