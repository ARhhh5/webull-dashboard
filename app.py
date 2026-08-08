import os
import json
import re
import base64
import importlib.util
from datetime import datetime, timedelta
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
            transition: all 0.2s ease !important;
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
        .badge-delta-pos { background-color: rgba(34, 197, 94, 0.12); color: #4ade80; padding: 4px 8px; border-radius: 6px; font-size: 0.78rem; font-family: 'JetBrains Mono', monospace; }

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
    """เชื่อมต่อ Google Sheets API โดยสแกนหา Credentials จาก Secrets ทุกตำแหน่งที่เป็นไปได้"""
    if not HAS_GSPREAD:
        return None
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds_dict = None
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
        elif "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            creds_dict = dict(st.secrets["connections"]["gsheets"])
        elif "type" in st.secrets and st.secrets["type"] == "service_account":
            creds_dict = dict(st.secrets)

        if creds_dict:
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            return gspread.authorize(creds)
    except Exception:
        pass
    return None

def load_history_from_gsheet():
    """ดึงข้อมูลประวัติย้อนหลังจาก Portfolio_History มาประมวลผล"""
    client = get_gspread_client()
    if not client:
        return None
    try:
        sheet_title = st.secrets.get("SPREADSHEET_NAME", "หุ้นของเรา")
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            sheet_title = st.secrets["connections"]["gsheets"].get("spreadsheet", sheet_title)
            
        try:
            sh = client.open(sheet_title)
        except Exception:
            sh = client.open_by_key(sheet_title) if len(sheet_title) > 20 else client.open_by_url(sheet_title)

        worksheet = sh.worksheet("Portfolio_History")
        data = worksheet.get_all_values()
        
        if len(data) > 0:
            df = pd.DataFrame(data)
            
            first_val = str(df.iloc[0, 0]).strip()
            if "วัน" in first_val or "Date" in first_val or "Timestamp" in first_val:
                df = df.iloc[1:].reset_index(drop=True)
                
            cols = ["Timestamp", "Invested", "MarketValue", "PnL", "PnLPct"]
            df = df.iloc[:, :len(cols)]
            df.columns = cols[:len(df.columns)]
            
            def clean_num(val):
                if pd.isna(val) or val == "": return 0.0
                val_str = str(val).replace(",", "").replace("%", "").replace("$", "").replace("฿", "").strip()
                try: return float(val_str)
                except: return 0.0

            df["MarketValue"] = df["MarketValue"].apply(clean_num)
            df["Invested"] = df["Invested"].apply(clean_num)
            df["PnL"] = df["PnL"].apply(clean_num)
            df["PnLPct"] = df["PnLPct"].apply(clean_num)
            
            df = df[df["MarketValue"] > 0].reset_index(drop=True)
            df["Parsed_Date"] = pd.to_datetime(df["Timestamp"], errors='coerce')
            df = df.dropna(subset=["Parsed_Date"]).sort_values("Parsed_Date").reset_index(drop=True)

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

    usd_fx_rate = st.session_state.get("usd_thb_rate", 35.0)
    is_usd = "USD" in currency_selected
    symbol = "$" if is_usd else "฿"

    # 1. ดึงจาก Shared Session State ใน Portfolio
    df_shared = st.session_state.get("all_holdings_df", pd.DataFrame())
    
    # 2. ดึงข้อมูลประวัติจาก Portfolio_History
    df_history = load_history_from_gsheet()

    if not df_shared.empty:
        tot_invested_usd = df_shared['Invested_USD'].sum()
        tot_market_usd = df_shared['Market_Value_USD'].sum()
        tot_pnl_usd = tot_market_usd - tot_invested_usd
        tot_pnl_pct = (tot_pnl_usd / tot_invested_usd * 100) if tot_invested_usd > 0 else 0.0
    elif df_history is not None and not df_history.empty:
        latest_row = df_history.iloc[-1]
        tot_invested_usd = latest_row["Invested"]
        tot_market_usd = latest_row["MarketValue"]
        tot_pnl_usd = latest_row["PnL"] if latest_row["PnL"] != 0 else (tot_market_usd - tot_invested_usd)
        tot_pnl_pct = latest_row["PnLPct"] if latest_row["PnLPct"] != 0 else ((tot_pnl_usd / tot_invested_usd * 100) if tot_invested_usd > 0 else 0.0)
    else:
        tot_invested_usd = 47944.46
        tot_market_usd = 45778.22
        tot_pnl_usd = -2166.24
        tot_pnl_pct = -4.52

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
            <div style="color: {'#4ade80' if display_pnl >= 0 else '#f87171'}; font-size: 0.82rem; margin-top: 6px; font-family: 'JetBrains Mono', monospace;">
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
        if "selected_tf" not in st.session_state:
            st.session_state["selected_tf"] = "MAX"

        # แสดงปุ่มกดเลือกช่วงเวลา (Pills/Buttons)
        tf_options = ["1D", "7D", "1M", "6M", "1Y", "MAX"]
        tf_cols = st.columns(len(tf_options))
        
        for idx, option in enumerate(tf_options):
            btn_type = "primary" if st.session_state["selected_tf"] == option else "secondary"
            if tf_cols[idx].button(option, key=f"tf_btn_{option}", use_container_width=True, type=btn_type):
                st.session_state["selected_tf"] = option
                st.rerun()

        selected_tf = st.session_state["selected_tf"]

        # จัดการกรองข้อมูลย้อนหลังจาก Portfolio_History แบบเป๊ะๆ
        if df_history is not None and not df_history.empty:
            filtered_df = df_history.copy()
            max_date = filtered_df["Parsed_Date"].max()
            
            if selected_tf == "1D":
                # 1D: ดึงเฉพาะ 2 จุดล่าสุดเพื่อดูมูฟเม้นท์เปรียบเทียบ
                filtered_df = filtered_df.tail(2)
                
            elif selected_tf == "7D":
                # 7D: ดึงเฉพาะข้อมูลย้อนหลังไม่เกิน 6 วันเพื่อไม่ให้โดนดึงจุด 7 วันที่แล้วติดมา
                start_date = max_date - timedelta(days=6)
                temp_df = filtered_df[filtered_df["Parsed_Date"] >= start_date]
                # ถ้าจุดข้อมูลมีมากกว่า 3 จุด ดึงจุดย้อนหลัง 3 จุดล่าสุด
                filtered_df = temp_df if not temp_df.empty else filtered_df.tail(3)
                
            elif selected_tf == "1M":
                start_date = max_date - timedelta(days=30)
                temp_df = filtered_df[filtered_df["Parsed_Date"] >= start_date]
                filtered_df = temp_df if not temp_df.empty else filtered_df.copy()
            elif selected_tf == "6M":
                start_date = max_date - timedelta(days=180)
                temp_df = filtered_df[filtered_df["Parsed_Date"] >= start_date]
                filtered_df = temp_df if not temp_df.empty else filtered_df.copy()
            elif selected_tf == "1Y":
                start_date = max_date - timedelta(days=365)
                temp_df = filtered_df[filtered_df["Parsed_Date"] >= start_date]
                filtered_df = temp_df if not temp_df.empty else filtered_df.copy()
            else:  # MAX
                filtered_df = df_history.copy()

            x_axis = filtered_df["Parsed_Date"].dt.strftime("%Y-%m-%d").tolist()
            y_axis = (filtered_df["MarketValue"] if is_usd else (filtered_df["MarketValue"] * usd_fx_rate)).tolist()
        else:
            x_axis = ['2026-08-01', '2026-08-02', '2026-08-05', '2026-08-08']
            y_axis = [15000.00, 48180.96, 45941.50, display_market]
        
        # วาดกราฟ Plotly
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x_axis, 
            y=y_axis, 
            mode='lines+markers', 
            line=dict(color='#38bdf8', width=3, shape='spline'), 
            marker=dict(size=6, color='#38bdf8'),
            fill='tozeroy', 
            fillcolor='rgba(56, 189, 248, 0.05)',
            hovertemplate="<b>วันที่: %{x}</b><br>มูลค่าพอร์ต: %{y:$,.2f}<extra></extra>"
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)', 
            font=dict(color='#6b7280', family='Plus Jakarta Sans'), 
            xaxis=dict(showgrid=False, zeroline=False, type='category'), 
            yaxis=dict(showgrid=True, gridcolor='#16181f', zeroline=False), 
            margin=dict(t=15, b=10, l=10, r=10), 
            height=260
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # คำนวณ Broker Allocation จาก Shared DataFrame สด
    if not df_shared.empty:
        df_b_sum = df_shared.groupby("Broker")["Market_Value_USD"].sum().to_dict()
        val_dime_us = df_b_sum.get("Dime US", 32412.11) * (1.0 if is_usd else usd_fx_rate)
        val_webull = df_b_sum.get("Webull", 9131.88) * (1.0 if is_usd else usd_fx_rate)
        val_dime_th = df_b_sum.get("Dime TH", 4234.23) * (1.0 if is_usd else usd_fx_rate)
    else:
        val_dime_us = 32412.11 * (1.0 if is_usd else usd_fx_rate)
        val_webull = 9131.88 * (1.0 if is_usd else usd_fx_rate)
        val_dime_th = 4234.23 * (1.0 if is_usd else usd_fx_rate)

    c_btm_left, c_btm_right = st.columns([1.1, 1.9])
    with c_btm_left:
        st.markdown(f"""
        <div class="dash-card">
            <div class="card-header-title">Broker Allocation Real-time</div>
            <div class="asset-row">
                <div class="asset-label">💵 Dime US</div>
                <div class="asset-val">{symbol}{val_dime_us:,.2f}</div>
            </div>
            <div class="asset-row">
                <div class="asset-label">⚡ Webull US</div>
                <div class="asset-val">{symbol}{val_webull:,.2f}</div>
            </div>
            <div class="asset-row" style="border-bottom:none;">
                <div class="asset-label">🇹🇭 Dime TH</div>
                <div class="asset-val">{symbol}{val_dime_th:,.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c_btm_right:
        st.markdown('<div style="font-size: 0.85rem; font-weight: 600; color: #9ca3af; margin-bottom: 10px;">Top Holdings Performance</div>', unsafe_allow_html=True)
        g1, g2, g3 = st.columns(3)
        with g1: st.markdown('<div class="stock-grid-card"><div style="display:flex; justify-content:space-between; align-items:center;"><span class="stock-symbol">🟢 Dime US</span><span class="badge-delta-pos">+11.37%</span></div><div class="stock-price">$32,412.11</div></div>', unsafe_allow_html=True)
        with g2: st.markdown('<div class="stock-grid-card"><div style="display:flex; justify-content:space-between; align-items:center;"><span class="stock-symbol">🔴 Webull US</span><span class="badge-delta-neg">-34.48%</span></div><div class="stock-price">$9,131.88</div></div>', unsafe_allow_html=True)
        with g3: st.markdown('<div class="stock-grid-card"><div style="display:flex; justify-content:space-between; align-items:center;"><span class="stock-symbol">🔴 Dime TH</span><span class="badge-delta-neg">-13.67%</span></div><div class="stock-price">$4,234.23</div></div>', unsafe_allow_html=True)

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
