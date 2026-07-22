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
        
        try:
            ws1 = sh.worksheet("Webull_Order_History")
            df_webull_orders = pd.DataFrame(ws1.get_all_records())
        except: pass
        
        try:
            ws2 = sh.worksheet("Dime_Closed_Orders")
            df_dime_closed = pd.DataFrame(ws2.get_all_records())
        except: pass
        
        try:
            ws3 = sh.worksheet("Dime_Portfolio")
            df_dime_us_port = pd.DataFrame(ws3.get_all_records())
        except: pass
        
        try:
            ws4 = sh.worksheet("Dime_TH_Portfolio")
            df_dime_th_port = pd.DataFrame(ws4.get_all_records())
        except: pass

    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูลจาก Google Sheet: {e}")

    return df_webull_orders, df_dime_closed, df_dime_us_port, df_dime_th_port

df_webull, df_dime_closed, df_dime_us, df_dime_th = load_all_history_sheets()

tab_net_pnl, tab_closed_summary, tab_raw_logs = st.tabs([
    "⚖️ 1. ผลประกอบการสุทธิของแท้ (True Net PnL)", 
    "🎯 2. สรุปเฉพาะไม้ที่ปิดขายไปแล้ว (Realized PnL)", 
    "📜 3. ประวัติคำสั่งซื้อขายแยกตาม Sheet"
])

# ----------------------------------------------------
# คำนวณ FIFO PnL สรุปผล Realized PnL
# ----------------------------------------------------
realized_pnl_map = {}
closed_summary = []

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
                
                realized_pnl_map[symbol_clean] = total_realized_pnl
                closed_summary.append({
                    "ชื่อหุ้น": symbol_clean,
                    "โบรกเกอร์": "Webull",
                    "จำนวนหุ้นที่ปิดขาย": total_matched_qty,
                    "ราคาซื้อเฉลี่ย": avg_buy,
                    "ราคาขายเฉลี่ย": avg_sell,
                    "กำไร/ขาดทุนสุทธิ ($)": total_realized_pnl,
                    "ผลตอบแทน (%)": ret_pct
                })

# ==========================================
# แท็บที่ 1: True Net PnL (รวม Realized + Unrealized)
# ==========================================
with tab_net_pnl:
    st.markdown("### ⚖️ สรุปผลประกอบการที่แท้จริง (True Net PnL)")
    st.caption("นำ 'กำไร/ขาดทุนสะสมที่ขายไปแล้ว' รวมกับ 'สถานะติดดอย/กำไรของหุ้นที่ถือปัจจุบัน' เพื่อหาตัวเลขจริง")
    
    net_pnl_list = []
    
    # 1. หุ้นที่เคยขายปิดไม้ไปแล้ว
    for sym, r_pnl in realized_pnl_map.items():
        net_pnl_list.append({
            "Symbol": sym,
            "Realized PnL ($)": r_pnl,
            "Unrealized PnL ($)": 0.0,
            "True Net PnL ($)": r_pnl
        })
        
    # 2. หุ้นที่ถือค้างใน Dime US
    if not df_dime_us.empty:
        df_du = df_dime_us.copy()
        df_du.columns = [str(c).strip() for c in df_du.columns]
        sym_col = next((c for c in df_du.columns if 'ticker' in str(c).lower() or 'หุ้น' in str(c).lower()), None)
        qty_col = next((c for c in df_du.columns if 'volume' in str(c).lower() or 'จำนวน' in str(c).lower()), None)
        cost_col = next((c for c in df_du.columns if 'cost' in str(c).lower() or 'ต้นทุน' in str(c).lower()), None)
        
        if sym_col and qty_col and cost_col:
            for _, r in df_du.iterrows():
                sym = str(r[sym_col]).strip().upper()
                try:
                    qty = float(str(r[qty_col]).replace(",", ""))
                    cost = float(str(r[cost_col]).replace(",", ""))
                except: continue
                
                if sym and qty > 0:
                    try:
                        ticker_data = yf.Ticker(sym)
                        cur_p = ticker_data.fast_info.get('last_price') or cost
                    except:
                        cur_p = cost
                    
                    unrealized = qty * (cur_p - cost)
                    
                    # เช็คว่ามีใน net_pnl_list หรือยัง
                    existing = next((item for item in net_pnl_list if item["Symbol"] == sym), None)
                    if existing:
                        existing["Unrealized PnL ($)"] += unrealized
                        existing["True Net PnL ($)"] = existing["Realized PnL ($)"] + existing["Unrealized PnL ($)"]
                    else:
                        net_pnl_list.append({
                            "Symbol": sym,
                            "Realized PnL ($)": 0.0,
                            "Unrealized PnL ($)": unrealized,
                            "True Net PnL ($)": unrealized
                        })

    if net_pnl_list:
        df_net = pd.DataFrame(net_pnl_list)
        
        grand_realized = df_net["Realized PnL ($)"].sum()
        grand_unrealized = df_net["Unrealized PnL ($)"].sum()
        grand_total_net = df_net["True Net PnL ($)"].sum()
        
        r_class = "pnl-positive" if grand_realized >= 0 else "pnl-negative"
        u_class = "pnl-positive" if grand_unrealized >= 0 else "pnl-negative"
        net_class = "pnl-positive" if grand_total_net >= 0 else "pnl-negative"
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="metric-container"><div class="metric-label">💰 กำไร/ขาดทุนจริง (ขายแล้ว)</div><div class="metric-value {r_class}">${grand_realized:,.2f}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-container"><div class="metric-label">📉 สถานะค้างพอร์ต (Unrealized)</div><div class="metric-value {u_class}">${grand_unrealized:,.2f}</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-container"><div class="metric-label">⚖️ ผลประกอบการสุทธิรวมทุกตัว</div><div class="metric-value {net_class}">${grand_total_net:,.2f}</div></div>', unsafe_allow_html=True)
            
        st.markdown("---")
        
        def color_pnl(val):
            if isinstance(val, (int, float)):
                color = '#00c853' if val > 0 else ('#ff3d00' if val < 0 else '#848e9c')
                return f'color: {color}; font-weight: bold;'
            return ''

        df_show = df_net.sort_values(by="True Net PnL ($)", ascending=True)
        st.dataframe(
            df_show.style.map(color_pnl, subset=["Realized PnL ($)", "Unrealized PnL ($)", "True Net PnL ($)"])
            .format({
                "Realized PnL ($)": "${:,.2f}",
                "Unrealized PnL ($)": "${:,.2f}",
                "True Net PnL ($)": "${:,.2f}"
            }),
            use_container_width=True
        )
    else:
        st.info("ไม่พบข้อมูลคำนวณ True Net PnL")

# ==========================================
# แท็บที่ 2: สรุป Realized PnL
# ==========================================
with tab_closed_summary:
    st.markdown("### 🎯 สรุปผลกำไร/ขาดทุนเฉพาะหุ้นที่ปิดขายแล้ว (Realized PnL)")
    if closed_summary:
        df_closed_res = pd.DataFrame(closed_summary)
        st.dataframe(
            df_closed_res.style.map(color_pnl, subset=["กำไร/ขาดทุนสุทธิ ($)", "ผลตอบแทน (%)"])
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
        st.info("ยังไม่มีข้อมูลรายการปิดขาย")

# ==========================================
# แท็บที่ 3: Raw Logs
# ==========================================
with tab_raw_logs:
    s1, s2 = st.tabs(["1. Webull Order History", "2. Dime Portfolio"])
    with s1:
        if not df_webull.empty: st.dataframe(df_webull, use_container_width=True)
    with s2:
        if not df_dime_us.empty: st.dataframe(df_dime_us, use_container_width=True)
