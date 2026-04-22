"""Prompt-guard tests for Sprint 4B.2 — Tier 2+3 Personality & Format rules.

Pins the 15 Tier-2+3 rules from `PHASE_4B_PROMPT_TUNING_PREVIEW.md`:

Tier 2 Personality & Agentic (6 rules):
- Rule 5  Seamless memory — forbidden phrases (Opus 4.6)
- Rule 6  Overfamiliarity warning (Opus 4.6)
- Rule 7  Push back + kindness balance (Sonnet 4.5)
- Rule 19 Avoid over-engineering (docs.anthropic.com)
- Rule 20 State scope explicitly (docs.anthropic.com)
- Rule 21 Persistence directive (docs.anthropic.com)

Tier 3 Format & Anti-sycophancy (9 rules):
- Rule 8  Minimum formatting (Sonnet 4.5)
- Rule 9  Anti-sycophancy 8-word Georgian ban (Claude 4)
- Rule 10 Asterisk-actions ban (Sonnet 4.5)
- Rule 11 Emoji calibration — functional only (Sonnet 4.5)
- Rule 12 Tool scaling ladder 0 / 2-4 / 5-9 / 10+ (Opus 4.6)
- Rule 13 Financial override — documented (Sonnet 4.5 default override)
- Rule 14 File-may-not-exist (Sonnet 4.5)
- Rule 15 Metaphor usage (Sonnet 4.5)
- Rule 26 Oververbosity 1-10 scale, default 3 (GPT-5)

Investigator prompt stays untouched (do-not-touch rule) — final guard
asserts that.
"""

from __future__ import annotations

import pytest

from dashboard_pipeline.ai.prompts import (
    SYSTEM_PROMPT_KA,
    SYSTEM_PROMPT_KA_INVESTIGATOR,
    build_system_prompt,
)


# ---------------------------------------------------------------------------
# 🎭 Tier 2 section anchor + placement
# ---------------------------------------------------------------------------


class TestTier2SectionAnchor:
    def test_personality_section_header_present(self):
        assert "🎭 Personality & Agentic" in SYSTEM_PROMPT_KA

    def test_personality_section_tagged_4b2_tier2(self):
        assert "Phase 4B.2 Tier 2" in SYSTEM_PROMPT_KA

    def test_placed_after_4b1_principles_before_map(self):
        principles_idx = SYSTEM_PROMPT_KA.find("🎯 ქცევის პრინციპები")
        personality_idx = SYSTEM_PROMPT_KA.find("🎭 Personality & Agentic")
        map_idx = SYSTEM_PROMPT_KA.find("🗺️ პროექტის რუკა")
        assert 0 < principles_idx < personality_idx < map_idx


# ---------------------------------------------------------------------------
# 🧠 Rule 5 — Seamless memory
# ---------------------------------------------------------------------------


class TestRule5SeamlessMemory:
    def test_subsection_header_present(self):
        assert "Seamless memory" in SYSTEM_PROMPT_KA
        assert "forbidden phrases" in SYSTEM_PROMPT_KA

    def test_forbidden_phrases_enumerated(self):
        # All four concrete forbidden phrases from Opus 4.6 guidance
        for phrase in (
            "ჩემს მეხსიერებაში ვხედავ",
            "ბოლო საუბრებიდან ვიპოვე",
            "ChromaDB-ში აღმოვაჩინე",
            "`recall_context`-ში ვპოულობ",
        ):
            assert phrase in SYSTEM_PROMPT_KA, phrase

    def test_good_example_shows_natural_fact(self):
        # The Alpha 31,450 ₾ worked example proves the rule is behavioral
        assert "31,450 ₾" in SYSTEM_PROMPT_KA

    def test_source_citation_still_required(self):
        # Citation != forbidden memory phrase — explicit carve-out
        assert "(წყარო: data.json → supplier_aging)" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 👥 Rule 6 — Overfamiliarity
# ---------------------------------------------------------------------------


class TestRule6Overfamiliarity:
    def test_subsection_header_present(self):
        assert "Overfamiliarity warning" in SYSTEM_PROMPT_KA

    def test_chunk_count_cited(self):
        # 18,263 indexed chunks is the concrete scale that motivates the rule
        assert "18,263" in SYSTEM_PROMPT_KA

    def test_verifiable_recall_required(self):
        assert "verifiable" in SYSTEM_PROMPT_KA

    def test_chat_id_example_shown(self):
        # The fix: cite chat_id instead of bare "გახსოვს..."
        assert "chat_id" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 💪 Rule 7 — Push back + kindness
# ---------------------------------------------------------------------------


class TestRule7PushBackKindness:
    def test_subsection_header_present(self):
        assert "Push back + Kindness balance" in SYSTEM_PROMPT_KA

    def test_strict_not_rude_principle(self):
        assert "მკაცრი ტონი ≠ უხეში ტონი" in SYSTEM_PROMPT_KA

    def test_empathy_phrased_correction_example(self):
        # The 20% vs 6.8% alternative-interpretation example
        assert "6.8%" in SYSTEM_PROMPT_KA
        assert "იქნებ" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🔧 Rule 19 — Avoid over-engineering
# ---------------------------------------------------------------------------


class TestRule19AvoidOverEngineering:
    def test_subsection_header_present(self):
        assert "Avoid over-engineering" in SYSTEM_PROMPT_KA

    def test_minimal_change_rule(self):
        assert "მინიმალური ცვლილება" in SYSTEM_PROMPT_KA

    def test_phase_3_1_pull_only_cross_ref(self):
        # Rule 19 explicitly ties to Phase 3.1 Co-Designer PULL-ONLY
        assert "PULL-ONLY" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 📏 Rule 20 — State scope explicitly
# ---------------------------------------------------------------------------


class TestRule20StateScope:
    def test_subsection_header_present(self):
        assert "State scope explicitly" in SYSTEM_PROMPT_KA

    def test_scope_definition_matrix(self):
        # scope = year/month + object + metric_type + source
        assert "წელი/თვე" in SYSTEM_PROMPT_KA
        assert "metric type" in SYSTEM_PROMPT_KA
        assert "წყარო" in SYSTEM_PROMPT_KA

    def test_good_vs_weak_example(self):
        # "margin 18.7%" (weak) vs full-scope version
        assert "18.7%" in SYSTEM_PROMPT_KA
        assert "2025 დეკემბერში" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🔋 Rule 21 — Persistence directive
# ---------------------------------------------------------------------------


class TestRule21Persistence:
    def test_subsection_header_present(self):
        assert "Persistence directive" in SYSTEM_PROMPT_KA

    def test_long_horizon_chain_example(self):
        # The canonical 3-tool long-horizon chain
        assert "build_debt_repayment_plan" in SYSTEM_PROMPT_KA
        assert "prepare_supplier_brief" in SYSTEM_PROMPT_KA
        assert "compute_cash_runway" in SYSTEM_PROMPT_KA

    def test_early_stop_forbidden(self):
        assert "early stop" in SYSTEM_PROMPT_KA.lower() or "early-stop" in SYSTEM_PROMPT_KA

    def test_rule_18_cross_reference(self):
        # Rule 21 explicitly extends Rule 18 Commit to approach
        assert "Rule 18" in SYSTEM_PROMPT_KA or "Commit to approach" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 📐 Tier 3 section anchor + placement
# ---------------------------------------------------------------------------


class TestTier3SectionAnchor:
    def test_format_section_header_present(self):
        assert "📐 Format & Style" in SYSTEM_PROMPT_KA

    def test_format_section_tagged_4b2_tier3(self):
        assert "Phase 4B.2 Tier 3" in SYSTEM_PROMPT_KA

    def test_format_section_placed_after_personality(self):
        personality_idx = SYSTEM_PROMPT_KA.find("🎭 Personality & Agentic")
        format_idx = SYSTEM_PROMPT_KA.find("📐 Format & Style")
        map_idx = SYSTEM_PROMPT_KA.find("🗺️ პროექტის რუკა")
        assert 0 < personality_idx < format_idx < map_idx


# ---------------------------------------------------------------------------
# ✏️ Rule 8 — Minimum formatting
# ---------------------------------------------------------------------------


class TestRule8MinimumFormatting:
    def test_subsection_header_present(self):
        assert "Minimum formatting" in SYSTEM_PROMPT_KA

    def test_anthropic_verbatim_prose_over_lists(self):
        assert "prose, not lists" in SYSTEM_PROMPT_KA

    def test_matrix_covers_five_question_types(self):
        # Simple / fact+context / comparison / strategic / crisis
        for question_type in (
            "მარტივი ფაქტობრივი",
            "ფაქტი + context",
            "შედარება",
            "სტრატეგიული",
            "კრიზისი",
        ):
            assert question_type in SYSTEM_PROMPT_KA, question_type


# ---------------------------------------------------------------------------
# 🚫 Rule 9 — Anti-sycophancy
# ---------------------------------------------------------------------------


class TestRule9AntiSycophancy:
    def test_subsection_header_present(self):
        assert "Anti-sycophancy" in SYSTEM_PROMPT_KA

    def test_all_eight_banned_phrases(self):
        # Exactly the 8 Georgian flattery words the preview specified
        for phrase in (
            "მშვენიერი",
            "შესანიშნავი",
            "საინტერესო",
            "ფუნდამენტური",
            "გულწრფელად",
            "პირდაპირ",
            "ცხადია",
            "მარტივად",
        ):
            assert phrase in SYSTEM_PROMPT_KA, phrase

    def test_direct_start_rule(self):
        assert "პირდაპირ ფაქტით ან ციფრით" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 💬 Rule 10 — Asterisk-actions ban
# ---------------------------------------------------------------------------


class TestRule10AsteriskBan:
    def test_subsection_header_present(self):
        assert "Asterisk-actions ban" in SYSTEM_PROMPT_KA

    def test_roleplay_examples_forbidden(self):
        assert "Stage direction" in SYSTEM_PROMPT_KA

    def test_functional_emphasis_still_allowed(self):
        # Bold as functional emphasis is NOT banned
        assert "ფუნქციური emphasis" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🎨 Rule 11 — Emoji calibration
# ---------------------------------------------------------------------------


class TestRule11EmojiCalibration:
    def test_subsection_header_present(self):
        assert "Emoji calibration" in SYSTEM_PROMPT_KA

    def test_functional_only_rule(self):
        assert "Functional only" in SYSTEM_PROMPT_KA

    def test_allowed_functional_emojis_listed(self):
        # Confidence + status emojis are explicitly kept
        assert "🟢🟡🟠⚪" in SYSTEM_PROMPT_KA

    def test_decoration_examples_banned(self):
        # 🎉 🌟 💯 🔥 listed as banned
        for emoji in ("🎉", "🌟", "💯", "🔥"):
            assert emoji in SYSTEM_PROMPT_KA, emoji


# ---------------------------------------------------------------------------
# 🪜 Rule 12 — Tool scaling ladder
# ---------------------------------------------------------------------------


class TestRule12ToolScaling:
    def test_subsection_header_present(self):
        assert "Tool scaling ladder" in SYSTEM_PROMPT_KA

    def test_four_tier_ladder_present(self):
        # Exactly the 4 tiers from Opus 4.6 guidance
        for tier_marker in ("| **0** |", "| **2-4** |", "| **5-9** |", "| **10+** |"):
            assert tier_marker in SYSTEM_PROMPT_KA, tier_marker

    def test_anti_pattern_stated(self):
        # 1 tool call on crisis = bug; 15 tool calls on trivial = bug
        assert "Anti-pattern" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 💰 Rule 13 — Financial override (documented)
# ---------------------------------------------------------------------------


class TestRule13FinancialOverride:
    def test_subsection_header_present(self):
        assert "Financial override" in SYSTEM_PROMPT_KA

    def test_anthropic_default_quoted(self):
        assert "not a licensed financial advisor" in SYSTEM_PROMPT_KA

    def test_override_justified(self):
        # User owns business + real-time data + non-regulated advice
        assert "business-ის მფლობელი" in SYSTEM_PROMPT_KA

    def test_safety_disclaimer_still_present(self):
        # უსაფრთხოება section disclaimer still exists
        assert "data-driven კომენტარია" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 📎 Rule 14 — File may not exist
# ---------------------------------------------------------------------------


class TestRule14FileMayNotExist:
    def test_subsection_header_present(self):
        assert "File-may-not-exist" in SYSTEM_PROMPT_KA

    def test_verify_before_ref_rule(self):
        assert "read_excel_source" in SYSTEM_PROMPT_KA

    def test_error_handling_script_present(self):
        assert "Financial_Analysis/" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🔮 Rule 15 — Metaphor usage
# ---------------------------------------------------------------------------


class TestRule15Metaphor:
    def test_subsection_header_present(self):
        assert "Metaphor usage" in SYSTEM_PROMPT_KA

    def test_hhi_worked_example(self):
        # HHI 551 is the concrete worked example from the Phase 2.12 deck
        assert "HHI 551" in SYSTEM_PROMPT_KA

    def test_rule_targets_plain_georgian_user(self):
        assert "plain ქართული" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 📊 Rule 26 — Oververbosity 1-10 (GPT-5)
# ---------------------------------------------------------------------------


class TestRule26Oververbosity:
    def test_subsection_header_present(self):
        assert "Oververbosity 1-10 scale" in SYSTEM_PROMPT_KA

    def test_gpt5_source_cited(self):
        # Rule 26 is a GPT-5 leaked-prompt original
        gpt5_count = SYSTEM_PROMPT_KA.count("GPT-5")
        assert gpt5_count >= 3, f"GPT-5 cited only {gpt5_count} times"

    def test_default_verbosity_declared(self):
        assert "Default: **3**" in SYSTEM_PROMPT_KA

    def test_five_levels_enumerated(self):
        # Levels 2, 3, 5, 7, 9 in the scale table
        for level in ("| **2** |", "| **3** (default) |", "| **5** |",
                      "| **7** (strategic) |", "| **9** |"):
            assert level in SYSTEM_PROMPT_KA, level

    def test_strategic_and_crisis_anchors(self):
        assert "Strategic: **7**" in SYSTEM_PROMPT_KA
        assert "Crisis: **2**" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🧩 build_system_prompt integration (chat picks up 4B.2)
# ---------------------------------------------------------------------------


class TestBuildSystemPromptIntegration:
    def test_chat_mode_includes_tier2_tier3(self):
        prompt = build_system_prompt("")
        assert "🎭 Personality & Agentic" in prompt
        assert "📐 Format & Style" in prompt
        assert "Phase 4B.2 Tier 2" in prompt
        assert "Phase 4B.2 Tier 3" in prompt

    def test_investigate_mode_skips_4b2(self):
        prompt = build_system_prompt("", mode="investigate")
        assert "🎭 Personality & Agentic" not in prompt
        assert "📐 Format & Style" not in prompt


# ---------------------------------------------------------------------------
# 🛡 Investigator prompt do-not-touch (4B.2 markers absent)
# ---------------------------------------------------------------------------


class TestInvestigatorPromptUntouched:
    """Investigator prompt must stay marker-free for 4B.2 chat-mode content."""

    MARKERS = (
        "🎭 Personality & Agentic",
        "📐 Format & Style",
        "Phase 4B.2 Tier 2",
        "Phase 4B.2 Tier 3",
        "Seamless memory",
        "Overfamiliarity warning",
        "Push back + Kindness balance",
        "Avoid over-engineering",
        "State scope explicitly",
        "Persistence directive",
        "Minimum formatting",
        "Anti-sycophancy",
        "Asterisk-actions ban",
        "Emoji calibration",
        "Tool scaling ladder",
        "Financial override",
        "File-may-not-exist",
        "Metaphor usage",
        "Oververbosity 1-10 scale",
    )

    @pytest.mark.parametrize("marker", MARKERS)
    def test_marker_absent_from_investigator(self, marker):
        assert marker not in SYSTEM_PROMPT_KA_INVESTIGATOR, marker
