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


def _read_supplier_rollups(backup_meta: BackupFile, db_name: str) -> dict:
    """Per-supplier revenue/cost/profit/margin across multiple time windows."""
    conn = _connect(db_name, autocommit=False)
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT MIN(ORD_TIMESTAMP), MAX(ORD_TIMESTAMP), COUNT(*) "
            "FROM ORDERS WHERE ORD_ACT = 1"
        )
        min_ts, max_ts, total_rows = cur.fetchone()

        # Lifetime per-supplier
        cur.execute(
            """
            SELECT
                d.DIST_UUID                                  AS supplier_uuid,
                d.saidentifikacio                            AS tax_id,
                d.dasaxeleba                                 AS supplier_name,
                COUNT(DISTINCT o.ORD_ID)                     AS sale_lines,
                SUM(o.ORD_jamjam)                            AS revenue,
                SUM(o.ORD_GETPRICE * o.ORD_quant)            AS cogs,
                SUM(o.ORD_jamjam) - SUM(o.ORD_GETPRICE * o.ORD_quant) AS profit
            FROM ORDERS o
            JOIN PRODUCTS p ON o.ORD_P_ID = p.P_ID
            JOIN DISTRIBUTORS d ON p.P_DAFAULTSUPPLIER = d.DIST_UUID
            WHERE o.ORD_ACT = 1
            GROUP BY d.DIST_UUID, d.saidentifikacio, d.dasaxeleba
            """
        )
        suppliers: dict[str, dict] = {}
        for uuid, tax_id, name, lines, rev, cogs, profit in cur.fetchall():
            suppliers[uuid] = {
                "supplier_uuid": uuid,
                "tax_id": tax_id,
                "name": name,
                "lifetime": {
                    "sale_lines": int(lines or 0),
                    "revenue": float(rev or 0),
                    "cogs": float(cogs or 0),
                    "profit": float(profit or 0),
                    "margin_pct": (float(profit or 0) / float(rev) * 100) if rev else None,
                },
            }

        # Windowed: last 30 + 90 days, anchored to MAX(ORD_TIMESTAMP) so missing-day backups still work
        anchor = max_ts or datetime.now()
        for window_days, key in ((30, "last_30_days"), (90, "last_90_days")):
            since = anchor - timedelta(days=window_days)
            cur.execute(
                """
                SELECT
                    d.DIST_UUID,
                    SUM(o.ORD_jamjam)                            AS revenue,
                    SUM(o.ORD_GETPRICE * o.ORD_quant)            AS cogs,
                    SUM(o.ORD_jamjam) - SUM(o.ORD_GETPRICE * o.ORD_quant) AS profit,
                    COUNT(DISTINCT o.ORD_ID)                     AS sale_lines
                FROM ORDERS o
                JOIN PRODUCTS p ON o.ORD_P_ID = p.P_ID
                JOIN DISTRIBUTORS d ON p.P_DAFAULTSUPPLIER = d.DIST_UUID
                WHERE o.ORD_ACT = 1 AND o.ORD_TIMESTAMP >= ?
                GROUP BY d.DIST_UUID
                """,
                since,
            )
            for uuid, rev, cogs, profit, lines in cur.fetchall():
                if uuid in suppliers:
                    suppliers[uuid][key] = {
                        "sale_lines": int(lines or 0),
                        "revenue": float(rev or 0),
                        "cogs": float(cogs or 0),
                        "profit": float(profit or 0),
                        "margin_pct": (float(profit or 0) / float(rev) * 100) if rev else None,
                    }

        # Portfolio totals
        cur.execute(
            "SELECT SUM(ORD_jamjam), SUM(ORD_GETPRICE * ORD_quant), COUNT(*) "
            "FROM ORDERS WHERE ORD_ACT = 1"
        )
        rev_t, cogs_t, lines_t = cur.fetchone()
        totals = {
            "sale_lines": int(lines_t or 0),
            "revenue": float(rev_t or 0),
            "cogs": float(cogs_t or 0),
            "profit": float((rev_t or 0) - (cogs_t or 0)),
            "margin_pct": (float((rev_t or 0) - (cogs_t or 0)) / float(rev_t) * 100) if rev_t else None,
        }
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
    return rollup


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
        # Persist per-store rollup next to its own watch folder for debugging.
        watch = next((f for f in folders if (f / STATE_FILENAME).exists()
                      and _read_state(f / STATE_FILENAME).get("last_processed_zip", "").startswith(f"PLUS_{store_id}_")), None)
        if watch is not None:
            out_file = watch / "_megaplus_live.json"
            out_file.write_text(json.dumps(rollup, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"wrote store {store_id} rollup → {out_file}")

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
