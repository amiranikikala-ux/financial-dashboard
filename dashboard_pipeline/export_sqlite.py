"""
data.json → data.db (SQLite) ექსპორტი.

რატომ გვჭირდება:
    132 MB data.json-ში ad-hoc კითხვები (Python sub-script-ების გამოძახება)
    ნელია და ბევრ token-ს ხარჯავს. SQLite ფაილი + Claude-ის SQLite MCP
    server საშუალებას იძლევა იმავე კითხვებზე SQL-ის ერთი ხაზით პასუხი
    გავცე millisecond-ებში.

რა ცხრილებს ვაშენებთ:
    suppliers              — data.suppliers ფლეტი
    supplier_aging         — data.supplier_aging
    monthly_pnl            — data.monthly_pnl (one row per month)
    retail_sales_category  — data.retail_sales.by_category
    imported_suppliers     — data.imported_products.suppliers (cross-check)
    iban_taxid_conflicts   — data.meta.iban_taxid_conflicts (audit signal)
    meta_kv                — data.meta scalar fields (key-value)

ცხრილი იქმნება საფეხურეობრივად: წაშლა + ახალი ჩასმა (idempotent).
ფაილი: rs-dashboard/public/data.db (data.json-ის გვერდით; gitignore-ში).
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Iterable

from dashboard_pipeline.logging_config import get_logger

logger = get_logger(__name__)


def _coerce(value: Any) -> Any:
    """SQLite-მ რთული ობიექტები ვერ ინახავს — list/dict-ი JSON-ად ვწეროთ."""
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    return json.dumps(value, ensure_ascii=False)


def _flat_rows(items: Iterable[dict]) -> tuple[list[str], list[tuple]]:
    """Returns (columns, rows) where columns = union of all keys (sorted)."""
    items = list(items or [])
    if not items:
        return [], []
    keys: set[str] = set()
    for r in items:
        if isinstance(r, dict):
            keys.update(r.keys())
    cols = sorted(keys)
    rows = []
    for r in items:
        if not isinstance(r, dict):
            continue
        rows.append(tuple(_coerce(r.get(c)) for c in cols))
    return cols, rows


def _create_table(con: sqlite3.Connection, name: str, cols: list[str]) -> None:
    con.execute(f"DROP TABLE IF EXISTS \"{name}\"")
    if not cols:
        con.execute(f"CREATE TABLE \"{name}\" (_empty TEXT)")
        return
    col_sql = ", ".join(f'"{c}"' for c in cols)
    con.execute(f"CREATE TABLE \"{name}\" ({col_sql})")


def _insert_rows(
    con: sqlite3.Connection, name: str, cols: list[str], rows: list[tuple]
) -> None:
    if not cols or not rows:
        return
    placeholders = ", ".join(["?"] * len(cols))
    col_sql = ", ".join(f'"{c}"' for c in cols)
    con.executemany(
        f"INSERT INTO \"{name}\" ({col_sql}) VALUES ({placeholders})",
        rows,
    )


def export_data_json_to_sqlite(data_json_path: str, db_path: str) -> dict:
    """Read data.json from path, write a fresh SQLite db to db_path."""
    if not os.path.exists(data_json_path):
        logger.warning("data.json ვერ ვიპოვე: %s — SQLite ექსპორტი გამოტოვდა", data_json_path)
        return {"status": "skipped", "reason": "data.json missing"}

    with open(data_json_path, encoding="utf-8") as f:
        data = json.load(f)

    # ფაილი ცარიელად შევქმნათ + WAL ჟურნალი (concurrent read)
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError as exc:
            logger.warning("ძველი data.db ვერ წაიშალა: %s", exc)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")

    table_specs: list[tuple[str, list]] = [
        ("suppliers", data.get("suppliers") or []),
        ("supplier_aging", data.get("supplier_aging") or []),
        ("monthly_pnl", data.get("monthly_pnl") or []),
        ("ap_monthly_trend", data.get("ap_monthly_trend") or []),
        (
            "retail_sales_category",
            (data.get("retail_sales") or {}).get("by_category") or [],
        ),
        (
            "retail_sales_top_products",
            (data.get("retail_sales") or {}).get("top_products") or [],
        ),
        (
            "imported_suppliers",
            (data.get("imported_products") or {}).get("suppliers") or [],
        ),
        (
            "imported_products_top",
            (data.get("imported_products") or {}).get("products") or [],
        ),
        (
            "iban_taxid_conflicts",
            (data.get("meta") or {}).get("iban_taxid_conflicts") or [],
        ),
    ]

    counts: dict[str, int] = {}
    for name, items in table_specs:
        cols, rows = _flat_rows(items)
        _create_table(con, name, cols)
        _insert_rows(con, name, cols, rows)
        counts[name] = len(rows)

    # meta_kv: scalar/short fields ცალცალკე row-ით
    meta = data.get("meta") or {}
    meta_rows: list[tuple] = []
    for k, v in meta.items():
        if isinstance(v, (int, float, str, bool)) or v is None:
            meta_rows.append((str(k), _coerce(v)))
    con.execute("DROP TABLE IF EXISTS meta_kv")
    con.execute("CREATE TABLE meta_kv (key TEXT PRIMARY KEY, value TEXT)")
    if meta_rows:
        con.executemany("INSERT INTO meta_kv (key, value) VALUES (?, ?)", meta_rows)
    counts["meta_kv"] = len(meta_rows)

    # _info ცხრილი — ცოდნა, როდის გენერირდა
    con.execute("DROP TABLE IF EXISTS _info")
    con.execute("CREATE TABLE _info (key TEXT PRIMARY KEY, value TEXT)")
    info_rows = [
        ("generated_at", str(data.get("generated_at") or "")),
        ("source", "data.json export by dashboard_pipeline.export_sqlite"),
        ("data_json_size_bytes", str(os.path.getsize(data_json_path))),
    ]
    con.executemany("INSERT INTO _info (key, value) VALUES (?, ?)", info_rows)

    con.commit()
    con.close()

    logger.info(
        "SQLite ექსპორტი → %s · %s",
        db_path,
        ", ".join(f"{n}={c}" for n, c in counts.items()),
    )
    return {"status": "ok", "db_path": db_path, "counts": counts}
