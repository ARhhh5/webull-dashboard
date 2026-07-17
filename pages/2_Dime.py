import base64
import json
import streamlit as st
import pandas as pd
import gspread
import yfinance as yf

st.title("🇹🇭 Dime! Portfolio Dashboard (Multi-Currency)")
st.markdown("---")

# ฟังก์ชันดึงอัตราแลกเปลี่ยนเรียลไทม์ (USD/THB)
@st.cache_data(ttl=3600)
def get_usd_thb_rate():
    try:
        ticker = yf.Ticker("USDTHB=X")
        rate = ticker.fast_info.get('last_price') or ticker.info.get('regularMarketPrice') or 35.0
        return float(rate)
    except:
        return 35.0

fx_rate = get_usd_thb_rate()

# ฟังก์ชันโหลดข้อมูลพอร์ต Dime จาก Google Sheet
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
    
    live_prices_orig = {}
    if symbols:
        with st.spinner("⏳ กำลังดึงราคาสดและคำนวณอัตราแลกเปลี่ยน..."):
            try:
                tickers_data = yf.Tickers(" ".join(symbols))
                for sym in symbols:
                    info = tickers_data.tickers[sym].fast_info
                    live_prices_orig[sym] = float(info['last_price'])
            except:
                pass

    for r in records:
        symbol = str(r.get("หุ้น (Ticker)", "")).strip().upper()
        if not symbol: continue
        
        qty = float(r.get("จำนวนหุ้น (Volume)", 0))
        cost_input = float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0))
        
        # ตรวจสอบว่าคีย์ข้อมูลเป็นหุ้นไทยหรือไม่ (.BK)
        is_thai_stock = symbol.endswith(".BK")
        
        # ดึงราคาดิบจากตลาด (หุ้นไทยจะได้เป็นบาท หุ้นนอกจะได้เป็นดอลลาร์)
        raw_live_price = live_prices_orig.get(symbol, cost_input)
        
        # 🎯 แปลงทุกอย่างให้เป็น USD เพื่อใช้เป็นฐานคำนวณหลังบ้าน
        if is_thai_stock:
            # หุ้นไทย: แปลงต้นทุน (บาท) และราคาตลาด (บาท) ให้เป็น USD โดยการหาร fx_rate
            cost_usd = cost_input / fx_rate
            price_usd = raw_live_price / fx_rate
            currency_symbol = "฿"
            display_cost = f"฿{cost_input:,.2f}"
            display_live = f"฿{raw_live_price:,.2f}"
        else:
            # หุ้นสหรัฐฯ: เป็น USD อยู่แล้ว ไม่ต้องแปลงอะไร
            cost_usd = cost_input
            price_usd = raw_live_price
            currency_symbol = "$"
            display_cost = f"${cost_input:,.2f}"
            display_live = f"${raw_live_price:,.2f}"
            
        invested_usd = qty * cost_usd
        market_value_usd = qty * price_usd
        pnl_usd = market_value_usd - invested_usd
        pnl_pct = (pnl_usd / invested_usd * 100) if invested_usd > 0 else 0.0
        
        total_invested_usd += invested_usd
        total_market_value_usd += market_value_usd
        pnl_sign = "🟢" if pnl_usd >= 0 else "🔴"
        
        # แปลงมูลค่ารวมของหุ้นตัวนั้นๆ กลับมาแสดงผลตามสกุลเงินจริงในตารางให้ดูไม่งง
        if is_thai_stock:
            display_invested = f"฿{qty * cost_input:,.2f}"
            display_market = f"฿{qty * raw_live_price:,.2f}"
            display_pnl = f"{pnl_sign} ฿{pnl_usd * fx_rate:,.2f} ({pnl_pct:+.2f}%)"
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
        
    # สรุปยอดเงินในกล่องบนสุด (แปลงเป็นดอลลาร์รวมภาพใหญ่ให้ถูกต้อง)
    total_pnl_usd = total_market_value_usd - total_invested_usd
    total_pnl_pct = (total_pnl_usd / total_invested_usd * 100) if total_invested_usd > 0 else 0.0
    pnl_class = "color: #00c853;" if total_pnl_usd >= 0 else "color: #ff3d00;"
    pnl_prefix = "+" if total_pnl_usd >= 0 else ""
    
    st.markdown(f"💡 *คำนวณด้วยอัตราแลกเปลี่ยนปัจจุบัน: 1 USD = {fx_rate:,.2f} THB*")
    st.markdown(f"""
    <div style="background-color: #1e222d; padding: 20px; border-radius: 10px; border: 1px solid #2a2e39; text-align: center;">
        <h4 style="color: #848e9c; margin: 0;">💰 มูลค่ารวมพอร์ต Dime! (แปลงเป็น USD แล้ว)</h4>
        <h2 style="color: white; margin: 10px 0;">${total_market_value_usd:,.2f} <span style="font-size: 18px; color: #848e9c;">(≈ ฿{total_market_value_usd * fx_rate:,.2f})</span></h2>
        <p style="{pnl_class} font-weight: bold; margin: 0; font-size: 18px;">
            กำไร/ขาดทุนสุทธิทั้งหมด: {pnl_prefix}${total_pnl_usd:,.2f} ({total_pnl_pct:+.2f}%)
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📋 รายการสินทรัพย์ใน Dime! (แยกสกุลเงินอัตโนมัติ)")
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
else:
    st.info("💡 แท็บ 'Dime_Portfolio' ว่างเปล่า พิมพ์ข้อมูลลงกูเกิ้ลชีทได้เลยเพื่อน")
