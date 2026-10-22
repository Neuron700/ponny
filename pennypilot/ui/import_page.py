"""Wizard impor CSV: baca, petakan, validasi, lalu impor."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pennypilot import db
from pennypilot.config import (
    AMOUNT_MODES,
    DATE_FORMAT_OPTIONS,
    DELIMITER_OPTIONS,
    ENCODING_OPTIONS,
    MAX_FILE_SIZE_BYTES,
    MAX_IMPORT_ROWS,
)
from pennypilot.services.csv_import import (
    ColumnMapping,
    CsvImportError,
    ImportOptions,
    analyze_import,
    frame_preview,
    guess_mapping,
    import_rows,
    read_csv_file,
)
from pennypilot.ui import common
from pennypilot.utils import format_rupiah

_LOADED_KEY = "import_loaded"
_ANALYSIS_KEY = "import_analysis"
_SIGNATURE_KEY = "import_analysis_signature"
_ERROR_KEY = "import_error"
_RESET_PENDING_KEY = "_import_reset_pending"
_MAPPING_WIDGET_KEYS = (
    "map_date",
    "map_description",
    "map_amount",
    "map_type",
    "map_category",
    "map_date_format",
    "map_amount_mode",
    "include_duplicates",
)


def _clear_analysis() -> None:
    st.session_state.pop(_ANALYSIS_KEY, None)
    st.session_state.pop(_SIGNATURE_KEY, None)


def _reset_mapping_widgets() -> None:
    for key in _MAPPING_WIDGET_KEYS:
        st.session_state.pop(key, None)


def _clear_import(*, reset_widgets: bool = True) -> None:
    st.session_state.pop(_LOADED_KEY, None)
    _clear_analysis()
    st.session_state.pop(_ERROR_KEY, None)
    if reset_widgets:
        _reset_mapping_widgets()


def _index_of(options: list[str], value: str | None) -> int:
    if value in options:
        return options.index(value)  # type: ignore[arg-type]
    return 0


def _analysis_signature(
    file_signature: tuple[str, int],
    date_column: str,
    description_column: str,
    amount_column: str,
    type_column: str | None,
    category_column: str | None,
    date_format_label: str,
    amount_mode: str,
) -> tuple[object, ...]:
    return (
        file_signature,
        date_column,
        description_column,
        amount_column,
        type_column,
        category_column,
        date_format_label,
        amount_mode,
    )


def _render_issues(analysis) -> None:
    if analysis.issues:
        issues = pd.DataFrame(
            [
                {
                    "Baris": issue.row_number,
                    "Kolom": issue.field,
                    "Alasan": issue.message,
                }
                for issue in analysis.issues
            ]
        )
        with st.expander(
            f"Lihat {analysis.invalid_row_count} baris tidak valid", expanded=True
        ):
            st.dataframe(issues, hide_index=True, width="stretch")
            st.caption(
                "Baris tidak valid tidak disimpan. Baris valid lainnya tetap dapat diimpor."
            )

    duplicate_rows = [row for row in analysis.rows if row.is_duplicate]
    if duplicate_rows:
        duplicates = pd.DataFrame(
            [
                {
                    "Baris": row.row_number,
                    "Tanggal": row.transaction.transaction_date.isoformat(),
                    "Deskripsi": row.transaction.description,
                    "Nominal": format_rupiah(row.transaction.amount),
                    "Alasan": row.duplicate_reason,
                }
                for row in duplicate_rows
            ]
        )
        with st.expander(
            f"Lihat {len(duplicate_rows)} kandidat duplikat", expanded=True
        ):
            st.dataframe(duplicates, hide_index=True, width="stretch")
            st.caption(
                "Duplikat dilewati secara default. Dua transaksi identik bisa saja sah; "
                "centang opsi di bawah hanya setelah meninjau."
            )


def render(connection) -> None:
    common.page_header(
        "Impor data",
        "Impor CSV",
        "Petakan kolom, lihat pratinjau, dan validasi setiap baris sebelum menyimpan. "
        "File asli tidak pernah diubah.",
    )
    if st.session_state.pop(_RESET_PENDING_KEY, False):
        _reset_mapping_widgets()

    uploaded = st.file_uploader(
        "Pilih file CSV",
        type=["csv", "txt"],
        help=(
            f"Batas {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB dan "
            f"{MAX_IMPORT_ROWS:,} baris per file.".replace(",", ".")
        ),
        key="csv_uploader",
    )
    if uploaded is None:
        st.info(
            "Belum ada file dipilih. Ekspor CSV dari bank atau e-wallet, lalu unggah di sini."
        )
        st.caption(
            "Contoh kolom: tanggal, deskripsi, nominal, tipe, kategori. "
            "Kolom tipe dan kategori bersifat opsional."
        )
        return

    file_signature = (
        uploaded.name,
        uploaded.size,
        getattr(uploaded, "file_id", None),
    )
    if st.session_state.get("_import_file_signature") != file_signature:
        _clear_import()
        st.session_state["_import_file_signature"] = file_signature

    with st.container(border=True):
        st.subheader("1. Format file")
        first, second = st.columns(2)
        with first:
            delimiter_label = st.selectbox(
                "Delimiter",
                options=list(DELIMITER_OPTIONS),
                key="import_delimiter",
            )
        with second:
            encoding_label = st.selectbox(
                "Encoding",
                options=list(ENCODING_OPTIONS),
                key="import_encoding",
            )
        if st.button("Baca dan pratinjau file", type="primary", key="read_csv_button"):
            st.session_state.pop(_ERROR_KEY, None)
            st.session_state.pop(_LOADED_KEY, None)
            _clear_analysis()
            try:
                loaded = read_csv_file(
                    uploaded.getvalue(),
                    delimiter=DELIMITER_OPTIONS[delimiter_label],
                    encoding=None
                    if encoding_label == "Deteksi otomatis"
                    else encoding_label,
                )
            except CsvImportError as exc:
                st.session_state[_ERROR_KEY] = str(exc)
            except Exception:
                st.session_state[_ERROR_KEY] = (
                    "File tidak dapat dibaca. Periksa delimiter, encoding, dan struktur CSV."
                )
            else:
                st.session_state[_LOADED_KEY] = loaded

    error = st.session_state.get(_ERROR_KEY)
    if error:
        st.error(error)
        return

    loaded = st.session_state.get(_LOADED_KEY)
    if loaded is None:
        return

    st.caption(
        f"Terdeteksi encoding **{loaded.encoding}** dan delimiter "
        f"**{repr(loaded.delimiter)}**. Pratinjau 20 baris pertama; "
        "nomor baris mengikuti file asli."
    )
    preview = frame_preview(loaded.frame)
    st.dataframe(preview, width="stretch", height=330)

    columns = list(loaded.frame.columns)
    guessed = guess_mapping(columns)
    optional_columns = ["(tidak digunakan)"] + columns

    with st.container(border=True):
        st.subheader("2. Pemetaan dan validasi")
        with st.form("mapping_form"):
            first, second, third = st.columns(3)
            with first:
                date_column = st.selectbox(
                    "Kolom tanggal",
                    options=columns,
                    index=_index_of(columns, guessed["date"]),
                    key="map_date",
                )
            with second:
                description_column = st.selectbox(
                    "Kolom deskripsi",
                    options=columns,
                    index=_index_of(columns, guessed["description"]),
                    key="map_description",
                )
            with third:
                amount_column = st.selectbox(
                    "Kolom nominal",
                    options=columns,
                    index=_index_of(columns, guessed["amount"]),
                    key="map_amount",
                )

            fourth, fifth = st.columns(2)
            with fourth:
                type_column_label = st.selectbox(
                    "Kolom tipe transaksi (opsional)",
                    options=optional_columns,
                    index=_index_of(optional_columns, guessed["transaction_type"]),
                    key="map_type",
                )
            with fifth:
                category_column_label = st.selectbox(
                    "Kolom kategori (opsional)",
                    options=optional_columns,
                    index=_index_of(optional_columns, guessed["category"]),
                    key="map_category",
                )

            sixth, seventh = st.columns(2)
            with sixth:
                date_format_label = st.selectbox(
                    "Format tanggal",
                    options=list(DATE_FORMAT_OPTIONS),
                    index=0,
                    key="map_date_format",
                    help=(
                        "Jika tanggal ambigu (misalnya 01/02/2026), pilih format eksplisit "
                        "sebelum mengimpor."
                    ),
                )
            with seventh:
                amount_mode = st.selectbox(
                    "Interpretasi nominal",
                    options=list(AMOUNT_MODES),
                    format_func=lambda key: AMOUNT_MODES[key],
                    key="map_amount_mode",
                )
            submitted = st.form_submit_button("Validasi dan analisis", type="primary")

        type_column = (
            None if type_column_label == "(tidak digunakan)" else type_column_label
        )
        category_column = (
            None
            if category_column_label == "(tidak digunakan)"
            else category_column_label
        )
        current_signature = _analysis_signature(
            file_signature,
            date_column,
            description_column,
            amount_column,
            type_column,
            category_column,
            date_format_label,
            amount_mode,
        )

        if submitted:
            if len({date_column, description_column, amount_column}) < 3:
                st.error("Kolom tanggal, deskripsi, dan nominal harus berbeda.")
                return
            try:
                analysis = analyze_import(
                    loaded.frame,
                    ColumnMapping(
                        date=date_column,
                        description=description_column,
                        amount=amount_column,
                        transaction_type=type_column,
                        category=category_column,
                    ),
                    ImportOptions(
                        amount_mode=amount_mode,
                        date_format=DATE_FORMAT_OPTIONS[date_format_label],
                    ),
                    existing_fingerprints=db.get_existing_fingerprints(connection),
                    rules=db.get_enabled_rules(connection),
                    source_file=uploaded.name,
                    encoding=loaded.encoding,
                    delimiter=loaded.delimiter,
                    parse_issues=loaded.parse_issues,
                    total_rows=loaded.total_rows,
                )
            except CsvImportError as exc:
                st.error(str(exc))
                _clear_analysis()
            except Exception:
                st.error(
                    "Analisis gagal. Periksa pemetaan kolom, format tanggal, dan "
                    "interpretasi nominal."
                )
                _clear_analysis()
            else:
                if st.session_state.get(_SIGNATURE_KEY) != current_signature:
                    st.session_state["include_duplicates"] = False
                st.session_state[_ANALYSIS_KEY] = analysis
                st.session_state[_SIGNATURE_KEY] = current_signature

    analysis = st.session_state.get(_ANALYSIS_KEY)
    analysis_signature = st.session_state.get(_SIGNATURE_KEY)
    if analysis is None:
        return
    if analysis_signature != current_signature:
        st.info("Pengaturan pemetaan berubah. Jalankan validasi ulang sebelum mengimpor.")
        return

    st.subheader("3. Ringkasan validasi")
    metrics = st.columns(4)
    metrics[0].metric("Total baris", f"{analysis.total_rows:,}".replace(",", "."))
    metrics[1].metric("Baris valid", f"{analysis.valid_count:,}".replace(",", "."))
    metrics[2].metric(
        "Baris tidak valid", f"{analysis.invalid_row_count:,}".replace(",", ".")
    )
    metrics[3].metric(
        "Kandidat duplikat", f"{analysis.duplicate_count:,}".replace(",", ".")
    )

    for warning in analysis.warnings:
        st.warning(warning)
    _render_issues(analysis)

    include_duplicates = st.checkbox(
        "Sertakan kandidat duplikat setelah saya meninjau (default: dilewati)",
        value=False,
        key="include_duplicates",
        disabled=analysis.duplicate_count == 0,
    )
    rows_to_import = analysis.rows_to_import(include_duplicates=include_duplicates)
    ambiguous = analysis.ambiguous_dates
    blocked = ambiguous or not rows_to_import
    if ambiguous:
        st.error(
            "Format tanggal ambigu. Pilih format eksplisit seperti DD/MM/YYYY atau "
            "MM/DD/YYYY, lalu jalankan validasi ulang."
        )
    elif not rows_to_import:
        st.warning("Tidak ada baris yang siap diimpor dengan pilihan saat ini.")
    else:
        duplicate_note = (
            f" {analysis.duplicate_count} kandidat duplikat dilewati."
            if not include_duplicates and analysis.duplicate_count
            else ""
        )
        st.info(
            f"{len(rows_to_import):,} baris siap disimpan ke SQLite.{duplicate_note}".replace(
                ",", "."
            )
        )
        st.caption(
            "Baris tidak valid tidak diimpor. Kamu bisa memperbaiki file lalu mengimpor ulang; "
            "deteksi duplikat akan membantu mencegah data ganda."
        )

    import_column, cancel_column = st.columns([1, 1])
    with import_column:
        import_clicked = st.button(
            f"Impor {len(rows_to_import)} baris",
            type="primary",
            disabled=blocked,
            key="perform_import",
        )
    with cancel_column:
        cancel_clicked = st.button("Batalkan impor", key="cancel_import")

    if import_clicked:
        imported = import_rows(
            connection, analysis, include_duplicates=include_duplicates
        )
        if imported:
            common.flash(
                f"{imported} transaksi berhasil diimpor. Dashboard sudah memakai data baru."
            )
        else:
            common.flash("Tidak ada transaksi yang diimpor.", "warning")
        _clear_import(reset_widgets=False)
        st.session_state[_RESET_PENDING_KEY] = True
        st.rerun()
    if cancel_clicked:
        _clear_import(reset_widgets=False)
        st.session_state[_RESET_PENDING_KEY] = True
        common.flash("Impor dibatalkan. Tidak ada data yang ditulis.", "info")
        st.rerun()

    common.footer()
