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
        
        # ค้นหาชีท Closed Trades แบบยืดหยุ่น
        df_closed = pd.DataFrame()
        closed_sheet_names = ["Closed_Trades", "Closed Trades", "closed_trades", "History", "Closed"]
        for name in closed_sheet_names:
            if name in worksheet_list:
                try:
                    df_closed = pd.DataFrame(sh.worksheet(name).get_all_records())
                    if not df_closed.empty:
                        break
                except:
                    pass
                    
        # ค้นหาชีท Order History แบบยืดหยุ่น
        df_order = pd.DataFrame()
        order_sheet_names = ["Webull_Order_History", "Order History", "Webull_Orders", "Orders"]
        for name in order_sheet_names:
            if name in worksheet_list:
                try:
                    df_order = pd.DataFrame(sh.worksheet(name).get_all_records())
                    if not df_order.empty:
                        break
                except:
                    pass
                    
        # ถ้าหา Order ไม่เจอ ลองดึงชีทแรกมาเผื่อไว้
        if df_order.empty and len(worksheet_list) > 0:
            for ws_name in worksheet_list:
                temp_df = pd.DataFrame(sh.worksheet(ws_name).get_all_records())
                if "Symbol" in temp_df.columns or "Ticker" in temp_df.columns:
                    df_order = temp_df
                    break
                    
        return df_closed, df_order
    except Exception as e:
        st.error(f"⚠️ เกิดข้อผิดพลาดในการเชื่อมต่อ Google Sheet: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_closed_raw, df_webull_raw = load_google_sheet_data()

tab1, tab2 = st.tabs(["🎯 สรุปหุ้นที่ปิดขายแล้ว (Closed Trades)", "📋 ประวัติออเดอร์ดิบ (Raw Orders)"])

with tab1:
    st.markdown("### สรุปผลกำไร/ขาดทุนจริง (Realized PnL)")
    
    # ถ้าชีท Closed ว่าง แต่มี Order History ให้ลองคำนวณจาก Order ดิบเบื้องต้น
    df_to_use = pd.DataFrame()
    if not df_closed_raw.empty:
        df_to_use = df_closed_raw.copy()
    elif not df_webull_raw.empty:
        # พยายามแปลงคอลัมน์มาตรฐาน
        df_temp = df_webull_raw.copy()
        # แปลงชื่อคอลัมน์ให้เป็นมาตรฐาน
        col_map = {}
        for c in df_temp.columns:
            cl = c.lower()
            if 'symbol' in cl or 'ticker' in cl: col_map[c] = 'Symbol'
            elif 'qty' in cl or 'volume' in cl or 'amount' in cl: col_map[c] = 'Qty'
            elif 'price' in cl: col_map[c] = 'Price'
            elif 'side' in cl: col_map[c] = 'Side'
        df_temp = df_temp.rename(columns=col_map)
        
        if 'Symbol' in df_temp.columns and 'Side' in df_temp.columns:
            # กรองเฉพาะฝั่งขาย หรือทำสรุปง่ายๆ ให้มีข้อมูลแสดงผลไม่โล่ง
            df_to_use = df_temp

    if not df_closed_raw.empty:
        df = df_closed_raw.copy()
        # Standardize columns
        df.columns = [str(c).strip() for c in df.columns]
        
        # ค้นหาชื่อคอลัมน์แบบยืดหยุ่น
        sym_col = next((c for c in df.columns if 'symbol' in c.lower() or 'ticker' in c.lower()), 'Symbol')
        qty_col = next((c for c in df.columns if 'qty' in c.lower() or 'volume' in c.lower() or 'จำนวน' in c), 'Qty')
        buy_col = next((c for c in df.columns if 'buy' in c.lower() or 'ต้นทุน' in c), 'Buy_Price')
        sell_col = next((c for c in df.columns if 'sell' in c.lower() or 'ราคาขาย' in c), 'Sell_Price')
        
        for col in [qty_col, buy_col, sell_col]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            else:
                df[col] = 0.0
                
        grouped_data = []
        for symbol, group in df.groupby(sym_col if sym_col in df.columns else df.columns[0]):
            total_qty = group[qty_col].sum() if qty_col in group.columns else 0
            total_buy_val = (group[buy_col] * group[qty_col]).sum() if buy_col in group.columns and qty_col in group.columns else 0
            total_sell_val = (group[sell_col] * group[qty_col]).sum() if sell_col in group.columns and qty_col in group.columns else 0
            
            avg_buy = total_buy_val / total_qty if total_qty > 0 else 0
            avg_sell = total_sell_val / total_qty if total_qty > 0 else 0
            
            total_pnl = (avg_sell - avg_buy) * total_qty
            return_pct = ((avg_sell - avg_buy) / avg_buy * 100) if avg_buy > 0 else 0.0
            
            grouped_data.append({
                "Symbol": symbol,
                "Broker": group["Broker"].iloc[0] if "Broker" in group.columns else "Webull",
                "Total_Qty": total_qty,
                "Avg Buy Price": avg_buy,
                "Avg Sell Price": avg_sell,
                "Total_PnL": total_pnl,
                "Return (%)": return_pct
            })
            
        df_grouped = pd.DataFrame(grouped_data)
        
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
        st.warning("⚠️ ไม่พบตาราง Closed_Trades บน Google Sheet แต่ระบบดึงข้อมูลออเดอร์ดิบมาแสดงด้านล่างแทนเรียบร้อยครับ")
        if not df_webull_raw.empty:
            st.dataframe(df_webull_raw, use_container_width=True)

with tab2:
    st.markdown("### ประวัติออเดอร์ทั้งหมดจาก Google Sheet")
    if not df_webull_raw.empty:
        df_raw_display = df_webull_raw.sort_values(by=df_webull_raw.columns[1], ascending=False).copy() if len(df_webull_raw.columns) > 1 else df_webull_raw.copy()
        st.dataframe(df_raw_display, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลออเดอร์ดิบในระบบ Google Sheet (โปรดตรวจสอบชื่อชีทและกุญแจเชื่อมต่ออีกครั้ง)")
