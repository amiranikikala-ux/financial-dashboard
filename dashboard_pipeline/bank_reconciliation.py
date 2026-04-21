"""
Bank reconciliation: get_bank_payments + all matching/classification helpers.

Extracted from generate_dashboard_data.py lines 7069-8371.
"""
import json
import os
from collections import defaultdict

import pandas as pd

from dashboard_pipeline.bank_unmatched import (
    _auto_category_from_unmatched_row,
    _extract_ibans_from_text,
    _rule_matches_unmatched,
    get_auto_unmatched_category_rules,
)
from dashboard_pipeline.config_loaders import (
    load_supplier_matching_registry,
    supplier_matching_registry_path,
)
from dashboard_pipeline.constants import (
    BOG_RECEIVER_ID_TO_RS_TAX_ID,
    DEFAULT_RECON_SCORE_ACCEPT_THRESHOLD,
    DEFAULT_RECON_SCORE_GAP_THRESHOLD,
    NON_SUPPLIER_CATEGORY_IDS,
    NON_SUPPLIER_FINAL_CONFIDENCE,
    PARTNER_IBAN_TO_RS_TAX_ID,
    RECON_FINAL_STATUSES,
    RECON_MATCH_STATUSES,
)
from dashboard_pipeline.date_filters import parse_source_datetime
from dashboard_pipeline.file_utils import (
    _excel_cell,
    _find_excel_column_danishnuleba,
    _find_tbc_additional_purpose_column,
    _find_tbc_partner_column,
    _normalize_iban_ge,
    _save_excel,
    clean_id,
    find_header_row,
    list_bog_bank_statement_xlsx,
    list_tbc_bank_statement_xlsx,
    verify_bank_debit_totals,
)
from dashboard_pipeline.logging_config import get_logger
from dashboard_pipeline.manual_payments import load_manual_payments
from dashboard_pipeline.supplier_matching import (
    _build_truth_boundary_summary_for_supplier_master,
    _build_waybill_reference_index,
    _extract_candidate_name_segments,
    _extract_tax_ids_from_text,
    _extract_waybill_refs_from_text,
    _infer_truth_source_label_from_scored_candidate,
    _normalize_account_hint,
    _supplier_truth_context,
    build_supplier_master,
    canonical_tax_id_from_bog_receiver,
    infer_bog_receiver_id_to_rs_tax_id,
    match_partner_to_id_legacy,
    normalize_name,
)
from dashboard_pipeline.truth_boundary import (
    build_payment_scope_summary,
    build_reconciliation_provenance,
    build_truth_boundary_summary,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# _supplier_display_name
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _build_reconciliation_line
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _line_to_row_for_category
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _candidate_preview_list
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _finalize_reconciliation_line
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Excel helpers
# ---------------------------------------------------------------------------

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


def _normalize_supplier_payment_row_date(value):
    ts = parse_source_datetime(value)
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def build_strict_supplier_payment_rows(rows):
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        matched_tax_id = str(row.get("matched_tax_id") or "").strip()
        if not matched_tax_id:
            continue
        out.append(
            {
                "row_date": _normalize_supplier_payment_row_date(row.get("row_date")),
                "amount": float(row.get("amount") or 0),
                "matched_tax_id": matched_tax_id,
                "matched_supplier_name": str(row.get("matched_supplier_name") or ""),
                "status": str(row.get("status") or ""),
                "source_bank": str(row.get("source_bank") or ""),
                "matched_by": str(row.get("matched_by") or ""),
                "confidence": str(row.get("confidence") or ""),
                "truth_source_label": str(row.get("truth_source_label") or ""),
                "supplier_truth_summary": str(row.get("supplier_truth_summary") or ""),
                "official_name_truth_source": str(
                    row.get("official_name_truth_source") or ""
                ),
                "payment_origin": "strict_bank",
            }
        )
    return out


def _write_bank_status_excel(rows, download_dir, filename, title_ka):
    excel_rows = [_line_for_excel(r) for r in (rows or [])]
    path = _save_excel(excel_rows, download_dir, filename)
    if path:
        logger.info(
            f"  Excel ({title_ka}) \u2192 {path} "
            f"({len(rows)} \u10ee\u10d0\u10d6\u10d8, {sum(float(r.get('amount') or 0) for r in rows):,.2f} \u20be)"
        )


def write_bank_ambiguous_excel(rows, download_dir):
    _write_bank_status_excel(rows, download_dir, "\u10d1\u10d0\u10dc\u10d9\u10d8_\u10d1\u10e3\u10dc\u10d3\u10dd\u10d5\u10d0\u10dc\u10d8_\u10db\u10d8\u10d1\u10db\u10d4\u10d1\u10d8.xlsx", "\u10d1\u10e3\u10dc\u10d3\u10dd\u10d5\u10d0\u10dc\u10d8 \u10db\u10d8\u10d1\u10db\u10d4\u10d1\u10d8")


def write_bank_non_supplier_excel(rows, download_dir):
    _write_bank_status_excel(
        rows, download_dir, "\u10d1\u10d0\u10dc\u10d9\u10d8_non_supplier_\u10ee\u10d0\u10d6\u10d4\u10d1\u10d8.xlsx", "non_supplier \u10ee\u10d0\u10d6\u10d4\u10d1\u10d8"
    )


def write_bank_matched_high_excel(rows, download_dir):
    _write_bank_status_excel(
        rows,
        download_dir,
        "\u10d1\u10d0\u10dc\u10d9\u10d8_\u10db\u10d0\u10e6\u10d0\u10da\u10d8_\u10e1\u10d0\u10dc\u10d3\u10dd\u10dd\u10d1\u10d8\u10e1_\u10db\u10d8\u10d1\u10db\u10d4\u10d1\u10d8.xlsx",
        "\u10db\u10d0\u10e6\u10d0\u10da\u10d8 \u10e1\u10d0\u10dc\u10d3\u10dd\u10dd\u10d1\u10d8\u10e1 \u10db\u10d8\u10d1\u10db\u10d4\u10d1\u10d8",
    )


# ---------------------------------------------------------------------------
# _legacy_match_from_line
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _build_reconciliation_audit
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _compute_supplier_delta_vs_legacy
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# empty_bank_reconciliation_audit
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# get_bank_payments  (main entry point)
# ---------------------------------------------------------------------------

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

    logger.info(
        "Supplier reconciliation master: %s suppliers, %s legal-name keys, %s alias keys",
        len(supplier_master.get('suppliers_by_id') or {}),
        len(legal_name_to_id), len(alias_union),
    )
    logger.info("  Waybill refs indexed: %s", len((waybill_index.get('known_refs') or [])))
    logger.info(
        "  Truth boundary: registry primary=%s | RS backstop=%s | legacy audit-only=%s",
        truth_boundary_summary.get('registry_primary_supplier_count', 0),
        truth_boundary_summary.get('rs_backstop_supplier_count', 0),
        truth_boundary_summary.get('legacy_truth_assist_supplier_count', 0),
    )

    raw_lines = []
    logger.info("Reading BOG bank statements...")
    for f in list_bog_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = df.columns
            debit_col = next(
                (c for c in cols if "\u10d3\u10d4\u10d1\u10d4\u10e2\u10d8" in str(c) and "\u10d1\u10e0\u10e3\u10dc\u10d5\u10d0" not in str(c)),
                None,
            )
            if not debit_col:
                continue
            id_col = next((c for c in cols if "\u10db\u10d8\u10db\u10e6\u10d4\u10d1\u10d8\u10e1 \u10e1\u10d0\u10d8\u10d3\u10d4\u10dc\u10e2\u10d8\u10e4\u10d8\u10d9\u10d0\u10ea\u10d8\u10dd" in str(c)), None)
            name_col = next((c for c in cols if "\u10db\u10d8\u10db\u10e6\u10d4\u10d1\u10d8\u10e1 \u10d3\u10d0\u10e1\u10d0\u10ee\u10d4\u10da\u10d4\u10d1\u10d0" in str(c)), None)
            desc_col = next((c for c in cols if "\u10dd\u10de\u10d4\u10e0\u10d0\u10ea\u10d8\u10d8\u10e1 \u10e8\u10d8\u10dc\u10d0\u10d0\u10e0\u10e1\u10d8" in str(c)), None)
            purpose_col = _find_excel_column_danishnuleba(cols)
            account_col = next(
                (c for c in cols if "\u10db\u10d8\u10db\u10e6\u10d4\u10d1\u10d8\u10e1 \u10d0\u10dc\u10d2\u10d0\u10e0\u10d8\u10e8\u10d8\u10e1 \u10dc\u10dd\u10db\u10d4\u10e0\u10d8" in str(c)),
                None,
            )
            date_col = next((c for c in cols if "\u10d7\u10d0\u10e0\u10d8\u10e6\u10d8" in str(c)), None)
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
            logger.error("Reading BOG %s: %s", f, e)

    logger.info("Reading TBC bank statements...")
    for f in list_tbc_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = df.columns
            debit_col = next((c for c in cols if "\u10d2\u10d0\u10e1\u10e3\u10da\u10d8 \u10d7\u10d0\u10dc\u10ee\u10d0" in str(c)), None)
            if not debit_col:
                continue
            id_col = next(
                (c for c in cols if "\u10de\u10d0\u10e0\u10e2\u10dc\u10d8\u10dd\u10e0\u10d8\u10e1 \u10e1\u10d0\u10d2\u10d0\u10d3\u10d0\u10e1\u10d0\u10ee\u10d0\u10d3\u10dd \u10d9\u10dd\u10d3\u10d8" in str(c)),
                None,
            )
            partner_col = _find_tbc_partner_column(cols)
            purpose_col = _find_excel_column_danishnuleba(cols)
            extra_purpose_col = _find_tbc_additional_purpose_column(cols)
            account_col = next((c for c in cols if "\u10de\u10d0\u10e0\u10e2\u10dc\u10d8\u10dd\u10e0\u10d8\u10e1 \u10d0\u10dc\u10d2\u10d0\u10e0\u10d8\u10e8\u10d8" in str(c)), None)
            date_col = next((c for c in cols if "\u10d7\u10d0\u10e0\u10d8\u10e6\u10d8" in str(c)), None)
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
            logger.error("Reading TBC %s: %s", f, e)

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
        logger.warning(
            "bank_reconciliation_audit balance mismatch: %s",
            f"{(audit_block.get('balance_check_summary') or {}).get('delta', 0):,.2f}",
        )

    logger.info(
        "Reconciliation strict: matched=%s (%s) | ambiguous=%s (%s) | unmatched=%s (%s) | non_supplier=%s (%s) | skipped=%s (%s)",
        audit_block['matched_high_confidence_rows'],
        f"{audit_block['matched_high_confidence_amount']:,.2f}",
        audit_block['ambiguous_rows'], f"{audit_block['ambiguous_amount']:,.2f}",
        audit_block['unmatched_rows'], f"{audit_block['unmatched_amount']:,.2f}",
        audit_block['non_supplier_rows'], f"{audit_block['non_supplier_amount']:,.2f}",
        audit_block['skipped_explicit_rows'], f"{audit_block['skipped_explicit_amount']:,.2f}",
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
        logger.info(
            "\u10ee\u10d4\u10da\u10d8\u10d7 \u10d2\u10d0\u10d3\u10d0\u10ee\u10d3\u10d4\u10d1\u10d8 (manual_payments.csv): %s ID, +%s \u2192 \u10e1\u10e3\u10da: %s",
            len(manual_map), f"{man_sum:,.2f}", f"{sum(payments.values()):,.2f}",
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
            rr["\u10e1\u10e2\u10d0\u10e2\u10e3\u10e1\u10d8"] = row.get("status", "")
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
