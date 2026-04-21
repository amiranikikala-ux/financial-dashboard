"""Prompt-guard tests for Phase 1 Part D — Self-Correction Loop.

Pins the new 🔄 section in ``SYSTEM_PROMPT_KA`` so future refactors cannot
silently drop the retry protocol + Latin alias MANDATE + self-triage rules that
turn retrieval failures into false-negative "ვერ ვიპოვე" answers.

Trigger incident: 2026-04-20 02:30 BOG 2026-02 chat — AI answered "ფაილი არ მაქვს"
after a single weak query against ChromaDB; the file was indexed all along.
Phase 1 Part D ensures retrieval resilience: minimum 3 query retries, MANDATORY
Latin alias for 3-letter Georgian abbreviations, explicit date-format triage,
and a structured "ვერ ვიპოვე" fallback that lists the attempted queries.

Investigator prompt must stay **untouched** through Phase 1 (carry-over
do-not-touch rule from Sprint 1/2/3/4 AND Phase 1 Part A AND Part B AND Part C)
— final guard at the bottom of this module asserts that.
"""

from __future__ import annotations

from dashboard_pipeline.ai.prompts import (
    SYSTEM_PROMPT_KA,
    SYSTEM_PROMPT_KA_INVESTIGATOR,
    build_system_prompt,
)


# ---------------------------------------------------------------------------
# 🔄 Section anchor + intro rules
# ---------------------------------------------------------------------------


class TestSelfCorrectionSection:
    def test_section_header_present(self):
        assert "🔄 საკუთარი თავის გასწორების ციკლი" in SYSTEM_PROMPT_KA

    def test_section_tagged_phase_1_part_d(self):
        assert "Phase 1 Part D" in SYSTEM_PROMPT_KA

    def test_intro_declares_empty_not_missing(self):
        # Core anti-false-negative contract: empty result != "does not exist"
        assert "≠ \"არ არსებობს\"" in SYSTEM_PROMPT_KA

    def test_minimum_three_retries_rule_present(self):
        assert "მინიმუმ 3-ჯერ" in SYSTEM_PROMPT_KA

    def test_first_attempt_negative_answer_forbidden(self):
        assert "პირველ ცდაზე" in SYSTEM_PROMPT_KA
        assert "აკრძალულია" in SYSTEM_PROMPT_KA

    def test_section_placed_after_multi_store_dna_before_source_hierarchy(self):
        dna_idx = SYSTEM_PROMPT_KA.find("🏪 მაღაზიების DNA")
        self_correct_idx = SYSTEM_PROMPT_KA.find(
            "🔄 საკუთარი თავის გასწორების ციკლი"
        )
        hierarchy_idx = SYSTEM_PROMPT_KA.find("⚖️ წყაროების იერარქია")
        assert dna_idx != -1
        assert self_correct_idx != -1
        assert hierarchy_idx != -1
        assert dna_idx < self_correct_idx < hierarchy_idx


# ---------------------------------------------------------------------------
# 🔁 Retry Protocol (4-step table)
# ---------------------------------------------------------------------------


class TestRetryProtocol:
    def test_retry_protocol_header_present(self):
        assert "🔁 Retry Protocol" in SYSTEM_PROMPT_KA

    def test_four_step_table_present(self):
        # The table enumerates 1-2-3-4 steps explicitly in the cells
        # After the header, each step row starts with | **N** |
        for step_marker in ("| **1** |", "| **2** |", "| **3** |", "| **4** |"):
            assert step_marker in SYSTEM_PROMPT_KA, step_marker

    def test_step_1_user_phrase_verbatim(self):
        assert "User-ის ფრაზა 1-1-ზე" in SYSTEM_PROMPT_KA

    def test_step_2_latin_alias_full_phrase_required(self):
        assert "Bank of Georgia" in SYSTEM_PROMPT_KA
        # Anti-pattern guard: "არა \"BOG\"" tells AI that 3-letter alone is wrong
        assert 'არა "BOG"' in SYSTEM_PROMPT_KA

    def test_step_3_date_three_formats_mention(self):
        assert "თარიღი 3 ფორმატით" in SYSTEM_PROMPT_KA

    def test_step_4_file_or_folder_fallback(self):
        assert "ფაილის სახელი" in SYSTEM_PROMPT_KA
        assert "ფოლდერი" in SYSTEM_PROMPT_KA

    def test_bog_2026_example_query_in_protocol(self):
        # The trigger incident lives as an example in the prompt
        assert "BOG 2026-02 ჩარიცხვა" in SYSTEM_PROMPT_KA

    def test_query_progression_shows_incremental_enrichment(self):
        # Step 2 introduces the Latin alias the first attempt was missing
        assert "ბოგ ბანკი BOG Bank of Georgia 2026-02" in SYSTEM_PROMPT_KA
        # Step 3 adds the English month + domain keyword
        assert "Bank of Georgia February 2026" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🎯 Self-Triage — 3 hypotheses
# ---------------------------------------------------------------------------


class TestSelfTriage:
    def test_self_triage_header_present(self):
        assert "🎯 Self-Triage" in SYSTEM_PROMPT_KA

    def test_zero_hit_hypothesis_present(self):
        assert "0 hit" in SYSTEM_PROMPT_KA
        assert "Query ძალიან ვიწროა" in SYSTEM_PROMPT_KA

    def test_five_plus_hit_hypothesis_present(self):
        assert "5+ hit" in SYSTEM_PROMPT_KA
        assert "Latin alias სუსტია" in SYSTEM_PROMPT_KA

    def test_off_topic_hypothesis_present(self):
        assert "Off-topic" in SYSTEM_PROMPT_KA
        assert "Embedding ურევს" in SYSTEM_PROMPT_KA

    def test_domain_anchor_keywords_listed(self):
        for anchor in ("ამონაწერი", "ანგარიში", "POS", "ტერმინალი"):
            assert anchor in SYSTEM_PROMPT_KA, anchor

    def test_three_hypothesis_rows_present(self):
        # Count symptom-hypothesis rows by the section delimiter
        triage_section_start = SYSTEM_PROMPT_KA.find("🎯 Self-Triage")
        latin_mandate_start = SYSTEM_PROMPT_KA.find("📢 Latin Alias")
        assert triage_section_start != -1
        assert latin_mandate_start != -1
        triage_block = SYSTEM_PROMPT_KA[triage_section_start:latin_mandate_start]
        # Exactly 3 hypothesis rows live between header and next section
        assert triage_block.count("Query ძალიან ვიწროა") == 1
        assert triage_block.count("Latin alias სუსტია") == 1
        assert triage_block.count("Embedding ურევს") == 1


# ---------------------------------------------------------------------------
# 📢 Latin Alias MANDATE
# ---------------------------------------------------------------------------


class TestLatinAliasMandate:
    def test_latin_alias_section_header_present(self):
        assert "📢 Latin Alias — MANDATORY" in SYSTEM_PROMPT_KA

    def test_bog_maps_to_bank_of_georgia(self):
        # Row: ბოგ | Bank of Georgia | BOG alone forbidden
        assert "| **ბოგ** |" in SYSTEM_PROMPT_KA
        assert "`Bank of Georgia`" in SYSTEM_PROMPT_KA

    def test_tbs_maps_to_tbc(self):
        assert "| **თბს** |" in SYSTEM_PROMPT_KA
        assert "`TBC`" in SYSTEM_PROMPT_KA

    def test_rs_maps_to_revenue_service(self):
        assert "| **რს** |" in SYSTEM_PROMPT_KA
        assert "`Revenue Service`" in SYSTEM_PROMPT_KA

    def test_anti_pattern_explicitly_forbidden(self):
        # Anti-patterns: BOG alone / TBS (not TBC) / RS alone
        assert "ANTI-PATTERN" in SYSTEM_PROMPT_KA
        assert '"BOG" alone' in SYSTEM_PROMPT_KA
        assert '"RS" alone' in SYSTEM_PROMPT_KA

    def test_mandatory_keyword_present(self):
        assert "MANDATORY" in SYSTEM_PROMPT_KA

    def test_reliability_tradeoff_stated(self):
        # "სრული ფრაზა = საიმედო match; 3-ასოიანი alone = random ბანკი"
        assert "საიმედო match" in SYSTEM_PROMPT_KA
        assert "random ბანკი" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 📅 Date Triage
# ---------------------------------------------------------------------------


class TestDateTriage:
    def test_date_triage_header_present(self):
        assert "📅 თარიღის 3 ფორმატი" in SYSTEM_PROMPT_KA

    def test_yyyy_mm_format_listed(self):
        assert "`YYYY-MM`" in SYSTEM_PROMPT_KA
        assert "`2026-02`" in SYSTEM_PROMPT_KA

    def test_month_yyyy_format_listed(self):
        assert "`Month YYYY`" in SYSTEM_PROMPT_KA
        assert "`February 2026`" in SYSTEM_PROMPT_KA

    def test_georgian_month_format_listed(self):
        assert "`ქართული თვე YYYY`" in SYSTEM_PROMPT_KA
        assert "`2026 თებერვალი`" in SYSTEM_PROMPT_KA

    def test_second_attempt_trigger_mentioned(self):
        # Date triage activates on the 2nd retry, not the 1st
        assert "მე-2 ცდაზე" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# ❌ "Can't find" gate
# ---------------------------------------------------------------------------


class TestCannotFindGate:
    def test_cant_find_section_header_present(self):
        assert "❌ \"ვერ ვიპოვე\"" in SYSTEM_PROMPT_KA

    def test_three_plus_retries_prerequisite(self):
        assert "3+ ცდის შემდეგ" in SYSTEM_PROMPT_KA

    def test_example_output_lists_attempts(self):
        # The example quote must show 3 enumerated attempts
        assert "ვცადე:" in SYSTEM_PROMPT_KA
        assert "(1)" in SYSTEM_PROMPT_KA
        assert "(2)" in SYSTEM_PROMPT_KA
        assert "(3)" in SYSTEM_PROMPT_KA

    def test_example_output_asks_user_to_clarify(self):
        # AI must invite user to disambiguate after 3 failures
        assert "დააზუსტე" in SYSTEM_PROMPT_KA

    def test_attempts_work_shown_not_only_conclusion(self):
        # "ცდის შრომა, არა მხოლოდ დასკვნა"
        assert "ცდის შრომა" in SYSTEM_PROMPT_KA

    def test_bare_no_data_forbidden(self):
        # "არასოდეს არ თქვა \"არ მაქვს\" ცდების ჩამოყალიბების გარეშე"
        assert "არასოდეს" in SYSTEM_PROMPT_KA
        assert "ცდების ჩამოყალიბების გარეშე" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# Build system prompt wiring (chat vs investigator)
# ---------------------------------------------------------------------------


class TestBuildSystemPromptWiring:
    def test_chat_prompt_contains_self_correction_section(self):
        chat_prompt = build_system_prompt(mode="chat")
        assert "🔄 საკუთარი თავის გასწორების ციკლი" in chat_prompt

    def test_chat_prompt_contains_retry_protocol(self):
        chat_prompt = build_system_prompt(mode="chat")
        assert "🔁 Retry Protocol" in chat_prompt

    def test_chat_prompt_contains_latin_alias_mandate(self):
        chat_prompt = build_system_prompt(mode="chat")
        assert "📢 Latin Alias — MANDATORY" in chat_prompt
        assert "MANDATORY" in chat_prompt

    def test_investigator_prompt_lacks_self_correction_section(self):
        investigator_prompt = build_system_prompt(mode="investigate")
        assert "🔄 საკუთარი თავის გასწორების ციკლი" not in investigator_prompt
        assert "Phase 1 Part D" not in investigator_prompt


# ---------------------------------------------------------------------------
# Investigator prompt do-not-touch (carry-over: Sprint 1/2/3/4 + Part A/B/C + D)
# ---------------------------------------------------------------------------


class TestInvestigatorPromptUntouched:
    def test_no_phase_1_part_d_tag(self):
        assert "Phase 1 Part D" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_no_self_correction_section_header(self):
        assert (
            "🔄 საკუთარი თავის გასწორების ციკლი"
            not in SYSTEM_PROMPT_KA_INVESTIGATOR
        )

    def test_no_retry_protocol_header(self):
        assert "🔁 Retry Protocol" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_no_self_triage_header(self):
        assert "🎯 Self-Triage" not in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_no_latin_alias_mandate_header(self):
        assert (
            "📢 Latin Alias — MANDATORY"
            not in SYSTEM_PROMPT_KA_INVESTIGATOR
        )

    def test_fifteen_part_d_markers_all_absent(self):
        markers = (
            "Phase 1 Part D",
            "🔄 საკუთარი თავის გასწორების ციკლი",
            "🔁 Retry Protocol",
            "🎯 Self-Triage",
            "📢 Latin Alias — MANDATORY",
            "📅 თარიღის 3 ფორმატი",
            "მინიმუმ 3-ჯერ",
            "Query ძალიან ვიწროა",
            "Latin alias სუსტია",
            "Embedding ურევს",
            "ANTI-PATTERN",
            "საიმედო match",
            "3+ ცდის შემდეგ",
            "ცდის შრომა",
            'არა "BOG"',
        )
        for marker in markers:
            assert (
                marker not in SYSTEM_PROMPT_KA_INVESTIGATOR
            ), f"investigator prompt leaked Part D marker: {marker!r}"


# ---------------------------------------------------------------------------
# Phase 1 prior parts (A + B + C) still present
# ---------------------------------------------------------------------------


class TestPhase1PriorPartsStillPresent:
    def test_part_a_role_contract_still_present(self):
        assert "🎯 როლის კონტრაქტი" in SYSTEM_PROMPT_KA

    def test_part_a_five_hats_still_present(self):
        assert "🎭 5 ქუდი" in SYSTEM_PROMPT_KA or "🎭" in SYSTEM_PROMPT_KA

    def test_part_b_georgian_regulation_still_present(self):
        assert "🇬🇪 ქართული რეგულაცია" in SYSTEM_PROMPT_KA

    def test_part_b_monthly_rhythm_still_present(self):
        assert "🌅 ქართული თვის რიტმი" in SYSTEM_PROMPT_KA

    def test_part_c_multi_store_dna_still_present(self):
        assert "🏪 მაღაზიების DNA" in SYSTEM_PROMPT_KA

    def test_part_c_ozurgeti_urban_flagship_still_present(self):
        assert "🏪 ოზურგეთი — Urban Flagship" in SYSTEM_PROMPT_KA

    def test_part_c_dvabzu_rural_local_still_present(self):
        assert "🏡 დვაბზუ — Rural Local" in SYSTEM_PROMPT_KA
