"""Kategorisasi deterministik berbasis aturan kata kunci."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pennypilot.config import (
    DEFAULT_CATEGORIES,
    EXPENSE_FALLBACK,
    INCOME_FALLBACK,
)
from pennypilot.models import CategoryRule
from pennypilot.utils import normalize_description


def canonical_category(value: object) -> str | None:
    """Kembalikan nama kategori baku bila nilai cocok (tanpa peduli huruf)."""

    if value is None:
        return None
    text = str(value).strip().casefold()
    if not text:
        return None
    for category in DEFAULT_CATEGORIES:
        if category.casefold() == text:
            return category
    return None


def find_matching_rule(
    description: str,
    rules: Iterable[CategoryRule],
) -> CategoryRule | None:
    """Pilih aturan paling spesifik.

    Urutan: keyword terpanjang -> prioritas terbesar -> id terkecil.
    Hanya aturan aktif yang dipertimbangkan.
    """

    text = normalize_description(description)
    candidates: list[CategoryRule] = []
    for rule in rules:
        if not rule.enabled:
            continue
        keyword = normalize_description(rule.keyword)
        if keyword and keyword in text:
            candidates.append(rule)
    if not candidates:
        return None
    candidates.sort(
        key=lambda rule: (
            -len(normalize_description(rule.keyword)),
            -int(rule.priority),
            rule.id if rule.id is not None else 0,
        )
    )
    return candidates[0]


def categorize(
    description: str,
    transaction_type: str,
    rules: Iterable[CategoryRule],
    source_category: object = None,
) -> tuple[str, str]:
    """Tentukan kategori dan sumbernya.

    Prioritas: kategori CSV valid -> aturan keyword -> fallback tipe transaksi.
    Kategori manual tidak pernah melewati fungsi ini saat kategorisasi ulang.
    """

    category_from_csv = canonical_category(source_category)
    if category_from_csv is not None:
        return category_from_csv, "csv"

    rule = find_matching_rule(description, rules)
    if rule is not None:
        category = canonical_category(rule.category)
        if category is not None:
            return category, "rule"

    if transaction_type == "income":
        return INCOME_FALLBACK, "default"
    return EXPENSE_FALLBACK, "default"


def recategorize_transactions(connection, rules: list[CategoryRule] | None = None) -> int:
    """Terapkan aturan ke transaksi otomatis; kategori manual/CSV dilindungi."""

    from pennypilot import db

    active_rules = rules if rules is not None else db.get_enabled_rules(connection)
    rows = connection.execute(
        """
        SELECT id, description, transaction_type, category, category_source
        FROM transactions
        WHERE category_source IN ('rule', 'default')
        """
    ).fetchall()
    changes: list[tuple[str, str, str, int]] = []
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    for row in rows:
        category, source = categorize(
            str(row["description"]),
            str(row["transaction_type"]),
            active_rules,
        )
        if category != row["category"] or source != row["category_source"]:
            changes.append((category, source, now, int(row["id"])))
    if changes:
        with connection:
            connection.executemany(
                """
                UPDATE transactions
                SET category = ?, category_source = ?, updated_at = ?
                WHERE id = ?
                """,
                changes,
            )
    return len(changes)
