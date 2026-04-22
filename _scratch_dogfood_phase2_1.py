"""Phase 2.1 — live Anthropic dog-food for `compute_cash_flow_projection`.

Goal: verify on a REAL Anthropic turn that the new daily-projection tool:
1. gets invoked on forward-looking daily cash questions (not confused with
   cash_runway)
2. ships `summary_ka` in its tool_result
3. the AI narrates the red-day count / min balance / forecast engines
   verbatim from summary_ka instead of re-narrating the raw daily series
4. does NOT trigger on static "how many months do I have left" questions
   (→ compute_cash_runway should win instead)

Runs IN-PROCESS (no Windows Service restart needed — service still holds
pre-Phase-2.1 tools.py; this script imports the working tree directly so
my freshly-committed code is exercised).

Cost budget: ~$0.30 total across 3 scenarios (Sonnet 4.6 think=True).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from dashboard_pipeline.ai.agent import AIAgent  # noqa: E402
from dashboard_pipeline.ai.config import load_ai_config  # noqa: E402
from backend_paths import get_dashboard_data_path  # noqa: E402

DATA_PATH = Path(get_dashboard_data_path())


def _loader() -> Dict[str, Any]:
    with open(DATA_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _run_scenario(
    agent: AIAgent,
    *,
    label: str,
    message: str,
    expected_tool: str,
    summary_ka_must_contain: List[str],
    forbid_tool: str | None = None,
) -> Dict[str, Any]:
    print(f"\n{'=' * 70}")
    print(f"SCENARIO: {label}")
    print(f"{'=' * 70}")
    print(f"user: {message[:160]}")

    start = time.time()
    try:
        result = agent.chat(message, mode="chat", think=True)
    except Exception as exc:
        print(f"[ERR] chat failed: {exc!r}")
        return {"ok": False, "label": label, "error": str(exc)}

    elapsed = time.time() - start
    reply = result.get("reply") or ""
    usage = result.get("usage") or {}
    history = result.get("history") or []

    tool_calls: List[Dict[str, Any]] = []
    tool_results: List[str] = []
    for msg in history:
        blocks = msg.get("content") or []
        if not isinstance(blocks, list):
            continue
        for b in blocks:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                tool_calls.append(
                    {"name": b.get("name"), "input": b.get("input") or {}}
                )
            elif b.get("type") == "tool_result":
                body = b.get("content")
                if isinstance(body, list):
                    for piece in body:
                        if isinstance(piece, dict) and piece.get("type") == "text":
                            tool_results.append(piece.get("text") or "")
                elif isinstance(body, str):
                    tool_results.append(body)

    print(f"elapsed: {elapsed:.1f}s | usage: {usage}")
    print(f"tool_calls ({len(tool_calls)}):")
    for tc in tool_calls:
        print(f"  - {tc['name']} {list(tc['input'].keys())}")

    summary_ka_seen: List[str] = []
    for body in tool_results:
        try:
            parsed = json.loads(body)
        except (TypeError, ValueError):
            continue
        if not isinstance(parsed, dict):
            continue
        # Accept either the Phase 4C.2 canonical key (`summary_ka`) OR the
        # legacy Phase 3.5 `status_summary_ka` used by `compute_cash_runway`.
        for key in ("summary_ka", "status_summary_ka"):
            val = parsed.get(key)
            if isinstance(val, str):
                summary_ka_seen.append(val)

    print(f"summary_ka found in tool_results: {len(summary_ka_seen)}")
    for sk in summary_ka_seen:
        print(f"  « {sk[:220]} »")

    def _p(name: str, ok: bool) -> bool:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        return ok

    print("=== checks ===")
    called_right = any(tc["name"] == expected_tool for tc in tool_calls)
    has_summary = len(summary_ka_seen) > 0
    thinking_on = usage.get("thinking") is True

    all_fragments_present = all(
        any(frag in sk for sk in summary_ka_seen)
        for frag in summary_ka_must_contain
    ) if summary_ka_seen else False

    forbid_ok = True
    if forbid_tool:
        forbid_ok = not any(tc["name"] == forbid_tool for tc in tool_calls)

    # Anti-markers (Phase 4B rules — should be absent).
    anti_markers = (
        "ვცდი და მოვახსენებ",
        "ჩემს მეხსიერებაში",
        "მშვენიერი კითხვაა",
    )
    any_anti_marker = any(m in reply for m in anti_markers)

    checks = [
        _p(f"{expected_tool} was called", called_right),
    ]
    if forbid_tool:
        checks.append(_p(f"{forbid_tool} was NOT called", forbid_ok))
    if called_right:
        checks.append(_p("summary_ka present in ≥1 tool_result", has_summary))
        checks.append(_p("summary_ka contains all expected fragments", all_fragments_present))
    checks.append(_p("usage.thinking == True", thinking_on))
    checks.append(_p("no anti-markers in reply", not any_anti_marker))

    print()
    print("=== AI REPLY (first 1200 chars) ===")
    print(reply[:1200])

    return {
        "ok": all(checks),
        "label": label,
        "elapsed": elapsed,
        "usage": usage,
        "tool_calls": [tc["name"] for tc in tool_calls],
        "summary_ka_seen": summary_ka_seen,
        "anti_marker_hit": any_anti_marker,
    }


def main() -> int:
    cfg = load_ai_config()
    if not cfg.is_enabled:
        print("ANTHROPIC_API_KEY missing; aborting.")
        return 1
    if not cfg.enable_thinking:
        print("AI_ENABLE_THINKING env must be 'true' for think=True scenarios.")
        return 1

    print(f"model: {cfg.model} / think budget: {cfg.thinking_budget_tokens}")
    print(f"data.json size: {DATA_PATH.stat().st_size / 1_048_576:.1f} MB")

    agent = AIAgent(cfg, _loader, today_context_enabled=False)

    results: List[Dict[str, Any]] = []

    # Scenario 1: daily forward cash projection — tool MUST trigger.
    # Provide balances upfront so AI doesn't waste a turn asking.
    results.append(_run_scenario(
        agent,
        label="1. cash_flow_projection — 14 day forward trajectory",
        message=(
            "BOG ნაშთი 28,000 ₾ მაქვს, TBC 12,500 ₾. მომდევნო 14 დღეში როდის "
            "ჩავარდები მინუსში? ყოველდღიური cash flow პროგნოზი მინდა — "
            "ცოცხლად მითხარი რომელ დღეებში გვექნება პრობლემა."
        ),
        expected_tool="compute_cash_flow_projection",
        summary_ka_must_contain=["დღის პროექცია", "საწყისი"],
    ))

    # Scenario 2: upcoming_payments overlay — user provides fixed commitment.
    results.append(_run_scenario(
        agent,
        label="2. cash_flow_projection — with upcoming fixed payment (ქირა)",
        message=(
            "BOG 15,000 ₾, TBC 8,000 ₾ მაქვს. 3 მაისს ქირა 4,500 ₾ "
            "უნდა გადავიხადო. 2 კვირიანი daily cash flow დამიტანე — "
            "ეს გადახდა ითვალისწინე."
        ),
        expected_tool="compute_cash_flow_projection",
        summary_ka_must_contain=["დღის პროექცია"],
    ))

    # Scenario 3: anti-trigger — static "how many months" question MUST
    # route to compute_cash_runway, NOT the new daily projection tool.
    results.append(_run_scenario(
        agent,
        label="3. cash_runway (anti-trigger) — months-left question",
        message=(
            "BOG 50,000 ₾, TBC 20,000 ₾ მაქვს. ამჟამინდელი burn rate-ით "
            "რამდენი თვე ვძლებ? cash runway რა მაქვს?"
        ),
        expected_tool="compute_cash_runway",
        summary_ka_must_contain=[],  # cash_runway uses status_summary_ka not summary_ka
        forbid_tool="compute_cash_flow_projection",
    ))

    # Aggregate report.
    print(f"\n\n{'=' * 70}")
    print("AGGREGATE")
    print(f"{'=' * 70}")
    passed = sum(1 for r in results if r.get("ok"))
    print(f"scenarios passed: {passed}/{len(results)}")
    for r in results:
        status = "✅" if r.get("ok") else "❌"
        print(f"  {status} {r['label']}")

    total_input = sum(
        int(r.get("usage", {}).get("input_tokens") or 0) for r in results
    )
    total_output = sum(
        int(r.get("usage", {}).get("output_tokens") or 0) for r in results
    )
    total_cache_read = sum(
        int(r.get("usage", {}).get("cache_read_input_tokens") or 0)
        for r in results
    )
    # Sonnet 4.6 pricing: $3/MTok in, $15/MTok out, $0.30/MTok cache read.
    cost_usd = (
        total_input * 3.0 / 1_000_000
        + total_output * 15.0 / 1_000_000
        + total_cache_read * 0.30 / 1_000_000
    )
    print(
        f"\ntokens: in={total_input:,} out={total_output:,} "
        f"cache_read={total_cache_read:,}"
    )
    print(f"est. cost: ${cost_usd:.4f}")

    return 0 if passed == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
