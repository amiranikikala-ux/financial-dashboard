"""Inventory cleanup section — surfaces three classes of "problem stock"
that owner can review and clear from MegaPlus directly:

  1. dead_365_plus   — items with qty>0 that have not sold in 365+ days
                       (likely physically gone: spoilage, breakage, loss)
  2. negative_stock  — items with qty<0 (system says more sold than received;
                       sign of historical barcode/data mix-up)
  3. phantom_duplicates — duplicate-barcode clusters where one variant has
                       qty>0 but has never sold; the active variant on the
                       same barcode absorbs all real sales

Derived from already-cached `inventory_view` + `duplicate_products`.
Once the owner fixes a row in MegaPlus (e.g. corrects qty to 0 or marks
inactive), the next pipeline refresh re-derives this list and the fixed
row naturally disappears.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _store_name_to_id() -> dict[str, str]:
    return {"დვაბზუ": "1329", "ოზურგეთი": "1301"}


def _slim_item(item: dict[str, Any]) -> dict[str, Any]:
    """Trim per-SKU rows to only the columns the cleanup page renders."""
    return {
        "product_id": item.get("product_id"),
        "product_code": item.get("product_code") or "",
        "barcode": item.get("barcode") or "",
        "product_name": item.get("product_name") or "",
        "category": item.get("category") or "",
        "supplier_name": item.get("supplier_name") or "",
        "supplier_tax_id": item.get("supplier_tax_id") or "",
        "qty": float(item.get("qty") or 0),
        "cost_unit": float(item.get("cost_unit") or 0),
        "sell_unit": float(item.get("sell_unit") or 0),
        "stock_value_cost": float(item.get("stock_value_cost") or 0),
        "stock_value_retail": float(item.get("stock_value_retail") or 0),
        "last_sale_date": item.get("last_sale_date"),
        "days_since_sale": item.get("days_since_sale"),
        "qty_sold_30d": float(item.get("qty_sold_30d") or 0),
    }


def _phantom_rows_for_store(
    store_name: str,
    duplicate_clusters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """For each phantom cluster in this store, emit one row per phantom variant
    with the active variant's name so owner can see which valid product
    the duplicate barcode collides with.
    """
    out: list[dict[str, Any]] = []
    for cluster in duplicate_clusters:
        if cluster.get("store") != store_name:
            continue
        if not cluster.get("has_phantom"):
            continue
        variants = cluster.get("variants") or []
        active_names = [v.get("name") for v in variants if v.get("kind") == "active"]
        active_name = (active_names[0] if active_names else "") or "(არააქტიური)"
        for v in variants:
            if v.get("kind") != "phantom":
                continue
            qty = float(v.get("stock") or 0)
            getp = float(v.get("get_price_ge") or 0)
            sellp = float(v.get("sell_price_ge") or 0)
            out.append({
                "product_id": v.get("product_id"),
                "barcode": cluster.get("barcode") or "",
                "phantom_name": v.get("name") or "",
                "active_name_on_same_barcode": active_name,
                "qty": qty,
                "cost_unit": getp,
                "sell_unit": sellp,
                "stock_value_cost": qty * getp,
                "stock_value_retail": qty * sellp,
            })
    return out


def build_inventory_cleanup_bundle(
    inventory_view: dict[str, Any] | None,
    duplicate_products: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compose the inventory_cleanup payload from already-built bundles."""
    if not inventory_view or not inventory_view.get("available"):
        return {
            "available": False,
            "stores": {},
            "snapshot_date": None,
            "totals_combined": {},
        }

    dup_clusters = (duplicate_products or {}).get("clusters") or []
    name_to_id = _store_name_to_id()

    stores_out: dict[str, dict[str, Any]] = {}
    combined = {
        "dead_count": 0, "dead_value_cost": 0.0,
        "negative_count": 0, "negative_value_cost": 0.0,
        "phantom_count": 0, "phantom_value_cost": 0.0, "phantom_value_retail": 0.0,
    }

    for sid, store in (inventory_view.get("stores") or {}).items():
        store_name = store.get("store_name") or ""
        items = store.get("items") or []

        dead = [
            _slim_item(it) for it in items
            if float(it.get("qty") or 0) > 0
            and (it.get("days_since_sale") is None or int(it.get("days_since_sale") or 0) >= 365)
        ]
        neg = [
            _slim_item(it) for it in items
            if float(it.get("qty") or 0) < 0
        ]
        phantoms = _phantom_rows_for_store(store_name, dup_clusters)

        # Sort by impact (largest first)
        dead.sort(key=lambda r: -float(r.get("stock_value_cost") or 0))
        neg.sort(key=lambda r: float(r.get("qty") or 0))
        phantoms.sort(key=lambda r: -float(r.get("stock_value_cost") or 0))

        dead_value = sum(r["stock_value_cost"] for r in dead)
        neg_value = sum(abs(r["stock_value_cost"]) for r in neg)
        phantom_value_cost = sum(r["stock_value_cost"] for r in phantoms)
        phantom_value_retail = sum(r["stock_value_retail"] for r in phantoms)

        stores_out[str(sid)] = {
            "store_id": str(sid),
            "store_name": store_name,
            "backup_date": store.get("backup_date"),
            "dead_365_plus": dead,
            "negative_stock": neg,
            "phantom_duplicates": phantoms,
            "totals": {
                "dead_count": len(dead),
                "dead_value_cost": dead_value,
                "negative_count": len(neg),
                "negative_value_cost": neg_value,
                "phantom_count": len(phantoms),
                "phantom_value_cost": phantom_value_cost,
                "phantom_value_retail": phantom_value_retail,
            },
        }
        combined["dead_count"] += len(dead)
        combined["dead_value_cost"] += dead_value
        combined["negative_count"] += len(neg)
        combined["negative_value_cost"] += neg_value
        combined["phantom_count"] += len(phantoms)
        combined["phantom_value_cost"] += phantom_value_cost
        combined["phantom_value_retail"] += phantom_value_retail

    logger.info(
        "inventory_cleanup: dead=%d (%.0f ₾) · negative=%d (%.0f ₾) · phantom=%d (%.0f ₾ get / %.0f ₾ sell)",
        combined["dead_count"], combined["dead_value_cost"],
        combined["negative_count"], combined["negative_value_cost"],
        combined["phantom_count"], combined["phantom_value_cost"],
        combined["phantom_value_retail"],
    )

    return {
        "available": True,
        "snapshot_date": inventory_view.get("snapshot_date"),
        "stores": stores_out,
        "totals_combined": combined,
    }
