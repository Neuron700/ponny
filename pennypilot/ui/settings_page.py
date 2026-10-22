"""Halaman pengaturan, data lokal, bantuan, dan tentang."""

from __future__ import annotations

import os
from datetime import date

import streamlit as st

from pennypilot import db
from pennypilot.config import (
    ANOMALY_FALLBACK_MULTIPLIER,
    ANOMALY_LOOKBACK_DAYS,
    ANOMALY_MAD_MULTIPLIER,
    ANOMALY_MAD_SCALE,
    ANOMALY_MIN_COMPARISONS,
    APP_NAME,
    APP_VERSION,
    DB_PATH_ENV,
    MAX_FILE_SIZE_BYTES,
    MAX_IMPORT_ROWS,
    get_db_path,
)
from pennypilot.services import analytics, exports
from pennypilot.ui import common
from pennypilot.utils import format_rupiah


def _database_size(path: str) -> str:
    try:
        size = os.path.getsize(path) if path != ":memory:" else 0
    except OSError:
        return "Tidak tersedia"
    if size < 1024:
        return f"{size} byte"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def render(connection) -> None:
    common.page_header(
        "Aplikasi lokal",
        "Pengaturan & Tentang",
        "Kelola data lokal, unduh cadangan, dan pahami cara kerja analisis PennyPilot.",
    )
    db_path = get_db_path()
    frame = analytics.to_frame(db.list_transactions(connection))
    transaction_count = len(frame)
    months = analytics.available_months(frame)
    rules = db.list_category_rules(connection)
    month_count = len(months)

    metrics = st.columns(4)
    metrics[0].metric("Transaksi", f"{transaction_count:,}".replace(",", "."))
    metrics[1].metric("Bulan dengan data", str(month_count))
    metrics[2].metric("Aturan kategori", str(len(rules)))
    metrics[3].metric("Ukuran database", _database_size(str(db_path)))

    overview, data_tab, help_tab = st.tabs(["Ringkasan", "Data & Privasi", "Bantuan"])

    with overview:
        st.subheader("Tentang PennyPilot")
        st.write(
            f"{APP_NAME} versi {APP_VERSION} adalah aplikasi web lokal untuk mencatat dan "
            "menganalisis pengeluaran pribadi dari CSV. Tidak ada akun, API key, cloud, "
            "koneksi bank, atau model machine learning."
        )
        st.markdown(
            """
            - **Local-first:** transaksi tetap di komputer ini.
            - **Transparan:** setiap tanda pengeluaran tidak biasa menyertakan alasan.
            - **Aman saat impor:** pratinjau, validasi per baris, dan kandidat duplikat.
            - **Non-destruktif:** file CSV asli tidak diubah.
            """
        )
        st.markdown("**Lokasi database**")
        st.code(str(db_path), language="text")
        st.caption(
            f"Ubah lokasi dengan variabel lingkungan `{DB_PATH_ENV}` sebelum menjalankan "
            "aplikasi. Skema database: versi "
            f"{db.get_metadata(connection, 'schema_version') or 'tidak diketahui'}."
        )

        st.divider()
        st.subheader("Dataset contoh")
        st.caption(
            "Dataset demo berisi transaksi sintetis April–Oktober 2026, termasuk contoh "
            "pengeluaran tidak biasa. Memuat ulang tidak akan menggandakan data karena "
            "deteksi duplikat aktif."
        )
        if transaction_count and st.checkbox(
            "Saya mengerti data demo akan ditambahkan ke database yang sudah berisi data.",
            key="settings_demo_confirm",
        ):
            common.load_demo_button(
                connection, key="settings_load_demo", label="Muat dataset demo"
            )
        elif not transaction_count:
            common.load_demo_button(
                connection, key="settings_load_demo_empty", label="Muat dataset demo"
            )

    with data_tab:
        st.subheader("Ekspor dan cadangan")
        st.write(
            "Ekspor CSV tidak mengubah database. Untuk cadangan manual, hentikan aplikasi "
            "terlebih dahulu lalu salin file database."
        )
        if transaction_count:
            all_rows = db.list_transactions(connection)
            st.download_button(
                "Unduh semua transaksi (CSV)",
                data=exports.transactions_to_csv_bytes(all_rows),
                file_name=f"pennypilot_semua_transaksi_{date.today().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                key="settings_export_all",
            )
        else:
            st.caption("Belum ada transaksi untuk diekspor.")

        st.download_button(
            "Unduh cadangan database (.db)",
            data=db.backup_database_bytes(connection),
            file_name=f"pennypilot_backup_{date.today().strftime('%Y%m%d')}.db",
            mime="application/vnd.sqlite3",
            key="settings_backup_db",
        )
        st.caption(
            "Cadangan dibuat sebagai snapshot SQLite yang konsisten, termasuk transaksi "
            "dan anggaran terbaru."
        )

        st.markdown("**Cadangan manual**")
        st.code(
            f'copy "{db_path}" "cadangan-pennypilot.db"\n'
            "# atau di macOS/Linux:\n"
            f'cp "{db_path}" cadangan-pennypilot.db',
            language="powershell",
        )
        st.caption(
            "File database, file CSV pribadi, dan `-wal`/`-shm` sudah masuk `.gitignore`. "
            "Jangan commit data keuangan ke repositori."
        )

        st.divider()
        st.subheader("Hapus semua transaksi")
        st.warning(
            "Tindakan ini menghapus seluruh transaksi dari SQLite. Aturan kategori dan "
            "anggaran tetap disimpan. Buat cadangan terlebih dahulu bila perlu."
        )
        confirmation = st.text_input(
            "Ketik HAPUS untuk mengonfirmasi",
            key="delete_all_confirmation",
            placeholder="HAPUS",
        )
        acknowledge = st.checkbox(
            "Saya memahami tindakan ini tidak dapat dibatalkan.",
            key="delete_all_acknowledge",
        )
        if st.button(
            "Hapus semua transaksi",
            disabled=not (confirmation == "HAPUS" and acknowledge),
            key="delete_all_button",
        ):
            deleted = db.delete_all_transactions(connection)
            common.flash(f"{deleted} transaksi dihapus dari database.")
            st.rerun()

        st.divider()
        st.subheader("Privasi dan keamanan")
        row_limit = f"{MAX_IMPORT_ROWS:,}".replace(",", ".")
        st.markdown(
            f"""
            - Tidak ada telemetri, permintaan jaringan keluar, atau unggahan data.
            - Batas impor: {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB dan
              {row_limit} baris per file.
            - Keamanan data bergantung pada keamanan perangkat dan akun pengguna.
            - Jangan menjalankan aplikasi di jaringan publik tanpa perlindungan tambahan.
            """
        )

    with help_tab:
        st.subheader("Cara kerja deteksi pengeluaran tidak biasa")
        st.markdown(
            f"""
            PennyPilot **tidak memakai machine learning**. Aturan default:

            1. Hanya transaksi bertipe pengeluaran yang dievaluasi.
            2. Baseline diambil dari transaksi kategori yang sama dalam
               **{ANOMALY_LOOKBACK_DAYS} hari sebelum** tanggal transaksi.
            3. Minimal **{ANOMALY_MIN_COMPARISONS} transaksi pembanding**. Jika belum cukup,
               statusnya **Belum cukup data**, bukan normal.
            4. Baseline memakai **median** dan **MAD** (median absolute deviation).
            5. Jika MAD > 0, ambang = `median + {ANOMALY_MAD_MULTIPLIER} ×
               {str(ANOMALY_MAD_SCALE).replace('.', ',')} × MAD`.
            6. Jika MAD = 0 dan median > 0, ambang fallback =
               `{str(ANOMALY_FALLBACK_MULTIPLIER).replace('.', ',')} × median`.
            7. Jika MAD dan median sama-sama nol, baseline dianggap tidak informatif dan
               tidak ada keputusan otomatis.

            Label “Pengeluaran tidak biasa” hanya berarti nominal relatif menyimpang
            dari riwayat kategori. Ini bukan tuduhan fraud, pencurian, atau kesalahan.
            """
        )

        st.subheader("Cara kerja estimasi anggaran")
        st.markdown(
            """
            Untuk bulan berjalan:

            `estimasi = pengeluaran sejauh ini ÷ hari yang telah berjalan × jumlah hari bulan`

            Hari berjalan minimal 1. Jika belum ada pengeluaran, estimasi berstatus
            “Belum tersedia”. Bulan lampau memakai total aktual final, bukan proyeksi.
            Ini ekstrapolasi linear sederhana, bukan jaminan.

            **Saran anggaran** memakai median total kategori pada tiga bulan kalender
            lengkap terakhir yang memiliki data. Bulan tanpa pengeluaran kategori dihitung
            Rp0. Jika data kurang dari tiga bulan, saran tidak ditampilkan. Pengguna wajib
            meninjau dan mengonfirmasi sebelum menyimpan.
            """
        )

        st.subheader("Batasan MVP")
        st.markdown(
            """
            - Satu pengguna, satu database lokal, dan satu mata uang (Rupiah).
            - Tidak ada koneksi bank, sinkronisasi cloud, OCR struk, atau saran finansial.
            - Deteksi anomali hanya membandingkan nominal dalam kategori yang sama.
            - Kategori berasal dari CSV, aturan kata kunci, atau edit manual.
            - Tidak ada autentikasi; jangan mengekspos aplikasi ke internet tanpa proteksi.
            """
        )
        st.caption(
            f"Nilai anggaran dan nominal ditampilkan dengan format Rupiah. Contoh: "
            f"{format_rupiah(1234567.89)}."
        )
    common.footer()
