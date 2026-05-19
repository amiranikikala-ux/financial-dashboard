"""rs.ge ↔ MegaPlus waybill reconciliation.

Surfaces the waybills the operator must act on. The dashboard's rule is
"show only problems, hide what's already correct". After spot-verifying
5 random rows against source, the categorization landed on these classes:

  🔴 missing                 — rs.ge active waybill, no MegaPlus GET row
                                  for the same number
  🔄 wrong_store             — rs.ge dest=A, MegaPlus received only in B
                                  (kind=only_other) OR received in both
                                  A and B (kind=duplicate). Operator
                                  picked the wrong store dropdown.
  🟠 amount_mismatch         — both sides have it but totals diverge by
                                  more than ₾0.5 / 0.5%
  👻 ghost_ap                — MegaPlus GET has it, but rs.ge marked it
                                  cancelled — operator received against a
                                  cancelled document
  🟡 returns_not_recorded     — rs.ge "უკან დაბრუნება" without a matching
                                  GACERA entry
  🟡 sub_waybills_not_recorded — rs.ge "ქვე-ზედნადები" (`/N` suffix) with
                                  no matching MegaPlus row, even by base
  ⚠️ possible_replacements   — soft signal: same supplier has a GET row
                                  within ±14 days at amount within ±10%
                                  → likely a replacement waybill with a
                                  different number. NOT confirmed.
  🆕 rs_data_stale           — MegaPlus GET has waybills not present in
                                  any rs.ge xls file → rs.ge data needs
                                  refresh

Cancelled+replaced rs.ge waybills (most ფუდმარტი-style cases) are
filtered out before categorization — those are normal noise.

Closed-store waybills (Tbilisi addresses from 2022-2024) are filtered
out by destination-address classification. The user has 4 physical
locations: 2 active (1329 დვაბზუ + 1301 ოზურგეთი) and 2 closed
(Tbilisi). Only active-store destinations make it onto the dashboard.

Spot-check log (2026-05-02 — 5/5 rows verified against source):
  - 0755115527 ზედაზენი 383.58₾ ✅ rs.ge active, GET=0, GACERA=0
  - 0763193772 ბარამბო 408₾    ✅ rs.ge active, GET=0, GACERA=0
  - 0789696472/6 იფქლი 9.30₾   ✅ rs.ge active, base+full=0 in GET
  - 0820382602 იფქლი -6.39₾    ✅ rs.ge active return, GACERA=0
  - 0831673651 ჯი დი სი 72.55₾ ✅ rs.ge=72.55, GET=63.09 (Δ9.46)

Wrong-store spot-check (2026-05-02 — 14/14 verified):
  - 7 random `only_other` rows (rs.ge dest=ოზურგეთი, MegaPlus only in დვაბზუ)
  - 7 `duplicate` rows including Lactalis 0917949641 (received in both stores)
  - First pass found 26 false-positives where rs.ge address spelled the
    village as `დვაბზა` / `დვაბზეე` (not `დვაბზუ`); fixed by switching
    `1329` keyword to prefix `"დვაბზ"` per user verification — all
    variants resolve to the same physical store.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

STORE_ID_TO_NAME: dict[str, str] = {
    "1329": "დვაბზუ",
    "1301": "ოზურგეთი",
}

# Active-store classification by delivery address keywords. Anything
# matching Tbilisi address keywords is a closed-store leftover and is
# excluded from the dashboard.
#
# `1329` uses a prefix `"დვაბზ"` (not full `"დვაბზუ"`) because rs.ge data
# entries vary spelling — observed in production: `დვაბზუ`, `დვაბზა`,
# `დვაბზეე`. All resolve to the same physical village; the store there
# is named `დვაბზუ` in MegaPlus.
ACTIVE_STORE_KEYWORDS = {
    "1329": ("დვაბზ", "ლანჩხუთი"),
    "1301": ("ოზურგეთი",),
}
CLOSED_STORE_KEYWORDS = ("თბილის", "ბარამიძ", "ისაკიან")

# Amount tolerances
GET_AMOUNT_TOLERANCE_ABS = 0.5    # ₾
GET_AMOUNT_TOLERANCE_REL = 0.005  # 0.5%
GACERA_AMOUNT_TOLERANCE_REL = 0.05  # 5% (returns lose precision in conversion)

# ±N day window for the "possible replacement" soft signal
REPLACEMENT_WINDOW_DAYS = 14
REPLACEMENT_AMOUNT_TOLERANCE_REL = 0.10  # ±10%


def classify_destination(address: str | None) -> str:
    """Map rs.ge delivery-address string to one of:
      "1329" | "1301" | "closed" | "unknown"
    """
    if not isinstance(address, str) or not address.strip():
        return "unknown"
    addr_lower = address.lower()
    for store_id, keywords in ACTIVE_STORE_KEYWORDS.items():
        for kw in keywords:
            if kw in address or kw.lower() in addr_lower:
                return store_id
    for kw in CLOSED_STORE_KEYWORDS:
        if kw in address or kw.lower() in addr_lower:
            return "closed"
    return "unknown"


def parse_g_time(g_time: int | str | None) -> pd.Timestamp | None:
    """Decode MegaPlus G_TIME bigint (yymmddhhxx) to a Timestamp.

    G_TIME=2403250001 → 2024-03-25. Returns None on parse failure.
    """
    if g_time is None:
        return None
    s = str(g_time)
    if len(s) < 6:
        return None
    try:
        yy, mm, dd = int(s[0:2]), int(s[2:4]), int(s[4:6])
        return pd.Timestamp(2000 + yy, mm, dd)
    except Exception:
        return None


def load_rs_waybills(paths) -> pd.DataFrame:
    """Read every rs.ge waybill source path (parquet or .xls), normalize columns.

    `paths` is an iterable of file paths. Auto-dispatches via
    `rsge_cache.read_waybill_file` so cache-parquet and legacy XLS both work.

    Returns a DataFrame with normalized columns:
      zed, zed_base, status, type, tax_id, supplier_name, amount,
      act_date, cancel_date, destination, source_file
    """
    from dashboard_pipeline.rsge_cache import read_waybill_file
    frames = []
    for path in sorted(Path(p) for p in paths):
        df = read_waybill_file(path)
        df["_source_file"] = path.name
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=[
            "zed", "zed_base", "status", "type", "tax_id", "supplier_name",
            "amount", "act_date", "cancel_date", "destination", "source_file",
        ])
    rs = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame()
    out["zed"] = rs["ზედნადები"].astype(str).str.strip()
    out["zed_base"] = out["zed"].str.split("/").str[0]
    out["status"] = rs["სტატუსი"].fillna("")
    out["type"] = rs["ტიპი"].fillna("")
    out["tax_id"] = rs["ორგანიზაცია"].str.extract(r"\((\d{9,11})", expand=False)
    out["supplier_name"] = rs["ორგანიზაცია"].str.extract(r"\)\s*(.+)$", expand=False).fillna("(უცნობი)")
    out["amount"] = pd.to_numeric(rs["თანხა"], errors="coerce")
    out["act_date"] = pd.to_datetime(rs["გააქტიურების თარ."], errors="coerce")
    out["cancel_date"] = pd.to_datetime(rs.get("გაუქმების თარ."), errors="coerce")
    out["destination"] = rs["მიწოდების ადგილი"].fillna("")
    out["source_file"] = rs["_source_file"]
    return out


def fetch_megaplus_waybill_data(cur, store_id: str) -> dict[str, Any]:
    """Pull GET + GACERA waybill totals + supplier-resolution chain.

    Returned shape:
      {
        "store_id": "1329",
        "get": [{"zed": str, "tax_id": str|None, "total": float, "date": "YYYY-MM-DD"|None}],
        "gacera": [{"zed": str, "orig_zed": str|None, "tax_id": str|None, "total": float}],
      }
    """
    # DISTRIBUTORS UUID → tax_id
    cur.execute("SELECT DIST_UUID, saidentifikacio FROM DISTRIBUTORS")
    dist_uuid_to_taxid = {u: t for u, t in cur.fetchall() if u}

    # AGREEMENTS UUID → DISTRIBUTORS UUID
    cur.execute("SELECT AG_UUID, AG_SUPPLIER FROM AGREEMENTS")
    agr_to_dist = {a: s for a, s in cur.fetchall() if a and s}

    def agr_to_taxid(agr: str | None) -> str | None:
        if not agr:
            return None
        d = agr_to_dist.get(agr)
        return dist_uuid_to_taxid.get(d) if d else None

    # GET — group by ZED + AGR + TIME so we keep date for supplier-window match
    cur.execute("""
        SELECT G_ZED, G_AGR, G_TIME, SUM(G_PRICE * G_QUANT)
        FROM GET WHERE G_ACT = 1
        GROUP BY G_ZED, G_AGR, G_TIME
    """)
    get_rows = []
    for zed, agr, gtime, total in cur.fetchall():
        if not zed:
            continue
        date = parse_g_time(gtime)
        get_rows.append({
            "zed": str(zed).strip(),
            "tax_id": agr_to_taxid(agr),
            "total": float(total or 0),
            "date": date.strftime("%Y-%m-%d") if date is not None else None,
        })

    # GACERA — return waybills (rs.ge "უკან დაბრუნება" type)
    cur.execute("""
        SELECT GAC_ZED, GAC_G_ZED, GAC_D_ID, SUM(GAC_PRICE * GAC_QUANT)
        FROM GACERA WHERE GAC_ACT = 1
        GROUP BY GAC_ZED, GAC_G_ZED, GAC_D_ID
    """)
    # GAC_D_ID resolves to tax_id via DISTRIBUTORS.ID
    cur.execute("SELECT ID, saidentifikacio FROM DISTRIBUTORS")
    dist_id_to_taxid = {int(i): t for i, t in cur.fetchall() if i is not None}

    cur.execute("""
        SELECT GAC_ZED, GAC_G_ZED, GAC_D_ID, SUM(GAC_PRICE * GAC_QUANT)
        FROM GACERA WHERE GAC_ACT = 1
        GROUP BY GAC_ZED, GAC_G_ZED, GAC_D_ID
    """)
    gacera_rows = []
    for ret_zed, orig_zed, did, total in cur.fetchall():
        gacera_rows.append({
            "zed": (str(ret_zed).strip() if ret_zed else None),
            "orig_zed": (str(orig_zed).strip() if orig_zed else None),
            "tax_id": dist_id_to_taxid.get(int(did)) if did is not None else None,
            "total": float(total or 0),
        })

    return {
        "store_id": str(store_id),
        "get": get_rows,
        "gacera": gacera_rows,
    }


def _index_get(megaplus_stores: dict) -> tuple[dict, list]:
    """Build lookups across all stores.

    Returns:
      get_index — {zed: [(store, total, date_str)]}
      get_flat  — list of dicts with store/zed/tax_id/total/date for ±window match
    """
    get_index: dict[str, list] = defaultdict(list)
    get_flat: list[dict] = []
    for store_id, store_data in (megaplus_stores or {}).items():
        for row in store_data.get("get") or []:
            zed = row["zed"]
            get_index[zed].append((store_id, row["total"], row["date"]))
            get_flat.append({**row, "store_id": store_id})
    return get_index, get_flat


def _index_gacera(megaplus_stores: dict) -> dict:
    """{zed: [(store, total)]} — try both GAC_ZED and GAC_G_ZED."""
    idx: dict[str, list] = defaultdict(list)
    for store_id, store_data in (megaplus_stores or {}).items():
        for row in store_data.get("gacera") or []:
            for key in (row.get("zed"), row.get("orig_zed")):
                if key:
                    idx[key].append((store_id, row["total"]))
    return idx


def _categorize_row(
    row: pd.Series,
    get_index: dict,
    gacera_index: dict,
    dest_class: str,
) -> tuple[str, dict | None]:
    """Return (category, match_metadata).

    Categories: "missing" | "amount_mismatch" | "returns_not_recorded"
              | "sub_waybills_not_recorded" | "received_get" | "received_gacera"
              | "wrong_store"

    `dest_class` is the rs.ge destination's active-store classification
    ("1329" / "1301" / "closed" / "unknown"). Used to detect wrong-store
    cases: rs.ge dest=A but MegaPlus received it only in B, OR received
    in both A and B (operator picked wrong dropdown / duplicated entry).
    """
    zed = row["zed"]
    amt = row["amount"] if pd.notna(row["amount"]) else 0.0
    typ = row["type"]

    if zed in get_index:
        entries = get_index[zed]
        receiving_stores = sorted({s for s, _, _ in entries})
        get_total_all = sum(t for _, t, _ in entries)

        if dest_class in ("1329", "1301"):
            other_stores = [s for s in receiving_stores if s != dest_class]
            if other_stores:
                in_dest = dest_class in receiving_stores
                get_total_dest = sum(t for s, t, _ in entries if s == dest_class)
                get_total_other = get_total_all - get_total_dest
                kind = "duplicate" if in_dest else "only_other"
                return "wrong_store", {
                    "kind": kind,
                    "received_stores": receiving_stores,
                    "received_store_names": [STORE_ID_TO_NAME.get(s, s) for s in receiving_stores],
                    "get_total_all": get_total_all,
                    "get_total_dest": get_total_dest,
                    "get_total_other": get_total_other,
                }

        tol = max(GET_AMOUNT_TOLERANCE_ABS, abs(amt) * GET_AMOUNT_TOLERANCE_REL)
        if abs(amt - get_total_all) <= tol:
            return "received_get", {"get_total": get_total_all}
        return "amount_mismatch", {"get_total": get_total_all}

    if zed in gacera_index:
        gac_total = sum(t for _, t in gacera_index[zed])
        if abs(abs(amt) - abs(gac_total)) <= max(GET_AMOUNT_TOLERANCE_ABS, abs(amt) * GACERA_AMOUNT_TOLERANCE_REL):
            return "received_gacera", {"gacera_total": gac_total}
        return "amount_mismatch_gacera", {"gacera_total": gac_total}

    if typ == "უკან დაბრუნება":
        return "returns_not_recorded", None
    if typ == "ქვე-ზედნადები":
        return "sub_waybills_not_recorded", None
    return "missing", None


def _row_to_dict(row: pd.Series, store_id: str, extra: dict | None = None) -> dict:
    out = {
        "zed": row["zed"],
        "supplier_name": row["supplier_name"],
        "tax_id": row["tax_id"],
        "amount": float(row["amount"]) if pd.notna(row["amount"]) else 0.0,
        "type": row["type"],
        "act_date": row["act_date"].strftime("%Y-%m-%d %H:%M") if pd.notna(row["act_date"]) else None,
        "destination": row["destination"],
        "store_id": store_id,
        "store_name": STORE_ID_TO_NAME.get(store_id, "—"),
        "source_file": row["source_file"],
    }
    if extra:
        out.update(extra)
    return out


def _find_window_matches(missing_rows: pd.DataFrame, get_flat: list[dict]) -> list[dict]:
    """For each missing row, find a same-supplier GET entry within ±14 days
    at amount ±10%. Returns "soft signal" candidate replacements.
    """
    if missing_rows.empty or not get_flat:
        return []
    get_df = pd.DataFrame(get_flat)
    get_df["date"] = pd.to_datetime(get_df["date"], errors="coerce")
    matches: list[dict] = []
    for _, m in missing_rows.iterrows():
        if pd.isna(m["act_date"]) or not m["tax_id"]:
            continue
        amt = m["amount"] or 0
        if amt == 0:
            continue
        cand = get_df[
            (get_df["tax_id"] == m["tax_id"]) &
            (get_df["date"] >= m["act_date"] - timedelta(days=REPLACEMENT_WINDOW_DAYS)) &
            (get_df["date"] <= m["act_date"] + timedelta(days=REPLACEMENT_WINDOW_DAYS))
        ]
        if cand.empty:
            continue
        lo = amt * (1 - REPLACEMENT_AMOUNT_TOLERANCE_REL)
        hi = amt * (1 + REPLACEMENT_AMOUNT_TOLERANCE_REL)
        cand = cand[(cand["total"] >= lo) & (cand["total"] <= hi)]
        if cand.empty:
            continue
        best = cand.iloc[(cand["total"] - amt).abs().argmin()]
        matches.append({
            "rs_zed": m["zed"],
            "rs_amount": float(amt),
            "rs_date": m["act_date"].strftime("%Y-%m-%d"),
            "rs_supplier_name": m["supplier_name"],
            "rs_tax_id": m["tax_id"],
            "matched_get_zed": best["zed"],
            "matched_get_amount": float(best["total"]),
            "matched_get_date": best["date"].strftime("%Y-%m-%d") if pd.notna(best["date"]) else None,
            "matched_get_store": best["store_id"],
            "days_offset": int((best["date"] - m["act_date"]).days) if pd.notna(best["date"]) else None,
        })
    return matches


def _find_ghost_ap(rs_df: pd.DataFrame, get_index: dict) -> list[dict]:
    """rs.ge cancelled + MegaPlus GET has it = ghost AP (received against
    a cancelled document)."""
    cancelled = rs_df[rs_df["status"] == "გაუქმებული"]
    out: list[dict] = []
    for _, r in cancelled.iterrows():
        zed = r["zed"]
        if zed not in get_index:
            continue
        get_total = sum(t for _, t, _ in get_index[zed])
        stores = sorted({s for s, _, _ in get_index[zed]})
        out.append({
            "zed": zed,
            "supplier_name": r["supplier_name"],
            "tax_id": r["tax_id"],
            "rs_amount": float(r["amount"]) if pd.notna(r["amount"]) else 0.0,
            "get_total": get_total,
            "stores": stores,
            "store_names": [STORE_ID_TO_NAME.get(s, s) for s in stores],
            "rs_cancel_date": r["cancel_date"].strftime("%Y-%m-%d %H:%M") if pd.notna(r["cancel_date"]) else None,
        })
    return out


def _find_rs_stale(get_index: dict, all_rs_zeds: set) -> list[dict]:
    """GET has waybill that's not in any rs.ge xls — rs.ge data needs refresh."""
    stale: list[dict] = []
    for zed, refs in get_index.items():
        if zed in all_rs_zeds:
            continue
        if not (zed.startswith("0") and len(zed.replace("/", "")) >= 10):
            continue  # not rs.ge format
        total = sum(t for _, t, _ in refs)
        stores = sorted({s for s, _, _ in refs})
        stale.append({
            "zed": zed,
            "get_total": total,
            "stores": stores,
            "store_names": [STORE_ID_TO_NAME.get(s, s) for s in stores],
        })
    stale.sort(key=lambda x: -x["get_total"])
    return stale


def reconcile(rs_df: pd.DataFrame, megaplus_stores: dict) -> dict:
    """Build the full reconciliation bundle.

    Args:
      rs_df: DataFrame from `load_rs_waybills`
      megaplus_stores: {"1329": {"get": [...], "gacera": [...]}, ...}
    """
    if rs_df.empty:
        return {
            "totals": {
                "missing": 0, "wrong_store": 0, "wrong_store_only_other": 0,
                "wrong_store_duplicate": 0, "amount_mismatch": 0, "ghost_ap": 0,
                "returns_not_recorded": 0, "sub_waybills_not_recorded": 0,
                "possible_replacements": 0, "rs_data_stale": 0,
                "missing_amount_sum": 0.0, "wrong_store_amount_sum": 0.0,
                "amount_mismatch_amount_sum": 0.0, "ghost_ap_amount_sum": 0.0,
            },
            "missing": [], "wrong_store": [], "amount_mismatch": [], "ghost_ap": [],
            "returns_not_recorded": [], "sub_waybills_not_recorded": [],
            "possible_replacements": [], "rs_data_stale": [],
            "by_supplier": [],
        }

    get_index, get_flat = _index_get(megaplus_stores)
    gacera_index = _index_gacera(megaplus_stores)
    all_rs_zeds = set(rs_df["zed"].dropna().unique())

    rs_df = rs_df.copy()
    rs_df["dest_class"] = rs_df["destination"].apply(classify_destination)

    # Categorize active rs.ge rows. For returns specifically ("უკან დაბრუნება"),
    # also include "დასრულებული" status — owner-confirmed completed returns
    # must still be present in MegaPlus GACERA; filtering by "აქტიური" alone
    # hides 13+ completed returns that were never recorded (silent gap).
    # For non-return waybills we keep the original "აქტიური" filter to avoid
    # surfacing thousands of historical completed deliveries.
    active = rs_df[
        (rs_df["status"] == "აქტიური") |
        ((rs_df["status"] == "დასრულებული") & (rs_df["type"] == "უკან დაბრუნება"))
    ].copy()
    cats = active.apply(lambda r: _categorize_row(r, get_index, gacera_index, r["dest_class"]), axis=1)
    active["category"] = [c[0] for c in cats]
    active["match_meta"] = [c[1] for c in cats]

    # Filter to active-store destinations only for the problem categories
    is_active_store = active["dest_class"].isin(("1329", "1301"))

    missing_rows = active[(active["category"] == "missing") & is_active_store]
    mismatch_rows = active[(active["category"].isin(("amount_mismatch", "amount_mismatch_gacera"))) & is_active_store]
    wrong_store_rows = active[(active["category"] == "wrong_store") & is_active_store]
    returns_rows = active[(active["category"] == "returns_not_recorded") & is_active_store]
    sub_rows = active[(active["category"] == "sub_waybills_not_recorded") & is_active_store]

    # GHOST AP (cancelled rs.ge + GET present)
    ghost = _find_ghost_ap(rs_df, get_index)

    # ±14-day window soft signal — only on the missing rows (active stores)
    possible = _find_window_matches(missing_rows, get_flat)

    # rs.ge xls stale → GET has it, no rs.ge entry
    stale = _find_rs_stale(get_index, all_rs_zeds)

    # Materialize lists
    def to_dicts(df: pd.DataFrame) -> list[dict]:
        out = []
        for _, r in df.iterrows():
            store = r["dest_class"] if r["dest_class"] in ("1329", "1301") else "—"
            extra = {}
            mm = r.get("match_meta")
            if isinstance(mm, dict):
                extra = mm
            out.append(_row_to_dict(r, store, extra))
        return out

    missing_list = to_dicts(missing_rows)
    mismatch_list = to_dicts(mismatch_rows)
    wrong_store_list = to_dicts(wrong_store_rows)
    returns_list = to_dicts(returns_rows)
    sub_list = to_dicts(sub_rows)

    # Per-supplier summary across all problem categories
    by_supplier: dict[str, dict] = {}
    for category_name, rows in (
        ("missing", missing_list),
        ("wrong_store", wrong_store_list),
        ("amount_mismatch", mismatch_list),
        ("returns_not_recorded", returns_list),
        ("sub_waybills_not_recorded", sub_list),
    ):
        for r in rows:
            key = r["tax_id"] or r["supplier_name"]
            entry = by_supplier.setdefault(key, {
                "supplier_name": r["supplier_name"],
                "tax_id": r["tax_id"],
                "missing_count": 0,
                "missing_amount": 0.0,
                "wrong_store_count": 0,
                "amount_mismatch_count": 0,
                "amount_mismatch_amount": 0.0,
                "returns_not_recorded_count": 0,
                "sub_waybills_not_recorded_count": 0,
                "total_count": 0,
            })
            entry["total_count"] += 1
            if category_name == "missing":
                entry["missing_count"] += 1
                entry["missing_amount"] += r["amount"]
            elif category_name == "wrong_store":
                entry["wrong_store_count"] += 1
            elif category_name == "amount_mismatch":
                entry["amount_mismatch_count"] += 1
                entry["amount_mismatch_amount"] += r["amount"]
            elif category_name == "returns_not_recorded":
                entry["returns_not_recorded_count"] += 1
            elif category_name == "sub_waybills_not_recorded":
                entry["sub_waybills_not_recorded_count"] += 1

    by_supplier_list = sorted(
        by_supplier.values(),
        key=lambda x: -x["total_count"],
    )

    totals = {
        "missing": len(missing_list),
        "wrong_store": len(wrong_store_list),
        "wrong_store_only_other": sum(1 for r in wrong_store_list if r.get("kind") == "only_other"),
        "wrong_store_duplicate": sum(1 for r in wrong_store_list if r.get("kind") == "duplicate"),
        "amount_mismatch": len(mismatch_list),
        "ghost_ap": len(ghost),
        "returns_not_recorded": len(returns_list),
        "sub_waybills_not_recorded": len(sub_list),
        "possible_replacements": len(possible),
        "rs_data_stale": len(stale),
        "missing_amount_sum": round(sum(r["amount"] for r in missing_list), 2),
        "wrong_store_amount_sum": round(sum(r["amount"] for r in wrong_store_list), 2),
        "amount_mismatch_amount_sum": round(sum(r["amount"] for r in mismatch_list), 2),
        "ghost_ap_amount_sum": round(sum(r["get_total"] for r in ghost), 2),
        "rs_active_total": int((rs_df["status"] == "აქტიური").sum()),
        "rs_active_in_active_stores": int(((rs_df["status"] == "აქტიური") & rs_df["dest_class"].isin(("1329", "1301"))).sum()),
        "filtered_closed_stores": int(((rs_df["status"] == "აქტიური") & (rs_df["dest_class"] == "closed")).sum()),
    }

    return {
        "totals": totals,
        "missing": missing_list,
        "wrong_store": wrong_store_list,
        "amount_mismatch": mismatch_list,
        "ghost_ap": ghost,
        "returns_not_recorded": returns_list,
        "sub_waybills_not_recorded": sub_list,
        "possible_replacements": possible,
        "rs_data_stale": stale,
        "by_supplier": by_supplier_list,
    }
