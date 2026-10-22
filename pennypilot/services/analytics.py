"""Agregasi analitik murni dari DataFrame transaksi."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from pennypilot.utils import month_bounds, month_range, parse_month

TRANSACTION_COLUMNS = [
    "id",
    "transaction_date",
    "description",
    "amount",
    "transaction_type",
    "category",
    "category_source",
    "fingerprint",
    "source_file",
    "created_at",
    "updated_at",
]

TREND_COLUMNS = ["month", "income", "expense", "net"]


def empty_transactions_frame() -> pd.DataFrame:
    frame = pd.DataFrame(columns=TRANSACTION_COLUMNS)
    frame["transaction_date"] = pd.to_datetime(frame["transaction_date"], errors="coerce", format="mixed")
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").astype(float)
    return frame


def to_frame(rows: Iterable[Any]) -> pd.DataFrame:
    """Normalisasi baris database menjadi DataFrame yang aman untuk analitik."""

    records: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            records.append(dict(row))
        elif hasattr(row, "keys"):
            records.append({key: row[key] for key in row.keys()})
    if not records:
        return empty_transactions_frame()

    frame = pd.DataFrame(records)
    for column in TRANSACTION_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    frame = frame[TRANSACTION_COLUMNS].copy()
    frame["transaction_date"] = pd.to_datetime(frame["transaction_date"], errors="coerce", format="mixed")
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    frame = frame[frame["transaction_date"].notna() & frame["amount"].notna()].copy()
    frame["amount"] = frame["amount"].astype(float).abs()
    frame["transaction_type"] = frame["transaction_type"].fillna("expense")
    frame["category"] = frame["category"].fillna("Lainnya")
    frame["description"] = frame["description"].fillna("")
    frame["month"] = frame["transaction_date"].dt.strftime("%Y-%m")
    return frame.reset_index(drop=True)


def filter_month(frame: pd.DataFrame, month: str) -> pd.DataFrame:
    parse_month(month)
    if frame.empty:
        return frame.copy()
    if "month" not in frame.columns:
        frame = to_frame(frame)
    return frame[frame["month"] == month].copy()


def filter_range(
    frame: pd.DataFrame,
    start_date,
    end_date,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    date_values = pd.to_datetime(frame["transaction_date"], errors="coerce", format="mixed")
    mask = (date_values >= pd.Timestamp(start_date)) & (date_values <= pd.Timestamp(end_date))
    return frame[mask].copy()


def available_months(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "month" not in frame.columns:
        return []
    months = [str(value) for value in frame["month"].dropna().unique()]
    return sorted(months, reverse=True)


def monthly_kpis(frame: pd.DataFrame, month: str) -> dict[str, float | int]:
    month_frame = filter_month(frame, month)
    income = float(
        month_frame.loc[month_frame["transaction_type"] == "income", "amount"].sum()
    )
    expense = float(
        month_frame.loc[month_frame["transaction_type"] == "expense", "amount"].sum()
    )
    return {
        "income": round(income, 2),
        "expense": round(expense, 2),
        "net": round(income - expense, 2),
        "transaction_count": int(len(month_frame)),
        "income_count": int((month_frame["transaction_type"] == "income").sum()),
        "expense_count": int((month_frame["transaction_type"] == "expense").sum()),
    }


def category_breakdown(frame: pd.DataFrame, month: str) -> pd.DataFrame:
    month_frame = filter_month(frame, month)
    expenses = month_frame[month_frame["transaction_type"] == "expense"]
    if expenses.empty:
        return pd.DataFrame(columns=["category", "amount", "share"])
    grouped = (
        expenses.groupby("category", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
        .reset_index(drop=True)
    )
    total = float(grouped["amount"].sum())
    grouped["share"] = grouped["amount"] / total * 100 if total > 0 else 0.0
    return grouped


def monthly_trend(
    frame: pd.DataFrame,
    *,
    end_month: str | None = None,
    months: int = 6,
) -> pd.DataFrame:
    """Tren kalender termasuk bulan tanpa transaksi (nilai nol)."""

    if frame.empty:
        return pd.DataFrame(columns=TREND_COLUMNS)
    if end_month is None:
        valid_months = available_months(frame)
        if not valid_months:
            return pd.DataFrame(columns=TREND_COLUMNS)
        end_month = valid_months[0]
    month_list = month_range(end_month, months)
    if not month_list:
        return pd.DataFrame(columns=TREND_COLUMNS)

    scoped = frame[frame["month"].isin(month_list)]
    pivot = (
        scoped.groupby(["month", "transaction_type"])["amount"]
        .sum()
        .unstack(fill_value=0.0)
        .reindex(month_list, fill_value=0.0)
    )
    for column in ("income", "expense"):
        if column not in pivot.columns:
            pivot[column] = 0.0
    pivot["net"] = pivot["income"] - pivot["expense"]
    result = pivot.reset_index().rename(columns={"index": "month"})
    result = result[TREND_COLUMNS].copy()
    result.columns.name = None
    for column in ("income", "expense", "net"):
        result[column] = result[column].astype(float).round(2)
    return result


def budget_vs_actual_by_category(
    frame: pd.DataFrame,
    month: str,
    budgets: dict[str | None, float],
) -> pd.DataFrame:
    breakdown = category_breakdown(frame, month)
    categories = set(breakdown["category"].tolist()) | {
        category for category in budgets if category is not None
    }
    rows: list[dict[str, Any]] = []
    actual_map = dict(zip(breakdown["category"], breakdown["amount"], strict=False))
    for category in sorted(categories):
        actual = float(actual_map.get(category, 0.0))
        budget = budgets.get(category)
        if budget is None:
            rows.append(
                {
                    "category": category,
                    "actual": actual,
                    "budget": None,
                    "percentage": None,
                    "remaining": None,
                    "status": "Belum diatur",
                }
            )
        elif budget == 0:
            rows.append(
                {
                    "category": category,
                    "actual": actual,
                    "budget": 0.0,
                    "percentage": None,
                    "remaining": -actual,
                    "status": "Anggaran nol",
                }
            )
        else:
            percentage = actual / budget * 100
            rows.append(
                {
                    "category": category,
                    "actual": actual,
                    "budget": float(budget),
                    "percentage": round(percentage, 1),
                    "remaining": round(float(budget) - actual, 2),
                    "status": "Melewati anggaran" if actual > budget else "Dalam anggaran",
                }
            )
    return pd.DataFrame(
        rows,
        columns=["category", "actual", "budget", "percentage", "remaining", "status"],
    )


def month_expense_total(frame: pd.DataFrame, month: str) -> float:
    start, end = month_bounds(month)
    scoped = filter_range(frame, start, end)
    return float(
        scoped.loc[scoped["transaction_type"] == "expense", "amount"].sum()
    )
