import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px

st.set_page_config(page_title="Winner Tilt Strategy", layout="wide")

st.markdown("""
    <style>
    .status-card {
        background-color: #1e222d;
        padding: 18px;
        border-radius: 10px;
        border: 1px solid #2a2e39;
        text-align: center;
    }
    .status-title { color: #848e9c; font-size: 14px; font-weight: 500; margin-bottom: 5px; }
    .status-value { font-size: 22px; font-weight: bold; }
    .status-bull { color: #00c853 !important; }
    .status-bear { color: #ff3d00 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🏆 The Winner Tilt Playbook Engine")
st.markdown("ระบบวิเคราะห์กลยุทธ์ **Winner Tilt 25** (QQQ 15 / VOO 5 / SMH 5 + GLD Hedge) พร้อมตัวกรองเส้น SMA 200 วัน")
st.markdown("---")

# ==========================================
# 1. รายชื่อ Universe หุ้นตาม Playbook
# ==========================================
UNIVERSE_QQQ_15 = ["NVDA", "AAPL", "MU", "MSFT", "AMZN", "AMD", "GOOGL", "TSLA", "INTC", "AVGO", "META", "AMAT", "LRCX", "CSCO", "SNDK"]
UNIVERSE_VOO_5 = ["LLY", "BRK-B", "JPM", "JNJ", "V"]
UNIVERSE_SMH_5 = ["TSM", "KLAC", "ASML", "MRVL", "TXN"]
HEDGE_ASSET = ["GLD"]

ALL_STRATEGY_TICKERS = list(set(UNIVERSE_QQQ_15 + UNIVERSE_VOO_5 + UNIVERSE_SMH_5 + HEDGE_ASSET))

# ==========================================
# 2. ฟังก์ชันดึงราคาและคำนวณ SMA 200
# ==========================================
@st.cache_data(ttl=1800)
def fetch_market_data(tickers):
    data_list = []
    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            df_hist = ticker.history(period="1y")
            if not df_hist.empty and len(df_hist) >= 200:
                current_price = float(df_hist['Close'].iloc[-1])
                sma_200 = float(df_hist['Close'].rolling(window=200).mean().iloc[-1])
                diff_pct = ((current_price - sma_200) / sma_200) * 100
                is_above_sma = current_price >= sma_200
                
                data_list.append({
                    "Symbol": symbol,
                    "Current_Price": current_price,
                    "SMA_200": sma_200,
                    "Diff_Pct": diff_pct,
                    "Above_SMA200": is_above_sma
                })
            else:
                data_list.append({
                    "Symbol": symbol, "Current_Price": 0.0, "SMA_200": 0.0, "Diff_Pct": 0.0, "Above_SMA200": False
                })
        except Exception:
            data_list.append({
                "Symbol": symbol, "Current_Price": 0.0, "SMA_200": 0.0, "Diff_Pct": 0.0, "Above_SMA200": False
            })
    return pd.DataFrame(data_list)

# ==========================================
# 3. ตรวจสอบ Market Regime (ดัชนีภาพรวม)
# ==========================================
st.subheader("1. 📈 Market Regime First (เช็กสภาวะตลาดใหญ่)")
st.caption("ดัชนีหลักต้องอยู่เหนือเส้น SMA 200 วัน เพื่อยืนยันว่าตลาดยังอยู่ในสภาวะขาขึ้นที่เกื้อหนุนกลยุทธ์")

with st.spinner("⏳ กำลังวิเคราะห์สภาวะตลาดใหญ่ (S&P 500, Nasdaq 100, SMH)..."):
    market_benchmarks = ["SPY", "QQQ", "SMH"]
    df_market = fetch_market_data(market_benchmarks)
    
    col_m1, col_m2, col_m3 = st.columns(3)
    cols = [col_m1, col_m2, col_m3]
    
    for i, row in df_market.iterrows():
        sym = row["Symbol"]
        status_text = "เหนือเส้น 200 วัน (Bullish)" if row["Above_SMA200"] else "ต่ำกว่าเส้น 200 วัน (Caution)"
        status_class = "status-bull" if row["Above_SMA200"] else "status-bear"
        
        with cols[i]:
            st.markdown(f"""
                <div class="status-card">
                    <div class="status-title">{sym} Benchmark</div>
                    <div class="status-value {status_class}">${row['Current_Price']:,.2f}</div>
                    <div style="font-size: 13px; margin-top: 5px;" class="{status_class}">{status_text} ({row['Diff_Pct']:+.2f}%)</div>
                </div>
            """, unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# 4. สแกนหุ้นทั้ง 25 ตัว + GLD
# ==========================================
st.subheader("2. 🔍 Rebalance Trend Filter Checklist (สแกนเส้น 200 วัน รายตัว)")

with st.spinner("⏳ กำลังสแกนหุ้นรายตัวใน Winner Tilt Universe..."):
    df_assets = fetch_market_data(ALL_STRATEGY_TICKERS)
    
    def get_group_name(sym):
        if sym in UNIVERSE_QQQ_15: return "QQQ 15 (Growth)"
        if sym in UNIVERSE_VOO_5: return "VOO 5 (Quality)"
        if sym in UNIVERSE_SMH_5: return "SMH 5 (Semi/AI)"
        if sym in HEDGE_ASSET: return "GLD (Hedge)"
        return "Other"

    df_assets["Group"] = df_assets["Symbol"].apply(get_group_name)

# ==========================================
# 🎨 ฟังก์ชันใส่สีกระทิง / หมี ในตาราง
# ==========================================
def style_trend_table(val):
    if val == "PASS (เหนือ 200 วัน)":
        return 'background-color: #0b3818; color: #00e676; font-weight: bold;'
    elif val == "FAIL (ต่ำกว่า 200 วัน - คัดออก)":
        return 'background-color: #3b1111; color: #ff5252; font-weight: bold;'
    return ''

# แสดงผลแยกตามหมวด
groups = ["QQQ 15 (Growth)", "VOO 5 (Quality)", "SMH 5 (Semi/AI)", "GLD (Hedge)"]

for grp in groups:
    st.markdown(f"#### 📌 กลุ่ม {grp}")
    df_sub = df_assets[df_assets["Group"] == grp].copy()
    
    if not df_sub.empty:
        df_sub["Status_Signal"] = df_sub["Above_SMA200"].apply(lambda x: "PASS (เหนือ 200 วัน)" if x else "FAIL (ต่ำกว่า 200 วัน - คัดออก)")
        
        df_display = df_sub[["Symbol", "Current_Price", "SMA_200", "Diff_Pct", "Status_Signal"]].rename(columns={
            "Current_Price": "ราคาปัจจุบัน ($)",
            "SMA_200": "เส้น SMA 200 วัน ($)",
            "Diff_Pct": "ระยะห่างจาก SMA200 (%)",
            "Status_Signal": "สถานะสัญญาณ Rebalance"
        })
        
        formatted_df = df_display.style.format({
            "ราคาปัจจุบัน ($)": "${:,.2f}",
            "เส้น SMA 200 วัน ($)": "${:,.2f}",
            "ระยะห่างจาก SMA200 (%)": "{:+.2f}%"
        }).map(style_trend_table, subset=["สถานะสัญญาณ Rebalance"])
        
        st.dataframe(formatted_df, use_container_width=True)

st.markdown("---")

# ==========================================
# 5. สรุปคำแนะนำในการ Rebalance
# ==========================================
st.subheader("3. 📋 Action Summary (สรุปรายการที่ต้องแอ็กชัน)")

df_failed = df_assets[~df_assets["Above_SMA200"]]

col_a1, col_a2 = st.columns(2)

with col_a1:
    st.markdown("### 🔴 หุ้นที่เข้าเกณฑ์ต้องพิจารณาคัดออก")
    if not df_failed.empty:
        for _, r in df_failed.iterrows():
            st.error(f"❌ **{r['Symbol']}** ({r['Group']}): ราคาปัจจุบัน ${r['Current_Price']:,.2f} ต่ำกว่าเส้น SMA 200 วัน (${r['SMA_200']:,.2f}) อยู่ {r['Diff_Pct']:.2f}%")
    else:
        st.success("✅ หุ้นทุกตัวในพอร์ตยึดสถานะเหนือเส้น SMA 200 วันได้ทั้งหมด ยังไม่ต้องคัดออก!")

with col_a2:
    st.markdown("### 🟢 กติกาการ Rebalance 6 เดือน")
    st.info("""
    * **ถ้าหุ้นในลิสต์ยืนเหนือเส้น 200 วัน:** ให้ปล่อยผู้ชนะวิ่งสร้างผลตอบแทนต่อไป (Let Profit Run)[cite: 1]
    * **ถ้าหลุดเส้น 200 วัน ในขณะที่ดัชนีใหญ่ยังเป็นขาขึ้น:** คัดออกตามวินัยโดยไม่มีอารมณ์ร่วม เพื่อนำเงินไปใส่ในตัวแทนถัดไป[cite: 1]
    * **คุมสัดส่วน GLD:** คุมสัดส่วนให้อยู่ในกรอบ 10-20% เพื่อบริหาร Risk / Drawdown ของภาพรวมพอร์ต[cite: 1]
    """)
