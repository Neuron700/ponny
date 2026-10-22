"""Koneksi SQLite, skema, dan repository data PennyPilot."""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pennypilot.config import (
    CATEGORY_SOURCES,
    DEFAULT_CATEGORIES,
    DEFAULT_CATEGORY_RULES,
    TRANSACTION_TYPES,
    get_db_path,
)
from pennypilot.models import (
    Budget,
    CategoryRule,
    TransactionRecord,
    row_to_dict,
)
from pennypilot.utils import DomainError, make_fingerprint, month_key, round_money

SCHEMA_VERSION = "1"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount >= 0),
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('expense', 'income')),
    category TEXT NOT NULL,
    category_source TEXT NOT NULL CHECK (
        category_source IN ('csv', 'rule', 'manual', 'default')
    ),
    fingerprint TEXT NOT NULL,
    source_file TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_transactions_fingerprint ON transactions(fingerprint);

CREATE TABLE IF NOT EXISTS category_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    category TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rules_category ON category_rules(category);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    category TEXT,
    amount REAL NOT NULL CHECK (amount >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_budgets_month_category
    ON budgets(month, IFNULL(category, '__total__'));

CREATE TABLE IF NOT EXISTS app_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_RULE_SEED_FLAG = "default_rules_seeded"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Buka koneksi SQLite dan siapkan direktori database bila perlu."""

    path_value = str(db_path) if db_path is not None else str(get_db_path())
    if path_value != ":memory:":
        path = Path(path_value).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path_value = str(path)
    connection = sqlite3.connect(path_value, timeout=30, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    if path_value != ":memory:":
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    """Buat skema dan seed aturan bawaan secara idempoten."""

    connection.executescript(SCHEMA_SQL)
    with connection:
        connection.execute(
            "INSERT OR IGNORE INTO app_metadata(key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        seeded = connection.execute(
            "SELECT value FROM app_metadata WHERE key = ?", (_RULE_SEED_FLAG,)
        ).fetchone()
        if seeded is None:
            count = connection.execute("SELECT COUNT(*) FROM category_rules").fetchone()[0]
            if count == 0:
                now = _now()
                connection.executemany(
                    """
                    INSERT INTO category_rules(keyword, category, enabled, priority, created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?, ?)
                    """,
                    [
                        (keyword, category, priority, now, now)
                        for keyword, category, priority in DEFAULT_CATEGORY_RULES
                    ],
                )
            connection.execute(
                "INSERT INTO app_metadata(key, value) VALUES (?, '1')", (_RULE_SEED_FLAG,)
            )


def get_metadata(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute("SELECT value FROM app_metadata WHERE key = ?", (key,)).fetchone()
    return None if row is None else str(row["value"])


def _validate_record(record: TransactionRecord) -> None:
    if not record.description.strip():
        raise DomainError("Deskripsi transaksi tidak boleh kosong.")
    if record.transaction_type not in TRANSACTION_TYPES:
        raise DomainError("Tipe transaksi tidak valid.")
    if record.category_source not in CATEGORY_SOURCES:
        raise DomainError("Sumber kategori tidak valid.")
    if not record.category.strip():
        raise DomainError("Kategori tidak boleh kosong.")
    if not math.isfinite(record.amount) or record.amount < 0:
        raise DomainError("Nominal transaksi harus angka non-negatif.")
    if not record.fingerprint:
        raise DomainError("Fingerprint transaksi tidak boleh kosong.")


def insert_transactions(
    connection: sqlite3.Connection,
    records: Iterable[TransactionRecord],
) -> int:
    """Simpan banyak transaksi dalam satu transaksi database."""

    now = _now()
    payload: list[tuple[Any, ...]] = []
    for record in records:
        _validate_record(record)
        payload.append(
            (
                record.transaction_date.isoformat(),
                record.description.strip(),
                round_money(record.amount),
                record.transaction_type,
                record.category.strip(),
                record.category_source,
                record.fingerprint,
                record.source_file,
                now,
                now,
            )
        )
    if not payload:
        return 0
    with connection:
        connection.executemany(
            """
            INSERT INTO transactions(
                transaction_date, description, amount, transaction_type, category,
                category_source, fingerprint, source_file, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
    return len(payload)


def get_existing_fingerprints(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT DISTINCT fingerprint FROM transactions").fetchall()
    return {str(row["fingerprint"]) for row in rows}


def _transaction_filters(
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    categories: Sequence[str] | None = None,
    transaction_type: str | None = None,
    search: str | None = None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if start_date is not None:
        clauses.append("transaction_date >= ?")
        params.append(start_date.isoformat() if isinstance(start_date, date) else str(start_date))
    if end_date is not None:
        clauses.append("transaction_date <= ?")
        params.append(end_date.isoformat() if isinstance(end_date, date) else str(end_date))
    if categories:
        placeholders = ", ".join("?" for _ in categories)
        clauses.append(f"category IN ({placeholders})")
        params.extend(categories)
    if transaction_type:
        clauses.append("transaction_type = ?")
        params.append(transaction_type)
    if search and search.strip():
        clauses.append("LOWER(description) LIKE ?")
        params.append(f"%{search.strip().lower()}%")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def list_transactions(
    connection: sqlite3.Connection,
    *,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    categories: Sequence[str] | None = None,
    transaction_type: str | None = None,
    search: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[sqlite3.Row]:
    where, params = _transaction_filters(
        start_date, end_date, categories, transaction_type, search
    )
    sql = (
        "SELECT * FROM transactions"
        f"{where} ORDER BY transaction_date DESC, id DESC"
    )
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([max(0, int(limit)), max(0, int(offset))])
    return connection.execute(sql, params).fetchall()


def count_transactions(
    connection: sqlite3.Connection,
    *,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    categories: Sequence[str] | None = None,
    transaction_type: str | None = None,
    search: str | None = None,
) -> int:
    where, params = _transaction_filters(
        start_date, end_date, categories, transaction_type, search
    )
    row = connection.execute(f"SELECT COUNT(*) AS n FROM transactions{where}", params).fetchone()
    return int(row["n"])


def get_transaction(connection: sqlite3.Connection, transaction_id: int) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM transactions WHERE id = ?", (int(transaction_id),)
    ).fetchone()


def update_transaction(
    connection: sqlite3.Connection,
    transaction_id: int,
    *,
    transaction_date: date,
    description: str,
    amount: float,
    transaction_type: str,
    category: str,
    category_source: str = "manual",
) -> bool:
    """Perbarui transaksi; kategori hasil edit dianggap manual."""

    record = TransactionRecord(
        transaction_date=transaction_date,
        description=description,
        amount=amount,
        transaction_type=transaction_type,
        category=category,
        category_source=category_source,
        fingerprint="pending-validation",
        source_file=None,
    )
    _validate_record(record)
    fingerprint = make_fingerprint(
        transaction_date, description.strip(), amount, transaction_type
    )
    with connection:
        cursor = connection.execute(
            """
            UPDATE transactions
            SET transaction_date = ?, description = ?, amount = ?, transaction_type = ?,
                category = ?, category_source = ?, fingerprint = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                transaction_date.isoformat(),
                description.strip(),
                round_money(amount),
                transaction_type,
                category.strip(),
                category_source,
                fingerprint,
                _now(),
                int(transaction_id),
            ),
        )
    return cursor.rowcount > 0


def delete_transaction(connection: sqlite3.Connection, transaction_id: int) -> bool:
    with connection:
        cursor = connection.execute("DELETE FROM transactions WHERE id = ?", (int(transaction_id),))
    return cursor.rowcount > 0


def delete_all_transactions(connection: sqlite3.Connection) -> int:
    with connection:
        cursor = connection.execute("DELETE FROM transactions")
    return cursor.rowcount


def backup_database_bytes(connection: sqlite3.Connection) -> bytes:
    """Buat snapshot SQLite yang konsisten, termasuk isi WAL yang belum checkpoint."""

    destination = sqlite3.connect(":memory:")
    try:
        connection.backup(destination)
        return destination.serialize()
    finally:
        destination.close()


def get_available_months(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        """
        SELECT DISTINCT substr(transaction_date, 1, 7) AS month
        FROM transactions
        ORDER BY month DESC
        """
    ).fetchall()
    return [str(row["month"]) for row in rows]


def get_date_bounds(connection: sqlite3.Connection) -> tuple[date, date] | None:
    row = connection.execute(
        "SELECT MIN(transaction_date) AS min_date, MAX(transaction_date) AS max_date FROM transactions"
    ).fetchone()
    if row is None or row["min_date"] is None:
        return None
    return date.fromisoformat(row["min_date"]), date.fromisoformat(row["max_date"])


def list_category_rules(connection: sqlite3.Connection) -> list[CategoryRule]:
    rows = connection.execute(
        "SELECT * FROM category_rules ORDER BY keyword COLLATE NOCASE, id"
    ).fetchall()
    return [
        CategoryRule(
            id=int(row["id"]),
            keyword=str(row["keyword"]),
            category=str(row["category"]),
            enabled=bool(row["enabled"]),
            priority=int(row["priority"]),
        )
        for row in rows
    ]


def get_enabled_rules(connection: sqlite3.Connection) -> list[CategoryRule]:
    return [rule for rule in list_category_rules(connection) if rule.enabled]


def _validate_rule(keyword: str, category: str, priority: int) -> tuple[str, str, int]:
    cleaned_keyword = " ".join(str(keyword).split())
    if not cleaned_keyword:
        raise DomainError("Kata kunci aturan tidak boleh kosong.")
    if len(cleaned_keyword) > 100:
        raise DomainError("Kata kunci aturan maksimal 100 karakter.")
    if category not in DEFAULT_CATEGORIES:
        raise DomainError("Kategori aturan tidak dikenal.")
    try:
        priority_value = int(priority)
    except (TypeError, ValueError) as exc:
        raise DomainError("Prioritas aturan harus bilangan bulat.") from exc
    return cleaned_keyword, category, priority_value


def add_category_rule(
    connection: sqlite3.Connection,
    keyword: str,
    category: str,
    priority: int = 0,
    enabled: bool = True,
) -> int:
    keyword, category, priority = _validate_rule(keyword, category, priority)
    now = _now()
    with connection:
        cursor = connection.execute(
            """
            INSERT INTO category_rules(keyword, category, enabled, priority, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (keyword, category, int(enabled), priority, now, now),
        )
    return int(cursor.lastrowid)


def update_category_rule(
    connection: sqlite3.Connection,
    rule_id: int,
    *,
    keyword: str,
    category: str,
    priority: int,
    enabled: bool,
) -> bool:
    keyword, category, priority = _validate_rule(keyword, category, priority)
    with connection:
        cursor = connection.execute(
            """
            UPDATE category_rules
            SET keyword = ?, category = ?, priority = ?, enabled = ?, updated_at = ?
            WHERE id = ?
            """,
            (keyword, category, priority, int(enabled), _now(), int(rule_id)),
        )
    return cursor.rowcount > 0


def delete_category_rule(connection: sqlite3.Connection, rule_id: int) -> bool:
    with connection:
        cursor = connection.execute("DELETE FROM category_rules WHERE id = ?", (int(rule_id),))
    return cursor.rowcount > 0


def get_budgets(connection: sqlite3.Connection, month: str) -> list[Budget]:
    month_value = month_key(month)
    rows = connection.execute(
        "SELECT * FROM budgets WHERE month = ? ORDER BY category IS NOT NULL, category",
        (month_value,),
    ).fetchall()
    return [
        Budget(
            id=int(row["id"]),
            month=str(row["month"]),
            category=row["category"],
            amount=float(row["amount"]),
        )
        for row in rows
    ]


def get_budget_map(connection: sqlite3.Connection, month: str) -> dict[str | None, float]:
    return {budget.category: budget.amount for budget in get_budgets(connection, month)}


def upsert_budget(
    connection: sqlite3.Connection,
    month: str,
    amount: float | None,
    category: str | None = None,
) -> None:
    """Simpan anggaran; ``None`` menghapus anggaran untuk bulan/kategori itu."""

    month_value = month_key(month)
    if amount is None:
        with connection:
            connection.execute(
                "DELETE FROM budgets WHERE month = ? AND IFNULL(category, '__total__') = IFNULL(?, '__total__')",
                (month_value, category),
            )
        return
    if not math.isfinite(amount) or amount < 0:
        raise DomainError("Anggaran harus angka non-negatif.")
    category_value = category if category else None
    if category_value is not None and category_value not in DEFAULT_CATEGORIES:
        raise DomainError("Kategori anggaran tidak dikenal.")
    now = _now()
    amount_value = round_money(amount)
    with connection:
        cursor = connection.execute(
            """
            UPDATE budgets SET amount = ?, updated_at = ?
            WHERE month = ? AND IFNULL(category, '__total__') = IFNULL(?, '__total__')
            """,
            (amount_value, now, month_value, category_value),
        )
        if cursor.rowcount == 0:
            connection.execute(
                """
                INSERT INTO budgets(month, category, amount, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (month_value, category_value, amount_value, now, now),
            )


def save_budgets(
    connection: sqlite3.Connection,
    month: str,
    total: float | None,
    categories: dict[str, float | None],
) -> None:
    """Simpan anggaran total dan per kategori dalam satu transaksi."""

    month_value = month_key(month)
    if total is not None and (not math.isfinite(total) or total < 0):
        raise DomainError("Anggaran total harus angka non-negatif.")
    for category, amount in categories.items():
        if category not in DEFAULT_CATEGORIES:
            raise DomainError("Kategori anggaran tidak dikenal.")
        if amount is not None and (not math.isfinite(amount) or amount < 0):
            raise DomainError("Anggaran kategori harus angka non-negatif.")
    now = _now()
    with connection:
        connection.execute(
            "DELETE FROM budgets WHERE month = ?", (month_value,)
        )
        rows: list[tuple[Any, ...]] = []
        if total is not None:
            rows.append((month_value, None, round_money(total), now, now))
        for category, amount in categories.items():
            if amount is not None:
                rows.append((month_value, category, round_money(amount), now, now))
        if rows:
            connection.executemany(
                """
                INSERT INTO budgets(month, category, amount, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )


def update_transaction_category(
    connection: sqlite3.Connection,
    transaction_id: int,
    category: str,
    category_source: str,
) -> bool:
    if category not in DEFAULT_CATEGORIES:
        raise DomainError("Kategori tidak dikenal.")
    if category_source not in CATEGORY_SOURCES:
        raise DomainError("Sumber kategori tidak valid.")
    with connection:
        cursor = connection.execute(
            "UPDATE transactions SET category = ?, category_source = ?, updated_at = ? WHERE id = ?",
            (category, category_source, _now(), int(transaction_id)),
        )
    return cursor.rowcount > 0


def fetch_transactions_as_dicts(
    connection: sqlite3.Connection,
    *,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
) -> list[dict[str, Any]]:
    rows = list_transactions(connection, start_date=start_date, end_date=end_date)
    return [row_to_dict(row) for row in rows]
