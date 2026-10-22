"""Komponen UI bersama dan pemformatan tampilan."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import TYPE_CHECKING, Any

import streamlit as st

from pennypilot.config import SOURCE_LABELS, TYPE_LABELS
from pennypilot.utils import format_rupiah, month_label, month_range, shift_month

if TYPE_CHECKING:
    import pandas as pd

CSS = """
<style>
:root {
  --pp-ink: #14201d;
  --pp-muted: #5d6b66;
  --pp-line: #e1e6df;
  --pp-card: #ffffff;
  --pp-bg: #f5f4ef;
  --pp-accent: #0f766e;
  --pp-accent-soft: #dcefe9;
  --pp-warn: #a15c00;
  --pp-warn-soft: #fff1d8;
  --pp-danger: #a83232;
}
html, body, [class*="css"] {
  font-family: "Segoe UI", "Inter", system-ui, -apple-system, sans-serif;
}
.stApp {
  background:
    radial-gradient(circle at 92% 2%, rgba(15, 118, 110, 0.08), transparent 28rem),
    var(--pp-bg);
  color: var(--pp-ink);
}
.block-container {
  padding-top: 2rem;
  padding-bottom: 4rem;
  max-width: 1240px;
}
[data-testid="stSidebar"] {
  background: #fbfaf7;
  border-right: 1px solid var(--pp-line);
}
[data-testid="stSidebar"] .block-container { padding-top: 1.4rem; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label {
  color: var(--pp-ink);
}
.pp-brand {
  font-size: 1.55rem;
  font-weight: 750;
  letter-spacing: -0.04em;
  color: var(--pp-ink);
  margin-bottom: 0.1rem;
}
.pp-brand span { color: var(--pp-accent); }
.pp-brand-sub {
  color: var(--pp-muted);
  font-size: 0.8rem;
  margin-bottom: 1.2rem;
}
.pp-hero {
  padding: 1.55rem 1.7rem 1.45rem;
  border: 1px solid var(--pp-line);
  border-radius: 20px;
  background:
    linear-gradient(120deg, rgba(15, 118, 110, 0.10), rgba(255, 255, 255, 0.92) 55%),
    #ffffff;
  margin-bottom: 1.2rem;
}
.pp-kicker {
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.69rem;
  font-weight: 700;
  color: var(--pp-accent);
  margin-bottom: 0.45rem;
}
.pp-hero h1 {
  margin: 0;
  font-size: clamp(1.7rem, 3vw, 2.35rem);
  letter-spacing: -0.04em;
  line-height: 1.1;
  color: var(--pp-ink);
}
.pp-hero p {
  margin: 0.55rem 0 0;
  color: var(--pp-muted);
  max-width: 46rem;
  line-height: 1.55;
}
[data-testid="stMetric"] {
  background: var(--pp-card);
  border: 1px solid var(--pp-line);
  border-radius: 16px;
  padding: 0.95rem 1.05rem;
  box-shadow: 0 1px 2px rgba(20, 32, 29, 0.03);
}
[data-testid="stMetricLabel"] p {
  color: var(--pp-muted);
  font-size: 0.82rem;
  font-weight: 600;
}
[data-testid="stMetricValue"] {
  color: var(--pp-ink);
  font-weight: 720;
  letter-spacing: -0.035em;
  font-variant-numeric: tabular-nums;
}
.pp-pill {
  display: inline-block;
  border-radius: 999px;
  padding: 0.16rem 0.62rem;
  font-size: 0.76rem;
  font-weight: 700;
  border: 1px solid var(--pp-line);
  background: #f3f4f1;
  color: var(--pp-ink);
}
.pp-pill.warn { background: var(--pp-warn-soft); border-color: #f0d3a4; color: var(--pp-warn); }
.pp-pill.good { background: var(--pp-accent-soft); border-color: #b9ded5; color: #0a5f58; }
.pp-pill.bad { background: #fbe4e4; border-color: #f0c3c3; color: var(--pp-danger); }
.pp-empty {
  text-align: center;
  padding: 2.6rem 1.5rem;
  border: 1px dashed #c9d2ca;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.62);
}
.pp-empty h3 { margin: 0 0 0.4rem; letter-spacing: -0.02em; }
.pp-empty p { color: var(--pp-muted); margin: 0 auto 1rem; max-width: 34rem; }
.pp-note {
  font-size: 0.8rem;
  color: var(--pp-muted);
  line-height: 1.5;
}
.pp-footer {
  margin-top: 2.5rem;
  border-top: 1px solid var(--pp-line);
  padding-top: 1rem;
  color: var(--pp-muted);
  font-size: 0.78rem;
}
div[data-testid="stExpander"] {
  border-color: var(--pp-line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.65);
}
.stButton > button, .stDownloadButton > button {
  border-radius: 10px;
  font-weight: 600;
}
.stButton > button[kind="primary"] {
  background: var(--pp-accent);
  border-color: var(--pp-accent);
}
.stButton > button[kind="primary"]:hover {
  background: #0b615a;
  border-color: #0b615a;
}
[data-testid="stDataFrame"] {
  border: 1px solid var(--pp-line);
  border-radius: 14px;
  overflow: hidden;
  background: #ffffff;
}
[data-testid="stAlert"] { border-radius: 12px; }
hr { border-color: var(--pp-line) !important; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="pp-hero">
          <div class="pp-kicker">{kicker}</div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def flash(message: str, kind: str = "success") -> None:
    st.session_state["_pp_flash"] = (message, kind)


def render_flash() -> None:
    payload = st.session_state.pop("_pp_flash", None)
    if not payload:
        return
    message, kind = payload
    if kind == "error":
        st.error(message)
    elif kind == "warning":
        st.warning(message)
    elif kind == "info":
        st.info(message)
    else:
        st.success(message)


def empty_state(title: str, message: str, *, page: str | None = None) -> None:
    st.markdown(
        f"""
        <div class="pp-empty">
          <h3>{title}</h3>
          <p>{message}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if page:
        st.button(
            "Buka halaman Impor CSV",
            on_click=_goto,
            args=(page,),
            type="primary",
            key=f"empty_goto_{page}",
        )


def _goto(page: str) -> None:
    st.session_state["nav"] = page


def load_demo_button(connection, *, key: str, label: str = "Muat dataset demo") -> None:
    if st.button(label, type="primary", key=key):
        from pennypilot.services.csv_import import load_demo_data

        try:
            analysis, imported = load_demo_data(connection)
        except Exception as exc:  # pesan ramah, tanpa detail sensitif
            st.error(f"Dataset demo gagal dimuat: {exc}")
            return
        if imported:
            flash(
                f"{imported} transaksi demo dimuat. "
                f"{analysis.duplicate_count} kandidat duplikat dilewati."
            )
        elif analysis.duplicate_count:
            flash("Semua transaksi demo sudah ada di database.", "info")
        else:
            flash("Tidak ada transaksi demo yang bisa dimuat.", "warning")
        st.rerun()


def demo_months() -> list[str]:
    current = date.today().strftime("%Y-%m")
    return sorted(
        set(month_range(shift_month(current, 1), 15)) | {current},
        reverse=True,
    )


def display_month_options() -> list[str]:
    return demo_months()


def signed_amount(row: Any) -> str:
    amount = float(row["amount"])
    if row["transaction_type"] == "income":
        return f"+{format_rupiah(amount)}"
    return f"-{format_rupiah(amount)}"


def transaction_table(rows: Iterable[Any]) -> pd.DataFrame:
    import pandas as pd

    records: list[dict[str, str]] = []
    for row in rows:
        records.append(
            {
                "Tanggal": date.fromisoformat(str(row["transaction_date"])).strftime("%d/%m/%Y"),
                "Deskripsi": str(row["description"]),
                "Tipe": TYPE_LABELS.get(str(row["transaction_type"]), str(row["transaction_type"])),
                "Kategori": str(row["category"]),
                "Nominal": signed_amount(row),
                "Sumber Kategori": SOURCE_LABELS.get(
                    str(row["category_source"]), str(row["category_source"])
                ),
            }
        )
    return pd.DataFrame(
        records,
        columns=[
            "Tanggal",
            "Deskripsi",
            "Tipe",
            "Kategori",
            "Nominal",
            "Sumber Kategori",
        ],
    )


def month_selectbox(
    months: list[str],
    *,
    key: str,
    label: str = "Pilih bulan",
    default: str | None = None,
) -> str:
    index = 0
    if default and default in months:
        index = months.index(default)
    return st.selectbox(
        label,
        options=months,
        index=index,
        format_func=month_label,
        key=key,
    )


def status_text(text: str, tone: str = "neutral") -> str:
    css_class = {"warn": "warn", "good": "good", "bad": "bad"}.get(tone, "")
    return f'<span class="pp-pill {css_class}">{text}</span>'


def footer() -> None:
    st.markdown(
        """
        <div class="pp-footer">
          PennyPilot menyimpan data secara lokal di SQLite. Tidak ada telemetri,
          akun, atau koneksi ke layanan eksternal.
        </div>
        """,
        unsafe_allow_html=True,
    )
