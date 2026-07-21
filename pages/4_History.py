import streamlit as st
import pandas as pd
import json
import base64
import gspread
import yfinance as yf

st.set_page_config(page_title="Trade History & True Net Performance", layout="wide")

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

st.title("📜 ประวัติการเทรด & ผลประกอบการที่แท้จริง (True Net PnL)")
st.markdown("---")

@st.cache_resource
def init_gsheet():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64: return None
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        return gc
    except Exception as e:
        st.error(f"เชื่อมต่อ Google Sheets ล้มเหลว: {e}")
        return None

# ==========================================
# 1. ฟังก์ชันดึงประวัติออเดอร์ (Realized PnL) แบบ FIFO
# ==========================================
def get_historical_realized_pnl(gc):
    if not gc: return pd.DataFrame()
    orders = []
    try:
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Webull_Order_History")
        records = worksheet.get_all_records()
        
        for r in records:
            sym = str(r.get("Symbol") or r.get("Symbol & Name") or r.get("หุ้น (Ticker)") or "").strip().upper()
            if not sym: continue
            if " " in sym: sym = sym.split(" ")[0]
                
            raw_side = str(r.get("Side") or r.get("Buy/Sell") or "").strip().upper()
            if "BUY" in raw_side: side = "BUY"
            elif "SELL" in raw_side: side = "SELL"
            else: continue
                
            try:
                qty = float(str(r.get("Qty") or r.get("Quantity") or r.get("จำนวนหุ้น (Volume)") or 0).replace(",", ""))
                price = float(str(r.get("Price") or r.get("Traded Price") or r.get("ราคาซื้อเฉลี่ย (Buy Price)") or 0).replace(",", ""))
            except: continue
                
            time_val = str(r.get("Time") or r.get("Trade Date") or r.get("วันที่ปิดไม้ (Date)") or "2025-01-01")
            
            if qty > 0 and price > 0:
                orders.append({
                    "Time": time_val,
                    "Symbol": sym,
                    "Side": side,
                    "Qty": qty,
                    "Price": price
                })
    except Exception as e:
        st.warning(f"อ่านชีท Webull_Order_History ไม่สำเร็จ: {e}")
        
    df_orders = pd.DataFrame(orders)
    if df_orders.empty: return pd.DataFrame()
    
    df_sorted = df_orders.sort_values(by=["Time"], ascending=True).copy()
    closed_trades = []
    
    for symbol, group in df_sorted.groupby("Symbol"):
        buy_queue = []
        for _, row in group.iterrows():
            side = row["Side"]
            qty = row["Qty"]
            price = row["Price"]
            
            if side == "BUY":
                buy_queue.append({"qty": qty, "price": price})
            elif side == "SELL":
                sell_qty_left = qty
                while sell_qty_left > 0 and buy_queue:
                    first_buy = buy_queue[0]
                    matched_qty = min(sell_qty_left, first_buy["qty"])
                    buy_price = first_buy["price"]
                    sell_price = price
                    pnl = matched_qty * (sell_price - buy_price)
                    
                    closed_trades.append({
                        "Symbol": symbol,
                        "Realized PnL ($)": pnl
                    })
                    
                    sell_qty_left -= matched_qty
                    first_buy["qty"] -= matched_qty
                    if first_buy["qty"] <= 0:
                        buy_queue.pop(0)
                        
    df_closed = pd.DataFrame(closed_trades)
    if not df_closed.empty:
        return df_closed.groupby("Symbol")["Realized PnL ($)"].sum().reset_index()
    return pd.DataFrame()

# ==========================================
# 2. ฟังก์ชันคำนวณ Unrealized PnL จากราคาตลาดจริง (yfinance)
# ==========================================
@st.cache_data(ttl=300)
def fetch_live_prices(symbols):
    prices = {}
    for sym in symbols:
        try:
            # แปลงสัญลักษณ์สำหรับหุ้นไทยถ้ามี
            ticker_sym = sym if not sym.isalpha() or len(sym) <= 5 else sym
            t = yf.Ticker(ticker_sym)
            price = t.fast_info.get('lastPrice') or t.info.get('regularMarketPrice') or 0.0
            prices[sym] = float(price)
        except:
            prices[sym] = 0.0
    return prices

def get_current_unrealized_pnl(gc):
    if not gc: return pd.DataFrame()
    unrealized_data = []
    try:
        sh = gc.open("หุ้นของเรา")
        for sheet_name in ["Dime_Portfolio", "Webull_Positions", "Dime_TH_Portfolio"]: 
            try:
                ws = sh.worksheet(sheet_name)
                records = ws.get_all_records()
                if not records: continue
                
                df_rec = pd.DataFrame(records)
                
                # ค้นหาคอลัมน์ Ticker / Qty / AvgCost
                sym_col = next((c for c in df_rec.columns if 'ticker' in str(c).lower() or 'symbol' in str(c).lower() or 'หุ้น' in str(c)), None)
                qty_col = next((c for c in df_rec.columns if 'volume' in str(c).lower() or 'qty' in str(c).lower() or 'จำนวน' in str(c)), None)
                cost_col = next((c for c in df_rec.columns if 'cost' in str(c).lower() or 'ต้นทุน' in str(c)), None)
                
                if not sym_col or not qty_col or not cost_col: continue
                
                # ดึงลิสต์หุ้นเพื่อไปเอาราคาจริง
                symbols = [str(s).strip().upper().split(" ")[0] for s in df_rec[sym_col] if str(s).strip()]
                live_prices = fetch_live_prices(list(set(symbols)))
                
                for _, r in df_rec.iterrows():
                    sym = str(r.get(sym_col, "")).strip().upper()
                    if not sym: continue
                    if " " in sym: sym = sym.split(" ")[0]
                    
                    try:
                        qty = float(str(r.get(qty_col, 0)).replace(",", ""))
                        avg_cost = float(str(r.get(cost_col, 0)).replace(",", ""))
                        
                        if qty <= 0 or avg_cost <= 0: continue
                        
                        current_price = live_prices.get(sym, avg_cost)
                        # คำนวณ PnL จริง: (ราคาปัจจุบัน - ต้นทุนเฉลี่ย) * จำนวนหุ้น
                        if current_price > 0:
                            unrealized_pnl = (current_price - avg_cost) * qty
                        else:
                            unrealized_pnl = 0.0
                            
                        unrealized_data.append({
                            "Symbol": sym,
                            "Unrealized PnL ($)": unrealized_pnl
                        })
                    except: continue
            except: continue
    except: pass
    
    df_unrealized = pd.DataFrame(unrealized_data)
    if not df_unrealized.empty:
        return df_unrealized.groupby("Symbol")["Unrealized PnL ($)"].sum().reset_index()
    return pd.DataFrame()

def color_pnl(val):
    if pd.isna(val): return ''
    color = '#00c853' if val > 0 else ('#ff3d00' if val < 0 else '#848e9c')
    return f'color: {color}; font-weight: bold;'

# ดึงข้อมูลทั้งหมดมาประมวลผล
gc = init_gsheet()
df_realized = get_historical_realized_pnl(gc)
df_unrealized = get_current_unrealized_pnl(gc)

if not df_realized.empty or not df_unrealized.empty:
    if df_realized.empty:
        df_net = df_unrealized.copy()
        df_net["Realized PnL ($)"] = 0.0
    elif df_unrealized.empty:
        df_net = df_realized.copy()
        df_net["Unrealized PnL ($)"] = 0.0
    else:
        df_net = pd.merge(df_realized, df_unrealized, on="Symbol", how="outer").fillna(0.0)
        
    df_net["True Net PnL ($)"] = df_net["Realized PnL ($)"] + df_net["Unrealized PnL ($)"]
    df_net = df_net.sort_values(by="True Net PnL ($)", ascending=False)
    
    total_realized = df_net["Realized PnL ($)"].sum()
    total_unrealized = df_net["Unrealized PnL ($)"].sum()
    grand_total_net = df_net["True Net PnL ($)"].sum()
    
    tab1, tab2 = st.tabs(["🔥 สรุปความจริงรายหุ้น (True Net PnL)", "📜 ข้อมูลดิบที่ระบบอ่านได้"])
    
    with tab1:
        net_class = "pnl-positive" if grand_total_net >= 0 else "pnl-negative"
        net_prefix = "+" if grand_total_net >= 0 else ""
        
        realized_class = "pnl-positive" if total_realized >= 0 else "pnl-negative"
        realized_prefix = "+" if total_realized >= 0 else ""
        
        unrealized_class = "pnl-positive" if total_unrealized >= 0 else "pnl-negative"
        unrealized_prefix = "+" if total_unrealized >= 0 else ""
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="metric-container"><div class="metric-label">💰 กำไรที่ปิดไปแล้ว (อดีต)</div><div class="metric-value {realized_class}">{realized_prefix}${total_realized:,.2f}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-container"><div class="metric-label">📉 สถานะติดดอย/กำไร (ปัจจุบัน)</div><div class="metric-value {unrealized_class}">{unrealized_prefix}${total_unrealized:,.2f}</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-container"><div class="metric-label">⚖️ ผลประกอบการสุทธิของแท้!</div><div class="metric-value {net_class}">{net_prefix}${grand_total_net:,.2f}</div></div>', unsafe_allow_html=True)
            
        st.markdown("---")
        
        df_show = df_net[["Symbol", "Realized PnL ($)", "Unrealized PnL ($)", "True Net PnL ($)"]]
        df_show.columns = ["ชื่อหุ้น", "กำไรอดีต (ปิดแล้ว)", "สถานะปัจจุบัน (ติดดอย/กำไร)", "สุทธิของแท้ (Net PnL)"]
        
        st.dataframe(
            df_show.style.map(color_pnl, subset=["กำไรอดีต (ปิดแล้ว)", "สถานะปัจจุบัน (ติดดอย/กำไร)", "สุทธิของแท้ (Net PnL)"])
            .format({
                "กำไรอดีต (ปิดแล้ว)": "${:,.2f}",
                "สถานะปัจจุบัน (ติดดอย/กำไร)": "${:,.2f}",
                "สุทธิของแท้ (Net PnL)": "${:,.2f}"
            }),
            use_container_width=True
        )
        
    with tab2:
        st.subheader("ประวัติ Realized แยกรายตัว")
        st.dataframe(df_realized, use_container_width=True)
        st.subheader("สถานะ Unrealized แยกรายตัว")
        st.dataframe(df_unrealized, use_container_width=True)
else:
    st.error("⚠️ ไม่สามารถดึงข้อมูลหุ้นจาก Google Sheet ได้ กรุณาตรวจสอบชื่อแท็บ (Webull_Order_History, Dime_Portfolio) อีกครั้งครับ!")
