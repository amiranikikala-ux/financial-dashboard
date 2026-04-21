"""Regression tests for Phase 0A.3 — Today's Pulse context builder.

Covers:
- `build_today_context` output shape + defensive fallbacks;
- `format_today_block` XML-tagged formatting + Georgian labels;
- Agent integration: Today's Pulse is prepended as a NON-cached second system
  block, never overrides the cached base prompt, can be toggled off.

Contract guarantees enforced here:
1. Module NEVER raises on missing/broken data — always returns a valid dict
   with at least `date` + `weekday`.
2. Agent's `today_context_enabled=False` path produces exactly 1 system block
   (preserves Phase 1/2 cache contract).
3. Agent's `today_context_enabled=True` path (default) produces 2 system
   blocks: base (cached) + today (NOT cached).
4. LLM-visible block wraps content in `<TODAY>...</TODAY>` so the model can
   locate it predictably.
"""

from __future__ import annotations

import datetime as _dt

from dashboard_pipeline.ai.agent import AIAgent
from dashboard_pipeline.ai.config import AIConfig
from dashboard_pipeline.ai.today_context import (
    GEORGIAN_WEEKDAYS,
    STORE_LABELS,
    build_today_block,
    build_today_context,
    format_today_block,
)


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

FIXED_TODAY = _dt.date(2026, 4, 18)  # Saturday — Georgian weekday = "შაბათი"


def _yesterday_row(store: str, revenue: float, date: str = "2026-04-17") -> dict:
    """Minimal synthetic retail_sales.rows_preview row."""
    return {
        "date": date,
        "object": store,
        "revenue_ge": revenue,
        "cost_ge": revenue * 0.9,
        "profit_ge": revenue * 0.1,
        "quantity": 1.0,
        "product_name": "x",
        "product_code": "x",
        "barcode": "x",
        "category": "x",
        "file_name": "x",
        "unit": "x",
    }


def _happy_fixture() -> dict:
    """Synthetic data.json slice: 7 days of Ozurgeti + Dvabzu retail + aging."""
    rows = []
    # Seven-day rolling window: 2026-04-11 .. 2026-04-17 (yesterday).
    for i, date in enumerate(
        [
            "2026-04-11", "2026-04-12", "2026-04-13", "2026-04-14",
            "2026-04-15", "2026-04-16", "2026-04-17",
        ]
    ):
        rows.append(_yesterday_row("ოზურგეთი", 14000.0 + i * 100, date=date))
        rows.append(_yesterday_row("დვაბზუ", 3000.0 + i * 30, date=date))
    return {
        "retail_sales": {"rows_preview": rows},
        "aging_summary": {
            "current": 12000.0,
            "overdue_30": 4500.0,
            "overdue_60": 2200.0,
            "overdue_90": 1000.0,
            "overdue_180": 500.0,
            "overdue_180_plus": 0.0,
        },
        "supplier_aging": [
            {
                "ორგანიზაცია": "შპს Alpha",
                "current": 5000.0,
                "overdue_30": 2000.0,
                "overdue_60": 3000.0,
                "overdue_90": 1500.0,
                "overdue_180": 500.0,
                "overdue_180_plus": 0.0,
            },
        ],
    }


def _config(api_key: str = "sk-ant-test-key") -> AIConfig:
    return AIConfig(api_key=api_key, model="claude-sonnet-4-6")


class _NoLLMClient:
    """AIAgent expects a client with `.messages.create`/`.messages.stream`.

    For today_context tests we never actually invoke chat(), we only
    introspect `_maybe_today_block()` — so a minimal stub is fine.
    """

    class _Messages:
        def create(self, **_kwargs):  # pragma: no cover — should not be hit
            raise AssertionError("client should not be called by today_context tests")

        def stream(self, **_kwargs):  # pragma: no cover
            raise AssertionError("client should not be called by today_context tests")

    def __init__(self):
        self.messages = self._Messages()


# ---------------------------------------------------------------------------
# build_today_context — happy path
# ---------------------------------------------------------------------------

class TestBuildTodayContextHappyPath:
    def test_date_and_weekday_set(self):
        ctx = build_today_context(_happy_fixture, today=FIXED_TODAY)
        assert ctx["date"] == "2026-04-18"
        assert ctx["weekday"] == "შაბათი"
        assert ctx["weekday"] in GEORGIAN_WEEKDAYS

    def test_yesterday_pos_contains_both_stores(self):
        ctx = build_today_context(_happy_fixture, today=FIXED_TODAY)
        ypos = ctx["yesterday_pos"]
        for store in STORE_LABELS:
            assert store in ypos
            assert "revenue_ge" in ypos[store]

    def test_yesterday_revenue_matches_fixture(self):
        ctx = build_today_context(_happy_fixture, today=FIXED_TODAY)
        # Last day (2026-04-17) Ozurgeti = 14000 + 6*100 = 14600.
        assert ctx["yesterday_pos"]["ოზურგეთი"]["revenue_ge"] == 14600.0
        # Dvabzu yesterday = 3000 + 6*30 = 3180.
        assert ctx["yesterday_pos"]["დვაბზუ"]["revenue_ge"] == 3180.0

    def test_avg7_and_delta_pct_computed(self):
        ctx = build_today_context(_happy_fixture, today=FIXED_TODAY)
        ozurgeti = ctx["yesterday_pos"]["ოზურგეთი"]
        assert "avg7_ge" in ozurgeti
        assert "delta_pct" in ozurgeti
        # 6-day window avg (excluding yesterday): 14000..14500 = 14250.0
        assert ozurgeti["avg7_ge"] == 14250.0
        # delta = (14600 − 14250) / 14250 × 100 ≈ +2.46
        assert abs(ozurgeti["delta_pct"] - 2.46) < 0.1

    def test_cash_forecast_uses_aging_summary_first(self):
        ctx = build_today_context(_happy_fixture, today=FIXED_TODAY)
        cash = ctx["cash_forecast_7day"]
        assert cash["upcoming_ap"] == 12000.0
        # overdue = 4500 + 2200 + 1000 + 500 + 0 = 8200
        assert cash["overdue_total"] == 8200.0
        assert cash["window_days"] == 7

    def test_notes_empty_on_happy_path(self):
        ctx = build_today_context(_happy_fixture, today=FIXED_TODAY)
        assert ctx["notes"] == []


# ---------------------------------------------------------------------------
# build_today_context — defensive fallbacks
# ---------------------------------------------------------------------------

class TestBuildTodayContextDefensive:
    def test_empty_data_returns_date_weekday_plus_notes(self):
        ctx = build_today_context(lambda: {}, today=FIXED_TODAY)
        assert ctx["date"] == "2026-04-18"
        assert ctx["weekday"] == "შაბათი"
        assert ctx["yesterday_pos"] == {}
        assert ctx["notes"]  # at least one breadcrumb

    def test_broken_data_loader_never_raises(self):
        def _broken():
            raise RuntimeError("disk full")

        ctx = build_today_context(_broken, today=FIXED_TODAY)
        # Must NOT propagate — chat turn would die otherwise.
        assert ctx["date"] == "2026-04-18"
        assert any("disk full" in n or "RuntimeError" in n for n in ctx["notes"])

    def test_non_dict_data_returns_note(self):
        ctx = build_today_context(lambda: [1, 2, 3], today=FIXED_TODAY)
        assert ctx["yesterday_pos"] == {}
        assert any("dict" in n.lower() for n in ctx["notes"])

    def test_missing_retail_sales_leaves_pos_empty(self):
        def _loader():
            return {"aging_summary": {"current": 100}}

        ctx = build_today_context(_loader, today=FIXED_TODAY)
        assert ctx["yesterday_pos"] == {}

    def test_yesterday_all_zeros_adds_staleness_note(self):
        """When every store has 0 ₾ yesterday, that's usually "data not
        refreshed" not "stores earned nothing" — note must warn the LLM."""
        def _loader():
            return {
                "retail_sales": {
                    "rows_preview": [
                        _yesterday_row("ოზურგეთი", 5000.0, date="2026-04-10"),
                        _yesterday_row("დვაბზუ", 1000.0, date="2026-04-10"),
                    ]
                }
            }

        ctx = build_today_context(_loader, today=FIXED_TODAY)
        # Yesterday (2026-04-17) → nothing in rows_preview; all stores 0.
        assert ctx["yesterday_pos"]["ოზურგეთი"]["revenue_ge"] == 0
        assert ctx["yesterday_pos"]["დვაბზუ"]["revenue_ge"] == 0
        assert any("0 ₾" in n or "არ განახლდა" in n for n in ctx["notes"])


# ---------------------------------------------------------------------------
# Top risks detection
# ---------------------------------------------------------------------------

class TestTopRisks:
    def test_pos_drop_flagged(self):
        """Dvabzu drops 50% vs 7-day avg — must surface in top_risks."""
        rows = []
        # 6 baseline days at 3000, then yesterday = 1500 (−50%).
        for date in (
            "2026-04-11", "2026-04-12", "2026-04-13", "2026-04-14",
            "2026-04-15", "2026-04-16",
        ):
            rows.append(_yesterday_row("ოზურგეთი", 14000, date=date))
            rows.append(_yesterday_row("დვაბზუ", 3000, date=date))
        rows.append(_yesterday_row("ოზურგეთი", 14200, date="2026-04-17"))
        rows.append(_yesterday_row("დვაბზუ", 1500, date="2026-04-17"))

        ctx = build_today_context(
            lambda: {"retail_sales": {"rows_preview": rows}},
            today=FIXED_TODAY,
        )
        risks = ctx["top_risks"]
        assert any("დვაბზუ" in r for r in risks)

    def test_high_overdue_supplier_flagged(self):
        ctx = build_today_context(_happy_fixture, today=FIXED_TODAY)
        # Alpha has overdue_60+ = 3000 + 1500 + 500 + 0 = 5000 (right at
        # the threshold) — flagged.
        assert any("Alpha" in r for r in ctx["top_risks"])

    def test_top_risks_capped_at_three(self):
        # 5 stores with huge drops → only top 3 surface.
        # Use synthetic store labels so only ოზურგეთი + დვაბზუ's real
        # drops count.  Add an aging overrun too.
        rows = []
        for date in (
            "2026-04-11", "2026-04-12", "2026-04-13", "2026-04-14",
            "2026-04-15", "2026-04-16",
        ):
            rows.append(_yesterday_row("ოზურგეთი", 14000, date=date))
            rows.append(_yesterday_row("დვაბზუ", 3000, date=date))
        rows.append(_yesterday_row("ოზურგეთი", 1000, date="2026-04-17"))  # −93%
        rows.append(_yesterday_row("დვაბზუ", 200, date="2026-04-17"))     # −93%

        ctx = build_today_context(
            lambda: {
                "retail_sales": {"rows_preview": rows},
                "aging_summary": {
                    "current": 500.0,
                    "overdue_30": 5000.0,
                    "overdue_60": 5000.0,
                    "overdue_90": 5000.0,
                    "overdue_180": 0.0,
                    "overdue_180_plus": 0.0,
                },
                "supplier_aging": [
                    {
                        "ორგანიზაცია": "შპს Gamma",
                        "overdue_60": 20000,
                        "overdue_90": 5000,
                        "overdue_180": 0,
                        "overdue_180_plus": 0,
                    },
                ],
            },
            today=FIXED_TODAY,
        )
        assert len(ctx["top_risks"]) <= 3


# ---------------------------------------------------------------------------
# format_today_block — XML wrapping + Georgian labels
# ---------------------------------------------------------------------------

class TestFormatTodayBlock:
    def test_block_wrapped_in_today_tags(self):
        block = format_today_block(
            build_today_context(_happy_fixture, today=FIXED_TODAY)
        )
        assert block.startswith("<TODAY>")
        assert block.endswith("</TODAY>")

    def test_block_contains_date_and_weekday(self):
        block = build_today_block(_happy_fixture, today=FIXED_TODAY)
        assert "2026-04-18" in block
        assert "შაბათი" in block

    def test_block_contains_both_store_pos_lines(self):
        block = build_today_block(_happy_fixture, today=FIXED_TODAY)
        assert "ოზურგეთი" in block
        assert "დვაბზუ" in block

    def test_block_uses_georgian_labels(self):
        block = build_today_block(_happy_fixture, today=FIXED_TODAY)
        assert "თარიღი" in block
        assert "POS" in block

    def test_empty_data_produces_compact_block(self):
        block = build_today_block(lambda: {}, today=FIXED_TODAY)
        assert "<TODAY>" in block
        assert "</TODAY>" in block
        # At minimum: date line + notes.
        assert "2026-04-18" in block
        assert "შენიშვნები" in block


# ---------------------------------------------------------------------------
# Agent integration
# ---------------------------------------------------------------------------

class _CapturingClient:
    """Records a single messages.create call; returns a trivial end_turn."""

    class _Msg:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)

            class _Usage:
                input_tokens = 10
                output_tokens = 3
                cache_creation_input_tokens = 0
                cache_read_input_tokens = 0

            class _Resp:
                stop_reason = "end_turn"
                usage = _Usage()
                content = [type("B", (), {"type": "text", "text": "OK"})()]

            return _Resp()

    def __init__(self):
        self.messages = self._Msg()


class TestAgentTodayContextIntegration:
    def test_default_enabled_produces_two_system_blocks(self):
        client = _CapturingClient()
        agent = AIAgent(
            config=_config(),
            data_loader=_happy_fixture,
            client=client,
            # today_context_enabled defaults to True
        )
        agent.chat("test")
        system = client.messages.calls[0]["system"]
        assert isinstance(system, list)
        assert len(system) == 2
        # Block 0 = base prompt with cache_control.
        assert system[0]["cache_control"] == {"type": "ephemeral"}
        assert "🎯 როლის კონტრაქტი" in system[0]["text"]
        # Block 1 = today block WITHOUT cache_control.
        assert "cache_control" not in system[1]
        assert "<TODAY>" in system[1]["text"]

    def test_explicit_disable_single_system_block(self):
        client = _CapturingClient()
        agent = AIAgent(
            config=_config(),
            data_loader=_happy_fixture,
            client=client,
            today_context_enabled=False,
        )
        agent.chat("test")
        system = client.messages.calls[0]["system"]
        assert len(system) == 1
        assert system[0]["cache_control"] == {"type": "ephemeral"}

    def test_broken_data_loader_does_not_break_chat(self):
        """Chat must still complete when today_context build fails."""
        def _broken():
            raise RuntimeError("boom")

        client = _CapturingClient()
        agent = AIAgent(
            config=_config(),
            data_loader=_broken,
            client=client,
            today_context_enabled=True,
        )
        # Should NOT raise.
        result = agent.chat("test")
        assert result["reply"] == "OK"
        system = client.messages.calls[0]["system"]
        # Broken data_loader still produces a (minimal) today block with
        # date + breadcrumb — so we still have 2 blocks.
        assert len(system) == 2

    def test_investigate_mode_also_gets_today_block(self):
        """Today's Pulse is mode-agnostic — helpful in both chat + investigate."""
        client = _CapturingClient()
        agent = AIAgent(
            config=_config(),
            data_loader=_happy_fixture,
            client=client,
            today_context_enabled=True,
        )
        agent.chat("test", mode="investigate")
        system = client.messages.calls[0]["system"]
        assert len(system) == 2
        assert "data investigator" in system[0]["text"]
        assert "<TODAY>" in system[1]["text"]
