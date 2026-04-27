from __future__ import annotations

import os
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from dashboard_pipeline.config_loaders import load_object_mapping
from dashboard_pipeline.constants import (
    IMPORTED_PRODUCTS_CSV_ENCODINGS,
    IMPORTED_PRODUCTS_SHEET_NAME,
    OBJECT_UNALLOCATED,
    _safe_text,
)
from dashboard_pipeline.sources import list_imported_product_files


DEFAULT_TOP_N = 20
MAX_TOP_N = 100
DEFAULT_MAX_ROWS = 100_000
MAX_SCAN_ROWS = 500_000
DEFAULT_MIN_SIMILARITY = 0.82
DESTINATION_COLUMN = "ტრანსპორტირების დასრულება"
SOURCE_LABEL = "data_quality_guard"


_LEGAL_PREFIX_RE = re.compile(
    r"^(შპს|სს|ს\.ს|ი/მ|ი\.მ|ინდ\.მეწარმე|llc|ltd)\s+",
    re.IGNORECASE,
)
_TAX_ID_RE = re.compile(r"\b\d{9,11}\b")


def _coerce_focus(value: Any) -> str:
    focus = str(value or "all").strip().lower()
    return focus if focus in {"all", "stores", "suppliers"} else "all"


def _coerce_top_n(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = DEFAULT_TOP_N
    return max(1, min(MAX_TOP_N, n))


def _coerce_max_rows(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = DEFAULT_MAX_ROWS
    return max(1, min(MAX_SCAN_ROWS, n))


def _coerce_min_similarity(value: Any) -> float:
    try:
        threshold = float(value)
    except (TypeError, ValueError):
        threshold = DEFAULT_MIN_SIMILARITY
    if threshold > 1:
        threshold = threshold / 100.0
    return max(0.6, min(0.98, threshold))


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFC", _safe_text(value)).lower().strip()
    text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_identity_text(value: Any) -> str:
    text = _normalize_text(value)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = _TAX_ID_RE.sub(" ", text)
    text = _LEGAL_PREFIX_RE.sub("", text).strip()
    return re.sub(r"\s+", " ", text).strip()


def _strip_ge_suffix(token: str) -> str:
    for suffix in ("ებთან", "ებიდან", "ებში", "იდან", "თან", "ში", "ზე", "ზეა", "ს"):
        if token.endswith(suffix) and len(token) > len(suffix) + 3:
            return token[: -len(suffix)]
    return token


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _token_candidates(text: str) -> List[str]:
    out: List[str] = []
    for token in _normalize_text(text).split():
        if len(token) < 3:
            continue
        out.append(token)
        stemmed = _strip_ge_suffix(token)
        if stemmed != token and len(stemmed) >= 3:
            out.append(stemmed)
    return out


def _build_store_variants(object_mapping: Dict[str, Any]) -> Dict[str, Tuple[str, ...]]:
    variants_by_target: Dict[str, List[str]] = {}
    rs_map = object_mapping.get("rs_location_to_object") or {}
    for target, variants in rs_map.items():
        if not target or str(target) == OBJECT_UNALLOCATED:
            continue
        bucket = variants_by_target.setdefault(str(target), [])
        bucket.append(str(target))
        for variant in variants or []:
            variant_text = _safe_text(variant).strip()
            if variant_text:
                bucket.append(variant_text)
    for source_key in ("tbc_text_to_object", "salary_text_to_object"):
        for token, target in (object_mapping.get(source_key) or {}).items():
            if not target or str(target) == OBJECT_UNALLOCATED:
                continue
            bucket = variants_by_target.setdefault(str(target), [])
            token_text = _safe_text(token).strip()
            if token_text:
                bucket.append(token_text)
    return {
        target: tuple(dict.fromkeys(values))
        for target, values in variants_by_target.items()
        if values
    }


def _best_store_candidate(
    text: Any,
    variants_by_target: Dict[str, Tuple[str, ...]],
) -> Dict[str, Any]:
    normalized = _normalize_text(text)
    if not normalized:
        return {"score": 0.0, "exact": False}

    exact_objects: List[str] = []
    exact_variants: List[str] = []
    for target, variants in variants_by_target.items():
        for variant in variants:
            variant_norm = _normalize_text(variant)
            if variant_norm and variant_norm in normalized:
                exact_objects.append(target)
                exact_variants.append(variant)
                break

    best: Dict[str, Any] = {"score": 0.0, "exact": False}
    text_tokens = _token_candidates(normalized)
    for target, variants in variants_by_target.items():
        if target in exact_objects:
            continue
        for variant in variants:
            variant_norm = _normalize_text(variant)
            if not variant_norm:
                continue
            for variant_token in _token_candidates(variant_norm):
                for token in text_tokens:
                    score = _similarity(token, variant_token)
                    if score > best.get("score", 0.0):
                        best = {
                            "score": score,
                            "exact": False,
                            "suggested_object": target,
                            "matched_variant": variant,
                            "matched_token": token,
                        }
    if exact_objects and best.get("suggested_object"):
        best["exact"] = True
        best["conflict"] = True
        best["exact_objects"] = sorted(set(exact_objects))
        best["exact_variants"] = sorted(set(exact_variants))
        return best
    if exact_objects:
        return {
            "score": 1.0,
            "exact": True,
            "conflict": False,
            "suggested_object": exact_objects[0],
            "matched_variant": exact_variants[0] if exact_variants else exact_objects[0],
            "matched_token": exact_variants[0] if exact_variants else exact_objects[0],
            "exact_objects": sorted(set(exact_objects)),
            "exact_variants": sorted(set(exact_variants)),
        }
    return best


def _find_destination_column(columns: Iterable[Any]) -> Optional[str]:
    names = [str(c).strip() for c in columns]
    for name in names:
        if name == DESTINATION_COLUMN:
            return name
    for name in names:
        norm = _normalize_text(name)
        if "ტრანსპორტირების" in norm and "დასრულება" in norm:
            return name
    for name in names:
        if "დასრულ" in _normalize_text(name):
            return name
    return None


def _read_tabular_sample(path: str, nrows: int) -> Tuple[Optional[pd.DataFrame], str]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        last_error: Optional[Exception] = None
        for enc in IMPORTED_PRODUCTS_CSV_ENCODINGS:
            for sep in (",", ";", None):
                try:
                    kwargs: Dict[str, Any] = {
                        "encoding": enc,
                        "nrows": nrows,
                        "low_memory": False,
                    }
                    if sep is None:
                        kwargs["sep"] = None
                        kwargs["engine"] = "python"
                    else:
                        kwargs["sep"] = sep
                    df = pd.read_csv(path, **kwargs)
                    if df.shape[1] < 5:
                        continue
                    df = df.copy()
                    df.columns = [str(c).strip() for c in df.columns]
                    return df, "csv"
                except Exception as exc:
                    last_error = exc
                    continue
        if last_error is not None:
            raise last_error
        return None, "csv"
    return pd.read_excel(path, sheet_name=IMPORTED_PRODUCTS_SHEET_NAME, nrows=nrows), "excel"


def _relative_source_path(project_root: Path, path: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _scan_store_aliases(
    *,
    project_root: Path,
    max_rows: int,
    top_n: int,
    min_similarity: float,
) -> Dict[str, Any]:
    mapping = load_object_mapping(str(project_root))
    variants_by_target = _build_store_variants(mapping)
    files = list_imported_product_files(str(project_root / "generate_dashboard_data.py"))

    issues: Dict[Tuple[str, str], Dict[str, Any]] = {}
    rows_scanned = 0
    rows_with_destination = 0
    exact_mapped_rows = 0
    unknown_rows = 0
    files_scanned = 0
    missing_destination_files: List[str] = []
    candidate_cache: Dict[str, Dict[str, Any]] = {}

    for path in files:
        if rows_scanned >= max_rows:
            break
        remaining = max_rows - rows_scanned
        try:
            df, source_type = _read_tabular_sample(path, remaining)
        except Exception as exc:
            missing_destination_files.append(
                f"{_relative_source_path(project_root, path)}: read failed: {exc}"
            )
            continue
        if df is None or df.empty:
            continue
        files_scanned += 1
        rows_scanned += int(len(df))
        col = _find_destination_column(df.columns)
        if not col:
            missing_destination_files.append(_relative_source_path(project_root, path))
            continue

        values = df[col].fillna("").astype(str).str.strip()
        value_counts = Counter(v for v in values.tolist() if v)
        first_rows: Dict[str, int] = {}
        for idx, value in values.items():
            if value and value not in first_rows:
                first_rows[value] = int(idx) + 2
        rows_with_destination += sum(value_counts.values())

        for value, count in value_counts.items():
            candidate = candidate_cache.get(value)
            if candidate is None:
                candidate = _best_store_candidate(value, variants_by_target)
                candidate_cache[value] = candidate
            if candidate.get("exact") and not candidate.get("conflict"):
                exact_mapped_rows += int(count)
                continue
            if float(candidate.get("score") or 0.0) >= min_similarity:
                key = (value, str(candidate.get("suggested_object") or ""))
                issue = issues.setdefault(
                    key,
                    {
                        "type": "store_mapping_conflict" if candidate.get("conflict") else "store_alias_suspect",
                        "original_value": value,
                        "suggested_object": candidate.get("suggested_object"),
                        "matched_variant": candidate.get("matched_variant"),
                        "matched_token": candidate.get("matched_token"),
                        "exact_objects": candidate.get("exact_objects") or [],
                        "confidence_pct": round(float(candidate.get("score") or 0.0) * 100, 1),
                        "occurrences": 0,
                        "source_file": _relative_source_path(project_root, path),
                        "source_row": first_rows.get(value),
                        "source_type": source_type,
                        "action": "review_mapping_before_final_analysis",
                    },
                )
                issue["occurrences"] += int(count)
            else:
                unknown_rows += int(count)

    issue_list = sorted(
        issues.values(),
        key=lambda row: (-int(row.get("occurrences") or 0), -float(row.get("confidence_pct") or 0.0)),
    )[:top_n]
    return {
        "files_scanned": files_scanned,
        "rows_scanned": rows_scanned,
        "rows_with_destination": rows_with_destination,
        "exact_mapped_rows": exact_mapped_rows,
        "unknown_rows": unknown_rows,
        "registered_objects": sorted(variants_by_target.keys()),
        "registered_alias_count": sum(len(v) for v in variants_by_target.values()),
        "issue_count": len(issues),
        "issues": issue_list,
        "missing_destination_files": missing_destination_files[:top_n],
    }


def _extract_tax_id(value: Any) -> str:
    match = _TAX_ID_RE.search(_safe_text(value))
    return match.group(0) if match else ""


def _supplier_records(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for row in data.get("suppliers") or []:
        if not isinstance(row, dict):
            continue
        name = _safe_text(row.get("ორგანიზაცია") or row.get("supplier"))
        norm = _normalize_identity_text(name)
        if norm:
            records.append({
                "section": "suppliers",
                "name": name,
                "normalized_name": norm,
                "tax_id": _safe_text(row.get("tax_id")) or _extract_tax_id(name),
                "amount_ge": float(row.get("total_effective") or row.get("total_debt") or 0.0),
            })
    imported = data.get("imported_products") or {}
    for row in imported.get("suppliers") or []:
        if not isinstance(row, dict):
            continue
        name = _safe_text(row.get("supplier") or row.get("ორგანიზაცია"))
        norm = _normalize_identity_text(row.get("normalized_supplier") or name)
        if norm:
            records.append({
                "section": "imported_products.suppliers",
                "name": name,
                "normalized_name": norm,
                "tax_id": _safe_text(row.get("tax_id")) or _extract_tax_id(name),
                "amount_ge": float(row.get("total_amount_ge") or row.get("total_effective") or 0.0),
            })
    seen = set()
    unique: List[Dict[str, Any]] = []
    for record in records:
        key = (record["section"], record["normalized_name"], record["tax_id"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def _scan_supplier_aliases(
    data: Dict[str, Any],
    *,
    top_n: int,
    min_similarity: float,
) -> Dict[str, Any]:
    records = _supplier_records(data)
    issues: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    for idx, left in enumerate(records):
        for right in records[idx + 1:]:
            if left["normalized_name"] == right["normalized_name"]:
                continue
            score = _similarity(left["normalized_name"], right["normalized_name"])
            same_tax_id = bool(left.get("tax_id") and left.get("tax_id") == right.get("tax_id"))
            if not same_tax_id and score < min_similarity:
                continue
            issue_type = "same_tax_id_name_variant" if same_tax_id else "similar_supplier_names"
            key = tuple(sorted([
                left["normalized_name"],
                right["normalized_name"],
                left.get("tax_id") or "",
                right.get("tax_id") or "",
            ]))
            if key in issues:
                continue
            issues[key] = {
                "type": issue_type,
                "left": left,
                "right": right,
                "confidence_pct": 100.0 if same_tax_id else round(score * 100, 1),
                "action": "use_tax_id_or_manual_review_before_merging",
            }
    issue_list = sorted(
        issues.values(),
        key=lambda row: (-float(row.get("confidence_pct") or 0.0), -max(
            float((row.get("left") or {}).get("amount_ge") or 0.0),
            float((row.get("right") or {}).get("amount_ge") or 0.0),
        )),
    )[:top_n]
    return {
        "records_scanned": len(records),
        "issue_count": len(issues),
        "issues": issue_list,
    }


def _risk_level(store_result: Optional[Dict[str, Any]], supplier_result: Optional[Dict[str, Any]]) -> str:
    store_count = int((store_result or {}).get("issue_count") or 0)
    supplier_count = int((supplier_result or {}).get("issue_count") or 0)
    if store_count > 0:
        return "HIGH"
    if supplier_count > 0:
        return "MEDIUM"
    return "LOW"


def _summary_ka(result: Dict[str, Any]) -> str:
    risk = result.get("risk_level")
    store_count = int(((result.get("stores") or {}).get("issue_count")) or 0)
    supplier_count = int(((result.get("suppliers") or {}).get("issue_count")) or 0)
    if risk == "LOW":
        return "მონაცემების ხარისხის სწრაფმა კონტროლმა მაღალი რისკის typo/alias პრობლემა ვერ იპოვა."
    parts = []
    if store_count:
        parts.append(f"მაღაზია/მისამართი: {store_count} საეჭვო ვარიანტი")
    if supplier_count:
        parts.append(f"კომპანია/მომწოდებელი: {supplier_count} საეჭვო წყვილი")
    return "⚠️ Data Quality Guard: " + "; ".join(parts) + ". საბოლოო ანალიზამდე ესენი გადაამოწმე."


def audit_data_quality(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    focus: Any = None,
    top_n: Any = None,
    min_similarity: Any = None,
    max_rows: Any = None,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    resolved_focus = _coerce_focus(focus)
    resolved_top_n = _coerce_top_n(top_n)
    resolved_min_similarity = _coerce_min_similarity(min_similarity)
    resolved_max_rows = _coerce_max_rows(max_rows)
    root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent.parent

    try:
        data = data_loader() or {}
    except Exception as exc:
        return {
            "error": "data.json-ის ჩატვირთვა ვერ მოხერხდა",
            "hint": str(exc),
            "source": SOURCE_LABEL,
        }
    if not isinstance(data, dict):
        return {"error": "data_loader did not return a dict", "source": SOURCE_LABEL}

    store_result = None
    supplier_result = None
    if resolved_focus in {"all", "stores"}:
        store_result = _scan_store_aliases(
            project_root=root,
            max_rows=resolved_max_rows,
            top_n=resolved_top_n,
            min_similarity=resolved_min_similarity,
        )
    if resolved_focus in {"all", "suppliers"}:
        supplier_result = _scan_supplier_aliases(
            data,
            top_n=resolved_top_n,
            min_similarity=resolved_min_similarity,
        )

    result: Dict[str, Any] = {
        "source": SOURCE_LABEL,
        "focus": resolved_focus,
        "top_n": resolved_top_n,
        "max_rows": resolved_max_rows,
        "min_similarity": resolved_min_similarity,
        "stores": store_result,
        "suppliers": supplier_result,
        "notes": [
            "ეს ინსტრუმენტი საეჭვო დამთხვევებს პოულობს, მაგრამ მონაცემებს ჩუმად არ ცვლის.",
            "HIGH/MEDIUM რისკის დროს AI-მ საბოლოო ციფრი არ უნდა დახუროს review-ის გარეშე.",
        ],
    }
    result["risk_level"] = _risk_level(store_result, supplier_result)
    result["summary_ka"] = _summary_ka(result)
    return result
