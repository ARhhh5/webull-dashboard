import streamlit as st
import pandas as pd
import json
import base64
import urllib.parse
import http.client
import uuid
import hmac
import hashlib
import gspread
import plotly.express as px
from datetime import datetime, timezone

st.set_page_config(page_title="Trade History & Realized PnL", layout="wide")

st.title("📜 ประวัติการเทรด & สรุปกำไร/ขาดทุนที่เกิดขึ้นจริง (Realized PnL)")
st.markdown("---")

# ดึง Config Webull
webull_config = st.secrets.get("Webull", {})
APP_KEY = webull_config.get("AppKey", "").strip()
APP_SECRET = webull_config.get("AppSecret", "").strip()
ACCESS_TOKEN = webull_config.get("AccessToken", "").strip()
ACCOUNT_ID = webull_config.get("AccountId", "").strip()
HOST = "api.webull.co.th"

# 1. ดึงประวัติ Webull (รองรับ Order Matching จับคู่ BUY/SELL)
def get_webull_history():
    path = "/openapi/trade/v2/orders"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex
    signing_values = {"host": HOST, "x-app-key": APP_KEY, "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-signature-version": "1.0", "x-timestamp": timestamp, "account_id": ACCOUNT_ID}
    string_1 = "&".join(f"{key}={signing_values[key]}" for key in sorted(signing_values))
    signature = base64.b64encode(hmac.new(f"{APP_SECRET}&".encode("utf-8"), urllib.parse.quote(f"{path}&{string_1}", safe="").encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
    headers = {"Accept": "application/json", "x-app-key": APP_KEY, "x-timestamp": timestamp, "x-signature-version": "1.0", "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-version": "v2", "x-signature": signature, "x-access-token": ACCESS_TOKEN}
    
    orders = []
    try:
        conn = http.client.HTTPSConnection(HOST)
        conn.request("GET", f"{path}?account_id={ACCOUNT_ID}&status=FILLED", "", headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        if isinstance(data, list):
            for o in data:
                orders.append({
                    "Date": o.get("filled_time", "")[:10],
                    "Symbol": str(o.get("symbol", "")).upper(),
                    "Action": str(o.get("action", "")).upper(), # BUY / SELL
                    "Qty": float(o.get("filled_quantity", 0)),
                    "Price": float(o.get("avg_filled_price", 0)),
                    "Broker": "Webull"
                })
    except:
        pass
    return orders

# 2. ดึงประวัติไม้ที่ปิดขายแล้วจาก Dime Sheet
def get_dime_closed_orders():
    closed_orders = []
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            gc = gspread.service_account_from_dict(cred_dict)
            sh = gc.open("หุ้นของเรา")
            worksheet = sh.worksheet("Dime_Closed_Orders")
            records = worksheet.get_all_records()
            for r in records:
                sym = str(r.get("หุ้น (Ticker)", "")).strip().upper()
                if sym:
                    market = str(r.get("ตลาด (US/TH)", "US")).strip().upper()
                    qty = float(r.get("จำนวนหุ้น (Qty)", 0))
                    buy_price = float(r.get("ราคาซื้อเฉลี่ย (Buy Price)", 0))
                    sell_price = float(r.get("ราคาขายจริง (Sell Price)", 0))
                    date = str(r.get("วันที่ปิดไม้ (Date)", ""))
                    
                    pnl = (sell_price - buy_price) * qty
                    pnl_pct = ((sell_price - buy_price) / buy_price * 100) if buy_price > 0 else 0
                    
                    closed_orders.append({
                        "Date": date,
                        "Symbol": sym,
                        "Broker": f"Dime {market}",
                        "Qty": qty,
                        "Buy Price": buy_price,
                        "Sell Price": sell_price,
                        "Realized PnL ($)": pnl,
                        "Return (%)": pnl_pct
                    })
    except:
        pass
    return closed_orders

with st.spinner("⏳ กำลังโหลดประวัติการซื้อขายและประมวลผล Realized PnL..."):
    webull_orders = get_webull_history()
    dime_closed = get_dime_closed_orders()

# TAB 1: ตารางเปรียบเทียบไม้ที่ปิดขายแล้ว (Realized PnL)
tab1, tab2 = st.tabs(["💰 สรุปไม้ที่ปิดขายแล้ว (Realized PnL)", "📑 ประวัติออเดอร์ทั้งหมด (Raw Logs)"])

with tab1:
    st.subheader("📊 เปรียบเทียบราคาซื้อ vs ราคาขายจริง (Closed Trades)")
    
    # ประมวลผล Order Matching สำหรับ Webull (ถ้ามีไม้ขายเกิดขึ้น)
    webull_matched = []
    if webull_orders:
        df_w = pd.DataFrame(webull_orders)
        symbols = df_w['Symbol'].unique()
        
        for sym in symbols:
            df_sym = df_w[df_w['Symbol'] == sym].sort_values("Date")
            buys = df_sym[df_sym['Action'] == "BUY"].to_dict('records')
            sells = df_sym[df_sym['Action'] == "SELL"].to_dict('records')
            
            for sell in sells:
                s_qty = sell['Qty']
                s_price = sell['Price']
                # คิดต้นทุนซื้อเฉลี่ยเรียบง่าย
                if buys:
                    avg_b_price = sum(b['Price'] * b['Qty'] for b in buys) / sum(b['Qty'] for b in buys) if sum(b['Qty'] for b in buys) > 0 else s_price
                    pnl = (s_price - avg_b_price) * s_qty
                    pnl_pct = ((s_price - avg_b_price) / avg_b_price * 100) if avg_b_price > 0 else 0
                    
                    webull_matched.append({
                        "Date": sell['Date'],
                        "Symbol": sym,
                        "Broker": "Webull",
                        "Qty": s_qty,
                        "Buy Price": avg_b_price,
                        "Sell Price": s_price,
                        "Realized PnL ($)": pnl,
                        "Return (%)": pnl_pct
                    })

    all_closed = dime_closed + webull_matched
    
    if all_closed:
        df_closed = pd.DataFrame(all_closed)
        
        # กล่องสรุปสถิติสำคัญ
        total_realized_pnl = df_closed['Realized PnL ($)'].sum()
        win_trades = df_closed[df_closed['Realized PnL ($)'] > 0]
        win_rate = (len(win_trades) / len(df_closed) * 100) if len(df_closed) > 0 else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 กำไร/ขาดทุนสะสมจริงทั้งหมด", f"${total_realized_pnl:,.2f}", delta=f"{total_realized_pnl:,.2f}")
        m2.metric("🎯 จำนวนไม้ที่ปิดขายแล้ว", f"{len(df_closed)} ไม้")
        m3.metric("🔥 อัตราการชนะ (Win Rate)", f"{win_rate:.1f}%")
        
        st.markdown("---")
        
        # แสดงตารางผลตอบแทน
        st.dataframe(
            df_closed.style.format({
                "Qty": "{:,.2f}",
                "Buy Price": "${:,.2f}",
                "Sell Price": "${:,.2f}",
                "Realized PnL ($)": "${:+,.2f}",
                "Return (%)": "{:+,.2f}%"
            }).map(lambda val: 'color: #00c853' if val > 0 else 'color: #ff3d00', subset=['Realized PnL ($)', 'Return (%)']),
            use_container_width=True
        )
        
        # กราฟแท่งผลตอบแทนตามรายไม้
        fig_pnl = px.bar(
            df_closed, x='Symbol', y='Realized PnL ($)', color='Broker',
            title="กำไร/ขาดทุนสะสมแยกรายหุ้น ($)",
            text_auto='.2f'
        )
        st.plotly_chart(fig_pnl, use_container_width=True)
    else:
        st.info("ยังไม่มีประวัติรายการที่ปิดขาย (Sell Orders) ในระบบ")

with tab2:
    st.subheader("📑 ประวัติรายการสั่งซื้อขายดิบ (Raw Trade Logs)")
    if webull_orders:
        df_raw = pd.DataFrame(webull_orders)
        st.dataframe(df_raw, use_container_width=True)
    else:
        st.write("ไม่พบประวัติออเดอร์ดิบจาก Webull")
