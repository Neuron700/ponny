from __future__ import annotations

from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pennypilot import db
from pennypilot.models import TransactionRecord
from pennypilot.utils import make_fingerprint

APP_PATH = Path(__file__).resolve().parent.parent / "pennypilot" / "app.py"
PAGES = [
    "Dashboard",
    "Transaksi",
    "Impor CSV",
    "Anggaran",
    "Kategori & Aturan",
    "Pengaturan & Tentang",
]


def _button(at, label: str):
    return next(button for button in at.button if button.label == label)


def _load_demo(at) -> None:
    _button(at, "Muat dataset demo").click().run()
    assert not at.exception


def test_app_pages_run_with_demo_data(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYPILOT_DB_PATH", str(tmp_path / "app.db"))
    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    assert not at.exception
    _load_demo(at)

    assert any(metric.label == "Pendapatan" for metric in at.metric)
    for page in PAGES:
        at.radio[0].set_value(page).run()
        assert not at.exception, f"Halaman {page} gagal: {[e.value for e in at.exception]}"


def test_budget_page_saves_total(tmp_path, monkeypatch):
    path = tmp_path / "budget.db"
    monkeypatch.setenv("PENNYPILOT_DB_PATH", str(path))
    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    _load_demo(at)
    at.radio[0].set_value("Anggaran").run()
    at.toggle[0].set_value(True).run()
    at.number_input[0].set_value(1_000_000.0).run()
    _button(at, "Simpan anggaran").click().run()
    assert not at.exception

    conn = db.connect(path)
    try:
        current_month = date.today().strftime("%Y-%m")
        assert db.get_budget_map(conn, current_month)[None] == 1_000_000
    finally:
        conn.close()


def test_rules_page_adds_rule(tmp_path, monkeypatch):
    path = tmp_path / "rules.db"
    monkeypatch.setenv("PENNYPILOT_DB_PATH", str(path))
    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    at.radio[0].set_value("Kategori & Aturan").run()
    at.text_input[0].set_value("kedai baru")
    at.selectbox[0].set_value("Makanan")
    _button(at, "Tambah aturan").click().run()
    assert not at.exception

    conn = db.connect(path)
    try:
        assert any(rule.keyword == "kedai baru" for rule in db.list_category_rules(conn))
    finally:
        conn.close()


def test_add_manual_transaction_from_empty_database(tmp_path, monkeypatch):
    path = tmp_path / "manual.db"
    monkeypatch.setenv("PENNYPILOT_DB_PATH", str(path))
    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    at.radio[0].set_value("Transaksi").run()
    at.text_input[0].set_value("Makan siang manual")
    at.number_input[0].set_value(30_000.0)
    _button(at, "Tambah transaksi").click().run()
    assert not at.exception

    conn = db.connect(path)
    try:
        rows = db.list_transactions(conn)
        assert len(rows) == 1
        assert rows[0]["description"] == "Makan siang manual"
        assert rows[0]["category_source"] == "manual"
    finally:
        conn.close()


def test_edit_form_refreshes_when_selection_changes(tmp_path, monkeypatch):
    path = tmp_path / "edit.db"
    monkeypatch.setenv("PENNYPILOT_DB_PATH", str(path))
    conn = db.connect(path)
    db.init_db(conn)
    records = []
    for description, amount in (("Transaksi pertama", 10_000.0), ("Transaksi kedua", 20_000.0)):
        records.append(
            TransactionRecord(
                transaction_date=date(2026, 10, 1),
                description=description,
                amount=amount,
                transaction_type="expense",
                category="Makanan",
                category_source="manual",
                fingerprint=make_fingerprint(date(2026, 10, 1), description, amount, "expense"),
            )
        )
    db.insert_transactions(conn, records)
    rows = db.list_transactions(conn)
    second_id = int(rows[0]["id"])
    conn.close()

    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    at.radio[0].set_value("Transaksi").run()
    selector = next(box for box in at.selectbox if box.label == "Pilih transaksi")
    selector.set_value(second_id).run()

    description_fields = [field for field in at.text_input if field.label == "Deskripsi"]
    assert description_fields[-1].value == "Transaksi kedua"
    description_fields[-1].set_value("Transaksi kedua diubah")
    _button(at, "Simpan perubahan").click().run()
    assert not at.exception

    conn = db.connect(path)
    try:
        updated = next(row for row in db.list_transactions(conn) if int(row["id"]) == second_id)
        assert updated["description"] == "Transaksi kedua diubah"
    finally:
        conn.close()
