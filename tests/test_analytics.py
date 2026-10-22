from __future__ import annotations

import math
from datetime import date

import pandas as pd

from pennypilot.services import analytics


def _rows():
    return [
        {
            "id": 1,
            "transaction_date": date(2026, 1, 2),
            "description": "Gaji",
            "amount": 10_000_000,
            "transaction_type": "income",
            "category": "Pendapatan",
        },
        {
            "id": 2,
            "transaction_date": date(2026, 1, 3),
            "description": "Makan",
            "amount": 200_000,
            "transaction_type": "expense",
            "category": "Makanan",
        },
        {
            "id": 3,
            "transaction_date": date(2026, 1, 5),
            "description": "Belanja",
            "amount": 300_000,
            "transaction_type": "expense",
            "category": "Belanja",
        },
        {
            "id": 4,
            "transaction_date": date(2026, 4, 2),
            "description": "Makan",
            "amount": 100_000,
            "transaction_type": "expense",
            "category": "Makanan",
        },
    ]


def test_to_frame_empty():
    frame = analytics.to_frame([])
    assert frame.empty
    assert "transaction_date" in frame.columns
    assert "amount" in frame.columns


def test_monthly_kpis():
    frame = analytics.to_frame(_rows())
    kpi = analytics.monthly_kpis(frame, "2026-01")
    assert kpi["income"] == 10_000_000
    assert kpi["expense"] == 500_000
    assert kpi["net"] == 9_500_000
    assert kpi["transaction_count"] == 3
    assert kpi["expense_count"] == 2


def test_monthly_kpis_empty_month_is_zero_not_nan():
    frame = analytics.to_frame(_rows())
    kpi = analytics.monthly_kpis(frame, "2026-02")
    assert kpi == {
        "income": 0.0,
        "expense": 0.0,
        "net": 0.0,
        "transaction_count": 0,
        "income_count": 0,
        "expense_count": 0,
    }
    assert all(not isinstance(value, float) or math.isfinite(value) for value in kpi.values())


def test_category_breakdown_and_share():
    frame = analytics.to_frame(_rows())
    result = analytics.category_breakdown(frame, "2026-01")
    assert result["category"].tolist() == ["Belanja", "Makanan"]
    assert result["amount"].tolist() == [300_000, 200_000]
    assert result["share"].tolist() == [60.0, 40.0]

    empty = analytics.category_breakdown(frame, "2026-02")
    assert empty.empty
    assert list(empty.columns) == ["category", "amount", "share"]


def test_monthly_trend_includes_zero_months_and_no_nan():
    frame = analytics.to_frame(_rows())
    trend = analytics.monthly_trend(frame, end_month="2026-04", months=4)
    assert trend["month"].tolist() == ["2026-01", "2026-02", "2026-03", "2026-04"]
    assert trend.loc[trend["month"] == "2026-02", "expense"].iloc[0] == 0
    assert trend.loc[trend["month"] == "2026-04", "income"].iloc[0] == 0
    assert not trend[["income", "expense", "net"]].isna().any().any()


def test_trend_empty_data():
    trend = analytics.monthly_trend(analytics.to_frame([]))
    assert trend.empty
    assert list(trend.columns) == analytics.TREND_COLUMNS


def test_available_months_and_filter():
    frame = analytics.to_frame(_rows())
    assert analytics.available_months(frame) == ["2026-04", "2026-01"]
    january = analytics.filter_month(frame, "2026-01")
    assert len(january) == 3


def test_budget_vs_actual_by_category_statuses():
    frame = analytics.to_frame(_rows())
    result = analytics.budget_vs_actual_by_category(
        frame,
        "2026-01",
        {"Makanan": 250_000, "Belanja": 200_000, "Hiburan": None, "Kesehatan": 0},
    )
    by_category = {row["category"]: row for _, row in result.iterrows()}
    assert by_category["Makanan"]["status"] == "Dalam anggaran"
    assert by_category["Makanan"]["percentage"] == 80.0
    assert by_category["Belanja"]["status"] == "Melewati anggaran"
    assert by_category["Hiburan"]["status"] == "Belum diatur"
    assert by_category["Kesehatan"]["status"] == "Anggaran nol"
    assert pd.isna(by_category["Kesehatan"]["percentage"])


def test_to_frame_sanitizes_bad_rows():
    frame = analytics.to_frame(
        [
            {
                "id": 1,
                "transaction_date": "bukan tanggal",
                "description": "Rusak",
                "amount": 100,
                "transaction_type": "expense",
                "category": "Lainnya",
            },
            {
                "id": 2,
                "transaction_date": date(2026, 1, 1),
                "description": "Baik",
                "amount": 200,
                "transaction_type": "expense",
                "category": "Lainnya",
            },
        ]
    )
    assert len(frame) == 1
    assert frame.iloc[0]["description"] == "Baik"
    assert pd.notna(frame.iloc[0]["transaction_date"])
