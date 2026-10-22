"""Entry point Streamlit PennyPilot."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from pennypilot import db  # noqa: E402
from pennypilot.config import APP_NAME, APP_VERSION, get_db_path  # noqa: E402
from pennypilot.ui import common  # noqa: E402

PAGES = [
    "Dashboard",
    "Transaksi",
    "Impor CSV",
    "Anggaran",
    "Kategori & Aturan",
    "Pengaturan & Tentang",
]

PAGE_MODULES = {
    "Dashboard": "pennypilot.ui.dashboard",
    "Transaksi": "pennypilot.ui.transactions",
    "Impor CSV": "pennypilot.ui.import_page",
    "Anggaran": "pennypilot.ui.budgets_page",
    "Kategori & Aturan": "pennypilot.ui.rules_page",
    "Pengaturan & Tentang": "pennypilot.ui.settings_page",
}


@st.cache_resource(show_spinner=False)
def _get_connection(path: str):
    connection = db.connect(path)
    db.init_db(connection)
    return connection


def _sidebar(connection) -> str:
    with st.sidebar:
        st.markdown(
            '<div class="pp-brand">Penny<span>Pilot</span></div>'
            '<div class="pp-brand-sub">Keuangan lokal, tanpa cloud.</div>',
            unsafe_allow_html=True,
        )
        page = st.radio(
            "Navigasi",
            options=PAGES,
            key="nav",
            label_visibility="collapsed",
        )
        st.divider()
        count = db.count_transactions(connection)
        st.caption(f"{count:,} transaksi tersimpan".replace(",", "."))
        path = get_db_path()
        st.caption(f"Database: {path.name}")
        st.divider()
        st.caption(
            "Data finansial tetap di perangkat ini. Tidak ada telemetri atau API key."
        )
    return page


def main() -> None:
    st.set_page_config(
        page_title=f"{APP_NAME} · Keuangan lokal",
        page_icon=":material/account_balance_wallet:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    common.inject_css()
    db_path = get_db_path()
    try:
        connection = _get_connection(str(db_path))
    except Exception:
        st.error(
            "Database tidak dapat dibuka. Periksa izin folder dan pastikan lokasi "
            "database dapat ditulis."
        )
        st.code(str(db_path), language="text")
        st.caption(
            "Kamu bisa mengubah lokasi database lewat variabel lingkungan "
            "PENNYPILOT_DB_PATH."
        )
        st.stop()

    page = _sidebar(connection)
    common.render_flash()
    module = importlib.import_module(PAGE_MODULES[page])
    module.render(connection)
    st.caption(f"{APP_NAME} v{APP_VERSION}")


if __name__ == "__main__":
    main()
