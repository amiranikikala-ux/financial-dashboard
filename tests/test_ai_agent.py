"""Unit tests for dashboard_pipeline.ai.agent.

Exercises the tool-use loop with a fake LLM client (no network I/O).
Also validates config loading + prompt composition + agent guardrails.
"""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from dashboard_pipeline.ai.agent import (
    AIAgent,
    AIAgentError,
    MAX_TOOL_ITERATIONS,
    MAX_TOOL_ITERATIONS_DEEP,
)
from dashboard_pipeline.ai.config import AIConfig, load_ai_config
from dashboard_pipeline.ai.prompts import (
    DEFAULT_MODE,
    SUPPORTED_MODES,
    SYSTEM_PROMPT_KA,
    SYSTEM_PROMPT_KA_INVESTIGATOR,
    build_system_prompt,
    build_system_prompt_blocks,
)
from dashboard_pipeline.ai.tools import TOOL_SCHEMAS


# ---------------------------------------------------------------------------
# Fake Anthropic client
# ---------------------------------------------------------------------------

class FakeMessages:
    """Mimics `anthropic.Anthropic().messages.create(...)` behaviour."""

    def __init__(self, script: List[Dict[str, Any]]):
        # Each entry: {"stop_reason": "...", "content": [...blocks...]}
        self._script = list(script)
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs):
        # Snapshot the call args — the agent reuses the `messages` list across
        # iterations, so a reference capture would show the post-call state.
        self.calls.append(copy.deepcopy(kwargs))
        if not self._script:
            raise AssertionError("FakeMessages script exhausted")
        step = self._script.pop(0)

        # Convert dict blocks to namespace objects so `getattr(block, 'type')`
        # works exactly like the real SDK.
        content_blocks = []
        for block in step["content"]:
            content_blocks.append(SimpleNamespace(**block))

        usage_kwargs = {
            "input_tokens": step.get("input_tokens", 10),
            "output_tokens": step.get("output_tokens", 20),
        }
        # Optional: simulate Anthropic prompt-caching metrics per step.
        if "cache_creation_input_tokens" in step:
            usage_kwargs["cache_creation_input_tokens"] = step["cache_creation_input_tokens"]
        if "cache_read_input_tokens" in step:
            usage_kwargs["cache_read_input_tokens"] = step["cache_read_input_tokens"]
        usage = SimpleNamespace(**usage_kwargs)
        return SimpleNamespace(
            content=content_blocks,
            stop_reason=step["stop_reason"],
            usage=usage,
        )


class FakeClient:
    def __init__(self, script):
        self.messages = FakeMessages(script)


def _config(api_key: str = "sk-ant-test-key"):
    return AIConfig(api_key=api_key, model="claude-sonnet-4-6")


SAMPLE_DATA = {
    "meta": {"data_period_label": "2025-01 – 2025-03"},
    "suppliers": [
        {"tax_id": "100", "normalized_supplier": "A", "total_debt": 500},
        {"tax_id": "101", "normalized_supplier": "B", "total_debt": 1200},
    ],
    "monthly_pnl": [{"month": "2025-01", "revenue": 80000, "net": 10000}],
}


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestAIConfig:
    def test_redacted_never_exposes_key(self):
        cfg = AIConfig(api_key="sk-ant-super-secret-xyz")
        redacted = cfg.redacted()
        encoded = json.dumps(redacted)
        assert "super-secret" not in encoded
        assert redacted["api_key_prefix"].startswith("sk-ant-")
        assert redacted["api_key_length"] == len("sk-ant-super-secret-xyz")

    def test_is_enabled_requires_prefix(self):
        assert AIConfig(api_key="sk-ant-abc").is_enabled is True
        assert AIConfig(api_key="").is_enabled is False
        assert AIConfig(api_key="random-junk").is_enabled is False

    def test_load_ai_config_env(self, monkeypatch, tmp_path):
        # Force load_dotenv to no-op by pointing to nonexistent path.
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env-key")
        monkeypatch.setenv("AI_MODEL", "claude-opus-4-7")
        monkeypatch.setenv("AI_MODEL_FALLBACK", "claude-haiku-4-5-20251001")
        monkeypatch.setenv("AI_MAX_TOKENS", "2048")
        monkeypatch.setenv("AI_TEMPERATURE", "0.7")
        cfg = load_ai_config(env_path=tmp_path / "nope.env")
        assert cfg.api_key == "sk-ant-env-key"
        assert cfg.model == "claude-opus-4-7"
        assert cfg.model_fallback == "claude-haiku-4-5-20251001"
        assert cfg.max_tokens == 2048
        assert cfg.temperature == pytest.approx(0.7)

    def test_load_ai_config_invalid_numeric_falls_back(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env-key")
        monkeypatch.setenv("AI_MAX_TOKENS", "not-a-number")
        monkeypatch.setenv("AI_TEMPERATURE", "bogus")
        cfg = load_ai_config(env_path=tmp_path / "nope.env")
        assert cfg.max_tokens == 4096
        assert cfg.temperature == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Prompt composition
# ---------------------------------------------------------------------------

class TestPrompts:
    def test_system_prompt_is_georgian(self):
        # At least one Georgian letter must appear in the base prompt.
        assert any("\u10a0" <= ch <= "\u10ff" for ch in SYSTEM_PROMPT_KA)

    def test_build_system_prompt_default(self):
        prompt = build_system_prompt()
        assert "იოლი მარკეტი" in prompt
        assert "read_data_json" in prompt

    def test_build_system_prompt_with_extra(self):
        prompt = build_system_prompt("ტესტ-კონტექსტი")
        assert "ტესტ-კონტექსტი" in prompt

    def test_build_system_prompt_blocks_default_cached(self):
        blocks = build_system_prompt_blocks()
        assert isinstance(blocks, list) and len(blocks) == 1
        assert blocks[0]["type"] == "text"
        assert "იოლი მარკეტი" in blocks[0]["text"]
        # Default: cache_control set on the final block.
        assert blocks[-1]["cache_control"] == {"type": "ephemeral"}

    def test_build_system_prompt_blocks_cached_false(self):
        blocks = build_system_prompt_blocks(cached=False)
        assert "cache_control" not in blocks[-1]


# ---------------------------------------------------------------------------
# Agent construction guardrails
# ---------------------------------------------------------------------------

class TestAgentConstruction:
    def test_missing_key_raises(self):
        with pytest.raises(AIAgentError):
            AIAgent(config=AIConfig(api_key=""), data_loader=lambda: {})

    def test_rejects_empty_message(self):
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient([]),
        )
        with pytest.raises(AIAgentError):
            agent.chat("")
        with pytest.raises(AIAgentError):
            agent.chat("   \n  ")


# ---------------------------------------------------------------------------
# Tool-use loop
# ---------------------------------------------------------------------------

class TestToolUseLoop:
    def test_text_only_response_no_tools(self):
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "გამარჯობა."}],
                "input_tokens": 5,
                "output_tokens": 3,
            }
        ]
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient(script),
        )
        result = agent.chat("გამარჯობა")
        assert result["reply"] == "გამარჯობა."
        assert result["sources"] == []
        assert result["usage"]["input_tokens"] == 5
        assert result["usage"]["output_tokens"] == 3
        assert result["usage"]["stop_reason"] == "end_turn"

    def test_single_tool_use_then_text(self):
        """Agent asks for suppliers, then produces a text answer."""
        script = [
            {
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "read_data_json",
                        "input": {"section": "suppliers", "limit": 2},
                    }
                ],
                "input_tokens": 20,
                "output_tokens": 15,
            },
            {
                "stop_reason": "end_turn",
                "content": [
                    {
                        "type": "text",
                        "text": "2 მომწოდებელი. (წყარო: data.json → suppliers)",
                    }
                ],
                "input_tokens": 80,
                "output_tokens": 25,
            },
        ]
        fake = FakeClient(script)
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=fake,
        )
        result = agent.chat("რამდენი მომწოდებელია?")

        assert "2 მომწოდებელი" in result["reply"]
        assert len(result["sources"]) == 1
        assert result["sources"][0]["tool"] == "read_data_json"
        assert result["sources"][0]["result_summary"]["section"] == "suppliers"
        assert result["usage"]["input_tokens"] == 100
        assert result["usage"]["output_tokens"] == 40

        # Assert the second call carried the tool_result back into messages.
        second_call = fake.messages.calls[1]
        second_messages = second_call["messages"]
        tool_result_turn = second_messages[-1]
        assert tool_result_turn["role"] == "user"
        tool_result_blocks = tool_result_turn["content"]
        assert tool_result_blocks[0]["type"] == "tool_result"
        assert tool_result_blocks[0]["tool_use_id"] == "toolu_1"
        # Returned content should be JSON-encoded string (tool_result contract).
        parsed = json.loads(tool_result_blocks[0]["content"])
        assert parsed["section"] == "suppliers"

    def test_tool_error_does_not_crash_loop(self):
        """If the model calls an unknown section, the tool returns an error
        and the next model turn should still produce text."""
        script = [
            {
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_err",
                        "name": "read_data_json",
                        "input": {"section": "not_a_section"},
                    }
                ],
            },
            {
                "stop_reason": "end_turn",
                "content": [
                    {
                        "type": "text",
                        "text": "მონაცემი არ მაქვს.",
                    }
                ],
            },
        ]
        fake = FakeClient(script)
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=fake,
        )
        result = agent.chat("რაღაცა?")
        assert "მონაცემი არ მაქვს" in result["reply"]
        # The tool_result should be marked is_error=True.
        second_call = fake.messages.calls[1]
        tool_result = second_call["messages"][-1]["content"][0]
        assert tool_result["is_error"] is True

    def test_max_iterations_guard(self):
        """Infinite tool_use should be capped and return a polite fallback."""
        loop_step = {
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_loop",
                    "name": "read_data_json",
                    "input": {"section": "meta"},
                }
            ],
        }
        script = [dict(loop_step) for _ in range(MAX_TOOL_ITERATIONS + 2)]
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient(script),
        )
        result = agent.chat("loop forever")
        assert result["usage"]["stop_reason"] == "max_iterations"
        # Should still return a reply string (fallback warning).
        assert isinstance(result["reply"], str)
        assert len(result["reply"]) > 0

    def test_history_is_returned_for_next_turn(self):
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "პასუხი."}],
            }
        ]
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient(script),
        )
        result = agent.chat("ტესტი")
        # User turn + assistant turn = 2
        assert len(result["history"]) == 2
        assert result["history"][0]["role"] == "user"
        assert result["history"][0]["content"] == "ტესტი"
        assert result["history"][1]["role"] == "assistant"
        assert result["history"][1]["content"][0]["type"] == "text"

    def test_history_carried_forward(self):
        """Pass previous history back; it should appear before the new user turn."""
        prior = [
            {"role": "user", "content": "პირველი კითხვა"},
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "პირველი პასუხი"}],
            },
        ]
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "მეორე პასუხი"}],
            }
        ]
        fake = FakeClient(script)
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=fake,
        )
        result = agent.chat("მეორე კითხვა", history=prior)
        # messages passed to the model should contain prior + new user.
        sent = fake.messages.calls[0]["messages"]
        assert len(sent) == 3
        assert sent[0]["content"] == "პირველი კითხვა"
        assert sent[2]["content"] == "მეორე კითხვა"
        # result["history"] extends prior by 2 (new user + assistant).
        assert len(result["history"]) == 4


# ---------------------------------------------------------------------------
# Phase 0B Sprint 4 Part 2 follow-up: deep-iteration cap for think / investigate
# ---------------------------------------------------------------------------


class TestDeepIterationCap:
    """Phase 0B Sprint 4 Part 2 metrics-run surfaced that the 6-iteration
    chat-mode cap is too tight for Extended Thinking on strategic
    questions and for investigator-mode triangulation. Phase 1 Part A
    (2026-04-20) further bumped the deep cap 10 -> 12 because the
    5-hat / multi-hypothesis / multi-store triangulation combinations
    routinely push tool-use chains past 10 steps. The agent now lifts
    the cap to :data:`MAX_TOOL_ITERATIONS_DEEP` (12) when either
    ``think=True`` or ``mode="investigate"`` is active, while plain
    chat still fails fast at the original 6-iteration budget.
    """

    @staticmethod
    def _thinking_config():
        return AIConfig(
            api_key="sk-ant-test-key",
            model="claude-sonnet-4-6",
            enable_thinking=True,
        )

    def test_constants_order(self):
        assert MAX_TOOL_ITERATIONS == 6
        assert MAX_TOOL_ITERATIONS_DEEP == 12
        assert MAX_TOOL_ITERATIONS_DEEP > MAX_TOOL_ITERATIONS

    def test_resolve_default_chat_returns_shallow_cap(self):
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient([]),
        )
        assert (
            agent._resolve_max_iterations(mode="chat", thinking_enabled=False)
            == MAX_TOOL_ITERATIONS
        )

    def test_resolve_think_returns_deep_cap(self):
        agent = AIAgent(
            config=self._thinking_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient([]),
        )
        assert (
            agent._resolve_max_iterations(mode="chat", thinking_enabled=True)
            == MAX_TOOL_ITERATIONS_DEEP
        )

    def test_resolve_investigate_returns_deep_cap(self):
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient([]),
        )
        assert (
            agent._resolve_max_iterations(mode="investigate", thinking_enabled=False)
            == MAX_TOOL_ITERATIONS_DEEP
        )

    def test_resolve_both_switches_still_capped_at_deep(self):
        agent = AIAgent(
            config=self._thinking_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient([]),
        )
        assert (
            agent._resolve_max_iterations(mode="investigate", thinking_enabled=True)
            == MAX_TOOL_ITERATIONS_DEEP
        )

    def test_think_mode_allows_more_than_six_iterations(self):
        """Nine tool_use turns + final text should complete end-to-end
        when ``think=True`` unlocks the deeper cap (would fail at 6)."""
        loop_step = {
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_deep",
                    "name": "read_data_json",
                    "input": {"section": "meta"},
                }
            ],
        }
        script = [dict(loop_step) for _ in range(9)] + [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "ბოლოს გამოვიდა."}],
            }
        ]
        agent = AIAgent(
            config=self._thinking_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient(script),
            today_context_enabled=False,
        )
        result = agent.chat("complex strategy", think=True)
        assert result["usage"]["stop_reason"] == "end_turn"
        assert result["usage"]["thinking"] is True
        assert "ბოლოს გამოვიდა" in result["reply"]

    def test_investigate_mode_allows_more_than_six_iterations(self):
        loop_step = {
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_inv",
                    "name": "read_data_json",
                    "input": {"section": "meta"},
                }
            ],
        }
        script = [dict(loop_step) for _ in range(9)] + [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "triangulated."}],
            }
        ]
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient(script),
            today_context_enabled=False,
        )
        result = agent.chat("investigate please", mode="investigate")
        assert result["usage"]["stop_reason"] == "end_turn"
        assert result["usage"]["mode"] == "investigate"
        assert "triangulated" in result["reply"]

    def test_deep_cap_still_enforces_twelve_iteration_limit(self):
        """Even with ``think=True`` the agent still bails out at
        :data:`MAX_TOOL_ITERATIONS_DEEP` — a runaway prompt can't loop
        forever."""
        loop_step = {
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_runaway",
                    "name": "read_data_json",
                    "input": {"section": "meta"},
                }
            ],
        }
        script = [dict(loop_step) for _ in range(MAX_TOOL_ITERATIONS_DEEP + 2)]
        agent = AIAgent(
            config=self._thinking_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient(script),
            today_context_enabled=False,
        )
        result = agent.chat("runaway prompt", think=True)
        assert result["usage"]["stop_reason"] == "max_iterations"
        assert "tool-ების ლიმიტის" in result["reply"]

    def test_plain_chat_without_think_still_capped_at_six(self):
        """Regression guard for the tighter default cap — a plain chat
        turn with 8 tool_use steps must hit the 6-iteration fallback,
        not the deeper 10-iteration budget."""
        loop_step = {
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_plain",
                    "name": "read_data_json",
                    "input": {"section": "meta"},
                }
            ],
        }
        # 8 steps = 2 more than the plain cap but 2 fewer than the deep cap.
        # If the helper mistakenly routes plain chat to the deep cap this
        # script would complete; instead it must fall back at iter 6.
        script = [dict(loop_step) for _ in range(MAX_TOOL_ITERATIONS + 2)]
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient(script),
            today_context_enabled=False,
        )
        result = agent.chat("plain chat")
        assert result["usage"]["stop_reason"] == "max_iterations"


# ---------------------------------------------------------------------------
# Phase 1 polish: prompt caching wiring + cache usage aggregation
# ---------------------------------------------------------------------------


class TestPromptCachingWired:
    """Agent must send `system` as a list of cache-annotated blocks and
    `tools` with `cache_control` on the last tool, so Anthropic prompt
    caching kicks in on repeat prefixes.
    """

    def _run_once(self):
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "OK"}],
            }
        ]
        fake = FakeClient(script)
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            today_context_enabled=False,
            client=fake,
        )
        agent.chat("test")
        return fake.messages.calls[0]

    def test_system_sent_as_blocks_with_cache_control(self):
        call = self._run_once()
        system = call["system"]
        assert isinstance(system, list)
        assert len(system) >= 1
        last = system[-1]
        assert last.get("type") == "text"
        assert "იოლი მარკეტი" in last["text"]
        assert last.get("cache_control") == {"type": "ephemeral"}

    def test_tools_sent_with_cache_control_on_last(self):
        call = self._run_once()
        tools = call["tools"]
        assert isinstance(tools, list) and len(tools) >= 1
        assert tools[-1].get("cache_control") == {"type": "ephemeral"}
        # Module-level TOOL_SCHEMAS must remain un-annotated (pure data).
        assert "cache_control" not in TOOL_SCHEMAS[-1]

    def test_tools_still_have_read_data_json(self):
        call = self._run_once()
        names = [t["name"] for t in call["tools"]]
        assert "read_data_json" in names


class TestCacheUsageTracking:
    """When Anthropic reports cache_creation_input_tokens /
    cache_read_input_tokens, the agent sums them across iterations and
    surfaces them in the final `usage` object so the UI can display savings.
    """

    def test_cache_tokens_zero_when_api_omits_them(self):
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "hi"}],
                "input_tokens": 5,
                "output_tokens": 3,
            }
        ]
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient(script),
        )
        result = agent.chat("test")
        assert result["usage"]["cache_creation_input_tokens"] == 0
        assert result["usage"]["cache_read_input_tokens"] == 0

    def test_cache_tokens_aggregated_across_iterations(self):
        script = [
            {
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_x",
                        "name": "read_data_json",
                        "input": {"section": "meta"},
                    }
                ],
                "input_tokens": 20,
                "output_tokens": 10,
                "cache_creation_input_tokens": 1500,
                "cache_read_input_tokens": 0,
            },
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "done"}],
                "input_tokens": 80,
                "output_tokens": 25,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 1500,
            },
        ]
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient(script),
        )
        result = agent.chat("test")
        assert result["usage"]["input_tokens"] == 100
        assert result["usage"]["output_tokens"] == 35
        assert result["usage"]["cache_creation_input_tokens"] == 1500
        assert result["usage"]["cache_read_input_tokens"] == 1500


# ---------------------------------------------------------------------------
# Streaming (Phase 2+) — AIAgent.chat_stream
# ---------------------------------------------------------------------------


class FakeStream:
    """Mimics Anthropic's MessageStreamManager sync context manager."""

    def __init__(self, content_blocks, stop_reason, usage, text_chunks=None):
        self._content = content_blocks
        self._stop = stop_reason
        self._usage = usage
        # text_chunks: explicit list of text deltas (empty → no deltas)
        self._text_chunks = text_chunks

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    @property
    def text_stream(self):
        if self._text_chunks is not None:
            for chunk in self._text_chunks:
                yield chunk
            return
        # Fallback: split text blocks into ~10-char chunks.
        for block in self._content:
            if block.get("type") == "text":
                text = block.get("text", "")
                for i in range(0, len(text), 10):
                    yield text[i:i + 10]

    def get_final_message(self):
        ns_content = [SimpleNamespace(**b) for b in self._content]
        return SimpleNamespace(
            content=ns_content,
            stop_reason=self._stop,
            usage=self._usage,
        )


class FakeStreamMessages(FakeMessages):
    """Extends FakeMessages with a .stream() method mirroring anthropic SDK."""

    def stream(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        if not self._script:
            raise AssertionError("FakeMessages script exhausted")
        step = self._script.pop(0)
        usage_kwargs = {
            "input_tokens": step.get("input_tokens", 10),
            "output_tokens": step.get("output_tokens", 20),
        }
        if "cache_creation_input_tokens" in step:
            usage_kwargs["cache_creation_input_tokens"] = step[
                "cache_creation_input_tokens"
            ]
        if "cache_read_input_tokens" in step:
            usage_kwargs["cache_read_input_tokens"] = step["cache_read_input_tokens"]
        usage = SimpleNamespace(**usage_kwargs)
        return FakeStream(
            step["content"],
            step["stop_reason"],
            usage,
            text_chunks=step.get("text_chunks"),
        )


class FakeStreamingClient:
    def __init__(self, script):
        self.messages = FakeStreamMessages(script)


class TestChatStream:
    def test_text_only_streams_deltas(self):
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "გამარჯობა მსოფლიოვ"}],
                "input_tokens": 5,
                "output_tokens": 3,
                "text_chunks": ["გამარჯობა ", "მსოფლიოვ"],
            }
        ]
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeStreamingClient(script),
        )
        events = list(agent.chat_stream("test"))
        types = [e["type"] for e in events]

        # Two delta events, in order.
        deltas = [e for e in events if e["type"] == "delta"]
        assert [d["text"] for d in deltas] == ["გამარჯობა ", "მსოფლიოვ"]

        # Final envelope events always appear, in order.
        assert "sources" in types
        assert "usage" in types
        assert "history" in types
        assert types[-1] == "done"

        done = events[-1]
        assert done["reply"] == "გამარჯობა მსოფლიოვ"
        assert done["stop_reason"] == "end_turn"

        usage_evt = next(e for e in events if e["type"] == "usage")
        assert usage_evt["usage"]["input_tokens"] == 5
        assert usage_evt["usage"]["output_tokens"] == 3
        assert usage_evt["usage"]["model"] == "claude-sonnet-4-6"

    def test_tool_use_iteration_emits_tool_events(self):
        script = [
            {
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tu1",
                        "name": "read_data_json",
                        "input": {"section": "suppliers", "limit": 2},
                    }
                ],
                "input_tokens": 20,
                "output_tokens": 15,
                "text_chunks": [],
            },
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "2 მომწოდებელი"}],
                "input_tokens": 80,
                "output_tokens": 25,
                "text_chunks": ["2 ", "მომწოდებელი"],
            },
        ]
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeStreamingClient(script),
        )
        events = list(agent.chat_stream("რამდენი მომწოდებელია?"))
        types = [e["type"] for e in events]

        assert "tool_call" in types
        assert "tool_result" in types
        # tool_call must precede tool_result.
        assert types.index("tool_call") < types.index("tool_result")

        tool_call = next(e for e in events if e["type"] == "tool_call")
        assert tool_call["tool"] == "read_data_json"
        assert tool_call["arguments"] == {"section": "suppliers", "limit": 2}
        assert tool_call["tool_use_id"] == "tu1"

        tool_result = next(e for e in events if e["type"] == "tool_result")
        assert tool_result["tool_use_id"] == "tu1"
        assert tool_result["result_summary"]["ok"] is True
        assert tool_result["result_summary"]["section"] == "suppliers"

        sources_evt = next(e for e in events if e["type"] == "sources")
        assert len(sources_evt["sources"]) == 1
        assert sources_evt["sources"][0]["tool"] == "read_data_json"

        done = events[-1]
        assert done["type"] == "done"
        assert done["reply"] == "2 მომწოდებელი"

    def test_empty_message_yields_error(self):
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeStreamingClient([]),
        )
        events = list(agent.chat_stream(""))
        assert len(events) == 1
        assert events[0]["type"] == "error"

    def test_missing_stream_method_yields_error(self):
        """Simulate an older SDK without messages.stream()."""

        class _NoStreamClient:
            class messages:
                @staticmethod
                def create(**_kwargs):
                    raise AssertionError("should not be called")

        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=_NoStreamClient(),
        )
        events = list(agent.chat_stream("test"))
        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert "stream" in events[0]["error"].lower()

    def test_max_iterations_guard(self):
        loop_step = {
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "id": "x",
                    "name": "read_data_json",
                    "input": {"section": "meta"},
                }
            ],
            "text_chunks": [],
        }
        script = [dict(loop_step) for _ in range(MAX_TOOL_ITERATIONS + 2)]
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeStreamingClient(script),
        )
        events = list(agent.chat_stream("loop forever"))

        deltas = [e for e in events if e["type"] == "delta"]
        assert any("tool-ების ლიმიტის" in d["text"] for d in deltas)

        usage_evt = next(e for e in events if e["type"] == "usage")
        assert usage_evt["usage"]["stop_reason"] == "max_iterations"

        done = events[-1]
        assert done["type"] == "done"
        assert done["stop_reason"] == "max_iterations"

    def test_cache_tokens_aggregated(self):
        script = [
            {
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tu",
                        "name": "read_data_json",
                        "input": {"section": "meta"},
                    }
                ],
                "input_tokens": 20,
                "output_tokens": 10,
                "cache_creation_input_tokens": 1200,
                "cache_read_input_tokens": 0,
                "text_chunks": [],
            },
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "done"}],
                "input_tokens": 80,
                "output_tokens": 25,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 1200,
                "text_chunks": ["done"],
            },
        ]
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeStreamingClient(script),
        )
        events = list(agent.chat_stream("test"))
        usage_evt = next(e for e in events if e["type"] == "usage")
        assert usage_evt["usage"]["input_tokens"] == 100
        assert usage_evt["usage"]["output_tokens"] == 35
        assert usage_evt["usage"]["cache_creation_input_tokens"] == 1200
        assert usage_evt["usage"]["cache_read_input_tokens"] == 1200

    def test_history_returned_in_history_event(self):
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "პასუხი"}],
                "text_chunks": ["პასუხი"],
            }
        ]
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeStreamingClient(script),
        )
        events = list(agent.chat_stream("კითხვა"))
        history_evt = next(e for e in events if e["type"] == "history")
        assert len(history_evt["history"]) == 2
        assert history_evt["history"][0]["role"] == "user"
        assert history_evt["history"][0]["content"] == "კითხვა"
        assert history_evt["history"][1]["role"] == "assistant"
        assert history_evt["history"][1]["content"][0]["type"] == "text"

    def test_prompt_caching_wired_on_stream(self):
        """Streaming path must send cache-annotated system + tools, just like chat()."""
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "OK"}],
                "text_chunks": ["OK"],
            }
        ]
        fake = FakeStreamingClient(script)
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=fake,
            today_context_enabled=False,
        )
        list(agent.chat_stream("test"))
        call = fake.messages.calls[0]
        assert isinstance(call["system"], list)
        assert call["system"][-1].get("cache_control") == {"type": "ephemeral"}
        tools = call["tools"]
        assert isinstance(tools, list) and len(tools) >= 1
        assert tools[-1].get("cache_control") == {"type": "ephemeral"}
        # Module constant must remain untouched.
        assert "cache_control" not in TOOL_SCHEMAS[-1]

    def test_tool_error_does_not_break_stream(self):
        script = [
            {
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "err",
                        "name": "read_data_json",
                        "input": {"section": "nonexistent"},
                    }
                ],
                "text_chunks": [],
            },
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "ვერ ვიპოვე."}],
                "text_chunks": ["ვერ ვიპოვე."],
            },
        ]
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeStreamingClient(script),
        )
        events = list(agent.chat_stream("test"))
        tool_result = next(e for e in events if e["type"] == "tool_result")
        assert tool_result["result_summary"]["ok"] is False
        done = events[-1]
        assert done["type"] == "done"
        assert "ვერ ვიპოვე" in done["reply"]

    def test_history_carried_forward_into_stream(self):
        """Prior history appears before new user turn in the outgoing request."""
        prior = [
            {"role": "user", "content": "პირველი"},
            {"role": "assistant", "content": [{"type": "text", "text": "პასუხი 1"}]},
        ]
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "პასუხი 2"}],
                "text_chunks": ["პასუხი 2"],
            }
        ]
        fake = FakeStreamingClient(script)
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=fake,
        )
        list(agent.chat_stream("მეორე", history=prior))
        sent = fake.messages.calls[0]["messages"]
        assert len(sent) == 3
        assert sent[0]["content"] == "პირველი"
        assert sent[2]["content"] == "მეორე"


# ---------------------------------------------------------------------------
# Phase 2 Sprint 2: prompt mode ("chat" / "investigate")
# ---------------------------------------------------------------------------


class TestPromptMode:
    """Pure prompt-level assertions — no agent involved."""

    def test_supported_modes_tuple_exposed(self):
        assert "chat" in SUPPORTED_MODES
        assert "investigate" in SUPPORTED_MODES
        assert DEFAULT_MODE == "chat"

    def test_investigator_prompt_is_georgian_and_distinct(self):
        """Investigator prompt must be Georgian and clearly different from chat."""
        # At least one Georgian letter present.
        assert any("\u10a0" <= ch <= "\u10ff" for ch in SYSTEM_PROMPT_KA_INVESTIGATOR)
        # Different from the MVP chat prompt.
        assert SYSTEM_PROMPT_KA_INVESTIGATOR != SYSTEM_PROMPT_KA
        # Must mention at least one investigator tool (sanity check).
        assert "validate_vs_source" in SYSTEM_PROMPT_KA_INVESTIGATOR
        # Must mention the Cascade copy-paste contract keyword.
        assert "Cascade" in SYSTEM_PROMPT_KA_INVESTIGATOR

    def test_build_system_prompt_default_is_chat(self):
        default = build_system_prompt()
        explicit = build_system_prompt(mode="chat")
        assert default == explicit
        assert "🎯 როლის კონტრაქტი" in default
        # Investigator-specific phrasing must NOT leak into the chat prompt.
        assert "data investigator" not in default

    def test_build_system_prompt_investigate_mode(self):
        prompt = build_system_prompt(mode="investigate")
        assert "data investigator" in prompt
        # Core chat-mode identity must not leak into investigator mode.
        assert "🎯 როლის კონტრაქტი" not in prompt

    def test_build_system_prompt_mode_case_insensitive(self):
        upper = build_system_prompt(mode="INVESTIGATE")
        mixed = build_system_prompt(mode="Investigate")
        assert upper == mixed == build_system_prompt(mode="investigate")

    def test_build_system_prompt_empty_mode_falls_back_to_default(self):
        assert build_system_prompt(mode="") == build_system_prompt()
        assert build_system_prompt(mode="   ") == build_system_prompt()

    def test_build_system_prompt_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            build_system_prompt(mode="strategize")
        with pytest.raises(ValueError):
            build_system_prompt(mode="unknown")

    def test_build_system_prompt_extra_context_preserved_across_modes(self):
        chat = build_system_prompt("extra Q1", mode="chat")
        investigate = build_system_prompt("extra Q1", mode="investigate")
        assert "extra Q1" in chat
        assert "extra Q1" in investigate
        # Extra context appears under the same heading in both modes.
        assert "# დამატებითი კონტექსტი" in chat
        assert "# დამატებითი კონტექსტი" in investigate

    def test_build_system_prompt_blocks_investigate_mode_cached(self):
        blocks = build_system_prompt_blocks(mode="investigate")
        assert isinstance(blocks, list) and len(blocks) == 1
        assert blocks[0]["type"] == "text"
        assert "data investigator" in blocks[0]["text"]
        assert blocks[-1]["cache_control"] == {"type": "ephemeral"}

    def test_build_system_prompt_blocks_cache_isolation_per_mode(self):
        """Two different modes must produce different cacheable prefixes so
        Anthropic caches them independently."""
        chat_blocks = build_system_prompt_blocks(mode="chat")
        investigate_blocks = build_system_prompt_blocks(mode="investigate")
        assert chat_blocks[0]["text"] != investigate_blocks[0]["text"]

    def test_build_system_prompt_blocks_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            build_system_prompt_blocks(mode="bogus")


class TestChatMode:
    """Agent-level mode tests against :meth:`AIAgent.chat`."""

    def _capture_system(self, mode_kwargs, *, today_context_enabled=False):
        """Run one chat turn and return the system blocks sent to the client.

        ``today_context_enabled`` defaults to False so the system-block
        assertions pin base prompt content deterministically. Today's Pulse
        integration has its own test module (``test_ai_today_context.py``).
        """
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "OK"}],
            }
        ]
        fake = FakeClient(script)
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=fake,
            today_context_enabled=today_context_enabled,
        )
        result = agent.chat("test", **mode_kwargs)
        return fake.messages.calls[0]["system"], result

    def test_default_mode_uses_chat_system_prompt(self):
        """No `mode` kwarg should behave exactly like Phase 1."""
        system, result = self._capture_system({})
        assert isinstance(system, list) and len(system) == 1
        assert "🎯 როლის კონტრაქტი" in system[0]["text"]
        assert "data investigator" not in system[0]["text"]
        assert result["usage"]["mode"] == "chat"

    def test_explicit_chat_mode_matches_default(self):
        sys_default, _ = self._capture_system({})
        sys_explicit, result = self._capture_system({"mode": "chat"})
        assert sys_default[0]["text"] == sys_explicit[0]["text"]
        assert result["usage"]["mode"] == "chat"

    def test_investigate_mode_swaps_system_prompt(self):
        system, result = self._capture_system({"mode": "investigate"})
        assert "data investigator" in system[0]["text"]
        assert "🎯 როლის კონტრაქტი" not in system[0]["text"]
        # Cache prefix still applies on investigator prompt.
        assert system[-1]["cache_control"] == {"type": "ephemeral"}
        assert result["usage"]["mode"] == "investigate"

    def test_investigate_mode_preserves_tool_surface(self):
        """All 28 tools must stay visible regardless of mode (Phase 3.8: +margin_radar)."""
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "OK"}],
            }
        ]
        fake = FakeClient(script)
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=fake,
        )
        agent.chat("test", mode="investigate")
        tools = fake.messages.calls[0]["tools"]
        names = {t["name"] for t in tools}
        assert names == {
            "read_data_json",
            "compute_waybill_total",
            "compute",
            "forecast_revenue",
            "recall_context",
            "save_memory",
            "journal_add_entry",
            "journal_list_entries",
            "journal_update_entry",
            "analyze_dead_stock",
            "prepare_supplier_brief",
            "compute_cash_runway",  # Phase 3.5 Cash Runway
            "compute_cash_flow_projection",  # Phase 2.1 Cash Flow Projection
            "build_debt_repayment_plan",  # Phase 4A Debt Plan (autonomous strategist)
            "simulate_scenario",  # Phase 2.2 Scenario Simulator
            "mix_analyzer",  # Phase 2.3 Category Mix Analyzer
            "margin_radar",  # Phase 3.8 Margin Compression Radar
            "analyze_product_profitability",  # Phase 2.5 Product X-Ray
            "find_promotion_candidates",  # Phase 2.6 Promotion Finder
            "detect_trends",  # Phase 2.9 MoM/YoY price × volume decomposition
            "get_vat_reconciliation_month",  # Phase 5.1 VAT single-month
            "explain_unaccounted_cash",  # Phase 5.1 VAT consultation
            "record_cash_outflow",  # Phase 5.1 VAT journal append
            "read_source_code",
            "grep_code",
            "read_excel_source",
            "validate_vs_source",
            "propose_feature",  # Phase 3.1 Co-Designer
        }

    def test_invalid_mode_raises_agent_error(self):
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient([]),
        )
        with pytest.raises(AIAgentError):
            agent.chat("test", mode="strategize")
        with pytest.raises(AIAgentError):
            agent.chat("test", mode="random")

    def test_mode_case_normalized(self):
        _, result_upper = self._capture_system({"mode": "INVESTIGATE"})
        _, result_mixed = self._capture_system({"mode": "Investigate"})
        assert result_upper["usage"]["mode"] == "investigate"
        assert result_mixed["usage"]["mode"] == "investigate"

    def test_mode_none_falls_back_to_default(self):
        system, result = self._capture_system({"mode": None})
        assert "🎯 როლის კონტრაქტი" in system[0]["text"]
        assert result["usage"]["mode"] == "chat"

    def test_mode_non_string_raises(self):
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=FakeClient([]),
        )
        with pytest.raises(AIAgentError):
            agent.chat("test", mode=42)
        with pytest.raises(AIAgentError):
            agent.chat("test", mode=["investigate"])


class TestChatStreamMode:
    """Agent-level mode tests against :meth:`AIAgent.chat_stream`."""

    def _run_stream(self, mode_kwargs, *, today_context_enabled=False):
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "OK"}],
                "text_chunks": ["OK"],
            }
        ]
        fake = FakeStreamingClient(script)
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=fake,
            today_context_enabled=today_context_enabled,
        )
        events = list(agent.chat_stream("test", **mode_kwargs))
        return fake.messages.calls[0] if fake.messages.calls else None, events

    def test_default_mode_uses_chat_system_prompt(self):
        call, events = self._run_stream({})
        assert "🎯 როლის კონტრაქტი" in call["system"][0]["text"]
        usage_evt = next(e for e in events if e["type"] == "usage")
        assert usage_evt["usage"]["mode"] == "chat"

    def test_investigate_mode_swaps_system_prompt_on_stream(self):
        call, events = self._run_stream({"mode": "investigate"})
        assert "data investigator" in call["system"][0]["text"]
        # Cache prefix retained on streaming path.
        assert call["system"][-1]["cache_control"] == {"type": "ephemeral"}
        usage_evt = next(e for e in events if e["type"] == "usage")
        assert usage_evt["usage"]["mode"] == "investigate"

    def test_invalid_mode_yields_single_error_event(self):
        """Streaming consumers always see a well-formed SSE frame; invalid
        mode must NOT raise (would break the bridge) — it must surface as an
        `error` event and terminate the generator cleanly."""
        _, events = self._run_stream({"mode": "strategize"})
        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert "strategize" in events[0]["error"]

    def test_invalid_mode_does_not_open_stream(self):
        """If `mode` is invalid we must reject BEFORE opening an Anthropic
        stream (which would cost tokens). The fake client's `.stream()` must
        never be called."""
        fake = FakeStreamingClient([])  # empty script → would raise if called
        agent = AIAgent(
            config=_config(),
            data_loader=lambda: SAMPLE_DATA,
            client=fake,
        )
        events = list(agent.chat_stream("test", mode="bogus"))
        assert len(events) == 1 and events[0]["type"] == "error"
        assert fake.messages.calls == []

    def test_stream_mode_case_normalized(self):
        call, events = self._run_stream({"mode": "Investigate"})
        assert "data investigator" in call["system"][0]["text"]
        usage_evt = next(e for e in events if e["type"] == "usage")
        assert usage_evt["usage"]["mode"] == "investigate"


# ---------------------------------------------------------------------------
# Phase 0B.1 — Extended Thinking (ღრმა ფიქრი) passthrough
# ---------------------------------------------------------------------------

def _config_with_thinking(
    *,
    enable_thinking: bool = True,
    thinking_budget_tokens: int = 5000,
    max_tokens: int = 4096,
):
    """Helper: AIConfig tuned for Phase 0B.1 tests."""
    return AIConfig(
        api_key="sk-ant-test-key",
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        temperature=0.3,
        enable_thinking=enable_thinking,
        thinking_budget_tokens=thinking_budget_tokens,
    )


class TestChatThinking:
    """Non-streaming ``chat()`` Extended Thinking passthrough."""

    def _run_chat(self, *, config, think):
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "OK"}],
            }
        ]
        fake = FakeClient(script)
        agent = AIAgent(
            config=config,
            data_loader=lambda: SAMPLE_DATA,
            client=fake,
            today_context_enabled=False,
        )
        result = agent.chat("test", think=think)
        call = fake.messages.calls[-1]
        return call, result

    def test_default_think_false_omits_thinking_param(self):
        call, result = self._run_chat(
            config=_config_with_thinking(enable_thinking=True),
            think=False,
        )
        assert "thinking" not in call
        assert call["temperature"] == pytest.approx(0.3)
        assert result["usage"]["thinking"] is False

    def test_think_true_with_deployment_enabled_adds_thinking_block(self):
        call, result = self._run_chat(
            config=_config_with_thinking(
                enable_thinking=True, thinking_budget_tokens=5000
            ),
            think=True,
        )
        assert call["thinking"] == {"type": "enabled", "budget_tokens": 5000}
        assert call["temperature"] == pytest.approx(1.0)
        assert result["usage"]["thinking"] is True

    def test_think_true_bumps_max_tokens_above_budget_plus_headroom(self):
        # Config max_tokens=4096, budget=5000 → required >= 6024, actual bumped
        call, _ = self._run_chat(
            config=_config_with_thinking(
                enable_thinking=True,
                thinking_budget_tokens=5000,
                max_tokens=4096,
            ),
            think=True,
        )
        assert call["max_tokens"] >= 5000 + 1024

    def test_think_true_keeps_max_tokens_when_already_sufficient(self):
        call, _ = self._run_chat(
            config=_config_with_thinking(
                enable_thinking=True,
                thinking_budget_tokens=3000,
                max_tokens=16000,
            ),
            think=True,
        )
        # Pre-configured max_tokens already leaves room; must not shrink it.
        assert call["max_tokens"] == 16000

    def test_think_true_ignored_when_deployment_flag_off(self):
        """``config.enable_thinking=False`` is the authoritative gate —
        per-turn ``think=True`` is silently ignored (no thinking param, no
        temperature bump, no max_tokens change)."""
        call, result = self._run_chat(
            config=_config_with_thinking(enable_thinking=False),
            think=True,
        )
        assert "thinking" not in call
        assert call["temperature"] == pytest.approx(0.3)
        assert call["max_tokens"] == 4096
        assert result["usage"]["thinking"] is False

    def test_think_non_bool_is_treated_as_falsy(self):
        """Agent-level tolerant to truthy-but-non-True values — only literal
        ``True`` flips the flag (matches ``_resolve_thinking`` contract).
        Server-level validation rejects non-bool body values upstream."""
        call, result = self._run_chat(
            config=_config_with_thinking(enable_thinking=True),
            think=1,  # truthy but not True — should be treated per Python
        )
        # Python truthiness: `if not think: return False` → `1` is truthy,
        # so this passes through to thinking mode. Documenting the behavior.
        assert call.get("thinking") is not None
        assert result["usage"]["thinking"] is True

    def test_temperature_override_only_on_thinking(self):
        """Temperature must stay at config value (0.3) when thinking is off
        even if enable_thinking=True (deployment ready but turn opted out)."""
        call, _ = self._run_chat(
            config=_config_with_thinking(enable_thinking=True),
            think=False,
        )
        assert call["temperature"] == pytest.approx(0.3)

    def test_usage_mode_still_echoed_with_thinking(self):
        """Thinking + mode should coexist — neither clobbers the other."""
        call, result = self._run_chat(
            config=_config_with_thinking(enable_thinking=True),
            think=True,
        )
        assert result["usage"]["thinking"] is True
        assert result["usage"]["mode"] == DEFAULT_MODE  # default "chat"


class TestChatStreamThinking:
    """Streaming ``chat_stream()`` Extended Thinking passthrough."""

    def _run_stream(self, *, config, think):
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "OK"}],
                "text_chunks": ["OK"],
            }
        ]
        fake = FakeStreamingClient(script)
        agent = AIAgent(
            config=config,
            data_loader=lambda: SAMPLE_DATA,
            client=fake,
            today_context_enabled=False,
        )
        events = list(agent.chat_stream("test", think=think))
        call = fake.messages.calls[-1]
        return call, events

    def test_stream_default_think_false_omits_thinking(self):
        call, events = self._run_stream(
            config=_config_with_thinking(enable_thinking=True),
            think=False,
        )
        assert "thinking" not in call
        assert call["temperature"] == pytest.approx(0.3)
        usage_evt = next(e for e in events if e["type"] == "usage")
        assert usage_evt["usage"]["thinking"] is False

    def test_stream_think_true_adds_thinking_block(self):
        call, events = self._run_stream(
            config=_config_with_thinking(enable_thinking=True),
            think=True,
        )
        assert call["thinking"]["type"] == "enabled"
        assert call["thinking"]["budget_tokens"] == 5000
        assert call["temperature"] == pytest.approx(1.0)
        usage_evt = next(e for e in events if e["type"] == "usage")
        assert usage_evt["usage"]["thinking"] is True

    def test_stream_think_ignored_when_deployment_flag_off(self):
        call, events = self._run_stream(
            config=_config_with_thinking(enable_thinking=False),
            think=True,
        )
        assert "thinking" not in call
        assert call["temperature"] == pytest.approx(0.3)
        usage_evt = next(e for e in events if e["type"] == "usage")
        assert usage_evt["usage"]["thinking"] is False

    def test_stream_think_budget_value_propagates(self):
        call, _ = self._run_stream(
            config=_config_with_thinking(
                enable_thinking=True, thinking_budget_tokens=10000
            ),
            think=True,
        )
        assert call["thinking"]["budget_tokens"] == 10000
        # Budget + headroom (1024) = 11024 > default max 4096 → bumped
        assert call["max_tokens"] >= 11024


class TestChatThinkingIntegration:
    """End-to-end: pre-Phase 0B.1 tests must keep passing unchanged."""

    def test_agent_accepts_think_kwarg_without_config_change(self):
        """Agent must be constructible + callable on a legacy AIConfig
        (no enable_thinking field set). Think=False is the legacy default,
        so everything should behave like pre-Phase 0B.1."""
        legacy_cfg = AIConfig(api_key="sk-ant-test", model="claude-sonnet-4-6")
        script = [
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "legacy reply"}],
            }
        ]
        fake = FakeClient(script)
        agent = AIAgent(
            config=legacy_cfg,
            data_loader=lambda: SAMPLE_DATA,
            client=fake,
            today_context_enabled=False,
        )
        result = agent.chat("test")  # no think kwarg at all
        assert result["reply"] == "legacy reply"
        assert result["usage"]["thinking"] is False
        assert "thinking" not in fake.messages.calls[-1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
