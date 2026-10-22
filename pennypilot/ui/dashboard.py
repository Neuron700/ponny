"""Halaman dashboard bulanan."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import streamlit as st

from pennypilot import db
from pennypilot.ui import common
from pennypilot.utils import format_rupiah, month_bounds, month_label

if TYPE_CHECKING:
    import pandas as pd
    import plotly.graph_objects as go

TEAL = "#0f766e"
TERRACOTTA = "#c2703d"
INK = "#14201d"
GRID = "#e6e9e3"


def _category_figure(breakdown: pd.DataFrame) -> go.Figure:
    import plotly.graph_objects as go

    labels = breakdown["category"].tolist()
    values = breakdown["amount"].astype(float).tolist()
    hover = [format_rupiah(value) for value in values]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=TEAL,
            customdata=hover,
            hovertemplate="%{y}<br>%{customdata}<extra></extra>",
        )
    )
    figure.update_layout(
        title="Pengeluaran per kategori",
        height=360,
        margin=dict(l=10, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Pengeluaran (Rp)", gridcolor=GRID, tickprefix="Rp"),
        yaxis=dict(title=None, autorange="reversed"),
        font=dict(family="Segoe UI, sans-serif", color=INK),
        showlegend=False,
    )
    return figure


def _trend_figure(trend: pd.DataFrame) -> go.Figure:
    import plotly.graph_objects as go

    labels = [month_label(month) for month in trend["month"].tolist()]
    income = trend["income"].astype(float).tolist()
    expense = trend["expense"].astype(float).tolist()
    net = trend["net"].astype(float).tolist()
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            name="Pendapatan",
            x=labels,
            y=income,
            marker_color=TEAL,
            customdata=[format_rupiah(value) for value in income],
            hovertemplate="%{x}<br>Pendapatan %{customdata}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            name="Pengeluaran",
            x=labels,
            y=expense,
            marker_color=TERRACOTTA,
            customdata=[format_rupiah(value) for value in expense],
            hovertemplate="%{x}<br>Pengeluaran %{customdata}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            name="Arus kas bersih",
            x=labels,
            y=net,
            mode="lines+markers",
            line=dict(color=INK, width=2.5),
            marker=dict(size=7),
            customdata=[format_rupiah(value) for value in net],
            hovertemplate="%{x}<br>Bersih %{customdata}<extra></extra>",
        )
    )
    figure.update_layout(
        title="Tren pendapatan dan pengeluaran",
        height=360,
        margin=dict(l=10, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis=dict(title=None, gridcolor=GRID),
        yaxis=dict(title="Nominal (Rp)", gridcolor=GRID, tickprefix="Rp"),
        font=dict(family="Segoe UI, sans-serif", color=INK),
    )
    return figure


def _render_anomalies(frame, month: str) -> None:
    import pandas as pd

    from pennypilot.services.anomalies import detect_anomalies, summarize_statuses

    start, end = month_bounds(month)
    results = detect_anomalies(frame, start_date=start, end_date=end)
    unusual = [result for result in results if result.status == "unusual"]
    summary = summarize_statuses(results)

    st.subheader("Pengeluaran tidak biasa")
    st.caption(
        "Tanda ini berarti nominal relatif menyimpang dari riwayat kategori, "
        "bukan bukti kesalahan atau kecurangan. Lihat metode di Pengaturan & Tentang."
    )
    if unusual:
        st.info(
            f"{len(unusual)} pengeluaran perlu ditinjau pada {month_label(month)}. "
            "Semua baris disertai alasan dan data pembanding."
        )
        table = pd.DataFrame(
            [
                {
                    "Tanggal": result.transaction_date.strftime("%d/%m/%Y")
                    if result.transaction_date
                    else "",
                    "Deskripsi": result.description,
                    "Kategori": result.category,
                    "Nominal": format_rupiah(result.amount),
                    "Alasan": result.reason,
                }
                for result in unusual
            ]
        )
        st.dataframe(
            table,
            hide_index=True,
            width="stretch",
            column_config={
                "Alasan": st.column_config.TextColumn(width="large"),
                "Nominal": st.column_config.TextColumn(width="small"),
            },
        )
    else:
        st.caption("Tidak ada pengeluaran yang melewati ambang pada bulan ini.")

    if summary["insufficient"]:
        st.caption(
            f"{summary['insufficient']} transaksi berstatus 'Belum cukup data' karena "
            "baseline kategori belum mencapai 5 transaksi dalam 180 hari."
        )
    if summary["not_informative"]:
        st.caption(
            f"{summary['not_informative']} transaksi tidak dapat dinilai karena baseline "
            "kategori tidak informatif (median dan MAD nol)."
        )


def render(connection) -> None:
    common.page_header(
        "Ringkasan bulanan",
        "Dashboard",
        "Pantau arus kas, kategori terbesar, anggaran, dan pengeluaran yang perlu ditinjau.",
    )
    rows = db.list_transactions(connection)
    if not rows:
        common.empty_state(
            "Belum ada transaksi",
            "Mulai dengan mengimpor CSV milikmu atau muat dataset demo sintetis untuk "
            "melihat dashboard, anggaran, dan contoh deteksi pengeluaran tidak biasa.",
            page="Impor CSV",
        )
        st.write("")
        left, right = st.columns([1, 2])
        with left:
            common.load_demo_button(connection, key="dashboard_demo", label="Muat dataset demo")
        with right:
            st.caption(
                "Dataset demo berisi transaksi sintetis. Tidak ada data pribadi di dalamnya."
            )
        return

    import pandas as pd

    from pennypilot.services import analytics
    from pennypilot.services.budgets import budget_usage, current_projection_for_frame

    frame = analytics.to_frame(rows)
    months = analytics.available_months(frame)
    today = date.today()
    current_month = today.strftime("%Y-%m")
    default_month = current_month if current_month in months else months[0]
    left, right = st.columns([2, 1])
    with left:
        month = common.month_selectbox(
            months, key="dashboard_month", default=default_month
        )
    with right:
        st.caption(
            f"{len(months)} bulan tersedia · {len(frame):,} transaksi tersimpan".replace(
                ",", "."
            )
        )

    kpis = analytics.monthly_kpis(frame, month)
    columns = st.columns(4)
    columns[0].metric("Pendapatan", format_rupiah(kpis["income"]))
    columns[1].metric("Pengeluaran", format_rupiah(kpis["expense"]))
    columns[2].metric(
        "Arus kas bersih",
        format_rupiah(kpis["net"]),
        help="Pendapatan dikurangi pengeluaran pada bulan terpilih.",
    )
    columns[3].metric("Transaksi", f"{int(kpis['transaction_count'])}")

    budget_map = db.get_budget_map(connection, month)
    total_budget = budget_map.get(None)
    usage = budget_usage(float(kpis["expense"]), total_budget)
    projection = current_projection_for_frame(frame, month, today)

    budget_columns = st.columns(3)
    budget_columns[0].metric(
        "Anggaran bulan ini",
        format_rupiah(total_budget) if total_budget is not None else "Belum diatur",
        help="Atur anggaran total dan per kategori di halaman Anggaran.",
    )
    if usage.percentage is None:
        percentage_value = "—" if total_budget is None else "Tidak tersedia"
    else:
        percentage_value = f"{usage.percentage:.0f}%"
    budget_columns[1].metric(
        "Realisasi anggaran",
        percentage_value,
        delta=format_rupiah(usage.remaining) if usage.remaining is not None else None,
        delta_color="normal",
        help=(
            "Persentase pengeluaran terhadap anggaran. Anggaran nol atau belum diatur "
            "tidak dihitung sebagai persentase."
        ),
    )
    projection_label = "Total aktual" if projection.status == "final" else "Estimasi akhir bulan"
    budget_columns[2].metric(
        projection_label,
        format_rupiah(projection.projected) if projection.available else "Belum tersedia",
        help=projection.note,
    )

    if projection.available and total_budget is not None:
        projected_usage = budget_usage(projection.projected or 0.0, total_budget)
        if projected_usage.is_over and total_budget > 0:
            st.warning(
                f"Estimasi {format_rupiah(projection.projected)} melewati anggaran "
                f"{format_rupiah(total_budget)}. Ini ekstrapolasi sederhana, bukan kepastian."
            )
        elif projected_usage.is_over and total_budget == 0:
            st.warning(
                "Anggaran bulan ini Rp0, sementara masih ada pengeluaran. "
                "Periksa kembali anggaran bila perlu."
            )
    if projection.note:
        st.caption(projection.note)

    breakdown = analytics.category_breakdown(frame, month)
    st.write("")
    chart_left, chart_right = st.columns([1, 1])
    with chart_left:
        if breakdown.empty:
            st.info("Belum ada pengeluaran pada bulan ini.")
        else:
            st.plotly_chart(
                _category_figure(breakdown),
                width="stretch",
                config={"displayModeBar": False},
            )
    with chart_right:
        trend = analytics.monthly_trend(frame, end_month=month, months=6)
        st.plotly_chart(
            _trend_figure(trend),
            width="stretch",
            config={"displayModeBar": False},
        )

    table_left, table_right = st.columns([1, 1])
    with table_left:
        st.subheader("Kategori terbesar")
        if breakdown.empty:
            st.caption("Belum ada kategori pengeluaran pada bulan ini.")
        else:
            display = breakdown.head(8).copy()
            display["Pengeluaran"] = display["amount"].map(format_rupiah)
            display["Porsi"] = display["share"].map(lambda value: f"{value:.1f}%")
            st.dataframe(
                display[["category", "Pengeluaran", "Porsi"]].rename(
                    columns={"category": "Kategori"}
                ),
                hide_index=True,
                width="stretch",
            )
    with table_right:
        st.subheader("Anggaran per kategori")
        if not budget_map:
            st.caption("Belum ada anggaran untuk bulan ini.")
            st.button(
                "Atur anggaran",
                on_click=common._goto,
                args=("Anggaran",),
                key="dash_goto_budget",
            )
        else:
            category_budgets = {
                key: value for key, value in budget_map.items() if key is not None
            }
            comparison = analytics.budget_vs_actual_by_category(
                frame, month, category_budgets
            )
            if comparison.empty:
                st.caption("Belum ada kategori yang dianggarkan.")
            else:
                display = comparison[["category", "actual", "budget", "percentage", "status"]].copy()
                display["Aktual"] = display["actual"].map(format_rupiah)
                display["Anggaran"] = display["budget"].map(
                    lambda value: format_rupiah(value) if pd.notna(value) else "Belum diatur"
                )
                display["Terpakai"] = display["percentage"].map(
                    lambda value: f"{value:.0f}%" if pd.notna(value) else "—"
                )
                st.dataframe(
                    display[["category", "Aktual", "Anggaran", "Terpakai", "status"]].rename(
                        columns={"category": "Kategori", "status": "Status"}
                    ),
                    hide_index=True,
                    width="stretch",
                )

    st.write("")
    _render_anomalies(frame, month)
    common.footer()
