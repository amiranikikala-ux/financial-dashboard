"""
PRODUCTS orphan resolver — read-only utility.

Identifies MegaPlus PRODUCTS rows whose `P_DAFAULTSUPPLIER` field is
empty, zero-UUID, or points to a missing DISTRIBUTORS row, then proposes
the correct supplier using two evidence sources, in order of confidence:

  1. RS_CODES   — MegaPlus's own product↔supplier-TIN mapping ledger
                  (189K+ rows; the authoritative source — bypasses the
                   ghost-UUID problem because it joins by TIN, not by UUID).
  2. GET        — historical receipt records (G_P_ID, G_AGR, G_TIME).
  3. SOAP fallback — `rs_waybill_connector.get_name_from_tin` for the
                     remainder (TINs unknown to DISTRIBUTORS).

Produces an Excel review file. NEVER writes back to MegaPlus. The user
reviews the proposed mappings and applies them manually via MegaPlus UI.

Usage (PowerShell, parent venv):

    & "C:\\Users\\tengiz\\OneDrive\\Desktop\\AI აგენტი\\venv\\Scripts\\python.exe" \\
        -m dashboard_pipeline.orphan_resolver
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard_pipeline.megaplus_backup import _connect, _db_name_for

logger = logging.getLogger(__name__)

STORES = {"1329": "დვაბზუ", "1301": "ოზურგეთი"}

SOAP_CACHE_FILENAME = "orphan_soap_cache.json"

# ─── SQL building blocks ─────────────────────────────────────────────────────

ORPHAN_FILTER_SQL = """
    p.P_DAFAULTSUPPLIER IS NULL
    OR LTRIM(RTRIM(p.P_DAFAULTSUPPLIER)) IN ('', '00000000-0000-0000-0000-000000000000')
    OR d_current.DIST_UUID IS NULL
"""

ORPHAN_LIST_SQL = f"""
    SELECT
        p.P_ID,
        p.P_BARCODE,
        p.P_NAME,
        p.P_DAFAULTSUPPLIER                       AS current_supplier_uuid,
        ISNULL(SUM(o.ORD_jamjam), 0)              AS lifetime_revenue,
        COUNT(DISTINCT o.ORD_ID)                  AS sale_lines,
        MAX(o.ORD_TIMESTAMP)                      AS last_sale_at,
        CASE
          WHEN p.P_DAFAULTSUPPLIER IS NULL
            OR LTRIM(RTRIM(p.P_DAFAULTSUPPLIER)) = ''
            THEN N'ცარიელი'
          WHEN LTRIM(RTRIM(p.P_DAFAULTSUPPLIER)) = '00000000-0000-0000-0000-000000000000'
            THEN N'ნულოვანი ID'
          ELSE N'მოჩვენების ID'
        END                                       AS orphan_kind
    FROM PRODUCTS p
    LEFT JOIN DISTRIBUTORS d_current
        ON p.P_DAFAULTSUPPLIER = d_current.DIST_UUID
    JOIN ORDERS o ON o.ORD_P_ID = p.P_ID
    WHERE o.ORD_ACT = 1
      AND ({ORPHAN_FILTER_SQL})
    GROUP BY
        p.P_ID, p.P_BARCODE, p.P_NAME, p.P_DAFAULTSUPPLIER
"""


@dataclass
class Candidate:
    tin: str
    supplier_name: str | None
    dist_uuid: str | None        # DISTRIBUTORS.DIST_UUID if TIN known
    receipt_lines_in_get: int    # how many GET rows for this P_ID had this supplier
    last_receipt_at: datetime | None
    rs_codes_rows: int           # RS_CODES rows linking this P_ID + TIN


# ─── core resolver ───────────────────────────────────────────────────────────


def fetch_orphans(cur) -> pd.DataFrame:
    cur.execute(ORPHAN_LIST_SQL)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    df = pd.DataFrame.from_records(rows, columns=cols)
    if "current_supplier_uuid" in df.columns:
        df["current_supplier_uuid"] = df["current_supplier_uuid"].astype(str).str.strip()
    return df


def fetch_rs_candidates(cur, p_ids: list[int]) -> dict[int, list[tuple[str, int]]]:
    """For each P_ID → list of (TIN, rs_codes_row_count) sorted by row count desc."""
    if not p_ids:
        return {}
    out: dict[int, list[tuple[str, int]]] = {}
    # Process in chunks of 1000 to stay under SQL Server's 2100-parameter limit
    for i in range(0, len(p_ids), 1000):
        chunk = p_ids[i : i + 1000]
        placeholders = ",".join("?" * len(chunk))
        cur.execute(
            f"""
            SELECT RS_PID, LTRIM(RTRIM(RS_SAID)) AS tin, COUNT(*) AS n
            FROM RS_CODES
            WHERE RS_PID IN ({placeholders})
              AND RS_SAID IS NOT NULL
              AND LTRIM(RTRIM(RS_SAID)) <> ''
            GROUP BY RS_PID, LTRIM(RTRIM(RS_SAID))
            """,
            *chunk,
        )
        for pid, tin, n in cur.fetchall():
            out.setdefault(int(pid), []).append((tin, int(n)))
    for pid in out:
        out[pid].sort(key=lambda t: t[1], reverse=True)
    return out


def fetch_get_history(
    cur, p_ids: list[int]
) -> dict[int, dict[str, tuple[int, datetime | None]]]:
    """For each P_ID → {supplier_uuid: (line_count, latest_receipt_dt)}."""
    if not p_ids:
        return {}
    out: dict[int, dict[str, tuple[int, datetime | None]]] = {}
    for i in range(0, len(p_ids), 1000):
        chunk = p_ids[i : i + 1000]
        placeholders = ",".join("?" * len(chunk))
        cur.execute(
            f"""
            SELECT G_P_ID, LTRIM(RTRIM(G_AGR)) AS supplier_uuid,
                   COUNT(*) AS lines,
                   MAX(G_TIME) AS last_g_time
            FROM GET
            WHERE G_P_ID IN ({placeholders})
              AND G_AGR IS NOT NULL
              AND LTRIM(RTRIM(G_AGR)) <> ''
            GROUP BY G_P_ID, LTRIM(RTRIM(G_AGR))
            """,
            *chunk,
        )
        for pid, uuid, lines, last_g_time in cur.fetchall():
            # G_TIME format is YYMMDDxxxx — best-effort decode
            dt = _decode_g_time(last_g_time)
            out.setdefault(int(pid), {})[uuid] = (int(lines), dt)
    return out


def _decode_g_time(g_time) -> datetime | None:
    if g_time is None:
        return None
    try:
        s = str(int(g_time))
        if len(s) >= 6:
            yy = int(s[0:2])
            mm = int(s[2:4])
            dd = int(s[4:6])
            year = 2000 + yy
            return datetime(year, mm, dd)
    except (ValueError, TypeError):
        return None
    return None


def fetch_distributors(cur) -> pd.DataFrame:
    cur.execute(
        """
        SELECT
            LTRIM(RTRIM(DIST_UUID))         AS dist_uuid,
            LTRIM(RTRIM(saidentifikacio))   AS tin,
            dasaxeleba                      AS supplier_name
        FROM DISTRIBUTORS
        WHERE saidentifikacio IS NOT NULL
          AND LTRIM(RTRIM(saidentifikacio)) <> ''
        """
    )
    cols = [d[0] for d in cur.description]
    return pd.DataFrame.from_records(cur.fetchall(), columns=cols)


def best_candidate(
    p_id: int,
    rs_candidates: list[tuple[str, int]],
    get_history: dict[str, tuple[int, datetime | None]],
    distributors: pd.DataFrame,
) -> tuple[Candidate | None, list[Candidate]]:
    """Rank candidates and return (best, all_ranked_with_distributors_lookup)."""
    if not rs_candidates:
        return None, []
    dist_by_tin = distributors.set_index("tin")
    dist_by_uuid = distributors.set_index("dist_uuid")

    candidates = []
    for tin, rs_rows in rs_candidates:
        # Look up TIN in DISTRIBUTORS (canonical name + UUID, if registered)
        dist_uuid = None
        supplier_name = None
        if tin in dist_by_tin.index:
            row = dist_by_tin.loc[tin]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            dist_uuid = row["dist_uuid"]
            supplier_name = row["supplier_name"]

        # GET history for this supplier UUID (if we have one)
        receipt_lines = 0
        last_receipt_at = None
        if dist_uuid and dist_uuid in get_history:
            receipt_lines, last_receipt_at = get_history[dist_uuid]

        candidates.append(
            Candidate(
                tin=tin,
                supplier_name=supplier_name,
                dist_uuid=dist_uuid,
                receipt_lines_in_get=receipt_lines,
                last_receipt_at=last_receipt_at,
                rs_codes_rows=rs_rows,
            )
        )

    # Rank: registered (dist_uuid present) first, then RS_CODES row count, then receipts
    candidates.sort(
        key=lambda c: (
            c.dist_uuid is None,            # False (registered) sorts first
            -c.rs_codes_rows,
            -c.receipt_lines_in_get,
        )
    )
    return (candidates[0] if candidates else None), candidates


def soap_fallback_names(unresolved_tins: set[str]) -> dict[str, str]:
    """For TINs not in DISTRIBUTORS, query rs.ge SOAP for the registered name.

    Credentials: env vars RS_USER + RS_PASS, or interactive prompt if missing.
    """
    if not unresolved_tins:
        return {}

    user = os.environ.get("RS_USER") or "dashboard_api:400333858"
    password = os.environ.get("RS_PASS")
    if not password:
        import getpass
        try:
            password = getpass.getpass(f"  [soap-fallback] rs.ge password for {user}: ")
        except (EOFError, KeyboardInterrupt):
            print("  [soap-fallback] skipped — no password supplied")
            return {}
        if not password:
            print("  [soap-fallback] skipped — empty password")
            return {}

    from dashboard_pipeline.rs_waybill_connector import RSWaybillConnector

    out = {}
    try:
        connector = RSWaybillConnector(user=user, password=password)
        print(f"  [soap-fallback] resolving {len(unresolved_tins)} TINs via SOAP...")
        for tin in sorted(unresolved_tins):
            try:
                name = connector.get_name_from_tin(tin)
                if name:
                    out[tin] = name
                    print(f"      ✓ TIN {tin}: {name!r}")
                else:
                    print(f"      · TIN {tin}: rs.ge returned null (unknown TIN)")
            except Exception as e:
                print(f"      ✗ TIN {tin}: {e}")
    except Exception as e:
        print(f"  [soap-fallback] connector unavailable: {e}")
    return out


# ─── SOAP cache (persisted across pipeline runs) ─────────────────────────────


def _soap_cache_path(financial_analysis_dir: Path | None = None) -> Path:
    base = financial_analysis_dir or (Path(__file__).resolve().parent.parent / "Financial_Analysis")
    return base / SOAP_CACHE_FILENAME


def load_soap_cache(financial_analysis_dir: Path | None = None) -> dict[str, str]:
    """Read TIN→supplier_name mapping previously resolved via SOAP. Empty dict if missing."""
    path = _soap_cache_path(financial_analysis_dir)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {str(k).strip(): str(v).strip() for k, v in data.items() if k and v}
    except (OSError, ValueError) as e:
        logger.warning("orphan_soap_cache: read failed (%s) — treating as empty", e)
        return {}


def save_soap_cache(cache: dict[str, str], financial_analysis_dir: Path | None = None) -> None:
    path = _soap_cache_path(financial_analysis_dir)
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


# ─── main entry ──────────────────────────────────────────────────────────────


def build_orphan_dataframe(soap_cache: dict[str, str] | None = None) -> pd.DataFrame:
    """Query MegaPlus DB across all stores and return the resolved orphan DataFrame.

    Non-interactive. Pipeline-callable. Names for TINs not in DISTRIBUTORS are
    filled from `soap_cache` (a {TIN: supplier_name} dict, typically loaded
    from Financial_Analysis/orphan_soap_cache.json). Rows with TINs unknown to
    both DISTRIBUTORS and the cache keep `best_supplier_name=None` and
    resolution_method='RS_CODES (TIN unknown to DISTRIBUTORS)'.
    """
    soap_cache = soap_cache or {}
    frames = []
    for sid, label in STORES.items():
        frames.append(build_review_for_store(sid, label))
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    if combined.empty:
        return combined

    # Apply SOAP cache: where TIN is known but DISTRIBUTORS lookup failed,
    # fill the name from cache and re-tag resolution_method.
    if soap_cache:
        cache_keys = set(soap_cache.keys())
        mask = (
            combined["best_DIST_UUID"].isna()
            & combined["best_TIN"].notna()
            & combined["best_TIN"].astype(str).isin(cache_keys)
        )
        if int(mask.sum()) > 0:
            combined.loc[mask, "best_supplier_name"] = (
                combined.loc[mask, "best_TIN"].astype(str).map(soap_cache)
            )
            combined.loc[mask, "resolution_method"] = (
                "SOAP fallback (TIN not in DISTRIBUTORS — manual add needed)"
            )
    return combined


def build_review_for_store(store_id: str, label: str) -> pd.DataFrame:
    db = _db_name_for(store_id)
    print(f"\n=== {label} ({db}) ===")
    conn = _connect(db, autocommit=True)
    cur = conn.cursor()

    orphans = fetch_orphans(cur)
    print(f"  orphans (active sales): {len(orphans):,}")
    if orphans.empty:
        return orphans

    p_ids = orphans["P_ID"].astype(int).tolist()
    rs_candidates_by_pid = fetch_rs_candidates(cur, p_ids)
    print(f"  P_IDs with RS_CODES entry: {len(rs_candidates_by_pid):,}")

    get_history_by_pid = fetch_get_history(cur, p_ids)
    print(f"  P_IDs with GET history:    {len(get_history_by_pid):,}")

    distributors = fetch_distributors(cur)
    conn.close()

    # Resolve each orphan
    rows = []
    for _, orphan in orphans.iterrows():
        pid = int(orphan["P_ID"])
        rs_cands = rs_candidates_by_pid.get(pid, [])
        get_hist = get_history_by_pid.get(pid, {})
        best, ranked = best_candidate(pid, rs_cands, get_hist, distributors)

        rows.append({
            "store": label,
            "P_ID": pid,
            "P_BARCODE": str(orphan["P_BARCODE"] or "").strip(),
            "P_NAME": orphan["P_NAME"],
            "orphan_kind": orphan["orphan_kind"],
            "current_supplier_uuid": orphan["current_supplier_uuid"],
            "lifetime_revenue": float(orphan["lifetime_revenue"] or 0),
            "sale_lines": int(orphan["sale_lines"] or 0),
            "last_sale_at": orphan["last_sale_at"],
            "n_candidates": len(ranked),
            "best_TIN": best.tin if best else None,
            "best_supplier_name": best.supplier_name if best else None,
            "best_DIST_UUID": best.dist_uuid if best else None,
            "best_in_DISTRIBUTORS": "YES" if (best and best.dist_uuid) else "NO",
            "best_RS_CODES_rows": best.rs_codes_rows if best else 0,
            "best_GET_receipt_lines": best.receipt_lines_in_get if best else 0,
            "best_last_receipt_at": best.last_receipt_at if best else None,
            "all_candidate_TINs": ", ".join(c.tin for c in ranked) if ranked else "",
            "resolution_method": (
                "RS_CODES + DISTRIBUTORS" if (best and best.dist_uuid)
                else ("RS_CODES (TIN unknown to DISTRIBUTORS)" if best else "NO MATCH")
            ),
        })

    return pd.DataFrame(rows)


def main() -> int:
    # Load persisted SOAP cache (so we only ask rs.ge for *new* unresolved TINs)
    soap_cache = load_soap_cache()
    if soap_cache:
        print(f"  [soap-cache] loaded {len(soap_cache)} TIN(s) from disk")

    combined = build_orphan_dataframe(soap_cache)
    if combined.empty:
        print("no orphans found")
        return 0

    # SOAP fallback ONLY for TINs not yet in cache and not in DISTRIBUTORS
    unresolved_tins = set(
        combined.loc[
            combined["best_TIN"].notna()
            & combined["best_DIST_UUID"].isna()
            & ~combined["best_TIN"].astype(str).isin(soap_cache.keys()),
            "best_TIN",
        ].astype(str)
    )
    if unresolved_tins:
        print(f"\n=== SOAP fallback ({len(unresolved_tins)} new unresolved TINs) ===")
        soap_names = soap_fallback_names(unresolved_tins)
        if soap_names:
            mask = combined["best_DIST_UUID"].isna() & combined["best_TIN"].astype(str).isin(soap_names.keys())
            combined.loc[mask, "best_supplier_name"] = combined.loc[mask, "best_TIN"].astype(str).map(soap_names)
            combined.loc[
                mask, "resolution_method"
            ] = "SOAP fallback (TIN not in DISTRIBUTORS — manual add needed)"
            print(f"  → applied {len(soap_names)} names to {int(mask.sum())} rows")
            soap_cache.update(soap_names)
            save_soap_cache(soap_cache)
            print(f"  → updated cache to {len(soap_cache)} TIN(s)")

    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = Path("Financial_Analysis")
    out_dir.mkdir(exist_ok=True)
    out_xlsx = out_dir / f"orphan_resolver_review_{today}.xlsx"

    # Summary tab
    summary = (
        combined.assign(
            resolved=lambda d: d["best_DIST_UUID"].notna(),
            soap_fallback=lambda d: d["resolution_method"].str.startswith("SOAP"),
            no_match=lambda d: d["resolution_method"] == "NO MATCH",
        )
        .groupby("store")
        .agg(
            orphan_count=("P_ID", "count"),
            lifetime_revenue=("lifetime_revenue", "sum"),
            resolved_count=("resolved", "sum"),
            soap_fallback_count=("soap_fallback", "sum"),
            no_match_count=("no_match", "sum"),
        )
        .reset_index()
    )
    summary["resolved_pct"] = (
        summary["resolved_count"] / summary["orphan_count"] * 100
    ).round(1)

    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="summary", index=False)
        combined.sort_values(
            ["store", "lifetime_revenue"], ascending=[True, False]
        ).to_excel(writer, sheet_name="all_orphans", index=False)
        # Multi-candidate tab
        multi = combined[combined["n_candidates"] > 1]
        if not multi.empty:
            multi.to_excel(writer, sheet_name="multi_candidate", index=False)
        # Unresolved tab (no match found)
        unresolved = combined[combined["best_TIN"].isna()]
        if not unresolved.empty:
            unresolved.to_excel(writer, sheet_name="no_match", index=False)

    print(f"\n✓ Review file written: {out_xlsx}")
    print()
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
