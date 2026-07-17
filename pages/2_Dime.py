import base64
import json
import streamlit as st
import pandas as pd
import gspread
import yfinance as yf

st.title("🇹🇭 Dime! Portfolio Dashboard (Real-time)")
st.markdown("---")

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
        
        # เปิดแท็บ Dime_Portfolio ในไฟล์ "หุ้นของเรา"
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Dime_Portfolio")
        
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"❌ ดึงข้อมูลจาก Google Sheet ไม่สำเร็จ: {str(e)}")
        return []

records = load_dime_portfolio()

if records:
    total_invested = 0.0
    total_market_value = 0.0
    table_rows = []
    
    # ดึงรายชื่อหุ้นทั้งหมดในชีทเพื่อไปยิงหาราคาตลาดสดรอบเดียวพร้อมกัน (ประหยัดเวลาโหลด)
    symbols = [str(r.get("หุ้น (Ticker)", "")).strip().upper() for r in records if str(r.get("หุ้น (Ticker)", "")).strip()]
    
    live_prices = {}
    if symbols:
        with st.spinner("⏳ กำลังดึงราคาล่าสุดจากตลาดหุ้นอเมริกา..."):
            try:
                # ยิงไปสืบราคาปัจจุบันของหุ้นทุกตัวพร้อมกันผ่าน yfinance
                tickers_data = yf.Tickers(" ".join(symbols))
                for sym in symbols:
                    # ดึงราคาล่าสุด (regularMarketPrice)
                    info = tickers_data.tickers[sym].fast_info
                    live_prices[sym] = float(info['last_price'])
            except:
                pass

    for r in records:
        symbol = str(r.get("หุ้น (Ticker)", "")).strip().upper()
        if not symbol: continue
        
        qty = float(r.get("จำนวนหุ้น (Volume)", 0))
        cost = float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0))
        
        # ถ้าดึงราคาตลาดสดสำเร็จให้ใช้ราคาตลาด ถ้าล้มเหลวค่อยใช้ราคาต้นทุนดักไว้
        last_price = live_prices.get(symbol, cost)
        
        invested = qty * cost
        market_value = qty * last_price
        pnl = market_value - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
        
        total_invested += invested
        total_market_value += market_value
        pnl_sign = "🟢" if pnl >= 0 else "🔴"
        
        table_rows.append({
            "หุ้น Dime": symbol,
            "จำนวนหุ้น": f"{qty:,.4f}",
            "ต้นทุนเฉลี่ย": f"${cost:,.2f}",
            "ราคาตลาดสด": f"${last_price:,.2f}",
            "เงินลงทุนรวม": f"${invested:,.2f}",
            "มูลค่าปัจจุบัน": f"${market_value:,.2f}",
            "กำไร/ขาดทุน": f"{pnl_sign} ${pnl:,.2f} ({pnl_pct:+.2f}%)"
        })
        
    # สรุปยอดเงินในกล่องบนสุด
    total_pnl = total_market_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
    pnl_class = "color: #00c853;" if total_pnl >= 0 else "color: #ff3d00;"
    pnl_prefix = "+" if total_pnl >= 0 else ""
    
    st.markdown(f"""
    <div style="background-color: #1e222d; padding: 20px; border-radius: 10px; border: 1px solid #2a2e39; text-align: center;">
        <h4 style="color: #848e9c; margin: 0;">💰 มูลค่ารวมพอร์ต Dime! (ราคาตลาดปัจจุบัน)</h4>
        <h2 style="color: white; margin: 10px 0;">${total_market_value:,.2f}</h2>
        <p style="{pnl_class} font-weight: bold; margin: 0; font-size: 18px;">
            กำไร/ขาดทุนสุทธิทั้งหมด: {pnl_prefix}${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📋 รายการสินทรัพย์ใน Dime! (ราคาอัปเดตอัตโนมัติ)")
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
else:
    st.info("💡 แท็บ 'Dime_Portfolio' ว่างเปล่า พิมพ์ข้อมูลลงกูเกิ้ลชีทได้เลยเพื่อน")
