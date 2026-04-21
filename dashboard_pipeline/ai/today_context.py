"""Today's Pulse — automatic situational-awareness block for the AI Advisor.

Produces a compact snapshot of business-critical "today" metrics that gets
injected into every chat turn's system prompt as a **non-cached** XML block.
The LLM then answers questions like "რა ვაკეთო დღეს?" with immediate context,
instead of starting from a blank slate every session.

Design goals:
- Defensive. If data.json structure shifts or a section is missing, produce a
  graceful "ამ მონაცემი ვერ მოვიძიე" note rather than crashing. The context
  block must NEVER fail the chat turn.
- Fast. The block is rebuilt on every new chat (cache-miss) — keep it under
  ~200 ms by walking each section once.
- Truthful. Never fabricate numbers; if data is missing, say so.
- Short. The block goes into the LLM context on every turn; keep it dense.

Public API:
- :func:`build_today_context(data_loader, today=None) -> Dict`
- :func:`format_today_block(ctx) -> str` — XML-tagged Georgian string
- :func:`build_today_block(data_loader, today=None) -> str` — convenience
  one-shot that runs both.
"""

from __future__ import annotations

import datetime as _dt
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


# Georgian weekday names, 0 = Monday per `date.weekday()`.
GEORGIAN_WEEKDAYS: Tuple[str, ...] = (
    "ორშაბათი",
    "სამშაბათი",
    "ოთხშაბათი",
    "ხუთშაბათი",
    "პარასკევი",
    "შაბათი",
    "კვირა",
)

#: Canonical store labels — matches `retail_sales.by_object[i].object` values.
STORE_LABELS: Tuple[str, ...] = ("ოზურგეთი", "დვაბზუ")

#: How many days back to compare "yesterday" against (moving average window).
_POS_COMPARE_DAYS = 7

#: Upcoming-AP window for the 7-day cash forecast.
_FORECAST_DAYS = 7

#: Thresholds for `top_risks` auto-detection.
_POS_DROP_PCT_THRESHOLD = 25.0  # ≥ 25% drop vs 7-day avg flags a POS anomaly
_SUPPLIER_OVERDUE_FLAG = 5_000.0  # overdue_60+ ≥ this flags supplier risk

#: How many freshest open journal entries (non-overdue) to surface in the
#: ``<TODAY>`` block. Overdue entries are always shown in full — they are
#: the reason the journal exists.
_TODAY_NEWEST_OPEN_LIMIT = 3

#: Georgian labels for the four journal kinds. Used only for rendering.
_JOURNAL_KIND_ICONS: Dict[str, str] = {
    "promise": "🤝",
    "ai_commitment": "🔍",
    "recommendation": "💡",
    "reminder": "⏰",
}


# Phase 1 Part A (2026-04-20) — Georgian regulatory calendar for the
# ``<TODAY>`` block's "upcoming deadlines" section. The goal is NOT to
# replace the decision journal (user-specific commitments belong
# there); it is to surface FIXED Georgian business-law deadlines the
# LLM should proactively cite so the user avoids saurpi (late-payment
# penalties).
#
# We intentionally ship a conservative two-entry list:
#   * VAT declaration (RS.ge) — monthly, day 15
#   * Pension fund contribution — monthly, day 15
# These two are universal for every legal entity in Georgia. Franchise
# royalty / income tax / property tax dates are contract-specific and
# therefore belong in the user's ``journal_add_entry`` workflow, not in
# this hard-coded table.
#
# Each entry: ``(label, day_of_month)`` — the helper below rolls the
# monthly anchor forward whenever today has already passed it.
_FIXED_MONTHLY_DEADLINES: Tuple[Tuple[str, int], ...] = (
    ("VAT დეკლარაცია (RS.ge)", 15),
    ("საპენსიო ფონდი", 15),
)

#: Upcoming-deadline warning thresholds. A deadline ≤ this many days
#: away gets the "approaching" severity; ≤ the tighter threshold gets
#: the "urgent" severity. Anything farther out is included only up to
#: ``_DEADLINE_HORIZON_DAYS``.
_DEADLINE_URGENT_DAYS = 3
_DEADLINE_APPROACHING_DAYS = 7
_DEADLINE_HORIZON_DAYS = 10


# Phase 1 Part A — weekday-context one-liners. These are deliberately
# short (≤ 35 chars) so they sit on the same line as the ISO date and
# don't bloat the cached-prefix budget. The LLM reads them as hints,
# not facts — it's fine if a "weekend ahead" note shows on a Friday
# holiday.
_WEEKDAY_CONTEXT: Tuple[str, ...] = (
    "კვირის დასაწყისი — დაგეგმე",              # Monday
    "სამუშაო რიტმი",                             # Tuesday
    "შუა კვირა",                                   # Wednesday
    "სამუშაო რიტმი",                             # Thursday
    "კვირის ბოლო — weekend-ის წინ",          # Friday
    "weekend — retail peak",                      # Saturday
    "weekend — retail peak",                      # Sunday
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_today_context(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    today: Optional[_dt.date] = None,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Gather today's business metrics into a compact dict.

    Parameters
    ----------
    data_loader : callable
        Zero-arg callable that returns the canonical data.json dict. Called
        once; if it raises, the returned context still has ``date`` /
        ``weekday`` but every data-derived field is empty with a note.
    today : date, optional
        Override for testing; defaults to :func:`datetime.date.today`.
    project_root : Path, optional
        Override for the journal store's persist directory; defaults to
        the canonical project root resolved inside ``memory.py``. Tests
        pass ``tmp_path`` to isolate the fake ChromaDB store.

    Returns
    -------
    dict
        Keys:
          - ``date``        — ISO YYYY-MM-DD
          - ``weekday``     — Georgian weekday name
          - ``yesterday_pos`` — ``{store: {"revenue_ge": float,
            "avg7_ge": float, "delta_pct": float}}`` (empty dict on failure)
          - ``cash_forecast_7day`` — ``{"upcoming_ap": float,
            "overdue_total": float, "window_days": 7}``
          - ``top_risks``   — list of short Georgian strings (≤ 3 items)
          - ``open_promises`` — ``{"overdue": [...], "newest_open": [...]}``
            (Phase 0B Sprint 4) — entries from the decision journal that
            the LLM should honour in every reply.
          - ``notes``       — list of "ვერ მოვიძიე X" breadcrumbs (transparency)
    """
    today = today or _dt.date.today()
    weekday = GEORGIAN_WEEKDAYS[today.weekday()]
    notes: List[str] = []

    ctx: Dict[str, Any] = {
        "date": today.isoformat(),
        "weekday": weekday,
        "weekday_context": _WEEKDAY_CONTEXT[today.weekday()],
        "yesterday_pos": {},
        "cash_forecast_7day": {},
        "top_risks": [],
        "upcoming_deadlines": _upcoming_deadlines(today),
        "open_promises": {"overdue": [], "newest_open": []},
        "notes": notes,
    }

    try:
        data = data_loader()
    except Exception as exc:
        logger.warning("today_context: data_loader failed: %s", exc)
        notes.append(f"data.json ვერ წავიკითხე ({type(exc).__name__}).")
        # Even without data.json we still try to surface the journal —
        # overdue commitments do not depend on fresh POS numbers.
        ctx["open_promises"] = _collect_open_promises(today, notes, project_root)
        return ctx

    if not isinstance(data, dict):
        notes.append("data.json არ არის dict — struct გაუგებარია.")
        ctx["open_promises"] = _collect_open_promises(today, notes, project_root)
        return ctx

    # --- Yesterday POS -----------------------------------------------------
    ctx["yesterday_pos"] = _compute_yesterday_pos(data, today, notes)

    # --- 7-day cash forecast ----------------------------------------------
    ctx["cash_forecast_7day"] = _compute_cash_forecast(data, today, notes)

    # --- Top 3 risks -------------------------------------------------------
    ctx["top_risks"] = _detect_top_risks(ctx, data, notes)

    # --- Open journal promises (Sprint 4) ---------------------------------
    ctx["open_promises"] = _collect_open_promises(today, notes, project_root)

    return ctx


def format_today_block(ctx: Dict[str, Any]) -> str:
    """Format the context dict as a Georgian XML-tagged block for the prompt.

    The block is wrapped in ``<TODAY>...</TODAY>`` so the LLM can locate it
    predictably. If a section is empty, it is simply skipped rather than
    shown as "0 ₾" — that would mislead the LLM into thinking 0 is the
    actual value.
    """
    lines: List[str] = ["<TODAY>"]
    date_str = ctx.get("date", "?")
    weekday_str = ctx.get("weekday", "?")
    weekday_hint = ctx.get("weekday_context") or ""
    header = f"თარიღი: {date_str} ({weekday_str})"
    if weekday_hint:
        header = f"{header} — {weekday_hint}"
    lines.append(header)

    ypos = ctx.get("yesterday_pos") or {}
    if ypos:
        lines.append("გუშინდელი POS (რევენიუ):")
        for store in STORE_LABELS:
            entry = ypos.get(store)
            if not isinstance(entry, dict):
                continue
            rev = entry.get("revenue_ge")
            avg = entry.get("avg7_ge")
            delta = entry.get("delta_pct")
            if rev is None:
                continue
            suffix = ""
            if isinstance(delta, (int, float)):
                arrow = "📈" if delta >= 0 else "📉"
                suffix = f" ({arrow} {delta:+.1f}% vs 7-დღიანი საშუალო)"
            avg_txt = ""
            if isinstance(avg, (int, float)) and avg > 0:
                avg_txt = f" [საშ.: {avg:,.0f} ₾]"
            lines.append(f"  {store}: {rev:,.0f} ₾{suffix}{avg_txt}")

    cash = ctx.get("cash_forecast_7day") or {}
    upcoming = cash.get("upcoming_ap")
    overdue = cash.get("overdue_total")
    if isinstance(upcoming, (int, float)) or isinstance(overdue, (int, float)):
        lines.append("AP (მომწოდებელი ვალი):")
        if isinstance(overdue, (int, float)):
            lines.append(f"  ვადაგადაცილებული ჯამი: {overdue:,.0f} ₾")
        if isinstance(upcoming, (int, float)):
            lines.append(f"  მიმდინარე (ვადაშიდა): {upcoming:,.0f} ₾")

    risks = ctx.get("top_risks") or []
    if risks:
        lines.append("ყურადღების 3 პუნქტი:")
        for i, risk in enumerate(risks[:3], 1):
            lines.append(f"  {i}. {risk}")

    deadlines = ctx.get("upcoming_deadlines") or []
    if deadlines:
        lines.append("⏰ უახლოესი ვადები:")
        for entry in deadlines:
            if not isinstance(entry, dict):
                continue
            label = entry.get("label") or ""
            due_iso = entry.get("due_date") or ""
            days = entry.get("days_until")
            severity = entry.get("severity") or ""
            if not label or not due_iso or not isinstance(days, int):
                continue
            if severity == "urgent":
                prefix = "🚨"
            elif severity == "approaching":
                prefix = "⏰"
            else:
                prefix = "📆"
            if days == 0:
                when = "დღესვე"
            elif days == 1:
                when = "ხვალ"
            else:
                when = f"{days} დღეში"
            lines.append(f"  {prefix} {label} — {due_iso} ({when})")

    promises = ctx.get("open_promises") or {}
    overdue = promises.get("overdue") or []
    newest_open = promises.get("newest_open") or []
    if overdue or newest_open:
        header_counts: List[str] = []
        if overdue:
            header_counts.append(f"{len(overdue)} ვადაგადაცილებული")
        if newest_open:
            header_counts.append(f"{len(newest_open)} ახალი")
        header_suffix = f" ({' + '.join(header_counts)})" if header_counts else ""
        lines.append(f"⏳ ღია დაპირებები{header_suffix}:")
        for entry in overdue:
            lines.append(f"  {_format_journal_entry(entry, overdue=True)}")
        for entry in newest_open:
            lines.append(f"  {_format_journal_entry(entry, overdue=False)}")

    notes = ctx.get("notes") or []
    if notes:
        lines.append("შენიშვნები:")
        for n in notes:
            lines.append(f"  • {n}")

    lines.append("</TODAY>")
    return "\n".join(lines)


def build_today_block(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    today: Optional[_dt.date] = None,
    project_root: Optional[Path] = None,
) -> str:
    """One-shot convenience: build context + format block in one call."""
    return format_today_block(
        build_today_context(data_loader, today=today, project_root=project_root)
    )


def _upcoming_deadlines(today: _dt.date) -> List[Dict[str, Any]]:
    """Return the next occurrence of each fixed monthly Georgian deadline.

    For each ``(label, day_of_month)`` in :data:`_FIXED_MONTHLY_DEADLINES`
    we compute the next date in the calendar at or after ``today``. If
    today already passed the anchor day this month, we roll forward to
    the next month. Results farther than :data:`_DEADLINE_HORIZON_DAYS`
    away are dropped so the ``<TODAY>`` block stays short.

    Severity buckets:
      * ``"urgent"``       — days_until ≤ :data:`_DEADLINE_URGENT_DAYS`
      * ``"approaching"``  — days_until ≤ :data:`_DEADLINE_APPROACHING_DAYS`
      * ``"normal"``       — everything else within the horizon

    The returned list is sorted by ``days_until`` ascending. Each entry
    is a plain dict with string / int values so it JSON-serialises into
    the chat's tool-call trace cleanly.
    """
    out: List[Dict[str, Any]] = []
    for label, day in _FIXED_MONTHLY_DEADLINES:
        due = _next_monthly_anchor(today, day)
        if due is None:
            continue
        days_until = (due - today).days
        if days_until < 0 or days_until > _DEADLINE_HORIZON_DAYS:
            continue
        if days_until <= _DEADLINE_URGENT_DAYS:
            severity = "urgent"
        elif days_until <= _DEADLINE_APPROACHING_DAYS:
            severity = "approaching"
        else:
            severity = "normal"
        out.append(
            {
                "label": label,
                "due_date": due.isoformat(),
                "days_until": days_until,
                "severity": severity,
            }
        )
    out.sort(key=lambda entry: entry["days_until"])
    return out


def _next_monthly_anchor(today: _dt.date, day: int) -> Optional[_dt.date]:
    """Return today's or next month's occurrence of ``day``.

    Guards against invalid day numbers (e.g. day=31 in February) by
    rolling to the last valid day of the target month. Returns ``None``
    only for blatantly invalid inputs (day < 1 or day > 31).
    """
    if day < 1 or day > 31:
        return None
    anchor = _clamp_day(today.year, today.month, day)
    if anchor >= today:
        return anchor
    if today.month == 12:
        return _clamp_day(today.year + 1, 1, day)
    return _clamp_day(today.year, today.month + 1, day)


def _clamp_day(year: int, month: int, day: int) -> _dt.date:
    """Return ``date(year, month, day)`` clamped to the month's last day."""
    import calendar as _cal

    last = _cal.monthrange(year, month)[1]
    return _dt.date(year, month, min(day, last))


def _format_journal_entry(entry: Dict[str, Any], *, overdue: bool) -> str:
    """Render a single journal entry for the ``<TODAY>`` block."""
    kind = entry.get("kind") or ""
    icon = _JOURNAL_KIND_ICONS.get(kind, "•")
    title = str(entry.get("title") or entry.get("summary") or "").strip()
    entry_id = entry.get("entry_id") or ""
    due_date = entry.get("due_date") or ""
    overdue_days = entry.get("overdue_days")
    created_at = entry.get("created_at") or ""

    if overdue and isinstance(overdue_days, int) and overdue_days > 0:
        tag = f"🚨 ვადა გადაცილებული {overdue_days} დღე"
    elif isinstance(overdue_days, int) and overdue_days == 0:
        tag = "📆 დღეს ვადა"
    elif isinstance(overdue_days, int) and overdue_days < 0:
        tag = f"📆 ვადა {due_date}"
    elif created_at:
        # Drop the time portion for readability.
        tag = f"🆕 {created_at[:10]}"
    else:
        tag = "ახალი"

    id_hint = f" (id: {entry_id})" if entry_id else ""
    return f"{icon} [{tag}] {title}{id_hint}"


def _collect_open_promises(
    today: _dt.date,
    notes: List[str],
    project_root: Optional[Path],
) -> Dict[str, Any]:
    """Proxy to :func:`journal.collect_today_journal_highlights`.

    Kept as a thin local wrapper so the import is lazy (the journal
    module imports ChromaDB indirectly via ``memory.py``). Swallows any
    unexpected exception so a broken journal never crashes the chat
    turn.
    """
    try:
        from dashboard_pipeline.ai import journal as _journal
    except Exception as exc:  # pragma: no cover — defensive
        logger.info("journal module unavailable: %s", exc)
        notes.append("journal module ვერ ჩაიტვირთა.")
        return {"overdue": [], "newest_open": []}

    try:
        payload = _journal.collect_today_journal_highlights(
            today=today,
            newest_open_limit=_TODAY_NEWEST_OPEN_LIMIT,
            project_root=project_root,
        )
    except Exception as exc:
        logger.info("collect_today_journal_highlights failed: %s", exc)
        notes.append("ღია დაპირებები ვერ ამოვიღე.")
        return {"overdue": [], "newest_open": []}

    for note in payload.get("notes") or []:
        if note and note not in notes:
            notes.append(note)

    return {
        "overdue": payload.get("overdue") or [],
        "newest_open": payload.get("newest_open") or [],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_yesterday_pos(
    data: Dict[str, Any],
    today: _dt.date,
    notes: List[str],
) -> Dict[str, Dict[str, float]]:
    """Per-store yesterday POS revenue + 7-day average + delta %.

    Uses ``data["retail_sales"]["rows_preview"]`` (daily granularity) as the
    source. If rows_preview is missing or empty, returns an empty dict and
    pushes a breadcrumb onto ``notes``.
    """
    rs = data.get("retail_sales")
    if not isinstance(rs, dict):
        notes.append("retail_sales section არ არის data.json-ში.")
        return {}

    rows = rs.get("rows_preview")
    if not isinstance(rows, list) or not rows:
        notes.append("retail_sales.rows_preview ცარიელია (daily POS ვერ დავთვალე).")
        return {}

    yesterday = today - _dt.timedelta(days=1)
    yesterday_str = yesterday.isoformat()
    window_start = (today - _dt.timedelta(days=_POS_COMPARE_DAYS)).isoformat()

    # One pass: collect yesterday totals + window totals by (store, date).
    yesterday_by_store: Dict[str, float] = defaultdict(float)
    window_by_store_date: Dict[Tuple[str, str], float] = defaultdict(float)

    for row in rows:
        if not isinstance(row, dict):
            continue
        date = row.get("date")
        obj = row.get("object")
        revenue = row.get("revenue_ge")
        if (
            not isinstance(date, str)
            or not isinstance(obj, str)
            or not isinstance(revenue, (int, float))
        ):
            continue
        if date == yesterday_str:
            yesterday_by_store[obj] += float(revenue)
        if window_start <= date < yesterday_str:
            window_by_store_date[(obj, date)] += float(revenue)

    # Average daily revenue across the window (per store).
    window_days_by_store: Dict[str, set] = defaultdict(set)
    window_sum_by_store: Dict[str, float] = defaultdict(float)
    for (store, date), amt in window_by_store_date.items():
        window_days_by_store[store].add(date)
        window_sum_by_store[store] += amt

    result: Dict[str, Dict[str, float]] = {}
    for store in STORE_LABELS:
        rev = yesterday_by_store.get(store)
        days = len(window_days_by_store.get(store, set()))
        window_sum = window_sum_by_store.get(store, 0.0)
        avg = (window_sum / days) if days > 0 else 0.0
        entry: Dict[str, float] = {
            "revenue_ge": round(float(rev or 0.0), 2),
            "avg7_ge": round(avg, 2),
        }
        if avg > 0 and rev is not None:
            entry["delta_pct"] = round(((rev - avg) / avg) * 100.0, 2)
        result[store] = entry

    # Post-hoc: if every store has 0 yesterday revenue, that's suspicious —
    # most likely the data just hasn't been refreshed yet. Leave a note so
    # the LLM doesn't report "both stores earned 0 ₾ yesterday" as fact.
    if all(entry.get("revenue_ge", 0) == 0 for entry in result.values()):
        notes.append(
            "გუშინდელი POS ყველა მაღაზიაში 0 ₾ — სავარაუდოდ data.json "
            "ჯერ არ განახლდა; რეალური ციფრი უცნობია."
        )

    return result


def _compute_cash_forecast(
    data: Dict[str, Any],
    today: _dt.date,
    notes: List[str],
) -> Dict[str, Any]:
    """Approximate 7-day AP exposure.

    Uses ``aging_summary`` when present, otherwise collapses
    ``supplier_aging`` to totals. We expose:
      - ``upcoming_ap``   — the "current" (not-yet-overdue) bucket
      - ``overdue_total`` — everything past-due in all buckets
      - ``window_days``   — 7 (contract signal, not a computed field)

    True cash inflow requires retail forecast data we don't reliably expose;
    that is left for Phase 0B (forecasting tool).
    """
    summary = data.get("aging_summary")
    current = 0.0
    overdue = 0.0
    if isinstance(summary, dict):
        try:
            current = float(summary.get("current") or 0)
            overdue = (
                float(summary.get("overdue_30") or 0)
                + float(summary.get("overdue_60") or 0)
                + float(summary.get("overdue_90") or 0)
                + float(summary.get("overdue_180") or 0)
                + float(summary.get("overdue_180_plus") or 0)
            )
        except (TypeError, ValueError):
            notes.append("aging_summary ციფრები არასწორი ფორმატისაა.")
    else:
        aging_list = data.get("supplier_aging")
        if isinstance(aging_list, list) and aging_list:
            for row in aging_list:
                if not isinstance(row, dict):
                    continue
                try:
                    current += float(row.get("current") or 0)
                    overdue += float(row.get("overdue_30") or 0)
                    overdue += float(row.get("overdue_60") or 0)
                    overdue += float(row.get("overdue_90") or 0)
                    overdue += float(row.get("overdue_180") or 0)
                    overdue += float(row.get("overdue_180_plus") or 0)
                except (TypeError, ValueError):
                    continue
        else:
            notes.append("aging section ვერ ვიპოვე — cash forecast უცნობია.")
            return {}

    return {
        "upcoming_ap": round(current, 2),
        "overdue_total": round(overdue, 2),
        "window_days": _FORECAST_DAYS,
    }


def _detect_top_risks(
    ctx: Dict[str, Any],
    data: Dict[str, Any],
    notes: List[str],
) -> List[str]:
    """Surface up to 3 short risk lines the LLM should be aware of.

    Heuristics (cheap, deterministic):
    1. POS drop vs 7-day average ≥ ``_POS_DROP_PCT_THRESHOLD`` for any store.
    2. Any supplier with ``overdue_60+`` ≥ ``_SUPPLIER_OVERDUE_FLAG``.
    3. Aggregate overdue_total vs current ratio — if overdue > current, that
       is a cash-strain signal worth flagging.
    """
    risks: List[str] = []

    ypos = ctx.get("yesterday_pos") or {}
    for store, entry in ypos.items():
        if not isinstance(entry, dict):
            continue
        delta = entry.get("delta_pct")
        rev = entry.get("revenue_ge")
        if not isinstance(delta, (int, float)) or not isinstance(rev, (int, float)):
            continue
        if delta <= -_POS_DROP_PCT_THRESHOLD:
            risks.append(
                f"{store}: გუშინ {rev:,.0f} ₾ ({delta:+.1f}% vs 7-დღიანი "
                "საშუალო) — შეამოწმე POS ტერმინალი."
            )

    aging_list = data.get("supplier_aging")
    if isinstance(aging_list, list) and len(risks) < 3:
        flagged = []
        for row in aging_list:
            if not isinstance(row, dict):
                continue
            try:
                overdue_60_plus = (
                    float(row.get("overdue_60") or 0)
                    + float(row.get("overdue_90") or 0)
                    + float(row.get("overdue_180") or 0)
                    + float(row.get("overdue_180_plus") or 0)
                )
            except (TypeError, ValueError):
                continue
            if overdue_60_plus >= _SUPPLIER_OVERDUE_FLAG:
                supplier_name = (
                    row.get("ორგანიზაცია")
                    or row.get("supplier")
                    or row.get("normalized_supplier")
                    or "?"
                )
                flagged.append((supplier_name, overdue_60_plus))
        # Sort by size desc, take at most one (the worst) — we don't want to
        # fill all 3 risk slots with AP items.
        flagged.sort(key=lambda x: x[1], reverse=True)
        if flagged:
            name, amount = flagged[0]
            risks.append(
                f"{name}: ვადაგადაცილებული 60+ დღე = {amount:,.0f} ₾ — AP რისკი."
            )

    cash = ctx.get("cash_forecast_7day") or {}
    current = cash.get("upcoming_ap")
    overdue = cash.get("overdue_total")
    if (
        isinstance(current, (int, float))
        and isinstance(overdue, (int, float))
        and current > 0
        and overdue > current
        and len(risks) < 3
    ):
        risks.append(
            f"ვადაგადაცილებული AP ({overdue:,.0f} ₾) აჭარბებს მიმდინარეს "
            f"({current:,.0f} ₾) — cash strain სიგნალი."
        )

    return risks[:3]
