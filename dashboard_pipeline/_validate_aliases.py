"""Validate ``product_aliases.json`` before passing to supplier_profitability.

Returns ``(aliases, errors)``. On any structural error or unsafe entry
the entry is dropped and an error string is appended; the rest of the
file still loads. The pipeline never crashes on a bad alias file — it
proceeds with whatever passes validation and logs the rejected entries.

Hard requirements per entry:

* ``confirmed_by == "user"`` — automation must not seed aliases silently
  (memory: feedback_perfect_or_silent — only user-confirmed mappings
  reach UI numbers).
* both ``imported_code`` and ``retail_code_or_barcode`` non-empty after
  strip.
* ``retail_code_or_barcode`` exists in the live retail_sales index
  (barcode OR product_code) — otherwise the alias points at nothing.
* no duplicate ``imported_code`` (would cause non-deterministic match).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_aliases_file(path: Path) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Read ``product_aliases.json``. Returns ``(parsed, errors)``.

    If the file does not exist, returns ``({"version": 1, "aliases": []}, [])``
    so callers can treat "no file" as "no aliases" without special-casing.
    """
    errors: List[str] = []
    if not path.exists():
        return {"version": 1, "aliases": []}, []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"product_aliases.json: invalid JSON — {exc}"]

    if not isinstance(raw, dict):
        return None, ["product_aliases.json: top level must be an object"]
    if "aliases" not in raw or not isinstance(raw["aliases"], list):
        errors.append("product_aliases.json: missing or non-list `aliases` — treating as empty")
        raw["aliases"] = []
    return raw, errors


def validate_aliases(
    parsed: Optional[Dict[str, Any]],
    retail_known_keys: Set[str],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Return ``(safe_aliases, errors)``.

    ``retail_known_keys`` should be the union of all retail_sales barcodes
    and product_codes (stripped strings). Each alias's
    ``retail_code_or_barcode`` must exist in this set.
    """
    errors: List[str] = []
    if not parsed:
        return [], errors

    aliases = parsed.get("aliases") or []
    safe: List[Dict[str, Any]] = []
    seen_imported: Set[str] = set()

    for idx, entry in enumerate(aliases):
        if not isinstance(entry, dict):
            errors.append(f"alias #{idx}: not an object, skipped")
            continue

        imported = _norm(entry.get("imported_code"))
        target = _norm(entry.get("retail_code_or_barcode"))
        confirmed_by = _norm(entry.get("confirmed_by"))

        if not imported:
            errors.append(f"alias #{idx}: empty imported_code, skipped")
            continue
        if not target:
            errors.append(f"alias #{idx} ({imported!r}): empty retail_code_or_barcode, skipped")
            continue
        if confirmed_by != "user":
            errors.append(
                f"alias #{idx} ({imported!r}): confirmed_by must be \"user\" "
                f"(got {confirmed_by!r}), skipped"
            )
            continue
        if imported in seen_imported:
            errors.append(
                f"alias #{idx} ({imported!r}): duplicate imported_code, skipped"
            )
            continue
        if target not in retail_known_keys:
            errors.append(
                f"alias #{idx} ({imported!r}): retail_code_or_barcode "
                f"{target!r} does not exist in current retail_sales — skipped"
            )
            continue

        seen_imported.add(imported)
        safe.append(
            {
                "imported_code": imported,
                "retail_code_or_barcode": target,
                "imported_supplier_taxid": _norm(entry.get("imported_supplier_taxid")),
                "imported_name_sample": _norm(entry.get("imported_name_sample")),
                "confirmed_by": confirmed_by,
                "confirmed_at": _norm(entry.get("confirmed_at")),
                "note": _norm(entry.get("note")),
            }
        )

    return safe, errors


def load_and_validate(
    path: Path,
    retail_known_keys: Set[str],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Convenience wrapper — read the file then validate. Returns
    ``(safe_aliases, all_errors)`` ready for ``build_supplier_profitability``.
    """
    parsed, parse_errors = load_aliases_file(path)
    safe, validate_errors = validate_aliases(parsed, retail_known_keys)
    return safe, parse_errors + validate_errors


__all__ = [
    "load_aliases_file",
    "validate_aliases",
    "load_and_validate",
]
