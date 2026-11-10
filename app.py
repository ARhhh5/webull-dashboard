import streamlit as st

from core import theme

st.set_page_config(page_title="Webull Dashboard", page_icon="⚡", layout="wide",
                   initial_sidebar_state="expanded")
theme.inject()

with st.sidebar:
    st.markdown('<div class="hero-title" style="font-size:1.15rem;color:#38bdf8">⚡ WEBULL DESK</div>'
                '<div class="hero-sub">Portfolio command center</div>', unsafe_allow_html=True)

nav = st.navigation([
    st.Page("pages/1_Webull_Dashboard.py", title="Webull Dashboard", icon="📊", default=True),
])
nav.run()
