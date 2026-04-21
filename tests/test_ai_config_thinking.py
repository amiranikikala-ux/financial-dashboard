"""Phase 0B.1 — Extended Thinking config tests.

Covers:
- AIConfig defaults (enable_thinking=False, thinking_budget_tokens=5000).
- ``load_ai_config`` env-var parsing (``AI_ENABLE_THINKING``,
  ``AI_THINKING_BUDGET``).
- Internal helpers ``_parse_bool`` and ``_parse_thinking_budget`` — spelling
  variants, empty / None, clamp to 1024-token floor.
- ``redacted()`` surface exposes the new fields without echoing the API key.

No live Anthropic call; pure config-loader coverage.
"""

from typing import Dict

import pytest

from dashboard_pipeline.ai.config import (
    AIConfig,
    _MIN_THINKING_BUDGET,
    _parse_bool,
    _parse_thinking_budget,
    load_ai_config,
)


@pytest.fixture
def clean_env(monkeypatch):
    """Reset every AI-config env var so each test starts from a blank slate."""
    for key in (
        "ANTHROPIC_API_KEY",
        "AI_MODEL",
        "AI_MODEL_FALLBACK",
        "AI_MAX_TOKENS",
        "AI_TEMPERATURE",
        "AI_ENABLE_THINKING",
        "AI_THINKING_BUDGET",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-0123456789abcdef")


class TestAIConfigDefaults:
    """AIConfig should default to a safe, feature-flag-off state for Phase 0B.1."""

    def test_enable_thinking_defaults_false(self):
        cfg = AIConfig(api_key="sk-ant-test")
        assert cfg.enable_thinking is False

    def test_thinking_budget_defaults_to_5000(self):
        cfg = AIConfig(api_key="sk-ant-test")
        assert cfg.thinking_budget_tokens == 5000

    def test_default_thinking_budget_is_above_anthropic_floor(self):
        # Sanity: whatever default we pick must satisfy Anthropic's requirement.
        cfg = AIConfig(api_key="sk-ant-test")
        assert cfg.thinking_budget_tokens >= _MIN_THINKING_BUDGET

    def test_explicit_thinking_config_survives(self):
        cfg = AIConfig(
            api_key="sk-ant-test",
            enable_thinking=True,
            thinking_budget_tokens=8192,
        )
        assert cfg.enable_thinking is True
        assert cfg.thinking_budget_tokens == 8192


class TestRedactedSurfaceExposesThinking:
    def test_redacted_exposes_enable_thinking(self):
        cfg = AIConfig(api_key="sk-ant-test", enable_thinking=True)
        dump: Dict = cfg.redacted()
        assert dump["enable_thinking"] is True

    def test_redacted_exposes_thinking_budget(self):
        cfg = AIConfig(
            api_key="sk-ant-test",
            enable_thinking=True,
            thinking_budget_tokens=6000,
        )
        dump: Dict = cfg.redacted()
        assert dump["thinking_budget_tokens"] == 6000

    def test_redacted_never_leaks_api_key_even_with_thinking_enabled(self):
        cfg = AIConfig(
            api_key="sk-ant-supersecret-DO-NOT-LEAK-0123456789",
            enable_thinking=True,
        )
        dump = cfg.redacted()
        # key must be a length + prefix-only indicator, never the raw value
        assert "supersecret" not in str(dump)
        assert dump["api_key_prefix"].startswith("sk-ant-")
        assert dump["api_key_prefix"].endswith("...")


class TestParseBool:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("1", True),
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("yes", True),
            ("Yes", True),
            ("on", True),
            ("ON", True),
            (" true ", True),  # whitespace tolerated
            ("0", False),
            ("false", False),
            ("FALSE", False),
            ("no", False),
            ("off", False),
            (" false ", False),
        ],
    )
    def test_recognized_spellings(self, raw, expected):
        assert _parse_bool(raw, default=not expected) is expected

    def test_none_returns_default(self):
        assert _parse_bool(None, default=True) is True
        assert _parse_bool(None, default=False) is False

    def test_empty_string_returns_default(self):
        assert _parse_bool("", default=True) is True
        assert _parse_bool("   ", default=False) is False

    def test_unknown_spelling_returns_default(self):
        # Typos / unrelated strings fall back to the default rather than
        # silently flipping semantics.
        assert _parse_bool("maybe", default=False) is False
        assert _parse_bool("enabled", default=True) is True
        assert _parse_bool("2", default=False) is False


class TestParseThinkingBudget:
    def test_returns_default_when_raw_is_none(self):
        assert _parse_thinking_budget(None, default=5000) == 5000

    def test_returns_default_when_raw_is_empty(self):
        assert _parse_thinking_budget("", default=5000) == 5000
        assert _parse_thinking_budget("   ", default=5000) == 5000

    def test_parses_integer_string(self):
        assert _parse_thinking_budget("8192", default=5000) == 8192

    def test_clamps_below_anthropic_floor(self):
        # Anthropic requires budget_tokens >= 1024. Anything less gets
        # promoted silently so the API call doesn't 400.
        assert _parse_thinking_budget("500", default=5000) == _MIN_THINKING_BUDGET
        assert _parse_thinking_budget("0", default=5000) == _MIN_THINKING_BUDGET
        assert _parse_thinking_budget("1023", default=5000) == _MIN_THINKING_BUDGET

    def test_accepts_exact_minimum(self):
        assert _parse_thinking_budget("1024", default=5000) == 1024

    def test_invalid_integer_falls_back_to_default_then_clamps(self):
        # _parse_int falls back to default (5000) on garbage, then clamp is
        # a no-op because 5000 > 1024.
        assert _parse_thinking_budget("not-a-number", default=5000) == 5000

    def test_invalid_integer_with_low_default_clamps_to_floor(self):
        # Defensive: if someone passes a default below the floor, we still
        # clamp. (The baked-in module default is 5000, so this is guard-rail
        # only.)
        assert _parse_thinking_budget("garbage", default=500) == _MIN_THINKING_BUDGET


class TestLoadAIConfigThinkingEnvVars:
    def test_defaults_when_env_vars_absent(self, clean_env):
        cfg = load_ai_config()
        assert cfg.enable_thinking is False
        assert cfg.thinking_budget_tokens == 5000

    def test_ai_enable_thinking_true(self, clean_env, monkeypatch):
        monkeypatch.setenv("AI_ENABLE_THINKING", "true")
        cfg = load_ai_config()
        assert cfg.enable_thinking is True

    def test_ai_enable_thinking_various_true_spellings(self, clean_env, monkeypatch):
        for spelling in ("1", "TRUE", "yes", "on"):
            monkeypatch.setenv("AI_ENABLE_THINKING", spelling)
            cfg = load_ai_config()
            assert cfg.enable_thinking is True, f"spelling={spelling!r}"

    def test_ai_enable_thinking_various_false_spellings(self, clean_env, monkeypatch):
        for spelling in ("0", "false", "no", "off", ""):
            monkeypatch.setenv("AI_ENABLE_THINKING", spelling)
            cfg = load_ai_config()
            assert cfg.enable_thinking is False, f"spelling={spelling!r}"

    def test_ai_thinking_budget_custom_value(self, clean_env, monkeypatch):
        monkeypatch.setenv("AI_THINKING_BUDGET", "12000")
        cfg = load_ai_config()
        assert cfg.thinking_budget_tokens == 12000

    def test_ai_thinking_budget_clamped_when_below_floor(
        self, clean_env, monkeypatch
    ):
        monkeypatch.setenv("AI_THINKING_BUDGET", "256")
        cfg = load_ai_config()
        assert cfg.thinking_budget_tokens == _MIN_THINKING_BUDGET

    def test_ai_thinking_budget_garbage_falls_back_to_default(
        self, clean_env, monkeypatch
    ):
        monkeypatch.setenv("AI_THINKING_BUDGET", "plenty")
        cfg = load_ai_config()
        assert cfg.thinking_budget_tokens == 5000  # module default


class TestThinkingDoesNotBreakExistingFields:
    """Sanity guard — adding 2 fields to AIConfig must not shift defaults
    on pre-existing fields. Tests pre-Phase 0B.1 behavior continues."""

    def test_model_default_unchanged(self):
        cfg = AIConfig(api_key="sk-ant-test")
        assert cfg.model == "claude-sonnet-4-6"

    def test_max_tokens_default_unchanged(self):
        cfg = AIConfig(api_key="sk-ant-test")
        assert cfg.max_tokens == 4096

    def test_temperature_default_unchanged(self):
        cfg = AIConfig(api_key="sk-ant-test")
        assert cfg.temperature == pytest.approx(0.3)

    def test_is_enabled_still_guards_on_api_key(self):
        cfg_good = AIConfig(api_key="sk-ant-test")
        cfg_bad = AIConfig(api_key="garbage")
        assert cfg_good.is_enabled is True
        assert cfg_bad.is_enabled is False
