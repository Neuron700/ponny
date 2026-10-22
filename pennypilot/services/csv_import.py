"""Parsing, validasi, pemetaan, dan impor CSV."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from pennypilot import db
from pennypilot.config import (
    AMOUNT_MODES,
    MAX_FILE_SIZE_BYTES,
    MAX_IMPORT_ROWS,
    SAMPLE_DATA_PATH,
)
from pennypilot.models import (
    CategoryRule,
    ImportAnalysis,
    ImportIssue,
    ImportRow,
    TransactionRecord,
)
from pennypilot.services.categorizer import canonical_category, categorize
from pennypilot.utils import (
    DomainError,
    detect_date_ambiguity,
    make_fingerprint,
    parse_amount,
    parse_transaction_date,
)


class CsvImportError(ValueError):
    """Kesalahan tingkat file yang bisa ditampilkan kepada pengguna."""


@dataclass(frozen=True)
class ColumnMapping:
    date: str
    description: str
    amount: str
    transaction_type: str | None = None
    category: str | None = None


@dataclass(frozen=True)
class ImportOptions:
    amount_mode: str = "signed"
    date_format: str | None = None


@dataclass
class LoadedCsv:
    frame: pd.DataFrame
    encoding: str
    delimiter: str
    parse_issues: list[ImportIssue]
    total_rows: int


_TYPE_WORDS = {
    "expense": {
        "expense",
        "expenses",
        "pengeluaran",
        "keluar",
        "debit",
        "db",
        "dr",
        "out",
        "minus",
        "-",
    },
    "income": {
        "income",
        "pemasukan",
        "masuk",
        "credit",
        "kredit",
        "cr",
        "in",
        "plus",
        "+",
    },
}


def _decode(data: bytes, encoding: str | None) -> str:
    candidates = [encoding] if encoding and encoding != "auto" else []
    if not candidates:
        candidates = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    last_error: Exception | None = None
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return data.decode(candidate)
        except (UnicodeDecodeError, LookupError) as exc:
            last_error = exc
    raise CsvImportError(
        "Encoding file tidak dapat dibaca. Coba pilih UTF-8 atau Windows-1252."
    ) from last_error


def detect_encoding(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for candidate in ("utf-8", "cp1252"):
        try:
            data.decode(candidate)
            return candidate
        except UnicodeDecodeError:
            continue
    return "latin-1"


def detect_delimiter(text: str) -> str:
    sample = "\n".join(line for line in text.splitlines()[:20] if line.strip())
    if not sample:
        return ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        lines = [line for line in sample.splitlines() if line.strip()]
        scores = {
            delimiter: sum(line.count(delimiter) for line in lines)
            for delimiter in (",", ";", "\t", "|")
        }
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else ","


def _unique_headers(raw_headers: list[str]) -> list[str]:
    headers: list[str] = []
    seen: dict[str, int] = {}
    for index, raw in enumerate(raw_headers):
        name = str(raw).replace("\ufeff", "").strip()
        if not name:
            name = f"kolom_{index + 1}"
        base = name
        count = seen.get(base, 0)
        if count:
            name = f"{base}_{count + 1}"
        seen[base] = count + 1
        headers.append(name)
    return headers


def read_csv_file(
    data: bytes,
    *,
    delimiter: str | None = None,
    encoding: str | None = None,
) -> LoadedCsv:
    """Baca CSV secara baris-per-baris agar satu baris rusak tidak menggagalkan file."""

    if len(data) > MAX_FILE_SIZE_BYTES:
        size_mb = len(data) / (1024 * 1024)
        raise CsvImportError(
            f"Ukuran file {size_mb:.1f} MB melebihi batas 10 MB. Pecah file lalu impor terpisah."
        )
    if not data.strip():
        raise CsvImportError("File CSV kosong.")

    chosen_encoding = encoding if encoding and encoding != "auto" else detect_encoding(data)
    text = _decode(data, chosen_encoding)
    chosen_delimiter = delimiter or detect_delimiter(text)

    reader = csv.reader(io.StringIO(text, newline=""), delimiter=chosen_delimiter)
    try:
        raw_headers = next(reader)
    except StopIteration as exc:
        raise CsvImportError("File CSV tidak memiliki header.") from exc
    headers = _unique_headers(raw_headers)
    if not any(header.strip() for header in headers):
        raise CsvImportError("Header CSV tidak valid.")

    records: list[dict[str, str]] = []
    row_numbers: list[int] = []
    parse_issues: list[ImportIssue] = []
    total_rows = 0
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        total_rows += 1
        if total_rows > MAX_IMPORT_ROWS:
            raise CsvImportError(
                f"File melebihi batas {MAX_IMPORT_ROWS:,} baris. Pecah file lalu impor terpisah."
            )
        row_number = reader.line_num
        if len(row) != len(headers):
            parse_issues.append(
                ImportIssue(
                    row_number=row_number,
                    field="baris",
                    message=(
                        f"Jumlah kolom {len(row)} tidak sesuai dengan header "
                        f"({len(headers)} kolom)."
                    ),
                )
            )
            continue
        records.append(dict(zip(headers, row, strict=True)))
        row_numbers.append(row_number)

    if not records and not parse_issues:
        raise CsvImportError("File CSV tidak memiliki baris data.")

    frame = pd.DataFrame(records, columns=headers, index=row_numbers, dtype=object)
    frame.index.name = "baris"
    return LoadedCsv(
        frame=frame,
        encoding=chosen_encoding,
        delimiter=chosen_delimiter,
        parse_issues=parse_issues,
        total_rows=total_rows,
    )


def _normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def guess_mapping(columns: list[str]) -> dict[str, str | None]:
    """Tebak kolom berdasarkan nama header yang umum."""

    normalized = {column: _normalized_header(column) for column in columns}
    aliases = {
        "date": ("tanggal", "date", "tgl", "transactiondate", "waktu", "time"),
        "description": (
            "deskripsi",
            "description",
            "keterangan",
            "memo",
            "catatan",
            "merchant",
            "detail",
        ),
        "amount": ("nominal", "amount", "jumlah", "total", "nilai", "value"),
        "transaction_type": ("tipe", "type", "jenis", "transactiontype", "debitkredit"),
        "category": ("kategori", "category", "grup", "group"),
    }
    result: dict[str, str | None] = {}
    for target, terms in aliases.items():
        match = None
        for column, header in normalized.items():
            if header in terms:
                match = column
                break
        if match is None:
            for column, header in normalized.items():
                if any(term in header for term in terms):
                    match = column
                    break
        result[target] = match
    return result


def _parse_type(raw: object) -> str | None:
    value = str(raw).strip().casefold()
    if not value:
        return None
    for transaction_type, words in _TYPE_WORDS.items():
        if value in words:
            return transaction_type
    return None


def _clean_description(raw: object) -> str:
    return " ".join(str(raw).split())


def analyze_import(
    frame: pd.DataFrame,
    mapping: ColumnMapping,
    options: ImportOptions,
    *,
    existing_fingerprints: set[str] | None = None,
    rules: list[CategoryRule] | None = None,
    source_file: str = "",
    encoding: str = "utf-8",
    delimiter: str = ",",
    parse_issues: list[ImportIssue] | None = None,
    total_rows: int | None = None,
) -> ImportAnalysis:
    """Validasi seluruh baris dan hasilkan ringkasan sebelum menulis database."""

    if options.amount_mode not in AMOUNT_MODES:
        raise CsvImportError("Interpretasi nominal tidak dikenal.")
    for column in (mapping.date, mapping.description, mapping.amount):
        if column not in frame.columns:
            raise CsvImportError(f"Kolom '{column}' tidak ditemukan pada file CSV.")
    if options.amount_mode == "absolute_with_type":
        if not mapping.transaction_type:
            raise CsvImportError(
                "Mode nominal absolut memerlukan kolom tipe transaksi. Pilih kolom tipe."
            )
        if mapping.transaction_type not in frame.columns:
            raise CsvImportError(
                f"Kolom tipe '{mapping.transaction_type}' tidak ditemukan pada file CSV."
            )
    if mapping.transaction_type and mapping.transaction_type not in frame.columns:
        raise CsvImportError(
            f"Kolom tipe '{mapping.transaction_type}' tidak ditemukan pada file CSV."
        )
    if mapping.category and mapping.category not in frame.columns:
        raise CsvImportError(
            f"Kolom kategori '{mapping.category}' tidak ditemukan pada file CSV."
        )

    issues: list[ImportIssue] = list(parse_issues or [])
    warnings: list[str] = []
    warning_set: set[str] = set()
    seen: dict[str, int] = {}
    existing = existing_fingerprints or set()
    active_rules = rules or []
    rows: list[ImportRow] = []

    date_values = [str(value) for value in frame[mapping.date].tolist()]
    ambiguous = options.date_format is None and detect_date_ambiguity(date_values)
    if ambiguous:
        warnings.append(
            "Format tanggal ambigu (DD/MM dan MM/DD sama-sama valid). "
            "Pilih format tanggal eksplisit sebelum mengimpor."
        )

    for row_number, row in frame.iterrows():
        row_issues: list[ImportIssue] = []
        raw_date = row[mapping.date]
        raw_description = row[mapping.description]
        raw_amount = row[mapping.amount]

        try:
            transaction_date = parse_transaction_date(raw_date, options.date_format)
        except DomainError as exc:
            row_issues.append(ImportIssue(int(row_number), "tanggal", str(exc)))
            transaction_date = None

        description = _clean_description(raw_description)
        if not description:
            row_issues.append(ImportIssue(int(row_number), "deskripsi", "Deskripsi kosong."))

        try:
            parsed_amount = parse_amount(raw_amount)
        except DomainError as exc:
            row_issues.append(ImportIssue(int(row_number), "nominal", str(exc)))
            parsed_amount = None

        transaction_type: str | None = None
        if parsed_amount is not None:
            if options.amount_mode == "signed":
                if parsed_amount < 0:
                    transaction_type = "expense"
                elif parsed_amount > 0:
                    transaction_type = "income"
                else:
                    row_issues.append(
                        ImportIssue(int(row_number), "nominal", "Nominal tidak boleh nol.")
                    )
            elif options.amount_mode == "absolute_with_type":
                if parsed_amount < 0:
                    row_issues.append(
                        ImportIssue(
                            int(row_number),
                            "nominal",
                            "Nominal harus positif pada mode absolut + kolom tipe.",
                        )
                    )
                elif parsed_amount == 0:
                    row_issues.append(
                        ImportIssue(int(row_number), "nominal", "Nominal tidak boleh nol.")
                    )
                else:
                    transaction_type = _parse_type(row[mapping.transaction_type])
                    if transaction_type is None:
                        row_issues.append(
                            ImportIssue(
                                int(row_number),
                                "tipe",
                                f"Tipe '{row[mapping.transaction_type]}' tidak dikenali.",
                            )
                        )
            else:
                if parsed_amount == 0:
                    row_issues.append(
                        ImportIssue(int(row_number), "nominal", "Nominal tidak boleh nol.")
                    )
                else:
                    transaction_type = "expense"

        if row_issues or transaction_date is None or parsed_amount is None or transaction_type is None:
            issues.extend(row_issues)
            continue

        raw_category = row[mapping.category] if mapping.category else None
        source_category = canonical_category(raw_category)
        if (
            mapping.category
            and str(raw_category).strip()
            and source_category is None
            and str(raw_category).strip() not in warning_set
        ):
            warning_set.add(str(raw_category).strip())
            warnings.append(
                f"Kategori CSV '{str(raw_category).strip()}' tidak dikenal; "
                "aturan otomatis dipakai untuk baris terkait."
            )

        category, category_source = categorize(
            description,
            transaction_type,
            active_rules,
            source_category=source_category,
        )
        amount = abs(parsed_amount)
        fingerprint = make_fingerprint(
            transaction_date, description, amount, transaction_type
        )
        duplicate = False
        duplicate_reason = ""
        if fingerprint in existing:
            duplicate = True
            duplicate_reason = "Sudah ada di database."
        elif fingerprint in seen:
            duplicate = True
            duplicate_reason = f"Duplikat dalam file dengan baris {seen[fingerprint]}."
        else:
            seen[fingerprint] = int(row_number)

        rows.append(
            ImportRow(
                row_number=int(row_number),
                transaction=TransactionRecord(
                    transaction_date=transaction_date,
                    description=description,
                    amount=amount,
                    transaction_type=transaction_type,
                    category=category,
                    category_source=category_source,
                    fingerprint=fingerprint,
                    source_file=source_file or None,
                ),
                is_duplicate=duplicate,
                duplicate_reason=duplicate_reason,
            )
        )

    issues.sort(key=lambda issue: (issue.row_number, issue.field))
    return ImportAnalysis(
        rows=rows,
        issues=issues,
        total_rows=total_rows if total_rows is not None else len(frame) + len(parse_issues or []),
        source_file=source_file,
        encoding=encoding,
        delimiter=delimiter,
        warnings=warnings,
        ambiguous_dates=ambiguous,
    )


def import_rows(
    connection,
    analysis: ImportAnalysis,
    *,
    include_duplicates: bool = False,
) -> int:
    """Simpan baris valid; duplikat dilewati kecuali diminta eksplisit."""

    selected = analysis.rows_to_import(include_duplicates=include_duplicates)
    return db.insert_transactions(connection, [row.transaction for row in selected])


def load_demo_data(connection) -> tuple[ImportAnalysis, int]:
    """Muat dataset sintetis; impor ulang tidak menggandakan secara diam-diam."""

    if not SAMPLE_DATA_PATH.exists():
        raise CsvImportError("Dataset contoh tidak ditemukan di paket aplikasi.")
    data = Path(SAMPLE_DATA_PATH).read_bytes()
    loaded = read_csv_file(data)
    mapping = ColumnMapping(
        date="tanggal",
        description="deskripsi",
        amount="nominal",
        transaction_type="tipe",
        category="kategori",
    )
    analysis = analyze_import(
        loaded.frame,
        mapping,
        ImportOptions(amount_mode="signed", date_format="%Y-%m-%d"),
        existing_fingerprints=db.get_existing_fingerprints(connection),
        rules=db.get_enabled_rules(connection),
        source_file=SAMPLE_DATA_PATH.name,
        encoding=loaded.encoding,
        delimiter=loaded.delimiter,
        parse_issues=loaded.parse_issues,
        total_rows=loaded.total_rows,
    )
    imported = import_rows(connection, analysis)
    return analysis, imported


def frame_preview(frame: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    """Pratinjau tanpa mengubah file sumber."""

    return frame.head(rows).copy()
