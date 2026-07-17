import base64
import json
import streamlit as st
import pandas as pd
import gspread
import yfinance as yf
import uuid
import hashlib
import hmac
import http.client
from datetime import datetime, timezone

st.title("🇹🇭 Dime! Portfolio Dashboard")
st.markdown("---")

# โหลด Secrets ของ Webull มาใช้ดึงราคาและค่าเงิน
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
        rate = ticker.info.get('regularMarketPrice') or ticker.info.get('currentPrice') or ticker.fast_info.get('last_price') or 35.0
        return float(rate)
    except:
        return 35.0

fx_rate = get_usd_thb_rate()

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

def load_sheet_data(sheet_name):
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64: return []
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet(sheet_name)
        return worksheet.get_all_records()
    except:
        return []

# 1. ดึงข้อมูลจาก Google Sheet ทั้งสองแท็บ
us_records = load_sheet_data("Dime_Portfolio")
th_records = load_sheet_data("Dime_TH_Portfolio")

webull_prices = get_webull_live_prices()
total_invested_usd = 0.0
total_market_value_usd = 0.0

st.markdown(f"💡 *อัตราแลกเปลี่ยนปัจจุบัน: 1 USD = {fx_rate:,.2f} THB*")

# --- ส่วนที่ 1: จัดการหุ้นสหรัฐฯ (Dime US) ---
us_rows = []
if us_records:
    for r in us_records:
        symbol = str(r.get("หุ้น (Ticker)", "")).strip().upper()
        if not symbol: continue
        qty = float(r.get("จำนวนหุ้น (Volume)", 0))
        cost = float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0))
        
        # ดึงราคาจาก Webull หรือใช้ราคาต้นทุนดักไว้
        price = webull_prices.get(symbol, 0)
        if price == 0:
            try:
                t = yf.Ticker(symbol)
                price = float(t.info.get('currentPrice') or t.info.get('regularMarketPrice') or t.fast_info.get('last_price') or cost)
            except:
                price = cost
                
        invested = qty * cost
        market_val = qty * price
        pnl = market_val - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
        
        total_invested_usd += invested
        total_market_value_usd += market_val
        
        pnl_sign = "🟢" if pnl > 0.01 else ("🔴" if pnl < -0.01 else "⚪")
        us_rows.append({
            "หุ้น US": symbol, "จำนวนหุ้น": f"{qty:,.4f}",
            "ต้นทุนเฉลี่ย": f"${cost:,.2f}", "ราคาตลาด": f"${price:,.2f}",
            "เงินลงทุน": f"${invested:,.2f}", "มูลค่าปัจจุบัน": f"${market_val:,.2f}",
            "กำไร/ขาดทุน": f"{pnl_sign} ${pnl:,.2f} ({pnl_pct:+.2f}%)"
        })

# --- ส่วนที่ 2: จัดการหุ้นไทย (Dime TH) ---
th_rows = []
if th_records:
    for r in th_records:
        symbol = str(r.get("หุ้น (Ticker)", "")).strip().upper()
        if not symbol: continue
        qty = float(r.get("จำนวนหุ้น (Volume)", 0))
        cost_thb = float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0))
        
        # ค้นหาราคาหุ้นไทยผ่าน yfinance เติม .BK อัตโนมัติในระบบ
        yf_symbol = f"{symbol}.BK" if not symbol.endswith(".BK") else symbol
        try:
            t = yf.Ticker(yf_symbol)
            price_thb = float(t.info.get('currentPrice') or t.info.get('regularMarketPrice') or t.fast_info.get('last_price') or cost_thb)
        except:
            price_thb = cost_thb
            
        invested_thb = qty * cost_thb
        market_val_thb = qty * price_thb
        pnl_thb = market_val_thb - invested_thb
        pnl_pct = (pnl_thb / invested_thb * 100) if invested_thb > 0 else 0.0
        
        # แปลงเป็น USD ยัดเข้ากองกลางสรุปภาพรวมด้านบน
        total_invested_usd += (invested_thb / fx_rate)
        total_market_value_usd += (market_val_thb / fx_rate)
        
        pnl_sign = "🟢" if pnl_thb > 0.01 else ("🔴" if pnl_thb < -0.01 else "⚪")
        th_rows.append({
            "หุ้นไทย": symbol, "จำนวนหุ้น": f"{qty:,.2f}",
            "ต้นทุนเฉลี่ย": f"฿{cost_thb:,.2f}", "ราคาตลาด": f"฿{price_thb:,.2f}",
            "เงินลงทุน": f"฿{invested_thb:,.2f}", "มูลค่าปัจจุบัน": f"฿{market_val_thb:,.2f}",
            "กำไร/ขาดทุน": f"{pnl_sign} ฿{pnl_thb:,.2f} ({pnl_pct:+.2f}%)"
        })

# --- ส่วนที่ 3: แสดงกล่องสรุปยอดพอร์ต Dime! รวมสองฝั่งสากล ---
total_pnl_usd = total_market_value_usd - total_invested_usd
total_pnl_pct = (total_pnl_usd / total_invested_usd * 100) if total_invested_usd > 0 else 0.0
pnl_class = "color: #00c853;" if total_pnl_usd > 0 else ("color: #ff3d00;" if total_pnl_usd < 0 else "color: #848e9c;")
pnl_prefix = "+" if total_pnl_usd > 0 else ""

st.markdown(f"""
<div style="background-color: #1e222d; padding: 20px; border-radius: 10px; border: 1px solid #2a2e39; text-align: center;">
    <h4 style="color: #848e9c; margin: 0;">💰 มูลค่ารวมพอร์ต Dime! ทั้งสิ้น</h4>
    <h2 style="color: white; margin: 10px 0;">${total_market_value_usd:,.2f} <span style="font-size: 18px; color: #848e9c;">(≈ ฿{total_market_value_usd * fx_rate:,.2f})</span></h2>
    <p style="{pnl_class} font-weight: bold; margin: 0; font-size: 18px;">
        กำไร/ขาดทุนสุทธิรวม: {pnl_prefix}${total_pnl_usd:,.2f} ({total_pnl_pct:+.2f}%)
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# โชว์ตารางแยกฝั่งชัดเจน
if us_rows:
    st.subheader("🇺🇸 รายการหุ้นสหรัฐฯ (Dime! US Portfolio)")
    st.dataframe(pd.DataFrame(us_rows), use_container_width=True, hide_index=True)

if th_rows:
    st.subheader("🇹🇭 รายการหุ้นไทย (Dime! TH Portfolio)")
    st.dataframe(pd.DataFrame(th_rows), use_container_width=True, hide_index=True)

if not us_rows and not th_rows:
    st.info("ℹ️ ไม่พบข้อมูลในแท็บ Dime_Portfolio และ Dime_TH_Portfolio บน Google Sheet")
