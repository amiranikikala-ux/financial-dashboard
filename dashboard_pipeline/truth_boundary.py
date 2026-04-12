from __future__ import annotations


def _distinct_non_empty(values):
    out = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def build_reconciliation_provenance(
    line,
    status,
    confidence,
    matched_by,
    truth_sources=None,
    truth_source_label="",
    supplier_truth_summary="",
):
    extracted_tax_ids = _distinct_non_empty(line.get("extracted_tax_ids") or [])
    extracted_ibans = _distinct_non_empty(line.get("extracted_ibans") or [])
    extracted_account_hints = _distinct_non_empty(
        line.get("extracted_account_hints") or []
    )
    waybill_hits = _distinct_non_empty(line.get("waybill_reference_hits") or [])
    truth_sources = _distinct_non_empty(truth_sources or [])
    evidence_sources = []
    if str(line.get("raw_tax_id") or "").strip():
        evidence_sources.append("raw_tax_id")
    if extracted_tax_ids:
        evidence_sources.append("extracted_tax_ids")
    if extracted_ibans:
        evidence_sources.append("extracted_ibans")
    if extracted_account_hints:
        evidence_sources.append("account_hints")
    if waybill_hits:
        evidence_sources.append("waybill_reference_hits")
    if str(line.get("legacy_matched_tax_id") or "").strip():
        evidence_sources.append("legacy_reference")
    if str(matched_by or "").strip():
        evidence_sources.append(f"decision:{matched_by}")
    return {
        "decision_scope": "strict_bank_reconciliation",
        "supplier_total_scope": (
            "strict_bank_only"
            if str(status or "") in {
                "matched_exact_id",
                "matched_exact_iban",
                "matched_exact_name",
                "matched_alias",
                "matched_scored_high",
            }
            else "excluded_from_supplier_paid_totals"
        ),
        "status": str(status or ""),
        "confidence": str(confidence or ""),
        "matched_by": str(matched_by or ""),
        "truth_source_label": str(truth_source_label or ""),
        "truth_sources": truth_sources,
        "supplier_truth_summary": str(supplier_truth_summary or ""),
        "evidence_sources": evidence_sources,
        "evidence_counts": {
            "tax_ids": len(extracted_tax_ids),
            "ibans": len(extracted_ibans),
            "account_hints": len(extracted_account_hints),
            "waybill_reference_hits": len(waybill_hits),
        },
    }


def build_truth_boundary_summary(
    primary_supplier_truth_path="",
    registry_primary_count=0,
    rs_backstop_count=0,
    legacy_assist_count=0,
):
    return {
        "summary_ka": (
            "Strict supplier matching-ში `supplier_matching_registry.json` არის primary truth. "
            "RS supplier names რჩება exact-name backstop-ად, ხოლო legacy IBAN/alias რუკები "
            "audit-only truth-assist layer-ია და strict supplier totals-ში არ ერთვება."
        ),
        "badges_ka": [
            "registry primary",
            "RS backstop",
            "legacy audit-only",
        ],
        "primary_supplier_truth_path": str(primary_supplier_truth_path or ""),
        "registry_primary_supplier_count": int(registry_primary_count or 0),
        "rs_backstop_supplier_count": int(rs_backstop_count or 0),
        "legacy_truth_assist_supplier_count": int(legacy_assist_count or 0),
        "strict_layers": [
            "bank.raw_tax_id",
            "bank.extracted_tax_id",
            "supplier_matching_registry.official_name",
            "supplier_matching_registry.alias",
            "supplier_matching_registry.person_alias",
            "supplier_matching_registry.iban",
            "supplier_matching_registry.account_hint",
            "rs_waybills.organization_name",
            "rs_waybills.waybill_reference",
        ],
        "legacy_audit_only_layers": [
            "legacy_truth_assist.partner_iban_map",
            "legacy_truth_assist.known_aliases",
        ],
    }


def describe_supplier_payment_scope(strict_bank_paid, manual_paid):
    strict_bank_paid = float(strict_bank_paid or 0)
    manual_paid = float(manual_paid or 0)
    combined = strict_bank_paid + manual_paid
    if strict_bank_paid > 0 and manual_paid > 0:
        scope = "strict_bank_plus_manual"
        note = "მომწოდებლის გადახდაში შედის strict ბანკი და manual/off-bank ჟურნალი."
    elif strict_bank_paid > 0:
        scope = "strict_bank_only"
        note = "მომწოდებლის გადახდა სრულად strict bank reconciliation-ით არის დაფარული."
    elif manual_paid > 0:
        scope = "manual_only"
        note = "გადახდა ჩანს მხოლოდ manual/off-bank ჟურნალში."
    elif combined < 0:
        scope = "negative_adjustment"
        note = "გადახდების ჯამი უარყოფითია; გადაამოწმე journal/bank corrections."
    else:
        scope = "unpaid_or_unmatched"
        note = "დადასტურებული supplier payment ამ მომწოდებელზე არ ჩანს."
    return {
        "payment_scope": scope,
        "payment_scope_note": note,
    }


def build_payment_scope_summary(
    strict_payments,
    manual_payments,
    supplier_names=None,
    preview_limit=20,
):
    strict_payments = {
        str(tax_id): float(amount or 0)
        for tax_id, amount in (strict_payments or {}).items()
        if str(tax_id or "").strip()
    }
    manual_payments = {
        str(tax_id): float(amount or 0)
        for tax_id, amount in (manual_payments or {}).items()
        if str(tax_id or "").strip()
    }
    supplier_names = supplier_names or {}
    strict_ids = {tid for tid, amount in strict_payments.items() if amount != 0}
    manual_ids = {tid for tid, amount in manual_payments.items() if amount != 0}
    overlap_ids = sorted(strict_ids & manual_ids)
    manual_only_ids = sorted(manual_ids - strict_ids)
    strict_only_ids = sorted(strict_ids - manual_ids)
    combined_ids = sorted(strict_ids | manual_ids)

    def _preview(ids, source):
        rows = []
        for tax_id in ids[:preview_limit]:
            strict_amount = float(strict_payments.get(tax_id) or 0)
            manual_amount = float(manual_payments.get(tax_id) or 0)
            rows.append(
                {
                    "tax_id": tax_id,
                    "supplier_name": supplier_names.get(tax_id) or tax_id,
                    "strict_bank_paid": strict_amount,
                    "manual_paid": manual_amount,
                    "combined_paid": strict_amount + manual_amount,
                    "source": source,
                }
            )
        return rows

    largest_manual = sorted(
        (
            {
                "tax_id": tax_id,
                "supplier_name": supplier_names.get(tax_id) or tax_id,
                "manual_paid": float(amount or 0),
                "strict_bank_paid": float(strict_payments.get(tax_id) or 0),
                "combined_paid": float(strict_payments.get(tax_id) or 0)
                + float(amount or 0),
            }
            for tax_id, amount in manual_payments.items()
            if float(amount or 0) != 0
        ),
        key=lambda item: abs(float(item.get("manual_paid") or 0)),
        reverse=True,
    )[:preview_limit]

    return {
        "strict_bank_only_total": round(
            sum(float(amount or 0) for amount in strict_payments.values()), 2
        ),
        "manual_journal_total": round(
            sum(float(amount or 0) for amount in manual_payments.values()), 2
        ),
        "combined_supplier_paid_total": round(
            sum(
                float(strict_payments.get(tax_id) or 0)
                + float(manual_payments.get(tax_id) or 0)
                for tax_id in combined_ids
            ),
            2,
        ),
        "strict_supplier_count": len(strict_ids),
        "manual_supplier_count": len(manual_ids),
        "combined_supplier_count": len(combined_ids),
        "strict_and_manual_overlap_count": len(overlap_ids),
        "manual_only_supplier_count": len(manual_only_ids),
        "strict_only_supplier_count": len(strict_only_ids),
        "scope_notes": [
            "strict_bank_only_total ითვლის მხოლოდ მაღალი სანდოობის bank-reconciled supplier matches-ს.",
            "manual_journal_total ითვლის მხოლოდ manual/off-bank journal adjustments-ს.",
            "combined_supplier_paid_total არის supplier-level total_paid მეტრიკების წყარო.",
        ],
        "manual_only_suppliers_preview": _preview(manual_only_ids, "manual_only"),
        "strict_only_suppliers_preview": _preview(strict_only_ids, "strict_bank_only"),
        "strict_and_manual_overlap_preview": _preview(
            overlap_ids, "strict_bank_plus_manual"
        ),
        "largest_manual_adjustments_preview": largest_manual,
    }
