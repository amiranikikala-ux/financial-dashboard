"""Reconcile data.json supplier per-store totals against raw RS.ge source CSVs.

Reads ``Financial_Analysis/შემოტანილი პროდუქცია/*.csv`` directly, applies the
same filters as the pipeline (exclude ``გაუქმებული`` status; composite-key
dedup). Each row is classified into a store TWO ways:

  1. ``pipeline``  — uses ``_resolve_destination_object`` from
     ``dashboard_pipeline/imported_products.py``. This proves the pipeline
     ran the resolver as documented (data.json should match this exactly).
  2. ``truth``     — independent keyword-priority classifier embedded in
     this script. Iterates targets in priority order
     (default: დვაბზუ → ოზურგეთი → ...) and returns the first target whose
     core spelling appears in the destination text. This is the *intended*
     classification — the canonical answer when the destination text
     contains both store names (e.g., "ოზურგეთი, სოფ. დვაბზუ" → დვაბზუ).

Output: red/green report per supplier. Three columns to look at:

  * data.json   = what the dashboard / AI / Excel actually shows
  * pipeline    = what the source-via-current-resolver computes (should match data.json)
  * truth       = what the source-via-independent-classifier says is correct

A divergence between ``pipeline`` and ``truth`` reveals the resolver bug.
A divergence between ``data.json`` and ``pipeline`` reveals stale data.json
or filter mismatch.

Run:

    python scripts/reconcile_suppliers.py            # top-12 suppliers
    python scripts/reconcile_suppliers.py --all      # every supplier
    python scripts/reconcile_suppliers.py --top 25
    python scripts/reconcile_suppliers.py --tax-id 204920381    # single supplier
    python scripts/reconcile_suppliers.py --tax-id 204920381 --show-destinations
                                                     # also dump per-destination-text breakdown

Exit code: 0 if all reconcile within tolerance, 1 if any divergence found.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

# Allow `from dashboard_pipeline.imported_products import ...` when run from repo root.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard_pipeline.imported_products import (  # noqa: E402
    CANCELLED_STATUS_KA,
    _build_destination_lookup,
    _resolve_destination_object,
)

WORKSPACE_ROOT = Path(r"C:\Users\tengiz\OneDrive\Desktop\AI აგენტი")
SOURCE_DIR = WORKSPACE_ROOT / "Financial_Analysis" / "შემოტანილი პროდუქცია"
OBJECT_MAPPING_PATH = WORKSPACE_ROOT / "Financial_Analysis" / "object_mapping.json"
DATA_JSON = ROOT / "rs-dashboard" / "public" / "data.json"
SOURCE_FILES = [
    "პროდუქცია 2023.csv",
    "პროდუქცია 2024.csv",
    "პროდუქცია 2025.csv",
    "პროდუქცია 2026 -01-02.csv",
]

EPS = 0.5  # ₾ tolerance — sub-cent float drift across thousands of rows
KNOWN_STORES = ("ოზურგეთი", "დვაბზუ", "გაუნაწილებელი")

# Independent ground-truth classifier. Higher-priority targets are checked
# first — when the destination text contains BOTH "ოზურგეთი" and "დვაბზუ"
# (typical RS.ge format: "ოზურგეთი, სოფ. დვაბზუ"), the more specific
# store wins. Variants are CORE spellings only — substring match handles
# all the surface variants ("სოფ. დვაბზუ", "სოფ.დვაბზუ", "ს.დვაბზუ", etc.)
TRUTH_PRIORITY: list[tuple[str, tuple[str, ...]]] = [
    ("დვაბზუ", ("დვაბზუ", "დუაბზო", "დავაბზუ", "დვაბზე")),
    ("ოზურგეთი", ("ოზურგეთი", "ოზურგეთო", "ოზუეგეთი")),
]
TRUTH_DEFAULT = "გაუნაწილებელი"


def _resolve_truth(text: str) -> str:
    """Independent ground-truth classifier — does NOT use object_mapping.json.

    Used by this reconcile script to expose any classification disagreement
    between the pipeline resolver and the canonical priority-order rule.
    """
    if not text:
        return TRUTH_DEFAULT
    blob = str(text)
    for target, variants in TRUTH_PRIORITY:
        for v in variants:
            if v in blob:
                return target
    return TRUTH_DEFAULT


def _parse_amount(s):
    if s is None:
        return 0.0
    s = str(s).strip().replace(",", ".")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_qty(s):
    return _parse_amount(s)


def _parse_seller_id(seller_text: str) -> str | None:
    """Pulls (123456789) from '(123456789) შპს ELIZI ჯგუფი'."""
    if not seller_text:
        return None
    txt = seller_text.strip()
    if txt.startswith("(") and ")" in txt:
        return txt[1:txt.index(")")]
    return None


def load_source_per_supplier_per_store(resolver_lookup, default_obj):
    """Read all source CSVs, apply pipeline filters. For every row we keep
    classification under BOTH the pipeline resolver and the truth resolver
    so the report can show the disagreement.

    Returns: { tax_id: {
        'name': str,
        'per_store_pipeline': {store: {amount, rows, qty}},
        'per_store_truth':    {store: {amount, rows, qty}},
        'destinations':       {dest_text: {amount, rows, pipeline, truth}},
        'total':              {amount, rows, qty},
        'cancelled':          {amount, rows},
        'duplicates':         {amount, rows},
    } }
    """
    seen_keys = set()
    by_supplier = defaultdict(lambda: {
        "name": None,
        "per_store_pipeline": defaultdict(lambda: {"amount": 0.0, "rows": 0, "qty": 0.0}),
        "per_store_truth": defaultdict(lambda: {"amount": 0.0, "rows": 0, "qty": 0.0}),
        "destinations": defaultdict(lambda: {"amount": 0.0, "rows": 0, "pipeline": "", "truth": ""}),
        "total": {"amount": 0.0, "rows": 0, "qty": 0.0},
        "cancelled": {"amount": 0.0, "rows": 0},
        "duplicates": {"amount": 0.0, "rows": 0},
    })

    for fn in SOURCE_FILES:
        path = SOURCE_DIR / fn
        if not path.exists():
            print(f"  [warn] missing source file: {path}", file=sys.stderr)
            continue
        # `utf-8-sig` strips the BOM (﻿) the source export prepends to
        # the first header. Without this, `row.get("საქონლის კოდი")` returns
        # None for every row, the dedup composite key loses its product-code
        # component, and source-vs-pipeline rows that share (waybill, name,
        # amount, qty) but differ in barcode get incorrectly collapsed —
        # producing a phantom +N rows / +X ₾ delta against data.json.
        with open(path, encoding="utf-8-sig") as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                seller_text = row.get("გამყიდველი") or ""
                tax_id = _parse_seller_id(seller_text)
                if not tax_id:
                    continue
                status = (row.get("სტატუსი") or "").strip()
                amount = _parse_amount(row.get("საქონლის ფასი"))
                qty = _parse_qty(row.get("რაოდ."))
                bucket = by_supplier[tax_id]
                if bucket["name"] is None:
                    bucket["name"] = seller_text.strip()

                if status == CANCELLED_STATUS_KA:
                    bucket["cancelled"]["amount"] += amount
                    bucket["cancelled"]["rows"] += 1
                    continue

                # composite-key dedup mirrors pipeline (commit ae91710)
                key = (
                    (row.get("ზედნადების ნომერი") or "").strip(),
                    (row.get("საქონლის კოდი") or "").strip(),
                    (row.get("საქონლის დასახელება") or "").strip(),
                    round(amount, 2),
                    round(qty, 4),
                )
                if key in seen_keys:
                    bucket["duplicates"]["amount"] += amount
                    bucket["duplicates"]["rows"] += 1
                    continue
                seen_keys.add(key)

                dest_text = (row.get("ტრანსპორტირების დასრულება") or "").strip()
                pipeline_store = _resolve_destination_object(
                    dest_text, resolver_lookup, default_obj
                )
                truth_store = _resolve_truth(dest_text)

                bucket["per_store_pipeline"][pipeline_store]["amount"] += amount
                bucket["per_store_pipeline"][pipeline_store]["rows"] += 1
                bucket["per_store_pipeline"][pipeline_store]["qty"] += qty
                bucket["per_store_truth"][truth_store]["amount"] += amount
                bucket["per_store_truth"][truth_store]["rows"] += 1
                bucket["per_store_truth"][truth_store]["qty"] += qty

                de = bucket["destinations"][dest_text]
                de["amount"] += amount
                de["rows"] += 1
                de["pipeline"] = pipeline_store
                de["truth"] = truth_store

                bucket["total"]["amount"] += amount
                bucket["total"]["rows"] += 1
                bucket["total"]["qty"] += qty

    return by_supplier


def load_data_json_per_supplier_per_store():
    if not DATA_JSON.exists():
        print(f"FATAL: data.json not found at {DATA_JSON}", file=sys.stderr)
        sys.exit(2)
    blob = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    ip = blob.get("imported_products") or {}
    out = {}
    for s in ip.get("suppliers") or []:
        tax_id = s.get("tax_id")
        if not tax_id:
            continue
        per_store = {}
        for ob in s.get("object_breakdown") or []:
            obj = (ob.get("object") or "").strip()
            per_store[obj] = {
                "amount": ob.get("total_amount_ge") or 0.0,
                "rows": ob.get("row_count") or 0,
                "qty": ob.get("total_quantity") or 0.0,
            }
        out[tax_id] = {
            "name": s.get("supplier"),
            "total": {
                "amount": s.get("total_amount_ge") or 0.0,
                "rows": s.get("row_count") or 0,
                "qty": s.get("total_quantity") or 0.0,
            },
            "per_store": per_store,
        }
    return out


def fmt_money(x):
    return f"{x:>12,.2f} ₾"


def reconcile(top_n: int | None, only_tax_id: str | None, show_destinations: bool) -> int:
    obj_map = json.loads(OBJECT_MAPPING_PATH.read_text(encoding="utf-8"))
    lookup = _build_destination_lookup(obj_map)
    default_obj = obj_map.get("default_object") or "გაუნაწილებელი"

    print(f"Loading source CSVs from {SOURCE_DIR} …")
    src = load_source_per_supplier_per_store(lookup, default_obj)
    print(f"  source: {len(src)} suppliers")
    print(f"Loading data.json from {DATA_JSON} …")
    out = load_data_json_per_supplier_per_store()
    print(f"  data.json: {len(out)} suppliers")
    print()

    candidates = sorted(
        out.items(),
        key=lambda kv: kv[1]["total"]["amount"],
        reverse=True,
    )
    if only_tax_id:
        candidates = [(tid, d) for tid, d in candidates if tid == only_tax_id]
        if not candidates:
            print(f"FATAL: tax_id {only_tax_id} not in data.json", file=sys.stderr)
            return 2
    elif top_n is not None:
        candidates = candidates[:top_n]

    pipeline_failed = False
    truth_failed = False

    print(f"{'='*120}")
    for tax_id, out_data in candidates:
        src_data = src.get(tax_id)
        name = (out_data.get("name") or (src_data.get("name") if src_data else "?")) or "?"
        print(f"\n{name}  (tax_id={tax_id})")
        print(f"{'-'*120}")

        if not src_data:
            print(f"  ⚠ source: 0 rows for this tax_id — supplier exists in data.json only")
            pipeline_failed = True
            continue

        all_stores = (
            set(src_data["per_store_pipeline"].keys())
            | set(src_data["per_store_truth"].keys())
            | set(out_data["per_store"].keys())
            | set(KNOWN_STORES)
        )
        print(f"  {'store':<20s} {'data.json ₾':>14s} {'pipeline ₾':>14s} "
              f"{'truth ₾':>14s} {'truth-pipe ₾':>14s}  status")
        store_pipe_bad = False
        store_truth_bad = False
        for store in sorted(all_stores):
            o_amt = out_data["per_store"].get(store, {}).get("amount", 0.0)
            p_amt = src_data["per_store_pipeline"].get(store, {}).get("amount", 0.0)
            t_amt = src_data["per_store_truth"].get(store, {}).get("amount", 0.0)
            pipe_diff = o_amt - p_amt   # data.json vs pipeline-via-source
            truth_diff = t_amt - p_amt  # truth vs pipeline-via-source = bug magnitude
            pipe_ok = abs(pipe_diff) <= EPS
            truth_ok = abs(truth_diff) <= EPS
            if not pipe_ok:
                store_pipe_bad = True
            if not truth_ok:
                store_truth_bad = True
            marks = []
            if not pipe_ok:
                marks.append("✗ data≠pipeline")
            if not truth_ok:
                marks.append("✗ resolver bug")
            if pipe_ok and truth_ok:
                marks.append("✓")
            print(f"  {store:<20s} {o_amt:>12,.2f}  {p_amt:>12,.2f}  "
                  f"{t_amt:>12,.2f}  {truth_diff:+12,.2f}  {' '.join(marks)}")

        s_total = src_data["total"]["amount"]
        o_total = out_data["total"]["amount"]
        s_total_rows = src_data["total"]["rows"]
        o_total_rows = out_data["total"]["rows"]
        total_diff = o_total - s_total
        total_ok = abs(total_diff) <= EPS and s_total_rows == o_total_rows
        total_mark = "✓ TOTAL OK" if total_ok else "✗ TOTAL MISMATCH"
        print(f"  {'TOTAL':<20s} {o_total:>12,.2f}  {s_total:>12,.2f}  "
              f"{s_total:>12,.2f}  {0.0:+12,.2f}  {total_mark} (src rows {s_total_rows} vs out {o_total_rows})")

        c = src_data.get("cancelled", {})
        d = src_data.get("duplicates", {})
        print(f"  context: cancelled dropped {c.get('rows', 0)} rows / "
              f"{c.get('amount', 0):,.2f} ₾ · "
              f"duplicates dropped {d.get('rows', 0)} rows / "
              f"{d.get('amount', 0):,.2f} ₾")

        if store_pipe_bad or not total_ok:
            pipeline_failed = True
        if store_truth_bad:
            truth_failed = True
            print(f"  ⚠ resolver bug — destinations classified differently by pipeline vs truth:")
            for dest_text, info in sorted(
                src_data["destinations"].items(),
                key=lambda kv: kv[1]["amount"],
                reverse=True,
            ):
                if info["pipeline"] != info["truth"]:
                    print(f"     {info['amount']:>10,.2f} ₾ ({info['rows']:>4d} rows) "
                          f"pipeline={info['pipeline']:<14s} truth={info['truth']:<14s} "
                          f"| {dest_text[:80]!r}")

        if show_destinations:
            print(f"  per-destination breakdown:")
            for dest_text, info in sorted(
                src_data["destinations"].items(),
                key=lambda kv: kv[1]["amount"],
                reverse=True,
            ):
                print(f"     {info['amount']:>10,.2f} ₾ ({info['rows']:>4d} rows) "
                      f"pipeline={info['pipeline']:<14s} truth={info['truth']:<14s} "
                      f"| {dest_text[:80]!r}")

    print()
    print("="*120)
    if pipeline_failed:
        print("✗ data.json ≠ pipeline-via-source (data.json is stale or filter mismatch)")
    else:
        print("✓ data.json matches pipeline-via-source — pipeline ran cleanly")
    if truth_failed:
        print("✗ pipeline ≠ truth (RESOLVER BUG: destination text contains both stores; "
              "pipeline picks the wrong one)")
    else:
        print("✓ pipeline matches independent truth classifier — no resolver bug detected")
    return 1 if (pipeline_failed or truth_failed) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--top", type=int, default=12, help="check top-N suppliers (default 12)")
    g.add_argument("--all", action="store_true", help="check every supplier in data.json")
    g.add_argument("--tax-id", type=str, default=None, help="check a single supplier by tax_id")
    ap.add_argument("--show-destinations", action="store_true",
                    help="dump per-destination-text breakdown for each supplier checked")
    args = ap.parse_args()
    top = None if args.all else args.top
    sys.exit(reconcile(top_n=top, only_tax_id=args.tax_id,
                        show_destinations=args.show_destinations))


if __name__ == "__main__":
    main()
