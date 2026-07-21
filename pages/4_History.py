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
        
        df_closed = pd.DataFrame()
        df_order = pd.DataFrame()
        
        # ค้นหาชีท Closed Trades / Closed Orders / History แบบกวาดทุกชื่อที่เป็นไปได้
        for ws_name in worksheet_list:
            lower_name = ws_name.lower()
            if any(k in lower_name for k in ["closed", "history", "order"]):
                try:
                    temp_df = pd.DataFrame(sh.worksheet(ws_name).get_all_records())
                    if not temp_df.empty:
                        if any(k in lower_name for k in ["closed", "history"]):
                            if df_closed.empty:
                                df_closed = temp_df
                        if any(k in lower_name for k in ["order", "history"]):
                            if df_order.empty:
                                df_order = temp_df
                except:
                    pass
                    
        # ถ้ายังหาไม่เจอ ลองดึงชีทแรกๆ มาสำรอง
        if df_closed.empty and len(worksheet_list) > 0:
            for ws_name in worksheet_list:
                try:
                    temp_df = pd.DataFrame(sh.worksheet(ws_name).get_all_records())
                    if not temp_df.empty:
                        df_closed = temp_df
                        break
                except:
                    pass

        if df_order.empty and len(worksheet_list) > 1:
            for ws_name in worksheet_list:
                try:
                    temp_df = pd.DataFrame(sh.worksheet(ws_name).get_all_records())
                    if not temp_df.empty and ('Symbol' in temp_df.columns or 'Ticker' in temp_df.columns):
                        df_order = temp_df
                        break
                except:
                    pass
                    
        return df_closed, df_order
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

df_closed_raw, df_webull_raw = load_google_sheet_data()

tab1, tab2 = st.tabs(["🎯 สรุปหุ้นที่ปิดขายแล้ว (Closed Trades)", "📋 ประวัติออเดอร์ดิบ (Raw Orders)"])

with tab1:
    st.markdown("### สรุปผลกำไร/ขาดทุนจริง (Realized PnL)")
    
    df_use = pd.DataFrame()
    if not df_closed_raw.empty:
        df_use = df_closed_raw.copy()
    elif not df_webull_raw.empty:
        df_use = df_webull_raw.copy()
        
    if not df_use.empty:
        df_use.columns = [str(c).strip() for c in df_use.columns]
        
        col_map = {}
        for c in df_use.columns:
            cl = c.lower()
            if 'symbol' in cl or 'ticker' in cl or 'หุ้น' in cl: col_map[c] = 'Symbol'
            elif 'qty' in cl or 'volume' in cl or 'จำนวน' in cl: col_map[c] = 'Qty'
            elif 'buy' in cl or 'ต้นทุน' in cl: col_map[c] = 'Buy_Price'
            elif 'sell' in cl or 'ราคาขาย' in cl: col_map[c] = 'Sell_Price'
            elif 'price' in cl and 'Buy' not in col_map.values() and 'Sell' not in col_map.values(): col_map[c] = 'Price'
            elif 'side' in cl: col_map[c] = 'Side'
            elif 'broker' in cl or 'โบรกเกอร์' in cl: col_map[c] = 'Broker'
            
        df_use = df_use.rename(columns=col_map)
        
        if 'Side' in df_use.columns and 'Symbol' in df_use.columns and 'Price' in df_use.columns and 'Qty' in df_use.columns:
            grouped_rows = []
            for symbol, group in df_use.groupby('Symbol'):
                buys = group[group['Side'].astype(str).str.upper() == 'BUY']
                sells = group[group['Side'].astype(str).str.upper() == 'SELL']
                
                total_buy_qty = pd.to_numeric(buys['Qty'], errors='coerce').sum()
                total_sell_qty = pd.to_numeric(sells['Qty'], errors='coerce').sum()
                
                if total_buy_qty > 0 and total_sell_qty > 0:
                    avg_buy = (pd.to_numeric(buys['Price'], errors='coerce') * pd.to_numeric(buys['Qty'], errors='coerce')).sum() / total_buy_qty
                    avg_sell = (pd.to_numeric(sells['Price'], errors='coerce') * pd.to_numeric(sells['Qty'], errors='coerce')).sum() / total_sell_qty
                    
                    matched_qty = min(total_buy_qty, total_sell_qty)
                    total_pnl = (avg_sell - avg_buy) * matched_qty
                    return_pct = ((avg_sell - avg_buy) / avg_buy * 100) if avg_buy > 0 else 0
                    
                    grouped_rows.append({
                        "Symbol": symbol,
                        "Broker": "Webull",
                        "Total_Qty": matched_qty,
                        "Avg Buy Price": avg_buy,
                        "Avg Sell Price": avg_sell,
                        "Total_PnL": total_pnl,
                        "Return (%)": return_pct
                    })
            df_grouped = pd.DataFrame(grouped_rows) if len(grouped_rows) > 0 else pd.DataFrame()
        else:
            sym_c = 'Symbol' if 'Symbol' in df_use.columns else df_use.columns[0]
            qty_c = 'Qty' if 'Qty' in df_use.columns else (df_use.columns[2] if len(df_use.columns)>2 else 'Qty')
            buy_c = 'Buy_Price' if 'Buy_Price' in df_use.columns else (df_use.columns[3] if len(df_use.columns)>3 else 'Buy_Price')
            sell_c = 'Sell_Price' if 'Sell_Price' in df_use.columns else (df_use.columns[4] if len(df_use.columns)>4 else 'Sell_Price')
            
            for col in [qty_c, buy_c, sell_c]:
                if col in df_use.columns:
                    df_use[col] = pd.to_numeric(df_use[col], errors="coerce").fillna(0.0)
                    
            grouped_rows = []
            for symbol, group in df_use.groupby(sym_c):
                q = group[qty_c].sum() if qty_c in group.columns else 0
                b = group[buy_c].mean() if buy_c in group.columns else 0
                s = group[sell_c].mean() if sell_c in group.columns else 0
                pnl = (s - b) * q
                ret = ((s - b) / b * 100) if b > 0 else 0
                grouped_rows.append({
                    "Symbol": symbol,
                    "Broker": group["Broker"].iloc[0] if "Broker" in group.columns else "Webull",
                    "Total_Qty": q,
                    "Avg Buy Price": b,
                    "Avg Sell Price": s,
                    "Total_PnL": pnl,
                    "Return (%)": ret
                })
            df_grouped = pd.DataFrame(grouped_rows)
            
        if not df_grouped.empty:
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
            st.info("ยังไม่มีข้อมูลรายการปิดขายหุ้น หรือโครงสร้างตารางไม่ตรงกัน")
    else:
        st.warning("⚠️ ไม่พบข้อมูลใน Google Sheet โปรดตรวจสอบชื่อชีทและ Secrets อีกครั้ง")

with tab2:
    st.markdown("### ประวัติออเดอร์ทั้งหมดจาก Google Sheet")
    if not df_webull_raw.empty:
        st.dataframe(df_webull_raw, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลออเดอร์ดิบในระบบ")
