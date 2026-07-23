import json
import base64
import streamlit as st
import pandas as pd
import gspread
import yfinance as yf

st.set_page_config(page_title="Stock News & Analysis", layout="wide")

st.markdown("""
    <style>
    .news-card {
        background-color: #1e222d;
        padding: 16px;
        border-radius: 8px;
        border-left: 4px solid #2962ff;
        margin-bottom: 12px;
    }
    .news-title {
        font-size: 16px;
        font-weight: bold;
        color: #ffffff;
        text-decoration: none;
    }
    .news-title:hover {
        color: #2962ff;
    }
    .news-publisher {
        font-size: 12px;
        color: #848e9c;
        margin-top: 6px;
    }
    .stock-header {
        background-color: #1e222d;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #2a2e39;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📰 ศูนย์รวมข่าวสาร & วิเคราะห์หุ้น (Stock News)")
st.markdown("---")

# ==========================================
# ดึงข้อมูลจาก Google Sheet เพื่อหาหุ้นที่ถืออยู่จริง
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
        
        # 1. จาก Webull Order History (คำนวณคงเหลือ)
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
# ฟังก์ชันดึงข่าวสารและข้อมูลหุ้นด้วย yfinance
# ==========================================
def render_stock_news(ticker_symbol):
    try:
        ticker_obj = yf.Ticker(ticker_symbol)
        info = ticker_obj.info
        
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 0.0))
        day_change = info.get('regularMarketChangePercent', 0.0)
        company_name = info.get('longName', ticker_symbol)
        market_cap = info.get('marketCap', 0)
        
        st.markdown(f"""
            <div class="stock-header">
                <h3>📌 {company_name} ({ticker_symbol})</h3>
                <span>💵 ราคาปัจจุบัน: <b>${current_price:,.2f}</b> | เปลี่ยนแปลงวันนี้: <b style="color: {'#00c853' if day_change >= 0 else '#ff3d00'};">{day_change:+.2f}%</b> | Market Cap: <b>${market_cap:,.0f}</b></span>
            </div>
        """, unsafe_allow_html=True)
        
        st.subheader("📰 รายการข่าวล่าสุด")
        news_list = ticker_obj.news
        
        if news_list:
            for n in news_list[:8]:  # แสดง 8 ข่าวล่าสุด
                title = n.get('title', 'ไม่มีหัวข้อข่าว')
                link = n.get('link', '#')
                publisher = n.get('publisher', 'ข่าวการเงิน')
                
                st.markdown(f"""
                    <div class="news-card">
                        <a class="news-title" href="{link}" target="_blank">🔗 {title}</a>
                        <div class="news-publisher">สำนักข่าว: {publisher}</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info(f"ไม่พบข่าวสารอัปเดตสำหรับหุ้น {ticker_symbol} ในขณะนี้")
            
    except Exception as e:
        st.error(f"ไม่สามารถดึงข้อมูลข่าวสารของ {ticker_symbol} ได้: {str(e)}")

# ==========================================
# โครงสร้าง 2 แท็บตามโจทย์ของบอส
# ==========================================
tab_search, tab_holdings = st.tabs([
    "🔍 1. ค้นหาข่าวหุ้นรายตัว (Search Any Stock)", 
    "💼 2. ข่าวหุ้นที่ยังถืออยู่ในพอร์ต (Holding Stocks)"
])

# ------------------------------------------
# แท็บที่ 1: ค้นหาข่าวหุ้นอะไรก็ได้
# ------------------------------------------
with tab_search:
    st.markdown("### 🔎 ค้นหาข่าวหุ้นรายตัวเพื่อวางแผนเทรด")
    
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        search_ticker = st.text_input("กรอก Ticker Symbol หุ้นที่ต้องการดูข่าว (เช่น NVDA, EOSE, PLTR, TSLA):", value="EOSE").strip().upper()
    
    st.markdown("---")
    if search_ticker:
        render_stock_news(search_ticker)

# ------------------------------------------
# แท็บที่ 2: ข่าวเฉพาะหุ้นที่ยังถืออยู่
# ------------------------------------------
with tab_holdings:
    st.markdown("### 💼 ติดตามข่าวสารเฉพาะหุ้นที่มีสถานะถือครองอยู่ในพอร์ต")
    
    holding_tickers = get_current_holdings()
    
    if holding_tickers:
        selected_holding = st.selectbox("🎯 เลือกหุ้นที่อยู่ในพอร์ตของคุณ:", options=holding_tickers, index=0)
        st.markdown("---")
        if selected_holding:
            render_stock_news(selected_holding)
    else:
        st.warning("💡 ไม่พบข้อมูลหุ้นที่ถือครองอยู่ ณ ปัจจุบัน หรือระบบไม่สามารถเชื่อมต่อ Google Sheets ได้")
