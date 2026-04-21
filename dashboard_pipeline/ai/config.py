"""AI configuration loader.

Reads environment variables (populated from .env) without ever echoing secrets.
`AIConfig.redacted()` is safe to log for debugging.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


_DEFAULT_MODEL = "claude-sonnet-4-6"
_DEFAULT_FALLBACK = "claude-haiku-4-5-20251001"
_DEFAULT_MAX_TOKENS = 4096
_DEFAULT_TEMPERATURE = 0.3

# Phase 0B.1 — Extended Thinking (ღრმა ფიქრი).
# Claude Sonnet 4.6 supports an opt-in ``thinking`` mode where the model
# allocates up to ``budget_tokens`` to internal reasoning before emitting the
# user-facing answer. Extra token cost, much deeper output on strategic
# questions. Off by default (``enable_thinking=False``) so cached prefix +
# temperature=0.3 chat behavior stays unchanged for the common case.
_DEFAULT_THINKING_BUDGET = 5000
# Anthropic requires ``budget_tokens >= 1024`` when thinking is enabled.
_MIN_THINKING_BUDGET = 1024


@dataclass(frozen=True)
class AIConfig:
    """Resolved AI configuration snapshot.

    Never log `api_key` directly; use `redacted()` for diagnostics.
    """

    api_key: str
    model: str = _DEFAULT_MODEL
    model_fallback: str = _DEFAULT_FALLBACK
    max_tokens: int = _DEFAULT_MAX_TOKENS
    temperature: float = _DEFAULT_TEMPERATURE
    #: Whether Extended Thinking is available at all for this deployment.
    #: Acts as a per-deployment feature flag — requests can still opt-in per
    #: turn via the ``think`` body field, but only if this flag is ``True``.
    enable_thinking: bool = False
    #: Token budget allocated to internal thinking when ``think=True``. Must
    #: be >= 1024 (Anthropic requirement). Loader clamps below the minimum.
    thinking_budget_tokens: int = _DEFAULT_THINKING_BUDGET

    @property
    def is_enabled(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("sk-ant-"))

    def redacted(self) -> dict:
        """Diagnostics-safe representation (no secrets)."""
        prefix = self.api_key[:8] if self.api_key else ""
        return {
            "api_key_prefix": f"{prefix}..." if prefix else "(unset)",
            "api_key_length": len(self.api_key) if self.api_key else 0,
            "model": self.model,
            "model_fallback": self.model_fallback,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "enable_thinking": self.enable_thinking,
            "thinking_budget_tokens": self.thinking_budget_tokens,
            "enabled": self.is_enabled,
        }


def _load_dotenv_once(env_path: Optional[Path] = None) -> None:
    """Best-effort `.env` loader. Silent if python-dotenv missing or file absent."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    if env_path is None:
        # Default: project root .env, relative to this file (ai/config.py).
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _parse_int(raw: Optional[str], default: int) -> int:
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_float(raw: Optional[str], default: float) -> float:
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_bool(raw: Optional[str], default: bool) -> bool:
    """Accept common truthy/falsy spellings; fall back to ``default``.

    Accepted true: ``1``, ``true``, ``yes``, ``on`` (case-insensitive).
    Accepted false: ``0``, ``false``, ``no``, ``off`` (case-insensitive).
    Anything else (empty, None, typo) → ``default``.
    """
    if raw is None:
        return default
    normalized = str(raw).strip().lower()
    if not normalized:
        return default
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False
    return default


def _parse_thinking_budget(raw: Optional[str], default: int) -> int:
    """Parse thinking budget + clamp below Anthropic's 1024-token floor."""
    value = _parse_int(raw, default)
    if value < _MIN_THINKING_BUDGET:
        return _MIN_THINKING_BUDGET
    return value


def load_ai_config(env_path: Optional[Path] = None) -> AIConfig:
    """Load AI configuration from environment variables.

    Reads `.env` (if python-dotenv installed) without overriding existing env.
    Returns a frozen `AIConfig` snapshot.

    Phase 0B.1 adds two env vars:

    - ``AI_ENABLE_THINKING`` (bool, default ``false``) — deployment-level
      feature flag. If ``false``, the ``think`` body field on ``/api/chat``
      is ignored (never sent to Anthropic).
    - ``AI_THINKING_BUDGET`` (int, default 5000, min 1024) — tokens allocated
      to internal reasoning when thinking is enabled.
    """
    _load_dotenv_once(env_path)
    return AIConfig(
        api_key=(os.environ.get("ANTHROPIC_API_KEY") or "").strip(),
        model=(os.environ.get("AI_MODEL") or _DEFAULT_MODEL).strip(),
        model_fallback=(os.environ.get("AI_MODEL_FALLBACK") or _DEFAULT_FALLBACK).strip(),
        max_tokens=_parse_int(os.environ.get("AI_MAX_TOKENS"), _DEFAULT_MAX_TOKENS),
        temperature=_parse_float(os.environ.get("AI_TEMPERATURE"), _DEFAULT_TEMPERATURE),
        enable_thinking=_parse_bool(os.environ.get("AI_ENABLE_THINKING"), False),
        thinking_budget_tokens=_parse_thinking_budget(
            os.environ.get("AI_THINKING_BUDGET"), _DEFAULT_THINKING_BUDGET
        ),
    )
