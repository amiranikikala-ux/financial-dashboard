"""
Analytics builder functions: P&L, aging, ratios, forecast, budget,
company valuation, and executive summary.

Extracted from generate_dashboard_data.py lines 2545-4437.
"""
from collections import Counter, defaultdict

import pandas as pd

from dashboard_pipeline.constants import (
    ACCOUNTING_ROLE_OPERATING,
    BOG_EXPENSES_LEDGER_NOTE_KA,
    OBJECT_COMMON,
    OBJECT_DVABZU,
    OBJECT_OZURGETI,
    OBJECT_UNALLOCATED,
    TBC_EXPENSES_LEDGER_NOTE_KA,
    _clone_default_budget_config,
    _clone_default_object_mapping,
    _clone_default_sector_benchmarks,
    _empty_aging_summary,
    _extract_tax_id_from_org,
    _month_key,
    _month_sort_key,
    _monthly_summary,
    _object_order_for_monthly_pnl,
    _parse_rs_datetime,
    _pick_aging_bucket,
    _to_waybills_df,
    detect_object,
)
from dashboard_pipeline.export_artifacts import (
    publish_download_excels as _publish_download_excels_external,
)


# ---------------------------------------------------------------------------
# build_monthly_pnl
# ---------------------------------------------------------------------------

def _retail_sales_max_pos_by_object_month(retail_sales_bundle):
    """Per-(month, object) MAX POS revenue from retail_sales bundle.

    Mirror of vat_reconciliation._retail_sales_by_object_month so cashreg_in
    in monthly_pnl matches the audit-tested formula in vat_reconciliation
    (Sprint 5.8). Returns {"YYYY-MM": {object_label: revenue_ge}}; empty dict
    when bundle is None or has no by_object_by_month section.
    """
    out = defaultdict(dict)
    rows = (retail_sales_bundle or {}).get("by_object_by_month") or []
    for row in rows:
        month = str((row or {}).get("month") or "")
        if len(month) < 7 or month[4] != "-":
            continue
        obj = str((row or {}).get("object") or "").strip()
        if not obj:
            continue
        try:
            revenue = float(row.get("revenue_ge") or 0)
        except (TypeError, ValueError):
            continue
        out[month][obj] = revenue
    return dict(out)


def _retail_sales_cogs_by_object_month(retail_sales_bundle):
    """Per-(month, object) COGS (cost of goods sold) from retail_sales bundle.

    Returns {"YYYY-MM": {object_label: cost_ge}}; empty dict when bundle is
    None or has no by_object_by_month section. Used to surface real gross
    margin in monthly_pnl. Matches MegaPlus per-sale `cost_paid` aggregation.
    """
    out = defaultdict(dict)
    rows = (retail_sales_bundle or {}).get("by_object_by_month") or []
    for row in rows:
        month = str((row or {}).get("month") or "")
        if len(month) < 7 or month[4] != "-":
            continue
        obj = str((row or {}).get("object") or "").strip()
        if not obj:
            continue
        try:
            cost = float(row.get("cost_ge") or 0)
        except (TypeError, ValueError):
            continue
        out[month][obj] = cost
    return dict(out)


def _supplier_payments_by_month(supplier_payment_lines):
    """Total supplier payments per month from supplier_payment_lines index.

    supplier_payment_lines is {tax_id: [{date, amount, source, purpose}, ...]}
    as built by build_supplier_payment_lines. Returns {"YYYY-MM": total_ge}.
    Per-object split is not available because purpose-text → object resolution
    is unreliable; total-level only for now.
    """
    out = defaultdict(float)
    if not supplier_payment_lines:
        return dict(out)
    for _tax_id, lines in supplier_payment_lines.items():
        for line in lines or []:
            date = str((line or {}).get("date") or "")
            if len(date) < 7:
                continue
            month = date[:7]
            try:
                amount = float(line.get("amount") or 0)
            except (TypeError, ValueError):
                continue
            out[month] += amount
    return dict(out)


def build_monthly_pnl(
    pos_bundle,
    tbc_expenses_bundle,
    object_mapping,
    bog_expenses_bundle=None,
    retail_sales_bundle=None,
    supplier_payment_lines=None,
):
    """
    თვიური P&L: POS შემოსავალი (ბანკი) + ნაღდი ფული (Megaplus სალარო) +
    TBC/BOG ხარჯები ობიექტების ჭრილში + COGS (Megaplus per-sale cost) +
    operating_expenses (bank outflows minus supplier payments).

    Two layers of P&L now coexist:

    Cash-flow layer (legacy, per-object):
      pos_income, cash_income, total_income, expenses, net
      `expenses` here = ALL bank outflows including supplier payments;
      `net` = total_income − expenses (cash burn, not real margin).

    Accrual layer (new, per-object cogs/gross_margin; total-only for the
    rest because supplier_payment_lines have no per-object info):
      cogs (per-obj + total) — from retail_sales by_object_by_month.cost_ge
      gross_margin (per-obj + total) = total_income − cogs
      supplier_payments (total) — sum of supplier_payment_lines per month
      operating_expenses (total) = expenses − supplier_payments
      net_profit (total) = gross_margin − operating_expenses
      gross_margin_pct, net_margin_pct (total)

    cashreg_in formula (per Sprint 5.8 vat_reconciliation): for each
    (month, object), `cash_income = max(0, max_pos − bank_card)`, where
    max_pos comes from retail_sales.by_object_by_month and bank_card is the
    POS terminal income aggregated from `pos_bundle.pnl_lines`. When
    retail_sales_bundle is None (older callers / fixtures), cash_income is
    0.0 and `total_income == pos_income` for backward compat. When
    supplier_payment_lines is None, supplier_payments is 0 and
    operating_expenses == expenses (legacy behaviour).
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

    max_pos_by_month = _retail_sales_max_pos_by_object_month(retail_sales_bundle)
    cogs_by_month = _retail_sales_cogs_by_object_month(retail_sales_bundle)
    supplier_payments_by_month = _supplier_payments_by_month(supplier_payment_lines)

    months = sorted(
        set(month_income.keys())
        | set(month_expenses.keys())
        | set(max_pos_by_month.keys()),
        key=_month_sort_key,
    )
    objects_order = _object_order_for_monthly_pnl(mapping)
    seen_objects = set(objects_order)
    dynamic_objects = set()
    for month in months:
        dynamic_objects.update(month_income[month].keys())
        dynamic_objects.update(month_expenses[month].keys())
        dynamic_objects.update(max_pos_by_month.get(month, {}).keys())
    for obj in sorted(dynamic_objects):
        if obj not in seen_objects:
            objects_order.append(obj)
            seen_objects.add(obj)

    out = []
    for month in months:
        month_objects = {}
        total_pos_income = 0.0
        total_cash_income = 0.0
        total_expenses = 0.0
        total_cogs = 0.0
        max_pos_for_month = max_pos_by_month.get(month, {})
        cogs_for_month = cogs_by_month.get(month, {})
        for obj in objects_order:
            pos_income = float(month_income[month].get(obj) or 0)
            expenses = float(month_expenses[month].get(obj) or 0)
            max_pos = float(max_pos_for_month.get(obj) or 0)
            cash_income = max(0.0, max_pos - pos_income)
            obj_total_income = pos_income + cash_income
            cogs = float(cogs_for_month.get(obj) or 0)
            gross_margin = obj_total_income - cogs
            total_pos_income += pos_income
            total_cash_income += cash_income
            total_expenses += expenses
            total_cogs += cogs
            month_objects[obj] = {
                "pos_income": pos_income,
                "cash_income": cash_income,
                "total_income": obj_total_income,
                "expenses": expenses,
                "net": float(obj_total_income - expenses),
                "cogs": cogs,
                "gross_margin": gross_margin,
            }
        total_income = total_pos_income + total_cash_income
        supplier_payments = float(supplier_payments_by_month.get(month) or 0)
        operating_expenses = total_expenses - supplier_payments
        gross_margin = total_income - total_cogs
        net_profit = gross_margin - operating_expenses
        gross_margin_pct = (
            round(gross_margin / total_income * 100, 2) if total_income else 0.0
        )
        net_margin_pct = (
            round(net_profit / total_income * 100, 2) if total_income else 0.0
        )
        out.append(
            {
                "month": month,
                "objects": month_objects,
                "total": {
                    "pos_income": float(total_pos_income),
                    "cash_income": float(total_cash_income),
                    "total_income": float(total_income),
                    "expenses": float(total_expenses),
                    "net": float(total_income - total_expenses),
                    "cogs": float(total_cogs),
                    "gross_margin": float(gross_margin),
                    "supplier_payments": supplier_payments,
                    "operating_expenses": float(operating_expenses),
                    "net_profit": float(net_profit),
                    "gross_margin_pct": gross_margin_pct,
                    "net_margin_pct": net_margin_pct,
                },
            }
        )
    return out


# ---------------------------------------------------------------------------
# build_supplier_aging
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# build_ap_monthly_trend
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# build_financial_ratios
# ---------------------------------------------------------------------------

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

    def _row_income(total_block):
        # Prefer the new total_income field (pos + cash); fall back to
        # pos_income for monthly_pnl rows produced before the Megaplus
        # cash wire-in.
        block = total_block or {}
        if "total_income" in block:
            return float(block.get("total_income") or 0)
        return float(block.get("pos_income") or 0)

    total_income = sum(_row_income(m.get("total")) for m in monthly_rows)
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
            _row_income((m.get("objects") or {}).get(obj_name)) for m in monthly_rows
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
        income_amount = _row_income(total_row)
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


# ---------------------------------------------------------------------------
# build_forecast
# ---------------------------------------------------------------------------

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
        _safe_amount(((h.get("row") or {}).get("total") or {}).get("total_income"))
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
            object_income_series[obj].append(_safe_amount(obj_data.get("total_income")))
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
        income = _safe_amount(total_data.get("total_income"))
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

    last_12_income = _sum_total(last_12_rows, "total_income")
    last_12_expenses = _sum_total(last_12_rows, "expenses")
    last_12_net = _sum_total(last_12_rows, "net")
    prev_12_income = _sum_total(prev_12_rows, "total_income")
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


# ---------------------------------------------------------------------------
# build_budget
# ---------------------------------------------------------------------------

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
                "income": _safe_float(total.get("total_income")),
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

    current_year = max(actual_yearly.keys()) if actual_yearly else int(pd.Timestamp.now().year)
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


# ---------------------------------------------------------------------------
# build_company_valuation
# ---------------------------------------------------------------------------

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
                _safe_float(((r.get("total") or {}).get("total_income")))
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


# ---------------------------------------------------------------------------
# build_executive_summary  +  helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Phase 3.5/3.7 — Dashboard widgets pre-compute
# ---------------------------------------------------------------------------

def build_dead_stock_summary(data, *, days_threshold=180, top_n=30):
    """Pre-compute Phase 2.11 dead-stock analysis for Dashboard widget.

    Reuses the AI tool `analyze_dead_stock` with a sensible default
    (180-day threshold + top-30 SKUs + all stores). Returns the full
    tool contract when both `imported_products` and `retail_sales`
    have been ingested; otherwise a minimal stub so the UI can render
    an empty-state banner.
    """
    from dashboard_pipeline.ai.dead_stock import analyze_dead_stock

    imported = (data or {}).get("imported_products") or {}
    retail = (data or {}).get("retail_sales") or {}
    if not imported.get("products") or not retail.get("by_product"):
        return {
            "available": False,
            "reason_ka": (
                "imported_products ან retail_sales ცარიელია — "
                "Dead Stock analysis ვერ გავუშვი."
            ),
        }

    result = analyze_dead_stock(
        data_loader=lambda: data,
        days_threshold=days_threshold,
        store=None,
        top_n=top_n,
    )
    if isinstance(result, dict) and "error" in result:
        return {
            "available": False,
            "reason_ka": result.get("error"),
            "hint_ka": result.get("hint"),
        }
    # Enrich with an `available` flag so the UI can detect stub vs real payload.
    result["available"] = True
    return result


def build_supplier_concentration(data, *, top_n=10):
    """Pre-compute Phase 2.12 supplier portfolio concentration for the widget.

    Reuses the AI tool `prepare_supplier_brief` in portfolio mode (no
    focus supplier = HHI + Top-N ranked by leverage × savings × spend).
    """
    from dashboard_pipeline.ai.supplier_brief import prepare_supplier_brief

    suppliers = (data or {}).get("suppliers") or []
    if not suppliers:
        return {
            "available": False,
            "reason_ka": (
                "suppliers ცარიელია — supplier concentration ვერ ავაგე."
            ),
        }

    result = prepare_supplier_brief(
        data_loader=lambda: data,
        top_n=top_n,
    )
    if isinstance(result, dict) and "error" in result:
        return {
            "available": False,
            "reason_ka": result.get("error"),
            "hint_ka": result.get("hint"),
        }
    result["available"] = True
    return result
