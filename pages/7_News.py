import json
import base64
import urllib.parse
import xml.etree.ElementTree as ET
import http.client
import streamlit as st
import pandas as pd
import gspread
import yfinance as yf

st.set_page_config(page_title="Stock Thai News", layout="wide")

st.markdown("""
    <style>
    .news-card {
        background-color: #1e222d;
        padding: 16px;
        border-radius: 8px;
        border-left: 4px solid #00c853;
        margin-bottom: 12px;
    }
    .news-title {
        font-size: 16px;
        font-weight: bold;
        color: #ffffff;
        text-decoration: none;
    }
    .news-title:hover {
        color: #00c853;
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

st.title("📰 ศูนย์รวมข่าวสารหุ้นภาษาไทย (Thai Stock News)")
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
# ฟังก์ชันดึงข่าวภาษาไทยจาก Google News RSS Direct
# ==========================================
def fetch_thai_news_rss(ticker):
    news_items = []
    try:
        # ค้นหาด้วย Ticker + คำว่า หุ้น ภาษาไทย
        search_query = f"หุ้น {ticker}"
        encoded_query = urllib.parse.quote(search_query)
        
        conn = http.client.HTTPSConnection("news.google.com")
        # กำหนด hl=th, gl=TH, ceid=TH:th เพื่อบังคับดึงข่าวภาษาไทยเท่านั้น
        conn.request("GET", f"/rss/search?q={encoded_query}&hl=th&gl=TH&ceid=TH:th")
        res = conn.getresponse()
        xml_data = res.read()
        conn.close()

        root = ET.fromstring(xml_data)
        for item in root.findall(".//channel/item")[:10]:
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else "#"
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            source_elem = item.find("source")
            publisher = source_elem.text if source_elem is not None else "สำนักข่าวการเงิน"
            
            if title:
                news_items.append({
                    "title": title,
                    "link": link,
                    "publisher": publisher,
                    "date": pub_date
                })
    except Exception:
        pass
    return news_items

# ==========================================
# ฟังก์ชันแสดงผลหน้าข่าวภาษาไทย
# ==========================================
def render_thai_stock_news(ticker_symbol):
    try:
        # ดึงราคาตลาดจาก yfinance
        current_price = 0.0
        day_change = 0.0
        company_name = ticker_symbol
        
        try:
            ticker_obj = yf.Ticker(ticker_symbol)
            info = ticker_obj.info
            current_price = info.get('currentPrice', info.get('regularMarketPrice', 0.0))
            day_change = info.get('regularMarketChangePercent', 0.0)
            company_name = info.get('longName', ticker_symbol)
        except Exception:
            pass

        st.markdown(f"""
            <div class="stock-header">
                <h3>📌 {company_name} ({ticker_symbol})</h3>
                <span>💵 ราคาปัจจุบัน: <b>${current_price:,.2f}</b> | เปลี่ยนแปลงวันนี้: <b style="color: {'#00c853' if day_change >= 0 else '#ff3d00'};">{day_change:+.2f}%</b></span>
            </div>
        """, unsafe_allow_html=True)
        
        st.subheader(f"🇹🇭 ข่าวสารภาษาไทยล่าสุดของหุ้น {ticker_symbol}")
        
        # ดึงข่าวภาษาไทย
        thai_news = fetch_thai_news_rss(ticker_symbol)

        if thai_news:
            for item in thai_news:
                st.markdown(f"""
                    <div class="news-card">
                        <a class="news-title" href="{item['link']}" target="_blank">🔗 {item['title']}</a>
                        <div class="news-publisher">📰 สำนักข่าว: <b>{item['publisher']}</b> | 🕒 {item['date']}</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info(f"ไม่พบข่าวสารภาษาไทยล่าสุดสำหรับหุ้น {ticker_symbol} ในขณะนี้")
            
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดข่าวสารของ {ticker_symbol}: {str(e)}")

# ==========================================
# โครงสร้าง 2 แท็บ
# ==========================================
tab_search, tab_holdings = st.tabs([
    "🔍 1. ค้นหาข่าวหุ้นภาษาไทย (Search Any Stock)", 
    "💼 2. ข่าวภาษาไทยเฉพาะหุ้นที่ถืออยู่ (Holding Stocks)"
])

# ------------------------------------------
# แท็บที่ 1: ค้นหาข่าวหุ้นภาษาไทยอะไรก็ได้
# ------------------------------------------
with tab_search:
    st.markdown("### 🔎 ค้นหาข่าวสารภาษาไทยเพื่อวางแผนเทรด")
    
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        search_ticker = st.text_input("กรอก Ticker Symbol หุ้นที่ต้องการดูข่าวภาษาไทย (เช่น NVDA, EOSE, PLTR, TSLA):", value="EOSE").strip().upper()
    
    st.markdown("---")
    if search_ticker:
        render_thai_stock_news(search_ticker)

# ------------------------------------------
# แท็บที่ 2: ข่าวภาษาไทยเฉพาะหุ้นที่ยังถืออยู่
# ------------------------------------------
with tab_holdings:
    st.markdown("### 💼 ติดตามข่าวภาษาไทยเฉพาะหุ้นที่มีสถานะถือครองอยู่ในพอร์ต")
    
    holding_tickers = get_current_holdings()
    
    if holding_tickers:
        selected_holding = st.selectbox("🎯 เลือกหุ้นที่อยู่ในพอร์ตของคุณ:", options=holding_tickers, index=0)
        st.markdown("---")
        if selected_holding:
            render_thai_stock_news(selected_holding)
    else:
        st.warning("💡 ไม่พบข้อมูลหุ้นที่ถือครองอยู่ ณ ปัจจุบัน หรือระบบไม่สามารถเชื่อมต่อ Google Sheets ได้")
