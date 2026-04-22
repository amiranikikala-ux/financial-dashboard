"""Sprint 4C.3 — live Anthropic dog-food for Sprint 4C.2 summary_ka additions.

Goal: verify on a REAL Anthropic turn that the four freshly-enhanced tools
(`prepare_supplier_brief` focused + portfolio, `validate_vs_source`,
`recall_context`) ship `summary_ka` in their tool_result, AND that the AI
actually leans on it instead of re-narrating the raw JSON.

Runs IN-PROCESS (no Windows Service restart needed — service still holds
the pre-Sprint 4C.2-remaining snapshot of `tools.py`; this script imports
the working tree directly so my freshly-committed code is exercised).

Cost budget: ~$0.25 total across 3 scenarios (Sonnet 4.6 think=True).
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
) -> Dict[str, Any]:
    print(f"\n{'=' * 70}")
    print(f"SCENARIO: {label}")
    print(f"{'=' * 70}")
    print(f"user: {message[:120]}")

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
    tool_results: List[Dict[str, Any]] = []
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
        print(f"  - {tc['name']}")

    # Extract summary_ka from tool_results.
    summary_ka_seen: List[str] = []
    for body in tool_results:
        try:
            parsed = json.loads(body)
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("summary_ka"), str):
            summary_ka_seen.append(parsed["summary_ka"])

    print(f"summary_ka found in tool_results: {len(summary_ka_seen)}")
    for sk in summary_ka_seen:
        print(f"  « {sk[:180]} »")

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

    # Anti-markers (Phase 4B rules — should be absent).
    anti_markers = (
        "ვცდი და მოვახსენებ",
        "ჩემს მეხსიერებაში",
        "მშვენიერი კითხვაა",
    )
    any_anti_marker = any(m in reply for m in anti_markers)

    checks = [
        _p(f"{expected_tool} was called", called_right),
        _p("summary_ka present in ≥1 tool_result", has_summary),
        _p("summary_ka contains all expected fragments", all_fragments_present),
        _p("usage.thinking == True", thinking_on),
        _p("no anti-markers in reply", not any_anti_marker),
    ]

    print()
    print(f"=== AI REPLY (first 1000 chars) ===")
    print(reply[:1000])

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

    # Scenario 1: prepare_supplier_brief FOCUSED mode.
    # "ვასაძე" is a known supplier in data.json (top-5 by spend).
    results.append(_run_scenario(
        agent,
        label="1. supplier_brief FOCUSED — ვასაძე negotiation",
        message=(
            "ხვალ ვასაძესთან მაქვს შეხვედრა მომწოდებლის მხრიდან. "
            "რა ვთხოვო? მითხარი ცოცხლად leverage-ი რა მაქვს."
        ),
        expected_tool="prepare_supplier_brief",
        summary_ka_must_contain=["leverage", "play"],
    ))

    # Scenario 2: prepare_supplier_brief PORTFOLIO mode.
    results.append(_run_scenario(
        agent,
        label="2. supplier_brief PORTFOLIO — first call priority",
        message=(
            "მომწოდებლებს რომ გადავხედო, ვის ვესაუბრო პირველად "
            "ფასდაკლების მოსალაპარაკებლად? მთლიანი portfolio-დან "
            "top-3 რომელია?"
        ),
        expected_tool="prepare_supplier_brief",
        summary_ka_must_contain=["მომწოდებელი", "top-5"],
    ))

    # Scenario 3: validate_vs_source — inspection path (no expected values).
    results.append(_run_scenario(
        agent,
        label="3. validate_vs_source — suppliers section inspection",
        message=(
            "შეამოწმე suppliers section data.json-ში — რამდენი row-ია "
            "ახლა და source-ი რა არის?"
        ),
        expected_tool="validate_vs_source",
        summary_ka_must_contain=["suppliers", "მწკრივი"],
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
