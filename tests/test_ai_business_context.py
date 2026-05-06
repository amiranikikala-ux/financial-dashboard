"""Owner business context wire-up — MY_BUSINESS.md → system prompt.

Pins the contract that ``build_system_prompt()`` includes the owner's
strategic answers (``Financial_Analysis/MY_BUSINESS.md``) inside the
cached system prompt, so AI replies stay grounded in the owner's
reality instead of generic textbook KPI advice.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dashboard_pipeline.ai import business_context as bc
from dashboard_pipeline.ai.prompts import (
    build_system_prompt,
    build_system_prompt_blocks,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    bc.reload_business_context()
    yield
    bc.reload_business_context()


def test_business_context_path_points_to_financial_analysis():
    path = bc.get_business_context_path()
    assert path.name == "MY_BUSINESS.md"
    assert path.parent.name == "Financial_Analysis"


def test_load_business_context_reads_real_file():
    text = bc.load_business_context()
    assert text is not None
    assert "შპს ჯეო ფუდთაიმი" in text or "ბიზნეს კონტექსტი" in text


def test_load_business_context_returns_none_for_missing_file(tmp_path, monkeypatch):
    fake_path = tmp_path / "missing.md"
    monkeypatch.setattr(bc, "_BUSINESS_CONTEXT_PATH", fake_path)
    bc.reload_business_context()
    assert bc.load_business_context() is None


def test_load_business_context_returns_none_for_empty_file(tmp_path, monkeypatch):
    empty = tmp_path / "empty.md"
    empty.write_text("   \n  \n", encoding="utf-8")
    monkeypatch.setattr(bc, "_BUSINESS_CONTEXT_PATH", empty)
    bc.reload_business_context()
    assert bc.load_business_context() is None


def test_load_business_context_picks_up_edits_via_mtime(tmp_path, monkeypatch):
    import os
    import time

    file = tmp_path / "ctx.md"
    file.write_text("first", encoding="utf-8")
    monkeypatch.setattr(bc, "_BUSINESS_CONTEXT_PATH", file)
    bc.reload_business_context()
    assert bc.load_business_context() == "first"

    time.sleep(0.05)
    new_mtime = time.time()
    file.write_text("second", encoding="utf-8")
    os.utime(file, (new_mtime, new_mtime))
    assert bc.load_business_context() == "second"


def test_system_prompt_includes_business_context_heading():
    prompt = build_system_prompt()
    assert "📋 ბიზნესის კონტექსტი" in prompt


def test_system_prompt_includes_owner_answers():
    prompt = build_system_prompt()
    assert "შპს ჯეო ფუდთაიმი" in prompt or "მფლობელი თვითონ წყვეტს" in prompt


def test_business_context_appears_before_extra_context():
    prompt = build_system_prompt(extra_context="data period: 2026-01..2026-05")
    business_idx = prompt.index("ბიზნესის კონტექსტი")
    extra_idx = prompt.index("დამატებითი კონტექსტი")
    assert business_idx < extra_idx


def test_business_context_inside_cached_block_not_today_block():
    blocks = build_system_prompt_blocks(today_block="დღევანდელი snapshot")
    assert len(blocks) == 2
    cached_text = blocks[0]["text"]
    today_text = blocks[1]["text"]
    assert "ბიზნესის კონტექსტი" in cached_text
    assert "ბიზნესის კონტექსტი" not in today_text
    assert blocks[0].get("cache_control") == {"type": "ephemeral"}


def test_missing_my_business_file_does_not_break_prompt(tmp_path, monkeypatch):
    fake_path = tmp_path / "absent.md"
    monkeypatch.setattr(bc, "_BUSINESS_CONTEXT_PATH", fake_path)
    bc.reload_business_context()

    prompt = build_system_prompt()
    assert "ბიზნესის კონტექსტი" not in prompt
    assert "სტრატეგიული ფინანსური პარტნიორი" in prompt


def test_investigator_mode_also_includes_business_context():
    prompt = build_system_prompt(mode="investigate")
    assert "ბიზნესის კონტექსტი" in prompt
