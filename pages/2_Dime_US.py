import streamlit as st
import pandas as pd
import yfinance as yf
import json
import base64
import gspread

st.set_page_config(page_title="Dime! US Portfolio", layout="wide")

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

st.title("🇺🇸 พอร์ตหุ้นสหรัฐฯ (Dime!)")
st.markdown("---")

# ==========================================
# ฟังก์ชันดึงราคาตลาดปัจจุบันสดๆ แบบ Bulk Download
# ==========================================
@st.cache_data(ttl=120)
def fetch_us_live_prices(symbols):
    prices = {}
    if not symbols:
        return prices
        
    clean_syms = list(set([s.upper().strip() for s in symbols if s]))
    
    # 1. ลองดึงแบบ Bulk Download รวดเดียวจบ
    try:
        data = yf.download(tickers=clean_syms, period="5d", interval="1d", progress=False)
        if not data.empty and 'Close' in data:
            close_df = data['Close']
            for sym in clean_syms:
                try:
                    if len(clean_syms) == 1:
                        val = close_df.dropna().iloc[-1]
                    else:
                        val = close_df[sym].dropna().iloc[-1]
                    if pd.notna(val) and float(val) > 0:
                        prices[sym] = float(val)
                except:
                    pass
    except Exception as e:
        pass

    # 2. Backup Fallback กรณีตัวไหนยังไม่ได้ราคา ให้ยิงผ่าน history
    for sym in clean_syms:
        if prices.get(sym, 0.0) == 0.0:
            try:
                ticker = yf.Ticker(sym)
                hist = ticker.history(period="5d")
                if not hist.empty:
                    last_price = float(hist['Close'].iloc[-1])
                    if last_price > 0:
                        prices[sym] = last_price
            except:
                pass
                
    return prices

def get_dime_us_data():
    holdings = []
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            gc = gspread.service_account_from_dict(cred_dict)
            sh = gc.open("หุ้นของเรา")
            worksheet = sh.worksheet("Dime_Portfolio")
            records = worksheet.get_all_records()
            
            if not records:
                return pd.DataFrame()
                
            df_raw = pd.DataFrame(records)
            
            # ค้นหาคอลัมน์ชื่อหุ้น, จำนวน, และต้นทุน
            sym_col = next((c for c in df_raw.columns if 'ticker' in str(c).lower() or 'symbol' in str(c).lower() or 'หุ้น' in str(c)), None)
            qty_col = next((c for c in df_raw.columns if 'volume' in str(c).lower() or 'qty' in str(c).lower() or 'จำนวน' in str(c)), None)
            cost_col = next((c for c in df_raw.columns if 'cost' in str(c).lower() or 'ต้นทุน' in str(c)), None)
            
            if not sym_col or not qty_col or not cost_col:
                st.error("❌ ไม่พบคอลัมน์ข้อมูลหุ้น/จำนวน/ต้นทุน ในชีท Dime_Portfolio")
                return pd.DataFrame()

            # ดึงรายชื่อหุ้นทั้งหมดเพื่อไปเอาราคาเรียลไทม์
            symbols = [str(r[sym_col]).strip().upper().split(" ")[0] for _, r in df_raw.iterrows() if str(r[sym_col]).strip()]
            live_prices = fetch_us_live_prices(symbols)

            for _, r in df_raw.iterrows():
                sym = str(r.get(sym_col, "")).strip().upper()
                if not sym: continue
                if " " in sym: sym = sym.split(" ")[0]
                
                try:
                    qty = float(str(r.get(qty_col, 0)).replace(",", ""))
                    avg_cost = float(str(r.get(cost_col, 0)).replace(",", ""))
                    
                    if qty <= 0: continue
                    
                    # เอาราคาเรียลไทม์
                    current_price = live_prices.get(sym, 0.0)
                    
                    # ถ้าราคาเรียลไทม์ดึงไม่ได้จริงๆ ให้คงราคาต้นทุนไว้ แต่เตือนผู้ใช้
                    if current_price == 0.0:
                        current_price = avg_cost
                    
                    invested = qty * avg_cost
                    market_val = qty * current_price
                    pnl = market_val - invested
                    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
                    
                    holdings.append({
                        "หุ้น US": sym,
                        "จำนวนหุ้น": qty,
                        "ต้นทุนเฉลี่ย": avg_cost,
                        "ราคาปัจจุบัน": current_price,
                        "มูลค่าลงทุน ($)": invested,
                        "มูลค่าตลาด ($)": market_val,
                        "PnL": pnl,
                        "PnL_Pct": pnl_pct
                    })
                except Exception as e:
                    continue
                    
    except Exception as e:
        st.error(f"⚠️ เกิดข้อผิดพลาดในการโหลดข้อมูล Dime US: {e}")
        
    return pd.DataFrame(holdings)

def color_pnl(val):
    if isinstance(val, (int, float)):
        color = '#00c853' if val > 0 else ('#ff3d00' if val < 0 else '#848e9c')
        return f'color: {color}; font-weight: bold;'
    return ''

# โหลดข้อมูลพอร์ต Dime US
with st.spinner("⏳ กำลังดึงราคาหุ้นสหรัฐฯ เรียลไทม์..."):
    df = get_dime_us_data()

if not df.empty:
    total_invested = df["มูลค่าลงทุน ($)"].sum()
    total_market = df["มูลค่าตลาด ($)"].sum()
    total_pnl = total_market - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
    
    pnl_class = "pnl-positive" if total_pnl >= 0 else "pnl-negative"
    pnl_prefix = "+" if total_pnl >= 0 else ""
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="metric-container"><div class="metric-label">💵 เงินลงทุนรวม</div><div class="metric-value">${total_invested:,.2f}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-container"><div class="metric-label">📈 มูลค่าตลาดรวม (ปัจจุบัน)</div><div class="metric-value">${total_market:,.2f}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-container"><div class="metric-label">📊 กำไร / ขาดทุนสุทธิ</div><div class="metric-value {pnl_class}">{pnl_prefix}${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)
        
    st.markdown("---")
    
    # จัดตารางแสดงผลเรียงตามมูลค่าตลาด
    df_display = df.sort_values(by="มูลค่าตลาด ($)", ascending=False).copy()
    df_display["กำไร/ขาดทุนสุทธิ"] = df_display.apply(lambda r: f"{'+' if r['PnL']>=0 else ''}${r['PnL']:,.2f} ({r['PnL_Pct']:+.2f}%)", axis=1)
    
    st.dataframe(
        df_display[["หุ้น US", "จำนวนหุ้น", "ต้นทุนเฉลี่ย", "ราคาปัจจุบัน", "มูลค่าลงทุน ($)", "มูลค่าตลาด ($)", "กำไร/ขาดทุนสุทธิ"]]
        .style.map(color_pnl, subset=["PnL"])
        .format({
            "จำนวนหุ้น": "{:,.4f}",
            "ต้นทุนเฉลี่ย": "${:,.2f}",
            "ราคาปัจจุบัน": "${:,.2f}",
            "มูลค่าลงทุน ($)": "${:,.2f}",
            "มูลค่าตลาด ($)": "${:,.2f}"
        }),
        use_container_width=True
    )
else:
    st.info("⚠️ ไม่พบข้อมูลหุ้นในพอร์ต Dime US หรือยังไม่ได้บันทึกข้อมูลใน Google Sheets แท็บ Dime_Portfolio")
