import base64
import json
import streamlit as st
import pandas as pd
import gspread
import yfinance as yf

st.title("🇹🇭 Dime! Portfolio Dashboard (Multi-Currency)")
st.markdown("---")

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
        res = conn.getcall = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        if isinstance(data, list):
            for p in data:
                prices[str(p.get("symbol")).upper()] = float(p.get("last_price", 0))
    except:
        pass
    return prices

def load_dime_portfolio():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64:
            st.warning("⚠️ ไม่พบกุญแจ Google ใน Secrets")
            return []
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Dime_Portfolio")
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"❌ ดึงข้อมูลจาก Google Sheet ไม่สำเร็จ: {str(e)}")
        return []

records = load_dime_portfolio()

if records:
    total_invested_usd = 0.0
    total_market_value_usd = 0.0
    table_rows = []
    
    symbols = [str(r.get("หุ้น (Ticker)", "")).strip().upper() for r in records if str(r.get("หุ้น (Ticker)", "")).strip()]
    webull_prices = get_webull_live_prices()
    
    live_prices_orig = {}
    if symbols:
        with st.spinner("⏳ กำลังดึงราคาสดจากกระดาน..."):
            for sym in symbols:
                if sym in webull_prices and webull_prices[sym] > 0:
                    live_prices_orig[sym] = webull_prices[sym]
                else:
                    try:
                        ticker_data = yf.Ticker(sym)
                        price = ticker_data.info.get('currentPrice') or ticker_data.info.get('regularMarketPrice') or ticker_data.fast_info.get('last_price')
                        if not price:
                            hist = ticker_data.history(period="1d")
                            if not hist.empty: price = hist['Close'].iloc[-1]
                        if price:
                            live_prices_orig[sym] = float(price)
                    except:
                        pass

    for r in records:
        symbol = str(r.get("หุ้น (Ticker)", "")).strip().upper()
        if not symbol: continue
        
        qty = float(r.get("จำนวนหุ้น (Volume)", 0))
        cost_input = float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0))
        
        is_thai_stock = symbol.endswith(".BK")
        raw_live_price = live_prices_orig.get(symbol, 0)
        if raw_live_price == 0:
            raw_live_price = cost_input
        
        if is_thai_stock:
            cost_usd = cost_input / fx_rate
            price_usd = raw_live_price / fx_rate
            display_cost = f"฿{cost_input:,.2f}"
            display_live = f"฿{raw_live_price:,.2f}"
        else:
            cost_usd = cost_input
            price_usd = raw_live_price
            display_cost = f"${cost_input:,.2f}"
            display_live = f"${raw_live_price:,.2f}"
            
        invested_usd = qty * cost_usd
        market_value_usd = qty * price_usd
        pnl_usd = market_value_usd - invested_usd
        pnl_pct = (pnl_usd / invested_usd * 100) if invested_usd > 0 else 0.0
        
        total_invested_usd += invested_usd
        total_market_value_usd += market_value_usd
        
        pnl_sign = "🟢" if pnl_usd > 0.01 else ("🔴" if pnl_usd < -0.01 else "⚪")
        
        if is_thai_stock:
            display_invested = f"฿{qty * cost_input:,.2f}"
            display_market = f"฿{qty * raw_live_price:,.2f}"
            display_pnl = f"{pnl_sign} ฿{qty * (raw_live_price - cost_input):,.2f} ({pnl_pct:+.2f}%)"
        else:
            display_invested = f"${invested_usd:,.2f}"
            display_market = f"${market_value_usd:,.2f}"
            display_pnl = f"{pnl_sign} ${pnl_usd:,.2f} ({pnl_pct:+.2f}%)"
            
        table_rows.append({
            "หุ้น Dime": symbol,
            "จำนวนหุ้น": f"{qty:,.4f}",
            "ต้นทุนเฉลี่ย": display_cost,
            "ราคาตลาดสด": display_live,
            "เงินลงทุนรวม": display_invested,
            "มูลค่าปัจจุบัน": display_market,
            "กำไร/ขาดทุน": display_pnl
        })
        
    total_pnl_usd = total_market_value_usd - total_invested_usd
    total_pnl_pct = (total_pnl_usd / total_invested_usd * 100) if total_invested_usd > 0 else 0.0
    pnl_class = "color: #00c853;" if total_pnl_usd > 0 else ("color: #ff3d00;" if total_pnl_usd < 0 else "color: #848e9c;")
    pnl_prefix = "+" if total_pnl_usd > 0 else ""
    
    st.markdown(f"💡 *คำนวณด้วยอัตราแลกเปลี่ยนปัจจุบัน: 1 USD = {fx_rate:,.2f} THB*")
    st.markdown(f"""
    <div style="background-color: #1e222d; padding: 20px; border-radius: 10px; border: 1px solid #2a2e39; text-align: center;">
        <h4 style="color: #848e9c; margin: 0;">💰 มูลค่ารวมพอร์ต Dime! (คำนวณค่าเงินถูกต้อง)</h4>
        <h2 style="color: white; margin: 10px 0;">${total_market_value_usd:,.2f} <span style="font-size: 18px; color: #848e9c;">(≈ ฿{total_market_value_usd * fx_rate:,.2f})</span></h2>
        <p style="{pnl_class} font-weight: bold; margin: 0; font-size: 18px;">
            กำไร/ขาดทุนสุทธิทั้งหมด: {pnl_prefix}${total_pnl_usd:,.2f} ({total_pnl_pct:+.2f}%)
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📋 รายการสินทรัพย์ใน Dime! (แยกสกุลเงินอัตโนมัติ)")
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
