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
import plotly.express as px
import yfinance as yf
import gspread
from datetime import datetime, timezone

# 1. ตั้งค่าหน้าตา Dashboard
st.set_page_config(page_title="Master Portfolio Dashboard", layout="wide")

st.markdown("""
    <style>
    .metric-container {
        background-color: #1e222d;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #2a2e39;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    .metric-label { color: #848e9c; font-size: 16px; font-weight: 500; margin-bottom: 8px; }
    .metric-value { color: #ffffff; font-size: 32px; font-weight: 700; }
    .pnl-positive { color: #00c853 !important; }
    .pnl-negative { color: #ff3d00 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Master Dashboard: วิเคราะห์พอร์ตโฟลิโอรวม")
st.markdown("---")

def clean_num(val):
    if pd.isna(val) or val is None:
        return 0.0
    try:
        s = str(val).replace("$", "").replace("฿", "").replace(",", "").strip()
        return float(s)
    except:
        return 0.0

@st.cache_data(ttl=3600)
def get_usd_thb_rate():
    try:
        ticker = yf.Ticker("USDTHB=X")
        rate = ticker.fast_info.get('last_price') or ticker.info.get('regularMarketPrice') or 35.0
        return float(rate)
    except:
        return 35.0

fx_rate = get_usd_thb_rate()

@st.cache_resource
def init_gsheet():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64: return None
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        return gc.open("หุ้นของเรา")
    except Exception as e:
        st.error(f"⚠️ เกิดข้อผิดพลาดในการเชื่อมต่อ Google Sheets: {e}")
        return None

sh = init_gsheet()

# --- ดึงข้อมูลจากโบรกเกอร์ต่างๆ ---
def load_all_portfolios():
    all_holdings = []
    
    if not sh:
        return pd.DataFrame()

    # 1. ดึงข้อมูล Dime US
    try:
        ws_us = sh.worksheet("Dime_Portfolio")
        rec_us = ws_us.get_all_records()
        if rec_us:
            df_us = pd.DataFrame(rec_us)
            sym_col = next((c for c in df_us.columns if 'ticker' in str(c).lower() or 'symbol' in str(c).lower() or 'หุ้น' in str(c)), None)
            qty_col = next((c for c in df_us.columns if 'volume' in str(c).lower() or 'qty' in str(c).lower() or 'จำนวน' in str(c)), None)
            cost_col = next((c for c in df_us.columns if 'cost' in str(c).lower() or 'ต้นทุน' in str(c)), None)

            if sym_col and qty_col and cost_col:
                syms = [str(r[sym_col]).strip().upper() for _, r in df_us.iterrows() if str(r[sym_col]).strip()]
                prices = {}
                try:
                    t_data = yf.download(tickers=syms, period="5d", interval="1d", progress=False)
                    if not t_data.empty and 'Close' in t_data:
                        for s in syms:
                            try:
                                val = t_data['Close'][s].dropna().iloc[-1] if len(syms) > 1 else t_data['Close'].dropna().iloc[-1]
                                prices[s] = float(val)
                            except: pass
                except: pass

                for _, r in df_us.iterrows():
                    sym = str(r[sym_col]).strip().upper()
                    if not sym: continue
                    qty = clean_num(r[qty_col])
                    avg_cost = clean_num(r[cost_col])
                    if qty <= 0: continue
                    
                    p_now = prices.get(sym, avg_cost)
                    invested = qty * avg_cost
                    market_val = qty * p_now
                    pnl = market_val - invested
                    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

                    all_holdings.append({
                        "Broker": "Dime US",
                        "Symbol": sym,
                        "Qty": qty,
                        "Avg_Cost": avg_cost,
                        "Current_Price": p_now,
                        "Invested_USD": invested,
                        "Market_Val_USD": market_val,
                        "PnL": pnl,
                        "PnL_Pct": pnl_pct,
                        "Sector": "US Equities"
                    })
    except Exception as e:
        pass

    # 2. ดึงข้อมูล Dime TH (แปลงเป็น USD เพื่อสรุป Master Dashboard)
    try:
        ws_th = sh.worksheet("Dime_TH_Portfolio")
        rec_th = ws_th.get_all_records()
        if rec_th:
            df_th = pd.DataFrame(rec_th)
            sym_col = next((c for c in df_th.columns if 'ticker' in str(c).lower() or 'symbol' in str(c).lower() or 'หุ้น' in str(c)), None)
            qty_col = next((c for c in df_th.columns if 'volume' in str(c).lower() or 'qty' in str(c).lower() or 'จำนวน' in str(c)), None)
            cost_col = next((c for c in df_th.columns if 'cost' in str(c).lower() or 'ต้นทุน' in str(c)), None)

            if sym_col and qty_col and cost_col:
                syms = [f"{str(r[sym_col]).strip().upper()}.BK" for _, r in df_th.iterrows() if str(r[sym_col]).strip()]
                prices = {}
                try:
                    t_data = yf.download(tickers=syms, period="5d", interval="1d", progress=False)
                    if not t_data.empty and 'Close' in t_data:
                        for s in syms:
                            orig = s.replace(".BK", "")
                            try:
                                val = t_data['Close'][s].dropna().iloc[-1] if len(syms) > 1 else t_data['Close'].dropna().iloc[-1]
                                prices[orig] = float(val)
                            except: pass
                except: pass

                for _, r in df_th.iterrows():
                    sym = str(r[sym_col]).strip().upper()
                    if not sym: continue
                    qty = clean_num(r[qty_col])
                    avg_cost_thb = clean_num(r[cost_col])
                    if qty <= 0: continue
                    
                    p_now_thb = prices.get(sym, avg_cost_thb)
                    invested_thb = qty * avg_cost_thb
                    market_val_thb = qty * p_now_thb
                    pnl_thb = market_val_thb - invested_thb
                    pnl_pct = (pnl_thb / invested_thb * 100) if invested_thb > 0 else 0.0

                    all_holdings.append({
                        "Broker": "Dime TH",
                        "Symbol": sym,
                        "Qty": qty,
                        "Avg_Cost": avg_cost_thb / fx_rate,
                        "Current_Price": p_now_thb / fx_rate,
                        "Invested_USD": invested_thb / fx_rate,
                        "Market_Val_USD": market_val_thb / fx_rate,
                        "PnL": pnl_thb / fx_rate,
                        "PnL_Pct": pnl_pct,
                        "Sector": "Thai Equities"
                    })
    except Exception as e:
        pass

    return pd.DataFrame(all_holdings)

# โหลดข้อมูลพอร์ตทั้งหมด
with st.spinner("⏳ กำลังโหลดและประมวลผลข้อมูลพอร์ตโฟลิโอภาพรวม..."):
    df_port = load_all_portfolios()

if not df_port.empty:
    total_invested = df_port["Invested_USD"].sum()
    total_market_val = df_port["Market_Val_USD"].sum()
    total_pnl = total_market_val - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

    pnl_class = "pnl-positive" if total_pnl >= 0 else "pnl-negative"
    pnl_prefix = "+" if total_pnl >= 0 else ""

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="metric-container"><div class="metric-label">💵 เงินลงทุนรวมทั้งหมด ($ USD)</div><div class="metric-value">${total_invested:,.2f}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-container"><div class="metric-label">📈 มูลค่าพอร์ตรวมปัจจุบัน ($ USD)</div><div class="metric-value">${total_market_val:,.2f}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-container"><div class="metric-label">📊 กำไร / ขาดทุนสุทธิรวม</div><div class="metric-value {pnl_class}">{pnl_prefix}${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # --- กราฟวิเคราะห์พอร์ต ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🥧 สัดส่วนเงินลงทุนแยกตามโบรกเกอร์ / พอร์ต")
        df_broker = df_port.groupby("Broker")["Market_Val_USD"].sum().reset_index()
        fig_broker = px.pie(
            df_broker, 
            values='Market_Val_USD', 
            names='Broker', 
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.Tealgrn
        )
        fig_broker.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
        st.plotly_chart(fig_broker, use_container_width=True)

    with col2:
        st.subheader("📊 ยอดกำไร / ขาดทุนสุทธิแยกตามโบรกเกอร์")
        df_pnl_broker = df_port.groupby("Broker")["PnL"].sum().reset_index()
        df_pnl_broker['Color'] = df_
