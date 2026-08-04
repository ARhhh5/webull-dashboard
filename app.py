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
# 2. SHARED PORTFOLIO DATA PIPELINE
# ==========================================
webull_config = st.secrets.get("Webull", {})
APP_KEY = webull_config.get("AppKey", "").strip()
APP_SECRET = webull_config.get("AppSecret", "").strip()
ACCESS_TOKEN = webull_config.get("AccessToken", "").strip()
ACCOUNT_ID = webull_config.get("AccountId", "").strip()
HOST = "api.webull.co.th"

@st.cache_data(ttl=60)
def get_usd_thb_rate():
    try:
        ticker = yf.Ticker("USDTHB=X")
        rate = ticker.fast_info.get('last_price') or ticker.info.get('regularMarketPrice') or 35.0
        return float(rate)
    except:
        return 35.0

def get_gspread_client():
    if not HAS_GSPREAD:
        return None
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            return gspread.service_account_from_dict(cred_dict)
        elif "gcp_service_account" in st.secrets:
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
            return gspread.authorize(creds)
    except Exception:
        pass
    return None

def get_webull_live_prices():
    path = "/openapi/assets/positions"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex
    signing_values = {"host": HOST, "x-app-key": APP_KEY, "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-signature-version": "1.0", "x-timestamp": timestamp, "account_id": ACCOUNT_ID}
    string_1 = "&".join(f"{key}={signing_values[key]}" for key in sorted(signing_values))
    signature = base64.b64encode(hmac.new(f"{APP_SECRET}&".encode("utf-8"), urllib.parse.quote(f"{path}&{string_1}", safe="").encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
    headers = {"Accept": "application/json", "x-app-key": APP_KEY, "x-timestamp": timestamp, "x-signature-version": "1.0", "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-version": "v2", "x-signature": signature, "x-access-token": ACCESS_TOKEN}
    
    prices = {}
    try:
        conn = http.client.HTTPSConnection(HOST)
        conn.request("GET", f"{path}?account_id={ACCOUNT_ID}", "", headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        if isinstance(data, list):
            for p in data:
                prices[str(p.get("symbol")).upper()] = float(p.get("last_price", 0))
    except:
        pass
    return prices

def get_webull_holdings():
    path = "/openapi/assets/positions"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex
    signing_values = {"host": HOST, "x-app-key": APP_KEY, "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-signature-version": "1.0", "x-timestamp": timestamp, "account_id": ACCOUNT_ID}
    string_1 = "&".join(f"{key}={signing_values[key]}" for key in sorted(signing_values))
    signature = base64.b64encode(hmac.new(f"{APP_SECRET}&".encode("utf-8"), urllib.parse.quote(f"{path}&{string_1}", safe="").encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
    headers = {"Accept": "application/json", "x-app-key": APP_KEY, "x-timestamp": timestamp, "x-signature-version": "1.0", "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-version": "v2", "x-signature": signature, "x-access-token": ACCESS_TOKEN}
    
    holdings = []
    try:
        conn = http.client.HTTPSConnection(HOST)
        conn.request("GET", f"{path}?account_id={ACCOUNT_ID}", "", headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        if isinstance(data, list):
            for p in data:
                if p.get("instrument_type") == "EQUITY":
                    holdings.append({
                        "Symbol": str(p.get("symbol", "")).strip().upper(),
                        "Qty": float(p.get("quantity", 0)),
                        "Cost": float(p.get("cost_price", 0)),
                        "Broker": "Webull"
                    })
    except:
        pass
    return holdings

def get_dime_us_holdings():
    holdings = []
    gc = get_gspread_client()
    if gc:
        try:
            sh = gc.open("หุ้นของเรา")
            worksheet = sh.worksheet("Dime_Portfolio")
            records = worksheet.get_all_records()
            for r in records:
                sym = str(r.get("หุ้น (Ticker)", "")).strip().upper()
                if sym:
                    holdings.append({
                        "Symbol": sym,
                        "Qty": float(r.get("จำนวนหุ้น (Volume)", 0)),
                        "Cost": float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0)),
                        "Broker": "Dime US",
                        "Manual_Price": r.get("ราคาปัจจุบันล็อก (Manual Price)", "")
                    })
        except:
            pass
    return holdings

def get_dime_th_holdings():
    holdings = []
    gc = get_gspread_client()
    if gc:
        try:
            sh = gc.open("หุ้นของเรา")
            worksheet = sh.worksheet("Dime_TH_Portfolio")
            records = worksheet.get_all_records()
            for r in records:
                sym = str(r.get("หุ้น (Ticker)", "")).strip().upper()
                if sym:
                    holdings.append({
                        "Symbol": sym,
                        "Qty": float(r.get("จำนวนหุ้น (Volume)", 0)),
                        "Cost": float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0)),
                        "Broker": "Dime TH"
                    })
        except:
            pass
    return holdings

def load_master_portfolio_data():
    fx_rate = get_usd_thb_rate()
    webull_prices = get_webull_live_prices()
    w_holdings = get_webull_holdings()
    d_us_holdings = get_dime_us_holdings()
    d_th_holdings = get_dime_th_holdings()
    
    all_holdings = w_holdings + d_us_holdings + d_th_holdings
    
    if all_holdings:
        df_raw = pd.DataFrame(all_holdings)
        live_prices = {}
        
        for index, row in df_raw.iterrows():
            sym = row['Symbol']
            broker = row['Broker']
            
            if broker == "Webull" and sym in webull_prices and webull_prices[sym] > 0:
                live_prices[sym] = webull_prices[sym]
            elif broker == "Dime US" and row.get("Manual_Price") != "" and row.get("Manual_Price") is not None:
                try: live_prices[sym] = float(row["Manual_Price"])
                except: live_prices[sym] = 0.0
            
            if sym not in live_prices or live_prices[sym] == 0.0:
                yf_sym = f"{sym}.BK" if broker == "Dime TH" and not sym.endswith(".BK") else sym
                try:
                    t_data = yf.Ticker(yf_sym)
                    p = t_data.info.get('currentPrice') or t_data.info.get('regularMarketPrice') or t_data.fast_info.get('last_price')
                    if not p:
                        h = t_data.history(period="1d")
                        if not h.empty: p = h['Close'].iloc[-1]
                    live_prices[sym] = float(p) if p else 0.0
                except:
                    live_prices[sym] = 0.0

        portfolio_rows = []
        for index, row in df_raw.iterrows():
            sym = row['Symbol']
            qty = row['Qty']
            cost_in = row['Cost']
            broker = row['Broker']
            
            price_raw = live_prices.get(sym, 0)
            if price_raw == 0: price_raw = cost_in
            
            if broker == "Dime TH":
                invested_usd = (qty * cost_in) / fx_rate
                market_val_usd = (qty * price_raw) / fx_rate
            else:
                invested_usd = qty * cost_in
                market_val_usd = qty * price_raw
                
            pnl_usd = market_val_usd - invested_usd
            pnl_pct = (pnl_usd / invested_usd * 100) if invested_usd > 0 else 0.0
            
            portfolio_rows.append({
                "Symbol": sym, "Broker": broker, "Qty": qty, "Cost": cost_in, "Price": price_raw,
                "Invested_USD": invested_usd, "Market_Value_USD": market_val_usd,
                "PnL_USD": pnl_usd, "PnL_Pct": pnl_pct
            })
        df_port = pd.DataFrame(portfolio_rows)
    else:
        df_port = pd.DataFrame()
        
    st.session_state["all_holdings_df"] = df_port
    st.session_state["usd_thb_rate"] = fx_rate
    return df_port, fx_rate

def sync_portfolio_snapshot_to_gsheet(market_val, invested_val, pnl_val, pnl_pct):
    gc = get_gspread_client()
    if not gc:
        return False, "ไม่พบการเชื่อมต่อ Google Sheets Credentials"
    try:
        sh = gc.open("หุ้นของเรา")
        try:
            worksheet = sh.worksheet("Portfolio_History")
        except:
            worksheet = sh.add_worksheet(title="Portfolio_History", rows="1000", cols="5")
            worksheet.append_row(["Timestamp", "Market Value", "Invested Value", "PnL Value", "PnL %"])
            
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [now_str, round(market_val, 2), round(invested_val, 2), round(pnl_val, 2), f"{pnl_pct:.2f}%"]
        worksheet.append_row(new_row)
        return True, "บันทึกประวัติลง Portfolio_History สำเร็จ!"
    except Exception as e:
        return False, f"เกิดข้อผิดพลาดในการเขียน Google Sheets: {str(e)}"

def load_history_from_gsheet():
    gc = get_gspread_client()
    if not gc:
        return None
    try:
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Portfolio_History")
        data = worksheet.get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=["Timestamp", "MarketValue", "Invested", "PnL", "PnLPct"])
            def clean_num(val):
                if pd.isna(val): return 0.0
                return float(str(val).replace(",", "").replace("%", "").strip() or 0)
            df["MarketValue"] = df["MarketValue"].apply(clean_num)
            return df
    except Exception:
        pass
    return None

# ==========================================
# 3. DASHBOARD MAIN RENDER FUNCTION
# ==========================================
def render_dashboard():
    df_port, fx_rate = load_master_portfolio_data()

    # Calculate Real Portfolio Totals
    if not df_port.empty:
        tot_invested_usd = df_port['Invested_USD'].sum()
        tot_market_usd = df_port['Market_Value_USD'].sum()
        tot_pnl_usd = tot_market_usd - tot_invested_usd
        tot_pnl_pct = (tot_pnl_usd / tot_invested_usd * 100) if tot_invested_usd > 0 else 0.0
    else:
        tot_invested_usd, tot_market_usd, tot_pnl_usd, tot_pnl_pct = 0.0, 0.0, 0.0, 0.0

    # Top Ticker Marquee
    ticker_cards_html = ""
    if not df_port.empty:
        top_stocks = df_port.sort_values(by="Market_Value_USD", ascending=False).head(6)
        for _, r in top_stocks.iterrows():
            badge_cls = "badge-mini-pos" if r['PnL_Pct'] >= 0 else "badge-mini-neg"
            sign = "+" if r['PnL_Pct'] >= 0 else ""
            ticker_cards_html += f"""<div class="ticker-card-pill"><span class="ticker-card-symbol">{r['Symbol']}</span><span class="ticker-card-price">${r['Price']:,.2f}</span><span class="{badge_cls}">{sign}{r['PnL_Pct']:.2f}%</span></div>"""
    else:
        ticker_cards_html = """<div class="ticker-card-pill"><span class="ticker-card-symbol">N/A</span><span class="ticker-card-price">$0.00</span><span class="badge-mini-pos">+0.00%</span></div>"""

    st.markdown(f"""<div class="ticker-container"><div class="ticker-track">{ticker_cards_html}{ticker_cards_html}</div></div>""", unsafe_allow_html=True)

    c_title, c_curr = st.columns([3, 1])
    with c_title:
        st.title("Executive Dashboard")
    with c_curr:
        currency_selected = st.radio("Display Currency", ("USD ($)", "THB (฿)"), horizontal=True, index=0)

    is_usd = "USD" in currency_selected
    multiplier = 1.0 if is_usd else fx_rate
    symbol = "$" if is_usd else "฿"

    display_market = tot_market_usd * multiplier
    display_pnl = tot_pnl_usd * multiplier

    pnl_badge = "badge-delta-pos" if display_pnl >= 0 else "badge-delta-neg"
    pnl_sign = "+" if display_pnl >= 0 else ""

    st.markdown("<br>", unsafe_allow_html=True)
    col_left, col_right = st.columns([1.1, 1.9])

    with col_left:
        # Broker Breakdown
        broker_vals = df_port.groupby("Broker")["Market_Value_USD"].sum().to_dict() if not df_port.empty else {}
        webull_mkt = broker_vals.get("Webull", 0.0) * multiplier
        dime_us_mkt = broker_vals.get("Dime US", 0.0) * multiplier
        dime_th_mkt = broker_vals.get("Dime TH", 0.0) * multiplier

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
            <div style="margin-top: 20px; font-size: 0.8rem; color: #6b7280; font-weight: 600;">Broker Allocation Breakdown</div>
            <div class="allocation-bar-container">
                <div class="bar-segment" style="width: 50%; background-color: #3b82f6;"></div>
                <div class="bar-segment" style="width: 35%; background-color: #a855f7;"></div>
                <div class="bar-segment" style="width: 15%; background-color: #34d399;"></div>
            </div>
            <div class="asset-row">
                <div class="asset-label"><div class="dot" style="background-color: #3b82f6;"></div> 🇺🇸 Dime US</div>
                <div class="asset-val">{symbol}{dime_us_mkt:,.2f}</div>
            </div>
            <div class="asset-row">
                <div class="asset-label"><div class="dot" style="background-color: #a855f7;"></div> ⚡ Webull US</div>
                <div class="asset-val">{symbol}{webull_mkt:,.2f}</div>
            </div>
            <div class="asset-row" style="border-bottom: none;">
                <div class="asset-label"><div class="dot" style="background-color: #34d399;"></div> 🇹🇭 Dime TH</div>
                <div class="asset-val">{symbol}{dime_th_mkt:,.2f}</div>
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

    with col_right:
        tf_col1, tf_col2 = st.columns([3, 1])
        with tf_col1:
            selected_tf = st.select_slider("Timeframe Range", options=["1D", "7D", "1M", "3M", "6M", "1Y", "3Y", "MAX"], value="6M")
        with tf_col2:
            st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)
            if st.button("🔄 Sync Snapshot", use_container_width=True, type="primary"):
                with st.spinner("⏳ บันทึกประวัติลง Google Sheets..."):
                    success, msg = sync_portfolio_snapshot_to_gsheet(tot_market_usd, tot_invested_usd, tot_pnl_usd, tot_pnl_pct)
                    if success:
                        st.toast(f"✅ {msg}", icon="🎉")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        df_history = load_history_from_gsheet()
        if df_history is not None and not df_history.empty:
            x_axis = df_history["Timestamp"].tolist()
            y_axis = (df_history["MarketValue"] * multiplier).tolist()
        else:
            x_axis = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul']
            y_axis = [display_market*0.9, display_market*0.93, display_market*0.91, display_market*0.96, display_market*0.94, display_market*0.98, display_market]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_axis, y=y_axis, mode='lines+markers', line=dict(color='#38bdf8', width=3, shape='spline'), fill='tozeroy', fillcolor='rgba(56, 189, 248, 0.05)'))
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#6b7280', family='Plus Jakarta Sans'), xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=True, gridcolor='#16181f', zeroline=False), margin=dict(t=10, b=10, l=10, r=10), height=250)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # Top Holdings Section
    if not df_port.empty:
        st.markdown('<div style="font-size: 0.85rem; font-weight: 600; color: #9ca3af; margin-bottom: 10px;">Top Holdings Performance</div>', unsafe_allow_html=True)
        top_3 = df_port.sort_values(by="Market_Value_USD", ascending=False).head(3)
        cols = st.columns(3)
        for idx, (_, r) in enumerate(top_3.iterrows()):
            with cols[idx]:
                badge_cls = "badge-delta-pos" if r['PnL_Pct'] >= 0 else "badge-delta-neg"
                icon = "🟢" if r['PnL_Pct'] >= 0 else "🔴"
                sign = "+" if r['PnL_Pct'] >= 0 else ""
                disp_p = r['Price'] * multiplier
                st.markdown(f'<div class="stock-grid-card"><div style="display:flex; justify-content:space-between; align-items:center;"><span class="stock-symbol">{icon} {r["Symbol"]}</span><span class="{badge_cls}">{sign}{r["PnL_Pct"]:.2f}%</span></div><div class="stock-price">{symbol}{disp_p:,.2f}</div></div>', unsafe_allow_html=True)

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
