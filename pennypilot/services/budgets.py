"""Perhitungan anggaran, proyeksi akhir bulan, dan saran anggaran."""

from __future__ import annotations

import math
import statistics
from datetime import date

import pandas as pd

from pennypilot.config import BUDGET_SUGGESTION_MONTHS
from pennypilot.models import BudgetUsage, ProjectionResult, SuggestionResult
from pennypilot.utils import (
    days_in_month,
    format_rupiah,
    month_bounds,
    month_label,
    parse_month,
    shift_month,
)


def budget_usage(actual: float, budget: float | None) -> BudgetUsage:
    """Hitung pemakaian anggaran tanpa pembagian nol atau nilai tak hingga."""

    actual_value = float(actual) if math.isfinite(float(actual)) else 0.0
    if budget is None:
        return BudgetUsage(
            actual=actual_value,
            budget=None,
            percentage=None,
            remaining=None,
            is_over=False,
            status="Belum diatur",
        )
    budget_value = float(budget)
    if not math.isfinite(budget_value) or budget_value < 0:
        budget_value = 0.0
    if budget_value == 0:
        return BudgetUsage(
            actual=actual_value,
            budget=0.0,
            percentage=None,
            remaining=-actual_value,
            is_over=actual_value > 0,
            status="Anggaran nol",
        )
    percentage = actual_value / budget_value * 100
    return BudgetUsage(
        actual=actual_value,
        budget=budget_value,
        percentage=round(percentage, 1),
        remaining=round(budget_value - actual_value, 2),
        is_over=actual_value > budget_value,
        status="Melewati anggaran" if actual_value > budget_value else "Dalam anggaran",
    )


def estimate_month_end(
    spent_so_far: float,
    today: date,
    month: str,
) -> ProjectionResult:
    """Ekstrapolasi linear pengeluaran bulan berjalan.

    * Bulan lampau: total aktual final.
    * Bulan mendatang: belum tersedia.
    * Bulan berjalan tanpa pengeluaran: belum tersedia.
    """

    year, month_number = parse_month(month)
    total_days = days_in_month(year, month_number)
    today_month = today.strftime("%Y-%m")
    spent = float(spent_so_far) if math.isfinite(float(spent_so_far)) else 0.0
    spent = max(0.0, spent)

    if month < today_month:
        return ProjectionResult(
            available=True,
            projected=round(spent, 2),
            status="final",
            days_elapsed=total_days,
            days_in_month=total_days,
            note="Bulan sudah selesai; angka adalah total aktual, bukan proyeksi.",
        )
    if month > today_month:
        return ProjectionResult(
            available=False,
            projected=None,
            status="future",
            days_elapsed=0,
            days_in_month=total_days,
            note="Proyeksi belum tersedia untuk bulan yang belum berjalan.",
        )
    if spent <= 0:
        return ProjectionResult(
            available=False,
            projected=None,
            status="no_data",
            days_elapsed=max(today.day, 1),
            days_in_month=total_days,
            note="Belum ada pengeluaran bulan ini, sehingga proyeksi belum tersedia.",
        )

    days_elapsed = min(max(today.day, 1), total_days)
    projected = spent / days_elapsed * total_days
    return ProjectionResult(
        available=True,
        projected=round(projected, 2),
        status="current",
        days_elapsed=days_elapsed,
        days_in_month=total_days,
        note=(
            f"Estimasi = pengeluaran {format_rupiah(spent)} / {days_elapsed} hari "
            f"x {total_days} hari. Ini ekstrapolasi sederhana, bukan jaminan."
        ),
    )


def suggest_budgets(
    frame: pd.DataFrame,
    today: date,
    *,
    months_count: int = BUDGET_SUGGESTION_MONTHS,
) -> SuggestionResult:
    """Saran dari median total kategori pada bulan lengkap terakhir yang ada data."""

    if frame.empty:
        return SuggestionResult(
            available=False,
            note="Belum ada data pengeluaran untuk membuat saran anggaran.",
        )
    data = frame.copy()
    data["transaction_date"] = pd.to_datetime(data["transaction_date"], errors="coerce", format="mixed")
    data["amount"] = pd.to_numeric(data["amount"], errors="coerce")
    data = data[
        data["transaction_date"].notna()
        & data["amount"].notna()
        & (data["transaction_type"] == "expense")
    ].copy()
    if data.empty:
        return SuggestionResult(
            available=False,
            note="Belum ada data pengeluaran untuk membuat saran anggaran.",
        )

    current_month = today.strftime("%Y-%m")
    data["month"] = data["transaction_date"].dt.strftime("%Y-%m")
    data = data[data["month"] < current_month]
    complete_months = sorted(data["month"].unique(), reverse=True)
    if len(complete_months) < months_count:
        return SuggestionResult(
            available=False,
            months_used=sorted(complete_months),
            note=(
                f"Butuh minimal {months_count} bulan lengkap dengan data pengeluaran. "
                f"Saat ini tersedia {len(complete_months)} bulan."
            ),
        )

    selected = sorted(complete_months[:months_count])
    scoped = data[data["month"].isin(selected)]
    pivot = scoped.groupby(["month", "category"])["amount"].sum().unstack()
    pivot = pivot.reindex(selected).fillna(0.0)
    suggestions: dict[str, float] = {}
    for category in pivot.columns:
        values = [float(value) for value in pivot[category].tolist()]
        median = float(statistics.median(values))
        if median > 0:
            suggestions[str(category)] = round(median, 2)

    monthly_totals = scoped.groupby("month")["amount"].sum().reindex(selected, fill_value=0.0)
    total_suggestion = round(float(statistics.median(monthly_totals.tolist())), 2)
    if not suggestions:
        return SuggestionResult(
            available=False,
            months_used=selected,
            note="Data tiga bulan terakhir belum cukup beragam untuk membuat saran.",
        )

    return SuggestionResult(
        available=True,
        suggestions=dict(sorted(suggestions.items())),
        total_suggestion=total_suggestion,
        months_used=selected,
        note=(
            "Median total kategori per bulan dari "
            f"{month_label(selected[0])} sampai {month_label(selected[-1])}. "
            "Bulan tanpa pengeluaran kategori dihitung Rp0. Tinjau sebelum menyimpan."
        ),
    )


def current_projection_for_frame(
    frame: pd.DataFrame,
    month: str,
    today: date,
) -> ProjectionResult:
    start, end = month_bounds(month)
    if frame.empty:
        spent = 0.0
    else:
        dates = pd.to_datetime(frame["transaction_date"], errors="coerce", format="mixed")
        mask = (
            (dates.dt.date >= start)
            & (dates.dt.date <= end)
            & (frame["transaction_type"] == "expense")
        )
        spent = float(pd.to_numeric(frame.loc[mask, "amount"], errors="coerce").sum())
    return estimate_month_end(spent, today, month)


def next_month(month: str, offset: int = 1) -> str:
    return shift_month(month, offset)
