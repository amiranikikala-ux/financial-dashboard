"""Phase 2.4 REDUCED — live Anthropic dog-food for
`prepare_supplier_brief` portfolio `sort_by` extension.

Verifies on REAL Sonnet 4.6 turns that:

1. Payment-risk questions route to `prepare_supplier_brief(sort_by="risk")`
   → summary_ka carries the "#1 risk" / "debt-at-risk" headline and
   `sort_mode` echoed as "risk" in the tool payload.
2. Negotiation/leverage questions keep the default behavior — no `sort_by`
   arg OR `sort_by="leverage"` — producing the legacy summary_ka shape
   ("#1 call" + "portfolio savings") unchanged (backward-compat).
3. Focused supplier-name requests still hit FOCUSED mode (not portfolio),
   so the new portfolio `sort_by` param didn't break routing discipline.

Runs IN-PROCESS. Cost budget: ~$0.35 across 3 scenarios.
"""
from __future__ import annotations

import json
import os
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
    expected_payload_has: Optional[Dict[str, Any]] = None,
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
    parsed_payloads: List[Dict[str, Any]] = []
    for body in tool_results:
        try:
            parsed = json.loads(body)
        except (TypeError, ValueError):
            continue
        if not isinstance(parsed, dict):
            continue
        parsed_payloads.append(parsed)
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

    payload_ok = True
    if expected_payload_has:
        payload_ok = any(
            all(
                str(p.get(k, "")).lower() == str(v).lower()
                for k, v in expected_payload_has.items()
            )
            for p in parsed_payloads
        )

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
        if expected_payload_has:
            checks.append(_p(
                f"payload includes {expected_payload_has}",
                payload_ok,
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

    # Scenario 1: strategic payment-risk monitoring → sort_by="risk" portfolio.
    # Framing intentionally avoids "how much debt with whom" (that's the
    # `read_data_json(supplier_aging)` anti-trigger baked into the schema
    # description). Instead we ask for a *ranked watch list* — that's the
    # sort_by="risk" use case.
    # Expect risk-mode summary_ka + sort_mode=risk echo in payload.
    results.append(_run_scenario(
        agent,
        label="1. portfolio sort_by=risk — watch list for payment reliability",
        message=(
            "მომწოდებლების პორტფოლიოში ვისი payment reliability-ია ყველაზე "
            "ცუდი? ვინ უნდა ჩავსვა watch list-ზე შემდეგი კვარტალისთვის? "
            "ranked ranking მინდა — ვის დავაკვირდე პირველ რიგში."
        ),
        expected_tool="prepare_supplier_brief",
        expected_tool_arg_has={"sort_by": "risk"},
        expected_payload_has={"sort_mode": "risk"},
        summary_ka_must_contain=["#1 risk", "debt-at-risk"],
        summary_ka_must_not_contain=["portfolio savings"],
    ))

    # Scenario 2: negotiation-priority question → default leverage mode.
    # Must NOT carry risk-mode markers; must preserve legacy summary_ka.
    results.append(_run_scenario(
        agent,
        label="2. portfolio leverage default — negotiation priority (backward-compat)",
        message=(
            "ვის ვთხოვო discount-ი ჯერ? რომელ მომწოდებელთან მაქვს ყველაზე "
            "დიდი leverage და რა annual savings-ია შესაძლებელი?"
        ),
        expected_tool="prepare_supplier_brief",
        expected_payload_has={"sort_mode": "leverage"},
        summary_ka_must_contain=["#1 call", "portfolio savings"],
        summary_ka_must_not_contain=["#1 risk", "debt-at-risk"],
    ))

    # Scenario 3: focused brief — specific supplier by name.
    # Portfolio `sort_by` extension must not break FOCUSED routing.
    results.append(_run_scenario(
        agent,
        label="3. focused supplier brief — routing intact after sort_by addition",
        message=(
            "შპს ჯიდიაიზე გამიკეთე ერთი მომწოდებლის brief — "
            "რამდენი leverage მაქვს და რა play-ები შემოგვაქვს?"
        ),
        expected_tool="prepare_supplier_brief",
        summary_ka_must_contain=["leverage"],
        summary_ka_must_not_contain=[
            "მომწოდებელი, სულ",  # portfolio header (total_suppliers count)
        ],
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
