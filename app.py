import os
import json
import base64
import importlib.util
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ตรวจสอบการ Import gspread สำหรับจัดการ Google Sheets
try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

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

        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            background-color: #08090b !important;
            color: #d1d5db;
        }

        .stApp {
            background-color: #08090b;
        }

        /* HIDE STREAMLIT DEFAULT NAVIGATION */
        [data-testid="stSidebarNav"] {
            display: none !important;
        }

        /* Custom Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #0d0e12 !important;
            border-right: 1px solid #181a20 !important;
        }

        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1rem;
        }

        .sidebar-brand {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.1rem;
            font-weight: 800;
            color: #38bdf8;
            padding: 10px 0px 15px 0px;
            letter-spacing: 1px;
            display: flex;
            align-items: center;
            gap: 8px;
            border-bottom: 1px solid #181a20;
            margin-bottom: 15px;
        }

        div[data-testid="stSidebar"] .stButton > button {
            background-color: #111318;
            color: #9ca3af;
            border: 1px solid #1f232d;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.85rem;
            transition: all 0.2s ease;
            text-align: left;
            padding: 8px 12px;
            margin-bottom: 2px;
        }

        div[data-testid="stSidebar"] .stButton > button:hover {
            border-color: #38bdf8;
            color: #38bdf8;
            background-color: #161a23;
        }

        div[data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: linear-gradient(90deg, #0284c7 0%, #0369a1 100%) !important;
            color: #ffffff !important;
            border: 1px solid #38bdf8 !important;
            box-shadow: 0 4px 12px rgba(56, 189, 248, 0.2);
        }

        div[data-testid="stSidebar"] .streamlit-expanderHeader {
            background-color: #111318 !important;
            border: 1px solid #1f232d !important;
            border-radius: 8px !important;
            color: #e2e8f0 !important;
            font-size: 0.88rem !important;
            font-weight: 700 !important;
            padding: 8px 12px !important;
        }

        div[data-testid="stSidebar"] .streamlit-expanderContent {
            background-color: transparent !important;
            border: none !important;
            padding: 8px 0px 0px 8px !important;
        }

        /* TICKER MARQUEE STYLING */
        .ticker-container {
            width: 100%;
            overflow: hidden;
            background-color: #0d0e12;
            border: 1px solid #1f232d;
            border-radius: 10px;
            padding: 8px 0;
            margin-bottom: 20px;
            white-space: nowrap;
        }

        .ticker-track {
            display: inline-flex;
            gap: 12px;
            animation: marquee 30s linear infinite;
        }

        .ticker-container:hover .ticker-track {
            animation-play-state: paused;
        }

        @keyframes marquee {
            0% { transform: translateX(0%); }
            100% { transform: translateX(-50%); }
        }

        .ticker-card-pill {
            background-color: #111318;
            border: 1px solid #1f232d;
            border-radius: 8px;
            padding: 6px 14px;
            font-size: 0.82rem;
            font-family: 'JetBrains Mono', monospace;
            display: inline-flex;
            align-items: center;
            gap: 10px;
        }

        .ticker-card-symbol { font-weight: 700; color: #ffffff; }
        .ticker-card-price { color: #e2e8f0; font-weight: 600; }
        .badge-mini-pos { background-color: rgba(34, 197, 94, 0.15); color: #4ade80; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; }
        .badge-mini-neg { background-color: rgba(239, 68, 68, 0.15); color: #f87171; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; }

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

        .badge-delta-neg { background-color: rgba(239, 68, 68, 0.12); color: #f87171; padding: 4px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
        .badge-delta-pos { background-color: rgba(34, 197, 94, 0.12); color: #4ade80; padding: 4px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; }

        .allocation-bar-container {
            display: flex;
            height: 10px;
            border-radius: 5px;
            overflow: hidden;
            margin: 14px 0px;
            background-color: #1a1d24;
        }
        .bar-segment { height: 100%; }

        .asset-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            font-size: 0.85rem;
            border-bottom: 1px solid #16181f;
        }
        .asset-label { display: flex; align-items: center; gap: 10px; color: #d1d5db; }
        .dot { width: 8px; height: 8px; border-radius: 50%; }
        .asset-val { font-family: 'JetBrains Mono', monospace; font-weight: 600; color: #ffffff; }

        .stock-grid-card {
            background-color: #111318;
            border: 1px solid #1a1d24;
            border-radius: 10px;
            padding: 14px;
            margin-bottom: 10px;
        }
        .stock-symbol { font-weight: 700; color: #ffffff; font-size: 0.9rem; }
        .stock-price { font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; font-weight: 700; color: #ffffff; margin-top: 6px; }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ==========================================
# 2. GOOGLE SHEETS DATA PIPELINE
# ==========================================
def get_gspread_client():
    """เชื่อมต่อ Google Sheets API จาก Secrets"""
    if not HAS_GSPREAD:
        return None
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=scopes
            )
            return gspread.authorize(creds)
    except Exception:
        pass
    return None

def sync_portfolio_snapshot_to_gsheet(market_val, invested_val, pnl_val, pnl_pct):
    """บันทึกแถวใหม่ลงใน Sheet Portfolio_History"""
    client = get_gspread_client()
    if not client:
        return False, "ไม่พบการเชื่อมต่อ GCP Service Account ใน st.secrets"
    
    sheet_title = st.secrets.get("SPREADSHEET_NAME", "Webull_Portfolio")
    try:
        sh = client.open(sheet_title)
        worksheet = sh.worksheet("Portfolio_History")
        
        # รูปแบบ Timestamp แบบในรูปของบอส: YYYY-MM-DD HH:MM:SS
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # แถวข้อมูล: Timestamp, Market Value, Invested, Return, Return %
        new_row = [now_str, round(market_val, 2), round(invested_val, 2), round(pnl_val, 2), f"{pnl_pct:.2f}%"]
        worksheet.append_row(new_row)
        return True, "บันทึกประวัติลง Google Sheets สำเร็จ!"
    except Exception as e:
        return False, f"เกิดข้อผิดพลาดในการเขียน Google Sheets: {str(e)}"

def load_history_from_gsheet():
    """ดึงข้อมูลประวัติย้อนหลังเพื่อวาดกราฟ"""
    client = get_gspread_client()
    if not client:
        return None
    try:
        sheet_title = st.secrets.get("SPREADSHEET_NAME", "Webull_Portfolio")
        sh = client.open(sheet_title)
        worksheet = sh.worksheet("Portfolio_History")
        data = worksheet.get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=["Timestamp", "MarketValue", "Invested", "PnL", "PnLPct"])
            df["MarketValue"] = pd.to_numeric(df["MarketValue"], errors='coerce')
            return df
    except Exception:
        pass
    return None

# ==========================================
# 3. DASHBOARD MAIN RENDER FUNCTION
# ==========================================
def render_dashboard():
    sample_stocks = [
        ("NU", 14.30, 18.48), ("SVCO", 7.93, 123.38), ("CV", 6.58, 31.60),
        ("DVLT", 0.34, -86.67), ("SUSCO", 3.85, 5.00), ("YMAG", 15.80, -0.19)
    ]
    
    ticker_cards_html = ""
    for sym, price, pnl in sample_stocks:
        badge_cls = "badge-mini-pos" if pnl >= 0 else "badge-mini-neg"
        sign = "+" if pnl >= 0 else ""
        ticker_cards_html += f"""<div class="ticker-card-pill"><span class="ticker-card-symbol">{sym}</span><span class="ticker-card-price">${price:,.2f}</span><span class="{badge_cls}">{sign}{pnl:.2f}%</span></div>"""

    full_track_html = f"""<div class="ticker-container"><div class="ticker-track">{ticker_cards_html}{ticker_cards_html}</div></div>"""
    st.markdown(full_track_html, unsafe_allow_html=True)

    c_title, c_curr = st.columns([3, 1])
    with c_title:
        st.title("Executive Dashboard")
    with c_curr:
        currency_selected = st.radio("Display Currency", ("USD ($)", "THB (฿)"), horizontal=True, index=0)

    usd_fx_rate = 35.5
    is_usd = "USD" in currency_selected
    symbol = "$" if is_usd else "฿"

    tot_invested_usd = 48180.96
    tot_market_usd = 43870.99
    tot_pnl_usd = tot_market_usd - tot_invested_usd
    tot_pnl_pct = (tot_pnl_usd / tot_invested_usd * 100) if tot_invested_usd > 0 else 0.0

    display_market = tot_market_usd if is_usd else (tot_market_usd * usd_fx_rate)
    display_pnl = tot_pnl_usd if is_usd else (tot_pnl_usd * usd_fx_rate)

    pnl_badge = "badge-delta-pos" if display_pnl >= 0 else "badge-delta-neg"
    pnl_sign = "+" if display_pnl >= 0 else ""

    st.markdown("<br>", unsafe_allow_html=True)
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
        tf_col1, tf_col2 = st.columns([3, 1])
        with tf_col1:
            selected_tf = st.select_slider("Timeframe Range", options=["1D", "7D", "1M", "3M", "6M", "1Y", "3Y", "5Y", "MAX"], value="6M")
        with tf_col2:
            st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)
            if st.button("🔄 Sync Snapshot", use_container_width=True, type="primary"):
                with st.spinner("⏳ กำลังบันทึกประวัติลง Portfolio_History..."):
                    success, msg = sync_portfolio_snapshot_to_gsheet(
                        tot_market_usd, tot_invested_usd, tot_pnl_usd, tot_pnl_pct
                    )
                    if success:
                        st.toast(f"✅ {msg}", icon="🎉")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        # ดึงข้อมูลจริงจาก Google Sheets
        df_history = load_history_from_gsheet()
        
        if df_history is not None and not df_history.empty:
            x_axis = df_history["Timestamp"].tolist()
            y_axis = (df_history["MarketValue"] if is_usd else (df_history["MarketValue"] * usd_fx_rate)).tolist()
        else:
            tf_points_map = {
                "1D": (['9:30', '11:00', '13:00', '15:00', '16:00'], [43500, 43700, 43600, 43800, display_market]),
                "7D": (['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], [42800, 43000, 42900, 43200, 43500, 43700, display_market]),
                "1M": (['W1', 'W2', 'W3', 'W4'], [41500, 42200, 43100, display_market]),
                "3M": (['May', 'Jun', 'Jul'], [40000, 42000, display_market]),
                "6M": (['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'], [42000, 45000, 41000, 46000, 44500, 47800, display_market]),
                "1Y": (['Q1', 'Q2', 'Q3', 'Q4'], [38000, 41000, 44000, display_market]),
                "3Y": (['2024', '2025', '2026'], [30000, 39000, display_market]),
                "5Y": (['2022', '2023', '2024', '2025', '2026'], [20000, 26000, 32000, 39000, display_market]),
                "MAX": (['Start', '2023', '2024', '2025', '2026'], [15000, 25000, 32000, 39000, display_market])
            }
            x_axis, y_axis = tf_points_map.get(selected_tf, tf_points_map["6M"])
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_axis, y=y_axis, mode='lines+markers', line=dict(color='#38bdf8', width=3, shape='spline'), fill='tozeroy', fillcolor='rgba(56, 189, 248, 0.05)'))
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#6b7280', family='Plus Jakarta Sans'), xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=True, gridcolor='#16181f', zeroline=False), margin=dict(t=10, b=10, l=10, r=10), height=250)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    c_btm_left, c_btm_right = st.columns([1.1, 1.9])
    with c_btm_left:
        st.markdown("""<div class="dash-card"><div class="card-header-title">Broker Allocation</div><div class="asset-row"><div class="asset-label">🇺🇸 Dime US</div><div class="asset-val">$25,000.00</div></div><div class="asset-row"><div class="asset-label">⚡ Webull US</div><div class="asset-val">$15,000.00</div></div><div class="asset-row" style="border-bottom:none;"><div class="asset-label">🇹🇭 Dime TH</div><div class="asset-val">$3,870.99</div></div></div>""", unsafe_allow_html=True)
    with c_btm_right:
        st.markdown('<div style="font-size: 0.85rem; font-weight: 600; color: #9ca3af; margin-bottom: 10px;">Top Holdings Performance</div>', unsafe_allow_html=True)
        g1, g2, g3 = st.columns(3)
        with g1: st.markdown('<div class="stock-grid-card"><div style="display:flex; justify-content:space-between; align-items:center;"><span class="stock-symbol">🟢 NU</span><span class="badge-delta-pos">+18.48%</span></div><div class="stock-price">$157.30</div></div>', unsafe_allow_html=True)
        with g2: st.markdown('<div class="stock-grid-card"><div style="display:flex; justify-content:space-between; align-items:center;"><span class="stock-symbol">🟢 SVCO</span><span class="badge-delta-pos">+123.38%</span></div><div class="stock-price">$7.93</div></div>', unsafe_allow_html=True)
        with g3: st.markdown('<div class="stock-grid-card"><div style="display:flex; justify-content:space-between; align-items:center;"><span class="stock-symbol">🔴 DVLT</span><span class="badge-delta-neg">-86.67%</span></div><div class="stock-price">$0.34</div></div>', unsafe_allow_html=True)

def load_page_module(file_name):
    possible_paths = [f"pages/{file_name}.py", f"pages/{file_name}"]
    target_path = None
    for path in possible_paths:
        if os.path.exists(path):
            target_path = path
            break
    if not target_path and os.path.exists("pages"):
        for f in os.listdir("pages"):
            if f.lower() == f"{file_name}.py".lower():
                target_path = os.path.join("pages", f)
                break

    if target_path:
        spec = importlib.util.spec_from_file_location("subpage_module", target_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        st.warning(f"⚠️ ไม่พบไฟล์ระบบย่อยที่ตำแหน่ง: `pages/{file_name}.py`")

# ==========================================
# 4. SIDEBAR NAVIGATION
# ==========================================
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Dashboard"

with st.sidebar:
    st.markdown('<div class="sidebar-brand">♾️ WEBULL DESK</div>', unsafe_allow_html=True)
    
    is_dash_active = "primary" if st.session_state["current_page"] == "Dashboard" else "secondary"
    if st.button("🏠 Executive Dashboard", use_container_width=True, type=is_dash_active):
        st.session_state["current_page"] = "Dashboard"
        st.rerun()

    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

    # --- SECTION 1.0 PORTFOLIO ---
    with st.expander("📁 Portfolio", expanded=True):
        if st.button("📊 Portfolio Holdings", use_container_width=True):
            st.session_state["current_page"] = "1.1_Portfolio"
            st.rerun()
        if st.button("⚡ Trade Execution", use_container_width=True):
            st.session_state["current_page"] = "1.2_Trade_Execution"
            st.rerun()
        if st.button("📜 Trade History", use_container_width=True):
            st.session_state["current_page"] = "1.3_History"
            st.rerun()
        if st.button("💰 Dividends", use_container_width=True):
            st.session_state["current_page"] = "1.4_Dividends"
            st.rerun()

    # --- SECTION 2.0 PORTFOLIO MANAGEMENT TOOLS ---
    with st.expander("🛠️ Portfolio Management Tools", expanded=True):
        if st.button("🎯 Winner Tilt", use_container_width=True):
            st.session_state["current_page"] = "2.1_Winner_Tilt"
            st.rerun()
        if st.button("🛡️ Portfolio Risk Desk", use_container_width=True):
            st.session_state["current_page"] = "2.2_Portfolio_Risk_Desk"
            st.rerun()
        if st.button("📐 MM Calculator", use_container_width=True):
            st.session_state["current_page"] = "2.3_MM_Calculator"
            st.rerun()
        if st.button("📰 Market News", use_container_width=True):
            st.session_state["current_page"] = "2.4_News"
            st.rerun()

    # --- SECTION 3.0 AI STOCK SELECTION & BUYING DECISIONS ---
    with st.expander("🧠 AI Stock Selection", expanded=True):
        if st.button("🎯 AI Fundamental (GOD MODE)", use_container_width=True):
            st.session_state["current_page"] = "3.1_AI_Fundamental"
            st.rerun()
        if st.button("💎 Diamond Hunter OS (v3.0)", use_container_width=True):
            st.session_state["current_page"] = "3.2_Diamond_Hunter"
            st.rerun()
        if st.button("🔍 Peer Comparison", use_container_width=True):
            st.session_state["current_page"] = "3.3_Peer_Comparison"
            st.rerun()
        if st.button("🧠 Multi-Brain Guru AI", use_container_width=True):
            st.session_state["current_page"] = "3.4_Multi_Brain_AI"
            st.rerun()

# ==========================================
# 5. PAGE SWITCHER ROUTER
# ==========================================
selected_page = st.session_state["current_page"]

if selected_page == "Dashboard":
    render_dashboard()
else:
    load_page_module(selected_page)
