import streamlit as st
import pandas as pd
import json
import base64
import gspread
import plotly.graph_objects as go

# ==========================================
# 1. PAGE CONFIGURATION & GLOBAL STYLE
# ==========================================
st.set_page_config(
    page_title="Executive Dashboard - Webull Desk",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

def inject_custom_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

        /* Global Theme */
        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            background-color: #08090b !important;
            color: #d1d5db;
        }

        .stApp {
            background-color: #08090b;
        }

        /* Custom Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #0d0e12 !important;
            border-right: 1px solid #181a20 !important;
        }

        /* Sidebar Brand Title */
        .sidebar-brand {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.1rem;
            font-weight: 800;
            color: #38bdf8;
            padding: 10px 0px 20px 0px;
            letter-spacing: 1px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* Navigation Expander Group Styling */
        [data-testid="stSidebar"] .stSectionHeader {
            font-weight: 700 !important;
            color: #9ca3af !important;
        }

        /* Top Ticker Scroll */
        .ticker-scroll {
            display: flex;
            gap: 12px;
            overflow-x: auto;
            padding-bottom: 5px;
            margin-bottom: 15px;
        }

        .ticker-pill {
            background-color: #111318;
            border: 1px solid #1f232d;
            border-radius: 8px;
            padding: 6px 14px;
            font-size: 0.8rem;
            font-family: 'JetBrains Mono', monospace;
            white-space: nowrap;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* Main Dashboard Cards */
        .dash-card {
            background-color: #0f1115;
            border: 1px solid #1a1d24;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
        }

        .card-header-title {
            color: #9ca3af;
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .big-value {
            font-family: 'Plus Jakarta Sans', sans-serif;
            font-size: 2.2rem;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -1px;
            line-height: 1.1;
        }

        .badge-delta-neg {
            background-color: rgba(239, 68, 68, 0.12);
            color: #f87171;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }

        .badge-delta-pos {
            background-color: rgba(34, 197, 94, 0.12);
            color: #4ade80;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }

        /* Multi-segment progress bar */
        .allocation-bar-container {
            display: flex;
            height: 10px;
            border-radius: 5px;
            overflow: hidden;
            margin: 14px 0px;
            background-color: #1a1d24;
        }

        .bar-segment {
            height: 100%;
        }

        .asset-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            font-size: 0.85rem;
            border-bottom: 1px solid #16181f;
        }

        .asset-label {
            display: flex;
            align-items: center;
            gap: 10px;
            color: #d1d5db;
        }

        .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        .asset-val {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: #ffffff;
        }

        /* Stock Mini Grid Card */
        .stock-grid-card {
            background-color: #111318;
            border: 1px solid #1a1d24;
            border-radius: 10px;
            padding: 14px;
            margin-bottom: 10px;
        }

        .stock-symbol {
            font-weight: 700;
            color: #ffffff;
            font-size: 0.9rem;
        }

        .stock-price {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.1rem;
            font-weight: 700;
            color: #ffffff;
            margin-top: 6px;
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ==========================================
# 2. DASHBOARD MAIN CONTENT FUNCTION
# ==========================================
def render_dashboard():
    # Data Cache Connection
    @st.cache_resource
    def get_gspread_client():
        try:
            google_secrets = st.secrets.get("Google", {})
            cred_base64 = google_secrets.get("credentials_base64", "")
            if cred_base64:
                cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
                return gspread.service_account_from_dict(cred_dict)
            return None
        except Exception:
            return None

    def load_summary_data():
        gc = get_gspread_client()
        if not gc:
            return pd.DataFrame(), pd.DataFrame()
        df_us, df_th = pd.DataFrame(), pd.DataFrame()
        try:
            sh = gc.open("หุ้นของเรา")
            try: df_us = pd.DataFrame(sh.worksheet("Dime_Portfolio").get_all_records())
            except: pass
            try: df_th = pd.DataFrame(sh.worksheet("Dime_TH_Portfolio").get_all_records())
            except: pass
        except Exception: pass
        return df_us, df_th

    df_us_raw, df_th_raw = load_summary_data()

    # Top Ticker Strip
    st.markdown("""
    <div class="ticker-scroll">
        <div class="ticker-pill"><span style="color:#4ade80;">🟢 Market</span> <span>NVDA $875.20 <span style="color:#4ade80;">+3.4%</span></span></div>
        <div class="ticker-pill"><span>TSLA $215.30 <span style="color:#f87171;">-0.8%</span></span></div>
        <div class="ticker-pill"><span>AAPL $182.50 <span style="color:#4ade80;">+1.2%</span></span></div>
        <div class="ticker-pill"><span>MSFT $420.10 <span style="color:#4ade80;">+0.5%</span></span></div>
        <div class="ticker-pill"><span>AMZN $178.35 <span style="color:#4ade80;">+2.1%</span></span></div>
    </div>
    """, unsafe_allow_html=True)

    # Title & Currency Control
    c_title, c_curr = st.columns([3, 1])
    with c_title:
        st.title("Executive Dashboard")
    with c_curr:
        currency_selected = st.radio(
            "Display Currency",
            ("USD ($)", "THB (฿)"),
            horizontal=True,
            index=0
        )

    usd_fx_rate = 35.5
    is_usd = "USD" in currency_selected
    symbol = "$" if is_usd else "฿"

    # Calculated Figures
    tot_invested_usd = 48180.96
    tot_market_usd = 43870.99
    tot_pnl_usd = tot_market_usd - tot_invested_usd
    tot_pnl_pct = (tot_pnl_usd / tot_invested_usd * 100) if tot_invested_usd > 0 else 0.0

    display_market = tot_market_usd if is_usd else (tot_market_usd * usd_fx_rate)
    display_pnl = tot_pnl_usd if is_usd else (tot_pnl_usd * usd_fx_rate)

    pnl_badge = "badge-delta-pos" if display_pnl >= 0 else "badge-delta-neg"
    pnl_sign = "+" if display_pnl >= 0 else ""

    st.markdown("<br>", unsafe_allow_html=True)

    # Grid Layout
    col_left, col_right = st.columns([1.1, 1.9])

    with col_left:
        card_html = f"""
        <div class="dash-card">
            <div class="card-header-title">
                <span>Portfolio value</span>
                <span class="{pnl_badge}">{pnl_sign}{tot_pnl_pct:.2f}%</span>
            </div>
            <div class="big-value">{symbol}{display_market:,.2f}</div>
            <div style="color: #f87171; font-size: 0.82rem; margin-top: 6px; font-family: 'JetBrains Mono', monospace;">
                {pnl_sign}{symbol}{display_pnl:,.2f} total return
            </div>
            <div style="margin-top: 20px; font-size: 0.8rem; color: #6b7280; font-weight: 600;">Where your money is invested</div>
            <div class="allocation-bar-container">
                <div class="bar-segment" style="width: 65%; background-color: #3b82f6;"></div>
                <div class="bar-segment" style="width: 20%; background-color: #a855f7;"></div>
                <div class="bar-segment" style="width: 10%; background-color: #ec4899;"></div>
                <div class="bar-segment" style="width: 5%; background-color: #f59e0b;"></div>
            </div>
            <div class="asset-row">
                <div class="asset-label"><div class="dot" style="background-color: #3b82f6;"></div> Tech Stocks</div>
                <div class="asset-val">{symbol}{display_market*0.65:,.2f}</div>
            </div>
            <div class="asset-row">
                <div class="asset-label"><div class="dot" style="background-color: #a855f7;"></div> ETFs & Index</div>
                <div class="asset-val">{symbol}{display_market*0.20:,.2f}</div>
            </div>
            <div class="asset-row">
                <div class="asset-label"><div class="dot" style="background-color: #ec4899;"></div> Financials</div>
                <div class="asset-val">{symbol}{display_market*0.10:,.2f}</div>
            </div>
            <div class="asset-row" style="border-bottom: none;">
                <div class="asset-label"><div class="dot" style="background-color: #f59e0b;"></div> Cash & Other</div>
                <div class="asset-val">{symbol}{display_market*0.05:,.2f}</div>
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

    with col_right:
        chart_header = """
        <div class="dash-card" style="padding-bottom: 5px;">
            <div class="card-header-title">
                <span>Value trend & impact</span>
                <span style="font-family: 'JetBrains Mono'; font-size: 0.75rem; color: #6b7280;">1D  7D  1M  <span style="color:#38bdf8; font-weight:700;">6M</span>  1Y</span>
            </div>
        </div>
        """
        st.markdown(chart_header, unsafe_allow_html=True)
        
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul']
        trend_vals = [42000, 45000, 41000, 46000, 44500, 47800, tot_market_usd]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=months, y=trend_vals, mode='lines',
            line=dict(color='#38bdf8', width=3, shape='spline'),
            fill='tozeroy', fillcolor='rgba(56, 189, 248, 0.05)'
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#6b7280', family='Plus Jakarta Sans'),
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(showgrid=True, gridcolor='#16181f', zeroline=False),
            margin=dict(t=5, b=10, l=10, r=10), height=270
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # Bottom Cards
    c_btm_left, c_btm_right = st.columns([1.1, 1.9])
    with c_btm_left:
        broker_html = """
        <div class="dash-card">
            <div class="card-header-title">Broker Allocation</div>
            <div class="asset-row"><div class="asset-label">🇺🇸 Dime US</div><div class="asset-val">$25,000.00</div></div>
            <div class="asset-row"><div class="asset-label">⚡ Webull US</div><div class="asset-val">$15,000.00</div></div>
            <div class="asset-row" style="border-bottom:none;"><div class="asset-label">🇹🇭 Dime TH</div><div class="asset-val">$3,870.99</div></div>
        </div>
        """
        st.markdown(broker_html, unsafe_allow_html=True)

    with c_btm_right:
        st.markdown('<div style="font-size: 0.85rem; font-weight: 600; color: #9ca3af; margin-bottom: 10px;">Top Holdings Performance</div>', unsafe_allow_html=True)
        g1, g2, g3 = st.columns(3)
        with g1:
            st.markdown('<div class="stock-grid-card"><div style="display:flex; justify-between; align-items:center;"><span class="stock-symbol">🟢 NVDA</span><span class="badge-delta-pos" style="margin-left:auto;">+9.10%</span></div><div class="stock-price">$892,812.00</div></div>', unsafe_allow_html=True)
        with g2:
            st.markdown('<div class="stock-grid-card"><div style="display:flex; justify-between; align-items:center;"><span class="stock-symbol">🔴 ABNB</span><span class="badge-delta-neg" style="margin-left:auto;">-3.89%</span></div><div class="stock-price">$92,900.00</div></div>', unsafe_allow_html=True)
        with g3:
            st.markdown('<div class="stock-grid-card"><div style="display:flex; justify-between; align-items:center;"><span class="stock-symbol">🟢 AMZN</span><span class="badge-delta-pos" style="margin-left:auto;">+2.67%</span></div><div class="stock-price">$854,414.00</div></div>', unsafe_allow_html=True)

# ==========================================
# 3. MODERN COLLAPSIBLE SIDEBAR NAVIGATION
# ==========================================
with st.sidebar:
    st.markdown('<div class="sidebar-brand">♾️ WEBULL DESK</div>', unsafe_allow_html=True)
    
    # 1. Main Overview Button
    if st.button("🏠 Executive Dashboard", use_container_width=True, type="primary"):
        st.session_state["current_page"] = "Dashboard"

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Portfolio Management Group (Collapsible Expander)
    with st.expander("📂 Portfolio Management", expanded=True):
        if st.button("📊 Portfolio Holdings", use_container_width=True):
            st.session_state["current_page"] = "Portfolio"
        if st.button("⚡ Trade Execution", use_container_width=True):
            st.session_state["current_page"] = "Trade Execution"
        if st.button("📜 Trade History", use_container_width=True):
            st.session_state["current_page"] = "History"
        if st.button("💰 Dividends", use_container_width=True):
            st.session_state["current_page"] = "Dividends"

    # 3. AI Analytics Group (Collapsible Expander)
    with st.expander("🧠 AI & Analytics", expanded=False):
        if st.button("🎯 Winner Tilt", use_container_width=True):
            st.session_state["current_page"] = "Winner Tilt"
        if st.button("🤖 AI Fundamental", use_container_width=True):
            st.session_state["current_page"] = "AI Fundamental"
        if st.button("🛡️ Portfolio Risk Desk", use_container_width=True):
            st.session_state["current_page"] = "Risk Desk"
        if st.button("🧮 MM Calculator", use_container_width=True):
            st.session_state["current_page"] = "MM Calculator"

# Initialize Session State Page
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Dashboard"

# Page Switcher Router
selected_page = st.session_state["current_page"]

if selected_page == "Dashboard":
    render_dashboard()
elif selected_page == "Portfolio":
    st.title("📊 Portfolio Holdings")
    st.info("ระบบกำลังเชื่อมต่อหน้านี้เข้ากับไฟล์ pages/portfolio.py")
elif selected_page == "Trade Execution":
    st.title("⚡ Trade Execution")
    st.info("ระบบกำลังเชื่อมต่อหน้านี้เข้ากับไฟล์ pages/trade_execution.py")
elif selected_page == "History":
    st.title("📜 Trade History")
    st.info("ระบบกำลังเชื่อมต่อหน้านี้เข้ากับไฟล์ pages/history.py")
elif selected_page == "AI Fundamental":
    st.title("🤖 AI Fundamental Analysis")
    st.info("ระบบกำลังเชื่อมต่อหน้านี้เข้ากับไฟล์ pages/ai_fundamental.py")
else:
    st.title(f"📌 {selected_page}")
    st.caption("หน้าต่างแสดงผลระบบย่อย")
