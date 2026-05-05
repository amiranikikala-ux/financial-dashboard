"""Build the duplicate_products section of data.json by querying MegaPlus
SQL directly (live).

Detects products that share the same trimmed P_BARCODE but are stored as
2+ distinct P_ID rows. For each cluster, classifies variants as:

  * active   — has lifetime sales > 0
  * phantom  — has P_QUANT > 0 but zero sales (cluster also has ≥1 active)
  * dormant  — empty record (no stock, no sales)

A "phantom-stock cluster" is a duplicate cluster where at least one
variant is phantom — i.e., MegaPlus inventory shows units that will
never decrement, inflating apparent stock.

Non-interactive. Pipeline-callable. Returns None on DB error.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


STORES = {"1329": "დვაბზუ", "1301": "ოზურგეთი"}

QUERY = """
    WITH bc AS (
        SELECT LTRIM(RTRIM(P_BARCODE)) AS barcode, COUNT(*) AS n
        FROM PRODUCTS
        WHERE P_BARCODE IS NOT NULL AND LTRIM(RTRIM(P_BARCODE)) <> ''
        GROUP BY LTRIM(RTRIM(P_BARCODE))
        HAVING COUNT(*) >= 2
    )
    SELECT
        p.P_ID,
        LTRIM(RTRIM(p.P_BARCODE))                AS barcode,
        p.P_NAME,
        p.P_QUANT,
        p.P_GETPRICE,
        p.P_PRICE,
        p.P_DAFAULTSUPPLIER,
        ISNULL((SELECT SUM(o.ORD_jamjam) FROM ORDERS o WHERE o.ORD_P_ID = p.P_ID AND o.ORD_ACT = 1), 0) AS lifetime_revenue,
        ISNULL((SELECT COUNT(*)         FROM ORDERS o WHERE o.ORD_P_ID = p.P_ID AND o.ORD_ACT = 1), 0) AS sale_lines,
                 (SELECT MAX(o.ORD_TIMESTAMP) FROM ORDERS o WHERE o.ORD_P_ID = p.P_ID AND o.ORD_ACT = 1) AS last_sale
    FROM PRODUCTS p
    JOIN bc ON LTRIM(RTRIM(p.P_BARCODE)) = bc.barcode
"""


def _format_dt(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    return s.split(" ")[0] if s else None


def _round(v: Any, digits: int = 2) -> float:
    try:
        return round(float(v or 0), digits)
    except (ValueError, TypeError):
        return 0.0


def _int(v: Any) -> int:
    try:
        return int(v or 0)
    except (ValueError, TypeError):
        return 0


def _query_store(sid: str, label: str) -> list[dict[str, Any]]:
    from dashboard_pipeline.megaplus_backup import _connect, _db_name_for
    db = _db_name_for(sid)
    conn = _connect(db, autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute(QUERY)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    finally:
        conn.close()
    return [{**dict(zip(cols, r)), "store": label} for r in rows]


def _classify(item: dict[str, Any], cluster_has_active: bool) -> str:
    rev = float(item.get("lifetime_revenue") or 0)
    qty = float(item.get("P_QUANT") or 0)
    sales = _int(item.get("sale_lines"))
    if rev > 0 or sales > 0:
        return "active"
    if qty > 0 and cluster_has_active:
        return "phantom"
    return "dormant"


def build_duplicate_products_bundle() -> dict[str, Any] | None:
    try:
        all_rows: list[dict[str, Any]] = []
        for sid, label in STORES.items():
            all_rows.extend(_query_store(sid, label))
    except Exception as exc:
        logger.warning("duplicate_products: DB query failed — %s", exc)
        return None

    if not all_rows:
        logger.info("duplicate_products: 0 rows — section omitted")
        return None

    # Group by (store, barcode) — duplicates only count within the same store
    clusters_acc: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in all_rows:
        clusters_acc[(r["store"], r["barcode"])].append(r)

    clusters_out: list[dict[str, Any]] = []
    by_store_acc: dict[str, dict[str, Any]] = {}

    grand_total_clusters = 0
    grand_phantom_clusters = 0
    grand_phantom_units = 0.0
    grand_phantom_value_get = 0.0
    grand_phantom_value_sell = 0.0

    for (store, barcode), items in clusters_acc.items():
        if len(items) < 2:
            continue
        grand_total_clusters += 1

        cluster_has_active = any(
            float(it.get("lifetime_revenue") or 0) > 0 or _int(it.get("sale_lines")) > 0
            for it in items
        )

        variants = []
        cluster_phantom_units = 0.0
        cluster_phantom_value_get = 0.0
        cluster_phantom_value_sell = 0.0
        for it in items:
            kind = _classify(it, cluster_has_active)
            qty = _round(it.get("P_QUANT"), 3)
            getp = _round(it.get("P_GETPRICE"))
            sellp = _round(it.get("P_PRICE"))
            if kind == "phantom":
                cluster_phantom_units += qty
                cluster_phantom_value_get += qty * getp
                cluster_phantom_value_sell += qty * sellp
            variants.append({
                "product_id": _int(it.get("P_ID")),
                "name": (it.get("P_NAME") or "").strip() or None,
                "stock": qty,
                "get_price_ge": getp,
                "sell_price_ge": sellp,
                "lifetime_revenue_ge": _round(it.get("lifetime_revenue")),
                "sale_lines": _int(it.get("sale_lines")),
                "last_sale_at": _format_dt(it.get("last_sale")),
                "kind": kind,
            })

        # Sort variants: active first, then phantom, then dormant
        kind_rank = {"active": 0, "phantom": 1, "dormant": 2}
        variants.sort(key=lambda v: (kind_rank.get(v["kind"], 9), -v["lifetime_revenue_ge"]))

        has_phantom = cluster_phantom_units > 0
        if has_phantom:
            grand_phantom_clusters += 1
            grand_phantom_units += cluster_phantom_units
            grand_phantom_value_get += cluster_phantom_value_get
            grand_phantom_value_sell += cluster_phantom_value_sell

        clusters_out.append({
            "store": store,
            "barcode": barcode,
            "variant_count": len(variants),
            "variants": variants,
            "has_phantom": has_phantom,
            "phantom_units": _round(cluster_phantom_units, 3),
            "phantom_value_get_ge": _round(cluster_phantom_value_get),
            "phantom_value_sell_ge": _round(cluster_phantom_value_sell),
            "active_revenue_ge": _round(sum(v["lifetime_revenue_ge"] for v in variants if v["kind"] == "active")),
        })

        # Per-store accumulator
        st = by_store_acc.setdefault(store, {
            "store": store,
            "cluster_count": 0,
            "phantom_cluster_count": 0,
            "phantom_units": 0.0,
            "phantom_value_get_ge": 0.0,
            "phantom_value_sell_ge": 0.0,
        })
        st["cluster_count"] += 1
        if has_phantom:
            st["phantom_cluster_count"] += 1
            st["phantom_units"] += cluster_phantom_units
            st["phantom_value_get_ge"] += cluster_phantom_value_get
            st["phantom_value_sell_ge"] += cluster_phantom_value_sell

    # Sort clusters: phantom first by sell value desc, then non-phantom by active revenue desc
    clusters_out.sort(key=lambda c: (not c["has_phantom"], -c["phantom_value_sell_ge"], -c["active_revenue_ge"]))

    by_store: list[dict[str, Any]] = []
    for st in sorted(by_store_acc.values(), key=lambda s: s["store"]):
        st["phantom_units"] = _round(st["phantom_units"], 3)
        st["phantom_value_get_ge"] = _round(st["phantom_value_get_ge"])
        st["phantom_value_sell_ge"] = _round(st["phantom_value_sell_ge"])
        by_store.append(st)

    bundle = {
        "label_ka": "დუბლირებული პროდუქცია",
        "source": "megaplus_sql_live",
        "source_generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": {
            "cluster_count": grand_total_clusters,
            "phantom_cluster_count": grand_phantom_clusters,
            "phantom_units": _round(grand_phantom_units, 3),
            "phantom_value_get_ge": _round(grand_phantom_value_get),
            "phantom_value_sell_ge": _round(grand_phantom_value_sell),
            "by_store": by_store,
        },
        "clusters": clusters_out,
    }

    logger.info(
        "duplicate_products: %d clusters | %d phantom | %.0f phantom units | %.0f ₾ sell value",
        grand_total_clusters, grand_phantom_clusters,
        grand_phantom_units, grand_phantom_value_sell,
    )
    return bundle
