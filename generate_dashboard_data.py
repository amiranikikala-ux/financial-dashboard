import json
import os
import re
import shutil
import sys
import zipfile
from collections import defaultdict
from collections import Counter

import glob
import pandas as pd

# სამეურნეო ბლოკი — ბუღალტრული მნიშვნელობა: კომპანიის საქმიანობისთვის აუცილებელი ხარჯის მოძრაობა (ბანკის ტექსტის ფილტრით).
SAMURNEO_LEDGER_CLASS_KA = "კომპანიის საქმიანობისთვის აუცილებელი ხარჯი"
SAMURNEO_LABEL_KA = "საქმიანობისთვის აუცილებელი ხარჯი (სამეურნეო მოძრაობა)"
SAMURNEO_ACCOUNTING_NOTE_KA = (
    "ბუღალტრული მნიშვნელობა: კომპანიის საქმიანობისთვის აუცილებელი ხარჯის მოძრაობა. "
    "ტექნიკურად: ბანკის ხაზები ერთდება tbc_samurneo_patterns.json-ის ტექსტურ ფილტრთან; "
    "საგადასახადო/აუდიტის დასკვნა — პირველადი დოკუმენტაციით."
)
SAMURNEO_EXPENSE_DIRECTION_KA = f"{SAMURNEO_LEDGER_CLASS_KA} — გასვლა"
SAMURNEO_RETURN_DIRECTION_KA = f"{SAMURNEO_LEDGER_CLASS_KA} — დაბრუნება (შემოტანა)"

# არამიბმული ბანკი: „ვერ მიბმა RS მომწოდებელთან“ ≠ „არ არის ხარჯი“.
BANK_UNMATCHED_LEDGER_NOTE_KA = (
    "„არამიბმული ბანკი“ ნიშნავს: ხაზი ვერ მიება RS ზედნადების მომწოდებლის საგადასახადო ID-ს — "
    "არა ის, რომ ოპერაცია ხარჯი არაა. ბარათით შეძენა (მათ შორის სასურსაო/საკვები, ოფისი/საჩუქრები, მასალა, საკუთარი ქსელი), "
    "ნაღდი განაღდება/ბანკომატი, საბანკო ანგარიშის პაკეტი და მსგავსი ავტო-კატეგორიები "
    "ბუღალტრულად კომპანიის საქმიანობისთვის ხარჯებია; საგადასახადო დასკვნა — პირველადი დოკუმენტაციით."
)

# RS / ბიუჯეტი / სახელმწიფო ხაზინა — ერთი ოჯახის ოპერაციები სხვადასხვა ბლოკში.
TAX_TREASURY_CLUSTER_NOTE_KA = (
    "ბიუჯეტი/გადასახადები, RS-ზე საბიუჯეტო გადარიცხვები და საგადასახადო მოძრაობა ერთმანეთთანაა დაკავშირებული: "
    "ფული მიდის/მოდის სახელმწიფო ბიუჯეტის/RS-ის არხებით (მათ შორის ფინანსთა სამინისტროს სახაზინო სამსახური, ერთიანი კოდები, TRES/RS IBAN). "
    "დეშბორდზე: «საგადასახადო» — tax_flow_patterns.json; არამიბმულის ავტო-კატეგორიები — სხვა წესები."
)

TBC_EXPENSES_LEDGER_NOTE_KA = (
    "TBC კატეგორიები: accounting_role=state_treasury — სახელმწიფო ხაზინა/საბიუჯეტო არხი "
    "(ინკასო/ნაღდის საკომისიო, სახაზინო-ბიუჯეტის საკომისიო); "
    "operating_expense — კომპანიის საოპერაციო/საქმიანობის ხარჯები. "
    "სუფთა სხვაობაში ხარჯად ითვლება მხოლოდ operating_expense."
)

ACCOUNTING_ROLE_OPERATING = "operating_expense"
ACCOUNTING_ROLE_STATE_TREASURY = "state_treasury"


def _financial_analysis_path(*parts):
    """Financial_Analysis/ — აბსოლუტური გზა (არ არის დამოკიდებული cwd / os.chdir-ზე)."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "Financial_Analysis", *parts)


def _sorted_glob_in_financial(subdir, pattern):
    return sorted(glob.glob(os.path.join(_financial_analysis_path(subdir), pattern)))


def list_bog_bank_statement_xlsx():
    """BOG: ყველა `.xlsx` `Financial_Analysis/ბოგ ბანკი ამონაწერი/`-ში (სახელით დალაგებული)."""
    return _sorted_glob_in_financial("ბოგ ბანკი ამონაწერი", "*.xlsx")


def list_tbc_bank_statement_xlsx():
    """TBC: ყველა `.xlsx` `Financial_Analysis/თბს ბანკი ამონაწერი/`-ში (სახელით დალაგებული)."""
    return _sorted_glob_in_financial("თბს ბანკი ამონაწერი", "*.xlsx")


def list_rs_waybill_files():
    """
    RS ზედნადები: ყველა `.xlsx` და `.xls` `Financial_Analysis/რს ზედნადები/`-ში (ორივე ავტომატურად).
    """
    base = _financial_analysis_path("რს ზედნადები")
    merged = []
    merged.extend(glob.glob(os.path.join(base, "*.xlsx")))
    merged.extend(glob.glob(os.path.join(base, "*.xls")))
    return sorted(set(merged))


def write_suppliers_excel(suppliers_data, download_dir):
    """
    download/ მომწოდებლები_RS.xlsx — სვეტები დეშბორდის მიხედვით.
    ნაღდით გადახდა = manual_payments.csv (ბრაუზერის ჩანაწერი არა).
    """
    if not suppliers_data:
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print(
            "  [შეტყობინება] Excel-ისთვის დააყენე: pip install openpyxl"
        )
        return
    rows = []
    for r in suppliers_data:
        rows.append(
            {
                "ორგანიზაცია": r.get("ორგანიზაცია"),
                "რაოდენობა": r.get("waybills_count"),
                "ნომინალური": float(r.get("total_nominal") or 0),
                "რეალური ჯამი": float(r.get("total_effective") or 0),
                "ნაღდით გადახდა": float(r.get("manual_paid") or 0),
                "სულ გადახდილი": float(r.get("total_paid") or 0),
                "დავალიანება": float(r.get("total_debt") or 0),
            }
        )
    out_df = pd.DataFrame(rows)
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, "მომწოდებლები_RS.xlsx")
    out_df.to_excel(path, index=False, engine="openpyxl")
    print(f"  Excel → {path}")


def _excel_cell(row, col):
    if col is None or col not in row.index:
        return ""
    v = row[col]
    if pd.isna(v):
        return ""
    return str(v).strip()


def write_bank_unmatched_excel(unmatched_rows, download_dir):
    """
    download/ბანკი_არამიბმული_ხაზები.xlsx — BOG/TBC ხაზები, სადაც RS მომწოდებელთან მიბმა ვერ მოხერხდა.
    """
    if not unmatched_rows:
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print(
            "  [შეტყობინება] Excel-ისთვის დააყენე: pip install openpyxl"
        )
        return
    out_df = pd.DataFrame(unmatched_rows)
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, "ბანკი_არამიბმული_ხაზები.xlsx")
    out_df.to_excel(path, index=False, engine="openpyxl")
    total = sum(float(r.get("თანხა") or 0) for r in unmatched_rows)
    print(
        f"  Excel (არამიბმული ბანკი) → {path} "
        f"({len(unmatched_rows)} ხაზი, {total:,.2f} ₾)"
    )


def _rules_from_tbc_expense_json_for_unmatched(script_dir):
    """
    არამიბმულის ავტო-წესები — იგივე რიგი/იგივე id რაც collect_tbc_expense_categories-ში
    (IBAN → match_all_substrings → match_substrings OR), ფაილი: tbc_expense_categories.json.
    """
    path = os.path.join(script_dir, "Financial_Analysis", "tbc_expense_categories.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return []
    out = []
    for c in cfg.get("categories") or []:
        cid = str(c.get("id", "")).strip()
        if not cid:
            continue
        rule = {
            "id": cid,
            "label_ka": str(c.get("label_ka", "") or cid),
            "confidence": "high",
            "keywords": [
                str(p).lower()
                for p in c.get("match_substrings", [])
                if str(p).strip()
            ],
            "keywords_all": [
                str(p).lower()
                for p in c.get("match_all_substrings", [])
                if str(p).strip()
            ],
            "iban_hints": [
                str(p) for p in c.get("iban_hints", []) if str(p).strip()
            ],
        }
        if cid == "salary_payments":
            for extra in ("salary", "payroll", "ოზურგეთი", "დვაბზუ"):
                el = extra.lower()
                if el not in rule["keywords"]:
                    rule["keywords"].append(el)
        out.append(rule)
    return out


# მხოლოდ ის, რაც TBC ხარჯების JSON-ში არაა — იგივე პრიორიტეტის ბლოკში ბოლოში (ნახ. get_auto_unmatched_category_rules).
_EXTRA_AUTO_UNMATCHED_RULES = [
    {
        "id": "rent_known_landlord_ibans",
        "label_ka": "იჯარა — ცნობილი მიმღების ანგარიში (IBAN)",
        "confidence": "high",
        "keywords": [],
        "keywords_all": [],
        "iban_hints": [
            "GE60BG0000000667583800",
            "GE78BG0000000269727500",
            "GE81BG0000000890516000",
        ],
    },
    {
        "id": "cashback_foodmart",
        "label_ka": "ქეშბექი (შპს ფუდმარტი)",
        "confidence": "high",
        "keywords": [
            "ფუდმარტ",
            "foodmart",
            "ქეშბექ",
            "cashback",
            "cash back",
        ],
        "keywords_all": [],
        "iban_hints": [],
    },
    {
        "id": "rent_related",
        "label_ka": "იჯარა/ქონების ხარჯები",
        "confidence": "medium",
        "keywords": ["იჯარა", "rent", "lease", "ქონების", "არენდა"],
        "keywords_all": [],
        "iban_hints": [],
    },
    {
        "id": "tax_and_budget",
        "label_ka": "ბიუჯეტი / გადასახადები (სახელმწიფო — RS, ხაზინა)",
        "confidence": "medium",
        "keywords": [
            "საშემოსავლო",
            "გადასახად",
            "ბიუჯეტ",
            "revenue service",
            "rs.ge",
            "tax",
            "treasury",
            "ხაზინ",
            "tresge",
            "საბიუჯეტო",
        ],
        "keywords_all": [],
        "iban_hints": [],
    },
    {
        "id": "loan_and_finance",
        "label_ka": "სესხი/ფინანსური ვალდებულებები",
        "confidence": "medium",
        "keywords": ["სესხ", "loan", "credit", "interest", "პროცენტ"],
        "keywords_all": [],
        "iban_hints": [],
    },
    {
        "id": "cash_withdrawal",
        "label_ka": "ნაღდი განაღდება / ბანკომატი",
        "confidence": "high",
        "keywords": [
            "განაღდება",
            "atm",
            "bankomati",
            "ბანკომატი",
            "mcc:6011",
            "cash withdrawal",
            "bankomat",
        ],
        "keywords_all": [],
        "iban_hints": [],
    },
    {
        "id": "card_purchase_expense",
        "label_ka": "ბარათით შეძენა / საოპერაციო ხარჯი (სხვა მერჩანტი)",
        "confidence": "medium",
        "keywords": [
            "ოპერაცია:გადახდა - თანხა",
            "ობიექტი:",
            "gorgia",
            "jibe",
            "ltd me-va",
            "sakancelario",
        ],
        "keywords_all": [],
        "iban_hints": [],
    },
    {
        "id": "rs_budget_payments",
        "label_ka": "RS — საბიუჯეტო გადარიცხვები / სახელმწიფო ხაზინა",
        "confidence": "medium",
        "keywords": [
            "rs",
            "revenue service",
            "ge60bg0000000667583800rs",
            "ge04bg0000000201978600rs",
            "საბიუჯეტო გადარიცხვ",
            "ხაზინის ერთიანი",
            "გადასახადების ერთიანი კოდი",
            "tresge22",
            "სახაზინო",
        ],
        "keywords_all": [],
        "iban_hints": [],
    },
    {
        "id": "card_network_settlement",
        "label_ka": "ბარათების ქსელური ოპერაციები (VISA/MC)",
        "confidence": "low",
        "keywords": [
            "tbcbank_ის visa/mc",
            "tbcbank_ის ბანკომატებში",
            "visa ბარათებით სავაჭრო ობიექტებში",
            "mc ბარათებით",
        ],
        "keywords_all": [],
        "iban_hints": [],
    },
    {
        "id": "utilities_related",
        "label_ka": "კომუნალური და მობილური (ზოგადი)",
        "confidence": "medium",
        "keywords": [
            "კომუნალური",
            "utility",
            "ელექტრო",
            "წყალი",
            "გაზი",
            "მობილური",
            "ჯარიმ",
        ],
        "keywords_all": [],
        "iban_hints": [],
    },
    {
        "id": "bank_fees",
        "label_ka": "ბანკის საკომისიო/მომსახურება (სხვა)",
        "confidence": "high",
        "keywords": [
            "საკომისიო",
            "commission",
            "service fee",
            "მომსახურების",
            "bank fee",
            "processing fee",
        ],
        "keywords_all": [],
        "iban_hints": [],
    },
]

_cached_auto_unmatched_rules = None
_cached_auto_unmatched_script_dir = None


def get_auto_unmatched_category_rules(script_dir=None):
    """ერთი წყარო: tbc_expense_categories.json რიგით + დამატებითი წესები ბოლოში."""
    global _cached_auto_unmatched_rules, _cached_auto_unmatched_script_dir
    if script_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    if (
        _cached_auto_unmatched_rules is not None
        and _cached_auto_unmatched_script_dir == script_dir
    ):
        return _cached_auto_unmatched_rules
    rules = _rules_from_tbc_expense_json_for_unmatched(script_dir)
    rules.extend(_EXTRA_AUTO_UNMATCHED_RULES)
    _cached_auto_unmatched_rules = rules
    _cached_auto_unmatched_script_dir = script_dir
    return rules


BANK_UNMATCHED_CATEGORY_ORDER = {
    # collect_tbc_expense_categories-ის იგივე id-ები (tbc_expense_categories.json რიგით)
    "transfer_commission_fee": 9,
    "transit_ucc_communal": 10,
    "utility_telecom_bank_commission": 11,
    "transit_magti_mobile": 12,
    "pos_terminal_service_fee": 13,
    "incoming_packages_fee": 14,
    "incasso_cash_handling": 15,
    "treasury_budget_commission": 16,
    "bank_account_package_fee": 17,
    "bank_fees_software_service": 18,
    "card_retail_own_chain": 19,
    "card_mcc_groceries_5411": 20,
    "card_mcc_misc_retail_5943": 21,
    "card_mcc_building_supplies_5039": 22,
    "salary_payments": 23,
    # ხელით / ძველი data.json — იგივე რანჟირი ახალ id-ებთან
    "utility_transit_ucc": 10,
    "utility_transit_magti": 12,
    "pos_and_acquiring_fee": 13,
    "salary_related": 23,
    "cashback_foodmart": 28,
    "rent_related": 29,
    "tax_and_budget": 40,
    "loan_and_finance": 42,
    "utilities_related": 43,
    "rs_budget_payments": 44,
    "cash_withdrawal": 50,
    "card_purchase_expense": 70,
    "card_network_settlement": 75,
    "bank_fees": 80,
    "other_unclassified": 999,
}


def _bank_unmatched_sort_key(cat):
    # Keep dashboard stable: preferred business order first, then larger totals.
    cid = str(cat.get("id") or "")
    rank = int(BANK_UNMATCHED_CATEGORY_ORDER.get(cid, 500))
    total = float(cat.get("total_ge") or 0)
    return (rank, -total, cid)


def _unmatched_blob(row):
    fields = [
        row.get("მიმღები_სახელი", ""),
        row.get("ოპერაციის_შინაარსი", ""),
        row.get("დანიშნულება", ""),
        row.get("მიზეზი", ""),
        row.get("საგადასახადო_ID", ""),
        row.get("ფაილი", ""),
    ]
    return " ".join(str(x) for x in fields if x).lower()


def _rule_matches_unmatched(rule, blob_lower):
    """
    იგივე ლოგიკა რაც TBC ხარჯის კატეგორიაში: IBAN → keywords_all (AND) → keywords (OR).
    blob_lower — უკვე lowercase.
    """
    blob_lower = blob_lower or ""
    compact_upper = re.sub(r"\s+", "", blob_lower).upper()
    for ib in rule.get("iban_hints") or []:
        ibc = re.sub(r"\s+", "", str(ib).upper())
        if ibc and ibc in compact_upper:
            return True
    kw_all = [str(x).lower() for x in (rule.get("keywords_all") or []) if str(x).strip()]
    kw_any = [str(x).lower() for x in (rule.get("keywords") or []) if str(x).strip()]
    if kw_all:
        if all(k in blob_lower for k in kw_all):
            return True
        if not kw_any:
            return False
    if kw_any and any(k in blob_lower for k in kw_any):
        return True
    return False


def _auto_category_from_unmatched_row(row):
    blob = _unmatched_blob(row)
    blob_lower = blob.lower()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for rule in get_auto_unmatched_category_rules(script_dir):
        if _rule_matches_unmatched(rule, blob_lower):
            return rule["id"], rule["label_ka"], str(rule.get("confidence") or "medium")
    return "other_unclassified", "სხვა (მოუმზადებელი წესები)", "low"


def _extract_ibans_from_text(text):
    if not text:
        return []
    s = str(text).upper().replace(" ", "")
    return re.findall(r"GE\d{2}[A-Z0-9]{16,26}", s)


def _best_dynamic_key_for_row(row):
    blob = _unmatched_blob(row)
    ibans = _extract_ibans_from_text(blob)
    if ibans:
        return f"IBAN:{ibans[0]}", f"ავტო (IBAN {ibans[0]})"
    name = str(row.get("მიმღები_სახელი", "") or "").strip()
    if name and name != "-" and re.search(r"[\w\u10A0-\u10FF]", name):
        if re.fullmatch(r"[.\-_, ]+", name):
            name = ""
    if name:
        norm = re.sub(r"\s+", " ", name).strip()
        if len(norm) >= 4:
            label = norm[:80]
            return f"NAME:{label.lower()}", f"ავტო ({label})"
    sid = str(row.get("საგადასახადო_ID", "") or "").strip()
    if sid and sid.isdigit():
        return f"ID:{sid}", f"ავტო (ID {sid})"
    return None, None


def _promote_dynamic_unclassified_groups(unclassified_rows):
    """
    „სხვა“ ჯგუფის შიგნით ვეძებთ განმეორებად კონტრაგენტს/IBAN-ს
    და ვქმნით დროებით ავტო-ქვეკატეგორიებს.
    """
    key_bucket = defaultdict(list)
    for r in unclassified_rows:
        k, lbl = _best_dynamic_key_for_row(r)
        if not k:
            continue
        key_bucket[(k, lbl)].append(r)
    promoted = []
    leftovers = []
    for (k, lbl), rows in key_bucket.items():
        total = sum(float(x.get("თანხა") or 0) for x in rows)
        if len(rows) >= 4 or total >= 5000:
            cid = "auto_" + re.sub(r"[^a-z0-9]+", "_", k.lower()).strip("_")[:40]
            promoted.append(
                {
                    "id": cid,
                    "label_ka": lbl,
                    "confidence": "low",
                    "total_ge": float(total),
                    "line_count": len(rows),
                    "rows_preview": rows[:120],
                    "_rows_all": rows,
                }
            )
    used = set()
    for c in promoted:
        for r in c["_rows_all"]:
            used.add(id(r))
    for r in unclassified_rows:
        if id(r) not in used:
            leftovers.append(r)
    return promoted, leftovers


def _signature_from_unclassified_row(row):
    """
    ვქმნით მოკლე „ნიშანს“ — IBAN > მიმღების სახელი > ოპერაციის ტექსტი.
    """
    blob = _unmatched_blob(row)
    ibans = _extract_ibans_from_text(blob)
    if ibans:
        return f"IBAN:{ibans[0]}"
    name = str(row.get("მიმღები_სახელი", "") or "").strip()
    if name and name != "-":
        name = re.sub(r"\s+", " ", name)
        return f"NAME:{name[:120]}"
    op = str(row.get("ოპერაციის_შინაარსი", "") or "").strip()
    if op:
        op = re.sub(r"\s+", " ", op)
        return f"ოპერაცია:{op[:120]}"
    reason = str(row.get("მიზეზი", "") or "").strip()
    if reason:
        return f"მიზეზი:{reason[:120]}"
    return "უცნობი"


def load_unmatched_overrides():
    """
    ხელით approve/reject წესები:
    Financial_Analysis/unmatched_overrides.json
    """
    path = _financial_analysis_path("unmatched_overrides.json")
    out = {"approvals": [], "rejections": []}
    if not os.path.isfile(path):
        return out
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            out["approvals"] = raw.get("approvals", []) or []
            out["rejections"] = raw.get("rejections", []) or []
    except Exception as e:
        print(f"  [warn] unmatched_overrides ვერ წაიკითხა: {e}")
    return out


def _row_matches_override(row, rule):
    blob = _unmatched_blob(row)
    sig = _signature_from_unclassified_row(row).lower()
    ibans = _extract_ibans_from_text(blob)
    contains_any = [str(x).lower() for x in (rule.get("contains_any") or []) if str(x).strip()]
    signature_contains = str(rule.get("signature_contains") or "").lower().strip()
    ibans_any = [str(x).upper().replace(" ", "") for x in (rule.get("ibans_any") or []) if str(x).strip()]
    ok_contains = True if not contains_any else any(k in blob for k in contains_any)
    ok_sig = True if not signature_contains else (signature_contains in sig)
    ok_iban = True
    if ibans_any:
        row_ibans = [x.upper().replace(" ", "") for x in ibans]
        ok_iban = any(x in row_ibans for x in ibans_any)
    return ok_contains and ok_sig and ok_iban


def _manual_override_category(row, overrides):
    for idx, rr in enumerate(overrides.get("rejections", []), start=1):
        if _row_matches_override(row, rr):
            return {
                "id": "other_unclassified",
                "label_ka": "სხვა (ხელით reject)",
                "confidence": "low",
                "manual_decision": "reject",
                "manual_rule_note": str(rr.get("note") or f"reject #{idx}"),
            }
    for idx, ar in enumerate(overrides.get("approvals", []), start=1):
        if _row_matches_override(row, ar):
            cid = str(ar.get("category_id") or "").strip() or "manual_approved"
            label = str(ar.get("label_ka") or "").strip() or "ხელით დამტკიცებული კატეგორია"
            conf = str(ar.get("confidence") or "high").lower().strip()
            if conf not in {"high", "medium", "low"}:
                conf = "high"
            return {
                "id": cid,
                "label_ka": label,
                "confidence": conf,
                "manual_decision": "approve",
                "manual_rule_note": str(ar.get("note") or f"approve #{idx}"),
            }
    return None


def _top_unclassified_signatures(rows, limit=20):
    cnt = Counter()
    sums = defaultdict(float)
    for r in rows:
        sig = _signature_from_unclassified_row(r)
        amt = float(r.get("თანხა") or 0)
        cnt[sig] += 1
        sums[sig] += amt
    ordered = sorted(
        cnt.keys(),
        key=lambda k: (sums[k], cnt[k]),
        reverse=True,
    )
    out = []
    for k in ordered[:limit]:
        out.append(
            {
                "signature": k,
                "line_count": int(cnt[k]),
                "total_ge": float(sums[k]),
            }
        )
    return out


def analyze_bank_unmatched_rows(unmatched_rows):
    if not unmatched_rows:
        return {
            "total_ge": 0.0,
            "line_count": 0,
            "categorized_total_ge": 0.0,
            "uncategorized_total_ge": 0.0,
            "categories": [],
            "top_unclassified_preview": [],
            "ledger_note_ka": BANK_UNMATCHED_LEDGER_NOTE_KA,
        }

    overrides = load_unmatched_overrides()
    bucket = {}
    manual_approve_lines = 0
    manual_reject_lines = 0
    manual_override_audit_rows = []
    for row in unmatched_rows:
        manual = _manual_override_category(row, overrides)
        if manual:
            cid = manual["id"]
            label = manual["label_ka"]
            conf = manual["confidence"]
            if manual.get("manual_decision") == "approve":
                manual_approve_lines += 1
            elif manual.get("manual_decision") == "reject":
                manual_reject_lines += 1
            manual_override_audit_rows.append(
                {
                    "manual_decision": manual.get("manual_decision"),
                    "manual_rule_note": manual.get("manual_rule_note", ""),
                    "assigned_category_id": cid,
                    "assigned_label_ka": label,
                    "confidence": conf,
                    "ბანკი": row.get("ბანკი", ""),
                    "ფაილი": row.get("ფაილი", ""),
                    "თარიღი": row.get("თარიღი", ""),
                    "თანხა": float(row.get("თანხა") or 0),
                    "საგადასახადო_ID": row.get("საგადასახადო_ID", ""),
                    "მიმღები_სახელი": row.get("მიმღები_სახელი", ""),
                    "ოპერაციის_შინაარსი": row.get("ოპერაციის_შინაარსი", ""),
                    "მიზეზი": row.get("მიზეზი", ""),
                    "signature": _signature_from_unclassified_row(row),
                }
            )
        else:
            cid, label, conf = _auto_category_from_unmatched_row(row)
        if cid not in bucket:
            bucket[cid] = {
                "id": cid,
                "label_ka": label,
                "confidence": conf,
                "total_ge": 0.0,
                "line_count": 0,
                "rows_preview": [],
            }
        amt = float(row.get("თანხა") or 0)
        bucket[cid]["total_ge"] += amt
        bucket[cid]["line_count"] += 1
        if len(bucket[cid]["rows_preview"]) < 120:
            bucket[cid]["rows_preview"].append(row)

    cats = sorted(
        [
            {
                "id": v["id"],
                "label_ka": v["label_ka"],
                "confidence": v.get("confidence", "medium"),
                "total_ge": float(v["total_ge"]),
                "line_count": int(v["line_count"]),
                "rows_preview": v["rows_preview"],
            }
            for v in bucket.values()
        ],
        key=_bank_unmatched_sort_key,
    )

    unc = next((c for c in cats if c["id"] == "other_unclassified"), None)
    promoted = []
    dynamic_promoted_total = 0.0
    dynamic_promoted_lines = 0
    if unc and unc.get("rows_preview"):
        promoted, unc_left = _promote_dynamic_unclassified_groups(unc["rows_preview"])
        dynamic_promoted_total = sum(float(c["total_ge"]) for c in promoted)
        dynamic_promoted_lines = sum(int(c["line_count"]) for c in promoted)
        unc["rows_preview"] = unc_left[:120]
        unc["total_ge"] = float(sum(float(r.get("თანხა") or 0) for r in unc_left))
        unc["line_count"] = len(unc_left)
        cats.extend(
            [
                {
                    "id": c["id"],
                    "label_ka": c["label_ka"],
                    "confidence": c.get("confidence", "low"),
                    "total_ge": float(c["total_ge"]),
                    "line_count": int(c["line_count"]),
                    "rows_preview": c["rows_preview"],
                }
                for c in promoted
            ]
        )
        cats = sorted(cats, key=_bank_unmatched_sort_key)

    total_ge = sum(float(r.get("თანხა") or 0) for r in unmatched_rows)
    unc = next((c for c in cats if c["id"] == "other_unclassified"), None)
    unc_total = float(unc["total_ge"]) if unc else 0.0
    unc_preview = unc["rows_preview"][:60] if unc else []
    top_unc = _top_unclassified_signatures(unc["rows_preview"], limit=20) if unc else []
    confidence_totals = defaultdict(float)
    for c in cats:
        confidence_totals[str(c.get("confidence") or "low")] += float(c.get("total_ge") or 0)
    return {
        "total_ge": float(total_ge),
        "line_count": len(unmatched_rows),
        "categorized_total_ge": float(total_ge - unc_total),
        "uncategorized_total_ge": float(unc_total),
        "manual_override_approved_lines": int(manual_approve_lines),
        "manual_override_rejected_lines": int(manual_reject_lines),
        "manual_override_audit_rows": manual_override_audit_rows,
        "dynamic_promoted_total_ge": float(dynamic_promoted_total),
        "dynamic_promoted_line_count": int(dynamic_promoted_lines),
        "confidence_totals": {
            "high": float(confidence_totals.get("high", 0.0)),
            "medium": float(confidence_totals.get("medium", 0.0)),
            "low": float(confidence_totals.get("low", 0.0)),
        },
        "categories": cats,
        "top_unclassified_preview": unc_preview,
        "top_unclassified_signatures": top_unc,
        "ledger_note_ka": BANK_UNMATCHED_LEDGER_NOTE_KA,
    }


def write_bank_unmatched_categories_excel(analysis, download_dir):
    cats = analysis.get("categories") or []
    rows = []
    for c in cats:
        rows.append(
            {
                "კატეგორია": c.get("label_ka", c.get("id", "")),
                "კატეგორია_id": c.get("id", ""),
                "სანდოობა": c.get("confidence", "low"),
                "ხაზების რაოდენობა": int(c.get("line_count") or 0),
                "ჯამი": float(c.get("total_ge") or 0),
            }
        )
    if not rows:
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("  [შეტყობინება] Excel-ისთვის დააყენე: pip install openpyxl")
        return
    out_df = pd.DataFrame(rows)
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, "ბანკი_არამიბმული_კატეგორიები.xlsx")
    out_df.to_excel(path, index=False, engine="openpyxl")
    print(f"  Excel (არამიბმული კატეგორიები) → {path}")


def write_bank_unclassified_top_excel(analysis, download_dir):
    rows = analysis.get("top_unclassified_signatures") or []
    if not rows:
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("  [შეტყობინება] Excel-ისთვის დააყენე: pip install openpyxl")
        return
    out_df = pd.DataFrame(rows)
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, "ბანკი_სხვა_top20.xlsx")
    out_df.to_excel(path, index=False, engine="openpyxl")
    print(f"  Excel (არამიბმული სხვა TOP20) → {path}")


def write_bank_overrides_audit_excel(analysis, download_dir):
    rows = analysis.get("manual_override_audit_rows") or []
    if not rows:
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("  [შეტყობინება] Excel-ისთვის დააყენე: pip install openpyxl")
        return
    out_df = pd.DataFrame(rows)
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, "ბანკი_overrides_audit.xlsx")
    out_df.to_excel(path, index=False, engine="openpyxl")
    print(f"  Excel (overrides audit) → {path}")


def _tbc_income_row_text_join(row, cols, credit_col):
    parts = []
    for c in cols:
        if c == credit_col:
            continue
        v = row[c]
        if pd.notna(v) and str(v).strip():
            parts.append(str(v))
    return " ".join(parts)


def _tbc_row_text_join_skip(row, cols, skip_cols=None):
    skip = set(skip_cols or [])
    parts = []
    for c in cols:
        if c in skip:
            continue
        v = row[c]
        if pd.notna(v) and str(v).strip():
            parts.append(str(v))
    return " ".join(parts)


def _tbc_income_matches_blob(blob_lower, patterns, iban_hints):
    for p in patterns:
        if p.lower() in blob_lower:
            return True
    compact_upper = re.sub(r"\s+", "", blob_lower).upper()
    for ib in iban_hints:
        ibc = re.sub(r"\s+", "", str(ib).upper())
        if ibc and ibc in compact_upper:
            return True
    return False


def collect_tbc_samurneo_flow(script_dir):
    """
    სამეურნეო მოძრაობა TBC-ში (ბუღალტრულად: საქმიანობისთვის აუცილებელი ხარჯის მოძრაობა):
    - გასული თანხა (>0) => გასვლა
    - შემოსული თანხა (>0) => დაბრუნება/შემოტანა
    """
    cfg_path = os.path.join(script_dir, "Financial_Analysis", "tbc_samurneo_patterns.json")
    patterns = []
    include_all = True
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            include_all = bool(cfg.get("include_all_transactions", True))
            patterns = [str(x).lower() for x in (cfg.get("match_substrings") or []) if str(x).strip()]
        except Exception:
            include_all = True
            patterns = []

    out_exp = []
    out_ret = []
    for f in list_tbc_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            debit_col = next((c for c in cols if "გასული თანხა" in str(c)), None)
            credit_col = next((c for c in cols if "შემოსული თანხა" in str(c)), None)
            if not debit_col and not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                raw = _tbc_row_text_join_skip(row, cols, [debit_col, credit_col])
                blob = raw.lower()
                if (not include_all) and patterns and (not any(p in blob for p in patterns)):
                    continue
                debit_amt = pd.to_numeric(row[debit_col], errors="coerce") if debit_col else float("nan")
                credit_amt = pd.to_numeric(row[credit_col], errors="coerce") if credit_col else float("nan")
                base = {
                    "ფაილი": os.path.basename(f),
                    "თარიღი": _excel_cell(row, date_col),
                    "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw,
                }
                if pd.notna(debit_amt) and float(debit_amt) > 0:
                    out_exp.append(
                        {
                            **base,
                            "თანხა": float(debit_amt),
                            "მიმართულება": SAMURNEO_EXPENSE_DIRECTION_KA,
                        }
                    )
                if pd.notna(credit_amt) and float(credit_amt) > 0:
                    out_ret.append(
                        {
                            **base,
                            "თანხა": float(credit_amt),
                            "მიმართულება": SAMURNEO_RETURN_DIRECTION_KA,
                        }
                    )
        except Exception as e:
            print(f"Error TBC samurneo {f}: {e}")

    exp_total = sum(float(r.get("თანხა") or 0) for r in out_exp)
    ret_total = sum(float(r.get("თანხა") or 0) for r in out_ret)
    return {
        "expense_total_ge": float(exp_total),
        "return_total_ge": float(ret_total),
        "net_ge": float(ret_total - exp_total),
        "expense_line_count": len(out_exp),
        "return_line_count": len(out_ret),
        "expense_rows_preview": out_exp[:300],
        "return_rows_preview": out_ret[:300],
        "expense_monthly_summary": _monthly_summary(out_exp),
        "return_monthly_summary": _monthly_summary(out_ret),
    }


def collect_bog_samurneo_flow(script_dir):
    """
    BOG ამონაწერი — იგივე ლოგიკა, რაც collect_tbc_samurneo_flow (ბუღალტრულად: საქმიანობისთვის აუცილებელი ხარჯის მოძრაობა).
    """
    cfg_path = os.path.join(script_dir, "Financial_Analysis", "tbc_samurneo_patterns.json")
    patterns = []
    include_all = True
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            include_all = bool(cfg.get("include_all_transactions", True))
            patterns = [str(x).lower() for x in (cfg.get("match_substrings") or []) if str(x).strip()]
        except Exception:
            include_all = True
            patterns = []

    out_exp = []
    out_ret = []
    for f in list_bog_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            debit_col = next((c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)), None)
            credit_col = next((c for c in cols if "კრედიტი" in str(c) and "ბრუნვა" not in str(c)), None)
            if not debit_col and not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                raw = _tbc_row_text_join_skip(row, cols, [debit_col, credit_col])
                blob = raw.lower()
                if (not include_all) and patterns and (not any(p in blob for p in patterns)):
                    continue
                debit_amt = pd.to_numeric(row[debit_col], errors="coerce") if debit_col else float("nan")
                credit_amt = pd.to_numeric(row[credit_col], errors="coerce") if credit_col else float("nan")
                base = {
                    "ბანკი": "BOG",
                    "ფაილი": os.path.basename(f),
                    "თარიღი": _excel_cell(row, date_col),
                    "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw,
                }
                if pd.notna(debit_amt) and float(debit_amt) > 0:
                    out_exp.append(
                        {
                            **base,
                            "თანხა": float(debit_amt),
                            "მიმართულება": SAMURNEO_EXPENSE_DIRECTION_KA,
                        }
                    )
                if pd.notna(credit_amt) and float(credit_amt) > 0:
                    out_ret.append(
                        {
                            **base,
                            "თანხა": float(credit_amt),
                            "მიმართულება": SAMURNEO_RETURN_DIRECTION_KA,
                        }
                    )
        except Exception as e:
            print(f"Error BOG samurneo {f}: {e}")

    exp_total = sum(float(r.get("თანხა") or 0) for r in out_exp)
    ret_total = sum(float(r.get("თანხა") or 0) for r in out_ret)
    return {
        "expense_total_ge": float(exp_total),
        "return_total_ge": float(ret_total),
        "net_ge": float(ret_total - exp_total),
        "expense_line_count": len(out_exp),
        "return_line_count": len(out_ret),
        "expense_rows_preview": out_exp[:300],
        "return_rows_preview": out_ret[:300],
        "expense_monthly_summary": _monthly_summary(out_exp),
        "return_monthly_summary": _monthly_summary(out_ret),
    }


def collect_tax_flow(script_dir):
    """
    საგადასახადო მოძრაობა (BOG+TBC):
    - გადარიცხული (debit/out) => გადარიცხული
    - ჩარიცხული (credit/in) => ჩარიცხული
    """
    cfg_path = os.path.join(script_dir, "Financial_Analysis", "tax_flow_patterns.json")
    default_patterns = [
        "საშემოსავლო",
        "გადასახად",
        "ბიუჯეტ",
        "revenue service",
        "rs.ge",
        "treasury",
        "tresge22",
        "204931440",
        "ge24nb0330100200165022",
        "ge60bg0000000667583800rs",
        "ge04bg0000000201978600rs",
    ]
    treasury_in_markers = [
        "tresge22",
        "სახელმწიფო ხაზინა",
        "204931440",
        "ge24nb0330100200165022",
    ]
    patterns = default_patterns
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            patterns = [
                str(x).lower()
                for x in (cfg.get("match_substrings") or [])
                if str(x).strip()
            ] or default_patterns
        except Exception:
            patterns = default_patterns

    out_rows = []
    in_rows = []
    treasury_in_rows = []

    # BOG
    for f in list_bog_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            debit_col = next((c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)), None)
            credit_col = next((c for c in cols if "კრედიტი" in str(c) and "ბრუნვა" not in str(c)), None)
            if not debit_col and not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                raw = _tbc_row_text_join_skip(row, cols, [debit_col, credit_col]).lower()
                if not any(p in raw for p in patterns):
                    continue
                debit_amt = pd.to_numeric(row[debit_col], errors="coerce") if debit_col else float("nan")
                credit_amt = pd.to_numeric(row[credit_col], errors="coerce") if credit_col else float("nan")
                base = {
                    "ბანკი": "BOG",
                    "ფაილი": os.path.basename(f),
                    "თარიღი": _excel_cell(row, date_col),
                    "ტექსტი_მოკლე": raw[:500],
                }
                if pd.notna(debit_amt) and float(debit_amt) > 0:
                    out_rows.append({**base, "თანხა": float(debit_amt), "მიმართულება": "საგადასახადო გადარიცხული"})
                if pd.notna(credit_amt) and float(credit_amt) > 0:
                    in_rec = {**base, "თანხა": float(credit_amt), "მიმართულება": "საგადასახადო ჩარიცხული"}
                    in_rows.append(in_rec)
                    if any(m in raw for m in treasury_in_markers):
                        treasury_in_rows.append(
                            {**in_rec, "მიმართულება": "სახელმწიფო ხაზინიდან ჩარიცხული"}
                        )
        except Exception as e:
            print(f"Error BOG tax flow {f}: {e}")

    # TBC
    for f in list_tbc_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            debit_col = next((c for c in cols if "გასული თანხა" in str(c)), None)
            credit_col = next((c for c in cols if "შემოსული თანხა" in str(c)), None)
            if not debit_col and not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                raw = _tbc_row_text_join_skip(row, cols, [debit_col, credit_col]).lower()
                if not any(p in raw for p in patterns):
                    continue
                debit_amt = pd.to_numeric(row[debit_col], errors="coerce") if debit_col else float("nan")
                credit_amt = pd.to_numeric(row[credit_col], errors="coerce") if credit_col else float("nan")
                base = {
                    "ბანკი": "TBC",
                    "ფაილი": os.path.basename(f),
                    "თარიღი": _excel_cell(row, date_col),
                    "ტექსტი_მოკლე": raw[:500],
                }
                if pd.notna(debit_amt) and float(debit_amt) > 0:
                    out_rows.append({**base, "თანხა": float(debit_amt), "მიმართულება": "საგადასახადო გადარიცხული"})
                if pd.notna(credit_amt) and float(credit_amt) > 0:
                    in_rec = {**base, "თანხა": float(credit_amt), "მიმართულება": "საგადასახადო ჩარიცხული"}
                    in_rows.append(in_rec)
                    if any(m in raw for m in treasury_in_markers):
                        treasury_in_rows.append(
                            {**in_rec, "მიმართულება": "სახელმწიფო ხაზინიდან ჩარიცხული"}
                        )
        except Exception as e:
            print(f"Error TBC tax flow {f}: {e}")

    out_total = sum(float(r.get("თანხა") or 0) for r in out_rows)
    in_total = sum(float(r.get("თანხა") or 0) for r in in_rows)
    treasury_in_total = sum(float(r.get("თანხა") or 0) for r in treasury_in_rows)
    return {
        "label_ka": "საგადასახადო / ბიუჯეტი / სახელმწიფო ხაზინა (ბანკის ფილტრი)",
        "ledger_note_ka": TAX_TREASURY_CLUSTER_NOTE_KA,
        "out_total_ge": float(out_total),
        "in_total_ge": float(in_total),
        "treasury_in_total_ge": float(treasury_in_total),
        "net_ge": float(in_total - out_total),
        "out_line_count": len(out_rows),
        "in_line_count": len(in_rows),
        "treasury_in_line_count": len(treasury_in_rows),
        "out_rows_preview": out_rows[:300],
        "in_rows_preview": in_rows[:300],
        "treasury_in_rows_preview": treasury_in_rows[:300],
        "out_monthly_summary": _monthly_summary(out_rows),
        "in_monthly_summary": _monthly_summary(in_rows),
        "treasury_in_monthly_summary": _monthly_summary(treasury_in_rows),
    }


def merge_samurneo_flows(tbc_bundle, bog_bundle):
    tbc_bundle = tbc_bundle or {}
    bog_bundle = bog_bundle or {}
    tbc_exp = float(tbc_bundle.get("expense_total_ge") or 0)
    tbc_ret = float(tbc_bundle.get("return_total_ge") or 0)
    bog_exp = float(bog_bundle.get("expense_total_ge") or 0)
    bog_ret = float(bog_bundle.get("return_total_ge") or 0)
    all_exp_rows = (tbc_bundle.get("expense_rows_preview") or []) + (bog_bundle.get("expense_rows_preview") or [])
    all_ret_rows = (tbc_bundle.get("return_rows_preview") or []) + (bog_bundle.get("return_rows_preview") or [])
    return {
        "tbc_expense_total_ge": tbc_exp,
        "tbc_return_total_ge": tbc_ret,
        "bog_expense_total_ge": bog_exp,
        "bog_return_total_ge": bog_ret,
        "expense_total_ge": float(tbc_exp + bog_exp),
        "return_total_ge": float(tbc_ret + bog_ret),
        "net_ge": float((tbc_ret + bog_ret) - (tbc_exp + bog_exp)),
        "expense_line_count": int((tbc_bundle.get("expense_line_count") or 0) + (bog_bundle.get("expense_line_count") or 0)),
        "return_line_count": int((tbc_bundle.get("return_line_count") or 0) + (bog_bundle.get("return_line_count") or 0)),
        "expense_rows_preview": all_exp_rows[:300],
        "return_rows_preview": all_ret_rows[:300],
        "expense_monthly_summary": _monthly_summary(all_exp_rows),
        "return_monthly_summary": _monthly_summary(all_ret_rows),
        "label_ka": SAMURNEO_LABEL_KA,
        "accounting_note_ka": SAMURNEO_ACCOUNTING_NOTE_KA,
        "ledger_classification_ka": SAMURNEO_LEDGER_CLASS_KA,
    }


def write_tbc_samurneo_excel(bundle, download_dir):
    exp_rows = bundle.get("expense_rows_preview", [])
    ret_rows = bundle.get("return_rows_preview", [])
    all_rows = []
    for r in exp_rows:
        all_rows.append(
            {
                "ბანკი": r.get("ბანკი", "TBC"),
                "ბუღალტრული_კლასიფიკაცია": SAMURNEO_LEDGER_CLASS_KA,
                "მიმართულება": SAMURNEO_EXPENSE_DIRECTION_KA,
                "ფაილი": r.get("ფაილი", ""),
                "თარიღი": r.get("თარიღი", ""),
                "თანხა": float(r.get("თანხა") or 0),
                "საინით": -abs(float(r.get("თანხა") or 0)),
                "ტექსტი_მოკლე": r.get("ტექსტი_მოკლე", ""),
            }
        )
    for r in ret_rows:
        all_rows.append(
            {
                "ბანკი": r.get("ბანკი", "TBC"),
                "ბუღალტრული_კლასიფიკაცია": SAMURNEO_LEDGER_CLASS_KA,
                "მიმართულება": SAMURNEO_RETURN_DIRECTION_KA,
                "ფაილი": r.get("ფაილი", ""),
                "თარიღი": r.get("თარიღი", ""),
                "თანხა": float(r.get("თანხა") or 0),
                "საინით": abs(float(r.get("თანხა") or 0)),
                "ტექსტი_მოკლე": r.get("ტექსტი_მოკლე", ""),
            }
        )
    if not all_rows:
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("  [შეტყობინება] Excel-ისთვის დააყენე: pip install openpyxl")
        return
    out_df = pd.DataFrame(all_rows)
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, "TBC_სამეურნეო_მოძრაობა.xlsx")
    out_df.to_excel(path, index=False, engine="openpyxl")
    print(
        f"  Excel (სამეურნეო / საქმიანობისთვის აუცილებელი ხარჯი) → {path} "
        f"(გასვლა {bundle.get('expense_total_ge', 0):,.2f} ₾ | დაბრუნება {bundle.get('return_total_ge', 0):,.2f} ₾)"
    )


def write_tax_flow_excel(bundle, download_dir):
    out_rows = bundle.get("out_rows_preview", [])
    in_rows = bundle.get("in_rows_preview", [])
    rows = []
    for r in out_rows:
        rows.append(
            {
                "ბანკი": r.get("ბანკი", ""),
                "მიმართულება": "საგადასახადო გადარიცხული",
                "ფაილი": r.get("ფაილი", ""),
                "თარიღი": r.get("თარიღი", ""),
                "თანხა": float(r.get("თანხა") or 0),
                "ტექსტი_მოკლე": r.get("ტექსტი_მოკლე", ""),
            }
        )
    for r in in_rows:
        rows.append(
            {
                "ბანკი": r.get("ბანკი", ""),
                "მიმართულება": "საგადასახადო ჩარიცხული",
                "ფაილი": r.get("ფაილი", ""),
                "თარიღი": r.get("თარიღი", ""),
                "თანხა": float(r.get("თანხა") or 0),
                "ტექსტი_მოკლე": r.get("ტექსტი_მოკლე", ""),
            }
        )
    if not rows:
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("  [შეტყობინება] Excel-ისთვის დააყენე: pip install openpyxl")
        return
    out_df = pd.DataFrame(rows)
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, "საგადასახადო_მოძრაობა.xlsx")
    out_df.to_excel(path, index=False, engine="openpyxl")
    print(
        f"  Excel (საგადასახადო) → {path} "
        f"(გადარიცხული {bundle.get('out_total_ge', 0):,.2f} ₾ | ჩარიცხული {bundle.get('in_total_ge', 0):,.2f} ₾)"
    )

def write_treasury_incoming_excel(bundle, download_dir):
    rows = bundle.get("treasury_in_rows_preview", [])
    if not rows:
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("  [შეტყობინება] Excel-ისთვის დააყენე: pip install openpyxl")
        return
    out_df = pd.DataFrame(
        [
            {
                "ბანკი": r.get("ბანკი", ""),
                "მიმართულება": "სახელმწიფო ხაზინიდან ჩარიცხული",
                "ფაილი": r.get("ფაილი", ""),
                "თარიღი": r.get("თარიღი", ""),
                "თანხა": float(r.get("თანხა") or 0),
                "ტექსტი_მოკლე": r.get("ტექსტი_მოკლე", ""),
            }
            for r in rows
        ]
    )
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, "სახელმწიფო_ხაზინა_ჩარიცხვები.xlsx")
    out_df.to_excel(path, index=False, engine="openpyxl")
    print(
        f"  Excel (სახელმწიფო ხაზინა ჩარიცხვები) → {path} "
        f"({bundle.get('treasury_in_line_count', 0)} ხაზი, {bundle.get('treasury_in_total_ge', 0):,.2f} ₾)"
    )


def collect_tbc_foodmart_cashback(script_dir):
    """
    TBC შემოსული ხაზები ფუდმარტიდან (cashback/მომსახურების ღირებულება).
    """
    patterns = [
        "ფუდმარტ",
        "foodmart",
        "404460187",
        "ge06tb7064936020100010",
        "ქეშბექ",
        "cashback",
        "cash back",
        "მომსახურების ღირებულება",
    ]
    rows = []
    total = 0.0
    for f in list_tbc_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            credit_col = next((c for c in cols if "შემოსული თანხა" in str(c)), None)
            if not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[credit_col], errors="coerce")
                if pd.isna(amt) or float(amt) <= 0:
                    continue
                raw = _tbc_row_text_join_skip(row, cols, [credit_col]).lower()
                if not any(p in raw for p in patterns):
                    continue
                total += float(amt)
                rows.append(
                    {
                        "ბანკი": "TBC",
                        "ფაილი": os.path.basename(f),
                        "თარიღი": _excel_cell(row, date_col),
                        "თანხა": float(amt),
                        "ტექსტი_მოკლე": raw[:500],
                    }
                )
        except Exception as e:
            print(f"Error TBC foodmart cashback {f}: {e}")
    return {
        "label_ka": "ფუდმარტის ქეშბექი/შემოსავალი",
        "total_ge": float(total),
        "line_count": len(rows),
        "rows_preview": rows[:300],
        "monthly_summary": _monthly_summary(rows),
    }


def write_tbc_foodmart_cashback_excel(bundle, download_dir):
    rows = bundle.get("rows_preview", [])
    if not rows:
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("  [შეტყობინება] Excel-ისთვის დააყენე: pip install openpyxl")
        return
    out_df = pd.DataFrame(rows)
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, "TBC_ფუდმარტი_ქეშბექი.xlsx")
    out_df.to_excel(path, index=False, engine="openpyxl")
    print(
        f"  Excel (TBC ფუდმარტი ქეშბექი) → {path} "
        f"({bundle.get('line_count', 0)} ხაზი, {bundle.get('total_ge', 0):,.2f} ₾)"
    )


def collect_bog_pos_terminal_income(script_dir):
    """
    BOG ამონაწერში POS ტერმინალის ჩარიცხვები (კრედიტი):
    ტიპური ტექსტები: "გადახდა - თარიღი", "ტერმინალის id", "ბარათი", "ტრანზაქციის დეტალები".
    """
    cfg_path = os.path.join(
        script_dir, "Financial_Analysis", "bog_pos_terminal_income_patterns.json"
    )
    default_patterns = [
        "გადახდა - თარიღი",
        "ტერმინალის id",
        "ბარათი:",
        "ტრანზაქციის დეტალები",
        "დანიშნულება ჩარიცხვა",
        "pos",
        "პოს",
    ]
    patterns = default_patterns
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            patterns = [
                str(x).lower()
                for x in (cfg.get("match_substrings") or [])
                if str(x).strip()
            ] or default_patterns
        except Exception:
            patterns = default_patterns

    lines = []
    total = 0.0
    for f in list_bog_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            credit_col = next(
                (c for c in cols if "კრედიტი" in str(c) and "ბრუნვა" not in str(c)),
                None,
            )
            if not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[credit_col], errors="coerce")
                if pd.isna(amt) or float(amt) <= 0:
                    continue
                raw = _tbc_row_text_join_skip(row, cols, [credit_col])
                blob_lower = raw.lower()
                if not any(p in blob_lower for p in patterns):
                    continue
                total += float(amt)
                lines.append(
                    {
                        "ბანკი": "BOG",
                        "ფაილი": os.path.basename(f),
                        "თარიღი": _excel_cell(row, date_col),
                        "თანხა": float(amt),
                        "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw,
                    }
                )
        except Exception as e:
            print(f"Error BOG POS income {f}: {e}")

    return {
        "label_ka": "POS ტერმინალის შემოსავალი (BOG)",
        "total_ge": float(total),
        "line_count": len(lines),
        "lines": lines,
    }


def merge_pos_terminal_income(tbc_bundle, bog_bundle):
    tbc_total = float((tbc_bundle or {}).get("total_ge") or 0)
    bog_total = float((bog_bundle or {}).get("total_ge") or 0)
    tbc_lines = list((tbc_bundle or {}).get("lines") or [])
    bog_lines = list((bog_bundle or {}).get("lines") or [])
    all_lines = tbc_lines + bog_lines
    tbc_daily = _daily_summary(tbc_lines)
    bog_daily = _daily_summary(bog_lines)
    tbc_daily_map = {r.get("day"): float(r.get("total_ge") or 0) for r in tbc_daily}
    bog_daily_map = {r.get("day"): float(r.get("total_ge") or 0) for r in bog_daily}
    all_days = sorted(set(tbc_daily_map.keys()) | set(bog_daily_map.keys()))
    daily_combined = []
    for d in all_days:
        tbc_d = float(tbc_daily_map.get(d) or 0)
        bog_d = float(bog_daily_map.get(d) or 0)
        daily_combined.append(
            {
                "day": d,
                "tbc_total_ge": tbc_d,
                "bog_total_ge": bog_d,
                "total_ge": float(tbc_d + bog_d),
            }
        )
    return {
        "label_ka": "POS ტერმინალის შემოსავალი (TBC+BOG)",
        "tbc_total_ge": float(tbc_total),
        "bog_total_ge": float(bog_total),
        "total_ge": float(tbc_total + bog_total),
        "tbc_line_count": int((tbc_bundle or {}).get("line_count") or 0),
        "bog_line_count": int((bog_bundle or {}).get("line_count") or 0),
        "line_count": len(all_lines),
        "rows_preview": all_lines[:400],
        "monthly_summary": _monthly_summary(all_lines),
        "daily_summary": daily_combined,
    }


def write_pos_terminal_income_excel(bundle, download_dir, full_rows=None):
    rows = list(full_rows or [])
    if not rows:
        rows = bundle.get("rows_preview", [])
    if not rows:
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("  [შეტყობინება] Excel-ისთვის დააყენე: pip install openpyxl")
        return
    out_df = pd.DataFrame(rows)
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, "POS_ტერმინალი_TBC_BOG.xlsx")
    out_df.to_excel(path, index=False, engine="openpyxl")
    print(
        f"  Excel (POS ტერმინალი TBC+BOG) → {path} "
        f"(TBC {bundle.get('tbc_total_ge', 0):,.2f} ₾ | "
        f"BOG {bundle.get('bog_total_ge', 0):,.2f} ₾ | "
        f"ჯამი {bundle.get('total_ge', 0):,.2f} ₾ | ხაზები {len(rows)})"
    )


def collect_tbc_card_income(script_dir):
    """
    TBC ამონაწერში „შემოსული თანხა“ — ხაზები, სადაც ტექსტი ემთხვევა
    Financial_Analysis/tbc_card_income_patterns.json ნიმუშებს (ბარათით შემოსავალი მაღაზიაში).
    """
    cfg_path = os.path.join(
        script_dir, "Financial_Analysis", "tbc_card_income_patterns.json"
    )
    empty = {"total_ge": 0.0, "lines": [], "line_count": 0, "label_ka": ""}
    if not os.path.isfile(cfg_path):
        return empty
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return empty
    patterns = [str(p) for p in cfg.get("match_substrings", []) if str(p).strip()]
    iban_hints = [str(p) for p in cfg.get("iban_hints", []) if str(p).strip()]
    label_ka = str(cfg.get("label_ka", "") or "")
    if not patterns and not iban_hints:
        return {**empty, "label_ka": label_ka}

    lines = []
    total = 0.0
    for f in list_tbc_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            credit_col = next(
                (
                    c
                    for c in cols
                    if "შემოსული" in str(c) and "გასული" not in str(c)
                ),
                None,
            )
            if not credit_col:
                credit_col = next(
                    (c for c in cols if "incoming" in str(c).lower()),
                    None,
                )
            if not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[credit_col], errors="coerce")
                if pd.isna(amt) or amt <= 0:
                    continue
                raw = _tbc_income_row_text_join(row, cols, credit_col)
                blob_lower = raw.lower()
                if not _tbc_income_matches_blob(blob_lower, patterns, iban_hints):
                    continue
                total += float(amt)
                lines.append(
                    {
                        "ფაილი": os.path.basename(f),
                        "თარიღი": _excel_cell(row, date_col),
                        "თანხა": float(amt),
                        "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw,
                    }
                )
        except Exception as e:
            print(f"Error TBC card income {f}: {e}")

    return {
        "total_ge": total,
        "lines": lines,
        "line_count": len(lines),
        "label_ka": label_ka,
    }


def write_tbc_card_income_excel(lines, download_dir):
    if not lines:
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print(
            "  [შეტყობინება] Excel-ისთვის დააყენე: pip install openpyxl"
        )
        return
    out_df = pd.DataFrame(lines)
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, "TBC_ბარათის_შემოსავალი.xlsx")
    out_df.to_excel(path, index=False, engine="openpyxl")
    tot = sum(float(r.get("თანხა") or 0) for r in lines)
    print(
        f"  Excel (TBC ბარათის შემოსავალი) → {path} "
        f"({len(lines)} ხაზი, {tot:,.2f} ₾)"
    )


def _tbc_expense_cat_matches(cat, blob_lower):
    """
    match_all_substrings (AND) — თუ სრულად ემთხვევა → True.
    სხვა შემთხვევაში ან თუ match_all ცარიელია → OR match_substrings.
    (ორივე ერთ კატეგორიაში: მაგ. სატრანზიტო საკომისიო AND, ან ინგლისური ფრაზა OR.)
    """
    mall = [str(x).lower() for x in (cat.get("match_all") or []) if str(x).strip()]
    if mall and all(m in blob_lower for m in mall):
        return True
    return _tbc_income_matches_blob(blob_lower, cat["patterns"], [])


def _match_tbc_expense_category(blob_lower, cats_norm):
    """
    ჯერ ტექსტური წესები ფაილის რიგით (პატერნი / match_all), შემდეგ IBAN.
    ასე „საკომისიო:“ ხაზები სატრანზიტოზე არ მიდის მხოლოდ IBAN-ით transit_ucc-ში.
    """
    compact_upper = re.sub(r"\s+", "", blob_lower).upper()
    for cat in cats_norm:
        if _tbc_expense_cat_matches(cat, blob_lower):
            return cat["id"]
    for cat in cats_norm:
        for ib in cat["ibans"]:
            ibc = re.sub(r"\s+", "", str(ib).upper())
            if ibc and ibc in compact_upper:
                return cat["id"]
    return None


def collect_tbc_expense_categories(script_dir):
    """
    TBC „გასული თანხა“ — ხარჯის კატეგორიები (Financial_Analysis/tbc_expense_categories.json).
    """
    cfg_path = os.path.join(
        script_dir, "Financial_Analysis", "tbc_expense_categories.json"
    )
    empty = {
        "categories": [],
        "grand_total_ge": 0.0,
        "grand_total_operating_expense_ge": 0.0,
        "grand_total_state_treasury_ge": 0.0,
    }
    if not os.path.isfile(cfg_path):
        return empty
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return empty
    raw_cats = cfg.get("categories", [])
    if not raw_cats:
        return empty

    cats_norm = []
    for c in raw_cats:
        cid = str(c.get("id", "")).strip()
        if not cid:
            continue
        role = str(c.get("accounting_role") or ACCOUNTING_ROLE_OPERATING).strip()
        if role not in (ACCOUNTING_ROLE_OPERATING, ACCOUNTING_ROLE_STATE_TREASURY):
            role = ACCOUNTING_ROLE_OPERATING
        cats_norm.append(
            {
                "id": cid,
                "label_ka": str(c.get("label_ka", "") or ""),
                "accounting_role": role,
                "patterns": [
                    str(p) for p in c.get("match_substrings", []) if str(p).strip()
                ],
                "match_all": [
                    str(p)
                    for p in c.get("match_all_substrings", []) if str(p).strip()
                ],
                "ibans": [
                    str(p) for p in c.get("iban_hints", []) if str(p).strip()
                ],
            }
        )
    if not cats_norm:
        return empty

    buckets = {c["id"]: [] for c in cats_norm}
    for f in list_tbc_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            debit_col = next(
                (c for c in cols if "გასული თანხა" in str(c)), None
            )
            if not debit_col:
                continue
            df = df[
                ~df[debit_col]
                .astype(str)
                .str.contains("Paid|Out|Amount", case=False, na=False)
            ]
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors="coerce")
                if pd.isna(amt) or amt <= 0:
                    continue
                raw = _tbc_income_row_text_join(row, cols, debit_col)
                blob_lower = raw.lower()
                mid = _match_tbc_expense_category(blob_lower, cats_norm)
                if not mid:
                    continue
                buckets[mid].append(
                    {
                        "კატეგორია_id": mid,
                        "ფაილი": os.path.basename(f),
                        "თარიღი": _excel_cell(row, date_col),
                        "თანხა": float(amt),
                        "ტექსტი_მოკლე": (raw[:500] + "...")
                        if len(raw) > 500
                        else raw,
                    }
                )
        except Exception as e:
            print(f"Error TBC expenses {f}: {e}")

    out_cats = []
    grand = 0.0
    grand_operating = 0.0
    grand_treasury = 0.0
    label_by_id = {c["id"]: c["label_ka"] for c in cats_norm}
    for c in cats_norm:
        cid = c["id"]
        role = c.get("accounting_role") or ACCOUNTING_ROLE_OPERATING
        lines = buckets.get(cid, [])
        t = sum(float(x.get("თანხა") or 0) for x in lines)
        grand += t
        if role == ACCOUNTING_ROLE_STATE_TREASURY:
            grand_treasury += t
        else:
            grand_operating += t
        out_cats.append(
            {
                "id": cid,
                "label_ka": label_by_id.get(cid, cid),
                "accounting_role": role,
                "total_ge": float(t),
                "line_count": len(lines),
                "lines": lines,
                "rows_preview": lines[:150],
            }
        )

    return {
        "categories": out_cats,
        "grand_total_ge": float(grand),
        "grand_total_operating_expense_ge": float(grand_operating),
        "grand_total_state_treasury_ge": float(grand_treasury),
    }


def write_tbc_expenses_excel(tbc_expenses_bundle, download_dir):
    cats = tbc_expenses_bundle.get("categories") or []
    rows = []
    for c in cats:
        label = c.get("label_ka", c.get("id", ""))
        role = c.get("accounting_role") or ACCOUNTING_ROLE_OPERATING
        role_ka = (
            "სახელმწიფო ხაზინა"
            if role == ACCOUNTING_ROLE_STATE_TREASURY
            else "საოპერაციო ხარჯი"
        )
        for line in c.get("lines") or []:
            r = dict(line)
            r["კატეგორია"] = label
            r["ბუღალტრული_როლი"] = role_ka
            rows.append(r)
    if not rows:
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print(
            "  [შეტყობინება] Excel-ისთვის დააყენე: pip install openpyxl"
        )
        return
    out_df = pd.DataFrame(rows)
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, "TBC_ხარჯები_კატეგორიები.xlsx")
    out_df.to_excel(path, index=False, engine="openpyxl")
    tot = sum(float(r.get("თანხა") or 0) for r in rows)
    print(
        f"  Excel (TBC ხარჯები კატეგორიებით) → {path} "
        f"({len(rows)} ხაზი, {tot:,.2f} ₾)"
    )


def _month_key(date_val):
    if not date_val:
        return "უცნობი თვე"
    try:
        s = str(date_val).strip()
        dt = pd.to_datetime(
            s,
            errors="coerce",
            format="%Y-%m-%d %H:%M:%S",
        )
        if pd.isna(dt):
            dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
        if pd.isna(dt):
            return "უცნობი თვე"
        return dt.strftime("%Y-%m")
    except Exception:
        return "უცნობი თვე"


def _monthly_summary(rows):
    sums = defaultdict(float)
    cnt = defaultdict(int)
    for r in rows:
        m = _month_key(r.get("თარიღი"))
        amt = float(r.get("თანხა") or 0)
        sums[m] += amt
        cnt[m] += 1
    out = []
    for m in sorted(sums.keys()):
        out.append(
            {
                "month": m,
                "total_ge": float(sums[m]),
                "line_count": int(cnt[m]),
            }
        )
    return out


def _day_key(date_val):
    if not date_val:
        return "უცნობი დღე"
    try:
        s = str(date_val).strip()
        dt = pd.to_datetime(
            s,
            errors="coerce",
            format="%Y-%m-%d %H:%M:%S",
        )
        if pd.isna(dt):
            dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
        if pd.isna(dt):
            return "უცნობი დღე"
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return "უცნობი დღე"


def _daily_summary(rows):
    sums = defaultdict(float)
    cnt = defaultdict(int)
    for r in rows:
        d = _day_key(r.get("თარიღი"))
        amt = float(r.get("თანხა") or 0)
        sums[d] += amt
        cnt[d] += 1
    out = []
    for d in sorted(sums.keys()):
        out.append(
            {
                "day": d,
                "total_ge": float(sums[d]),
                "line_count": int(cnt[d]),
            }
        )
    return out


def publish_download_excels(download_dir, public_dir):
    """
    download/*.xlsx ფაილების გამოქვეყნება rs-dashboard/public/download-ში,
    რომ UI-დან პირდაპირ ჩამოტვირთვა იმუშაოს.
    """
    dst_dir = os.path.join(public_dir, "download")
    os.makedirs(dst_dir, exist_ok=True)
    copied = 0
    copied_files = []
    for src in sorted(glob.glob(os.path.join(download_dir, "*.xlsx"))):
        try:
            dst = os.path.join(dst_dir, os.path.basename(src))
            shutil.copy2(src, dst)
            copied += 1
            copied_files.append(os.path.basename(dst))
        except Exception as e:
            print(f"Warn publish excel {src}: {e}")
    zip_name = "ყველა_ანგარიში.xlsx.zip"
    zip_path = os.path.join(dst_dir, zip_name)
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fn in copied_files:
                p = os.path.join(dst_dir, fn)
                if os.path.isfile(p):
                    zf.write(p, arcname=fn)
    except Exception as e:
        print(f"Warn zip create {zip_path}: {e}")
        zip_name = ""

    print(f"  Published Excel files to public/download: {copied}")
    return {"files": copied_files, "zip_file": zip_name}


def _salary_breakdown(lines):
    buckets = {
        "ოზურგეთი": 0.0,
        "დვაბზუ": 0.0,
        "სხვა": 0.0,
    }
    for line in lines:
        txt = str(line.get("ტექსტი_მოკლე", "") or "").lower()
        amt = float(line.get("თანხა") or 0)
        if "ოზურგეთი" in txt:
            buckets["ოზურგეთი"] += amt
        elif "დვაბზუ" in txt:
            buckets["დვაბზუ"] += amt
        else:
            buckets["სხვა"] += amt
    return [{"name": k, "total_ge": float(v)} for k, v in buckets.items()]


def tbc_expenses_public_json(bundle):
    """data.json — უსაფრთხო ზომა: preview, სრული ხაზები მხოლოდ Excel-ში."""
    if not bundle or not bundle.get("categories"):
        return {
            "grand_total_ge": 0.0,
            "grand_total_operating_expense_ge": 0.0,
            "grand_total_state_treasury_ge": 0.0,
            "ledger_note_ka": TBC_EXPENSES_LEDGER_NOTE_KA,
            "categories": [],
            "monthly_summary": [],
            "salary_breakdown": [],
        }
    all_lines = []
    for c in bundle["categories"]:
        all_lines.extend(c.get("lines") or [])
    salary_lines = []
    for c in bundle["categories"]:
        if c.get("id") == "salary_payments":
            salary_lines = c.get("lines") or []
            break
    return {
        "grand_total_ge": float(bundle.get("grand_total_ge") or 0),
        "grand_total_operating_expense_ge": float(
            bundle.get("grand_total_operating_expense_ge") or 0
        ),
        "grand_total_state_treasury_ge": float(
            bundle.get("grand_total_state_treasury_ge") or 0
        ),
        "ledger_note_ka": TBC_EXPENSES_LEDGER_NOTE_KA,
        "monthly_summary": _monthly_summary(all_lines),
        "salary_breakdown": _salary_breakdown(salary_lines),
        "categories": [
            {
                "id": c["id"],
                "label_ka": c.get("label_ka", ""),
                "accounting_role": c.get("accounting_role")
                or ACCOUNTING_ROLE_OPERATING,
                "total_ge": float(c.get("total_ge") or 0),
                "line_count": int(c.get("line_count") or 0),
                "rows_preview": c.get("rows_preview") or [],
                "monthly_summary": _monthly_summary(c.get("lines") or []),
            }
            for c in bundle["categories"]
        ],
    }


def find_header_row(file_path):
    """
    სათაურის სტრიქონი: ვეძებთ უჯრების ტექსტში რამდენიმე მარკერის ერთად არსებობას,
    რომ ზედა ბლოკში მთლიანად „თარიღი“ სიტყვამ არ აირჩიოს არასწორი სტრიქონი.
    """
    df = pd.read_excel(file_path, header=None, nrows=30)
    weights = {
        "თარიღი": 3.0,
        "დებეტი": 2.0,
        "გასული თანხა": 2.0,
        "კრედიტი": 1.0,
        "შემოსული თანხა": 1.0,
        "მიმღების საიდენტიფიკაციო": 2.0,
        "პარტნიორის საგადასახადო კოდი": 2.0,
        "პარტნიორი": 1.0,
        "დანიშნულება": 1.0,
    }
    best_i, best_score = 0, -1.0
    for i, row in df.iterrows():
        line = " ".join(str(x) for x in row.tolist() if not (x is None or (isinstance(x, float) and pd.isna(x))))
        score = 0.0
        for needle, w in weights.items():
            if needle in line:
                score += w
        if score > best_score:
            best_score, best_i = score, i
    if best_score >= 5.0:
        return int(best_i)
    for i, row in df.iterrows():
        if row.astype(str).str.contains("თარიღი", regex=False).any():
            return int(i)
    return 0

def clean_id(val):
    if pd.isna(val):
        return None
    # Convert to string and remove .0 if it's treated as float
    s = str(val).split('.')[0].strip()
    return s if s else None


def _find_excel_column_danishnuleba(cols):
    """
    BOG/TBC ამონაწერის 'დანიშნულება' (არა 'დამატებითი დანიშნულება').
    """
    for c in cols:
        if str(c).strip() == "დანიშნულება":
            return c
    for c in cols:
        s = str(c)
        if "დანიშნულება" in s and "დამატებითი" not in s:
            return c
    return None


def _find_tbc_partner_column(cols):
    """TBC: 'პარტნიორი' — ზუსტი სათაური (strip), სხვა 'პარტნიორის …' სვეტების გარეშე."""
    for c in cols:
        if str(c).strip() == "პარტნიორი":
            return c
    return None


def _find_tbc_additional_purpose_column(cols):
    """TBC: 'დამატებითი დანიშნულება' — არა ძირითადი 'დანიშნულება' (BOG-ის 'ოპერაციის შინაარსი' არ არის)."""
    for c in cols:
        if str(c).strip() == "დამატებითი დანიშნულება":
            return c
    return None


def _bank_positive_debit_total_ge():
    """
    BOG+TBC ყველა ფაილში დადებითი დებეტის ჯამი — იგივე ფილტრი, რაც get_bank_payments-ში
    (რეკონცილიაციისთვის Excel-ის დონეზე).
    """
    total = 0.0
    for f in list_bog_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = df.columns
            debit_col = next(
                (c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)), None
            )
            if not debit_col:
                continue
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors="coerce")
                if pd.isna(amt) or amt <= 0:
                    continue
                total += float(amt)
        except Exception:
            continue
    for f in list_tbc_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = df.columns
            debit_col = next((c for c in cols if "გასული თანხა" in str(c)), None)
            if not debit_col:
                continue
            df = df[
                ~df[debit_col]
                .astype(str)
                .str.contains("Paid|Out|Amount", case=False, na=False)
            ]
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors="coerce")
                if pd.isna(amt) or amt <= 0:
                    continue
                total += float(amt)
        except Exception:
            continue
    return float(total)


def _enable_windows_console_ansi():
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        h = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if not kernel32.GetConsoleMode(h, ctypes.byref(mode)):
            return
        kernel32.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


def _print_console_colored(msg, color):
    """color: 'red' | 'green'"""
    _enable_windows_console_ansi()
    codes = {"red": "\033[91m", "green": "\033[92m"}
    reset = "\033[0m"
    c = codes.get(color, "")
    if c:
        print(f"{c}{msg}{reset}")
    else:
        print(msg)


def verify_bank_debit_totals(matched_bank_sum, unmatched_rows, exit_on_fail=True):
    """
    ამოწმებს: ბანკის დებეტის ჯამი (Excel) = მიბმული ხაზების ჯამი + არამიბმული ხაზების ჯამი.
    წარმატება — მწვანე; სხვაობა — წითელი; exit_on_fail=True-ზე sys.exit(1).
    """
    tol = 0.02
    bank_total = _bank_positive_debit_total_ge()
    unmatched_sum = sum(float(r.get("თანხა") or 0) for r in unmatched_rows)
    expected = float(matched_bank_sum) + float(unmatched_sum)
    delta = bank_total - expected
    if abs(delta) <= tol:
        _print_console_colored(
            f"  [რეკონცილიაცია OK] ბანკის დებეტი {bank_total:,.2f} ₾ = მიბმული {matched_bank_sum:,.2f} ₾ + არამიბმული {unmatched_sum:,.2f} ₾",
            "green",
        )
        return True
    _print_console_colored(
        f"  [რეკონცილიაცია ჩავარდა] ბანკის დებეტი (Excel) {bank_total:,.2f} ₾ ≠ მიბმული {matched_bank_sum:,.2f} ₾ + არამიბმული {unmatched_sum:,.2f} ₾ = {expected:,.2f} ₾ | სხვაობა {delta:,.2f} ₾",
        "red",
    )
    if exit_on_fail:
        sys.exit(1)
    return False


# BOG-ში „მიმღების საიდენტიფიკაციო“ ზოგჯერ არ ემთხვევა RS-ის საგადასახადო კოდს.
# უმეტესობა იჭერება infer_bog_receiver_id_to_rs_tax_id()-ით (სახელი → name_to_id, ერთნაირი RS ID ყველა ხაზზე).
# აუდიტი: ინფერირებული BOG→RS მაპინგი პერიოდულად შეამოწმეთ ნიმუშ ხაზებზე (ID + მიმღების სახელი + თანხა).
# აქ მხოლოდ გამონაკლისი: ხელი უნდა ჩაერიოს, როცა ავტო ვერ ან საეჭვოა (ამ ლექსიკონს უპირატესობა აქვს).
BOG_RECEIVER_ID_TO_RS_TAX_ID = {}


def _normalize_iban_ge(cell_val):
    """უჯრიდან GE… IBAN — სივრცეების/GEL სუფიქსის გარეშე."""
    if cell_val is None or (isinstance(cell_val, float) and pd.isna(cell_val)):
        return None
    s = re.sub(r"\s+", "", str(cell_val).upper())
    s = s.replace("GEL", "")
    m = re.search(r"GE\d{2}[A-Z0-9]{16,22}", s)
    return m.group(0) if m else None


# BOG/TBC: მიმღების/პარტნიორის IBAN → საგადასახადო კოდი (ხელით; წყარო: ბანკის მიმღების ID / იჯარა)
PARTNER_IBAN_TO_RS_TAX_ID = {
    "GE60BG0000000667583800": "01025003711",
    "GE78BG0000000269727500": "33001015189",
    "GE81BG0000000890516000": "33001023234",
}


def collect_rs_tax_ids(rs_files):
    ids = set()
    for f in sorted(rs_files):
        try:
            df = pd.read_excel(f)
            for org in df['ორგანიზაცია'].dropna().unique():
                m = re.search(r'\((\d+)', str(org))
                if m:
                    ids.add(m.group(1))
        except Exception:
            pass
    return ids


def infer_bog_receiver_id_to_rs_tax_id(rs_files, bog_glob=None):
    """
    BOG raw ID, რომელიც RS საგადასახადო სიაში არაა, მაგრამ მიმღების სახელის ზუსტი ნორმალიზაციით
    ერთადერთ RS ID-ზე მიბმულია ყველა დებეტ ხაზზე → დააბრუნე {bog_id: rs_tax_id}.

    bog_glob: თუ None — იკითხება `list_bog_bank_statement_xlsx()` (ყველა BOG `.xlsx`);
    სხვა შემთხვევაში — glob-ის სტრიქონი (ტესტი/სპეც. შერჩევა).
    """
    if bog_glob is None:
        bog_files = list_bog_bank_statement_xlsx()
    else:
        bog_files = sorted(glob.glob(bog_glob))
    rs_tax_ids = collect_rs_tax_ids(rs_files)
    name_to_id = build_name_to_id_map(rs_files)
    targets = defaultdict(set)
    for f in bog_files:
        try:
            header_idx = find_header_row(f)
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
            if not debit_col or not id_col:
                continue
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors='coerce')
                if pd.isna(amt) or amt <= 0:
                    continue
                raw = clean_id(row[id_col])
                if not raw or not raw.isdigit() or len(raw) < 5:
                    continue
                if raw in rs_tax_ids:
                    continue
                nm = (
                    str(row[name_col]).strip()
                    if name_col and pd.notna(row[name_col])
                    else ''
                )
                if not nm or nm.lower() == 'nan':
                    continue
                key = normalize_name(nm)
                if not key:
                    continue
                tid = name_to_id.get(key)
                if tid:
                    targets[raw].add(tid)
        except Exception:
            pass
    auto = {}
    for raw, tids in targets.items():
        if raw in rs_tax_ids:
            continue
        if len(tids) == 1:
            auto[raw] = next(iter(tids))
    return auto


def get_merged_bog_receiver_map(rs_files):
    """ხელით ლექსიკონი ფარავს ინფერის შედეგს იგივე BOG ID-ზე."""
    auto = infer_bog_receiver_id_to_rs_tax_id(rs_files)
    return {**auto, **BOG_RECEIVER_ID_TO_RS_TAX_ID}


def canonical_tax_id_from_bog_receiver(rec_id, merged_receiver_map=None):
    # თუ merged_receiver_map=None — მხოლოდ ხელით BOG_RECEIVER_ID_TO_RS_TAX_ID (უკან თავსებადობა).
    m = (
        merged_receiver_map
        if merged_receiver_map is not None
        else BOG_RECEIVER_ID_TO_RS_TAX_ID
    )
    if rec_id and rec_id in m:
        return m[rec_id]
    return rec_id


# თუ ტექსტში (სახელი/აღწერა/პარტნიორი) ერთ-ერთი ეს ქვესტრიქონია, სახელით RS ID-ზე მიბმა არ ხდება.
# იფქლის TBC-ში უმეტესობა „იფქლი, BAGAGE22…“ ფორმატითაა — მათი ჩათვლით დავალიანება ემთხვევა ხელით დათვლილ ჯამს (~BOG ID + ყველა TBC „იფქლი“).
# სხვა მომწოდებელზე ყალბი დამთხვევის გამოჩენისას შეგიძლია დაამატო მაგ. ('some_keyword',).
NAME_MATCH_BLOCK_SUBSTRINGS = ()


def skip_name_only_supplier_match(text):
    """სრული ტექსტი ბანკის ველიდან — თუ ეჭვმიტნიურია, დავტოვოთ ID-ით ტრანზაქცია ან missed, არა fuzzy სახელით."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return False
    s = str(text).lower()
    return any(block in s for block in NAME_MATCH_BLOCK_SUBSTRINGS)


def normalize_name(name):
    """სახელის ნორმალიზაცია: ბრჭყალები, ზედმეტი სივრცეები, პრეფიქსები"""
    s = str(name).lower().strip()
    # ამოვშალოთ ბრჭყალები, პუნქტუაცია
    s = re.sub(r'[\"\'„"«»\(\)\[\]]', '', s)
    # ამოვშალოთ პრეფიქსები
    s = re.sub(r'^(შპს|სს|ი/მ|ი\.მ|შ\.პ\.ს)\s*', '', s).strip()
    # ნორმალიზაცია: მრავალ სივრცე -> ერთი
    s = re.sub(r'\s+', ' ', s).strip()
    # ამოვშალოთ "-დღგ" სუფიქსი
    s = re.sub(r'-დღგ$', '', s).strip()
    return s

def build_name_to_id_map(rs_files):
    """RS-ის ფაილებიდან ვაშენებთ სახელი -> ID ლექსიკონს.
    მრავალი ვარიანტი თითოეული კომპანიისთვის.
    """
    name_map = {}
    for f in sorted(rs_files):
        try:
            df = pd.read_excel(f)
            for org in df['ორგანიზაცია'].dropna().unique():
                org_str = str(org)
                match = re.search(r'\((\d+)', org_str)
                if match:
                    s_id = match.group(1)
                    # სრული სახელი ბრჩხილის შემდეგ
                    name_part = re.sub(r'\([^)]*\)\s*', '', org_str).strip()
                    name_clean = normalize_name(name_part)
                    
                    if name_clean and len(name_clean) > 2:
                        # ვარიანტი 1: სრული სახელი
                        name_map[name_clean] = s_id
                        
                        # ვარიანტი 2: რიცხვებისა და წლების გარეშე (მაგ: "შრომა - 2023" -> "შრომა")
                        base_name = re.sub(r'[\s\-]+\d{4}$', '', name_clean).strip()
                        base_name = re.sub(r'\s*-\s*$', '', base_name).strip()
                        if base_name and len(base_name) > 2 and base_name != name_clean:
                            name_map[base_name] = s_id
                        
                        # ვარიანტი 3: პირველი სიტყვა თუ 4+ სიმბოლოა (მაგ: "თოლია ქუთაისი" -> "თოლია")
                        first_word = name_clean.split()[0] if name_clean.split() else ''
                        if first_word and len(first_word) >= 4 and first_word != name_clean:
                            # მხოლოდ თუ უნიკალურია (არ გადაეფაროს სხვა კომპანიას)
                            if first_word not in name_map:
                                name_map[first_word] = s_id
        except:
            pass
    return name_map

def match_partner_to_id(partner_name, name_to_id):
    """
    TBC/BOG ტექსტს ვადარებთ RS-ის სახელ→ID ლექსიკონს (ქვესტრინგები, aliases).
    აუდიტის რისკი: მსგავსი სახელები შეიძლება არასწორ ID-ზე მიებნენ — უპირატესობა მიეცით საგადასახადო კოდით ხაზებს.
    """
    raw_partner = str(partner_name or "")

    # TBC-ში ზოგჯერ პარტნიორის ტექსტი იწყება "შ.პ.ს ,,....'', BAGAGE22, GE...."
    # და naive split(',')[0] ტოვებს მხოლოდ "შ.პ.ს"-ს. ამიტომ ვცდილობთ რამდენიმე კანდიდატს.
    candidates = []
    for token in raw_partner.split(","):
        t = normalize_name(token)
        if not t or len(t) < 3:
            continue
        if re.match(r"^[a-z]{4,}\d{2,}$", t):  # BAGAGE22 / TBCBGE22 და მსგავსი
            continue
        if re.match(r"^ge\d{2}[a-z0-9]+$", t):  # IBAN-like token
            continue
        candidates.append(t)
    # fallback: მთელი სტრიქონის ნორმალიზაცია
    whole = normalize_name(raw_partner)
    if whole and len(whole) >= 3:
        candidates.append(whole)
    # უნიკალური/სტაბილური რიგითობა
    seen = set()
    candidates = [c for c in candidates if not (c in seen or seen.add(c))]
    if not candidates:
        return None
    
    # 0. ცნობილი aliases (ხელით დადგენილი, რაც ავტომატურად ვერ ემთხვევა)
    KNOWN_ALIASES = {
        'ინტერნეიშენალ მარკეტინგ ენდ თრეიდინგი': '420424393',
        'ინტერნეიშენალ მარკეტინგ': '420424393',
        'შრომა': '437078485',       # RS: შრომა - 2023
        'თოლია': '412731281',       # RS: თოლია ქუთაისი
        'სალი': '237113333',        # RS: სალი 2009
        'ელიტფუდი 2': '412761097',  # RS: ელიტ ფუდი 2
        'sah&co': '404995680',      # RS: SAH & Co
        'sahco': '404995680',
        'ჯეომარკი': '205239053',    # RS: ჯეო მარკი
        # იჯარა — საგადასახადო კოდები ბანკის ამონაწერიდან (BOG მიმღების ID); RS ზედნადებში შეიძლება არ იყოს მომწოდებელი
        'ბესიკ კურტანიძე': '01025003711',
        'კურტანიძე ბესიკ': '01025003711',
        'თენიეშვილი ზვიად': '33001015189',
        'ზვიად თენიეშვილი': '33001015189',
        'ხუჭუა კახაბერ': '33001023234',
    }
    for pname in candidates:
        if pname in KNOWN_ALIASES:
            return KNOWN_ALIASES[pname]
        for alias, alias_id in KNOWN_ALIASES.items():
            if alias in pname or pname in alias:
                return alias_id

        # 1. ზუსტი დამთხვევა
        if pname in name_to_id:
            return name_to_id[pname]

        # 2. RS სახელი შედის TBC სახელში
        for rs_name, rs_id in name_to_id.items():
            if len(rs_name) >= 4 and rs_name in pname:
                return rs_id

        # 3. TBC სახელი შედის RS სახელში
        for rs_name, rs_id in name_to_id.items():
            if len(pname) >= 4 and pname in rs_name:
                return rs_id

        # 4. სივრცეების, ტირეების, პუნქტუაციის გარეშე შედარება
        pname_compact = re.sub(r'[\s\-&\.\,\_]', '', pname)
        for rs_name, rs_id in name_to_id.items():
            rs_compact = re.sub(r'[\s\-&\.\,\_]', '', rs_name)
            if len(pname_compact) >= 4 and (pname_compact in rs_compact or rs_compact in pname_compact):
                return rs_id
    
    return None


def manual_payments_csv_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "Financial_Analysis", "manual_payments.csv")


def _journal_find_col(columns, alternatives):
    low = {str(n).strip().lower().replace(" ", "_"): n for n in columns}
    for a in alternatives:
        a2 = str(a).strip().lower().replace(" ", "_")
        if a2 in low:
            return low[a2]
    for n in columns:
        ns = str(n).strip()
        if ns in alternatives:
            return n
    # Excel/ქართული სათაურები: „თანხა (₾)“, „საგადასახადო კოდი“ და ა.შ.
    for a in alternatives:
        a2 = str(a).strip().lower()
        if len(a2) < 3:
            continue
        for n in columns:
            ns = str(n).strip().lower()
            if a2 in ns:
                return n
    return None


def parse_journal_amount(val):
    """
    Excel/CSV ხშირი ფორმატები: 1 234,56 / 1234,56 / 1.234,56 / (1 234)
    pd.to_numeric ხშირად აბრუნებს NaN-ს და ჟურნალში თანხა უჩინარი რჩება.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if isinstance(val, float) and pd.isna(val):
            return 0.0
        return float(val)
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return 0.0
    s = s.replace("\u00a0", " ").replace("'", "").replace("„", "").replace('"', "")
    s = re.sub(r"\((.*)\)", r"\1", s)
    s = s.replace(" ", "")
    if not s:
        return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")
    elif s.count(",") > 1 and "." not in s:
        s = s.replace(",", "")
    elif s.count(".") > 1 and "," not in s:
        parts = s.split(".")
        s = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return max(0.0, float(s))
    except ValueError:
        n = pd.to_numeric(val, errors="coerce")
        return float(n) if not pd.isna(n) else 0.0


def _read_manual_payments_csv(path):
    """კომა, ავტო ან Excel-ის ; გამყოფი — რომ ხაზები არ შევიდეს ერთ სვეტში."""
    encodings = ("utf-8-sig", "utf-8", "cp1251", "cp1252")
    for enc in encodings:
        for sep in (None, ",", ";"):
            try:
                if sep is None:
                    df = pd.read_csv(path, encoding=enc, sep=None, engine="python")
                else:
                    df = pd.read_csv(path, encoding=enc, sep=sep)
                if df.shape[1] >= 2:
                    return df
            except Exception:
                continue
    return pd.read_csv(path, encoding="utf-8-sig", sep=None, engine="python")


def collect_rs_suppliers_by_tax_id(rs_files):
    """უნიკალური საგადასახადო ID → RS-ის ორგანიზაციის სტრიქონი."""
    by_id = {}
    for f in sorted(rs_files):
        try:
            d = pd.read_excel(f)
            if "ორგანიზაცია" not in d.columns:
                continue
            for org in d["ორგანიზაცია"].dropna().unique():
                s = str(org).strip()
                m = re.search(r"\((\d+)", s)
                if not m:
                    continue
                tid = m.group(1)
                by_id[tid] = s
        except Exception:
            pass
    return by_id


def read_manual_journal_full(path):
    """
    CSV ყველა ხაზი: tax_id → amount (ჯამი), comment (ბოლო არაცარიელი), company (არასავალდებულო).
    """
    if not os.path.isfile(path):
        return {}
    try:
        df = _read_manual_payments_csv(path)
    except Exception:
        return {}
    if df.empty or len(df.columns) < 2:
        return {}

    tid_col = _journal_find_col(
        df.columns,
        ("tax_id", "taxid", "საგადასახადო", "საგადასახადო_კოდი", "id"),
    )
    amt_col = _journal_find_col(df.columns, ("amount", "თანხა", "sum", "ჯამი", "paid"))
    company_col = _journal_find_col(
        df.columns,
        ("company", "ორგანიზაცია", "კომპანია", "supplier", "მომწოდებელი"),
    )
    comment_col = _journal_find_col(
        df.columns,
        ("comment", "კომენტარი", "note", "შენიშვნა"),
    )
    if tid_col is None:
        tid_col = df.columns[0]
    if amt_col is None:
        amt_col = df.columns[1]

    by_tid = {}
    for _, row in df.iterrows():
        tid = clean_id(row[tid_col])
        if not tid or not tid.isdigit():
            continue
        if tid not in by_tid:
            by_tid[tid] = {"amount": 0.0, "comment": "", "company": ""}
        amt = parse_journal_amount(row[amt_col])
        by_tid[tid]["amount"] += float(amt)
        if company_col and pd.notna(row[company_col]):
            co = str(row[company_col]).strip()
            if co and co.lower() != "nan":
                by_tid[tid]["company"] = co
        if comment_col and pd.notna(row[comment_col]):
            cm = str(row[comment_col]).strip()
            if cm and cm.lower() != "nan":
                by_tid[tid]["comment"] = cm
    return by_tid


def sync_manual_payments_journal(rs_files):
    """
    manual_payments.csv: ყველა RS მომწოდებელი ერთ სვეტზე; არსებული თანხა/კომენტარი ინახება.
    RS-ში აღარ არსებული ID-ები (ხაზი ჟურნალში დარჩა) — ირჩევა ბოლოში.
    """
    path = manual_payments_csv_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rs_map = collect_rs_suppliers_by_tax_id(rs_files)
    if not rs_map:
        return

    prev = read_manual_journal_full(path) if os.path.isfile(path) else {}
    rs_tids = set(rs_map.keys())

    rows = []
    for tid in sorted(rs_map.keys(), key=lambda t: rs_map[t].lower()):
        org = rs_map[tid]
        p = prev.get(tid, {})
        amt = float(p.get("amount", 0) or 0)
        com = str(p.get("comment", "") or "")
        rows.append(
            {"tax_id": tid, "company": org, "amount": amt, "comment": com}
        )

    orphans = []
    for tid, p in prev.items():
        if tid not in rs_tids:
            org = p.get("company") or "(არაა RS ზედნადებში)"
            amt = float(p.get("amount", 0) or 0)
            com = str(p.get("comment", "") or "")
            orphans.append(
                {"tax_id": tid, "company": org, "amount": amt, "comment": com}
            )
    orphans.sort(key=lambda r: str(r["company"]).lower())
    rows.extend(orphans)

    out_df = pd.DataFrame(rows, columns=["tax_id", "company", "amount", "comment"])
    out_df.to_csv(path, index=False, encoding="utf-8-sig")
    n_manual = sum(1 for r in rows if float(r["amount"] or 0) > 0)
    print(
        f"  manual_payments.csv: {len(rs_map)} კომპანია RS-ით, "
        f"ხელით თანხით >0: {n_manual}"
        + (f", დამატებითი ID (არ RS-ში): {len(orphans)}" if orphans else "")
    )


def load_manual_payments():
    """
    ნაღდი / სხვა არხი — იკითხება manual_payments.csv (ჟურნალის ყველა ხაზიდან amount>0 ჯამდება ID-ზე).
    """
    path = manual_payments_csv_path()
    full = read_manual_journal_full(path)
    return {tid: v["amount"] for tid, v in full.items() if v.get("amount", 0) > 0}


def get_bank_payments(rs_files, reconciliation_exit_on_fail=True):
    """
    BOG/TBC გადახდები RS საგადასახადო ID-ზე: მხოლოდ გასავალი (დადებითი დებეტი / გასული თანხა).
    კრედიტი/შემოსული თანხა აქ არ შედის — სხვა ბლოკებშია (POS, ბარათი, საგადასახადო ნაკადი და ა.შ.).
    სახელით მიბმა: match_partner_to_id — fuzzy; აუდიტისთვის პერიოდულად შეამოწმეთ ID-ით დადასტურებული ხაზები.
    """
    payments = {}
    unmatched_rows = []

    print("Building name-to-ID map from RS (needed for BOG/TBC name matching)...")
    name_to_id = build_name_to_id_map(rs_files)
    print(f"  Mapped {len(name_to_id)} unique company names to IDs")

    _bog_auto = infer_bog_receiver_id_to_rs_tax_id(rs_files)
    bog_receiver_map = {**_bog_auto, **BOG_RECEIVER_ID_TO_RS_TAX_ID}
    print(
        f"  BOG→RS მიმღების ID: {len(bog_receiver_map)} სულ "
        f"(ინფერით {len(_bog_auto)}, ხელით override {len(BOG_RECEIVER_ID_TO_RS_TAX_ID)})"
    )

    print("Reading BOG bank statements...")
    bog_files = list_bog_bank_statement_xlsx()

    bog_by_id = 0
    bog_by_name = 0
    bog_missed = 0
    bog_amt_id = 0.0
    bog_amt_name = 0.0
    bog_amt_missed = 0.0

    for f in bog_files:
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = df.columns
            
            debit_col = next((c for c in cols if 'დებეტი' in str(c) and 'ბრუნვა' not in str(c)), None)
            id_col = next((c for c in cols if 'მიმღების საიდენტიფიკაციო' in str(c)), None)
            name_col = next((c for c in cols if 'მიმღების დასახელება' in str(c)), None)
            desc_col = next((c for c in cols if 'ოპერაციის შინაარსი' in str(c)), None)
            purpose_col = _find_excel_column_danishnuleba(cols)
            date_col = next((c for c in cols if 'თარიღი' in str(c)), None)

            if not debit_col:
                continue

            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors='coerce')
                if pd.isna(amt) or amt <= 0:
                    continue

                # Strategy 1: მიმღების ID-ით (ზუსტი + ინფერირებული BOG→RS)
                raw_rec_id = clean_id(row[id_col]) if id_col else None
                rec_id = canonical_tax_id_from_bog_receiver(raw_rec_id, bog_receiver_map)
                if rec_id and rec_id.isdigit() and len(rec_id) >= 5:
                    payments[rec_id] = payments.get(rec_id, 0.0) + float(amt)
                    bog_by_id += 1
                    bog_amt_id += float(amt)
                    continue

                # Strategy 2: მიმღების სახელით (fallback)
                matched_id = None
                if name_col and pd.notna(row[name_col]) and not skip_name_only_supplier_match(row[name_col]):
                    matched_id = match_partner_to_id(str(row[name_col]), name_to_id)
                # Strategy 3: ოპერაციის შინაარსით (second fallback)
                if not matched_id and desc_col and pd.notna(row[desc_col]) and not skip_name_only_supplier_match(row[desc_col]):
                    matched_id = match_partner_to_id(str(row[desc_col]), name_to_id)
                # Strategy 4: დანიშნულება (სხვაგვარად იშვიათად სრულია მიმღების სახელი/RS-თან მიბმა)
                if not matched_id and purpose_col and pd.notna(row[purpose_col]) and not skip_name_only_supplier_match(row[purpose_col]):
                    matched_id = match_partner_to_id(str(row[purpose_col]), name_to_id)
                # Strategy 5: მიმღების ანგარიში (IBAN) — იჯარა/ფიზიკური პირი ID-ის გარეშე
                if not matched_id:
                    acct_col = next(
                        (c for c in cols if "მიმღების ანგარიშის ნომერი" in str(c)), None
                    )
                    if acct_col and pd.notna(row[acct_col]):
                        ib = _normalize_iban_ge(row[acct_col])
                        if ib and ib in PARTNER_IBAN_TO_RS_TAX_ID:
                            matched_id = PARTNER_IBAN_TO_RS_TAX_ID[ib]

                if matched_id:
                    payments[matched_id] = payments.get(matched_id, 0.0) + float(amt)
                    bog_by_name += 1
                    bog_amt_name += float(amt)
                else:
                    bog_missed += 1
                    bog_amt_missed += float(amt)
                    unmatched_rows.append(
                        {
                            "ბანკი": "BOG",
                            "ფაილი": os.path.basename(f),
                            "თარიღი": _excel_cell(row, date_col),
                            "თანხა": float(amt),
                            "საგადასახადო_ID": raw_rec_id or "",
                            "მიმღები_სახელი": _excel_cell(row, name_col),
                            "ოპერაციის_შინაარსი": _excel_cell(row, desc_col),
                            "დანიშნულება": _excel_cell(row, purpose_col)
                            if purpose_col
                            else "",
                            "მიზეზი": "RS მომწოდებელთან ვერ მიბმულა (ID/სახელი/აღწერა/დანიშნულება)",
                        }
                    )
        except Exception as e:
            print(f"Error reading BOG {f}: {e}")

    print(
        f"  BOG: ID-ით: {bog_by_id} ({bog_amt_id:,.2f} ₾), "
        f"სახელით/აღწერით/დანიშნულებით: {bog_by_name} ({bog_amt_name:,.2f} ₾), "
        f"ვერ დაემთხვა: {bog_missed} ({bog_amt_missed:,.2f} ₾)"
    )

    print("Reading TBC bank statements...")
    tbc_files = list_tbc_bank_statement_xlsx()
    tbc_by_id = 0
    tbc_by_name = 0
    tbc_missed = 0
    tbc_amt_id = 0.0
    tbc_amt_name = 0.0
    tbc_amt_missed = 0.0

    for f in tbc_files:
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = df.columns
            
            debit_col = next((c for c in cols if 'გასული თანხა' in str(c)), None)
            id_col = next((c for c in cols if 'პარტნიორის საგადასახადო კოდი' in str(c)), None)
            partner_col = _find_tbc_partner_column(cols)
            purpose_col = _find_excel_column_danishnuleba(cols)
            tbc_extra_purpose_col = _find_tbc_additional_purpose_column(cols)
            date_col = next((c for c in cols if 'თარიღი' in str(c)), None)

            if not debit_col:
                continue

            # გავფილტროთ ინგლისური header სტრიქონები
            df = df[~df[debit_col].astype(str).str.contains('Paid|Out|Amount', case=False, na=False)]

            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors='coerce')
                if pd.isna(amt) or amt <= 0:
                    continue

                # Strategy 1: ID-ით ძებნა (ზუსტი)
                rec_id = clean_id(row[id_col]) if id_col else None
                if rec_id and rec_id.isdigit() and len(rec_id) >= 5:
                    payments[rec_id] = payments.get(rec_id, 0.0) + float(amt)
                    tbc_by_id += 1
                    tbc_amt_id += float(amt)
                    continue

                # Strategy 2–3: პარტნიორი, შემდეგ დანიშნულება (ერთი ფილტრი არ უნდა გამორიცხოს მეორე)
                matched_id = None
                if partner_col and pd.notna(row[partner_col]) and not skip_name_only_supplier_match(row[partner_col]):
                    matched_id = match_partner_to_id(str(row[partner_col]), name_to_id)
                if not matched_id and purpose_col and pd.notna(row[purpose_col]) and not skip_name_only_supplier_match(row[purpose_col]):
                    matched_id = match_partner_to_id(str(row[purpose_col]), name_to_id)
                # Strategy 4: პარტნიორის ანგარიში (IBAN) — როცა საგადასახადო კოდი ცარიელია
                if not matched_id:
                    iban_col = next(
                        (c for c in cols if "პარტნიორის ანგარიში" in str(c)), None
                    )
                    if iban_col and pd.notna(row[iban_col]):
                        ib = _normalize_iban_ge(row[iban_col])
                        if ib and ib in PARTNER_IBAN_TO_RS_TAX_ID:
                            matched_id = PARTNER_IBAN_TO_RS_TAX_ID[ib]

                if matched_id:
                    payments[matched_id] = payments.get(matched_id, 0.0) + float(amt)
                    tbc_by_name += 1
                    tbc_amt_name += float(amt)
                else:
                    tbc_missed += 1
                    tbc_amt_missed += float(amt)
                    can_partner = (
                        partner_col
                        and pd.notna(row[partner_col])
                        and not skip_name_only_supplier_match(row[partner_col])
                    )
                    can_purpose = (
                        purpose_col
                        and pd.notna(row[purpose_col])
                        and not skip_name_only_supplier_match(row[purpose_col])
                    )
                    if not can_partner and not can_purpose:
                        reason = "სახელით/დანიშნულებით მიბმა გამოტოვებული (ფილტრი)"
                    else:
                        reason = "RS მომწოდებელთან ვერ მიბმულა (პარტნიორი/დანიშნულება)"
                    unmatched_rows.append(
                        {
                            "ბანკი": "TBC",
                            "ფაილი": os.path.basename(f),
                            "თარიღი": _excel_cell(row, date_col),
                            "თანხა": float(amt),
                            "საგადასახადო_ID": rec_id or "",
                            "მიმღები_სახელი": _excel_cell(row, partner_col) if partner_col else "",
                            # TBC-ს BOG-ის მსგავსი „ოპერაციის შინაარსი“ სვეტი არ აქვს — აქ მხოლოდ „დამატებითი დანიშნულება“.
                            "ოპერაციის_შინაარსი": _excel_cell(row, tbc_extra_purpose_col)
                            if tbc_extra_purpose_col
                            else "",
                            "დანიშნულება": _excel_cell(row, purpose_col)
                            if purpose_col
                            else "",
                            "მიზეზი": reason,
                        }
                    )
        except Exception as e:
            print(f"Error reading TBC {f}: {e}")

    print(
        f"  TBC: ID-ით: {tbc_by_id} ({tbc_amt_id:,.2f} ₾), "
        f"სახელით/დანიშნულებით: {tbc_by_name} ({tbc_amt_name:,.2f} ₾), "
        f"ვერ დაემთხვა: {tbc_missed} ({tbc_amt_missed:,.2f} ₾)"
    )

    bank_grand = sum(payments.values())
    print(f"  ბანკის ჯამი (უნიკალური ID-ებით, BOG+TBC ერთ ქოლგაში): {bank_grand:,.2f} ₾")

    reconciliation_ok = verify_bank_debit_totals(
        bank_grand, unmatched_rows, exit_on_fail=reconciliation_exit_on_fail
    )

    manual_map = load_manual_payments()
    if manual_map:
        man_sum = sum(manual_map.values())
        for tid, amt in manual_map.items():
            payments[tid] = payments.get(tid, 0.0) + amt
        print(
            f"  ხელით გადახდები (manual_payments.csv): {len(manual_map)} საგად. ID, "
            f"+{man_sum:,.2f} ₾ → სულ გადახდების ლექსიკონი: {sum(payments.values()):,.2f} ₾"
        )

    return payments, unmatched_rows, reconciliation_ok

def run():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    tbc_card_income_bundle = collect_tbc_card_income(script_dir)
    bog_pos_income_bundle = collect_bog_pos_terminal_income(script_dir)
    pos_terminal_all_rows = list(tbc_card_income_bundle.get("lines") or []) + list(
        bog_pos_income_bundle.get("lines") or []
    )
    pos_terminal_income_bundle = merge_pos_terminal_income(
        tbc_card_income_bundle, bog_pos_income_bundle
    )
    print(
        f"  TBC ბარათის შემოსავალი (კონფიგი): {tbc_card_income_bundle['line_count']} ხაზი, "
        f"{tbc_card_income_bundle['total_ge']:,.2f} ₾"
    )
    print(
        "  POS ტერმინალი (TBC+BOG): "
        f"TBC {pos_terminal_income_bundle['tbc_total_ge']:,.2f} ₾ | "
        f"BOG {pos_terminal_income_bundle['bog_total_ge']:,.2f} ₾ | "
        f"ჯამი {pos_terminal_income_bundle['total_ge']:,.2f} ₾"
    )

    tbc_expenses_bundle = collect_tbc_expense_categories(script_dir)
    _te_lines = sum(
        int(c.get("line_count") or 0)
        for c in (tbc_expenses_bundle.get("categories") or [])
    )
    print(
        f"  TBC ხარჯები (კატეგორიები): {_te_lines} ხაზი, "
        f"{tbc_expenses_bundle.get('grand_total_ge', 0):,.2f} ₾"
    )
    tbc_samurneo_bundle = collect_tbc_samurneo_flow(script_dir)
    bog_samurneo_bundle = collect_bog_samurneo_flow(script_dir)
    samurneo_bundle = merge_samurneo_flows(tbc_samurneo_bundle, bog_samurneo_bundle)
    tax_flow_bundle = collect_tax_flow(script_dir)
    tbc_foodmart_cashback_bundle = collect_tbc_foodmart_cashback(script_dir)
    print(
        "  სამეურნეო / საქმიანობისთვის აუცილებელი ხარჯი (BOG+TBC, ნიშნით): "
        f"გატანა {samurneo_bundle['expense_total_ge']:,.2f} ₾ | "
        f"შემოტანა {samurneo_bundle['return_total_ge']:,.2f} ₾ | "
        f"net {samurneo_bundle['net_ge']:,.2f} ₾"
    )
    print(
        "  საგადასახადო (BOG+TBC): "
        f"გადარიცხული {tax_flow_bundle['out_total_ge']:,.2f} ₾ | "
        f"ჩარიცხული {tax_flow_bundle['in_total_ge']:,.2f} ₾ | "
        f"net {tax_flow_bundle['net_ge']:,.2f} ₾"
    )
    print(
        "  TBC ფუდმარტი ქეშბექი: "
        f"{tbc_foodmart_cashback_bundle['line_count']} ხაზი, "
        f"{tbc_foodmart_cashback_bundle['total_ge']:,.2f} ₾"
    )

    print("Reading RS files...")
    rs_files = list_rs_waybill_files()
    all_rs = []

    for f in rs_files:
        try:
            df = pd.read_excel(f)
            df['file_source'] = os.path.basename(f)
            all_rs.append(df)
        except Exception as e:
            print(f"Error {f}: {e}")

    if not all_rs:
        print("No RS files found!")
        data = {
            "suppliers": [],
            "waybills": [],
            "tbc_card_income": {
                "label_ka": tbc_card_income_bundle["label_ka"],
                "total_ge": float(tbc_card_income_bundle["total_ge"]),
                "line_count": int(tbc_card_income_bundle["line_count"]),
                "rows_preview": tbc_card_income_bundle["lines"][:300],
                "monthly_summary": _monthly_summary(tbc_card_income_bundle["lines"]),
            },
            "pos_terminal_income": pos_terminal_income_bundle,
            "tbc_expenses": tbc_expenses_public_json(tbc_expenses_bundle),
            "tbc_samurneo": samurneo_bundle,
            "tax_flow": tax_flow_bundle,
            "tbc_foodmart_cashback": tbc_foodmart_cashback_bundle,
            "bank_unmatched_analysis": analyze_bank_unmatched_rows([]),
            "meta": {
                "manual_payments_total": 0.0,
                "manual_payments_rows_with_amount": 0,
                "suppliers_only_journal_or_bank": 0,
                "bank_orphan_total_ge": 0.0,
                "bank_unmatched_total_ge": 0.0,
                "bank_unmatched_line_count": 0,
                "bank_unmatched_categorized_total_ge": 0.0,
                "bank_unmatched_uncategorized_total_ge": 0.0,
                "bank_unmatched_dynamic_promoted_total_ge": 0.0,
                "bank_unmatched_confidence_high_ge": 0.0,
                "bank_unmatched_confidence_medium_ge": 0.0,
                "bank_unmatched_confidence_low_ge": 0.0,
                "bank_unmatched_manual_override_approved_lines": 0,
                "bank_unmatched_manual_override_rejected_lines": 0,
                "tbc_card_income_total_ge": float(tbc_card_income_bundle["total_ge"]),
                "tbc_card_income_line_count": int(tbc_card_income_bundle["line_count"]),
                "pos_terminal_income_total_ge": float(pos_terminal_income_bundle.get("total_ge") or 0),
                "pos_terminal_income_tbc_total_ge": float(pos_terminal_income_bundle.get("tbc_total_ge") or 0),
                "pos_terminal_income_bog_total_ge": float(pos_terminal_income_bundle.get("bog_total_ge") or 0),
                "tbc_expenses_grand_total_ge": float(
                    tbc_expenses_bundle.get("grand_total_ge") or 0
                ),
                "tbc_expenses_operating_total_ge": float(
                    tbc_expenses_bundle.get("grand_total_operating_expense_ge") or 0
                ),
                "tbc_expenses_treasury_total_ge": float(
                    tbc_expenses_bundle.get("grand_total_state_treasury_ge") or 0
                ),
                "tbc_expenses_total_lines": sum(
                    int(c.get("line_count") or 0)
                    for c in (tbc_expenses_bundle.get("categories") or [])
                ),
                "tbc_samurneo_expense_total_ge": float(samurneo_bundle.get("expense_total_ge") or 0),
                "tbc_samurneo_return_total_ge": float(samurneo_bundle.get("return_total_ge") or 0),
                "tbc_samurneo_net_ge": float(samurneo_bundle.get("net_ge") or 0),
                "tax_out_total_ge": float(tax_flow_bundle.get("out_total_ge") or 0),
                "tax_in_total_ge": float(tax_flow_bundle.get("in_total_ge") or 0),
                "tax_treasury_in_total_ge": float(tax_flow_bundle.get("treasury_in_total_ge") or 0),
                "tax_treasury_in_line_count": int(tax_flow_bundle.get("treasury_in_line_count") or 0),
                "tax_net_ge": float(tax_flow_bundle.get("net_ge") or 0),
                "tbc_foodmart_cashback_total_ge": float(tbc_foodmart_cashback_bundle.get("total_ge") or 0),
                "tbc_foodmart_cashback_line_count": int(tbc_foodmart_cashback_bundle.get("line_count") or 0),
            },
        }
    else:
        df = pd.concat(all_rs, ignore_index=True)
        print(
            "  RS: ნომინალი + რეალური ჯამი + დაბრუნება — data.json (total_cancelled შიგნით, UI-ზე არა)."
        )

        # Parse Dates safely
        if 'გააქტიურების თარ.' in df.columns:
            df['გააქტიურების თარ.'] = df['გააქტიურების თარ.'].astype(str)
        
        # Flags checking text
        df['უკან დაბრუნება (ფლეგი)'] = df['ტიპი'].astype(str).str.contains('უკან დაბრუნება', case=False, na=False)
        df['გაუქმებული (ფლეგი)'] = df['სტატუსი'].astype(str).str.contains('გაუქმებული', case=False, na=False)
        
        # Calculate amounts
        raw_amt = pd.to_numeric(df['თანხა'], errors='coerce').fillna(0.0)
        df['ნომინალური თანხა'] = raw_amt
        df['გაუქმებული_თანხა'] = raw_amt.where(df['გაუქმებული (ფლეგი)'], 0.0)

        def get_effective(row):
            val = float(pd.to_numeric(row['თანხა'], errors='coerce') or 0)
            if row['გაუქმებული (ფლეგი)']:
                return 0.0
            if row['უკან დაბრუნება (ფლეგი)']:
                v = float(val) if not pd.isna(val) else 0.0
                return v if v < 0 else -v
            return val

        def get_returned(row):
            val = float(pd.to_numeric(row['თანხა'], errors='coerce') or 0)
            if row['უკან დაბრუნება (ფლეგი)'] and not row['გაუქმებული (ფლეგი)']:
                return val
            return 0.0

        df['ეფექტური თანხა'] = df.apply(get_effective, axis=1)
        df['დაბრუნებული თანხა'] = df.apply(get_returned, axis=1)
        df['_აქტიური_ხაზი'] = (~df['გაუქმებული (ფლეგი)']).astype(int)

        # Group by Organization
        agg_df = df.groupby('ორგანიზაცია').agg(
            waybills_count=('_აქტიური_ხაზი', 'sum'),
            total_nominal=('ნომინალური თანხა', 'sum'),
            total_cancelled=('გაუქმებული_თანხა', 'sum'),
            total_returned=('დაბრუნებული თანხა', 'sum'),
            total_effective=('ეფექტური თანხა', 'sum'),
        ).reset_index()
        
        # ----- ხელით გადახდების ჟურნალი (ყველა კომპანია RS-იდან) -----
        sync_manual_payments_journal(rs_files)
        # ----- Merge with Bank Payments -----
        bank_payments, bank_unmatched_rows, _bank_reconciliation_ok = get_bank_payments(
            rs_files
        )
        bank_unmatched_sum = sum(
            float(r.get("თანხა") or 0) for r in bank_unmatched_rows
        )
        bank_unmatched_analysis = analyze_bank_unmatched_rows(bank_unmatched_rows)
        print(
            f"  ბანკი — არამიბმული ხაზები (RS-თან): {len(bank_unmatched_rows)} ხაზი, "
            f"{bank_unmatched_sum:,.2f} ₾"
        )
        print(
            "  ბანკი — ავტომატური კატეგორიზაცია: "
            f"{bank_unmatched_analysis['categorized_total_ge']:,.2f} ₾ "
            f"(არაკატეგორიზებული: {bank_unmatched_analysis['uncategorized_total_ge']:,.2f} ₾)"
        )
        if bank_unmatched_analysis.get("manual_override_approved_lines", 0) or bank_unmatched_analysis.get("manual_override_rejected_lines", 0):
            print(
                "    ხელით override: approve "
                f"{bank_unmatched_analysis.get('manual_override_approved_lines', 0)} | "
                f"reject {bank_unmatched_analysis.get('manual_override_rejected_lines', 0)}"
            )
        if float(bank_unmatched_analysis.get("dynamic_promoted_total_ge") or 0) > 0:
            print(
                "    მათგან ავტო-ჯგუფებით დაჭერილი: "
                f"{bank_unmatched_analysis['dynamic_promoted_total_ge']:,.2f} ₾ "
                f"({bank_unmatched_analysis.get('dynamic_promoted_line_count', 0)} ხაზი)"
            )

        def extract_supplier_id(org_name):
            match = re.search(r'\((\d+)', str(org_name))
            return match.group(1) if match else None

        agg_df['supplier_id'] = agg_df['ორგანიზაცია'].apply(extract_supplier_id)
        
        def get_paid_amount(s_id):
            if not s_id: return 0.0
            return bank_payments.get(s_id, 0.0)
            
        agg_df['total_paid'] = agg_df['supplier_id'].apply(get_paid_amount)
        manual_only = load_manual_payments()

        def get_manual_paid(s_id):
            if not s_id:
                return 0.0
            return float(manual_only.get(s_id, 0) or 0)

        agg_df['manual_paid'] = agg_df['supplier_id'].apply(get_manual_paid)
        agg_df['bank_paid'] = agg_df['total_paid'] - agg_df['manual_paid']
        agg_df['total_debt'] = agg_df['total_effective'] - agg_df['total_paid']

        rs_ids = set(agg_df['supplier_id'].dropna().astype(str))
        paid_mapped_to_rs = sum(bank_payments.get(sid, 0.0) for sid in rs_ids)
        bank_orphan = sum(amt for pid, amt in bank_payments.items() if pid not in rs_ids)
        print(
            f"Reconciliation: RS მომწოდებლებზე მიბმული გადახდების ჯამი: {paid_mapped_to_rs:,.2f} ₾ | "
            f"ბანკშია მაგრამ RS სიაში ID არ უნდა: {bank_orphan:,.2f} ₾"
        )

        # RS ზედნადებში არ არსებული, მაგრამ manual_payments.csv-ში ან ბანკში (ორფანი) არის
        jfull = read_manual_journal_full(manual_payments_csv_path())
        bank_tids_positive = {
            k
            for k, v in bank_payments.items()
            if k and float(v or 0) != 0
        }
        extra_rows = []
        extra_supplier_count = 0
        for tid in set(jfull.keys()) | bank_tids_positive:
            if tid in rs_ids:
                continue
            tp = float(bank_payments.get(tid, 0) or 0)
            mp = float((jfull.get(tid) or {}).get("amount", 0) or 0)
            if tp == 0 and mp == 0:
                continue
            co = str((jfull.get(tid) or {}).get("company") or "").strip()
            if not co or co == "(არაა RS ზედნადებში)":
                co = f"({tid}) — არაა RS ზედნადებში"
            extra_rows.append(
                {
                    "ორგანიზაცია": co,
                    "waybills_count": 0,
                    "total_nominal": 0.0,
                    "total_cancelled": 0.0,
                    "total_returned": 0.0,
                    "total_effective": 0.0,
                    "supplier_id": tid,
                    "total_paid": tp,
                    "manual_paid": mp,
                    "bank_paid": tp - mp,
                    "total_debt": 0.0 - tp,
                }
            )
        if extra_rows:
            extra_supplier_count = len(extra_rows)
            agg_df = pd.concat(
                [agg_df, pd.DataFrame(extra_rows)], ignore_index=True
            )
            print(
                f"  დეშბორდი: +{extra_supplier_count} მომწოდებელი "
                f"(მხოლოდ ჟურნალი/ბანკი, RS ზედნადის გარეშე)"
            )

        # Sort
        agg_df = agg_df.sort_values('total_effective', ascending=False)
        
        # Cleanup
        del agg_df['supplier_id'] 

        suppliers_data = agg_df.replace({float('nan'): None}).to_dict(orient='records')

        download_dir = os.path.join(script_dir, "download")
        write_suppliers_excel(suppliers_data, download_dir)
        write_bank_unmatched_excel(bank_unmatched_rows, download_dir)
        write_bank_unmatched_categories_excel(bank_unmatched_analysis, download_dir)
        write_bank_unclassified_top_excel(bank_unmatched_analysis, download_dir)
        write_bank_overrides_audit_excel(bank_unmatched_analysis, download_dir)

        safe_cols = {
            'გააქტიურების თარ.': 'date',
            'ორგანიზაცია': 'supplier',
            'ზედნადები': 'waybill_number',
            'თანხა': 'nominal_amount',
            'სტატუსი': 'status',
            'ტიპი': 'type',
            'ეფექტური თანხა': 'effective_amount'
        }
        
        waybills_df = df[[c for c in safe_cols.keys() if c in df.columns]].rename(columns=safe_cols)
        waybills_df = waybills_df.fillna("N/A")
        
        waybills_data = waybills_df.to_dict(orient='records')
        
        manual_grand = float(sum(manual_only.values()))
        data = {
            "suppliers": suppliers_data,
            "waybills": waybills_data,
            "tbc_card_income": {
                "label_ka": tbc_card_income_bundle["label_ka"],
                "total_ge": float(tbc_card_income_bundle["total_ge"]),
                "line_count": int(tbc_card_income_bundle["line_count"]),
                "rows_preview": tbc_card_income_bundle["lines"][:300],
                "monthly_summary": _monthly_summary(tbc_card_income_bundle["lines"]),
            },
            "pos_terminal_income": pos_terminal_income_bundle,
            "tbc_expenses": tbc_expenses_public_json(tbc_expenses_bundle),
            "tbc_samurneo": samurneo_bundle,
            "tax_flow": tax_flow_bundle,
            "tbc_foodmart_cashback": tbc_foodmart_cashback_bundle,
            "bank_unmatched_analysis": bank_unmatched_analysis,
            "meta": {
                "manual_payments_total": manual_grand,
                "manual_payments_rows_with_amount": len(
                    [a for a in manual_only.values() if a > 0]
                ),
                "suppliers_only_journal_or_bank": extra_supplier_count,
                "bank_orphan_total_ge": float(bank_orphan),
                "bank_unmatched_total_ge": float(bank_unmatched_sum),
                "bank_unmatched_line_count": len(bank_unmatched_rows),
                "bank_unmatched_categorized_total_ge": float(
                    bank_unmatched_analysis.get("categorized_total_ge") or 0
                ),
                "bank_unmatched_uncategorized_total_ge": float(
                    bank_unmatched_analysis.get("uncategorized_total_ge") or 0
                ),
                "bank_unmatched_dynamic_promoted_total_ge": float(
                    bank_unmatched_analysis.get("dynamic_promoted_total_ge") or 0
                ),
                "bank_unmatched_confidence_high_ge": float(
                    (bank_unmatched_analysis.get("confidence_totals") or {}).get("high", 0)
                ),
                "bank_unmatched_confidence_medium_ge": float(
                    (bank_unmatched_analysis.get("confidence_totals") or {}).get("medium", 0)
                ),
                "bank_unmatched_confidence_low_ge": float(
                    (bank_unmatched_analysis.get("confidence_totals") or {}).get("low", 0)
                ),
                "bank_unmatched_manual_override_approved_lines": int(
                    bank_unmatched_analysis.get("manual_override_approved_lines", 0)
                ),
                "bank_unmatched_manual_override_rejected_lines": int(
                    bank_unmatched_analysis.get("manual_override_rejected_lines", 0)
                ),
                "tbc_card_income_total_ge": float(tbc_card_income_bundle["total_ge"]),
                "tbc_card_income_line_count": int(tbc_card_income_bundle["line_count"]),
                "pos_terminal_income_total_ge": float(pos_terminal_income_bundle.get("total_ge") or 0),
                "pos_terminal_income_tbc_total_ge": float(pos_terminal_income_bundle.get("tbc_total_ge") or 0),
                "pos_terminal_income_bog_total_ge": float(pos_terminal_income_bundle.get("bog_total_ge") or 0),
                "tbc_expenses_grand_total_ge": float(
                    tbc_expenses_bundle.get("grand_total_ge") or 0
                ),
                "tbc_expenses_operating_total_ge": float(
                    tbc_expenses_bundle.get("grand_total_operating_expense_ge") or 0
                ),
                "tbc_expenses_treasury_total_ge": float(
                    tbc_expenses_bundle.get("grand_total_state_treasury_ge") or 0
                ),
                "tbc_expenses_total_lines": sum(
                    int(c.get("line_count") or 0)
                    for c in (tbc_expenses_bundle.get("categories") or [])
                ),
                "tbc_samurneo_expense_total_ge": float(samurneo_bundle.get("expense_total_ge") or 0),
                "tbc_samurneo_return_total_ge": float(samurneo_bundle.get("return_total_ge") or 0),
                "tbc_samurneo_net_ge": float(samurneo_bundle.get("net_ge") or 0),
                "tax_out_total_ge": float(tax_flow_bundle.get("out_total_ge") or 0),
                "tax_in_total_ge": float(tax_flow_bundle.get("in_total_ge") or 0),
                "tax_treasury_in_total_ge": float(tax_flow_bundle.get("treasury_in_total_ge") or 0),
                "tax_treasury_in_line_count": int(tax_flow_bundle.get("treasury_in_line_count") or 0),
                "tax_net_ge": float(tax_flow_bundle.get("net_ge") or 0),
                "tbc_foodmart_cashback_total_ge": float(tbc_foodmart_cashback_bundle.get("total_ge") or 0),
                "tbc_foodmart_cashback_line_count": int(tbc_foodmart_cashback_bundle.get("line_count") or 0),
            },
        }

    download_dir = os.path.join(script_dir, "download")
    write_tbc_card_income_excel(tbc_card_income_bundle["lines"], download_dir)
    write_pos_terminal_income_excel(
        pos_terminal_income_bundle, download_dir, pos_terminal_all_rows
    )
    write_tbc_expenses_excel(tbc_expenses_bundle, download_dir)
    write_tbc_samurneo_excel(samurneo_bundle, download_dir)
    write_tax_flow_excel(tax_flow_bundle, download_dir)
    write_treasury_incoming_excel(tax_flow_bundle, download_dir)
    write_tbc_foodmart_cashback_excel(tbc_foodmart_cashback_bundle, download_dir)

    out_dir = r"c:\Users\tengiz\OneDrive\Desktop\AI აგენტი\rs-dashboard\public"
    os.makedirs(out_dir, exist_ok=True)
    published = publish_download_excels(download_dir, out_dir)
    data["download_files"] = published.get("files", [])
    data["download_zip_file"] = published.get("zip_file", "")
    out_file = os.path.join(out_dir, "data.json")
    
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Data generated at {out_file}")

if __name__ == "__main__":
    run()
