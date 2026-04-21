"""AI chat agent — Phase 1 MVP.

Wraps Anthropic's `messages.create` with a minimal tool-use loop:
  1. Build system prompt + user message.
  2. Send to Claude with TOOL_SCHEMAS.
  3. While response.stop_reason == "tool_use":
       - dispatch every tool_use block through ToolDispatcher
       - append assistant + tool_result blocks to history
       - call messages.create again
  4. Return final assistant text + tool call trace as `sources`.

The Anthropic SDK is imported lazily so the module stays importable
in test environments that don't have the SDK installed.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Iterator, List, Optional

from dashboard_pipeline.ai.config import AIConfig
from dashboard_pipeline.ai.prompts import (
    DEFAULT_MODE,
    SUPPORTED_MODES,
    build_system_prompt_blocks,
)
from dashboard_pipeline.ai.today_context import build_today_block
from dashboard_pipeline.ai.tools import ToolDispatcher, get_cached_tool_schemas


logger = logging.getLogger(__name__)


MAX_TOOL_ITERATIONS = 6
# Phase 0B Sprint 4 Part 2 follow-up (2026-04-19); bumped 10 -> 12 in
# Phase 1 Part A (2026-04-20).
# Complex strategic questions (``think=True``) and investigator
# discrepancy hunts (``mode="investigate"``) naturally chain more tool
# calls than a simple chat lookup — Alpha-supplier strategy + Extended
# Thinking burned through the 6-iteration cap in live dog-food, and the
# 5-hat / multi-store / multi-hypothesis combinations introduced in
# Phase 1 Part A push routine triangulation past 10 steps too. The
# deeper cap is used whenever either switch is on; plain chat turns
# keep the tighter 6-iteration budget so a misbehaving prompt still
# fails fast.
MAX_TOOL_ITERATIONS_DEEP = 12
# Per-message timeout for Anthropic SDK. Phase 1 Part A introduced a
# heavier system prompt (role-contract + project-map + 5 hats + confidence
# marks); combined with Extended Thinking a single strategic message can
# exceed the prior 60 s budget, triggering SDK auto-retry loops. 120 s
# gives Anthropic comfortable headroom for thinking + output generation.
DEFAULT_TIMEOUT_S = 120.0

# Phase 0B.1 — Extended Thinking constants.
# When thinking is enabled Anthropic requires ``temperature = 1.0`` and
# ``max_tokens >= thinking_budget_tokens + headroom`` so the model has room
# for the user-visible answer on top of internal reasoning tokens.
_THINKING_TEMPERATURE = 1.0
_THINKING_OUTPUT_HEADROOM = 1024


class AIAgentError(RuntimeError):
    """Wraps any failure from the agent loop (missing config, API error, etc.)."""


# Interface for the underlying LLM client. We keep it minimal so tests can
# inject a fake client without pulling in the real anthropic SDK.
LLMClient = Callable[..., Any]


def _build_anthropic_client(api_key: str) -> Any:
    try:
        import anthropic  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise AIAgentError(
            "anthropic package is not installed. Install from requirements.txt."
        ) from exc
    return anthropic.Anthropic(api_key=api_key, timeout=DEFAULT_TIMEOUT_S)


def _extract_text_blocks(content: Any) -> str:
    """Concatenate text blocks from an Anthropic response content list."""
    parts: List[str] = []
    for block in content or []:
        btype = getattr(block, "type", None)
        if btype is None and isinstance(block, dict):
            btype = block.get("type")
        if btype == "text":
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text")
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def _blocks_to_raw(content: Any) -> List[Dict[str, Any]]:
    """Convert SDK content blocks into JSON-serializable dicts for re-sending."""
    raw: List[Dict[str, Any]] = []
    for block in content or []:
        if isinstance(block, dict):
            raw.append(block)
            continue
        btype = getattr(block, "type", None)
        if btype == "text":
            raw.append({"type": "text", "text": getattr(block, "text", "")})
        elif btype == "tool_use":
            raw.append({
                "type": "tool_use",
                "id": getattr(block, "id", ""),
                "name": getattr(block, "name", ""),
                "input": getattr(block, "input", {}) or {},
            })
        # other block types are ignored for now (thinking, etc.)
    return raw


class AIAgent:
    """Minimal chat agent with tool-use loop.

    Parameters
    ----------
    config : AIConfig
        Loaded configuration (API key, model, limits).
    data_loader : Callable[[], dict]
        Called (lazily) to load the data.json snapshot used by tools.
    client : optional
        Injected LLM client (for tests). If None, the real Anthropic SDK
        client is constructed from `config.api_key`.
    """

    def __init__(
        self,
        config: AIConfig,
        data_loader: Callable[[], Dict[str, Any]],
        client: Optional[Any] = None,
        *,
        today_context_enabled: bool = True,
    ):
        if not config.is_enabled:
            raise AIAgentError(
                "AI is not configured: ANTHROPIC_API_KEY missing or malformed."
            )
        self._config = config
        self._data_loader = data_loader
        self._client = client or _build_anthropic_client(config.api_key)
        # Phase 0A.3 — Today's Pulse.
        # The today block is a small Georgian snapshot (date + yesterday POS
        # + 7-day AP exposure + top risks) prepended to every chat turn's
        # system prompt as a NON-cached second content block. Disable via
        # ``today_context_enabled=False`` for unit tests that pin prompt text.
        self._today_context_enabled = bool(today_context_enabled)

    # ---- helpers ---------------------------------------------------------

    def _maybe_today_block(self) -> Optional[str]:
        """Return the formatted today block, or ``None`` if disabled / empty.

        Wrapped in a broad ``try``: if the block builder fails for any reason
        we log and return ``None`` so the chat turn proceeds normally (the
        base prompt is self-sufficient). Today's Pulse is an assist, not a
        hard requirement.
        """
        if not self._today_context_enabled:
            return None
        try:
            block = build_today_block(self._data_loader)
        except Exception:
            logger.exception("today_context build failed; proceeding without it")
            return None
        if not isinstance(block, str) or not block.strip():
            return None
        return block

    def _resolve_max_iterations(
        self, *, mode: str, thinking_enabled: bool
    ) -> int:
        """Return the tool-use iteration cap for this turn.

        Plain chat turns get :data:`MAX_TOOL_ITERATIONS` (6). Extended
        Thinking (``think=True``) and investigator mode both unlock
        :data:`MAX_TOOL_ITERATIONS_DEEP` (12) because those paths
        legitimately chain more tool calls (triangulation, multi-
        hypothesis, 5-hat perspectives, Excel cross-checks).

        The two switches don't compound — 12 is the ceiling even when
        both are active, so a runaway prompt still can't loop forever.
        """
        if thinking_enabled or mode == "investigate":
            return MAX_TOOL_ITERATIONS_DEEP
        return MAX_TOOL_ITERATIONS

    def _resolve_thinking(self, think: bool) -> bool:
        """Return the effective thinking flag for this turn.

        The deployment flag (``config.enable_thinking``) takes precedence: if
        a deployment has not opted in, per-turn ``think=True`` requests are
        silently ignored (logged at DEBUG). This keeps the body-field
        contract stable on clients even when the backend is configured to
        never spend tokens on reasoning.
        """
        if not think:
            return False
        if not self._config.enable_thinking:
            logger.debug(
                "think=True requested but AIConfig.enable_thinking is False; "
                "ignoring per-turn request (set AI_ENABLE_THINKING=true to opt in)."
            )
            return False
        return True

    def _build_llm_call_kwargs(
        self,
        *,
        system_blocks: List[Dict[str, Any]],
        cached_tools: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        thinking_enabled: bool,
    ) -> Dict[str, Any]:
        """Build the kwargs dict for ``messages.create`` / ``messages.stream``.

        Factored out so both :meth:`chat` and :meth:`chat_stream` share the
        exact same request shape, including Extended Thinking mode.
        """
        kwargs: Dict[str, Any] = {
            "model": self._config.model,
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
            "system": system_blocks,
            "tools": cached_tools,
            "messages": messages,
        }
        if thinking_enabled:
            budget = self._config.thinking_budget_tokens
            # Ensure max_tokens leaves headroom for the user-facing answer on
            # top of thinking tokens. Anthropic counts thinking tokens
            # against max_tokens.
            required_max = budget + _THINKING_OUTPUT_HEADROOM
            if kwargs["max_tokens"] < required_max:
                kwargs["max_tokens"] = required_max
            # Anthropic requires temperature=1.0 when thinking is enabled.
            kwargs["temperature"] = _THINKING_TEMPERATURE
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": budget,
            }
        return kwargs

    # ---- public entry point -----------------------------------------------

    def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        *,
        mode: str = DEFAULT_MODE,
        think: bool = False,
    ) -> Dict[str, Any]:
        """Run one chat turn. Returns `{reply, sources, usage, history}`.

        ``history`` is a list of Anthropic-style message dicts
        (``{"role": "user"|"assistant", "content": [...]}``) from previous
        turns.

        ``mode`` selects the system prompt variant (``"chat"`` or
        ``"investigate"``). Tool schemas and the cached-prefix plumbing are
        identical across modes; only the ``system`` text swaps. The Anthropic
        cache works per-prefix, so alternating modes does NOT thrash the
        other mode's cache entry.

        ``think`` (Phase 0B.1) opts this turn in to Extended Thinking. The
        deployment flag (``config.enable_thinking``) must also be ``True`` —
        otherwise per-turn ``think=True`` is silently ignored. When
        effective, Anthropic allocates up to ``config.thinking_budget_tokens``
        to internal reasoning before emitting the user-facing answer; this
        is transparent to the frontend (thinking blocks are stripped). The
        resolved value is echoed in ``usage.thinking`` so clients can
        confirm the turn used Extended Thinking.
        """
        if not isinstance(message, str) or not message.strip():
            raise AIAgentError("message must be a non-empty string")

        resolved_mode = _validate_mode(mode)
        resolved_thinking = self._resolve_thinking(think)
        max_iterations = self._resolve_max_iterations(
            mode=resolved_mode, thinking_enabled=resolved_thinking
        )

        dispatcher = ToolDispatcher(self._data_loader)
        messages: List[Dict[str, Any]] = list(history or [])
        messages.append({"role": "user", "content": message})

        # Build the cacheable prefix once. Both `system` and `tools` carry
        # `cache_control: {"type": "ephemeral"}` on their final block so the
        # Anthropic API re-uses the cached prefix across turns (~10x input
        # token savings on identical prefixes). Today's Pulse (Phase 0A.3) is
        # appended as a non-cached second system block — it varies per
        # session and would otherwise invalidate the prefix.
        system_blocks = build_system_prompt_blocks(
            mode=resolved_mode,
            today_block=self._maybe_today_block(),
        )
        cached_tools = get_cached_tool_schemas()
        usage_totals = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }
        final_text = ""
        stop_reason: Optional[str] = None

        for iteration in range(max_iterations):
            call_kwargs = self._build_llm_call_kwargs(
                system_blocks=system_blocks,
                cached_tools=cached_tools,
                messages=messages,
                thinking_enabled=resolved_thinking,
            )
            response = self._client.messages.create(**call_kwargs)

            # Aggregate token usage across iterations (including cache metrics
            # when the Anthropic API reports them).
            usage = getattr(response, "usage", None)
            if usage is not None:
                usage_totals["input_tokens"] += int(getattr(usage, "input_tokens", 0) or 0)
                usage_totals["output_tokens"] += int(getattr(usage, "output_tokens", 0) or 0)
                usage_totals["cache_creation_input_tokens"] += int(
                    getattr(usage, "cache_creation_input_tokens", 0) or 0
                )
                usage_totals["cache_read_input_tokens"] += int(
                    getattr(usage, "cache_read_input_tokens", 0) or 0
                )

            content = getattr(response, "content", [])
            stop_reason = getattr(response, "stop_reason", None)

            # Always record the assistant turn in our transcript (raw blocks).
            assistant_blocks = _blocks_to_raw(content)
            messages.append({"role": "assistant", "content": assistant_blocks})

            if stop_reason != "tool_use":
                final_text = _extract_text_blocks(content)
                break

            # Execute every tool_use block in this assistant turn.
            tool_results: List[Dict[str, Any]] = []
            for block in assistant_blocks:
                if block.get("type") != "tool_use":
                    continue
                tool_name = block.get("name") or ""
                tool_input = block.get("input") or {}
                try:
                    result = dispatcher.dispatch(tool_name, tool_input)
                    is_error = "error" in result
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.get("id", ""),
                        "content": _stringify_tool_result(result),
                        "is_error": is_error,
                    })
                except Exception as exc:  # defensive: never break the loop
                    logger.exception("Tool dispatch crashed: %s", tool_name)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.get("id", ""),
                        "content": f"Tool '{tool_name}' failed: {exc}",
                        "is_error": True,
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            # Hit the resolved iteration cap without a final text — force a reply.
            logger.warning("Agent hit MAX_TOOL_ITERATIONS=%d", max_iterations)
            final_text = _extract_text_blocks(
                messages[-1].get("content") if messages else []
            ) or (
                "⚠️ პასუხის გენერაცია შეწყდა tool-ების ლიმიტის გამო. "
                "გთხოვ, გადამოთხოვე უფრო ვიწრო კითხვით."
            )
            stop_reason = "max_iterations"

        return {
            "reply": final_text,
            "sources": dispatcher.calls,
            "usage": {
                **usage_totals,
                "model": self._config.model,
                "stop_reason": stop_reason,
                "mode": resolved_mode,
                "thinking": resolved_thinking,
            },
            "history": messages,
        }

    # ---- streaming entry point --------------------------------------------

    def chat_stream(
        self,
        message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        *,
        mode: str = DEFAULT_MODE,
        think: bool = False,
    ) -> Iterator[Dict[str, Any]]:
        """Streaming variant of :meth:`chat`.

        Yields one dict per event in roughly this order:

        - ``{"type": "delta", "text": str}`` — incremental text chunks (many)
        - ``{"type": "tool_call", ...}``     — before each tool dispatch
        - ``{"type": "tool_result", ...}``   — after each tool resolves
        - ``{"type": "sources", "sources": list}``
        - ``{"type": "usage", "usage": dict}``
        - ``{"type": "history", "history": list}``
        - ``{"type": "done", "reply": str, "stop_reason": str}``
        - ``{"type": "error", "error": str}`` (only on fatal failure)

        The ``reply`` field in the final ``done`` event matches the semantic
        of :meth:`chat` — it is the accumulated text of the *final* (non-
        ``tool_use``) iteration, so non-streaming consumers can use it as a
        drop-in replacement.

        ``mode`` mirrors :meth:`chat`: ``"chat"`` (default) or
        ``"investigate"``. An invalid mode is reported via a single ``error``
        event rather than raising, so streaming consumers always see a
        well-formed SSE frame.
        """
        if not isinstance(message, str) or not message.strip():
            yield {"type": "error", "error": "message must be a non-empty string"}
            return

        try:
            resolved_mode = _validate_mode(mode)
        except AIAgentError as exc:
            yield {"type": "error", "error": str(exc)}
            return

        resolved_thinking = self._resolve_thinking(think)
        max_iterations = self._resolve_max_iterations(
            mode=resolved_mode, thinking_enabled=resolved_thinking
        )

        stream_method = getattr(getattr(self._client, "messages", None), "stream", None)
        if stream_method is None:
            yield {
                "type": "error",
                "error": "LLM client does not support streaming (messages.stream missing)",
            }
            return

        dispatcher = ToolDispatcher(self._data_loader)
        messages: List[Dict[str, Any]] = list(history or [])
        messages.append({"role": "user", "content": message})

        # Today's Pulse injected exactly the same way as the non-streaming
        # path — keeps behavior consistent across `chat` vs `chat_stream`.
        system_blocks = build_system_prompt_blocks(
            mode=resolved_mode,
            today_block=self._maybe_today_block(),
        )
        cached_tools = get_cached_tool_schemas()
        usage_totals = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }
        final_text = ""
        stop_reason: Optional[str] = None

        for _iteration in range(max_iterations):
            try:
                call_kwargs = self._build_llm_call_kwargs(
                    system_blocks=system_blocks,
                    cached_tools=cached_tools,
                    messages=messages,
                    thinking_enabled=resolved_thinking,
                )
                stream_ctx = stream_method(**call_kwargs)
            except Exception as exc:
                logger.exception("Failed to open Anthropic stream")
                yield {
                    "type": "error",
                    "error": f"stream open failed: {type(exc).__name__}: {exc}",
                }
                return

            try:
                with stream_ctx as stream:
                    text_stream = getattr(stream, "text_stream", None)
                    if text_stream is not None:
                        for text_chunk in text_stream:
                            if text_chunk:
                                yield {"type": "delta", "text": text_chunk}
                    final = stream.get_final_message()
            except Exception as exc:
                logger.exception("Anthropic stream failed")
                yield {
                    "type": "error",
                    "error": f"stream failed: {type(exc).__name__}: {exc}",
                }
                return

            usage = getattr(final, "usage", None)
            if usage is not None:
                usage_totals["input_tokens"] += int(getattr(usage, "input_tokens", 0) or 0)
                usage_totals["output_tokens"] += int(getattr(usage, "output_tokens", 0) or 0)
                usage_totals["cache_creation_input_tokens"] += int(
                    getattr(usage, "cache_creation_input_tokens", 0) or 0
                )
                usage_totals["cache_read_input_tokens"] += int(
                    getattr(usage, "cache_read_input_tokens", 0) or 0
                )

            content = getattr(final, "content", [])
            stop_reason = getattr(final, "stop_reason", None)
            assistant_blocks = _blocks_to_raw(content)
            messages.append({"role": "assistant", "content": assistant_blocks})

            if stop_reason != "tool_use":
                final_text = _extract_text_blocks(content)
                break

            # Dispatch every tool_use block in this assistant turn.
            tool_results: List[Dict[str, Any]] = []
            for block in assistant_blocks:
                if block.get("type") != "tool_use":
                    continue
                tool_name = block.get("name") or ""
                tool_input = block.get("input") or {}
                tool_use_id = block.get("id", "")
                yield {
                    "type": "tool_call",
                    "tool": tool_name,
                    "arguments": tool_input,
                    "tool_use_id": tool_use_id,
                }
                try:
                    result = dispatcher.dispatch(tool_name, tool_input)
                    is_error = "error" in result
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": _stringify_tool_result(result),
                        "is_error": is_error,
                    })
                    summary = (
                        dispatcher.calls[-1].get("result_summary")
                        if dispatcher.calls
                        else None
                    )
                    yield {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "result_summary": summary,
                    }
                except Exception as exc:
                    logger.exception("Tool dispatch crashed: %s", tool_name)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": f"Tool '{tool_name}' failed: {exc}",
                        "is_error": True,
                    })
                    yield {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "result_summary": {"ok": False, "error": str(exc)},
                    }

            messages.append({"role": "user", "content": tool_results})
        else:
            logger.warning(
                "Streaming agent hit MAX_TOOL_ITERATIONS=%d", max_iterations
            )
            fallback = (
                "⚠️ პასუხის გენერაცია შეწყდა tool-ების ლიმიტის გამო. "
                "გთხოვ, გადამოთხოვე უფრო ვიწრო კითხვით."
            )
            final_text = fallback
            stop_reason = "max_iterations"
            yield {"type": "delta", "text": fallback}

        yield {"type": "sources", "sources": dispatcher.calls}
        yield {
            "type": "usage",
            "usage": {
                **usage_totals,
                "model": self._config.model,
                "stop_reason": stop_reason,
                "mode": resolved_mode,
                "thinking": resolved_thinking,
            },
        }
        yield {"type": "history", "history": messages}
        yield {"type": "done", "reply": final_text, "stop_reason": stop_reason}


def _stringify_tool_result(result: Dict[str, Any]) -> str:
    """Anthropic tool_result.content accepts a plain string. Encode as JSON."""
    import json as _json

    try:
        return _json.dumps(result, ensure_ascii=False, default=str)
    except Exception:
        return str(result)


def _validate_mode(mode: Any) -> str:
    """Normalize + validate a prompt mode, raising :class:`AIAgentError`.

    Delegates the canonical rule to :data:`dashboard_pipeline.ai.prompts.
    SUPPORTED_MODES` so agent + server + prompts stay in sync.
    """
    if mode is None:
        return DEFAULT_MODE
    if not isinstance(mode, str):
        raise AIAgentError(
            f"mode must be a string (one of {list(SUPPORTED_MODES)}); got {type(mode).__name__}"
        )
    normalized = mode.strip().lower()
    if not normalized:
        return DEFAULT_MODE
    if normalized not in SUPPORTED_MODES:
        raise AIAgentError(
            f"unknown mode {mode!r}; supported: {list(SUPPORTED_MODES)}"
        )
    return normalized
