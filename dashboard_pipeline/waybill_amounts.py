"""
Shared waybill amount calculation helpers.

These functions compute nominal, effective, and returned amounts
for RS waybill rows based on cancellation / return flags.
Previously duplicated in 5 files; now centralised here.
"""
import pandas as pd


def get_nominal(row):
    """Return raw numeric amount from 'თანხა', or 0 if missing/unparseable."""
    return pd.to_numeric(row["თანხა"], errors="coerce") if not pd.isna(row["თანხა"]) else 0


def get_effective(row):
    """Effective amount: 0 if cancelled, negated if returned, else nominal."""
    raw = pd.to_numeric(row["თანხა"], errors="coerce")
    val = 0.0 if pd.isna(raw) else float(raw)
    if row["გაუქმებული (ფლეგი)"]:
        return 0.0
    if row["უკან დაბრუნება (ფლეგი)"]:
        v = float(val) if not pd.isna(val) else 0.0
        return v if v < 0 else -v
    return val


def get_returned(row):
    """Returned amount: nominal if returned & not cancelled, else 0."""
    raw = pd.to_numeric(row["თანხა"], errors="coerce")
    val = 0.0 if pd.isna(raw) else float(raw)
    if row["უკან დაბრუნება (ფლეგი)"] and not row["გაუქმებული (ფლეგი)"]:
        return val
    return 0.0
