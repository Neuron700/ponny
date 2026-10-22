from __future__ import annotations

import sqlite3
from datetime import date

from pennypilot import db
from pennypilot.models import TransactionRecord
from pennypilot.utils import DomainError, make_fingerprint


def make_record(
    day: date,
    description: str,
    amount: float,
    transaction_type: str = "expense",
    category: str = "Makanan",
) -> TransactionRecord:
    return TransactionRecord(
        transaction_date=day,
        description=description,
        amount=amount,
        transaction_type=transaction_type,
        category=category,
        category_source="rule",
        fingerprint=make_fingerprint(day, description, amount, transaction_type),
    )


def test_backup_database_bytes_restores_consistent_snapshot(connection):
    db.insert_transactions(
        connection,
        [make_record(date(2026, 3, 1), "Kopi", 25_000)],
    )
    backup = db.backup_database_bytes(connection)
    assert backup.startswith(b"SQLite format 3\x00")

    restored = sqlite3.connect(":memory:")
    restored.row_factory = sqlite3.Row
    try:
        restored.deserialize(backup)
        assert restored.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1
        assert restored.execute("SELECT COUNT(*) FROM category_rules").fetchone()[0] >= 10
    finally:
        restored.close()


def test_init_is_idempotent_and_seeds_once(connection):
    count = len(db.list_category_rules(connection))
    assert count >= 10
    db.init_db(connection)
    assert len(db.list_category_rules(connection)) == count

    for rule in db.list_category_rules(connection):
        db.delete_category_rule(connection, rule.id)
    assert db.list_category_rules(connection) == []
    db.init_db(connection)
    assert db.list_category_rules(connection) == []


def test_insert_fetch_filter_and_bounds(connection):
    records = [
        make_record(date(2026, 1, 5), "Kopi", 25_000, "expense", "Makanan"),
        make_record(date(2026, 2, 5), "Gaji", 5_000_000, "income", "Pendapatan"),
        make_record(date(2026, 2, 6), "Belanja", 300_000, "expense", "Belanja"),
    ]
    assert db.insert_transactions(connection, records) == 3
    assert db.count_transactions(connection) == 3
    assert db.count_transactions(connection, transaction_type="expense") == 2
    assert db.count_transactions(connection, categories=["Belanja"]) == 1
    assert db.count_transactions(connection, search="kopi") == 1
    assert len(db.list_transactions(connection, start_date=date(2026, 2, 1))) == 2
    assert db.get_date_bounds(connection) == (date(2026, 1, 5), date(2026, 2, 6))
    assert db.get_available_months(connection) == ["2026-02", "2026-01"]


def test_search_query_is_parameterized(connection):
    db.insert_transactions(
        connection, [make_record(date(2026, 1, 5), "Kopi", 25_000)]
    )
    assert db.count_transactions(connection, search="' OR 1=1 --") == 0
    assert db.count_transactions(connection) == 1


def test_update_and_delete(connection):
    db.insert_transactions(connection, [make_record(date(2026, 1, 5), "Kopi", 25_000)])
    row = db.list_transactions(connection)[0]
    updated = db.update_transaction(
        connection,
        int(row["id"]),
        transaction_date=date(2026, 1, 6),
        description="Kopi susu",
        amount=30_000,
        transaction_type="expense",
        category="Hiburan",
    )
    assert updated is True
    changed = db.get_transaction(connection, int(row["id"]))
    assert changed["description"] == "Kopi susu"
    assert changed["amount"] == 30_000
    assert changed["category"] == "Hiburan"
    assert changed["category_source"] == "manual"
    assert changed["transaction_date"] == "2026-01-06"
    assert changed["fingerprint"] == make_fingerprint(
        date(2026, 1, 6), "Kopi susu", 30_000, "expense"
    )

    assert db.delete_transaction(connection, int(row["id"])) is True
    assert db.get_transaction(connection, int(row["id"])) is None


def test_manual_category_persists_after_reconnect(tmp_path):
    path = tmp_path / "nested" / "pennypilot.db"
    conn = db.connect(path)
    db.init_db(conn)
    db.insert_transactions(conn, [make_record(date(2026, 1, 5), "Kopi", 25_000)])
    row = db.list_transactions(conn)[0]
    db.update_transaction(
        conn,
        int(row["id"]),
        transaction_date=date(2026, 1, 5),
        description="Kopi",
        amount=25_000,
        transaction_type="expense",
        category="Hiburan",
    )
    conn.close()

    reopened = db.connect(path)
    try:
        db.init_db(reopened)
        saved = db.list_transactions(reopened)[0]
        assert saved["category"] == "Hiburan"
        assert saved["category_source"] == "manual"
    finally:
        reopened.close()


def test_invalid_record_rejected(connection):
    bad = TransactionRecord(
        transaction_date=date(2026, 1, 1),
        description="",
        amount=-1,
        transaction_type="expense",
        category="Lainnya",
        category_source="manual",
        fingerprint="x",
    )
    try:
        db.insert_transactions(connection, [bad])
    except DomainError:
        pass
    else:
        raise AssertionError("Transaksi tidak valid seharusnya ditolak")


def test_budget_upsert_and_delete(connection):
    db.upsert_budget(connection, "2026-04", 5_000_000)
    db.upsert_budget(connection, "2026-04", 6_000_000)
    db.upsert_budget(connection, "2026-04", 1_500_000, "Makanan")
    db.upsert_budget(connection, "2026-04", 1_200_000, "Makanan")

    budgets = db.get_budget_map(connection, "2026-04")
    assert budgets[None] == 6_000_000
    assert budgets["Makanan"] == 1_200_000

    db.upsert_budget(connection, "2026-04", None, "Makanan")
    assert "Makanan" not in db.get_budget_map(connection, "2026-04")
    assert db.get_budget_map(connection, "2026-04")[None] == 6_000_000


def test_save_budgets_replaces_month(connection):
    db.save_budgets(connection, "2026-04", 5_000_000, {"Makanan": 1_000_000})
    db.save_budgets(connection, "2026-05", 2_000_000, {"Belanja": 500_000})
    db.save_budgets(connection, "2026-04", None, {"Makanan": None, "Hiburan": 0})
    budgets = db.get_budget_map(connection, "2026-04")
    assert budgets == {"Hiburan": 0.0}
    assert db.get_budget_map(connection, "2026-05")[None] == 2_000_000


def test_rules_crud(connection):
    rule_id = db.add_category_rule(connection, "  kopi   susu ", "Makanan", 3)
    rule = next(rule for rule in db.list_category_rules(connection) if rule.id == rule_id)
    assert rule.keyword == "kopi susu"
    assert rule.priority == 3
    assert rule.enabled is True

    assert db.update_category_rule(
        connection,
        rule_id,
        keyword="teh",
        category="Hiburan",
        priority=1,
        enabled=False,
    )
    changed = next(rule for rule in db.list_category_rules(connection) if rule.id == rule_id)
    assert changed.category == "Hiburan"
    assert changed.enabled is False
    assert all(rule.id != rule_id for rule in db.get_enabled_rules(connection))
    assert db.delete_category_rule(connection, rule_id) is True


def test_fingerprint_is_not_unique_constraint(connection):
    today = date(2026, 1, 1)
    fingerprint = make_fingerprint(today, "Kopi", 25_000, "expense")
    records = [
        TransactionRecord(
            transaction_date=today,
            description="Kopi",
            amount=25_000,
            transaction_type="expense",
            category="Makanan",
            category_source="manual",
            fingerprint=fingerprint,
        )
        for _ in range(2)
    ]
    assert db.insert_transactions(connection, records) == 2
