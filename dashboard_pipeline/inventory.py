"""Inventory snapshot — current stock + sales velocity + DOS + alerts.

Reads each restored MEGAPLUS_<store_id> database directly. One focused
query per store joins PRODUCTS + DISTRIBUTORS and derives 7d/30d/today
sales velocity, days-of-supply (DOS), sell-through, plus alert flags.

Output shape consumed by `rs-dashboard/src/Inventory.jsx`:
    {
        "snapshot_date": "YYYY-MM-DD",                # max backup_date across stores
        "stores": {
            "<store_id>": {
                "store_id": "...",
                "store_name": "...",                  # derived from object_mapping
                "backup_date": "YYYY-MM-DD",
                "last_complete_day": "YYYY-MM-DD",    # anchor for "today" sales
                "totals": { ... store-level summary ... },
                "items": [ ... per-SKU rows ... ],
                "suppliers": [ ... per-supplier rollup ... ],
                "alerts": {
                    "negative_stock": [...],
                    "stockout_recent": [...],
                    "low_stock": [...],
                    "dead_365_plus": [...],
                },
            }, ...
        },
        "totals_combined": { ... aggregated across all stores ... },
    }
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from dashboard_pipeline.megaplus_backup import (
    _connect,
    _db_name_for,
    LIVE_FILENAME,
)

logger = logging.getLogger(__name__)

LOW_STOCK_QTY_THRESHOLD = 5.0      # qty cutoff for "low stock" alert
LOW_STOCK_SOLD_30D_MIN = 1.0       # must have moved at least 1 in 30d
STOCKOUT_RECENT_DAYS = 14          # zero qty + sold in last N days = stockout alert
DEAD_DAYS = 365                    # 365+ days since sale = dead


def _store_name_for(store_id: str) -> str:
    """Best-effort display name. Mirrors object_mapping convention."""
    mapping = {
        "1301": "ოზურგეთი",
        "1329": "დვაბზუ",
    }
    return mapping.get(str(store_id), f"მაღაზია {store_id}")


def _safe_float(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _build_store_inventory(store_id: str, backup_date: str | None) -> dict | None:
    """Run inventory query for one store. Returns dict or None on failure."""
    db_name = _db_name_for(store_id)
    try:
        conn = _connect(db_name, autocommit=False)
    except Exception as exc:
        logger.warning("inventory: cannot connect to %s: %s", db_name, exc)
        return None

    try:
        cur = conn.cursor()

        # Anchor for windows = last_complete_day. Prefer backup_date (the cached
        # rollup's freshness), fall back to MAX(ORD_TIMESTAMP) in DB.
        cur.execute(
            "SELECT MAX(ORD_TIMESTAMP) FROM ORDERS WHERE ORD_ACT = 1"
        )
        max_ts_row = cur.fetchone()
        max_ts = max_ts_row[0] if max_ts_row else None

        if backup_date:
            try:
                anchor = datetime.strptime(backup_date, "%Y-%m-%d")
            except ValueError:
                anchor = max_ts or datetime.now()
        else:
            anchor = max_ts or datetime.now()

        # "today" = the last full calendar day represented in the backup (one
        # day before the snapshot since same-day backups arrive mid-evening).
        last_complete_day = (anchor - timedelta(days=1)).date()
        anchor_30 = anchor - timedelta(days=30)
        anchor_7 = anchor - timedelta(days=7)

        cur.execute(
            """
            WITH last_sale AS (
                SELECT ORD_P_ID, MAX(ORD_TIMESTAMP) AS last_sale_ts
                FROM ORDERS WHERE ORD_ACT = 1
                GROUP BY ORD_P_ID
            ),
            sold_7d AS (
                SELECT ORD_P_ID,
                       SUM(ORD_quant) AS qty,
                       SUM(ORD_jamjam) AS revenue
                FROM ORDERS
                WHERE ORD_ACT = 1 AND ORD_TIMESTAMP >= ?
                GROUP BY ORD_P_ID
            ),
            sold_30d AS (
                SELECT ORD_P_ID,
                       SUM(ORD_quant) AS qty,
                       SUM(ORD_jamjam) AS revenue
                FROM ORDERS
                WHERE ORD_ACT = 1 AND ORD_TIMESTAMP >= ?
                GROUP BY ORD_P_ID
            ),
            sold_today AS (
                SELECT ORD_P_ID,
                       SUM(ORD_quant) AS qty,
                       SUM(ORD_jamjam) AS revenue
                FROM ORDERS
                WHERE ORD_ACT = 1 AND CAST(ORD_TIMESTAMP AS DATE) = ?
                GROUP BY ORD_P_ID
            )
            SELECT
                p.P_ID, p.P_CODE, p.P_BARCODE, p.P_NAME, p.P_GROUP,
                p.P_QUANT, p.P_GETPRICE, p.P_PRICE, p.P_ACTIVE,
                d.DIST_UUID, d.dasaxeleba, d.saidentifikacio,
                ls.last_sale_ts,
                ISNULL(s7.qty, 0)   AS qty_sold_7d,
                ISNULL(s7.revenue, 0) AS rev_7d,
                ISNULL(s30.qty, 0)  AS qty_sold_30d,
                ISNULL(s30.revenue, 0) AS rev_30d,
                ISNULL(st.qty, 0)   AS qty_sold_today,
                ISNULL(st.revenue, 0) AS rev_today
            FROM PRODUCTS p
            LEFT JOIN DISTRIBUTORS d ON p.P_DAFAULTSUPPLIER = d.DIST_UUID
            LEFT JOIN last_sale ls ON ls.ORD_P_ID = p.P_ID
            LEFT JOIN sold_7d  s7  ON s7.ORD_P_ID  = p.P_ID
            LEFT JOIN sold_30d s30 ON s30.ORD_P_ID = p.P_ID
            LEFT JOIN sold_today st ON st.ORD_P_ID = p.P_ID
            WHERE p.P_QUANT <> 0
               OR s30.qty IS NOT NULL
               OR st.qty IS NOT NULL
            """,
            anchor_7, anchor_30, last_complete_day,
        )

        items: list[dict] = []
        by_supplier: dict[str, dict] = {}
        for row in cur.fetchall():
            (pid, code, barcode, name, group,
             qty, getprice, sellprice, active,
             dist_uuid, dist_name, dist_tin,
             last_sale_ts,
             qty7, rev7, qty30, rev30, qty_today, rev_today) = row

            qty_f = _safe_float(qty)
            getprice_f = _safe_float(getprice)
            sellprice_f = _safe_float(sellprice)
            qty7_f = _safe_float(qty7)
            qty30_f = _safe_float(qty30)
            qty_today_f = _safe_float(qty_today)
            rev_today_f = _safe_float(rev_today)
            rev30_f = _safe_float(rev30)

            stock_value_cost = qty_f * getprice_f
            stock_value_retail = qty_f * sellprice_f
            margin_unit = sellprice_f - getprice_f

            # Days of supply — qty / avg daily sales over last 30d.
            if qty30_f > 0:
                avg_daily = qty30_f / 30.0
                dos = qty_f / avg_daily if avg_daily > 0 else None
            else:
                dos = None

            # Sell-through 30d = qty_sold / (qty_sold + qty_on_hand). 100% = sold out.
            denom = qty30_f + qty_f
            sell_through_30d = (qty30_f / denom * 100.0) if denom > 0 else None

            days_since_sale = (anchor - last_sale_ts).days if last_sale_ts else None

            items.append({
                "product_id": int(pid) if pid is not None else 0,
                "product_code": code or "",
                "barcode": barcode or "",
                "product_name": name or "",
                "category": group or "(უცნობი)",
                "qty": qty_f,
                "cost_unit": getprice_f,
                "sell_unit": sellprice_f,
                "stock_value_cost": stock_value_cost,
                "stock_value_retail": stock_value_retail,
                "supplier_uuid": dist_uuid or "",
                "supplier_name": dist_name or "(უცნობი)",
                "supplier_tax_id": (dist_tin or "").strip(),
                "last_sale_date": last_sale_ts.isoformat() if last_sale_ts else None,
                "days_since_sale": days_since_sale,
                "qty_sold_30d": qty30_f,
                "qty_sold_today": qty_today_f,
                "revenue_today": rev_today_f,
                "days_of_supply": dos,
            })

            # Per-supplier rollup — folded into the same pass so revenue_30d
            # / qty_sold_7d don't have to ride along on every per-SKU row.
            skey = dist_uuid or "_unknown"
            bucket = by_supplier.setdefault(skey, {
                "supplier_uuid": dist_uuid or "",
                "supplier_name": dist_name or "(უცნობი)",
                "supplier_tax_id": (dist_tin or "").strip(),
                "sku_count": 0,
                "qty_total": 0.0,
                "stock_value_cost": 0.0,
                "stock_value_retail": 0.0,
                "qty_sold_30d": 0.0,
                "revenue_30d": 0.0,
                "qty_sold_today": 0.0,
                "revenue_today": 0.0,
            })
            if qty_f > 0:
                bucket["sku_count"] += 1
                bucket["qty_total"] += qty_f
                bucket["stock_value_cost"] += stock_value_cost
                bucket["stock_value_retail"] += stock_value_retail
            bucket["qty_sold_30d"] += qty30_f
            bucket["revenue_30d"] += rev30_f
            bucket["qty_sold_today"] += qty_today_f
            bucket["revenue_today"] += rev_today_f
    finally:
        conn.close()

    # ─── Alerts ────────────────────────────────────────────────────────────
    negative_stock = [it for it in items if it["qty"] < 0]
    stockout_recent = [
        it for it in items
        if it["qty"] == 0
        and it["days_since_sale"] is not None
        and it["days_since_sale"] <= STOCKOUT_RECENT_DAYS
    ]
    low_stock = [
        it for it in items
        if 0 < it["qty"] <= LOW_STOCK_QTY_THRESHOLD
        and it["qty_sold_30d"] >= LOW_STOCK_SOLD_30D_MIN
    ]
    dead_365_plus = [
        it for it in items
        if it["qty"] > 0
        and (it["days_since_sale"] is None or it["days_since_sale"] >= DEAD_DAYS)
    ]

    suppliers_sorted = sorted(
        by_supplier.values(),
        key=lambda s: s["stock_value_cost"],
        reverse=True,
    )

    # ─── Store totals ─────────────────────────────────────────────────────
    positive = [it for it in items if it["qty"] > 0]
    totals = {
        "sku_total": len(positive),
        "qty_total": sum(it["qty"] for it in positive),
        "stock_value_cost": sum(it["stock_value_cost"] for it in positive),
        "stock_value_retail": sum(it["stock_value_retail"] for it in positive),
        "dead_value_cost": sum(it["stock_value_cost"] for it in dead_365_plus),
        "qty_sold_today": sum(b["qty_sold_today"] for b in by_supplier.values()),
        "revenue_today": sum(b["revenue_today"] for b in by_supplier.values()),
        "qty_sold_30d": sum(b["qty_sold_30d"] for b in by_supplier.values()),
        "revenue_30d": sum(b["revenue_30d"] for b in by_supplier.values()),
        "negative_stock_count": len(negative_stock),
        "stockout_recent_count": len(stockout_recent),
        "low_stock_count": len(low_stock),
        "dead_365_plus_count": len(dead_365_plus),
    }
    if totals["stock_value_cost"] > 0:
        totals["dead_pct"] = totals["dead_value_cost"] / totals["stock_value_cost"] * 100.0
    else:
        totals["dead_pct"] = 0.0

    return {
        "store_id": store_id,
        "store_name": _store_name_for(store_id),
        "backup_date": backup_date,
        "last_complete_day": last_complete_day.isoformat(),
        "totals": totals,
        "items": items,
        "suppliers": suppliers_sorted,
    }


def build_inventory_view(megaplus_combined: dict | None) -> dict:
    """Build the cross-store inventory_view bundle.

    `megaplus_combined` is the cached `{"stores": {store_id: rollup}}` dict
    from `read_combined_rollup`. We only need each rollup's `store_id` and
    `backup_date` — the actual SKU data is queried fresh from SQL Server.
    """
    out_stores: dict[str, dict] = {}
    snapshot_dates: list[str] = []

    stores_meta = (megaplus_combined or {}).get("stores") or {}
    if not stores_meta:
        return {"available": False, "stores": {}, "snapshot_date": None, "totals_combined": {}}

    for store_id, rollup in stores_meta.items():
        backup_date = (rollup or {}).get("backup_date")
        try:
            store_view = _build_store_inventory(str(store_id), backup_date)
        except Exception as exc:
            logger.warning("inventory: store %s failed: %s", store_id, exc)
            store_view = None
        if store_view is None:
            continue
        out_stores[str(store_id)] = store_view
        if store_view.get("backup_date"):
            snapshot_dates.append(store_view["backup_date"])

    if not out_stores:
        return {"available": False, "stores": {}, "snapshot_date": None, "totals_combined": {}}

    combined_totals = {
        "sku_total": 0,
        "qty_total": 0.0,
        "stock_value_cost": 0.0,
        "stock_value_retail": 0.0,
        "dead_value_cost": 0.0,
        "qty_sold_today": 0.0,
        "revenue_today": 0.0,
        "qty_sold_30d": 0.0,
        "revenue_30d": 0.0,
        "negative_stock_count": 0,
        "stockout_recent_count": 0,
        "low_stock_count": 0,
        "dead_365_plus_count": 0,
    }
    for s in out_stores.values():
        t = s.get("totals") or {}
        for k in combined_totals:
            combined_totals[k] += _safe_float(t.get(k))
    combined_totals["sku_total"] = int(combined_totals["sku_total"])
    combined_totals["negative_stock_count"] = int(combined_totals["negative_stock_count"])
    combined_totals["stockout_recent_count"] = int(combined_totals["stockout_recent_count"])
    combined_totals["low_stock_count"] = int(combined_totals["low_stock_count"])
    combined_totals["dead_365_plus_count"] = int(combined_totals["dead_365_plus_count"])
    if combined_totals["stock_value_cost"] > 0:
        combined_totals["dead_pct"] = (
            combined_totals["dead_value_cost"] / combined_totals["stock_value_cost"] * 100.0
        )
    else:
        combined_totals["dead_pct"] = 0.0

    return {
        "available": True,
        "snapshot_date": max(snapshot_dates) if snapshot_dates else None,
        "stores": out_stores,
        "totals_combined": combined_totals,
    }
