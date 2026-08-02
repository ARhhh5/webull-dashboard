import os
import json
import base64
import urllib.parse
import http.client
import uuid
import hmac
import hashlib
import importlib.util
from datetime import datetime, timezone
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import gspread

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

        /* Global Canvas Theme */
        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            background-color: #08090b !important;
            color: #d1d5db;
        }

        .stApp {
            background-color: #08090b;
        }

        /* CRITICAL: HIDE STREAMLIT DEFAULT NAVIGATION */
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

        /* Sidebar Brand Title */
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

        /* Custom Sidebar Buttons */
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

        /* Expander Custom Styling */
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

        /* ------------------------------------------------ */
        /* INFINITE RUNNING TICKER MARQUEE                  */
        /* ------------------------------------------------ */
        .ticker-container {
            width: 100%;
            overflow: hidden;
            background-color: #0d0e12;
            border: 1px solid #1f232d;
            border-radius: 10px;
            padding: 8px 0;
            margin-bottom: 20px;
            white-space: nowrap;
            position: relative;
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

        .ticker-card-symbol {
            font-weight: 700;
            color: #ffffff;
        }

        .ticker-card-price {
            color: #e2e8f0;
            font-weight: 600;
        }

        .badge-mini-pos {
            background-color: rgba(34, 197, 94, 0.15);
            color: #4ade80;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
        }

        .badge-mini-neg {
            background-color: rgba(239, 68, 68, 0.15);
            color: #f87171;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
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
# 2. DATA PIPELINE & GOOGLE SHEETS SERVICES
# ==========================================
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

def fetch_portfolio_stock_data():
    gc = get_gspread_client()
    holdings = []
    sh_obj = None
    if gc:
        try:
            sh_obj = gc.open("หุ้นของเรา")
            # Fetch Dime US
            try:
                ws_us = sh_obj.worksheet("Dime_Portfolio")
                for r in ws_us.get_all_records():
                    sym = str(r.get("หุ้น (Ticker)", "")).strip().upper()
                    if sym:
                        holdings.append({
                            "Symbol": sym,
                            "Qty": float(r.get("จำนวนหุ้น (Volume)", 0)),
                            "Cost": float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0)),
                            "Broker": "Dime US"
                        })
            except Exception: pass
            
            # Fetch Dime TH
            try:
                ws_th = sh_obj.worksheet("Dime_TH_Portfolio")
                for r in ws_th.get_all_records():
                    sym = str(r.get("หุ้น (Ticker)", "")).strip().upper()
                    if sym:
                        holdings.append({
                            "Symbol": sym,
                            "Qty": float(r.get("จำนวนหุ้น (Volume)", 0)),
                            "Cost": float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0)),
                            "Broker": "Dime TH"
                        })
            except Exception: pass
        except Exception: pass
    return pd.DataFrame(holdings), sh_obj

# ==========================================
# 3. DASHBOARD MAIN RENDER FUNCTION
# ==========================================
def render_dashboard():
    df_holdings, sh_obj = fetch_portfolio_stock_data()

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

    # Process Ticker Cards Data (Price & PnL%)
    ticker_cards_html = ""
    
    if not df_holdings.empty:
        # Group by Symbol to aggregate cost & volume
        grouped_stocks = []
        for sym, group in df_holdings.groupby("Symbol"):
            tot_qty = group["Qty"].sum()
            avg_cost = (group["Qty"] * group["Cost"]).sum() / tot_qty if tot_qty > 0 else 0
            grouped_stocks.append({"Symbol": sym, "Qty": tot_qty, "Cost": avg_cost})
        
        df_ticker_stocks = pd.DataFrame(grouped_stocks)
        
        # Mock/Fetch Prices for Stock Ticker Cards
        default_prices = {
            "PG": 162.40, "YMAG": 15.80, "QQQM": 182.50, "CYN": 24.10, 
            "ETOR": 68.20, "INM": 5.10, "SCHG": 36.80, "SLDE": 24.50, 
            "JEPQ": 55.40, "CHPY": 91.20, "QQQI": 56.80, "NVDA": 875.20, "AMZN": 178.35
        }

        for idx, row in df_ticker_stocks.iterrows():
            sym = row["Symbol"]
            cost = row["Cost"]
            price = default_prices.get(sym, cost * 1.05 if cost > 0 else 100.0)
            
            pnl_pct = ((price - cost) / cost * 100) if cost > 0 else 0.0
            badge_class = "badge-mini-pos" if pnl_pct >= 0 else "badge-mini-neg"
            pnl_sign = "+" if pnl_pct >= 0 else ""
            
            card_item = f"""
            <div class="ticker-card-pill">
                <span class="ticker-card-symbol">{sym}</span>
                <span class="ticker-card-price">${price:,.2f}</span>
                <span class="{badge_class}">{pnl_sign}{pnl_pct:.2f}%</span>
            </div>
            """
            ticker_cards_html += card_item
    else:
        # Default Fallback Display if Sheet empty
        sample_data = [
            ("NVDA", 875.20, 9.10), ("TSLA", 215.30, -0.80), ("AAPL", 182.50, 1.20),
            ("MSFT", 420.10, 0.50), ("AMZN", 178.35, 2.10), ("QQQM", 182.50, 3.40)
        ]
        for sym, price, pnl_pct in sample_data:
            badge_class = "badge-mini-pos" if pnl_pct >= 0 else "badge-mini-neg"
            pnl_sign = "+" if pnl_pct >= 0 else ""
            ticker_cards_html += f"""
            <div class="ticker-card-pill">
                <span class="ticker-card-symbol">{sym}</span>
                <span class="ticker-card-price">${price:,.2f}</span>
                <span class="{badge_class}">{pnl_sign}{pnl_pct:.2f}%</span>
            </div>
            """

    # Render Infinite Running Marquee Top Strip
    full_track_html = f"""
    <div class="ticker-container">
        <div class="ticker-track">
            {ticker_cards_html}
            {ticker_cards_html}
        </div>
    </div>
    """
    st.markdown(full_track_html, unsafe_allow_html=True)

    # Portfolio Totals
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
        # Timeframe Filter & Sync Button Bar
        tf_col1, tf_col2 = st.columns([3, 1])
        with tf_col1:
            selected_tf = st.select_slider(
                "Timeframe Range",
                options=["1D", "7D", "1M", "3M", "6M", "1Y", "3Y", "5Y", "MAX"],
                value="6M"
            )
        with tf_col2:
            st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)
            if st.button("🔄 Sync Snapshot", use_container_width=True, help="อัปเดตมูลค่าพอร์ตลง Google Sheets"):
                if sh_obj:
                    try:
                        try:
                            ws_hist = sh_obj.worksheet("Portfolio_History")
                        except Exception:
                            ws_hist = sh_obj.add_worksheet(title="Portfolio_History", rows="1000", cols="5")
                            ws_hist.append_row(["Timestamp", "Total_Market_USD", "Total_Invested_USD", "PnL_USD", "PnL_Pct"])
                        
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ws_hist.append_row([now_str, tot_market_usd, tot_invested_usd, tot_pnl_usd, f"{tot_pnl_pct:.2f}%"])
                        st.toast("✅ บันทึกประวัติลง Google Sheets สำเร็จ!", icon="🎉")
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในการ Sync: {e}")
                else:
                    st.warning("ไม่สามารถเชื่อมต่อ Google Sheets ได้")

        # Trend Chart Simulation base on timeframe
        tf_points_map = {
            "1D": (['9:30', '11:00', '13:00', '15:00', '16:00'], [43500, 43700, 43600, 43800, tot_market_usd]),
            "7D": (['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], [42800, 43000, 42900, 43200, 43500, 43700, tot_market_usd]),
            "1M": (['W1', 'W2', 'W3', 'W4'], [41500, 42200, 43100, tot_market_usd]),
            "3M": (['May', 'Jun', 'Jul'], [40000, 42000, tot_market_usd]),
            "6M": (['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'], [42000, 45000, 41000, 46000, 44500, 47800, tot_market_usd]),
            "1Y": (['Q1', 'Q2', 'Q3', 'Q4'], [38000, 41000, 44000, tot_market_usd]),
            "3Y": (['2024', '2025', '2026'], [30000, 39000, tot_market_usd]),
            "5Y": (['2022', '2023', '2024', '2025', '2026'], [20000, 26000, 32000, 39000, tot_market_usd]),
            "MAX": (['Start', '2023', '2024', '2025', '2026'], [15000, 25000, 32000, 39000, tot_market_usd])
        }
        
        x_axis, y_axis = tf_points_map.get(selected_tf, tf_points_map["6M"])
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x_axis, y=y_axis, mode='lines+markers',
            line=dict(color='#38bdf8', width=3, shape='spline'),
            fill='tozeroy', fillcolor='rgba(56, 189, 248, 0.05)'
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#6b7280', family='Plus Jakarta Sans'),
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(showgrid=True, gridcolor='#16181f', zeroline=False),
            margin=dict(t=10, b=10, l=10, r=10), height=250
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

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
            st.markdown('<div class="stock-grid-card"><div style="display:flex; justify-content:space-between; align-items:center;"><span class="stock-symbol">🟢 NVDA</span><span class="badge-delta-pos">+9.10%</span></div><div class="stock-price">$892,812.00</div></div>', unsafe_allow_html=True)
        with g2:
            st.markdown('<div class="stock-grid-card"><div style="display:flex; justify-between; align-items:center;"><span class="stock-symbol">🔴 ABNB</span><span class="badge-delta-neg">+3.89%</span></div><div class="stock-price">$92,900.00</div></div>', unsafe_allow_html=True)
        with g3:
            st.markdown('<div class="stock-grid-card"><div style="display:flex; justify-between; align-items:center;"><span class="stock-symbol">🟢 AMZN</span><span class="badge-delta-pos">+2.67%</span></div><div class="stock-price">$854,414.00</div></div>', unsafe_allow_html=True)

# Smart Helper Function to Load Subpages Dynamic
def load_page_module(file_name):
    possible_paths = [
        f"pages/{file_name}.py",
        f"pages/{file_name}",
    ]
    
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
        st.info("กรุณาตรวจสอบว่ามีไฟล์ชื่อนี้ตรงๆ อยู่ในโฟลเดอร์ pages/ ครับ")

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

    # หมวดหมู่ที่ 1: Portfolio Management
    with st.expander("📁 1.0 Portfolio", expanded=True):
        if st.button("📊 1.1 Portfolio Holdings", use_container_width=True):
            st.session_state["current_page"] = "1.1_Portfolio"
            st.rerun()
        if st.button("⚡ 1.2 Trade Execution", use_container_width=True):
            st.session_state["current_page"] = "1.2_Trade_Execution"
            st.rerun()
        if st.button("📜 1.3 Trade History", use_container_width=True):
            st.session_state["current_page"] = "1.3_History"
            st.rerun()
        if st.button("💰 1.4 Dividends", use_container_width=True):
            st.session_state["current_page"] = "1.4_Dividends"
            st.rerun()

    # หมวดหมู่ที่ 2: Assistant & AI Intelligence
    with st.expander("🧠 2.0 Assistant & AI", expanded=True):
        if st.button("🎯 2.1 Winner Tilt", use_container_width=True):
            st.session_state["current_page"] = "2.1_Winner_Tilt"
            st.rerun()
        if st.button("🤖 2.2 AI Fundamental", use_container_width=True):
            st.session_state["current_page"] = "2.2_AI_Fundamental"
            st.rerun()
        if st.button("🛡️ 2.3 Portfolio Risk Desk", use_container_width=True):
            st.session_state["current_page"] = "2.3_Portfolio_Risk_Desk"
            st.rerun()
        if st.button("🧮 2.4 MM Calculator", use_container_width=True):
            st.session_state["current_page"] = "2.4_MM_Calculator"
        if st.button("📰 2.5 News", use_container_width=True):
            st.session_state["current_page"] = "2.5_News"
            st.rerun()

    # หมวดหมู่ที่ 3: Future Extensions
    with st.expander("🚀 3.0 Future Extensions", expanded=False):
        st.caption("พื้นที่สำรองสำหรับการขยายระบบในอนาคต")

# ==========================================
# 5. PAGE SWITCHER ROUTER
# ==========================================
selected_page = st.session_state["current_page"]

if selected_page == "Dashboard":
    render_dashboard()
else:
    load_page_module(selected_page)
