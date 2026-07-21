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
        
        # โหลด Closed_Trades
        try:
            worksheet_closed = sh.worksheet("Closed_Trades")
            data_closed = worksheet_closed.get_all_records()
            df_closed = pd.DataFrame(data_closed)
        except:
            df_closed = pd.DataFrame()
            
        # โหลด Order History
        try:
            worksheet_order = sh.worksheet("Webull_Order_History")
            data_order = worksheet_order.get_all_records()
            df_order = pd.DataFrame(data_order)
        except:
            df_order = pd.DataFrame()
            
        return df_closed, df_order
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

df_closed_raw, df_webull_raw = load_google_sheet_data()

tab1, tab2 = st.tabs(["🎯 สรุปหุ้นที่ปิดขายแล้ว (Closed Trades)", "📋 ประวัติออเดอร์ดิบ (Raw Orders)"])

with tab1:
    st.markdown("### สรุปผลกำไร/ขาดทุนจริง (Realized PnL)")
    
    if not df_closed_raw.empty:
        df = df_closed_raw.copy()
        
        # แปลงข้อมูลตัวเลขให้ปลอดภัย
        for col in ["Qty", "Buy_Price", "Sell_Price", "Realized_PnL"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            else:
                df[col] = 0.0
                
        # จัดกลุ่มคำนวณตาม Symbol
        grouped_data = []
        for symbol, group in df.groupby("Symbol"):
            total_qty = group["Qty"].sum()
            total_buy_val = (group["Buy_Price"] * group["Qty"]).sum()
            total_sell_val = (group["Sell_Price"] * group["Qty"]).sum()
            
            avg_buy = total_buy_val / total_qty if total_qty > 0 else 0
            avg_sell = total_sell_val / total_qty if total_qty > 0 else 0
            
            # สูตรคำนวณกำไร/ขาดทุนที่ถูกต้อง: (ราคาขาย - ราคาซื้อ) * จำนวนหุ้น
            # ถ้าขายต่ำกว่าซื้อ ตัวเลขจะติดลบอัตโนมัติอย่างถูกต้อง
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
        
        # คำนวณ Metric รวมภาพใหญ่
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
        st.info("ยังไม่มีบันทึกข้อมูลในตาราง Closed_Trades บน Google Sheet หรือข้อมูลกำลังเชื่อมต่อ")

with tab2:
    st.markdown("### ประวัติออเดอร์ทั้งหมดจาก Google Sheet")
    if not df_webull_raw.empty:
        df_raw_display = df_webull_raw.sort_values(by="Time", ascending=False).copy()
        st.dataframe(
            df_raw_display.style.format({
                "Qty": "{:,.2f}" if "Qty" in df_raw_display.columns else "{}",
                "Price": "${:,.2f}" if "Price" in df_raw_display.columns else "{}"
            }), 
            use_container_width=True
        )
    else:
        st.info("ไม่พบข้อมูลออเดอร์ดิบในระบบ")
