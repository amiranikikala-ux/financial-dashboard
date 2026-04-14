"""
სრული აუდიტი: RS წესები, ბანკის ხაზების ბალანსი, data.json vs ცოცხალი გამოთვლა.
გაუშვი პროექტის root-იდან:  venv\\Scripts\\python.exe audit_all.py
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys

import glob
import pandas as pd

import generate_dashboard_data as g
from dashboard_pipeline.waybill_amounts import get_nominal, get_effective, get_returned

TOL = 0.02  # ლარის მრგვალი შეცდომა


def hr(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def ok(cond: bool) -> str:
    return "OK" if cond else "FAIL"


def main() -> int:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    fails = 0

    rs_paths = sorted(glob.glob("Financial_Analysis/რს ზედნადები/*.xls"))
    bog_paths = sorted(glob.glob("Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx"))
    tbc_paths = sorted(glob.glob("Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx"))

    hr("0. ფაილები")
    print(f"  RS .xls:   {len(rs_paths)}")
    print(f"  BOG .xlsx: {len(bog_paths)}")
    print(f"  TBC .xlsx: {len(tbc_paths)}")
    if not rs_paths:
        print("  ❌ RS ფაილი არ არის — აუდიტი ვერ გაგრძელდება")
        return 1

    # --- RS concat + იგივე get_nominal / get_effective რაც generate_dashboard_data ---
    all_rs = []
    for f in rs_paths:
        try:
            df = pd.read_excel(f)
            df["_source_file"] = os.path.basename(f)
            all_rs.append(df)
        except Exception as e:
            print(f"  ❌ RS წაკითხვა {f}: {e}")
            fails += 1
    df = pd.concat(all_rs, ignore_index=True)

    required = ["ორგანიზაცია", "ზედნადები", "თანხა", "ტიპი", "სტატუსი"]
    missing = [c for c in required if c not in df.columns]
    hr("1. RS სვეტები")
    if missing:
        print(f"  ❌ აკლია: {missing}")
        fails += 1
    else:
        print(f"  {ok(True)} საჭირო სვეტები არსებობს")

    df["უკან დაბრუნება (ფლეგი)"] = df["ტიპი"].astype(str).str.contains(
        "უკან დაბრუნება", case=False, na=False
    )
    df["გაუქმებული (ფლეგი)"] = df["სტატუსი"].astype(str).str.contains(
        "გაუქმებული", case=False, na=False
    )

    df["_eff"] = df.apply(get_effective, axis=1)
    df["_nom"] = df.apply(get_nominal, axis=1)
    df["_ret"] = df.apply(get_returned, axis=1)

    hr("2. RS „უკან დაბრუნება“ ნიშანი")
    ret_mask = df["უკან დაბრუნება (ფლეგი)"] & ~df["გაუქმებული (ფლეგი)"]
    pos_on_return = (pd.to_numeric(df.loc[ret_mask, "თანხა"], errors="coerce") > 0).sum()
    print(f"  დაბრუნების ხაზები (არა გაუქმებული): {int(ret_mask.sum())}")
    print(f"  მათგან დადებითი თანხით: {int(pos_on_return)}  (ლოგიკა: უნდა იყოს 0)")
    if pos_on_return > 0:
        print("  ⚠️  ზოგი დაბრუნება დადებითია — get_effective იყენებს -val")
        fails += 1
    else:
        print(f"  {ok(True)}")

    hr("3. RS აგრეგაცია vs ხაზ-ხაზად")
    grp = df.groupby("ორგანიზაცია", dropna=False).agg(
        n=("ზედნადები", "count"),
        sum_eff=("_eff", "sum"),
        sum_nom=("_nom", "sum"),
        sum_ret=("_ret", "sum"),
    )
    line_sum_eff = float(df["_eff"].sum())
    group_sum_eff = float(grp["sum_eff"].sum())
    if abs(line_sum_eff - group_sum_eff) > TOL:
        print(f"  ❌ ეფექტური ჯამი: ხაზები {line_sum_eff:,.2f} ≠ groupby {group_sum_eff:,.2f}")
        fails += 1
    else:
        print(f"  {ok(True)} ეფექტური ჯამი ხაზებისა და groupby-ის ემთხვევა: {line_sum_eff:,.2f} ₾")

    hr("4. RS ორგანიზაცია → საიდენტ. კოდი")
    def extract_id(org):
        m = re.search(r"\((\d+)", str(org))
        return m.group(1) if m else None

    no_id = df["ორგანიზაცია"].dropna().unique()
    no_id = [str(o) for o in no_id if not extract_id(o)]
    print(f"  უნიკალური ორგანიზაცია სულ: {df['ორგანიზაცია'].nunique()}")
    print(f"  სადაც ბრჭყალებში ID ვერ ამოიკითხა: {len(no_id)}")
    if no_id:
        for s in no_id[:15]:
            print(f"      · {s[:70]}")
        if len(no_id) > 15:
            print(f"      … +{len(no_id) - 15}")

    hr("5. ბანკი: ხაზების ბალანსი (დაკრეფილი = ID+სახელი+missed)")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        payments, _, _, _, _ = g.get_bank_payments(rs_paths)

    # ერთხელ name map
    nmap = g.build_name_to_id_map(rs_paths)
    bog_merged = g.get_merged_bog_receiver_map(rs_paths)

    def bog_sums_fast():
        counted_id = counted_name = missed_amt = 0.0
        n_id = n_name = n_miss = 0
        for f in bog_paths:
            try:
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
                desc = next(
                    (c for c in cols if "ოპერაციის შინაარსი" in str(c)),
                    None,
                )
                for _, row in d.iterrows():
                    amt = pd.to_numeric(row[dc], errors="coerce")
                    if pd.isna(amt) or amt <= 0:
                        continue
                    rid = g.clean_id(row[ic]) if ic else None
                    rid = g.canonical_tax_id_from_bog_receiver(rid, bog_merged)
                    if rid and rid.isdigit() and len(rid) >= 5:
                        counted_id += float(amt)
                        n_id += 1
                        continue
                    mid = None
                    if nc and pd.notna(row[nc]) and not g.skip_name_only_supplier_match(
                        row[nc]
                    ):
                        mid = g.match_partner_to_id(str(row[nc]), nmap)
                    if not mid and desc and pd.notna(row[desc]) and not g.skip_name_only_supplier_match(row[desc]):
                        mid = g.match_partner_to_id(str(row[desc]), nmap)
                    if mid:
                        counted_name += float(amt)
                        n_name += 1
                    else:
                        missed_amt += float(amt)
                        n_miss += 1
            except Exception:
                pass
        return counted_id, counted_name, missed_amt, n_id, n_name, n_miss

    bi, bn, bm, ni, nn, nm = bog_sums_fast()
    bog_total_processed = bi + bn + bm
    print(
        f"  BOG დათვლილი: ID {ni} ხაზი ({bi:,.2f} ₾) + სახელი {nn} ({bn:,.2f}) + missed {nm} ({bm:,.2f})"
    )
    print(f"  BOG სულ დათვლილი ჯამი: {bog_total_processed:,.2f} ₾")

    def tbc_sums_fast():
        counted_id = counted_name = missed_amt = 0.0
        n_id = n_name = n_miss = 0
        for f in tbc_paths:
            try:
                h = g.find_header_row(f)
                d = pd.read_excel(f, header=h)
                cols = d.columns
                dc = next((c for c in cols if "გასული თანხა" in str(c)), None)
                if not dc:
                    continue
                ic = next(
                    (c for c in cols if "პარტნიორის საგადასახადო კოდი" in str(c)),
                    None,
                )
                pc = next((c for c in cols if c == "პარტნიორი"), None)
                d = d[
                    ~d[dc]
                    .astype(str)
                    .str.contains("Paid|Out|Amount", case=False, na=False)
                ]
                for _, row in d.iterrows():
                    amt = pd.to_numeric(row[dc], errors="coerce")
                    if pd.isna(amt) or amt <= 0:
                        continue
                    rid = g.clean_id(row[ic]) if ic else None
                    if rid and rid.isdigit() and len(rid) >= 5:
                        counted_id += float(amt)
                        n_id += 1
                        continue
                    if pc:
                        if g.skip_name_only_supplier_match(row[pc]):
                            missed_amt += float(amt)
                            n_miss += 1
                        else:
                            mid = g.match_partner_to_id(str(row[pc]), nmap)
                            if mid:
                                counted_name += float(amt)
                                n_name += 1
                            else:
                                missed_amt += float(amt)
                                n_miss += 1
            except Exception:
                pass
        return counted_id, counted_name, missed_amt, n_id, n_name, n_miss

    ti, tn, tm, tti, ttn, ttm = tbc_sums_fast()
    tbc_total_processed = ti + tn + tm
    print(
        f"  TBC დათვლილი: ID {tti} ({ti:,.2f}) + სახელი {ttn} ({tn:,.2f}) + missed {ttm} ({tm:,.2f})"
    )
    print(f"  TBC სულ დათვლილი ჯამი: {tbc_total_processed:,.2f} ₾")

    pay_sum = sum(payments.values())
    # payments-ში ერთი ID ორივე ბანკიდან იჯამება — ეს ნორმაა
    print(f"  get_bank_payments ლექსიკონის ჯამი: {pay_sum:,.2f} ₾")

    hr("6. data.json vs RS+ბანკი")
    json_path = os.path.join("rs-dashboard", "public", "data.json")
    if not os.path.isfile(json_path):
        print(f"  ❌ არ არსებობს: {json_path} — გაუშვი generate_dashboard_data.py")
        fails += 1
    else:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        suppliers = data.get("suppliers", [])
        waybills = data.get("waybills", [])

        json_eff_sum = sum(float(s.get("total_effective") or 0) for s in suppliers)
        json_paid_sum = sum(float(s.get("total_paid") or 0) for s in suppliers)
        rs_eff_match = abs(json_eff_sum - line_sum_eff) < TOL * max(1, len(suppliers))
        print(
            f"  suppliers რიცხვი: {len(suppliers)} | waybills ჩანაწერი: {len(waybills)}"
        )
        print(
            f"  JSON total_effective ჯამი: {json_eff_sum:,.2f} | RS live ჯამი: {line_sum_eff:,.2f}  [{ok(rs_eff_match)}]"
        )
        if not rs_eff_match:
            fails += 1

        mapped_paid = sum(
            float(payments.get(extract_id(s.get("ორგანიზაცია")), 0) or 0)
            for s in suppliers
        )
        json_paid_round = sum(float(s.get("total_paid") or 0) for s in suppliers)
        paid_match = abs(mapped_paid - json_paid_round) < TOL * max(1, len(suppliers))
        print(
            f"  JSON total_paid ჯამი: {json_paid_round:,.2f} | payments[ID]-ით იგივე მომწოდებლებზე: {mapped_paid:,.2f}  [{ok(paid_match)}]"
        )
        if not paid_match:
            fails += 1

        debt_errors = 0
        for s in suppliers:
            te = float(s.get("total_effective") or 0)
            tp = float(s.get("total_paid") or 0)
            td = float(s.get("total_debt") or 0)
            if abs(td - (te - tp)) > TOL:
                debt_errors += 1
        print(
            f"  დავალიანება=რეალური-გადახდილი: შეცდომის მქონე მომწოდებელი {debt_errors} / {len(suppliers)}  [{ok(debt_errors == 0)}]"
        )
        if debt_errors:
            fails += 1

        # JSON მომწოდებლის ეფექტური vs groupby
        mism = 0
        for org, row in grp.iterrows():
            sid = extract_id(org)
            js = next(
                (
                    float(x.get("total_effective") or 0)
                    for x in suppliers
                    if x.get("ორგანიზაცია") == org
                ),
                None,
            )
            if js is None:
                continue
            if abs(js - float(row["sum_eff"])) > TOL:
                mism += 1
        print(
            f"  JSON total_effective vs RS groupby იდენტური სახელით: შეუსაბამო {mism}  [{ok(mism == 0)}]"
        )
        if mism:
            fails += 1

    hr("7. შეჯამება")
    if fails == 0:
        print("  ✅ აუდიტი: ყველა ავტომატური შემოწმება გადის (TOL={:.2f} ₾)".format(TOL))
        print("     ხელით გადასამოწმებელი: BOG/TBC missed ხაზები, ID-გარეშე ორგანიზაცია, fuzzy სახელით შეჯახება.")
        return 0
    print(f"  ❌ აუდიტი: {fails} ჯგუფი/შემოწმება ვერ გაივლის — ზემოთ იპოვე FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
