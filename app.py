import streamlit as st

# ==========================================
# 1. PAGE CONFIG & MODERN DARK CSS
# ==========================================
st.set_page_config(
    page_title="WEBULL DESK - Executive Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

    /* Global Dark Theme */
    .stApp {
        background-color: #090a0f;
        color: #e2e8f0;
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    /* Sidebar Custom Styling */
    section[data-testid="stSidebar"] {
        background-color: #0f1117 !important;
        border-right: 1px solid #1a1d26;
        width: 280px !important;
    }

    /* Custom Logo Title */
    .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 5px 20px 5px;
        font-size: 1.1rem;
        font-weight: 800;
        color: #38bdf8;
        letter-spacing: 0.5px;
    }

    /* Expander / Section Headers */
    div[data-testid="stSidebar"] .streamlit-expanderHeader {
        background-color: #141822 !important;
        border: 1px solid #1a1d26 !important;
        border-radius: 8px !important;
        color: #f1f5f9 !important;
        font-size: 0.85rem !important;
        font-weight: 700 !important;
        margin-bottom: 6px !important;
    }

    /* Sidebar Page Navigation Buttons */
    div[data-testid="stSidebar"] div.stButton > button {
        background-color: #0f1117 !important;
        border: 1px solid #1a1d26 !important;
        border-radius: 8px !important;
        color: #9ca3af !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        text-align: left !important;
        padding: 8px 12px !important;
        margin-bottom: 4px !important;
        transition: all 0.2s ease !important;
        width: 100% !important;
    }

    div[data-testid="stSidebar"] div.stButton > button:hover {
        border-color: #38bdf8 !important;
        color: #ffffff !important;
        background-color: #141822 !important;
    }

    div[data-testid="stSidebar"] div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
        border: 1px solid #f87171 !important;
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    /* Metric Card Styling */
    .metric-card-main {
        background-color: #0f1117;
        border: 1px solid #1a1d26;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
    }
    .metric-title {
        color: #9ca3af;
        font-size: 0.8rem;
        font-weight: 600;
        margin-bottom: 6px;
    }
    .metric-val {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.8rem;
        font-weight: 800;
        color: #ffffff;
    }
    .text-danger { color: #f87171 !important; }
    .text-success { color: #4ade80 !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CUSTOM SIDEBAR NAVIGATION ENGINE
# ==========================================
with st.sidebar:
    st.markdown('<div class="sidebar-brand">♾️ WEBULL DESK</div>', unsafe_allow_html=True)
    
    # Home / Executive Dashboard Button
    if st.button("🏠 Executive Dashboard", type="primary", use_container_width=True):
        st.switch_page("app.py")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- SECTION 1.0 PORTFOLIO ---
    with st.expander("📁 1.0 Portfolio", expanded=False):
        if st.button("📊 1.1 Portfolio Holdings", use_container_width=True):
            st.switch_page("pages/1.1_Portfolio.py")
        if st.button("⚡ 1.2 Trade Execution", use_container_width=True):
            st.switch_page("pages/1.2_Trade_Execution.py")
        if st.button("📜 1.3 Trade History", use_container_width=True):
            st.switch_page("pages/1.3_History.py")
        if st.button("💰 1.4 Dividends", use_container_width=True):
            st.switch_page("pages/1.4_Dividends.py")

    # --- SECTION 2.0 PORTFOLIO MANAGEMENT TOOLS ---
    with st.expander("🧠 2.0 Portfolio Management Tools", expanded=True):
        if st.button("🎯 2.1 Winner Tilt", use_container_width=True):
            st.switch_page("pages/2.1_Winner_Tilt.py")
        if st.button("🛡️ 2.2 Portfolio Risk Desk", use_container_width=True):
            st.switch_page("pages/2.2_Portfolio_Risk_Desk.py")
        if st.button("📐 2.3 MM Calculator", use_container_width=True):
            st.switch_page("pages/2.3_MM_Calculator.py")
        if st.button("📰 2.4 Market News", use_container_width=True):
            st.switch_page("pages/2.4_News.py")

    # --- SECTION 3.0 AI STOCK SELECTION & BUYING DECISIONS (NEW!) ---
    with st.expander("🎯 3.0 AI Stock Selection", expanded=True):
        if st.button("🧠 3.1 AI Fundamental (GOD MODE)", use_container_width=True):
            st.switch_page("pages/3.1_AI_Fundamental.py")
        if st.button("🔍 3.2 Peer Comparison", use_container_width=True):
            st.switch_page("pages/3.2_Peer_Comparison.py")

# ==========================================
# 3. EXECUTIVE DASHBOARD CONTENT
# ==========================================
st.title("Executive Dashboard")

c1, c2 = st.columns([1.5, 2.5])

with c1:
    st.markdown("""
        <div class="metric-card-main">
            <div class="metric-title">Portfolio value <span class="text-danger" style="float:right;">-8.95%</span></div>
            <div class="metric-val">$43,870.99</div>
            <div style="color: #f87171; font-size: 0.85rem; margin-top: 4px;">$-4,309.97 total return</div>
            <hr style="border-color: #1a1d26; margin: 15px 0;">
            <div style="font-size: 0.8rem; color: #9ca3af; margin-bottom: 8px;">Where your money is invested</div>
            <div style="display: flex; gap: 8px; font-size: 0.8rem; margin-top: 6px;">
                <span style="color: #38bdf8;">● Tech Stocks</span>
                <span style="margin-left: auto; font-weight: 700;">$28,516.14</span>
            </div>
            <div style="display: flex; gap: 8px; font-size: 0.8rem; margin-top: 6px;">
                <span style="color: #c084fc;">● ETFs & Index</span>
                <span style="margin-left: auto; font-weight: 700;">$8,774.20</span>
            </div>
            <div style="display: flex; gap: 8px; font-size: 0.8rem; margin-top: 6px;">
                <span style="color: #f472b6;">● Financials</span>
                <span style="margin-left: auto; font-weight: 700;">$4,387.10</span>
            </div>
            <div style="display: flex; gap: 8px; font-size: 0.8rem; margin-top: 6px;">
                <span style="color: #fbbf24;">● Cash & Other</span>
                <span style="margin-left: auto; font-weight: 700;">$2,193.55</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown('<div class="metric-card-main">', unsafe_allow_html=True)
    st.subheader("Performance Trend")
    st.caption("Timeframe Range: 6M")
    st.line_chart({"Portfolio Value": [42000, 45000, 41000, 44000, 47000, 43870]})
    st.markdown('</div>', unsafe_allow_html=True)
