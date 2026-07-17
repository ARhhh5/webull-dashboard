import base64
import json
import streamlit as st
import pandas as pd
import gspread
import yfinance as yf

st.title("🇹🇭 Dime! TH Portfolio Dashboard")
st.markdown("---")

@st.cache_data(ttl=60)
def get_usd_thb_rate():
    try:
        ticker = yf.Ticker("USDTHB=X")
        rate = ticker.info.get('regularMarketPrice') or ticker.info.get('currentPrice') or ticker.fast_info.get('last_price') or 35.0
        return float(rate)
    except:
        return 35.0

fx_rate = get_usd_thb_rate()

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

th_records = load_sheet_data("Dime_TH_Portfolio")
total_invested_thb = 0.0
total_market_value_thb = 0.0
th_rows = []

if th_records:
    with st.spinner("⏳ กำลังดึงราคาสดหุ้นไทยตรงจากกระดาน..."):
        for r in th_records:
            symbol = str(r.get("หุ้น (Ticker)", "")).strip().upper()
            if not symbol: continue
            qty = float(r.get("จำนวนหุ้น (Volume)", 0))
            cost_thb = float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0))
            
            yf_symbol = f"{symbol}.BK" if not symbol.endswith(".BK") else symbol
            try:
                t = yf.Ticker(yf_symbol)
                price_thb = t.info.get('currentPrice') or t.info.get('regularMarketPrice') or t.fast_info.get('last_price') or cost_thb
                if not price_thb or price_thb == cost_thb:
                    hist = t.history(period="1d")
                    if not hist.empty: price_thb = float(hist['Close'].iloc[-1])
            except:
                price_thb = cost_thb
                
            invested_thb = qty * cost_thb
            market_val_thb = qty * price_thb
            pnl_thb = market_val_thb - invested_thb
            pnl_pct = (pnl_thb / invested_thb * 100) if invested_thb > 0 else 0.0
            
            total_invested_thb += invested_thb
            total_market_value_thb += market_val_thb
            
            pnl_sign = "🟢" if pnl_thb > 0.01 else ("🔴" if pnl_thb < -0.01 else "⚪")
            th_rows.append({
                "หุ้นไทย": symbol, "จำนวนหุ้น": f"{qty:,.2f}",
                "ต้นทุนเฉลี่ย": f"฿{cost_thb:,.2f}", "ราคาตลาด": f"฿{price_thb:,.2f}",
                "เงินลงทุน": f"฿{invested_thb:,.2f}", "มูลค่าปัจจุบัน": f"฿{market_val_thb:,.2f}",
                "กำไร/ขาดทุน": f"{pnl_sign} ฿{pnl_thb:,.2f} ({pnl_pct:+.2f}%)"
            })

if th_rows:
    total_pnl_thb = total_market_value_thb - total_invested_thb
    total_pnl_pct = (total_pnl_thb / total_invested_thb * 100) if total_invested_thb > 0 else 0.0
    pnl_class = "color: #00c853;" if total_pnl_thb > 0 else ("color: #ff3d00;" if total_pnl_thb < 0 else "color: #848e9c;")
    pnl_prefix = "+" if total_pnl_thb > 0 else ""

    st.markdown(f"""
    <div style="background-color: #1e222d; padding: 20px; border-radius: 10px; border: 1px solid #2a2e39; text-align: center;">
        <h4 style="color: #848e9c; margin: 0;">💰 มูลค่ารวมพอร์ต Dime! หุ้นไทย</h4>
        <h2 style="color: white; margin: 10px 0;">฿{total_market_value_thb:,.2f} <span style="font-size: 16px; color: #848e9c;">(≈ ${total_market_value_thb / fx_rate:,.2f})</span></h2>
        <p style="{pnl_class} font-weight: bold; margin: 0; font-size: 18px;">
            กำไร/ขาดทุนสุทธิ: {pnl_prefix}฿{total_pnl_thb:,.2f} ({total_pnl_pct:+.2f}%)
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(th_rows), use_container_width=True, hide_index=True)
else:
    st.info("ℹ️ ไม่พบข้อมูลหุ้นไทยในแท็บ 'Dime_TH_Portfolio'")
