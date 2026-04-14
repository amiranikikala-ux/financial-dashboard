"""
Unit tests for dashboard_pipeline.waybill_amounts

Covers all edge cases for get_nominal, get_effective, get_returned:
- Normal row, cancelled, returned, cancelled+returned, missing amount, non-numeric.
"""
import pandas as pd
import pytest

from dashboard_pipeline.waybill_amounts import get_effective, get_nominal, get_returned


def _row(amount, cancelled=False, returned=False):
    """Helper: build a dict that looks like a waybill DataFrame row."""
    return {
        "თანხა": amount,
        "გაუქმებული (ფლეგი)": cancelled,
        "უკან დაბრუნება (ფლეგი)": returned,
    }


# ── get_nominal ──────────────────────────────────────────────────────

class TestGetNominal:
    def test_normal_number(self):
        assert get_nominal(_row(150.5)) == pytest.approx(150.5)

    def test_string_number(self):
        assert get_nominal(_row("200")) == pytest.approx(200.0)

    def test_zero(self):
        assert get_nominal(_row(0)) == pytest.approx(0.0)

    def test_missing_none(self):
        assert get_nominal(_row(None)) == 0

    def test_missing_nan(self):
        assert get_nominal(_row(float("nan"))) == 0

    def test_non_numeric_string(self):
        result = get_nominal(_row("abc"))
        assert pd.isna(result)


# ── get_effective ────────────────────────────────────────────────────

class TestGetEffective:
    def test_normal_row(self):
        """Normal row → return amount as-is."""
        assert get_effective(_row(100.0)) == pytest.approx(100.0)

    def test_cancelled(self):
        """Cancelled → 0."""
        assert get_effective(_row(500.0, cancelled=True)) == 0.0

    def test_returned_positive(self):
        """Returned with positive amount → negate it."""
        assert get_effective(_row(300.0, returned=True)) == pytest.approx(-300.0)

    def test_returned_negative(self):
        """Returned with already-negative amount → keep negative."""
        assert get_effective(_row(-250.0, returned=True)) == pytest.approx(-250.0)

    def test_cancelled_and_returned(self):
        """Cancelled takes precedence over returned → 0."""
        assert get_effective(_row(100.0, cancelled=True, returned=True)) == 0.0

    def test_zero_amount(self):
        assert get_effective(_row(0)) == pytest.approx(0.0)

    def test_missing_amount(self):
        assert get_effective(_row(None)) == pytest.approx(0.0)


# ── get_returned ─────────────────────────────────────────────────────

class TestGetReturned:
    def test_normal_row(self):
        """Not returned → 0."""
        assert get_returned(_row(100.0)) == 0.0

    def test_returned(self):
        """Returned → return amount."""
        assert get_returned(_row(300.0, returned=True)) == pytest.approx(300.0)

    def test_cancelled_and_returned(self):
        """Cancelled+returned → 0 (cancelled wins)."""
        assert get_returned(_row(300.0, cancelled=True, returned=True)) == 0.0

    def test_cancelled_only(self):
        assert get_returned(_row(500.0, cancelled=True)) == 0.0

    def test_missing_amount(self):
        assert get_returned(_row(None, returned=True)) == pytest.approx(0.0)


# ── DataFrame integration ───────────────────────────────────────────

class TestDataFrameIntegration:
    """Verify functions work correctly with df.apply(fn, axis=1)."""

    def test_apply_effective(self):
        df = pd.DataFrame([
            {"თანხა": 100, "ტიპი": "მიწოდება", "სტატუსი": "აქტიური"},
            {"თანხა": 200, "ტიპი": "უკან დაბრუნება", "სტატუსი": "აქტიური"},
            {"თანხა": 300, "ტიპი": "მიწოდება", "სტატუსი": "გაუქმებული"},
        ])
        df["უკან დაბრუნება (ფლეგი)"] = df["ტიპი"].str.contains("უკან დაბრუნება", case=False, na=False)
        df["გაუქმებული (ფლეგი)"] = df["სტატუსი"].str.contains("გაუქმებული", case=False, na=False)

        result = df.apply(get_effective, axis=1)
        assert result.tolist() == pytest.approx([100.0, -200.0, 0.0])

    def test_apply_returned(self):
        df = pd.DataFrame([
            {"თანხა": 100, "ტიპი": "მიწოდება", "სტატუსი": "აქტიური"},
            {"თანხა": 200, "ტიპი": "უკან დაბრუნება", "სტატუსი": "აქტიური"},
        ])
        df["უკან დაბრუნება (ფლეგი)"] = df["ტიპი"].str.contains("უკან დაბრუნება", case=False, na=False)
        df["გაუქმებული (ფლეგი)"] = df["სტატუსი"].str.contains("გაუქმებული", case=False, na=False)

        result = df.apply(get_returned, axis=1)
        assert result.tolist() == pytest.approx([0.0, 200.0])
