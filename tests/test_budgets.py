from __future__ import annotations

from datetime import date

import pandas as pd

from pennypilot.services.budgets import (
    budget_usage,
    estimate_month_end,
    suggest_budgets,
)


def test_budget_usage_not_set():
    usage = budget_usage(100_000, None)
    assert usage.percentage is None
    assert usage.remaining is None
    assert usage.status == "Belum diatur"
    assert usage.is_over is False


def test_budget_usage_zero_budget_has_no_division_by_zero():
    usage = budget_usage(100_000, 0)
    assert usage.percentage is None
    assert usage.remaining == -100_000
    assert usage.is_over is True
    assert usage.status == "Anggaran nol"


def test_budget_usage_normal_and_over():
    normal = budget_usage(250_000, 1_000_000)
    assert normal.percentage == 25.0
    assert normal.remaining == 750_000
    assert normal.status == "Dalam anggaran"

    over = budget_usage(1_250_000, 1_000_000)
    assert over.percentage == 125.0
    assert over.is_over is True
    assert over.status == "Melewati anggaran"


def test_projection_28_day_month_first_day():
    result = estimate_month_end(100_000, date(2026, 2, 1), "2026-02")
    assert result.available is True
    assert result.days_in_month == 28
    assert result.days_elapsed == 1
    assert result.projected == 2_800_000


def test_projection_29_day_month():
    result = estimate_month_end(100_000, date(2024, 2, 1), "2024-02")
    assert result.days_in_month == 29
    assert result.projected == 2_900_000


def test_projection_30_day_month():
    result = estimate_month_end(1_000_000, date(2026, 4, 10), "2026-04")
    assert result.days_in_month == 30
    assert result.days_elapsed == 10
    assert result.projected == 3_000_000


def test_projection_31_day_month_last_day():
    result = estimate_month_end(2_000_000, date(2026, 5, 31), "2026-05")
    assert result.days_in_month == 31
    assert result.days_elapsed == 31
    assert result.projected == 2_000_000


def test_projection_past_month_is_final_not_extrapolated():
    result = estimate_month_end(4_321_000, date(2026, 4, 10), "2026-03")
    assert result.available is True
    assert result.status == "final"
    assert result.projected == 4_321_000


def test_projection_future_month_unavailable():
    result = estimate_month_end(100_000, date(2026, 4, 10), "2026-05")
    assert result.available is False
    assert result.projected is None
    assert result.status == "future"


def test_projection_current_month_without_spending():
    result = estimate_month_end(0, date(2026, 4, 10), "2026-04")
    assert result.available is False
    assert result.projected is None
    assert result.status == "no_data"
    assert "Belum ada pengeluaran" in result.note


def test_projection_uses_local_today_and_day_at_least_one():
    result = estimate_month_end(300_000, date(2026, 4, 1), "2026-04")
    assert result.days_elapsed == 1
    assert result.projected == 9_000_000


def _frame(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "transaction_date",
            "amount",
            "transaction_type",
            "category",
            "description",
        ],
    )


def test_budget_suggestions_use_median_of_three_complete_months():
    rows = [
        (date(2026, 1, 5), 100, "expense", "Makanan", "A"),
        (date(2026, 1, 6), 50, "expense", "Transportasi", "B"),
        (date(2026, 2, 5), 200, "expense", "Makanan", "C"),
        (date(2026, 3, 5), 300, "expense", "Makanan", "D"),
        (date(2026, 3, 6), 100, "expense", "Transportasi", "E"),
        (date(2026, 4, 2), 9_999, "expense", "Makanan", "Bulan berjalan"),
    ]
    result = suggest_budgets(_frame(rows), date(2026, 4, 15))
    assert result.available is True
    assert result.months_used == ["2026-01", "2026-02", "2026-03"]
    assert result.suggestions == {"Makanan": 200, "Transportasi": 50}
    assert result.total_suggestion == 200


def test_budget_suggestions_require_three_months():
    rows = [
        (date(2026, 1, 5), 100, "expense", "Makanan", "A"),
        (date(2026, 2, 5), 200, "expense", "Makanan", "B"),
    ]
    result = suggest_budgets(_frame(rows), date(2026, 4, 15))
    assert result.available is False
    assert "minimal 3" in result.note


def test_budget_suggestions_empty_and_income_only():
    assert suggest_budgets(_frame([]), date(2026, 4, 15)).available is False
    rows = [(date(2026, 1, 5), 100, "income", "Pendapatan", "Gaji")]
    assert suggest_budgets(_frame(rows), date(2026, 4, 15)).available is False
