"""Prompt-guard tests for Sprint 4B.3 — Tier 4 Workflow Anti-patterns.

Pins the 4 Tier-4 rules from `PHASE_4B_PROMPT_TUNING_PREVIEW.md`:

- Rule 22 Ruthlessly prune (code.claude.com) — in AGENTS.md
- Rule 23 Kitchen sink session (code.claude.com) — in AGENTS.md
- Rule 24 General-purpose solution (docs.anthropic.com) — in SYSTEM_PROMPT_KA
- Rule 25 2× correction → restart (code.claude.com) — in `.claude/commands/restart-session.md`

These rules target workflow discipline more than in-prompt behavior, so
assertions span three files. Lightweight guard — ~15 cases.

Investigator prompt stays untouched (do-not-touch rule).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dashboard_pipeline.ai.prompts import (
    SYSTEM_PROMPT_KA,
    SYSTEM_PROMPT_KA_INVESTIGATOR,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENTS_MD = PROJECT_ROOT / "AGENTS.md"
RESTART_CMD = PROJECT_ROOT / ".claude" / "commands" / "restart-session.md"


# ---------------------------------------------------------------------------
# 🧹 Rule 22 — Ruthlessly prune (AGENTS.md)
# ---------------------------------------------------------------------------


class TestRule22RuthlesslyPrune:
    def test_agents_md_has_prompt_hygiene_section(self):
        assert AGENTS_MD.exists()
        text = AGENTS_MD.read_text(encoding="utf-8")
        assert "Prompt Hygiene" in text
        assert "Ruthlessly prune" in text

    def test_section_tagged_phase_4b3_rule_22(self):
        text = AGENTS_MD.read_text(encoding="utf-8")
        assert "Phase 4B.3 Rule 22" in text

    def test_thousand_line_threshold_cited(self):
        text = AGENTS_MD.read_text(encoding="utf-8")
        # The 1000-line threshold is Anthropic's explicit guidance
        assert ">1000-line" in text

    def test_grep_assertion_rule_present(self):
        text = AGENTS_MD.read_text(encoding="utf-8")
        # Every new rule must have grep coverage
        assert "grep-assertion" in text


# ---------------------------------------------------------------------------
# 📦 Rule 23 — Kitchen-sink session (AGENTS.md)
# ---------------------------------------------------------------------------


class TestRule23KitchenSink:
    def test_session_boundaries_section_present(self):
        text = AGENTS_MD.read_text(encoding="utf-8")
        assert "Session Boundaries" in text

    def test_no_kitchen_sink_rule(self):
        text = AGENTS_MD.read_text(encoding="utf-8")
        assert "No kitchen-sink sessions" in text

    def test_one_session_one_goal(self):
        text = AGENTS_MD.read_text(encoding="utf-8")
        assert "ერთი session = ერთი logical goal" in text

    def test_restart_command_cross_referenced(self):
        text = AGENTS_MD.read_text(encoding="utf-8")
        assert "/restart-session" in text


# ---------------------------------------------------------------------------
# 🎯 Rule 24 — General-purpose solution (SYSTEM_PROMPT_KA)
# ---------------------------------------------------------------------------


class TestRule24GeneralPurpose:
    def test_subsection_header_present(self):
        assert "🎯 General-purpose solution" in SYSTEM_PROMPT_KA

    def test_rule_tagged_phase_4b3_tier_4(self):
        assert "Phase 4B.3 Tier 4" in SYSTEM_PROMPT_KA

    def test_ozurgeti_worked_example(self):
        # The რა ვქნა? example proves the principle is behavioral
        assert "ოზურგეთში margin დაცემულია, რა ვქნა?" in SYSTEM_PROMPT_KA

    def test_both_stores_principle_stated(self):
        assert "ორივე მაღაზიაზე" in SYSTEM_PROMPT_KA

    def test_test_hardcoding_anti_pattern(self):
        # Anti-pattern: answer scoped to single test, breaks on variation
        assert "test-hard-coded answers" in SYSTEM_PROMPT_KA

    def test_compute_waybill_total_generality(self):
        # The compute_waybill_total any-date example
        assert "ნებისმიერი" in SYSTEM_PROMPT_KA


# ---------------------------------------------------------------------------
# 🔄 Rule 25 — 2× correction → restart (.claude/commands/restart-session.md)
# ---------------------------------------------------------------------------


class TestRule25CorrectionRestart:
    def test_restart_command_file_exists(self):
        assert RESTART_CMD.exists(), f"missing: {RESTART_CMD}"

    def test_command_file_has_frontmatter(self):
        text = RESTART_CMD.read_text(encoding="utf-8")
        assert text.startswith("---")
        assert "name: restart-session" in text
        assert "description:" in text

    def test_trigger_signals_enumerated(self):
        text = RESTART_CMD.read_text(encoding="utf-8")
        assert "Trigger signals" in text
        assert "იგივე შეცდომა გამისწორა 2-ჯერ" in text

    def test_do_not_trigger_list_present(self):
        # Rule must distinguish restart-worthy mistakes from valid scope shifts
        text = RESTART_CMD.read_text(encoding="utf-8")
        assert "Do NOT trigger on" in text

    def test_agents_md_references_correction_rule(self):
        text = AGENTS_MD.read_text(encoding="utf-8")
        assert "Correction Escalation" in text
        assert "Phase 4B.3 Rule 25" in text
        # 3× forbidden — restart on 2×
        assert "3-ჯერ" in text

    def test_workflow_includes_context_handoff_refresh(self):
        text = RESTART_CMD.read_text(encoding="utf-8")
        assert "CONTEXT_HANDOFF.md" in text


# ---------------------------------------------------------------------------
# 🛡 Investigator prompt do-not-touch (Rule 24 marker absent)
# ---------------------------------------------------------------------------


class TestInvestigatorPromptUntouched:
    MARKERS = (
        "🎯 General-purpose solution",
        "Phase 4B.3 Tier 4",
        "ოზურგეთში margin დაცემულია",
        "test-hard-coded answers",
    )

    @pytest.mark.parametrize("marker", MARKERS)
    def test_marker_absent(self, marker):
        assert marker not in SYSTEM_PROMPT_KA_INVESTIGATOR, marker
