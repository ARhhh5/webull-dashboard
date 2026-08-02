import streamlit as st

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Webull Dashboard Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. GLOBAL MODERN DARK THEME (CUSTOM CSS)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        /* Import Font: Inter */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        /* Global Theme Setting */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            background-color: #0d0f12 !important;
            color: #e2e8f0;
        }

        /* App Background */
        .stApp {
            background-color: #0d0f12;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #131722 !important;
            border-right: 1px solid #1e222d;
        }

        /* Sidebar Header Title */
        [data-testid="stSidebarNav"]::before {
            content: "⚡ WEBULL PRO";
            margin-left: 20px;
            margin-top: 20px;
            font-size: 20px;
            font-weight: 700;
            color: #6366f1;
            letter-spacing: 1px;
            display: block;
            margin-bottom: 10px;
        }

        /* Card Container - Modern Dark Box */
        div[data-testid="stVerticalBlock"] > div[style*="flex"] {
            background-color: #161a25;
            border: 1px solid #222736;
            border-radius: 12px;
            padding: 16px;
        }

        /* Streamlit Metric Customization */
        div[data-testid="stMetric"] {
            background-color: #161a25;
            border: 1px solid #232838;
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        }

        div[data-testid="stMetricLabel"] {
            font-size: 0.85rem !important;
            color: #8b949e !important;
            font-weight: 500;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            color: #ffffff !important;
        }

        /* Custom Stat Card Class */
        .metric-card {
            background: linear-gradient(135deg, #181c28 0%, #12151e 100%);
            border: 1px solid #262c3d;
            border-radius: 14px;
            padding: 20px;
            margin-bottom: 15px;
        }

        .metric-title {
            color: #8b94a0;
            font-size: 0.85rem;
            font-weight: 500;
            margin-bottom: 6px;
        }

        .metric-value {
            color: #ffffff;
            font-size: 1.8rem;
            font-weight: 700;
        }

        .metric-delta-positive {
            color: #10b981;
            font-size: 0.85rem;
            font-weight: 600;
            margin-top: 4px;
        }

        .metric-delta-negative {
            color: #ef4444;
            font-size: 0.85rem;
            font-weight: 600;
            margin-top: 4px;
        }

        /* Tab Customization */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: #131722;
            padding: 6px;
            border-radius: 10px;
            border: 1px solid #1e222d;
        }

        .stTabs [data-baseweb="tab"] {
            height: 40px;
            white-space: pre-wrap;
            border-radius: 6px;
            color: #8b949e;
            font-weight: 500;
        }

        .stTabs [aria-selected="true"] {
            background-color: #6366f1 !important;
            color: #ffffff !important;
        }

        /* Plotly Background Matching */
        .js-plotly-plot .plotly .main-svg {
            background: transparent !important;
        }

        /* Hide Streamlit Default Header Footer */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# Apply CSS
inject_custom_css()

# ==========================================
# 3. MAIN DASHBOARD LANDING PAGE
# ==========================================
st.title("📊 Webull Financial Overview")
st.caption("ระบบบริหารจัดการพอร์ตและวิเคราะห์ข้อมูลการลงทุนแบบเรียลไทม์")

st.divider()

# Top Ticker Banner (Mockup / Live Dynamic Bar Style)
st.markdown("""
<div style="background-color: #131722; border: 1px solid #222736; border-radius: 10px; padding: 12px 20px; margin-bottom: 25px; display: flex; justify-content: space-between; align-items: center;">
    <span style="color: #10b981; font-weight: 600;">🟢 Market Open</span>
    <span><b>AAPL</b> <span style="color: #10b981;">$182.50 (+1.2%)</span></span>
    <span><b>TSLA</b> <span style="color: #ef4444;">$215.30 (-0.8%)</span></span>
    <span><b>NVDA</b> <span style="color: #10b981;">$875.20 (+3.4%)</span></span>
    <span><b>MSFT</b> <span style="color: #10b981;">$420.10 (+0.5%)</span></span>
</div>
""", unsafe_allow_html=True)

# KPI Overview Row
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    <div class="metric-card">
        <div class="metric-title">Total Portfolio Value</div>
        <div class="metric-value">$325,980.65</div>
        <div class="metric-delta-positive">▲ +$39,117.67 (12.0%)</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="metric-card">
        <div class="metric-title">Total Investments</div>
        <div class="metric-value">$270,560.20</div>
        <div class="metric-delta-positive">▲ +$54,112.04 (20.0%)</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="metric-card">
        <div class="metric-title">Unrealized P/L</div>
        <div class="metric-value">$55,420.45</div>
        <div class="metric-delta-positive">▲ +$9,879.43 (7.2%)</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class="metric-card">
        <div class="metric-title">Buying Power / Cash</div>
        <div class="metric-value">$18,450.00</div>
        <div style="color: #6b7280; font-size: 0.85rem; margin-top: 4px;">Ready to allocate</div>
    </div>
    """, unsafe_allow_html=True)

st.info("👈 กรุณาเลือกเมนูด้านซ้ายมือเพื่อเข้าสู่หน้าต่างวิเคราะห์ข้อมูลย่อย เช่น Portfolio, Winner Tilt, AI Fundamental หรือ Risk Desk")
