"""
BOG „მიმღების საიდენტიფიკაციო" vs RS საგადასახადო კოდი — აღმოჩენა საეჭვო ID-ებისა (როგორც თოლია 60001101925).
გაშვება პროექტის root-იდან.
"""
import os
import re
from collections import defaultdict

import glob
import pandas as pd

import generate_dashboard_data as g

SCRIPT = os.path.dirname(os.path.abspath(__file__))


def extract_rs_tax_id(org_str: str):
    m = re.search(r"\((\d+)", str(org_str))
    return m.group(1) if m else None


def main():
    os.chdir(SCRIPT)
    rs_files = sorted(glob.glob("Financial_Analysis/რს ზედნადები/*.xls"))
    bog_files = sorted(glob.glob("Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx"))

    if not rs_files or not bog_files:
        print("RS ან BOG ფაილები არ მოიძებნა.")
        return 1

    dfs = []
    for f in rs_files:
        dfs.append(pd.read_excel(f))
    rdf = pd.concat(dfs, ignore_index=True)

    rs_tax_ids = set()
    for org in rdf["ორგანიზაცია"].dropna().unique():
        tid = extract_rs_tax_id(org)
        if tid:
            rs_tax_ids.add(tid)

    name_to_id = g.build_name_to_id_map(rs_files)
    bog_merged = g.get_merged_bog_receiver_map(rs_files)

    # raw BOG id -> names, amount, count
    by_raw: dict[str, dict] = defaultdict(
        lambda: {"names": set(), "amt": 0.0, "n": 0}
    )

    for f in bog_files:
        h = g.find_header_row(f)
        d = pd.read_excel(f, header=h)
        cols = d.columns
        dc = next(
            (c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)),
            None,
        )
        if not dc:
            continue
        ic = next(
            (c for c in cols if "მიმღების საიდენტიფიკაციო" in str(c)),
            None,
        )
        nc = next(
            (c for c in cols if "მიმღების დასახელება" in str(c)),
            None,
        )
        for _, row in d.iterrows():
            amt = pd.to_numeric(row[dc], errors="coerce")
            if pd.isna(amt) or amt <= 0:
                continue
            raw = g.clean_id(row[ic]) if ic else None
            if not raw or not raw.isdigit() or len(raw) < 5:
                continue
            nm = str(row[nc]).strip() if nc and pd.notna(row[nc]) else ""
            by_raw[raw]["names"].add(nm)
            by_raw[raw]["amt"] += float(amt)
            by_raw[raw]["n"] += 1

    print("=" * 78)
    print("1. BOG→RS რუკა (ავტო ინფერი + ხელით override generate_dashboard_data-ში)")
    print("=" * 78)
    for k, v in sorted(bog_merged.items(), key=lambda kv: kv[0]):
        tag = "ხელით" if k in g.BOG_RECEIVER_ID_TO_RS_TAX_ID else "ავტო"
        info = by_raw.get(k, {})
        names = info.get("names", set()) if info else set()
        print(
            f"  [{tag}] {k} → {v} | BOG ხაზები: {info.get('n',0)} | ჯამი {info.get('amt',0):,.2f} ₾"
        )
        if names:
            print(f"      სახელები: {names}")

    print()
    print("=" * 78)
    print("2. BOG ID არა-RS, რომელსაც ავტორუკა არ მიაკვრის — name_to_id-ით ზუსტი ერთი სახელი")
    print("   (დარჩენილი ხელით / ალიასები)")
    print("=" * 78)

    candidates = []
    ambiguous = []
    for raw, info in sorted(by_raw.items(), key=lambda x: -x[1]["amt"]):
        if raw in bog_merged:
            continue
        if raw in rs_tax_ids:
            continue
        names = {n for n in info["names"] if n and n.lower() != "nan"}
        if len(names) != 1:
            ambiguous.append((raw, info["amt"], info["n"], names))
            continue
        only_name = next(iter(names))
        key = g.normalize_name(only_name)
        hit = name_to_id.get(key) if key else None
        if not hit:
            continue
        if hit == raw:
            continue
        candidates.append(
            {
                "bog_raw_id": raw,
                "rs_tax_id": hit,
                "name": only_name,
                "amt": info["amt"],
                "n": info["n"],
            }
        )

    candidates.sort(key=lambda x: -x["amt"])
    for c in candidates:
        print(
            f"  {c['bog_raw_id']} → {c['rs_tax_id']} ?  ({c['n']} ხაზი, {c['amt']:,.2f} ₾)  |  {c['name'][:65]}"
        )

    if not candidates:
        print("  (არაფერი — ან ყველა BOG ID უკვე RS-შია, ან სახელით ზუსტი გასაღები არ ემთხვევა)")

    print()
    print("=" * 78)
    print("3. BOG ID არა-RS + ერთზე მეტი სხვადასხვა სახელი (ამბივალენტური — არ ჩავთვლით ავტომაფში)")
    print("=" * 78)
    amb = [a for a in ambiguous if a[1] > 0]
    amb.sort(key=lambda x: -x[1])
    shown = 0
    for raw, amt, n, names in amb[:25]:
        if raw in rs_tax_ids:
            continue
        print(f"  {raw}: {n} ხაზი, {amt:,.2f} ₾ | სახელები ({len(names)}): …")
        for nm in list(names)[:3]:
            print(f"      · {nm[:70]}")
        shown += 1
    if not shown:
        print("  (არაფერი ან ყველა დარჩენილი უკვე RS ID)")
    else:
        print(f"  ნაჩვენებია max 25 / სულ ამბიგუობა: {len(amb)}")

    print()
    print("=" * 78)
    print("4. შეჯამება")
    print("=" * 78)
    total_bog_id_debits = sum(x["amt"] for x in by_raw.values())
    in_rs = sum(
        x["amt"] for raw, x in by_raw.items() if raw in rs_tax_ids
    )
    mapped = sum(by_raw[k]["amt"] for k in bog_merged if k in by_raw)
    orphans = sum(
        x["amt"]
        for raw, x in by_raw.items()
        if raw not in rs_tax_ids and raw not in bog_merged
    )
    print(f"  BOG დებეტი (ანგარიშით ID≥5 ციფრი): ჯამი ~{total_bog_id_debits:,.2f} ₾")
    print(f"  მათგან ID პირდაპირ RS საგადასახადოში:     ~{in_rs:,.2f} ₾")
    print(f"  რუკით გადაყვანილი BOG→RS (ავტო+ხელით): ~{mapped:,.2f} ₾")
    print(f"  დარჩენილი „სხვა“ ID (საეჭვო/ორფანი):     ~{orphans:,.2f} ₾")
    print(f"  ახალი კანდიდატი რუკისთვის (სექცია 2):   {len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
