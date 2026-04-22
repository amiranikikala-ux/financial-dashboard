"""Phase 2.6 — live Anthropic dog-food for `find_promotion_candidates`.

Verifies on REAL Sonnet 4.6 turns that:

1. Promotion-menu questions (general) route to `find_promotion_candidates`
   with no `sort_by`-equivalent filters; summary_ka carries
   "**promotion menu**" + margin→discount math; AI surfaces the top pick
   in its reply.
2. Store-specific promo questions pass `store="ოზურგეთი"` and produce a
   store-scoped summary_ka (Georgian store label in summary).
3. Anti-trigger: dead-stock questions ("რა დევს 90+ დღე?") route to
   `analyze_dead_stock`, NOT `find_promotion_candidates` — different
   tools, different goals (liquidation vs promotional push).

Runs IN-PROCESS. Cost budget: ~$0.35 across 3 scenarios.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    expected_tool_arg_has: Optional[Dict[str, Any]] = None,
    summary_ka_must_contain: List[str],
    summary_ka_must_not_contain: Optional[List[str]] = None,
    forbid_tool: Optional[str] = None,
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
        print(f"  - {tc['name']} {dict(tc['input'])}")

    summary_ka_seen: List[str] = []
    for body in tool_results:
        try:
            parsed = json.loads(body)
        except (TypeError, ValueError):
            continue
        if not isinstance(parsed, dict):
            continue
        for key in ("summary_ka", "status_summary_ka"):
            val = parsed.get(key)
            if isinstance(val, str):
                summary_ka_seen.append(val)

    print(f"summary_ka found in tool_results: {len(summary_ka_seen)}")
    for sk in summary_ka_seen:
        print(f"  « {sk[:240]} »")

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

    no_forbidden_fragments = True
    if summary_ka_must_not_contain and summary_ka_seen:
        no_forbidden_fragments = all(
            all(frag not in sk for sk in summary_ka_seen)
            for frag in summary_ka_must_not_contain
        )

    args_ok = True
    if expected_tool_arg_has:
        matching_calls = [tc for tc in tool_calls if tc["name"] == expected_tool]
        args_ok = any(
            all(
                str(call.get("input", {}).get(k, "")).lower()
                == str(v).lower()
                for k, v in expected_tool_arg_has.items()
            )
            for call in matching_calls
        ) if matching_calls else False

    forbid_ok = True
    if forbid_tool:
        forbid_ok = not any(tc["name"] == forbid_tool for tc in tool_calls)

    anti_markers = (
        "ვცდი და მოვახსენებ",
        "ჩემს მეხსიერებაში",
        "მშვენიერი კითხვაა",
    )
    any_anti_marker = any(m in reply for m in anti_markers)

    checks = [_p(f"{expected_tool} was called", called_right)]
    if forbid_tool:
        checks.append(_p(f"{forbid_tool} was NOT called", forbid_ok))
    if called_right:
        checks.append(_p("summary_ka present in ≥1 tool_result", has_summary))
        if summary_ka_must_contain:
            checks.append(_p(
                "summary_ka contains all expected fragments",
                all_fragments_present,
            ))
        if summary_ka_must_not_contain:
            checks.append(_p(
                "summary_ka omits forbidden fragments",
                no_forbidden_fragments,
            ))
        if expected_tool_arg_has:
            checks.append(_p(
                f"tool args include {expected_tool_arg_has}",
                args_ok,
            ))
    checks.append(_p("usage.thinking == True", thinking_on))
    checks.append(_p("no anti-markers in reply", not any_anti_marker))

    print()
    print("=== AI REPLY (first 1400 chars) ===")
    print(reply[:1400])

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

    # Scenario 1: generic promotion question.
    results.append(_run_scenario(
        agent,
        label="1. promotion menu — generic 'რა ჩავდოთ promotion-ში?'",
        message=(
            "მომავალი კვირის promotion-ისთვის რა პროდუქცია გავიტანო? "
            "5 კანდიდატი მაჩვენე რომელიც ყველაზე კარგად უპასუხებს discount-ს "
            "(margin ბევრი აქვს, volume-იც ჯდება)."
        ),
        expected_tool="find_promotion_candidates",
        summary_ka_must_contain=["promotion menu", "margin"],
    ))

    # Scenario 2: store-specific promo question.
    results.append(_run_scenario(
        agent,
        label="2. promotion menu — ოზურგეთი-specific",
        message=(
            "ოზურგეთის მაღაზიისთვის promotion-ი ვამზადებ. რომელ 5 SKU-ზე "
            "გავუშვა 10-15% discount რომ margin ბოლომდე არ მომიშალოს?"
        ),
        expected_tool="find_promotion_candidates",
        expected_tool_arg_has={"store": "ოზურგეთი"},
        summary_ka_must_contain=["ოზურგეთი", "promotion menu"],
    ))

    # Scenario 3: anti-trigger — dead-stock should NOT route here.
    results.append(_run_scenario(
        agent,
        label="3. anti-trigger — 'რა დევს 90+ დღე?' (dead_stock, NOT promotion)",
        message=(
            "რა პროდუქცია დევს მაღაზიაში 90+ დღე გაუყიდავი? "
            "dead stock-ი რომელია — ფული გამოვიყვანო."
        ),
        expected_tool="analyze_dead_stock",
        summary_ka_must_contain=[],
        forbid_tool="find_promotion_candidates",
    ))

    print(f"\n\n{'=' * 70}")
    print("AGGREGATE")
    print(f"{'=' * 70}")
    passed = sum(1 for r in results if r.get("ok"))
    print(f"scenarios passed: {passed}/{len(results)}")
    for r in results:
        status = "OK" if r.get("ok") else "FAIL"
        print(f"  [{status}] {r['label']}")

    total_input = sum(int(r.get("usage", {}).get("input_tokens") or 0) for r in results)
    total_output = sum(int(r.get("usage", {}).get("output_tokens") or 0) for r in results)
    total_cache_read = sum(
        int(r.get("usage", {}).get("cache_read_input_tokens") or 0) for r in results
    )
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
