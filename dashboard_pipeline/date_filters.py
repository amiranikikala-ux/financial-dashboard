from __future__ import annotations

from datetime import datetime

import pandas as pd

from dashboard_pipeline.constants import _parse_rs_datetime

DEFAULT_FROM_TIME = "00:00"
DEFAULT_TO_TIME = "23:59"


def _clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_date(value, field_name):
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name} '{text}'. Expected YYYY-MM-DD.") from exc


def _normalize_time(value, field_name):
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return datetime.strptime(text, "%H:%M").strftime("%H:%M")
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name} '{text}'. Expected HH:MM.") from exc


def build_period_filter(from_date=None, to_date=None, from_time=None, to_time=None):
    requested_from_date = _clean_text(from_date)
    requested_to_date = _clean_text(to_date)
    requested_from_time = _clean_text(from_time)
    requested_to_time = _clean_text(to_time)

    if not any((requested_from_date, requested_to_date, requested_from_time, requested_to_time)):
        return {
            "applied": False,
            "from_date": None,
            "to_date": None,
            "from_time": DEFAULT_FROM_TIME,
            "to_time": DEFAULT_TO_TIME,
            "from_iso": None,
            "to_iso": None,
            "from_ts": None,
            "to_ts": None,
            "label_ka": "",
        }

    if not (requested_from_date or requested_to_date):
        raise ValueError("from_time/to_time require from_date/to_date.")

    normalized_from_date = _normalize_date(
        requested_from_date or requested_to_date,
        "from_date",
    )
    normalized_to_date = _normalize_date(
        requested_to_date or requested_from_date,
        "to_date",
    )
    normalized_from_time = _normalize_time(
        requested_from_time or DEFAULT_FROM_TIME,
        "from_time",
    ) or DEFAULT_FROM_TIME
    normalized_to_time = _normalize_time(
        requested_to_time or DEFAULT_TO_TIME,
        "to_time",
    ) or DEFAULT_TO_TIME

    from_ts = pd.Timestamp(
        datetime.strptime(
            f"{normalized_from_date} {normalized_from_time}",
            "%Y-%m-%d %H:%M",
        )
    )
    to_ts = pd.Timestamp(
        datetime.strptime(
            f"{normalized_to_date} {normalized_to_time}",
            "%Y-%m-%d %H:%M",
        )
    )
    if from_ts > to_ts:
        raise ValueError("from_date/from_time must be less than or equal to to_date/to_time.")

    if normalized_from_date == normalized_to_date:
        label_ka = f"{normalized_from_date} {normalized_from_time} — {normalized_to_time}"
    else:
        label_ka = (
            f"{normalized_from_date} {normalized_from_time} — "
            f"{normalized_to_date} {normalized_to_time}"
        )

    return {
        "applied": True,
        "from_date": normalized_from_date,
        "to_date": normalized_to_date,
        "from_time": normalized_from_time,
        "to_time": normalized_to_time,
        "from_iso": from_ts.isoformat(),
        "to_iso": to_ts.isoformat(),
        "from_ts": from_ts,
        "to_ts": to_ts,
        "label_ka": label_ka,
    }


def parse_source_datetime(value):
    if isinstance(value, pd.Timestamp):
        return value
    if isinstance(value, datetime):
        return pd.Timestamp(value)
    dt = _parse_rs_datetime(value)
    if dt is None or pd.isna(dt):
        return pd.NaT
    return pd.Timestamp(dt)


def matches_period(value, period_filter):
    if not period_filter or not bool(period_filter.get("applied")):
        return True
    ts = parse_source_datetime(value)
    if pd.isna(ts):
        return False
    return period_filter["from_ts"] <= ts <= period_filter["to_ts"]


def serialize_period_filter(
    period_filter,
    *,
    total_rows_seen=0,
    matched_rows=0,
    excluded_unparseable_count=0,
):
    applied = bool((period_filter or {}).get("applied"))
    base = {
        "applied": applied,
        "from_date": (period_filter or {}).get("from_date"),
        "to_date": (period_filter or {}).get("to_date"),
        "from_time": (period_filter or {}).get("from_time") or DEFAULT_FROM_TIME,
        "to_time": (period_filter or {}).get("to_time") or DEFAULT_TO_TIME,
        "from_iso": (period_filter or {}).get("from_iso"),
        "to_iso": (period_filter or {}).get("to_iso"),
        "label_ka": (period_filter or {}).get("label_ka") or "",
        "total_rows_seen": int(total_rows_seen or 0),
        "matched_rows": int(matched_rows or 0),
        "excluded_unparseable_count": int(excluded_unparseable_count or 0),
    }
    return base


def build_period_caveat_ka(period_meta):
    if not isinstance(period_meta, dict) or not period_meta.get("applied"):
        return ""
    excluded_unparseable_count = int(period_meta.get("excluded_unparseable_count") or 0)
    if excluded_unparseable_count <= 0:
        return ""
    return (
        "არჩეული პერიოდის ფილტრისას "
        f"{excluded_unparseable_count} ჩანაწერი გამოირიცხა, რადგან თარიღი ვერ დაიპარსა."
    )
