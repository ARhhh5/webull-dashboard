from datetime import datetime, timezone

import streamlit as st

from core import db_manager, theme

st.set_page_config(page_title="Portfolio Command Center", page_icon="⚡", layout="wide",
                   initial_sidebar_state="expanded")
theme.inject()
db_manager.init_db()

with st.sidebar:
    st.markdown('<div class="hero-title" style="font-size:1.15rem;color:#38bdf8">⚡ PORTFOLIO DESK</div>'
                '<div class="hero-sub">Webull auto-sync · Dime manual</div>', unsafe_allow_html=True)
    # On Streamlit Cloud the backups/ folder does not survive a redeploy, so offer a copy to keep locally.
    st.download_button("💾 Download database backup", data=db_manager.backup_bytes(),
                       file_name=f"portfolio-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.db",
                       mime="application/vnd.sqlite3", width="stretch", key="db_backup")

# Exactly three flat links; sub-sections live in st.tabs inside each page.
nav = st.navigation([
    st.Page("pages/1_Executive_Dashboard.py", title="Executive Dashboard", icon="🏠", default=True),
    st.Page("pages/2_Webull.py", title="Webull Portfolio", icon="📈"),
    st.Page("pages/3_Dime.py", title="Dime Desk", icon="🧠"),
])
nav.run()
