"""Prompt-guard tests for Phase 1 Part B — Georgian regulation + franchise context.

Pins the new 🇬🇪 section in ``SYSTEM_PROMPT_KA`` so future refactors cannot
silently drop the tax-deadline / RS.ge / franchise-baseline / monthly-rhythm
contracts that make the advisor reason in Georgian reality instead of generic
retail abstractions.

Investigator prompt must stay **untouched** through Phase 1 (carry-over
do-not-touch rule from Sprint 1/2/3/4 AND Phase 1 Part A) — final guard at the
bottom of this module asserts that.
"""

from __future__ import annotations

from dashboard_pipeline.ai.prompts import (
    SYSTEM_PROMPT_KA,
    SYSTEM_PROMPT_KA_INVESTIGATOR,
    build_system_prompt,
)


# ---------------------------------------------------------------------------
# 🇬🇪 Section anchor + sub-headings
# ---------------------------------------------------------------------------

class TestGeorgianRegulationSection:
    def test_section_header_present(self):
        assert "🇬🇪 ქართული რეგულაცია" in SYSTEM_PROMPT_KA

    def test_section_tagged_phase_1_part_b(self):
        assert "Phase 1 Part B" in SYSTEM_PROMPT_KA

    def test_section_declares_georgia_operating_context(self):
        assert "საქართველოში" in SYSTEM_PROMPT_KA

    def test_four_subsections_present(self):
        for heading in (
            "💰 საჯარო გადასახადები",
            "🧾 RS.ge",
            "🏪 ფრენჩაიზი",
            "🌅 ქართული თვის რიტმი",
        ):
            assert heading in SYSTEM_PROMPT_KA, heading

    def test_section_placed_after_project_map_before_source_hierarchy(self):
        pos_map = SYSTEM_PROMPT_KA.index("🗺️ პროექტის რუკა")
        pos_regulation = SYSTEM_PROMPT_KA.index("🇬🇪 ქართული რეგულაცია")
        pos_hierarchy = SYSTEM_PROMPT_KA.index("⚖️ წყაროების იერარქია")
        assert pos_map < pos_regulation < pos_hierarchy


# ---------------------------------------------------------------------------
# 💰 Tax rules (VAT + pension + income tax + penalty)
# ---------------------------------------------------------------------------

class TestTaxRules:
    def test_vat_rate_18_percent(self):
        assert "VAT (დღგ)" in SYSTEM_PROMPT_KA
        assert "18%" in SYSTEM_PROMPT_KA

    def test_pension_fund_employer_and_employee_2_percent(self):
        assert "საპენსიო ფონდი" in SYSTEM_PROMPT_KA
        assert "2% დამსაქმებელი" in SYSTEM_PROMPT_KA
        assert "2% თანამშრომელი" in SYSTEM_PROMPT_KA

    def test_day_15_deadline_for_vat_and_pension(self):
        # Both VAT and საპენსიო roll up to the same monthly anchor.
        lines = [
            line for line in SYSTEM_PROMPT_KA.splitlines()
            if "VAT (დღგ)" in line or "საპენსიო ფონდი" in line
        ]
        assert any("15" in line for line in lines)

    def test_income_tax_small_business_1_percent(self):
        assert "1%" in SYSTEM_PROMPT_KA
        assert "მცირე ბიზნესი" in SYSTEM_PROMPT_KA

    def test_income_tax_standard_15_percent(self):
        # Standard rate must be present so AI knows to ask user's status.
        assert "standard" in SYSTEM_PROMPT_KA.lower()
        assert "15%" in SYSTEM_PROMPT_KA

    def test_small_business_500k_turnover_threshold(self):
        assert "500K" in SYSTEM_PROMPT_KA

    def test_vat_registration_100k_threshold(self):
        assert "100K" in SYSTEM_PROMPT_KA

    def test_late_payment_penalty_rule_present(self):
        assert "საურავი" in SYSTEM_PROMPT_KA
        assert "CB discount rate" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🧾 RS.ge specifics
# ---------------------------------------------------------------------------

class TestRsGeRules:
    def test_e_invoice_30_day_unpaid_warning(self):
        assert "ე-ინვოისი" in SYSTEM_PROMPT_KA
        assert "30+ დღე" in SYSTEM_PROMPT_KA

    def test_waybill_three_date_fields_referenced(self):
        # Part B cross-references the existing waybill date semantics section.
        for field in ("date", "transport_start_date", "delivery_date"):
            assert field in SYSTEM_PROMPT_KA

    def test_waybill_section_cross_reference_exists(self):
        assert "ზედნადების თარიღების სემანტიკა" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🏪 Franchise context (royalty + sourcing + opening fee + brand)
# ---------------------------------------------------------------------------

class TestFranchiseContext:
    def test_royalty_range_4_to_7_percent(self):
        assert "Royalty" in SYSTEM_PROMPT_KA
        assert "4-7%" in SYSTEM_PROMPT_KA

    def test_sourcing_obligation_60_to_75_percent(self):
        assert "Sourcing obligation" in SYSTEM_PROMPT_KA
        assert "60-75%" in SYSTEM_PROMPT_KA

    def test_opening_fee_dollar_range(self):
        assert "Opening fee" in SYSTEM_PROMPT_KA
        assert "$5K-20K" in SYSTEM_PROMPT_KA

    def test_brand_standards_mentioned(self):
        assert "Brand standards" in SYSTEM_PROMPT_KA

    def test_franchise_violations_named(self):
        # AI must know the consequences of franchise breach.
        for consequence in (
            "contract breach",
            "royalty freeze",
            "termination",
        ):
            assert consequence in SYSTEM_PROMPT_KA, consequence

    def test_royalty_marked_as_assumption_not_fact(self):
        # The generic 4-7% is a 📌 ვარაუდი, not a verified number.
        assert "📌 ვარაუდი" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 📋 Baseline facts — auto-journal placeholder mechanism
# ---------------------------------------------------------------------------

class TestBaselineFacts:
    def test_baseline_section_header_present(self):
        assert "Baseline facts" in SYSTEM_PROMPT_KA

    def test_four_baseline_facts_enumerated(self):
        # Royalty % + Sourcing obligation % + Income tax status + VAT status.
        for fact_marker in (
            "Royalty %",
            "Sourcing obligation %",
            "შემოსავლის გადასახადის სტატუსი",
            "VAT რეგისტრაციის სტატუსი",
        ):
            assert fact_marker in SYSTEM_PROMPT_KA, fact_marker

    def test_journal_add_entry_tool_referenced_for_baseline(self):
        assert "journal_add_entry" in SYSTEM_PROMPT_KA

    def test_reminder_kind_used_for_baseline_placeholders(self):
        # Baseline tag set includes kind:reminder — the tool dispatches to
        # journal.py's JOURNAL_KINDS = ("promise", "ai_commitment",
        # "recommendation", "reminder").
        assert 'kind="reminder"' in SYSTEM_PROMPT_KA
        assert "kind:reminder" in SYSTEM_PROMPT_KA

    def test_topic_franchise_tag_convention(self):
        assert "topic:franchise" in SYSTEM_PROMPT_KA

    def test_topic_tax_tag_convention(self):
        assert "topic:tax" in SYSTEM_PROMPT_KA

    def test_ask_not_guess_rule_present(self):
        # The key contract: if baseline fact missing → ask, don't guess.
        assert "გადააკითხე" in SYSTEM_PROMPT_KA
        assert "არა გამოიცნო" in SYSTEM_PROMPT_KA

    def test_recall_and_list_mechanisms_referenced(self):
        assert "recall_context" in SYSTEM_PROMPT_KA
        assert "journal_list_entries" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🌅 Monthly rhythm
# ---------------------------------------------------------------------------

class TestMonthlyRhythm:
    def test_monthly_rhythm_section_header(self):
        assert "🌅 ქართული თვის რიტმი" in SYSTEM_PROMPT_KA

    def test_day_15_marked_as_deadline_day(self):
        assert "deadline day" in SYSTEM_PROMPT_KA

    def test_four_buckets_present(self):
        # 1-10 calm / 11-14 pre-deadline / 15 deadline / 16-30 accumulation.
        for bucket in ("1-10", "11-14", "15", "16-30"):
            assert bucket in SYSTEM_PROMPT_KA, bucket

    def test_cash_intensive_recommendation_rule(self):
        # 5-10 window is safer for cash-intensive advice.
        assert "cash-intensive" in SYSTEM_PROMPT_KA

    def test_post_15_qualifier_rule_for_high_expense(self):
        # 12-14 window → advise "15-ე-ს შემდეგ" qualifier.
        assert "15-ე-ს შემდეგ" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# build_system_prompt wiring + mode isolation
# ---------------------------------------------------------------------------

class TestBuildSystemPromptWiring:
    def test_chat_mode_exposes_part_b_section(self):
        text = build_system_prompt(mode="chat")
        assert "🇬🇪 ქართული რეგულაცია" in text
        assert "Phase 1 Part B" in text

    def test_chat_mode_exposes_baseline_facts_mechanism(self):
        text = build_system_prompt(mode="chat")
        assert "Baseline facts" in text
        assert "journal_add_entry" in text

    def test_investigate_mode_hides_part_b_section(self):
        text = build_system_prompt(mode="investigate")
        assert "🇬🇪 ქართული რეგულაცია" not in text
        assert "Phase 1 Part B" not in text


# ---------------------------------------------------------------------------
# 🛡️ Do-not-touch — Investigator prompt stays Phase-1-free
# ---------------------------------------------------------------------------

class TestInvestigatorPromptUntouched:
    def test_investigator_prompt_has_no_part_b_marker(self):
        assert "Phase 1 Part B" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_investigator_prompt_has_no_georgian_regulation_section(self):
        assert "🇬🇪 ქართული რეგულაცია" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_investigator_prompt_has_no_baseline_facts_section(self):
        assert "Baseline facts" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_investigator_prompt_has_no_monthly_rhythm_section(self):
        assert "🌅 ქართული თვის რიტმი" not in SYSTEM_PROMPT_KA_INVESTIGATOR
