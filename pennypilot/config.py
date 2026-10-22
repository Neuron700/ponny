"""Konfigurasi aplikasi dan batas-batas impor."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "PennyPilot"
APP_VERSION = "0.1.0"
DB_PATH_ENV = "PENNYPILOT_DB_PATH"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DATA_PATH = Path(__file__).resolve().parent / "sample_data" / "sample_transactions.csv"

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 50_000
PREVIEW_ROWS = 20

DEFAULT_DB_PATH = Path.home() / ".pennypilot" / "pennypilot.db"

DEFAULT_CATEGORIES: tuple[str, ...] = (
    "Makanan",
    "Transportasi",
    "Belanja",
    "Tagihan",
    "Kesehatan",
    "Hiburan",
    "Pendidikan",
    "Pendapatan",
    "Transfer",
    "Lainnya",
)

EXPENSE_FALLBACK = "Lainnya"
INCOME_FALLBACK = "Pendapatan"

CATEGORY_SOURCES = ("csv", "rule", "manual", "default")
TRANSACTION_TYPES = ("expense", "income")

# (keyword, kategori, prioritas). Urutan pencocokan: keyword terpanjang,
# lalu prioritas terbesar, lalu id aturan terkecil.
DEFAULT_CATEGORY_RULES: tuple[tuple[str, str, int], ...] = (
    ("indomaret", "Belanja", 0),
    ("alfamart", "Belanja", 0),
    ("supermarket", "Belanja", 0),
    ("grab", "Transportasi", 0),
    ("gojek", "Transportasi", 0),
    ("transjakarta", "Transportasi", 0),
    ("pertamina", "Transportasi", 0),
    ("pln", "Tagihan", 0),
    ("telkom", "Tagihan", 0),
    ("listrik", "Tagihan", 0),
    ("internet", "Tagihan", 0),
    ("air", "Tagihan", 0),
    ("apotek", "Kesehatan", 0),
    ("klinik", "Kesehatan", 0),
    ("rumah sakit", "Kesehatan", 0),
    ("bioskop", "Hiburan", 0),
    ("netflix", "Hiburan", 0),
    ("spotify", "Hiburan", 0),
    ("buku", "Pendidikan", 0),
    ("kursus", "Pendidikan", 0),
    ("sekolah", "Pendidikan", 0),
    ("restoran", "Makanan", 0),
    ("warung", "Makanan", 0),
    ("kafe", "Makanan", 0),
    ("makan", "Makanan", 0),
    ("gaji", "Pendapatan", 0),
    ("bonus", "Pendapatan", 0),
    ("salary", "Pendapatan", 0),
    ("transfer", "Transfer", 0),
)

TYPE_LABELS = {"expense": "Pengeluaran", "income": "Pendapatan"}
SOURCE_LABELS = {
    "csv": "Dari CSV",
    "rule": "Aturan kata kunci",
    "manual": "Manual",
    "default": "Default",
}

AMOUNT_MODES = {
    "signed": "Nominal bertanda (negatif = pengeluaran, positif = pendapatan)",
    "absolute_with_type": "Nominal absolut + kolom tipe transaksi",
    "all_expense": "Semua baris dianggap pengeluaran",
}

DATE_FORMAT_OPTIONS: dict[str, str | None] = {
    "Deteksi otomatis": None,
    "ISO (YYYY-MM-DD)": "%Y-%m-%d",
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "DD-MM-YYYY": "%d-%m-%Y",
    "MM-DD-YYYY": "%m-%d-%Y",
    "YYYY/MM/DD": "%Y/%m/%d",
    "DD.MM.YYYY": "%d.%m.%Y",
    "MM.DD.YYYY": "%m.%d.%Y",
    "DD Mon YYYY": "%d %b %Y",
}

AUTO_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%d.%m.%Y",
    "%d %b %Y",
    "%d-%b-%Y",
    "%d %B %Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)

DELIMITER_OPTIONS: dict[str, str | None] = {
    "Deteksi otomatis": None,
    "Koma (,)": ",",
    "Titik koma (;)": ";",
    "Tab": "\t",
    "Pipa (|)": "|",
}

ENCODING_OPTIONS: tuple[str, ...] = (
    "Deteksi otomatis",
    "utf-8-sig",
    "utf-8",
    "cp1252",
    "latin-1",
)

ANOMALY_LOOKBACK_DAYS = 180
ANOMALY_MIN_COMPARISONS = 5
ANOMALY_MAD_MULTIPLIER = 3.0
ANOMALY_MAD_SCALE = 1.4826
ANOMALY_FALLBACK_MULTIPLIER = 2.5
BUDGET_SUGGESTION_MONTHS = 3


def get_db_path() -> Path:
    """Lokasi database; bisa dioverride lewat variabel lingkungan."""

    raw = os.environ.get(DB_PATH_ENV)
    if raw:
        return Path(raw).expanduser()
    return DEFAULT_DB_PATH
