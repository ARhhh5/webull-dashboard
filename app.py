import os
import json
import re
import base64
import importlib.util
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

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
            background-color: #8b5cf6 !important;
            color: #ffffff !important;
            border: 1px solid #a78bfa !important;
            box-shadow: 0 2px 10px rgba(139, 92, 246, 0.4) !important;
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

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ==========================================
# 2. GOOGLE SHEETS DATA PIPELINE (ROBUST)
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

def fetch_live_prices(symbols):
    price_map = {}
    if not symbols: return price_map
    clean_symbols = [str(s).strip().upper() for s in symbols if str(s).strip()]
    for sym in clean_symbols:
        try:
            ticker = yf.Ticker(sym)
            fast_info = ticker.fast_info
            price = fast_info.last_price
            if price is None or pd.isna(price):
                hist = ticker.history(period="1d")
                if not hist.empty: price = hist['Close'].iloc[-1]
            price_map[sym] = float(price) if price and not pd.isna(price) else None
        except Exception:
            price_map[sym] = None
    return price_map

@st.cache_data(ttl=10)
def load_all_portfolio_data_direct():
    """คำนวณพอร์ตสดทุกโบรกเกอร์โดยตรงจาก Google Sheets (ไม่พึ่ง Session State)"""
    client = get_gspread_client()
    if not client:
        return pd.DataFrame(), pd.DataFrame()
        
    try:
        sheet_title = st.secrets.get("SPREADSHEET_NAME", "หุ้นของเรา")
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            sheet_title = st.secrets["connections"]["gsheets"].get("spreadsheet", sheet_title)
            
        try: sh = client.open(sheet_title)
        except: sh = client.open_by_key(sheet_title) if len(sheet_title) > 20 else client.open_by_url(sheet_title)

        # 1. อ่านพอร์ต Webull ( Webull_Order_History )
        raw_records = []
        try:
            ws_w = sh.worksheet("Webull_Order_History")
            data_w = ws_w.get_all_values()
            if len(data_w) > 1:
                df_w = pd.DataFrame(data_w[1:], columns=data_w[0])
                cols = list(df_w.columns)
                time_col = next((c for c in cols if "Time" in c or "Date" in c or "วันที่" in c), cols[1] if len(cols) > 1 else None)
                sym_col = next((c for c in cols if "Sym" in c or "Ticker" in c or "หุ้น" in c), cols[2] if len(cols) > 2 else cols[0])
                qty_col = next((c for c in cols if "Qty" in c or "Volume" in c or "จำนวน" in c), cols[4] if len(cols) > 4 else cols[1])
                cost_col = next((c for c in cols if "Pr" in c or "Cost" in c or "ต้นทุน" in c or "Avg" in c), cols[5] if len(cols) > 5 else cols[2])
                status_col = next((c for c in cols if "สถานะ" in c or "Status" in c), cols[6] if len(cols) > 6 else None)

                if time_col and time_col in df_w.columns:
                    df_w["parsed_date"] = pd.to_datetime(df_w[time_col], errors='coerce')
                    valid_dates = df_w.dropna(subset=["parsed_date"])
                    if not valid_dates.empty:
                        max_date = valid_dates["parsed_date"].max()
                        df_latest = df_w[df_w["parsed_date"] == max_date].copy()
                        for sym, grp in df_latest.groupby(sym_col):
                            clean_sym = str(sym).strip().upper()
                            if not clean_sym: continue
                            latest_r = grp.iloc[-1]
                            qty = clean_num(latest_r.get(qty_col, 0))
                            cost = clean_num(latest_r.get(cost_col, 0))
                            status_val = str(latest_r.get(status_col, "")).strip().upper() if status_col else ""
                            if qty > 0 and status_val != "C":
                                raw_records.append({"Broker": "Webull", "Symbol": clean_sym, "Qty": qty, "Cost": cost})
        except Exception: pass

        # 2. อ่านพอร์ต Dime US ( Dime_Portfolio )
        try:
            ws_dus = sh.worksheet("Dime_Portfolio")
            data_dus = ws_dus.get_all_values()
            if len(data_dus) > 1:
                df_dus = pd.DataFrame(data_dus[1:], columns=data_dus[0])
                sym_col = next((c for c in df_dus.columns if "หุ้น" in c or "Ticker" in c or "Sym" in c), df_dus.columns[0])
                qty_col = next((c for c in df_dus.columns if "จำนวน" in c or "Volume" in c or "Qty" in c), df_dus.columns[1])
                cost_col = next((c for c in df_dus.columns if "ต้นทุน" in c or "Avg" in c or "Cost" in c), df_dus.columns[2])

                for sym, grp in df_dus.groupby(sym_col):
                    clean_sym = str(sym).strip().upper()
                    if not clean_sym: continue
                    tot_q = sum(clean_num(r.get(qty_col, 0)) for _, r in grp.iterrows())
                    tot_c_cash = sum(clean_num(r.get(qty_col, 0)) * clean_num(r.get(cost_col, 0)) for _, r in grp.iterrows())
                    if tot_q > 0.0001:
                        raw_records.append({"Broker": "Dime US", "Symbol": clean_sym, "Qty": tot_q, "Cost": tot_c_cash / tot_q})
        except Exception: pass

        # 3. อ่านพอร์ต Dime TH ( Dime_TH_Portfolio )
        try:
            ws_dth = sh.worksheet("Dime_TH_Portfolio")
            data_dth = ws_dth.get_all_values()
            if len(data_dth) > 1:
                df_dth = pd.DataFrame(data_dth[1:], columns=data_dth[0])
                sym_col = next((c for c in df_dth.columns if "หุ้น" in c or "Ticker" in c or "Sym" in c), df_dth.columns[0])
                qty_col = next((c for c in df_dth.columns if "จำนวน" in c or "Volume" in c or "Qty" in c), df_dth.columns[1])
                cost_col = next((c for c in df_dth.columns if "ต้นทุน" in c or "Avg" in c or "Cost" in c), df_dth.columns[2])

                for sym, grp in df_dth.groupby(sym_col):
                    clean_sym = str(sym).strip().upper()
                    if not clean_sym: continue
                    tot_q = sum(clean_num(r.get(qty_col, 0)) for _, r in grp.iterrows())
                    tot_c_cash = sum(clean_num(r.get(qty_col, 0)) * clean_num(r.get(cost_col, 0)) for _, r in grp.iterrows())
                    if tot_q > 0.0001:
                        raw_records.append({"Broker": "Dime TH", "Symbol": clean_sym, "Qty": tot_q, "Cost": tot_c_cash / tot_q})
        except Exception: pass

        # 4. อ่านประวัติการเติบโตพอร์ต ( Portfolio_History )
        df_history = pd.DataFrame()
        try:
            ws_h = sh.worksheet("Portfolio_History")
            data_h = ws_h.get_all_values()
            if len(data_h) > 1:
                df_h = pd.DataFrame(data_h[1:], columns=data_h[0])
                cols = [str(c).strip() for c in df_h.columns]
                time_c = next((c for c in cols if 'วัน' in c or 'date' in c.lower() or 'time' in c.lower() or 'timestamp' in c.lower()), cols[0])
                mkt_c = next((c for c in cols if 'ปัจจุบัน' in c or 'market' in c.lower() or 'มูลค่าป' in c), cols[2] if len(cols) > 2 else cols[0])
                inv_c = next((c for c in cols if 'ตั้งต้น' in c or 'invested' in c.lower() or 'ต้นทุน' in c or 'มูลค่าต' in c), cols[1] if len(cols) > 1 else cols[0])

                df_history["Raw_Date"] = df_h[time_c].astype(str)
                df_history["MarketValue"] = df_h[mkt_c].apply(clean_num)
                df_history["Invested"] = df_h[inv_c].apply(clean_num)
                df_history = df_history[df_history["MarketValue"] > 0].reset_index(drop=True)
                df_history["Parsed_Date"] = pd.to_datetime(df_history["Raw_Date"], format='mixed', errors='coerce')
                df_history = df_history.dropna(subset=["Parsed_Date"]).sort_values("Parsed_Date").reset_index(drop=True)
                df_history["Date_Str"] = df_history["Parsed_Date"].dt.strftime("%Y-%m-%d")
                df_history = df_history.groupby("Date_Str", as_index=False).last().sort_values("Date_Str").reset_index(drop=True)
        except Exception: pass

        if not raw_records:
            return pd.DataFrame(), df_history

        df_holdings = pd.DataFrame(raw_records)

        # 5. ดึง Live Price ผ่าน yfinance
        us_symbols = df_holdings[df_holdings["Broker"].isin(["Webull", "Dime US"])]["Symbol"].unique().tolist()
        th_symbols = [f"{s}.BK" for s in df_holdings[df_holdings["Broker"] == "Dime TH"]["Symbol"].unique().tolist()]
        live_prices = fetch_live_prices(us_symbols + th_symbols)
        fx_rate = st.session_state.get("usd_thb_rate", 35.0)

        calc_holdings = []
        for _, row in df_holdings.iterrows():
            broker, sym, qty, cost = row["Broker"], row["Symbol"], row["Qty"], row["Cost"]
            if broker in ["Webull", "Dime US"]:
                price = live_prices.get(sym) or cost
                inv_usd, mkt_usd = qty * cost, qty * price
                calc_holdings.append({"Broker": broker, "Symbol": sym, "Qty": qty, "Cost": cost, "Price": price, "Invested_USD": inv_usd, "Market_Value_USD": mkt_usd, "PnL_USD": mkt_usd - inv_usd})
            else:
                th_sym = f"{sym}.BK"
                price = live_prices.get(th_sym) or cost
                inv_thb, mkt_thb = qty * cost, qty * price
                calc_holdings.append({"Broker": broker, "Symbol": sym, "Qty": qty, "Cost": cost, "Price": price, "Invested_USD": inv_thb / fx_rate, "Market_Value_USD": mkt_thb / fx_rate, "PnL_USD": (mkt_thb - inv_thb) / fx_rate})

        return pd.DataFrame(calc_holdings), df_history

    except Exception:
        return pd.DataFrame(), pd.DataFrame()

# ==========================================
# 3. DASHBOARD MAIN RENDER FUNCTION
# ==========================================
def render_dashboard():
    col_refresh, c_curr = st.columns([3, 1])
    with col_refresh:
        if st.button("🔄 ดึงข้อมูลสดจาก Google Sheets", help="ล้างแคชและดึงข้อมูลจาก Google Sheet ใหม่"):
            st.cache_data.clear()
            st.rerun()
    with c_curr:
        currency_selected = st.radio("Display Currency", ("USD ($)", "THB (฿)"), horizontal=True, index=0)

    usd_fx_rate = st.session_state.get("usd_thb_rate", 35.0)
    is_usd = "USD" in currency_selected

    # ดึงข้อมูลพอร์ตสดตรงจาก Google Sheets
    df_holdings, df_history = load_all_portfolio_data_direct()

    if not df_holdings.empty:
        tot_invested_usd = df_holdings['Invested_USD'].sum()
        tot_market_usd = df_holdings['Market_Value_USD'].sum()
        tot_pnl_usd = tot_market_usd - tot_invested_usd
        tot_pnl_pct = (tot_pnl_usd / tot_invested_usd * 100) if tot_invested_usd > 0 else 0.0
    elif not df_history.empty:
        latest_row = df_history.iloc[-1]
        tot_invested_usd = latest_row["Invested"]
        tot_market_usd = latest_row["MarketValue"]
        tot_pnl_usd = tot_market_usd - tot_invested_usd
        tot_pnl_pct = (tot_pnl_usd / tot_invested_usd * 100) if tot_invested_usd > 0 else 0.0
    else:
        tot_invested_usd = 0.0
        tot_market_usd = 0.0
        tot_pnl_usd = 0.0
        tot_pnl_pct = 0.0

    display_market_usd = tot_market_usd
    display_market_thb = tot_market_usd * usd_fx_rate
    
    pnl_class = "badge-dime-pos" if tot_pnl_pct >= 0 else "badge-dime-neg"
    pnl_sign = "↗ " if tot_pnl_pct >= 0 else "↘ "

    latest_date_display = df_history.iloc[-1]["Parsed_Date"].strftime("%d %b %y") if not df_history.empty else datetime.now().strftime("%d %b %y")

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

    st.markdown(f'<div class="{pnl_class}">กำไรของสินทรัพย์ที่ถืออยู่: {pnl_sign}{tot_pnl_pct:.2f}%</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="dime-fx-text">อัตราแลกเปลี่ยน: 🇺🇸 1 USD = {usd_fx_rate:.2f} บาท</div>', unsafe_allow_html=True)

    # ----------------------------------------------------
    # DIME AREA CHART WITH INTERACTIVE HOVER
    # ----------------------------------------------------
    if "selected_tf" not in st.session_state:
        st.session_state["selected_tf"] = "MAX"

    st.markdown('<div class="dime-pill-container">', unsafe_allow_html=True)
    tf_options = ["1W", "1M", "3M", "6M", "YTD", "1Y", "MAX"]
    tf_cols = st.columns(len(tf_options))
    
    for idx, option in enumerate(tf_options):
        btn_type = "primary" if st.session_state["selected_tf"] == option else "secondary"
        if tf_cols[idx].button(option, key=f"dime_tf_{option}", use_container_width=True, type=btn_type):
            st.session_state["selected_tf"] = option
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    selected_tf = st.session_state["selected_tf"]

    # Filter Data by Selected Range
    if not df_history.empty:
        max_dt = df_history["Parsed_Date"].max()
        
        if selected_tf == "1W":
            start_dt = max_dt - timedelta(days=7)
            filtered_df = df_history[df_history["Parsed_Date"] >= start_dt].copy()
            if len(filtered_df) < 2: filtered_df = df_history.tail(2).copy()
        elif selected_tf == "1M":
            start_dt = max_dt - timedelta(days=30)
            filtered_df = df_history[df_history["Parsed_Date"] >= start_dt].copy()
            if len(filtered_df) < 2: filtered_df = df_history.tail(4).copy()
        elif selected_tf == "3M":
            start_dt = max_dt - timedelta(days=90)
            filtered_df = df_history[df_history["Parsed_Date"] >= start_dt].copy()
        elif selected_tf == "6M":
            start_dt = max_dt - timedelta(days=180)
            filtered_df = df_history[df_history["Parsed_Date"] >= start_dt].copy()
        elif selected_tf == "YTD":
            start_dt = pd.to_datetime(f"{max_dt.year}-01-01")
            filtered_df = df_history[df_history["Parsed_Date"] >= start_dt].copy()
        elif selected_tf == "1Y":
            start_dt = max_dt - timedelta(days=365)
            filtered_df = df_history[df_history["Parsed_Date"] >= start_dt].copy()
        else: # MAX
            filtered_df = df_history.copy()

        if filtered_df.empty: filtered_df = df_history.copy()

        x_axis = filtered_df["Date_Str"].tolist()
        y_axis = (filtered_df["MarketValue"] if is_usd else (filtered_df["MarketValue"] * usd_fx_rate)).tolist()
    else:
        x_axis = [datetime.now().strftime("%Y-%m-%d")]
        y_axis = [display_market_usd if is_usd else display_market_thb]

    # Auto Zoom Y-Axis Calculation
    min_y = min(y_axis) if y_axis else 0
    max_y = max(y_axis) if y_axis else 100
    padding = (max_y - min_y) * 0.15 if max_y != min_y else max_y * 0.1
    y_range = [max(0, min_y - padding), max_y + padding]

    # Render Dime Smooth Area Line Chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_axis, 
        y=y_axis, 
        mode='lines+markers' if len(x_axis) < 10 else 'lines', 
        line=dict(color='#8b5cf6', width=3, shape='spline'), 
        marker=dict(size=8, color='#8b5cf6'),
        fill='tozeroy', 
        fillcolor='rgba(139, 92, 246, 0.12)',
        hovertemplate="<b>วันที่: %{x}</b><br>มูลค่า: %{y:$,.2f}<extra></extra>" if is_usd else "<b>วันที่: %{x}</b><br>มูลค่า: ฿%{y:,.2f}<extra></extra>"
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)', 
        font=dict(color='#64748b', family='Plus Jakarta Sans'), 
        xaxis=dict(showgrid=False, zeroline=False, type='category', tickangle=0), 
        yaxis=dict(showgrid=True, gridcolor='#161923', zeroline=False, range=y_range, autorange=False), 
        margin=dict(t=10, b=10, l=10, r=10), 
        height=280,
        hovermode="x unified"
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False}, key=f"dime_app_chart_v4_{selected_tf}_{currency_selected}_{len(x_axis)}")

    # ----------------------------------------------------
    # BROKER ALLOCATION
    # ----------------------------------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    c_btm_left, c_btm_right = st.columns([1.1, 1.9])

    if not df_holdings.empty:
        df_b_sum = df_holdings.groupby("Broker")["Market_Value_USD"].sum().to_dict()
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
