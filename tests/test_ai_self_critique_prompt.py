"""Prompt-guard tests for Phase 0A.2 — Self-Critique Loop.

These tests assert that the chat-mode system prompt contains the required
Self-Critique directives. They do NOT exercise the LLM (that needs the live
API) — they pin the prompt text so future edits can't silently remove the
directive and reintroduce "cocksure AI" regressions.

If a future prompt rewrite intentionally removes one of these pieces, the
corresponding assertion should be deleted here — but the removal is then a
deliberate decision, not an accident.
"""

from __future__ import annotations

from dashboard_pipeline.ai.prompts import (
    SYSTEM_PROMPT_KA,
    SYSTEM_PROMPT_KA_INVESTIGATOR,
    build_system_prompt,
)


class TestSelfCritiqueDirective:
    def test_chat_prompt_has_self_critique_section(self):
        assert "თვითკრიტიკა" in SYSTEM_PROMPT_KA

    def test_chat_prompt_mentions_three_check_questions(self):
        # The three internal-reflection questions.
        assert "რა ფაქტი არ გადავამოწმე" in SYSTEM_PROMPT_KA
        assert "რაში ვარ გაურკვეველი" in SYSTEM_PROMPT_KA
        assert "რა ლოგიკური პრობლემა" in SYSTEM_PROMPT_KA

    def test_chat_prompt_has_output_structure_labels(self):
        # Structured output: Fact / Uncertain / Recommendation.
        assert "📊 ფაქტი" in SYSTEM_PROMPT_KA
        assert "⚠️ გაურკვეველი" in SYSTEM_PROMPT_KA
        assert "🎯 რეკომენდაცია" in SYSTEM_PROMPT_KA

    def test_chat_prompt_forbids_exposing_internal_check(self):
        # AI must not dump the self-check questions into the user-visible
        # output.
        assert "არასოდეს გამოიტანო internal self-check" in SYSTEM_PROMPT_KA

    def test_chat_prompt_allows_skipping_uncertain_section(self):
        # False skepticism is as harmful as false certainty — allow omitting
        # "⚠️ გაურკვეველი" when nothing is actually uncertain.
        assert "გამოტოვე" in SYSTEM_PROMPT_KA


class TestCalculatorDirective:
    def test_chat_prompt_forbids_mental_arithmetic(self):
        assert "არასოდეს" in SYSTEM_PROMPT_KA
        assert "გონებაში" in SYSTEM_PROMPT_KA

    def test_chat_prompt_references_compute_tool(self):
        assert "`compute`" in SYSTEM_PROMPT_KA

    def test_chat_prompt_references_compute_waybill_total(self):
        assert "`compute_waybill_total`" in SYSTEM_PROMPT_KA

    def test_chat_prompt_documents_compute_operations(self):
        # The 8 generic operations should be enumerated in the prompt so the
        # LLM knows what's available.
        for op in ("sum", "avg", "min", "max", "count", "pct", "growth", "diff"):
            assert f"`{op}`" in SYSTEM_PROMPT_KA

    def test_chat_prompt_three_number_threshold_mentioned(self):
        # "3-ზე მეტი რიცხვის" — any arithmetic touching >3 numbers must go
        # through a tool.
        assert "3-ზე მეტი" in SYSTEM_PROMPT_KA or "3-ზე მეტ" in SYSTEM_PROMPT_KA


class TestInvestigatorPromptUnaffected:
    """Phase 0A changes target chat mode only — investigator prompt should
    stay untouched so discrepancy-hunting behavior doesn't regress."""

    def test_investigator_prompt_is_different_text(self):
        assert SYSTEM_PROMPT_KA_INVESTIGATOR != SYSTEM_PROMPT_KA

    def test_investigator_prompt_still_has_discrepancy_sections(self):
        # Preserved from Sprint 2.
        assert "Cascade" in SYSTEM_PROMPT_KA_INVESTIGATOR
        assert "🔍 აღმოჩენა" in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_investigator_prompt_does_not_carry_chat_self_critique(self):
        # The self-critique directive is a chat-mode artifact; investigator
        # uses the Sprint 2 structured output format instead.
        assert "📊 ფაქტი" not in SYSTEM_PROMPT_KA_INVESTIGATOR


class TestStopCheckDirective:
    """Phase 0A follow-up (2026-04-19): after the live dog-food revealed that
    the LLM routinely skipped clarify on ambiguous-year questions (e.g.
    "რამდენი ზედნადები შემოვიდა დეკემბერში?" — no year), the prompt was
    hardened with an explicit STOP-CHECK section placed above all other rules.

    These tests pin the new directive so a future edit can't silently weaken
    it.
    """

    def test_chat_prompt_has_stop_check_header(self):
        assert "STOP-CHECK" in SYSTEM_PROMPT_KA

    def test_chat_prompt_stop_check_is_above_other_rules(self):
        # Must appear before the self-critique + citation sections so the LLM
        # reads it first.
        stop_idx = SYSTEM_PROMPT_KA.find("STOP-CHECK")
        critique_idx = SYSTEM_PROMPT_KA.find("თვითკრიტიკა")
        citation_idx = SYSTEM_PROMPT_KA.find("წყაროს ციტირება")
        assert 0 < stop_idx < critique_idx
        assert 0 < stop_idx < citation_idx

    def test_chat_prompt_year_check_mentions_all_four_years(self):
        # The clarify response template must enumerate the years we actually
        # have data for, so the LLM can't fallback to a bare "რომელი წელი?"
        # without listing options.
        assert "2024" in SYSTEM_PROMPT_KA
        assert "2025" in SYSTEM_PROMPT_KA
        assert "2026" in SYSTEM_PROMPT_KA

    def test_chat_prompt_stop_check_forbids_running_tool(self):
        # Core safety invariant: no tool call before clarify.
        assert "არ გაუშვა არც ერთი tool" in SYSTEM_PROMPT_KA or (
            "არ გაუშვა" in SYSTEM_PROMPT_KA and "tool" in SYSTEM_PROMPT_KA
        )

    def test_chat_prompt_blocks_short_answer_override(self):
        # "მოკლედ მითხარი" / "მხოლოდ რიცხვი" must NOT bypass clarify — this
        # was the exact regression observed in the 2026-04-19 live test.
        assert "მოკლედ მითხარი" in SYSTEM_PROMPT_KA
        assert "მხოლოდ რიცხვი" in SYSTEM_PROMPT_KA
        # And the prompt must explicitly say these do NOT override.
        assert "არ აუქმებს" in SYSTEM_PROMPT_KA or "არ აუქმებდეს" in SYSTEM_PROMPT_KA

    def test_chat_prompt_month_names_trigger_clarify(self):
        # Month-name-only questions (e.g. "დეკემბერში") must trigger clarify.
        # Pin this by checking the prompt references month names explicitly.
        assert "დეკემბერი" in SYSTEM_PROMPT_KA
        assert "იანვარი" in SYSTEM_PROMPT_KA

    def test_chat_prompt_ambiguous_verb_triggers_date_field_clarify(self):
        # Check 2: waybill date-column ambiguity must route to clarify.
        assert "რომელი თარიღით" in SYSTEM_PROMPT_KA

    def test_chat_prompt_scope_check_covers_store_axis(self):
        # Check 3: store-axis scope (ოზურგეთი vs დვაბზუ).
        assert "ოზურგეთი" in SYSTEM_PROMPT_KA
        assert "დვაბზუ" in SYSTEM_PROMPT_KA

    def test_investigator_prompt_does_not_carry_stop_check(self):
        # STOP-CHECK is a chat-mode gate; investigator uses the Sprint 2
        # triangulation flow and should not inherit it.
        assert "STOP-CHECK" not in SYSTEM_PROMPT_KA_INVESTIGATOR


class TestMultiHypothesisDirective:
    """Phase 0B.1 — Multi-hypothesis prompt directive.

    Strategic / causal / decision-type questions must produce 3 alternative
    hypotheses with probability %'s rather than a single cocksure answer.
    Pure factual queries (counts, sums, filtered totals) stay single-answer
    per the ``ფაქტობრივ კითხვებზე → ერთი პასუხი`` rule.
    """

    def test_chat_prompt_has_multi_hypothesis_section(self):
        assert "Multi-hypothesis" in SYSTEM_PROMPT_KA

    def test_chat_prompt_has_three_versions_template(self):
        assert "ვერსია 1" in SYSTEM_PROMPT_KA
        assert "ვერსია 2" in SYSTEM_PROMPT_KA
        assert "ვერსია 3" in SYSTEM_PROMPT_KA

    def test_chat_prompt_mentions_probability_percentages(self):
        # "(X% ალბათობა)" / "(Y%" / "(Z%" template must be present so the
        # LLM actually attaches probabilities instead of bare alternatives.
        assert "X% ალბათობა" in SYSTEM_PROMPT_KA
        assert "Y% ალბათობა" in SYSTEM_PROMPT_KA
        assert "Z% ალბათობა" in SYSTEM_PROMPT_KA

    def test_chat_prompt_has_strategic_trigger_keywords(self):
        # The four categories that trigger 3-version output.
        for keyword in (
            "მიზეზს",        # causal
            "გადაწყვეტილებას",  # decisional
            "სცენარს",       # scenario
            "რისკ-შეფასებას", # risk assessment
        ):
            assert keyword in SYSTEM_PROMPT_KA, f"missing trigger: {keyword!r}"

    def test_chat_prompt_factual_questions_keep_single_answer(self):
        # Critical guardrail: multi-hypothesis must NOT apply to "how many"
        # / "how much" / "what is the total" questions — those stay
        # deterministic single answers.
        assert "ერთი პასუხი" in SYSTEM_PROMPT_KA
        assert "ფაქტობრივ" in SYSTEM_PROMPT_KA

    def test_chat_prompt_probability_sum_constraint_stated(self):
        # X + Y + Z ≈ 100% — must be explicit so AI doesn't output random %s.
        assert "≈ 100%" in SYSTEM_PROMPT_KA or "100%" in SYSTEM_PROMPT_KA

    def test_chat_prompt_multi_hypothesis_does_not_replace_self_critique(self):
        # Self-Critique 📊/⚠️/🎯 remains; multi-hypothesis adds alongside.
        assert "არ ცვლის" in SYSTEM_PROMPT_KA
        # Both structures must coexist in the prompt.
        assert "📊 ფაქტი" in SYSTEM_PROMPT_KA
        assert "ვერსია 1" in SYSTEM_PROMPT_KA

    def test_investigator_prompt_does_not_carry_multi_hypothesis(self):
        # Multi-hypothesis is a chat-mode artifact; investigator uses the
        # Sprint 2 discrepancy structure (🔍/📊/🔎/📋) instead.
        assert "Multi-hypothesis" not in SYSTEM_PROMPT_KA_INVESTIGATOR
        assert "ვერსია 1" not in SYSTEM_PROMPT_KA_INVESTIGATOR


class TestBuildSystemPromptEndToEnd:
    def test_chat_build_contains_self_critique(self):
        prompt = build_system_prompt(mode="chat")
        assert "თვითკრიტიკა" in prompt
        assert "📊 ფაქტი" in prompt

    def test_chat_build_contains_stop_check(self):
        prompt = build_system_prompt(mode="chat")
        assert "STOP-CHECK" in prompt

    def test_chat_build_contains_multi_hypothesis(self):
        prompt = build_system_prompt(mode="chat")
        assert "Multi-hypothesis" in prompt
        assert "ვერსია 1" in prompt

    def test_investigate_build_does_not_contain_self_critique(self):
        prompt = build_system_prompt(mode="investigate")
        assert "თვითკრიტიკა" not in prompt
