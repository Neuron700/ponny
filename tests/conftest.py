from __future__ import annotations

from dataclasses import asdict
from datetime import date

import pandas as pd
import pytest

from pennypilot import db
from pennypilot.models import TransactionRecord
from pennypilot.utils import make_fingerprint


@pytest.fixture()
def connection():
    conn = db.connect(":memory:")
    db.init_db(conn)
    yield conn
    conn.close()


def make_record(
    day: date,
    description: str,
    amount: float,
    transaction_type: str = "expense",
    category: str = "Makanan",
    category_source: str = "rule",
) -> TransactionRecord:
    return TransactionRecord(
        transaction_date=day,
        description=description,
        amount=amount,
        transaction_type=transaction_type,
        category=category,
        category_source=category_source,
        fingerprint=make_fingerprint(day, description, amount, transaction_type),
    )


@pytest.fixture()
def expense_frame() -> pd.DataFrame:
    rows = [
        make_record(date(2026, 3, 1), "Makan siang", 50_000, "expense", "Makanan"),
        make_record(date(2026, 3, 5), "Makan malam", 80_000, "expense", "Makanan"),
        make_record(date(2026, 4, 2), "Gaji", 10_000_000, "income", "Pendapatan"),
        make_record(date(2026, 4, 3), "Belanja", 300_000, "expense", "Belanja"),
        make_record(date(2026, 4, 4), "Makan siang", 60_000, "expense", "Makanan"),
    ]
    return pd.DataFrame([asdict(record) for record in rows])
