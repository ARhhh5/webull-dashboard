import streamlit as st

from core import db_manager, theme

st.set_page_config(page_title="Portfolio Command Center", page_icon="⚡", layout="wide",
                   initial_sidebar_state="expanded")
theme.inject()
db_manager.init_db()

with st.sidebar:
    st.markdown('<div class="hero-title" style="font-size:1.15rem;color:#38bdf8">⚡ PORTFOLIO DESK</div>'
                '<div class="hero-sub">Webull auto-sync · Dime manual</div>', unsafe_allow_html=True)

nav = st.navigation({
    "Overview": [
        st.Page("pages/1_Executive_Dashboard.py", title="Executive Dashboard", icon="🏠", default=True),
    ],
    "Accounts": [
        st.Page("pages/2_Webull_Auto.py", title="Webull Portfolio", icon="⚡"),
        st.Page("pages/3_Dime_Manual_Desk.py", title="Dime Manual Desk", icon="✍️"),
    ],
})
nav.run()
