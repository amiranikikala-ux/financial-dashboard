"""Telegram bot listener for the dashboard's AI Advisor.

Long-polls Telegram ``getUpdates``, forwards each authorised message to
the local ``POST /api/chat`` endpoint, and sends the AI reply back to
the same chat. No webhook / public URL required.

Run:
    python telegram_bot.py

Required .env variables:
    TELEGRAM_BOT_TOKEN   — token from @BotFather
    TELEGRAM_CHAT_ID     — single allowed chat_id (comma-separated for
                           multiple). Messages from any other chat are
                           ignored silently.

Optional:
    DASHBOARD_API_URL    — defaults to http://127.0.0.1:8000
    TELEGRAM_OFFSET_FILE — defaults to .telegram_bot_offset.json

Special commands:
    /start, /help        — short greeting
    /reset               — clear conversation history for that chat
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("telegram_bot")

TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
ALLOWED_CHAT_IDS = {
    s.strip()
    for s in (os.environ.get("TELEGRAM_CHAT_ID") or "").split(",")
    if s.strip()
}
DASHBOARD_API_URL = (os.environ.get("DASHBOARD_API_URL") or "http://127.0.0.1:8000").rstrip("/")
OFFSET_FILE = PROJECT_ROOT / (os.environ.get("TELEGRAM_OFFSET_FILE") or ".telegram_bot_offset.json")
TG_API = f"https://api.telegram.org/bot{TOKEN}"
LONG_POLL_TIMEOUT = 25
TG_MAX_MSG = 4000  # Telegram limit is 4096; leave headroom for safety
HISTORY_BY_CHAT: dict[str, list] = {}


def _read_offset() -> int:
    if not OFFSET_FILE.exists():
        return 0
    try:
        return int(json.loads(OFFSET_FILE.read_text()).get("offset", 0))
    except (OSError, ValueError):
        return 0


def _write_offset(offset: int) -> None:
    try:
        OFFSET_FILE.write_text(json.dumps({"offset": offset}))
    except OSError as e:
        log.warning("offset write failed: %s", e)


def _tg(method: str, **payload) -> dict | None:
    try:
        r = requests.post(f"{TG_API}/{method}", json=payload, timeout=LONG_POLL_TIMEOUT + 5)
        data = r.json()
        if not data.get("ok"):
            log.warning("telegram %s error: %s", method, data)
            return None
        return data.get("result")
    except (requests.RequestException, ValueError) as e:
        log.warning("telegram %s network error: %s", method, e)
        return None


def _send(chat_id: str, text: str) -> None:
    if not text:
        return
    # Split long replies on paragraph boundaries when possible
    while text:
        if len(text) <= TG_MAX_MSG:
            chunk, text = text, ""
        else:
            cut = text.rfind("\n\n", 0, TG_MAX_MSG)
            if cut < 1000:
                cut = text.rfind("\n", 0, TG_MAX_MSG)
            if cut < 1000:
                cut = TG_MAX_MSG
            chunk, text = text[:cut], text[cut:].lstrip("\n")
        _tg("sendMessage", chat_id=chat_id, text=chunk, disable_web_page_preview=True)


def _typing(chat_id: str) -> None:
    _tg("sendChatAction", chat_id=chat_id, action="typing")


def _ai_chat(message: str, history: list | None) -> tuple[str, list]:
    body = {"message": message}
    if history:
        body["history"] = history
    r = requests.post(f"{DASHBOARD_API_URL}/api/chat", json=body, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"AI HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    return data.get("reply") or "(ცარიელი პასუხი)", data.get("history") or []


def _handle_message(msg: dict) -> None:
    chat_id = str(msg.get("chat", {}).get("id") or "")
    text = (msg.get("text") or "").strip()
    if not chat_id or not text:
        return
    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
        log.info("ignored message from unauthorized chat_id=%s", chat_id)
        return

    if text in ("/start", "/help"):
        _send(
            chat_id,
            "გამარჯობა! მე dashboard-ის AI ვარ.\nმომწერე კითხვა — ვუპასუხებ.\n"
            "ბრძანებები:\n  /reset — საუბრის ისტორიის გასუფთავება",
        )
        return

    if text == "/reset":
        HISTORY_BY_CHAT.pop(chat_id, None)
        _send(chat_id, "✅ ისტორია გასუფთავდა.")
        return

    log.info("MSG from %s: %r", chat_id, text[:80])
    _typing(chat_id)
    history = HISTORY_BY_CHAT.get(chat_id)
    try:
        reply, new_history = _ai_chat(text, history)
        HISTORY_BY_CHAT[chat_id] = new_history
        log.info("AI reply (%d chars) — sending to %s", len(reply), chat_id)
        _send(chat_id, reply)
        log.info("sent OK")
    except requests.RequestException as e:
        log.exception("AI request failed")
        _send(chat_id, f"⚠️ ვერ დავუკავშირდი dashboard-ის სერვერს:\n{e}")
    except Exception as e:
        log.exception("AI chat failed")
        _send(chat_id, f"⚠️ შეცდომა AI-ს მხრიდან:\n{type(e).__name__}: {e}")


def main() -> int:
    if not TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is missing in .env", file=sys.stderr)
        return 1

    me = _tg("getMe")
    if not me:
        print("ERROR: getMe failed — bad token or network blocked.", file=sys.stderr)
        return 1
    log.info("connected as @%s (id=%s)", me.get("username"), me.get("id"))
    if ALLOWED_CHAT_IDS:
        log.info("allowed chat_ids: %s", ", ".join(sorted(ALLOWED_CHAT_IDS)))
    else:
        log.warning("TELEGRAM_CHAT_ID is empty — bot will respond to ANY chat (not recommended).")

    offset = _read_offset()
    log.info("starting long-poll loop (offset=%d)", offset)

    while True:
        try:
            r = requests.get(
                f"{TG_API}/getUpdates",
                params={"offset": offset, "timeout": LONG_POLL_TIMEOUT, "allowed_updates": '["message"]'},
                timeout=LONG_POLL_TIMEOUT + 5,
            )
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            log.warning("getUpdates error: %s — sleeping 5s", e)
            time.sleep(5)
            continue

        if not data.get("ok"):
            log.warning("getUpdates not ok: %s — sleeping 5s", data)
            time.sleep(5)
            continue

        for update in data.get("result", []):
            offset = max(offset, int(update.get("update_id", 0)) + 1)
            msg = update.get("message")
            if msg:
                try:
                    _handle_message(msg)
                except Exception:
                    log.exception("handle_message crashed")
        if data.get("result"):
            _write_offset(offset)


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        log.info("interrupted by user — exiting.")
        sys.exit(0)
