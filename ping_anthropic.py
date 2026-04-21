"""One-shot Anthropic API ping.

Loads .env, sends a minimal Georgian test prompt to Claude 3.5 Sonnet,
prints first response text.

Never prints the API key.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    import anthropic
except ImportError as exc:
    print(f"ERROR: missing dependency: {exc}. Run: pip install anthropic python-dotenv")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent


def main() -> int:
    env_path = ROOT / ".env"
    if not env_path.exists():
        print(f"ERROR: .env not found at {env_path}")
        return 1
    load_dotenv(env_path)

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or not key.startswith("sk-ant-"):
        print("ERROR: ANTHROPIC_API_KEY missing or malformed in .env")
        return 1
    print(f"key length: {len(key)} chars, prefix: {key[:8]}...")

    model = os.environ.get("AI_MODEL", "claude-3-5-sonnet-20241022")
    print(f"model: {model}")

    client = anthropic.Anthropic(api_key=key)

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "გამარჯობა. ეს არის ტესტ-პინგი Financial Dashboard-დან. "
                        "უბრალოდ მომიპასუხე ქართულად ერთი მოკლე წინადადებით რომ კავშირი მუშაობს."
                    ),
                }
            ],
        )
    except anthropic.APIStatusError as exc:
        print(f"ERROR: Anthropic API status error: {exc.status_code} {exc.message}")
        return 1
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1

    text_parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
    reply = "\n".join(text_parts).strip()

    print("\n=== Claude reply ===")
    print(reply)
    print("\n=== Usage ===")
    print(f"input_tokens : {resp.usage.input_tokens}")
    print(f"output_tokens: {resp.usage.output_tokens}")
    print(f"stop_reason  : {resp.stop_reason}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
