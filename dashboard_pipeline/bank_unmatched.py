"""
Bank unmatched transaction analysis: auto-categorization rules,
dynamic grouping, manual overrides, and Excel exports.
"""
import os
import re
from collections import defaultdict, Counter

from dashboard_pipeline.logging_config import get_logger
from dashboard_pipeline.constants import BANK_UNMATCHED_LEDGER_NOTE_KA
from dashboard_pipeline.file_utils import _save_excel
from dashboard_pipeline.config_loaders import load_unmatched_overrides

logger = get_logger(__name__)

import json


def _rules_from_tbc_expense_json_for_unmatched(script_dir):
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
            "keywords": [str(p).lower() for p in c.get("match_substrings", []) if str(p).strip()],
            "keywords_all": [str(p).lower() for p in c.get("match_all_substrings", []) if str(p).strip()],
            "iban_hints": [str(p) for p in c.get("iban_hints", []) if str(p).strip()],
        }
        if cid == "salary_payments":
            for extra in ("salary", "payroll"):
                el = extra.lower()
                if el not in rule["keywords"]:
                    rule["keywords"].append(el)
        out.append(rule)
    return out


_EXTRA_AUTO_UNMATCHED_RULES = [
    {"id": "rent_known_landlord_ibans", "label_ka": "იჯარა — ცნობილი მიმღების ანგარიში (IBAN)", "confidence": "high",
     "keywords": [], "keywords_all": [], "iban_hints": ["GE60BG0000000667583800", "GE78BG0000000269727500", "GE81BG0000000890516000"]},
    {"id": "cashback_foodmart", "label_ka": "ქეშბექი (შპს ფუდმარტი)", "confidence": "high",
     "keywords": ["ფუდმარტ", "foodmart", "ქეშბექ", "cashback", "cash back"], "keywords_all": [], "iban_hints": []},
    {"id": "rent_related", "label_ka": "იჯარა/ქონების ხარჯები", "confidence": "medium",
     "keywords": ["იჯარა", "rent", "lease", "ქონების", "არენდა"], "keywords_all": [], "iban_hints": []},
    {"id": "tax_and_budget", "label_ka": "ბიუჯეტი / გადასახადები (სახელმწიფო — RS, ხაზინა)", "confidence": "medium",
     "keywords": ["საშემოსავლო", "გადასახად", "ბიუჯეტ", "revenue service", "rs.ge", "tax", "treasury", "ხაზინ", "tresge", "საბიუჯეტო"],
     "keywords_all": [], "iban_hints": []},
    {"id": "loan_and_finance", "label_ka": "სესხი/ფინანსური ვალდებულებები", "confidence": "medium",
     "keywords": ["სესხ", "loan", "credit", "interest", "პროცენტ"], "keywords_all": [], "iban_hints": []},
    {"id": "cash_withdrawal", "label_ka": "ნაღდი განაღდება / ბანკომატი", "confidence": "high",
     "keywords": ["განაღდება", "atm", "bankomati", "ბანკომატი", "mcc:6011", "cash withdrawal", "bankomat"],
     "keywords_all": [], "iban_hints": []},
    {"id": "card_purchase_expense", "label_ka": "ბარათით შეძენა / საოპერაციო ხარჯი (სხვა მერჩანტი)", "confidence": "medium",
     "keywords": ["ოპერაცია:გადახდა - თანხა", "ობიექტი:", "gorgia", "jibe", "ltd me-va", "sakancelario"],
     "keywords_all": [], "iban_hints": []},
    {"id": "rs_budget_payments", "label_ka": "RS — საბიუჯეტო გადარიცხვები / სახელმწიფო ხაზინა", "confidence": "medium",
     "keywords": ["rs", "revenue service", "ge60bg0000000667583800rs", "ge04bg0000000201978600rs",
                   "საბიუჯეტო გადარიცხვ", "ხაზინის ერთიანი", "გადასახადების ერთიანი კოდი", "tresge22", "სახაზინო"],
     "keywords_all": [], "iban_hints": []},
    {"id": "card_network_settlement", "label_ka": "ბარათების ქსელური ოპერაციები (VISA/MC)", "confidence": "low",
     "keywords": ["tbcbank_ის visa/mc", "tbcbank_ის ბანკომატებში", "visa ბარათებით სავაჭრო ობიექტებში", "mc ბარათებით"],
     "keywords_all": [], "iban_hints": []},
    {"id": "utilities_related", "label_ka": "კომუნალური და მობილური (ზოგადი)", "confidence": "medium",
     "keywords": ["კომუნალური", "utility", "ელექტრო", "წყალი", "გაზი", "მობილური", "ჯარიმ"],
     "keywords_all": [], "iban_hints": []},
    {"id": "bank_fees", "label_ka": "ბანკის საკომისიო/მომსახურება (სხვა)", "confidence": "high",
     "keywords": ["საკომისიო", "commission", "service fee", "მომსახურების", "bank fee", "processing fee"],
     "keywords_all": [], "iban_hints": []},
]

_cached_auto_unmatched_rules = None
_cached_auto_unmatched_script_dir = None


def get_auto_unmatched_category_rules(script_dir=None):
    global _cached_auto_unmatched_rules, _cached_auto_unmatched_script_dir
    if script_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    if _cached_auto_unmatched_rules is not None and _cached_auto_unmatched_script_dir == script_dir:
        return _cached_auto_unmatched_rules
    rules = _rules_from_tbc_expense_json_for_unmatched(script_dir)
    rules.extend(_EXTRA_AUTO_UNMATCHED_RULES)
    _cached_auto_unmatched_rules = rules
    _cached_auto_unmatched_script_dir = script_dir
    return rules


def _bank_unmatched_sort_key(cat):
    from dashboard_pipeline.constants import BANK_UNMATCHED_CATEGORY_ORDER
    cid = str(cat.get("id") or "")
    rank = int(BANK_UNMATCHED_CATEGORY_ORDER.get(cid, 500))
    total = float(cat.get("total_ge") or 0)
    return (rank, -total, cid)


def _unmatched_blob(row):
    fields = [row.get("მიმღები_სახელი", ""), row.get("ოპერაციის_შინაარსი", ""),
              row.get("დანიშნულება", ""), row.get("მიზეზი", ""),
              row.get("საგადასახადო_ID", ""), row.get("ფაილი", "")]
    return " ".join(str(x) for x in fields if x).lower()


def _rule_matches_unmatched(rule, blob_lower):
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
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
            promoted.append({"id": cid, "label_ka": lbl, "confidence": "low",
                             "total_ge": float(total), "line_count": len(rows),
                             "rows_preview": rows[:120], "_rows_all": rows})
    used = set()
    for c in promoted:
        for r in c["_rows_all"]:
            used.add(id(r))
    for r in unclassified_rows:
        if id(r) not in used:
            leftovers.append(r)
    return promoted, leftovers


def _signature_from_unclassified_row(row):
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
            return {"id": "other_unclassified", "label_ka": "სხვა (ხელით reject)", "confidence": "low",
                    "manual_decision": "reject", "manual_rule_note": str(rr.get("note") or f"reject #{idx}")}
    for idx, ar in enumerate(overrides.get("approvals", []), start=1):
        if _row_matches_override(row, ar):
            cid = str(ar.get("category_id") or "").strip() or "manual_approved"
            label = str(ar.get("label_ka") or "").strip() or "ხელით დამტკიცებული კატეგორია"
            conf = str(ar.get("confidence") or "high").lower().strip()
            if conf not in {"high", "medium", "low"}:
                conf = "high"
            return {"id": cid, "label_ka": label, "confidence": conf,
                    "manual_decision": "approve", "manual_rule_note": str(ar.get("note") or f"approve #{idx}")}
    return None


def _top_unclassified_signatures(rows, limit=20):
    cnt = Counter()
    sums = defaultdict(float)
    for r in rows:
        sig = _signature_from_unclassified_row(r)
        amt = float(r.get("თანხა") or 0)
        cnt[sig] += 1
        sums[sig] += amt
    ordered = sorted(cnt.keys(), key=lambda k: (sums[k], cnt[k]), reverse=True)
    return [{"signature": k, "line_count": int(cnt[k]), "total_ge": float(sums[k])} for k in ordered[:limit]]


def analyze_bank_unmatched_rows(unmatched_rows):
    if not unmatched_rows:
        return {"total_ge": 0.0, "line_count": 0, "categorized_total_ge": 0.0,
                "uncategorized_total_ge": 0.0, "categories": [],
                "top_unclassified_preview": [], "ledger_note_ka": BANK_UNMATCHED_LEDGER_NOTE_KA}

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
            manual_override_audit_rows.append({
                "manual_decision": manual.get("manual_decision"),
                "manual_rule_note": manual.get("manual_rule_note", ""),
                "assigned_category_id": cid, "assigned_label_ka": label, "confidence": conf,
                "ბანკი": row.get("ბანკი", ""), "ფაილი": row.get("ფაილი", ""),
                "თარიღი": row.get("თარიღი", ""), "თანხა": float(row.get("თანხა") or 0),
                "საგადასახადო_ID": row.get("საგადასახადო_ID", ""),
                "მიმღები_სახელი": row.get("მიმღები_სახელი", ""),
                "ოპერაციის_შინაარსი": row.get("ოპერაციის_შინაარსი", ""),
                "მიზეზი": row.get("მიზეზი", ""),
                "signature": _signature_from_unclassified_row(row),
            })
        else:
            cid, label, conf = _auto_category_from_unmatched_row(row)
        if cid not in bucket:
            bucket[cid] = {"id": cid, "label_ka": label, "confidence": conf,
                           "total_ge": 0.0, "line_count": 0, "rows_preview": []}
        amt = float(row.get("თანხა") or 0)
        bucket[cid]["total_ge"] += amt
        bucket[cid]["line_count"] += 1
        if len(bucket[cid]["rows_preview"]) < 120:
            bucket[cid]["rows_preview"].append(row)

    cats = sorted([{"id": v["id"], "label_ka": v["label_ka"], "confidence": v.get("confidence", "medium"),
                    "total_ge": float(v["total_ge"]), "line_count": int(v["line_count"]),
                    "rows_preview": v["rows_preview"]} for v in bucket.values()], key=_bank_unmatched_sort_key)

    unc = next((c for c in cats if c["id"] == "other_unclassified"), None)
    dynamic_promoted_total = 0.0
    dynamic_promoted_lines = 0
    if unc and unc.get("rows_preview"):
        promoted, unc_left = _promote_dynamic_unclassified_groups(unc["rows_preview"])
        dynamic_promoted_total = sum(float(c["total_ge"]) for c in promoted)
        dynamic_promoted_lines = sum(int(c["line_count"]) for c in promoted)
        unc["rows_preview"] = unc_left[:120]
        unc["total_ge"] = float(sum(float(r.get("თანხა") or 0) for r in unc_left))
        unc["line_count"] = len(unc_left)
        cats.extend([{"id": c["id"], "label_ka": c["label_ka"], "confidence": c.get("confidence", "low"),
                      "total_ge": float(c["total_ge"]), "line_count": int(c["line_count"]),
                      "rows_preview": c["rows_preview"]} for c in promoted])
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
        "total_ge": float(total_ge), "line_count": len(unmatched_rows),
        "categorized_total_ge": float(total_ge - unc_total), "uncategorized_total_ge": float(unc_total),
        "manual_override_approved_lines": int(manual_approve_lines),
        "manual_override_rejected_lines": int(manual_reject_lines),
        "manual_override_audit_rows": manual_override_audit_rows,
        "dynamic_promoted_total_ge": float(dynamic_promoted_total),
        "dynamic_promoted_line_count": int(dynamic_promoted_lines),
        "confidence_totals": {"high": float(confidence_totals.get("high", 0.0)),
                              "medium": float(confidence_totals.get("medium", 0.0)),
                              "low": float(confidence_totals.get("low", 0.0))},
        "categories": cats, "top_unclassified_preview": unc_preview,
        "top_unclassified_signatures": top_unc, "ledger_note_ka": BANK_UNMATCHED_LEDGER_NOTE_KA,
    }


def write_bank_unmatched_excel(unmatched_rows, download_dir):
    path = _save_excel(unmatched_rows, download_dir, "ბანკი_არამიბმული_ხაზები.xlsx")
    if path:
        total = sum(float(r.get("თანხა") or 0) for r in unmatched_rows)
        logger.info(f"  Excel (არამიბმული ბანკი) → {path} ({len(unmatched_rows)} ხაზი, {total:,.2f} ₾)")


def write_bank_unmatched_categories_excel(analysis, download_dir):
    cats = analysis.get("categories") or []
    rows = [{"კატეგორია": c.get("label_ka", c.get("id", "")), "კატეგორია_id": c.get("id", ""),
             "სანდოობა": c.get("confidence", "low"), "ხაზების რაოდენობა": int(c.get("line_count") or 0),
             "ჯამი": float(c.get("total_ge") or 0)} for c in cats]
    path = _save_excel(rows, download_dir, "ბანკი_არამიბმული_კატეგორიები.xlsx")
    if path:
        logger.info(f"  Excel (არამიბმული კატეგორიები) → {path}")


def write_bank_unclassified_top_excel(analysis, download_dir):
    rows = analysis.get("top_unclassified_signatures") or []
    path = _save_excel(rows, download_dir, "ბანკი_სხვა_top20.xlsx")
    if path:
        logger.info(f"  Excel (არამიბმული სხვა TOP20) → {path}")


def write_bank_overrides_audit_excel(analysis, download_dir):
    rows = analysis.get("manual_override_audit_rows") or []
    path = _save_excel(rows, download_dir, "ბანკი_overrides_audit.xlsx")
    if path:
        logger.info(f"  Excel (overrides audit) → {path}")
