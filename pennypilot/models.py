"""Tipe data domain yang dipakai lintas service dan UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class TransactionRecord:
    """Satu transaksi siap disimpan (nominal selalu non-negatif)."""

    transaction_date: date
    description: str
    amount: float
    transaction_type: str
    category: str
    category_source: str
    fingerprint: str
    source_file: str | None = None


@dataclass(frozen=True)
class CategoryRule:
    id: int | None
    keyword: str
    category: str
    enabled: bool = True
    priority: int = 0


@dataclass(frozen=True)
class Budget:
    id: int | None
    month: str
    category: str | None
    amount: float


@dataclass(frozen=True)
class ImportIssue:
    row_number: int
    field: str
    message: str


@dataclass
class ImportRow:
    """Baris valid hasil analisis CSV, sebelum disimpan."""

    row_number: int
    transaction: TransactionRecord
    is_duplicate: bool = False
    duplicate_reason: str = ""


@dataclass
class ImportAnalysis:
    rows: list[ImportRow] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)
    total_rows: int = 0
    source_file: str = ""
    encoding: str = "utf-8"
    delimiter: str = ","
    warnings: list[str] = field(default_factory=list)
    ambiguous_dates: bool = False

    @property
    def valid_count(self) -> int:
        return len(self.rows)

    @property
    def invalid_count(self) -> int:
        return len(self.issues)

    @property
    def duplicate_count(self) -> int:
        return sum(1 for row in self.rows if row.is_duplicate)

    @property
    def ready_count(self) -> int:
        return sum(1 for row in self.rows if not row.is_duplicate)

    @property
    def invalid_row_count(self) -> int:
        return len({issue.row_number for issue in self.issues})

    def rows_to_import(self, include_duplicates: bool = False) -> list[ImportRow]:
        if include_duplicates:
            return list(self.rows)
        return [row for row in self.rows if not row.is_duplicate]


@dataclass(frozen=True)
class AnomalyResult:
    transaction_id: int | None
    transaction_date: date | None
    description: str
    category: str
    amount: float
    status: str
    threshold: float | None
    comparison_count: int
    median: float | None
    mad: float | None
    reason: str

    @property
    def is_unusual(self) -> bool:
        return self.status == "unusual"


@dataclass(frozen=True)
class ProjectionResult:
    available: bool
    projected: float | None
    status: str
    days_elapsed: int
    days_in_month: int
    note: str


@dataclass(frozen=True)
class BudgetUsage:
    actual: float
    budget: float | None
    percentage: float | None
    remaining: float | None
    is_over: bool
    status: str


@dataclass
class SuggestionResult:
    available: bool
    suggestions: dict[str, float] = field(default_factory=dict)
    total_suggestion: float | None = None
    months_used: list[str] = field(default_factory=list)
    note: str = ""


def row_to_dict(row: Any) -> dict[str, Any]:
    """Konversi sqlite3.Row atau mapping ke dict biasa."""

    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)
