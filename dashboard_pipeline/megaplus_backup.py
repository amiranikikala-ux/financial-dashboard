"""MegaPlus daily SQL Server backup ingestion (per-store).

User drops PLUS_<storeID>_MEGA_<YYYYMMDD>.zip files into a per-store watch
folder. Two layouts are auto-discovered:
  - legacy: `მეგა პლუს backup` (1329), `მეგა პლუს backup ოზურგეთი` (1301)
  - current: `მეგაპლიუსის არქიტექტურა/<store>/` — any subfolder with PLUS_*.zip
This module finds the newest ZIP inside each folder, extracts the .bak,
restores it into its own SQL Server Express database (`MEGAPLUS_<storeID>`),
and reads per-supplier rollups.

State file `_megaplus_state.json` lives next to each watch folder's ZIPs and
remembers which ZIP was last restored — re-runs are no-ops if nothing changed.

CLI:
    python -m dashboard_pipeline.megaplus_backup                     # auto-discover all watch folders
    python -m dashboard_pipeline.megaplus_backup PATH1 PATH2 ...     # explicit folders
    python -m dashboard_pipeline.megaplus_backup ... --force         # ignore state, re-restore

Library:
    from dashboard_pipeline.megaplus_backup import process_all_stores
    combined = process_all_stores([folder1, folder2])  # {"stores": {...}} or None
"""
from __future__ import annotations

import json
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pyodbc  # type: ignore
except ImportError:
    pyodbc = None  # surfaced at call-time, so import never fails

ZIP_PATTERN = re.compile(r"^PLUS_(\d+)_MEGA_(\d{8})\.zip$", re.IGNORECASE)
STATE_FILENAME = "_megaplus_state.json"
LIVE_FILENAME = "_megaplus_live.json"

DEFAULT_INSTANCE = r"localhost\SQLEXPRESS"
DEFAULT_BAK_STAGING = Path(r"C:\Users\tengiz\megaplus_bak_staging")
DEFAULT_DATA_DIR = Path(r"C:\Users\tengiz\sql_data")


def _db_name_for(store_id: str) -> str:
    """Per-store database name so multiple POS backups can co-exist on one SQL instance."""
    return f"MEGAPLUS_{store_id}"


# ─────────────────────────────────────────── helpers ──────────────────────────


@dataclass
class BackupFile:
    path: Path
    store_id: str
    backup_date: str  # YYYY-MM-DD


def _pick_newest_zip(folder: Path) -> BackupFile | None:
    candidates: list[tuple[Path, str, str]] = []
    for entry in folder.iterdir():
        if not entry.is_file():
            continue
        m = ZIP_PATTERN.match(entry.name)
        if not m:
            continue
        ymd = m.group(2)
        iso_date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
        candidates.append((entry, m.group(1), iso_date))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[2], reverse=True)
    p, store_id, iso_date = candidates[0]
    return BackupFile(path=p, store_id=store_id, backup_date=iso_date)


def _read_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(state_path: Path, state: dict) -> None:
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_driver() -> str:
    if pyodbc is None:
        raise RuntimeError("pyodbc not installed")
    for d in pyodbc.drivers():
        if "ODBC Driver 18 for SQL Server" in d:
            return d
    for d in pyodbc.drivers():
        if "ODBC Driver 17 for SQL Server" in d:
            return d
    raise RuntimeError(f"No suitable ODBC Driver found. Available: {pyodbc.drivers()}")


def _connect(database: str, autocommit: bool = False):
    drv = _get_driver()
    extras = ";Encrypt=no" if "18" in drv else ""
    cs = (
        f"DRIVER={{{drv}}};"
        f"SERVER={DEFAULT_INSTANCE};"
        f"DATABASE={database};"
        f"Trusted_Connection=yes"
        f"{extras}"
    )
    return pyodbc.connect(cs, timeout=30, autocommit=autocommit)


# ─────────────────────────────────────────── extract + restore ────────────────


def _extract_bak(zip_path: Path, staging: Path) -> Path:
    staging.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        if len(names) != 1:
            raise RuntimeError(f"expected 1 file inside zip, got {len(names)}: {names}")
        inner = names[0]
        out = staging / inner
        with zf.open(inner) as src, out.open("wb") as dst:
            for chunk in iter(lambda: src.read(1 << 20), b""):
                dst.write(chunk)
    return out


def _restore(bak_path: Path, db_name: str) -> None:
    if not bak_path.exists():
        raise RuntimeError(f"bak file not found: {bak_path}")
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = _connect("master", autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute(f"RESTORE FILELISTONLY FROM DISK = N'{bak_path}'")
        files = []
        cols = [c[0] for c in cur.description]
        for row in cur.fetchall():
            files.append(dict(zip(cols, row)))

        move_parts = []
        for rec in files:
            ext = ".mdf" if rec["Type"] == "D" else ".ldf"
            new_path = DEFAULT_DATA_DIR / f"{db_name}_{rec['LogicalName']}{ext}"
            move_parts.append(f"MOVE N'{rec['LogicalName']}' TO N'{new_path}'")

        # Take the DB offline-then-drop if it exists, so RESTORE WITH REPLACE has no locks
        cur.execute(
            "IF DB_ID(?) IS NOT NULL "
            "BEGIN "
            f"  ALTER DATABASE [{db_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
            f"END",
            db_name,
        )
        while cur.nextset():
            pass

        sql = (
            f"RESTORE DATABASE [{db_name}] FROM DISK = N'{bak_path}' "
            f"WITH {', '.join(move_parts)}, REPLACE, RECOVERY, STATS = 25"
        )
        cur.execute(sql)
        while cur.nextset():
            pass

        cur.execute(f"ALTER DATABASE [{db_name}] SET MULTI_USER")
        while cur.nextset():
            pass
    finally:
        conn.close()


# ─────────────────────────────────────────── analytics ────────────────────────


def _build_cost_lookup_temp_table(cur) -> None:
    """Materialize per-product effective_unit_cost into a temp table (#pec).

    d1ff190 logic ported to SQL: MAX POS operators frequently leave
    ORD_GETPRICE empty or set to a placeholder (e.g. ვასაძის პური bread
    products), producing spurious 70-95% per-store margins. We replace the
    recorded cost with an imputed unit cost computed from the supplier-
    purchase table (GET) — cost_paid / qty_bought. Cap the attribution at
    qty_bought so name-fuzzy multi-supplier matches don't credit one
    supplier with cost on volumes they didn't ship.

    Mathematically: effective_unit_cost = cost_paid / MAX(qty_bought, qty_sold).
    - qty_sold ≤ qty_bought (no cap): cost_paid / qty_bought = imp_unit_cost
    - qty_sold > qty_bought (cap): cost_paid / qty_sold → total imputed cost
      equals the full purchase value (you can't sell more than you bought)
    - No GET data: fall back to recorded ORD_GETPRICE per-unit average

    Materialization avoids re-scanning ORDERS+GET on every aggregation query
    (8 reuses below) — single sequential scan + indexed lookups thereafter.
    """
    cur.execute(
        """
        SELECT
            pst.p_id,
            pst.qty_sold_total,
            COALESCE(pp.qty_bought, 0) AS qty_bought,
            COALESCE(pp.cost_paid, 0)  AS cost_paid,
            CASE
                WHEN pp.qty_bought > 0 AND pp.cost_paid > 0 THEN
                    pp.cost_paid / (CASE
                        WHEN pst.qty_sold_total > pp.qty_bought THEN pst.qty_sold_total
                        ELSE pp.qty_bought
                    END)
                WHEN pst.qty_sold_total > 0 THEN
                    pst.cost_recorded / pst.qty_sold_total
                ELSE 0
            END AS effective_unit_cost
        INTO #pec
        FROM (
            SELECT
                ORD_P_ID AS p_id,
                SUM(ORD_quant) AS qty_sold_total,
                SUM(ORD_GETPRICE * ORD_quant) AS cost_recorded
            FROM ORDERS
            WHERE ORD_ACT = 1
            GROUP BY ORD_P_ID
            HAVING SUM(ORD_quant) > 0
        ) pst
        LEFT JOIN (
            SELECT
                G_P_ID AS p_id,
                SUM(G_QUANT) AS qty_bought,
                SUM(G_PRICE * G_QUANT) AS cost_paid
            FROM GET
            WHERE G_ACT = 1
            GROUP BY G_P_ID
            HAVING SUM(G_QUANT) > 0
        ) pp ON pst.p_id = pp.p_id
        """
    )
    cur.execute("CREATE CLUSTERED INDEX ix_pec_pid ON #pec(p_id)")


def _read_supplier_rollups(backup_meta: BackupFile, db_name: str) -> dict:
    """Per-supplier + per-product + per-month + per-category rollups.

    Cost is imputed from supplier-invoice (GET table) when available — see
    `_build_cost_lookup_temp_table` for the d1ff190 logic. Recorded MAX-POS
    cost is preserved as `cogs_recorded` alongside `cogs` (imputed) for UI
    transparency.
    """
    conn = _connect(db_name, autocommit=False)
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT MIN(ORD_TIMESTAMP), MAX(ORD_TIMESTAMP), COUNT(*) "
            "FROM ORDERS WHERE ORD_ACT = 1"
        )
        min_ts, max_ts, total_rows = cur.fetchone()

        # Materialize per-product effective_unit_cost lookup (#pec). All
        # aggregation queries below join against this temp table for fast
        # cost imputation without re-scanning ORDERS+GET.
        _build_cost_lookup_temp_table(cur)

        # ─── Supplier rollup (lifetime) ──────────────────────────────────────
        cur.execute(
            """
            SELECT
                d.DIST_UUID                                  AS supplier_uuid,
                d.saidentifikacio                            AS tax_id,
                d.dasaxeleba                                 AS supplier_name,
                COUNT(DISTINCT o.ORD_ID)                     AS sale_lines,
                SUM(o.ORD_jamjam)                            AS revenue,
                SUM(o.ORD_quant * pec.effective_unit_cost)   AS cogs_imputed,
                SUM(o.ORD_GETPRICE * o.ORD_quant)            AS cogs_recorded
            FROM ORDERS o
            JOIN PRODUCTS p ON o.ORD_P_ID = p.P_ID
            JOIN DISTRIBUTORS d ON p.P_DAFAULTSUPPLIER = d.DIST_UUID
            LEFT JOIN #pec pec ON p.P_ID = pec.p_id
            WHERE o.ORD_ACT = 1
            GROUP BY d.DIST_UUID, d.saidentifikacio, d.dasaxeleba
            """
        )
        suppliers: dict[str, dict] = {}
        for uuid, tax_id, name, lines, rev, cogs_imp, cogs_rec in cur.fetchall():
            rev_f = float(rev or 0)
            cogs_imp_f = float(cogs_imp or 0)
            profit = rev_f - cogs_imp_f
            suppliers[uuid] = {
                "supplier_uuid": uuid,
                "tax_id": tax_id,
                "name": name,
                "lifetime": {
                    "sale_lines": int(lines or 0),
                    "revenue": rev_f,
                    "cogs": cogs_imp_f,
                    "cogs_recorded": float(cogs_rec or 0),
                    "profit": profit,
                    "margin_pct": (profit / rev_f * 100) if rev_f else None,
                },
            }

        # ─── Supplier rollup (windowed: last 30/90 days) ────────────────────
        anchor = max_ts or datetime.now()
        for window_days, key in ((30, "last_30_days"), (90, "last_90_days")):
            since = anchor - timedelta(days=window_days)
            cur.execute(
                """
                SELECT
                    d.DIST_UUID,
                    SUM(o.ORD_jamjam)                            AS revenue,
                    SUM(o.ORD_quant * pec.effective_unit_cost)   AS cogs_imputed,
                    SUM(o.ORD_GETPRICE * o.ORD_quant)            AS cogs_recorded,
                    COUNT(DISTINCT o.ORD_ID)                     AS sale_lines
                FROM ORDERS o
                JOIN PRODUCTS p ON o.ORD_P_ID = p.P_ID
                JOIN DISTRIBUTORS d ON p.P_DAFAULTSUPPLIER = d.DIST_UUID
                LEFT JOIN #pec pec ON p.P_ID = pec.p_id
                WHERE o.ORD_ACT = 1 AND o.ORD_TIMESTAMP >= ?
                GROUP BY d.DIST_UUID
                """,
                since,
            )
            for uuid, rev, cogs_imp, cogs_rec, lines in cur.fetchall():
                if uuid not in suppliers:
                    continue
                rev_f = float(rev or 0)
                cogs_imp_f = float(cogs_imp or 0)
                profit = rev_f - cogs_imp_f
                suppliers[uuid][key] = {
                    "sale_lines": int(lines or 0),
                    "revenue": rev_f,
                    "cogs": cogs_imp_f,
                    "cogs_recorded": float(cogs_rec or 0),
                    "profit": profit,
                    "margin_pct": (profit / rev_f * 100) if rev_f else None,
                }

        # ─── Portfolio totals ───────────────────────────────────────────────
        cur.execute(
            """
            SELECT
                SUM(o.ORD_jamjam)                            AS revenue,
                SUM(o.ORD_quant * pec.effective_unit_cost)   AS cogs_imputed,
                SUM(o.ORD_GETPRICE * o.ORD_quant)            AS cogs_recorded,
                COUNT(*)                                     AS sale_lines
            FROM ORDERS o
            LEFT JOIN #pec pec ON o.ORD_P_ID = pec.p_id
            WHERE o.ORD_ACT = 1
            """
        )
        rev_t, cogs_imp_t, cogs_rec_t, lines_t = cur.fetchone()
        rev_t_f = float(rev_t or 0)
        cogs_imp_t_f = float(cogs_imp_t or 0)
        profit_t = rev_t_f - cogs_imp_t_f
        totals = {
            "sale_lines": int(lines_t or 0),
            "revenue": rev_t_f,
            "cogs": cogs_imp_t_f,
            "cogs_recorded": float(cogs_rec_t or 0),
            "profit": profit_t,
            "margin_pct": (profit_t / rev_t_f * 100) if rev_t_f else None,
        }

        # ─── By-product, two windows: lifetime + last 365 days ──────────────
        #
        # The 365-day window is what supplier_profitability prefers when
        # matching against RS waybills. Reason: imported_products typically
        # spans Q1 of the current year (3 months), but MegaPlus lifetime
        # spans 24-37 months. Pricing changes (inflation, promotions) over
        # that long window would dilute the per-product margin computation
        # — a supplier shipping at recent (higher) cost would be matched
        # against lifetime-average (lower) retail revenue, yielding a
        # falsely-negative margin. The 365-day window keeps cost↔revenue
        # in the same pricing era.
        windows = (
            ("lifetime", None),
            ("recent", anchor - timedelta(days=365)),
        )
        by_product_buckets: dict[str, list[dict]] = {"lifetime": [], "recent": []}
        for window_name, since in windows:
            if since is None:
                where_clause = "WHERE o.ORD_ACT = 1"
                params: tuple = ()
            else:
                where_clause = "WHERE o.ORD_ACT = 1 AND o.ORD_TIMESTAMP >= ?"
                params = (since,)
            cur.execute(
                f"""
                SELECT TOP 10000
                    p.P_ID                                       AS product_id,
                    p.P_CODE                                     AS product_code,
                    p.P_BARCODE                                  AS barcode,
                    p.P_NAME                                     AS product_name,
                    p.P_UNIT                                     AS unit,
                    p.P_GROUP                                    AS category,
                    d.DIST_UUID                                  AS supplier_uuid,
                    d.dasaxeleba                                 AS supplier_name,
                    SUM(o.ORD_quant)                             AS qty_sold,
                    SUM(o.ORD_jamjam)                            AS revenue,
                    SUM(o.ORD_quant * pec.effective_unit_cost)   AS cogs_imputed,
                    SUM(o.ORD_GETPRICE * o.ORD_quant)            AS cogs_recorded,
                    COUNT(*)                                     AS row_count,
                    MIN(o.ORD_TIMESTAMP)                         AS min_date,
                    MAX(o.ORD_TIMESTAMP)                         AS max_date
                FROM ORDERS o
                JOIN PRODUCTS p ON o.ORD_P_ID = p.P_ID
                LEFT JOIN DISTRIBUTORS d ON p.P_DAFAULTSUPPLIER = d.DIST_UUID
                LEFT JOIN #pec pec ON p.P_ID = pec.p_id
                {where_clause}
                GROUP BY p.P_ID, p.P_CODE, p.P_BARCODE, p.P_NAME, p.P_UNIT, p.P_GROUP,
                         d.DIST_UUID, d.dasaxeleba
                ORDER BY SUM(o.ORD_jamjam) DESC
                """,
                *params,
            )
            for row in cur.fetchall():
                (pid, code, barcode, name, unit, category, sup_uuid, sup_name,
                 qty, rev, cogs_imp, cogs_rec, row_count, min_d, max_d) = row
                rev_f = float(rev or 0)
                cogs_imp_f = float(cogs_imp or 0)
                profit = rev_f - cogs_imp_f
                by_product_buckets[window_name].append({
                    "product_id": int(pid),
                    "product_code": code or "",
                    "barcode": barcode or "",
                    "product_name": name or "",
                    "unit": unit or "",
                    "category": category or "",
                    "supplier_uuid": sup_uuid or "",
                    "supplier_name": sup_name or "",
                    "row_count": int(row_count or 0),
                    "qty_sold": float(qty or 0),
                    "revenue": rev_f,
                    "cogs": cogs_imp_f,
                    "cogs_recorded": float(cogs_rec or 0),
                    "profit": profit,
                    "margin_pct": (profit / rev_f * 100) if rev_f else None,
                    "min_date": min_d.isoformat() if min_d else None,
                    "max_date": max_d.isoformat() if max_d else None,
                })

        by_product = by_product_buckets["lifetime"]
        by_product_recent = by_product_buckets["recent"]

        # ─── By-month ───────────────────────────────────────────────────────
        cur.execute(
            """
            SELECT
                CAST(YEAR(o.ORD_TIMESTAMP) AS varchar(4)) + '-'
                    + RIGHT('0' + CAST(MONTH(o.ORD_TIMESTAMP) AS varchar(2)), 2) AS month,
                COUNT(*)                                     AS row_count,
                COUNT(DISTINCT o.ORD_N)                      AS receipts,
                SUM(o.ORD_quant)                             AS qty_sold,
                SUM(o.ORD_jamjam)                            AS revenue,
                SUM(o.ORD_quant * pec.effective_unit_cost)   AS cogs_imputed,
                SUM(o.ORD_GETPRICE * o.ORD_quant)            AS cogs_recorded
            FROM ORDERS o
            LEFT JOIN #pec pec ON o.ORD_P_ID = pec.p_id
            WHERE o.ORD_ACT = 1
            GROUP BY YEAR(o.ORD_TIMESTAMP), MONTH(o.ORD_TIMESTAMP)
            ORDER BY YEAR(o.ORD_TIMESTAMP), MONTH(o.ORD_TIMESTAMP)
            """
        )
        by_month = []
        for month, row_count, receipts, qty, rev, cogs_imp, cogs_rec in cur.fetchall():
            rev_f = float(rev or 0)
            cogs_imp_f = float(cogs_imp or 0)
            profit = rev_f - cogs_imp_f
            by_month.append({
                "month": month,
                "row_count": int(row_count or 0),
                "receipts": int(receipts or 0),
                "qty_sold": float(qty or 0),
                "revenue": rev_f,
                "cogs": cogs_imp_f,
                "cogs_recorded": float(cogs_rec or 0),
                "profit": profit,
                "margin_pct": (profit / rev_f * 100) if rev_f else None,
            })

        # ─── By-category ────────────────────────────────────────────────────
        cur.execute(
            """
            SELECT
                ISNULL(p.P_GROUP, '(უცნობი)')               AS category,
                COUNT(*)                                     AS row_count,
                COUNT(DISTINCT p.P_ID)                       AS distinct_product_count,
                SUM(o.ORD_quant)                             AS qty_sold,
                SUM(o.ORD_jamjam)                            AS revenue,
                SUM(o.ORD_quant * pec.effective_unit_cost)   AS cogs_imputed,
                SUM(o.ORD_GETPRICE * o.ORD_quant)            AS cogs_recorded
            FROM ORDERS o
            JOIN PRODUCTS p ON o.ORD_P_ID = p.P_ID
            LEFT JOIN #pec pec ON p.P_ID = pec.p_id
            WHERE o.ORD_ACT = 1
            GROUP BY p.P_GROUP
            ORDER BY SUM(o.ORD_jamjam) DESC
            """
        )
        by_category = []
        for cat, row_count, prod_count, qty, rev, cogs_imp, cogs_rec in cur.fetchall():
            rev_f = float(rev or 0)
            cogs_imp_f = float(cogs_imp or 0)
            profit = rev_f - cogs_imp_f
            by_category.append({
                "category": cat or "(უცნობი)",
                "row_count": int(row_count or 0),
                "distinct_product_count": int(prod_count or 0),
                "qty_sold": float(qty or 0),
                "revenue": rev_f,
                "cogs": cogs_imp_f,
                "cogs_recorded": float(cogs_rec or 0),
                "profit": profit,
                "margin_pct": (profit / rev_f * 100) if rev_f else None,
            })

        # ─── By-category-by-month ───────────────────────────────────────────
        cur.execute(
            """
            SELECT
                CAST(YEAR(o.ORD_TIMESTAMP) AS varchar(4)) + '-'
                    + RIGHT('0' + CAST(MONTH(o.ORD_TIMESTAMP) AS varchar(2)), 2) AS month,
                ISNULL(p.P_GROUP, '(უცნობი)')               AS category,
                COUNT(*)                                     AS row_count,
                SUM(o.ORD_quant)                             AS qty_sold,
                SUM(o.ORD_jamjam)                            AS revenue,
                SUM(o.ORD_quant * pec.effective_unit_cost)   AS cogs_imputed,
                SUM(o.ORD_GETPRICE * o.ORD_quant)            AS cogs_recorded
            FROM ORDERS o
            JOIN PRODUCTS p ON o.ORD_P_ID = p.P_ID
            LEFT JOIN #pec pec ON p.P_ID = pec.p_id
            WHERE o.ORD_ACT = 1
            GROUP BY YEAR(o.ORD_TIMESTAMP), MONTH(o.ORD_TIMESTAMP), p.P_GROUP
            ORDER BY YEAR(o.ORD_TIMESTAMP), MONTH(o.ORD_TIMESTAMP), SUM(o.ORD_jamjam) DESC
            """
        )
        by_category_by_month = []
        for month, cat, row_count, qty, rev, cogs_imp, cogs_rec in cur.fetchall():
            rev_f = float(rev or 0)
            cogs_imp_f = float(cogs_imp or 0)
            profit = rev_f - cogs_imp_f
            by_category_by_month.append({
                "month": month,
                "category": cat or "(უცნობი)",
                "row_count": int(row_count or 0),
                "qty_sold": float(qty or 0),
                "revenue": rev_f,
                "cogs": cogs_imp_f,
                "cogs_recorded": float(cogs_rec or 0),
                "profit": profit,
                "margin_pct": (profit / rev_f * 100) if rev_f else None,
            })

        # ─── By-product × month — top 50 per (store, month) ────────────────
        # Lets the UI compute period-scoped top products for any picked
        # month/year by summing rows within the requested date range.
        # Capped at top-50 per month to keep payload bounded (~37 months ×
        # 50 × 2 stores ≈ 3,700 rows per store rollup).
        cur.execute(
            """
            WITH ranked AS (
                SELECT
                    CAST(YEAR(o.ORD_TIMESTAMP) AS varchar(4)) + '-'
                        + RIGHT('0' + CAST(MONTH(o.ORD_TIMESTAMP) AS varchar(2)), 2) AS month,
                    p.P_ID                                       AS product_id,
                    p.P_CODE                                     AS product_code,
                    p.P_BARCODE                                  AS barcode,
                    p.P_NAME                                     AS product_name,
                    p.P_GROUP                                    AS category,
                    SUM(o.ORD_quant)                             AS qty_sold,
                    SUM(o.ORD_jamjam)                            AS revenue,
                    SUM(o.ORD_quant * pec.effective_unit_cost)   AS cogs_imputed,
                    COUNT(*)                                     AS row_count,
                    COUNT(DISTINCT o.ORD_N)                      AS receipts,
                    ROW_NUMBER() OVER (
                        PARTITION BY YEAR(o.ORD_TIMESTAMP), MONTH(o.ORD_TIMESTAMP)
                        ORDER BY SUM(o.ORD_jamjam) DESC
                    ) AS rk
                FROM ORDERS o
                JOIN PRODUCTS p ON o.ORD_P_ID = p.P_ID
                LEFT JOIN #pec pec ON p.P_ID = pec.p_id
                WHERE o.ORD_ACT = 1 AND o.ORD_TIMESTAMP IS NOT NULL
                GROUP BY YEAR(o.ORD_TIMESTAMP), MONTH(o.ORD_TIMESTAMP),
                         p.P_ID, p.P_CODE, p.P_BARCODE, p.P_NAME, p.P_GROUP
            )
            SELECT month, product_id, product_code, barcode, product_name, category,
                   qty_sold, revenue, cogs_imputed, row_count, receipts, rk
            FROM ranked
            WHERE rk <= 50
            ORDER BY month, rk
            """
        )
        by_product_by_month = []
        for row in cur.fetchall():
            (mo, pid, code, barcode, name, category,
             qty, rev, cogs, row_count, receipts, rk) = row
            rev_f = float(rev or 0)
            cogs_f = float(cogs or 0)
            by_product_by_month.append({
                "month": mo,
                "product_id": int(pid),
                "product_code": code or "",
                "barcode": barcode or "",
                "product_name": name or "",
                "category": category or "",
                "qty_sold": float(qty or 0),
                "revenue": rev_f,
                "cogs": cogs_f,
                "profit": rev_f - cogs_f,
                "row_count": int(row_count or 0),
                "receipts": int(receipts or 0),
                "rank_in_month": int(rk),
            })

        # ─── Data-quality flags (no silent gaps) ────────────────────────────
        # Surface rows that would otherwise drop out of by_month: NULL
        # timestamps (no month bucket) and legacy pre-2023 rows (likely test
        # seed data). UI can show these as explicit warnings instead of
        # silently excluding them from time-series aggregations.
        cur.execute(
            """
            SELECT
                COUNT(*)                              AS row_count,
                ISNULL(SUM(o.ORD_jamjam), 0)          AS revenue,
                ISNULL(SUM(o.ORD_quant), 0)           AS qty
            FROM ORDERS o
            WHERE o.ORD_ACT = 1 AND o.ORD_TIMESTAMP IS NULL
            """
        )
        nt_count, nt_rev, nt_qty = cur.fetchone()
        null_timestamp_stats = {
            "row_count": int(nt_count or 0),
            "revenue": float(nt_rev or 0),
            "quantity": float(nt_qty or 0),
        }
        cur.execute(
            """
            SELECT
                COUNT(*)                              AS row_count,
                ISNULL(SUM(o.ORD_jamjam), 0)          AS revenue,
                ISNULL(SUM(o.ORD_quant), 0)           AS qty,
                MIN(o.ORD_TIMESTAMP)                  AS min_ts,
                MAX(o.ORD_TIMESTAMP)                  AS max_ts
            FROM ORDERS o
            WHERE o.ORD_ACT = 1
              AND o.ORD_TIMESTAMP IS NOT NULL
              AND o.ORD_TIMESTAMP < '2023-01-01'
            """
        )
        lg_count, lg_rev, lg_qty, lg_min, lg_max = cur.fetchone()
        legacy_pre_2023_stats = {
            "row_count": int(lg_count or 0),
            "revenue": float(lg_rev or 0),
            "quantity": float(lg_qty or 0),
            "min_timestamp": lg_min.isoformat() if lg_min else None,
            "max_timestamp": lg_max.isoformat() if lg_max else None,
        }

        # ─── Sales analytics: receipt / payment / cashier / time-of-day ─────
        # Lift the depth of the Sales page from "totals + monthly trend" to
        # operational analytics by exposing the columns ORDERS already has.
        # ORD_N groups lines into receipts (ORD_ID is line-level — many lines
        # per receipt share one ORD_N).

        # Receipt-level basket metrics (overall — full lifetime).
        cur.execute(
            """
            SELECT
                COUNT(*)                                   AS lines,
                COUNT(DISTINCT o.ORD_N)                    AS receipts,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue,
                ISNULL(SUM(o.ORD_quant), 0)                AS qty
            FROM ORDERS o
            WHERE o.ORD_ACT = 1
            """
        )
        bm_lines, bm_receipts, bm_rev, bm_qty = cur.fetchone()
        bm_lines = int(bm_lines or 0)
        bm_receipts = int(bm_receipts or 0)
        bm_rev = float(bm_rev or 0)
        bm_qty = float(bm_qty or 0)
        basket_metrics = {
            "lines": bm_lines,
            "receipts": bm_receipts,
            "revenue": bm_rev,
            "quantity": bm_qty,
            "aov": (bm_rev / bm_receipts) if bm_receipts else 0.0,
            "items_per_basket": (bm_lines / bm_receipts) if bm_receipts else 0.0,
            "qty_per_basket": (bm_qty / bm_receipts) if bm_receipts else 0.0,
        }

        # Payment-type breakdown. ORD_PAY_TYP=0 = ნაღდი, =1 = ბარათი
        # (verified by Megaplus operator convention; surfaced in UI).
        cur.execute(
            """
            SELECT
                o.ORD_PAY_TYP                              AS pay_typ,
                COUNT(*)                                   AS lines,
                COUNT(DISTINCT o.ORD_N)                    AS receipts,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue
            FROM ORDERS o
            WHERE o.ORD_ACT = 1
            GROUP BY o.ORD_PAY_TYP
            """
        )
        payment_types = []
        for pt, lines, receipts, rev in cur.fetchall():
            payment_types.append({
                "pay_typ": int(pt) if pt is not None else None,
                "lines": int(lines or 0),
                "receipts": int(receipts or 0),
                "revenue": float(rev or 0),
            })

        # Cashier-level breakdown (top 30 by revenue). STAFF table is empty
        # in this DB so we can only show ORD_USER_ID — UI maps to "მოლარე #N".
        cur.execute(
            """
            SELECT TOP 30
                o.ORD_USER_ID                              AS user_id,
                COUNT(*)                                   AS lines,
                COUNT(DISTINCT o.ORD_N)                    AS receipts,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue,
                MIN(o.ORD_TIMESTAMP)                       AS first_sale,
                MAX(o.ORD_TIMESTAMP)                       AS last_sale
            FROM ORDERS o
            WHERE o.ORD_ACT = 1
            GROUP BY o.ORD_USER_ID
            ORDER BY ISNULL(SUM(o.ORD_jamjam), 0) DESC
            """
        )
        cashiers = []
        for uid, lines, receipts, rev, fs, ls in cur.fetchall():
            cashiers.append({
                "user_id": int(uid) if uid is not None else None,
                "lines": int(lines or 0),
                "receipts": int(receipts or 0),
                "revenue": float(rev or 0),
                "aov": (float(rev or 0) / int(receipts)) if receipts else 0.0,
                "first_sale": fs.isoformat() if fs else None,
                "last_sale": ls.isoformat() if ls else None,
            })

        # Cash-register breakdown (ORD_TAB_ID).
        cur.execute(
            """
            SELECT
                o.ORD_TAB_ID                               AS tab_id,
                COUNT(*)                                   AS lines,
                COUNT(DISTINCT o.ORD_N)                    AS receipts,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue
            FROM ORDERS o
            WHERE o.ORD_ACT = 1
            GROUP BY o.ORD_TAB_ID
            ORDER BY ISNULL(SUM(o.ORD_jamjam), 0) DESC
            """
        )
        registers = []
        for tab, lines, receipts, rev in cur.fetchall():
            registers.append({
                "tab_id": int(tab) if tab is not None else None,
                "lines": int(lines or 0),
                "receipts": int(receipts or 0),
                "revenue": float(rev or 0),
            })

        # Hour-of-day (0-23). NULL timestamps excluded — already counted in
        # null_timestamp_stats; including them would muddy a clear time-of-day
        # signal.
        cur.execute(
            """
            SELECT
                DATEPART(HOUR, o.ORD_TIMESTAMP)            AS hr,
                COUNT(*)                                   AS lines,
                COUNT(DISTINCT o.ORD_N)                    AS receipts,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue
            FROM ORDERS o
            WHERE o.ORD_ACT = 1 AND o.ORD_TIMESTAMP IS NOT NULL
            GROUP BY DATEPART(HOUR, o.ORD_TIMESTAMP)
            ORDER BY 1
            """
        )
        hour_of_day = []
        for hr, lines, receipts, rev in cur.fetchall():
            hour_of_day.append({
                "hour": int(hr) if hr is not None else None,
                "lines": int(lines or 0),
                "receipts": int(receipts or 0),
                "revenue": float(rev or 0),
            })

        # Day-of-week. SET DATEFIRST 1 → Monday=1 .. Sunday=7 (ISO).
        cur.execute("SET DATEFIRST 1")
        cur.execute(
            """
            SELECT
                DATEPART(WEEKDAY, o.ORD_TIMESTAMP)         AS dow,
                COUNT(*)                                   AS lines,
                COUNT(DISTINCT o.ORD_N)                    AS receipts,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue
            FROM ORDERS o
            WHERE o.ORD_ACT = 1 AND o.ORD_TIMESTAMP IS NOT NULL
            GROUP BY DATEPART(WEEKDAY, o.ORD_TIMESTAMP)
            ORDER BY 1
            """
        )
        day_of_week = []
        for dow, lines, receipts, rev in cur.fetchall():
            day_of_week.append({
                "dow": int(dow) if dow is not None else None,
                "lines": int(lines or 0),
                "receipts": int(receipts or 0),
                "revenue": float(rev or 0),
            })

        # Hour × Day-of-week heatmap (7 dow × 24 hour = up to 168 cells).
        # Lets the UI render a single grid showing the busiest weekday-hour
        # combination instead of two separate one-dimensional charts.
        cur.execute(
            """
            SELECT
                DATEPART(WEEKDAY, o.ORD_TIMESTAMP)         AS dow,
                DATEPART(HOUR,    o.ORD_TIMESTAMP)         AS hr,
                COUNT(*)                                   AS lines,
                COUNT(DISTINCT o.ORD_N)                    AS receipts,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue
            FROM ORDERS o
            WHERE o.ORD_ACT = 1 AND o.ORD_TIMESTAMP IS NOT NULL
            GROUP BY DATEPART(WEEKDAY, o.ORD_TIMESTAMP), DATEPART(HOUR, o.ORD_TIMESTAMP)
            ORDER BY 1, 2
            """
        )
        hour_dow_grid = []
        for dow, hr, lines, receipts, rev in cur.fetchall():
            hour_dow_grid.append({
                "dow": int(dow) if dow is not None else None,
                "hour": int(hr) if hr is not None else None,
                "lines": int(lines or 0),
                "receipts": int(receipts or 0),
                "revenue": float(rev or 0),
            })

        # Daily trend — last 365 days only (calendar heatmap + recent trend).
        anchor_dt = max_ts or datetime.now()
        since_365 = anchor_dt - timedelta(days=365)
        cur.execute(
            """
            SELECT
                CAST(o.ORD_TIMESTAMP AS DATE)              AS day,
                COUNT(*)                                   AS lines,
                COUNT(DISTINCT o.ORD_N)                    AS receipts,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue,
                ISNULL(SUM(o.ORD_quant * pec.effective_unit_cost), 0) AS cogs_imputed
            FROM ORDERS o
            LEFT JOIN #pec pec ON o.ORD_P_ID = pec.p_id
            WHERE o.ORD_ACT = 1 AND o.ORD_TIMESTAMP IS NOT NULL AND o.ORD_TIMESTAMP >= ?
            GROUP BY CAST(o.ORD_TIMESTAMP AS DATE)
            ORDER BY 1
            """,
            since_365,
        )
        daily_trend = []
        for day, lines, receipts, rev, cogs in cur.fetchall():
            rev_f = float(rev or 0)
            cogs_f = float(cogs or 0)
            daily_trend.append({
                "day": day.isoformat() if day else None,
                "lines": int(lines or 0),
                "receipts": int(receipts or 0),
                "revenue": rev_f,
                "cogs": cogs_f,
                "profit": rev_f - cogs_f,
            })

        # Returns + voids (ORD_ACT != 1).
        cur.execute(
            """
            SELECT
                o.ORD_ACT                                  AS act,
                COUNT(*)                                   AS lines,
                COUNT(DISTINCT o.ORD_N)                    AS receipts,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue,
                ISNULL(SUM(o.ORD_quant), 0)                AS qty,
                MIN(o.ORD_TIMESTAMP)                       AS first_at,
                MAX(o.ORD_TIMESTAMP)                       AS last_at
            FROM ORDERS o
            WHERE o.ORD_ACT IN (0, 2)
            GROUP BY o.ORD_ACT
            """
        )
        returns_voids = []
        for act, lines, receipts, rev, qty, fa, la in cur.fetchall():
            returns_voids.append({
                "act": int(act) if act is not None else None,
                "kind": "void" if act == 0 else ("return" if act == 2 else "other"),
                "lines": int(lines or 0),
                "receipts": int(receipts or 0),
                "revenue": float(rev or 0),
                "quantity": float(qty or 0),
                "first_at": fa.isoformat() if fa else None,
                "last_at": la.isoformat() if la else None,
            })

        # Discount totals — ORD_FASDAKLEBAMDE > ORD_jamjam means a markdown
        # was applied. ORD_discount also exists but per-line ORD_FASDAKLEBAMDE
        # is the more reliable source.
        cur.execute(
            """
            SELECT
                COUNT(*)                                   AS lines,
                COUNT(DISTINCT o.ORD_N)                    AS receipts,
                ISNULL(SUM(o.ORD_FASDAKLEBAMDE - o.ORD_jamjam), 0) AS markdown_total,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue_after,
                ISNULL(SUM(o.ORD_FASDAKLEBAMDE), 0)        AS revenue_before
            FROM ORDERS o
            WHERE o.ORD_ACT = 1 AND o.ORD_FASDAKLEBAMDE > o.ORD_jamjam
            """
        )
        d_lines, d_receipts, d_total, d_after, d_before = cur.fetchone()
        d_after_f = float(d_after or 0)
        d_before_f = float(d_before or 0)
        discount_totals = {
            "discounted_lines": int(d_lines or 0),
            "discounted_receipts": int(d_receipts or 0),
            "markdown_total": float(d_total or 0),
            "revenue_after_markdown": d_after_f,
            "revenue_before_markdown": d_before_f,
            "markdown_pct": ((d_before_f - d_after_f) / d_before_f * 100) if d_before_f > 0 else 0.0,
        }

        # Per-shift breakdown (cashier session-level analytics).
        # ORD_SHIFT identifies one cashier session on one register (typically
        # a single ~17h day-shift, e.g. 8 AM → 1 AM next morning). One shift =
        # one user_id × one tab_id × one operating window.
        cur.execute(
            """
            SELECT
                o.ORD_SHIFT                                AS shift_id,
                o.ORD_USER_ID                              AS user_id,
                o.ORD_TAB_ID                               AS tab_id,
                MIN(o.ORD_TIMESTAMP)                       AS shift_start,
                MAX(o.ORD_TIMESTAMP)                       AS shift_end,
                COUNT(*)                                   AS lines,
                COUNT(DISTINCT o.ORD_N)                    AS receipts,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue,
                ISNULL(SUM(o.ORD_quant), 0)                AS qty,
                ISNULL(SUM(o.ORD_FASDAKLEBAMDE - o.ORD_jamjam), 0) AS markdown
            FROM ORDERS o
            WHERE o.ORD_ACT = 1 AND o.ORD_SHIFT IS NOT NULL AND o.ORD_TIMESTAMP IS NOT NULL
            GROUP BY o.ORD_SHIFT, o.ORD_USER_ID, o.ORD_TAB_ID
            ORDER BY o.ORD_SHIFT DESC
            """
        )
        # ORD_SHIFT can group lines spanning multiple weeks if the cashier
        # never formally closed a shift. A handful of shifts also happen to
        # match a 2009 legacy timestamp giving impossible 15-year spans. Filter
        # >30h durations into a separate "anomalous" bucket for visibility
        # rather than letting them poison avg / max / duration.
        SHIFT_DURATION_NORMAL_MAX_H = 30.0
        all_shifts = []
        anomalous_shifts = []
        normal_revenues = []
        normal_durations = []
        for row in cur.fetchall():
            sid, uid, tid, ts_start, ts_end, lines, receipts, rev, qty, md = row
            rev_f = float(rev or 0)
            dur_h = 0.0
            if ts_start and ts_end:
                dur_h = max(0.0, (ts_end - ts_start).total_seconds() / 3600.0)
            receipts_i = int(receipts or 0)
            entry = {
                "shift_id": int(sid) if sid is not None else None,
                "user_id": int(uid) if uid is not None else None,
                "tab_id": int(tid) if tid is not None else None,
                "shift_start": ts_start.isoformat() if ts_start else None,
                "shift_end": ts_end.isoformat() if ts_end else None,
                "duration_hours": round(dur_h, 2),
                "lines": int(lines or 0),
                "receipts": receipts_i,
                "revenue": rev_f,
                "quantity": float(qty or 0),
                "markdown": float(md or 0),
                "aov": round(rev_f / receipts_i, 2) if receipts_i else 0.0,
                "is_anomalous": dur_h > SHIFT_DURATION_NORMAL_MAX_H,
            }
            all_shifts.append(entry)
            if dur_h > SHIFT_DURATION_NORMAL_MAX_H:
                anomalous_shifts.append(entry)
            else:
                normal_revenues.append(rev_f)
                if dur_h > 0:
                    normal_durations.append(dur_h)
        # Headline stats over NORMAL shifts only — anomalies are surfaced
        # separately. Total count includes both for transparency.
        if normal_revenues:
            sorted_revs = sorted(normal_revenues)
            median_rev = sorted_revs[len(sorted_revs) // 2]
        else:
            median_rev = 0.0
        shift_summary = {
            "total_shifts": len(all_shifts),
            "normal_shift_count": len(all_shifts) - len(anomalous_shifts),
            "anomalous_shift_count": len(anomalous_shifts),
            "avg_revenue_ge": round(sum(normal_revenues) / len(normal_revenues), 2) if normal_revenues else 0.0,
            "median_revenue_ge": round(median_rev, 2),
            "best_shift_revenue_ge": round(max(normal_revenues), 2) if normal_revenues else 0.0,
            "worst_shift_revenue_ge": round(min(normal_revenues), 2) if normal_revenues else 0.0,
            "avg_duration_hours": round(sum(normal_durations) / len(normal_durations), 2) if normal_durations else 0.0,
            "last_shift_start": all_shifts[0].get("shift_start") if all_shifts else None,
        }
        shifts = all_shifts[:200]
        # Surface up to 10 worst anomalies (longest first) for owner review.
        shift_anomalies = sorted(anomalous_shifts, key=lambda s: -s["duration_hours"])[:10]

        # Per-line VAT (ORD_VAT) — total VAT collected, by month, by category.
        # Effective rate = ORD_VAT / ORD_jamjam. ORD_VAT = 0 indicates a
        # VAT-exempt line (e.g. cigarettes / specific food categories).
        cur.execute(
            """
            SELECT
                ISNULL(SUM(o.ORD_VAT), 0)                  AS vat_total,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue,
                COUNT(*)                                   AS lines,
                SUM(CASE WHEN o.ORD_VAT = 0 THEN 1 ELSE 0 END)         AS exempt_lines,
                ISNULL(SUM(CASE WHEN o.ORD_VAT = 0 THEN o.ORD_jamjam ELSE 0 END), 0) AS exempt_revenue
            FROM ORDERS o
            WHERE o.ORD_ACT = 1
            """
        )
        v_total, v_rev, v_lines, v_exempt_lines, v_exempt_rev = cur.fetchone()
        v_total_f = float(v_total or 0)
        v_rev_f = float(v_rev or 0)
        v_exempt_rev_f = float(v_exempt_rev or 0)
        vat_totals = {
            "vat_collected_ge": v_total_f,
            "revenue_ge": v_rev_f,
            "effective_rate_pct": round(v_total_f / v_rev_f * 100, 2) if v_rev_f else 0.0,
            "lines": int(v_lines or 0),
            "exempt_lines": int(v_exempt_lines or 0),
            "exempt_revenue_ge": v_exempt_rev_f,
            "exempt_share_pct": round(v_exempt_rev_f / v_rev_f * 100, 2) if v_rev_f else 0.0,
        }

        # VAT by month
        cur.execute(
            """
            SELECT
                CAST(YEAR(o.ORD_TIMESTAMP) AS varchar(4)) + '-'
                    + RIGHT('0' + CAST(MONTH(o.ORD_TIMESTAMP) AS varchar(2)), 2) AS month,
                ISNULL(SUM(o.ORD_VAT), 0)                  AS vat_total,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue
            FROM ORDERS o
            WHERE o.ORD_ACT = 1 AND o.ORD_TIMESTAMP IS NOT NULL
            GROUP BY YEAR(o.ORD_TIMESTAMP), MONTH(o.ORD_TIMESTAMP)
            ORDER BY YEAR(o.ORD_TIMESTAMP), MONTH(o.ORD_TIMESTAMP)
            """
        )
        vat_by_month = []
        for month, vat_t, rev in cur.fetchall():
            vat_t_f = float(vat_t or 0)
            rev_f = float(rev or 0)
            vat_by_month.append({
                "month": month,
                "vat_collected": vat_t_f,
                "revenue": rev_f,
                "effective_rate_pct": round(vat_t_f / rev_f * 100, 2) if rev_f else 0.0,
            })

        # VAT by category
        cur.execute(
            """
            SELECT
                ISNULL(p.P_GROUP, '(უცნობი)')              AS category,
                ISNULL(SUM(o.ORD_VAT), 0)                  AS vat_total,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue,
                COUNT(*)                                   AS lines,
                SUM(CASE WHEN o.ORD_VAT = 0 THEN 1 ELSE 0 END) AS exempt_lines
            FROM ORDERS o
            JOIN PRODUCTS p ON o.ORD_P_ID = p.P_ID
            WHERE o.ORD_ACT = 1
            GROUP BY p.P_GROUP
            ORDER BY SUM(o.ORD_VAT) DESC
            """
        )
        vat_by_category = []
        for cat, vat_t, rev, lines, exempt_lines in cur.fetchall():
            vat_t_f = float(vat_t or 0)
            rev_f = float(rev or 0)
            lines_i = int(lines or 0)
            exempt_lines_i = int(exempt_lines or 0)
            vat_by_category.append({
                "category": cat or "(უცნობი)",
                "vat_collected": vat_t_f,
                "revenue": rev_f,
                "effective_rate_pct": round(vat_t_f / rev_f * 100, 2) if rev_f else 0.0,
                "lines": lines_i,
                "exempt_lines": exempt_lines_i,
                "exempt_share_pct": round(exempt_lines_i / lines_i * 100, 2) if lines_i else 0.0,
            })

        # Returns by product (ORD_ACT = 2). Top 30 most-returned SKUs by
        # absolute return revenue. Pairs the existing returns_voids aggregate
        # with line-level product attribution so the UI can show "which SKUs
        # are coming back" rather than only a single total.
        cur.execute(
            """
            SELECT TOP 30
                p.P_ID                                     AS product_id,
                p.P_CODE                                   AS product_code,
                p.P_BARCODE                                AS barcode,
                p.P_NAME                                   AS product_name,
                p.P_GROUP                                  AS category,
                COUNT(*)                                   AS return_lines,
                COUNT(DISTINCT o.ORD_N)                    AS return_receipts,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS return_revenue,
                ISNULL(SUM(o.ORD_quant), 0)                AS return_qty,
                MIN(o.ORD_TIMESTAMP)                       AS first_return,
                MAX(o.ORD_TIMESTAMP)                       AS last_return
            FROM ORDERS o
            JOIN PRODUCTS p ON o.ORD_P_ID = p.P_ID
            WHERE o.ORD_ACT = 2
            GROUP BY p.P_ID, p.P_CODE, p.P_BARCODE, p.P_NAME, p.P_GROUP
            ORDER BY ABS(ISNULL(SUM(o.ORD_jamjam), 0)) DESC
            """
        )
        returns_by_product = []
        for row in cur.fetchall():
            (pid, code, barcode, name, category, lines, receipts,
             rev, qty, first_at, last_at) = row
            returns_by_product.append({
                "product_id": int(pid),
                "product_code": code or "",
                "barcode": barcode or "",
                "product_name": name or "",
                "category": category or "",
                "return_lines": int(lines or 0),
                "return_receipts": int(receipts or 0),
                "return_revenue": float(rev or 0),
                "return_quantity": float(qty or 0),
                "first_return": first_at.isoformat() if first_at else None,
                "last_return": last_at.isoformat() if last_at else None,
            })

        # Returns by cashier — which user accepts most returns + ratio to
        # their lifetime sales. user_id 0 / NULL grouped together as anonymous.
        cur.execute(
            """
            SELECT
                o.ORD_USER_ID                              AS user_id,
                COUNT(*)                                   AS return_lines,
                COUNT(DISTINCT o.ORD_N)                    AS return_receipts,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS return_revenue
            FROM ORDERS o
            WHERE o.ORD_ACT = 2
            GROUP BY o.ORD_USER_ID
            ORDER BY ABS(ISNULL(SUM(o.ORD_jamjam), 0)) DESC
            """
        )
        returns_by_cashier = []
        for uid, lines, receipts, rev in cur.fetchall():
            returns_by_cashier.append({
                "user_id": int(uid) if uid is not None else None,
                "return_lines": int(lines or 0),
                "return_receipts": int(receipts or 0),
                "return_revenue": float(rev or 0),
            })

        # Returns by month — anomaly detection on returns trend.
        cur.execute(
            """
            SELECT
                CAST(YEAR(o.ORD_TIMESTAMP) AS varchar(4)) + '-'
                    + RIGHT('0' + CAST(MONTH(o.ORD_TIMESTAMP) AS varchar(2)), 2) AS month,
                COUNT(*)                                   AS lines,
                COUNT(DISTINCT o.ORD_N)                    AS receipts,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue,
                ISNULL(SUM(o.ORD_quant), 0)                AS qty
            FROM ORDERS o
            WHERE o.ORD_ACT = 2 AND o.ORD_TIMESTAMP IS NOT NULL
            GROUP BY YEAR(o.ORD_TIMESTAMP), MONTH(o.ORD_TIMESTAMP)
            ORDER BY YEAR(o.ORD_TIMESTAMP), MONTH(o.ORD_TIMESTAMP)
            """
        )
        returns_by_month = []
        for month, lines, receipts, rev, qty in cur.fetchall():
            returns_by_month.append({
                "month": month,
                "lines": int(lines or 0),
                "receipts": int(receipts or 0),
                "revenue": float(rev or 0),
                "quantity": float(qty or 0),
            })

        # Discount detail — per-category breakdown of markdowns. Reveals
        # whether markdowns are concentrated in a few categories (= signal
        # of selective promotion) vs spread across all (= signal of broad
        # mark-down policy).
        cur.execute(
            """
            SELECT
                ISNULL(p.P_GROUP, '(უცნობი)')              AS category,
                COUNT(*)                                   AS lines,
                COUNT(DISTINCT o.ORD_N)                    AS receipts,
                ISNULL(SUM(o.ORD_FASDAKLEBAMDE - o.ORD_jamjam), 0) AS markdown,
                ISNULL(SUM(o.ORD_jamjam), 0)               AS revenue_after,
                ISNULL(SUM(o.ORD_FASDAKLEBAMDE), 0)        AS revenue_before,
                ISNULL(SUM(o.ORD_quant * pec.effective_unit_cost), 0) AS cogs_imputed
            FROM ORDERS o
            JOIN PRODUCTS p ON o.ORD_P_ID = p.P_ID
            LEFT JOIN #pec pec ON p.P_ID = pec.p_id
            WHERE o.ORD_ACT = 1 AND o.ORD_FASDAKLEBAMDE > o.ORD_jamjam
            GROUP BY p.P_GROUP
            ORDER BY ISNULL(SUM(o.ORD_FASDAKLEBAMDE - o.ORD_jamjam), 0) DESC
            """
        )
        discount_by_category = []
        for cat, lines, receipts, md, rev_after, rev_before, cogs in cur.fetchall():
            md_f = float(md or 0)
            ra_f = float(rev_after or 0)
            rb_f = float(rev_before or 0)
            cogs_f = float(cogs or 0)
            profit_actual = ra_f - cogs_f
            profit_no_discount = rb_f - cogs_f  # If no markdown was given.
            discount_by_category.append({
                "category": cat or "(უცნობი)",
                "lines": int(lines or 0),
                "receipts": int(receipts or 0),
                "markdown_total": md_f,
                "revenue_after_markdown": ra_f,
                "revenue_before_markdown": rb_f,
                "cost": cogs_f,
                "profit_actual": profit_actual,
                "profit_if_no_discount": profit_no_discount,
                "lift_lost_ge": md_f,  # = revenue_before − revenue_after, by definition
                "markdown_pct": round((rb_f - ra_f) / rb_f * 100, 2) if rb_f else 0.0,
            })

        # ─── Dead stock — per-SKU inventory snapshot with last-sale aging ────
        # PRODUCTS.P_QUANT is the per-store stock snapshot (decimal). LEFT JOIN
        # to ORDERS yields last_sale_date (NULL = never sold). Bucket logic in
        # Python — 4 dead/slow buckets + 2 special panels (free-stock and
        # negative-stock are surfaced separately so they don't pollute totals).
        # Snapshot anchor = max_ts (latest sale in DB) for consistency with the
        # daily_trend anchor used elsewhere in this rollup.
        cur.execute(
            """
            WITH last_sale AS (
                SELECT ORD_P_ID, MAX(ORD_TIMESTAMP) AS last_sale_ts
                FROM ORDERS
                WHERE ORD_ACT = 1 AND ORD_TIMESTAMP IS NOT NULL
                GROUP BY ORD_P_ID
            )
            SELECT
                p.P_ID, p.P_CODE, p.P_BARCODE, p.P_NAME, p.P_GROUP,
                p.P_QUANT, p.P_GETPRICE, p.P_PRICE, p.P_ACTIVE,
                ls.last_sale_ts
            FROM PRODUCTS p
            LEFT JOIN last_sale ls ON ls.ORD_P_ID = p.P_ID
            WHERE p.P_QUANT <> 0
            """
        )
        ds_anchor = max_ts or datetime.now()
        ds_buckets: dict[str, list[dict]] = {
            "dead_365d_plus": [],
            "dead_180_365d": [],
            "slow_90_180d": [],
            "active_under_90d": [],
            "free_stock": [],
            "negative_stock": [],
        }
        for pid, code, barcode, name, group, qty, getprice, sellprice, active, last_sale_ts in cur.fetchall():
            qty_f = float(qty or 0)
            getprice_f = float(getprice or 0)
            sellprice_f = float(sellprice or 0)
            stock_value = qty_f * getprice_f
            days_since_sale = (ds_anchor - last_sale_ts).days if last_sale_ts else None
            item = {
                "product_id": int(pid),
                "product_code": code or "",
                "barcode": barcode or "",
                "product_name": name or "",
                "category": group or "(უცნობი)",
                "qty": qty_f,
                "getprice": getprice_f,
                "sellprice": sellprice_f,
                "stock_value": stock_value,
                "active": int(active or 0),
                "last_sale_date": last_sale_ts.isoformat() if last_sale_ts else None,
                "days_since_sale": days_since_sale,
            }
            if qty_f < 0:
                ds_buckets["negative_stock"].append(item)
            elif sellprice_f == 0:
                ds_buckets["free_stock"].append(item)
            elif days_since_sale is None or days_since_sale >= 365:
                ds_buckets["dead_365d_plus"].append(item)
            elif days_since_sale >= 180:
                ds_buckets["dead_180_365d"].append(item)
            elif days_since_sale >= 90:
                ds_buckets["slow_90_180d"].append(item)
            else:
                ds_buckets["active_under_90d"].append(item)

        def _ds_summarize(items: list[dict], top_n: int = 50) -> dict:
            items_sorted = sorted(items, key=lambda x: x["stock_value"], reverse=True)
            return {
                "count": len(items),
                "stock_value": sum(it["stock_value"] for it in items),
                "never_sold_count": sum(1 for it in items if it["last_sale_date"] is None),
                "top_items": items_sorted[:top_n],
            }

        ds_total_positive = sum(
            it["stock_value"]
            for key in ("dead_365d_plus", "dead_180_365d", "slow_90_180d", "active_under_90d", "free_stock")
            for it in ds_buckets[key]
        )
        ds_dead_value = sum(
            it["stock_value"]
            for key in ("dead_365d_plus", "dead_180_365d", "slow_90_180d")
            for it in ds_buckets[key]
        )
        ds_neg = ds_buckets["negative_stock"]
        negative_stock_alert = {
            "count": len(ds_neg),
            "abs_value_total": sum(abs(it["stock_value"]) for it in ds_neg),
            "min_qty": min((it["qty"] for it in ds_neg), default=0.0),
            "top_items": sorted(ds_neg, key=lambda x: abs(x["stock_value"]), reverse=True)[:50],
        }
        dead_stock_summary = {
            "snapshot_date": ds_anchor.isoformat(),
            "total_stock_value": ds_total_positive,
            "dead_stock_value": ds_dead_value,
            "dead_stock_pct": (ds_dead_value / ds_total_positive * 100) if ds_total_positive else 0.0,
            "buckets": {
                "dead_365d_plus": _ds_summarize(ds_buckets["dead_365d_plus"]),
                "dead_180_365d":  _ds_summarize(ds_buckets["dead_180_365d"]),
                "slow_90_180d":   _ds_summarize(ds_buckets["slow_90_180d"]),
                "active_under_90d": {
                    "count": len(ds_buckets["active_under_90d"]),
                    "stock_value": sum(it["stock_value"] for it in ds_buckets["active_under_90d"]),
                    "never_sold_count": sum(1 for it in ds_buckets["active_under_90d"] if it["last_sale_date"] is None),
                },
                "free_stock": _ds_summarize(ds_buckets["free_stock"]),
            },
            "negative_stock_alert": negative_stock_alert,
        }

        # Operator-error detection on PRODUCTS table — empty / duplicate-variant
        # / PROTECTED-supplier review. Built on the same connection so it
        # joins the per-store snapshot the rest of this rollup is reading.
        from dashboard_pipeline.category_anomalies import build_anomaly_bundle
        anomaly_bundle = build_anomaly_bundle(cur, backup_meta.store_id)

        # Waybill data for rs.ge ↔ MegaPlus reconciliation. Cached here so the
        # central pipeline can match without re-querying SQL on every run.
        from dashboard_pipeline.waybill_reconciliation import fetch_megaplus_waybill_data
        waybill_data = fetch_megaplus_waybill_data(cur, backup_meta.store_id)
    finally:
        conn.close()

    return {
        "store_id": backup_meta.store_id,
        "backup_date": backup_meta.backup_date,
        "source_zip": backup_meta.path.name,
        "data_range": {
            "min_timestamp": min_ts.isoformat() if min_ts else None,
            "max_timestamp": max_ts.isoformat() if max_ts else None,
            "total_active_orders": int(total_rows or 0),
        },
        "totals": totals,
        "data_quality": {
            "null_timestamp": null_timestamp_stats,
            "legacy_pre_2023": legacy_pre_2023_stats,
        },
        "basket_metrics": basket_metrics,
        "payment_types": payment_types,
        "cashiers": cashiers,
        "registers": registers,
        "hour_of_day": hour_of_day,
        "day_of_week": day_of_week,
        "hour_dow_grid": hour_dow_grid,
        "daily_trend": daily_trend,
        "returns_voids": returns_voids,
        "discount_totals": discount_totals,
        "shifts": shifts,
        "shift_summary": shift_summary,
        "shift_anomalies": shift_anomalies,
        "vat_totals": vat_totals,
        "vat_by_month": vat_by_month,
        "vat_by_category": vat_by_category,
        "returns_by_product": returns_by_product,
        "returns_by_cashier": returns_by_cashier,
        "returns_by_month": returns_by_month,
        "discount_by_category": discount_by_category,
        "suppliers": sorted(suppliers.values(), key=lambda s: s["lifetime"]["revenue"], reverse=True),
        "by_product": by_product,
        "by_product_recent": by_product_recent,
        "by_month": by_month,
        "by_category": by_category,
        "by_category_by_month": by_category_by_month,
        "by_product_by_month": by_product_by_month,
        "dead_stock_summary": dead_stock_summary,
        "category_anomalies": anomaly_bundle,
        "waybill_data": waybill_data,
    }


# ─────────────────────────────────────────── orchestration ────────────────────


def process_newest_backup(folder: Path, force: bool = False) -> dict | None:
    """Find newest PLUS_*.zip, restore + read if newer than last run.

    Returns the per-supplier rollup dict (with embedded `store_id`), or None if
    nothing new. Each store gets its own SQL database `MEGAPLUS_<store_id>` so
    multiple POS backups can co-exist on a single SQL Express instance.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise RuntimeError(f"watch folder does not exist: {folder}")

    pick = _pick_newest_zip(folder)
    if pick is None:
        return None

    state_path = folder / STATE_FILENAME
    state = _read_state(state_path)

    if not force and state.get("last_processed_zip") == pick.path.name:
        return None  # already processed

    db_name = _db_name_for(pick.store_id)
    bak = _extract_bak(pick.path, DEFAULT_BAK_STAGING)
    _restore(bak, db_name)
    rollup = _read_supplier_rollups(pick, db_name)

    state["last_processed_zip"] = pick.path.name
    state["last_processed_at"] = datetime.now().isoformat()
    state["last_backup_date"] = pick.backup_date
    state["database"] = db_name
    _write_state(state_path, state)

    # Persist the per-store rollup so downstream consumers (dashboard pipeline,
    # debug tools) keep seeing this store's data even when no new ZIP triggers
    # a re-restore on subsequent pipeline runs.
    live_path = folder / LIVE_FILENAME
    live_path.write_text(json.dumps(rollup, ensure_ascii=False, indent=2), encoding="utf-8")

    return rollup


def read_combined_rollup(folders: list[Path]) -> dict | None:
    """Build a combined `{"stores": {store_id: rollup}}` dict from each folder's
    cached `_megaplus_live.json`. Returns None if no cached rollups exist.

    This is the persistent path the pipeline uses on every run — the SQL restore
    only fires when a new ZIP arrives, but the cached rollup keeps data.json
    populated in-between.
    """
    stores: dict[str, dict] = {}
    for folder in folders:
        live = Path(folder) / LIVE_FILENAME
        if not live.exists():
            continue
        try:
            rollup = json.loads(live.read_text(encoding="utf-8"))
        except Exception:
            continue
        store_id = str(rollup.get("store_id") or "")
        if store_id:
            stores[store_id] = rollup
    if not stores:
        return None
    return {"stores": stores}


def process_all_stores(folders: list[Path], force: bool = False) -> dict | None:
    """Process every watch folder; return combined rollup keyed by store_id.

    Returns None if no folder produced new data. Folders that yield None (already
    processed or empty) are skipped silently.
    """
    stores: dict[str, dict] = {}
    for folder in folders:
        rollup = process_newest_backup(Path(folder), force=force)
        if rollup is None:
            continue
        store_id = str(rollup.get("store_id"))
        if not store_id:
            continue
        stores[store_id] = rollup
    if not stores:
        return None
    return {"stores": stores}


# ─────────────────────────────────────────── CLI ──────────────────────────────


def _discover_watch_folders(parent: Path) -> list[Path]:
    """Find watch folders containing PLUS_*.zip under the financial_analysis parent.

    Two layouts supported:
      - legacy `მეგა პლუს backup*` siblings
      - `მეგაპლიუსის არქიტექტურა/<store>/` subfolders that hold PLUS_*.zip
    """
    if not parent.is_dir():
        return []
    folders: list[Path] = [p for p in parent.glob("მეგა პლუს backup*") if p.is_dir()]
    arch = parent / "მეგაპლიუსის არქიტექტურა"
    if arch.is_dir():
        for sub in arch.iterdir():
            if not sub.is_dir():
                continue
            if any(ZIP_PATTERN.match(f.name) for f in sub.iterdir() if f.is_file()):
                folders.append(sub)
    return sorted(folders)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    force = "--force" in argv

    if args:
        folders = [Path(a) for a in args]
    else:
        fa_parent = Path(r"C:\financial-dashboard\Financial_Analysis")
        folders = _discover_watch_folders(fa_parent)
        if not folders:
            print(f"no watch folders found under {fa_parent}")
            return 1

    print(f"watching {len(folders)} folder(s):")
    for f in folders:
        print(f"  - {f}")

    combined = process_all_stores(folders, force=force)
    if combined is None:
        print("no new backups to process across any store")
        return 0

    summary = {"stores": {}}
    for store_id, rollup in combined["stores"].items():
        # process_newest_backup already wrote `_megaplus_live.json` next to each
        # watch folder; CLI just prints a confirmation summary.
        print(f"store {store_id} rollup persisted (suppliers={len(rollup['suppliers'])})")

        summary["stores"][store_id] = {
            "store_id": rollup["store_id"],
            "backup_date": rollup["backup_date"],
            "supplier_count": len(rollup["suppliers"]),
            "totals": rollup["totals"],
            "data_range": rollup["data_range"],
            "top_suppliers": [
                {
                    "name": s["name"],
                    "tax_id": s["tax_id"],
                    "lifetime_revenue": s["lifetime"]["revenue"],
                    "lifetime_margin_pct": s["lifetime"]["margin_pct"],
                }
                for s in rollup["suppliers"][:15]
            ],
        }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
