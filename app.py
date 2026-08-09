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
# 1. PAGE CONFIGURATION & DIME-STYLE CSS
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
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            background-color: #090a0f !important;
            color: #e2e8f0;
        }

        .stApp {
            background-color: #090a0f;
        }

        /* HIDE STREAMLIT DEFAULT NAVIGATION */
        [data-testid="stSidebarNav"] {
            display: none !important;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #0f1117 !important;
            border-right: 1px solid #1a1d26 !important;
        }

        .sidebar-brand {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.1rem;
            font-weight: 800;
            color: #38bdf8;
            padding: 10px 0px 15px 0px;
            letter-spacing: 1px;
            border-bottom: 1px solid #1a1d26;
            margin-bottom: 15px;
        }

        div[data-testid="stSidebar"] .stButton > button {
            background-color: #141722;
            color: #9ca3af;
            border: 1px solid #222736;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.85rem;
            transition: all 0.2s ease !important;
            text-align: left;
            padding: 8px 12px;
            margin-bottom: 2px;
            width: 100%;
        }

        div[data-testid="stSidebar"] .stButton > button:hover {
            border-color: #38bdf8;
            color: #38bdf8;
            background-color: #1a202c;
        }

        div[data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: linear-gradient(90deg, #8b5cf6 0%, #6d28d9 100%) !important;
            color: #ffffff !important;
            border: 1px solid #a78bfa !important;
            box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
        }

        /* Dime Header Typography */
        .dime-sub-label {
            font-size: 0.88rem;
            font-weight: 600;
            color: #94a3b8;
            margin-bottom: 2px;
        }

        .dime-big-title {
            font-size: 2.5rem;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -1px;
            line-height: 1.1;
            margin-bottom: 4px;
        }

        .dime-sub-currency {
            font-size: 1rem;
            font-weight: 600;
            color: #cbd5e1;
            margin-bottom: 10px;
        }

        .badge-dime-pos {
            color: #4ade80;
            font-weight: 700;
            font-size: 1.05rem;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .badge-dime-neg {
            color: #f87171;
            font-weight: 700;
            font-size: 1.05rem;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .dime-fx-text {
            font-size: 0.85rem;
            color: #64748b;
            margin-top: 6px;
            margin-bottom: 20px;
        }

        /* Pill Range Buttons Override */
        .dime-pill-container div[data-testid="stColumn"] div.stButton > button {
            background-color: #141722 !important;
            border: 1px solid #222736 !important;
            border-radius: 20px !important;
            color: #94a3b8 !important;
            font-size: 0.82rem !important;
            font-weight: 700 !important;
            height: 36px !important;
            transition: all 0.2s ease !important;
        }

        .dime-pill-container div[data-testid="stColumn"] div.stButton > button:hover {
            border-color: #8b5cf6 !important;
            color: #c4b5fd !important;
        }

        .dime-pill-container div[data-testid="stColumn"] div.stButton > button[kind="primary"] {
            background-color: #f43f5e !important;
            color: #ffffff !important;
            border: 1px solid #fb7185 !important;
            box-shadow: 0 2px 10px rgba(244, 63, 94, 0.4) !important;
        }

        .dash-card {
            background-color: #0f1117;
            border: 1px solid #1a1d26;
            border-radius: 14px;
            padding: 20px;
            margin-bottom: 15px;
        }

        .asset-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            font-size: 0.88rem;
            border-bottom: 1px solid #161923;
        }
        .asset-label { display: flex; align-items: center; gap: 10px; color: #cbd5e1; }
        .asset-val { font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #ffffff; }

        .stock-grid-card {
            background-color: #111318;
            border: 1px solid #1a1d26;
            border-radius: 10px;
            padding: 14px;
            margin-bottom: 10px;
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ==========================================
# 2. GOOGLE SHEETS DATA PIPELINE (100% ROBUST)
# ==========================================
def get_gspread_client():
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

def clean_num(val):
    if pd.isna(val) or val == "": return 0.0
    val_str = str(val).replace(",", "").replace("%", "").replace("$", "").replace("฿", "").strip()
    try: return float(val_str)
    except: return 0.0

@st.cache_data(ttl=5)
def fetch_portfolio_history_clean_realtime():
    """ดึงข้อมูลประวัติโดยใช้ Index (A=0, B=1, C=2) ป้องกันบั๊ก 0.00 จากชื่อคอลัมน์ไม่ตรง"""
    client = get_gspread_client()
    if not client:
        return pd.DataFrame()
    try:
        sheet_title = st.secrets.get("SPREADSHEET_NAME", "หุ้นของเรา")
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            sheet_title = st.secrets["connections"]["gsheets"].get("spreadsheet", sheet_title)
            
        try: sh = client.open(sheet_title)
        except: sh = client.open_by_key(sheet_title) if len(sheet_title) > 20 else client.open_by_url(sheet_title)

        ws = sh.worksheet("Portfolio_History")
        data = ws.get_all_values()
        
        if len(data) > 1:
            df = pd.DataFrame(data[1:])
            # บังคับใช้ Index: 0=วันที่, 1=มูลค่าตั้งต้น(Invested), 2=มูลค่าปัจจุบัน(MarketValue)
            df_res = pd.DataFrame()
            df_res["Raw_Date"] = df.iloc[:, 0].astype(str)
            df_res["Invested"] = df.iloc[:, 1].apply(clean_num)
            df_res["MarketValue"] = df.iloc[:, 2].apply(clean_num)
            
            # กรองและแปลงวันที่
            df_res = df_res[df_res["MarketValue"] > 0].reset_index(drop=True)
            df_res["Parsed_Date"] = pd.to_datetime(df_res["Raw_Date"], errors='coerce')
            df_res = df_res.dropna(subset=["Parsed_Date"]).sort_values("Parsed_Date").reset_index(drop=True)
            
            df_res["Date_Str"] = df_res["Parsed_Date"].dt.strftime("%Y-%m-%d")
            
            # ยุบข้อมูลซ้ำในวันเดียวกัน เอาเฉพาะ Snapshot ล่าสุดของวัน
            df_res = df_res.groupby("Date_Str", as_index=False).last()
            df_res = df_res.sort_values("Parsed_Date").reset_index(drop=True)
            return df_res
    except Exception:
        pass
    return pd.DataFrame()

# ==========================================
# 3. DASHBOARD MAIN RENDER FUNCTION
# ==========================================
def render_dashboard():
    # Header Control Bar (Cleaned up, no refresh button)
    c_spacer, c_curr = st.columns([3, 1])
    with c_spacer:
        st.empty() # Placeholder for spacing
    with c_curr:
        currency_selected = st.radio("Display Currency", ("USD ($)", "THB (฿)"), horizontal=True, index=0)

    usd_fx_rate = st.session_state.get("usd_thb_rate", 32.96)
    is_usd = "USD" in currency_selected

    # Load Real-time Data
    df_shared = st.session_state.get("all_holdings_df", pd.DataFrame())
    df_history = fetch_portfolio_history_clean_realtime()

    if "selected_tf" not in st.session_state:
        st.session_state["selected_tf"] = "1W"

    selected_tf = st.session_state["selected_tf"]

    # ----------------------------------------------------
    # CALCULATE TIMEFRAME PERFORMANCE & MARKER
    # ----------------------------------------------------
    marker_date_str = ""
    marker_val = 0.0
    tf_pnl_pct = 0.0

    if not df_history.empty:
        max_dt = df_history["Parsed_Date"].max()
        current_market_val = df_history.iloc[-1]["MarketValue"]
        current_invested_val = df_history.iloc[-1]["Invested"]
        
        # กำหนดวันที่เริ่มต้นของ Timeframe
        if selected_tf == "1W":
            start_dt = max_dt - timedelta(days=7)
        elif selected_tf == "1M":
            start_dt = max_dt - timedelta(days=30)
        elif selected_tf == "3M":
            start_dt = max_dt - timedelta(days=90)
        elif selected_tf == "6M":
            start_dt = max_dt - timedelta(days=180)
        elif selected_tf == "YTD":
            start_dt = pd.to_datetime(f"{max_dt.year}-01-01")
        elif selected_tf == "1Y":
            start_dt = max_dt - timedelta(days=365)
        else: # MAX
            start_dt = df_history["Parsed_Date"].min()

        # หาแถวที่เป็นจุดเริ่มต้น (Base Row) สำหรับ Timeframe นั้น
        if selected_tf == "MAX":
            base_row = df_history.iloc[0]
            base_val = base_row["Invested"] # ใช้มูลค่าลงทุนตั้งต้นสำหรับ MAX
        else:
            past_df = df_history[df_history["Parsed_Date"] >= start_dt]
            if not past_df.empty:
                base_row = past_df.iloc[0]
            else:
                base_row = df_history.iloc[0]
            base_val = base_row["MarketValue"]

        # ดึงข้อมูลสำหรับปักหมุด
        marker_date_str = base_row["Date_Str"]
        marker_val = base_row["MarketValue"]
        
        # คำนวณ PnL ณ Timeframe นั้น
        tf_pnl_usd = current_market_val - base_val
        tf_pnl_pct = (tf_pnl_usd / base_val * 100) if base_val > 0 else 0.0

    else:
        current_market_val = 0.0
        current_invested_val = 0.0

    display_market_usd = current_market_val
    display_market_thb = current_market_val * usd_fx_rate
    
    pnl_class = "badge-dime-pos" if tf_pnl_pct >= 0 else "badge-dime-neg"
    pnl_sign = "↗ " if tf_pnl_pct >= 0 else "↘ "

    latest_date_display = df_history.iloc[-1]["Parsed_Date"].strftime("%d %b %y") if not df_history.empty else datetime.now().strftime("%d %b %y")
    tf_label = f" (ตั้งแต่เริ่ม {selected_tf})" if selected_tf != "MAX" else " (ตั้งแต่เริ่มต้น)"

    # ----------------------------------------------------
    # DIME-STYLE HEADER DISPLAY SECTION
    # ----------------------------------------------------
    st.markdown(f'<div class="dime-sub-label">มูลค่าสินทรัพย์ทั้งหมด ({latest_date_display}) 👁️</div>', unsafe_allow_html=True)
    
    if is_usd:
        st.markdown(f'<div class="dime-big-title">{display_market_usd:,.2f} <span style="font-size: 1.5rem; font-weight: 700;">USD</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="dime-sub-currency">≈ {display_market_thb:,.2f} บาท</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="dime-big-title">฿{display_market_thb:,.2f}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="dime-sub-currency">≈ ${display_market_usd:,.2f} USD</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="{pnl_class}">กำไรของสินทรัพย์ที่ถืออยู่{tf_label}: {pnl_sign}{tf_pnl_pct:.2f}%</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="dime-fx-text">อัตราแลกเปลี่ยน: 🇺🇸 1 USD = {usd_fx_rate:.2f} บาท</div>', unsafe_allow_html=True)

    # ----------------------------------------------------
    # TIMEFRAME BUTTONS
    # ----------------------------------------------------
    st.markdown('<div class="dime-pill-container">', unsafe_allow_html=True)
    tf_options = ["1W", "1M", "3M", "6M", "YTD", "1Y", "MAX"]
    tf_cols = st.columns(len(tf_options))
    
    for idx, option in enumerate(tf_options):
        btn_type = "primary" if selected_tf == option else "secondary"
        if tf_cols[idx].button(option, key=f"dime_tf_{option}", use_container_width=True, type=btn_type):
            st.session_state["selected_tf"] = option
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ----------------------------------------------------
    # ALWAYS-MAX CHART WITH HIGHLIGHT MARKER
    # ----------------------------------------------------
    if not df_history.empty:
        x_axis = df_history["Date_Str"].tolist()
        y_axis = (df_history["MarketValue"] if is_usd else (df_history["MarketValue"] * usd_fx_rate)).tolist()
    else:
        x_axis = [datetime.now().strftime("%Y-%m-%d")]
        y_axis = [0.0]

    min_y = min(y_axis) if y_axis else 0
    max_y = max(y_axis) if y_axis else 100
    padding = (max_y - min_y) * 0.15 if max_y != min_y else max_y * 0.1
    y_range = [max(0, min_y - padding), max_y + padding]

    fig = go.Figure()
    
    # 1. วาดกราฟเส้นแนวยาว (MAX) เสมอ
    fig.add_trace(go.Scatter(
        x=x_axis, 
        y=y_axis, 
        mode='lines', 
        line=dict(color='#8b5cf6', width=3, shape='spline'), 
        fill='tozeroy', 
        fillcolor='rgba(139, 92, 246, 0.12)',
        hovertemplate="<b>วันที่: %{x}</b><br>มูลค่า: %{y:$,.2f}<extra></extra>" if is_usd else "<b>วันที่: %{x}</b><br>มูลค่า: ฿%{y:,.2f}<extra></extra>",
        name="Portfolio"
    ))

    # 2. ปักหมุด Highlight Marker ณ วันที่เริ่มต้น Timeframe นั้น
    if not df_history.empty and marker_date_str in x_axis:
        idx = x_axis.index(marker_date_str)
        marker_y_val = y_axis[idx]
        curr_sym = "$" if is_usd else "฿"
        
        fig.add_trace(go.Scatter(
            x=[marker_date_str],
            y=[marker_y_val],
            mode='markers+text',
            marker=dict(color='#f43f5e', size=12, symbol='circle', line=dict(color='#ffffff', width=2)),
            text=[f"เริ่ม {selected_tf}<br>{curr_sym}{marker_y_val:,.2f}"],
            textposition="top center",
            textfont=dict(color='#fb7185', size=12, weight='bold'),
            hoverinfo='skip',
            name="Start Point"
        ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)', 
        font=dict(color='#64748b', family='Plus Jakarta Sans'), 
        xaxis=dict(showgrid=False, zeroline=False, type='category', tickangle=0), 
        yaxis=dict(showgrid=True, gridcolor='#161923', zeroline=False, range=y_range, autorange=False), 
        margin=dict(t=30, b=10, l=10, r=10), 
        height=320,
        hovermode="x unified",
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False}, key="always_max_chart_v1")

    # ----------------------------------------------------
    # BROKER ALLOCATION
    # ----------------------------------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    c_btm_left, c_btm_right = st.columns([1.1, 1.9])

    if not df_shared.empty:
        df_b_sum = df_shared.groupby("Broker")["Market_Value_USD"].sum().to_dict()
        val_dime_us = df_b_sum.get("Dime US", 0.0) * (1.0 if is_usd else usd_fx_rate)
        val_webull = df_b_sum.get("Webull", 0.0) * (1.0 if is_usd else usd_fx_rate)
        val_dime_th = df_b_sum.get("Dime TH", 0.0) * (1.0 if is_usd else usd_fx_rate)
    else:
        val_dime_us = 0.0
        val_webull = 0.0
        val_dime_th = 0.0

    curr_sym = "$" if is_usd else "฿"

    with c_btm_left:
        st.markdown(f"""
        <div class="dash-card">
            <div class="dime-sub-label">สัดส่วนสินทรัพย์แยกตามโบรกเกอร์</div>
            <div class="asset-row" style="margin-top: 10px;">
                <div class="asset-label">💵 Dime US</div>
                <div class="asset-val">{curr_sym}{val_dime_us:,.2f}</div>
            </div>
            <div class="asset-row">
                <div class="asset-label">⚡ Webull US</div>
                <div class="asset-val">{curr_sym}{val_webull:,.2f}</div>
            </div>
            <div class="asset-row" style="border-bottom:none;">
                <div class="asset-label">🇹🇭 Dime TH</div>
                <div class="asset-val">{curr_sym}{val_dime_th:,.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c_btm_right:
        st.markdown('<div class="dime-sub-label" style="margin-bottom: 10px;">ภาพรวมพอร์ตตามโบรกเกอร์</div>', unsafe_allow_html=True)
        g1, g2, g3 = st.columns(3)
        with g1: st.markdown(f'<div class="dash-card" style="padding: 14px;"><div style="display:flex; justify-content:space-between;"><span style="font-weight:700; color:#fff;">🟢 Dime US</span></div><div style="font-family:JetBrains Mono; font-size:1.1rem; font-weight:700; color:#fff; margin-top:6px;">{curr_sym}{val_dime_us:,.2f}</div></div>', unsafe_allow_html=True)
        with g2: st.markdown(f'<div class="dash-card" style="padding: 14px;"><div style="display:flex; justify-content:space-between;"><span style="font-weight:700; color:#fff;">🔵 Webull US</span></div><div style="font-family:JetBrains Mono; font-size:1.1rem; font-weight:700; color:#fff; margin-top:6px;">{curr_sym}{val_webull:,.2f}</div></div>', unsafe_allow_html=True)
        with g3: st.markdown(f'<div class="dash-card" style="padding: 14px;"><div style="display:flex; justify-content:space-between;"><span style="font-weight:700; color:#fff;">🔴 Dime TH</span></div><div style="font-family:JetBrains Mono; font-size:1.1rem; font-weight:700; color:#fff; margin-top:6px;">{curr_sym}{val_dime_th:,.2f}</div></div>', unsafe_allow_html=True)

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
