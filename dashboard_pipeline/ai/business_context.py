"""Owner-authored business context loader.

Reads ``Financial_Analysis/MY_BUSINESS.md`` and exposes its content as a
string for inclusion in the AI system prompt. The file holds the owner's
answers to the AI's strategic interview (10Q) — generic textbook KPI
advice may not apply; this context lets the AI tailor recommendations
to the owner's actual reality.

Cache is keyed on the file's mtime so owner edits become visible to the
next AI turn without a backend restart. When the file content is
unchanged across turns the Anthropic prompt cache still hits, since the
final prompt string is byte-identical.

Missing file → returns ``None``. Empty / whitespace-only file → returns
``None``. Both cases are non-fatal: the AI continues without the extra
context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BUSINESS_CONTEXT_PATH = _PROJECT_ROOT / "Financial_Analysis" / "MY_BUSINESS.md"

_cached: Optional[str] = None
_cached_mtime: Optional[float] = None


def get_business_context_path() -> Path:
    return _BUSINESS_CONTEXT_PATH


def load_business_context() -> Optional[str]:
    """Return MY_BUSINESS.md content. Re-reads when the file's mtime changes."""
    global _cached, _cached_mtime
    try:
        mtime = _BUSINESS_CONTEXT_PATH.stat().st_mtime
    except (FileNotFoundError, OSError):
        _cached = None
        _cached_mtime = None
        return None

    if _cached_mtime == mtime:
        return _cached

    try:
        text = _BUSINESS_CONTEXT_PATH.read_text(encoding="utf-8")
    except OSError:
        _cached = None
        _cached_mtime = None
        return None

    text = text.strip()
    _cached = text or None
    _cached_mtime = mtime
    return _cached


def reload_business_context() -> Optional[str]:
    """Force re-read on next call (drops mtime cache)."""
    global _cached, _cached_mtime
    _cached = None
    _cached_mtime = None
    return load_business_context()
