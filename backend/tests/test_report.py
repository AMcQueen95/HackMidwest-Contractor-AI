import json
from pathlib import Path

import pytest

from backend.app.finance import build_report


def test_report_matches_frontend_finance_fixtures(books):
    fixtures = json.loads(
        (
            Path(__file__).resolve().parents[2] / "frontend/src/api/mock/books.json"
        ).read_text()
    )
    for month, expected in fixtures.items():
        report = build_report(books, month, is_sample=True, dataset_revision="sample")
        for key, value in expected.items():
            assert report[key] == value, (month, key)
        assert report["months"] == ["2026-08", "2026-09"]
        assert report["is_sample"] is True
        json.dumps(report, allow_nan=False)


def test_report_defaults_to_latest_and_preserves_snapshot_dates(books):
    report = build_report(books)
    assert report["month"] == "2026-09"
    assert report["previous_summary"]["profit"] == 15000
    august = build_report(books, "2026-08")
    assert august["previous_summary"] is None
    assert august["monthly_summary"]["month"] == "2026-08"
    assert august["cash_balance"]["as_of_date"] == "2026-09-30"
    assert august["receivables"]["as_of_date"] == "2026-09-30"


@pytest.mark.parametrize("month", ["2026-07", "2026-10", "2026-9", "bad", ""])
def test_report_rejects_unavailable_months(books, month):
    with pytest.raises(ValueError, match="opening/as-of window"):
        build_report(books, month)
