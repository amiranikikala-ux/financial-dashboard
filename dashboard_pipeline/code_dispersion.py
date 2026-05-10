"""
Code dispersion detector — forensic timeline-based, read-only utility.

Identifies MegaPlus PRODUCTS rows where the same physical product is
registered under multiple DIFFERENT codes. Symptom: one code holds heavy
negative P_QUANT while sibling codes hold compensating positive — intake
recorded on one code, sales on another.

Distinct from PRODUCTS_FRAGMENTATION (`HANDOFF_ARCHIVE/PREVIEWS/
PRODUCTS_FRAGMENTATION_2026-05-03.md`) which detects same-barcode-multiple-
P_IDs. Here different-barcodes-same-physical-product.

Approach (no AI guessing — owner's explicit feedback 2026-05-11):
  Math closure + supplier overlap + brand stem + temporal coexistence.
  AI was removed because it over-merged distinct brands sharing only one
  generic word (Spilo vs Leopardi matchsticks both contained "ასანთი").

Pair detection (Strategy A — anchor has intake history):
  1. Pair math closure: anchor.qty + candidate.qty ≈ (in - out)
  2. Same brand stem (first 4-char content token)
  3. Shared supplier (G_D_ID) within overlapping intake year-window

Pair detection (Strategy B — anchor has ZERO intake, phased-out code):
  1. Pair math closure
  2. Same brand stem
  3. Same first 7 digits of EAN barcode (same manufacturer)

Output: Excel review file (Georgian labels). Mirrors orphan_resolver.py:
read-only, owner moves stock manually in MegaPlus, both codes stay ACTIVE
(prevents broken cashier scans on physically-shelved old-barcode boxes).

Usage:

    & "C:\\Users\\tengiz\\OneDrive\\Desktop\\AI აგენტი\\venv\\Scripts\\python.exe" \\
        -m dashboard_pipeline.code_dispersion --limit 100
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from openpyxl.styles import Font, PatternFill

from dashboard_pipeline.megaplus_backup import _connect
from dashboard_pipeline.waybill_reconciliation import parse_g_time

logger = logging.getLogger(__name__)

STORES: dict[str, str] = {"1329": "დვაბზუ", "1301": "ოზურგეთი"}
DESKTOP = Path(r"C:\Users\tengiz\OneDrive\Desktop")

_IN_CHUNK = 1500           # SQL Server cap on IN-clause params
MATH_TOLERANCE = 1.0       # qty closure tolerance (units)
BARCODE_PREFIX_LEN = 7     # for Strategy B (zero-intake anchor)
SUPPLIER_OVERLAP_YEARS = 2 # Strategy A — shared supplier within ±N years


# ─────────────────────────── Normalization ─────────────────────────────────

_token_re = re.compile(r"[\s/+\-_().,*\\\[\]]+")

_GENERIC_PREFIXES = {
    "მინ", "წყალი", "გაზ", "სასმელი", "შ", "მ", "შიდა", "მოხმარება",
    "სიგარეტი", "ერთჯერადი", "საღეჭი", "რეზინი", "ნამცხვარი", "ხორცი",
    "რძე", "ყველი", "მაკარონი", "შოკოლადი", "შოკოლადის",
    "ფქვილი", "ნაყინი", "ფაფა", "ფაფი", "ბატონი", "ბატონჩიკი",
    "ყავა", "ხსნადი", "ყინულოვანი", "ცივი", "ცხელი",
    "ჩაი", "წვენი", "ნექტარი", "კოკტეილი", "კავპუჩინო", "ლატე",
    "სოუსი", "კეჩუპი", "მაიონეზი",
    "კონფეტი", "კონფეტები", "ნამცხვრის", "გამოსაცხობი",
    "ჭიქა", "თეფში", "კოვზი", "ჩანგალი", "დანა",
    "პარკი", "პოლიეთილენის", "ერთჯერადი",
    "სათამაშო", "თოჯინა",
    "fr", "g", "ml", "kg",
}


def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(name or "")).strip().lower())


def first_content_stem(name: str, stem_len: int = 4) -> str:
    """First non-generic non-numeric content token's first 4 chars (stem)."""
    for tok in _token_re.split(normalize(name)):
        if not tok or len(tok) < 3:
            continue
        if tok in _GENERIC_PREFIXES:
            continue
        if re.match(r"^\d", tok):
            continue
        return tok[:stem_len]
    return ""


def discriminating_token_stems(name: str, stem_len: int = 4) -> set[str]:
    """All non-generic non-numeric non-size content tokens (as 4-char stems).

    Used to require AT LEAST 2 shared discriminating tokens between paired
    products. Single-word brand match (e.g. "ფეირი" alone) is too weak —
    Fairy Lemon vs Fairy Orange would pass with just brand stem, but they're
    different products.
    """
    out: set[str] = set()
    for tok in _token_re.split(normalize(name)):
        if not tok or len(tok) < 3:
            continue
        if tok in _GENERIC_PREFIXES:
            continue
        if re.match(r"^\d", tok):
            continue
        # skip size-like tokens (NNNxNNN, NNNგ, NNNმლ etc.)
        if re.match(r"^\d+(\.\d+)?[a-zა-ჰ]+$", tok):
            continue
        out.add(tok[:stem_len])
    return out


def shared_discriminating_count(a_name: str, c_name: str) -> int:
    return len(discriminating_token_stems(a_name) & discriminating_token_stems(c_name))


def barcode_prefix(barcode: str, n: int = BARCODE_PREFIX_LEN) -> str:
    digits = "".join(c for c in (barcode or "") if c.isdigit())
    return digits[:n] if len(digits) >= n else ""


# ─────────────────────────── Data model ────────────────────────────────────

@dataclass
class Product:
    p_id: int
    barcode: str
    name: str
    qty: float
    supplier_uuid: str
    qty_in: float = 0.0
    qty_out: float = 0.0
    last_intake_g_time: Optional[int] = None     # raw yymmddhhxx
    intake_supplier_years: set[tuple] = field(default_factory=set)
    # set of (year, supplier_id) tuples from GET history


@dataclass
class Pair:
    anchor: Product
    candidate: Product
    strategy: str           # "A_supplier" or "B_barcode_prefix"
    pair_math_balance: float
    shared_signal: str      # human-readable proof


@dataclass
class DispersionGroup:
    store_id: str
    store_label: str
    members: list[Product]               # all P_IDs in group, anchor first
    pairs: list[Pair]                    # all qualifying pair edges
    canonical: Product
    losers: list[Product]
    family_qty_now: float
    family_qty_in: float
    family_qty_out: float
    balance_check: float
    balance_consistent: bool
    proof_lines_ka: list[str]            # human-readable evidence


# ─────────────────────────── SQL fetch ─────────────────────────────────────

def _fetch_products(cur) -> list[Product]:
    cur.execute(
        """
        SELECT P_ID, LTRIM(RTRIM(P_BARCODE)) AS bc, P_NAME, P_QUANT,
               P_DAFAULTSUPPLIER
        FROM PRODUCTS
        WHERE P_NAME IS NOT NULL AND LTRIM(RTRIM(P_NAME)) <> ''
        """
    )
    return [
        Product(
            p_id=int(r.P_ID),
            barcode=r.bc or "",
            name=r.P_NAME,
            qty=float(r.P_QUANT or 0),
            supplier_uuid=str(r.P_DAFAULTSUPPLIER) if r.P_DAFAULTSUPPLIER else "",
        )
        for r in cur.fetchall()
    ]


def _fetch_intake_details(cur, p_ids: list[int]):
    """For each P_ID, return GET aggregates: qty_in, last_g_time,
    set of (year, G_D_ID) tuples (each unique supplier-year combination).
    """
    qty_in: dict[int, float] = defaultdict(float)
    last_intake: dict[int, int] = {}
    supplier_years: dict[int, set] = defaultdict(set)

    for i in range(0, len(p_ids), _IN_CHUNK):
        chunk = p_ids[i:i + _IN_CHUNK]
        if not chunk:
            continue
        ph = ",".join(["?"] * len(chunk))
        cur.execute(
            f"""
            SELECT G_P_ID, G_TIME, G_QUANT, G_D_ID
            FROM GET WHERE G_ACT = 1 AND G_P_ID IN ({ph})
            """,
            *chunk,
        )
        for r in cur.fetchall():
            pid = int(r.G_P_ID)
            qty_in[pid] += float(r.G_QUANT or 0)
            ts = int(r.G_TIME) if r.G_TIME is not None else 0
            if ts and (pid not in last_intake or ts > last_intake[pid]):
                last_intake[pid] = ts
            d = parse_g_time(ts)
            if d is not None and r.G_D_ID is not None:
                supplier_years[pid].add((d.year, int(r.G_D_ID)))
    return qty_in, last_intake, supplier_years


def _fetch_sales_total(cur, p_ids: list[int]) -> dict[int, float]:
    qty_out: dict[int, float] = {}
    for i in range(0, len(p_ids), _IN_CHUNK):
        chunk = p_ids[i:i + _IN_CHUNK]
        if not chunk:
            continue
        ph = ",".join(["?"] * len(chunk))
        cur.execute(
            f"""
            SELECT ORD_P_ID, SUM(ORD_QUANT) AS s FROM ORDERS
            WHERE ORD_ACT = 1 AND ORD_P_ID IN ({ph})
            GROUP BY ORD_P_ID
            """,
            *chunk,
        )
        for r in cur.fetchall():
            qty_out[int(r.ORD_P_ID)] = float(r.s or 0)
    return qty_out


# ─────────────────────────── Filters ───────────────────────────────────────

def pair_math_closes(a: Product, c: Product) -> tuple[bool, float]:
    sum_qty = a.qty + c.qty
    sum_in = a.qty_in + c.qty_in
    sum_out = a.qty_out + c.qty_out
    diff = (sum_in - sum_out) - sum_qty
    return abs(diff) < MATH_TOLERANCE, diff


def shared_supplier_in_window(a: Product, c: Product) -> tuple[bool, set[int]]:
    """A and C both received from same supplier within ±SUPPLIER_OVERLAP_YEARS."""
    a_set = a.intake_supplier_years
    c_set = c.intake_supplier_years
    if not a_set or not c_set:
        return False, set()
    matched: set[int] = set()
    for ya, sa in a_set:
        for yc, sc in c_set:
            if sa == sc and abs(ya - yc) <= SUPPLIER_OVERLAP_YEARS:
                matched.add(sa)
    return bool(matched), matched


def same_brand_stem(a: Product, c: Product) -> tuple[bool, str]:
    sa = first_content_stem(a.name)
    sc = first_content_stem(c.name)
    if sa and sa == sc:
        return True, sa
    return False, ""


def same_barcode_prefix(a: Product, c: Product) -> tuple[bool, str]:
    pa = barcode_prefix(a.barcode)
    pc = barcode_prefix(c.barcode)
    if pa and pa == pc:
        return True, pa
    return False, ""


MIN_SHARED_TOKENS = 2  # require ≥2 discriminating tokens (brand + variant)


def evaluate_pair(a: Product, c: Product) -> Optional[Pair]:
    """Return Pair if all filters pass; None otherwise.

    Filters (all must pass):
      1. Math closure pair-wise (qty_in − qty_out ≈ qty_now sum)
      2. Brand stem match (first content token, 4-char prefix)
      3. ≥2 shared discriminating tokens (brand + variant — distinguishes
         "ფეირი ლიმონი" from "ფეირი ფორთოხალი", "კაპი ატამი" from "კაპი ფალფი")
      4. Same supplier (G_D_ID) within ±SUPPLIER_OVERLAP_YEARS window

    Anchor MUST have intake history. Zero-intake anchors excluded (can't
    trace stock origin without supplier evidence — barcode prefix alone is
    too weak; same-manufacturer can produce different products).
    """
    if a.qty_in == 0:
        return None
    closes, diff = pair_math_closes(a, c)
    if not closes:
        return None
    brand_ok, brand = same_brand_stem(a, c)
    if not brand_ok:
        return None
    if shared_discriminating_count(a.name, c.name) < MIN_SHARED_TOKENS:
        return None
    sup_ok, suppliers = shared_supplier_in_window(a, c)
    if not sup_ok:
        return None
    return Pair(
        anchor=a, candidate=c, strategy="A_supplier",
        pair_math_balance=diff,
        shared_signal=f"იგივე მომწოდებელი {sorted(suppliers)} ±{SUPPLIER_OVERLAP_YEARS} წელში",
    )


# ─────────────────────────── Group assembly ────────────────────────────────

def _pick_canonical(members: list[Product]) -> Product:
    """Most-recent intake first; real EAN barcode preferred; highest intake."""
    def key(p: Product) -> tuple:
        return (
            -(p.last_intake_g_time or 0),
            0 if (p.barcode.isdigit() and len(p.barcode) >= 8) else 1,
            -p.qty_in,
            p.p_id,
        )
    return min(members, key=key)


def _build_proof(group_members: list[Product], pairs: list[Pair],
                 canonical: Product) -> list[str]:
    lines: list[str] = []
    lines.append(
        f"ჯგუფი {len(group_members)} კოდისგან: "
        + ", ".join(str(p.p_id) for p in group_members)
    )
    total_in = sum(p.qty_in for p in group_members)
    total_out = sum(p.qty_out for p in group_members)
    total_qty = sum(p.qty for p in group_members)
    lines.append(
        f"მათემატიკა: შემოვიდა {total_in:.0f} − გაიყიდა {total_out:.0f} = "
        f"{total_in - total_out:.0f} (qty ჯამი {total_qty:.0f})"
    )
    for pair in pairs:
        lines.append(
            f"  {pair.anchor.p_id} ↔ {pair.candidate.p_id}: "
            f"{pair.shared_signal}; დახურვა={pair.pair_math_balance:.1f}"
        )
    lines.append(
        f"მთავარი კოდი: {canonical.p_id} "
        f"(ბოლო შემოსვლა: "
        + (parse_g_time(canonical.last_intake_g_time).strftime("%Y-%m-%d")
           if canonical.last_intake_g_time and parse_g_time(canonical.last_intake_g_time)
           else "—")
        + f"; ბარკოდი {canonical.barcode or '—'})"
    )
    return lines


def detect_groups_for_store(
    store_id: str, store_label: str, products: list[Product]
) -> list[DispersionGroup]:
    by_pid = {p.p_id: p for p in products}
    anchors = [p for p in products if p.qty < 0 and p.qty_out > 0]
    positives = [p for p in products if p.qty > 0]

    # Bucket positives by brand stem for cheap O(N×k) prefilter
    pos_by_stem: dict[str, list[Product]] = defaultdict(list)
    for p in positives:
        s = first_content_stem(p.name)
        if s:
            pos_by_stem[s].append(p)

    qualified_pairs: list[Pair] = []
    pairs_by_anchor: dict[int, list[Pair]] = defaultdict(list)

    for a in anchors:
        stem = first_content_stem(a.name)
        if not stem:
            continue
        for c in pos_by_stem.get(stem, []):
            if c.p_id == a.p_id:
                continue
            pair = evaluate_pair(a, c)
            if pair is not None:
                qualified_pairs.append(pair)
                pairs_by_anchor[a.p_id].append(pair)

    print(f"  pairs that pass all filters: {len(qualified_pairs):,}", flush=True)

    # Pair-based output — for each anchor pick the BEST candidate (smallest
    # absolute math gap; tie-break by highest qty_in). No transitive groups.
    out: list[DispersionGroup] = []
    for anchor_pid, anchor_pairs in pairs_by_anchor.items():
        if not anchor_pairs:
            continue
        best = min(
            anchor_pairs,
            key=lambda p: (abs(p.pair_math_balance), -p.candidate.qty_in),
        )
        members = [best.anchor, best.candidate]
        group_qty = sum(p.qty for p in members)
        group_in = sum(p.qty_in for p in members)
        group_out = sum(p.qty_out for p in members)
        canonical = _pick_canonical(members)
        losers = [p for p in members if p.p_id != canonical.p_id]
        proof = _build_proof(members, [best], canonical)
        out.append(DispersionGroup(
            store_id=store_id, store_label=store_label,
            members=members, pairs=[best],
            canonical=canonical, losers=losers,
            family_qty_now=group_qty,
            family_qty_in=group_in, family_qty_out=group_out,
            balance_check=group_in - group_out,
            balance_consistent=True,
            proof_lines_ka=proof,
        ))
    return out


# ─────────────────────────── Excel writer ──────────────────────────────────

_BOLD = Font(bold=True)
_FILL_GREEN = PatternFill("solid", fgColor="C8E6C9")
_FILL_BLUE = PatternFill("solid", fgColor="BBDEFB")


def write_excel(groups: list[DispersionGroup], out_path: Path) -> None:
    wb = openpyxl.Workbook()

    # Sheet 1: ქმედებები — one row per group, simple instruction
    ws_act = wb.active
    ws_act.title = "ქმედებები"
    headers_act = [
        "მაღაზია", "პროდუქტი",
        "მთავარი კოდი (დარჩება)", "მთავარის ბარკოდი",
        "გადასატანი კოდები", "ნაშთი ჯამში გადატანის შემდეგ",
        "მტკიცებულება", "შესრულდა? (✓ ან თარიღი)",
    ]
    ws_act.append(headers_act)
    for c in ws_act[1]:
        c.font = _BOLD

    sortable = sorted(groups, key=lambda g: min(p.qty for p in g.members))
    for g in sortable:
        loser_str = ", ".join(
            f"{p.p_id} (ნაშთი {int(p.qty):+d})" for p in g.losers
        )
        proof_str = " | ".join(g.proof_lines_ka)
        ws_act.append([
            g.store_label,
            g.canonical.name,
            g.canonical.p_id,
            g.canonical.barcode or "—",
            loser_str,
            round(g.family_qty_now, 2),
            proof_str,
            "",
        ])
        for cell in ws_act[ws_act.max_row]:
            cell.fill = _FILL_GREEN

    # Sheet 2: დეტალები — full per-member breakdown
    ws_det = wb.create_sheet("დეტალები")
    headers_det = [
        "მაღაზია", "ჯგუფი (მთავარი კოდი)", "როლი", "P_ID", "ბარკოდი",
        "სახელი", "ნაშთი", "ჯამური შემოვიდა", "ჯამური გაიყიდა",
        "ბოლო შემოსვლა",
    ]
    ws_det.append(headers_det)
    for c in ws_det[1]:
        c.font = _BOLD
    for g in sortable:
        for p in g.members:
            role = "მთავარი" if p.p_id == g.canonical.p_id else "გადასატანი"
            last_dt = parse_g_time(p.last_intake_g_time) if p.last_intake_g_time else None
            ws_det.append([
                g.store_label, g.canonical.p_id, role,
                p.p_id, p.barcode or "—", p.name,
                p.qty, p.qty_in, p.qty_out,
                last_dt.strftime("%Y-%m-%d") if last_dt else "—",
            ])
            if role == "მთავარი":
                for cell in ws_det[ws_det.max_row]:
                    cell.fill = _FILL_BLUE
            else:
                for cell in ws_det[ws_det.max_row]:
                    cell.fill = _FILL_GREEN

    # Column widths
    for ws in (ws_act, ws_det):
        for col in ws.columns:
            ml = 0
            letter = col[0].column_letter
            for cell in col:
                v = str(cell.value) if cell.value is not None else ""
                if len(v) > ml:
                    ml = len(v)
            ws.column_dimensions[letter].width = min(80, max(10, ml + 2))

    wb.save(out_path)


# ─────────────────────────── Per-store driver ──────────────────────────────

def process_store(store_id: str, store_label: str,
                  limit: Optional[int] = None) -> list[DispersionGroup]:
    db = f"MEGAPLUS_{store_id}"
    print(f"\n=== {store_label} ({db}) ===", flush=True)
    conn = _connect(db, autocommit=True)
    cur = conn.cursor()

    products = _fetch_products(cur)
    print(f"  PRODUCTS: {len(products):,}", flush=True)

    pid_set = {p.p_id for p in products}
    qty_in, last_intake, supplier_years = _fetch_intake_details(cur, list(pid_set))
    qty_out = _fetch_sales_total(cur, list(pid_set))
    for p in products:
        p.qty_in = qty_in.get(p.p_id, 0.0)
        p.qty_out = qty_out.get(p.p_id, 0.0)
        p.last_intake_g_time = last_intake.get(p.p_id)
        p.intake_supplier_years = supplier_years.get(p.p_id, set())

    n_anchors = sum(1 for p in products if p.qty < 0 and p.qty_out > 0)
    print(f"  qualified anchors (qty<0 AND has sales): {n_anchors:,}", flush=True)

    # If --limit applied, sort anchors by most-negative-first and clip
    if limit is not None:
        anchors = sorted(
            [p for p in products if p.qty < 0 and p.qty_out > 0], key=lambda p: p.qty
        )[:limit]
        anchor_pids = {p.p_id for p in anchors}
        products_view = [
            p for p in products
            if p.p_id in anchor_pids or p.qty > 0
        ]
        groups = detect_groups_for_store(store_id, store_label, products_view)
    else:
        groups = detect_groups_for_store(store_id, store_label, products)

    print(f"  groups (math+supplier+brand all pass): {len(groups):,}", flush=True)
    return groups


# ─────────────────────────── Main ──────────────────────────────────────────

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="MegaPlus code-dispersion forensic detector (no AI)"
    )
    parser.add_argument("--limit", type=int, default=None,
                        help="Per-store anchor cap (most-negative first).")
    parser.add_argument("--store", choices=list(STORES.keys()) + ["all"],
                        default="all")
    parser.add_argument("--out", type=str, default=None,
                        help="Excel output path. Default: Desktop\\code_dispersion_forensic_<date>.xlsx")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    selected = (
        list(STORES.items())
        if args.store == "all"
        else [(args.store, STORES[args.store])]
    )
    all_groups: list[DispersionGroup] = []
    for store_id, store_label in selected:
        all_groups.extend(process_store(store_id, store_label, limit=args.limit))

    out_path = (
        Path(args.out) if args.out
        else DESKTOP / f"code_dispersion_forensic_{datetime.now():%Y-%m-%d}.xlsx"
    )
    write_excel(all_groups, out_path)
    print(f"\n>>> Excel written: {out_path}", flush=True)
    print(f"\n=== TOTAL groups across both stores: {len(all_groups):,} ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
