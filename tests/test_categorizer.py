from __future__ import annotations

from datetime import date

from pennypilot import db
from pennypilot.models import CategoryRule, TransactionRecord
from pennypilot.services.categorizer import (
    canonical_category,
    categorize,
    find_matching_rule,
    recategorize_transactions,
)
from pennypilot.utils import make_fingerprint


def test_case_insensitive_matching_and_longest_keyword_wins():
    rules = [
        CategoryRule(1, "makan", "Makanan"),
        CategoryRule(2, "makan malam", "Hiburan"),
        CategoryRule(3, "makan malam restoran", "Makanan", priority=10),
    ]
    match = find_matching_rule("MAKAN MALAM RESTORAN", rules)
    assert match is not None
    assert match.category == "Makanan"


def test_priority_breaks_equal_length_ties():
    rules = [
        CategoryRule(1, "kopi", "Makanan", priority=0),
        CategoryRule(2, "kopi", "Hiburan", priority=5),
    ]
    match = find_matching_rule("Kopi susu", rules)
    assert match is not None
    assert match.category == "Hiburan"


def test_disabled_rules_are_ignored():
    rules = [CategoryRule(1, "kopi", "Makanan", enabled=False)]
    assert find_matching_rule("Kopi susu", rules) is None


def test_fallback_by_transaction_type():
    assert categorize("Sesuatu", "expense", []) == ("Lainnya", "default")
    assert categorize("Sesuatu", "income", []) == ("Pendapatan", "default")


def test_csv_category_is_kept():
    rules = [CategoryRule(1, "kopi", "Makanan")]
    assert categorize("Kopi", "expense", rules, source_category="hiburan") == (
        "Hiburan",
        "csv",
    )


def test_canonical_category():
    assert canonical_category("  makanan ") == "Makanan"
    assert canonical_category("tidak ada") is None


def _record(description: str, source: str, category: str) -> TransactionRecord:
    return TransactionRecord(
        transaction_date=date(2026, 1, 1),
        description=description,
        amount=1000,
        transaction_type="expense",
        category=category,
        category_source=source,
        fingerprint=make_fingerprint(date(2026, 1, 1), description, 1000, "expense"),
    )


def test_recategorize_protects_manual_and_csv(connection):
    db.add_category_rule(connection, "kopi", "Makanan")
    records = [
        _record("Kopi manual", "manual", "Hiburan"),
        _record("Kopi csv", "csv", "Belanja"),
        _record("Kopi otomatis", "rule", "Lainnya"),
        _record("Kopi default", "default", "Lainnya"),
    ]
    db.insert_transactions(connection, records)

    changed = recategorize_transactions(connection)

    assert changed == 2
    rows = {
        row["description"]: (row["category"], row["category_source"])
        for row in db.list_transactions(connection)
    }
    assert rows["Kopi manual"] == ("Hiburan", "manual")
    assert rows["Kopi csv"] == ("Belanja", "csv")
    assert rows["Kopi otomatis"] == ("Makanan", "rule")
    assert rows["Kopi default"] == ("Makanan", "rule")
