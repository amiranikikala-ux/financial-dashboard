import json
import os
import re
import sys
from collections import defaultdict
from collections import Counter

import glob
import pandas as pd

from backend_paths import (
    get_dashboard_data_path,
    get_dashboard_public_dir,
    get_dashboard_tab_data_dir,
)
from dashboard_pipeline.api_contracts import build_static_api_artifacts
from dashboard_pipeline.config_validation import (
    validate_api_artifacts,
    validate_config_bundle,
)
from dashboard_pipeline.export_artifacts import (
    publish_download_excels as _publish_download_excels_external,
    write_api_artifacts,
)
from dashboard_pipeline.sources import (
    build_source_manifest,
    financial_analysis_path as _pipeline_financial_analysis_path,
    list_bog_bank_statement_xlsx as _pipeline_list_bog_bank_statement_xlsx,
    list_imported_product_files as _pipeline_list_imported_product_files,
    list_retail_sales_dvabzu_files as _pipeline_list_retail_sales_dvabzu_files,
    list_retail_sales_files as _pipeline_list_retail_sales_files,
    list_retail_sales_ozurgeti_files as _pipeline_list_retail_sales_ozurgeti_files,
    list_rs_waybill_files as _pipeline_list_rs_waybill_files,
    list_tbc_bank_statement_xlsx as _pipeline_list_tbc_bank_statement_xlsx,
    summarize_source_manifest,
)
from dashboard_pipeline.truth_boundary import (
    build_truth_boundary_summary,
    build_payment_scope_summary,
    build_reconciliation_provenance,
    describe_supplier_payment_scope,
)

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
BOG_EXPENSES_LEDGER_NOTE_KA = (
    "BOG კატეგორიები: იგივე წესები რაც tbc_expense_categories.json-ში; "
    "თუ კატეგორია ვერ განისაზღვრა — 'BOG — სხვა ხარჯი'. "
    "P&L-ისთვის BOG დებეტის ყველა ხაზი ითვლება ხარჯად."
)

ACCOUNTING_ROLE_OPERATING = "operating_expense"
ACCOUNTING_ROLE_STATE_TREASURY = "state_treasury"
BOG_OTHER_EXPENSE_ID = "bog_other_expense"
BOG_OTHER_EXPENSE_LABEL_KA = "BOG — სხვა ხარჯი"
TBC_OTHER_EXPENSE_ID = "tbc_other_expense"
TBC_OTHER_EXPENSE_LABEL_KA = "TBC — სხვა ხარჯი"
AGING_BUCKET_ORDER = ["0-30", "31-60", "61-90", "91-180", "180+"]
IMPORTED_PRODUCTS_SHEET_NAME = "Grid"
# დიდი მოცულობის rollup-ები: ერთი ჭერი (გენერაციის შემდეგ data.json იზრდება).
FULL_ROLLUP_ROW_CAP = 10_000_000

IMPORTED_PRODUCTS_ROWS_PREVIEW_LIMIT = 50_000
IMPORTED_PRODUCTS_TOP_LIMIT = FULL_ROLLUP_ROW_CAP
IMPORTED_PRODUCTS_SUPPLIER_TOP_PRODUCTS_LIMIT = FULL_ROLLUP_ROW_CAP
IMPORTED_PRODUCTS_PRODUCT_TOP_SUPPLIERS_LIMIT = FULL_ROLLUP_ROW_CAP
IMPORTED_PRODUCTS_PRODUCTS_LIMIT = FULL_ROLLUP_ROW_CAP
IMPORTED_PRODUCTS_TOP_SUPPLIER_PRODUCT_PAIRS_LIMIT = FULL_ROLLUP_ROW_CAP
# ზუსტად ამ რიგების რაოდენობა = Excel-ის ცნობილი ზედა ზღვარი → შესაძლო truncate.
IMPORTED_PRODUCTS_TRUNCATION_ROW_COUNT = 1_048_576
IMPORTED_PRODUCTS_READ_ERROR_LIMIT = 20
IMPORTED_PRODUCTS_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1251", "cp1252")
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


def _financial_analysis_path(*parts):
    """Financial_Analysis/ — აბსოლუტური გზა (არ არის დამოკიდებული cwd / os.chdir-ზე)."""
    return _pipeline_financial_analysis_path(__file__, *parts)


def _sorted_glob_in_financial(subdir, pattern):
    return sorted(glob.glob(os.path.join(_financial_analysis_path(subdir), pattern)))


def list_bog_bank_statement_xlsx():
    """BOG: ყველა `.xlsx` `Financial_Analysis/ბოგ ბანკი ამონაწერი/`-ში (სახელით დალაგებული)."""
    return _pipeline_list_bog_bank_statement_xlsx(__file__)


def list_tbc_bank_statement_xlsx():
    """TBC: ყველა `.xlsx` `Financial_Analysis/თბს ბანკი ამონაწერი/`-ში (სახელით დალაგებული)."""
    return _pipeline_list_tbc_bank_statement_xlsx(__file__)


def list_rs_waybill_files():
    """
    RS ზედნადები: ყველა `.xlsx` და `.xls` `Financial_Analysis/რს ზედნადები/`-ში (ორივე ავტომატურად).
    """
    return _pipeline_list_rs_waybill_files(__file__)


def list_imported_product_files():
    """
    შემოტანილი პროდუქცია:
    - ჯერ ყველა `.csv` (preferred, სრული export)
    - თუ არ არის, legacy fallback: `.xls` / `.xlsx`
    """
    return _pipeline_list_imported_product_files(__file__)


def list_retail_sales_dvabzu_files():
    """Retail sales source: დვაბზუ ობიექტის ყველა `.xlsx`."""
    return _pipeline_list_retail_sales_dvabzu_files(__file__)


def list_retail_sales_ozurgeti_files():
    """Retail sales source: ოზურგეთი ობიექტის ყველა `.xlsx`."""
    return _pipeline_list_retail_sales_ozurgeti_files(__file__)


def list_retail_sales_files():
    """Retail sales source: დვაბზუ + ოზურგეთი `.xlsx` ფაილები, დუბლიკატების გარეშე."""
    return _pipeline_list_retail_sales_files(__file__)


def _to_financial_relative_path(path):
    if not path:
        return ""
    abs_path = os.path.abspath(path)
    base = _financial_analysis_path()
    try:
        rel = os.path.relpath(abs_path, base)
    except Exception:
        rel = abs_path
    rel = str(rel).replace("\\", "/").strip("./")
    if rel.startswith("Financial_Analysis/"):
        return rel
    return f"Financial_Analysis/{rel}" if rel else "Financial_Analysis"


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
    "rs_location_to_object": {
        OBJECT_OZURGETI: [
            "ოზურგეთი",
            "ოზურგეთო",
            "ოზუეგეთი",
            "სოფ. ოზურგეთი",
            "სოფ.ოზურგეთი",
            "სოფ ოზურგეთი",
            "ქ. ოზურგეთი",
        ],
        OBJECT_DVABZU: [
            "დვაბზუ",
            "დუაბზო",
            "დავაბზუ",
            "გაღმა დვაბზუ",
            "სოფ.დვაბზუ",
            "სოფ დვაბზუ",
            "სოფელი დვაბზუ",
        ],
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


def load_object_mapping(script_dir):
    path = os.path.join(script_dir, "Financial_Analysis", "object_mapping.json")
    mapping = _clone_default_object_mapping()
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                user_cfg = json.load(f)
            if isinstance(user_cfg, dict):
                for key in (
                    "notes",
                    "bog_terminal_to_object",
                    "tbc_text_to_object",
                    "rs_location_to_object",
                    "salary_text_to_object",
                    "default_object",
                ):
                    if key in user_cfg:
                        mapping[key] = user_cfg[key]
        except Exception as e:
            print(f"Warn object mapping read {path}: {e}")
    mapping["default_object"] = str(mapping.get("default_object") or OBJECT_UNALLOCATED)
    mapping["bog_terminal_to_object"] = {
        str(k).upper(): str(v)
        for k, v in (mapping.get("bog_terminal_to_object") or {}).items()
        if _safe_text(k).strip()
    }
    mapping["tbc_text_to_object"] = {
        str(k): str(v)
        for k, v in (mapping.get("tbc_text_to_object") or {}).items()
        if _safe_text(k).strip()
    }
    rs_loc = {}
    for obj, variants in (mapping.get("rs_location_to_object") or {}).items():
        if variants is None:
            continue
        if not isinstance(variants, list):
            variants = [variants]
        clean_variants = [str(v) for v in variants if _safe_text(v).strip()]
        if clean_variants:
            rs_loc[str(obj)] = clean_variants
    mapping["rs_location_to_object"] = rs_loc
    mapping["salary_text_to_object"] = {
        str(k): str(v)
        for k, v in (mapping.get("salary_text_to_object") or {}).items()
        if _safe_text(k).strip()
    }
    return mapping


def load_budget_config():
    path = _financial_analysis_path("budget_config.json")
    cfg = _clone_default_budget_config()
    if not os.path.isfile(path):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warn budget config create {path}: {e}")
        return cfg

    try:
        with open(path, encoding="utf-8") as f:
            user_cfg = json.load(f)
        if isinstance(user_cfg, dict):
            for key in ("notes", "auto_mode", "annual_targets", "expense_growth_cap_pct"):
                if key in user_cfg:
                    cfg[key] = user_cfg[key]
    except Exception as e:
        print(f"Warn budget config read {path}: {e}")
        return cfg

    if not isinstance(cfg.get("annual_targets"), dict):
        cfg["annual_targets"] = {}
    normalized_targets = {}
    for year_key, year_cfg in (cfg.get("annual_targets") or {}).items():
        yk = str(year_key)
        if not isinstance(year_cfg, dict):
            year_cfg = {}
        normalized_targets[yk] = {
            "income": year_cfg.get("income"),
            "expenses": year_cfg.get("expenses"),
            "net": year_cfg.get("net"),
        }
    cfg["annual_targets"] = normalized_targets
    return cfg


def load_sector_benchmarks():
    path = _financial_analysis_path("sector_benchmarks.json")
    cfg = _clone_default_sector_benchmarks()
    if not os.path.isfile(path):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warn sector benchmarks create {path}: {e}")
        return cfg

    try:
        with open(path, encoding="utf-8") as f:
            user_cfg = json.load(f)
        if isinstance(user_cfg, dict):
            for key in ("sector", "country", "notes", "benchmarks", "valuation_multiples"):
                if key in user_cfg:
                    cfg[key] = user_cfg[key]
    except Exception as e:
        print(f"Warn sector benchmarks read {path}: {e}")
        return cfg

    if not isinstance(cfg.get("benchmarks"), dict):
        cfg["benchmarks"] = (
            _clone_default_sector_benchmarks().get("benchmarks") or {}
        )
    if not isinstance(cfg.get("valuation_multiples"), dict):
        cfg["valuation_multiples"] = (
            _clone_default_sector_benchmarks().get("valuation_multiples") or {}
        )
    return cfg


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
        for obj, variants in rs_map.items():
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


def _read_imported_products_csv(path):
    """შემოტანილი პროდუქციის CSV export: utf-8/Excel სხვადასხვა encoding-ის fallback."""
    last_error = None
    for enc in IMPORTED_PRODUCTS_CSV_ENCODINGS:
        for sep in (",", ";", None):
            try:
                if sep is None:
                    df = pd.read_csv(
                        path,
                        encoding=enc,
                        sep=None,
                        engine="python",
                        low_memory=False,
                    )
                else:
                    df = pd.read_csv(
                        path,
                        encoding=enc,
                        sep=sep,
                        low_memory=False,
                    )
                if df.shape[1] < 5:
                    continue
                df = df.copy()
                df.columns = [str(c).strip() for c in df.columns]
                unnamed_cols = [
                    c for c in df.columns if str(c).strip().startswith("Unnamed:")
                ]
                if unnamed_cols:
                    df = df.drop(columns=unnamed_cols, errors="ignore")
                return df
            except Exception as exc:
                last_error = exc
                continue
    if last_error is not None:
        raise last_error
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _read_imported_products_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return _read_imported_products_csv(path), "csv", None
    return pd.read_excel(path, sheet_name=IMPORTED_PRODUCTS_SHEET_NAME), "excel", IMPORTED_PRODUCTS_SHEET_NAME


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
                "strict ბანკით გადახდა": float(
                    r.get("strict_bank_paid") or r.get("bank_paid") or 0
                ),
                "ნაღდით გადახდა": float(r.get("manual_paid") or 0),
                "სულ გადახდილი": float(r.get("total_paid") or 0),
                "დავალიანება": float(r.get("total_debt") or 0),
                "გადახდის scope": r.get("payment_scope"),
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
            # ობიექტის სახელები მარტო არ არის ხელფასის მტკიცებულება:
            # supplier debt payment-ებშიც ხშირად ჩანს ოზურგეთი/დვაბზუ.
            for extra in ("salary", "payroll"):
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


def collect_bog_pos_terminal_income(script_dir, object_mapping=None):
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

    object_mapping = object_mapping or load_object_mapping(script_dir)
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
                        "object": detect_object(
                            "bog_pos", text=raw, object_mapping=object_mapping
                        ),
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


def merge_pos_terminal_income(tbc_bundle, bog_bundle, object_mapping=None):
    object_mapping = object_mapping or _clone_default_object_mapping()
    pos_objects = _object_order_for_pos(object_mapping)
    default_object = str(object_mapping.get("default_object") or OBJECT_UNALLOCATED)
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
    object_daily = defaultdict(lambda: defaultdict(float))
    for line in all_lines:
        d = _day_key(line.get("თარიღი"))
        obj = str(line.get("object") or default_object)
        object_daily[d][obj] += float(line.get("თანხა") or 0)
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
                "by_object": {
                    obj: float(object_daily[d].get(obj) or 0) for obj in pos_objects
                },
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


def collect_tbc_card_income(script_dir, object_mapping=None):
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

    object_mapping = object_mapping or load_object_mapping(script_dir)
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
                        "object": detect_object(
                            "tbc_pos", text=raw, object_mapping=object_mapping
                        ),
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


def _is_non_operating_tbc_residual(blob_lower):
    """
    Residual TBC debit ხაზიდან ვაშორებთ მხოლოდ აშკარა არაოპერაციულ შემთხვევებს,
    რომ დანარჩენი დაუმატჩავი ხარჯი არ დაიკარგოს.
    """
    text = (blob_lower or "").strip()
    if not text:
        return False
    treasury_markers = (
        "revenue service",
        "rs.ge",
        "tresge",
        "სახაზინო",
        "ხაზინის",
        "საბიუჯეტო",
        "გადასახადების ერთიანი კოდი",
    )
    internal_transfer_markers = (
        "internal transfer",
        "between own accounts",
        "own account transfer",
        "საკუთარ ანგარიშ",
        "შიდა გადარიცხ",
    )
    all_markers = treasury_markers + internal_transfer_markers
    return any(marker in text for marker in all_markers)


def collect_tbc_expense_categories(script_dir, object_mapping=None):
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

    other_cat = {
        "id": TBC_OTHER_EXPENSE_ID,
        "label_ka": TBC_OTHER_EXPENSE_LABEL_KA,
        "accounting_role": ACCOUNTING_ROLE_OPERATING,
        "patterns": [],
        "match_all": [],
        "ibans": [],
    }
    cats_with_other = list(cats_norm) + [other_cat]

    object_mapping = object_mapping or load_object_mapping(script_dir)
    buckets = {c["id"]: [] for c in cats_with_other}
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
                    if _is_non_operating_tbc_residual(blob_lower):
                        continue
                    mid = TBC_OTHER_EXPENSE_ID
                obj_source = "tbc_salary" if mid == "salary_payments" else "tbc_expense"
                buckets[mid].append(
                    {
                        "კატეგორია_id": mid,
                        "ფაილი": os.path.basename(f),
                        "თარიღი": _excel_cell(row, date_col),
                        "თანხა": float(amt),
                        "object": detect_object(
                            obj_source, text=raw, object_mapping=object_mapping
                        ),
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
    label_by_id = {c["id"]: c["label_ka"] for c in cats_with_other}
    for c in cats_with_other:
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


def collect_bog_expense_categories(script_dir, object_mapping=None):
    """
    BOG „დებეტი“ — ხარჯის კატეგორიები (Financial_Analysis/tbc_expense_categories.json წესებით).
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

    other_cat = {
        "id": BOG_OTHER_EXPENSE_ID,
        "label_ka": BOG_OTHER_EXPENSE_LABEL_KA,
        "accounting_role": ACCOUNTING_ROLE_OPERATING,
        "patterns": [],
        "match_all": [],
        "ibans": [],
    }
    cats_with_other = list(cats_norm) + [other_cat]

    object_mapping = object_mapping or load_object_mapping(script_dir)
    buckets = {c["id"]: [] for c in cats_with_other}
    for f in list_bog_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            debit_col = next(
                (c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)),
                None,
            )
            if not debit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            operation_col = next(
                (c for c in cols if "ოპერაციის შინაარსი" in str(c)),
                None,
            )
            purpose_col = _find_excel_column_danishnuleba(cols)
            receiver_col = next(
                (c for c in cols if "მიმღების დასახელება" in str(c)),
                None,
            )
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors="coerce")
                if pd.isna(amt) or amt <= 0:
                    continue
                text_parts = []
                for col in (operation_col, purpose_col, receiver_col):
                    val = _excel_cell(row, col)
                    if val:
                        text_parts.append(val)
                raw = " | ".join(text_parts).strip()
                if not raw:
                    raw = _tbc_row_text_join_skip(row, cols, [debit_col])
                blob_lower = raw.lower()
                mid = _match_tbc_expense_category(blob_lower, cats_norm)
                if not mid:
                    mid = BOG_OTHER_EXPENSE_ID
                obj_source = "tbc_salary" if mid == "salary_payments" else "tbc_expense"
                buckets[mid].append(
                    {
                        "კატეგორია_id": mid,
                        "ფაილი": os.path.basename(f),
                        "თარიღი": _excel_cell(row, date_col),
                        "თანხა": float(amt),
                        "object": detect_object(
                            obj_source, text=raw, object_mapping=object_mapping
                        ),
                        "ტექსტი_მოკლე": (raw[:500] + "...")
                        if len(raw) > 500
                        else raw,
                    }
                )
        except Exception as e:
            print(f"Error BOG expenses {f}: {e}")

    out_cats = []
    grand = 0.0
    grand_operating = 0.0
    grand_treasury = 0.0
    label_by_id = {c["id"]: c["label_ka"] for c in cats_with_other}
    for c in cats_with_other:
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


def build_monthly_pnl(
    pos_bundle,
    tbc_expenses_bundle,
    object_mapping,
    bog_expenses_bundle=None,
):
    """
    თვიური P&L: POS შემოსავალი და TBC/BOG ხარჯები ობიექტების ჭრილში.
    """
    mapping = object_mapping or _clone_default_object_mapping()
    default_object = str(mapping.get("default_object") or OBJECT_UNALLOCATED)
    pos_lines = list(
        (pos_bundle or {}).get("pnl_lines")
        or (pos_bundle or {}).get("lines")
        or (pos_bundle or {}).get("rows_preview")
        or []
    )
    month_income = defaultdict(lambda: defaultdict(float))
    for line in pos_lines:
        month = _month_key(line.get("თარიღი"))
        obj = str(line.get("object") or default_object)
        month_income[month][obj] += float(line.get("თანხა") or 0)

    month_expenses = defaultdict(lambda: defaultdict(float))
    for bundle in [tbc_expenses_bundle, bog_expenses_bundle]:
        if not bundle:
            continue
        for cat in bundle.get("categories") or []:
            for line in cat.get("lines") or []:
                month = _month_key(line.get("თარიღი"))
                obj = str(line.get("object") or OBJECT_COMMON)
                month_expenses[month][obj] += float(line.get("თანხა") or 0)

    months = sorted(
        set(month_income.keys()) | set(month_expenses.keys()),
        key=_month_sort_key,
    )
    objects_order = _object_order_for_monthly_pnl(mapping)
    seen_objects = set(objects_order)
    dynamic_objects = set()
    for month in months:
        dynamic_objects.update(month_income[month].keys())
        dynamic_objects.update(month_expenses[month].keys())
    for obj in sorted(dynamic_objects):
        if obj not in seen_objects:
            objects_order.append(obj)
            seen_objects.add(obj)

    out = []
    for month in months:
        month_objects = {}
        total_income = 0.0
        total_expenses = 0.0
        for obj in objects_order:
            pos_income = float(month_income[month].get(obj) or 0)
            expenses = float(month_expenses[month].get(obj) or 0)
            total_income += pos_income
            total_expenses += expenses
            month_objects[obj] = {
                "pos_income": pos_income,
                "expenses": expenses,
                "net": float(pos_income - expenses),
            }
        out.append(
            {
                "month": month,
                "objects": month_objects,
                "total": {
                    "pos_income": float(total_income),
                    "expenses": float(total_expenses),
                    "net": float(total_income - total_expenses),
                },
            }
        )
    return out


def build_supplier_aging(suppliers_data, waybills_data_or_df):
    waybills_df = _to_waybills_df(waybills_data_or_df)
    summary = _empty_aging_summary()
    if not suppliers_data:
        return {"suppliers": [], "summary": summary}

    def _row_truth_sources(row):
        raw = row.get("supplier_truth_sources")
        if isinstance(raw, (list, tuple, set)):
            return [str(x) for x in raw if str(x).strip()]
        text = str(raw or "").strip()
        return [text] if text else []

    if waybills_df.empty:
        out = []
        for s in suppliers_data:
            debt = float(s.get("total_debt") or 0)
            if debt <= 0:
                continue
            bucket = "180+"
            summary[bucket]["count"] += 1
            summary[bucket]["total_debt"] += debt
            out.append(
                {
                    "tax_id": _extract_tax_id_from_org(s.get("ორგანიზაცია")),
                    "org": str(s.get("ორგანიზაცია") or ""),
                    "total_effective": float(s.get("total_effective") or 0),
                    "total_paid": float(s.get("total_paid") or 0),
                    "strict_bank_paid": float(s.get("strict_bank_paid") or s.get("bank_paid") or 0),
                    "manual_paid": float(s.get("manual_paid") or 0),
                    "total_debt": debt,
                    "last_waybill_date": "",
                    "days_since_last": None,
                    "aging_bucket": bucket,
                    "first_waybill_date": "",
                    "waybill_count": int(s.get("waybills_count") or 0),
                    "object": OBJECT_UNALLOCATED,
                    "payment_scope": str(s.get("payment_scope") or ""),
                    "payment_scope_note": str(s.get("payment_scope_note") or ""),
                    "supplier_truth_summary": str(
                        s.get("supplier_truth_summary") or ""
                    ),
                    "supplier_truth_sources": _row_truth_sources(s),
                    "official_name_truth_source": str(
                        s.get("official_name_truth_source") or ""
                    ),
                }
            )
        out.sort(key=lambda x: float(x.get("total_debt") or 0), reverse=True)
        return {"suppliers": out, "summary": summary}

    org_col = None
    for c in ("ორგანიზაცია", "supplier"):
        if c in waybills_df.columns:
            org_col = c
            break
    date_col = next(
        (c for c in waybills_df.columns if "გააქტიურების თარ" in str(c)),
        None,
    )
    if not date_col and "date" in waybills_df.columns:
        date_col = "date"
    status_col = "სტატუსი" if "სტატუსი" in waybills_df.columns else "status" if "status" in waybills_df.columns else None
    cancel_col = (
        "გაუქმებული (ფლეგი)" if "გაუქმებული (ფლეგი)" in waybills_df.columns else None
    )
    object_col = "object" if "object" in waybills_df.columns else None
    location_col = next(
        (c for c in waybills_df.columns if "მიწოდების ადგილი" in str(c)),
        None,
    )
    if not location_col:
        location_col = next(
            (
                c
                for c in waybills_df.columns
                if "მიწოდების" in str(c) and "ადგილი" in str(c)
            ),
            None,
        )

    df = waybills_df.copy()
    if org_col:
        df["_tax_id"] = df[org_col].apply(_extract_tax_id_from_org)
    else:
        df["_tax_id"] = ""
    if date_col:
        df["_date_dt"] = df[date_col].apply(_parse_rs_datetime)
    else:
        df["_date_dt"] = pd.NaT

    if cancel_col:
        active_mask = ~df[cancel_col].fillna(False).astype(bool)
    elif status_col:
        active_mask = ~df[status_col].astype(str).str.contains(
            "გაუქმებული", case=False, na=False
        )
    else:
        active_mask = pd.Series([True] * len(df), index=df.index)
    active_df = df[active_mask].copy()

    now_ts = pd.Timestamp.now().normalize()
    suppliers_out = []
    for s in suppliers_data:
        debt = float(s.get("total_debt") or 0)
        if debt <= 0:
            continue

        org_name = str(s.get("ორგანიზაცია") or "")
        tax_id = _extract_tax_id_from_org(org_name)
        if tax_id:
            s_rows = active_df[active_df["_tax_id"] == tax_id].copy()
        elif org_col:
            s_rows = active_df[active_df[org_col].astype(str) == org_name].copy()
        else:
            s_rows = active_df.iloc[0:0].copy()

        valid_dates = s_rows["_date_dt"].dropna() if "_date_dt" in s_rows.columns else pd.Series(dtype="datetime64[ns]")
        first_dt = valid_dates.min() if not valid_dates.empty else pd.NaT
        last_dt = valid_dates.max() if not valid_dates.empty else pd.NaT
        if pd.isna(last_dt):
            days_since_last = None
            last_waybill_date = ""
        else:
            days_since_last = int((now_ts - pd.Timestamp(last_dt).normalize()).days)
            last_waybill_date = pd.Timestamp(last_dt).strftime("%Y-%m-%d")
        first_waybill_date = (
            pd.Timestamp(first_dt).strftime("%Y-%m-%d") if not pd.isna(first_dt) else ""
        )

        if object_col and object_col in s_rows.columns:
            object_values = [
                str(x).strip()
                for x in s_rows[object_col].tolist()
                if str(x).strip() and str(x).strip().lower() != "nan"
            ]
        elif location_col and location_col in s_rows.columns:
            object_values = [
                detect_object("rs_waybill", rs_location=x)
                for x in s_rows[location_col].tolist()
            ]
        else:
            object_values = []
        supplier_object = (
            Counter(object_values).most_common(1)[0][0]
            if object_values
            else OBJECT_UNALLOCATED
        )

        bucket = _pick_aging_bucket(days_since_last)
        summary[bucket]["count"] += 1
        summary[bucket]["total_debt"] += debt
        suppliers_out.append(
            {
                "tax_id": tax_id,
                "org": org_name,
                "total_effective": float(s.get("total_effective") or 0),
                "total_paid": float(s.get("total_paid") or 0),
                "strict_bank_paid": float(s.get("strict_bank_paid") or s.get("bank_paid") or 0),
                "manual_paid": float(s.get("manual_paid") or 0),
                "total_debt": debt,
                "last_waybill_date": last_waybill_date,
                "days_since_last": days_since_last,
                "aging_bucket": bucket,
                "first_waybill_date": first_waybill_date,
                "waybill_count": int(len(s_rows.index)),
                "object": supplier_object,
                "payment_scope": str(s.get("payment_scope") or ""),
                "payment_scope_note": str(s.get("payment_scope_note") or ""),
                "supplier_truth_summary": str(s.get("supplier_truth_summary") or ""),
                "supplier_truth_sources": _row_truth_sources(s),
                "official_name_truth_source": str(
                    s.get("official_name_truth_source") or ""
                ),
            }
        )

    suppliers_out.sort(key=lambda x: float(x.get("total_debt") or 0), reverse=True)
    return {"suppliers": suppliers_out, "summary": summary}


def build_ap_monthly_trend(
    rs_df,
    bank_payments,
    strict_bank_payments=None,
    manual_payments=None,
):
    df = _to_waybills_df(rs_df)
    if df.empty:
        return []

    date_col = next((c for c in df.columns if "გააქტიურების თარ" in str(c)), None)
    if not date_col and "date" in df.columns:
        date_col = "date"
    effective_col = (
        "ეფექტური თანხა" if "ეფექტური თანხა" in df.columns else "effective_amount" if "effective_amount" in df.columns else None
    )
    if not date_col or not effective_col:
        return []

    rs_monthly = defaultdict(float)
    for _, row in df.iterrows():
        month = _month_key(row.get(date_col))
        amt = pd.to_numeric(row.get(effective_col), errors="coerce")
        if pd.isna(amt):
            continue
        rs_monthly[month] += float(amt)

    if not rs_monthly:
        return []

    org_col = "ორგანიზაცია" if "ორგანიზაცია" in df.columns else "supplier" if "supplier" in df.columns else None
    rs_tax_ids = set()
    if org_col:
        for org in df[org_col].dropna().tolist():
            tax_id = _extract_tax_id_from_org(org)
            if tax_id:
                rs_tax_ids.add(tax_id)
    total_paid = sum(float(bank_payments.get(tid) or 0) for tid in rs_tax_ids)
    strict_bank_total_paid = sum(
        float((strict_bank_payments or {}).get(tid) or 0) for tid in rs_tax_ids
    )
    manual_total_paid = sum(
        float((manual_payments or {}).get(tid) or 0) for tid in rs_tax_ids
    )
    total_rs_effective = sum(float(v) for v in rs_monthly.values())
    payment_ratio = (float(total_paid) / float(total_rs_effective)) if total_rs_effective else 0.0
    strict_bank_payment_ratio = (
        float(strict_bank_total_paid) / float(total_rs_effective)
        if total_rs_effective
        else 0.0
    )
    manual_payment_ratio = (
        float(manual_total_paid) / float(total_rs_effective)
        if total_rs_effective
        else 0.0
    )

    cumulative_debt = 0.0
    trend = []
    for month in sorted(rs_monthly.keys(), key=_month_sort_key):
        rs_purchases = float(rs_monthly[month])
        estimated_payments = float(rs_purchases * payment_ratio)
        estimated_strict_bank_payments = float(
            rs_purchases * strict_bank_payment_ratio
        )
        estimated_manual_payments = float(rs_purchases * manual_payment_ratio)
        monthly_debt_change = float(rs_purchases - estimated_payments)
        cumulative_debt += monthly_debt_change
        trend.append(
            {
                "month": month,
                "rs_purchases": rs_purchases,
                "estimated_payments": estimated_payments,
                "estimated_strict_bank_payments": estimated_strict_bank_payments,
                "estimated_manual_payments": estimated_manual_payments,
                "monthly_debt_change": monthly_debt_change,
                "cumulative_debt": float(cumulative_debt),
                "payment_scope": "combined_supplier_paid",
            }
        )
    return trend


def build_financial_ratios(monthly_pnl, supplier_aging, ap_monthly_trend):
    monthly_rows = list(monthly_pnl or [])
    supplier_rows = list(supplier_aging or [])
    ap_rows = list(ap_monthly_trend or [])

    def _safe_pct(numerator, denominator):
        den = float(denominator or 0)
        if den == 0:
            return 0.0
        return float((float(numerator or 0) / den) * 100.0)

    def _safe_list(value):
        if isinstance(value, (list, tuple, set)):
            return [str(x) for x in value if str(x).strip()]
        text = str(value or "").strip()
        return [text] if text else []

    monthly_rows = sorted(
        monthly_rows,
        key=lambda x: _month_sort_key(str((x or {}).get("month") or "უცნობი თვე")),
    )

    total_income = sum(
        float(((m.get("total") or {}).get("pos_income") or 0)) for m in monthly_rows
    )
    total_expenses = sum(
        float(((m.get("total") or {}).get("expenses") or 0)) for m in monthly_rows
    )
    total_net = sum(float(((m.get("total") or {}).get("net") or 0)) for m in monthly_rows)
    month_count = len(monthly_rows)
    avg_monthly_net = float(total_net / month_count) if month_count else 0.0

    total_paid = sum(float(s.get("total_paid") or 0) for s in supplier_rows)
    total_strict_bank_paid = sum(
        float(s.get("strict_bank_paid") or s.get("bank_paid") or 0)
        for s in supplier_rows
    )
    total_manual_paid = sum(float(s.get("manual_paid") or 0) for s in supplier_rows)
    total_effective = sum(float(s.get("total_effective") or 0) for s in supplier_rows)
    total_debt = sum(float(s.get("total_debt") or 0) for s in supplier_rows)

    ap_rows = sorted(
        ap_rows,
        key=lambda x: _month_sort_key(str((x or {}).get("month") or "უცნობი თვე")),
    )
    ap_monthly_purchases = [
        float(r.get("rs_purchases") or 0)
        for r in ap_rows
        if str(r.get("month") or "") != "უცნობი თვე"
    ]
    if not ap_monthly_purchases:
        ap_monthly_purchases = [float(r.get("rs_purchases") or 0) for r in ap_rows]
    last_three_rs_purchases = ap_monthly_purchases[-3:]
    avg_last_three_rs_purchases = (
        float(sum(last_three_rs_purchases) / len(last_three_rs_purchases))
        if last_three_rs_purchases
        else 0.0
    )
    ap_days = (
        float((total_debt / avg_last_three_rs_purchases) * 30.0)
        if avg_last_three_rs_purchases
        else 0.0
    )

    company_net_margin_pct = round(_safe_pct(total_net, total_income), 2)
    company = {
        "net_margin_pct": company_net_margin_pct,
        # Deprecated alias for backward compatibility with existing frontend fields.
        "gross_margin_pct": company_net_margin_pct,
        "payment_ratio_pct": round(_safe_pct(total_paid, total_effective), 2),
        "strict_bank_payment_ratio_pct": round(
            _safe_pct(total_strict_bank_paid, total_effective), 2
        ),
        "manual_payment_ratio_pct": round(
            _safe_pct(total_manual_paid, total_effective), 2
        ),
        "ap_days": int(round(ap_days)),
        "avg_monthly_net": round(avg_monthly_net, 2),
        "total_income": round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "total_net": round(total_net, 2),
        "total_debt": round(total_debt, 2),
        "total_paid": round(total_paid, 2),
        "total_strict_bank_paid": round(total_strict_bank_paid, 2),
        "total_manual_paid": round(total_manual_paid, 2),
        "total_effective": round(total_effective, 2),
    }

    objects = {}
    for obj_name in [OBJECT_OZURGETI, OBJECT_DVABZU]:
        obj_total_income = sum(
            float((((m.get("objects") or {}).get(obj_name) or {}).get("pos_income") or 0))
            for m in monthly_rows
        )
        obj_total_expenses = sum(
            float((((m.get("objects") or {}).get(obj_name) or {}).get("expenses") or 0))
            for m in monthly_rows
        )
        obj_total_net = sum(
            float((((m.get("objects") or {}).get(obj_name) or {}).get("net") or 0))
            for m in monthly_rows
        )
        obj_avg_net = float(obj_total_net / month_count) if month_count else 0.0
        obj_net_margin_pct = round(_safe_pct(obj_total_net, obj_total_income), 2)
        objects[obj_name] = {
            "net_margin_pct": obj_net_margin_pct,
            "gross_margin_pct": obj_net_margin_pct,
            "avg_monthly_net": round(obj_avg_net, 2),
            "share_of_income_pct": round(
                _safe_pct(obj_total_income, total_income), 2
            ),
            "share_of_expenses_pct": round(
                _safe_pct(obj_total_expenses, total_expenses), 2
            ),
            "total_income": round(obj_total_income, 2),
            "total_expenses": round(obj_total_expenses, 2),
            "total_net": round(obj_total_net, 2),
        }

    monthly_trend = []
    for m in monthly_rows[-12:]:
        total_row = m.get("total") or {}
        income_amount = float(total_row.get("pos_income") or 0)
        expenses_amount = float(total_row.get("expenses") or 0)
        net_amount = float(total_row.get("net") or 0)
        net_margin_pct = round(_safe_pct(net_amount, income_amount), 2)
        monthly_trend.append(
            {
                "month": str(m.get("month") or ""),
                "net_margin_pct": net_margin_pct,
                "gross_margin_pct": net_margin_pct,
                "net_amount": round(net_amount, 2),
                "income_amount": round(income_amount, 2),
                "expenses_amount": round(expenses_amount, 2),
            }
        )

    risk_candidates = [
        s for s in supplier_rows if float(s.get("total_debt") or 0) > 0
    ]
    risk_candidates.sort(key=lambda x: float(x.get("total_debt") or 0), reverse=True)
    top_risk_suppliers = []
    for s in risk_candidates[:5]:
        supplier_effective = float(s.get("total_effective") or 0)
        supplier_paid = float(s.get("total_paid") or 0)
        supplier_strict_bank_paid = float(
            s.get("strict_bank_paid") or s.get("bank_paid") or 0
        )
        supplier_manual_paid = float(s.get("manual_paid") or 0)
        days_since_last = s.get("days_since_last")
        supplier_truth_sources = _safe_list(s.get("supplier_truth_sources"))
        top_risk_suppliers.append(
            {
                "tax_id": str(s.get("tax_id") or ""),
                "org": str(s.get("org") or s.get("ორგანიზაცია") or ""),
                "total_debt": round(float(s.get("total_debt") or 0), 2),
                "days_since_last": (
                    int(days_since_last) if days_since_last is not None else None
                ),
                "aging_bucket": str(s.get("aging_bucket") or ""),
                "payment_ratio_pct": round(
                    _safe_pct(supplier_paid, supplier_effective), 2
                ),
                "strict_bank_paid": round(supplier_strict_bank_paid, 2),
                "manual_paid": round(supplier_manual_paid, 2),
                "combined_paid": round(supplier_paid, 2),
                "strict_bank_share_of_paid_pct": round(
                    _safe_pct(supplier_strict_bank_paid, supplier_paid), 2
                ),
                "manual_share_of_paid_pct": round(
                    _safe_pct(supplier_manual_paid, supplier_paid), 2
                ),
                "payment_scope": str(s.get("payment_scope") or ""),
                "payment_scope_note": str(s.get("payment_scope_note") or ""),
                "supplier_truth_summary": str(s.get("supplier_truth_summary") or ""),
                "supplier_truth_sources": supplier_truth_sources,
                "official_name_truth_source": str(
                    s.get("official_name_truth_source") or ""
                ),
            }
        )

    return {
        "company": company,
        "objects": objects,
        "monthly_trend": monthly_trend,
        "top_risk_suppliers": top_risk_suppliers,
    }


def build_forecast(monthly_pnl):
    monthly_rows = sorted(
        list(monthly_pnl or []),
        key=lambda x: _month_sort_key(str((x or {}).get("month") or "უცნობი თვე")),
    )
    object_names = [OBJECT_OZURGETI, OBJECT_DVABZU, OBJECT_COMMON, OBJECT_UNALLOCATED]

    valid_history = []
    for row in monthly_rows:
        month = str((row or {}).get("month") or "")
        month_dt = pd.to_datetime(month, errors="coerce", format="%Y-%m")
        if pd.isna(month_dt):
            continue
        valid_history.append({"month": month, "month_dt": month_dt, "row": row})

    def _safe_amount(v):
        return float(v or 0)

    def _rolling_avg(values, window=6):
        if not values:
            return 0.0
        sample = values[-window:] if len(values) >= window else values
        if not sample:
            return 0.0
        return float(sum(sample) / len(sample))

    total_income_series = [
        _safe_amount(((h.get("row") or {}).get("total") or {}).get("pos_income"))
        for h in valid_history
    ]
    total_expenses_series = [
        _safe_amount(((h.get("row") or {}).get("total") or {}).get("expenses"))
        for h in valid_history
    ]
    object_income_series = {obj: [] for obj in object_names}
    object_expenses_series = {obj: [] for obj in object_names}
    for h in valid_history:
        objects_map = (h.get("row") or {}).get("objects") or {}
        for obj in object_names:
            obj_data = objects_map.get(obj) or {}
            object_income_series[obj].append(_safe_amount(obj_data.get("pos_income")))
            object_expenses_series[obj].append(_safe_amount(obj_data.get("expenses")))

    if valid_history:
        last_month_dt = pd.Timestamp(valid_history[-1]["month_dt"]).to_period("M").to_timestamp()
    else:
        last_month_dt = pd.Timestamp.now().to_period("M").to_timestamp()

    forecast_months = []
    for month_idx in range(1, 7):
        month_dt = last_month_dt + pd.DateOffset(months=month_idx)
        month_key = month_dt.strftime("%Y-%m")

        total_income = _rolling_avg(total_income_series, window=6)
        total_expenses = _rolling_avg(total_expenses_series, window=6)
        total_net = float(total_income - total_expenses)
        total_income_series.append(total_income)
        total_expenses_series.append(total_expenses)

        month_objects = {}
        for obj in object_names:
            obj_income = _rolling_avg(object_income_series[obj], window=6)
            obj_expenses = _rolling_avg(object_expenses_series[obj], window=6)
            obj_net = float(obj_income - obj_expenses)
            object_income_series[obj].append(obj_income)
            object_expenses_series[obj].append(obj_expenses)
            month_objects[obj] = {
                "pos_income": round(obj_income, 2),
                "expenses": round(obj_expenses, 2),
                "net": round(obj_net, 2),
            }

        forecast_months.append(
            {
                "month": month_key,
                "is_forecast": True,
                "total": {
                    "pos_income": round(total_income, 2),
                    "expenses": round(total_expenses, 2),
                    "net": round(total_net, 2),
                },
                "objects": month_objects,
            }
        )

    forecast_section = {"method": "SMA-6", "months": forecast_months}

    month_labels = {
        1: "იანვარი",
        2: "თებერვალი",
        3: "მარტი",
        4: "აპრილი",
        5: "მაისი",
        6: "ივნისი",
        7: "ივლისი",
        8: "აგვისტო",
        9: "სექტემბერი",
        10: "ოქტომბერი",
        11: "ნოემბერი",
        12: "დეკემბერი",
    }
    by_month_raw = {
        month_num: {"income": [], "expenses": [], "net": []}
        for month_num in range(1, 13)
    }
    for h in valid_history:
        month_num = int(pd.Timestamp(h["month_dt"]).month)
        total_data = ((h.get("row") or {}).get("total") or {})
        income = _safe_amount(total_data.get("pos_income"))
        expenses = _safe_amount(total_data.get("expenses"))
        net = _safe_amount(total_data.get("net"))
        by_month_raw[month_num]["income"].append(income)
        by_month_raw[month_num]["expenses"].append(expenses)
        by_month_raw[month_num]["net"].append(net)

    all_income_values = []
    for month_num in range(1, 13):
        all_income_values.extend(by_month_raw[month_num]["income"])
    overall_avg_income = (
        float(sum(all_income_values) / len(all_income_values)) if all_income_values else 0.0
    )

    by_calendar_month = []
    for month_num in range(1, 13):
        income_arr = by_month_raw[month_num]["income"]
        expenses_arr = by_month_raw[month_num]["expenses"]
        net_arr = by_month_raw[month_num]["net"]
        months_count = len(income_arr)
        avg_income = float(sum(income_arr) / months_count) if months_count else 0.0
        avg_expenses = float(sum(expenses_arr) / months_count) if months_count else 0.0
        avg_net = float(sum(net_arr) / months_count) if months_count else 0.0
        seasonality_index = (
            float(avg_income / overall_avg_income) if overall_avg_income else 0.0
        )
        by_calendar_month.append(
            {
                "calendar_month": month_num,
                "label": month_labels[month_num],
                "avg_income": round(avg_income, 2),
                "avg_expenses": round(avg_expenses, 2),
                "avg_net": round(avg_net, 2),
                "months_count": months_count,
                "seasonality_index": round(seasonality_index, 2),
            }
        )

    seasonality_with_data = [m for m in by_calendar_month if int(m.get("months_count") or 0) > 0]
    if seasonality_with_data:
        strongest = max(seasonality_with_data, key=lambda x: float(x.get("seasonality_index") or 0))
        weakest = min(seasonality_with_data, key=lambda x: float(x.get("seasonality_index") or 0))
    else:
        strongest = {
            "calendar_month": 1,
            "label": month_labels[1],
            "seasonality_index": 0.0,
        }
        weakest = {
            "calendar_month": 1,
            "label": month_labels[1],
            "seasonality_index": 0.0,
        }

    seasonality_section = {
        "by_calendar_month": by_calendar_month,
        "strongest_month": {
            "calendar_month": int(strongest.get("calendar_month") or 1),
            "label": str(strongest.get("label") or month_labels[1]),
            "seasonality_index": round(float(strongest.get("seasonality_index") or 0), 2),
        },
        "weakest_month": {
            "calendar_month": int(weakest.get("calendar_month") or 1),
            "label": str(weakest.get("label") or month_labels[1]),
            "seasonality_index": round(float(weakest.get("seasonality_index") or 0), 2),
        },
    }

    history_rows = [h.get("row") or {} for h in valid_history]
    prev_12_rows = history_rows[-24:-12]
    last_12_rows = history_rows[-12:]

    def _sum_total(rows, metric_key):
        return float(
            sum(_safe_amount(((r.get("total") or {}).get(metric_key))) for r in rows)
        )

    last_12_income = _sum_total(last_12_rows, "pos_income")
    last_12_expenses = _sum_total(last_12_rows, "expenses")
    last_12_net = _sum_total(last_12_rows, "net")
    prev_12_income = _sum_total(prev_12_rows, "pos_income")
    prev_12_expenses = _sum_total(prev_12_rows, "expenses")
    prev_12_net = _sum_total(prev_12_rows, "net")

    def _pct_change(current_value, previous_value):
        prev_val = float(previous_value or 0)
        if prev_val == 0:
            return 0.0
        return float(((float(current_value or 0) - prev_val) / prev_val) * 100.0)

    yoy_section = {
        "last_12m": {
            "income": round(last_12_income, 2),
            "expenses": round(last_12_expenses, 2),
            "net": round(last_12_net, 2),
        },
        "prev_12m": {
            "income": round(prev_12_income, 2),
            "expenses": round(prev_12_expenses, 2),
            "net": round(prev_12_net, 2),
        },
        "income_change_pct": round(_pct_change(last_12_income, prev_12_income), 2),
        "expenses_change_pct": round(_pct_change(last_12_expenses, prev_12_expenses), 2),
        "net_change_pct": round(_pct_change(last_12_net, prev_12_net), 2),
    }

    return {
        "forecast": forecast_section,
        "seasonality": seasonality_section,
        "yoy": yoy_section,
    }


def build_budget(monthly_pnl, forecast_data, budget_config):
    monthly_rows = sorted(
        list(monthly_pnl or []),
        key=lambda x: _month_sort_key(str((x or {}).get("month") or "უცნობი თვე")),
    )
    forecast_obj = forecast_data or {}
    config = budget_config or _clone_default_budget_config()

    def _safe_float(value, default=0.0):
        try:
            if value is None:
                return float(default)
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _safe_pct_delta(actual_value, plan_value):
        plan = float(plan_value or 0)
        if plan == 0:
            return 0.0
        return float(((float(actual_value or 0) - plan) / plan) * 100.0)

    def _as_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "y", "on")

    valid_actual_rows = []
    for row in monthly_rows:
        month_key = str((row or {}).get("month") or "")
        month_dt = pd.to_datetime(month_key, errors="coerce", format="%Y-%m")
        if pd.isna(month_dt):
            continue
        total = (row.get("total") or {})
        valid_actual_rows.append(
            {
                "month": month_dt.strftime("%Y-%m"),
                "year": int(month_dt.year),
                "month_num": int(month_dt.month),
                "income": _safe_float(total.get("pos_income")),
                "expenses": _safe_float(total.get("expenses")),
                "net": _safe_float(total.get("net")),
            }
        )

    actual_yearly = defaultdict(
        lambda: {"income": 0.0, "expenses": 0.0, "net": 0.0, "months": set()}
    )
    actual_monthly_map = {}
    for item in valid_actual_rows:
        year = int(item["year"])
        month_num = int(item["month_num"])
        key = (year, month_num)
        actual_monthly_map[key] = {
            "income": float(item["income"]),
            "expenses": float(item["expenses"]),
            "net": float(item["net"]),
        }
        actual_yearly[year]["income"] += float(item["income"])
        actual_yearly[year]["expenses"] += float(item["expenses"])
        actual_yearly[year]["net"] += float(item["net"])
        actual_yearly[year]["months"].add(month_num)

    seasonality_rows = (
        ((forecast_obj.get("seasonality") or {}).get("by_calendar_month")) or []
    )
    seasonality_indices = {m: 1.0 for m in range(1, 13)}
    for row in seasonality_rows:
        month_num = int(_safe_float(row.get("calendar_month"), 0))
        if 1 <= month_num <= 12:
            seasonality_indices[month_num] = _safe_float(
                row.get("seasonality_index"), 1.0
            )
    seasonality_sum = float(
        sum(v for v in seasonality_indices.values() if float(v) > 0)
    )
    if seasonality_sum <= 0:
        seasonality_sum = 12.0
        seasonality_indices = {m: 1.0 for m in range(1, 13)}

    yoy = forecast_obj.get("yoy") or {}
    growth_rates = {
        "income": _safe_float(yoy.get("income_change_pct")) / 100.0,
        "expenses": _safe_float(yoy.get("expenses_change_pct")) / 100.0,
        "net": _safe_float(yoy.get("net_change_pct")) / 100.0,
    }
    expense_growth_cap = _safe_float(config.get("expense_growth_cap_pct")) / 100.0
    auto_mode = _as_bool(config.get("auto_mode"), default=True)
    annual_targets = config.get("annual_targets") or {}
    if not isinstance(annual_targets, dict):
        annual_targets = {}

    def _annualized_actual(year, metric):
        year_info = actual_yearly.get(int(year))
        if not year_info:
            return None
        month_count = len(year_info.get("months") or set())
        if month_count == 0:
            return None
        metric_sum = float(year_info.get(metric) or 0)
        if month_count < 12:
            return float((metric_sum / month_count) * 12.0)
        return float(metric_sum)

    current_year = int(pd.Timestamp.now().year)
    planning_years = list(range(2022, current_year + 2))
    annual_plan = {}
    for year in planning_years:
        year_cfg = annual_targets.get(str(year)) or {}
        if not isinstance(year_cfg, dict):
            year_cfg = {}
        year_plan = {}
        for metric in ("income", "expenses", "net"):
            cfg_value = year_cfg.get(metric)
            manual_target = None
            if cfg_value is not None:
                try:
                    manual_target = float(cfg_value)
                except (TypeError, ValueError):
                    manual_target = None
            if manual_target is not None:
                year_plan[metric] = float(manual_target)
                continue

            if not auto_mode:
                year_plan[metric] = 0.0
                continue

            prev_year = year - 1
            base_value = _annualized_actual(prev_year, metric)
            if base_value is None and (prev_year in annual_plan):
                base_value = float((annual_plan.get(prev_year) or {}).get(metric) or 0)
            if base_value is None:
                same_year_actual = _annualized_actual(year, metric)
                base_value = same_year_actual if same_year_actual is not None else 0.0

            growth = float(growth_rates.get(metric) or 0.0)
            if metric == "expenses" and growth > expense_growth_cap:
                growth = expense_growth_cap
            year_plan[metric] = float(base_value * (1.0 + growth))
        annual_plan[year] = year_plan

    monthly_plan_map = {}
    for year in planning_years:
        year_plan = annual_plan.get(year) or {}
        annual_income = float(year_plan.get("income") or 0)
        annual_expenses = float(year_plan.get("expenses") or 0)
        for month_num in range(1, 13):
            month_idx = float(seasonality_indices.get(month_num) or 0)
            plan_income = (
                float(annual_income * (month_idx / seasonality_sum))
                if seasonality_sum
                else float(annual_income / 12.0)
            )
            plan_expenses = float(annual_expenses / 12.0)
            monthly_plan_map[(year, month_num)] = {
                "income": plan_income,
                "expenses": plan_expenses,
                "net": float(plan_income - plan_expenses),
            }

    monthly_output = []
    for row in valid_actual_rows:
        year = int(row["year"])
        month_num = int(row["month_num"])
        plan = monthly_plan_map.get(
            (year, month_num), {"income": 0.0, "expenses": 0.0, "net": 0.0}
        )
        actual = {
            "income": float(row["income"]),
            "expenses": float(row["expenses"]),
            "net": float(row["net"]),
        }
        variance = {
            "income": float(actual["income"] - float(plan.get("income") or 0)),
            "expenses": float(actual["expenses"] - float(plan.get("expenses") or 0)),
            "net": float(actual["net"] - float(plan.get("net") or 0)),
        }
        variance_pct = {
            "income": _safe_pct_delta(actual["income"], plan.get("income")),
            "expenses": _safe_pct_delta(actual["expenses"], plan.get("expenses")),
            "net": _safe_pct_delta(actual["net"], plan.get("net")),
        }
        monthly_output.append(
            {
                "month": row["month"],
                "plan": {
                    "income": round(float(plan.get("income") or 0), 2),
                    "expenses": round(float(plan.get("expenses") or 0), 2),
                    "net": round(float(plan.get("net") or 0), 2),
                },
                "actual": {
                    "income": round(actual["income"], 2),
                    "expenses": round(actual["expenses"], 2),
                    "net": round(actual["net"], 2),
                },
                "variance": {
                    "income": round(variance["income"], 2),
                    "expenses": round(variance["expenses"], 2),
                    "net": round(variance["net"], 2),
                },
                "variance_pct": {
                    "income": round(variance_pct["income"], 2),
                    "expenses": round(variance_pct["expenses"], 2),
                    "net": round(variance_pct["net"], 2),
                },
                "on_track": bool(actual["net"] >= float(plan.get("net") or 0)),
            }
        )

    annual_output = {}
    for year in planning_years:
        plan_income = sum(
            float((monthly_plan_map.get((year, m)) or {}).get("income") or 0)
            for m in range(1, 13)
        )
        plan_expenses = sum(
            float((monthly_plan_map.get((year, m)) or {}).get("expenses") or 0)
            for m in range(1, 13)
        )
        plan_net = float(plan_income - plan_expenses)
        year_actual = actual_yearly.get(year) or {
            "income": 0.0,
            "expenses": 0.0,
            "net": 0.0,
            "months": set(),
        }
        actual_income = float(year_actual.get("income") or 0)
        actual_expenses = float(year_actual.get("expenses") or 0)
        actual_net = float(year_actual.get("net") or 0)
        month_count = len(year_actual.get("months") or set())
        remaining_months = max(0, 12 - month_count)
        completion_pct = (
            float((actual_income / plan_income) * 100.0) if float(plan_income) else 0.0
        )
        if month_count > 0:
            projected_monthly_net = float(actual_net / month_count)
        else:
            projected_monthly_net = float(plan_net / 12.0) if plan_net else 0.0
        projected_annual_net = float(actual_net + remaining_months * projected_monthly_net)
        annual_output[str(year)] = {
            "plan": {
                "income": round(plan_income, 2),
                "expenses": round(plan_expenses, 2),
                "net": round(plan_net, 2),
            },
            "actual": {
                "income": round(actual_income, 2),
                "expenses": round(actual_expenses, 2),
                "net": round(actual_net, 2),
            },
            "variance": {
                "income": round(actual_income - plan_income, 2),
                "expenses": round(actual_expenses - plan_expenses, 2),
                "net": round(actual_net - plan_net, 2),
            },
            "completion_pct": round(completion_pct, 2),
            "remaining_months": int(remaining_months),
            "projected_annual_net": round(projected_annual_net, 2),
        }

    current_actual_months = sorted((actual_yearly.get(current_year) or {}).get("months") or [])
    months_elapsed = len(current_actual_months)
    plan_ytd = {"income": 0.0, "expenses": 0.0, "net": 0.0}
    actual_ytd = {"income": 0.0, "expenses": 0.0, "net": 0.0}
    for month_num in current_actual_months:
        plan_vals = monthly_plan_map.get(
            (current_year, month_num), {"income": 0.0, "expenses": 0.0, "net": 0.0}
        )
        act_vals = actual_monthly_map.get(
            (current_year, month_num), {"income": 0.0, "expenses": 0.0, "net": 0.0}
        )
        for metric in ("income", "expenses", "net"):
            plan_ytd[metric] += float(plan_vals.get(metric) or 0)
            actual_ytd[metric] += float(act_vals.get(metric) or 0)
    variance_ytd = {
        metric: float(actual_ytd[metric] - plan_ytd[metric])
        for metric in ("income", "expenses", "net")
    }
    ytd_summary = {
        "current_year": str(current_year),
        "months_elapsed": int(months_elapsed),
        "plan_ytd": {
            "income": round(plan_ytd["income"], 2),
            "expenses": round(plan_ytd["expenses"], 2),
            "net": round(plan_ytd["net"], 2),
        },
        "actual_ytd": {
            "income": round(actual_ytd["income"], 2),
            "expenses": round(actual_ytd["expenses"], 2),
            "net": round(actual_ytd["net"], 2),
        },
        "variance_ytd": {
            "income": round(variance_ytd["income"], 2),
            "expenses": round(variance_ytd["expenses"], 2),
            "net": round(variance_ytd["net"], 2),
        },
        "on_track": bool(actual_ytd["net"] >= plan_ytd["net"]),
    }

    return {
        "config_source": "auto + budget_config.json",
        "annual": annual_output,
        "monthly": monthly_output,
        "ytd_summary": ytd_summary,
    }


def build_company_valuation(
    monthly_pnl, financial_ratios, forecast_data, sector_benchmarks
):
    ratios = financial_ratios or {}
    forecast = forecast_data or {}
    sector_cfg = sector_benchmarks or _clone_default_sector_benchmarks()
    benchmarks = sector_cfg.get("benchmarks") or {}

    def _safe_float(value, default=0.0):
        try:
            if value is None:
                return float(default)
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _assessment_from_score(score):
        if score >= 5:
            return "სექტორის საშუალოზე მნიშვნელოვნად მაღალი — ძლიერი"
        if score >= 4:
            return "სექტორის საშუალოზე მაღალი — კარგი"
        if score >= 3:
            return "სექტორის საშუალოსთან ახლოს — სტაბილური"
        if score >= 2:
            return "სექტორის საშუალოზე დაბალი — გასაუმჯობესებელია"
        return "სექტორულად მაღალი რისკი — სუსტი"

    def _high_better_comparison(
        metric_name, label_ka, your_value, sector_low, sector_median, sector_high
    ):
        v = float(your_value)
        if v > float(sector_high):
            position = "above_high"
            score = 5
        elif v > float(sector_median):
            position = "median_to_high"
            score = 4
        elif v > float(sector_low):
            position = "low_to_median"
            score = 3
        else:
            position = "below_low"
            score = 2
        return {
            "metric": metric_name,
            "label_ka": label_ka,
            "your_value": round(v, 2),
            "sector_low": float(sector_low),
            "sector_median": float(sector_median),
            "sector_high": float(sector_high),
            "position": position,
            "score": int(score),
            "assessment_ka": _assessment_from_score(score),
        }

    def _low_better_comparison(
        metric_name, label_ka, your_value, sector_good, sector_median, sector_high_risk
    ):
        v = float(your_value)
        if v < float(sector_good):
            position = "above_high"
            score = 5
        elif v < float(sector_median):
            position = "median_to_high"
            score = 4
        elif v < float(sector_high_risk):
            position = "low_to_median"
            score = 3
        else:
            position = "below_low"
            score = 1
        return {
            "metric": metric_name,
            "label_ka": label_ka,
            "your_value": round(v, 2),
            "sector_low": float(sector_good),
            "sector_median": float(sector_median),
            "sector_high": float(sector_high_risk),
            "position": position,
            "score": int(score),
            "assessment_ka": _assessment_from_score(score),
        }

    company_ratios = ratios.get("company") or {}
    forecast_yoy = forecast.get("yoy") or {}
    yoy_last_12m = forecast_yoy.get("last_12m") or {}
    annual_revenue = _safe_float(yoy_last_12m.get("income"))
    annual_net = _safe_float(yoy_last_12m.get("net"))
    if annual_revenue == 0 and monthly_pnl:
        monthly_rows = sorted(
            list(monthly_pnl or []),
            key=lambda x: _month_sort_key(str((x or {}).get("month") or "უცნობი თვე")),
        )
        valid_rows = []
        for row in monthly_rows:
            month_key = str((row or {}).get("month") or "")
            month_dt = pd.to_datetime(month_key, errors="coerce", format="%Y-%m")
            if pd.isna(month_dt):
                continue
            valid_rows.append(row)
        last_12_rows = valid_rows[-12:]
        annual_revenue = float(
            sum(
                _safe_float(((r.get("total") or {}).get("pos_income")))
                for r in last_12_rows
            )
        )
        annual_net = float(
            sum(_safe_float(((r.get("total") or {}).get("net"))) for r in last_12_rows)
        )
    net_margin_pct = _safe_float(company_ratios.get("net_margin_pct"))
    if net_margin_pct == 0.0 and annual_revenue:
        net_margin_pct = float((annual_net / annual_revenue) * 100.0)
    payment_ratio_pct = _safe_float(company_ratios.get("payment_ratio_pct"))
    ap_days = _safe_float(company_ratios.get("ap_days"))
    yoy_income_growth_pct = _safe_float(forecast_yoy.get("income_change_pct"))
    yoy_expenses_growth_pct = _safe_float(forecast_yoy.get("expenses_change_pct"))

    sector_comparison = []
    nm_b = benchmarks.get("net_margin_pct") or {}
    sector_comparison.append(
        _high_better_comparison(
            "net_margin_pct",
            "ნეტო მარჟა",
            net_margin_pct,
            _safe_float(nm_b.get("low")),
            _safe_float(nm_b.get("median")),
            _safe_float(nm_b.get("high")),
        )
    )
    pr_b = benchmarks.get("payment_ratio_pct") or {}
    sector_comparison.append(
        _high_better_comparison(
            "payment_ratio_pct",
            "გადახდის კოეფიციენტი",
            payment_ratio_pct,
            _safe_float(pr_b.get("low")),
            _safe_float(pr_b.get("median")),
            _safe_float(pr_b.get("high")),
        )
    )
    ap_b = benchmarks.get("ap_days") or {}
    sector_comparison.append(
        _low_better_comparison(
            "ap_days",
            "AP Days",
            ap_days,
            _safe_float(ap_b.get("good")),
            _safe_float(ap_b.get("median")),
            _safe_float(ap_b.get("high_risk")),
        )
    )
    rg_b = benchmarks.get("revenue_growth_yoy_pct") or {}
    sector_comparison.append(
        _high_better_comparison(
            "revenue_growth_yoy_pct",
            "წლიური შემოსავლის ზრდა",
            yoy_income_growth_pct,
            _safe_float(rg_b.get("low")),
            _safe_float(rg_b.get("median")),
            _safe_float(rg_b.get("high")),
        )
    )

    overall_sector_score = (
        float(sum(float(x.get("score") or 0) for x in sector_comparison))
        / len(sector_comparison)
        if sector_comparison
        else 0.0
    )
    metric_score_map = {
        str(item.get("metric")): int(item.get("score") or 0) for item in sector_comparison
    }
    nm_score = metric_score_map.get("net_margin_pct", 0)
    ap_score = metric_score_map.get("ap_days", 0)
    pay_score = metric_score_map.get("payment_ratio_pct", 0)
    if nm_score >= 4 and ap_score <= 2:
        overall_assessment_ka = (
            "კომპანია სექტორის საშუალოზე მაღლა დგას ნეტო მარჟით, მაგრამ AP Days კრიტიკულია"
        )
    elif overall_sector_score >= 4:
        overall_assessment_ka = "კომპანია სექტორის საშუალოზე მაღლა დგას და ოპერაციულად ძლიერი ჩანს"
    elif overall_sector_score >= 3:
        overall_assessment_ka = "კომპანია სექტორის საშუალოსთან ახლოსაა — გაუმჯობესების პოტენციალი არის"
    elif pay_score <= 2:
        overall_assessment_ka = "კომპანია სექტორის საშუალოზე დაბლაა და გადახდის დისციპლინა გასაძლიერებელია"
    else:
        overall_assessment_ka = "კომპანიის მაჩვენებლები სექტორულად სუსტ ზონაშია და რისკი მომატებულია"

    multiples = sector_cfg.get("valuation_multiples") or {}
    rev_mult = multiples.get("ev_to_revenue") or {}
    pe_mult = multiples.get("price_to_earnings") or {}
    skipped_methods = [
        {
            "method": "EBITDA Multiple",
            "status": "unsupported",
            "reason_ka": (
                "რეალური EBITDA-ის სანდო გამოთვლა მიმდინარე წყაროებით შეუძლებელია, "
                "ამიტომ მეთოდი valuation range-ში არ მონაწილეობს."
            ),
        }
    ]
    valuation_methods = [
        {
            "method": "Revenue Multiple",
            "low": round(float(annual_revenue * _safe_float(rev_mult.get("low"))), 2),
            "median": round(
                float(annual_revenue * _safe_float(rev_mult.get("median"))), 2
            ),
            "high": round(float(annual_revenue * _safe_float(rev_mult.get("high"))), 2),
        },
        {
            "method": "Earnings Multiple",
            "low": round(float(annual_net * _safe_float(pe_mult.get("low"))), 2),
            "median": round(float(annual_net * _safe_float(pe_mult.get("median"))), 2),
            "high": round(float(annual_net * _safe_float(pe_mult.get("high"))), 2),
        },
    ]
    range_low = min(float(m.get("low") or 0) for m in valuation_methods) if valuation_methods else 0.0
    range_median = (
        float(sum(float(m.get("median") or 0) for m in valuation_methods))
        / len(valuation_methods)
        if valuation_methods
        else 0.0
    )
    range_high = max(float(m.get("high") or 0) for m in valuation_methods) if valuation_methods else 0.0
    if valuation_methods and not (range_low < range_median < range_high):
        ordered = sorted([range_low, range_median, range_high])
        range_low, range_median, range_high = ordered[0], ordered[1], ordered[2]
    valuation = {
        "annual_revenue": round(annual_revenue, 2),
        "annual_net": round(annual_net, 2),
        "annual_ebitda": None,
        "methods": valuation_methods,
        "skipped_methods": skipped_methods,
        "range": {
            "low": round(range_low, 2),
            "median": round(range_median, 2),
            "high": round(range_high, 2),
        },
        "note_ka": (
            "შეფასება მიახლოებითია — ზუსტი ვალუაცია საჭიროებს "
            "აუდიტირებულ ფინანსურ ანგარიშგებას"
        ),
    }

    swot = {
        "strengths": [],
        "weaknesses": [],
        "opportunities": [],
        "threats": [],
    }

    def _swot_item(target_key, text_ka, metric, value, severity):
        swot[target_key].append(
            {
                "text_ka": str(text_ka),
                "metric": str(metric),
                "value": round(_safe_float(value), 2),
                "severity": str(severity),
            }
        )

    nm_high = _safe_float(nm_b.get("high"))
    ap_high_risk = _safe_float(ap_b.get("high_risk"))
    ap_median = _safe_float(ap_b.get("median"))
    pay_median = _safe_float(pr_b.get("median"))
    if net_margin_pct > nm_high:
        _swot_item(
            "strengths",
            "მარჟა სექტორის საშუალოზე მაღალია — ძლიერი მოგებიანობა",
            "net_margin_pct",
            net_margin_pct,
            "positive",
        )
    if payment_ratio_pct >= pay_median:
        _swot_item(
            "strengths",
            "მომწოდებლებთან გადახდის დისციპლინა სექტორულ საშუალოზეა",
            "payment_ratio_pct",
            payment_ratio_pct,
            "positive",
        )
    if ap_days > ap_high_risk:
        _swot_item(
            "weaknesses",
            "მომწოდებლების ვალის ვადა კრიტიკულია",
            "ap_days",
            ap_days,
            "negative",
        )
    elif ap_days > ap_median:
        _swot_item(
            "weaknesses",
            "AP Days სექტორულ საშუალოზე მაღალია",
            "ap_days",
            ap_days,
            "negative",
        )
    if net_margin_pct < _safe_float(nm_b.get("low")):
        _swot_item(
            "weaknesses",
            "ნეტო მარჟა სექტორულ მინიმუმზე დაბალია",
            "net_margin_pct",
            net_margin_pct,
            "negative",
        )
    if yoy_income_growth_pct > 15:
        _swot_item(
            "opportunities",
            "ზრდის ტემპი მაღალია — ახალი ობიექტის პოტენციალია",
            "revenue_growth_yoy_pct",
            yoy_income_growth_pct,
            "positive",
        )
    if overall_sector_score >= 3.5:
        _swot_item(
            "opportunities",
            "სექტორულად საშუალოზე მაღალი პოზიცია ზრდის დაფინანსების შანსს",
            "overall_sector_score",
            overall_sector_score,
            "positive",
        )
    if payment_ratio_pct < 80:
        _swot_item(
            "threats",
            "გადახდის რეიტინგი დაბალია — მომწოდებლის რისკი იზრდება",
            "payment_ratio_pct",
            payment_ratio_pct,
            "negative",
        )
    if yoy_expenses_growth_pct > yoy_income_growth_pct:
        _swot_item(
            "threats",
            "ხარჯების ზრდა უსწრებს შემოსავალს — მარჟაზე ზეწოლაა",
            "expenses_vs_income_growth_pct",
            yoy_expenses_growth_pct - yoy_income_growth_pct,
            "negative",
        )
    if ap_days > ap_high_risk:
        _swot_item(
            "threats",
            "მომწოდებლის მხრიდან მიწოდების შეზღუდვის რისკი მატულობს",
            "ap_days",
            ap_days,
            "negative",
        )

    if not swot["strengths"]:
        _swot_item(
            "strengths",
            "სტაბილური ოპერაციული პროფილი შენარჩუნებულია",
            "overall_sector_score",
            overall_sector_score,
            "neutral",
        )
    if not swot["weaknesses"]:
        _swot_item(
            "weaknesses",
            "მკვეთრი შიდა სისუსტე ჯერ არ ჩანს",
            "overall_sector_score",
            overall_sector_score,
            "neutral",
        )
    if not swot["opportunities"]:
        _swot_item(
            "opportunities",
            "გადანაწილებული მენეჯმენტის ოპტიმიზაცია შეუძლია წმინდა მოგების ზრდას",
            "overall_sector_score",
            overall_sector_score,
            "neutral",
        )
    if not swot["threats"]:
        _swot_item(
            "threats",
            "სექტორის კონკურენცია და ფასების წნეხი მუდმივი რისკია",
            "overall_sector_score",
            overall_sector_score,
            "neutral",
        )

    object_efficiency = {}
    ratio_objects = ratios.get("objects") or {}
    for obj_name in (OBJECT_OZURGETI, OBJECT_DVABZU):
        obj_data = ratio_objects.get(obj_name) or {}
        obj_net_margin = _safe_float(obj_data.get("net_margin_pct"))
        if obj_net_margin == 0.0 and obj_data.get("gross_margin_pct") is not None:
            obj_net_margin = _safe_float(obj_data.get("gross_margin_pct"))
        income_share = _safe_float(obj_data.get("share_of_income_pct"))
        expense_share = _safe_float(obj_data.get("share_of_expenses_pct"))
        score_raw = (
            obj_net_margin * 0.4
            + income_share * 0.3
            + (100.0 - expense_share) * 0.3
        )
        score = max(0.0, min(100.0, float(score_raw)))
        if expense_share < 10:
            note_ka = (
                "ხარჯის განაწილება შესაძლოა არაზუსტია — ტექსტით ატრიბუცია შეზღუდულია"
            )
        else:
            note_ka = "ეფექტურობა შეფასებულია მიმდინარე ატრიბუციის საფუძველზე"
        object_efficiency[obj_name] = {"score": round(score, 2), "note_ka": note_ka}

    return {
        "sector_comparison": sector_comparison,
        "overall_sector_score": round(overall_sector_score, 2),
        "overall_assessment_ka": overall_assessment_ka,
        "margin_semantics": {
            "primary_metric": "net_margin_pct",
            "deprecated_alias": "gross_margin_pct",
        },
        "valuation": valuation,
        "swot": swot,
        "object_efficiency": object_efficiency,
    }


def build_executive_summary(data):
    payload = data or {}

    def _safe_float(value, default=0.0):
        try:
            if value is None:
                return float(default)
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    monthly_pnl = list(payload.get("monthly_pnl") or [])
    financial_ratios = payload.get("financial_ratios") or {}
    forecast = payload.get("forecast") or {}
    budget = payload.get("budget") or {}
    company_valuation = payload.get("company_valuation") or {}
    supplier_aging = list(payload.get("supplier_aging") or [])
    tbc_expenses = payload.get("tbc_expenses") or {}
    bog_expenses = payload.get("bog_expenses") or {}
    meta = payload.get("meta") or {}
    unmatched_analysis = payload.get("bank_unmatched_analysis") or {}

    valid_months = []
    for row in monthly_pnl:
        month_key = str((row or {}).get("month") or "")
        month_dt = pd.to_datetime(month_key, errors="coerce", format="%Y-%m")
        if pd.isna(month_dt):
            continue
        valid_months.append(month_dt.strftime("%Y-%m"))
    valid_months = sorted(set(valid_months))
    months_count = len(valid_months)
    years_covered = float(months_count / 12.0) if months_count else 0.0

    pos_total = _safe_float((payload.get("pos_terminal_income") or {}).get("total_ge"))
    revenue_tracking_score = 90 if pos_total > 0 else 0
    revenue_note = (
        "POS ბარათით შემოსავალი ტრეკირდება TBC+BOG-დან. "
        "ნაღდი ამონაგები (სალარო) ჯერ არ არის სისტემაში — აუდიტისთვის საჭიროა."
    )

    tbc_exists = isinstance(tbc_expenses, dict)
    bog_exists = isinstance(bog_expenses, dict)
    expense_categorization_score = 80 if (tbc_exists and bog_exists) else 0
    unmatched_total = _safe_float(unmatched_analysis.get("total_ge"))
    uncategorized_total = _safe_float(unmatched_analysis.get("uncategorized_total_ge"))
    other_pct = (
        float((uncategorized_total / unmatched_total) * 100.0) if unmatched_total else 0.0
    )
    expense_note = (
        "TBC + BOG ხარჯი კატეგორიზებულია (~15 კატეგორია). "
        f"არამიბმული ბანკის ხაზების {other_pct:.1f}% ჯერ 'სხვა'-შია."
    )

    unmatched_lines = int(_safe_float(meta.get("bank_unmatched_line_count")))
    unmatched_ge = _safe_float(meta.get("bank_unmatched_total_ge"))
    tbc_expenses_total_ge = _safe_float(tbc_expenses.get("grand_total_ge"))
    bog_expenses_total_ge = _safe_float(bog_expenses.get("grand_total_ge"))
    reconciliation_denominator = (
        tbc_expenses_total_ge + bog_expenses_total_ge + unmatched_ge
    )
    unmatched_share_pct = (
        float((unmatched_ge / reconciliation_denominator) * 100.0)
        if reconciliation_denominator > 0
        else 0.0
    )
    if unmatched_ge == 0 and unmatched_lines == 0:
        supplier_reconciliation_score = 100
    elif unmatched_share_pct <= 1.0:
        supplier_reconciliation_score = 95
    elif unmatched_share_pct <= 3.0:
        supplier_reconciliation_score = 85
    elif unmatched_share_pct <= 7.0:
        supplier_reconciliation_score = 70
    elif unmatched_share_pct <= 12.0:
        supplier_reconciliation_score = 55
    else:
        supplier_reconciliation_score = 35
    supplier_note = (
        "RS ↔ ბანკი მიბმულია საგადასახადო ID-ით. "
        f"არამიბმული: {unmatched_lines} ხაზი, {unmatched_ge:,.2f} ₾ "
        f"({unmatched_share_pct:.2f}% შესაბამისი საბაზო მოცულობიდან)."
    )

    period_coverage_score = min(100.0, float((months_count / 48.0) * 100.0))
    period_note = (
        f"{months_count} თვე დაფარულია ({years_covered:.1f} წელი). "
        "აუდიტისთვის მინ. 12 თვე საჭიროა."
    )

    budget_exists_score = 70 if bool(budget) else 0
    budget_note = (
        "ავტომატური ბიუჯეტი (SMA-6 + სეზონურობა). "
        "ხელით annual_targets ჯერ არ არის შევსებული."
    )

    object_separation_score = 60
    object_separation_note = (
        "ოზურგეთი/დვაბზუ გამოიყოფა POS-ში და RS-ში. ხარჯების ატრიბუცია ნაწილობრივია."
    )

    cash_tracking_score = 20
    cash_tracking_note = (
        "ნაღდი გადახდები manual_payments.csv-ით. "
        "სალაროს ამონაგები არ არის — ეს მთავარი ხვრელია."
    )

    criteria = [
        {
            "criterion": "revenue_tracking",
            "label_ka": "შემოსავლის ტრეკინგი",
            "score": int(revenue_tracking_score),
            "note_ka": revenue_note,
        },
        {
            "criterion": "expense_categorization",
            "label_ka": "ხარჯების კატეგორიზაცია",
            "score": int(expense_categorization_score),
            "note_ka": expense_note,
        },
        {
            "criterion": "supplier_reconciliation",
            "label_ka": "მომწოდებელთა რეკონცილიაცია",
            "score": int(supplier_reconciliation_score),
            "note_ka": supplier_note,
        },
        {
            "criterion": "period_coverage",
            "label_ka": "პერიოდის დაფარვა",
            "score": int(round(period_coverage_score)),
            "note_ka": period_note,
        },
        {
            "criterion": "budget_exists",
            "label_ka": "ბიუჯეტის არსებობა",
            "score": int(budget_exists_score),
            "note_ka": budget_note,
        },
        {
            "criterion": "object_separation",
            "label_ka": "ობიექტების გამიჯვნა",
            "score": int(object_separation_score),
            "note_ka": object_separation_note,
        },
        {
            "criterion": "cash_tracking",
            "label_ka": "ნაღდი ფულის ტრეკინგი",
            "score": int(cash_tracking_score),
            "note_ka": cash_tracking_note,
        },
    ]
    overall_audit_score = (
        float(sum(float(c.get("score") or 0) for c in criteria)) / len(criteria)
        if criteria
        else 0.0
    )
    overall_audit_score_int = int(round(overall_audit_score))
    if overall_audit_score_int >= 85:
        grade = "A"
    elif overall_audit_score_int >= 70:
        grade = "B"
    elif overall_audit_score_int >= 55:
        grade = "C"
    elif overall_audit_score_int >= 40:
        grade = "D"
    else:
        grade = "F"

    grade_recommendations = {
        "A": "აუდიტის მზადყოფნა მაღალია — დარჩენილია კონტროლების დოკუმენტური ფორმალიზება.",
        "B": "აუდიტის მზადყოფნა კარგია, მაგრამ ნაღდი ნაკადები და ობიექტური ხარჯები გასამყარებელია.",
        "C": "აუდიტამდე აუცილებელია ნაღდი ამონაგების ინტეგრაცია და ხარჯების უფრო ზუსტი ატრიბუცია.",
        "D": "აუდიტის მზადყოფნა სუსტია — კრიტიკული კონტროლები და პირველადი მონაცემები დასამატებელია.",
        "F": "აუდიტის მზადყოფნა არასაკმარისია — საჭიროა ფინანსური პროცესების ფუნდამენტური რეორგანიზაცია.",
    }
    audit_readiness = {
        "criteria": criteria,
        "overall_score": overall_audit_score_int,
        "grade": grade,
        "recommendation_ka": grade_recommendations.get(grade) or grade_recommendations["C"],
    }

    company = financial_ratios.get("company") or {}
    forecast_yoy = forecast.get("yoy") or {}
    seasonality = forecast.get("seasonality") or {}
    valuation_range = ((company_valuation.get("valuation") or {}).get("range")) or {}
    object_ratios = financial_ratios.get("objects") or {}
    period_text = (
        f"{valid_months[0]} — {valid_months[-1]} ({months_count} თვე)"
        if valid_months
        else "უცნობი პერიოდი"
    )
    object_list = [
        obj
        for obj in [OBJECT_OZURGETI, OBJECT_DVABZU]
        if obj in object_ratios
    ]
    if not object_list:
        object_list = [OBJECT_OZURGETI, OBJECT_DVABZU]

    total_income = _safe_float(company.get("total_income"))
    total_expenses = _safe_float(company.get("total_expenses"))
    total_net = _safe_float(company.get("total_net"))
    period_years = float(months_count / 12.0) if months_count else 0.0
    annual_revenue = float(total_income / period_years) if period_years else 0.0
    annual_expenses = float(total_expenses / period_years) if period_years else 0.0
    annual_net = float(total_net / period_years) if period_years else 0.0
    net_margin_pct = _safe_float(company.get("net_margin_pct"))
    if net_margin_pct == 0.0 and company.get("gross_margin_pct") is not None:
        net_margin_pct = _safe_float(company.get("gross_margin_pct"))
    payment_ratio_pct = _safe_float(company.get("payment_ratio_pct"))
    ap_days = _safe_float(company.get("ap_days"))
    yoy_growth_pct = _safe_float(forecast_yoy.get("net_change_pct"))

    growth_label = "ძლიერ"
    if yoy_growth_pct < 5:
        growth_label = "სუსტ"
    elif yoy_growth_pct < 15:
        growth_label = "ზომიერ"
    margin_label = "მაღალი"
    if net_margin_pct < 2:
        margin_label = "დაბალი"
    elif net_margin_pct < 8:
        margin_label = "საშუალო"
    ap_status = "კრიტიკულია"
    if ap_days <= 30:
        ap_status = "შესანიშნავია"
    elif ap_days <= 90:
        ap_status = "ნორმაშია"
    connector = "მაგრამ" if ap_status == "კრიტიკულია" else "და"
    headline_ka = (
        f"კომპანია აჩვენებს {growth_label} ზრდას ({yoy_growth_pct:+.0f}% YoY net) "
        f"{margin_label} ნეტო მარჟით ({net_margin_pct:.0f}%), {connector} "
        f"AP Days ({int(round(ap_days))}) {ap_status}."
    )

    strongest_month = seasonality.get("strongest_month") or {}
    weakest_month = seasonality.get("weakest_month") or {}
    total_debt = float(sum(_safe_float(s.get("total_debt")) for s in supplier_aging))
    budget_on_track = bool(((budget.get("ytd_summary") or {}).get("on_track")))
    sector_score = _safe_float(company_valuation.get("overall_sector_score"))
    valuation_median = _safe_float(valuation_range.get("median"))

    kpis = {
        "annual_revenue": round(annual_revenue, 2),
        "annual_expenses": round(annual_expenses, 2),
        "annual_net": round(annual_net, 2),
        "net_margin_pct": round(net_margin_pct, 2),
        "gross_margin_pct": round(net_margin_pct, 2),
        "payment_ratio_pct": round(payment_ratio_pct, 2),
        "ap_days": round(ap_days, 2),
        "yoy_growth_pct": round(yoy_growth_pct, 2),
        "valuation_median": round(valuation_median, 2),
        "sector_score": round(sector_score, 2),
        "strongest_month": str(strongest_month.get("label") or ""),
        "weakest_month": str(weakest_month.get("label") or ""),
        "total_suppliers_with_debt": int(len(supplier_aging)),
        "total_debt": round(total_debt, 2),
        "budget_on_track": budget_on_track,
    }

    dv_ratio = object_ratios.get(OBJECT_DVABZU) or {}
    dv_margin = _safe_float(dv_ratio.get("net_margin_pct"))
    if dv_margin == 0.0 and dv_ratio.get("gross_margin_pct") is not None:
        dv_margin = _safe_float(dv_ratio.get("gross_margin_pct"))
    yoy_income = _safe_float(forecast_yoy.get("income_change_pct"))
    strongest_idx = _safe_float(strongest_month.get("seasonality_index"))
    key_decisions = [
        {
            "priority": 1,
            "area": "AP Management",
            "decision_ka": (
                f"AP Days {int(round(ap_days))} — მომწოდებლებთან გადახდის ვადა კრიტიკულია. "
                "რეკომენდაცია: TOP 5 მომწოდებელთან გადახდის გრაფიკის შეთანხმება."
            ),
            "impact_ka": "რისკის შემცირება — მომწოდებელმა შეიძლება პირობები გაამკაცროს ან მიწოდება შეაჩეროს.",
        },
        {
            "priority": 2,
            "area": "Cash Tracking",
            "decision_ka": (
                "ნაღდი ამონაგები (სალარო) სისტემაში არ არის. "
                "რეკომენდაცია: Z-ანგარიშგების ან სალაროს ჟურნალის ინტეგრაცია."
            ),
            "impact_ka": "შემოსავალი არასრულია — P&L და ვალუაცია ქვედა ზღვარია.",
        },
        {
            "priority": 3,
            "area": "Growth Strategy",
            "decision_ka": (
                f"YoY ზრდა {yoy_income:+.0f}% შემოსავალით, {yoy_growth_pct:+.0f}% net-ით. "
                f"სეზონური პიკი {str(strongest_month.get('label') or 'აგვისტო')} "
                f"(×{strongest_idx:.2f}). რეკომენდაცია: ზაფხულისთვის მარაგის და პერსონალის დაგეგმვა."
            ),
            "impact_ka": "სეზონური მაქსიმუმის ოპტიმიზაცია — +10-15% ზრდის პოტენციალი.",
        },
        {
            "priority": 4,
            "area": "Object Expansion",
            "decision_ka": (
                "ორი ობიექტი მუშაობს. "
                f"დვაბზუ მაღალი net margin-ით ჩანს ({dv_margin:.0f}%) — მაგრამ ხარჯის ატრიბუცია არაზუსტია. "
                "რეკომენდაცია: ობიექტების ხარჯის ზუსტი გამიჯვნა, შემდეგ მესამე ობიექტის ფიზიბილითი."
            ),
            "impact_ka": "გაფართოების გადაწყვეტილება ზუსტ ციფრებს საჭიროებს.",
        },
        {
            "priority": 5,
            "area": "Budget Targets",
            "decision_ka": (
                "ავტომატური ბიუჯეტი მუშაობს. "
                "რეკომენდაცია: budget_config.json-ში 2026 წლის სამიზნეები ხელით შეავსე."
            ),
            "impact_ka": "Plan vs Actual ტრეკინგი რეალისტური გახდება.",
        },
    ]
    next_steps = [
        "სალაროს ამონაგების ინტეგრაცია",
        "POS304BB/POS1XA88 ტერმინალების ობიექტზე მინიჭება",
        "budget_config.json-ში 2026 annual_targets-ის შევსება",
        "TOP 5 მომწოდებელთან გადახდის გრაფიკი",
        "ობიექტების ხარჯის ზუსტი გამიჯვნა (ცალკე ბანკის ანგარიში?)",
    ]

    executive = {
        "company_name": "FOODTIME LLC",
        "period": period_text,
        "objects": object_list,
        "headline_ka": headline_ka,
        "kpis": kpis,
        "key_decisions": key_decisions,
        "next_steps": next_steps,
    }

    return {"audit_readiness": audit_readiness, "executive": executive}


def publish_download_excels(download_dir, public_dir):
    """Backward-compatible wrapper for shared export helper."""
    return _publish_download_excels_external(download_dir, public_dir)


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


def _expenses_public_json(bundle, ledger_note_ka):
    """data.json — უსაფრთხო ზომა: preview, სრული ხაზები მხოლოდ Excel-ში."""
    if not bundle or not bundle.get("categories"):
        return {
            "grand_total_ge": 0.0,
            "grand_total_operating_expense_ge": 0.0,
            "grand_total_state_treasury_ge": 0.0,
            "ledger_note_ka": ledger_note_ka,
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
        "ledger_note_ka": ledger_note_ka,
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


def tbc_expenses_public_json(bundle):
    return _expenses_public_json(bundle, TBC_EXPENSES_LEDGER_NOTE_KA)


def bog_expenses_public_json(bundle):
    return _expenses_public_json(bundle, BOG_EXPENSES_LEDGER_NOTE_KA)


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


# Legacy truth-assist only:
# BOG/TBC partner IBAN -> RS tax_id. გამოიყენება audit/provenance helper-ად,
# არა strict supplier auto-match primary truth-ად.
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


def supplier_matching_registry_path():
    return _financial_analysis_path("supplier_matching_registry.json")


def load_supplier_matching_registry():
    """
    Optional registry:
    Financial_Analysis/supplier_matching_registry.json
    """
    path = supplier_matching_registry_path()
    empty = {"suppliers": [], "explicit_skip_keywords": []}
    if not os.path.isfile(path):
        return empty
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        print(f"  [warn] supplier registry read failed: {e}")
        return empty
    if not isinstance(raw, dict):
        return empty
    suppliers = raw.get("suppliers")
    if not isinstance(suppliers, list):
        suppliers = []
    skip_keywords = raw.get("explicit_skip_keywords") or []
    if not isinstance(skip_keywords, list):
        skip_keywords = []
    return {
        "suppliers": suppliers,
        "explicit_skip_keywords": [str(x).lower() for x in skip_keywords if str(x).strip()],
    }


def _registry_evidence_lines(item):
    evidence = item.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list):
        return []
    return [str(x).strip() for x in evidence if str(x).strip()]


def _registry_item_has_explicit_evidence(item):
    return bool(_registry_evidence_lines(item))


def _normalize_account_hint(value):
    if value is None:
        return ""
    s = str(value).strip().upper()
    if not s:
        return ""
    s = re.sub(r"\s+", "", s)
    return s


def _normalize_waybill_ref(value):
    if value is None:
        return ""
    s = str(value).strip().upper()
    if not s:
        return ""
    return re.sub(r"[^A-Z0-9]", "", s)


def _extract_tax_ids_from_text(text):
    if not text:
        return []
    s = str(text)
    out = []
    for tid in re.findall(r"(?<!\d)(\d{9,11})(?!\d)", s):
        if tid not in out:
            out.append(tid)
    return out


def _extract_candidate_name_segments(text):
    raw = str(text or "")
    if not raw.strip():
        return []
    parts = []
    for token in re.split(r"[,\n\r\|;/]", raw):
        norm = normalize_name(token)
        if not norm or len(norm) < 3:
            continue
        if re.match(r"^[a-z]{4,}\d{2,}$", norm):
            continue
        if re.match(r"^ge\d{2}[a-z0-9]+$", norm):
            continue
        parts.append(norm)
    whole = normalize_name(raw)
    if whole and len(whole) >= 3:
        parts.append(whole)
    seen = set()
    return [p for p in parts if not (p in seen or seen.add(p))]


def _extract_waybill_refs_from_text(text, known_waybill_refs):
    """
    Extract potential waybill/invoice refs and keep only exact refs known in RS.
    """
    if not text:
        return []
    known = set(known_waybill_refs or [])
    if not known:
        return []
    blob = str(text).upper()
    tokens = re.findall(r"[A-Z0-9][A-Z0-9\\-_/]{3,30}", blob)
    refs = []
    for tok in tokens:
        norm = _normalize_waybill_ref(tok)
        if not norm:
            continue
        if norm in known and norm not in refs:
            refs.append(norm)
    return refs


def build_supplier_master(rs_files, supplier_registry=None):
    """
    Builds strict supplier master + matching indexes.

    Truth boundary:
    - primary strict truth: supplier_matching_registry.json
    - backstop/base supplier list: RS waybills
    - legacy assist only: PARTNER_IBAN_TO_RS_TAX_ID / LEGACY_KNOWN_ALIASES
    """
    registry = supplier_registry or load_supplier_matching_registry()
    suppliers_by_id = {}

    def _ensure_supplier(tax_id):
        if not tax_id:
            return None
        tid = str(tax_id).strip()
        if not tid or not tid.isdigit():
            return None
        if tid not in suppliers_by_id:
            suppliers_by_id[tid] = {
                "tax_id": tid,
                "official_name_raw": "",
                "official_names": set(),
                "aliases": set(),
                "person_aliases": set(),
                "ibans": set(),
                "account_hints": set(),
                "force_non_supplier_keywords": set(),
                "registry_official_names": set(),
                "rs_official_names": set(),
                "registry_aliases": set(),
                "registry_person_aliases": set(),
                "registry_ibans": set(),
                "registry_account_hints": set(),
                "legacy_truth_assist_ibans": set(),
                "official_name_truth_source": "",
                "notes": [],
                "source": set(),
            }
        return suppliers_by_id[tid]

    for f in sorted(rs_files):
        try:
            df = pd.read_excel(f)
        except Exception:
            continue
        if "ორგანიზაცია" not in df.columns:
            continue
        for org in df["ორგანიზაცია"].dropna().unique():
            org_str = str(org).strip()
            if not org_str:
                continue
            tax_id = _extract_tax_id_from_org(org_str)
            if not tax_id:
                continue
            supplier = _ensure_supplier(tax_id)
            if not supplier:
                continue
            supplier["source"].add("rs")
            name_part = re.sub(r"\([^)]*\)\s*", "", org_str).strip()
            norm_name = normalize_name(name_part)
            if norm_name:
                supplier["official_names"].add(norm_name)
                supplier["rs_official_names"].add(norm_name)
            if name_part:
                if not supplier["official_name_raw"]:
                    supplier["official_name_raw"] = name_part
                if not supplier["official_name_truth_source"]:
                    supplier["official_name_truth_source"] = (
                        "rs_waybills.organization_name"
                    )

    for item in registry.get("suppliers") or []:
        if not isinstance(item, dict):
            continue
        supplier = _ensure_supplier(item.get("tax_id"))
        if not supplier:
            continue
        supplier["source"].add("registry")
        official_name = str(item.get("official_name") or "").strip()
        if official_name:
            supplier["official_name_raw"] = official_name
            supplier["official_name_truth_source"] = (
                "supplier_matching_registry.official_name"
            )
            norm_legal = normalize_name(official_name)
            if norm_legal:
                supplier["official_names"].add(norm_legal)
                supplier["registry_official_names"].add(norm_legal)
        evidence_lines = _registry_evidence_lines(item)
        has_explicit_evidence = _registry_item_has_explicit_evidence(item)
        for ev in evidence_lines:
            supplier["notes"].append(f"evidence: {ev}")
        if has_explicit_evidence:
            for alias in item.get("aliases") or []:
                norm_alias = normalize_name(alias)
                if norm_alias:
                    supplier["aliases"].add(norm_alias)
                    supplier["registry_aliases"].add(norm_alias)
            for alias in item.get("person_aliases") or []:
                norm_alias = normalize_name(alias)
                if norm_alias:
                    supplier["person_aliases"].add(norm_alias)
                    supplier["registry_person_aliases"].add(norm_alias)
            for iban in item.get("ibans") or []:
                ib = _normalize_iban_ge(iban)
                if ib:
                    supplier["ibans"].add(ib)
                    supplier["registry_ibans"].add(ib)
            for hint in item.get("account_hints") or []:
                h = _normalize_account_hint(hint)
                if h:
                    supplier["account_hints"].add(h)
                    supplier["registry_account_hints"].add(h)
                    ib_h = _normalize_iban_ge(h)
                    if ib_h:
                        supplier["ibans"].add(ib_h)
                        supplier["registry_ibans"].add(ib_h)
            for kw in item.get("force_non_supplier_keywords") or []:
                kw_s = str(kw).strip().lower()
                if kw_s:
                    supplier["force_non_supplier_keywords"].add(kw_s)
        elif any(
            item.get(field)
            for field in (
                "aliases",
                "person_aliases",
                "ibans",
                "account_hints",
                "force_non_supplier_keywords",
            )
        ):
            supplier["notes"].append(
                "registry match aids ignored: missing explicit evidence"
            )
        note = str(item.get("notes") or "").strip()
        if note:
            supplier["notes"].append(note)

    for iban, tax_id in PARTNER_IBAN_TO_RS_TAX_ID.items():
        supplier = _ensure_supplier(tax_id)
        if not supplier:
            continue
        supplier["source"].add("legacy_truth_assist")
        ib = _normalize_iban_ge(iban)
        if ib:
            supplier["legacy_truth_assist_ibans"].add(ib)
            supplier["notes"].append(
                "legacy truth-assist IBAN available for audit-only comparison"
            )

    legal_name_to_tax_ids = defaultdict(set)
    registry_legal_name_to_tax_ids = defaultdict(set)
    rs_legal_name_to_tax_ids = defaultdict(set)
    alias_to_tax_ids = defaultdict(set)
    person_alias_to_tax_ids = defaultdict(set)
    iban_to_tax_ids = defaultdict(set)
    account_hint_to_tax_ids = defaultdict(set)
    token_to_tax_ids = defaultdict(set)

    for tid, supplier in suppliers_by_id.items():
        names_for_tokens = set()
        for legal_name in supplier["official_names"]:
            legal_name_to_tax_ids[legal_name].add(tid)
            names_for_tokens.add(legal_name)
        for legal_name in supplier["registry_official_names"]:
            registry_legal_name_to_tax_ids[legal_name].add(tid)
        for legal_name in supplier["rs_official_names"]:
            rs_legal_name_to_tax_ids[legal_name].add(tid)
        for alias in supplier["aliases"]:
            alias_to_tax_ids[alias].add(tid)
            names_for_tokens.add(alias)
        for p_alias in supplier["person_aliases"]:
            person_alias_to_tax_ids[p_alias].add(tid)
            names_for_tokens.add(p_alias)
        for iban in supplier["ibans"]:
            iban_to_tax_ids[iban].add(tid)
        for hint in supplier["account_hints"]:
            account_hint_to_tax_ids[hint].add(tid)
        for nm in names_for_tokens:
            for token in nm.split():
                tok = token.strip()
                if len(tok) >= 4:
                    token_to_tax_ids[tok].add(tid)

    legal_name_to_id = {
        name: next(iter(ids))
        for name, ids in legal_name_to_tax_ids.items()
        if len(ids) == 1
    }
    registry_legal_name_to_id = {
        name: next(iter(ids))
        for name, ids in registry_legal_name_to_tax_ids.items()
        if len(ids) == 1
    }
    rs_legal_name_to_id = {
        name: next(iter(ids))
        for name, ids in rs_legal_name_to_tax_ids.items()
        if len(ids) == 1
    }
    alias_to_id = {
        name: next(iter(ids))
        for name, ids in alias_to_tax_ids.items()
        if len(ids) == 1
    }
    person_alias_to_id = {
        name: next(iter(ids))
        for name, ids in person_alias_to_tax_ids.items()
        if len(ids) == 1
    }
    iban_to_id = {
        iban: next(iter(ids))
        for iban, ids in iban_to_tax_ids.items()
        if len(ids) == 1
    }
    account_hint_to_id = {
        hint: next(iter(ids))
        for hint, ids in account_hint_to_tax_ids.items()
        if len(ids) == 1
    }
    return {
        "suppliers_by_id": suppliers_by_id,
        "legal_name_to_id": legal_name_to_id,
        "registry_legal_name_to_id": registry_legal_name_to_id,
        "rs_legal_name_to_id": rs_legal_name_to_id,
        "alias_to_id": alias_to_id,
        "person_alias_to_id": person_alias_to_id,
        "iban_to_id": iban_to_id,
        "account_hint_to_id": account_hint_to_id,
        "token_to_tax_ids": token_to_tax_ids,
        "explicit_skip_keywords": set(registry.get("explicit_skip_keywords") or []),
    }


def _build_waybill_reference_index(rs_files):
    known_refs = set()
    ref_to_supplier_ids = defaultdict(set)
    for f in sorted(rs_files):
        try:
            df = pd.read_excel(f)
        except Exception:
            continue
        if "ორგანიზაცია" not in df.columns or "ზედნადები" not in df.columns:
            continue
        for _, row in df.iterrows():
            tid = _extract_tax_id_from_org(row.get("ორგანიზაცია"))
            if not tid:
                continue
            ref = _normalize_waybill_ref(row.get("ზედნადები"))
            if not ref:
                continue
            known_refs.add(ref)
            ref_to_supplier_ids[ref].add(tid)
    return {
        "known_refs": known_refs,
        "ref_to_supplier_ids": ref_to_supplier_ids,
    }


def empty_retail_sales_bundle():
    return {
        "label_ka": "გაყიდული პროდუქცია (retail sales source)",
        "notes_ka": (
            "Retail sales source (დვაბზუ + ოზურგეთი). გამოიყენება sell-through / "
            "revenue / cost / profit / margin ანალიზისთვის და მკაფიოდ გამოყოფილია "
            "supplier debt/AP/bank reconciliation truth boundary-სგან."
        ),
        "source_glob": [
            "Financial_Analysis/გაყიდული პროდუქტები სოფ დვაბზუ/*.xlsx",
            "Financial_Analysis/გაყიდული პროდუქტები სოფ ოზურგეთი/*.xlsx",
        ],
        "source_column_schema_expected": [
            "P_ID",
            "კოდი",
            "შტრიხკოდი",
            "დასახელება",
            "ერთეული",
            "რაოდენობა",
            "ფასი",
            "თვითღირებულება",
            "დრო",
            "ობიექტი",
            "მოგება",
            "ქვეჯგუფი",
            "ცვლა",
        ],
        "amount_basis_ka": "`ფასი` = revenue, `თვითღირებულება` = cost, `მოგება` = profit.",
        "duplicate_policy": {
            "mode": RETAIL_SALES_DUPLICATE_POLICY_MODE,
            "notes_ka": (
                "Duplicate-suspected source default-ად totals-იდან გამორიცხულია, "
                "სანამ explicit inclusion/exclusion policy არ დადგება."
            ),
            "suspected_files": [],
            "excluded_files": [],
            "excluded_file_count": 0,
        },
        "files_found_count": 0,
        "files_read_count": 0,
        "files_error_count": 0,
        "files_skipped_by_policy_count": 0,
        "files_skipped_by_policy": [],
        "files": [],
        "read_errors": [],
        "overall": {
            "row_count": 0,
            "total_quantity": 0.0,
            "revenue_ge": 0.0,
            "cost_ge": 0.0,
            "profit_ge": 0.0,
            "gross_margin_pct": 0.0,
            "distinct_object_count": 0,
            "distinct_category_count": 0,
            "distinct_product_count": 0,
            "date_range": {"min": None, "max": None},
        },
        "by_object": [],
        "category_total_count": 0,
        "categories_truncated": False,
        "by_category": [],
        "products_total_count": 0,
        "products_truncated": False,
        "by_product": [],
        "by_month": [],
        "top_objects_by_profit": [],
        "top_categories_by_profit": [],
        "top_products_by_revenue": [],
        "top_products_by_profit": [],
        "rows_preview": [],
    }


def collect_retail_sales_bundle(object_mapping=None):
    files = list_retail_sales_files()
    bundle = empty_retail_sales_bundle()
    bundle["files_found_count"] = len(files)
    if not files:
        return bundle

    sales_object_mapping = object_mapping or _clone_default_object_mapping()

    duplicate_suspected_map = {
        f"Financial_Analysis/{str(path).replace('\\', '/').strip('/')}": dict(cfg or {})
        for path, cfg in RETAIL_SALES_DUPLICATE_SUSPECTED_FILES.items()
    }
    suspected_records = {
        path: {
            "relative_path": path,
            "suspected_duplicate_of": (
                f"Financial_Analysis/{str(cfg.get('suspected_duplicate_of') or '').replace('\\', '/').strip('/')}"
                if str(cfg.get("suspected_duplicate_of") or "").strip()
                else ""
            ),
            "reason_ka": str(cfg.get("reason_ka") or ""),
            "present_in_sources": False,
            "included_in_totals": False,
        }
        for path, cfg in duplicate_suspected_map.items()
    }

    def _coerce_float(value):
        if isinstance(value, str):
            value = value.replace(" ", "").replace(",", ".")
        num = pd.to_numeric(value, errors="coerce")
        if pd.isna(num):
            return 0.0
        return float(num)

    def _clean_text(value, fallback=""):
        text = _safe_text(value).strip()
        return text if text else fallback

    def _fmt_date(dt):
        if dt is None or pd.isna(dt):
            return None
        return pd.Timestamp(dt).strftime("%Y-%m-%d")

    def _margin_pct(revenue, profit):
        revenue_val = float(revenue or 0)
        if revenue_val == 0:
            return 0.0
        return float((float(profit or 0) / revenue_val) * 100.0)

    def _object_from_path(path):
        parent = _normalize_for_match(os.path.basename(os.path.dirname(path)))
        if "ოზურგეთი" in parent:
            return OBJECT_OZURGETI
        if "დვაბზუ" in parent:
            return OBJECT_DVABZU
        return OBJECT_UNALLOCATED

    def _pick_object(row_value, fallback_object):
        detected = detect_object(
            "rs_waybill",
            rs_location=row_value,
            object_mapping=sales_object_mapping,
        )
        detected = str(detected or "").strip()
        if detected and detected not in {OBJECT_UNALLOCATED, OBJECT_COMMON}:
            return detected
        if fallback_object and fallback_object != OBJECT_UNALLOCATED:
            return fallback_object
        return detected or fallback_object or OBJECT_UNALLOCATED

    def _update_date_range(entry, dt):
        if dt is None or pd.isna(dt):
            return
        if entry.get("min_date") is None or pd.isna(entry.get("min_date")) or dt < entry["min_date"]:
            entry["min_date"] = dt
        if entry.get("max_date") is None or pd.isna(entry.get("max_date")) or dt > entry["max_date"]:
            entry["max_date"] = dt

    required_summary_cols = [
        "კოდი",
        "დასახელება",
        "რაოდენობა",
        "ფასი",
        "თვითღირებულება",
        "მოგება",
        "დრო",
        "ობიექტი",
        "ქვეჯგუფი",
    ]

    all_dates = []
    month_stats = defaultdict(
        lambda: {
            "row_count": 0,
            "total_quantity": 0.0,
            "revenue_ge": 0.0,
            "cost_ge": 0.0,
            "profit_ge": 0.0,
        }
    )
    object_stats = {}
    category_stats = {}
    product_stats = {}
    preview_candidates = []
    read_error_count = 0

    for f in files:
        file_rel = _to_financial_relative_path(f)
        if file_rel in duplicate_suspected_map:
            suspected_records[file_rel]["present_in_sources"] = True
            bundle["files_skipped_by_policy"].append(file_rel)
            continue

        file_name = os.path.basename(f)
        fallback_object = _object_from_path(f)
        try:
            df = pd.read_excel(f)
        except Exception as exc:
            read_error_count += 1
            if len(bundle["read_errors"]) < RETAIL_SALES_READ_ERROR_LIMIT:
                bundle["read_errors"].append(
                    {
                        "name": file_name,
                        "relative_path": file_rel,
                        "error": str(exc),
                    }
                )
            continue

        if not isinstance(df, pd.DataFrame):
            continue
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        unnamed_cols = [c for c in df.columns if str(c).strip().startswith("Unnamed:")]
        if unnamed_cols:
            df = df.drop(columns=unnamed_cols, errors="ignore")

        row_count = int(len(df.index))
        missing_columns = [c for c in required_summary_cols if c not in df.columns]
        file_dates = []
        file_revenue = 0.0
        file_cost = 0.0
        file_profit = 0.0
        file_quantity = 0.0
        file_objects = set()
        file_categories = set()
        file_products = set()
        file_profit_fallback_rows = 0

        for _, row in df.iterrows():
            quantity = _coerce_float(row.get("რაოდენობა"))
            revenue_ge = _coerce_float(row.get("ფასი"))
            cost_ge = _coerce_float(row.get("თვითღირებულება"))
            raw_profit = pd.to_numeric(
                _safe_text(row.get("მოგება")).replace(",", "."),
                errors="coerce",
            )
            if pd.isna(raw_profit):
                profit_ge = revenue_ge - cost_ge
                file_profit_fallback_rows += 1
            else:
                profit_ge = float(raw_profit)

            date_value = _parse_rs_datetime(row.get("დრო"))
            month_key = (
                pd.Timestamp(date_value).strftime("%Y-%m")
                if not pd.isna(date_value)
                else "უცნობი თვე"
            )
            object_label = _pick_object(row.get("ობიექტი"), fallback_object)
            category = _clean_text(row.get("ქვეჯგუფი"), "უცნობი კატეგორია")
            category_key = normalize_name(category) or category.lower()
            product_code = _clean_text(row.get("კოდი"))
            barcode = _clean_text(row.get("შტრიხკოდი"))
            product_name = _clean_text(
                row.get("დასახელება"),
                product_code or barcode or "უცნობი პროდუქტი",
            )
            product_name_key = normalize_name(product_name) or product_name.lower()
            unit = _clean_text(row.get("ერთეული"))
            product_key = f"{product_code}||{barcode}||{product_name_key}"

            file_revenue += revenue_ge
            file_cost += cost_ge
            file_profit += profit_ge
            file_quantity += quantity
            file_objects.add(object_label)
            file_categories.add(category_key)
            file_products.add(product_key)

            month_stats[month_key]["row_count"] += 1
            month_stats[month_key]["total_quantity"] += quantity
            month_stats[month_key]["revenue_ge"] += revenue_ge
            month_stats[month_key]["cost_ge"] += cost_ge
            month_stats[month_key]["profit_ge"] += profit_ge

            object_entry = object_stats.setdefault(
                object_label,
                {
                    "object": object_label,
                    "row_count": 0,
                    "total_quantity": 0.0,
                    "revenue_ge": 0.0,
                    "cost_ge": 0.0,
                    "profit_ge": 0.0,
                    "category_keys": set(),
                    "product_keys": set(),
                    "month_keys": set(),
                    "min_date": None,
                    "max_date": None,
                },
            )
            object_entry["row_count"] += 1
            object_entry["total_quantity"] += quantity
            object_entry["revenue_ge"] += revenue_ge
            object_entry["cost_ge"] += cost_ge
            object_entry["profit_ge"] += profit_ge
            object_entry["category_keys"].add(category_key)
            object_entry["product_keys"].add(product_key)
            if month_key != "უცნობი თვე":
                object_entry["month_keys"].add(month_key)
            _update_date_range(object_entry, date_value)

            category_entry = category_stats.setdefault(
                category_key,
                {
                    "category": category,
                    "normalized_category": category_key,
                    "row_count": 0,
                    "total_quantity": 0.0,
                    "revenue_ge": 0.0,
                    "cost_ge": 0.0,
                    "profit_ge": 0.0,
                    "object_totals": {},
                    "product_keys": set(),
                    "month_keys": set(),
                    "min_date": None,
                    "max_date": None,
                },
            )
            if category and category_entry["category"] == "უცნობი კატეგორია":
                category_entry["category"] = category
            category_entry["row_count"] += 1
            category_entry["total_quantity"] += quantity
            category_entry["revenue_ge"] += revenue_ge
            category_entry["cost_ge"] += cost_ge
            category_entry["profit_ge"] += profit_ge
            category_entry["product_keys"].add(product_key)
            if month_key != "უცნობი თვე":
                category_entry["month_keys"].add(month_key)
            _update_date_range(category_entry, date_value)
            category_object_totals = category_entry["object_totals"].setdefault(
                object_label,
                {
                    "object": object_label,
                    "row_count": 0,
                    "total_quantity": 0.0,
                    "revenue_ge": 0.0,
                    "cost_ge": 0.0,
                    "profit_ge": 0.0,
                },
            )
            category_object_totals["row_count"] += 1
            category_object_totals["total_quantity"] += quantity
            category_object_totals["revenue_ge"] += revenue_ge
            category_object_totals["cost_ge"] += cost_ge
            category_object_totals["profit_ge"] += profit_ge

            product_entry = product_stats.setdefault(
                product_key,
                {
                    "product_code": product_code,
                    "barcode": barcode,
                    "product_name": product_name,
                    "unit": unit,
                    "category": category,
                    "category_key": category_key,
                    "row_count": 0,
                    "total_quantity": 0.0,
                    "revenue_ge": 0.0,
                    "cost_ge": 0.0,
                    "profit_ge": 0.0,
                    "object_totals": {},
                    "month_keys": set(),
                    "min_date": None,
                    "max_date": None,
                },
            )
            if product_name and product_entry["product_name"] == "უცნობი პროდუქტი":
                product_entry["product_name"] = product_name
            if unit and not product_entry["unit"]:
                product_entry["unit"] = unit
            if product_code and not product_entry["product_code"]:
                product_entry["product_code"] = product_code
            if barcode and not product_entry["barcode"]:
                product_entry["barcode"] = barcode
            if category and product_entry["category"] == "უცნობი კატეგორია":
                product_entry["category"] = category
            product_entry["row_count"] += 1
            product_entry["total_quantity"] += quantity
            product_entry["revenue_ge"] += revenue_ge
            product_entry["cost_ge"] += cost_ge
            product_entry["profit_ge"] += profit_ge
            if month_key != "უცნობი თვე":
                product_entry["month_keys"].add(month_key)
            _update_date_range(product_entry, date_value)
            product_object_totals = product_entry["object_totals"].setdefault(
                object_label,
                {
                    "object": object_label,
                    "row_count": 0,
                    "total_quantity": 0.0,
                    "revenue_ge": 0.0,
                    "cost_ge": 0.0,
                    "profit_ge": 0.0,
                },
            )
            product_object_totals["row_count"] += 1
            product_object_totals["total_quantity"] += quantity
            product_object_totals["revenue_ge"] += revenue_ge
            product_object_totals["cost_ge"] += cost_ge
            product_object_totals["profit_ge"] += profit_ge

            if not pd.isna(date_value):
                file_dates.append(date_value)
                all_dates.append(date_value)

            preview_candidates.append(
                {
                    "_sort_date": pd.Timestamp(date_value).timestamp()
                    if not pd.isna(date_value)
                    else float("-inf"),
                    "_sort_revenue": revenue_ge,
                    "date": _fmt_date(date_value),
                    "file_name": file_name,
                    "object": object_label,
                    "category": category,
                    "product_name": product_name,
                    "product_code": product_code,
                    "barcode": barcode,
                    "quantity": quantity,
                    "unit": unit,
                    "revenue_ge": revenue_ge,
                    "cost_ge": cost_ge,
                    "profit_ge": profit_ge,
                }
            )

        bundle["files"].append(
            {
                "name": file_name,
                "relative_path": file_rel,
                "row_count": row_count,
                "total_quantity": float(file_quantity),
                "revenue_ge": float(file_revenue),
                "cost_ge": float(file_cost),
                "profit_ge": float(file_profit),
                "gross_margin_pct": float(_margin_pct(file_revenue, file_profit)),
                "profit_fallback_rows": int(file_profit_fallback_rows),
                "distinct_object_count": len(file_objects),
                "distinct_category_count": len(file_categories),
                "distinct_product_count": len(file_products),
                "object_from_folder": (
                    fallback_object if fallback_object != OBJECT_UNALLOCATED else None
                ),
                "date_range": {
                    "min": _fmt_date(min(file_dates)) if file_dates else None,
                    "max": _fmt_date(max(file_dates)) if file_dates else None,
                },
                "missing_columns": missing_columns,
            }
        )

    bundle["files_read_count"] = len(bundle["files"])
    bundle["files_error_count"] = int(read_error_count)
    bundle["files_skipped_by_policy_count"] = len(bundle["files_skipped_by_policy"])

    for rel_path, record in suspected_records.items():
        if rel_path in bundle["files_skipped_by_policy"]:
            record["present_in_sources"] = True
    bundle["duplicate_policy"]["suspected_files"] = [
        suspected_records[key] for key in sorted(suspected_records)
    ]
    bundle["duplicate_policy"]["excluded_files"] = sorted(bundle["files_skipped_by_policy"])
    bundle["duplicate_policy"]["excluded_file_count"] = int(
        len(bundle["files_skipped_by_policy"])
    )

    overall_revenue = float(sum(item.get("revenue_ge") or 0 for item in bundle["files"]))
    overall_cost = float(sum(item.get("cost_ge") or 0 for item in bundle["files"]))
    overall_profit = float(sum(item.get("profit_ge") or 0 for item in bundle["files"]))
    overall_quantity = float(
        sum(item.get("total_quantity") or 0 for item in bundle["files"])
    )
    bundle["overall"] = {
        "row_count": int(sum(item.get("row_count") or 0 for item in bundle["files"])),
        "total_quantity": overall_quantity,
        "revenue_ge": overall_revenue,
        "cost_ge": overall_cost,
        "profit_ge": overall_profit,
        "gross_margin_pct": float(_margin_pct(overall_revenue, overall_profit)),
        "distinct_object_count": len(object_stats),
        "distinct_category_count": len(category_stats),
        "distinct_product_count": len(product_stats),
        "date_range": {
            "min": _fmt_date(min(all_dates)) if all_dates else None,
            "max": _fmt_date(max(all_dates)) if all_dates else None,
        },
    }

    bundle["by_month"] = [
        {
            "month": month,
            "row_count": int(stats.get("row_count") or 0),
            "total_quantity": float(stats.get("total_quantity") or 0),
            "revenue_ge": float(stats.get("revenue_ge") or 0),
            "cost_ge": float(stats.get("cost_ge") or 0),
            "profit_ge": float(stats.get("profit_ge") or 0),
            "gross_margin_pct": float(
                _margin_pct(stats.get("revenue_ge") or 0, stats.get("profit_ge") or 0)
            ),
        }
        for month, stats in sorted(month_stats.items(), key=lambda item: _month_sort_key(item[0]))
    ]

    object_rows = []
    for item in object_stats.values():
        object_rows.append(
            {
                "object": item.get("object") or OBJECT_UNALLOCATED,
                "row_count": int(item.get("row_count") or 0),
                "total_quantity": float(item.get("total_quantity") or 0),
                "revenue_ge": float(item.get("revenue_ge") or 0),
                "cost_ge": float(item.get("cost_ge") or 0),
                "profit_ge": float(item.get("profit_ge") or 0),
                "gross_margin_pct": float(
                    _margin_pct(item.get("revenue_ge") or 0, item.get("profit_ge") or 0)
                ),
                "distinct_category_count": len(item.get("category_keys") or set()),
                "distinct_product_count": len(item.get("product_keys") or set()),
                "distinct_month_count": len(item.get("month_keys") or set()),
                "date_range": {
                    "min": _fmt_date(item.get("min_date")),
                    "max": _fmt_date(item.get("max_date")),
                },
            }
        )
    bundle["by_object"] = sorted(
        object_rows,
        key=lambda value: (
            -float(value.get("revenue_ge") or 0),
            -float(value.get("profit_ge") or 0),
            str(value.get("object") or ""),
        ),
    )

    category_rows = []
    for item in category_stats.values():
        object_breakdown = [
            {
                "object": obj.get("object"),
                "row_count": int(obj.get("row_count") or 0),
                "total_quantity": float(obj.get("total_quantity") or 0),
                "revenue_ge": float(obj.get("revenue_ge") or 0),
                "cost_ge": float(obj.get("cost_ge") or 0),
                "profit_ge": float(obj.get("profit_ge") or 0),
                "gross_margin_pct": float(
                    _margin_pct(obj.get("revenue_ge") or 0, obj.get("profit_ge") or 0)
                ),
            }
            for obj in sorted(
                (item.get("object_totals") or {}).values(),
                key=lambda value: (
                    -float(value.get("revenue_ge") or 0),
                    -float(value.get("profit_ge") or 0),
                    str(value.get("object") or ""),
                ),
            )
        ]
        category_rows.append(
            {
                "category": item.get("category") or "უცნობი კატეგორია",
                "normalized_category": item.get("normalized_category") or None,
                "row_count": int(item.get("row_count") or 0),
                "total_quantity": float(item.get("total_quantity") or 0),
                "revenue_ge": float(item.get("revenue_ge") or 0),
                "cost_ge": float(item.get("cost_ge") or 0),
                "profit_ge": float(item.get("profit_ge") or 0),
                "gross_margin_pct": float(
                    _margin_pct(item.get("revenue_ge") or 0, item.get("profit_ge") or 0)
                ),
                "distinct_product_count": len(item.get("product_keys") or set()),
                "distinct_month_count": len(item.get("month_keys") or set()),
                "date_range": {
                    "min": _fmt_date(item.get("min_date")),
                    "max": _fmt_date(item.get("max_date")),
                },
                "object_breakdown": object_breakdown,
            }
        )
    category_rows = sorted(
        category_rows,
        key=lambda value: (
            -float(value.get("revenue_ge") or 0),
            -float(value.get("profit_ge") or 0),
            str(value.get("category") or ""),
        ),
    )
    bundle["category_total_count"] = len(category_rows)
    bundle["categories_truncated"] = len(category_rows) > RETAIL_SALES_CATEGORY_LIMIT
    bundle["by_category"] = category_rows[:RETAIL_SALES_CATEGORY_LIMIT]

    product_rows = []
    for item in product_stats.values():
        object_breakdown = [
            {
                "object": obj.get("object"),
                "row_count": int(obj.get("row_count") or 0),
                "total_quantity": float(obj.get("total_quantity") or 0),
                "revenue_ge": float(obj.get("revenue_ge") or 0),
                "cost_ge": float(obj.get("cost_ge") or 0),
                "profit_ge": float(obj.get("profit_ge") or 0),
                "gross_margin_pct": float(
                    _margin_pct(obj.get("revenue_ge") or 0, obj.get("profit_ge") or 0)
                ),
            }
            for obj in sorted(
                (item.get("object_totals") or {}).values(),
                key=lambda value: (
                    -float(value.get("revenue_ge") or 0),
                    -float(value.get("profit_ge") or 0),
                    str(value.get("object") or ""),
                ),
            )
        ]
        product_rows.append(
            {
                "product_code": item.get("product_code") or "",
                "barcode": item.get("barcode") or "",
                "product_name": item.get("product_name") or "უცნობი პროდუქტი",
                "unit": item.get("unit") or "",
                "category": item.get("category") or "უცნობი კატეგორია",
                "row_count": int(item.get("row_count") or 0),
                "total_quantity": float(item.get("total_quantity") or 0),
                "revenue_ge": float(item.get("revenue_ge") or 0),
                "cost_ge": float(item.get("cost_ge") or 0),
                "profit_ge": float(item.get("profit_ge") or 0),
                "gross_margin_pct": float(
                    _margin_pct(item.get("revenue_ge") or 0, item.get("profit_ge") or 0)
                ),
                "distinct_object_count": len(item.get("object_totals") or {}),
                "distinct_month_count": len(item.get("month_keys") or set()),
                "date_range": {
                    "min": _fmt_date(item.get("min_date")),
                    "max": _fmt_date(item.get("max_date")),
                },
                "object_breakdown": object_breakdown,
            }
        )
    product_rows = sorted(
        product_rows,
        key=lambda value: (
            -float(value.get("revenue_ge") or 0),
            -float(value.get("profit_ge") or 0),
            str(value.get("product_name") or ""),
            str(value.get("product_code") or ""),
        ),
    )
    bundle["products_total_count"] = len(product_rows)
    bundle["products_truncated"] = len(product_rows) > RETAIL_SALES_PRODUCT_LIMIT
    bundle["by_product"] = product_rows[:RETAIL_SALES_PRODUCT_LIMIT]

    bundle["top_objects_by_profit"] = sorted(
        bundle["by_object"],
        key=lambda value: (
            -float(value.get("profit_ge") or 0),
            -float(value.get("revenue_ge") or 0),
            str(value.get("object") or ""),
        ),
    )[:RETAIL_SALES_TOP_LIMIT]
    bundle["top_categories_by_profit"] = sorted(
        category_rows,
        key=lambda value: (
            -float(value.get("profit_ge") or 0),
            -float(value.get("revenue_ge") or 0),
            str(value.get("category") or ""),
        ),
    )[:RETAIL_SALES_TOP_LIMIT]
    bundle["top_products_by_revenue"] = product_rows[:RETAIL_SALES_TOP_LIMIT]
    bundle["top_products_by_profit"] = sorted(
        product_rows,
        key=lambda value: (
            -float(value.get("profit_ge") or 0),
            -float(value.get("revenue_ge") or 0),
            str(value.get("product_name") or ""),
            str(value.get("product_code") or ""),
        ),
    )[:RETAIL_SALES_TOP_LIMIT]

    preview_candidates.sort(
        key=lambda item: (
            float(item.get("_sort_date") or float("-inf")),
            float(item.get("_sort_revenue") or 0),
            str(item.get("product_name") or ""),
        ),
        reverse=True,
    )
    bundle["rows_preview"] = [
        {
            k: v
            for k, v in item.items()
            if not str(k).startswith("_sort_")
        }
        for item in preview_candidates[:RETAIL_SALES_ROWS_PREVIEW_LIMIT]
    ]
    return bundle


def empty_imported_products_bundle():
    return {
        "label_ka": "შემოტანილი პროდუქცია (reference)",
        "notes_ka": (
            "Reference/product-line წყარო imported-products export-იდან. CSV არის preferred source, "
            "legacy Excel reader fallback-ად რჩება. ეს ბლოკი არ ერთვება supplier debt-ში, "
            "RS truth totals-ში, bank reconciliation-ში და არსებულ AP ლოგიკაში. "
            "ფაილი, რომელსაც ზუსტად Excel-ის მაქსიმალური რიგების რაოდენობა (1,048,576) აქვს, "
            "შესაძლოა truncate/export limit იყოს — სრულობა გარანტირებული არ არის."
        ),
        "source_glob": "Financial_Analysis/შემოტანილი პროდუქცია/*.csv (preferred), legacy fallback: *.xls / *.xlsx",
        "source_format": None,
        "sheet_name": None,
        "date_basis_ka": (
            "თვე/პერიოდი ითვლება ჯერ `გააქტიურების თარიღი`-ით, "
            "fallback — `ტრანსპორტირების დაწყების თარიღი`."
        ),
        "amount_basis_ka": "`საქონლის ფასი` — თანხა, `რაოდ.` — რაოდენობა.",
        "files_found_count": 0,
        "files_read_count": 0,
        "files_error_count": 0,
        "files": [],
        "read_errors": [],
        "overall": {
            "row_count": 0,
            "total_quantity": 0.0,
            "total_amount_ge": 0.0,
            "distinct_waybill_count": 0,
            "distinct_supplier_count": 0,
            "distinct_product_count": 0,
            "date_range": {"min": None, "max": None},
        },
        "truncation_threshold_rows": IMPORTED_PRODUCTS_TRUNCATION_ROW_COUNT,
        "truncation_suspected_any": False,
        "truncation_suspected_file_count": 0,
        "truncation_suspected_files": [],
        "by_status": [],
        "by_month": [],
        "supplier_top_products_limit": IMPORTED_PRODUCTS_SUPPLIER_TOP_PRODUCTS_LIMIT,
        "product_top_suppliers_limit": IMPORTED_PRODUCTS_PRODUCT_TOP_SUPPLIERS_LIMIT,
        "products_limit": IMPORTED_PRODUCTS_PRODUCTS_LIMIT,
        "top_supplier_product_pairs_limit": IMPORTED_PRODUCTS_TOP_SUPPLIER_PRODUCT_PAIRS_LIMIT,
        "products_total_count": 0,
        "products_truncated": False,
        "top_supplier_product_pairs_total_count": 0,
        "top_supplier_product_pairs_truncated": False,
        "product_concentration_metric": "top_supplier_share_pct",
        "product_concentration_metric_ka": (
            "top_supplier_share_pct = ამ პროდუქტზე ყველაზე დიდი supplier-ის თანხა / "
            "ამ პროდუქტის ჯამური თანხა * 100"
        ),
        "suppliers": [],
        "products": [],
        "top_suppliers_by_amount": [],
        "top_products_by_amount": [],
        "top_supplier_product_pairs": [],
        "rows_preview": [],
        "rs_waybill_crosscheck": {
            "enabled": False,
            "matched_waybill_count": 0,
            "unmatched_waybill_count": 0,
            "match_rate_pct": 0.0,
            "matched_waybill_preview": [],
            "unmatched_waybill_preview": [],
        },
    }


def collect_imported_products_bundle(rs_files=None):
    files = list_imported_product_files()
    bundle = empty_imported_products_bundle()
    bundle["files_found_count"] = len(files)
    if not files:
        return bundle
    file_exts = {os.path.splitext(path)[1].lower() for path in files}
    if file_exts == {".csv"}:
        bundle["source_format"] = "csv"
        bundle["source_glob"] = "Financial_Analysis/შემოტანილი პროდუქცია/*.csv"
        bundle["sheet_name"] = None
    else:
        bundle["source_format"] = "excel"
        bundle["source_glob"] = "Financial_Analysis/შემოტანილი პროდუქცია/*.xls / *.xlsx"
        bundle["sheet_name"] = IMPORTED_PRODUCTS_SHEET_NAME

    required_summary_cols = [
        "საქონლის კოდი",
        "საქონლის დასახელება",
        "რაოდ.",
        "საქონლის ფასი",
        "ზედნადების ნომერი",
        "სტატუსი",
        "გამყიდველი",
        "გააქტიურების თარიღი",
        "ტრანსპორტირების დაწყების თარიღი",
    ]

    def _coerce_float(value):
        num = pd.to_numeric(value, errors="coerce")
        if pd.isna(num):
            return 0.0
        return float(num)

    def _clean_text(value, fallback=""):
        text = _safe_text(value).strip()
        return text if text else fallback

    def _pick_date(row):
        dt = _parse_rs_datetime(row.get("გააქტიურების თარიღი"))
        if pd.isna(dt):
            dt = _parse_rs_datetime(row.get("ტრანსპორტირების დაწყების თარიღი"))
        return dt

    def _fmt_date(dt):
        if dt is None or pd.isna(dt):
            return None
        return pd.Timestamp(dt).strftime("%Y-%m-%d")

    def _clean_supplier_display(value):
        text = _safe_text(value).strip()
        if not text:
            return ""
        cleaned = text
        for tid in _extract_tax_ids_from_text(text):
            cleaned = re.sub(r"\(?\s*" + re.escape(tid) + r"\s*\)?", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–,")
        return cleaned or text

    def _normalize_supplier_key(value):
        cleaned = _clean_supplier_display(value)
        normalized = normalize_name(cleaned)
        if normalized:
            return normalized
        raw = _safe_text(value).strip()
        return normalize_name(raw) or raw.lower()

    def _update_entry_date_range(entry, dt):
        if dt is None or pd.isna(dt):
            return
        if entry.get("min_date") is None or pd.isna(entry.get("min_date")) or dt < entry["min_date"]:
            entry["min_date"] = dt
        if entry.get("max_date") is None or pd.isna(entry.get("max_date")) or dt > entry["max_date"]:
            entry["max_date"] = dt

    def _merge_supplier_entries(target, source):
        target["row_count"] += int(source.get("row_count") or 0)
        target["total_ge"] += float(source.get("total_ge") or 0)
        target["quantity"] += float(source.get("quantity") or 0)
        target["waybill_refs"].update(source.get("waybill_refs") or set())
        target["month_keys"].update(source.get("month_keys") or set())
        target["tax_ids"].update(source.get("tax_ids") or set())
        target["display_names"].update(source.get("display_names") or Counter())
        _update_entry_date_range(target, source.get("min_date"))
        _update_entry_date_range(target, source.get("max_date"))
        for product_key, product_item in (source.get("products") or {}).items():
            target_product = target["products"].setdefault(
                product_key,
                {
                    "product_code": product_item.get("product_code") or "",
                    "product_name": product_item.get("product_name") or "უცნობი პროდუქცია",
                    "unit": product_item.get("unit") or "",
                    "row_count": 0,
                    "total_ge": 0.0,
                    "quantity": 0.0,
                    "waybill_refs": set(),
                    "month_keys": set(),
                    "min_date": None,
                    "max_date": None,
                },
            )
            if product_item.get("unit") and not target_product["unit"]:
                target_product["unit"] = product_item["unit"]
            if (
                product_item.get("product_name")
                and target_product["product_name"] == "უცნობი პროდუქცია"
            ):
                target_product["product_name"] = product_item["product_name"]
            target_product["row_count"] += int(product_item.get("row_count") or 0)
            target_product["total_ge"] += float(product_item.get("total_ge") or 0)
            target_product["quantity"] += float(product_item.get("quantity") or 0)
            target_product["waybill_refs"].update(product_item.get("waybill_refs") or set())
            target_product["month_keys"].update(product_item.get("month_keys") or set())
            _update_entry_date_range(target_product, product_item.get("min_date"))
            _update_entry_date_range(target_product, product_item.get("max_date"))

    def _pick_supplier_display(entry):
        display_names = entry.get("display_names") or Counter()
        if display_names:
            return sorted(
                display_names.items(),
                key=lambda item: (
                    -int(item[1]),
                    item[0] == "უცნობი მომწოდებელი",
                    -len(str(item[0])),
                    str(item[0]),
                ),
            )[0][0]
        fallback = _safe_text(entry.get("supplier")).strip()
        return fallback or "უცნობი მომწოდებელი"

    known_rs_refs = set()
    if rs_files:
        known_rs_refs = set(
            (_build_waybill_reference_index(rs_files) or {}).get("known_refs") or set()
        )
    bundle["rs_waybill_crosscheck"]["enabled"] = bool(known_rs_refs)

    all_dates = []
    imported_waybill_refs = set()
    preview_candidates = []
    read_error_count = 0
    status_stats = defaultdict(lambda: {"row_count": 0, "total_ge": 0.0, "quantity": 0.0})
    month_stats = defaultdict(lambda: {"row_count": 0, "total_ge": 0.0, "quantity": 0.0})
    supplier_stats = {}
    product_stats = {}

    for f in files:
        file_name = os.path.basename(f)
        file_ext = os.path.splitext(file_name)[1].lower()
        try:
            df, source_format, sheet_name = _read_imported_products_file(f)
        except Exception as e:
            read_error_count += 1
            if len(bundle["read_errors"]) < IMPORTED_PRODUCTS_READ_ERROR_LIMIT:
                bundle["read_errors"].append(
                    {
                        "name": file_name,
                        "source_format": file_ext.lstrip(".") or "unknown",
                        "sheet_name": IMPORTED_PRODUCTS_SHEET_NAME
                        if file_ext in {".xls", ".xlsx"}
                        else None,
                        "error": str(e),
                    }
                )
            continue

        row_count = int(len(df.index))
        truncation_suspected = row_count == IMPORTED_PRODUCTS_TRUNCATION_ROW_COUNT
        total_amount_ge = 0.0
        total_quantity = 0.0
        file_dates = []
        file_waybill_refs = set()
        file_suppliers = set()
        file_products = set()
        missing_columns = [c for c in required_summary_cols if c not in df.columns]

        for _, row in df.iterrows():
            amount_ge = _coerce_float(row.get("საქონლის ფასი"))
            quantity = _coerce_float(row.get("რაოდ."))
            status = _clean_text(row.get("სტატუსი"), "უცნობი სტატუსი")
            supplier_name = _clean_text(row.get("გამყიდველი"), "უცნობი მომწოდებელი")
            supplier_display = _clean_supplier_display(supplier_name) or supplier_name
            supplier_tax_ids = _extract_tax_ids_from_text(supplier_name)
            supplier_tax_id = supplier_tax_ids[0] if len(supplier_tax_ids) == 1 else ""
            product_code = _clean_text(row.get("საქონლის კოდი"))
            product_name = _clean_text(
                row.get("საქონლის დასახელება"),
                product_code or "უცნობი პროდუქცია",
            )
            unit = _clean_text(row.get("ზომის ერთეული"))
            waybill_number = _clean_text(row.get("ზედნადების ნომერი"))
            waybill_ref = _normalize_waybill_ref(waybill_number)
            dt = _pick_date(row)
            month_key = dt.strftime("%Y-%m") if not pd.isna(dt) else "უცნობი თვე"
            normalized_supplier = _normalize_supplier_key(supplier_name)
            supplier_key = (
                f"tax_id:{supplier_tax_id}"
                if supplier_tax_id
                else f"name:{normalized_supplier or supplier_name.lower()}"
            )
            product_name_key = normalize_name(product_name) or product_name.lower()
            product_key = f"{product_code}||{product_name_key}"

            total_amount_ge += amount_ge
            total_quantity += quantity
            status_stats[status]["row_count"] += 1
            status_stats[status]["total_ge"] += amount_ge
            status_stats[status]["quantity"] += quantity
            month_stats[month_key]["row_count"] += 1
            month_stats[month_key]["total_ge"] += amount_ge
            month_stats[month_key]["quantity"] += quantity

            supplier_entry = supplier_stats.setdefault(
                supplier_key,
                {
                    "supplier": supplier_display,
                    "normalized_supplier": normalized_supplier,
                    "tax_id": supplier_tax_id,
                    "tax_ids": set([supplier_tax_id]) if supplier_tax_id else set(),
                    "row_count": 0,
                    "total_ge": 0.0,
                    "quantity": 0.0,
                    "waybill_refs": set(),
                    "month_keys": set(),
                    "min_date": None,
                    "max_date": None,
                    "display_names": Counter(),
                    "products": {},
                },
            )
            if supplier_display and supplier_entry["supplier"] == "უცნობი მომწოდებელი":
                supplier_entry["supplier"] = supplier_display
            if normalized_supplier and not supplier_entry.get("normalized_supplier"):
                supplier_entry["normalized_supplier"] = normalized_supplier
            if supplier_tax_id and not supplier_entry.get("tax_id"):
                supplier_entry["tax_id"] = supplier_tax_id
            supplier_entry["row_count"] += 1
            supplier_entry["total_ge"] += amount_ge
            supplier_entry["quantity"] += quantity
            if supplier_display:
                supplier_entry["display_names"][supplier_display] += 1
            if supplier_tax_id:
                supplier_entry["tax_ids"].add(supplier_tax_id)
            if month_key != "უცნობი თვე":
                supplier_entry["month_keys"].add(month_key)
            _update_entry_date_range(supplier_entry, dt)

            product_entry = product_stats.setdefault(
                product_key,
                {
                    "product_code": product_code,
                    "product_name": product_name,
                    "unit": unit,
                    "row_count": 0,
                    "total_ge": 0.0,
                    "quantity": 0.0,
                    "waybill_refs": set(),
                },
            )
            if unit and not product_entry["unit"]:
                product_entry["unit"] = unit
            if product_name and product_entry["product_name"] == "უცნობი პროდუქცია":
                product_entry["product_name"] = product_name
            product_entry["row_count"] += 1
            product_entry["total_ge"] += amount_ge
            product_entry["quantity"] += quantity

            supplier_product_entry = supplier_entry["products"].setdefault(
                product_key,
                {
                    "product_code": product_code,
                    "product_name": product_name,
                    "unit": unit,
                    "row_count": 0,
                    "total_ge": 0.0,
                    "quantity": 0.0,
                    "waybill_refs": set(),
                    "month_keys": set(),
                    "min_date": None,
                    "max_date": None,
                },
            )
            if unit and not supplier_product_entry["unit"]:
                supplier_product_entry["unit"] = unit
            if (
                product_name
                and supplier_product_entry["product_name"] == "უცნობი პროდუქცია"
            ):
                supplier_product_entry["product_name"] = product_name
            supplier_product_entry["row_count"] += 1
            supplier_product_entry["total_ge"] += amount_ge
            supplier_product_entry["quantity"] += quantity
            if month_key != "უცნობი თვე":
                supplier_product_entry["month_keys"].add(month_key)
            _update_entry_date_range(supplier_product_entry, dt)

            if waybill_ref:
                imported_waybill_refs.add(waybill_ref)
                file_waybill_refs.add(waybill_ref)
                supplier_entry["waybill_refs"].add(waybill_ref)
                product_entry["waybill_refs"].add(waybill_ref)
                supplier_product_entry["waybill_refs"].add(waybill_ref)
            if supplier_name and supplier_name != "უცნობი მომწოდებელი":
                file_suppliers.add(supplier_key)
            if product_code or product_name:
                file_products.add(product_key)
            if not pd.isna(dt):
                file_dates.append(dt)
                all_dates.append(dt)

            preview_candidates.append(
                {
                    "_sort_date": pd.Timestamp(dt).timestamp() if not pd.isna(dt) else float("-inf"),
                    "_sort_amount": amount_ge,
                    "file_name": file_name,
                    "activation_date": _fmt_date(
                        _parse_rs_datetime(row.get("გააქტიურების თარიღი"))
                    ),
                    "transport_start_date": _fmt_date(
                        _parse_rs_datetime(row.get("ტრანსპორტირების დაწყების თარიღი"))
                    ),
                    "waybill_number": waybill_number,
                    "status": status,
                    "buyer": _clean_text(row.get("მყიდველი")),
                    "supplier": supplier_name,
                    "product_code": product_code,
                    "product_name": product_name,
                    "unit": unit,
                    "quantity": quantity,
                    "amount_ge": amount_ge,
                }
            )

        file_summary = {
            "name": file_name,
            "source_format": source_format,
            "sheet_name": sheet_name,
            "row_count": row_count,
            "truncation_suspected": truncation_suspected,
            "date_range": {
                "min": _fmt_date(min(file_dates)) if file_dates else None,
                "max": _fmt_date(max(file_dates)) if file_dates else None,
            },
            "total_amount_ge": float(total_amount_ge),
            "total_quantity": float(total_quantity),
            "distinct_waybill_count": len(file_waybill_refs),
            "distinct_supplier_count": len(file_suppliers),
            "distinct_product_count": len(file_products),
            "missing_columns": missing_columns,
        }
        if known_rs_refs:
            matched_refs = file_waybill_refs & known_rs_refs
            unmatched_refs = file_waybill_refs - known_rs_refs
            file_summary["rs_waybill_crosscheck"] = {
                "matched_waybill_count": len(matched_refs),
                "unmatched_waybill_count": len(unmatched_refs),
            }
        bundle["files"].append(file_summary)

    bundle["files_read_count"] = len(bundle["files"])
    bundle["files_error_count"] = int(read_error_count)
    bundle["truncation_suspected_files"] = [
        item["name"] for item in bundle["files"] if item.get("truncation_suspected")
    ]
    bundle["truncation_suspected_file_count"] = len(bundle["truncation_suspected_files"])
    bundle["truncation_suspected_any"] = bundle["truncation_suspected_file_count"] > 0
    supplier_keys_by_normalized_tax_id = defaultdict(set)
    for supplier_key, item in supplier_stats.items():
        if item.get("tax_id") and item.get("normalized_supplier"):
            supplier_keys_by_normalized_tax_id[item["normalized_supplier"]].add(supplier_key)

    merged_supplier_keys = set()
    for supplier_key, item in list(supplier_stats.items()):
        if supplier_key in merged_supplier_keys:
            continue
        if item.get("tax_id"):
            continue
        normalized_supplier = item.get("normalized_supplier") or ""
        if not normalized_supplier:
            continue
        candidate_keys = supplier_keys_by_normalized_tax_id.get(normalized_supplier) or set()
        if len(candidate_keys) != 1:
            continue
        target_key = next(iter(candidate_keys))
        if target_key == supplier_key:
            continue
        _merge_supplier_entries(supplier_stats[target_key], item)
        merged_supplier_keys.add(supplier_key)

    supplier_entries_with_keys = [
        (key, item) for key, item in supplier_stats.items() if key not in merged_supplier_keys
    ]
    supplier_entries = [item for _, item in supplier_entries_with_keys]
    bundle["overall"] = {
        "row_count": int(sum(item.get("row_count") or 0 for item in bundle["files"])),
        "total_quantity": float(sum(item.get("total_quantity") or 0 for item in bundle["files"])),
        "total_amount_ge": float(sum(item.get("total_amount_ge") or 0 for item in bundle["files"])),
        "distinct_waybill_count": len(imported_waybill_refs),
        "distinct_supplier_count": len(supplier_entries),
        "distinct_product_count": len(product_stats),
        "date_range": {
            "min": _fmt_date(min(all_dates)) if all_dates else None,
            "max": _fmt_date(max(all_dates)) if all_dates else None,
        },
    }

    bundle["by_status"] = [
        {
            "status": status,
            "row_count": int(stats["row_count"]),
            "total_ge": float(stats["total_ge"]),
            "quantity": float(stats["quantity"]),
        }
        for status, stats in sorted(
            status_stats.items(),
            key=lambda item: (-float(item[1]["total_ge"]), item[0]),
        )
    ]
    bundle["by_month"] = [
        {
            "month": month,
            "row_count": int(stats["row_count"]),
            "total_ge": float(stats["total_ge"]),
            "quantity": float(stats["quantity"]),
        }
        for month, stats in sorted(month_stats.items(), key=lambda item: _month_sort_key(item[0]))
    ]
    bundle["suppliers"] = [
        {
            "supplier": _pick_supplier_display(item),
            "tax_id": item.get("tax_id") or None,
            "tax_id_source": "supplier_text" if item.get("tax_id") else None,
            "normalized_supplier": item.get("normalized_supplier") or None,
            "row_count": int(item["row_count"]),
            "distinct_waybill_count": len(item["waybill_refs"]),
            "distinct_product_count": len(item["products"]),
            "distinct_month_count": len(item["month_keys"]),
            "total_quantity": float(item["quantity"]),
            "total_amount_ge": float(item["total_ge"]),
            "date_range": {
                "min": _fmt_date(item.get("min_date")),
                "max": _fmt_date(item.get("max_date")),
            },
            "top_products": [
                {
                    "product_code": product_item["product_code"],
                    "product_name": product_item["product_name"],
                    "unit": product_item["unit"],
                    "row_count": int(product_item["row_count"]),
                    "distinct_waybill_count": len(product_item["waybill_refs"]),
                    "total_quantity": float(product_item["quantity"]),
                    "total_amount_ge": float(product_item["total_ge"]),
                }
                for product_item in sorted(
                    item["products"].values(),
                    key=lambda value: (
                        -float(value["total_ge"]),
                        -int(value["row_count"]),
                        str(value["product_name"]),
                        str(value["product_code"]),
                    ),
                )[:IMPORTED_PRODUCTS_SUPPLIER_TOP_PRODUCTS_LIMIT]
            ],
        }
        for item in sorted(
            supplier_entries,
            key=lambda value: (
                -float(value["total_ge"]),
                -int(value["row_count"]),
                _pick_supplier_display(value),
            ),
        )
    ]
    product_rollup = {}
    supplier_product_pairs = []
    for supplier_key, supplier_item in supplier_entries_with_keys:
        supplier_display = _pick_supplier_display(supplier_item)
        supplier_tax_id = supplier_item.get("tax_id") or None
        for product_key, product_item in (supplier_item.get("products") or {}).items():
            product_rollup_entry = product_rollup.setdefault(
                product_key,
                {
                    "product_code": product_item.get("product_code") or "",
                    "product_name": product_item.get("product_name") or "უცნობი პროდუქცია",
                    "unit": product_item.get("unit") or "",
                    "row_count": 0,
                    "total_ge": 0.0,
                    "quantity": 0.0,
                    "waybill_refs": set(),
                    "month_keys": set(),
                    "min_date": None,
                    "max_date": None,
                    "suppliers": {},
                },
            )
            if product_item.get("unit") and not product_rollup_entry["unit"]:
                product_rollup_entry["unit"] = product_item["unit"]
            if (
                product_item.get("product_name")
                and product_rollup_entry["product_name"] == "უცნობი პროდუქცია"
            ):
                product_rollup_entry["product_name"] = product_item["product_name"]
            product_rollup_entry["row_count"] += int(product_item.get("row_count") or 0)
            product_rollup_entry["total_ge"] += float(product_item.get("total_ge") or 0)
            product_rollup_entry["quantity"] += float(product_item.get("quantity") or 0)
            product_rollup_entry["waybill_refs"].update(product_item.get("waybill_refs") or set())
            product_rollup_entry["month_keys"].update(product_item.get("month_keys") or set())
            _update_entry_date_range(product_rollup_entry, product_item.get("min_date"))
            _update_entry_date_range(product_rollup_entry, product_item.get("max_date"))

            product_rollup_entry["suppliers"][supplier_key] = {
                "supplier": supplier_display,
                "tax_id": supplier_tax_id,
                "row_count": int(product_item.get("row_count") or 0),
                "distinct_waybill_count": len(product_item.get("waybill_refs") or set()),
                "total_quantity": float(product_item.get("quantity") or 0),
                "total_amount_ge": float(product_item.get("total_ge") or 0),
            }
            supplier_product_pairs.append(
                {
                    "supplier": supplier_display,
                    "tax_id": supplier_tax_id,
                    "product_code": product_item.get("product_code") or "",
                    "product_name": product_item.get("product_name") or "უცნობი პროდუქცია",
                    "unit": product_item.get("unit") or "",
                    "row_count": int(product_item.get("row_count") or 0),
                    "distinct_waybill_count": len(product_item.get("waybill_refs") or set()),
                    "distinct_month_count": len(product_item.get("month_keys") or set()),
                    "total_quantity": float(product_item.get("quantity") or 0),
                    "total_amount_ge": float(product_item.get("total_ge") or 0),
                    "date_range": {
                        "min": _fmt_date(product_item.get("min_date")),
                        "max": _fmt_date(product_item.get("max_date")),
                    },
                }
            )

    sorted_product_rollup = sorted(
        product_rollup.values(),
        key=lambda value: (
            -float(value["total_ge"]),
            -int(value["row_count"]),
            str(value["product_name"]),
            str(value["product_code"]),
        ),
    )
    bundle["products_total_count"] = len(sorted_product_rollup)
    bundle["products_truncated"] = len(sorted_product_rollup) > IMPORTED_PRODUCTS_PRODUCTS_LIMIT
    bundle["products"] = []
    for product_item in sorted_product_rollup[:IMPORTED_PRODUCTS_PRODUCTS_LIMIT]:
        sorted_top_suppliers = sorted(
            product_item["suppliers"].values(),
            key=lambda value: (
                -float(value["total_amount_ge"]),
                -int(value["row_count"]),
                str(value["supplier"]),
            ),
        )
        top_supplier_amount = (
            float(sorted_top_suppliers[0]["total_amount_ge"])
            if sorted_top_suppliers
            else 0.0
        )
        product_total_amount = float(product_item.get("total_ge") or 0)
        top_supplier_share_pct = (
            float((top_supplier_amount / product_total_amount) * 100.0)
            if product_total_amount
            else 0.0
        )
        bundle["products"].append(
            {
                "product_code": product_item.get("product_code") or "",
                "product_name": product_item.get("product_name") or "უცნობი პროდუქცია",
                "unit": product_item.get("unit") or "",
                "row_count": int(product_item.get("row_count") or 0),
                "distinct_supplier_count": len(product_item.get("suppliers") or {}),
                "distinct_waybill_count": len(product_item.get("waybill_refs") or set()),
                "distinct_month_count": len(product_item.get("month_keys") or set()),
                "total_quantity": float(product_item.get("quantity") or 0),
                "total_amount_ge": float(product_total_amount),
                "top_supplier_share_pct": float(top_supplier_share_pct),
                "date_range": {
                    "min": _fmt_date(product_item.get("min_date")),
                    "max": _fmt_date(product_item.get("max_date")),
                },
                "top_suppliers": sorted_top_suppliers[
                    :IMPORTED_PRODUCTS_PRODUCT_TOP_SUPPLIERS_LIMIT
                ],
            }
        )

    sorted_supplier_product_pairs = sorted(
        supplier_product_pairs,
        key=lambda value: (
            -float(value["total_amount_ge"]),
            -int(value["row_count"]),
            str(value["supplier"]),
            str(value["product_name"]),
            str(value["product_code"]),
        ),
    )
    bundle["top_supplier_product_pairs_total_count"] = len(sorted_supplier_product_pairs)
    bundle["top_supplier_product_pairs_truncated"] = (
        len(sorted_supplier_product_pairs)
        > IMPORTED_PRODUCTS_TOP_SUPPLIER_PRODUCT_PAIRS_LIMIT
    )
    bundle["top_supplier_product_pairs"] = sorted_supplier_product_pairs[
        :IMPORTED_PRODUCTS_TOP_SUPPLIER_PRODUCT_PAIRS_LIMIT
    ]
    bundle["top_suppliers_by_amount"] = [
        {
            "supplier": _pick_supplier_display(item),
            "row_count": int(item["row_count"]),
            "total_ge": float(item["total_ge"]),
            "quantity": float(item["quantity"]),
            "distinct_waybill_count": len(item["waybill_refs"]),
        }
        for item in sorted(
            supplier_entries,
            key=lambda value: (
                -float(value["total_ge"]),
                -int(value["row_count"]),
                _pick_supplier_display(value),
            ),
        )[:IMPORTED_PRODUCTS_TOP_LIMIT]
    ]
    bundle["top_products_by_amount"] = [
        {
            "product_code": item["product_code"],
            "product_name": item["product_name"],
            "unit": item["unit"],
            "row_count": int(item["row_count"]),
            "total_ge": float(item["total_ge"]),
            "quantity": float(item["quantity"]),
            "distinct_waybill_count": len(item["waybill_refs"]),
        }
        for item in sorted(
            product_stats.values(),
            key=lambda value: (
                -float(value["total_ge"]),
                -int(value["row_count"]),
                str(value["product_name"]),
                str(value["product_code"]),
            ),
        )[:IMPORTED_PRODUCTS_TOP_LIMIT]
    ]

    preview_candidates.sort(
        key=lambda item: (
            float(item["_sort_date"]),
            float(item["_sort_amount"]),
            str(item["product_name"]),
        ),
        reverse=True,
    )
    bundle["rows_preview"] = [
        {k: v for k, v in item.items() if not k.startswith("_sort_")}
        for item in preview_candidates[:IMPORTED_PRODUCTS_ROWS_PREVIEW_LIMIT]
    ]

    matched_refs = imported_waybill_refs & known_rs_refs
    unmatched_refs = imported_waybill_refs - known_rs_refs
    total_refs = len(imported_waybill_refs)
    match_rate_pct = float((len(matched_refs) / total_refs) * 100.0) if total_refs else 0.0
    bundle["rs_waybill_crosscheck"] = {
        "enabled": bool(known_rs_refs),
        "matched_waybill_count": len(matched_refs),
        "unmatched_waybill_count": len(unmatched_refs),
        "match_rate_pct": float(match_rate_pct),
        "matched_waybill_preview": sorted(matched_refs)[:20],
        "unmatched_waybill_preview": sorted(unmatched_refs)[:20],
    }
    return bundle


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
    """
    Strict legal-name mapping only (no substring/fuzzy).
    """
    master = build_supplier_master(rs_files)
    return dict(master.get("legal_name_to_id") or {})


def match_partner_to_id(partner_name, name_to_id, alias_to_id=None):
    """
    Strict matching only:
    - exact normalized legal-name
    - exact alias from explicit alias dictionary
    """
    alias_map = alias_to_id or {}
    for candidate in _extract_candidate_name_segments(partner_name):
        if candidate in name_to_id:
            return name_to_id[candidate]
        if candidate in alias_map:
            return alias_map[candidate]
    return None


# Legacy truth-assist only:
# Known aliases below remain audit-only helper mappings for legacy delta/provenance
# comparison. ისინი strict supplier auto-match primary truth არ არის.
LEGACY_KNOWN_ALIASES = {
    "ინტერნეიშენალ მარკეტინგ ენდ თრეიდინგი": "420424393",
    "ინტერნეიშენალ მარკეტინგ": "420424393",
    "შრომა": "437078485",
    "თოლია": "412731281",
    "სალი": "237113333",
    "ელიტფუდი 2": "412761097",
    "sah&co": "404995680",
    "sahco": "404995680",
    "ჯეომარკი": "205239053",
    "ბესიკ კურტანიძე": "01025003711",
    "კურტანიძე ბესიკ": "01025003711",
    "თენიეშვილი ზვიად": "33001015189",
    "ზვიად თენიეშვილი": "33001015189",
    "ხუჭუა კახაბერ": "33001023234",
}


TRUTH_SOURCE_LABEL_TO_LAYERS = {
    "bank_tax_id": ["bank.raw_tax_id", "bank.extracted_tax_id"],
    "registry_legal_name": ["supplier_matching_registry.official_name"],
    "registry_alias": ["supplier_matching_registry.alias"],
    "registry_person_alias": ["supplier_matching_registry.person_alias"],
    "registry_iban": ["supplier_matching_registry.iban"],
    "registry_account_hint": ["supplier_matching_registry.account_hint"],
    "rs_legal_name_backstop": ["rs_waybills.organization_name"],
    "waybill_reference": ["rs_waybills.waybill_reference"],
}


def _legacy_truth_assist_aliases_for_tax_id(tax_id):
    tid = str(tax_id or "").strip()
    if not tid:
        return []
    aliases = []
    seen = set()
    for alias, alias_tid in LEGACY_KNOWN_ALIASES.items():
        if str(alias_tid or "").strip() != tid:
            continue
        alias_text = str(alias or "").strip()
        if not alias_text or alias_text in seen:
            continue
        seen.add(alias_text)
        aliases.append(alias_text)
    return aliases


def _layers_for_truth_source_label(truth_source_label):
    return list(TRUTH_SOURCE_LABEL_TO_LAYERS.get(str(truth_source_label or "").strip(), []))


def _supplier_truth_layers_for_tax_id(tax_id, supplier_master):
    tid = str(tax_id or "").strip()
    supplier = (supplier_master.get("suppliers_by_id") or {}).get(tid) or {}
    layers = []
    if supplier.get("registry_official_names"):
        layers.append("supplier_matching_registry.official_name")
    if supplier.get("registry_aliases"):
        layers.append("supplier_matching_registry.alias")
    if supplier.get("registry_person_aliases"):
        layers.append("supplier_matching_registry.person_alias")
    if supplier.get("registry_ibans"):
        layers.append("supplier_matching_registry.iban")
    if supplier.get("registry_account_hints"):
        layers.append("supplier_matching_registry.account_hint")
    if supplier.get("rs_official_names"):
        layers.append("rs_waybills.organization_name")
    if supplier.get("legacy_truth_assist_ibans"):
        layers.append("legacy_truth_assist.partner_iban_map")
    if _legacy_truth_assist_aliases_for_tax_id(tid):
        layers.append("legacy_truth_assist.known_aliases")
    return list(dict.fromkeys(layers))


def _supplier_truth_summary_for_tax_id(tax_id, supplier_master):
    tid = str(tax_id or "").strip()
    supplier = (supplier_master.get("suppliers_by_id") or {}).get(tid) or {}
    if not supplier and not _legacy_truth_assist_aliases_for_tax_id(tid):
        return ""

    parts = []
    official_name_truth_source = str(supplier.get("official_name_truth_source") or "").strip()
    if official_name_truth_source == "supplier_matching_registry.official_name":
        parts.append("official name: registry primary")
    elif official_name_truth_source == "rs_waybills.organization_name":
        parts.append("official name: RS backstop")
    elif official_name_truth_source:
        parts.append(f"official name: {official_name_truth_source}")

    if supplier.get("registry_aliases"):
        parts.append(
            f"registry aliases: {len(supplier.get('registry_aliases') or [])}"
        )
    if supplier.get("registry_person_aliases"):
        parts.append(
            "registry person aliases: "
            f"{len(supplier.get('registry_person_aliases') or [])}"
        )
    if supplier.get("registry_ibans"):
        parts.append(f"registry IBANs: {len(supplier.get('registry_ibans') or [])}")
    if supplier.get("registry_account_hints"):
        parts.append(
            "registry account hints: "
            f"{len(supplier.get('registry_account_hints') or [])}"
        )
    if (
        supplier.get("rs_official_names")
        and official_name_truth_source != "rs_waybills.organization_name"
    ):
        parts.append("RS exact-name backstop available")

    audit_only_parts = []
    if _legacy_truth_assist_aliases_for_tax_id(tid):
        audit_only_parts.append("legacy alias assist")
    if supplier.get("legacy_truth_assist_ibans"):
        audit_only_parts.append("legacy IBAN assist")
    if audit_only_parts:
        parts.append("audit-only: " + ", ".join(audit_only_parts))

    return "; ".join(parts)


def _supplier_truth_context(tax_id, supplier_master, truth_source_label=""):
    tid = str(tax_id or "").strip()
    supplier = (supplier_master.get("suppliers_by_id") or {}).get(tid) or {}
    truth_sources = list(_layers_for_truth_source_label(truth_source_label))
    truth_sources.extend(_supplier_truth_layers_for_tax_id(tid, supplier_master))
    return {
        "truth_source_label": str(truth_source_label or ""),
        "truth_sources": list(dict.fromkeys([src for src in truth_sources if src])),
        "supplier_truth_summary": _supplier_truth_summary_for_tax_id(
            tid, supplier_master
        ),
        "official_name_truth_source": str(
            supplier.get("official_name_truth_source") or ""
        ),
    }


def _build_truth_boundary_summary_for_supplier_master(supplier_master):
    suppliers_by_id = supplier_master.get("suppliers_by_id") or {}
    legacy_alias_tax_ids = {
        str(alias_tid or "").strip()
        for alias_tid in LEGACY_KNOWN_ALIASES.values()
        if str(alias_tid or "").strip()
    }
    legacy_iban_tax_ids = {
        str(tid)
        for tid, supplier in suppliers_by_id.items()
        if supplier.get("legacy_truth_assist_ibans")
    }
    return build_truth_boundary_summary(
        primary_supplier_truth_path=supplier_matching_registry_path(),
        registry_primary_count=sum(
            1
            for supplier in suppliers_by_id.values()
            if supplier.get("registry_official_names")
        ),
        rs_backstop_count=sum(
            1 for supplier in suppliers_by_id.values() if supplier.get("rs_official_names")
        ),
        legacy_assist_count=len(legacy_alias_tax_ids | legacy_iban_tax_ids),
    )


def _infer_truth_source_label_from_scored_candidate(candidate, supplier_master):
    candidate = candidate or {}
    tax_id = str(candidate.get("tax_id") or "").strip()
    supplier = (supplier_master.get("suppliers_by_id") or {}).get(tax_id) or {}
    reasons = [str(reason or "") for reason in (candidate.get("reasons") or [])]

    if any(reason.startswith("waybill_ref:") for reason in reasons):
        return "waybill_reference"
    if any(reason == "tax_id_in_text" for reason in reasons):
        return "bank_tax_id"
    if any(reason.startswith("alias:") for reason in reasons):
        return "registry_alias"
    if any(reason.startswith("person_alias:") for reason in reasons):
        return "registry_person_alias"
    for reason in reasons:
        if not reason.startswith("legal_name:"):
            continue
        legal_name = reason.split(":", 1)[1]
        if legal_name in (supplier.get("registry_official_names") or set()):
            return "registry_legal_name"
        if legal_name in (supplier.get("rs_official_names") or set()):
            return "rs_legal_name_backstop"
    return ""


def match_partner_to_id_legacy(partner_name, name_to_id):
    """
    Legacy optimistic matcher (for audit delta only).
    """
    raw_partner = str(partner_name or "")
    candidates = _extract_candidate_name_segments(raw_partner)
    if not candidates:
        return None
    for pname in candidates:
        if pname in LEGACY_KNOWN_ALIASES:
            return LEGACY_KNOWN_ALIASES[pname]
        for alias, alias_id in LEGACY_KNOWN_ALIASES.items():
            if alias in pname or pname in alias:
                return alias_id
        if pname in name_to_id:
            return name_to_id[pname]
        for rs_name, rs_id in name_to_id.items():
            if len(rs_name) >= 4 and rs_name in pname:
                return rs_id
        for rs_name, rs_id in name_to_id.items():
            if len(pname) >= 4 and pname in rs_name:
                return rs_id
        pname_compact = re.sub(r"[\s\-&\.\,\_]", "", pname)
        for rs_name, rs_id in name_to_id.items():
            rs_compact = re.sub(r"[\s\-&\.\,\_]", "", rs_name)
            if len(pname_compact) >= 4 and (
                pname_compact in rs_compact or rs_compact in pname_compact
            ):
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


def _supplier_display_name(tax_id, supplier_master, fallback_name=""):
    sup = (supplier_master.get("suppliers_by_id") or {}).get(str(tax_id))
    if not sup:
        return str(fallback_name or tax_id or "")
    if sup.get("official_name_raw"):
        return str(sup.get("official_name_raw"))
    names = sorted(list(sup.get("official_names") or []))
    if names:
        return str(names[0])
    return str(fallback_name or tax_id or "")


def _build_reconciliation_line(
    bank,
    file_name,
    row_date,
    amount,
    raw_tax_id="",
    receiver_name="",
    partner_name="",
    purpose_text="",
    description_text="",
    account_text="",
):
    raw_tax_id = str(raw_tax_id or "").strip()
    receiver_name = str(receiver_name or "").strip()
    partner_name = str(partner_name or "").strip()
    purpose_text = str(purpose_text or "").strip()
    description_text = str(description_text or "").strip()
    account_text = str(account_text or "").strip()
    blob_text = " | ".join(
        [
            receiver_name,
            partner_name,
            purpose_text,
            description_text,
            account_text,
            raw_tax_id,
        ]
    )
    blob_lower = blob_text.lower()
    extracted_tax_ids = []
    if raw_tax_id and raw_tax_id.isdigit():
        extracted_tax_ids.append(raw_tax_id)
    for tid in _extract_tax_ids_from_text(blob_text):
        if tid not in extracted_tax_ids:
            extracted_tax_ids.append(tid)
    extracted_ibans = []
    for source_text in (
        account_text,
        purpose_text,
        description_text,
        receiver_name,
        partner_name,
    ):
        for ib in _extract_ibans_from_text(source_text):
            ib2 = _normalize_iban_ge(ib) or ib
            if ib2 and ib2 not in extracted_ibans:
                extracted_ibans.append(ib2)
    return {
        "source_bank": str(bank),
        "file_name": str(file_name),
        "row_date": row_date,
        "amount": float(amount or 0),
        "raw_tax_id": raw_tax_id,
        "raw_receiver_name": receiver_name,
        "raw_partner_name": partner_name,
        "raw_purpose": purpose_text,
        "raw_description": description_text,
        "raw_account": account_text,
        "blob_text": blob_text,
        "blob_lower": blob_lower,
        "extracted_tax_ids": extracted_tax_ids,
        "extracted_ibans": extracted_ibans,
        "extracted_account_hints": [account_text] if account_text else [],
    }


def _line_to_row_for_category(line, reason=""):
    receiver = line.get("raw_receiver_name") or line.get("raw_partner_name") or ""
    return {
        "ბანკი": line.get("source_bank", ""),
        "ფაილი": line.get("file_name", ""),
        "თარიღი": line.get("row_date", ""),
        "თანხა": float(line.get("amount") or 0),
        "საგადასახადო_ID": line.get("raw_tax_id", ""),
        "მიმღები_სახელი": receiver,
        "ოპერაციის_შინაარსი": line.get("raw_description", ""),
        "დანიშნულება": line.get("raw_purpose", ""),
        "მიზეზი": reason,
    }


def _candidate_preview_list(scored_candidates, supplier_master):
    out = []
    for cand in scored_candidates[:5]:
        tid = str(cand.get("tax_id") or "")
        out.append(
            {
                "tax_id": tid,
                "supplier_name": _supplier_display_name(tid, supplier_master),
                "score": round(float(cand.get("score") or 0), 2),
                "reasons": cand.get("reasons") or [],
            }
        )
    return out


def _match_by_exact_tax_id(line, supplier_master):
    supplier_ids = set((supplier_master.get("suppliers_by_id") or {}).keys())
    candidates = [tid for tid in (line.get("extracted_tax_ids") or []) if tid in supplier_ids]
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) == 1:
        return candidates[0], "matched_exact_id", "explicit/extracted tax_id", "bank_tax_id"
    if len(candidates) > 1:
        return (
            None,
            "ambiguous",
            "multiple tax_id candidates in one line",
            "bank_tax_id",
        )
    return None, "", "", ""


def _match_by_exact_iban(line, supplier_master):
    iban_to_id = supplier_master.get("iban_to_id") or {}
    account_hint_to_id = supplier_master.get("account_hint_to_id") or {}
    hits_by_tax_id = defaultdict(list)
    for ib in line.get("extracted_ibans") or []:
        ib_norm = _normalize_iban_ge(ib) or str(ib or "").strip().upper()
        tid = iban_to_id.get(ib_norm)
        if tid:
            hits_by_tax_id[str(tid)].append(ib_norm)
    if len(hits_by_tax_id) == 1:
        tid, ibans = next(iter(hits_by_tax_id.items()))
        ibans = list(dict.fromkeys(ibans))
        if len(ibans) == 1:
            reason = f"exact IBAN {ibans[0]}"
        else:
            reason = f"exact IBAN variants {', '.join(ibans[:3])}"
        return tid, "matched_exact_iban", reason, "registry_iban"
    if len(hits_by_tax_id) > 1:
        return None, "ambiguous", "multiple supplier IBAN matches", "registry_iban"

    account_hits_by_tax_id = defaultdict(list)
    for raw_hint in line.get("extracted_account_hints") or []:
        hint = _normalize_account_hint(raw_hint)
        if not hint:
            continue
        tid = account_hint_to_id.get(hint)
        if tid:
            account_hits_by_tax_id[str(tid)].append(hint)
    if len(account_hits_by_tax_id) == 1:
        tid, hints = next(iter(account_hits_by_tax_id.items()))
        hints = list(dict.fromkeys(hints))
        sample = hints[0]
        if len(sample) > 48:
            sample = sample[:45] + "..."
        reason = (
            f"exact account hint {sample}"
            if len(hints) == 1
            else f"exact account hint variants {', '.join(hints[:3])}"
        )
        return tid, "matched_exact_iban", reason, "registry_account_hint"
    if len(account_hits_by_tax_id) > 1:
        return (
            None,
            "ambiguous",
            "multiple supplier account-hint matches",
            "registry_account_hint",
        )
    return None, "", "", ""


def _match_by_exact_names(line, supplier_master):
    registry_legal_map = supplier_master.get("registry_legal_name_to_id") or {}
    rs_legal_map = supplier_master.get("rs_legal_name_to_id") or {}
    alias_map = supplier_master.get("alias_to_id") or {}
    person_alias_map = supplier_master.get("person_alias_to_id") or {}

    def _unique_segments(*raw_values):
        segments = []
        for raw_text in raw_values:
            segments.extend(_extract_candidate_name_segments(raw_text))
        return list(dict.fromkeys(segments))

    def _resolve_segments(segments, source_label):
        registry_legal_hits = list(
            dict.fromkeys(
                [registry_legal_map[s] for s in segments if s in registry_legal_map]
            )
        )
        if len(registry_legal_hits) == 1:
            return (
                registry_legal_hits[0],
                "matched_exact_name",
                f"exact registry legal-name ({source_label})",
                "registry_legal_name",
            )
        if len(registry_legal_hits) > 1:
            return (
                None,
                "ambiguous",
                f"multiple registry legal-name hits in {source_label}",
                "registry_legal_name",
            )

        alias_hits = list(
            dict.fromkeys([alias_map[s] for s in segments if s in alias_map])
        )
        if not alias_hits:
            person_alias_hits = list(
                dict.fromkeys(
                    [person_alias_map[s] for s in segments if s in person_alias_map]
                )
            )
            if len(person_alias_hits) == 1:
                return (
                    person_alias_hits[0],
                    "matched_alias",
                    f"exact registry person alias ({source_label})",
                    "registry_person_alias",
                )
            if len(person_alias_hits) > 1:
                return (
                    None,
                    "ambiguous",
                    f"multiple registry person-alias hits in {source_label}",
                    "registry_person_alias",
                )
        if len(alias_hits) == 1:
            return (
                alias_hits[0],
                "matched_alias",
                f"exact registry alias ({source_label})",
                "registry_alias",
            )
        if len(alias_hits) > 1:
            return (
                None,
                "ambiguous",
                f"multiple registry alias hits in {source_label}",
                "registry_alias",
            )

        rs_legal_hits = list(
            dict.fromkeys([rs_legal_map[s] for s in segments if s in rs_legal_map])
        )
        if len(rs_legal_hits) == 1:
            return (
                rs_legal_hits[0],
                "matched_exact_name",
                f"exact RS legal-name backstop ({source_label})",
                "rs_legal_name_backstop",
            )
        if len(rs_legal_hits) > 1:
            return (
                None,
                "ambiguous",
                f"multiple RS legal-name backstop hits in {source_label}",
                "rs_legal_name_backstop",
            )
        return None, "", "", ""

    counterparty_segments = _unique_segments(
        line.get("raw_receiver_name"),
        line.get("raw_partner_name"),
    )
    tid, st, reason, truth_source_label = _resolve_segments(
        counterparty_segments, "counterparty fields"
    )
    if tid or st:
        return tid, st, reason, truth_source_label

    all_segments = _unique_segments(
        line.get("raw_receiver_name"),
        line.get("raw_partner_name"),
        line.get("raw_purpose"),
        line.get("raw_description"),
    )
    return _resolve_segments(all_segments, "full text")


def _score_supplier_candidates(line, supplier_master, waybill_index):
    suppliers_by_id = supplier_master.get("suppliers_by_id") or {}
    token_to_ids = supplier_master.get("token_to_tax_ids") or {}
    normalized_blob = " ".join(
        [
            normalize_name(line.get("raw_receiver_name") or ""),
            normalize_name(line.get("raw_partner_name") or ""),
            normalize_name(line.get("raw_purpose") or ""),
            normalize_name(line.get("raw_description") or ""),
        ]
    ).strip()
    blob_lower = normalized_blob.lower()

    candidate_ids = set()
    for tok in blob_lower.split():
        if len(tok) >= 4:
            candidate_ids.update(token_to_ids.get(tok, set()))

    waybill_hits = _extract_waybill_refs_from_text(
        line.get("blob_text") or "",
        (waybill_index or {}).get("known_refs") or set(),
    )
    line["waybill_reference_hits"] = waybill_hits
    waybill_supplier_ids = set()
    ref_to_supplier_ids = (waybill_index or {}).get("ref_to_supplier_ids") or {}
    for ref in waybill_hits:
        waybill_supplier_ids.update(ref_to_supplier_ids.get(ref, set()))
    candidate_ids.update(waybill_supplier_ids)

    scored = []
    for tid in sorted(candidate_ids):
        sup = suppliers_by_id.get(tid) or {}
        score = 0.0
        reasons = []
        for legal_name in sup.get("official_names") or []:
            if legal_name and legal_name in blob_lower:
                score += 36.0
                reasons.append(f"legal_name:{legal_name}")
        for alias in sup.get("aliases") or []:
            if alias and alias in blob_lower:
                score += 30.0
                reasons.append(f"alias:{alias}")
        for alias in sup.get("person_aliases") or []:
            if alias and alias in blob_lower:
                score += 22.0
                reasons.append(f"person_alias:{alias}")
        if tid in waybill_supplier_ids and waybill_hits:
            score += 35.0
            reasons.append(f"waybill_ref:{','.join(waybill_hits[:3])}")
        if tid in (line.get("extracted_tax_ids") or []):
            score += 45.0
            reasons.append("tax_id_in_text")
        for kw in sup.get("force_non_supplier_keywords") or []:
            if kw and kw in line.get("blob_lower", ""):
                score -= 55.0
                reasons.append(f"force_non_supplier_keyword:{kw}")
        if score > 0:
            scored.append({"tax_id": tid, "score": score, "reasons": reasons})
    scored.sort(key=lambda c: float(c.get("score") or 0), reverse=True)
    return scored


def _line_has_explicit_skip(line, supplier_master):
    blob_lower = line.get("blob_lower", "")
    for kw in supplier_master.get("explicit_skip_keywords") or set():
        if kw and kw in blob_lower:
            return True, f"explicit skip keyword: {kw}"
    return False, ""


def _line_force_non_supplier_for_supplier(line, tax_id, supplier_master):
    sup = (supplier_master.get("suppliers_by_id") or {}).get(str(tax_id)) or {}
    blob_lower = line.get("blob_lower", "")
    for kw in sup.get("force_non_supplier_keywords") or set():
        if kw and kw in blob_lower:
            return True, f"force_non_supplier keyword for supplier: {kw}"
    return False, ""


def _classify_non_supplier(line):
    rules = get_auto_unmatched_category_rules()
    rule_id = "rent_known_landlord_ibans"
    known_landlord_rule = next(
        (
            r
            for r in rules
            if str(r.get("id") or "").strip() == rule_id
        ),
        None,
    )
    rent_context_rule = next(
        (r for r in rules if str(r.get("id") or "").strip() == "rent_related"),
        None,
    )
    known_landlord_ibans = set()
    if known_landlord_rule:
        for raw_iban in known_landlord_rule.get("iban_hints") or []:
            iban = _normalize_iban_ge(raw_iban)
            if iban:
                known_landlord_ibans.add(iban)
    has_rent_context = bool(
        rent_context_rule
        and _rule_matches_unmatched(rent_context_rule, line.get("blob_lower", ""))
    )
    line_iban_signals = set()
    for raw_iban in line.get("extracted_ibans") or []:
        iban = _normalize_iban_ge(raw_iban)
        if iban:
            line_iban_signals.add(iban)
    for raw_hint in line.get("extracted_account_hints") or []:
        iban = _normalize_iban_ge(raw_hint)
        if iban:
            line_iban_signals.add(iban)
    raw_account_iban = _normalize_iban_ge(line.get("raw_account"))
    if raw_account_iban:
        line_iban_signals.add(raw_account_iban)

    if (
        known_landlord_ibans
        and known_landlord_ibans.intersection(line_iban_signals)
        and has_rent_context
    ):
        cid = rule_id
        label = str(known_landlord_rule.get("label_ka") or rule_id)
        conf = str(known_landlord_rule.get("confidence") or "high")
    else:
        row_for_cat = _line_to_row_for_category(line, reason="")
        cid, label, conf = _auto_category_from_unmatched_row(row_for_cat)
    conf_norm = str(conf or "low").lower().strip()
    if conf_norm not in {"high", "medium", "low"}:
        conf_norm = "low"
    is_known_non_supplier = cid in NON_SUPPLIER_CATEGORY_IDS and cid != "other_unclassified"
    return {
        "is_non_supplier": bool(
            is_known_non_supplier and conf_norm in NON_SUPPLIER_FINAL_CONFIDENCE
        ),
        "is_hint_only": bool(
            is_known_non_supplier and conf_norm not in NON_SUPPLIER_FINAL_CONFIDENCE
        ),
        "category_id": cid,
        "label_ka": label,
        "confidence": conf_norm,
    }


def _line_has_high_conf_non_supplier_category(line, category_id):
    row_for_cat = _line_to_row_for_category(line, reason="")
    cid, _, conf = _auto_category_from_unmatched_row(row_for_cat)
    conf_norm = str(conf or "low").lower().strip()
    if conf_norm not in {"high", "medium", "low"}:
        conf_norm = "low"
    return str(cid or "").strip() == str(category_id or "").strip() and conf_norm == "high"


def _finalize_reconciliation_line(
    line,
    status,
    confidence,
    reason,
    matched_by="",
    matched_tax_id="",
    supplier_master=None,
    candidate_suppliers=None,
    waybill_evidence=None,
    truth_source_label="",
):
    supplier_master = supplier_master or {"suppliers_by_id": {}}
    status = str(status or "unmatched")
    if status not in RECON_FINAL_STATUSES:
        status = "unmatched"
    matched_tax_id = str(matched_tax_id or "").strip()
    matched_supplier_name = (
        _supplier_display_name(matched_tax_id, supplier_master) if matched_tax_id else ""
    )
    line_with_hits = dict(line or {})
    line_with_hits["waybill_reference_hits"] = waybill_evidence or (
        line.get("waybill_reference_hits") or []
    )
    truth_context = _supplier_truth_context(
        matched_tax_id,
        supplier_master,
        truth_source_label=truth_source_label,
    )
    provenance = build_reconciliation_provenance(
        line_with_hits,
        status=status,
        confidence=confidence,
        matched_by=matched_by,
        truth_sources=truth_context.get("truth_sources") or [],
        truth_source_label=truth_context.get("truth_source_label") or "",
        supplier_truth_summary=truth_context.get("supplier_truth_summary") or "",
    )
    out = {
        "status": status,
        "confidence": str(confidence or ""),
        "reason": str(reason or ""),
        "matched_by": str(matched_by or ""),
        "matched_tax_id": matched_tax_id,
        "matched_supplier_name": matched_supplier_name,
        "candidate_suppliers": candidate_suppliers or [],
        "waybill_reference_hits": line_with_hits.get("waybill_reference_hits") or [],
        "source_bank": line.get("source_bank", ""),
        "file_name": line.get("file_name", ""),
        "row_date": line.get("row_date", ""),
        "amount": float(line.get("amount") or 0),
        "raw_receiver_name": line.get("raw_receiver_name", ""),
        "raw_partner_name": line.get("raw_partner_name", ""),
        "raw_purpose": line.get("raw_purpose", ""),
        "raw_description": line.get("raw_description", ""),
        "raw_tax_id": line.get("raw_tax_id", ""),
        "raw_account": line.get("raw_account", ""),
        "extracted_tax_ids": line.get("extracted_tax_ids") or [],
        "extracted_account_hints": line.get("extracted_account_hints") or [],
        "extracted_ibans": line.get("extracted_ibans") or [],
        "legacy_matched_tax_id": line.get("legacy_matched_tax_id", ""),
        "truth_source_label": truth_context.get("truth_source_label") or "",
        "truth_sources": truth_context.get("truth_sources") or [],
        "supplier_truth_summary": truth_context.get("supplier_truth_summary") or "",
        "official_name_truth_source": truth_context.get("official_name_truth_source")
        or "",
        "decision_scope": provenance.get("decision_scope"),
        "supplier_total_scope": provenance.get("supplier_total_scope"),
        "evidence_sources": provenance.get("evidence_sources") or [],
        "provenance": provenance,
    }
    return out


def _line_for_excel(decision):
    return {
        "ბანკი": decision.get("source_bank", ""),
        "ფაილი": decision.get("file_name", ""),
        "თარიღი": decision.get("row_date", ""),
        "თანხა": float(decision.get("amount") or 0),
        "სტატუსი": decision.get("status", ""),
        "confidence": decision.get("confidence", ""),
        "matched_by": decision.get("matched_by", ""),
        "reason": decision.get("reason", ""),
        "საგადასახადო_ID_raw": decision.get("raw_tax_id", ""),
        "matched_supplier_tax_id": decision.get("matched_tax_id", ""),
        "matched_supplier_name": decision.get("matched_supplier_name", ""),
        "მიმღები/პარტნიორი": decision.get("raw_receiver_name") or decision.get("raw_partner_name") or "",
        "ოპერაციის_შინაარსი": decision.get("raw_description", ""),
        "დანიშნულება": decision.get("raw_purpose", ""),
        "ანგარიში/IBAN_raw": decision.get("raw_account", ""),
        "extracted_tax_ids": ", ".join(decision.get("extracted_tax_ids") or []),
        "extracted_ibans": ", ".join(decision.get("extracted_ibans") or []),
        "candidate_suppliers": json.dumps(
            decision.get("candidate_suppliers") or [], ensure_ascii=False
        ),
        "waybill_refs": ", ".join(decision.get("waybill_reference_hits") or []),
        "legacy_matched_tax_id": decision.get("legacy_matched_tax_id", ""),
        "truth_source_label": decision.get("truth_source_label", ""),
        "truth_sources": ", ".join(decision.get("truth_sources") or []),
        "supplier_truth_summary": decision.get("supplier_truth_summary", ""),
        "official_name_truth_source": decision.get("official_name_truth_source", ""),
        "decision_scope": decision.get("decision_scope", ""),
        "supplier_total_scope": decision.get("supplier_total_scope", ""),
        "evidence_sources": ", ".join(decision.get("evidence_sources") or []),
    }


def _write_bank_status_excel(rows, download_dir, filename, title_ka):
    if not rows:
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("  [შეტყობინება] Excel-ისთვის დააყენე: pip install openpyxl")
        return
    out_df = pd.DataFrame([_line_for_excel(r) for r in rows])
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, filename)
    out_df.to_excel(path, index=False, engine="openpyxl")
    print(
        f"  Excel ({title_ka}) → {path} "
        f"({len(rows)} ხაზი, {sum(float(r.get('amount') or 0) for r in rows):,.2f} ₾)"
    )


def write_bank_ambiguous_excel(rows, download_dir):
    _write_bank_status_excel(rows, download_dir, "ბანკი_ბუნდოვანი_მიბმები.xlsx", "ბუნდოვანი მიბმები")


def write_bank_non_supplier_excel(rows, download_dir):
    _write_bank_status_excel(
        rows, download_dir, "ბანკი_non_supplier_ხაზები.xlsx", "non_supplier ხაზები"
    )


def write_bank_matched_high_excel(rows, download_dir):
    _write_bank_status_excel(
        rows,
        download_dir,
        "ბანკი_მაღალი_სანდოობის_მიბმები.xlsx",
        "მაღალი სანდოობის მიბმები",
    )


def _legacy_match_from_line(line, legacy_name_to_id, bog_receiver_map):
    source = line.get("source_bank")
    raw_tax_id = str(line.get("raw_tax_id") or "").strip()
    if source == "BOG":
        rec_id = canonical_tax_id_from_bog_receiver(raw_tax_id, bog_receiver_map)
    else:
        rec_id = raw_tax_id
    if rec_id and rec_id.isdigit() and len(rec_id) >= 5:
        return rec_id

    for raw_text in (
        line.get("raw_receiver_name"),
        line.get("raw_partner_name"),
        line.get("raw_description"),
        line.get("raw_purpose"),
    ):
        mid = match_partner_to_id_legacy(raw_text, legacy_name_to_id)
        if mid:
            return mid
    for ib in line.get("extracted_ibans") or []:
        if ib in PARTNER_IBAN_TO_RS_TAX_ID:
            return PARTNER_IBAN_TO_RS_TAX_ID[ib]
    return ""


def _build_reconciliation_audit(classified_rows, strict_payments, supplier_master):
    status_rows = defaultdict(list)
    status_totals = defaultdict(float)
    confidence_totals = defaultdict(float)
    confidence_counts = defaultdict(int)
    matched_method_breakdown = defaultdict(lambda: {"rows": 0, "amount": 0.0})
    truth_source_breakdown = defaultdict(lambda: {"rows": 0, "amount": 0.0})
    for row in classified_rows:
        st = str(row.get("status") or "unmatched")
        amt = float(row.get("amount") or 0)
        status_rows[st].append(row)
        status_totals[st] += amt
        conf = str(row.get("confidence") or "unknown")
        confidence_totals[conf] += amt
        confidence_counts[conf] += 1
        mb = str(row.get("matched_by") or st)
        matched_method_breakdown[mb]["rows"] += 1
        matched_method_breakdown[mb]["amount"] += amt
        truth_source_label = str(row.get("truth_source_label") or "").strip()
        if truth_source_label:
            truth_source_breakdown[truth_source_label]["rows"] += 1
            truth_source_breakdown[truth_source_label]["amount"] += amt

    relevant_rows = len(classified_rows)
    relevant_amount = float(sum(float(r.get("amount") or 0) for r in classified_rows))
    matched_high_amount = float(
        sum(float(v or 0) for v in strict_payments.values())
    )
    matched_high_rows = len(
        [r for r in classified_rows if str(r.get("status")) in RECON_MATCH_STATUSES]
    )
    ambiguous_rows = status_rows.get("ambiguous", [])
    unmatched_rows = status_rows.get("unmatched", [])
    non_supplier_rows = status_rows.get("non_supplier", [])
    skipped_rows = status_rows.get("skipped_explicit", [])

    rhs = (
        matched_high_amount
        + float(status_totals.get("ambiguous", 0.0))
        + float(status_totals.get("unmatched", 0.0))
        + float(status_totals.get("non_supplier", 0.0))
        + float(status_totals.get("skipped_explicit", 0.0))
    )
    delta = float(relevant_amount - rhs)
    balance_ok = abs(delta) <= 0.02

    top_ambiguous = sorted(
        ambiguous_rows,
        key=lambda r: float(r.get("amount") or 0),
        reverse=True,
    )[:10]
    status_breakdown = {}
    for st in sorted(status_rows.keys()):
        status_breakdown[st] = {
            "rows": int(len(status_rows[st])),
            "amount": float(status_totals.get(st, 0.0)),
        }
    method_breakdown = {}
    for k, v in sorted(
        matched_method_breakdown.items(),
        key=lambda item: float(item[1].get("amount") or 0),
        reverse=True,
    ):
        method_breakdown[k] = {
            "rows": int(v.get("rows") or 0),
            "amount": float(v.get("amount") or 0),
        }
    truth_breakdown = {}
    for k, v in sorted(
        truth_source_breakdown.items(),
        key=lambda item: float(item[1].get("amount") or 0),
        reverse=True,
    ):
        truth_breakdown[k] = {
            "rows": int(v.get("rows") or 0),
            "amount": float(v.get("amount") or 0),
        }

    return {
        "total_outgoing_relevant_rows": int(relevant_rows),
        "total_outgoing_relevant_amount": float(relevant_amount),
        "matched_high_confidence_rows": int(matched_high_rows),
        "matched_high_confidence_amount": float(matched_high_amount),
        "ambiguous_rows": int(len(ambiguous_rows)),
        "ambiguous_amount": float(status_totals.get("ambiguous", 0.0)),
        "unmatched_rows": int(len(unmatched_rows)),
        "unmatched_amount": float(status_totals.get("unmatched", 0.0)),
        "non_supplier_rows": int(len(non_supplier_rows)),
        "non_supplier_amount": float(status_totals.get("non_supplier", 0.0)),
        "skipped_explicit_rows": int(len(skipped_rows)),
        "skipped_explicit_amount": float(status_totals.get("skipped_explicit", 0.0)),
        "status_breakdown": status_breakdown,
        "match_method_breakdown": method_breakdown,
        "truth_source_breakdown": truth_breakdown,
        "confidence_breakdown": {
            c: {
                "rows": int(confidence_counts.get(c) or 0),
                "amount": float(confidence_totals.get(c) or 0.0),
            }
            for c in sorted(confidence_counts.keys())
        },
        "balance_check_summary": {
            "lhs_relevant_outgoing_amount": float(relevant_amount),
            "rhs_classified_amount": float(rhs),
            "delta": float(delta),
            "is_balanced": bool(balance_ok),
            "warning": ""
            if balance_ok
            else "Reconciliation balance mismatch: classified totals do not equal outgoing debit total.",
        },
        "ambiguous_preview": [_line_for_excel(r) for r in ambiguous_rows[:80]],
        "unmatched_preview": [_line_for_excel(r) for r in unmatched_rows[:80]],
        "top_ambiguous_cases": [_line_for_excel(r) for r in top_ambiguous],
        "all_lines_preview": [_line_for_excel(r) for r in classified_rows[:300]],
    }, status_rows


def _compute_supplier_delta_vs_legacy(
    strict_payments,
    classified_rows,
    supplier_master,
    limit=30,
):
    legacy = defaultdict(float)
    for row in classified_rows:
        tid = str(row.get("legacy_matched_tax_id") or "").strip()
        amt = float(row.get("amount") or 0)
        if tid and tid.isdigit() and amt > 0:
            legacy[tid] += amt
    strict = defaultdict(float)
    for tid, amt in (strict_payments or {}).items():
        if tid and str(tid).isdigit():
            strict[str(tid)] += float(amt or 0)
    deltas = []
    for tid in set(list(legacy.keys()) + list(strict.keys())):
        strict_amt = float(strict.get(tid, 0.0))
        legacy_amt = float(legacy.get(tid, 0.0))
        delta = float(strict_amt - legacy_amt)
        if abs(delta) < 0.01:
            continue
        deltas.append(
            {
                "tax_id": tid,
                "supplier_name": _supplier_display_name(tid, supplier_master),
                "strict_amount": round(strict_amt, 2),
                "legacy_optimistic_amount": round(legacy_amt, 2),
                "delta_vs_legacy": round(delta, 2),
            }
        )
    deltas.sort(key=lambda x: abs(float(x.get("delta_vs_legacy") or 0)), reverse=True)
    return deltas[:limit]


def empty_bank_reconciliation_audit():
    return {
        "total_outgoing_relevant_rows": 0,
        "total_outgoing_relevant_amount": 0.0,
        "matched_high_confidence_rows": 0,
        "matched_high_confidence_amount": 0.0,
        "ambiguous_rows": 0,
        "ambiguous_amount": 0.0,
        "unmatched_rows": 0,
        "unmatched_amount": 0.0,
        "non_supplier_rows": 0,
        "non_supplier_amount": 0.0,
        "skipped_explicit_rows": 0,
        "skipped_explicit_amount": 0.0,
        "status_breakdown": {},
        "match_method_breakdown": {},
        "confidence_breakdown": {},
        "balance_check_summary": {
            "lhs_relevant_outgoing_amount": 0.0,
            "rhs_classified_amount": 0.0,
            "delta": 0.0,
            "is_balanced": True,
            "warning": "",
        },
        "ambiguous_preview": [],
        "unmatched_preview": [],
        "top_ambiguous_cases": [],
        "all_lines_preview": [],
        "supplier_payment_deltas_vs_legacy": [],
        "registry_file_path": supplier_matching_registry_path(),
        "strict_payments_by_supplier": {},
        "manual_payments_by_supplier": {},
        "combined_payments_by_supplier": {},
        "payment_scope_summary": {
            "strict_bank_only_total": 0.0,
            "manual_journal_total": 0.0,
            "combined_supplier_paid_total": 0.0,
            "strict_supplier_count": 0,
            "manual_supplier_count": 0,
            "combined_supplier_count": 0,
            "strict_and_manual_overlap_count": 0,
            "manual_only_supplier_count": 0,
            "strict_only_supplier_count": 0,
            "scope_notes": [],
            "manual_only_suppliers_preview": [],
            "strict_only_suppliers_preview": [],
            "strict_and_manual_overlap_preview": [],
            "largest_manual_adjustments_preview": [],
        },
        "strict_matching_rules": {
            "score_accept_threshold": DEFAULT_RECON_SCORE_ACCEPT_THRESHOLD,
            "score_gap_threshold": DEFAULT_RECON_SCORE_GAP_THRESHOLD,
            "allowed_auto_match_statuses": sorted(list(RECON_MATCH_STATUSES)),
            "non_supplier_final_confidence": sorted(list(NON_SUPPLIER_FINAL_CONFIDENCE)),
        },
        "truth_source_breakdown": {},
        "truth_boundary_summary": build_truth_boundary_summary(
            primary_supplier_truth_path=supplier_matching_registry_path()
        ),
    }


def get_bank_payments(
    rs_files,
    reconciliation_exit_on_fail=True,
    supplier_registry=None,
    supplier_master=None,
):
    """
    Strict supplier reconciliation:
    - no substring-only auto match
    - only high-confidence matches affect supplier totals
    - all outgoing rows get explicit final status
    """
    supplier_registry = supplier_registry or load_supplier_matching_registry()
    supplier_master = supplier_master or build_supplier_master(
        rs_files, supplier_registry=supplier_registry
    )
    waybill_index = _build_waybill_reference_index(rs_files)
    truth_boundary_summary = _build_truth_boundary_summary_for_supplier_master(
        supplier_master
    )
    legal_name_to_id = supplier_master.get("legal_name_to_id") or {}
    alias_to_id = supplier_master.get("alias_to_id") or {}
    person_alias_to_id = supplier_master.get("person_alias_to_id") or {}
    alias_union = {**alias_to_id, **person_alias_to_id}
    legacy_name_to_id = dict(legal_name_to_id)

    _bog_auto = infer_bog_receiver_id_to_rs_tax_id(rs_files)
    bog_receiver_map = {**_bog_auto, **BOG_RECEIVER_ID_TO_RS_TAX_ID}

    print(
        "Building supplier reconciliation master... "
        f"{len(supplier_master.get('suppliers_by_id') or {})} suppliers, "
        f"{len(legal_name_to_id)} legal-name keys, "
        f"{len(alias_union)} alias keys"
    )
    print(
        f"  Waybill refs indexed: {len((waybill_index.get('known_refs') or []))}"
    )
    print(
        "  Truth boundary: "
        f"registry primary={truth_boundary_summary.get('registry_primary_supplier_count', 0)} | "
        f"RS backstop={truth_boundary_summary.get('rs_backstop_supplier_count', 0)} | "
        f"legacy audit-only={truth_boundary_summary.get('legacy_truth_assist_supplier_count', 0)}"
    )

    raw_lines = []
    print("Reading BOG bank statements...")
    for f in list_bog_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = df.columns
            debit_col = next(
                (c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)),
                None,
            )
            if not debit_col:
                continue
            id_col = next((c for c in cols if "მიმღების საიდენტიფიკაციო" in str(c)), None)
            name_col = next((c for c in cols if "მიმღების დასახელება" in str(c)), None)
            desc_col = next((c for c in cols if "ოპერაციის შინაარსი" in str(c)), None)
            purpose_col = _find_excel_column_danishnuleba(cols)
            account_col = next(
                (c for c in cols if "მიმღების ანგარიშის ნომერი" in str(c)),
                None,
            )
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors="coerce")
                if pd.isna(amt) or amt <= 0:
                    continue
                raw_rec_id = clean_id(row[id_col]) if id_col else None
                line = _build_reconciliation_line(
                    bank="BOG",
                    file_name=os.path.basename(f),
                    row_date=_excel_cell(row, date_col),
                    amount=float(amt),
                    raw_tax_id=canonical_tax_id_from_bog_receiver(
                        raw_rec_id, BOG_RECEIVER_ID_TO_RS_TAX_ID
                    )
                    or "",
                    receiver_name=_excel_cell(row, name_col),
                    partner_name="",
                    purpose_text=_excel_cell(row, purpose_col) if purpose_col else "",
                    description_text=_excel_cell(row, desc_col),
                    account_text=_excel_cell(row, account_col),
                )
                line["legacy_matched_tax_id"] = _legacy_match_from_line(
                    line, legacy_name_to_id, bog_receiver_map
                )
                raw_lines.append(line)
        except Exception as e:
            print(f"Error reading BOG {f}: {e}")

    print("Reading TBC bank statements...")
    for f in list_tbc_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = df.columns
            debit_col = next((c for c in cols if "გასული თანხა" in str(c)), None)
            if not debit_col:
                continue
            id_col = next(
                (c for c in cols if "პარტნიორის საგადასახადო კოდი" in str(c)),
                None,
            )
            partner_col = _find_tbc_partner_column(cols)
            purpose_col = _find_excel_column_danishnuleba(cols)
            extra_purpose_col = _find_tbc_additional_purpose_column(cols)
            account_col = next((c for c in cols if "პარტნიორის ანგარიში" in str(c)), None)
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            df = df[
                ~df[debit_col].astype(str).str.contains("Paid|Out|Amount", case=False, na=False)
            ]
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors="coerce")
                if pd.isna(amt) or amt <= 0:
                    continue
                rec_id = clean_id(row[id_col]) if id_col else None
                line = _build_reconciliation_line(
                    bank="TBC",
                    file_name=os.path.basename(f),
                    row_date=_excel_cell(row, date_col),
                    amount=float(amt),
                    raw_tax_id=rec_id or "",
                    receiver_name="",
                    partner_name=_excel_cell(row, partner_col),
                    purpose_text=_excel_cell(row, purpose_col) if purpose_col else "",
                    description_text=_excel_cell(row, extra_purpose_col),
                    account_text=_excel_cell(row, account_col),
                )
                line["legacy_matched_tax_id"] = _legacy_match_from_line(
                    line, legacy_name_to_id, bog_receiver_map
                )
                raw_lines.append(line)
        except Exception as e:
            print(f"Error reading TBC {f}: {e}")

    def _classify_line(line):
        line_is_transfer_commission_fee = _line_has_high_conf_non_supplier_category(
            line, "transfer_commission_fee"
        )
        should_skip, skip_reason = _line_has_explicit_skip(line, supplier_master)
        if should_skip:
            return _finalize_reconciliation_line(
                line,
                status="skipped_explicit",
                confidence="high",
                reason=skip_reason,
                matched_by="explicit_skip_rule",
                supplier_master=supplier_master,
            )

        tid, st, reason, truth_source_label = _match_by_exact_tax_id(
            line, supplier_master
        )
        if st == "ambiguous":
            candidates = [
                {
                    "tax_id": t,
                    "supplier_name": _supplier_display_name(t, supplier_master),
                    "score": 100.0,
                    "reasons": ["tax_id_conflict"],
                }
                for t in (line.get("extracted_tax_ids") or [])
                if t in (supplier_master.get("suppliers_by_id") or {})
            ]
            return _finalize_reconciliation_line(
                line,
                status="ambiguous",
                confidence="medium",
                reason=reason,
                matched_by="exact_tax_id",
                supplier_master=supplier_master,
                candidate_suppliers=candidates[:5],
                truth_source_label=truth_source_label,
            )
        if tid:
            forced, force_reason = _line_force_non_supplier_for_supplier(
                line, tid, supplier_master
            )
            if forced:
                return _finalize_reconciliation_line(
                    line,
                    status="skipped_explicit",
                    confidence="high",
                    reason=force_reason,
                    matched_by="force_non_supplier",
                    matched_tax_id=tid,
                    supplier_master=supplier_master,
                    truth_source_label=truth_source_label,
                )
            return _finalize_reconciliation_line(
                line,
                status="matched_exact_id",
                confidence="high",
                reason=reason,
                matched_by="exact_tax_id",
                matched_tax_id=tid,
                supplier_master=supplier_master,
                truth_source_label=truth_source_label,
            )

        tid, st, reason, truth_source_label = _match_by_exact_iban(
            line, supplier_master
        )
        if line_is_transfer_commission_fee and st in {"matched_exact_iban", "ambiguous"}:
            fee_tid_name, fee_st_name, _, _ = _match_by_exact_names(line, supplier_master)
            if not fee_tid_name and fee_st_name != "ambiguous":
                tid, st, reason, truth_source_label = None, "", "", ""
        if st == "ambiguous":
            return _finalize_reconciliation_line(
                line,
                status="ambiguous",
                confidence="medium",
                reason=reason,
                matched_by="exact_iban",
                supplier_master=supplier_master,
                truth_source_label=truth_source_label,
            )
        if tid:
            forced, force_reason = _line_force_non_supplier_for_supplier(
                line, tid, supplier_master
            )
            if forced:
                return _finalize_reconciliation_line(
                    line,
                    status="skipped_explicit",
                    confidence="high",
                    reason=force_reason,
                    matched_by="force_non_supplier",
                    matched_tax_id=tid,
                    supplier_master=supplier_master,
                    truth_source_label=truth_source_label,
                )
            return _finalize_reconciliation_line(
                line,
                status="matched_exact_iban",
                confidence="high",
                reason=reason,
                matched_by="exact_iban",
                matched_tax_id=tid,
                supplier_master=supplier_master,
                truth_source_label=truth_source_label,
            )

        tid, st, reason, truth_source_label = _match_by_exact_names(
            line, supplier_master
        )
        if st == "ambiguous":
            scored_candidates = _score_supplier_candidates(line, supplier_master, waybill_index)
            return _finalize_reconciliation_line(
                line,
                status="ambiguous",
                confidence="medium",
                reason=reason,
                matched_by="exact_name_or_alias",
                supplier_master=supplier_master,
                candidate_suppliers=_candidate_preview_list(
                    scored_candidates, supplier_master
                ),
                truth_source_label=truth_source_label,
            )
        if tid:
            forced, force_reason = _line_force_non_supplier_for_supplier(
                line, tid, supplier_master
            )
            if forced:
                return _finalize_reconciliation_line(
                    line,
                    status="skipped_explicit",
                    confidence="high",
                    reason=force_reason,
                    matched_by="force_non_supplier",
                    matched_tax_id=tid,
                    supplier_master=supplier_master,
                    truth_source_label=truth_source_label,
                )
            return _finalize_reconciliation_line(
                line,
                status=st,
                confidence="high",
                reason=reason,
                matched_by="exact_name" if st == "matched_exact_name" else "exact_alias",
                matched_tax_id=tid,
                supplier_master=supplier_master,
                truth_source_label=truth_source_label,
            )

        scored_candidates = _score_supplier_candidates(line, supplier_master, waybill_index)
        candidate_preview = _candidate_preview_list(scored_candidates, supplier_master)
        if scored_candidates:
            best = scored_candidates[0]
            second_score = (
                float(scored_candidates[1].get("score") or 0)
                if len(scored_candidates) > 1
                else -999.0
            )
            best_score = float(best.get("score") or 0)
            gap = float(best_score - second_score)
            if (
                best_score >= DEFAULT_RECON_SCORE_ACCEPT_THRESHOLD
                and gap >= DEFAULT_RECON_SCORE_GAP_THRESHOLD
            ):
                tid = str(best.get("tax_id") or "")
                forced, force_reason = _line_force_non_supplier_for_supplier(
                    line, tid, supplier_master
                )
                if forced:
                    return _finalize_reconciliation_line(
                        line,
                        status="skipped_explicit",
                        confidence="high",
                        reason=force_reason,
                        matched_by="force_non_supplier",
                        matched_tax_id=tid,
                        supplier_master=supplier_master,
                        candidate_suppliers=candidate_preview,
                    )
                return _finalize_reconciliation_line(
                    line,
                    status="matched_scored_high",
                    confidence="high",
                    reason=f"scored candidate accepted (score={best_score:.1f}, gap={gap:.1f})",
                    matched_by="scored_candidate",
                    matched_tax_id=tid,
                    supplier_master=supplier_master,
                    candidate_suppliers=candidate_preview,
                    truth_source_label=_infer_truth_source_label_from_scored_candidate(
                        best, supplier_master
                    ),
                )

        non_supplier_decision = _classify_non_supplier(line)
        if non_supplier_decision["is_non_supplier"]:
            return _finalize_reconciliation_line(
                line,
                status="non_supplier",
                confidence=non_supplier_decision["confidence"],
                reason=(
                    "non-supplier category: "
                    f"{non_supplier_decision['category_id']} "
                    f"({non_supplier_decision['label_ka']})"
                ),
                matched_by="non_supplier_rules",
                supplier_master=supplier_master,
                candidate_suppliers=candidate_preview,
            )
        non_supplier_hint = ""
        if non_supplier_decision["is_hint_only"]:
            non_supplier_hint = (
                "non-supplier hint only: "
                f"{non_supplier_decision['category_id']} "
                f"({non_supplier_decision['label_ka']}, "
                f"confidence={non_supplier_decision['confidence']}); "
                "kept unresolved until explicit evidence"
            )
        if candidate_preview:
            return _finalize_reconciliation_line(
                line,
                status="ambiguous",
                confidence="medium",
                reason=(
                    "scored candidates exist but confidence/gap is insufficient"
                    + (f"; {non_supplier_hint}" if non_supplier_hint else "")
                ),
                matched_by="scored_candidate",
                supplier_master=supplier_master,
                candidate_suppliers=candidate_preview,
            )
        return _finalize_reconciliation_line(
            line,
            status="unmatched",
            confidence="low",
            reason=(
                "no strong supplier evidence"
                + (f"; {non_supplier_hint}" if non_supplier_hint else "")
            ),
            matched_by="none",
            supplier_master=supplier_master,
            candidate_suppliers=[],
        )

    classified_rows = [_classify_line(line) for line in raw_lines]

    strict_payments = defaultdict(float)
    for row in classified_rows:
        if row.get("status") in RECON_MATCH_STATUSES:
            tid = str(row.get("matched_tax_id") or "").strip()
            if tid and tid.isdigit():
                strict_payments[tid] += float(row.get("amount") or 0)

    audit_block, status_rows = _build_reconciliation_audit(
        classified_rows, strict_payments, supplier_master
    )
    audit_block["supplier_payment_deltas_vs_legacy"] = _compute_supplier_delta_vs_legacy(
        strict_payments, classified_rows, supplier_master
    )
    audit_block["registry_file_path"] = supplier_matching_registry_path()
    audit_block["strict_matching_rules"] = {
        "score_accept_threshold": DEFAULT_RECON_SCORE_ACCEPT_THRESHOLD,
        "score_gap_threshold": DEFAULT_RECON_SCORE_GAP_THRESHOLD,
        "allowed_auto_match_statuses": sorted(list(RECON_MATCH_STATUSES)),
        "non_supplier_final_confidence": sorted(list(NON_SUPPLIER_FINAL_CONFIDENCE)),
    }
    audit_block["truth_boundary_summary"] = truth_boundary_summary

    matched_amount = float(sum(strict_payments.values()))
    balance_rows = [
        _line_to_row_for_category(r, reason=r.get("reason", ""))
        for r in classified_rows
        if r.get("status") not in RECON_MATCH_STATUSES
    ]
    reconciliation_ok = verify_bank_debit_totals(
        matched_amount,
        balance_rows,
        exit_on_fail=reconciliation_exit_on_fail,
    )
    if not bool((audit_block.get("balance_check_summary") or {}).get("is_balanced")):
        print(
            "  [warn] bank_reconciliation_audit balance mismatch: "
            f"{(audit_block.get('balance_check_summary') or {}).get('delta', 0):,.2f} ₾"
        )

    print(
        "  Reconciliation strict summary: "
        f"matched_high={audit_block['matched_high_confidence_rows']} "
        f"({audit_block['matched_high_confidence_amount']:,.2f} ₾) | "
        f"ambiguous={audit_block['ambiguous_rows']} ({audit_block['ambiguous_amount']:,.2f} ₾) | "
        f"unmatched={audit_block['unmatched_rows']} ({audit_block['unmatched_amount']:,.2f} ₾) | "
        f"non_supplier={audit_block['non_supplier_rows']} ({audit_block['non_supplier_amount']:,.2f} ₾) | "
        f"skipped={audit_block['skipped_explicit_rows']} ({audit_block['skipped_explicit_amount']:,.2f} ₾)"
    )

    strict_payments_out = {
        str(tid): float(amount or 0) for tid, amount in dict(strict_payments).items()
    }
    payments = dict(strict_payments_out)
    manual_map = load_manual_payments()
    if manual_map:
        man_sum = sum(manual_map.values())
        for tid, amt in manual_map.items():
            payments[tid] = payments.get(tid, 0.0) + amt
        print(
            f"  ხელით გადახდები (manual_payments.csv): {len(manual_map)} საგად. ID, "
            f"+{man_sum:,.2f} ₾ → სულ გადახდების ლექსიკონი: {sum(payments.values()):,.2f} ₾"
        )
    supplier_name_lookup = {
        str(tid): _supplier_display_name(str(tid), supplier_master)
        for tid in set(list(strict_payments_out.keys()) + list(manual_map.keys()))
    }
    audit_block["strict_payments_by_supplier"] = strict_payments_out
    audit_block["manual_payments_by_supplier"] = {
        str(tid): float(amount or 0) for tid, amount in (manual_map or {}).items()
    }
    audit_block["combined_payments_by_supplier"] = {
        str(tid): float(amount or 0) for tid, amount in payments.items()
    }
    audit_block["payment_scope_summary"] = build_payment_scope_summary(
        strict_payments_out,
        manual_map,
        supplier_names=supplier_name_lookup,
    )

    unresolved_rows = []
    for st in ("ambiguous", "unmatched"):
        for row in status_rows.get(st, []):
            rr = _line_to_row_for_category(row, reason=row.get("reason", ""))
            rr["სტატუსი"] = row.get("status", "")
            rr["confidence"] = row.get("confidence", "")
            rr["matched_by"] = row.get("matched_by", "")
            rr["candidates"] = json.dumps(
                row.get("candidate_suppliers") or [], ensure_ascii=False
            )
            unresolved_rows.append(rr)

    status_buckets = {
        "matched_high": status_rows.get("matched_exact_id", [])
        + status_rows.get("matched_exact_iban", [])
        + status_rows.get("matched_exact_name", [])
        + status_rows.get("matched_alias", [])
        + status_rows.get("matched_scored_high", []),
        "ambiguous": status_rows.get("ambiguous", []),
        "unmatched": status_rows.get("unmatched", []),
        "non_supplier": status_rows.get("non_supplier", []),
        "skipped_explicit": status_rows.get("skipped_explicit", []),
        "all": classified_rows,
    }

    return payments, unresolved_rows, reconciliation_ok, audit_block, status_buckets

def run():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    object_mapping = load_object_mapping(script_dir)
    generated_at = pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    source_manifest = build_source_manifest(
        [
            {
                "label_ka": "BOG ბანკის ამონაწერი",
                "source_kind": "bog_bank_statement",
                "paths": list_bog_bank_statement_xlsx(),
            },
            {
                "label_ka": "TBC ბანკის ამონაწერი",
                "source_kind": "tbc_bank_statement",
                "paths": list_tbc_bank_statement_xlsx(),
            },
            {
                "label_ka": "RS ზედნადები",
                "source_kind": "rs_waybills",
                "paths": list_rs_waybill_files(),
            },
            {
                "label_ka": "შემოტანილი პროდუქცია",
                "source_kind": "imported_products",
                "paths": list_imported_product_files(),
            },
            {
                "label_ka": "გაყიდული პროდუქცია — დვაბზუ",
                "source_kind": "retail_sales_dvabzu",
                "paths": list_retail_sales_dvabzu_files(),
            },
            {
                "label_ka": "გაყიდული პროდუქცია — ოზურგეთი",
                "source_kind": "retail_sales_ozurgeti",
                "paths": list_retail_sales_ozurgeti_files(),
            },
        ]
    )
    source_manifest_summary = summarize_source_manifest(source_manifest)
    budget_config = load_budget_config()
    sector_benchmarks = load_sector_benchmarks()
    supplier_registry_cfg = load_supplier_matching_registry()
    unmatched_overrides_cfg = load_unmatched_overrides()
    config_validation = validate_config_bundle(
        object_mapping,
        budget_config,
        sector_benchmarks,
        supplier_registry_cfg,
        unmatched_overrides_cfg,
    )
    print(
        "Config validation: "
        f"errors={config_validation.get('error_count', 0)} | "
        f"warnings={config_validation.get('warning_count', 0)}"
    )

    print("Reading card and POS income sources...")
    tbc_card_income_bundle = collect_tbc_card_income(
        script_dir, object_mapping=object_mapping
    )
    bog_pos_income_bundle = collect_bog_pos_terminal_income(
        script_dir, object_mapping=object_mapping
    )
    pos_terminal_all_rows = list(tbc_card_income_bundle.get("lines") or []) + list(
        bog_pos_income_bundle.get("lines") or []
    )
    pos_terminal_income_bundle = merge_pos_terminal_income(
        tbc_card_income_bundle,
        bog_pos_income_bundle,
        object_mapping=object_mapping,
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

    tbc_expenses_bundle = collect_tbc_expense_categories(
        script_dir, object_mapping=object_mapping
    )
    _te_lines = sum(
        int(c.get("line_count") or 0)
        for c in (tbc_expenses_bundle.get("categories") or [])
    )
    print(
        f"  TBC ხარჯები (კატეგორიები): {_te_lines} ხაზი, "
        f"{tbc_expenses_bundle.get('grand_total_ge', 0):,.2f} ₾"
    )
    bog_expenses_bundle = collect_bog_expense_categories(
        script_dir, object_mapping=object_mapping
    )
    _be_lines = sum(
        int(c.get("line_count") or 0)
        for c in (bog_expenses_bundle.get("categories") or [])
    )
    _be_active_categories = sum(
        1
        for c in (bog_expenses_bundle.get("categories") or [])
        if int(c.get("line_count") or 0) > 0
    )
    print(
        "  BOG ხარჯები: "
        f"{_be_active_categories} კატეგორია, {_be_lines} ხაზი, "
        f"{bog_expenses_bundle.get('grand_total_ge', 0):,.2f} ₾ "
        f"(operating: {bog_expenses_bundle.get('grand_total_operating_expense_ge', 0):,.2f} ₾, "
        f"treasury: {bog_expenses_bundle.get('grand_total_state_treasury_ge', 0):,.2f} ₾)"
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
    imported_products_bundle = collect_imported_products_bundle(rs_files)
    imported_overall = imported_products_bundle.get("overall") or {}
    print(
        "  შემოტანილი პროდუქცია (reference): "
        f"{imported_products_bundle.get('files_read_count', 0)} ფაილი, "
        f"{int(imported_overall.get('row_count') or 0)} ხაზი, "
        f"{float(imported_overall.get('total_amount_ge') or 0):,.2f} ₾"
    )
    if imported_products_bundle.get("truncation_suspected_any"):
        print(
            "    [warn] truncate/export limit ეჭვი: "
            + ", ".join(imported_products_bundle.get("truncation_suspected_files") or [])
        )
    retail_sales_bundle = collect_retail_sales_bundle(object_mapping=object_mapping)
    retail_overall = retail_sales_bundle.get("overall") or {}
    print(
        "  Retail sales source (reference-only): "
        f"{retail_sales_bundle.get('files_read_count', 0)} ფაილი, "
        f"{int(retail_overall.get('row_count') or 0)} ხაზი, "
        f"revenue {float(retail_overall.get('revenue_ge') or 0):,.2f} ₾ | "
        f"profit {float(retail_overall.get('profit_ge') or 0):,.2f} ₾ | "
        f"margin {float(retail_overall.get('gross_margin_pct') or 0):.2f}%"
    )
    retail_duplicate_policy = retail_sales_bundle.get("duplicate_policy") or {}
    if int(retail_duplicate_policy.get("excluded_file_count") or 0) > 0:
        print(
            "    [policy] duplicate-suspected ფაილი totals-იდან გამორიცხულია: "
            + ", ".join(retail_duplicate_policy.get("excluded_files") or [])
        )
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
        supplier_aging_result = {"suppliers": [], "summary": _empty_aging_summary()}
        ap_monthly_trend = []
        bank_reconciliation_audit = empty_bank_reconciliation_audit()
        data = {
            "suppliers": [],
            "waybills": [],
            "imported_products": imported_products_bundle,
            "retail_sales": retail_sales_bundle,
            "tbc_card_income": {
                "label_ka": tbc_card_income_bundle["label_ka"],
                "total_ge": float(tbc_card_income_bundle["total_ge"]),
                "line_count": int(tbc_card_income_bundle["line_count"]),
                "rows_preview": tbc_card_income_bundle["lines"][:300],
                "monthly_summary": _monthly_summary(tbc_card_income_bundle["lines"]),
            },
            "pos_terminal_income": pos_terminal_income_bundle,
            "tbc_expenses": tbc_expenses_public_json(tbc_expenses_bundle),
            "bog_expenses": bog_expenses_public_json(bog_expenses_bundle),
            "tbc_samurneo": samurneo_bundle,
            "tax_flow": tax_flow_bundle,
            "tbc_foodmart_cashback": tbc_foodmart_cashback_bundle,
            "bank_unmatched_analysis": analyze_bank_unmatched_rows([]),
            "bank_reconciliation_audit": bank_reconciliation_audit,
            "supplier_aging": supplier_aging_result["suppliers"],
            "aging_summary": supplier_aging_result["summary"],
            "ap_monthly_trend": ap_monthly_trend,
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
                "bank_recon_total_outgoing_amount": 0.0,
                "bank_recon_matched_high_amount": 0.0,
                "bank_recon_ambiguous_amount": 0.0,
                "bank_recon_non_supplier_amount": 0.0,
                "bank_recon_unmatched_amount": 0.0,
                "bank_recon_skipped_amount": 0.0,
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
                "retail_sales_row_count": int(retail_overall.get("row_count") or 0),
                "retail_sales_total_quantity": float(retail_overall.get("total_quantity") or 0),
                "retail_sales_revenue_ge": float(retail_overall.get("revenue_ge") or 0),
                "retail_sales_cost_ge": float(retail_overall.get("cost_ge") or 0),
                "retail_sales_profit_ge": float(retail_overall.get("profit_ge") or 0),
                "retail_sales_gross_margin_pct": float(
                    retail_overall.get("gross_margin_pct") or 0
                ),
                "retail_sales_distinct_object_count": int(
                    retail_overall.get("distinct_object_count") or 0
                ),
                "retail_sales_distinct_category_count": int(
                    retail_overall.get("distinct_category_count") or 0
                ),
                "retail_sales_distinct_product_count": int(
                    retail_overall.get("distinct_product_count") or 0
                ),
                "retail_sales_duplicate_excluded_file_count": int(
                    retail_duplicate_policy.get("excluded_file_count") or 0
                ),
            },
        }
    else:
        df = pd.concat(all_rs, ignore_index=True)
        print(
            "  RS: ნომინალი + რეალური ჯამი + დაბრუნება — data.json (total_cancelled შიგნით, UI-ზე არა)."
        )
        rs_location_col = next(
            (c for c in df.columns if "მიწოდების ადგილი" in str(c)),
            None,
        )
        if not rs_location_col:
            rs_location_col = next(
                (
                    c
                    for c in df.columns
                    if "მიწოდების" in str(c) and "ადგილი" in str(c)
                ),
                None,
            )
        if rs_location_col:
            df["object"] = df[rs_location_col].apply(
                lambda x: detect_object(
                    "rs_waybill",
                    rs_location=x,
                    object_mapping=object_mapping,
                )
            )
        else:
            df["object"] = detect_object("rs_waybill", object_mapping=object_mapping)

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
        rs_object_agg = df.groupby('object').agg(
            waybills_count=('_აქტიური_ხაზი', 'sum'),
            total_effective=('ეფექტური თანხა', 'sum'),
        ).reset_index()
        rs_object_summary = ", ".join(
            f"{r['object']}: {float(r['total_effective']):,.2f} ₾"
            for _, r in rs_object_agg.iterrows()
        )
        print(
            "  RS ობიექტების ეფექტური ჯამი: "
            f"{rs_object_summary or 'მონაცემი არ არის'}"
        )

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
        supplier_master = build_supplier_master(
            rs_files, supplier_registry=supplier_registry_cfg
        )
        # ----- Merge with Bank Payments -----
        (
            bank_payments,
            bank_unmatched_rows,
            _bank_reconciliation_ok,
            bank_reconciliation_audit,
            bank_reconciliation_status_rows,
        ) = get_bank_payments(
            rs_files,
            supplier_registry=supplier_registry_cfg,
            supplier_master=supplier_master,
        )
        bank_unmatched_sum = float(
            (bank_reconciliation_audit.get("ambiguous_amount") or 0)
            + (bank_reconciliation_audit.get("unmatched_amount") or 0)
        )
        bank_unmatched_analysis = analyze_bank_unmatched_rows(bank_unmatched_rows)
        print(
            "  ბანკი — strict audit: "
            f"total {bank_reconciliation_audit.get('total_outgoing_relevant_rows', 0)} ხაზი / "
            f"{float(bank_reconciliation_audit.get('total_outgoing_relevant_amount') or 0):,.2f} ₾ | "
            f"matched {bank_reconciliation_audit.get('matched_high_confidence_rows', 0)} "
            f"({float(bank_reconciliation_audit.get('matched_high_confidence_amount') or 0):,.2f} ₾)"
        )
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

        agg_df['supplier_id'] = agg_df['ორგანიზაცია'].apply(_extract_tax_id_from_org)
        strict_bank_only_map = (
            bank_reconciliation_audit.get("strict_payments_by_supplier") or {}
        )
        manual_only = (
            bank_reconciliation_audit.get("manual_payments_by_supplier") or {}
        )

        supplier_truth_cache = {}

        def _supplier_truth_fields(s_id):
            if s_id is None or pd.isna(s_id):
                return {
                    "supplier_truth_summary": "",
                    "supplier_truth_sources": [],
                    "official_name_truth_source": "",
                }
            tid = str(s_id).strip()
            if not tid or tid.lower() == "nan":
                return {
                    "supplier_truth_summary": "",
                    "supplier_truth_sources": [],
                    "official_name_truth_source": "",
                }
            cached = supplier_truth_cache.get(tid)
            if cached is None:
                truth_context = _supplier_truth_context(tid, supplier_master)
                cached = {
                    "supplier_truth_summary": str(
                        truth_context.get("supplier_truth_summary") or ""
                    ),
                    "supplier_truth_sources": list(
                        truth_context.get("truth_sources") or []
                    ),
                    "official_name_truth_source": str(
                        truth_context.get("official_name_truth_source") or ""
                    ),
                }
                supplier_truth_cache[tid] = cached
            return cached
        
        def get_paid_amount(s_id):
            if not s_id: return 0.0
            return bank_payments.get(s_id, 0.0)

        def get_strict_bank_paid(s_id):
            if not s_id:
                return 0.0
            return float(strict_bank_only_map.get(s_id, 0) or 0)
            
        agg_df['total_paid'] = agg_df['supplier_id'].apply(get_paid_amount)
        def get_manual_paid(s_id):
            if not s_id:
                return 0.0
            return float(manual_only.get(s_id, 0) or 0)

        agg_df['manual_paid'] = agg_df['supplier_id'].apply(get_manual_paid)
        agg_df['strict_bank_paid'] = agg_df['supplier_id'].apply(get_strict_bank_paid)
        agg_df['bank_paid'] = agg_df['strict_bank_paid']
        agg_df['total_debt'] = agg_df['total_effective'] - agg_df['total_paid']
        agg_df['payment_scope'] = agg_df.apply(
            lambda row: describe_supplier_payment_scope(
                row.get('strict_bank_paid'), row.get('manual_paid')
            ).get('payment_scope'),
            axis=1,
        )
        agg_df['payment_scope_note'] = agg_df.apply(
            lambda row: describe_supplier_payment_scope(
                row.get('strict_bank_paid'), row.get('manual_paid')
            ).get('payment_scope_note'),
            axis=1,
        )
        agg_df['supplier_truth_summary'] = agg_df['supplier_id'].apply(
            lambda s_id: _supplier_truth_fields(s_id).get(
                'supplier_truth_summary', ''
            )
        )
        agg_df['supplier_truth_sources'] = agg_df['supplier_id'].apply(
            lambda s_id: list(
                _supplier_truth_fields(s_id).get('supplier_truth_sources') or []
            )
        )
        agg_df['official_name_truth_source'] = agg_df['supplier_id'].apply(
            lambda s_id: _supplier_truth_fields(s_id).get(
                'official_name_truth_source', ''
            )
        )

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
                    "strict_bank_paid": tp - mp,
                    "bank_paid": tp - mp,
                    "total_debt": 0.0 - tp,
                    "payment_scope": describe_supplier_payment_scope(tp - mp, mp).get(
                        "payment_scope"
                    ),
                    "payment_scope_note": describe_supplier_payment_scope(
                        tp - mp, mp
                    ).get("payment_scope_note"),
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
        supplier_aging_result = build_supplier_aging(suppliers_data, df)
        ap_monthly_trend = build_ap_monthly_trend(
            df,
            bank_payments,
            strict_bank_payments=strict_bank_only_map,
            manual_payments=manual_only,
        )
        print("Aging summary:")
        for bucket in AGING_BUCKET_ORDER:
            b = supplier_aging_result["summary"].get(
                bucket, {"count": 0, "total_debt": 0.0}
            )
            print(
                f"  {bucket} დღე: {int(b.get('count') or 0)} მომწოდებელი, "
                f"{float(b.get('total_debt') or 0):,.2f} ₾"
            )
        if ap_monthly_trend:
            print(
                f"AP trend: {len(ap_monthly_trend)} თვე, ბოლო თვე cumulative debt: "
                f"{float(ap_monthly_trend[-1].get('cumulative_debt') or 0):,.2f} ₾"
            )
        else:
            print("AP trend: 0 თვე, ბოლო თვე cumulative debt: 0.00 ₾")

        download_dir = os.path.join(script_dir, "download")
        bank_unmatched_only_rows = bank_reconciliation_status_rows.get("unmatched", [])
        bank_ambiguous_rows = bank_reconciliation_status_rows.get("ambiguous", [])
        bank_non_supplier_rows = bank_reconciliation_status_rows.get("non_supplier", [])
        bank_matched_high_rows = bank_reconciliation_status_rows.get("matched_high", [])
        write_suppliers_excel(suppliers_data, download_dir)
        write_bank_unmatched_excel(
            [_line_for_excel(r) for r in bank_unmatched_only_rows],
            download_dir,
        )
        write_bank_ambiguous_excel(bank_ambiguous_rows, download_dir)
        write_bank_non_supplier_excel(bank_non_supplier_rows, download_dir)
        write_bank_matched_high_excel(bank_matched_high_rows, download_dir)
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
            "imported_products": imported_products_bundle,
            "retail_sales": retail_sales_bundle,
            "tbc_card_income": {
                "label_ka": tbc_card_income_bundle["label_ka"],
                "total_ge": float(tbc_card_income_bundle["total_ge"]),
                "line_count": int(tbc_card_income_bundle["line_count"]),
                "rows_preview": tbc_card_income_bundle["lines"][:300],
                "monthly_summary": _monthly_summary(tbc_card_income_bundle["lines"]),
            },
            "pos_terminal_income": pos_terminal_income_bundle,
            "tbc_expenses": tbc_expenses_public_json(tbc_expenses_bundle),
            "bog_expenses": bog_expenses_public_json(bog_expenses_bundle),
            "tbc_samurneo": samurneo_bundle,
            "tax_flow": tax_flow_bundle,
            "tbc_foodmart_cashback": tbc_foodmart_cashback_bundle,
            "bank_unmatched_analysis": bank_unmatched_analysis,
            "bank_reconciliation_audit": bank_reconciliation_audit,
            "supplier_aging": supplier_aging_result["suppliers"],
            "aging_summary": supplier_aging_result["summary"],
            "ap_monthly_trend": ap_monthly_trend,
            "meta": {
                "manual_payments_total": manual_grand,
                "manual_payments_rows_with_amount": len(
                    [a for a in manual_only.values() if a > 0]
                ),
                "suppliers_only_journal_or_bank": extra_supplier_count,
                "bank_orphan_total_ge": float(bank_orphan),
                "bank_unmatched_total_ge": float(bank_unmatched_sum),
                "bank_unmatched_line_count": int(
                    (bank_reconciliation_audit.get("ambiguous_rows") or 0)
                    + (bank_reconciliation_audit.get("unmatched_rows") or 0)
                ),
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
                "bank_recon_total_outgoing_amount": float(
                    bank_reconciliation_audit.get("total_outgoing_relevant_amount") or 0
                ),
                "bank_recon_matched_high_amount": float(
                    bank_reconciliation_audit.get("matched_high_confidence_amount") or 0
                ),
                "bank_recon_ambiguous_amount": float(
                    bank_reconciliation_audit.get("ambiguous_amount") or 0
                ),
                "bank_recon_non_supplier_amount": float(
                    bank_reconciliation_audit.get("non_supplier_amount") or 0
                ),
                "bank_recon_unmatched_amount": float(
                    bank_reconciliation_audit.get("unmatched_amount") or 0
                ),
                "bank_recon_skipped_amount": float(
                    bank_reconciliation_audit.get("skipped_explicit_amount") or 0
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
                "retail_sales_row_count": int(retail_overall.get("row_count") or 0),
                "retail_sales_total_quantity": float(retail_overall.get("total_quantity") or 0),
                "retail_sales_revenue_ge": float(retail_overall.get("revenue_ge") or 0),
                "retail_sales_cost_ge": float(retail_overall.get("cost_ge") or 0),
                "retail_sales_profit_ge": float(retail_overall.get("profit_ge") or 0),
                "retail_sales_gross_margin_pct": float(
                    retail_overall.get("gross_margin_pct") or 0
                ),
                "retail_sales_distinct_object_count": int(
                    retail_overall.get("distinct_object_count") or 0
                ),
                "retail_sales_distinct_category_count": int(
                    retail_overall.get("distinct_category_count") or 0
                ),
                "retail_sales_distinct_product_count": int(
                    retail_overall.get("distinct_product_count") or 0
                ),
                "retail_sales_duplicate_excluded_file_count": int(
                    retail_duplicate_policy.get("excluded_file_count") or 0
                ),
            },
        }

    meta = data.setdefault("meta", {})
    meta["generated_at"] = generated_at
    meta["source_manifest_summary"] = source_manifest_summary
    meta["config_validation"] = {
        "ok": bool(config_validation.get("ok")),
        "warning_count": int(config_validation.get("warning_count") or 0),
        "error_count": int(config_validation.get("error_count") or 0),
    }
    empty_reconciliation_meta = empty_bank_reconciliation_audit()
    meta["payment_scope_summary"] = (
        data.get("bank_reconciliation_audit", {}).get("payment_scope_summary")
        or empty_reconciliation_meta.get("payment_scope_summary")
    )
    meta["truth_source_breakdown"] = (
        data.get("bank_reconciliation_audit", {}).get("truth_source_breakdown")
        or empty_reconciliation_meta.get("truth_source_breakdown")
        or {}
    )
    meta["truth_boundary_summary"] = (
        data.get("bank_reconciliation_audit", {}).get("truth_boundary_summary")
        or empty_reconciliation_meta.get("truth_boundary_summary")
        or {}
    )
    meta["strict_bank_only_total"] = float(
        (meta.get("payment_scope_summary") or {}).get("strict_bank_only_total") or 0
    )
    meta["combined_supplier_paid_total"] = float(
        (meta.get("payment_scope_summary") or {}).get("combined_supplier_paid_total") or 0
    )
    meta["manual_vs_bank_gap_total"] = round(
        float(meta.get("combined_supplier_paid_total") or 0)
        - float(meta.get("strict_bank_only_total") or 0),
        2,
    )
    meta["reproducibility_report"] = {
        "generated_at": generated_at,
        "source_manifest_summary": source_manifest_summary,
        "config_validation": meta.get("config_validation"),
        "bank_unmatched_total_ge": float(meta.get("bank_unmatched_total_ge") or 0),
        "bank_recon_ambiguous_amount": float(meta.get("bank_recon_ambiguous_amount") or 0),
        "bank_recon_unmatched_amount": float(meta.get("bank_recon_unmatched_amount") or 0),
        "truth_source_breakdown": meta.get("truth_source_breakdown") or {},
        "truth_boundary_summary": meta.get("truth_boundary_summary") or {},
        "imported_products_truncation_suspected": bool(
            (data.get("imported_products") or {}).get("truncation_suspected_any")
        ),
        "retail_sales_duplicate_policy_mode": str(
            ((data.get("retail_sales") or {}).get("duplicate_policy") or {}).get("mode")
            or ""
        ),
        "retail_sales_duplicate_excluded_file_count": int(
            (
                ((data.get("retail_sales") or {}).get("duplicate_policy") or {}).get(
                    "excluded_file_count"
                )
                or 0
            )
        ),
    }
    data["source_manifest"] = source_manifest

    # Keep raw POS lines only in-process for P&L building; do not leak them into public data.json.
    pos_terminal_pnl_bundle = {
        **pos_terminal_income_bundle,
        "pnl_lines": pos_terminal_all_rows,
    }
    data["monthly_pnl"] = build_monthly_pnl(
        pos_terminal_pnl_bundle,
        tbc_expenses_bundle,
        object_mapping,
        bog_expenses_bundle=bog_expenses_bundle,
    )
    data["financial_ratios"] = build_financial_ratios(
        data.get("monthly_pnl", []),
        supplier_aging_result.get("suppliers", []),
        data.get("ap_monthly_trend", []),
    )
    data["forecast"] = build_forecast(data.get("monthly_pnl", []))
    data["budget"] = build_budget(
        data.get("monthly_pnl", []),
        data.get("forecast", {}),
        budget_config,
    )
    data["company_valuation"] = build_company_valuation(
        data.get("monthly_pnl", []),
        data.get("financial_ratios", {}),
        data.get("forecast", {}),
        sector_benchmarks,
    )
    data["executive_summary"] = build_executive_summary(data)
    monthly_pnl_total_net = sum(
        float((m.get("total") or {}).get("net") or 0)
        for m in data["monthly_pnl"]
    )
    monthly_pnl_objects = _object_order_for_monthly_pnl(object_mapping)
    seen_monthly_objects = set(monthly_pnl_objects)
    for m in data["monthly_pnl"]:
        for obj in (m.get("objects") or {}).keys():
            if obj not in seen_monthly_objects:
                monthly_pnl_objects.append(obj)
                seen_monthly_objects.add(obj)
    print(
        "  monthly_pnl: "
        f"{len(data['monthly_pnl'])} თვე | "
        f"ჯამური net {monthly_pnl_total_net:,.2f} ₾ | "
        f"ობიექტები: {', '.join(monthly_pnl_objects)}"
    )
    ratios = data.get("financial_ratios") or {}
    company_ratios = ratios.get("company") or {}
    object_ratios = ratios.get("objects") or {}
    company_net_margin = float(
        company_ratios.get("net_margin_pct")
        if company_ratios.get("net_margin_pct") is not None
        else company_ratios.get("gross_margin_pct")
        or 0
    )
    oz_ratio = object_ratios.get(OBJECT_OZURGETI) or {}
    dv_ratio = object_ratios.get(OBJECT_DVABZU) or {}
    oz_margin = float(
        oz_ratio.get("net_margin_pct")
        if oz_ratio.get("net_margin_pct") is not None
        else oz_ratio.get("gross_margin_pct")
        or 0
    )
    dv_margin = float(
        dv_ratio.get("net_margin_pct")
        if dv_ratio.get("net_margin_pct") is not None
        else dv_ratio.get("gross_margin_pct")
        or 0
    )
    top_risk = (ratios.get("top_risk_suppliers") or [{}])[0]
    top_risk_org = str(top_risk.get("org") or "N/A")
    top_risk_debt = float(top_risk.get("total_debt") or 0)
    top_risk_days = top_risk.get("days_since_last")
    top_risk_days_text = f"{int(top_risk_days)}" if top_risk_days is not None else "0"
    print("Financial Ratios:")
    print(f"  Net Margin: {company_net_margin:.1f}%")
    print(f"  Payment Ratio: {float(company_ratios.get('payment_ratio_pct') or 0):.1f}%")
    print(f"  AP Days: {int(company_ratios.get('ap_days') or 0)} დღე")
    print(f"  Avg Monthly Net: {float(company_ratios.get('avg_monthly_net') or 0):,.0f} ₾")
    print(f"  ოზურგეთი net margin: {oz_margin:.1f}% | დვაბზუ net margin: {dv_margin:.1f}%")
    print(
        f"  TOP risk: [{top_risk_org}] {top_risk_debt:,.0f} ₾ ({top_risk_days_text} დღე)"
    )
    forecast_data = data.get("forecast") or {}
    forecast_months = ((forecast_data.get("forecast") or {}).get("months") or [])
    first_forecast = forecast_months[0] if forecast_months else {}
    first_forecast_total = first_forecast.get("total") or {}
    first_forecast_month = str(first_forecast.get("month") or "N/A")
    first_forecast_net = float(first_forecast_total.get("net") or 0)
    seasonality = forecast_data.get("seasonality") or {}
    strongest_month = seasonality.get("strongest_month") or {}
    weakest_month = seasonality.get("weakest_month") or {}
    yoy = forecast_data.get("yoy") or {}
    print(
        f"Forecast (SMA-6): {len(forecast_months)} თვე | "
        f"პირველი: {first_forecast_month} net ~{first_forecast_net:,.0f} ₾"
    )
    print(
        "Seasonality: "
        f"ძლიერი — [{str(strongest_month.get('label') or 'N/A')}] "
        f"({float(strongest_month.get('seasonality_index') or 0):.2f}) | "
        f"სუსტი — [{str(weakest_month.get('label') or 'N/A')}] "
        f"({float(weakest_month.get('seasonality_index') or 0):.2f})"
    )
    print(
        "YoY: "
        f"შემოსავალი {float(yoy.get('income_change_pct') or 0):+.1f}% | "
        f"ხარჯი {float(yoy.get('expenses_change_pct') or 0):+.1f}% | "
        f"net {float(yoy.get('net_change_pct') or 0):+.1f}%"
    )
    budget = data.get("budget") or {}
    annual_budget = budget.get("annual") or {}
    print("Budget:")
    for budget_year in ("2024", "2025"):
        year_data = annual_budget.get(budget_year) or {}
        plan_net = float((year_data.get("plan") or {}).get("net") or 0)
        actual_net = float((year_data.get("actual") or {}).get("net") or 0)
        variance_net = float((year_data.get("variance") or {}).get("net") or 0)
        variance_pct = (float(variance_net / plan_net) * 100.0) if plan_net else 0.0
        print(
            f"  {budget_year}: plan net {plan_net:,.0f} ₾ | actual net {actual_net:,.0f} ₾ | "
            f"variance {variance_net:,.0f} ₾ ({variance_pct:+.1f}%)"
        )
    ytd_budget = budget.get("ytd_summary") or {}
    ytd_year = str(ytd_budget.get("current_year") or pd.Timestamp.now().year)
    ytd_plan_net = float((ytd_budget.get("plan_ytd") or {}).get("net") or 0)
    ytd_actual_net = float((ytd_budget.get("actual_ytd") or {}).get("net") or 0)
    ytd_on_track = "yes" if bool(ytd_budget.get("on_track")) else "no"
    print(
        f"  {ytd_year} YTD: plan net {ytd_plan_net:,.0f} ₾ | "
        f"actual net {ytd_actual_net:,.0f} ₾ | on_track: {ytd_on_track}"
    )
    company_valuation = data.get("company_valuation") or {}
    valuation = company_valuation.get("valuation") or {}
    valuation_range = valuation.get("range") or {}
    swot = company_valuation.get("swot") or {}
    print("Company Valuation:")
    print(
        "  Sector Score: "
        f"{float(company_valuation.get('overall_sector_score') or 0):.1f} / 5.0 — "
        f"{str(company_valuation.get('overall_assessment_ka') or '')}"
    )
    print(
        "  Valuation Range: "
        f"{float(valuation_range.get('low') or 0):,.0f} ₾ — "
        f"{float(valuation_range.get('median') or 0):,.0f} ₾ — "
        f"{float(valuation_range.get('high') or 0):,.0f} ₾"
    )
    print(
        "  SWOT: "
        f"{len(swot.get('strengths') or [])} strengths, "
        f"{len(swot.get('weaknesses') or [])} weaknesses, "
        f"{len(swot.get('opportunities') or [])} opportunities, "
        f"{len(swot.get('threats') or [])} threats"
    )
    executive_summary = data.get("executive_summary") or {}
    audit_readiness = executive_summary.get("audit_readiness") or {}
    executive = executive_summary.get("executive") or {}
    executive_kpis = executive.get("kpis") or {}
    print("Executive Summary:")
    print(
        f"  Audit Grade: {str(audit_readiness.get('grade') or 'N/A')} "
        f"({int(audit_readiness.get('overall_score') or 0)}/100)"
    )
    print(f"  Headline: {str(executive.get('headline_ka') or '')}")
    print(f"  Key Decisions: {len(executive.get('key_decisions') or [])}")
    print(f"  Next Steps: {len(executive.get('next_steps') or [])}")
    print(f"  Valuation: {float(executive_kpis.get('valuation_median') or 0):,.0f} ₾")

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

    out_dir = get_dashboard_public_dir(script_dir)
    os.makedirs(out_dir, exist_ok=True)
    published = publish_download_excels(download_dir, out_dir)
    data["download_files"] = published.get("files", [])
    data["download_zip_file"] = published.get("zip_file", "")
    if isinstance(data.get("pos_terminal_income"), dict):
        data["pos_terminal_income"].pop("pnl_lines", None)
    artifact_dir = get_dashboard_tab_data_dir(script_dir)
    artifact_dir_rel = os.path.relpath(artifact_dir, script_dir).replace("\\", "/")
    # Pre-rendered JSON for STATIC_RESPONSE_TABS only. Targeted tabs (e.g. waybills with
    # filters; imported_products_supplier_detail / imported_products_product_detail) are
    # built at request time in server.get_tab_payload from *_source artifacts.
    artifacts = build_static_api_artifacts(data)
    api_artifact_validation = validate_api_artifacts(artifacts)
    artifact_manifest = write_api_artifacts(artifact_dir, artifacts)
    data["meta"]["api_artifact_validation"] = {
        "ok": bool(api_artifact_validation.get("ok")),
        "warning_count": int(api_artifact_validation.get("warning_count") or 0),
        "error_count": int(api_artifact_validation.get("error_count") or 0),
    }
    data["meta"]["api_artifact_manifest"] = {
        **artifact_manifest,
        "artifact_dir": artifact_dir_rel,
        "artifacts": {
            name: {
                **info,
                "path": (
                    os.path.relpath(str(info.get("path") or ""), script_dir).replace(
                        "\\", "/"
                    )
                    if str(info.get("path") or "").strip()
                    else ""
                ),
            }
            for name, info in sorted((artifact_manifest.get("artifacts") or {}).items())
        },
    }
    out_file = get_dashboard_data_path(script_dir)
    
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Data generated at {out_file}")
    size_mb = float(os.path.getsize(out_file) / (1024 * 1024))
    print(f"data.json size: {size_mb:.2f} MB")
    print(
        "API artifacts: "
        f"{data['meta']['api_artifact_manifest']['artifact_count']} ფაილი | "
        f"errors={data['meta']['api_artifact_validation']['error_count']} | "
        f"warnings={data['meta']['api_artifact_validation']['warning_count']}"
    )

if __name__ == "__main__":
    run()
