from __future__ import annotations


def _issue(config_name, path, severity, message):
    return {
        "config": config_name,
        "path": path,
        "severity": severity,
        "message": message,
    }


def _is_non_empty_mapping(value):
    return isinstance(value, dict) and len(value) > 0


def _non_empty_list(value):
    return isinstance(value, list) and any(str(item or "").strip() for item in value)


def validate_object_mapping(mapping):
    issues = []
    if not isinstance(mapping, dict):
        issues.append(_issue("object_mapping", "$", "error", "Config must be an object."))
        return {"ok": False, "issues": issues}
    for key in (
        "bog_terminal_to_object",
        "tbc_text_to_object",
        "rs_location_to_object",
        "salary_text_to_object",
    ):
        if key not in mapping:
            issues.append(
                _issue("object_mapping", key, "warning", "Missing mapping section.")
            )
            continue
        if not isinstance(mapping.get(key), dict):
            issues.append(
                _issue("object_mapping", key, "error", "Section must be an object.")
            )
    if not str(mapping.get("default_object") or "").strip():
        issues.append(
            _issue(
                "object_mapping",
                "default_object",
                "warning",
                "Default object is empty.",
            )
        )
    return {
        "ok": not any(issue["severity"] == "error" for issue in issues),
        "issues": issues,
    }


def validate_budget_config(cfg):
    issues = []
    if not isinstance(cfg, dict):
        issues.append(_issue("budget_config", "$", "error", "Config must be an object."))
        return {"ok": False, "issues": issues}
    if not isinstance(cfg.get("auto_mode"), bool):
        issues.append(
            _issue("budget_config", "auto_mode", "warning", "Expected boolean.")
        )
    if not isinstance(cfg.get("annual_targets"), dict):
        issues.append(
            _issue(
                "budget_config",
                "annual_targets",
                "error",
                "Expected annual_targets object.",
            )
        )
    if "expense_growth_cap_pct" in cfg and not isinstance(
        cfg.get("expense_growth_cap_pct"), (int, float)
    ):
        issues.append(
            _issue(
                "budget_config",
                "expense_growth_cap_pct",
                "warning",
                "Expected numeric growth cap.",
            )
        )
    return {
        "ok": not any(issue["severity"] == "error" for issue in issues),
        "issues": issues,
    }


def validate_sector_benchmarks(cfg):
    issues = []
    if not isinstance(cfg, dict):
        issues.append(
            _issue("sector_benchmarks", "$", "error", "Config must be an object.")
        )
        return {"ok": False, "issues": issues}
    if not str(cfg.get("sector") or "").strip():
        issues.append(
            _issue("sector_benchmarks", "sector", "warning", "Sector name is empty.")
        )
    if not _is_non_empty_mapping(cfg.get("benchmarks")):
        issues.append(
            _issue(
                "sector_benchmarks",
                "benchmarks",
                "error",
                "Benchmarks object is missing or empty.",
            )
        )
    if not _is_non_empty_mapping(cfg.get("valuation_multiples")):
        issues.append(
            _issue(
                "sector_benchmarks",
                "valuation_multiples",
                "error",
                "Valuation multiples object is missing or empty.",
            )
        )
    return {
        "ok": not any(issue["severity"] == "error" for issue in issues),
        "issues": issues,
    }


def validate_supplier_matching_registry(cfg):
    issues = []
    if not isinstance(cfg, dict):
        issues.append(
            _issue(
                "supplier_matching_registry",
                "$",
                "error",
                "Config must be an object.",
            )
        )
        return {"ok": False, "issues": issues}
    suppliers = cfg.get("suppliers")
    if not isinstance(suppliers, list):
        issues.append(
            _issue(
                "supplier_matching_registry",
                "suppliers",
                "error",
                "Suppliers must be a list.",
            )
        )
        suppliers = []
    if "explicit_skip_keywords" in cfg and not isinstance(
        cfg.get("explicit_skip_keywords"), list
    ):
        issues.append(
            _issue(
                "supplier_matching_registry",
                "explicit_skip_keywords",
                "warning",
                "Skip keywords should be a list.",
            )
        )
    for idx, item in enumerate(suppliers):
        if not isinstance(item, dict):
            issues.append(
                _issue(
                    "supplier_matching_registry",
                    f"suppliers[{idx}]",
                    "warning",
                    "Supplier item should be an object.",
                )
            )
            continue
        has_identifier = str(item.get("tax_id") or "").strip() or str(
            item.get("name") or ""
        ).strip()
        if not has_identifier:
            issues.append(
                _issue(
                    "supplier_matching_registry",
                    f"suppliers[{idx}]",
                    "warning",
                    "Supplier entry is missing tax_id/name.",
                )
            )
        if not str(item.get("official_name") or item.get("name") or "").strip():
            issues.append(
                _issue(
                    "supplier_matching_registry",
                    f"suppliers[{idx}].official_name",
                    "warning",
                    "Official name is empty; registry should carry an explicit truth label.",
                )
            )
        evidence = item.get("evidence") or []
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list):
            issues.append(
                _issue(
                    "supplier_matching_registry",
                    f"suppliers[{idx}].evidence",
                    "warning",
                    "Evidence should be a list or string.",
                )
            )
            evidence = []
        for field in (
            "aliases",
            "person_aliases",
            "ibans",
            "account_hints",
            "force_non_supplier_keywords",
        ):
            if field in item and item.get(field) is not None and not isinstance(
                item.get(field), list
            ):
                issues.append(
                    _issue(
                        "supplier_matching_registry",
                        f"suppliers[{idx}].{field}",
                        "warning",
                        f"{field} should be a list.",
                    )
                )
        has_match_aids = any(
            _non_empty_list(item.get(field))
            for field in (
                "aliases",
                "person_aliases",
                "ibans",
                "account_hints",
                "force_non_supplier_keywords",
            )
        )
        has_evidence = any(str(entry or "").strip() for entry in evidence)
        if has_match_aids and not has_evidence:
            issues.append(
                _issue(
                    "supplier_matching_registry",
                    f"suppliers[{idx}]",
                    "warning",
                    "Match aids exist without explicit evidence; strict matcher will ignore them.",
                )
            )
    return {
        "ok": not any(issue["severity"] == "error" for issue in issues),
        "issues": issues,
    }


def validate_unmatched_overrides(cfg):
    issues = []
    if not isinstance(cfg, dict):
        issues.append(
            _issue("unmatched_overrides", "$", "error", "Config must be an object.")
        )
        return {"ok": False, "issues": issues}
    for key in ("approvals", "rejections"):
        rules = cfg.get(key)
        if not isinstance(rules, list):
            issues.append(
                _issue(
                    "unmatched_overrides",
                    key,
                    "error",
                    f"{key} must be a list.",
                )
            )
            continue
        for idx, item in enumerate(rules):
            if not isinstance(item, dict):
                issues.append(
                    _issue(
                        "unmatched_overrides",
                        f"{key}[{idx}]",
                        "warning",
                        "Override rule should be an object.",
                    )
                )
                continue
            if not any(
                (
                    item.get("contains_any"),
                    item.get("signature_contains"),
                    item.get("ibans_any"),
                )
            ):
                issues.append(
                    _issue(
                        "unmatched_overrides",
                        f"{key}[{idx}]",
                        "warning",
                        "Override rule has no match criteria.",
                    )
                )
    return {
        "ok": not any(issue["severity"] == "error" for issue in issues),
        "issues": issues,
    }


def validate_config_bundle(
    object_mapping,
    budget_config,
    sector_benchmarks,
    supplier_registry,
    unmatched_overrides,
):
    files = {
        "object_mapping": validate_object_mapping(object_mapping),
        "budget_config": validate_budget_config(budget_config),
        "sector_benchmarks": validate_sector_benchmarks(sector_benchmarks),
        "supplier_matching_registry": validate_supplier_matching_registry(
            supplier_registry
        ),
        "unmatched_overrides": validate_unmatched_overrides(unmatched_overrides),
    }
    issues = []
    for report in files.values():
        issues.extend(report.get("issues") or [])
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    return {
        "ok": error_count == 0,
        "warning_count": warning_count,
        "error_count": error_count,
        "files": {
            name: {
                "ok": bool(report.get("ok")),
                "issue_count": len(report.get("issues") or []),
            }
            for name, report in files.items()
        },
        "issues": issues,
    }


def validate_api_artifacts(artifacts):
    from dashboard_pipeline.api_contracts import STATIC_RESPONSE_TABS

    issues = []
    required_static = set(STATIC_RESPONSE_TABS) | {
        "waybills_source",
        "imported_products_source",
        "retail_sales_source",
    }
    artifact_names = set((artifacts or {}).keys())
    for name in sorted(required_static - artifact_names):
        issues.append(
            _issue("api_artifacts", name, "error", "Required artifact is missing.")
        )
    for name, payload in (artifacts or {}).items():
        if not isinstance(payload, dict):
            issues.append(
                _issue(
                    "api_artifacts",
                    name,
                    "error",
                    "Artifact payload must be an object.",
                )
            )
            continue
        if name.endswith("_source"):
            for key in ("meta", "download_files", "download_zip_file"):
                if key not in payload:
                    issues.append(
                        _issue(
                            "api_artifacts",
                            f"{name}.{key}",
                            "error",
                            "Source artifact is missing base response fields.",
                        )
                    )
        else:
            if "response_meta" not in payload:
                issues.append(
                    _issue(
                        "api_artifacts",
                        f"{name}.response_meta",
                        "warning",
                        "Static artifact should expose response_meta.",
                    )
                )
    return {
        "ok": not any(issue["severity"] == "error" for issue in issues),
        "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
        "error_count": sum(1 for issue in issues if issue["severity"] == "error"),
        "issues": issues,
    }
