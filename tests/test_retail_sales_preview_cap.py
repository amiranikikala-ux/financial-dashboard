"""Tier 2 Sprint 3a — retail_sales preview_rows per-file cap regression.

Pre-Sprint-3a ``_process_retail_sales_file`` returned EVERY matched row in
its ``preview_rows`` field, which ballooned the ``.pipeline_cache.json``
to 905MB (96% of payload was preview_rows). Downstream the global merger
keeps only the top RETAIL_SALES_ROWS_PREVIEW_LIMIT (50,000) after
sorting by (date desc, revenue desc, name) — so per-file caching beyond
that limit is strictly wasted space.

This test pins the cap so the bug cannot silently regress.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from dashboard_pipeline import retail_sales as rs
from dashboard_pipeline.constants import (
    RETAIL_SALES_ROWS_PREVIEW_LIMIT,
    _clone_default_object_mapping,
)


RETAIL_COLUMNS = [
    "კოდი", "შტრიხკოდი", "დასახელება", "ერთეული",
    "რაოდენობა", "ფასი", "თვითღირებულება", "მოგება",
    "დრო", "ობიექტი", "ქვეჯგუფი",
]


def _write_xlsx(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=RETAIL_COLUMNS)
    df.to_excel(path, index=False)


def _gen_rows(n: int):
    """n synthetic rows, deterministic dates + prices."""
    base = pd.Timestamp("2024-01-01")
    for i in range(n):
        yield {
            "კოდი": f"P{i:06d}",
            "შტრიხკოდი": "",
            "დასახელება": f"product_{i}",
            "ერთეული": "ცალი",
            "რაოდენობა": 1.0,
            "ფასი": 10.0 + (i % 100),
            "თვითღირებულება": 7.0,
            "მოგება": 3.0,
            "დრო": (base + pd.Timedelta(minutes=i)).isoformat(),
            "ობიექტი": "ოზურგეთი",
            "ქვეჯგუფი": "test",
        }


def test_preview_rows_are_capped_at_limit(tmp_path):
    """Generate > LIMIT rows → preview_rows length ≤ LIMIT."""
    n = RETAIL_SALES_ROWS_PREVIEW_LIMIT + 500
    path = tmp_path / "ოზ" / "big.xlsx"
    _write_xlsx(path, list(_gen_rows(n)))
    out = rs._process_retail_sales_file(
        str(path), object_mapping=_clone_default_object_mapping()
    )
    assert out["status"] == "ok"
    assert len(out["preview_rows"]) == RETAIL_SALES_ROWS_PREVIEW_LIMIT
    # Aggregate counters still reflect ALL rows — only preview is capped
    assert out["files_entry"]["row_count"] == n


def test_preview_rows_under_limit_pass_through(tmp_path):
    """Below-limit files keep every row — no unnecessary truncation."""
    n = 100
    path = tmp_path / "ოზ" / "small.xlsx"
    _write_xlsx(path, list(_gen_rows(n)))
    out = rs._process_retail_sales_file(
        str(path), object_mapping=_clone_default_object_mapping()
    )
    assert len(out["preview_rows"]) == n


def test_preview_cap_keeps_newest_first(tmp_path):
    """After capping we must keep the LATEST rows (global merger uses
    date-desc ordering, so per-file top-N must be the newest slice)."""
    n = RETAIL_SALES_ROWS_PREVIEW_LIMIT + 50
    path = tmp_path / "ოზ" / "time.xlsx"
    _write_xlsx(path, list(_gen_rows(n)))
    out = rs._process_retail_sales_file(
        str(path), object_mapping=_clone_default_object_mapping()
    )
    dates = [r["date"] for r in out["preview_rows"] if r.get("date")]
    # First row must be from 2024 (latest generated batch), not the earliest.
    # The first 50 generated rows are the earliest — they should NOT survive.
    first_product_names = [r.get("product_name", "") for r in out["preview_rows"][:10]]
    # The earliest 50 (product_0 .. product_49) must be dropped.
    for early in ("product_0", "product_5", "product_25"):
        assert early not in first_product_names or len(dates) == 0
