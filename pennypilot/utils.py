"""Utilitas domain: nominal Rupiah, parsing angka, tanggal, dan fingerprint."""

from __future__ import annotations

import calendar
import hashlib
import math
import re
import unicodedata
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from pennypilot.config import AUTO_DATE_FORMATS

_MONTH_NAMES_ID = (
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
)

_CURRENCY_PREFIX = re.compile(r"^(?:rp\.?|idr)\s*", re.IGNORECASE)


class DomainError(ValueError):
    """Kesalahan input domain dengan pesan yang aman ditampilkan."""


def format_rupiah(value: float | int | Decimal | None, *, fallback: str = "—") -> str:
    """Format angka menjadi Rupiah Indonesia tanpa nilai non-finite."""

    if value is None:
        return fallback
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return fallback
    if not number.is_finite():
        return fallback
    number = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    negative = number < 0
    number = abs(number)
    if number == number.to_integral_value():
        body = f"{int(number):,}".replace(",", ".")
    else:
        body = f"{number:,.2f}".replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")
    return f"{'-' if negative else ''}Rp{body}"


def round_money(value: float | Decimal) -> float:
    """Bulatkan nominal ke dua desimal agar konsisten di SQLite."""

    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DomainError("Nominal tidak valid.") from exc
    if not number.is_finite():
        raise DomainError("Nominal tidak valid.")
    return float(number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_amount(raw: object) -> float:
    """Parse nominal dengan pemisah ribuan/desimal umum.

    Mendukung contoh: ``1.234.567,89``, ``1,234,567.89``, ``Rp 1.234``,
    ``(25.000)``, dan ``-12500``. Nilai yang tidak bisa dipastikan ditolak.
    """

    if raw is None:
        raise DomainError("Nominal kosong.")
    text = str(raw).strip()
    if not text:
        raise DomainError("Nominal kosong.")

    text = text.replace("\u00a0", " ").replace("\u202f", " ").strip()
    text = _CURRENCY_PREFIX.sub("", text)
    text = re.sub(r"\s+", "", text)

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    if text.startswith("-"):
        negative = True
        text = text[1:]
    elif text.startswith("+"):
        text = text[1:]

    text = re.sub(r"[^\d.,]", "", text)
    if not text or not re.search(r"\d", text):
        raise DomainError("Nominal tidak dapat dibaca.")

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        if text.count(",") > 1:
            text = text.replace(",", "")
        else:
            left, right = text.split(",", 1)
            text = f"{left}.{right}" if len(right) in (1, 2) else f"{left}{right}"
    elif "." in text:
        if text.count(".") > 1:
            text = text.replace(".", "")
        else:
            left, right = text.split(".", 1)
            if len(right) == 3:
                text = f"{left}{right}"
            else:
                text = f"{left}.{right}"

    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise DomainError("Nominal tidak dapat dibaca.") from exc
    if not value.is_finite():
        raise DomainError("Nominal tidak valid.")
    if negative:
        value = -value
    return round_money(value)


def parse_transaction_date(raw: object, date_format: str | None = None) -> date:
    """Parse tanggal ISO atau format umum; format eksplisit diutamakan."""

    if raw is None:
        raise DomainError("Tanggal kosong.")
    text = str(raw).strip()
    if not text:
        raise DomainError("Tanggal kosong.")

    formats = (date_format,) if date_format else AUTO_DATE_FORMATS
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except (ValueError, TypeError):
            continue
    if date_format:
        raise DomainError(f"Tanggal '{text}' tidak sesuai format {date_format}.")
    raise DomainError(f"Tanggal '{text}' tidak dikenali.")


def detect_date_ambiguity(values: list[str]) -> bool:
    """Deteksi apakah data dd/mm dan mm/dd sama-sama valid dan berbeda."""

    samples = [value.strip() for value in values if str(value).strip()]
    if not samples:
        return False
    ambiguous = False
    format_pairs = (
        ("%d/%m/%Y", "%m/%d/%Y"),
        ("%d-%m-%Y", "%m-%d-%Y"),
        ("%d.%m.%Y", "%m.%d.%Y"),
    )
    for raw in samples[:200]:
        parsed: set[date] = set()
        for formats in format_pairs:
            for fmt in formats:
                try:
                    parsed.add(datetime.strptime(raw, fmt).date())
                except ValueError:
                    pass
        if len(parsed) > 1:
            ambiguous = True
            break
    return ambiguous


def normalize_description(description: str) -> str:
    """Normalisasi deskripsi untuk pencocokan dan fingerprint."""

    text = unicodedata.normalize("NFKC", str(description)).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def make_fingerprint(
    transaction_date: date | str,
    description: str,
    amount: float,
    transaction_type: str,
) -> str:
    """Fingerprint deterministik tanpa constraint unik di database."""

    day = transaction_date.isoformat() if isinstance(transaction_date, date) else str(transaction_date)
    payload = "|".join(
        (
            day,
            normalize_description(description),
            f"{round_money(amount):.2f}",
            transaction_type,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def month_key(value: date | datetime | str) -> str:
    """Kembalikan bulan dalam format YYYY-MM."""

    if isinstance(value, datetime):
        return value.strftime("%Y-%m")
    if isinstance(value, date):
        return value.strftime("%Y-%m")
    text = str(value).strip()
    if not re.fullmatch(r"\d{4}-\d{2}", text):
        raise DomainError("Format bulan harus YYYY-MM.")
    parse_month(text)
    return text


def parse_month(month: str) -> tuple[int, int]:
    """Validasi dan pecah bulan YYYY-MM menjadi (tahun, bulan)."""

    text = str(month).strip()
    if not re.fullmatch(r"\d{4}-\d{2}", text):
        raise DomainError("Format bulan harus YYYY-MM.")
    year, month_number = (int(part) for part in text.split("-"))
    if not 1 <= month_number <= 12:
        raise DomainError("Bulan tidak valid.")
    if not 1900 <= year <= 2200:
        raise DomainError("Tahun tidak valid.")
    return year, month_number


def month_label(month: str) -> str:
    year, month_number = parse_month(month)
    return f"{_MONTH_NAMES_ID[month_number - 1]} {year}"


def days_in_month(year: int, month_number: int) -> int:
    return calendar.monthrange(year, month_number)[1]


def month_bounds(month: str) -> tuple[date, date]:
    year, month_number = parse_month(month)
    last_day = days_in_month(year, month_number)
    return date(year, month_number, 1), date(year, month_number, last_day)


def shift_month(month: str, offset: int) -> str:
    """Geser bulan sebanyak offset (boleh negatif)."""

    year, month_number = parse_month(month)
    total = year * 12 + (month_number - 1) + offset
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def month_range(end_month: str, count: int) -> list[str]:
    """Daftar bulan berurutan yang berakhir pada ``end_month``."""

    if count < 1:
        return []
    return [shift_month(end_month, offset) for offset in range(-(count - 1), 1)]


def safe_percentage(numerator: float, denominator: float) -> float | None:
    """Persentase yang aman dari pembagian nol dan nilai non-finite."""

    if denominator is None or denominator == 0:
        return None
    result = numerator / denominator * 100
    if not math.isfinite(result):
        return None
    return result
