import base64
import json
import streamlit as st
import pandas as pd
import gspread
import yfinance as yf

st.title("🇺🇸 Dime! US Portfolio Dashboard")
st.markdown("---")

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

us_records = load_sheet_data("Dime_Portfolio")
total_invested_usd = 0.0
total_market_value_usd = 0.0
us_rows = []

if us_records:
    with st.spinner("⏳ กำลังดึงราคาสดหุ้นสหรัฐฯ จากกระดาน..."):
        for r in us_records:
            symbol = str(r.get("หุ้น (Ticker)", "")).strip().upper()
            if not symbol: continue
            qty = float(r.get("จำนวนหุ้น (Volume)", 0))
            cost = float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0))
            
            try:
                t = yf.Ticker(symbol)
                price = t.info.get('currentPrice') or t.info.get('regularMarketPrice') or t.fast_info.get('last_price') or cost
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

if us_rows:
    total_pnl_usd = total_market_value_usd - total_invested_usd
    total_pnl_pct = (total_pnl_usd / total_invested_usd * 100) if total_invested_usd > 0 else 0.0
    pnl_class = "color: #00c853;" if total_pnl_usd > 0 else ("color: #ff3d00;" if total_pnl_usd < 0 else "color: #848e9c;")
    pnl_prefix = "+" if total_pnl_usd > 0 else ""

    st.markdown(f"""
    <div style="background-color: #1e222d; padding: 20px; border-radius: 10px; border: 1px solid #2a2e39; text-align: center;">
        <h4 style="color: #848e9c; margin: 0;">💵 มูลค่ารวมพอร์ต Dime! สหรัฐฯ</h4>
        <h2 style="color: white; margin: 10px 0;">${total_market_value_usd:,.2f}</h2>
        <p style="{pnl_class} font-weight: bold; margin: 0; font-size: 18px;">
            กำไร/ขาดทุนสุทธิ: {pnl_prefix}${total_pnl_usd:,.2f} ({total_pnl_pct:+.2f}%)
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(us_rows), use_container_width=True, hide_index=True)
else:
    st.info("ℹ️ ไม่พบข้อมูลหุ้นสหรัฐฯ ในแท็บ 'Dime_Portfolio'")
