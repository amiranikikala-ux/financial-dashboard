"""Prompt-guard tests for Sprint 4B.1 — Tier 1 Fundamental Behavior Rules.

Pins the 9 Tier-1 rules from `PHASE_4B_PROMPT_TUNING_PREVIEW.md` so future
refactors cannot silently drop them:

- Rule 1  Attempt first, clarify second (Sonnet 4.5)
- Rule 2  Max 1 question per response (Claude 4)
- Rule 3  Premise-ის შემოწმება (false-premise pushback, Sonnet 4.5)
- Rule 4  User-იც შეიძლება შეცდეს (no auto-apology, Opus 4.6)
- Rule 16 `<use_parallel_tool_calls>` XML (docs.anthropic.com)
- Rule 17 `<investigate_before_answering>` XML (hallucination brake)
- Rule 18 Commit to approach (anti-180° pivot)
- Rule 27 Partial completion > clarification (GPT-5)
- Rule 28 No future promises ban (GPT-5)

Also asserts STOP-CHECK has been **rebalanced** (Open Q #6): narrow to
financial-critical decisions only, not every data lookup. Preserves every
previously grep-asserted Georgian phrase from Phase 1-4A sessions.

Investigator prompt stays untouched (do-not-touch rule carried from
Sprint 1/2/3/4 and Phase 1 A/B/C/D) — final guard at the bottom of this
module asserts that.
"""

from __future__ import annotations

import pytest

from dashboard_pipeline.ai.prompts import (
    SYSTEM_PROMPT_KA,
    SYSTEM_PROMPT_KA_INVESTIGATOR,
    build_system_prompt,
)


# ---------------------------------------------------------------------------
# 🎯 Section anchor + placement
# ---------------------------------------------------------------------------


class TestBehaviorPrinciplesSection:
    def test_section_header_present(self):
        assert "🎯 ქცევის პრინციპები" in SYSTEM_PROMPT_KA

    def test_section_tagged_phase_4b1(self):
        assert "Phase 4B.1" in SYSTEM_PROMPT_KA

    def test_section_declares_precedence(self):
        # The 9 rules sit above phase-specific sections.
        assert "ყველა phase-სპეციფიკურ წესზე მაღლა" in SYSTEM_PROMPT_KA

    def test_section_placed_after_role_contract_before_project_map(self):
        role_idx = SYSTEM_PROMPT_KA.find("🎯 როლის კონტრაქტი")
        principles_idx = SYSTEM_PROMPT_KA.find("🎯 ქცევის პრინციპები")
        map_idx = SYSTEM_PROMPT_KA.find("🗺️ პროექტის რუკა")
        assert role_idx != -1
        assert principles_idx != -1
        assert map_idx != -1
        assert role_idx < principles_idx < map_idx

    def test_distillation_sources_named(self):
        # Both Anthropic + GPT-5 sources are explicitly cited.
        assert "Anthropic" in SYSTEM_PROMPT_KA
        assert "GPT-5" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🚀 Rule 1 — Attempt first, clarify second
# ---------------------------------------------------------------------------


class TestRule1AttemptFirst:
    def test_subsection_header_present(self):
        assert "Attempt first, clarify second" in SYSTEM_PROMPT_KA

    def test_anthropic_verbatim_quote_present(self):
        # Anthropic's exact wording from Sonnet 4.5 docs
        assert "Claude does its best to address the person's query" in SYSTEM_PROMPT_KA
        assert "even if ambiguous" in SYSTEM_PROMPT_KA
        assert "before asking for clarification" in SYSTEM_PROMPT_KA

    def test_georgian_interpretation_of_attempt_first(self):
        assert "ჯერ ცადე ყველაზე მოსალოდნელი პასუხი" in SYSTEM_PROMPT_KA

    def test_refusal_gated_to_financial_critical(self):
        # "არ ვიცი რომელი წელი" refusal must be scoped
        assert "financial-critical" in SYSTEM_PROMPT_KA
        assert "მხოლოდ" in SYSTEM_PROMPT_KA

    def test_data_lookup_gets_default_not_refusal(self):
        assert "მოსალოდნელი default" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🎚 Rule 2 — Max 1 question per response
# ---------------------------------------------------------------------------


class TestRule2MaxOneQuestion:
    def test_subsection_header_present(self):
        assert "Max 1 question per response" in SYSTEM_PROMPT_KA

    def test_three_gate_cascade_forbidden(self):
        # The anti-pattern example must be present verbatim
        assert "3 gate ერთდროულად" in SYSTEM_PROMPT_KA

    def test_priority_cascade_mandated(self):
        assert "ერთ cascade" in SYSTEM_PROMPT_KA

    def test_claude_4_source_cited(self):
        assert "Claude 4" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🕵 Rule 3 — Premise check
# ---------------------------------------------------------------------------


class TestRule3PremiseCheck:
    def test_subsection_header_present(self):
        assert "🕵 Premise-ის შემოწმება" in SYSTEM_PROMPT_KA

    def test_blind_agreement_forbidden(self):
        assert "blind-agreement" in SYSTEM_PROMPT_KA
        assert "აკრძალულია" in SYSTEM_PROMPT_KA

    def test_push_back_example_present(self):
        # The margin 20% vs 6.8% worked example proves the rule is behavioral
        assert "20%" in SYSTEM_PROMPT_KA
        assert "push back" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🪞 Rule 4 — User can also err (no auto-apology)
# ---------------------------------------------------------------------------


class TestRule4UserCanErr:
    def test_subsection_header_present(self):
        assert "User-იც შეიძლება შეცდეს" in SYSTEM_PROMPT_KA

    def test_auto_apology_forbidden(self):
        assert "auto-apology" in SYSTEM_PROMPT_KA

    def test_apology_gated_to_ai_errors(self):
        assert "მხოლოდ" in SYSTEM_PROMPT_KA

    def test_opus_source_cited(self):
        assert "Opus 4.6" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# ⚡ Rule 16 — Parallel tool calls XML
# ---------------------------------------------------------------------------


class TestRule16ParallelToolsXml:
    def test_xml_open_tag_present(self):
        assert "<use_parallel_tool_calls>" in SYSTEM_PROMPT_KA

    def test_xml_close_tag_present(self):
        assert "</use_parallel_tool_calls>" in SYSTEM_PROMPT_KA

    def test_anthropic_verbatim_phrase(self):
        # Anthropic docs' exact phrasing for maximum efficiency
        assert "For maximum efficiency" in SYSTEM_PROMPT_KA
        assert "invoke all relevant tools simultaneously" in SYSTEM_PROMPT_KA

    def test_parallel_examples_named(self):
        assert "read_data_json" in SYSTEM_PROMPT_KA
        assert "compute" in SYSTEM_PROMPT_KA
        assert "recall_context" in SYSTEM_PROMPT_KA

    def test_xml_block_content_between_tags(self):
        start = SYSTEM_PROMPT_KA.find("<use_parallel_tool_calls>")
        end = SYSTEM_PROMPT_KA.find("</use_parallel_tool_calls>")
        assert start != -1 and end != -1 and start < end
        content = SYSTEM_PROMPT_KA[start:end]
        assert "Prioritize calling tools in parallel" in content


# ---------------------------------------------------------------------------
# 🔎 Rule 17 — Investigate before answering XML
# ---------------------------------------------------------------------------


class TestRule17InvestigateBeforeAnswering:
    def test_xml_open_tag_present(self):
        assert "<investigate_before_answering>" in SYSTEM_PROMPT_KA

    def test_xml_close_tag_present(self):
        assert "</investigate_before_answering>" in SYSTEM_PROMPT_KA

    def test_requires_data_reading_tool(self):
        assert "invoke at least one data-reading tool" in SYSTEM_PROMPT_KA

    def test_lists_grounding_tools(self):
        start = SYSTEM_PROMPT_KA.find("<investigate_before_answering>")
        end = SYSTEM_PROMPT_KA.find("</investigate_before_answering>")
        content = SYSTEM_PROMPT_KA[start:end]
        for tool in ("read_data_json", "compute", "compute_waybill_total",
                     "recall_context", "read_excel_source"):
            assert tool in content, tool

    def test_forbids_fabrication_after_retries(self):
        assert "3 attempts" in SYSTEM_PROMPT_KA
        assert "don't fabricate" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🎯 Rule 18 — Commit to approach
# ---------------------------------------------------------------------------


class TestRule18CommitToApproach:
    def test_subsection_header_present(self):
        assert "Commit to approach" in SYSTEM_PROMPT_KA

    def test_anti_pivot_rule_present(self):
        assert "ბოლომდე მიიყვანე" in SYSTEM_PROMPT_KA

    def test_tool_chain_example_present(self):
        # build_debt_repayment_plan → compute_cash_runway is the canonical chain
        assert "build_debt_repayment_plan" in SYSTEM_PROMPT_KA
        assert "compute_cash_runway" in SYSTEM_PROMPT_KA

    def test_one_time_strategy_change_allowed(self):
        assert "ერთხელ" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# ✂️ Rule 27 — Partial completion > clarification (GPT-5)
# ---------------------------------------------------------------------------


class TestRule27PartialCompletion:
    def test_subsection_header_present(self):
        assert "Partial completion > clarification" in SYSTEM_PROMPT_KA

    def test_gpt5_source_cited(self):
        assert "GPT-5" in SYSTEM_PROMPT_KA

    def test_non_critical_questions_never_clarify(self):
        # Core rule: don't clarify data lookup questions
        assert "არასოდეს" in SYSTEM_PROMPT_KA
        assert "partial completion" in SYSTEM_PROMPT_KA.lower()

    def test_december_margin_example_present(self):
        # Worked example: "რამდენი margin იყო დეკემბერში?"
        assert "რამდენი margin იყო დეკემბერში" in SYSTEM_PROMPT_KA

    def test_financial_critical_exception_preserved(self):
        assert "financial-critical" in SYSTEM_PROMPT_KA
        assert "გამონაკლისი" in SYSTEM_PROMPT_KA

    def test_good_vs_bad_pattern_shown(self):
        # Bad and Good examples in the prompt
        assert "❌" in SYSTEM_PROMPT_KA
        assert "✅" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 📢 Rule 28 — No future promises (GPT-5)
# ---------------------------------------------------------------------------


class TestRule28NoFuturePromises:
    def test_subsection_header_present(self):
        assert "No future promises" in SYSTEM_PROMPT_KA

    def test_banned_phrases_enumerated(self):
        assert "ვცდი და მოვახსენებ" in SYSTEM_PROMPT_KA
        assert "რამდენიმე წამში მოგახსენებ" in SYSTEM_PROMPT_KA

    def test_synchronous_nature_declared(self):
        assert "synchronous" in SYSTEM_PROMPT_KA

    def test_no_later_principle(self):
        assert "self-contained" in SYSTEM_PROMPT_KA

    def test_gpt5_source_cited_here_too(self):
        # Both Rule 27 and Rule 28 credit GPT-5 leaked prompt
        count = SYSTEM_PROMPT_KA.count("GPT-5")
        assert count >= 2, f"GPT-5 source cited only {count} times"


# ---------------------------------------------------------------------------
# 🛑 STOP-CHECK rebalance (Open Q #6)
# ---------------------------------------------------------------------------


class TestStopCheckRebalance:
    def test_stop_check_scope_narrowed_to_financial_critical(self):
        # The old "ყველა სხვა წესზე მაღლა" default is replaced by a scoped rule
        assert "financial-critical decisions only" in SYSTEM_PROMPT_KA

    def test_stop_check_routing_rule_present(self):
        # Data lookup → Rule 27 Partial completion; critical → STOP-CHECK
        assert "Partial completion" in SYSTEM_PROMPT_KA

    def test_stop_check_header_kept(self):
        # Existing regression guards still pass
        assert "🛑 STOP-CHECK" in SYSTEM_PROMPT_KA

    def test_single_question_cascade_enforced(self):
        assert "Max 1 question per response" in SYSTEM_PROMPT_KA

    def test_existing_stop_check_assertions_preserved(self):
        # These phrases are pinned by test_ai_self_critique_prompt.py
        assert "STOP-CHECK" in SYSTEM_PROMPT_KA
        assert "მოკლედ მითხარი" in SYSTEM_PROMPT_KA
        assert "მხოლოდ რიცხვი" in SYSTEM_PROMPT_KA
        assert "არ გაუშვა" in SYSTEM_PROMPT_KA
        for year in ("2024", "2025", "2026"):
            assert year in SYSTEM_PROMPT_KA, year


# ---------------------------------------------------------------------------
# 🧩 build_system_prompt integration (chat mode picks up 4B.1)
# ---------------------------------------------------------------------------


class TestBuildSystemPromptIntegration:
    def test_default_chat_mode_includes_principles(self):
        prompt = build_system_prompt("")
        assert "🎯 ქცევის პრინციპები" in prompt
        assert "<use_parallel_tool_calls>" in prompt
        assert "<investigate_before_answering>" in prompt

    def test_explicit_chat_mode_cites_phase_4b1(self):
        prompt = build_system_prompt("", mode="chat")
        assert "Phase 4B.1" in prompt

    def test_investigate_mode_skips_4b1_principles(self):
        prompt = build_system_prompt("", mode="investigate")
        assert "🎯 ქცევის პრინციპები" not in prompt
        # XML blocks are chat-mode artifacts
        assert "<use_parallel_tool_calls>" not in prompt
        assert "<investigate_before_answering>" not in prompt


# ---------------------------------------------------------------------------
# 🛡 Investigator prompt do-not-touch (Phase 4B.1 markers absent)
# ---------------------------------------------------------------------------


class TestInvestigatorPromptUntouched:
    """Investigator prompt must stay marker-free for 4B.1 chat-mode content."""

    MARKERS = (
        "🎯 ქცევის პრინციპები",
        "Phase 4B.1",
        "Attempt first, clarify second",
        "Max 1 question per response",
        "🕵 Premise-ის შემოწმება",
        "User-იც შეიძლება შეცდეს",
        "<use_parallel_tool_calls>",
        "<investigate_before_answering>",
        "Commit to approach",
        "Partial completion > clarification",
        "No future promises",
        "GPT-5",
        "ვცდი და მოვახსენებ",
    )

    @pytest.mark.parametrize("marker", MARKERS)
    def test_marker_absent_from_investigator(self, marker):
        assert marker not in SYSTEM_PROMPT_KA_INVESTIGATOR, marker

    def test_investigator_still_itself(self):
        # Sanity — investigator persona still present
        assert "investigator" in SYSTEM_PROMPT_KA_INVESTIGATOR.lower() \
            or "🔍" in SYSTEM_PROMPT_KA_INVESTIGATOR
