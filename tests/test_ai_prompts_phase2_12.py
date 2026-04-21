"""Prompt-guard tests for Phase 2.12 — Supplier Negotiation Prep.

Pins the new 📞 section in ``SYSTEM_PROMPT_KA`` so future refactors cannot
silently drop the `prepare_supplier_brief` trigger guidance, identity
confidence protocol, or relationship-discipline rules.

Background: Phase 2.12 added a strategic "negotiation brief" tool that
triangulates suppliers × imported_products × supplier_aging into a 1-page
pre-meeting deck. The prompt layer is what teaches the AI:

* WHEN to call it (explicit trigger list) vs. WHEN to reach for row-level
  lookups (`read_data_json`) — anti-trigger protection.
* How to handle `match_confidence=medium|low` — MUST confirm identity with
  the user BEFORE quoting figures.
* Relationship discipline — `#3 dual_source_leverage` is last-resort;
  `warning_ka` must be relayed verbatim.

Investigator prompt must stay **untouched** through all of Phase 1 AND
Phase 2 (carry-over do-not-touch rule from Sprint 1/2/3/4 + Phase 1
Parts A/B/C/D + Phase 2.11 Dead Stock). The final guard at the bottom
asserts that none of the Phase 2.12 markers leak into the investigator
prompt.
"""

from __future__ import annotations

from dashboard_pipeline.ai.prompts import (
    SYSTEM_PROMPT_KA,
    SYSTEM_PROMPT_KA_INVESTIGATOR,
    build_system_prompt,
)


# ---------------------------------------------------------------------------
# 📞 Section anchor + intro rules
# ---------------------------------------------------------------------------


class TestSupplierNegotiationSection:
    def test_section_header_present(self):
        assert "📞 მომწოდებელთან მოლაპარაკების მომზადება" in SYSTEM_PROMPT_KA

    def test_section_tagged_phase_2_12(self):
        assert "Phase 2.12" in SYSTEM_PROMPT_KA

    def test_intro_frames_negotiation_as_power_game(self):
        assert "ვაჭრობა ძალაუფლების თამაშია" in SYSTEM_PROMPT_KA

    def test_intro_mentions_one_page_brief(self):
        assert "1-გვერდიანი ცნობა" in SYSTEM_PROMPT_KA

    def test_section_placed_after_dead_stock_before_self_correction(self):
        dead_idx = SYSTEM_PROMPT_KA.find("💀 Dead Stock")
        negotiation_idx = SYSTEM_PROMPT_KA.find(
            "📞 მომწოდებელთან მოლაპარაკების მომზადება"
        )
        self_correct_idx = SYSTEM_PROMPT_KA.find(
            "🔄 საკუთარი თავის გასწორების ციკლი"
        )
        assert dead_idx != -1
        assert negotiation_idx != -1
        assert self_correct_idx != -1
        assert dead_idx < negotiation_idx < self_correct_idx


# ---------------------------------------------------------------------------
# ✅ When-to-use trigger list
# ---------------------------------------------------------------------------


class TestTriggerList:
    def test_trigger_header_present(self):
        assert "როდის გამოიყენე `prepare_supplier_brief`" in SYSTEM_PROMPT_KA

    def test_meeting_trigger(self):
        # "ხვალ X-თან მაქვს შეხვედრა"
        assert "შეხვედრა" in SYSTEM_PROMPT_KA

    def test_discount_ask_trigger(self):
        assert "ფასდაკლება ვთხოვო" in SYSTEM_PROMPT_KA

    def test_leverage_question_trigger(self):
        assert "ჩემი leverage რა არის" in SYSTEM_PROMPT_KA

    def test_alternative_supplier_trigger(self):
        assert "alternative supplier" in SYSTEM_PROMPT_KA or "ვის გადავიდე" in SYSTEM_PROMPT_KA

    def test_portfolio_wide_trigger(self):
        assert "პირველად" in SYSTEM_PROMPT_KA
        assert "portfolio-wide" in SYSTEM_PROMPT_KA

    def test_mode_disambiguation_explained(self):
        # Portfolio vs focused mode distinction
        assert "Portfolio vs focused mode" in SYSTEM_PROMPT_KA
        assert "supplier_name" in SYSTEM_PROMPT_KA
        assert "tax_id" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# ❌ Anti-trigger list (do-NOT-use)
# ---------------------------------------------------------------------------


class TestAntiTriggers:
    def test_anti_trigger_header_present(self):
        assert "ანტი-ტრიგერები" in SYSTEM_PROMPT_KA

    def test_debt_lookup_routes_to_read_data_json(self):
        assert "რამდენი ვალი მაქვს" in SYSTEM_PROMPT_KA
        assert "supplier_aging" in SYSTEM_PROMPT_KA

    def test_payment_lookup_routes_to_read_data_json(self):
        assert "რამდენი გადავუხადე" in SYSTEM_PROMPT_KA

    def test_waybill_lookup_routes_to_read_data_json(self):
        assert "ბოლო ზედნადები" in SYSTEM_PROMPT_KA
        assert "waybills" in SYSTEM_PROMPT_KA

    def test_rule_statement_present(self):
        # "წესი: ... სტრატეგიული lens. ცარიელი lookup-ისთვის `read_data_json` ბევრად იაფია."
        assert "სტრატეგიული lens" in SYSTEM_PROMPT_KA
        assert "lookup" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🪪 Identity Confidence Protocol
# ---------------------------------------------------------------------------


class TestIdentityConfidenceProtocol:
    def test_protocol_header_present(self):
        assert "🪪 Identity Confidence Protocol" in SYSTEM_PROMPT_KA

    def test_high_confidence_rule(self):
        assert "match_confidence=high" in SYSTEM_PROMPT_KA

    def test_medium_and_low_require_confirmation(self):
        assert "match_confidence=medium" in SYSTEM_PROMPT_KA or "medium" in SYSTEM_PROMPT_KA
        assert "არასოდეს ნუ გადახვალ პირდაპირ ციფრებზე" in SYSTEM_PROMPT_KA

    def test_confirmation_example_present(self):
        # The quoted example should give the AI a canonical phrasing
        assert "ჩემი ვარაუდი" in SYSTEM_PROMPT_KA
        assert "tax_id" in SYSTEM_PROMPT_KA

    def test_affirmation_keywords_listed(self):
        # "კი" / "დიახ" / "ზუსტად" before proceeding
        assert "კი" in SYSTEM_PROMPT_KA
        assert "დიახ" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 📋 Output Format
# ---------------------------------------------------------------------------


class TestOutputFormat:
    def test_format_header_present(self):
        assert "სავალდებულო Output Format" in SYSTEM_PROMPT_KA

    def test_identity_line_required(self):
        assert "მომწოდებლის identity" in SYSTEM_PROMPT_KA

    def test_leverage_label_required(self):
        assert "🟢 HIGH" in SYSTEM_PROMPT_KA
        assert "🟡 MEDIUM" in SYSTEM_PROMPT_KA
        assert "🟠 LOW" in SYSTEM_PROMPT_KA

    def test_factor_table_hint(self):
        assert "ფაქტორი" in SYSTEM_PROMPT_KA
        assert "რას ნიშნავს" in SYSTEM_PROMPT_KA

    def test_negotiation_plays_table_hint(self):
        assert "რა ვთხოვო" in SYSTEM_PROMPT_KA
        assert "რას ვთავაზობ სანაცვლოდ" in SYSTEM_PROMPT_KA or "სანაცვლოდ" in SYSTEM_PROMPT_KA

    def test_warning_relay_required(self):
        assert "warning_ka" in SYSTEM_PROMPT_KA
        assert "verbatim" in SYSTEM_PROMPT_KA

    def test_source_attribution_required(self):
        assert "data.json" in SYSTEM_PROMPT_KA
        assert "supplier_aging" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🛡 Relationship Discipline
# ---------------------------------------------------------------------------


class TestRelationshipDiscipline:
    def test_discipline_header_present(self):
        assert "🛡 Relationship Discipline" in SYSTEM_PROMPT_KA

    def test_relationship_over_margin_rule(self):
        assert "Relationship > margin" in SYSTEM_PROMPT_KA

    def test_play_3_last_resort_rule(self):
        assert "#3" in SYSTEM_PROMPT_KA
        assert "last-resort" in SYSTEM_PROMPT_KA
        assert "dual_source_leverage" in SYSTEM_PROMPT_KA

    def test_no_push_beyond_data_rule(self):
        # Must not invent aggressive moves beyond what the tool returned
        assert "data-ს მიღმა" in SYSTEM_PROMPT_KA or "data ცხადი" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🧠 Portfolio Mode example
# ---------------------------------------------------------------------------


class TestPortfolioModeExample:
    def test_portfolio_example_header_present(self):
        assert "🧠 Portfolio Mode მაგალითი" in SYSTEM_PROMPT_KA

    def test_example_user_question_present(self):
        assert "ვის უნდა ვესაუბრო ფასდაკლებისთვის" in SYSTEM_PROMPT_KA

    def test_example_shows_ranked_table(self):
        # The demo rendering must show a rank column + leverage + savings
        assert "Leverage" in SYSTEM_PROMPT_KA
        assert "წლიური savings" in SYSTEM_PROMPT_KA

    def test_example_recommends_starting_with_rank_one(self):
        # The model should be steered toward "start with #1"
        assert "დაიწყე #1" in SYSTEM_PROMPT_KA or "#1-ით" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🎯 Confidence labels
# ---------------------------------------------------------------------------


class TestConfidenceLabels:
    def test_confidence_labels_header_present(self):
        # This section appears under the negotiation section specifically
        section_start = SYSTEM_PROMPT_KA.find(
            "📞 მომწოდებელთან მოლაპარაკების მომზადება"
        )
        section_end = SYSTEM_PROMPT_KA.find(
            "🔄 საკუთარი თავის გასწორების ციკლი"
        )
        assert section_start != -1 and section_end != -1
        section = SYSTEM_PROMPT_KA[section_start:section_end]
        assert "🎯 Confidence labels" in section

    def test_all_four_labels_present(self):
        section_start = SYSTEM_PROMPT_KA.find(
            "📞 მომწოდებელთან მოლაპარაკების მომზადება"
        )
        section_end = SYSTEM_PROMPT_KA.find(
            "🔄 საკუთარი თავის გასწორების ციკლი"
        )
        section = SYSTEM_PROMPT_KA[section_start:section_end]
        assert "🟢 საიმედო" in section
        assert "🟡 ვარაუდი" in section
        assert "🟠 ფრთხილად" in section
        assert "⚪ ვერ დავადგინე" in section


# ---------------------------------------------------------------------------
# build_system_prompt integration (chat mode picks up Phase 2.12)
# ---------------------------------------------------------------------------


class TestBuildSystemPromptIntegration:
    def test_default_chat_mode_includes_phase_2_12(self):
        prompt = build_system_prompt("")
        assert "📞 მომწოდებელთან მოლაპარაკების მომზადება" in prompt
        assert "prepare_supplier_brief" in prompt

    def test_explicit_chat_mode_includes_phase_2_12(self):
        prompt = build_system_prompt("", mode="chat")
        assert "Phase 2.12" in prompt

    def test_investigate_mode_skips_phase_2_12(self):
        prompt = build_system_prompt("", mode="investigate")
        assert "📞 მომწოდებელთან მოლაპარაკების მომზადება" not in prompt
        assert "prepare_supplier_brief" not in prompt


# ---------------------------------------------------------------------------
# Investigator-prompt do-not-touch (Phase 2.12 markers absent)
# ---------------------------------------------------------------------------


class TestInvestigatorPromptUntouched:
    """Investigator prompt must never absorb Phase 2.12 chat-mode content."""

    def test_no_negotiation_section_header(self):
        assert (
            "📞 მომწოდებელთან მოლაპარაკების მომზადება"
            not in SYSTEM_PROMPT_KA_INVESTIGATOR
        )

    def test_no_identity_confidence_protocol_header(self):
        assert (
            "🪪 Identity Confidence Protocol"
            not in SYSTEM_PROMPT_KA_INVESTIGATOR
        )

    def test_no_relationship_discipline_header(self):
        assert (
            "🛡 Relationship Discipline"
            not in SYSTEM_PROMPT_KA_INVESTIGATOR
        )

    def test_no_portfolio_mode_example_header(self):
        assert "🧠 Portfolio Mode მაგალითი" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_no_prepare_supplier_brief_mention(self):
        assert "prepare_supplier_brief" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_fifteen_phase_2_12_markers_all_absent(self):
        markers = (
            "Phase 2.12",
            "📞 მომწოდებელთან მოლაპარაკების მომზადება",
            "🪪 Identity Confidence Protocol",
            "🛡 Relationship Discipline",
            "🧠 Portfolio Mode მაგალითი",
            "prepare_supplier_brief",
            "ვაჭრობა ძალაუფლების თამაშია",
            "1-გვერდიანი ცნობა",
            "match_confidence=high",
            "match_confidence=medium",
            "Relationship > margin",
            "last-resort",
            "dual_source_leverage",
            "ანტი-ტრიგერები",
            "სტრატეგიული lens",
        )
        for marker in markers:
            assert (
                marker not in SYSTEM_PROMPT_KA_INVESTIGATOR
            ), f"investigator prompt leaked Phase 2.12 marker: {marker!r}"


# ---------------------------------------------------------------------------
# Phase 1 + Phase 2.11 still present (regression guard)
# ---------------------------------------------------------------------------


class TestPriorPhasesStillPresent:
    """Phase 2.12 must not dislodge any earlier section."""

    def test_part_a_role_contract_still_present(self):
        assert "🎯 როლის კონტრაქტი" in SYSTEM_PROMPT_KA

    def test_part_b_georgian_regulation_still_present(self):
        assert "🇬🇪 ქართული რეგულაცია" in SYSTEM_PROMPT_KA

    def test_part_c_multi_store_dna_still_present(self):
        assert "🏪 მაღაზიების DNA" in SYSTEM_PROMPT_KA

    def test_part_d_self_correction_still_present(self):
        assert "🔄 საკუთარი თავის გასწორების ციკლი" in SYSTEM_PROMPT_KA

    def test_phase_2_11_dead_stock_still_present(self):
        assert "💀 Dead Stock" in SYSTEM_PROMPT_KA

    def test_phase_2_11_dead_stock_tool_name_still_present(self):
        assert "analyze_dead_stock" in SYSTEM_PROMPT_KA
