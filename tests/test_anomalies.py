from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from pennypilot.services.anomalies import detect_anomalies, evaluate_amount, summarize_statuses


def test_insufficient_comparisons_is_not_normal():
    result = evaluate_amount(500_000, [50_000, 60_000, 70_000, 80_000], "Makanan")
    assert result.status == "insufficient"
    assert result.comparison_count == 4
    assert result.threshold is None
    assert "Belum cukup data" in result.reason


def test_mad_zero_uses_fallback_threshold():
    result = evaluate_amount(300_000, [100_000] * 6, "Belanja")
    assert result.mad == 0
    assert result.threshold == 250_000
    assert result.status == "unusual"

    normal = evaluate_amount(200_000, [100_000] * 6, "Belanja")
    assert normal.status == "normal"


def test_median_and_mad_zero_is_not_informative():
    result = evaluate_amount(1_000, [0] * 5, "Lainnya")
    assert result.status == "not_informative"
    assert result.threshold is None
    assert "belum informatif" in result.reason


def test_mad_threshold_and_outlier():
    values = [10_000, 20_000, 30_000, 40_000, 50_000]
    result = evaluate_amount(100_000, values, "Makanan")
    assert result.median == 30_000
    assert result.mad == 10_000
    assert result.threshold == pytest.approx(74_478.0, abs=0.1)
    assert result.status == "unusual"
    assert "Rp100.000" in result.reason
    assert "median Rp30.000" in result.reason


def test_outlier_equal_to_threshold_is_normal():
    values = [10_000, 20_000, 30_000, 40_000, 50_000]
    result = evaluate_amount(74_478, values, "Makanan")
    assert result.status == "normal"


def _frame(rows):
    return pd.DataFrame(
        rows,
        columns=["id", "transaction_date", "description", "amount", "transaction_type", "category"],
    )


def test_detection_excludes_current_transaction_from_baseline():
    rows = [
        (index + 1, date(2026, 1, index + 1), f"Lama {index}", 50_000, "expense", "Makanan")
        for index in range(4)
    ]
    rows.append((99, date(2026, 2, 1), "Sekarang", 500_000, "expense", "Makanan"))
    results = detect_anomalies(_frame(rows))
    current = next(item for item in results if item.transaction_id == 99)
    assert current.comparison_count == 4
    assert current.status == "insufficient"


def test_detection_180_day_window_and_inclusive_boundary():
    today = date(2026, 7, 1)
    rows = [
        (1, today - timedelta(days=180), "Pas batas", 50_000, "expense", "Makanan"),
        (2, today - timedelta(days=20), "Dekat", 50_000, "expense", "Makanan"),
        (3, today - timedelta(days=19), "Dekat 2", 50_000, "expense", "Makanan"),
        (4, today - timedelta(days=18), "Dekat 3", 50_000, "expense", "Makanan"),
        (5, today - timedelta(days=17), "Dekat 4", 50_000, "expense", "Makanan"),
        (6, today - timedelta(days=200), "Terlalu lama", 50_000, "expense", "Makanan"),
        (7, today, "Sekarang", 500_000, "expense", "Makanan"),
    ]
    results = detect_anomalies(_frame(rows), start_date=today, end_date=today)
    current = results[0]
    assert current.transaction_id == 7
    assert current.comparison_count == 5
    assert current.status == "unusual"


def test_detection_isolates_categories_and_ignores_income():
    rows = [
        (index + 1, date(2026, 1, index + 1), f"Makan {index}", 50_000, "expense", "Makanan")
        for index in range(6)
    ]
    rows += [
        (20, date(2026, 1, 10), "Belanja", 500_000, "expense", "Belanja"),
        (21, date(2026, 1, 11), "Bonus", 5_000_000, "income", "Pendapatan"),
        (22, date(2026, 1, 12), "Makan besar", 500_000, "expense", "Makanan"),
    ]
    results = detect_anomalies(_frame(rows))
    by_id = {item.transaction_id: item for item in results}
    assert 21 not in by_id
    assert by_id[20].status == "insufficient"
    assert by_id[22].comparison_count == 6
    assert by_id[22].status == "unusual"


def test_same_day_transactions_are_not_used_as_baseline():
    rows = [
        (index + 1, date(2026, 1, index + 1), f"Lama {index}", 50_000, "expense", "Makanan")
        for index in range(4)
    ]
    rows += [
        (20, date(2026, 1, 10), "Pagi", 50_000, "expense", "Makanan"),
        (21, date(2026, 1, 10), "Malam", 500_000, "expense", "Makanan"),
    ]
    results = detect_anomalies(_frame(rows))
    by_id = {item.transaction_id: item for item in results}
    assert by_id[21].status == "insufficient"
    assert by_id[21].comparison_count == 4


def test_empty_data_and_status_summary():
    assert detect_anomalies(_frame([])) == []
    result = evaluate_amount(20, [10] * 5, "Makanan")
    assert summarize_statuses([result])["normal"] == 1
