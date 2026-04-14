"""
Supplier matching: build_supplier_master, name matching, BOG receiver mapping,
truth layers, legacy assist.

Extracted from generate_dashboard_data.py lines 4709-5050 + 6490-6860.
"""
import glob
import re
from collections import defaultdict

import pandas as pd

from dashboard_pipeline.constants import (
    BOG_RECEIVER_ID_TO_RS_TAX_ID,
    PARTNER_IBAN_TO_RS_TAX_ID,
    _extract_tax_id_from_org,
)
from dashboard_pipeline.config_loaders import (
    load_supplier_matching_registry,
    supplier_matching_registry_path,
)
from dashboard_pipeline.file_utils import (
    _normalize_iban_ge,
    clean_id,
    find_header_row,
    list_bog_bank_statement_xlsx,
)
from dashboard_pipeline.truth_boundary import build_truth_boundary_summary


# ---------------------------------------------------------------------------
# normalize_name  (used by many functions below)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# თუ ტექსტში (სახელი/აღწერა/პარტნიორი) ერთ-ერთი ეს ქვესტრიქონია, სახელით RS ID-ზე მიბმა არ ხდება.
# იფქლის TBC-ში უმეტესობა „იფქლი, BAGAGE22…" ფორმატითაა — მათი ჩათვლით დავალიანება ემთხვევა ხელით დათვლილ ჯამს (~BOG ID + ყველა TBC „იფქლი").
# სხვა მომწოდებელზე ყალბი დამთხვევის გამოჩენისას შეგიძლია დაამატო მაგ. ('some_keyword',).
NAME_MATCH_BLOCK_SUBSTRINGS = ()


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


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# build_supplier_master
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _build_waybill_reference_index
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# BOG receiver mapping
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Name matching
# ---------------------------------------------------------------------------

def skip_name_only_supplier_match(text):
    """სრული ტექსტი ბანკის ველიდან — თუ ეჭვმიტნიურია, დავტოვოთ ID-ით ტრანზაქცია ან missed, არა fuzzy სახელით."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return False
    s = str(text).lower()
    return any(block in s for block in NAME_MATCH_BLOCK_SUBSTRINGS)


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


# ---------------------------------------------------------------------------
# Truth layer functions
# ---------------------------------------------------------------------------

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
