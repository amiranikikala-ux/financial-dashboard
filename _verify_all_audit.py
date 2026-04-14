"""
ერთჯერადი სრული შემოწმება — წაშალეთ გაშვების შემდეგ თუ არ გჭირდებათ.
"""
import json
import os
import sys

import pandas as pd

import generate_dashboard_data as g
from dashboard_pipeline.waybill_amounts import get_effective

TOL = 0.02
ERR = []


def fail(msg):
    ERR.append(msg)
    print(f"  [FAIL] {msg}")


def ok(msg):
    print(f"  [OK] {msg}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print("=== 1) Python სინტაქსი ===")
    path = os.path.join(script_dir, "generate_dashboard_data.py")
    try:
        with open(path, encoding="utf-8") as f:
            compile(f.read(), path, "exec")
        ok("generate_dashboard_data.py კომპილირდება")
    except SyntaxError as e:
        fail(f"syntax: {e}")
        return 1

    rs_files = g.list_rs_waybill_files()
    bog_files = g.list_bog_bank_statement_xlsx()
    tbc_files = g.list_tbc_bank_statement_xlsx()

    print("\n=== 2) ბანკი: ჯამური რეკონცილიაცია ===")
    payments, unmatched, rec_ok, _, status_buckets = g.get_bank_payments(
        rs_files, reconciliation_exit_on_fail=False
    )
    matched_sum = sum(float(v) for v in payments.values())
    unmatched_sum = sum(float(r.get("თანხა") or 0) for r in unmatched)
    non_supplier_sum = sum(
        float(r.get("amount") or 0) for r in status_buckets.get("non_supplier", [])
    )
    skipped_sum = sum(
        float(r.get("amount") or 0) for r in status_buckets.get("skipped_explicit", [])
    )
    bank_excel = g._bank_positive_debit_total_ge()
    accounted = matched_sum + unmatched_sum + non_supplier_sum + skipped_sum
    delta = bank_excel - accounted
    if abs(delta) > TOL:
        fail(
            f"რეკონცილიაცია: Excel {bank_excel:.2f} vs მიბმ+არამიბმ+non_supplier+skipped {accounted:.2f}, delta {delta:.2f}"
        )
    else:
        ok(f"Excel გასავალი {bank_excel:,.2f} = მიბმული+არამიბმული+non_supplier+skipped (delta {delta:.4f})")
    if not rec_ok:
        fail("verify_bank_debit_totals დააბრუნა False")
    else:
        ok("verify_bank_debit_totals True")

    print("\n=== 3) ბანკი: ფაილ-ფაილობით (იგივე ლოგიკა) ===")
    name_to_id = g.build_name_to_id_map(rs_files)
    _bog_auto = g.infer_bog_receiver_id_to_rs_tax_id(rs_files)
    bog_receiver_map = {**_bog_auto, **g.BOG_RECEIVER_ID_TO_RS_TAX_ID}

    def bog_one(path):
        hr = g.find_header_row(path)
        df = pd.read_excel(path, header=hr)
        cols = list(df.columns)
        debit_col = next(
            (c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)), None
        )
        id_col = next(
            (c for c in cols if "მიმღების საიდენტიფიკაციო" in str(c)), None
        )
        name_col = next(
            (c for c in cols if "მიმღების დასახელება" in str(c)), None
        )
        desc_col = next(
            (c for c in cols if "ოპერაციის შინაარსი" in str(c)), None
        )
        purpose_col = g._find_excel_column_danishnuleba(cols)
        ex = m = u = 0.0
        if not debit_col:
            return ex, m, u
        for _, row in df.iterrows():
            amt = pd.to_numeric(row[debit_col], errors="coerce")
            if pd.isna(amt) or amt <= 0:
                continue
            ex += float(amt)
            raw_rec_id = g.clean_id(row[id_col]) if id_col else None
            rec_id = g.canonical_tax_id_from_bog_receiver(raw_rec_id, bog_receiver_map)
            mid = None
            if rec_id and rec_id.isdigit() and len(rec_id) >= 5:
                mid = rec_id
            else:
                if name_col and pd.notna(row[name_col]) and not g.skip_name_only_supplier_match(
                    row[name_col]
                ):
                    mid = g.match_partner_to_id(str(row[name_col]), name_to_id)
                if not mid and desc_col and pd.notna(row[desc_col]) and not g.skip_name_only_supplier_match(
                    row[desc_col]
                ):
                    mid = g.match_partner_to_id(str(row[desc_col]), name_to_id)
                if not mid and purpose_col and pd.notna(row[purpose_col]) and not g.skip_name_only_supplier_match(
                    row[purpose_col]
                ):
                    mid = g.match_partner_to_id(str(row[purpose_col]), name_to_id)
                if not mid:
                    acct_col = next(
                        (c for c in cols if "მიმღების ანგარიშის ნომერი" in str(c)),
                        None,
                    )
                    if acct_col and pd.notna(row[acct_col]):
                        ib = g._normalize_iban_ge(row[acct_col])
                        if ib and ib in g.PARTNER_IBAN_TO_RS_TAX_ID:
                            mid = g.PARTNER_IBAN_TO_RS_TAX_ID[ib]
            if mid:
                m += float(amt)
            else:
                u += float(amt)
        return ex, m, u

    def tbc_one(path):
        hr = g.find_header_row(path)
        df = pd.read_excel(path, header=hr)
        cols = list(df.columns)
        debit_col = next((c for c in cols if "გასული თანხა" in str(c)), None)
        id_col = next(
            (c for c in cols if "პარტნიორის საგადასახადო კოდი" in str(c)), None
        )
        partner_col = g._find_tbc_partner_column(cols)
        purpose_col = g._find_excel_column_danishnuleba(cols)
        ex = m = u = 0.0
        if not debit_col:
            return ex, m, u
        df = df[
            ~df[debit_col]
            .astype(str)
            .str.contains("Paid|Out|Amount", case=False, na=False)
        ]
        for _, row in df.iterrows():
            amt = pd.to_numeric(row[debit_col], errors="coerce")
            if pd.isna(amt) or amt <= 0:
                continue
            ex += float(amt)
            rec_id = g.clean_id(row[id_col]) if id_col else None
            mid = None
            if rec_id and rec_id.isdigit() and len(rec_id) >= 5:
                mid = rec_id
            else:
                if partner_col and pd.notna(row[partner_col]) and not g.skip_name_only_supplier_match(
                    row[partner_col]
                ):
                    mid = g.match_partner_to_id(str(row[partner_col]), name_to_id)
                if not mid and purpose_col and pd.notna(row[purpose_col]) and not g.skip_name_only_supplier_match(
                    row[purpose_col]
                ):
                    mid = g.match_partner_to_id(str(row[purpose_col]), name_to_id)
                if not mid:
                    iban_col = next(
                        (c for c in cols if "პარტნიორის ანგარიში" in str(c)), None
                    )
                    if iban_col and pd.notna(row[iban_col]):
                        ib = g._normalize_iban_ge(row[iban_col])
                        if ib and ib in g.PARTNER_IBAN_TO_RS_TAX_ID:
                            mid = g.PARTNER_IBAN_TO_RS_TAX_ID[ib]
            if mid:
                m += float(amt)
            else:
                u += float(amt)
        return ex, m, u

    for f in bog_files:
        ex, m, u = bog_one(f)
        d = ex - (m + u)
        bn = os.path.basename(f)
        if abs(d) > TOL:
            fail(f"BOG per-file {bn}: delta {d:.4f}")
        else:
            ok(f"BOG {bn}: ex={ex:,.2f} = m+u")

    for f in tbc_files:
        ex, m, u = tbc_one(f)
        d = ex - (m + u)
        bn = os.path.basename(f)
        if abs(d) > TOL:
            fail(f"TBC per-file {bn}: delta {d:.4f}")
        else:
            ok(f"TBC {bn}: ex={ex:,.2f} = m+u")

    print("\n=== 4) BOG ინფერირებული ID → RS + ნიმუშის ხაზები ===")
    for bog_id, rs_id in sorted(_bog_auto.items()):
        in_rs = rs_id in g.collect_rs_tax_ids(rs_files)
        if not in_rs:
            fail(f"ინფერის RS ID {rs_id} არ ჩანს RS ორგანიზაციაში")
        else:
            ok(f"BOG raw {bog_id} → RS {rs_id}: ID არსებობს RS ექსელებში")
        # ნიმუში: ხაზები ამ BOG ID-ით
        sample_names = []
        line_amt = 0.0
        n_lines = 0
        for f in bog_files:
            hr = g.find_header_row(f)
            df = pd.read_excel(f, header=hr)
            cols = list(df.columns)
            debit_col = next(
                (c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)),
                None,
            )
            id_col = next(
                (c for c in cols if "მიმღების საიდენტიფიკაციო" in str(c)), None
            )
            name_col = next(
                (c for c in cols if "მიმღების დასახელება" in str(c)), None
            )
            if not debit_col or not id_col:
                continue
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors="coerce")
                if pd.isna(amt) or amt <= 0:
                    continue
                raw = g.clean_id(row[id_col])
                if raw != bog_id:
                    continue
                n_lines += 1
                line_amt += float(amt)
                if name_col and pd.notna(row[name_col]) and len(sample_names) < 3:
                    sample_names.append(str(row[name_col]).strip()[:80])
        ok(
            f"  ხაზები BOG ID={bog_id}: {n_lines} ცალი, ჯამი {line_amt:,.2f} GEL; სახელის ნიმუში: {sample_names}"
        )

    print("\n=== 5) TBC არამიბმული: ოპერაციის_შინაარსი არ უნდა დუბლირებდეს დანიშნულებას (ორივე იგივე ტექსტი) ===")
    dup_same = 0
    for r in unmatched:
        if r.get("ბანკი") != "TBC":
            continue
        op = str(r.get("ოპერაციის_შინაარსი", "") or "").strip()
        pu = str(r.get("დანიშნულება", "") or "").strip()
        if op and pu and op == pu:
            dup_same += 1
    if dup_same:
        fail(f"TBC არამიბმულში {dup_same} ხაზი: ოპ_შინაარსი == დანიშნულება (სავარაუდოდ ძველი ბაგი)")
    else:
        ok("TBC: არც ერთ ხაზზე არ დუბლირდება ოპ_შინაარსი == დანიშნულება (ორივე არაცარიელი)")

    print("\n=== 6) analyze_bank_unmatched_rows — არ უნდა ჩავარდეს ===")
    try:
        analysis = g.analyze_bank_unmatched_rows(unmatched)
        ok(
            f"ავტოანალიზი: {analysis['line_count']} ხაზი, categorized {analysis['categorized_total_ge']:,.2f} GEL"
        )
    except Exception as e:
        fail(f"analyze_bank_unmatched_rows: {e}")

    print("\n=== 7) RS ეფექტური ჯამი vs data.json ===")
    all_rs = []
    for f in rs_files:
        try:
            d = pd.read_excel(f)
            all_rs.append(d)
        except Exception as e:
            fail(f"RS read {f}: {e}")
    if all_rs:
        df = pd.concat(all_rs, ignore_index=True)
        df["უკან დაბრუნება (ფლეგი)"] = (
            df["ტიპი"].astype(str).str.contains("უკან დაბრუნება", case=False, na=False)
        )
        df["გაუქმებული (ფლეგი)"] = (
            df["სტატუსი"].astype(str).str.contains("გაუქმებული", case=False, na=False)
        )

        df["ეფექტური თანხა"] = df.apply(get_effective, axis=1)
        eff_py = float(df["ეფექტური თანხა"].sum())
        dj = os.path.join(script_dir, "rs-dashboard", "public", "data.json")
        if os.path.isfile(dj):
            with open(dj, encoding="utf-8") as fp:
                data = json.load(fp)
            sup = data.get("suppliers") or []
            te = sum(float(s.get("total_effective") or 0) for s in sup)
            d_eff = eff_py - te
            if abs(d_eff) > TOL:
                fail(f"RS ეფექტური Python {eff_py:,.2f} vs data.json suppliers {te:,.2f}, delta {d_eff:,.2f}")
            else:
                ok(f"RS ეფექტური = data.json suppliers ჯამი ({eff_py:,.2f} GEL)")
        else:
            ok(f"data.json არ არის — გამოტოვებული: {dj}")

    print("\n=== 8) სათაურის სტრიქონი: საბაზისო სვეტები ===")
    joined_bog = " ".join(str(c) for c in pd.read_excel(bog_files[0], header=g.find_header_row(bog_files[0]), nrows=0).columns)
    if "თარიღი" not in joined_bog or "დებეტი" not in joined_bog:
        fail(f"BOG {os.path.basename(bog_files[0])}: თარიღი/დებეტი header-ში")
    else:
        ok(f"BOG {os.path.basename(bog_files[0])}: თარიღი + დებეტი OK")
    joined_tbc = " ".join(str(c) for c in pd.read_excel(tbc_files[0], header=g.find_header_row(tbc_files[0]), nrows=0).columns)
    if "გასული თანხა" not in joined_tbc:
        fail(f"TBC {os.path.basename(tbc_files[0])}: გასული თანხა")
    else:
        ok(f"TBC {os.path.basename(tbc_files[0])}: გასული თანხა OK")

    print("\n=== შეჯამება ===")
    if ERR:
        print(f"ჩავარდნილი შემოწმებები: {len(ERR)}")
        for e in ERR:
            print(" -", e)
        return 1
    print("ყველა შემოწმება გავიდა დადებითად.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
