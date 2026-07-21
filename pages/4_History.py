import streamlit as st
import pandas as pd
import json
import base64
import gspread

st.set_page_config(page_title="Trade History & Closed Trades", layout="wide")

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

st.title("📜 ประวัติการเทรด & สรุปไม้ที่ปิด (Closed Trades)")
st.markdown("---")

@st.cache_resource
def init_gsheet():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64:
            return None
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        return gc
    except Exception as e:
        st.error(f"เชื่อมต่อ Google Sheets ล้มเหลว: {e}")
        return None

def get_webull_orders(gc):
    orders = []
    if not gc: return pd.DataFrame()
    try:
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Webull_Order_History")
        records = worksheet.get_all_records()
        for r in records:
            sym = str(r.get("Symbol", "")).strip().upper()
            raw_side = str(r.get("Side", "")).strip().upper()
            
            # 🎯 แก้บั๊กสกัดไอคอน "🟢 BUY" และ "🔴 SELL" ออกให้อัตโนมัติ!
            if "BUY" in raw_side:
                side = "BUY"
            elif "SELL" in raw_side:
                side = "SELL"
            else:
                side = ""
                
            if sym and side:
                orders.append({
                    "Time": str(r.get("Time", "")),
                    "Symbol": sym,
                    "Side": side,
                    "Qty": float(r.get("Qty", 0)),
                    "Price": float(r.get("Price", 0)),
                    "Broker": "Webull"
                })
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการดึงข้อมูล Webull_Order_History: {e}")
    return pd.DataFrame(orders)

def get_dime_closed_orders(gc):
    closed_orders = []
    if not gc: return pd.DataFrame()
    try:
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Dime_Closed_Orders")
        records = worksheet.get_all_records()
        for r in records:
            sym = str(r.get("หุ้น (Ticker)", "")).strip().upper()
            if sym:
                market = str(r.get("ตลาด (US/TH)", "US")).strip().upper()
                qty = float(r.get("จำนวนหุ้น (Qty)", 0))
                buy_price = float(r.get("ราคาซื้อเฉลี่ย (Buy Price)", 0))
                sell_price = float(r.get("ราคาขายจริง (Sell Price)", 0))
                
                pnl = (sell_price - buy_price) * qty
                
                closed_orders.append({
                    "Symbol": sym,
                    "Broker": f"Dime {market}",
                    "Qty": qty,
                    "Buy Price": buy_price,
                    "Sell Price": sell_price,
                    "Realized PnL ($)": pnl
                })
    except:
        pass # ถ้าแท็บยังไม่มี ไม่เป็นไร
    return pd.DataFrame(closed_orders)

def calculate_webull_fifo(df_orders):
    if df_orders.empty:
        return pd.DataFrame()
    
    df_sorted = df_orders.sort_values(by="Time", ascending=True).copy()
    closed_trades = []
    
    for symbol, group in df_sorted.groupby("Symbol"):
        buy_queue = []
        for _, row in group.iterrows():
            side = row["Side"]
            qty = row["Qty"]
            price = row["Price"]
            broker = row["Broker"]
            
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
                        "Broker": broker,
                        "Qty": matched_qty,
                        "Buy Price": buy_price,
                        "Sell Price": sell_price,
                        "Realized PnL ($)": pnl
                    })
                    
                    sell_qty_left -= matched_qty
                    first_buy["qty"] -= matched_qty
                    
                    if first_buy["qty"] <= 0:
                        buy_queue.pop(0)
                        
    return pd.DataFrame(closed_trades)

# ฟังก์ชันไฮไลต์สีเขียวแดง
def color_pnl(val):
    if pd.isna(val):
        return ''
    color = '#00c853' if val > 0 else ('#ff3d00' if val < 0 else '#848e9c')
    return f'color: {color}; font-weight: bold;'

with st.spinner("⏳ กำลังประมวลผลประวัติการเทรด..."):
    gc = init_gsheet()
    
    # 1. ดึงข้อมูล
    df_webull_raw = get_webull_orders(gc)
    df_dime_closed = get_dime_closed_orders(gc)
    
    # 2. ทำ FIFO Webull
    df_webull_closed = calculate_webull_fifo(df_webull_raw)
    
    # 3. รวมร่าง Webull กับ Dime
    df_all_closed = pd.concat([df_webull_closed, df_dime_closed], ignore_index=True)
    
    tab1, tab2 = st.tabs(["📊 สรุปภาพรวมหุ้นที่ปิดขายแล้ว (Realized PnL)", "📜 ประวัติออเดอร์สั่งซื้อทั้งหมดจาก Sheet"])
    
    with tab1:
        if not df_all_closed.empty:
            total_realized_pnl = df_all_closed["Realized PnL ($)"].sum()
            
            # --- 🎯 กระบวนการรวมยอด (1 หุ้น = 1 บรรทัด) ---
            df_all_closed["Total_Buy_Cost"] = df_all_closed["Qty"] * df_all_closed["Buy Price"]
            df_all_closed["Total_Sell_Rev"] = df_all_closed["Qty"] * df_all_closed["Sell Price"]
            
            df_grouped = df_all_closed.groupby(["Symbol", "Broker"]).agg(
                Total_Qty=("Qty", "sum"),
                Total_Buy_Cost=("Total_Buy_Cost", "sum"),
                Total_Sell_Rev=("Total_Sell_Rev", "sum"),
                Total_PnL=("Realized PnL ($)", "sum")
            ).reset_index()
            
            # คำนวณราคาเฉลี่ย
            df_grouped["Avg Buy Price"] = df_grouped.apply(lambda r: r["Total_Buy_Cost"] / r["Total_Qty"] if r["Total_Qty"] > 0 else 0, axis=1)
            df_grouped["Avg Sell Price"] = df_grouped.apply(lambda r: r["Total_Sell_Rev"] / r["Total_Qty"] if r["Total_Qty"] > 0 else 0, axis=1)
            df_grouped["Return (%)"] = df_grouped.apply(lambda r: (r["Total_PnL"] / r["Total_Buy_Cost"] * 100) if r["Total_Buy_Cost"] > 0 else 0, axis=1)
            
            total_symbols_closed = len(df_grouped)
            winning_symbols = len(df_grouped[df_grouped["Total_PnL"] > 0])
            win_rate = (winning_symbols / total_symbols_closed * 100) if total_symbols_closed > 0 else 0
            
            pnl_class = "pnl-positive" if total_realized_pnl >= 0 else "pnl-negative"
            pnl_prefix = "+" if total_realized_pnl >= 0 else ""
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f'<div class="metric-container"><div class="metric-label">💰 กำไร/ขาดทุนสะสมจริงทั้งหมด</div><div class="metric-value {pnl_class}">{pnl_prefix}${total_realized_pnl:,.2f}</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="metric-container"><div class="metric-label">🎯 จำนวนหุ้นที่ปิดขายแล้วทั้งหมด</div><div class="metric-value">{total_symbols_closed} ตัว</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="metric-container"><div class="metric-label">🔥 อัตราการชนะ (Win Rate)</div><div class="metric-value">{win_rate:.1f}%</div></div>', unsafe_allow_html=True)
                
            st.markdown("---")
            
            # จัดเรียงลำดับ ให้ตัวที่กำไรสูงสุดขึ้นก่อน
            df_display = df_grouped.sort_values(by="Total_PnL", ascending=False).copy()
            
            df_show = df_display[["Symbol", "Broker", "Total_Qty", "Avg Buy Price", "Avg Sell Price", "Total_PnL", "Return (%)"]]
            df_show.columns = ["Symbol", "Broker", "จำนวนหุ้นรวม", "ราคาซื้อเฉลี่ย", "ราคาขายเฉลี่ย", "กำไร/ขาดทุนสะสม ($)", "ผลตอบแทน (%)"]
            
            # ใส่ Format และเพิ่มสีเขียว/แดงในตาราง
            st.dataframe(
                df_show.style.map(color_pnl, subset=["กำไร/ขาดทุนสะสม ($)", "ผลตอบแทน (%)"])
                .format({
                    "จำนวนหุ้นรวม": "{:,.2f}",
                    "ราคาซื้อเฉลี่ย": "${:,.2f}",
                    "ราคาขายเฉลี่ย": "${:,.2f}",
                    "กำไร/ขาดทุนสะสม ($)": "${:,.2f}",
                    "ผลตอบแทน (%)": "{:+.2f}%"
                }),
                use_container_width=True
            )
        else:
            st.info("ยังไม่มีรายการปิดขายหุ้น (Closed Trades) ในระบบ")
            
    with tab2:
        st.markdown("### ประวัติออเดอร์ทั้งหมดจาก Google Sheet")
        if not df_webull_raw.empty:
            df_raw_display = df_webull_raw.sort_values(by="Time", ascending=False).copy()
            st.dataframe(
                df_raw_display.style.format({
                    "Qty": "{:,.2f}",
                    "Price": "${:,.2f}"
                }),
                use_container_width=True
            )
        else:
            st.warning("ยังไม่พบข้อมูลการซื้อขายในแท็บ Webull_Order_History")
