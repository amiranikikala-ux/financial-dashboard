"""MegaPlus daily SQL Server backup ingestion (per-store).

User drops PLUS_<storeID>_MEGA_<YYYYMMDD>.zip files into a per-store watch
folder (e.g. `მეგა პლუს backup` for დვაბზუ 1329, `მეგა პლუს backup ოზურგეთი`
for ოზურგეთი 1301). This module finds the newest ZIP inside each folder,
extracts the .bak, restores it into its own SQL Server Express database
(`MEGAPLUS_<storeID>`), and reads per-supplier rollups.

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

        # ─── By-product (top 500 by revenue) ────────────────────────────────
        cur.execute(
            """
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
            WHERE o.ORD_ACT = 1
            GROUP BY p.P_ID, p.P_CODE, p.P_BARCODE, p.P_NAME, p.P_UNIT, p.P_GROUP,
                     d.DIST_UUID, d.dasaxeleba
            ORDER BY SUM(o.ORD_jamjam) DESC
            """
        )
        by_product = []
        for row in cur.fetchall():
            (pid, code, barcode, name, unit, category, sup_uuid, sup_name,
             qty, rev, cogs_imp, cogs_rec, row_count, min_d, max_d) = row
            rev_f = float(rev or 0)
            cogs_imp_f = float(cogs_imp or 0)
            profit = rev_f - cogs_imp_f
            by_product.append({
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

        # ─── By-month ───────────────────────────────────────────────────────
        cur.execute(
            """
            SELECT
                CAST(YEAR(o.ORD_TIMESTAMP) AS varchar(4)) + '-'
                    + RIGHT('0' + CAST(MONTH(o.ORD_TIMESTAMP) AS varchar(2)), 2) AS month,
                COUNT(*)                                     AS row_count,
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
        for month, row_count, qty, rev, cogs_imp, cogs_rec in cur.fetchall():
            rev_f = float(rev or 0)
            cogs_imp_f = float(cogs_imp or 0)
            profit = rev_f - cogs_imp_f
            by_month.append({
                "month": month,
                "row_count": int(row_count or 0),
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
        "suppliers": sorted(suppliers.values(), key=lambda s: s["lifetime"]["revenue"], reverse=True),
        "by_product": by_product,
        "by_month": by_month,
        "by_category": by_category,
        "by_category_by_month": by_category_by_month,
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
    """Find every `მეგა პლუს backup*` sibling folder under the financial_analysis parent."""
    if not parent.is_dir():
        return []
    return sorted([p for p in parent.glob("მეგა პლუს backup*") if p.is_dir()])


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
