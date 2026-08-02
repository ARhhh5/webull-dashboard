import os
import json
import base64
import urllib.parse
import http.client
import uuid
import hmac
import hashlib
import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from datetime import datetime, timezone

# ==========================================
# 1. PAGE CONFIG & MODERN DARK CSS
# ==========================================
st.set_page_config(page_title="Winner Tilt Strategy", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    /* Minimal Header */
    .page-title-minimal {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 1.4rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.5px;
        margin-bottom: 2px;
    }
    .page-subtitle-minimal {
        color: #6b7280;
        font-size: 0.85rem;
        margin-bottom: 18px;
    }

    /* Modern Pill Action Buttons */
    div[data-testid="stColumn"] div.stButton > button {
        background-color: #0f1115 !important;
        border: 1px solid #1a1d24 !important;
        border-radius: 10px !important;
        padding: 8px 14px !important;
        color: #9ca3af !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        transition: all 0.25s ease !important;
        width: 100% !important;
    }

    div[data-testid="stColumn"] div.stButton > button:hover {
        border-color: #38bdf8 !important;
        color: #ffffff !important;
        background-color: #141822 !important;
    }

    /* Active Segmented Button Highlight */
    div[data-testid="stColumn"] div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
        border: 1px solid #38bdf8 !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(56, 189, 248, 0.25) !important;
    }

    /* Status Cards */
    .status-card {
        background-color: #0f1115;
        padding: 18px;
        border-radius: 12px;
        border: 1px solid #1a1d24;
        text-align: center;
    }
    .status-title { color: #9ca3af; font-size: 13px; font-weight: 600; margin-bottom: 5px; text-transform: uppercase; }
    .status-value { font-size: 24px; font-weight: 800; font-family: 'JetBrains Mono', monospace; }
    .status-bull { color: #4ade80 !important; }
    .status-bear { color: #f87171 !important; }

    /* Custom Input Controls */
    div[data-baseweb="input"] > div {
        background-color: #0f1115 !important;
        border-color: #1a1d24 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Minimal Header
st.markdown('<div class="page-title-minimal">🏆 The Winner Tilt Playbook Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle-minimal">ระบบวิเคราะห์กลยุทธ์ Winner Tilt 25 พร้อมระบบสแกนเส้น SMA 200 วัน</div>', unsafe_allow_html=True)

# ==========================================
# 2. UNIVERSE & MARKET DATA PIPELINE
# ==========================================
UNIVERSE_QQQ_15 = ["NVDA", "AAPL", "MU", "MSFT", "AMZN", "AMD", "GOOGL", "TSLA", "INTC", "AVGO", "META", "AMAT", "LRCX", "CSCO", "SNDK"]
UNIVERSE_VOO_5 = ["LLY", "BRK-B", "JPM", "JNJ", "V"]
UNIVERSE_SMH_5 = ["TSM", "KLAC", "ASML", "MRVL", "TXN"]
HEDGE_ASSET = ["GLD"]

ALL_STRATEGY_TICKERS = list(set(UNIVERSE_QQQ_15 + UNIVERSE_VOO_5 + UNIVERSE_SMH_5 + HEDGE_ASSET))

def format_ticker_for_yf(symbol):
    sym_clean = str(symbol).strip().upper()
    if not sym_clean:
        return ""
    # ถ้าเป็นหุ้นไทย (ไม่มีจุด และยาวไม่เกิน 5 ตัวอักษร เช่น KKP, JAS, SUSCO)
    if "." not in sym_clean and len(sym_clean) <= 6 and sym_clean not in ALL_STRATEGY_TICKERS and sym_clean not in ["SPY", "QQQ", "SMH", "GLD"]:
        # เช็กกรณีหุ้นไทย
        if not sym_clean.endswith(".BK"):
            return f"{sym_clean}.BK"
    return sym_clean

@st.cache_data(ttl=1800)
def fetch_market_data(tickers):
    if not tickers:
        return pd.DataFrame()
        
    data_list = []
    for symbol in tickers:
        raw_sym = str(symbol).strip().upper()
        if not raw_sym:
            continue
            
        yf_sym = format_ticker_for_yf(raw_sym)
        
        try:
            ticker = yf.Ticker(yf_sym)
            df_hist = ticker.history(period="1y")
            
            # ลองดึงข้อมูลย้อนหลังถ้า period="1y" ว่างเปล่า
            if df_hist.empty:
                yf_sym_alt = raw_sym if yf_sym.endswith(".BK") else f"{raw_sym}.BK"
                ticker = yf.Ticker(yf_sym_alt)
                df_hist = ticker.history(period="1y")

            if not df_hist.empty and len(df_hist) >= 10:
                current_price = float(df_hist['Close'].iloc[-1])
                
                # ถ้ามีข้อมูลเกิน 200 วัน คำนวณ SMA 200
                if len(df_hist) >= 200:
                    sma_200 = float(df_hist['Close'].rolling(window=200).mean().iloc[-1])
                else:
                    sma_200 = float(df_hist['Close'].mean()) # ใช้ค่าเฉลี่ยเท่าที่มีถ้าไม่ถึง 200 วัน
                
                if sma_200 > 0:
                    diff_pct = ((current_price - sma_200) / sma_200) * 100
                else:
                    diff_pct = 0.0
                    
                is_above_sma = current_price >= sma_200
                
                data_list.append({
                    "Symbol": raw_sym,
                    "Current_Price": current_price,
                    "SMA_200": sma_200,
                    "Diff_Pct": diff_pct,
                    "Above_SMA200": is_above_sma
                })
            else:
                # Fallback ด้วย FastInfo ป้องกันราคาเป็น 0.00
                try:
                    fast_p = ticker.fast_info.get('lastPrice', 0.0)
                    if fast_p > 0:
                        data_list.append({
                            "Symbol": raw_sym, "Current_Price": float(fast_p), "SMA_200": float(fast_p), "Diff_Pct": 0.0, "Above_SMA200": True
                        })
                    else:
                        data_list.append({"Symbol": raw_sym, "Current_Price": 0.0, "SMA_200": 0.0, "Diff_Pct": 0.0, "Above_SMA200": False})
                except Exception:
                    data_list.append({"Symbol": raw_sym, "Current_Price": 0.0, "SMA_200": 0.0, "Diff_Pct": 0.0, "Above_SMA200": False})
        except Exception:
            data_list.append({"Symbol": raw_sym, "Current_Price": 0.0, "SMA_200": 0.0, "Diff_Pct": 0.0, "Above_SMA200": False})
            
    return pd.DataFrame(data_list)

# ==========================================
# 3. GET USER PORTFOLIO SYMBOLS
# ==========================================
def get_user_portfolio_symbols():
    symbols = set()
    
    # 3.1 Webull
    webull_config = st.secrets.get("Webull", {})
    APP_KEY = webull_config.get("AppKey", "").strip() or webull_config.get("app_key", "").strip()
    APP_SECRET = webull_config.get("AppSecret", "").strip() or webull_config.get("app_secret", "").strip()
    ACCESS_TOKEN = webull_config.get("AccessToken", "").strip()
    ACCOUNT_ID = webull_config.get("AccountId", "").strip() or webull_config.get("account_id", "").strip()
    HOST = "api.webull.co.th"

    if APP_KEY and ACCOUNT_ID:
        try:
            path = "/openapi/assets/positions"
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            nonce = uuid.uuid4().hex
            signing_values = {"host": HOST, "x-app-key": APP_KEY, "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-signature-version": "1.0", "x-timestamp": timestamp, "account_id": ACCOUNT_ID}
            string_1 = "&".join(f"{key}={signing_values[key]}" for key in sorted(signing_values))
            signature = base64.b64encode(hmac.new(f"{APP_SECRET}&".encode("utf-8"), urllib.parse.quote(f"{path}&{string_1}", safe="").encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
            headers = {"Accept": "application/json", "x-app-key": APP_KEY, "x-timestamp": timestamp, "x-signature-version": "1.0", "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-version": "v2", "x-signature": signature, "x-access-token": ACCESS_TOKEN}
            
            conn = http.client.HTTPSConnection(HOST)
            conn.request("GET", f"{path}?account_id={ACCOUNT_ID}", "", headers)
            res = conn.getresponse()
            data = json.loads(res.read().decode("utf-8"))
            if isinstance(data, list):
                for p in data:
                    if p.get("instrument_type") == "EQUITY":
                        symbols.add(str(p.get("symbol", "")).strip().upper())
        except Exception:
            pass

    # 3.2 Google Sheets (Dime US & Dime TH)
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            gc = gspread.service_account_from_dict(cred_dict)
            sh = gc.open("หุ้นของเรา")
            
            # Dime US
            try:
                ws_us = sh.worksheet("Dime_Portfolio")
                for r in ws_us.get_all_records():
                    sym = str(r.get("หุ้น (Ticker)", r.get("Ticker", r.get("Symbol", "")))).strip().upper()
                    if sym: symbols.add(sym)
            except Exception: pass

            # Dime TH
            try:
                ws_th = sh.worksheet("Dime_TH_Portfolio")
                for r in ws_th.get_all_records():
                    sym = str(r.get("หุ้น (Ticker)", r.get("Ticker", r.get("Symbol", "")))).strip().upper()
                    if sym: symbols.add(sym)
            except Exception: pass
    except Exception:
        pass

    return list(symbols)

def style_trend_table(val):
    if "PASS" in str(val):
        return 'background-color: #052e16; color: #4ade80; font-weight: bold;'
    elif "FAIL" in str(val):
        return 'background-color: #450a0a; color: #f87171; font-weight: bold;'
    return ''

# ==========================================
# 4. SEGMENTED PILL BUTTON NAVIGATION
# ==========================================
if "wt_tab_mode" not in st.session_state:
    st.session_state["wt_tab_mode"] = "UNIVERSE"

tab_mode = st.session_state["wt_tab_mode"]

c_b1, c_b2, c_b3 = st.columns(3)

with c_b1:
    b1_type = "primary" if tab_mode == "UNIVERSE" else "secondary"
    if st.button("📊 1. Winner Tilt Universe", key="btn_wt_univ", type=b1_type, use_container_width=True):
        st.session_state["wt_tab_mode"] = "UNIVERSE"
        st.rerun()

with c_b2:
    b2_type = "primary" if tab_mode == "MY_PORT" else "secondary"
    if st.button("💼 2. หุ้นในพอร์ตของฉัน", key="btn_wt_port", type=b2_type, use_container_width=True):
        st.session_state["wt_tab_mode"] = "MY_PORT"
        st.rerun()

with c_b3:
    b3_type = "primary" if tab_mode == "TARGET" else "secondary"
    if st.button("🎯 3. หุ้นที่ต้องการซื้อ", key="btn_wt_target", type=b3_type, use_container_width=True):
        st.session_state["wt_tab_mode"] = "TARGET"
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 5. TAB CONTENTS
# ==========================================

# ------------------------------------------
# MODE 1: WINNER TILT UNIVERSE
# ------------------------------------------
if tab_mode == "UNIVERSE":
    st.markdown("### 1. 📈 Market Regime First (เช็กสภาวะตลาดใหญ่)")
    st.caption("ดัชนีหลักต้องอยู่เหนือเส้น SMA 200 วัน เพื่อยืนยันว่าตลาดยังอยู่ในสภาวะขาขึ้นที่เกื้อหนุนกลยุทธ์")

    with st.spinner("⏳ กำลังวิเคราะห์สภาวะตลาดใหญ่ (S&P 500, Nasdaq 100, SMH)..."):
        market_benchmarks = ["SPY", "QQQ", "SMH"]
        df_market = fetch_market_data(market_benchmarks)
        
        col_m1, col_m2, col_m3 = st.columns(3)
        cols = [col_m1, col_m2, col_m3]
        
        for i, row in df_market.iterrows():
            sym = row["Symbol"]
            status_text = "เหนือเส้น 200 วัน (Bullish)" if row["Above_SMA200"] else "ต่ำกว่าเส้น 200 วัน (Caution)"
            status_class = "status-bull" if row["Above_SMA200"] else "status-bear"
            
            with cols[i]:
                st.markdown(f"""
                    <div class="status-card">
                        <div class="status-title">{sym} Benchmark</div>
                        <div class="status-value {status_class}">${row['Current_Price']:,.2f}</div>
                        <div style="font-size: 13px; margin-top: 5px;" class="{status_class}">{status_text} ({row['Diff_Pct']:+.2f}%)</div>
                    </div>
                """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 2. 🔍 Winner Tilt 25 Checklist")

    with st.spinner("⏳ กำลังสแกนหุ้น Winner Tilt Universe..."):
        df_assets = fetch_market_data(ALL_STRATEGY_TICKERS)
        
        def get_group_name(sym):
            if sym in UNIVERSE_QQQ_15: return "QQQ 15 (Growth)"
            if sym in UNIVERSE_VOO_5: return "VOO 5 (Quality)"
            if sym in UNIVERSE_SMH_5: return "SMH 5 (Semi/AI)"
            if sym in HEDGE_ASSET: return "GLD (Hedge)"
            return "Other"

        df_assets["Group"] = df_assets["Symbol"].apply(get_group_name)

    groups = ["QQQ 15 (Growth)", "VOO 5 (Quality)", "SMH 5 (Semi/AI)", "GLD (Hedge)"]

    for grp in groups:
        st.markdown(f"#### 📌 กลุ่ม {grp}")
        df_sub = df_assets[df_assets["Group"] == grp].copy()
        
        if not df_sub.empty:
            df_sub["Status_Signal"] = df_sub["Above_SMA200"].apply(
                lambda x: "PASS (เหนือ 200 วัน ➔ ถือต่อ)" if x else "FAIL (หลุดเส้น 200 วัน ➔ เตรียมขายคัดออก)"
            )
            
            df_display = df_sub[["Symbol", "Current_Price", "SMA_200", "Diff_Pct", "Status_Signal"]].rename(columns={
                "Current_Price": "ราคาปัจจุบัน ($)",
                "SMA_200": "เส้น SMA 200 วัน ($)",
                "Diff_Pct": "ระยะห่างจาก SMA200 (%)",
                "Status_Signal": "สถานะสัญญาณ Rebalance"
            })
            
            formatted_df = df_display.style.format({
                "ราคาปัจจุบัน ($)": "${:,.2f}",
                "เส้น SMA 200 วัน ($)": "${:,.2f}",
                "ระยะห่างจาก SMA200 (%)": "{:+.2f}%"
            }).map(style_trend_table, subset=["สถานะสัญญาณ Rebalance"])
            
            st.dataframe(formatted_df, use_container_width=True, hide_index=True)

# ------------------------------------------
# MODE 2: หุ้นในพอร์ตของฉัน
# ------------------------------------------
elif tab_mode == "MY_PORT":
    st.markdown("### 💼 ตรวจสอบสุขภาพหุ้นที่ถือครองอยู่จริงในพอร์ต (My Portfolio Trend Filter)")
    st.caption("ดึงข้อมูลจาก Webull, Dime US และ Dime TH เพื่อสแกนว่าหุ้นที่คุณถืออยู่ ตัวไหนยังยืนเหนือเส้น SMA 200 วัน")
    
    with st.spinner("⏳ กำลังดึงรายชื่อหุ้นในพอร์ตของคุณและประมวลผลเส้น 200 วัน..."):
        my_symbols = get_user_portfolio_symbols()
        
        if my_symbols:
            df_my_p = fetch_market_data(my_symbols)
            
            if not df_my_p.empty:
                df_my_p["Status_Signal"] = df_my_p["Above_SMA200"].apply(
                    lambda x: "PASS (เหนือ 200 วัน ➔ ถือต่อ)" if x else "FAIL (หลุดเส้น 200 วัน ➔ เตรียมขายคัดออก)"
                )
                
                df_my_disp = df_my_p[["Symbol", "Current_Price", "SMA_200", "Diff_Pct", "Status_Signal"]].rename(columns={
                    "Current_Price": "ราคาปัจจุบัน ($/฿)",
                    "SMA_200": "เส้น SMA 200 วัน ($/฿)",
                    "Diff_Pct": "ระยะห่างจาก SMA200 (%)",
                    "Status_Signal": "สถานะสัญญาณ Rebalance"
                })
                
                formatted_my_df = df_my_disp.style.format({
                    "ราคาปัจจุบัน ($/฿)": "{:,.2f}",
                    "เส้น SMA 200 วัน ($/฿)": "{:,.2f}",
                    "ระยะห่างจาก SMA200 (%)": "{:+.2f}%"
                }).map(style_trend_table, subset=["สถานะสัญญาณ Rebalance"])
                
                st.dataframe(formatted_my_df, use_container_width=True, hide_index=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                df_my_failed = df_my_p[~df_my_p["Above_SMA200"]]
                if not df_my_failed.empty:
                    st.error("🚨 **คำเตือนหุ้นในพอร์ตที่หลุดเส้น 200 วัน:**")
                    for _, r in df_my_failed.iterrows():
                        st.write(f"• **{r['Symbol']}**: ราคาปัจจุบัน {r['Current_Price']:,.2f} ต่ำกว่าเส้น 200 วัน ({r['SMA_200']:,.2f}) อยู่ {r['Diff_Pct']:.2f}% ➔ **พิจารณาคัดออกรอบ Rebalance**")
                else:
                    st.success("✅ ยินดีด้วย! หุ้นทุกตัวในพอร์ตของคุณยังคงยืนเหนือเส้น SMA 200 วัน ได้ทั้งหมด")
        else:
            st.info("💡 ไม่พบรายการหุ้นในพอร์ตของคุณจาก Webull หรือ Google Sheets")

# ------------------------------------------
# MODE 3: หุ้นที่ต้องการซื้อ
# ------------------------------------------
elif tab_mode == "TARGET":
    st.markdown("### 🎯 สแกนหุ้นที่กำลังเล็งไว้ก่อนตัดสินใจซื้อ (Target Buying Watchlist)")
    st.caption("พิมพ์ชื่อ Ticker หุ้นที่ต้องการสแกน (เช่น MU, NVDA, PLTR, PTT) หากต้องการค้นหาหลายตัวให้คั่นด้วยเครื่องหมายจุลภาค ( , )")
    
    input_symbols = st.text_input(
        "🔎 พิมพ์ชื่อ Ticker หุ้นที่ต้องการสแกน:",
        value="",
        placeholder="ตัวอย่าง: MU, NVDA, TSLA, PTT"
    )
    
    if input_symbols.strip():
        target_list = [s.strip().upper() for s in input_symbols.split(",") if s.strip()]
        
        with st.spinner("⏳ กำลังสแกนหุ้นเป้าหมาย..."):
            df_target = fetch_market_data(target_list)
            
            if not df_target.empty:
                df_target["Status_Signal"] = df_target["Above_SMA200"].apply(
                    lambda x: "PASS (เหนือ 200 วัน ➔ พร้อมเข้าซื้อ)" if x else "FAIL (ต่ำกว่า 200 วัน ➔ รอก่อน ยังไม่น่าซื้อ)"
                )
                
                df_target_disp = df_target[["Symbol", "Current_Price", "SMA_200", "Diff_Pct", "Status_Signal"]].rename(columns={
                    "Current_Price": "ราคาปัจจุบัน ($/฿)",
                    "SMA_200": "เส้น SMA 200 วัน ($/฿)",
                    "Diff_Pct": "ระยะห่างจาก SMA200 (%)",
                    "Status_Signal": "คำแนะนำการเข้าซื้อ"
                })
                
                formatted_target_df = df_target_disp.style.format({
                    "ราคาปัจจุบัน ($/฿)": "{:,.2f}",
                    "เส้น SMA 200 วัน ($/฿)": "{:,.2f}",
                    "ระยะห่างจาก SMA200 (%)": "{:+.2f}%"
                }).map(style_trend_table, subset=["คำแนะนำการเข้าซื้อ"])
                
                st.dataframe(formatted_target_df, use_container_width=True, hide_index=True)
    else:
        st.info("💡 พิมพ์รายชื่อ Ticker หุ้นในช่องด้านบน แล้วกด Enter เพื่อเริ่มสแกนสัญญาณซื้อตามเส้น SMA 200 วันได้ทันที!")
