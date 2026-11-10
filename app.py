import streamlit as st

from core import db_manager, theme

st.set_page_config(page_title="Portfolio Command Center", page_icon="⚡", layout="wide",
                   initial_sidebar_state="expanded")
theme.inject()
db_manager.init_db()

with st.sidebar:
    st.markdown('<div class="hero-title" style="font-size:1.15rem;color:#38bdf8">⚡ PORTFOLIO DESK</div>'
                '<div class="hero-sub">Webull auto-sync · Dime manual</div>', unsafe_allow_html=True)

# Exactly three flat links; sub-sections live in st.tabs inside each page.
nav = st.navigation([
    st.Page("pages/1_Executive_Dashboard.py", title="Executive Dashboard", icon="🏠", default=True),
    st.Page("pages/2_Webull.py", title="Webull Portfolio", icon="📈"),
    st.Page("pages/3_Dime.py", title="Dime Desk", icon="🧠"),
])
nav.run()
