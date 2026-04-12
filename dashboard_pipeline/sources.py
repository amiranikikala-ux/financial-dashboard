from __future__ import annotations

import glob
import hashlib
import os
from datetime import datetime, timezone


def financial_analysis_path(script_path, *parts):
    script_dir = os.path.dirname(os.path.abspath(script_path))
    return os.path.join(script_dir, "Financial_Analysis", *parts)


def sorted_glob_in_financial(script_path, subdir, pattern):
    return sorted(
        glob.glob(os.path.join(financial_analysis_path(script_path, subdir), pattern))
    )


def list_bog_bank_statement_xlsx(script_path):
    return sorted_glob_in_financial(script_path, "ბოგ ბანკი ამონაწერი", "*.xlsx")


def list_tbc_bank_statement_xlsx(script_path):
    return sorted_glob_in_financial(script_path, "თბს ბანკი ამონაწერი", "*.xlsx")


def list_rs_waybill_files(script_path):
    base = financial_analysis_path(script_path, "რს ზედნადები")
    merged = []
    merged.extend(glob.glob(os.path.join(base, "*.xlsx")))
    merged.extend(glob.glob(os.path.join(base, "*.xls")))
    return sorted(set(merged))


def list_imported_product_files(script_path):
    base = financial_analysis_path(script_path, "შემოტანილი პროდუქცია")
    csv_files = sorted(glob.glob(os.path.join(base, "*.csv")))
    if csv_files:
        return csv_files
    merged = []
    merged.extend(glob.glob(os.path.join(base, "*.xls")))
    merged.extend(glob.glob(os.path.join(base, "*.xlsx")))
    return sorted(set(merged))


def list_retail_sales_dvabzu_files(script_path):
    return sorted_glob_in_financial(
        script_path, "გაყიდული პროდუქტები სოფ დვაბზუ", "*.xlsx"
    )


def list_retail_sales_ozurgeti_files(script_path):
    return sorted_glob_in_financial(
        script_path, "გაყიდული პროდუქტები სოფ ოზურგეთი", "*.xlsx"
    )


def list_retail_sales_files(script_path):
    merged = []
    merged.extend(list_retail_sales_dvabzu_files(script_path))
    merged.extend(list_retail_sales_ozurgeti_files(script_path))
    return sorted(set(merged))


def _to_utc_iso(timestamp):
    return (
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _sha256_file(path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def describe_source_files(label_ka, source_kind, paths):
    files = []
    latest_modified_at = None
    total_size_bytes = 0
    unique_paths = sorted({os.path.abspath(path) for path in (paths or [])})
    for path in unique_paths:
        exists = os.path.isfile(path)
        item = {
            "file_name": os.path.basename(path),
            "path": path,
            "exists": bool(exists),
        }
        if exists:
            stat = os.stat(path)
            total_size_bytes += int(stat.st_size)
            modified_at = _to_utc_iso(stat.st_mtime)
            latest_modified_at = max(
                [latest_modified_at, modified_at], key=lambda v: v or ""
            )
            item.update(
                {
                    "size_bytes": int(stat.st_size),
                    "modified_at": modified_at,
                    "sha256": _sha256_file(path),
                }
            )
        files.append(item)
    return {
        "label_ka": str(label_ka or source_kind),
        "source_kind": str(source_kind or label_ka),
        "file_count": len(files),
        "total_size_bytes": int(total_size_bytes),
        "latest_modified_at": latest_modified_at,
        "files": files,
    }


def build_source_manifest(source_specs):
    manifest = []
    for spec in source_specs or []:
        if not isinstance(spec, dict):
            continue
        manifest.append(
            describe_source_files(
                spec.get("label_ka"),
                spec.get("source_kind"),
                spec.get("paths") or [],
            )
        )
    return manifest


def summarize_source_manifest(source_manifest):
    groups = {}
    total_files = 0
    total_size_bytes = 0
    missing_groups = []
    for entry in source_manifest or []:
        if not isinstance(entry, dict):
            continue
        source_kind = str(entry.get("source_kind") or entry.get("label_ka") or "")
        file_count = int(entry.get("file_count") or 0)
        total_size = int(entry.get("total_size_bytes") or 0)
        total_files += file_count
        total_size_bytes += total_size
        if file_count == 0:
            missing_groups.append(source_kind)
        groups[source_kind] = {
            "label_ka": entry.get("label_ka"),
            "file_count": file_count,
            "total_size_bytes": total_size,
            "latest_modified_at": entry.get("latest_modified_at"),
        }
    return {
        "group_count": len(groups),
        "total_files": int(total_files),
        "total_size_bytes": int(total_size_bytes),
        "missing_groups": missing_groups,
        "groups": groups,
    }
