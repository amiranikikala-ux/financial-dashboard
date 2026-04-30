"""
Retail-driven supplier attribution prototype (Phase 1 verification).

Iterates over per-row retail sales (not imports). For each row, attributes
to a supplier via:
  1. exact code/barcode match in imports (unique supplier)
  2. brand-exclusivity rule (configurable per supplier)
  3. most-recent supplier (for codes carried by multiple suppliers)
  4. unattributed (honest gap)

Outputs per-supplier-per-store totals + comparison to MAX rollup (dvabzu only).

Run: python _scratch_supplier_attribution_v2.py
"""
from __future__ import annotations
import glob, re, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent.parent  # this script lives in HANDOFF_ARCHIVE/
FA = ROOT / "Financial_Analysis"

# Brand-exclusivity rules: tax_id → list of regex patterns matching retail product names
# Used as fallback when code/barcode is not in any import
BRAND_RULES = {
    "204920381": [  # ELIZI - JTI cigarette distributor
        r"ვინსტონ", r"ქემელ", r"სობრანი", r"პირველი ინტერნაც", r"პირველი პრემიუმ",
    ],
    "406181616": [  # ჯიდიაი - Philip Morris cigarette distributor
        r"მალბორო", r"პარლამენტ", r"ტერეა", r"ელ ენდ ემ", r"l&m",
    ],
    "237077961": [  # ვასაძის პური - bakery (short codes 1002, 9003 etc. collide)
        r"ვასაძ", r"ქვის პური", r"შეფუთული ქვის",
    ],
}
BRAND_PATTERNS = {tid: re.compile("|".join(pats), re.IGNORECASE) for tid, pats in BRAND_RULES.items()}

STORE_FOLDERS = {
    "დვაბზუ": FA / "გაყიდული პროდუქტები სოფ დვაბზუ",
    "ოზურგეთი": FA / "გაყიდული პროდუქტები სოფ ოზურგეთი",
}


def _norm(v) -> str:
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def load_imports() -> pd.DataFrame:
    files = sorted((FA / "შემოტანილი პროდუქცია").glob("*.csv"))
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["supplier_id"] = df["გამყიდველი"].str.extract(r"\((\d+)\)")
    df["supplier_name"] = df["გამყიდველი"].str.replace(r"\(\d+\)\s*", "", regex=True).str.strip()
    df["code_str"] = df["საქონლის კოდი"].apply(_norm)
    df["activation_date"] = pd.to_datetime(df["გააქტიურების თარიღი"], errors="coerce", dayfirst=True)
    df["qty"] = pd.to_numeric(df["რაოდ."], errors="coerce")
    df["cost_paid"] = pd.to_numeric(df["საქონლის ფასი"], errors="coerce")
    return df


def load_retail(store_name: str) -> pd.DataFrame:
    folder = STORE_FOLDERS[store_name]
    files = sorted(folder.glob("*.xls*"))
    df = pd.concat([pd.read_excel(f) for f in files], ignore_index=True)
    df["code_str"] = df["კოდი"].apply(_norm)
    df["barcode_str"] = df["შტრიხკოდი"].apply(_norm)
    df["sale_date"] = pd.to_datetime(df["დრო"], errors="coerce")
    df["rev_ge"] = df["ფასი"] * df["რაოდენობა"]
    df["cost_ge"] = df["თვითღირებულება"] * df["რაოდენობა"]
    df["profit_ge"] = df["მოგება"]
    df["store"] = store_name
    return df


def build_code_to_suppliers(imports: pd.DataFrame) -> dict:
    """code → [(supplier_id, latest_activation_date, total_qty_share), ...]
    Sorted with the most-frequent supplier (by total qty) first, used as
    last-resort fallback when no past-dated candidate exists for the sale date.
    """
    out: dict = {}
    g = imports.dropna(subset=["code_str", "supplier_id"]).groupby(["code_str", "supplier_id"]).agg(
        latest=("activation_date", "max"),
        total_qty=("qty", "sum"),
    )
    for (code, sid), row in g.iterrows():
        out.setdefault(code, []).append((sid, row["latest"], float(row["total_qty"] or 0)))
    # Sort each list by qty desc so [0] is the dominant historical supplier
    for code in out:
        out[code].sort(key=lambda x: x[2], reverse=True)
    return out


def attribute(retail_row, code2sup: dict) -> tuple[str | None, str]:
    """Returns (supplier_id_or_None, kind)."""
    sale_date = retail_row.sale_date
    name = str(retail_row.დასახელება) if hasattr(retail_row, "დასახელება") else ""

    # Tier 1: code-or-barcode lookup
    for key in (retail_row.barcode_str, retail_row.code_str):
        suppliers = code2sup.get(key)
        if not suppliers:
            continue
        if len(suppliers) == 1:
            return suppliers[0][0], "code_unique"
        # Multi-supplier: prefer most-recent past-dated import
        past = [(sid, dt, qty) for sid, dt, qty in suppliers
                if pd.notna(dt) and (pd.isna(sale_date) or dt <= sale_date)]
        if past:
            past.sort(key=lambda x: x[1], reverse=True)
            return past[0][0], "multi_recent"
        # No past candidate: use most-frequent historical supplier by qty.
        # The list is already sorted by qty desc.
        return suppliers[0][0], "multi_dominant"

    # Tier 2: brand-exclusivity rule
    for tid, pat in BRAND_PATTERNS.items():
        if pat.search(name):
            return tid, "brand_rule"

    return None, "unattributed"


def main():
    print("Loading imports…")
    imports = load_imports()
    print(f"  {len(imports):,} import rows from 15 monthly files")
    code2sup = build_code_to_suppliers(imports)
    print(f"  {len(code2sup):,} unique codes mapped")

    print("\nLoading MAX rollup oracle (dvabzu only)…")
    mx = pd.read_excel(FA / "მეგა პლუს" / "კომპანიების გაყიდვა მოგება.xls")
    mx["tax_id_str"] = mx["საიდენტ."].apply(_norm)
    mx_by_tid = {row["tax_id_str"]: row for _, row in mx.iterrows()}
    print(f"  {len(mx_by_tid)} suppliers in oracle")

    # Index supplier_id → name (from imports for display)
    sup_names = imports.dropna(subset=["supplier_id"]).groupby("supplier_id")["supplier_name"].first().to_dict()

    rows_out = []
    for store_name in STORE_FOLDERS:
        print(f"\nLoading retail for {store_name}…")
        retail = load_retail(store_name)
        print(f"  {len(retail):,} retail rows")

        attr = retail.apply(lambda r: attribute(r, code2sup), axis=1)
        retail["supplier_id"] = attr.map(lambda x: x[0])
        retail["attr_kind"] = attr.map(lambda x: x[1])

        kind_counts = retail["attr_kind"].value_counts().to_dict()
        unattr_rev = retail.loc[retail["supplier_id"].isna(), "rev_ge"].sum()
        total_rev = retail["rev_ge"].sum()
        print(f"  attribution kinds: {kind_counts}")
        print(f"  total rev: {total_rev:,.2f} ₾   unattributed: {unattr_rev:,.2f} ₾ ({unattr_rev/total_rev*100:.1f}%)")

        # Per-supplier aggregate
        agg = retail.dropna(subset=["supplier_id"]).groupby("supplier_id").agg(
            rev=("rev_ge", "sum"),
            cost=("cost_ge", "sum"),
            profit=("profit_ge", "sum"),
            qty=("რაოდენობა", "sum"),
            rows=("rev_ge", "size"),
        ).reset_index()
        agg["margin_pct"] = (agg["profit"] / agg["rev"] * 100).round(2)
        agg["store"] = store_name

        for r in agg.itertuples(index=False):
            mx_row = mx_by_tid.get(r.supplier_id)
            mx_rev = float(mx_row["რეალიზ."]) if mx_row is not None else None
            mx_margin = float(mx_row["მარჟა"]) if mx_row is not None else None
            gap = ((r.rev - mx_rev) / mx_rev * 100) if (mx_rev and mx_rev > 0) else None
            badge = ""
            if gap is not None:
                if abs(gap) < 2:
                    badge = "✓"
                elif abs(gap) < 5:
                    badge = "🟢"
                elif abs(gap) < 15:
                    badge = "🟡"
                else:
                    badge = "🔴"
            rows_out.append({
                "store": store_name,
                "tax_id": r.supplier_id,
                "supplier": sup_names.get(r.supplier_id, "?")[:30],
                "rev_ge": round(r.rev, 2),
                "cost_ge": round(r.cost, 2),
                "profit_ge": round(r.profit, 2),
                "margin_pct": r.margin_pct,
                "rows": r.rows,
                "MAX_rev_oracle": round(mx_rev, 2) if mx_rev is not None else "",
                "MAX_margin_oracle": round(mx_margin, 2) if mx_margin is not None else "",
                "rev_gap_%": round(gap, 1) if gap is not None else "",
                "badge": badge,
            })

    out_df = pd.DataFrame(rows_out).sort_values(["store", "rev_ge"], ascending=[True, False])
    out_path = ROOT / "HANDOFF_ARCHIVE" / "supplier_attribution_v2_verification.csv"
    out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n→ Wrote {out_path}")

    # Summary
    print("\n=== SUMMARY (dvabzu only — has MAX oracle) ===")
    dv = out_df[out_df["store"] == "დვაბზუ"]
    with_oracle = dv[dv["badge"] != ""]
    counts = with_oracle["badge"].value_counts().to_dict()
    print(f"  ✓ within 2%:   {counts.get('✓', 0)}")
    print(f"  🟢 within 5%:   {counts.get('🟢', 0)}")
    print(f"  🟡 within 15%:  {counts.get('🟡', 0)}")
    print(f"  🔴 over 15%:    {counts.get('🔴', 0)}")
    print(f"  total compared: {len(with_oracle)}")
    print()
    print("=== Top 20 by revenue (dvabzu) ===")
    cols = ["badge", "supplier", "rev_ge", "MAX_rev_oracle", "rev_gap_%", "margin_pct", "MAX_margin_oracle"]
    print(dv[cols].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
