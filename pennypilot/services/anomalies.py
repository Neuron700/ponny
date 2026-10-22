"""Deteksi pengeluaran tidak biasa berbasis median dan MAD."""

from __future__ import annotations

import math
import statistics
from collections import deque
from datetime import date, timedelta

import pandas as pd

from pennypilot.config import (
    ANOMALY_FALLBACK_MULTIPLIER,
    ANOMALY_LOOKBACK_DAYS,
    ANOMALY_MAD_MULTIPLIER,
    ANOMALY_MAD_SCALE,
    ANOMALY_MIN_COMPARISONS,
)
from pennypilot.models import AnomalyResult
from pennypilot.utils import format_rupiah


def _comparison_values(values: list[float]) -> list[float]:
    return [float(value) for value in values if math.isfinite(float(value)) and value >= 0]


def evaluate_amount(
    amount: float,
    comparison_amounts: list[float],
    category: str,
    *,
    min_comparisons: int = ANOMALY_MIN_COMPARISONS,
    mad_multiplier: float = ANOMALY_MAD_MULTIPLIER,
    mad_scale: float = ANOMALY_MAD_SCALE,
    fallback_multiplier: float = ANOMALY_FALLBACK_MULTIPLIER,
) -> AnomalyResult:
    """Evaluasi satu nominal terhadap baseline kategori yang sama."""

    values = _comparison_values(comparison_amounts)
    count = len(values)
    median = round(float(statistics.median(values)), 2) if values else None

    if count < min_comparisons:
        return AnomalyResult(
            transaction_id=None,
            transaction_date=None,
            description="",
            category=category,
            amount=amount,
            status="insufficient",
            threshold=None,
            comparison_count=count,
            median=median,
            mad=None,
            reason=(
                f"Belum cukup data: {count} transaksi pembanding pada kategori "
                f"{category} (minimal {min_comparisons})."
            ),
        )

    assert median is not None
    deviations = [abs(value - median) for value in values]
    mad = round(float(statistics.median(deviations)), 2)

    if mad > 0:
        threshold = round(median + mad_multiplier * mad_scale * mad, 2)
        is_unusual = amount > threshold
        method = "median + 3 x 1,4826 x MAD"
    elif median > 0:
        threshold = round(fallback_multiplier * median, 2)
        is_unusual = amount > threshold
        method = "fallback 2,5 x median (MAD nol)"
    else:
        return AnomalyResult(
            transaction_id=None,
            transaction_date=None,
            description="",
            category=category,
            amount=amount,
            status="not_informative",
            threshold=None,
            comparison_count=count,
            median=median,
            mad=mad,
            reason=(
                f"Baseline kategori {category} belum informatif karena median dan MAD "
                "sama-sama nol."
            ),
        )

    if is_unusual:
        reason = (
            f"{format_rupiah(amount)} lebih tinggi dari baseline kategori {category} "
            f"(median {format_rupiah(median)}; {count} transaksi pembanding; {method})."
        )
        status = "unusual"
    else:
        reason = (
            f"Masih dalam rentang wajar kategori {category} "
            f"(median {format_rupiah(median)}; ambang {format_rupiah(threshold)}; "
            f"{count} transaksi pembanding)."
        )
        status = "normal"

    return AnomalyResult(
        transaction_id=None,
        transaction_date=None,
        description="",
        category=category,
        amount=amount,
        status=status,
        threshold=threshold,
        comparison_count=count,
        median=median,
        mad=mad,
        reason=reason,
    )


def detect_anomalies(
    frame: pd.DataFrame,
    *,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    lookback_days: int = ANOMALY_LOOKBACK_DAYS,
    min_comparisons: int = ANOMALY_MIN_COMPARISONS,
) -> list[AnomalyResult]:
    """Evaluasi transaksi pengeluaran dalam rentang, dengan baseline 180 hari.

    Baseline hanya memakai transaksi bertanggal lebih awal pada kategori yang sama.
    Transaksi yang dievaluasi tidak pernah masuk hitungan baseline-nya sendiri.
    """

    if frame.empty:
        return []
    data = frame.copy()
    data["transaction_date"] = pd.to_datetime(data["transaction_date"], errors="coerce", format="mixed")
    data["amount"] = pd.to_numeric(data["amount"], errors="coerce")
    data = data[
        data["transaction_date"].notna()
        & data["amount"].notna()
        & (data["amount"].astype(float) >= 0)
        & (data["transaction_type"] == "expense")
    ].copy()
    if data.empty:
        return []

    start = pd.Timestamp(start_date).date() if start_date is not None else None
    end = pd.Timestamp(end_date).date() if end_date is not None else None

    results: list[AnomalyResult] = []
    data["_day"] = data["transaction_date"].dt.date
    for category, group in data.groupby("category", sort=False):
        ordered = group.sort_values(["_day", "id"], kind="stable")
        window: deque[tuple[date, float]] = deque()
        for _, row in ordered.iterrows():
            current_day = row["_day"]
            cutoff = current_day - timedelta(days=lookback_days)
            while window and window[0][0] < cutoff:
                window.popleft()
            in_range = (start is None or current_day >= start) and (
                end is None or current_day <= end
            )
            if in_range:
                comparisons = [value for day, value in window if day < current_day]
                evaluation = evaluate_amount(
                    float(row["amount"]),
                    comparisons,
                    str(category),
                    min_comparisons=min_comparisons,
                )
                transaction_id: int | None
                raw_id = row.get("id")
                try:
                    transaction_id = int(raw_id) if pd.notna(raw_id) else None
                except (TypeError, ValueError):
                    transaction_id = None
                results.append(
                    AnomalyResult(
                        transaction_id=transaction_id,
                        transaction_date=current_day,
                        description=str(row.get("description", "")),
                        category=str(category),
                        amount=float(row["amount"]),
                        status=evaluation.status,
                        threshold=evaluation.threshold,
                        comparison_count=evaluation.comparison_count,
                        median=evaluation.median,
                        mad=evaluation.mad,
                        reason=evaluation.reason,
                    )
                )
            window.append((current_day, float(row["amount"])))

    results.sort(
        key=lambda item: (
            item.transaction_date or date.min,
            item.amount,
        ),
        reverse=True,
    )
    return results


def summarize_statuses(results: list[AnomalyResult]) -> dict[str, int]:
    summary = {"unusual": 0, "normal": 0, "insufficient": 0, "not_informative": 0}
    for result in results:
        summary[result.status] = summary.get(result.status, 0) + 1
    return summary
