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
        if not cred_base64: return None
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        return gc
    except Exception as e:
        return None

def load_google_sheet_data():
    gc = init_gsheet()
    if not gc:
        return pd.DataFrame(), pd.DataFrame()
    try:
        sh = gc.open("Webull_Portfolio")
        worksheet_list = [ws.title for ws in sh.worksheets()]
        
        df_order = pd.DataFrame()
        df_dime_closed = pd.DataFrame()
        
        # 1. โหลด Webull Order History
        for name in ["Webull_Order_History", "Order History", "Webull_Orders"]:
            if name in worksheet_list:
                try:
                    df_order = pd.DataFrame(sh.worksheet(name).get_all_records())
                    if not df_order.empty: break
                except: pass
        if df_order.empty and len(worksheet_list) > 0:
            for ws_name in worksheet_list:
                try:
                    temp = pd.DataFrame(sh.worksheet(ws_name).get_all_records())
                    if 'Symbol' in temp.columns or 'Ticker' in temp.columns:
                        df_order = temp
                        break
                except: pass

        # 2. โหลด Dime Closed Orders
        for name in ["Dime_Closed_Orders", "Closed_Orders", "Dime Closed"]:
            if name in worksheet_list:
                try:
                    df_dime_closed = pd.DataFrame(sh.worksheet(name).get_all_records())
                    if not df_dime_closed.empty: break
                except: pass
                
        return df_order, df_dime_closed
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

df_webull_raw, df_dime_closed_raw = load_google_sheet_data()

tab1, tab2 = st.tabs(["🎯 สรุปหุ้นที่ปิดขายแล้ว (Closed Trades)", "📋 ประวัติออเดอร์ดิบ (Raw Orders & Dime)"])

with tab1:
    st.markdown("### สรุปผลกำไร/ขาดทุนจริง (Realized PnL)")
    
    realized_trades = []
    
    # 1. คำนวณจาก Webull Order History ด้วยระบบ FIFO (จับคู่ซื้อ-ขายตามเวลาจริง)
    if not df_webull_raw.empty:
        df_w = df_webull_raw.copy()
        df_w.columns = [str(c).strip() for c in df_w.columns]
        
        # Standardize columns
        sym_col = next((c for c in df_w.columns if 'symbol' in c.lower() or 'ticker' in c.lower()), 'Symbol')
        side_col = next((c for c in df_w.columns if 'side' in c.lower()), 'Side')
        qty_col = next((c for c in df_w.columns if 'qty' in c.lower() or 'volume' in c.lower()), 'Qty')
        price_col = next((c for c in df_w.columns if 'price' in c.lower()), 'Price')
        time_col = next((c for c in df_w.columns if 'time' in c.lower() or 'date' in c.lower()), 'Time')
        
        if all(c in df_w.columns for c in [sym_col, side_col, qty_col, price_col]):
            df_w['Time_Sort'] = pd.to_datetime(df_w[time_col], errors='coerce')
            df_w = df_w.sort_values(by='Time_Sort', na_position='last')
            
            for symbol, group in df_w.groupby(sym_col):
                buy_queue = []
                for _, row in group.iterrows():
                    side = str(row[side_col]).upper().strip()
                    qty = pd.to_numeric(row[qty_col], errors='coerce')
                    price = pd.to_numeric(row[price_col], errors='coerce')
                    
                    if pd.isna(qty) or pd.isna(price) or qty <= 0: continue
                    
                    if 'BUY' in side:
                        buy_queue.append({'qty': qty, 'price': price})
                    elif 'SELL' in side:
                        sell_qty = qty
                        while sell_qty > 0 and len(buy_queue) > 0:
                            b = buy_queue[0]
                            matched_qty = min(sell_qty, b['qty'])
                            # คำนวณ PnL (ขาย - ซื้อ) * จำนวน -> ขายต่ำกว่าทุน ติดลบแดงแจ๋แน่นอน
                            pnl = (price - b['price']) * matched_qty
                            return_pct = ((price - b['price']) / b['price'] * 100) if b['price'] > 0 else 0
                            
                            realized_trades.append({
                                "Symbol": symbol,
                                "Broker": "Webull",
                                "Total_Qty": matched_qty,
                                "Avg Buy Price": b['price'],
                                "Avg Sell Price": price,
                                "Total_PnL": pnl,
                                "Return (%)": return_pct
                            })
                            
                            b['qty'] -= matched_qty
                            sell_qty -= matched_qty
                            if b['qty'] <= 0:
                                buy_queue.pop(0)

    # 2. นำข้อมูลจาก Dime Closed Orders (ถ้ามีบันทึกเข้ามา)
    if not df_dime_closed_raw.empty:
        df_d = df_dime_closed_raw.copy()
        df_d.columns = [str(c).strip() for c in df_d.columns]
        for _, row in df_d.iterrows():
            symbol = row.get('หุ้น (Ticker)') or row.get('Ticker') or row.get('Symbol', 'UNKNOWN')
            qty = pd.to_numeric(row.get('จำนวนหุ้น (Qty)') or row.get('Qty', 0), errors='coerce')
            buy_p = pd.to_numeric(row.get('ราคาซื้อเฉลี่ย (Buy Price)') or row.get('Buy Price', 0), errors='coerce')
            sell_p = pd.to_numeric(row.get('ราคาขายจริง (Sell Price)') or row.get('Sell Price', 0), errors='coerce')
            
            if qty > 0 and buy_p > 0 and sell_p > 0:
                pnl = (sell_p - buy_p) * qty
                ret = ((sell_p - buy_p) / buy_p * 100)
                realized_trades.append({
                    "Symbol": symbol,
                    "Broker": "DIME",
                    "Total_Qty": qty,
                    "Avg Buy Price": buy_p,
                    "Avg Sell Price": sell_p,
                    "Total_PnL": pnl,
                    "Return (%)": ret
                })

    if len(realized_trades) > 0:
        df_res = pd.DataFrame(realized_trades)
        
        # จัดกลุ่มรวมตาม Symbol
        grouped_data = []
        for symbol, group in df_res.groupby("Symbol"):
            total_qty = group["Total_Qty"].sum()
            total_buy_val = (group["Avg Buy Price"] * group["Total_Qty"]).sum()
            total_sell_val = (group["Avg Sell Price"] * group["Total_Qty"]).sum()
            
            avg_buy = total_buy_val / total_qty if total_qty > 0 else 0
            avg_sell = total_sell_val / total_qty if total_qty > 0 else 0
            total_pnl = group["Total_PnL"].sum()
            return_pct = ((avg_sell - avg_buy) / avg_buy * 100) if avg_buy > 0 else 0.0
            
            grouped_data.append({
                "Symbol": symbol,
                "Broker": group["Broker"].iloc[0],
                "Total_Qty": total_qty,
                "Avg Buy Price": avg_buy,
                "Avg Sell Price": avg_sell,
                "Total_PnL": total_pnl,
                "Return (%)": return_pct
            })
            
        df_grouped = pd.DataFrame(grouped_data)
        
        # Metric รวมภาพใหญ่
        total_realized_pnl = df_grouped["Total_PnL"].sum()
        pnl_class = "pnl-positive" if total_realized_pnl >= 0 else "pnl-negative"
        pnl_prefix = "+" if total_realized_pnl >= 0 else ""
        
        st.markdown(f'''
            <div class="metric-container" style="margin-bottom: 20px;">
                <div class="metric-label">💵 กำไร/ขาดทุนสุทธิสะสมจากหุ้นที่ขายแล้ว (Realized PnL)</div>
                <div class="metric-value {pnl_class}">{pnl_prefix}${total_realized_pnl:,.2f}</div>
            </div>
        ''', unsafe_allow_html=True)
        
        st.markdown("---")
        
        df_display = df_grouped.sort_values(by="Total_PnL", ascending=False).copy()
        df_show = df_display[["Symbol", "Broker", "Total_Qty", "Avg Buy Price", "Avg Sell Price", "Total_PnL", "Return (%)"]]
        df_show.columns = ["Symbol", "Broker", "จำนวนหุ้นรวม", "ราคาซื้อเฉลี่ย", "ราคาขายเฉลี่ย", "กำไร/ขาดทุนสะสม ($)", "ผลตอบแทน (%)"]
        
        def color_pnl(val):
            color = '#00c853' if val >= 0 else '#ff3d00'
            return f'color: {color}; font-weight: bold;'
            
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
        st.info("ยังไม่มีข้อมูลรายการปิดขายหุ้นที่จับคู่ได้")

with tab2:
    st.markdown("### 📋 Webull Order History (ข้อมูลดิบอัตโนมัติ)")
    if not df_webull_raw.empty:
        st.dataframe(df_webull_raw, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลใน Webull_Order_History")
        
    st.markdown("### 📝 Dime Closed Orders (บันทึกมือ)")
    if not df_dime_closed_raw.empty:
        st.dataframe(df_dime_closed_raw, use_container_width=True)
    else:
        st.info("ตาราง Dime_Closed_Orders ยังว่างเปล่า (สามารถคีย์เพิ่มใน Google Sheet ได้ทันทีเมื่อมีการขายหุ้น Dime)")
