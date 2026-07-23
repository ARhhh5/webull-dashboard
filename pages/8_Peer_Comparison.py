import json
import base64
import streamlit as st
import pandas as pd
import gspread
import yfinance as yf
import plotly.express as px

st.set_page_config(page_title="Stock Peer Comparison", layout="wide")

st.markdown("""
    <style>
    .peer-card {
        background-color: #1e222d;
        padding: 16px;
        border-radius: 8px;
        border: 1px solid #2a2e39;
        margin-bottom: 20px;
    }
    .metric-header {
        color: #2962ff;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚔️ Stock Peer Comparison (ระบบเปรียบเทียบหุ้นกับคู่แข่งในอุตสาหกรรม)")
st.markdown("วิเคราะห์มวยถูกคู่ เปรียบเทียบ Valuation, Profitability และอัตราการเติบโตของหุ้นในพอร์ตกับคู่แข่ง")
st.markdown("---")

# ==========================================
# 1. เชื่อมต่อ Google Sheets เพื่ออ่านพอร์ต
# ==========================================
@st.cache_resource
def init_gsheet():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64: return None
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        return gc
    except Exception:
        return None

def get_current_holdings():
    gc = init_gsheet()
    holdings = set()
    if not gc:
        return list(holdings)
    
    try:
        sh = gc.open("หุ้นของเรา")
        
        # 1. จาก Webull Order History
        try:
            ws1 = sh.worksheet("Webull_Order_History")
            df_w = pd.DataFrame(ws1.get_all_records())
            if not df_w.empty:
                sym_col = next((c for c in df_w.columns if 'sym' in str(c).lower() or 'symbol' in str(c).lower()), 'Symbol')
                side_col = next((c for c in df_w.columns if 'side' in str(c).lower() or 'buy/sell' in str(c).lower()), 'Side')
                qty_col = next((c for c in df_w.columns if 'qty' in str(c).lower() or 'quantity' in str(c).lower()), 'Qty')
                
                for symbol, group in df_w.groupby(sym_col):
                    sym_clean = str(symbol).strip().upper()
                    if not sym_clean or sym_clean == 'NAN': continue
                    
                    buy_qty = 0.0
                    sell_qty = 0.0
                    for _, row in group.iterrows():
                        side = str(row[side_col]).upper()
                        try: q = float(str(row[qty_col]).replace(",", "").replace("$", ""))
                        except: continue
                        
                        if "BUY" in side or "ซื้อ" in side: buy_qty += q
                        elif "SELL" in side or "ขาย" in side: sell_qty += q
                    
                    if (buy_qty - sell_qty) > 0.001:
                        holdings.add(sym_clean)
        except Exception: pass
        
        # 2. จาก Dime Portfolio (US)
        try:
            ws2 = sh.worksheet("Dime_Portfolio")
            df_dime_us = pd.DataFrame(ws2.get_all_records())
            if not df_dime_us.empty:
                sym_col = next((c for c in df_dime_us.columns if 'sym' in str(c).lower() or 'ticker' in str(c).lower() or 'หุ้น' in str(c)), None)
                if sym_col:
                    for s in df_dime_us[sym_col].astype(str).str.strip().str.upper().unique():
                        if s and s != 'NAN': holdings.add(s)
        except Exception: pass

    except Exception: pass
    
    return sorted(list(holdings))

# ==========================================
# 2. ระบบค้นหาคู่แข่งตามอุตสาหกรรม (Smart Matching)
# ==========================================
PRESET_MAPPING = {
    "QQQI": ["QQQM", "QQQ", "JEPQ", "SPYI", "JEPI"],
    "QQQM": ["QQQ", "QQQI", "JEPQ", "SPY", "IVV"],
    "QQQ": ["QQQM", "QQQI", "SPY", "VOO", "IWM"],
    "SPYI": ["QQQI", "JEPI", "JEPQ", "SPY", "VOO"],
    "NVDA": ["AMD", "TSM", "INTC", "AVGO", "QCOM", "MU"],
    "AMD": ["NVDA", "INTC", "TSM", "QCOM", "AVGO"],
    "TSLA": ["RIVN", "LCID", "NIO", "BYDDF", "GM", "F"],
    "PLTR": ["SNOW", "DDOG", "NET", "PATH", "AI"],
    "EOSE": ["STEM", "FLNC", "QS", "ENVX"],
    "ULTY": ["TSLY", "CONY", "NVDY", "JEPI", "JEPQ"]
}

INDUSTRY_PEERS_MAP = {
    "Semiconductors": ["AMD", "TSM", "NVDA", "INTC", "AVGO", "QCOM"],
    "Consumer Electronics": ["AAPL", "MSFT", "GOOGL", "AMZN"],
    "Software": ["PLTR", "SNOW", "DDOG", "NET", "MSFT", "ORCL"],
    "Auto Manufacturers": ["TSLA", "RIVN", "LCID", "NIO", "BYDDF"],
    "Electrical Equipment": ["EOSE", "STEM", "FLNC", "QS", "ENVX"]
}

def auto_suggest_peers(ticker_symbol):
    ticker_clean = ticker_symbol.strip().upper()
    
    # เช็กจาก Preset เฉพาะตัวก่อน (เช่น QQQI, QQQM)
    if ticker_clean in PRESET_MAPPING:
        return PRESET_MAPPING[ticker_clean], "ETF / Covered Call", "Fund / Index"
        
    try:
        t = yf.Ticker(ticker_clean)
        info = t.info
        industry = info.get("industry", "")
        sector = info.get("sector", "")
        quote_type = info.get("quoteType", "")
        
        if quote_type == "ETF":
            return ["QQQ", "QQQM", "SPY", "JEPQ", "JEPI"], "ETF", "Exchange Traded Fund"
            
        for key, peers in INDUSTRY_PEERS_MAP.items():
            if key.lower() in industry.lower() or key.lower() in sector.lower():
                return [p for p in peers if p != ticker_clean], sector, industry
                
        return ["AMD", "TSM", "NVDA", "MSFT", "AAPL"], sector if sector else "N/A", industry if industry else "N/A"
    except Exception:
        return ["QQQM", "QQQ", "SPY", "AMD"], "N/A", "N/A"

# ==========================================
# 3. ฟังก์ชันดึงเมตริกสำหรับเปรียบเทียบ
# ==========================================
def fetch_stock_metrics(ticker_list):
    metrics_data = []
    
    for symbol in ticker_list:
        symbol_clean = symbol.strip().upper()
        if not symbol_clean: continue
        
        try:
            t = yf.Ticker(symbol_clean)
            info = t.info
            
            m_cap = info.get("marketCap", info.get("totalAssets", 0))
            pe = info.get("trailingPE", info.get("forwardPE", None))
            fwd_pe = info.get("forwardPE", None)
            ps = info.get("priceToSalesTrailing12Months", None)
            pb = info.get("priceToBook", None)
            rev_growth = info.get("revenueGrowth", None)
            profit_margin = info.get("profitMargins", None)
            gross_margin = info.get("grossMargins", None)
            roe = info.get("returnOnEquity", None)
            beta = info.get("beta", None)
            price = info.get("currentPrice", info.get("regularMarketPrice", info.get("navPrice", 0.0)))
            
            metrics_data.append({
                "Ticker": symbol_clean,
                "Company": info.get("shortName", symbol_clean),
                "Price ($)": price if price else 0.0,
                "Market Cap / NAV ($B)": round(m_cap / 1e9, 2) if m_cap else 0.0,
                "P/E Ratio": round(pe, 2) if pe else None,
                "Forward P/E": round(fwd_pe, 2) if fwd_pe else None,
                "P/S Ratio": round(ps, 2) if ps else None,
                "P/B Ratio": round(pb, 2) if pb else None,
                "Gross Margin (%)": round(gross_margin * 100, 2) if gross_margin else None,
                "Net Margin (%)": round(profit_margin * 100, 2) if profit_margin else None,
                "ROE (%)": round(roe * 100, 2) if roe else None,
                "Revenue Growth (%)": round(rev_growth * 100, 2) if rev_growth else None,
                "Beta": round(beta, 2) if beta else None
            })
        except Exception:
            metrics_data.append({
                "Ticker": symbol_clean, "Company": "N/A", "Price ($)": 0.0,
                "Market Cap / NAV ($B)": 0.0, "P/E Ratio": None, "Forward P/E": None,
                "P/S Ratio": None, "P/B Ratio": None, "Gross Margin (%)": None,
                "Net Margin (%)": None, "ROE (%)": None, "Revenue Growth (%)": None,
                "Beta": None
            })
            
    return pd.DataFrame(metrics_data)

# ==========================================
# 4. ส่วนแสดงผล UI
# ==========================================
holding_list = get_current_holdings()

col_select, col_info = st.columns([1, 2])

with col_select:
    if holding_list:
        selected_stock = st.selectbox("🎯 เลือกหุ้นหลักในพอร์ตที่ต้องการเปรียบเทียบ:", options=holding_list, index=0)
    else:
        selected_stock = st.text_input("กรอก Ticker หุ้นหลัก (เช่น QQQI, NVDA, EOSE):", value="QQQI").strip().upper()

# ดึงคู่แข่งอัตโนมัติ
suggested_peers, sector_name, industry_name = auto_suggest_peers(selected_stock)

with col_info:
    st.markdown(f"""
        <div class="peer-card">
            📌 หุ้นหลัก: <span style="color:#00c853; font-size:18px;"><b>{selected_stock}</b></span> | 
            <b>Sector/Category:</b> {sector_name} | 
            <b>Industry/Type:</b> {industry_name}
        </div>
    """, unsafe_allow_html=True)

# พิมพ์เพื่อเพิ่มหรือแก้ไข Ticker คู่แข่งได้อย่างอิสระ (ไม่ติดปัญหา No Results)
default_peers_str = ", ".join(suggested_peers)
peers_user_input = st.text_input(
    "🤝 รายชื่อหุ้นคู่แข่งที่ดึงมาให้อัตโนมัติ (สามารถพิมพ์เพิ่ม/แก้ไข Ticker เองได้ คั่นด้วยเครื่องหมายจุลภาค , ):",
    value=default_peers_str
)

# แปลงข้อความที่พิมพ์เป็น List รายชื่อ Ticker
parsed_peers = [p.strip().upper() for p in peers_user_input.split(",") if p.strip()]
all_targets = [selected_stock] + [p for p in parsed_peers if p != selected_stock]

st.markdown("---")

if st.button("🚀 เริ่มเปรียบเทียบข้อมูล & วิเคราะห์กราฟ (Compare Peers)", type="primary"):
    with st.spinner("กำลังดึงข้อมูล Valuation และสร้างกราฟเปรียบเทียบ..."):
        df_metrics = fetch_stock_metrics(all_targets)
        
        if not df_metrics.empty:
            # ------------------------------------------
            # ส่วนที่ 1: ตารางสรุปข้อมูล
            # ------------------------------------------
            st.subheader(f"📊 1. ตารางเปรียบเทียบ Valuation & งบการเงิน ({' vs '.join(all_targets)})")
            
            df_display = df_metrics.copy()
            df_display["Price ($)"] = df_display["Price ($)"].apply(lambda x: f"${x:,.2f}" if x else "-")
            df_display["Market Cap / NAV ($B)"] = df_display["Market Cap / NAV ($B)"].apply(lambda x: f"${x:,.2f}B" if x else "-")
            
            df_transposed = df_display.set_index("Ticker").T
            st.dataframe(df_transposed, use_container_width=True)
            
            st.markdown("---")
            
            # ------------------------------------------
            # ส่วนที่ 2: กราฟแท่งเปรียบเทียบ (Visual Comparison Charts)
            # ------------------------------------------
            st.subheader("📈 2. กราฟเปรียบเทียบมวยถูกคู่ (Visual Bar Charts)")
            
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                # กราฟ Market Cap / NAV
                fig_mcap = px.bar(
                    df_metrics, 
                    x="Ticker", 
                    y="Market Cap / NAV ($B)", 
                    color="Ticker",
                    title="มูลค่าตลาด / ขนาดสินทรัพย์ (Market Cap or NAV - $B)",
                    text_auto=True,
                    template="plotly_dark"
                )
                fig_mcap.update_layout(showlegend=False)
                st.plotly_chart(fig_mcap, use_container_width=True)

                # กราฟ P/E
                df_pe = df_metrics.dropna(subset=["P/E Ratio"])
                if not df_pe.empty:
                    fig_pe = px.bar(
                        df_pe, 
                        x="Ticker", 
                        y="P/E Ratio", 
                        color="Ticker",
                        title="อัตราส่วนราคาต่อกำไร (P/E Ratio - ยิ่งต่ำยิ่งถูก)",
                        text_auto=True,
                        template="plotly_dark"
                    )
                    fig_pe.update_layout(showlegend=False)
                    st.plotly_chart(fig_pe, use_container_width=True)
                else:
                    st.info("💡 สินค้ากลุ่ม ETF/Covered Call บางประเภทอาจไม่มีค่า P/E Ratio")

            with col_chart2:
                # กราฟ Net Margin
                df_margin = df_metrics.dropna(subset=["Net Margin (%)"])
                if not df_margin.empty:
                    fig_margin = px.bar(
                        df_margin, 
                        x="Ticker", 
                        y="Net Margin (%)", 
                        color="Ticker",
                        title="อัตรากำไรสุทธิ (Net Profit Margin % - ยิ่งสูงยิ่งดี)",
                        text_auto=True,
                        template="plotly_dark"
                    )
                    fig_margin.update_layout(showlegend=False)
                    st.plotly_chart(fig_margin, use_container_width=True)

                # กราฟ Revenue Growth
                df_growth = df_metrics.dropna(subset=["Revenue Growth (%)"])
                if not df_growth.empty:
                    fig_growth = px.bar(
                        df_growth, 
                        x="Ticker", 
                        y="Revenue Growth (%)", 
                        color="Ticker",
                        title="อัตราการเติบโตของรายได้ (Revenue Growth % - QoQ)",
                        text_auto=True,
                        template="plotly_dark"
                    )
                    fig_growth.update_layout(showlegend=False)
                    st.plotly_chart(fig_growth, use_container_width=True)

            st.info("💡 **คำแนะนำจากโอเลี้ยง:** สำหรับสินทรัพย์ประเภท ETF/Covered Call บอสสามารถเปรียบเทียบขนาดสินทรัพย์ (NAV) และราคาเพื่อดูสภาพคล่องทดแทนได้ครับ!")
        else:
            st.warning("ไม่สามารถดึงข้อมูลได้ กรุณาตรวจสอบ Ticker หุ้นอีกครั้ง")
