"""Halaman daftar, filter, edit, hapus, dan ekspor transaksi."""

from __future__ import annotations

from datetime import date

import streamlit as st

from pennypilot import db
from pennypilot.config import DEFAULT_CATEGORIES, TYPE_LABELS
from pennypilot.models import TransactionRecord
from pennypilot.services import exports
from pennypilot.ui import common
from pennypilot.utils import format_rupiah, make_fingerprint


def _add_transaction_form(connection) -> None:
    with st.expander(
        "Tambah transaksi manual",
        expanded=db.count_transactions(connection) == 0,
    ):
        st.caption(
            "Gunakan untuk transaksi tunai atau koreksi cepat. Kategori yang ditambahkan "
            "di sini bertanda manual dan tidak ditimpa aturan otomatis."
        )
        with st.form("add_transaction_form", clear_on_submit=True):
            first, second = st.columns(2)
            with first:
                add_date = st.date_input("Tanggal", value=date.today(), key="add_date")
                add_amount = st.number_input(
                    "Nominal",
                    min_value=0.0,
                    value=0.0,
                    step=1000.0,
                    format="%.2f",
                    key="add_amount",
                )
            with second:
                add_type = st.selectbox(
                    "Tipe transaksi",
                    options=["expense", "income"],
                    format_func=lambda value: TYPE_LABELS[value],
                    key="add_type",
                )
                add_category = st.selectbox(
                    "Kategori",
                    options=list(DEFAULT_CATEGORIES),
                    index=list(DEFAULT_CATEGORIES).index("Makanan"),
                    key="add_category",
                )
            add_description = st.text_input(
                "Deskripsi",
                placeholder="Contoh: Makan siang di warung",
                key="add_description",
            )
            submitted = st.form_submit_button("Tambah transaksi", type="primary")
        if submitted:
            if not add_description.strip():
                st.error("Deskripsi tidak boleh kosong.")
            elif add_amount <= 0:
                st.error("Nominal harus lebih dari nol.")
            else:
                record = TransactionRecord(
                    transaction_date=add_date,
                    description=add_description.strip(),
                    amount=float(add_amount),
                    transaction_type=add_type,
                    category=add_category,
                    category_source="manual",
                    fingerprint=make_fingerprint(
                        add_date, add_description.strip(), float(add_amount), add_type
                    ),
                )
                db.insert_transactions(connection, [record])
                common.flash("Transaksi manual ditambahkan.")
                st.rerun()


def _selected_row(rows) -> tuple[int, object]:
    options = [int(row["id"]) for row in rows]
    rows_by_id = {int(row["id"]): row for row in rows}
    chosen = st.selectbox(
        "Pilih transaksi",
        options=options,
        format_func=lambda transaction_id: (
            f"#{transaction_id} · {rows_by_id[transaction_id]['transaction_date']} · "
            f"{rows_by_id[transaction_id]['description'][:60]}"
        ),
        key="transaction_edit_id",
    )
    return chosen, rows_by_id[chosen]


def render(connection) -> None:
    common.page_header(
        "Data transaksi",
        "Transaksi",
        "Cari, filter, perbaiki kategori, edit nominal, atau hapus transaksi. "
        "Semua perubahan langsung memengaruhi dashboard.",
    )
    _add_transaction_form(connection)
    bounds = db.get_date_bounds(connection)
    if bounds is None:
        common.empty_state(
            "Belum ada transaksi",
            "Impor CSV, muat dataset demo, atau tambahkan transaksi manual di atas. "
            "Setelah itu kamu bisa mengedit kategori, tanggal, deskripsi, nominal, "
            "dan tipe transaksi di sini.",
            page="Impor CSV",
        )
        return

    with st.container(border=True):
        st.markdown("**Filter transaksi**")
        first, second, third, fourth = st.columns([1, 1, 1, 2])
        with first:
            start_date = st.date_input(
                "Dari tanggal",
                value=bounds[0],
                min_value=bounds[0],
                max_value=bounds[1],
                key="filter_start",
            )
        with second:
            end_date = st.date_input(
                "Sampai tanggal",
                value=bounds[1],
                min_value=bounds[0],
                max_value=bounds[1],
                key="filter_end",
            )
        with third:
            type_label = st.selectbox(
                "Tipe",
                ["Semua tipe", "Pengeluaran", "Pendapatan"],
                key="filter_type",
            )
        with fourth:
            search = st.text_input(
                "Cari deskripsi",
                placeholder="Contoh: kopi, grab, listrik",
                key="filter_search",
            )
        categories = st.multiselect(
            "Kategori",
            options=list(DEFAULT_CATEGORIES),
            default=[],
            placeholder="Semua kategori",
            key="filter_categories",
        )

    if start_date > end_date:
        st.error("Tanggal awal tidak boleh melewati tanggal akhir.")
        return

    transaction_type = {
        "Pengeluaran": "expense",
        "Pendapatan": "income",
    }.get(type_label)
    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "categories": categories or None,
        "transaction_type": transaction_type,
        "search": search or None,
    }
    total = db.count_transactions(connection, **filters)
    rows = db.list_transactions(connection, limit=500, **filters)
    st.caption(
        f"{total:,} transaksi cocok dengan filter. Menampilkan maksimal 500 baris terbaru.".replace(
            ",", "."
        )
        if total > 500
        else f"{total:,} transaksi cocok dengan filter.".replace(",", ".")
    )

    if not rows:
        st.info("Tidak ada transaksi yang cocok. Ubah filter atau rentang tanggal.")
        return

    table = common.transaction_table(rows)
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "Deskripsi": st.column_config.TextColumn(width="large"),
            "Nominal": st.column_config.TextColumn(width="small"),
        },
    )

    export_rows = db.list_transactions(connection, **filters)
    export_bytes = exports.transactions_to_csv_bytes(export_rows)
    st.download_button(
        "Ekspor hasil filter ke CSV",
        data=export_bytes,
        file_name=f"pennypilot_transaksi_{date.today().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key="download_filtered_transactions",
    )

    st.write("")
    with st.expander("Edit transaksi", expanded=False):
        transaction_id, row = _selected_row(rows)
        current_category = str(row["category"])
        category_options = list(DEFAULT_CATEGORIES)
        if current_category not in category_options:
            category_options.append(current_category)

        with st.form(f"edit_transaction_form_{transaction_id}"):
            left, right = st.columns([1, 1])
            with left:
                edit_date = st.date_input(
                    "Tanggal",
                    value=date.fromisoformat(str(row["transaction_date"])),
                    key=f"edit_date_{transaction_id}",
                )
                edit_amount = st.number_input(
                    "Nominal",
                    min_value=0.0,
                    value=float(row["amount"]),
                    step=1000.0,
                    format="%.2f",
                    key=f"edit_amount_{transaction_id}",
                    help="Nominal selalu disimpan sebagai angka non-negatif; arah diatur oleh tipe.",
                )
            with right:
                edit_type = st.selectbox(
                    "Tipe transaksi",
                    options=["expense", "income"],
                    index=0 if row["transaction_type"] == "expense" else 1,
                    format_func=lambda value: TYPE_LABELS[value],
                    key=f"edit_type_{transaction_id}",
                )
                edit_category = st.selectbox(
                    "Kategori",
                    options=category_options,
                    index=category_options.index(current_category),
                    key=f"edit_category_{transaction_id}",
                )
            edit_description = st.text_input(
                "Deskripsi",
                value=str(row["description"]),
                key=f"edit_description_{transaction_id}",
            )
            save_clicked = st.form_submit_button("Simpan perubahan", type="primary")

        if save_clicked:
            if not edit_description.strip():
                st.error("Deskripsi tidak boleh kosong.")
            elif edit_amount <= 0:
                st.error("Nominal harus lebih dari nol.")
            else:
                updated = db.update_transaction(
                    connection,
                    transaction_id,
                    transaction_date=edit_date,
                    description=edit_description,
                    amount=edit_amount,
                    transaction_type=edit_type,
                    category=edit_category,
                )
                if updated:
                    common.flash(
                        f"Transaksi #{transaction_id} diperbarui. Kategorinya ditandai manual "
                        "sehingga tidak ditimpa aturan otomatis."
                    )
                    st.rerun()
                else:
                    st.error("Transaksi tidak ditemukan atau gagal diperbarui.")

        st.divider()
        st.markdown(f"**Hapus transaksi #{transaction_id}**")
        st.caption(f"{row['description']} · {format_rupiah(float(row['amount']))}")
        with st.form(f"delete_transaction_form_{transaction_id}"):
            confirm = st.checkbox(
                "Saya yakin ingin menghapus transaksi ini secara permanen.",
                key=f"delete_confirm_{transaction_id}",
            )
            delete_clicked = st.form_submit_button("Hapus transaksi")
        if delete_clicked:
            if not confirm:
                st.error("Centang konfirmasi sebelum menghapus.")
            else:
                deleted = db.delete_transaction(connection, transaction_id)
                if deleted:
                    common.flash(f"Transaksi #{transaction_id} dihapus.")
                    st.rerun()
                else:
                    st.error("Transaksi tidak ditemukan atau sudah terhapus.")
