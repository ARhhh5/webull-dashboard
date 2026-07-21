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

def get_order_history():
    orders = []
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            gc = gspread.service_account_from_dict(cred_dict)
            sh = gc.open("หุ้นของเรา")
            worksheet = sh.worksheet("Webull_Order_History")
            records = worksheet.get_all_records()
            for r in records:
                sym = str(r.get("Symbol", "")).strip().upper()
                side = str(r.get("Side", "")).strip().upper()
                if sym and side in ["BUY", "SELL"]:
                    orders.append({
                        "Order ID": str(r.get("Order ID", "")),
                        "Time": str(r.get("Time", "")),
                        "Symbol": sym,
                        "Side": side,
                        "Qty": float(r.get("Qty", 0)),
                        "Price": float(r.get("Price", 0)),
                        "Broker": "Webull"
                    })
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลประวัติออเดอร์: {e}")
    return pd.DataFrame(orders)

def calculate_closed_trades(df_orders):
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
            time_str = row["Time"]
            
            if side == "BUY":
                buy_queue.append({"qty": qty, "price": price, "time": time_str})
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
                        "Realized PnL ($)": pnl,
                        "Close Time": time_str
                    })
                    
                    sell_qty_left -= matched_qty
                    first_buy["qty"] -= matched_qty
                    
                    if first_buy["qty"] <= 0:
                        buy_queue.pop(0)
                        
    return pd.DataFrame(closed_trades)

# ฟังก์ชันไฮไลต์สีตัวเลข (เขียว/แดง)
def color_pnl(val):
    if pd.isna(val):
        return ''
    color = '#00c853' if val > 0 else ('#ff3d00' if val < 0 else '#848e9c')
    return f'color: {color}; font-weight: bold;'

with st.spinner("⏳ กำลังประมวลผลประวัติการเทรด..."):
    df_raw = get_order_history()
    
    if not df_raw.empty:
        df_closed = calculate_closed_trades(df_raw)
        
        tab1, tab2 = st.tabs(["📊 สรุปภาพรวมหุ้นที่ปิดขายแล้ว (Realized PnL)", "📜 ประวัติออเดอร์สั่งซื้อทั้งหมด (Buy / Sell Logs)"])
        
        with tab1:
            if not df_closed.empty:
                total_realized_pnl = df_closed["Realized PnL ($)"].sum()
                
                df_closed["Total_Buy_Cost"] = df_closed["Qty"] * df_closed["Buy Price"]
                df_closed["Total_Sell_Rev"] = df_closed["Qty"] * df_closed["Sell Price"]
                
                df_grouped = df_closed.groupby(["Symbol", "Broker"]).agg(
                    Total_Qty=("Qty", "sum"),
                    Total_Buy_Cost=("Total_Buy_Cost", "sum"),
                    Total_Sell_Rev=("Total_Sell_Rev", "sum"),
                    Total_PnL=("Realized PnL ($)", "sum")
                ).reset_index()
                
                df_grouped["Avg Buy Price"] = df_grouped["Total_Buy_Cost"] / df_grouped["Total_Qty"]
                df_grouped["Avg Sell Price"] = df_grouped["Total_Sell_Rev"] / df_grouped["Total_Qty"]
                df_grouped["Return (%)"] = (df_grouped["Total_PnL"] / df_grouped["Total_Buy_Cost"]) * 100
                
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
                st.info("ยังไม่มีรายการปิดขายหุ้น (Closed Trades)")
                
        with tab2:
            st.markdown("### ประวัติออเดอร์ทั้งหมดจาก Google Sheet")
            df_raw_display = df_raw.sort_values(by="Time", ascending=False).copy()
            st.dataframe(
                df_raw_display.style.format({
                    "Qty": "{:,.2f}",
                    "Price": "${:,.2f}"
                }),
                use_container_width=True
            )
    else:
        st.info("ไม่พบข้อมูลประวัติการเทรดใน Google Sheet")
