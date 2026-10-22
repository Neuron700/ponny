"""Halaman anggaran bulanan, proyeksi, dan saran anggaran."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from pennypilot import db
from pennypilot.config import DEFAULT_CATEGORIES
from pennypilot.services import analytics
from pennypilot.services.budgets import (
    budget_usage,
    estimate_month_end,
    suggest_budgets,
)
from pennypilot.ui import common
from pennypilot.utils import format_rupiah, month_label

_BUDGET_CATEGORIES = [category for category in DEFAULT_CATEGORIES if category != "Pendapatan"]


def _next_revision() -> int:
    revision = int(st.session_state.get("budget_revision", 0)) + 1
    st.session_state["budget_revision"] = revision
    return revision


def render(connection) -> None:
    common.page_header(
        "Perencanaan",
        "Anggaran",
        "Tetapkan anggaran total dan per kategori, lalu bandingkan dengan aktual serta "
        "estimasi akhir bulan.",
    )
    today = date.today()
    current_month = today.strftime("%Y-%m")
    months = common.display_month_options()
    month = common.month_selectbox(
        months, key="budget_month", default=current_month
    )
    frame = analytics.to_frame(db.list_transactions(connection))
    kpis = analytics.monthly_kpis(frame, month)
    actual_expense = float(kpis["expense"])
    budget_map = db.get_budget_map(connection, month)
    total_budget = budget_map.get(None)
    usage = budget_usage(actual_expense, total_budget)
    projection = estimate_month_end(actual_expense, today, month)

    metric_columns = st.columns(4)
    metric_columns[0].metric("Pengeluaran aktual", format_rupiah(actual_expense))
    metric_columns[1].metric(
        "Anggaran total",
        format_rupiah(total_budget) if total_budget is not None else "Belum diatur",
    )
    metric_columns[2].metric(
        "Sisa anggaran",
        format_rupiah(usage.remaining) if usage.remaining is not None else "—",
    )
    metric_columns[3].metric(
        "Terpakai",
        f"{usage.percentage:.0f}%" if usage.percentage is not None else "—",
        help="Anggaran nol atau belum diatur tidak dipaksakan menjadi persentase.",
    )

    projection_label = (
        "Total aktual" if projection.status == "final" else "Estimasi akhir bulan"
    )
    st.caption(
        f"{projection_label}: "
        f"{format_rupiah(projection.projected) if projection.available else 'Belum tersedia'}"
        + (f" · {projection.note}" if projection.note else "")
    )
    if projection.available and total_budget is not None:
        projected_usage = budget_usage(projection.projected or 0.0, total_budget)
        if projected_usage.is_over and total_budget > 0:
            st.warning(
                f"Estimasi {format_rupiah(projection.projected)} melewati anggaran "
                f"{format_rupiah(total_budget)}. Peringatan ini netral dan bukan saran finansial."
            )

    st.write("")
    with st.container(border=True):
        st.subheader("Atur anggaran")
        st.caption(
            f"Anggaran disimpan khusus untuk {month_label(month)}. Nilai kosong berarti "
            "belum diatur, bukan nol."
        )
        set_total = st.toggle(
            "Atur anggaran total bulan ini",
            value=total_budget is not None,
            key=f"budget_set_total_{month}",
        )
        total_value = st.number_input(
            "Anggaran total (Rp)",
            min_value=0.0,
            value=float(total_budget or 0.0),
            step=100_000.0,
            format="%.2f",
            disabled=not set_total,
            key=f"budget_total_input_{month}",
        )

        revision = int(st.session_state.get("budget_revision", 0))
        category_data = pd.DataFrame(
            {
                "Kategori": _BUDGET_CATEGORIES,
                "Anggaran": [
                    budget_map.get(category) for category in _BUDGET_CATEGORIES
                ],
            }
        )
        edited = st.data_editor(
            category_data,
            hide_index=True,
            width="stretch",
            num_rows="fixed",
            key=f"budget_editor_{month}_{revision}",
            column_config={
                "Kategori": st.column_config.TextColumn(disabled=True),
                "Anggaran": st.column_config.NumberColumn(
                    "Anggaran (Rp)",
                    min_value=0.0,
                    step=100_000.0,
                    format="%.0f",
                    help="Biarkan kosong bila kategori ini belum dianggarkan.",
                ),
            },
        )

        if st.button("Simpan anggaran", type="primary", key="save_budgets"):
            categories: dict[str, float | None] = {}
            for _, row in edited.iterrows():
                value = row["Anggaran"]
                categories[str(row["Kategori"])] = (
                    None if pd.isna(value) else float(value)
                )
            try:
                db.save_budgets(
                    connection,
                    month,
                    float(total_value) if set_total else None,
                    categories,
                )
            except Exception as exc:
                st.error(f"Anggaran gagal disimpan: {exc}")
            else:
                _next_revision()
                common.flash(f"Anggaran {month_label(month)} disimpan.")
                st.rerun()

    st.write("")
    st.subheader("Aktual dibanding anggaran")
    budget_categories = {
        key: value for key, value in budget_map.items() if key is not None
    }
    if not budget_categories:
        st.info("Belum ada anggaran per kategori untuk bulan ini.")
    else:
        comparison = analytics.budget_vs_actual_by_category(
            frame, month, budget_categories
        )
        display = comparison.copy()
        display["Aktual"] = display["actual"].map(format_rupiah)
        display["Anggaran"] = display["budget"].map(
            lambda value: format_rupiah(value) if pd.notna(value) else "Belum diatur"
        )
        display["Terpakai"] = display["percentage"].map(
            lambda value: f"{value:.0f}%" if pd.notna(value) else "—"
        )
        display["Sisa"] = display["remaining"].map(
            lambda value: format_rupiah(value) if pd.notna(value) else "—"
        )
        st.dataframe(
            display[
                ["category", "Aktual", "Anggaran", "Terpakai", "Sisa", "status"]
            ].rename(columns={"category": "Kategori", "status": "Status"}),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Status 'Melewati anggaran' hanya membandingkan aktual dengan anggaran, "
            "bukan penilaian atas keputusan finansial."
        )

    st.write("")
    st.subheader("Saran anggaran")
    suggestion = suggest_budgets(frame, today)
    if not suggestion.available:
        st.caption(suggestion.note)
        common.footer()
        return

    with st.expander("Lihat saran berdasarkan tiga bulan lengkap terakhir", expanded=True):
        st.caption(suggestion.note)
        suggestion_rows = pd.DataFrame(
            [
                {"Kategori": category, "Saran": format_rupiah(amount)}
                for category, amount in suggestion.suggestions.items()
            ]
        )
        st.dataframe(suggestion_rows, hide_index=True, width="stretch")
        total_text = (
            format_rupiah(suggestion.total_suggestion)
            if suggestion.total_suggestion is not None
            else "—"
        )
        st.markdown(f"**Saran anggaran total:** {total_text}")
        confirmed = st.checkbox(
            "Saya sudah meninjau saran ini dan ingin menyimpannya.",
            key=f"suggestion_confirm_{month}",
        )
        if st.button(
            "Terapkan saran sebagai anggaran",
            disabled=not confirmed,
            key=f"apply_suggestion_{month}",
        ):
            db.save_budgets(
                connection,
                month,
                suggestion.total_suggestion,
                {category: amount for category, amount in suggestion.suggestions.items()},
            )
            _next_revision()
            common.flash(
                f"Saran anggaran diterapkan untuk {month_label(month)}. "
                "Kamu masih bisa mengubahnya secara manual."
            )
            st.rerun()
    common.footer()
