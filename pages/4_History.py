import streamlit as st
import pandas as pd
import json
import base64
import gspread

st.set_page_config(page_title="Trade History & Closed Positions", layout="wide")

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

st.title("📜 ประวัติการเทรด & สรุปผลกำไร/ขาดทุนสะสม (Realized PnL)")
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

def load_all_history_sheets():
    gc = init_gsheet()
    if not gc:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    df_webull_orders = pd.DataFrame()
    df_dime_closed = pd.DataFrame()
    df_dime_us_port = pd.DataFrame()
    df_dime_th_port = pd.DataFrame()
    
    try:
        sh = gc.open("หุ้นของเรา")
        
        # 1. Webull Order History
        try:
            ws1 = sh.worksheet("Webull_Order_History")
            df_webull_orders = pd.DataFrame(ws1.get_all_records())
        except: pass
        
        # 2. Dime Closed Orders
        try:
            ws2 = sh.worksheet("Dime_Closed_Orders")
            df_dime_closed = pd.DataFrame(ws2.get_all_records())
        except: pass
        
        # 3. Dime US Portfolio
        try:
            ws3 = sh.worksheet("Dime_Portfolio")
            df_dime_us_port = pd.DataFrame(ws3.get_all_records())
        except: pass
        
        # 4. Dime TH Portfolio
        try:
            ws4 = sh.worksheet("Dime_TH_Portfolio")
            df_dime_th_port = pd.DataFrame(ws4.get_all_records())
        except: pass

    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูลจาก Google Sheet: {e}")

    return df_webull_orders, df_dime_closed, df_dime_us_port, df_dime_th_port

df_webull, df_dime_closed, df_dime_us, df_dime_th = load_all_history_sheets()

tab_closed_summary, tab_raw_logs = st.tabs([
    "🎯 1. สรุปผลกำไร/ขาดทุนหุ้นที่เคยขาย (Realized PnL)", 
    "📜 2. ประวัติคำสั่งซื้อขายแยกตาม Sheet"
])

# ==========================================
# แถบที่ 1: สรุป PnL หุ้นที่มีการขายปิดไม้ (รวม ULTY & หุ้นที่ขายขาดทุน)
# ==========================================
with tab_closed_summary:
    st.markdown("### 📊 สรุปผลกำไร/ขาดทุนจริงสะสมจากการขายหุ้น (Realized PnL)")
    
    closed_summary = []
    
    # คำนวณ FIFO PnL แบบรองรับการขายขาดทุนและการรวมหุ้น (Reverse Split)
    if not df_webull.empty:
        df_w = df_webull.copy()
        df_w.columns = [str(c).strip() for c in df_w.columns]
        
        sym_c = next((c for c in df_w.columns if 'symbol' in str(c).lower() or 'ticker' in str(c).lower()), 'Symbol')
        side_c = next((c for c in df_w.columns if 'side' in str(c).lower() or 'buy/sell' in str(c).lower()), 'Side')
        qty_c = next((c for c in df_w.columns if 'qty' in str(c).lower() or 'volume' in str(c).lower()), 'Qty')
        price_c = next((c for c in df_w.columns if 'price' in str(c).lower()), 'Price')
        time_c = next((c for c in df_w.columns if 'time' in str(c).lower() or 'date' in str(c).lower()), 'Time')
        
        if all(c in df_w.columns for c in [sym_c, side_c, qty_c, price_c]):
            df_w['Time_Sort'] = pd.to_datetime(df_w[time_c], errors='coerce')
            df_w = df_w.sort_values(by='Time_Sort', na_position='first')
            
            for symbol, group in df_w.groupby(sym_c):
                symbol_clean = str(symbol).strip().upper()
                if not symbol_clean: continue
                
                buy_queue = []
                total_realized_pnl = 0.0
                total_matched_qty = 0.0
                total_buy_cost = 0.0
                total_sell_rev = 0.0
                last_known_buy_price = 0.0
                
                for _, row in group.iterrows():
                    side = str(row[side_c]).upper().strip()
                    try:
                        qty = float(str(row[qty_c]).replace(",", ""))
                        price = float(str(row[price_c]).replace(",", ""))
                    except: continue
                    
                    if qty <= 0 or price <= 0: continue
                    
                    if "BUY" in side:
                        buy_queue.append({'qty': qty, 'price': price})
                        last_known_buy_price = price
                    elif "SELL" in side:
                        sell_qty_left = qty
                        while sell_qty_left > 0 and buy_queue:
                            b = buy_queue[0]
                            matched_qty = min(sell_qty_left, b['qty'])
                            
                            pnl = matched_qty * (price - b['price'])
                            total_realized_pnl += pnl
                            total_matched_qty += matched_qty
                            total_buy_cost += (matched_qty * b['price'])
                            total_sell_rev += (matched_qty * price)
                            
                            sell_qty_left -= matched_qty
                            b['qty'] -= matched_qty
                            if b['qty'] <= 0:
                                buy_queue.pop(0)
                        
                        # หากกรณีมีรายการ SELL แต่ buy_queue หมดแล้ว (เช่น ผลจากการรวมหุ้น)
                        if sell_qty_left > 0 and last_known_buy_price > 0:
                            pnl = sell_qty_left * (price - last_known_buy_price)
                            total_realized_pnl += pnl
                            total_matched_qty += sell_qty_left
                            total_buy_cost += (sell_qty_left * last_known_buy_price)
                            total_sell_rev += (sell_qty_left * price)
                            sell_qty_left = 0
                                
                if total_matched_qty > 0:
                    avg_buy = total_buy_cost / total_matched_qty if total_matched_qty > 0 else 0
                    avg_sell = total_sell_rev / total_matched_qty if total_matched_qty > 0 else 0
                    ret_pct = (total_realized_pnl / total_buy_cost * 100) if total_buy_cost > 0 else 0.0
                    
                    closed_summary.append({
                        "ชื่อหุ้น": symbol_clean,
                        "โบรกเกอร์": "Webull",
                        "จำนวนหุ้นที่ปิดขาย": total_matched_qty,
                        "ราคาซื้อเฉลี่ย": avg_buy,
                        "ราคาขายเฉลี่ย": avg_sell,
                        "กำไร/ขาดทุนสุทธิ ($)": total_realized_pnl,
                        "ผลตอบแทน (%)": ret_pct
                    })

    # ดึงข้อมูลจาก Dime_Closed_Orders เพิ่มเติม (ถ้ามี)
    if not df_dime_closed.empty:
        df_dc = df_dime_closed.copy()
        df_dc.columns = [str(c).strip() for c in df_dc.columns]
        for _, r in df_dc.iterrows():
            sym = str(r.get('หุ้น (Ticker)') or r.get('Ticker') or r.get('Symbol', '')).strip().upper()
            try:
                qty = float(str(r.get('จำนวนหุ้น (Qty)') or r.get('Qty', 0)).replace(",", ""))
                buy_p = float(str(r.get('ราคาซื้อเฉลี่ย (Buy Price)') or r.get('Buy Price', 0)).replace(",", ""))
                sell_p = float(str(r.get('ราคาขายจริง (Sell Price)') or r.get('Sell Price', 0)).replace(",", ""))
            except: continue
            
            if sym and qty > 0 and buy_p > 0 and sell_p > 0:
                pnl = qty * (sell_p - buy_p)
                ret_pct = ((sell_p - buy_p) / buy_p * 100)
                closed_summary.append({
                    "ชื่อหุ้น": sym,
                    "โบรกเกอร์": "Dime",
                    "จำนวนหุ้นที่ปิดขาย": qty,
                    "ราคาซื้อเฉลี่ย": buy_p,
                    "ราคาขายเฉลี่ย": sell_p,
                    "กำไร/ขาดทุนสุทธิ ($)": pnl,
                    "ผลตอบแทน (%)": ret_pct
                })

    if closed_summary:
        df_closed_res = pd.DataFrame(closed_summary)
        
        # รวมกลุ่มกรณีหุ้นชื่อซ้ำกัน
        df_grouped = df_closed_res.groupby("ชื่อหุ้น").agg({
            "โบรกเกอร์": "first",
            "จำนวนหุ้นที่ปิดขาย": "sum",
            "ราคาซื้อเฉลี่ย": "mean",
            "ราคาขายเฉลี่ย": "mean",
            "กำไร/ขาดทุนสุทธิ ($)": "sum",
            "ผลตอบแทน (%)": "mean"
        }).reset_index().sort_values(by="กำไร/ขาดทุนสุทธิ ($)", ascending=True)
        
        total_pnl = df_grouped["กำไร/ขาดทุนสุทธิ ($)"].sum()
        pnl_class = "pnl-positive" if total_pnl >= 0 else "pnl-negative"
        pnl_prefix = "+" if total_pnl >= 0 else ""
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="metric-container"><div class="metric-label">💰 กำไร/ขาดทุนสะสมรวมทั้งหมด (Realized PnL)</div><div class="metric-value {pnl_class}">{pnl_prefix}${total_pnl:,.2f}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-container"><div class="metric-label">🎯 จำนวนหุ้นทั้งหมดที่มีประวัติปิดขาย</div><div class="metric-value">{len(df_grouped)} ตัว</div></div>', unsafe_allow_html=True)
            
        st.markdown("---")
        
        def color_pnl(val):
            if isinstance(val, (int, float)):
                color = '#00c853' if val > 0 else ('#ff3d00' if val < 0 else '#848e9c')
                return f'color: {color}; font-weight: bold;'
            return ''

        st.dataframe(
            df_grouped.style.map(color_pnl, subset=["กำไร/ขาดทุนสุทธิ ($)", "ผลตอบแทน (%)"])
            .format({
                "จำนวนหุ้นที่ปิดขาย": "{:,.2f}",
                "ราคาซื้อเฉลี่ย": "${:,.2f}",
                "ราคาขายเฉลี่ย": "${:,.2f}",
                "กำไร/ขาดทุนสุทธิ ($)": "${:,.2f}",
                "ผลตอบแทน (%)": "{:+.2f}%"
            }),
            use_container_width=True
        )
    else:
        st.info("💡 ยังไม่พบประวัติรายการปิดขายหุ้นใน Google Sheet")

# ==========================================
# แถบที่ 2: แสดงข้อมูลดิบจาก 4 Sheets
# ==========================================
with tab_raw_logs:
    sub1, sub2, sub3, sub4 = st.tabs([
        "1. Webull_Order_History", 
        "2. Dime_Closed_Orders", 
        "3. Dime_Portfolio (US)", 
        "4. Dime_TH_Portfolio (TH)"
    ])
    
    with sub1:
        st.subheader("📋 1. Webull_Order_History (อัปเดตออโต้ + ข้อมูลเก่า)")
        if not df_webull.empty:
            st.dataframe(df_webull, use_container_width=True)
        else:
            st.info("ไม่พบข้อมูลในชีท Webull_Order_History")
            
    with sub2:
        st.subheader("📝 2. Dime_Closed_Orders (ประวัติขายของ Dime)")
        if not df_dime_closed.empty:
            st.dataframe(df_dime_closed, use_container_width=True)
        else:
            st.warning("ยังไม่มีข้อมูลบันทึกในชีท Dime_Closed_Orders")
            
    with sub3:
        st.subheader("🇺🇸 3. Dime_Portfolio (หุ้น US ปัจจุบัน)")
        if not df_dime_us.empty:
            st.dataframe(df_dime_us, use_container_width=True)
        else:
            st.info("ไม่พบข้อมูลในชีท Dime_Portfolio")
            
    with sub4:
        st.subheader("🇹🇭 4. Dime_TH_Portfolio (หุ้นไทยปัจจุบัน)")
        if not df_dime_th.empty:
            st.dataframe(df_dime_th, use_container_width=True)
        else:
            st.info("ไม่พบข้อมูลในชีท Dime_TH_Portfolio")
