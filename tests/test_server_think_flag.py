"""Phase 0B.1 — server.py `_extract_think_flag` helper tests.

Targeted unit tests for the wire-level shape validator. No live HTTP call;
we import the helper directly and drive it through representative payloads.
The upstream deployment flag (``AI_ENABLE_THINKING`` env var) is NOT this
helper's concern — ``agent._resolve_thinking`` handles that.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from server import _extract_think_flag


class TestExtractThinkFlag:
    def test_missing_key_returns_false(self):
        assert _extract_think_flag({}) is False

    def test_none_value_returns_false(self):
        assert _extract_think_flag({"think": None}) is False

    def test_explicit_true(self):
        assert _extract_think_flag({"think": True}) is True

    def test_explicit_false(self):
        assert _extract_think_flag({"think": False}) is False

    def test_non_dict_returns_false(self):
        # Defensive: payload validators upstream already guarantee dict, but
        # the helper should not crash on weird shapes.
        assert _extract_think_flag(None) is False
        assert _extract_think_flag([]) is False
        assert _extract_think_flag("garbage") is False

    def test_string_true_rejected_as_400(self):
        # JSON string "true" is not a boolean — wire-level reject.
        with pytest.raises(HTTPException) as exc:
            _extract_think_flag({"think": "true"})
        assert exc.value.status_code == 400
        assert "boolean" in exc.value.detail.lower()

    def test_integer_rejected_as_400(self):
        # JSON `1` or `0` is not a boolean per strict wire contract.
        # Note: Python's `bool` is a subclass of `int`, so we use `isinstance(x, bool)`
        # in the validator, which correctly accepts `True`/`False` and rejects
        # bare integers like 1, 0, 42.
        with pytest.raises(HTTPException) as exc:
            _extract_think_flag({"think": 1})
        assert exc.value.status_code == 400

    def test_zero_integer_rejected_as_400(self):
        with pytest.raises(HTTPException) as exc:
            _extract_think_flag({"think": 0})
        assert exc.value.status_code == 400

    def test_dict_value_rejected_as_400(self):
        with pytest.raises(HTTPException) as exc:
            _extract_think_flag({"think": {"enabled": True}})
        assert exc.value.status_code == 400

    def test_list_value_rejected_as_400(self):
        with pytest.raises(HTTPException) as exc:
            _extract_think_flag({"think": [True]})
        assert exc.value.status_code == 400


class TestThinkAndModeCoexist:
    """Both Phase 0B.1 `think` and Phase 2 `mode` must round-trip cleanly
    on the same payload without cross-contamination."""

    def test_think_and_mode_present_together(self):
        # Import mode helper here to avoid forcing its import order at top.
        from server import _extract_chat_mode

        payload = {"think": True, "mode": "investigate"}
        assert _extract_think_flag(payload) is True
        assert _extract_chat_mode(payload) == "investigate"

    def test_think_missing_mode_present(self):
        from server import _extract_chat_mode

        payload = {"mode": "chat"}
        assert _extract_think_flag(payload) is False
        assert _extract_chat_mode(payload) == "chat"
