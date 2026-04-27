"""
Configuration loading: object mapping, budget, sector benchmarks,
unmatched overrides, and supplier matching registry.
"""
import json
import os

from dashboard_pipeline.logging_config import get_logger
from dashboard_pipeline.file_utils import _financial_analysis_path
from dashboard_pipeline.export_artifacts import write_json_file
from dashboard_pipeline.constants import (
    _clone_default_object_mapping,
    _clone_default_budget_config,
    _clone_default_sector_benchmarks,
    _safe_text,
    OBJECT_UNALLOCATED,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Object mapping
# ---------------------------------------------------------------------------

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
                    "rs_location_priority_order",
                    "rs_location_to_object",
                    "salary_text_to_object",
                    "default_object",
                ):
                    if key in user_cfg:
                        mapping[key] = user_cfg[key]
        except Exception as e:
            logger.warning("Object mapping read %s: %s", path, e)
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
    # rs_location_priority_order — list of canonical target names; the
    # destination resolver tests these first-to-last so the more specific
    # store wins when multiple keywords appear in the same source text
    # (e.g. "ოზურგეთი, სოფ. დვაბზუ" → დვაბზუ if დვაბზუ is listed first).
    raw_priority = mapping.get("rs_location_priority_order")
    if raw_priority is None:
        clean_priority = []
    else:
        if not isinstance(raw_priority, list):
            raw_priority = [raw_priority]
        clean_priority = [str(t).strip() for t in raw_priority if _safe_text(t).strip()]
    mapping["rs_location_priority_order"] = clean_priority
    mapping["salary_text_to_object"] = {
        str(k): str(v)
        for k, v in (mapping.get("salary_text_to_object") or {}).items()
        if _safe_text(k).strip()
    }
    return mapping


# ---------------------------------------------------------------------------
# Budget config
# ---------------------------------------------------------------------------

def load_budget_config():
    path = _financial_analysis_path("budget_config.json")
    cfg = _clone_default_budget_config()
    if not os.path.isfile(path):
        try:
            write_json_file(path, cfg)
        except Exception as e:
            logger.warning("Budget config create %s: %s", path, e)
        return cfg

    try:
        with open(path, encoding="utf-8") as f:
            user_cfg = json.load(f)
        if isinstance(user_cfg, dict):
            for key in ("notes", "auto_mode", "annual_targets", "expense_growth_cap_pct"):
                if key in user_cfg:
                    cfg[key] = user_cfg[key]
    except Exception as e:
        logger.warning("Budget config read %s: %s", path, e)
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


# ---------------------------------------------------------------------------
# Sector benchmarks
# ---------------------------------------------------------------------------

def load_sector_benchmarks():
    path = _financial_analysis_path("sector_benchmarks.json")
    cfg = _clone_default_sector_benchmarks()
    if not os.path.isfile(path):
        try:
            write_json_file(path, cfg)
        except Exception as e:
            logger.warning("Sector benchmarks create %s: %s", path, e)
        return cfg

    try:
        with open(path, encoding="utf-8") as f:
            user_cfg = json.load(f)
        if isinstance(user_cfg, dict):
            for key in ("sector", "country", "notes", "benchmarks", "valuation_multiples"):
                if key in user_cfg:
                    cfg[key] = user_cfg[key]
    except Exception as e:
        logger.warning("Sector benchmarks read %s: %s", path, e)
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


# ---------------------------------------------------------------------------
# Unmatched overrides
# ---------------------------------------------------------------------------

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
        logger.warning("unmatched_overrides ვერ წაიკითხა: %s", e)
    return out


# ---------------------------------------------------------------------------
# Supplier matching registry
# ---------------------------------------------------------------------------

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
        logger.warning("Supplier registry read failed: %s", e)
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
