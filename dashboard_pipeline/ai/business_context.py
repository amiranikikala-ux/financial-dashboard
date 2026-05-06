"""Owner-authored business context loader.

Reads ``Financial_Analysis/MY_BUSINESS.md`` and exposes its content as a
string for inclusion in the AI system prompt. The file holds the owner's
answers to the AI's strategic interview (10Q) — generic textbook KPI
advice may not apply; this context lets the AI tailor recommendations
to the owner's actual reality.

Loaded lazily and cached on first call. ``reload_business_context()``
forces a re-read (useful in tests or when the owner edits the file
mid-session).

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
_loaded = False


def get_business_context_path() -> Path:
    return _BUSINESS_CONTEXT_PATH


def load_business_context() -> Optional[str]:
    """Return MY_BUSINESS.md content (cached). ``None`` if missing/empty."""
    global _cached, _loaded
    if _loaded:
        return _cached
    _loaded = True
    try:
        text = _BUSINESS_CONTEXT_PATH.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        _cached = None
        return None
    text = text.strip()
    _cached = text or None
    return _cached


def reload_business_context() -> Optional[str]:
    """Force re-read on next call."""
    global _cached, _loaded
    _cached = None
    _loaded = False
    return load_business_context()
