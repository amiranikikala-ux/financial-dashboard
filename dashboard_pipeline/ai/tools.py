"""AI agent tools.

Phase 1 tool surface:
- `read_data_json(section, filter?, limit?, columns?)` — bounded, read-only
  slice of data.json.

Phase 2 Investigator tool surface (this file):
- `read_source_code(file_path, line_range?)` — bounded slice of a project
  source file under an allowlisted code root.
- `grep_code(pattern, path?, max_hits?)` — regex search across allowlisted
  code roots with a hard hit cap.
- `read_excel_source(file_path, sheet?, nrows?, skiprows?)` — bounded pandas
  preview of a file under `Financial_Analysis/` (csv/xlsx/xls).
- `validate_vs_source(section, expected_row_count?, expected_total?, field_name?)`
  — compare data.json section metadata against user-provided expectations.

Design constraints:
- Only allowlisted sections are exposed.
- List sections are capped at `DEFAULT_ROW_LIMIT` to protect the context window.
- List rows are column-pruned to an analytical minimal set by default
  (`columns="minimal"`). Pass `columns="all"` to keep every field.
- Tool output is a plain dict — no nested Python objects — safe to JSON-dump.
- Errors are returned as `{"error": "..."}` so the agent loop can continue.
- File-system tools go through `_resolve_safe_path()` which enforces a
  hard allowlist against project root plus reject path traversal / absolute
  paths. Secrets (`.env`, `secrets/`, `node_modules/`, etc.) are never exposed.
"""

from __future__ import annotations

import copy
import json as _json_safe
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


DEFAULT_ROW_LIMIT = 10
MAX_ROW_LIMIT = 500
MAX_OUTPUT_CHARS = 32_000  # safety cap per tool result

# --- Phase 2 Investigator caps ---------------------------------------------
MAX_SOURCE_LINES = 500
DEFAULT_SOURCE_LINES = 200
MAX_GREP_HITS = 200
DEFAULT_GREP_HITS = 50
MAX_EXCEL_NROWS = 200
DEFAULT_EXCEL_NROWS = 20

# Allowlist roots (relative to project root). Directory entries match that
# directory and everything under it. File entries (endswith a known
# extension) match exactly that file — used to whitelist specific top-level
# scripts without exposing the rest of the repo root.
ALLOWED_CODE_ROOTS: Tuple[str, ...] = (
    "dashboard_pipeline",
    "rs-dashboard/src",
    "tests",
    "server.py",
    "generate_dashboard_data.py",
    "backend_paths.py",
)
ALLOWED_DATA_ROOTS: Tuple[str, ...] = ("Financial_Analysis",)

# File extensions that are considered text-readable by `read_source_code` and
# `grep_code`. Binary / unknown extensions are rejected to prevent leaking
# arbitrary bytes into the LLM context window.
_TEXT_FILE_EXTENSIONS: Tuple[str, ...] = (
    ".py", ".pyi",
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".json", ".md", ".css", ".html", ".htm",
    ".yml", ".yaml", ".toml", ".txt", ".ini",
    ".sh", ".ps1", ".bat",
)
_EXCEL_FILE_EXTENSIONS: Tuple[str, ...] = (".csv", ".xlsx", ".xls")

INVESTIGATOR_TOOL_NAMES: Tuple[str, ...] = (
    "read_source_code",
    "grep_code",
    "read_excel_source",
    "validate_vs_source",
)

# Static hints shown alongside validate_vs_source results so the LLM (and the
# user) know where the ground-truth data lives. These are descriptive labels,
# not allowlist entries.
_SECTION_SOURCE_HINTS: Dict[str, str] = {
    "suppliers": "Financial_Analysis/რს ზედნადები/ (yearly xls)",
    "supplier_aging": "Financial_Analysis/რს ზედნადები/ + payment reconciliation",
    "aging_summary": "Aggregated across supplier_aging",
    "ap_monthly_trend": "Aggregated across supplier_aging",
    "waybills": "Financial_Analysis/რს ზედნადები/ (yearly xls)",
    "waybills_summary": "Financial_Analysis/რს ზედნადები/",
    "monthly_pnl": "Aggregated across all Financial_Analysis/ sources",
    "financial_ratios": "Computed from monthly_pnl",
    "forecast": "Computed from monthly_pnl",
    "budget": "Financial_Analysis/budget_config.json + monthly_pnl actuals",
    "company_valuation": "Computed from monthly_pnl + budget",
    "executive_summary": "Aggregated across pnl / ratios / cashflow",
    "retail_sales": (
        "Financial_Analysis/გაყიდული პროდუქტები სოფ ოზურგეთი/ + "
        "Financial_Analysis/გაყიდული პროდუქტები სოფ დვაბზუ/"
    ),
    "imported_products": "Financial_Analysis/შემოტანილი პროდუქცია/ (yearly csv)",
    "cashflow_summary": (
        "Financial_Analysis/ბოგ ბანკი ამონაწერი/ + "
        "Financial_Analysis/თბს ბანკი ამონაწერი/ + manual_payments.csv"
    ),
    "meta": "data.json metadata block",
    "response_meta": "data.json response-meta block",
}


def _default_project_root() -> Path:
    """Repository root for the Financial Dashboard (canonical).

    Layout assumption: this file lives at
    ``financial-dashboard/dashboard_pipeline/ai/tools.py``; the repo root is
    three levels up. Tests may override via ``project_root`` kwarg on tools
    / dispatcher.
    """
    return Path(__file__).resolve().parent.parent.parent


def _resolve_safe_path(
    rel_path: Any,
    allowed_roots: Iterable[str],
    project_root: Path,
) -> Optional[Path]:
    """Return a safe absolute Path iff ``rel_path`` lies inside an allowlisted root.

    Returns ``None`` for any of:
    - Non-string, empty, or whitespace-only path.
    - Absolute path (leading ``/`` or drive-letter on Windows).
    - Path containing a ``..`` traversal segment.
    - Resolved path not under ``project_root``.
    - Resolved path not under any entry in ``allowed_roots``.

    Directory entries in ``allowed_roots`` match themselves and everything
    beneath. File entries (those containing a ``.`` in the final segment)
    must match exactly.

    Implementation note: we use :py:meth:`Path.absolute` (path concatenation
    + normalization) instead of :py:meth:`Path.resolve` because ``resolve``
    follows OS-level junctions / reparse points. On Windows + OneDrive a
    folder name with non-ASCII characters in an ancestor segment (e.g.
    ``AI აგენტი``) can cause ``resolve`` to silently jump out of
    ``project_root`` for some — but not all — child paths, breaking access
    to legitimate files. Traversal protection is preserved via the explicit
    ``..`` rejection above plus the ``relative_to`` check below.
    """
    if not isinstance(rel_path, str) or not rel_path.strip():
        return None
    rp_norm = rel_path.replace("\\", "/").strip()
    # Reject absolute paths / drive letters.
    if rp_norm.startswith("/"):
        return None
    if len(rp_norm) >= 2 and rp_norm[1] == ":":
        return None

    # Reject path-traversal segments explicitly. We can't rely on Path.resolve
    # to canonicalise these away because resolve also follows symlinks /
    # junctions, which breaks legitimate non-ASCII paths on Windows + OneDrive
    # (see docstring).
    segments = [seg for seg in rp_norm.split("/") if seg]
    if any(seg == ".." for seg in segments):
        return None

    try:
        root = project_root.resolve()
    except (OSError, RuntimeError):
        return None

    try:
        # Use absolute() (lexical) instead of resolve() (filesystem-aware)
        # so that OneDrive / junction quirks on non-ASCII ancestors don't
        # silently relocate the candidate outside project_root.
        candidate = (root / rp_norm).absolute()
    except (OSError, RuntimeError, ValueError):
        return None

    # Must sit under project_root. With ".." already rejected and root
    # canonicalised via resolve(), this is a sound containment check.
    try:
        rel = candidate.relative_to(root)
    except ValueError:
        return None

    rel_str = str(rel).replace("\\", "/")

    for allowed in allowed_roots:
        allowed_n = allowed.replace("\\", "/").strip("/")
        if not allowed_n:
            continue
        # File allowlist entry: must match exactly.
        last_segment = allowed_n.rsplit("/", 1)[-1]
        is_file_entry = "." in last_segment
        if is_file_entry:
            if rel_str == allowed_n:
                return candidate
        else:
            if rel_str == allowed_n or rel_str.startswith(allowed_n + "/"):
                return candidate
    return None


# Allowlist: top-level keys of data.json that are safe/useful for the LLM.
# We deliberately limit this to avoid leaking internal engineering fields
# that carry no analytical value.
ALLOWED_SECTIONS: Dict[str, str] = {
    "meta": "Top-level metadata: period label, generated_at, scope summaries",
    "suppliers": "List of suppliers with totals, debt, payment scope",
    "supplier_aging": "Aging buckets per supplier",
    "aging_summary": "Aging totals aggregated across suppliers",
    "ap_monthly_trend": "Monthly accounts-payable trend",
    "waybills": (
        "List of individual waybills (~21k rows). Each row has THREE date "
        "fields — CHOOSE CAREFULLY based on the user's question:\n"
        "  • `date` = RS activation/registration (გააქტიურების თარ.)\n"
        "  • `transport_start_date` = when transport started (ტრანსპ. დაწყება) — "
        "THIS is the semantic match for 'ზედნადები შემოვიდა X დღეს'\n"
        "  • `delivery_date` = delivery confirmation (ჩაბარების თარ.)\n"
        "For daily totals prefer the `compute_waybill_total` tool (server-side "
        "arithmetic, no hallucination risk). For listing rows, pass e.g. "
        "filter={'transport_start_date':'YYYY-MM-DD'}. ALWAYS filter before "
        "requesting data — unfiltered pulls blow up the context window."
    ),
    "waybills_summary": "Waybill totals / counts summary (aggregate)",
    "monthly_pnl": "Monthly P&L rows (revenue, cogs, profit)",
    "financial_ratios": "Financial ratios (current, quick, debt/equity, margins)",
    "forecast": "Forecast block (months, revenue, expenses projections)",
    "budget": "Budget plan vs actual, monthly + YTD",
    "company_valuation": "DCF, multiple, and book value summary",
    "executive_summary": "KPIs and alerts for executive view",
    "retail_sales": "Retail sales aggregates (overall, by_object, by_month, tops)",
    "imported_products": "Imported products summary + items",
    "cashflow_summary": "Cashflow inflow/outflow/net + monthly",
    "response_meta": "Contract meta of the artifact (source, tab, row_count)",
}


# Column profiles used when `columns="minimal"` (default).
# Only fields in this list are kept for each matching section's list rows.
# Unknown sections (not listed here) skip pruning entirely.
#
# Rationale: LLM answers rarely need every engineering field, and full rows
# blow up the context window + cost. Minimal profiles keep the analytically
# useful columns. If the model truly needs more fields it can pass
# `columns="all"`.
SECTION_COLUMN_PROFILES: Dict[str, List[str]] = {
    "suppliers": [
        "tax_id",
        "ორგანიზაცია",
        "normalized_supplier",
        "waybills_count",
        "total_nominal",
        "total_effective",
        "total_paid",
        "total_debt",
        "payment_scope",
    ],
    "supplier_aging": [
        "supplier",
        "tax_id",
        "normalized_supplier",
        "ორგანიზაცია",
        "current",
        "overdue_30",
        "overdue_60",
        "overdue_90",
        "overdue_180",
        "overdue_180_plus",
        "total",
        "total_debt",
    ],
    "ap_monthly_trend": [
        "month",
        "current",
        "overdue",
        "total",
        "total_debt",
    ],
    "monthly_pnl": [
        "month",
        "revenue",
        "cogs",
        "gross_profit",
        "opex",
        "ebitda",
        "net",
    ],
    "waybills": [
        "date",
        "transport_start_date",
        "delivery_date",
        "supplier",
        "waybill_number",
        "nominal_amount",
        "effective_amount",
        "status",
        "type",
    ],
}


# Tool schema handed to Anthropic's tool-use API.
READ_DATA_JSON_TOOL: Dict[str, Any] = {
    "name": "read_data_json",
    "description": (
        "Read a scoped slice of the dashboard's `data.json` (the canonical "
        "financial data store generated from Excel sources). Use this to fetch "
        "ground-truth numbers before answering. Always cite the returned "
        "`source` path in your final reply."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "section": {
                "type": "string",
                "enum": sorted(ALLOWED_SECTIONS.keys()),
                "description": "Which top-level section of data.json to read.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_ROW_LIMIT,
                "description": (
                    f"Row cap for list sections (default {DEFAULT_ROW_LIMIT}, "
                    f"max {MAX_ROW_LIMIT}). Keep small unless you truly need "
                    "more rows — large slices blow up the context window."
                ),
            },
            "filter": {
                "type": "object",
                "description": (
                    "Optional equality filter applied to list sections. "
                    "Each key maps to a value that must match (exact or "
                    "substring for strings)."
                ),
                "additionalProperties": True,
            },
            "columns": {
                "type": "string",
                "enum": ["minimal", "all"],
                "description": (
                    "Column density for list rows. 'minimal' (default) keeps "
                    "only the core analytical fields (fewer tokens). 'all' "
                    "returns every field. Use 'minimal' unless the user needs "
                    "a field not in the minimal set."
                ),
            },
        },
        "required": ["section"],
        "additionalProperties": False,
    },
}


READ_SOURCE_CODE_TOOL: Dict[str, Any] = {
    "name": "read_source_code",
    "description": (
        "Read a bounded slice of a project source file. Allowed roots: "
        "dashboard_pipeline/, rs-dashboard/src/, tests/, server.py, "
        "generate_dashboard_data.py, backend_paths.py. Use this to inspect "
        "pipeline logic when investigating data discrepancies or bugs. "
        f"Default range: first {DEFAULT_SOURCE_LINES} lines; max per call: "
        f"{MAX_SOURCE_LINES} lines."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Project-relative path under an allowed code root.",
            },
            "line_range": {
                "type": "object",
                "description": (
                    "Optional inclusive line range. Use to zoom into a "
                    "specific function or section after a wider read."
                ),
                "properties": {
                    "start": {"type": "integer", "minimum": 1},
                    "end": {"type": "integer", "minimum": 1},
                },
                "additionalProperties": False,
            },
        },
        "required": ["file_path"],
        "additionalProperties": False,
    },
}


GREP_CODE_TOOL: Dict[str, Any] = {
    "name": "grep_code",
    "description": (
        "Regex search across project source files (allowed code roots). "
        "Returns file_path + line_number + line for each hit. Use this to "
        "locate symbols, imports, or patterns across the codebase before "
        f"reading specific files. Default cap: {DEFAULT_GREP_HITS} hits, "
        f"max {MAX_GREP_HITS}."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Python regex pattern (re module syntax).",
            },
            "path": {
                "type": "string",
                "description": (
                    "Optional sub-path (must still resolve under an allowed "
                    "code root). Default: search across all allowed code roots."
                ),
            },
            "max_hits": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_GREP_HITS,
                "description": (
                    f"Max hits returned (default {DEFAULT_GREP_HITS}, "
                    f"max {MAX_GREP_HITS}). Higher values slow the call."
                ),
            },
        },
        "required": ["pattern"],
        "additionalProperties": False,
    },
}


READ_EXCEL_SOURCE_TOOL: Dict[str, Any] = {
    "name": "read_excel_source",
    "description": (
        "Read a bounded preview of a source file under Financial_Analysis/ "
        "(.csv, .xlsx, .xls). Use this to inspect ground-truth data before "
        "validating data.json. Returns column names + first N rows. "
        f"Default nrows: {DEFAULT_EXCEL_NROWS}, max: {MAX_EXCEL_NROWS}."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Project-relative path under Financial_Analysis/.",
            },
            "sheet": {
                "type": "string",
                "description": "Sheet name for xlsx/xls (default: first sheet).",
            },
            "nrows": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_EXCEL_NROWS,
                "description": (
                    f"Max rows to read (default {DEFAULT_EXCEL_NROWS}, "
                    f"max {MAX_EXCEL_NROWS})."
                ),
            },
            "skiprows": {
                "type": "integer",
                "minimum": 0,
                "description": "Rows to skip from the top (default 0).",
            },
        },
        "required": ["file_path"],
        "additionalProperties": False,
    },
}


VALIDATE_VS_SOURCE_TOOL: Dict[str, Any] = {
    "name": "validate_vs_source",
    "description": (
        "Compare a data.json section's current row count and/or field total "
        "against user-provided expected values (usually from an Excel source). "
        "Returns match/mismatch status and a source hint for manual verification. "
        "Use when the user reports a suspected discrepancy between dashboard "
        "numbers and source data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "section": {
                "type": "string",
                "enum": sorted(ALLOWED_SECTIONS.keys()),
                "description": "data.json section to validate.",
            },
            "expected_row_count": {
                "type": "integer",
                "minimum": 0,
                "description": "Expected row count (usually counted from Excel).",
            },
            "expected_total": {
                "type": "number",
                "description": (
                    "Expected sum of `field_name` across rows. Requires "
                    "`field_name` to also be supplied."
                ),
            },
            "field_name": {
                "type": "string",
                "description": (
                    "Field to sum when `expected_total` is given. "
                    "E.g., 'total_effective' for suppliers."
                ),
            },
        },
        "required": ["section"],
        "additionalProperties": False,
    },
}


_COMPUTE_OPERATIONS: Tuple[str, ...] = (
    "sum",
    "avg",
    "min",
    "max",
    "count",
    "pct",
    "growth",
    "diff",
)


COMPUTE_TOOL: Dict[str, Any] = {
    "name": "compute",
    "description": (
        "Exact arithmetic on arbitrary numbers — MANDATORY whenever an "
        "operation touches more than 3 numbers. LLM mental arithmetic on long "
        "lists is hallucination-prone (see Feb-27 waybill bug as evidence). "
        "Always route through this tool instead of summing/averaging in your "
        "head.\n\n"
        "Operations:\n"
        "  • 'sum'    — Σ numbers[]\n"
        "  • 'avg'    — arithmetic mean of numbers[]\n"
        "  • 'min'    — smallest of numbers[]\n"
        "  • 'max'    — largest of numbers[]\n"
        "  • 'count'  — number of non-null items in numbers[]\n"
        "  • 'pct'    — percentage: (numbers[0] / numbers[1]) × 100 "
        "(exactly 2 numbers required)\n"
        "  • 'growth' — growth percent: ((numbers[1] − numbers[0]) / "
        "numbers[0]) × 100 (exactly 2 numbers, [old, new])\n"
        "  • 'diff'   — difference: numbers[1] − numbers[0] "
        "(exactly 2 numbers, [old, new])\n\n"
        "For waybill-specific totals, prefer `compute_waybill_total` — it "
        "applies the business-default exclusions (returns + cancelled) and "
        "returns per-supplier breakdowns automatically."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": list(_COMPUTE_OPERATIONS),
                "description": "Which arithmetic operation to run.",
            },
            "numbers": {
                "type": "array",
                "items": {"type": "number"},
                "description": (
                    "The numbers the operation runs on. For 'pct' / 'growth' "
                    "/ 'diff' exactly 2 items are required (order matters: "
                    "[part, whole] for pct; [old, new] for growth / diff)."
                ),
            },
            "round_digits": {
                "type": "integer",
                "description": (
                    "Decimal places to round the final result to. Default 2. "
                    "Pass a negative value to skip rounding."
                ),
            },
            "label": {
                "type": "string",
                "description": (
                    "Optional short label (e.g., 'Feb retail revenue avg') "
                    "that is echoed in the result trace — helps audit later."
                ),
            },
        },
        "required": ["operation", "numbers"],
        "additionalProperties": False,
    },
}


RECALL_CONTEXT_TOOL: Dict[str, Any] = {
    "name": "recall_context",
    "description": (
        "Search the local semantic memory (past chat summaries + indexed "
        "Excel/project content) for context relevant to a question. **Use "
        "this — not guessing — whenever the user references the past or "
        "asks about historical data not in `data.json`** "
        "(`გახსოვს?`, `3 კვირის წინ`, `ბოლოს რა გითხარი`, `გასულ წელს`, "
        "`2024 ოქტ. რა იყო`).\n\n"
        "Returns up to `limit` ranked hits with their summary text, tags, "
        "source bucket, and creation timestamp. Distance is cosine — 0 = "
        "perfect match, 1 = unrelated. **You MUST cite the matched ids in "
        "your final answer** (e.g., 'წყარო: მეხსიერება chat_alpha_2026_03_23').\n\n"
        "`source` filter:\n"
        "  • omit — search BOTH chat memory and the project index\n"
        "  • 'chat' — only past conversation summaries\n"
        "  • 'excel' — only indexed Excel content\n\n"
        "NEVER call this for questions about the CURRENT period — those "
        "live in `data.json` and should go through `read_data_json` / "
        "`compute_waybill_total` / `forecast_revenue`."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Natural-language question to search for. Georgian or "
                    "English both work (multilingual embedding model). "
                    "Maximum 500 characters."
                ),
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": (
                    "How many hits to return (default 5). Higher values "
                    "dilute relevance; use 10+ only for broad surveys."
                ),
            },
            "source": {
                "type": "string",
                "enum": ["chat", "excel"],
                "description": (
                    "Optional source filter. Omit to search both buckets."
                ),
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional tag filter (AND-ed). Examples: ['supplier:alpha'], "
                    "['year:2025', 'category:waybills']."
                ),
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}


SAVE_MEMORY_TOOL: Dict[str, Any] = {
    "name": "save_memory",
    "description": (
        "Persist a short Georgian summary of THIS conversation (or a key "
        "fact / decision / promise) into the local semantic memory so a "
        "future session can `recall_context` it.\n\n"
        "**When to call:**\n"
        "  • End of a meaningful chat — write a 2-5 sentence summary of "
        "the decision, recommendation, observation, or promise.\n"
        "  • Mid-chat when the user makes an explicit decision "
        "('ვადასტურებ X', 'მერე გადავამოწმოთ Y').\n\n"
        "**When NOT to call:**\n"
        "  • Greetings, idle chit-chat, single-fact lookups.\n"
        "  • Anything the user can re-derive in 1 second from `data.json`.\n\n"
        "Returns the new `memory_id` so you can echo it in your reply ('"
        "შენახულია — chat_2026_04_19_alpha_decision'). Idempotency: passing "
        "the same id replaces the previous entry."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": (
                    "The text to remember. 10–8000 characters. Write it "
                    "as you would explain it to a future-you starting a "
                    "new chat tomorrow — full names, full numbers, full "
                    "context. Georgian preferred."
                ),
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Free-form tags to make recall + filtering easier. "
                    "Use lowercase snake_case; namespace with ':' for "
                    "structured tags (e.g., 'supplier:alpha', "
                    "'topic:cashflow', 'kind:decision')."
                ),
            },
            "source": {
                "type": "string",
                "enum": ["chat"],
                "description": (
                    "Memory bucket. Currently only 'chat' is allowed at "
                    "tool level (project-index entries are written by the "
                    "`index_project_files.py` script, not by the chat)."
                ),
            },
        },
        "required": ["summary"],
        "additionalProperties": False,
    },
}


JOURNAL_KINDS: Tuple[str, ...] = (
    "promise",
    "ai_commitment",
    "recommendation",
    "reminder",
    "proposal",         # Phase 3.1 Co-Designer
    "repayment_plan",   # Phase 4A Debt Plan
)

JOURNAL_STATUSES: Tuple[str, ...] = ("open", "done", "cancelled")


JOURNAL_ADD_ENTRY_TOOL: Dict[str, Any] = {
    "name": "journal_add_entry",
    "description": (
        "Record a structured **commitment / promise / recommendation / "
        "reminder** into the decision journal. Journal entries are shown "
        "to the user at the start of every new chat via the `<TODAY>` "
        "preamble (overdue + 3 newest open), so they never forget a "
        "follow-up.\n\n"
        "**When to call:**\n"
        "  • user commits ('ერთ კვირაში გადავამოწმო', 'ხვალ ვიზამ') → "
        "`kind='promise'`.\n"
        "  • you commit ('შემდეგ ჩატში გადავამოწმებ', 'მომდევნო ცვლილებას "
        "დავადევნებ') → `kind='ai_commitment'`.\n"
        "  • you offered a recommendation the user engaged with "
        "('გირჩევ X-ს, შეცვლი?') → `kind='recommendation'` (outcome "
        "tracked).\n"
        "  • dated deadline (VAT, bank, supplier payment) → "
        "`kind='reminder'` with `due_date`.\n\n"
        "**When NOT to call:**\n"
        "  • greetings, idle chit-chat, single-fact lookups.\n"
        "  • 'რამდენია X?' / 'რა იყო?' — route through `read_data_json` "
        "or `recall_context` instead.\n"
        "  • acknowledgments ('კარგი', 'ვხვდები') without a concrete "
        "commitment.\n\n"
        "Returns a new `entry_id`. Idempotency: each call creates a "
        "fresh id (no deduplication). If the user corrects you "
        "('არა, ვერ ვიზამ'), call `journal_update_entry` with "
        "`status='cancelled'` rather than re-adding."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": (
                    "Short Georgian sentence describing the commitment "
                    "(3–500 chars). Imperative mood preferred: 'Alpha-ს "
                    "ვალის გადამოწმება', 'POS30BWH ტერმინალის შეცვლა', "
                    "'VAT დეკლარაცია RS.ge-ზე'."
                ),
            },
            "kind": {
                "type": "string",
                "enum": list(JOURNAL_KINDS),
                "description": (
                    "Semantic category. 'promise' = user commitment; "
                    "'ai_commitment' = AI-side follow-up; "
                    "'recommendation' = outcome-tracked AI suggestion; "
                    "'reminder' = dated external deadline."
                ),
            },
            "due_date": {
                "type": "string",
                "description": (
                    "Optional ISO `YYYY-MM-DD` deadline. Omit for "
                    "commitments without a concrete date. 'ერთ კვირაში' "
                    "→ today + 7; 'ხვალ' → today + 1; 'მომდევნო ცვლილება' "
                    "→ omit."
                ),
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional topic tags: 'supplier:alpha', "
                    "'topic:cashflow', 'topic:waybills'. The journal "
                    "auto-adds 'journal', 'kind:<kind>', 'status:open' "
                    "— do NOT pass those."
                ),
            },
        },
        "required": ["title", "kind"],
        "additionalProperties": False,
    },
}


JOURNAL_LIST_ENTRIES_TOOL: Dict[str, Any] = {
    "name": "journal_list_entries",
    "description": (
        "Query the decision journal with structured filters (no "
        "embedding search). Use this when the user asks about open "
        "commitments ('რა დაპირებები მაქვს?', 'რომელი ვადა-გადაცილებულია?', "
        "'რა დავდე recommendation-ად ამ თვეს?'). Returns a sorted list: "
        "overdue first (most-overdue → least), then upcoming open "
        "entries (earliest due first), then the rest (done / cancelled / "
        "undated).\n\n"
        "Each entry carries `overdue_days` — positive = overdue, 0 = due "
        "today, negative = still in the future, null = no due date. "
        "Cite `entry_id` in follow-ups so `journal_update_entry` has a "
        "handle.\n\n"
        "This is NOT for 'გახსოვს?'-style historical recall — those go "
        "through `recall_context`."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": list(JOURNAL_STATUSES),
                "description": (
                    "Filter by status. Default: all statuses. "
                    "'open' = active commitments; 'done' = completed; "
                    "'cancelled' = user withdrew."
                ),
            },
            "kind": {
                "type": "string",
                "enum": list(JOURNAL_KINDS),
                "description": "Optional kind filter (see journal_add_entry).",
            },
            "overdue": {
                "type": "boolean",
                "description": (
                    "When true, return only open entries whose "
                    "`due_date` has passed. Ignores entries without a "
                    "date."
                ),
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": (
                    "Max entries returned (default 20, cap 100). "
                    "Use 5–10 for a summary view."
                ),
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}


ANALYZE_DEAD_STOCK_TOOL: Dict[str, Any] = {
    "name": "analyze_dead_stock",
    "description": (
        "Triangulate `imported_products` (inventory inflow) ⊕ `retail_sales` "
        "(sell-through) and return a salvage plan for SKUs that haven't sold "
        "in N+ days. **Use this — not `read_data_json` row-by-row** — for "
        "EVERY dead-stock / liquidation / 'frozen cash' / slow-mover question:\n"
        "  • 'რა SKU-ები მაქვს stock-ში დიდი ხანია?'\n"
        "  • 'გაყინული ფული' / 'frozen cash' / 'working capital ანალიზი'\n"
        "  • 'მომწოდებელს რა დავუბრუნო?' / 'რას ვარისკავ ფასდაკლებით?'\n"
        "  • 'inventory turnover უკეთესი იქნება?'\n\n"
        "Returns:\n"
        "  • `summary` — counts per stale bucket (active / 91-180d / 181-365d "
        "/ 365+d / unmatched), `frozen_cash_estimate`, `matching_warning`\n"
        "  • `by_action` — recommended salvage action with SKU count + "
        "expected freed cash (discount_15_pct / discount_30_pct / "
        "supplier_return / write_off)\n"
        "  • `top_stale_skus` — top N SKUs sorted by frozen amount with "
        "per-SKU recommendation\n"
        "  • `notes` — caveats you MUST relay to the user verbatim, including "
        "the matching warning when it fires\n\n"
        "**`days_threshold`**: 30-730 (default 90). Boundary between 'active' "
        "and 'stale' — independent of the 91/181/365 sub-bucket boundaries.\n"
        "**`store`**: 'total' (default) / 'ოზურგეთი' / 'დვაბზუ'. Latin "
        "aliases ('ozurgeti'/'dvabzu') are accepted.\n"
        "**`top_n`**: 1-100 (default 20).\n\n"
        "⚠️ The frozen_cash_estimate is an UPPER BOUND when the matching "
        "warning fires — barcode/code drift between sources inflates the "
        "'unmatched' bucket. Always quote `matched_total_amount` plus the "
        "warning text when reporting; never call the estimate a 'precise "
        "diagnosis'. Anti-trigger: do NOT call this for plain inventory "
        "lookups ('რა მაქვს stock-ში სულ?' → `read_data_json`)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "days_threshold": {
                "type": "integer",
                "minimum": 30,
                "maximum": 730,
                "description": (
                    "Days-since-last-sale boundary that splits 'active' from "
                    "'stale' (default 90)."
                ),
            },
            "store": {
                "type": "string",
                "description": (
                    "Optional store filter. 'total' / 'ოზურგეთი' / 'დვაბზუ' "
                    "(plus 'ozurgeti'/'dvabzu' Latin aliases)."
                ),
            },
            "top_n": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": (
                    "Maximum stale SKUs returned in `top_stale_skus` "
                    "(default 20)."
                ),
            },
        },
        "additionalProperties": False,
    },
}


PREPARE_SUPPLIER_BRIEF_TOOL: Dict[str, Any] = {
    "name": "prepare_supplier_brief",
    "description": (
        "Build a 1-page negotiation brief for a supplier (or the whole "
        "portfolio) by triangulating `suppliers` ⊕ `imported_products` ⊕ "
        "`supplier_aging`. **Use this — not `read_data_json` row-by-row** — "
        "for EVERY supplier negotiation / comparison / leverage question:\n"
        "  • 'ხვალ X-თან მაქვს შეხვედრა, რა ვთხოვო?'\n"
        "  • 'ვის ფასდაკლება ვთხოვო?' / 'ჩემი leverage რა არის?'\n"
        "  • 'X-ს ვიყიდი, Y უფრო იაფია?' (comparables / switch analysis)\n"
        "  • 'ვის ვესაუბრო პირველად?' (portfolio-wide ranking)\n\n"
        "Returns (focused mode, when `supplier_name` or `tax_id` passed):\n"
        "  • `supplier` — resolved identity + match_confidence (high/medium/low)\n"
        "  • `volume_snapshot` — spend, waybills, tenure, portfolio share\n"
        "  • `payment_profile` — billed/paid/debt, unpaid %, reliability label\n"
        "  • `price_benchmark` — per-product dual-source comparisons with "
        "cheapest alternative + gap %\n"
        "  • `price_benchmark_summary` — dual-source count + estimated annual "
        "savings if switch to cheapest\n"
        "  • `leverage_score` — 0-100 with component decomposition (share, "
        "payment, dual-sourcing, tenure, relationship)\n"
        "  • `negotiation_plays` — 1-3 ranked formulations with ask_ka / "
        "give_ka / rationale_ka / evidence_refs / warning_ka\n"
        "  • `matching_warnings` — emitted when match_confidence != high or "
        "imported_products lookup fails\n\n"
        "Returns (portfolio mode, when no identifier passed):\n"
        "  • `concentration` — Pareto shares (top 5/10/20), HHI, label\n"
        "  • `top_candidates` — ranked by leverage_score × savings, not just "
        "spend — includes per-candidate headline play\n"
        "  • `aggregate_savings_opportunity_ge` — full-portfolio annual upside\n\n"
        "**Identity confidence protocol:** if `match_confidence` is "
        "`medium` or `low`, ASK the user to confirm the identity BEFORE "
        "quoting numbers (example: 'ჩემი ვარაუდი X-ს ქვეშ ვიპოვე tax_id "
        "123456789 — ეს გჭირდება?'). Never silently trust a partial match.\n\n"
        "**Relationship discipline:** every play carries `warning_ka` for "
        "moves that could damage the relationship. Relay these verbatim. "
        "Never invent aggressive moves — stick to the ranked output.\n\n"
        "Anti-trigger: do NOT call this for plain lookups ('რამდენი ვალი "
        "მაქვს X-თან' → `read_data_json(section='supplier_aging')`; "
        "'X-ის ბოლო ზედნადები' → `read_data_json(section='waybills')`)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "supplier_name": {
                "type": "string",
                "description": (
                    "Supplier display name (Georgian or Latin). Fuzzy-matched "
                    "against `ორგანიზაცია` with legal-prefix stripping. "
                    "Ignored when `tax_id` is supplied."
                ),
            },
            "tax_id": {
                "type": "string",
                "description": (
                    "9-11 digit Georgian tax id (e.g., '406181616'). Takes "
                    "precedence over `supplier_name`. Use this when the "
                    "user quotes a tax id explicitly."
                ),
            },
            "lookback_months": {
                "type": "integer",
                "minimum": 1,
                "maximum": 36,
                "description": (
                    "How many months back to consider (default 12). Clamped."
                ),
            },
            "top_n": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": (
                    "Portfolio-mode: number of top candidates returned "
                    "(default 10). Ignored in focused mode."
                ),
            },
            "benchmark_n": {
                "type": "integer",
                "minimum": 1,
                "maximum": 30,
                "description": (
                    "Focused mode: maximum rows in `price_benchmark` "
                    "(default 10). Ignored in portfolio mode."
                ),
            },
        },
        "additionalProperties": False,
    },
}


JOURNAL_UPDATE_ENTRY_TOOL: Dict[str, Any] = {
    "name": "journal_update_entry",
    "description": (
        "Transition a journal entry's status after the user reports an "
        "outcome. Status transitions:\n"
        "  • 'done'      — commitment fulfilled ('Alpha-ს ვალი შესრულდა')\n"
        "  • 'cancelled' — user withdrew ('აღარ მინდა ამის გაკეთება')\n"
        "  • 'open'      — rollback if needed (rare)\n\n"
        "Always call this when the user says 'შესრულდა', 'გავაკეთე', "
        "'აღარ საჭიროა', 'გააუქმე' about a specific commitment. You "
        "need the `entry_id` — get it from `journal_list_entries` or "
        "from the `<TODAY>` preamble."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "entry_id": {
                "type": "string",
                "description": (
                    "The `entry_id` returned by `journal_add_entry` or "
                    "listed by `journal_list_entries` (format: "
                    "`journal_<32-hex>`)."
                ),
            },
            "status": {
                "type": "string",
                "enum": list(JOURNAL_STATUSES),
                "description": "Target status.",
            },
        },
        "required": ["entry_id", "status"],
        "additionalProperties": False,
    },
}


FORECAST_REVENUE_TOOL: Dict[str, Any] = {
    "name": "forecast_revenue",
    "description": (
        "Forecast the next N months of revenue (POS income) using a Prophet "
        "+ ARIMA ensemble run locally against `monthly_pnl`. **Use this — not "
        "mental arithmetic — for EVERY forward-looking revenue question** "
        "(`მომავალი`, `პროგნოზი`, `რამდენი იქნება`, `მომდევნო თვე`).\n\n"
        "Returns a per-month table with baseline + optimistic (95% upper) + "
        "pessimistic (95% lower) bounds, plus YoY growth and a list of "
        "caveats you MUST include in your final answer. Narrates the engines "
        "used ('prophet', 'arima', or both) so the user knows whether the "
        "forecast is a full ensemble or a degraded single-engine fallback.\n\n"
        "Horizon is clamped to 1-12 months (default 3). Requires at least "
        "12 months of history; shorter series return an explicit error "
        "rather than a bogus-confidence number.\n\n"
        "`store` values:\n"
        "  • omit or 'total' — combined across every store\n"
        "  • 'ოზურგეთი' — Ozurgeti only (3 POS, urban)\n"
        "  • 'დვაბზუ'   — Dvabzu only (2 POS, rural)\n\n"
        "NEVER run this for historical questions — Prophet outputs projections, "
        "not ground truth. For past totals use `read_data_json(section="
        "'monthly_pnl')` or `compute_waybill_total`."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "horizon_months": {
                "type": "integer",
                "minimum": 1,
                "maximum": 12,
                "description": (
                    "How many future months to forecast. Default 3 (the "
                    "sweet spot where Prophet's confidence is highest). "
                    "Values above 6 widen the 95% interval noticeably."
                ),
            },
            "store": {
                "type": "string",
                "enum": ["total", "ოზურგეთი", "დვაბზუ"],
                "description": (
                    "Which store to forecast. Default: 'total' (combined). "
                    "Pass 'ოზურგეთი' or 'დვაბზუ' for a single-store view."
                ),
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}


COMPUTE_WAYBILL_TOTAL_TOOL: Dict[str, Any] = {
    "name": "compute_waybill_total",
    "description": (
        "Compute EXACT sum of waybill amounts for a given date (substring "
        "match against the chosen date field). Server-side arithmetic — use "
        "this INSTEAD of fetching rows via read_data_json and summing them "
        "mentally (LLM arithmetic on long lists is hallucination-prone). "
        "Returns the total, matched row count, and top-10 suppliers by "
        "contribution.\n\n"
        "`date_field` selects WHICH date column to filter by:\n"
        "  • 'transport_start_date' (default, matches 'ზედნადები შემოვიდა')\n"
        "  • 'date' (RS activation / გააქტიურების თარ.)\n"
        "  • 'delivery_date' (ჩაბარების თარ.)\n\n"
        "By default excludes returns (type='უკან დაბრუნება') and cancelled "
        "(status='გაუქმებული'), matching the business meaning of 'received'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": (
                    "Date substring to match (e.g., 'YYYY-MM-DD' for a single "
                    "day or 'YYYY-MM' for a whole month). Case-sensitive."
                ),
            },
            "date_field": {
                "type": "string",
                "enum": ["date", "transport_start_date", "delivery_date"],
                "description": (
                    "Which date column to filter by. Default: "
                    "'transport_start_date' (business 'შემოვიდა' semantics)."
                ),
            },
            "exclude_returns": {
                "type": "boolean",
                "description": (
                    "Exclude rows where `type` contains 'უკან დაბრუნება'. "
                    "Default: true."
                ),
            },
            "exclude_cancelled": {
                "type": "boolean",
                "description": (
                    "Exclude rows where `status` contains 'გაუქმებული'. "
                    "Default: true."
                ),
            },
            "amount_field": {
                "type": "string",
                "enum": ["nominal_amount", "effective_amount"],
                "description": (
                    "Which amount column to sum. 'nominal_amount' = raw თანხა "
                    "(matches Excel exactly); 'effective_amount' = post-return "
                    "adjustment. Default: 'nominal_amount'."
                ),
            },
            "supplier": {
                "type": "string",
                "description": (
                    "Optional supplier substring filter (case-insensitive). "
                    "Omit to include all suppliers."
                ),
            },
        },
        "required": ["date"],
        "additionalProperties": False,
    },
}


COMPUTE_CASH_RUNWAY_TOOL: Dict[str, Any] = {
    "name": "compute_cash_runway",
    "description": (
        "Phase 3.5 — compute how many months/days the business can survive "
        "at the current burn rate, given USER-PROVIDED current cash balance. "
        "The tool triangulates user-provided BOG + TBC balances with the "
        "`monthly_pnl` burn trend from `data.json`.\n\n"
        "**Triggers (CRITICAL):** cash-runway / liquidity / survival / "
        "'რამდენი თვე ვძლებ', 'cash runway რა არის?', 'ფული თავდება?', "
        "'ქესი ფული საკმარისია?', 'რამდენ დღეს ვცოცხლობ ფულის გარეშე?'.\n\n"
        "**Anti-triggers (NEVER call):**\n"
        "  • plain balance lookup ('რამდენი ფული მაქვს?') → the USER knows "
        "their live balance via their bank app; do NOT imply runway.\n"
        "  • historical P&L question ('რამდენი გახარჯე 2026-02-ში?') → "
        "`read_data_json(section='monthly_pnl')`.\n"
        "  • strategic 'should I invest / open new store?' — use `forecast_revenue` "
        "and strategic reasoning instead.\n\n"
        "**Workflow MANDATE:** before calling this tool, ALWAYS ask the user for "
        "their current BOG + TBC balances verbatim (they have the bank app open — "
        "they know). NEVER guess, NEVER extrapolate from historical bank extracts. "
        "The user's live balance is the ONLY source of truth for `current_balance_*_ge`. "
        "If the user already provided a single combined figure, pass it via "
        "`current_balance_bog_ge` and set `current_balance_tbc_ge=0` (or vice versa).\n\n"
        "**Returns:** `{current_cash_ge, current_cash_breakdown, lookback_months, "
        "burn_rate_ge_per_month, burn_trend, burn_history, runway_months, "
        "runway_days, runway_label, status_summary_ka, notes}` where "
        "`runway_label ∈ {🟢 SAFE ≥6mo, 🟡 WATCH 2-6mo, 🔴 CRITICAL <2mo, "
        "🟢 PROFIT}`; `runway_months=-1` and `runway_days=-1` encode ∞ "
        "(profitable business → no runway concern).\n\n"
        "**Honesty rule:** always surface `burn_trend` verbatim in your answer. "
        "`accelerating` trend means the runway figure is optimistic (ხარჯი "
        "სწრაფად იზრდება), `decelerating` means it is pessimistic (ხარჯი "
        "ქრება). `insufficient_history` means do not oversell certainty."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "current_balance_bog_ge": {
                "type": "number",
                "description": (
                    "Current BOG (Bank of Georgia) cash balance in GEL, as "
                    "the user reads it from their bank app TODAY. "
                    "Non-negative. If user has no BOG account, pass 0."
                ),
            },
            "current_balance_tbc_ge": {
                "type": "number",
                "description": (
                    "Current TBC cash balance in GEL, as the user reads it "
                    "TODAY. Non-negative. If user has no TBC account, pass 0. "
                    "At least one of bog/tbc must be > 0."
                ),
            },
            "lookback_months": {
                "type": "integer",
                "minimum": 1,
                "maximum": 12,
                "description": (
                    "How many of the most recent months to average over "
                    "when computing burn rate. Default 3. Use 6 for a "
                    "smoother, more robust figure; 1 only for a quick "
                    "instant snapshot."
                ),
            },
        },
        "required": ["current_balance_bog_ge", "current_balance_tbc_ge"],
        "additionalProperties": False,
    },
}


PROPOSE_FEATURE_TOOL: Dict[str, Any] = {
    "name": "propose_feature",
    "description": (
        "Phase 3.1 Co-Designer — record a structured, user-facing feature "
        "proposal for the Financial Dashboard. The proposal is persisted in "
        "the decision journal as `kind='proposal'` so the user can recall, "
        "accept, or reject it later via `journal_list_entries(kind=\"proposal\")`.\n\n"
        "**Pull-only policy (CRITICAL):** call this tool ONLY when the user "
        "asks a direct open-ended co-design question. Accepted triggers: "
        "„რას შემომთავაზებდი?” / „რა ახალი feature გვინდა?” / „რა იდეები გაქვს?” / "
        "„შემომთავაზე რამე” / „co-designer” / direct roadmap requests.\n\n"
        "**Anti-triggers (NEVER call):** strategic business questions (sales, "
        "margins, suppliers) — answer with facts, do NOT append a proposal. "
        "Data lookups („რამდენია X?”) — route through `read_data_json`. "
        "Crisis analysis (−X% margin, AP overdue) — surface facts + critique, "
        "NEVER auto-propose a feature. Repeated questions on the same topic "
        "(3+ in a week) — still NO auto-trigger; wait for explicit "
        "„შემომთავაზე” phrasing.\n\n"
        "**Structured output contract (6 fields, all mandatory):**\n"
        "  • `title` — short Georgian headline (3–500 chars), imperative "
        "mood preferred.\n"
        "  • `problem` — what current UI/workflow fails to address (1–2 "
        "sentences, Georgian).\n"
        "  • `benefit` — concrete user payoff: time / money / accuracy "
        "(1–2 sentences).\n"
        "  • `mvp_scope` — minimum shippable surface that still delivers "
        "value (2–4 sentences).\n"
        "  • `data_needed` — existing data.json sections / new Excel inputs "
        "/ extra indexing (1–2 sentences).\n"
        "  • `time_estimate` — rough dev duration (e.g. `„2–3 დღე”`).\n"
        "  • `risk_critique` — AI's SELF-critique of the proposal's weakest "
        "link. Do NOT write „რისკი არ არის” — find the real soft spot. "
        "This field is non-negotiable (prevents low-quality proposals).\n\n"
        "Returns `{ok, entry_id, title, kind='proposal', status='open', "
        "due_date='', tags, created_at, proposal: {...6 fields}}`. Cite the "
        "`entry_id` in your user-facing reply so later calls to "
        "`journal_update_entry(entry_id, status='done'|'cancelled')` "
        "have a handle.\n\n"
        "Optional `tags`: topic tags (`topic:dashboard`, `topic:dead_stock`, "
        "`feature:<slug>`). The journal auto-adds `journal`, `kind:proposal`, "
        "`status:open` — do NOT pass those."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": (
                    "Short Georgian headline for the proposed feature "
                    "(3–500 chars). E.g. „გაყინული სტოკის ძე Dashboard გვერდი”, "
                    "„წვევული cash runway widget”."
                ),
            },
            "problem": {
                "type": "string",
                "description": (
                    "Georgian sentence (or two) describing what the current "
                    "Dashboard / AI workflow cannot do today and why the "
                    "user feels friction. Be concrete — quote a specific "
                    "recurring question or manual task."
                ),
            },
            "benefit": {
                "type": "string",
                "description": (
                    "Concrete user payoff: minutes saved per week, GEL "
                    "recovered, error reduction. If you cannot quantify, "
                    "say so — but be specific („დრო დაახლოებით 15 "
                    "წთ/კვირაში”)."
                ),
            },
            "mvp_scope": {
                "type": "string",
                "description": (
                    "Minimum shippable slice. Tightly bounded: what "
                    "columns/charts/buttons appear in v1. Avoid scope "
                    "creep — future enhancements belong in a separate "
                    "proposal."
                ),
            },
            "data_needed": {
                "type": "string",
                "description": (
                    "Which existing data.json sections power this? Is a "
                    "new Excel source needed? Would ChromaDB re-indexing "
                    "be required? Be honest about prerequisites."
                ),
            },
            "time_estimate": {
                "type": "string",
                "description": (
                    "Rough dev duration, e.g. `„2–3 დღე”`, `„1 კვირა”`, "
                    "`„უკვე არსებულ მოდულს ემატება — ნახევარი დღე”`."
                ),
            },
            "risk_critique": {
                "type": "string",
                "description": (
                    "YOUR OWN critique of the proposal's weakest link. "
                    "Mandatory — if you cannot find a real risk, do NOT "
                    "call this tool. Examples: barcode drift, data "
                    "staleness, over-scope, user adoption."
                ),
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional topic tags (`topic:dashboard`, "
                    "`feature:dead_stock_page`). Do NOT pass `journal` / "
                    "`kind:proposal` / `status:open` — auto-added."
                ),
            },
        },
        "required": [
            "title",
            "problem",
            "benefit",
            "mvp_scope",
            "data_needed",
            "time_estimate",
            "risk_critique",
        ],
        "additionalProperties": False,
    },
}


BUILD_DEBT_PLAN_TOOL: Dict[str, Any] = {
    "name": "build_debt_repayment_plan",
    "description": (
        "Phase 4A — compose a 1-2 month debt repayment plan that clears 3-5 "
        "critical suppliers while keeping baseline payments flowing to the "
        "rest. AUTONOMOUS strategic advisor tool: when called without "
        "`priority_suppliers`, auto-detects the most critical suppliers using "
        "a 4-factor score (debt magnitude 30% + aging 25% + supply frequency "
        "25% + payment dysfunction 20%) and forecasts next-month inflow from "
        "the last 3 months of `monthly_pnl`. Returns per-supplier recommended "
        "monthly + weekly payments, days-to-clear estimates, baseline minima "
        "for non-priority suppliers, allocation summary (priority vs baseline "
        "vs buffer), and risk flags.\n\n"
        "**Triggers (proactive):** any discussion of paying down debt, "
        "prioritizing suppliers, distributing cash among suppliers, reducing "
        "AP, 'ვალის გეგმა', 'როგორ გადავიხადო', 'რომელ მომწოდებელს რა ოდენობა', "
        "'კომპანიებზე როგორ გავანაწილო ფული', 'პრიორიტეტული მომწოდებლები', "
        "'გეგმა შევადგინო / შევადგინოთ', 'რამდენი ვასაძეს / კოკაკოლას'. Call "
        "IMMEDIATELY — do not ask the user to pick suppliers first, the tool "
        "proposes them.\n\n"
        "**Phase 4 philosophy:** AI proposes, user approves or edits. NEVER "
        "'ask first' — infer everything from available data (supplier_aging, "
        "monthly_pnl, waybill history). Surface confidence labels per-supplier "
        "so user can spot shallow-history cases. Always output `rationale_ka` "
        "citing which 2+ factors made each supplier critical.\n\n"
        "**Anti-triggers:** single-supplier deep negotiation brief → use "
        "`prepare_supplier_brief`; portfolio-wide leverage ranking → use "
        "`prepare_supplier_brief` without args; cash-runway check → use "
        "`compute_cash_runway`.\n\n"
        "**Returns:** `{as_of_date, plan_duration_months, forecast, "
        "priority_suppliers[*], non_priority_summary, allocation_summary, "
        "risks[], summary_ka, notes[]}` where `priority_suppliers[i]` "
        "contains `{tax_id, org, total_debt_ge, days_since_last, "
        "criticality_score, criticality_reasons[], "
        "historical_monthly_paid_ge, recommended_monthly_payment_ge, "
        "recommended_weekly_payment_ge, days_to_clear_est, "
        "confidence_label, rationale_ka}`, and `allocation_summary` reports "
        "`{priority_monthly_ge, non_priority_monthly_ge, buffer_ge, "
        "buffer_pct, forecast_ge, sustainable: bool}`. If the plan is not "
        "sustainable (total > 90% of forecast), a risk flag is always "
        "emitted and must be surfaced verbatim."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "priority_suppliers": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional list of supplier names (fragments OK) or tax_ids "
                    "to prioritize explicitly. OMIT for AI auto-detection — "
                    "the tool will pick the top-N most critical suppliers "
                    "based on the 4-factor score. Maximum 8 items."
                ),
                "maxItems": 8,
            },
            "plan_duration_months": {
                "type": "integer",
                "minimum": 1,
                "maximum": 6,
                "description": (
                    "Target window (months) to clear priority debts. Default "
                    "2. Longer windows lower each month's burden but keep "
                    "debt aging-bucket open longer."
                ),
            },
            "max_priority_count": {
                "type": "integer",
                "minimum": 2,
                "maximum": 8,
                "description": (
                    "Upper bound on auto-detected priority suppliers (default "
                    "5). Ignored when `priority_suppliers` is provided."
                ),
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}


COMPUTE_CASH_FLOW_PROJECTION_TOOL: Dict[str, Any] = {
    "name": "compute_cash_flow_projection",
    "description": (
        "Phase 2.1 — project the DAILY cash trajectory over the next 7–60 "
        "days. Complements `compute_cash_runway` (static 'months left at "
        "current burn') with a day-by-day forward view that identifies "
        "SPECIFIC red days ('17–19 მაისს cash −8,200 ₾').\n\n"
        "**Triggers (CRITICAL):** any forward-looking daily cash question: "
        "'მომდევნო 2 კვირაში რამდენი cash მექნება?', 'როდის ჩავარდები "
        "მინუსში?', 'cash flow projection', 'daily cash plan', "
        "'14 დღიანი პროგნოზი', 'გადავრჩები კვირას?', 'როდის მოვა "
        "პრობლემა?'.\n\n"
        "**Anti-triggers (NEVER call):**\n"
        "  • static runway ('რამდენ თვეს ვცოცხლობ?') → `compute_cash_runway`\n"
        "  • plain balance lookup → user knows via bank app\n"
        "  • month-level revenue forecast → `forecast_revenue`\n"
        "  • historical burn analysis → `read_data_json(section='monthly_pnl')`.\n\n"
        "**Workflow MANDATE:** ALWAYS ask the user for BOG + TBC balances "
        "verbatim before calling. NEVER guess balances. If the user knows "
        "upcoming fixed commitments (rent, royalty, loan instalments, tax "
        "payments) ask for `{date, amount_ge, label}` triplets and pass "
        "them via `upcoming_payments` so they land on the right day rather "
        "than smeared into the smoothed baseline.\n\n"
        "**Returns:** `{as_of_date, horizon_days, opening_balance_ge, "
        "daily_income_baseline_ge, daily_burn_ge, daily_projection[], "
        "risk_windows[], ending_balance_ge, minimum_balance_ge, "
        "minimum_balance_date, forecast_engines[], summary_ka, notes[]}`. "
        "Each `daily_projection[i]` = `{date, opening_ge, income_ge, "
        "outflow_ge, scheduled_payments[], closing_ge, status}` where "
        "`status ∈ {🟢 SAFE, 🟡 WATCH (<1 week buffer), 🔴 RED (closing <0)}`. "
        "`risk_windows[]` collapses consecutive 🔴 days into `{start_date, "
        "end_date, days, min_balance_ge, lowest_day}`.\n\n"
        "**Honesty rule:** surface `summary_ka` verbatim — it already cites "
        "the red-day count, the worst day, and the forecast engine mix. "
        "Daily numbers are SMOOTHED baselines (POS income averaged across "
        "days; real Saturday > Wednesday swings are ±10–20%). If "
        "`forecast_engines` is empty, income baseline fell back to a "
        "historical average — confidence is lower, say so."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "current_balance_bog_ge": {
                "type": "number",
                "description": (
                    "Current BOG (Bank of Georgia) cash balance in GEL, as "
                    "the user reads it from their bank app TODAY. "
                    "Non-negative. If user has no BOG account, pass 0."
                ),
            },
            "current_balance_tbc_ge": {
                "type": "number",
                "description": (
                    "Current TBC cash balance in GEL, as the user reads it "
                    "TODAY. Non-negative. If user has no TBC account, pass 0. "
                    "At least one of bog/tbc must be > 0."
                ),
            },
            "horizon_days": {
                "type": "integer",
                "minimum": 7,
                "maximum": 60,
                "description": (
                    "How many days forward to project. Default 14 (two weeks "
                    "is the most actionable planning window for a retail "
                    "shop). Values above 30 widen forecast uncertainty."
                ),
            },
            "store": {
                "type": "string",
                "enum": ["total", "ოზურგეთი", "დვაბზუ"],
                "description": (
                    "Which store's revenue to forecast. Default: 'total' "
                    "(combined). Pass 'ოზურგეთი' or 'დვაბზუ' for a "
                    "single-store projection."
                ),
            },
            "lookback_months": {
                "type": "integer",
                "minimum": 1,
                "maximum": 12,
                "description": (
                    "How many recent months to average over when computing "
                    "the smoothed daily burn baseline. Default 3."
                ),
            },
            "upcoming_payments": {
                "type": "array",
                "description": (
                    "Optional list of known fixed commitments to overlay on "
                    "specific days (rent, royalty, loan instalments, tax "
                    "payments). Entries outside [start, end] or with "
                    "invalid fields are silently dropped with a warning in "
                    "`notes`."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "YYYY-MM-DD when the payment falls.",
                        },
                        "amount_ge": {
                            "type": "number",
                            "description": "Payment amount in GEL (positive).",
                        },
                        "label": {
                            "type": "string",
                            "description": (
                                "Short label, e.g. 'ქირა', 'royalty', "
                                "'სესხის გადახდა'. Default 'გადახდა'."
                            ),
                        },
                    },
                    "required": ["date", "amount_ge"],
                    "additionalProperties": False,
                },
                "maxItems": 30,
            },
        },
        "required": ["current_balance_bog_ge", "current_balance_tbc_ge"],
        "additionalProperties": False,
    },
}


SCENARIO_SIMULATOR_TOOL: Dict[str, Any] = {
    "name": "simulate_scenario",
    "description": (
        "Phase 2.2 — run a deterministic what-if against a baseline month "
        "from `monthly_pnl`. Given price/volume/expense/fixed-cost knobs, "
        "returns baseline vs scenario side-by-side plus a decision indicator "
        "(🟢 PROFIT_IMPROVE / 🟡 NEUTRAL / 🔴 PROFIT_ERODE).\n\n"
        "**Triggers (CRITICAL):** any what-if / trade-off / sensitivity "
        "question: 'თუ ფასი ავწიე 5%-ით, რა მოხდება?', 'volume 10%-ით "
        "რომ დამეცა?', 'ხელფასის +10% რა დამიჯდება?', 'ფასდაკლება რას "
        "გამოიღებს?', 'scenario', 'simulation', 'what-if', '+5% "
        "ფასი → −8% volume', 'ან-ან რა სჯობს?'.\n\n"
        "**Anti-triggers (NEVER call):**\n"
        "  • historical month lookup ('რამდენი მოგება მქონდა 2026-02-ში?') "
        "→ `read_data_json(section='monthly_pnl')`\n"
        "  • forward revenue forecast ('მომდევნო 3 თვე') → `forecast_revenue`\n"
        "  • daily cash trajectory → `compute_cash_flow_projection`\n"
        "  • supplier-specific negotiation → `prepare_supplier_brief`.\n\n"
        "**Price × volume coupling (IMPORTANT):** when you pass "
        "`price_change_pct` alone (no explicit `volume_change_pct`), the "
        "tool auto-applies price elasticity (default -0.8 — price-elastic "
        "retail). Example: price_change_pct=+5 → volume_change_pct=-4.0 "
        "auto. If the user has a different elasticity assumption ('ჩემი "
        "მომხმარებელი ერთგულია'), pass `price_elasticity=-0.3` (less "
        "elastic) or `volume_change_pct=0` explicitly to disable the "
        "auto-apply.\n\n"
        "**Variable vs fixed cost split:** retail expenses are split "
        "`cogs_share` variable (scales with volume) + the rest fixed "
        "(stays flat when volume moves). Default `cogs_share=0.5`; "
        "override if the user has a concrete cost structure. "
        "`expense_change_pct` applies on top of the split (captures wage "
        "raises, rent index, general inflation). `fixed_cost_delta_ge` "
        "adds one-off additions like new equipment.\n\n"
        "**Returns:** `{base_period_used, store, scenario_label, baseline, "
        "scenario, deltas, adjustments_applied, decision_indicator, "
        "summary_ka, notes[]}`. `baseline` / `scenario` = "
        "`{revenue_ge, expenses_ge, net_ge, margin_pct}`; `deltas` = "
        "`{revenue_ge, expenses_ge, net_ge, margin_pp}` where `margin_pp` "
        "is percentage-point change. `decision_indicator` uses a ±2%-of-"
        "baseline-revenue band so rounding noise never flips to improve/erode.\n\n"
        "**Honesty rule:** ALWAYS surface `summary_ka` verbatim — it cites "
        "baseline→scenario net, margin pp delta, and decision. If "
        "`adjustments_applied.volume_implied_by_elasticity` is true, state "
        "it: 'volume -4% ავტომატურად დავიანგარიშე price elasticity -0.8-ით'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "base_period": {
                "type": "string",
                "description": (
                    "Which historical month to use as baseline. Options: "
                    "'last_month' (default — most recent in monthly_pnl), "
                    "'last_3_avg' (smoothed avg of last 3 months — reduces "
                    "single-month noise), or an explicit 'YYYY-MM' string."
                ),
            },
            "store": {
                "type": "string",
                "enum": ["total", "ოზურგეთი", "დვაბზუ"],
                "description": (
                    "Which store's P&L to simulate. Default: 'total' "
                    "(combined). Pass 'ოზურგეთი' or 'დვაბზუ' for a "
                    "single-store what-if."
                ),
            },
            "price_change_pct": {
                "type": "number",
                "description": (
                    "Percent change in unit price, e.g. +5 = raise prices 5%. "
                    "Default 0. When non-zero and `volume_change_pct` is "
                    "omitted, elasticity auto-computes the volume response."
                ),
            },
            "volume_change_pct": {
                "type": "number",
                "description": (
                    "Percent change in units sold, e.g. -8 = volume drops 8%. "
                    "Default 0. Pass explicitly (incl. 0) to override the "
                    "elasticity auto-compute from price_change_pct."
                ),
            },
            "expense_change_pct": {
                "type": "number",
                "description": (
                    "Percent change in total expenses on top of the "
                    "variable/fixed split (e.g. +10 = wages up 10%). Default 0."
                ),
            },
            "fixed_cost_delta_ge": {
                "type": "number",
                "description": (
                    "One-off GEL addition/subtraction to fixed cost (e.g. "
                    "+3000 for new equipment, -2000 for cancelling a "
                    "subscription). Default 0."
                ),
            },
            "price_elasticity": {
                "type": "number",
                "description": (
                    "Price elasticity of demand, used ONLY when "
                    "`volume_change_pct` is omitted and `price_change_pct` "
                    "is set. Default -0.8 (price-elastic retail). Clamped "
                    "to [-5, 0]. Less elastic example: -0.3 (customer "
                    "loyalty). Unit-elastic: -1.0."
                ),
            },
            "cogs_share": {
                "type": "number",
                "description": (
                    "Fraction of expenses that scales with volume (variable "
                    "cost share). Default 0.5. Accepts fractions (0.6) or "
                    "percents (60). Clamped to [0, 1]."
                ),
            },
            "scenario_label": {
                "type": "string",
                "description": (
                    "Optional human-readable label shown in summary_ka "
                    "(e.g. 'ფასი +5% · ხელფასი +10%'). Default empty."
                ),
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}


PRODUCT_PROFITABILITY_XRAY_TOOL: Dict[str, Any] = {
    "name": "analyze_product_profitability",
    "description": (
        "Phase 2.5 — Product Profitability X-Ray. Scans "
        "`retail_sales.by_product` and surfaces the worst margin bleeders "
        "+ best margin earners + suspicious entries (margin outside "
        "[-5%, 90%] = likely data entry error). Answers 'რომელი SKU "
        "ვკარგავ?' / 'რომელი პროდუქტი სიცოცხლეს მოიტანს?' / 'product "
        "profitability'.\n\n"
        "**Triggers (CRITICAL):** any product-level margin question: "
        "'რომელი პროდუქტი იზიდავს ფულს?', 'margin რომელ SKU-ზე დაბალია?', "
        "'რა პროდუქტები უნდა მოვიშორო?', 'product X-ray', 'რომელ კატეგორიაში "
        "margin პრობლემაა?', 'ტოპ 10 საუკეთესო/საუარესო პროდუქტი'.\n\n"
        "**Anti-triggers (NEVER call):**\n"
        "  • supplier-level analysis ('ვასაძეს რა ფული უნდა?') → "
        "`prepare_supplier_brief`\n"
        "  • category/store-level P&L (not product-level) → "
        "`read_data_json(section='monthly_pnl')`\n"
        "  • dead stock (unsold items) → `analyze_dead_stock`\n"
        "  • future price simulation → `simulate_scenario`.\n\n"
        "**Flags explained:**\n"
        "  • 🟢 HEALTHY — margin ≥ 15% (retail comfort zone)\n"
        "  • 🟡 THIN — margin 5–15% (vulnerable to any cost shock)\n"
        "  • 🔴 BLEEDING — margin < 5% (losing money OR near-zero)\n"
        "  • ⚠️ SUSPICIOUS — margin outside [-5%, 90%]: negative = "
        "selling below cost (data error or liquidation); > 90% = likely "
        "cost field missing. Quarantined from best/worst rankings.\n\n"
        "**Revenue threshold:** products with revenue < "
        "`min_revenue_threshold_ge` (default 500 ₾) are EXCLUDED from "
        "ranking — a product sold once for 12 ₾ doesn't deserve "
        "'worst performer' status. Raise threshold for store-level focus, "
        "lower for deep analysis.\n\n"
        "**Returns:** `{store, category_filter, min_revenue_threshold_ge, "
        "top_n, products_scanned, products_qualified, worst_performers[], "
        "best_performers[], suspicious[], portfolio_margin_pct, summary_ka, "
        "notes[]}`. Each entry in worst/best/suspicious = `{product_name, "
        "category, product_code, revenue_ge, cost_ge, profit_ge, "
        "gross_margin_pct, total_quantity, flag}`.\n\n"
        "**Honesty rule:** ALWAYS surface `summary_ka` verbatim — it "
        "cites portfolio margin, worst SKU, best SKU, and suspicious "
        "count. If `suspicious` is non-empty, warn the user explicitly "
        "that those rows need Excel verification before action — "
        "acting on a data-entry error can waste a week of work."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "store": {
                "type": "string",
                "enum": ["total", "ოზურგეთი", "დვაბზუ"],
                "description": (
                    "Which store's product-level P&L to x-ray. Default: "
                    "'total' (aggregate). Single-store mode reads the "
                    "per-product object_breakdown block."
                ),
            },
            "top_n": {
                "type": "integer",
                "minimum": 3,
                "maximum": 50,
                "description": (
                    "How many to return in worst_performers and "
                    "best_performers (each). Default 10. Raise for a "
                    "deeper review; 3-5 for a quick executive summary."
                ),
            },
            "category_filter": {
                "type": "string",
                "description": (
                    "Optional case-insensitive substring matched against "
                    "product category. Example: 'ფრენჩიზი', 'ალკოჰოლი', "
                    "'სულ რძე'. Omit to scan every category."
                ),
            },
            "min_revenue_threshold_ge": {
                "type": "number",
                "minimum": 0,
                "description": (
                    "Minimum GEL revenue required for a product to enter "
                    "the ranking. Default 500. Prevents one-off sales "
                    "from dominating 'worst margin' lists."
                ),
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}


TOOL_SCHEMAS: List[Dict[str, Any]] = [
    READ_DATA_JSON_TOOL,
    COMPUTE_WAYBILL_TOTAL_TOOL,
    COMPUTE_TOOL,
    FORECAST_REVENUE_TOOL,
    RECALL_CONTEXT_TOOL,
    SAVE_MEMORY_TOOL,
    JOURNAL_ADD_ENTRY_TOOL,
    JOURNAL_LIST_ENTRIES_TOOL,
    JOURNAL_UPDATE_ENTRY_TOOL,
    ANALYZE_DEAD_STOCK_TOOL,
    PREPARE_SUPPLIER_BRIEF_TOOL,
    COMPUTE_CASH_RUNWAY_TOOL,
    COMPUTE_CASH_FLOW_PROJECTION_TOOL,
    BUILD_DEBT_PLAN_TOOL,
    SCENARIO_SIMULATOR_TOOL,
    PRODUCT_PROFITABILITY_XRAY_TOOL,
    READ_SOURCE_CODE_TOOL,
    GREP_CODE_TOOL,
    READ_EXCEL_SOURCE_TOOL,
    VALIDATE_VS_SOURCE_TOOL,
    PROPOSE_FEATURE_TOOL,
]


def get_cached_tool_schemas() -> List[Dict[str, Any]]:
    """Return a deep-copy of `TOOL_SCHEMAS` with `cache_control` on the last tool.

    Anthropic prompt caching requires `cache_control: {"type": "ephemeral"}`
    on the final block of the cacheable prefix. For tools that means the
    last entry in the `tools=[...]` list.

    We mutate a copy so the module-level constant remains pure (tests assert
    on it, other non-Anthropic consumers may import it).
    """
    cached = copy.deepcopy(TOOL_SCHEMAS)
    if cached:
        cached[-1]["cache_control"] = {"type": "ephemeral"}
    return cached


# ---------------------------------------------------------------------------
# Filter + truncation helpers
# ---------------------------------------------------------------------------

def _match_filter(row: Any, criteria: Dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
    for key, expected in criteria.items():
        if key not in row:
            return False
        actual = row[key]
        if isinstance(expected, str) and isinstance(actual, str):
            if expected.lower() not in actual.lower():
                return False
        elif actual != expected:
            return False
    return True


def _project_row(row: Any, keep: List[str]) -> Any:
    """Keep only the columns listed in `keep` if present; pass-through otherwise."""
    if not isinstance(row, dict):
        return row
    keep_set = set(keep)
    return {k: v for k, v in row.items() if k in keep_set}


def _apply_filter_and_limit(
    value: Any,
    criteria: Optional[Dict[str, Any]],
    limit: int,
    *,
    section: Optional[str] = None,
    columns: str = "minimal",
) -> Dict[str, Any]:
    """Return a dict describing the sliced value.

    For list sections: applies filter, caps rows at `limit`, reports total_count,
    and (when `columns="minimal"` and a profile exists for `section`) prunes
    each row to the profile's allowed columns.
    For scalar / dict sections: returns the value directly (no filter applied).
    """
    if isinstance(value, list):
        total = len(value)
        filtered = value
        if criteria:
            filtered = [row for row in value if _match_filter(row, criteria)]
        truncated = len(filtered) > limit
        rows = filtered[:limit]

        column_profile = None
        if columns == "minimal" and section:
            column_profile = SECTION_COLUMN_PROFILES.get(section)
        if column_profile:
            rows = [_project_row(row, column_profile) for row in rows]

        payload = {
            "rows": rows,
            "row_count": len(rows),
            "total_count": total,
            "filtered_count": len(filtered) if criteria else total,
            "truncated": truncated,
            "columns": columns,
        }
        if column_profile:
            payload["columns_kept"] = list(column_profile)
        return payload
    # Non-list: dict/scalar values returned as-is under "value".
    return {
        "value": value,
        "row_count": 1,
        "total_count": 1,
        "truncated": False,
    }


def _truncate_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Hard safety cap: if serialized output exceeds MAX_OUTPUT_CHARS, drop rows or clamp dict.

    - For list sections (has ``rows`` key): halve rows until the JSON-serialized
      payload fits inside ``MAX_OUTPUT_CHARS``.
    - For dict/scalar sections (has ``value`` key from ``_apply_filter_and_limit``):
      if the raw value is too large to serialize safely, replace it with a
      compact metadata summary (top-level keys + item/key counts) and flag the
      payload as truncated. This prevents pathological cases like the 33 MB
      ``retail_sales`` / ``imported_products`` dict sections from blowing
      past Anthropic's request size limit (HTTP 413 RequestTooLargeError).
    """
    import json as _json

    try:
        encoded = _json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        return payload
    if len(encoded) <= MAX_OUTPUT_CHARS:
        return payload

    trimmed = copy.deepcopy(payload)
    rows = trimmed.get("rows")
    if isinstance(rows, list) and rows:
        # Keep halving until fits.
        while rows and len(_json.dumps(trimmed, ensure_ascii=False, default=str)) > MAX_OUTPUT_CHARS:
            rows = rows[: max(1, len(rows) // 2)]
            trimmed["rows"] = rows
            trimmed["row_count"] = len(rows)
            trimmed["truncated"] = True
        return trimmed

    # Dict / scalar section safety rail. ``_apply_filter_and_limit`` wraps
    # non-list values as ``{"value": <raw>, "row_count": 1, ...}``. We cannot
    # meaningfully "halve" a dict, so we replace it with a metadata summary
    # and let the agent ask for a narrower slice via a different tool.
    if "value" in trimmed:
        raw_value = trimmed.get("value")
        meta: Dict[str, Any] = {}
        if isinstance(raw_value, dict):
            meta["value_type"] = "dict"
            meta["top_level_keys"] = sorted([str(k) for k in raw_value.keys()])
            meta["key_count"] = len(raw_value)
        elif isinstance(raw_value, list):
            meta["value_type"] = "list"
            meta["item_count"] = len(raw_value)
        else:
            meta["value_type"] = type(raw_value).__name__

        trimmed["value"] = None
        trimmed["truncated"] = True
        trimmed["truncation_reason"] = (
            f"Section serialized to {len(encoded):,} chars, exceeds {MAX_OUTPUT_CHARS:,} "
            f"char cap. Dict/scalar sections are not auto-halved. "
            f"Use a more specific tool (read_excel_source / grep_code) or "
            f"ask for a different section with a filter."
        )
        trimmed["metadata"] = meta
    return trimmed


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

DataLoader = Callable[[], Dict[str, Any]]


class ToolDispatcher:
    """Executes tool calls against a cached data.json snapshot.

    The `data_loader` callable is invoked lazily on first tool use and
    then cached for the lifetime of this dispatcher (one per chat turn).
    """

    def __init__(
        self,
        data_loader: DataLoader,
        *,
        project_root: Optional[Path] = None,
    ):
        self._data_loader = data_loader
        self._data_cache: Optional[Dict[str, Any]] = None
        self._calls: List[Dict[str, Any]] = []
        self._project_root: Path = (
            Path(project_root) if project_root else _default_project_root()
        )

    @property
    def calls(self) -> List[Dict[str, Any]]:
        """Trace of executed tool calls (used for source attribution)."""
        return list(self._calls)

    def _get_data(self) -> Dict[str, Any]:
        if self._data_cache is None:
            data = self._data_loader()
            if not isinstance(data, dict):
                raise RuntimeError("data_loader did not return a dict")
            self._data_cache = data
        return self._data_cache

    def dispatch(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Route a tool call by name. Returns a dict ready for JSON encoding."""
        args = arguments or {}
        if name == "read_data_json":
            result = self._read_data_json(args)
        elif name == "compute_waybill_total":
            result = compute_waybill_total(
                data_loader=self._get_data,
                date=args.get("date"),
                date_field=args.get("date_field") or "transport_start_date",
                exclude_returns=args.get("exclude_returns", True),
                exclude_cancelled=args.get("exclude_cancelled", True),
                amount_field=args.get("amount_field") or "nominal_amount",
                supplier=args.get("supplier"),
            )
        elif name == "compute":
            result = compute(
                operation=args.get("operation"),
                numbers=args.get("numbers"),
                round_digits=args.get("round_digits", 2),
                label=args.get("label"),
            )
        elif name == "forecast_revenue":
            from dashboard_pipeline.ai.forecasting import (
                forecast_revenue as _forecast_revenue,
            )

            result = _forecast_revenue(
                data_loader=self._get_data,
                horizon_months=args.get("horizon_months"),
                store=args.get("store"),
            )
        elif name == "recall_context":
            from dashboard_pipeline.ai.memory import (
                recall_context as _recall_context,
            )

            result = _recall_context(
                args.get("query"),
                limit=args.get("limit"),
                source=args.get("source"),
                tags=args.get("tags"),
                project_root=self._project_root,
            )
        elif name == "save_memory":
            from dashboard_pipeline.ai.memory import (
                save_memory as _save_memory,
            )

            result = _save_memory(
                args.get("summary"),
                tags=args.get("tags"),
                source=args.get("source"),
                project_root=self._project_root,
            )
        elif name == "journal_add_entry":
            from dashboard_pipeline.ai.journal import (
                add_journal_entry as _journal_add,
            )

            result = _journal_add(
                args.get("title"),
                args.get("kind"),
                due_date=args.get("due_date"),
                tags=args.get("tags"),
                source_memory_id=args.get("source_memory_id"),
                project_root=self._project_root,
            )
        elif name == "journal_list_entries":
            from dashboard_pipeline.ai.journal import (
                list_journal_entries as _journal_list,
            )

            result = _journal_list(
                status=args.get("status"),
                kind=args.get("kind"),
                overdue=args.get("overdue"),
                due_before=args.get("due_before"),
                due_after=args.get("due_after"),
                limit=args.get("limit"),
                today=args.get("today"),
                project_root=self._project_root,
            )
        elif name == "journal_update_entry":
            from dashboard_pipeline.ai.journal import (
                update_journal_entry as _journal_update,
            )

            result = _journal_update(
                args.get("entry_id"),
                status=args.get("status"),
                project_root=self._project_root,
            )
        elif name == "propose_feature":
            from dashboard_pipeline.ai.journal import (
                add_journal_entry as _journal_add_proposal,
            )

            result = _journal_add_proposal(
                args.get("title"),
                "proposal",
                tags=args.get("tags"),
                problem=args.get("problem"),
                benefit=args.get("benefit"),
                mvp_scope=args.get("mvp_scope"),
                data_needed=args.get("data_needed"),
                time_estimate=args.get("time_estimate"),
                risk_critique=args.get("risk_critique"),
                project_root=self._project_root,
            )
            if isinstance(result, dict) and result.get("ok"):
                result["summary_ka"] = _render_propose_feature_summary_ka(result)
        elif name == "analyze_dead_stock":
            from dashboard_pipeline.ai.dead_stock import (
                analyze_dead_stock as _analyze_dead_stock,
            )

            result = _analyze_dead_stock(
                self._data_loader,
                days_threshold=args.get("days_threshold"),
                store=args.get("store"),
                top_n=args.get("top_n"),
            )
        elif name == "prepare_supplier_brief":
            from dashboard_pipeline.ai.supplier_brief import (
                prepare_supplier_brief as _prepare_supplier_brief,
            )

            result = _prepare_supplier_brief(
                self._data_loader,
                supplier_name=args.get("supplier_name"),
                tax_id=args.get("tax_id"),
                lookback_months=args.get("lookback_months"),
                top_n=args.get("top_n"),
                benchmark_n=args.get("benchmark_n"),
            )
        elif name == "compute_cash_runway":
            from dashboard_pipeline.ai.cash_runway import (
                compute_cash_runway as _compute_cash_runway,
            )

            result = _compute_cash_runway(
                self._data_loader,
                current_balance_bog_ge=args.get("current_balance_bog_ge"),
                current_balance_tbc_ge=args.get("current_balance_tbc_ge"),
                lookback_months=args.get("lookback_months"),
            )
        elif name == "compute_cash_flow_projection":
            from dashboard_pipeline.ai.cash_flow_projection import (
                compute_cash_flow_projection as _compute_cash_flow_projection,
            )

            result = _compute_cash_flow_projection(
                self._data_loader,
                current_balance_bog_ge=args.get("current_balance_bog_ge"),
                current_balance_tbc_ge=args.get("current_balance_tbc_ge"),
                horizon_days=args.get("horizon_days"),
                store=args.get("store"),
                lookback_months=args.get("lookback_months"),
                upcoming_payments=args.get("upcoming_payments"),
            )
        elif name == "build_debt_repayment_plan":
            from dashboard_pipeline.ai.debt_plan import (
                build_debt_repayment_plan as _build_debt_repayment_plan,
            )

            result = _build_debt_repayment_plan(
                self._data_loader,
                priority_suppliers=args.get("priority_suppliers"),
                plan_duration_months=args.get("plan_duration_months"),
                max_priority_count=args.get("max_priority_count"),
            )
        elif name == "simulate_scenario":
            from dashboard_pipeline.ai.scenario_simulator import (
                simulate_scenario as _simulate_scenario,
            )

            result = _simulate_scenario(
                self._data_loader,
                base_period=args.get("base_period"),
                store=args.get("store"),
                price_change_pct=args.get("price_change_pct"),
                volume_change_pct=args.get("volume_change_pct"),
                expense_change_pct=args.get("expense_change_pct"),
                fixed_cost_delta_ge=args.get("fixed_cost_delta_ge"),
                price_elasticity=args.get("price_elasticity"),
                cogs_share=args.get("cogs_share"),
                scenario_label=args.get("scenario_label"),
            )
        elif name == "analyze_product_profitability":
            from dashboard_pipeline.ai.product_profitability import (
                analyze_product_profitability as _analyze_product_profitability,
            )

            result = _analyze_product_profitability(
                self._data_loader,
                store=args.get("store"),
                top_n=args.get("top_n"),
                category_filter=args.get("category_filter"),
                min_revenue_threshold_ge=args.get("min_revenue_threshold_ge"),
            )
        elif name == "read_source_code":
            result = read_source_code(
                args.get("file_path"),
                line_range=args.get("line_range"),
                project_root=self._project_root,
            )
        elif name == "grep_code":
            result = grep_code(
                args.get("pattern"),
                path=args.get("path"),
                max_hits=args.get("max_hits"),
                project_root=self._project_root,
            )
        elif name == "read_excel_source":
            result = read_excel_source(
                args.get("file_path"),
                sheet=args.get("sheet"),
                nrows=args.get("nrows"),
                skiprows=args.get("skiprows"),
                project_root=self._project_root,
            )
        elif name == "validate_vs_source":
            result = validate_vs_source(
                args.get("section"),
                expected_row_count=args.get("expected_row_count"),
                expected_total=args.get("expected_total"),
                field_name=args.get("field_name"),
                data_loader=self._data_loader,
                project_root=self._project_root,
            )
        else:
            result = {"error": f"Unknown tool: {name}"}

        self._calls.append({
            "tool": name,
            "arguments": args,
            "result_summary": _summarize_result(result),
        })
        return result

    def _read_data_json(self, args: Dict[str, Any]) -> Dict[str, Any]:
        section = args.get("section")
        if not isinstance(section, str) or section not in ALLOWED_SECTIONS:
            return {
                "error": f"Unknown section '{section}'. Allowed: {sorted(ALLOWED_SECTIONS.keys())}",
            }

        limit_raw = args.get("limit", DEFAULT_ROW_LIMIT)
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            limit = DEFAULT_ROW_LIMIT
        limit = max(1, min(limit, MAX_ROW_LIMIT))

        criteria = args.get("filter")
        if criteria is not None and not isinstance(criteria, dict):
            return {"error": "filter must be an object (key/value pairs)"}

        columns = args.get("columns") or "minimal"
        if columns not in ("minimal", "all"):
            columns = "minimal"

        try:
            data = self._get_data()
        except FileNotFoundError as exc:
            return {"error": f"data.json unavailable: {exc}"}
        except Exception as exc:  # pragma: no cover — defensive
            return {"error": f"failed to load data.json: {exc}"}

        if section not in data:
            return {
                "error": f"Section '{section}' not present in current data.json snapshot.",
                "source": "data.json",
            }

        slice_payload = _apply_filter_and_limit(
            data[section],
            criteria,
            limit,
            section=section,
            columns=columns,
        )
        slice_payload.update({
            "section": section,
            "source": f"data.json:{section}",
        })
        if criteria:
            slice_payload["filter_applied"] = criteria
        return _truncate_output(slice_payload)


_SUMMARY_KEYS: Tuple[str, ...] = (
    "section",
    "source",
    "source_type",
    "file_path",
    "pattern",
    "status",
    "sheet",
    "row_count",
    "total_count",
    "total_hits",
    "total_lines",
    "line_start",
    "line_end",
    "current_row_count",
    "current_total",
    "expected_row_count",
    "expected_total",
    "row_count_match",
    "total_match",
    "truncated",
    "max_hits",
    # compute_waybill_total fields
    "date",
    "date_field",
    "amount_field",
    "exclude_returns",
    "exclude_cancelled",
    "matched_count",
    "total",
    # generic compute fields
    "operation",
    "input_count",
    "result",
    "formula",
    "label",
    # forecast_revenue fields
    "store",
    "horizon_months",
    "history_months",
    "history_start",
    "history_end",
    "last_12_months_total",
    "yoy_growth_pct",
    "engines_used",
    # memory tool fields (recall_context + save_memory)
    "memory_id",
    "stored_chars",
    "tags",
    "collection",
    "query",
    "limit",
    "result_count",
    "files",
    "chunks",
    # journal tool fields (add/list/update)
    "entry_id",
    "kind",
    "title",
    "due_date",
    "previous_status",
    "count",
    "today",
    "existed",
    # dead_stock tool fields
    "as_of_date",
    "days_threshold",
    "store_filter",
    # supplier_brief tool fields
    "mode",
    "lookback_months",
    "total_suppliers",
    "total_spend_ge",
    # Phase 3.1 Co-Designer tool fields (propose_feature + cleanup_stale_proposals)
    "problem",
    "benefit",
    "mvp_scope",
    "data_needed",
    "time_estimate",
    "risk_critique",
    "proposal",
    "cancelled_count",
    "cancelled_ids",
    "cutoff",
    # Phase 3.5 Cash Runway tool fields
    "current_cash_ge",
    "current_cash_breakdown",
    "burn_rate_ge_per_month",
    "burn_trend",
    "burn_history",
    "runway_months",
    "runway_days",
    "runway_label",
    "status_summary_ka",
    # Phase 2.1 Cash Flow Projection tool fields
    "horizon_days",
    "opening_balance_ge",
    "daily_income_baseline_ge",
    "daily_burn_ge",
    "daily_projection",
    "risk_windows",
    "ending_balance_ge",
    "minimum_balance_ge",
    "minimum_balance_date",
    "forecast_engines",
    "scheduled_payments",
    "opening_ge",
    "income_ge",
    "outflow_ge",
    "closing_ge",
    "status",
    "start_date",
    "end_date",
    "days",
    "min_balance_ge",
    "lowest_day",
    "amount_ge",
    # Phase 2.2 Scenario Simulator tool fields
    "base_period_used",
    "scenario_label",
    "baseline",
    "scenario",
    "deltas",
    "adjustments_applied",
    "decision_indicator",
    "price_change_pct",
    "volume_change_pct",
    "volume_implied_by_elasticity",
    "expense_change_pct",
    "fixed_cost_delta_ge",
    "elasticity_used",
    "cogs_share",
    "revenue_ge",
    "expenses_ge",
    "net_ge",
    "margin_pct",
    "margin_pp",
    # Phase 2.5 Product Profitability X-Ray tool fields
    "category_filter",
    "min_revenue_threshold_ge",
    "products_scanned",
    "products_qualified",
    "worst_performers",
    "best_performers",
    "suspicious",
    "portfolio_margin_pct",
    "product_name",
    "product_code",
    "cost_ge",
    "profit_ge",
    "gross_margin_pct",
    "total_quantity",
    "flag",
)


def _render_propose_feature_summary_ka(result: Dict[str, Any]) -> str:
    """One-sentence Georgian summary of a ``propose_feature`` journal entry.

    The AI cites the returned ``entry_id`` verbatim so the user can later
    run ``journal_update_entry(entry_id, status=...)``. Surfacing
    ``time_estimate`` + the first phrase of ``risk_critique`` keeps the
    summary ≤1 line while still flagging the weakest link.
    """
    title = str(result.get("title") or "").strip() or "შემოთავაზება"
    entry_id = str(result.get("entry_id") or "").strip()
    proposal = result.get("proposal") or {}
    time_est = str(proposal.get("time_estimate") or "").strip()
    risk = str(proposal.get("risk_critique") or "").strip()
    # Truncate the risk critique to ~60 chars to stay one-line.
    if len(risk) > 60:
        risk = risk[:57].rstrip() + "…"

    parts: List[str] = [f"შემოთავაზება: **{title}**"]
    if time_est:
        parts.append(f"დრო: *{time_est}*")
    if risk:
        parts.append(f"რისკი: *{risk}*")
    id_suffix = f" (`{entry_id}`)" if entry_id else ""
    return " · ".join(parts) + id_suffix


def _summarize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Compact summary of a tool result for trace logging.

    Works for every tool (read_data_json + investigator tools) — keeps only
    informative top-level fields so the agent's per-turn trace stays small.
    """
    if not isinstance(result, dict):
        return {"ok": False, "error": "non-dict tool result"}
    if "error" in result:
        return {"ok": False, "error": result["error"]}
    summary: Dict[str, Any] = {"ok": True}
    for key in _SUMMARY_KEYS:
        if key in result:
            summary[key] = result[key]
    if "filter_applied" in result:
        summary["filter_applied"] = result["filter_applied"]
    return summary


# ---------------------------------------------------------------------------
# Phase 2 Investigator — tool implementations
# ---------------------------------------------------------------------------


def _rel_to_root(path: Path, root: Path) -> str:
    """Return forward-slash relative path under ``root`` (Windows-safe)."""
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_source_code(
    file_path: Any,
    line_range: Optional[Dict[str, Any]] = None,
    *,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return a bounded slice of a project source file.

    See module docstring for allowlist + cap rules.
    """
    root = (project_root or _default_project_root()).resolve()
    resolved = _resolve_safe_path(file_path, ALLOWED_CODE_ROOTS, root)
    if resolved is None:
        return {
            "error": (
                f"Path not allowed: {file_path!r}. Allowed code roots: "
                f"{list(ALLOWED_CODE_ROOTS)}"
            )
        }
    if not resolved.exists() or not resolved.is_file():
        return {"error": f"File not found: {file_path!r}"}

    if resolved.suffix.lower() not in _TEXT_FILE_EXTENSIONS:
        return {
            "error": (
                f"Unsupported file extension: {resolved.suffix!r}. "
                f"Allowed: {list(_TEXT_FILE_EXTENSIONS)}"
            )
        }

    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {"error": f"Failed to read file: {type(exc).__name__}: {exc}"}

    lines = text.splitlines()
    total_lines = len(lines)

    if isinstance(line_range, dict):
        try:
            start_raw = line_range.get("start")
            start = int(start_raw) if start_raw is not None else 1
        except (TypeError, ValueError):
            start = 1
        try:
            end_raw = line_range.get("end")
            end = (
                int(end_raw)
                if end_raw is not None
                else start + DEFAULT_SOURCE_LINES - 1
            )
        except (TypeError, ValueError):
            end = start + DEFAULT_SOURCE_LINES - 1
    else:
        start = 1
        end = DEFAULT_SOURCE_LINES

    start = max(1, start)
    end = max(start, end)
    end = min(end, total_lines) if total_lines else start

    truncated = False
    if end - start + 1 > MAX_SOURCE_LINES:
        end = start + MAX_SOURCE_LINES - 1
        truncated = True

    slice_lines = lines[start - 1 : end] if total_lines else []
    source_text = "\n".join(slice_lines)

    return {
        "file_path": _rel_to_root(resolved, root),
        "source": source_text,
        "line_start": start,
        "line_end": end,
        "total_lines": total_lines,
        "truncated": truncated,
    }


def grep_code(
    pattern: Any,
    path: Optional[str] = None,
    max_hits: Optional[int] = None,
    *,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Regex search across allowlisted code roots (or a restricted sub-path).

    Returns ``{"pattern", "hits", "total_hits", "truncated", "max_hits"}``.
    Early-exits once ``max_hits`` hits accumulate.
    """
    if not isinstance(pattern, str) or not pattern:
        return {"error": "pattern must be a non-empty string"}
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return {"error": f"Invalid regex: {exc}"}

    try:
        cap = int(max_hits) if max_hits is not None else DEFAULT_GREP_HITS
    except (TypeError, ValueError):
        cap = DEFAULT_GREP_HITS
    cap = max(1, min(cap, MAX_GREP_HITS))

    root = (project_root or _default_project_root()).resolve()

    scope_paths: List[Path] = []
    if path:
        resolved_scope = _resolve_safe_path(path, ALLOWED_CODE_ROOTS, root)
        if resolved_scope is None:
            return {
                "error": (
                    f"Path not allowed for grep: {path!r}. Allowed code roots: "
                    f"{list(ALLOWED_CODE_ROOTS)}"
                )
            }
        scope_paths.append(resolved_scope)
    else:
        for allowed in ALLOWED_CODE_ROOTS:
            candidate = (root / allowed)
            if candidate.exists():
                scope_paths.append(candidate)

    hits: List[Dict[str, Any]] = []
    truncated = False

    for scope in scope_paths:
        if scope.is_file():
            files: Iterable[Path] = [scope]
        else:
            files = (p for p in scope.rglob("*") if p.is_file())
        for fp in files:
            if fp.suffix.lower() not in _TEXT_FILE_EXTENSIONS:
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            rel = _rel_to_root(fp, root)
            for lineno, line in enumerate(text.splitlines(), start=1):
                if compiled.search(line):
                    hits.append({
                        "file_path": rel,
                        "line_number": lineno,
                        "line": line.rstrip(),
                    })
                    if len(hits) >= cap:
                        truncated = True
                        return {
                            "pattern": pattern,
                            "hits": hits,
                            "total_hits": len(hits),
                            "truncated": True,
                            "max_hits": cap,
                        }

    return {
        "pattern": pattern,
        "hits": hits,
        "total_hits": len(hits),
        "truncated": truncated,
        "max_hits": cap,
    }


def _normalize_excel_cell(value: Any) -> Any:
    """Return a JSON-safe representation of a pandas cell value."""
    # Lazy import so tests/constants don't require pandas.
    try:
        import pandas as pd  # type: ignore
        if pd.isna(value):
            return None
    except Exception:  # pragma: no cover — defensive
        pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    try:
        _json_safe.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def read_excel_source(
    file_path: Any,
    sheet: Optional[str] = None,
    nrows: Optional[int] = None,
    skiprows: Optional[int] = None,
    *,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return a bounded pandas preview of a file under Financial_Analysis/.

    Supports ``.csv``, ``.xlsx``, ``.xls``. Rows are normalized to JSON-safe
    scalars so the result can be embedded in a tool-result block directly.
    """
    root = (project_root or _default_project_root()).resolve()
    resolved = _resolve_safe_path(file_path, ALLOWED_DATA_ROOTS, root)
    if resolved is None:
        return {
            "error": (
                f"Path not allowed: {file_path!r}. Allowed data roots: "
                f"{list(ALLOWED_DATA_ROOTS)}"
            )
        }
    if not resolved.exists() or not resolved.is_file():
        return {"error": f"File not found: {file_path!r}"}

    suffix = resolved.suffix.lower()
    if suffix not in _EXCEL_FILE_EXTENSIONS:
        return {
            "error": (
                f"Unsupported file type: {suffix!r}. Supported: "
                f"{list(_EXCEL_FILE_EXTENSIONS)}"
            )
        }

    try:
        effective_nrows = int(nrows) if nrows is not None else DEFAULT_EXCEL_NROWS
    except (TypeError, ValueError):
        effective_nrows = DEFAULT_EXCEL_NROWS
    effective_nrows = max(1, min(effective_nrows, MAX_EXCEL_NROWS))

    try:
        effective_skiprows = int(skiprows) if skiprows is not None else 0
    except (TypeError, ValueError):
        effective_skiprows = 0
    effective_skiprows = max(0, effective_skiprows)

    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        return {"error": f"pandas not available: {exc}"}

    try:
        if suffix == ".csv":
            df = pd.read_csv(
                resolved,
                nrows=effective_nrows,
                skiprows=effective_skiprows if effective_skiprows > 0 else None,
            )
            source_type = "csv"
        else:
            engine = "openpyxl" if suffix == ".xlsx" else "xlrd"
            df = pd.read_excel(
                resolved,
                sheet_name=sheet if sheet else 0,
                nrows=effective_nrows,
                skiprows=effective_skiprows if effective_skiprows > 0 else None,
                engine=engine,
            )
            source_type = "xlsx" if suffix == ".xlsx" else "xls"
    except Exception as exc:
        return {
            "error": f"Failed to read file: {type(exc).__name__}: {exc}"
        }

    rows: List[Dict[str, Any]] = []
    for _idx, row in df.iterrows():
        record: Dict[str, Any] = {}
        for col, val in row.to_dict().items():
            record[str(col)] = _normalize_excel_cell(val)
        rows.append(record)

    return {
        "file_path": _rel_to_root(resolved, root),
        "source_type": source_type,
        "sheet": sheet,
        "columns": [str(c) for c in df.columns],
        "rows": rows,
        "row_count": len(rows),
        "nrows_requested": effective_nrows,
        "truncated": len(rows) >= effective_nrows,
    }


def validate_vs_source(
    section: Any,
    expected_row_count: Optional[int] = None,
    expected_total: Optional[float] = None,
    field_name: Optional[str] = None,
    *,
    data_loader: Callable[[], Dict[str, Any]],
    project_root: Optional[Path] = None,  # noqa: ARG001 — kept for signature symmetry
) -> Dict[str, Any]:
    """Compare a data.json section against expected values provided by the caller.

    No arguments beyond ``section`` triggers ``status="inspected"`` — the tool
    simply reports current metadata plus a source hint so the agent / user
    can decide what to verify.

    Providing ``expected_row_count`` or ``expected_total`` flips the status
    to ``"match"`` or ``"mismatch"`` based on the comparison outcome.
    """
    if not isinstance(section, str) or section not in ALLOWED_SECTIONS:
        return {
            "error": (
                f"Unknown section '{section}'. Allowed: "
                f"{sorted(ALLOWED_SECTIONS.keys())}"
            )
        }

    if expected_total is not None and not field_name:
        return {"error": "field_name is required when expected_total is provided"}

    try:
        data = data_loader()
    except Exception as exc:
        return {"error": f"data_loader failed: {exc}"}
    if not isinstance(data, dict):
        return {"error": "data_loader did not return a dict"}
    if section not in data:
        return {
            "error": f"Section '{section}' not present in current data.json snapshot.",
            "source": "data.json",
        }

    value = data[section]
    if isinstance(value, list):
        current_row_count = len(value)
    elif isinstance(value, dict):
        current_row_count = 1
    else:
        current_row_count = 1 if value is not None else 0

    result: Dict[str, Any] = {
        "section": section,
        "current_row_count": current_row_count,
        "source_hint": _SECTION_SOURCE_HINTS.get(
            section, "data.json (no source hint available)"
        ),
        "source": f"data.json:{section}",
    }

    comparisons = 0
    mismatches = 0

    if expected_row_count is not None:
        try:
            expected_int = int(expected_row_count)
        except (TypeError, ValueError):
            return {"error": "expected_row_count must be an integer"}
        result["expected_row_count"] = expected_int
        result["row_count_delta"] = expected_int - current_row_count
        result["row_count_match"] = expected_int == current_row_count
        comparisons += 1
        if not result["row_count_match"]:
            mismatches += 1

    if expected_total is not None:
        try:
            expected_tot = float(expected_total)
        except (TypeError, ValueError):
            return {"error": "expected_total must be a number"}
        if not isinstance(value, list):
            return {
                "error": (
                    f"Section '{section}' is not a list; cannot sum field "
                    f"'{field_name}'."
                )
            }
        total = 0.0
        missing = 0
        for row in value:
            if not isinstance(row, dict) or field_name not in row:
                missing += 1
                continue
            raw = row.get(field_name)
            try:
                total += float(raw)
            except (TypeError, ValueError):
                missing += 1
        result["expected_total"] = expected_tot
        result["current_total"] = total
        result["field_name"] = field_name
        result["total_delta"] = expected_tot - total
        result["total_match"] = abs(expected_tot - total) < 0.01
        if missing:
            result["rows_missing_field"] = missing
        comparisons += 1
        if not result["total_match"]:
            mismatches += 1

    if comparisons == 0:
        result["status"] = "inspected"
    elif mismatches == 0:
        result["status"] = "match"
    else:
        result["status"] = "mismatch"

    result["summary_ka"] = _render_validate_vs_source_summary_ka(result)
    return result


def _render_validate_vs_source_summary_ka(result: Dict[str, Any]) -> str:
    """One-sentence Georgian summary of a ``validate_vs_source`` outcome.

    Surface order mirrors the AI's decision path — section, pass/fail icon,
    then the deltas that explain *why*.
    """
    section = str(result.get("section") or "?")
    status = str(result.get("status") or "inspected")
    current_rows = result.get("current_row_count")

    if status == "inspected":
        return (
            f"**{section}**: {current_rows} მწკრივი (საწყისი inspection — "
            "expected_row_count / expected_total არ გადმოიცა)."
        )

    parts: List[str] = []
    icon = "✅" if status == "match" else "❌"
    parts.append(f"{icon} **{section}**")

    if "row_count_match" in result:
        expected = result.get("expected_row_count")
        delta = result.get("row_count_delta")
        if result.get("row_count_match"):
            parts.append(f"row count ✓ ({current_rows})")
        else:
            parts.append(
                f"row count ✗ (expected {expected}, got {current_rows}, "
                f"Δ={delta:+d})"
                if isinstance(delta, int)
                else f"row count ✗ (expected {expected}, got {current_rows})"
            )

    if "total_match" in result:
        expected_tot = result.get("expected_total")
        current_tot = result.get("current_total")
        total_delta = result.get("total_delta")
        field = result.get("field_name") or "?"
        if result.get("total_match"):
            parts.append(
                f"`{field}` ჯამი ✓ ({current_tot:,.2f})"
                if isinstance(current_tot, (int, float))
                else f"`{field}` ჯამი ✓"
            )
        else:
            delta_str = (
                f" Δ={total_delta:+,.2f}"
                if isinstance(total_delta, (int, float))
                else ""
            )
            parts.append(
                f"`{field}` ჯამი ✗ (expected {expected_tot:,.2f}, got "
                f"{current_tot:,.2f}{delta_str})"
                if isinstance(expected_tot, (int, float))
                and isinstance(current_tot, (int, float))
                else f"`{field}` ჯამი ✗"
            )

    return " · ".join(parts)


# ---------------------------------------------------------------------------
# compute_waybill_total — server-side arithmetic helper
# ---------------------------------------------------------------------------

_WAYBILL_DATE_FIELDS: Tuple[str, ...] = (
    "date",
    "transport_start_date",
    "delivery_date",
)
_WAYBILL_AMOUNT_FIELDS: Tuple[str, ...] = (
    "nominal_amount",
    "effective_amount",
)


def compute(
    *,
    operation: Any,
    numbers: Any,
    round_digits: Any = 2,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """Generic exact-arithmetic helper — LLM calls this instead of summing
    numbers mentally.

    Parameters are validated strictly:

    - ``operation`` must be one of :data:`_COMPUTE_OPERATIONS`.
    - ``numbers`` must be a non-empty list of numbers (``int`` / ``float``).
      ``bool`` is rejected even though ``isinstance(True, int)`` is True —
      a boolean in an arithmetic list almost always indicates the LLM
      passed the wrong thing.
    - For ``pct`` / ``growth`` / ``diff``, ``numbers`` must have exactly two
      items. Order matters (see schema description).
    - ``round_digits`` clamps the final ``result`` via :func:`round`. Pass a
      negative integer to skip rounding entirely.

    Returns a dict with ``operation``, ``input_count``, ``result``,
    ``formula`` (human-readable trace) and ``source``. On validation failure
    returns ``{"error": "..."}``.
    """
    if operation not in _COMPUTE_OPERATIONS:
        return {
            "error": (
                f"`operation` must be one of {list(_COMPUTE_OPERATIONS)}, "
                f"got {operation!r}"
            )
        }

    if not isinstance(numbers, list) or not numbers:
        return {"error": "`numbers` must be a non-empty list of numbers"}

    parsed: List[float] = []
    for idx, raw in enumerate(numbers):
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return {
                "error": (
                    f"`numbers[{idx}]` must be a number (int or float); "
                    f"got {type(raw).__name__}"
                )
            }
        parsed.append(float(raw))

    if operation in ("pct", "growth", "diff") and len(parsed) != 2:
        return {
            "error": (
                f"`operation`={operation!r} requires exactly 2 numbers "
                f"(got {len(parsed)})"
            )
        }

    try:
        round_to = int(round_digits) if round_digits is not None else 2
    except (TypeError, ValueError):
        round_to = 2

    formula = ""
    try:
        if operation == "sum":
            raw_result = sum(parsed)
            formula = " + ".join(f"{n:g}" for n in parsed) + f" = {raw_result:g}"
        elif operation == "avg":
            raw_result = sum(parsed) / len(parsed)
            formula = (
                f"({' + '.join(f'{n:g}' for n in parsed)}) / {len(parsed)} = "
                f"{raw_result:g}"
            )
        elif operation == "min":
            raw_result = min(parsed)
            formula = f"min({', '.join(f'{n:g}' for n in parsed)}) = {raw_result:g}"
        elif operation == "max":
            raw_result = max(parsed)
            formula = f"max({', '.join(f'{n:g}' for n in parsed)}) = {raw_result:g}"
        elif operation == "count":
            raw_result = float(len(parsed))
            formula = f"count({len(parsed)} items) = {len(parsed)}"
        elif operation == "pct":
            part, whole = parsed
            if whole == 0:
                return {"error": "pct: whole (numbers[1]) cannot be zero"}
            raw_result = (part / whole) * 100.0
            formula = f"({part:g} / {whole:g}) × 100 = {raw_result:g}%"
        elif operation == "growth":
            old, new = parsed
            if old == 0:
                return {"error": "growth: old (numbers[0]) cannot be zero"}
            raw_result = ((new - old) / old) * 100.0
            formula = (
                f"(({new:g} − {old:g}) / {old:g}) × 100 = {raw_result:g}%"
            )
        elif operation == "diff":
            old, new = parsed
            raw_result = new - old
            formula = f"{new:g} − {old:g} = {raw_result:g}"
        else:  # pragma: no cover — guarded by enum check above
            return {"error": f"unhandled operation {operation!r}"}
    except Exception as exc:  # pragma: no cover — defensive
        return {"error": f"computation failed: {type(exc).__name__}: {exc}"}

    if round_to >= 0:
        result: Any = round(raw_result, round_to)
    else:
        result = raw_result

    op_label_ka = {
        "sum": "ჯამი",
        "avg": "საშუალო",
        "min": "მინიმუმი",
        "max": "მაქსიმუმი",
        "count": "დათვლა",
        "pct": "პროცენტი",
        "growth": "ცვლილება (%)",
        "diff": "სხვაობა",
    }.get(operation, operation)
    unit = "%" if operation in ("pct", "growth") else ""
    label_part = f" — *{label}*" if label else ""
    summary_ka = (
        f"**{op_label_ka}{label_part}**: **{result:g}{unit}** "
        f"({len(parsed)} მნიშვნელობაზე; formula: `{formula}`)"
    )

    payload: Dict[str, Any] = {
        "operation": operation,
        "input_count": len(parsed),
        "result": result,
        "formula": formula,
        "summary_ka": summary_ka,
        "source": "compute (server-side arithmetic)",
    }
    if label:
        payload["label"] = str(label)
    return payload


def compute_waybill_total(
    *,
    data_loader: Callable[[], Dict[str, Any]],
    date: Any,
    date_field: str = "transport_start_date",
    exclude_returns: bool = True,
    exclude_cancelled: bool = True,
    amount_field: str = "nominal_amount",
    supplier: Optional[str] = None,
) -> Dict[str, Any]:
    """Server-side waybill total — avoids LLM arithmetic hallucinations.

    Filters `data["waybills"]` by date substring (against the chosen
    `date_field`) and sums `amount_field`. By default excludes rows where
    `type` contains 'უკან დაბრუნება' (returns) and rows where `status`
    contains 'გაუქმებული' (cancelled) — matching the business meaning of
    "ზედნადები შემოვიდა X დღეს".

    Returns exact total, matched row count, and top-10 suppliers by
    contribution. Intended for the LLM to call INSTEAD of reading rows and
    summing them manually.
    """
    if not isinstance(date, str) or not date.strip():
        return {"error": "`date` is required (e.g., 'YYYY-MM-DD' or 'YYYY-MM')"}
    if date_field not in _WAYBILL_DATE_FIELDS:
        return {
            "error": (
                f"`date_field` must be one of {list(_WAYBILL_DATE_FIELDS)}, "
                f"got {date_field!r}"
            )
        }
    if amount_field not in _WAYBILL_AMOUNT_FIELDS:
        return {
            "error": (
                f"`amount_field` must be one of {list(_WAYBILL_AMOUNT_FIELDS)}, "
                f"got {amount_field!r}"
            )
        }

    try:
        data = data_loader()
    except Exception as exc:
        return {"error": f"data_loader failed: {exc}"}
    if not isinstance(data, dict):
        return {"error": "data_loader did not return a dict"}

    waybills = data.get("waybills")
    if not isinstance(waybills, list):
        return {
            "error": "waybills section missing or not a list in data.json",
            "source": "data.json:waybills",
        }

    date_str = date.strip()
    supplier_filter = (supplier or "").strip().lower() or None

    matched: List[Dict[str, Any]] = []
    for row in waybills:
        if not isinstance(row, dict):
            continue
        # Date match (substring).
        val = str(row.get(date_field, ""))
        if date_str not in val:
            continue
        # Exclude cancelled.
        if exclude_cancelled:
            status_val = str(row.get("status", ""))
            if "გაუქმებული" in status_val:
                continue
        # Exclude returns.
        if exclude_returns:
            type_val = str(row.get("type", ""))
            if "უკან დაბრუნება" in type_val:
                continue
        # Supplier filter.
        if supplier_filter is not None:
            sup_val = str(row.get("supplier", "")).lower()
            if supplier_filter not in sup_val:
                continue
        matched.append(row)

    # Sum amounts.
    total = 0.0
    bad_amounts = 0
    for row in matched:
        raw = row.get(amount_field)
        try:
            total += float(raw)
        except (TypeError, ValueError):
            bad_amounts += 1

    # Per-supplier contribution.
    per_supplier: Dict[str, Dict[str, Any]] = {}
    for row in matched:
        sup = str(row.get("supplier", "?"))
        entry = per_supplier.setdefault(
            sup, {"supplier": sup, "count": 0, "total": 0.0}
        )
        entry["count"] += 1
        try:
            entry["total"] += float(row.get(amount_field) or 0)
        except (TypeError, ValueError):
            pass

    top_suppliers = sorted(
        per_supplier.values(),
        key=lambda x: float(x.get("total") or 0),
        reverse=True,
    )[:10]
    # Round for readability.
    for s in top_suppliers:
        s["total"] = round(float(s["total"]), 2)

    total_rounded = round(total, 2)
    field_label_ka = {
        "transport_start_date": "ტრანსპ. დაწყება",
        "date": "RS რეგისტრაცია",
        "delivery_date": "ჩაბარების თარ.",
    }.get(date_field, date_field)

    if len(matched) == 0:
        summary_ka = (
            f"**{date_str}** თარიღზე ({field_label_ka}) ზედნადები **არ არის**."
        )
    else:
        supplier_hint = ""
        if supplier_filter:
            supplier_hint = f" · supplier filter: *{supplier_filter}*"
        summary_ka = (
            f"**{date_str}** ({field_label_ka}): **{total_rounded:,.2f} ₾** "
            f"ჯამი, {len(matched)} ზედნადებზე{supplier_hint}. "
            "(exclude returns + cancelled)"
            if (exclude_returns and exclude_cancelled)
            else (
                f"**{date_str}** ({field_label_ka}): **{total_rounded:,.2f} ₾** "
                f"ჯამი, {len(matched)} ზედნადებზე{supplier_hint}."
            )
        )

    return {
        "date": date_str,
        "date_field": date_field,
        "amount_field": amount_field,
        "exclude_returns": bool(exclude_returns),
        "exclude_cancelled": bool(exclude_cancelled),
        "supplier_filter": supplier_filter,
        "matched_count": len(matched),
        "total": total_rounded,
        "bad_amount_rows": bad_amounts,
        "top_suppliers": top_suppliers,
        "summary_ka": summary_ka,
        "source": "data.json:waybills (server-side computed)",
    }
