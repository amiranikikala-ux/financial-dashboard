"""
Shared constants, default configurations, and tiny utility functions
used across the dashboard pipeline modules.
"""
import json
import re
from collections import defaultdict

import pandas as pd


# ---------------------------------------------------------------------------
# კომპანიის თვითიდენტიფიკაცია
# ---------------------------------------------------------------------------

# შპს ჯეო ფუდთაიმის საგადასახადო ID. გამოიყენება მომწოდებლების ცხრილიდან
# საკუთარი ფირმის გასაფილტრად (RS-ის შიდა ზედნადები ან მაღაზიათშორისი
# გადარიცხვა მომწოდებლად არ უნდა ჩაითვალოს). ასევე VAT შედარებაში — Subjects
# Issued Filter-ად. ერთ წყაროს ვინახავთ, რომ ცვლილება ერთხელ გავაკეთოთ.
OWN_TAX_ID = "400333858"


# ---------------------------------------------------------------------------
# ბუღალტრული / ბიზნეს ლეიბლები
# ---------------------------------------------------------------------------

SAMURNEO_LEDGER_CLASS_KA = "კომპანიის საქმიანობისთვის აუცილებელი ხარჯი"
SAMURNEO_LABEL_KA = "საქმიანობისთვის აუცილებელი ხარჯი (სამეურნეო მოძრაობა)"
SAMURNEO_ACCOUNTING_NOTE_KA = (
    "ბუღალტრული მნიშვნელობა: კომპანიის საქმიანობისთვის აუცილებელი ხარჯის მოძრაობა. "
    "ტექნიკურად: ბანკის ხაზები ერთდება tbc_samurneo_patterns.json-ის ტექსტურ ფილტრთან; "
    "საგადასახადო/აუდიტის დასკვნა — პირველადი დოკუმენტაციით."
)
SAMURNEO_EXPENSE_DIRECTION_KA = f"{SAMURNEO_LEDGER_CLASS_KA} — გასვლა"
SAMURNEO_RETURN_DIRECTION_KA = f"{SAMURNEO_LEDGER_CLASS_KA} — დაბრუნება (შემოტანა)"

BANK_UNMATCHED_LEDGER_NOTE_KA = (
    "\u201Eარამიბმული ბანკი\u201D ნიშნავს: ხაზი ვერ მიება RS ზედნადების მომწოდებლის საგადასახადო ID-ს \u2014 "
    "არა ის, რომ ოპერაცია ხარჯი არაა. ბარათით შეძენა (მათ შორის სასურსაო/საკვები, ოფისი/საჩუქრები, მასალა, საკუთარი ქსელი), "
    "ნაღდი განაღდება/ბანკომატი, საბანკო ანგარიშის პაკეტი და მსგავსი ავტო-კატეგორიები "
    "ბუღალტრულად კომპანიის საქმიანობისთვის ხარჯებია; საგადასახადო დასკვნა — პირველადი დოკუმენტაციით."
)

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
BOG_EXPENSES_LEDGER_NOTE_KA = (
    "BOG კატეგორიები: იგივე წესები რაც tbc_expense_categories.json-ში; "
    "თუ კატეგორია ვერ განისაზღვრა — 'BOG — სხვა ხარჯი'. "
    "P&L-ისთვის BOG დებეტის ყველა ხაზი ითვლება ხარჯად."
)

# ---------------------------------------------------------------------------
# Accounting role + expense IDs
# ---------------------------------------------------------------------------

ACCOUNTING_ROLE_OPERATING = "operating_expense"
ACCOUNTING_ROLE_STATE_TREASURY = "state_treasury"
BOG_OTHER_EXPENSE_ID = "bog_other_expense"
BOG_OTHER_EXPENSE_LABEL_KA = "BOG — სხვა ხარჯი"
TBC_OTHER_EXPENSE_ID = "tbc_other_expense"
TBC_OTHER_EXPENSE_LABEL_KA = "TBC — სხვა ხარჯი"

# ---------------------------------------------------------------------------
# Aging buckets
# ---------------------------------------------------------------------------

AGING_BUCKET_ORDER = ["0-30", "31-60", "61-90", "91-180", "180+"]

# ---------------------------------------------------------------------------
# Imported products
# ---------------------------------------------------------------------------

IMPORTED_PRODUCTS_SHEET_NAME = "Grid"
FULL_ROLLUP_ROW_CAP = 10_000_000
IMPORTED_PRODUCTS_ROWS_PREVIEW_LIMIT = 50_000
IMPORTED_PRODUCTS_TOP_LIMIT = FULL_ROLLUP_ROW_CAP
IMPORTED_PRODUCTS_SUPPLIER_TOP_PRODUCTS_LIMIT = FULL_ROLLUP_ROW_CAP
IMPORTED_PRODUCTS_PRODUCT_TOP_SUPPLIERS_LIMIT = FULL_ROLLUP_ROW_CAP
IMPORTED_PRODUCTS_PRODUCTS_LIMIT = FULL_ROLLUP_ROW_CAP
IMPORTED_PRODUCTS_TOP_SUPPLIER_PRODUCT_PAIRS_LIMIT = FULL_ROLLUP_ROW_CAP
IMPORTED_PRODUCTS_TRUNCATION_ROW_COUNT = 1_048_576
IMPORTED_PRODUCTS_READ_ERROR_LIMIT = 20
IMPORTED_PRODUCTS_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1251", "cp1252")
IMPORTED_PRODUCTS_MONTH_TOKEN_TO_MM = {
    "იან": "01",
    "თებ": "02",
    "მარ": "03",
    "აპრ": "04",
    "მაი": "05",
    "ივნ": "06",
    "ივლ": "07",
    "აგვ": "08",
    "სექ": "09",
    "სეპ": "09",
    "ოქტ": "10",
    "ნოე": "11",
    "დეკ": "12",
}

# ---------------------------------------------------------------------------
# Retail sales
# ---------------------------------------------------------------------------

RETAIL_SALES_READ_ERROR_LIMIT = 20
RETAIL_SALES_TOP_LIMIT = FULL_ROLLUP_ROW_CAP
RETAIL_SALES_CATEGORY_LIMIT = FULL_ROLLUP_ROW_CAP
RETAIL_SALES_PRODUCT_LIMIT = FULL_ROLLUP_ROW_CAP
RETAIL_SALES_ROWS_PREVIEW_LIMIT = 50_000
RETAIL_SALES_DUPLICATE_POLICY_MODE = "exclude_suspected_until_explicit_policy"
RETAIL_SALES_DUPLICATE_SUSPECTED_FILES = {
    "გაყიდული პროდუქტები სოფ ოზურგეთი/2026-01-02.xlsx": {
        "suspected_duplicate_of": "გაყიდული პროდუქტები სოფ ოზურგეთი/2025.xlsx",
        "reason_ka": (
            "data-level duplicate-ს ეჭვი მაღალია. ამ run-ზე totals-იდან დროებით გამორიცხულია, "
            "სანამ explicit inclusion/exclusion policy არ დადასტურდება."
        ),
    }
}

# ---------------------------------------------------------------------------
# Phase 2.3 — Mix Analyzer (category mix optimization)
# ---------------------------------------------------------------------------

#: User-approved portfolio gross-margin target. Tool computes gap vs current
#: weighted portfolio GM and proposes drag→lift category shifts to close it.
USER_TARGET_GROSS_MARGIN_PCT = 20.0

#: Category labels whose ``normalized_category`` contains any of these
#: substrings are merged into a single PROTECTED entry — user decision:
#: cigarettes hold current share/margin (good seller, regulated, don't touch).
#: Live data.json has 3 cigarette labels ("0804 | სიგარეტი", "სიგარეტი",
#: "ელ. სიგარეტი"). Tuple (immutable) so it cannot be mutated at runtime.
PROTECTED_CATEGORY_SUBSTRINGS = ("სიგარეტ",)

#: Categories below (portfolio_gm − band) are DRAG; above (portfolio_gm +
#: band) are LIFT. 3pp is wide enough that borderline categories aren't
#: recommended for reallocation — only clear dilutors/accelerators surface.
MIX_ANALYZER_MARGIN_BAND_PP = 3.0

#: Minimum portfolio share for a category to qualify as a drag candidate
#: (1%). Removes long-tail noise — a 0.1%-share category with 2% margin
#: isn't moving the needle even if reallocated fully.
MIX_ANALYZER_MIN_DRAG_SHARE_PCT = 1.0

#: Minimum portfolio share for a category to qualify as a lift candidate
#: (0.5%). Lower than drag threshold because lift candidates must already
#: be present to grow into; we just don't want to suggest tilting into
#: a category that barely exists in today's mix.
MIX_ANALYZER_MIN_LIFT_SHARE_PCT = 0.5

#: Maximum fraction of a source category's revenue a single recommended
#: shift can propose to move (20%). Realism cap — telling a retailer to
#: shift 50% of bread revenue into drinks is not an executable action.
MIX_ANALYZER_MAX_SHIFT_PCT = 20.0

# ---------------------------------------------------------------------------
# Phase 3.8 — Margin Compression Radar (time-series GM decay tracker)
# ---------------------------------------------------------------------------

#: Default rolling window in months. 6 captures a quarter-and-a-half cycle —
#: long enough to smooth single-month seasonality (December/January), short
#: enough to surface live business signal (not ancient history).
MARGIN_RADAR_DEFAULT_WINDOW_MONTHS = 6

#: Hard min on user-supplied window_months. <3 cannot establish a trend
#: (only 2 data points = a line, not a slope).
MARGIN_RADAR_MIN_WINDOW_MONTHS = 3

#: Hard max on user-supplied window_months. >12 reaches into pre-Sprint-5.5
#: data (revenue formula was wrong before commit cf39cd3) — would corrupt
#: the trend signal.
MARGIN_RADAR_MAX_WINDOW_MONTHS = 12

#: Minimum number of data points a category must have inside the window
#: to be evaluated. <3 = spotty data, slope is meaningless.
MARGIN_RADAR_MIN_MONTHS_IN_WINDOW = 3

#: Noise floor on revenue_recent (avg of last 2 months in window). Below
#: this, a 30pp margin swing is statistically meaningless — one bad day
#: can move the number, not a real business trend.
MARGIN_RADAR_MIN_REVENUE_FOR_TRACKING_GE = 1000.0

#: A category is flagged as EXPANDING only when delta_pp > +1pp. Below
#: this it's measurement noise, not a real margin lift.
MARGIN_RADAR_EXPANSION_THRESHOLD_PP = 1.0

# ---------------------------------------------------------------------------
# Object mapping defaults
# ---------------------------------------------------------------------------

OBJECT_OZURGETI = "ოზურგეთი"
OBJECT_DVABZU = "დვაბზუ"
OBJECT_COMMON = "საერთო"
OBJECT_UNALLOCATED = "გაუნაწილებელი"
OBJECT_ORDER_BASE = [OBJECT_OZURGETI, OBJECT_DVABZU, OBJECT_COMMON, OBJECT_UNALLOCATED]

DEFAULT_OBJECT_MAPPING = {
    "notes": "ობიექტის mapping: ტერმინალი/ადგილი → ოზურგეთი / დვაბზუ / გაუნაწილებელი",
    "bog_terminal_to_object": {
        "POS30BOE": OBJECT_OZURGETI,
        "POS302WX": OBJECT_OZURGETI,
        "POS3F1Y7": OBJECT_OZURGETI,
        "POS30H3P": OBJECT_DVABZU,
        "POS30BWH": OBJECT_DVABZU,
        "POS304BB": OBJECT_UNALLOCATED,
        "POS1XA88": OBJECT_UNALLOCATED,
    },
    "tbc_text_to_object": {
        OBJECT_OZURGETI: OBJECT_OZURGETI,
        OBJECT_DVABZU: OBJECT_DVABZU,
    },
    "rs_location_priority_order": [OBJECT_DVABZU, OBJECT_OZURGETI],
    "rs_location_to_object": {
        OBJECT_DVABZU: ["დვაბზუ", "დუაბზო", "დავაბზუ", "დვაბზე"],
        OBJECT_OZURGETI: ["ოზურგეთი", "ოზურგეთო", "ოზუეგეთი"],
    },
    "salary_text_to_object": {
        OBJECT_OZURGETI: OBJECT_OZURGETI,
        OBJECT_DVABZU: OBJECT_DVABZU,
    },
    "default_object": OBJECT_UNALLOCATED,
}

DEFAULT_BUDGET_CONFIG = {
    "notes": (
        "ბიუჯეტის კონფიგურაცია. annual_target — წლიური სამიზნე (ხელით იცვლება). "
        "auto_mode: true = პროგნოზის საფუძველზე ავტომატური გეგმა; false = მხოლოდ annual_target-ს იყენებს."
    ),
    "auto_mode": True,
    "annual_targets": {
        "2025": {"income": None, "expenses": None, "net": None},
        "2026": {"income": None, "expenses": None, "net": None},
    },
    "expense_growth_cap_pct": 10.0,
}

DEFAULT_SECTOR_BENCHMARKS = {
    "sector": "საცალო ვაჭრობა (სასურსათო მაღაზია)",
    "country": "საქართველო",
    "notes": (
        "ბენჩმარკები ტიპიური მცირე/საშუალო სასურსათო ქსელისთვის. "
        "ციფრები მიახლოებითია — ზუსტი სექტორული კვლევა საჭიროებს ადგილობრივ სპეციალისტს."
    ),
    "benchmarks": {
        "gross_margin_pct": {"low": 15, "median": 25, "high": 40, "unit": "%"},
        "net_margin_pct": {"low": 2, "median": 5, "high": 12, "unit": "%"},
        "payment_ratio_pct": {"low": 70, "median": 85, "high": 95, "unit": "%"},
        "ap_days": {"good": 30, "median": 45, "high_risk": 90, "unit": "დღე"},
        "revenue_growth_yoy_pct": {"low": 3, "median": 8, "high": 20, "unit": "%"},
        "inventory_turnover_days": {
            "good": 15,
            "median": 25,
            "high_risk": 45,
            "unit": "დღე",
        },
    },
    "valuation_multiples": {
        "ev_to_revenue": {"low": 0.3, "median": 0.5, "high": 1.0},
        "ev_to_ebitda": {"low": 3, "median": 5, "high": 8},
        "price_to_earnings": {"low": 5, "median": 8, "high": 15},
    },
}

# ---------------------------------------------------------------------------
# Reconciliation constants
# ---------------------------------------------------------------------------

# BOG-ში „მიმღების საიდენტიფიკაციო" ზოგჯერ არ ემთხვევა RS-ის საგადასახადო კოდს.
BOG_RECEIVER_ID_TO_RS_TAX_ID = {}

# Legacy truth-assist only:
# BOG/TBC partner IBAN -> RS tax_id.
PARTNER_IBAN_TO_RS_TAX_ID = {
    "GE60BG0000000667583800": "01025003711",
    "GE78BG0000000269727500": "33001015189",
    "GE81BG0000000890516000": "33001023234",
}

RECON_MATCH_STATUSES = {
    "matched_exact_id",
    "matched_exact_iban",
    "matched_exact_name",
    "matched_alias",
    "matched_scored_high",
}
RECON_FINAL_STATUSES = {
    "matched_exact_id",
    "matched_exact_iban",
    "matched_exact_name",
    "matched_alias",
    "matched_scored_high",
    "ambiguous",
    "unmatched",
    "non_supplier",
    "skipped_explicit",
}
DEFAULT_RECON_SCORE_ACCEPT_THRESHOLD = 86.0
DEFAULT_RECON_SCORE_GAP_THRESHOLD = 18.0
NON_SUPPLIER_FINAL_CONFIDENCE = {"high"}
NON_SUPPLIER_CATEGORY_IDS = {
    "rent_known_landlord_ibans",
    "cashback_foodmart",
    "rent_related",
    "tax_and_budget",
    "loan_and_finance",
    "cash_withdrawal",
    "card_purchase_expense",
    "rs_budget_payments",
    "card_network_settlement",
    "utilities_related",
    "bank_fees",
    "transfer_commission_fee",
    "transit_ucc_communal",
    "utility_telecom_bank_commission",
    "transit_magti_mobile",
    "pos_terminal_service_fee",
    "incoming_packages_fee",
    "incasso_cash_handling",
    "treasury_budget_commission",
    "bank_account_package_fee",
    "bank_fees_software_service",
    "card_retail_own_chain",
    "card_mcc_groceries_5411",
    "card_mcc_misc_retail_5943",
    "card_mcc_building_supplies_5039",
    "salary_payments",
    "tbc_other_expense",
    "bog_other_expense",
    "cleaning_service_tbc_pay",
    "pension_agency",
    "card_mcc_restaurants_5462",
    "card_mcc_shopping_5999",
    "card_mcc_electronics_5065",
    "card_mcc_appliances_5722",
    "business_expense_kikalishvili",
    "rent_expense",
    "service_fee_mega_plus",
    "repair_maintenance",
    "charity_donation",
    "transport_evacuator",
    "salary_payments_additional",
    "rent_expense_additional",
    "salary_payments_additional2",
    "inventory_shelves",
    "street_food_125",
}

BANK_UNMATCHED_CATEGORY_ORDER = {
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


# ---------------------------------------------------------------------------
# Shared tiny utility functions
# ---------------------------------------------------------------------------

def _clone_default_object_mapping():
    return json.loads(json.dumps(DEFAULT_OBJECT_MAPPING, ensure_ascii=False))


def _clone_default_budget_config():
    return json.loads(json.dumps(DEFAULT_BUDGET_CONFIG, ensure_ascii=False))


def _clone_default_sector_benchmarks():
    return json.loads(json.dumps(DEFAULT_SECTOR_BENCHMARKS, ensure_ascii=False))


def _safe_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value)


def _normalize_for_match(value):
    s = _safe_text(value).strip().lower()
    return re.sub(r"\s+", " ", s)


def _ordered_unique(values):
    seen = set()
    out = []
    for v in values:
        if not v:
            continue
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _object_order_for_pos(mapping):
    values = []
    values.extend((mapping.get("tbc_text_to_object") or {}).values())
    values.extend((mapping.get("bog_terminal_to_object") or {}).values())
    values.append(mapping.get("default_object") or OBJECT_UNALLOCATED)
    return _ordered_unique(values)


def _object_order_for_monthly_pnl(mapping):
    return _ordered_unique(
        OBJECT_ORDER_BASE
        + list((mapping.get("tbc_text_to_object") or {}).values())
        + list((mapping.get("bog_terminal_to_object") or {}).values())
        + [mapping.get("default_object") or OBJECT_UNALLOCATED]
    )


def _month_sort_key(month_key):
    if month_key == "უცნობი თვე":
        return (1, month_key)
    dt = pd.to_datetime(month_key, errors="coerce", format="%Y-%m")
    if pd.isna(dt):
        return (1, month_key)
    return (0, dt.strftime("%Y-%m"))


def _match_text_to_object(blob_lower, text_map):
    for token, obj in (text_map or {}).items():
        tok = _normalize_for_match(token)
        if tok and tok in blob_lower:
            return str(obj)
    return None


def detect_object(source, text="", object_mapping=None, rs_location=None):
    mapping = object_mapping or _clone_default_object_mapping()
    src = _normalize_for_match(source)
    text_blob = _normalize_for_match(text)
    default_object = str(mapping.get("default_object") or OBJECT_UNALLOCATED)
    if src == "bog_pos":
        m = re.search(r"\b(POS\w+)\b", _safe_text(text).upper())
        if m:
            terminal_id = m.group(1).upper()
            return str(
                (mapping.get("bog_terminal_to_object") or {}).get(
                    terminal_id, default_object
                )
            )
        return default_object
    if src == "tbc_pos":
        found = _match_text_to_object(text_blob, mapping.get("tbc_text_to_object") or {})
        return found or default_object
    if src == "rs_waybill":
        location_blob = _normalize_for_match(rs_location if rs_location is not None else text)
        rs_map = mapping.get("rs_location_to_object") or {}
        # Priority order: explicit list wins, fallback to mapping insertion
        # order. Aligns with imported_products._resolve_destination_object —
        # when source text contains both store names ("ოზურგეთი, სოფ. დვაბზუ"),
        # the first-listed target wins instead of falling through to the
        # less-specific keyword.
        priority = mapping.get("rs_location_priority_order") or list(rs_map.keys())
        for obj in priority:
            variants = rs_map.get(obj) or []
            for variant in variants:
                v = _normalize_for_match(variant)
                if v and v in location_blob:
                    return str(obj)
        return default_object
    if src in ("tbc_expense", "tbc_salary"):
        found = _match_text_to_object(
            text_blob, mapping.get("salary_text_to_object") or {}
        )
        if not found:
            found = _match_text_to_object(text_blob, mapping.get("tbc_text_to_object") or {})
        return found or OBJECT_COMMON
    return default_object


def _extract_tax_id_from_org(org_name):
    m = re.search(r"\((\d+)", _safe_text(org_name))
    return m.group(1) if m else ""


def _pick_aging_bucket(days_since_last):
    if days_since_last is None:
        return "180+"
    if days_since_last <= 30:
        return "0-30"
    if days_since_last <= 60:
        return "31-60"
    if days_since_last <= 90:
        return "61-90"
    if days_since_last <= 180:
        return "91-180"
    return "180+"


def _empty_aging_summary():
    return {b: {"count": 0, "total_debt": 0.0} for b in AGING_BUCKET_ORDER}


def _to_waybills_df(waybills_data_or_df):
    if isinstance(waybills_data_or_df, pd.DataFrame):
        return waybills_data_or_df.copy()
    if isinstance(waybills_data_or_df, list):
        return pd.DataFrame(waybills_data_or_df)
    return pd.DataFrame()


def _parse_rs_datetime(value):
    if value is None:
        return pd.NaT
    if isinstance(value, float) and pd.isna(value):
        return pd.NaT
    s = str(value).strip()
    if not s:
        return pd.NaT
    dt = pd.to_datetime(s, errors="coerce", format="%Y-%m-%d %H:%M:%S")
    if pd.isna(dt):
        m = re.match(r"^\s*(\d{1,2})-([^-]+)-(\d{4})(.*)$", s)
        if m:
            day, month_token, year, rest = m.groups()
            normalized_month = re.sub(r"[^ა-ჰa-zA-Z]", "", month_token.lower())
            for token, mm in IMPORTED_PRODUCTS_MONTH_TOKEN_TO_MM.items():
                if normalized_month.startswith(token):
                    normalized_text = f"{year}-{mm}-{int(day):02d}{rest}"
                    dt = pd.to_datetime(
                        normalized_text,
                        errors="coerce",
                        format="%Y-%m-%d %H:%M:%S",
                    )
                    if pd.isna(dt):
                        dt = pd.to_datetime(normalized_text, errors="coerce")
                    break
    if pd.isna(dt):
        dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        dt = pd.to_datetime(s, errors="coerce")
    return dt


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


# ---------------------------------------------------------------------------
# Object detection & multi-object helpers
# ---------------------------------------------------------------------------

def _object_order_for_pos(mapping):
    values = []
    values.extend((mapping.get("tbc_text_to_object") or {}).values())
    values.extend((mapping.get("bog_terminal_to_object") or {}).values())
    values.append(mapping.get("default_object") or OBJECT_UNALLOCATED)
    return _ordered_unique(values)


def _object_order_for_monthly_pnl(mapping):
    return _ordered_unique(
        OBJECT_ORDER_BASE
        + list((mapping.get("tbc_text_to_object") or {}).values())
        + list((mapping.get("bog_terminal_to_object") or {}).values())
        + [mapping.get("default_object") or OBJECT_UNALLOCATED]
    )


def _month_sort_key(month_key):
    if month_key == "უცნობი თვე":
        return (1, month_key)
    dt = pd.to_datetime(month_key, errors="coerce", format="%Y-%m")
    if pd.isna(dt):
        return (1, month_key)
    return (0, dt.strftime("%Y-%m"))


def _match_text_to_object(blob_lower, text_map):
    for token, obj in (text_map or {}).items():
        tok = _normalize_for_match(token)
        if tok and tok in blob_lower:
            return str(obj)
    return None


def detect_object(source, text="", object_mapping=None, rs_location=None):
    mapping = object_mapping or _clone_default_object_mapping()
    src = _normalize_for_match(source)
    text_blob = _normalize_for_match(text)
    default_object = str(mapping.get("default_object") or OBJECT_UNALLOCATED)
    if src == "bog_pos":
        m = re.search(r"\b(POS\w+)\b", _safe_text(text).upper())
        if m:
            terminal_id = m.group(1).upper()
            return str(
                (mapping.get("bog_terminal_to_object") or {}).get(
                    terminal_id, default_object
                )
            )
        return default_object
    if src == "tbc_pos":
        found = _match_text_to_object(text_blob, mapping.get("tbc_text_to_object") or {})
        return found or default_object
    if src == "rs_waybill":
        location_blob = _normalize_for_match(rs_location if rs_location is not None else text)
        rs_map = mapping.get("rs_location_to_object") or {}
        # Priority order: explicit list wins, fallback to mapping insertion
        # order. Aligns with imported_products._resolve_destination_object —
        # when source text contains both store names ("ოზურგეთი, სოფ. დვაბზუ"),
        # the first-listed target wins instead of falling through to the
        # less-specific keyword.
        priority = mapping.get("rs_location_priority_order") or list(rs_map.keys())
        for obj in priority:
            variants = rs_map.get(obj) or []
            for variant in variants:
                v = _normalize_for_match(variant)
                if v and v in location_blob:
                    return str(obj)
        return default_object
    if src in ("tbc_expense", "tbc_salary"):
        found = _match_text_to_object(
            text_blob, mapping.get("salary_text_to_object") or {}
        )
        if not found:
            found = _match_text_to_object(text_blob, mapping.get("tbc_text_to_object") or {})
        return found or OBJECT_COMMON
    return default_object


def _extract_tax_id_from_org(org_name):
    m = re.search(r"\((\d+)", _safe_text(org_name))
    return m.group(1) if m else ""


def _pick_aging_bucket(days_since_last):
    if days_since_last is None:
        return "180+"
    if days_since_last <= 30:
        return "0-30"
    if days_since_last <= 60:
        return "31-60"
    if days_since_last <= 90:
        return "61-90"
    if days_since_last <= 180:
        return "91-180"
    return "180+"


def _empty_aging_summary():
    return {b: {"count": 0, "total_debt": 0.0} for b in AGING_BUCKET_ORDER}


def _to_waybills_df(waybills_data_or_df):
    if isinstance(waybills_data_or_df, pd.DataFrame):
        return waybills_data_or_df.copy()
    if isinstance(waybills_data_or_df, list):
        return pd.DataFrame(waybills_data_or_df)
    return pd.DataFrame()


def _parse_rs_datetime(value):
    if value is None:
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return value
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return pd.NaT
    dt = pd.NaT
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S",
                "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            dt = pd.to_datetime(s, format=fmt)
            if not pd.isna(dt):
                break
        except Exception:
            if "/" in s or "." in s or "-" in s:
                normalized_text = s.replace("/", "-").replace(".", "-")
                try:
                    dt = pd.to_datetime(
                        normalized_text, errors="coerce", format="%Y-%m-%d %H:%M:%S",
                    )
                    if pd.isna(dt):
                        dt = pd.to_datetime(normalized_text, errors="coerce")
                    break
                except Exception:
                    pass
    if pd.isna(dt):
        dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        dt = pd.to_datetime(s, errors="coerce")
    return dt
