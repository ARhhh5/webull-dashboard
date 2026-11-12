from datetime import datetime, timezone
from functools import partial

import streamlit as st

from core import db_manager, theme

st.set_page_config(page_title="Portfolio Command Center", page_icon="⚡", layout="wide",
                   initial_sidebar_state="expanded")
theme.inject()
db_manager.init_db()

with st.sidebar:
    st.markdown('<div class="hero-title" style="font-size:1.15rem;color:#38bdf8">⚡ PORTFOLIO DESK</div>'
                '<div class="hero-sub">Webull auto-sync · Dime manual</div>', unsafe_allow_html=True)
    # Streamlit Cloud keeps portfolio.db only until the next restart/redeploy: download a copy to keep it.
    with st.expander("💾 Database backup"):
        info = db_manager.inspect_db(db_manager.DB_PATH)
        st.caption(f"Schema v{info['schema_version']} · integrity {info['integrity']} · "
                   + " · ".join(f"{t} {n}" for t, n in info["tables"].items()))
        stamp = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
        # Callable: the snapshot is taken (SQLite backup API, verified) only when the button is clicked.
        st.download_button("Download database backup", data=lambda: db_manager.backup_bytes(),
                           file_name=f"portfolio-v{info['schema_version']}-{stamp}.db",
                           mime="application/vnd.sqlite3", width="stretch", key="db_backup")
        for i, path in enumerate(db_manager.pre_migration_backups()[:1]):
            st.download_button("Download pre-migration backup", data=partial(db_manager.backup_bytes, source=path),
                               file_name=path.name, mime="application/vnd.sqlite3", width="stretch",
                               key=f"db_backup_pre_{i}", help="Automatic copy taken just before the schema migration.")

# Exactly three flat links; sub-sections live in st.tabs inside each page.
nav = st.navigation([
    st.Page("pages/1_Executive_Dashboard.py", title="Executive Dashboard", icon="🏠", default=True),
    st.Page("pages/2_Webull.py", title="Webull Portfolio", icon="📈"),
    st.Page("pages/3_Dime.py", title="Dime Desk", icon="🧠"),
])
nav.run()
