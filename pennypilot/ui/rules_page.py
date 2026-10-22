"""Halaman kategori dan aturan kata kunci."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pennypilot import db
from pennypilot.config import DEFAULT_CATEGORIES
from pennypilot.services.categorizer import find_matching_rule, recategorize_transactions
from pennypilot.ui import common


def _rules_frame(rules) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ID": rule.id,
                "Kata kunci": rule.keyword,
                "Kategori": rule.category,
                "Prioritas": rule.priority,
                "Aktif": rule.enabled,
            }
            for rule in rules
        ],
        columns=["ID", "Kata kunci", "Kategori", "Prioritas", "Aktif"],
    )


def render(connection) -> None:
    common.page_header(
        "Kategorisasi",
        "Kategori & Aturan",
        "Atur kata kunci yang menentukan kategori otomatis. Kategori manual dan kategori "
        "dari CSV tidak pernah ditimpa.",
    )
    rules = db.list_category_rules(connection)
    total_transactions = db.count_transactions(connection)
    active = sum(1 for rule in rules if rule.enabled)

    metrics = st.columns(3)
    metrics[0].metric("Aturan tersimpan", len(rules))
    metrics[1].metric("Aturan aktif", active)
    metrics[2].metric("Transaksi", f"{total_transactions:,}".replace(",", "."))

    first, second = st.columns([1, 1])
    with first:
        st.subheader("Tambah aturan")
        with st.form("add_rule_form", clear_on_submit=True):
            keyword = st.text_input(
                "Kata kunci",
                placeholder="Contoh: indomaret",
                help="Pencocokan tidak peka huruf besar/kecil.",
            )
            category = st.selectbox(
                "Kategori tujuan",
                options=list(DEFAULT_CATEGORIES),
                index=list(DEFAULT_CATEGORIES).index("Belanja"),
            )
            priority = st.number_input(
                "Prioritas",
                min_value=0,
                max_value=1000,
                value=0,
                step=1,
                help="Prioritas lebih tinggi menang bila panjang kata kunci sama.",
            )
            enabled = st.checkbox("Aktif", value=True)
            submitted = st.form_submit_button("Tambah aturan", type="primary")
        if submitted:
            try:
                db.add_category_rule(
                    connection,
                    keyword,
                    category,
                    priority=int(priority),
                    enabled=enabled,
                )
            except Exception as exc:
                st.error(f"Aturan gagal ditambahkan: {exc}")
            else:
                common.flash(f"Aturan '{keyword.strip()}' ditambahkan.")
                st.rerun()

    with second:
        st.subheader("Uji aturan")
        with st.form("test_rule_form"):
            sample = st.text_input(
                "Teks deskripsi",
                placeholder="Contoh: Makan malam di restoran",
            )
            test_clicked = st.form_submit_button("Uji pencocokan")
        if test_clicked:
            match = find_matching_rule(sample, db.get_enabled_rules(connection))
            if match is None:
                st.info(
                    "Tidak ada aturan yang cocok. Pengeluaran akan memakai fallback "
                    "'Lainnya', pendapatan memakai 'Pendapatan'."
                )
            else:
                st.success(
                    f"Cocok dengan aturan **{match.keyword}** → **{match.category}** "
                    f"(prioritas {match.priority})."
                )

    st.write("")
    st.subheader("Aturan yang tersimpan")
    st.caption(
        "Urutan pencocokan: kata kunci terpanjang lebih dulu, lalu prioritas terbesar, "
        "lalu ID aturan terkecil. Hanya aturan aktif yang dipakai."
    )
    if not rules:
        st.info("Belum ada aturan. Tambahkan setidaknya satu aturan di atas.")
    else:
        edited = st.data_editor(
            _rules_frame(rules),
            hide_index=True,
            width="stretch",
            num_rows="fixed",
            key=f"rules_editor_{len(rules)}",
            column_config={
                "ID": st.column_config.NumberColumn("ID", disabled=True, format="%d"),
                "Kata kunci": st.column_config.TextColumn(required=True, width="medium"),
                "Kategori": st.column_config.SelectboxColumn(
                    options=list(DEFAULT_CATEGORIES), required=True
                ),
                "Prioritas": st.column_config.NumberColumn(
                    min_value=0, max_value=1000, step=1, format="%d"
                ),
                "Aktif": st.column_config.CheckboxColumn(),
            },
        )
        if st.button("Simpan perubahan aturan", type="primary", key="save_rules"):
            errors: list[str] = []
            updates: list[tuple[int, str, str, int, bool]] = []
            for _, row in edited.iterrows():
                keyword = " ".join(str(row["Kata kunci"]).split())
                category = str(row["Kategori"])
                try:
                    priority = int(row["Prioritas"])
                except (TypeError, ValueError):
                    errors.append(f"Prioritas untuk '{keyword}' bukan bilangan bulat.")
                    continue
                if not keyword:
                    errors.append("Kata kunci tidak boleh kosong.")
                elif category not in DEFAULT_CATEGORIES:
                    errors.append(f"Kategori '{category}' tidak dikenal.")
                else:
                    updates.append(
                        (
                            int(row["ID"]),
                            keyword,
                            category,
                            priority,
                            bool(row["Aktif"]),
                        )
                    )
            if errors:
                for error in errors:
                    st.error(error)
            else:
                for rule_id, keyword, category, priority, enabled in updates:
                    db.update_category_rule(
                        connection,
                        rule_id,
                        keyword=keyword,
                        category=category,
                        priority=priority,
                        enabled=enabled,
                    )
                common.flash("Perubahan aturan disimpan.")
                st.rerun()

        with st.expander("Hapus aturan", expanded=False):
            rule_options = {rule.id: f"{rule.keyword} → {rule.category}" for rule in rules}
            selected = st.selectbox(
                "Pilih aturan",
                options=list(rule_options),
                format_func=lambda rule_id: rule_options[rule_id],
                key="delete_rule_select",
            )
            confirm = st.checkbox(
                "Saya yakin ingin menghapus aturan ini.",
                key=f"delete_rule_confirm_{selected}",
            )
            if st.button(
                "Hapus aturan",
                disabled=not confirm,
                key="delete_rule_button",
            ):
                db.delete_category_rule(connection, int(selected))
                common.flash("Aturan dihapus.")
                st.rerun()

    st.divider()
    st.subheader("Terapkan ulang kategori otomatis")
    st.caption(
        "Hanya transaksi dengan sumber kategori 'Aturan kata kunci' atau 'Default' yang "
        "akan diperbarui. Kategori manual dan kategori dari CSV tetap dipertahankan."
    )
    if st.button("Terapkan ulang aturan ke transaksi otomatis", key="reapply_rules"):
        changed = recategorize_transactions(connection)
        common.flash(
            f"{changed} transaksi diperbarui. Kategori manual dan CSV tidak diubah."
        )
        st.rerun()
    common.footer()
