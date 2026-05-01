"""Per-store MegaPlus category-anomaly detection.

Surfaces three operator-error patterns in the MegaPlus PRODUCTS table so
the user can fix them in MegaPlus and rerun the pipeline:

  1. Empty category — `P_GROUP IS NULL OR ''` on active products. Operator
     forgot to assign a category at all. Each row is actionable.

  2. Duplicate variants — same conceptual category exists under two raw
     names that differ only by a numeric code prefix (e.g. "შოკოლადის ფილა"
     vs "1406 | შოკოლადის ფილა"). Normalize by stripping the
     `<digits>[.digits] | ` prefix + whitespace + lowercase; any normalized
     key with >1 raw variant is a duplicate cluster. Rows = products in
     non-majority variants (the minority group is what the operator should
     reassign to the majority spelling).

  3. PROTECTED-supplier overview — every active product attributed via
     `P_DAFAULTSUPPLIER → DISTRIBUTORS.saidentifikacio` to one of the three
     PROTECTED cigarette importer tax_ids (ELIZI, ჯიდიაი, ინტერნეიშნლ),
     rolled up per (supplier × category). Read-only review surface — the
     operator visually scans for misclassified products. Pre-emptive
     detector: had this existed before 43ba181, the IQOS-in-non-cigarette
     situation would have been visible at a glance.

The module is pure read — takes a pyodbc cursor pointing at a per-store
MEGAPLUS_<storeID> database, returns a dict bundle. No writes, no SQL
state, no temp tables.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyodbc  # noqa: F401  (only for type hints)

PROTECTED_TAX_IDS: dict[str, str] = {
    "204920381": "ELIZI",
    "406181616": "ჯიდიაი",
    "420424393": "ინტერნეიშნლ",
}

STORE_ID_TO_NAME: dict[str, str] = {
    "1329": "დვაბზუ",
    "1301": "ოზურგეთი",
}

# Numeric code prefix on category strings (e.g. "0103 | ", "07031 | ", "1999.1 | ").
# The prefix is operator metadata, not part of the category's identity.
_PREFIX_RE = re.compile(r"^[\d.]+\s*\|\s*")


def normalize_category(raw: str | None) -> str:
    """Strip code prefix + collapse whitespace + lowercase. Empty/None → ''."""
    if not raw:
        return ""
    s = _PREFIX_RE.sub("", raw)
    s = " ".join(s.split())
    return s.lower()


def _store_name(store_id: str) -> str:
    return STORE_ID_TO_NAME.get(str(store_id), f"store_{store_id}")


# ───────────────────────────── empty category ────────────────────────────────


def _fetch_empty_category(cur) -> list[dict]:
    """Active products with empty/null P_GROUP. Each row = one fix in MegaPlus."""
    cur.execute(
        """
        SELECT p.P_ID, p.P_CODE, p.P_BARCODE, p.P_NAME,
               d.dasaxeleba       AS supplier_name,
               d.saidentifikacio  AS supplier_tax_id
        FROM PRODUCTS p
        LEFT JOIN DISTRIBUTORS d ON p.P_DAFAULTSUPPLIER = d.DIST_UUID
        WHERE p.P_ACTIVE = 1
          AND (p.P_GROUP IS NULL OR LTRIM(RTRIM(p.P_GROUP)) = '')
        ORDER BY p.P_ID DESC
        """
    )
    rows = []
    for pid, code, barcode, name, sup_name, sup_tax in cur.fetchall():
        rows.append({
            "product_id": int(pid),
            "code": (code or "").strip(),
            "barcode": (barcode or "").strip(),
            "product_name": (name or "").strip(),
            "supplier_name": (sup_name or "").strip(),
            "supplier_tax_id": (sup_tax or "").strip(),
        })
    return rows


# ───────────────────────────── duplicate variants ────────────────────────────


def _fetch_distinct_categories(cur) -> list[tuple[str, int]]:
    cur.execute(
        """
        SELECT P_GROUP, COUNT(*)
        FROM PRODUCTS
        WHERE P_ACTIVE = 1
          AND P_GROUP IS NOT NULL
          AND LTRIM(RTRIM(P_GROUP)) <> ''
        GROUP BY P_GROUP
        """
    )
    return [(cat or "", int(cnt or 0)) for cat, cnt in cur.fetchall()]


def _fetch_minority_products(cur, raw_categories: list[str]) -> list[dict]:
    """Return product rows whose P_GROUP is in the given (minority-variant) list."""
    if not raw_categories:
        return []
    placeholders = ",".join("?" * len(raw_categories))
    cur.execute(
        f"""
        SELECT p.P_ID, p.P_CODE, p.P_BARCODE, p.P_NAME, p.P_GROUP,
               d.dasaxeleba       AS supplier_name,
               d.saidentifikacio  AS supplier_tax_id
        FROM PRODUCTS p
        LEFT JOIN DISTRIBUTORS d ON p.P_DAFAULTSUPPLIER = d.DIST_UUID
        WHERE p.P_ACTIVE = 1
          AND p.P_GROUP IN ({placeholders})
        ORDER BY p.P_GROUP, p.P_ID DESC
        """,
        *raw_categories,
    )
    rows = []
    for pid, code, barcode, name, grp, sup_name, sup_tax in cur.fetchall():
        rows.append({
            "product_id": int(pid),
            "code": (code or "").strip(),
            "barcode": (barcode or "").strip(),
            "product_name": (name or "").strip(),
            "current_category": (grp or "").strip(),
            "supplier_name": (sup_name or "").strip(),
            "supplier_tax_id": (sup_tax or "").strip(),
        })
    return rows


def _build_duplicate_clusters(
    raw_pairs: list[tuple[str, int]],
    minority_products: list[dict],
) -> list[dict]:
    """Group raw categories by normalized name; emit clusters with size>1.

    For each cluster, the variant with the most products is the "majority"
    (presumed canonical spelling); other variants are minorities (operator
    should reassign their products to the majority name).
    """
    by_norm: dict[str, list[tuple[str, int]]] = {}
    for raw, cnt in raw_pairs:
        norm = normalize_category(raw)
        if not norm:
            continue
        by_norm.setdefault(norm, []).append((raw, cnt))

    products_by_raw: dict[str, list[dict]] = {}
    for prod in minority_products:
        products_by_raw.setdefault(prod["current_category"], []).append(prod)

    clusters = []
    for norm, members in by_norm.items():
        if len(members) <= 1:
            continue
        members_sorted = sorted(members, key=lambda x: -x[1])
        majority_raw, majority_cnt = members_sorted[0]
        minorities = members_sorted[1:]
        cluster = {
            "normalized_name": norm,
            "majority_variant": {"raw_category": majority_raw, "product_count": majority_cnt},
            "minority_variants": [
                {"raw_category": raw, "product_count": cnt} for raw, cnt in minorities
            ],
            "minority_products": [
                p for raw, _ in minorities for p in products_by_raw.get(raw, [])
            ],
        }
        clusters.append(cluster)

    clusters.sort(key=lambda c: -sum(v["product_count"] for v in c["minority_variants"]))
    return clusters


def _detect_duplicate_clusters(cur) -> list[dict]:
    raw_pairs = _fetch_distinct_categories(cur)
    minority_raws: list[str] = []
    by_norm: dict[str, list[tuple[str, int]]] = {}
    for raw, cnt in raw_pairs:
        norm = normalize_category(raw)
        if not norm:
            continue
        by_norm.setdefault(norm, []).append((raw, cnt))
    for members in by_norm.values():
        if len(members) <= 1:
            continue
        members_sorted = sorted(members, key=lambda x: -x[1])
        for raw, _ in members_sorted[1:]:
            minority_raws.append(raw)

    minority_products = _fetch_minority_products(cur, minority_raws)
    return _build_duplicate_clusters(raw_pairs, minority_products)


# ───────────────────────────── PROTECTED supplier review ─────────────────────


def _fetch_protected_supplier_overview(cur) -> list[dict]:
    placeholders = ",".join("?" * len(PROTECTED_TAX_IDS))
    cur.execute(
        f"""
        SELECT d.saidentifikacio  AS tax_id,
               d.dasaxeleba       AS supplier_name,
               ISNULL(p.P_GROUP, '(NULL)') AS category,
               COUNT(*)           AS product_count
        FROM PRODUCTS p
        JOIN DISTRIBUTORS d ON p.P_DAFAULTSUPPLIER = d.DIST_UUID
        WHERE p.P_ACTIVE = 1
          AND d.saidentifikacio IN ({placeholders})
        GROUP BY d.saidentifikacio, d.dasaxeleba, p.P_GROUP
        ORDER BY d.saidentifikacio, COUNT(*) DESC
        """,
        *PROTECTED_TAX_IDS.keys(),
    )
    by_supplier: dict[str, dict] = {}
    for tax_id, sup_name, cat, cnt in cur.fetchall():
        key = (tax_id or "").strip()
        entry = by_supplier.setdefault(key, {
            "supplier_tax_id": key,
            "supplier_name": (sup_name or "").strip(),
            "supplier_label": PROTECTED_TAX_IDS.get(key, sup_name or ""),
            "categories": [],
        })
        entry["categories"].append({
            "raw_category": (cat or "").strip(),
            "product_count": int(cnt or 0),
        })
    # Preserve PROTECTED_TAX_IDS ordering for stable UI rendering.
    return [
        by_supplier[k]
        for k in PROTECTED_TAX_IDS.keys()
        if k in by_supplier
    ]


# ───────────────────────────── public entry ──────────────────────────────────


def build_anomaly_bundle(cur, store_id: str) -> dict:
    """Run all three detectors against `cur` and return one per-store bundle.

    `cur` must be a pyodbc cursor against a MEGAPLUS_<storeID> database.
    """
    empty = _fetch_empty_category(cur)
    clusters = _detect_duplicate_clusters(cur)
    protected = _fetch_protected_supplier_overview(cur)

    minority_count = sum(
        sum(v["product_count"] for v in c["minority_variants"])
        for c in clusters
    )

    return {
        "store_id": str(store_id),
        "store_name": _store_name(store_id),
        "summary": {
            "empty_category_count": len(empty),
            "duplicate_cluster_count": len(clusters),
            "duplicate_minority_product_count": minority_count,
            "protected_supplier_distinct_categories": sum(
                len(p["categories"]) for p in protected
            ),
        },
        "empty_category_products": empty,
        "duplicate_clusters": clusters,
        "protected_supplier_overview": protected,
    }
