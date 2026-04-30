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
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class AliasValidationError(ValueError):
    """Raised when a single alias entry fails validation.

    ``kind`` lets callers (e.g. the HTTP endpoint) map to the correct
    response code without parsing the message.
    """

    kind: str = "validation"


class AliasDuplicateError(AliasValidationError):
    """Raised when a confirm request targets an already-confirmed
    ``imported_code``. Callers map this to HTTP 409, not 400."""

    kind = "duplicate"


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


def append_alias_atomic(
    path: Path,
    entry: Dict[str, Any],
    retail_known_keys: Set[str],
) -> Dict[str, Any]:
    """Validate ``entry`` and atomically append it to ``path``.

    Used by the ``/api/aliases/confirm`` endpoint when a user confirms
    a pipeline-suggested ``name_candidate``. The function:

    1. Validates the new entry against the same rules the pipeline applies
       at load time (``confirmed_by`` is forced to ``"user"`` server-side).
    2. Reads any existing ``product_aliases.json`` to check for a
       duplicate ``imported_code``.
    3. Stamps ``confirmed_at`` with the current UTC ISO timestamp.
    4. Writes the new file to a sibling ``.tmp`` path, then ``os.replace``-s
       it onto the target — atomic on POSIX and Windows alike, so a
       concurrent pipeline reader never sees a partially written JSON.

    Returns the canonical alias dict that landed on disk.

    Raises:
        AliasValidationError — bad input (empty code, unknown retail key)
        AliasDuplicateError  — ``imported_code`` already confirmed
    """
    imported = _norm(entry.get("imported_code"))
    target = _norm(entry.get("retail_code_or_barcode"))

    if not imported:
        raise AliasValidationError(
            "imported_code სავალდებულოა — ცარიელი მნიშვნელობა მიუღებელია"
        )
    if not target:
        raise AliasValidationError(
            "retail_code_or_barcode სავალდებულოა — ცარიელი მნიშვნელობა მიუღებელია"
        )
    if target not in retail_known_keys:
        raise AliasValidationError(
            f"retail_code_or_barcode {target!r} ცოცხალ retail_sales-ში ვერ მოიძებნა"
        )

    # Read existing file (or seed an empty document with the canonical
    # version/comment/schema header so the file stays self-describing).
    if path.exists():
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AliasValidationError(
                f"product_aliases.json-ი გატეხილ JSON-ს შეიცავს — {exc}"
            ) from exc
        if not isinstance(doc, dict):
            raise AliasValidationError(
                "product_aliases.json-ის ზედა დონე უნდა იყოს object"
            )
    else:
        doc = {"version": 1, "aliases": []}

    aliases = doc.get("aliases")
    if not isinstance(aliases, list):
        aliases = []
        doc["aliases"] = aliases

    for existing in aliases:
        if not isinstance(existing, dict):
            continue
        if _norm(existing.get("imported_code")) == imported:
            raise AliasDuplicateError(
                f"imported_code {imported!r} უკვე დადასტურებულია — "
                f"იძებნება არსებულ alias-ად"
            )

    canonical = {
        "imported_code": imported,
        "retail_code_or_barcode": target,
        "imported_supplier_taxid": _norm(entry.get("imported_supplier_taxid")),
        "imported_name_sample": _norm(entry.get("imported_name_sample")),
        "confirmed_by": "user",
        "confirmed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": _norm(entry.get("note")),
    }
    aliases.append(canonical)

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)
    return canonical


__all__ = [
    "AliasValidationError",
    "AliasDuplicateError",
    "load_aliases_file",
    "validate_aliases",
    "load_and_validate",
    "append_alias_atomic",
]
