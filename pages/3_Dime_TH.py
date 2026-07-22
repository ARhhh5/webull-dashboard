import streamlit as st
import pandas as pd
import yfinance as yf
import json
import base64
import gspread

st.set_page_config(page_title="Dime! Thai Portfolio", layout="wide")

st.markdown("""
    <style>
    .metric-container {
        background-color: #1e222d;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #2a2e39;
        text-align: center;
    }
    .metric-label { color: #848e9c; font-size: 16px; font-weight: 500; margin-bottom: 8px; }
    .metric-value { color: #ffffff; font-size: 32px; font-weight: 700; }
    .pnl-positive { color: #00c853 !important; }
    .pnl-negative { color: #ff3d00 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🇹🇭 พอร์ตหุ้นไทย (Dime!)")
st.markdown("---")

def get_dime_th_data():
    holdings = []
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            gc = gspread.service_account_from_dict(cred_dict)
            sh = gc.open("หุ้นของเรา")
            worksheet = sh.worksheet("Dime_TH_Portfolio")
            records = worksheet.get_all_records()
            for r in records:
                sym = str(r.get("หุ้น (Ticker)", "")).strip().upper()
                if sym:
                    holdings.append({
                        "Symbol": sym,
                        "Qty": float(r.get("จำนวนหุ้น (Volume)", 0)),
                        "Cost": float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0))
                    })
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ Google Sheet: {e}")
    return holdings

# ฟังก์ชันใส่สีข้อความกำไร/ขาดทุน
def color_pnl_str(val):
    s = str(val).strip()
    if s.startswith("+"):
        return 'color: #00c853; font-weight: bold;'
    elif s.startswith("-"):
        return 'color: #ff3d00; font-weight: bold;'
    return 'color: #848e9c;'

with st.spinner("⏳ กำลังดึงราคาสดหุ้นไทย..."):
    holdings = get_dime_th_data()
    
    if holdings:
        data = []
        for h in holdings:
            sym = h["Symbol"]
            qty = h["Qty"]
            cost = h["Cost"]
            
            # แปลงสัญลักษณ์เป็นหุ้นไทย เช่น KKP -> KKP.BK
            yf_sym = f"{sym}.BK" if not sym.endswith(".BK") else sym
            
            price = 0.0
            try:
                ticker = yf.Ticker(yf_sym)
                p = ticker.fast_info.get('last_price') or ticker.info.get('currentPrice') or ticker.info.get('regularMarketPrice')
                if not p or float(p) == 0.0:
                    hist = ticker.history(period="5d")
                    if not hist.empty:
                        p = hist['Close'].iloc[-1]
                price = float(p) if p else cost
            except:
                price = cost
                
            invested = qty * cost
            market_val = qty * price
            pnl = market_val - invested
            pnl_pct = (pnl / invested * 100) if invested > 0 else 0
            
            data.append({
                "หุ้น TH": sym,
                "จำนวนหุ้น": qty,
                "ต้นทุนเฉลี่ย": cost,
                "ราคาตลาด": price,
                "เงินลงทุน (THB)": invested,
                "มูลค่าปัจจุบัน (THB)": market_val,
                "PnL": pnl,
                "PnL_Pct": pnl_pct
            })
            
        df = pd.DataFrame(data)
        
        total_invested = df["เงินลงทุน (THB)"].sum()
        total_market = df["มูลค่าปัจจุบัน (THB)"].sum()
        total_pnl = total_market - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        
        pnl_class = "pnl-positive" if total_pnl >= 0 else "pnl-negative"
        pnl_prefix = "+" if total_pnl >= 0 else ""
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="metric-container"><div class="metric-label">💵 มูลค่ารวมพอร์ต Dime! หุ้นไทย</div><div class="metric-value">฿{total_market:,.2f}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-container"><div class="metric-label">📊 กำไร / ขาดทุนสุทธิ</div><div class="metric-value {pnl_class}">{pnl_prefix}฿{total_pnl:,.2f} ({total_pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)
            
        st.markdown("---")
        
        df_display = df.copy()
        df_display["กำไร/ขาดทุน"] = df_display.apply(
            lambda r: f"+฿{r['PnL']:,.2f} ({r['PnL_Pct']:+.2f}%)" if r['PnL'] > 0 else (f"-฿{abs(r['PnL']):,.2f} ({r['PnL_Pct']:+.2f}%)" if r['PnL'] < 0 else f"฿{r['PnL']:,.2f} (0.00%)"),
            axis=1
        )
        
        st.dataframe(
            df_display[["หุ้น TH", "จำนวนหุ้น", "ต้นทุนเฉลี่ย", "ราคาตลาด", "เงินลงทุน (THB)", "มูลค่าปัจจุบัน (THB)", "กำไร/ขาดทุน"]]
            .style.map(color_pnl_str, subset=["กำไร/ขาดทุน"])
            .format({
                "จำนวนหุ้น": "{:,.2f}",
                "ต้นทุนเฉลี่ย": "฿{:,.2f}",
                "ราคาตลาด": "฿{:,.2f}",
                "เงินลงทุน (THB)": "฿{:,.2f}",
                "มูลค่าปัจจุบัน (THB)": "฿{:,.2f}"
            }),
            use_container_width=True
        )
    else:
        st.info("ไม่พบข้อมูลหุ้นไทยใน Google Sheet")
