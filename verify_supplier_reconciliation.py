"""
ერთი მომწოდებლის (საგადასახადო ID) დამოუკიდებელი შემოწმება:
- RS ეფექტური ჯამი (იგივე წესი, რაც generate_dashboard_data.run)
- BOG/TBC: ხაზ-ხაზად იგივე ლოგიკით გამოთვლილი total vs get_bank_payments[sid]
"""
import contextlib
import io
import json
import os
import sys

import glob
import pandas as pd

import generate_dashboard_data as g


def rs_effective_for_tax_id(rs_files, tax_id: str) -> float:
    all_rs = []
    for f in rs_files:
        try:
            all_rs.append(pd.read_excel(f))
        except Exception:
            pass
    if not all_rs:
        return 0.0
    df = pd.concat(all_rs, ignore_index=True)
    df = df[df['ორგანიზაცია'].astype(str).str.contains(tax_id, na=False)].copy()
    if df.empty:
        return 0.0
    df['უკან დაბრუნება (ფლეგი)'] = df['ტიპი'].astype(str).str.contains(
        'უკან დაბრუნება', case=False, na=False
    )
    df['გაუქმებული (ფლეგი)'] = df['სტატუსი'].astype(str).str.contains(
        'გაუქმებული', case=False, na=False
    )

    def get_nominal(row):
        # იგივე ლოგიკა, რაც generate_dashboard_data.run-ში
        return (
            pd.to_numeric(row['თანხა'], errors='coerce')
            if not pd.isna(row['თანხა'])
            else 0
        )

    def get_effective(row):
        val = get_nominal(row)
        if pd.isna(val):
            val = 0.0
        val = float(val)
        if row['გაუქმებული (ფლეგი)']:
            return 0.0
        if row['უკან დაბრუნება (ფლეგი)']:
            v = float(val) if not pd.isna(val) else 0.0
            return v if v < 0 else -v
        return val

    return float(df.apply(get_effective, axis=1).sum())


def manual_bank_total_for_id(
    rs_files,
    tax_id: str,
    bog_receiver_map=None,
    manual_payments_by_id=None,
) -> tuple[dict, float]:
    """იგივე ბიჯები, რაც get_bank_payments, მაგრამ მხოლოდ ერთი ID-ისთვის ჯამი (+ manual_payments.csv)."""
    if bog_receiver_map is None:
        bog_receiver_map = g.get_merged_bog_receiver_map(rs_files)
    if manual_payments_by_id is None:
        manual_payments_by_id = g.load_manual_payments()
    name_to_id = g.build_name_to_id_map(rs_files)
    b = {'bog_id': 0.0, 'bog_name': 0.0, 'tbc_id': 0.0, 'tbc_name': 0.0}
    cn = {'bog_id': 0, 'bog_name': 0, 'tbc_id': 0, 'tbc_name': 0}

    for f in sorted(glob.glob('Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx')):
        try:
            header_idx = g.find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = df.columns
            debit_col = next(
                (c for c in cols if 'დებეტი' in str(c) and 'ბრუნვა' not in str(c)), None
            )
            id_col = next(
                (c for c in cols if 'მიმღების საიდენტიფიკაციო' in str(c)), None
            )
            name_col = next(
                (c for c in cols if 'მიმღების დასახელება' in str(c)), None
            )
            desc_col = next(
                (c for c in cols if 'ოპერაციის შინაარსი' in str(c)), None
            )
            if not debit_col:
                continue
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors='coerce')
                if pd.isna(amt) or amt <= 0:
                    continue
                rec_id = g.clean_id(row[id_col]) if id_col else None
                rec_id = g.canonical_tax_id_from_bog_receiver(rec_id, bog_receiver_map)
                if rec_id and rec_id.isdigit() and len(rec_id) >= 5:
                    if rec_id == tax_id:
                        b['bog_id'] += float(amt)
                        cn['bog_id'] += 1
                    continue
                matched_id = None
                if name_col and pd.notna(row[name_col]) and not g.skip_name_only_supplier_match(
                    row[name_col]
                ):
                    matched_id = g.match_partner_to_id(str(row[name_col]), name_to_id)
                if not matched_id and desc_col and pd.notna(row[desc_col]) and not g.skip_name_only_supplier_match(row[desc_col]):
                    matched_id = g.match_partner_to_id(str(row[desc_col]), name_to_id)
                if matched_id == tax_id:
                    b['bog_name'] += float(amt)
                    cn['bog_name'] += 1
        except Exception:
            pass

    for f in sorted(glob.glob('Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx')):
        try:
            header_idx = g.find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = df.columns
            debit_col = next((c for c in cols if 'გასული თანხა' in str(c)), None)
            id_col = next(
                (c for c in cols if 'პარტნიორის საგადასახადო კოდი' in str(c)), None
            )
            partner_col = next((c for c in cols if c == 'პარტნიორი'), None)
            if not debit_col:
                continue
            df = df[~df[debit_col].astype(str).str.contains('Paid|Out|Amount', case=False, na=False)]
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors='coerce')
                if pd.isna(amt) or amt <= 0:
                    continue
                rec_id = g.clean_id(row[id_col]) if id_col else None
                if rec_id and rec_id.isdigit() and len(rec_id) >= 5:
                    if rec_id == tax_id:
                        b['tbc_id'] += float(amt)
                        cn['tbc_id'] += 1
                    continue
                if partner_col:
                    if g.skip_name_only_supplier_match(row[partner_col]):
                        continue
                    matched_id = g.match_partner_to_id(str(row[partner_col]), name_to_id)
                    if matched_id == tax_id:
                        b['tbc_name'] += float(amt)
                        cn['tbc_name'] += 1
        except Exception:
            pass

    csv_extra = float(manual_payments_by_id.get(tax_id, 0) or 0)
    total = sum(b.values()) + csv_extra
    out = {**b, '_counts': cn, '_manual_total': total}
    if csv_extra:
        out['_manual_csv'] = csv_extra
    return out, total


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    rs_files = sorted(glob.glob('Financial_Analysis/რს ზედნადები/*.xls'))
    args = sys.argv[1:]
    tax_ids = args if args else ['200179118', '445404232']

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        payments, _, _ = g.get_bank_payments(rs_files)

    bog_receiver_map = g.get_merged_bog_receiver_map(rs_files)
    manual_csv = g.load_manual_payments()

    with open('rs-dashboard/public/data.json', 'r', encoding='utf-8') as f:
        dash = json.load(f)

    for tax_id in tax_ids:
        print('=' * 72)
        print(f'საგადასახადო ID: {tax_id}')
        rs_eff = rs_effective_for_tax_id(rs_files, tax_id)
        detail, manual_total = manual_bank_total_for_id(
            rs_files, tax_id, bog_receiver_map, manual_csv
        )
        counts = detail.pop('_counts')
        detail.pop('_manual_total')
        csv_x = detail.pop('_manual_csv', 0.0)
        from_module = float(payments.get(tax_id, 0.0))
        diff = round(manual_total - from_module, 2)

        print(f'  RS ეფექტური ჯამი:     {rs_eff:,.2f} ₾')
        print(
            f'  BOG ID / სახელი:      {detail["bog_id"]:,.2f} / {detail["bog_name"]:,.2f} ₾ '
            f'({counts["bog_id"]}+{counts["bog_name"]} ხაზი)'
        )
        print(
            f'  TBC ID / სახელი:      {detail["tbc_id"]:,.2f} / {detail["tbc_name"]:,.2f} ₾ '
            f'({counts["tbc_id"]}+{counts["tbc_name"]} ხაზი)'
        )
        if csv_x:
            print(f'  manual_payments.csv:  {csv_x:,.2f} ₾')
        print(f'  ხელით ბანკის ჯამი:   {manual_total:,.2f} ₾')
        print(f'  get_bank_payments:    {from_module:,.2f} ₾')
        print(f'  სხვაობა:              {diff:,.2f} ₾', '(OK)' if abs(diff) < 0.02 else '❌ FAIL')

        sup = next(
            (s for s in dash['suppliers'] if tax_id in str(s.get('ორგანიზაცია', ''))), None
        )
        if sup:
            tp = float(sup.get('total_paid') or 0)
            print(f'  data.json total_paid: {tp:,.2f} ₾', end='')
            if abs(tp - from_module) < 0.02:
                print(' (matches module)')
            else:
                print(f' ❌ vs module {abs(tp-from_module):.2f}')


if __name__ == '__main__':
    main()
