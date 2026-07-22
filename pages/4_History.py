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
    except Exception:
        return None

def load_all_sheets():
    gc = init_gsheet()
    if not gc:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    df_webull, df_dime_us, df_dime_th = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        sh = gc.open("หุ้นของเรา")
        try:
            ws1 = sh.worksheet("Webull_Order_History")
            df_webull = pd.DataFrame(ws1.get_all_records())
        except Exception: pass
        try:
            ws2 = sh.worksheet("Dime_Portfolio")
            df_dime_us = pd.DataFrame(ws2.get_all_records())
        except Exception: pass
        try:
            ws3 = sh.worksheet("Dime_TH_Portfolio")
            df_dime_th = pd.DataFrame(ws3.get_all_records())
        except Exception: pass
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูล Google Sheet: {e}")
        
    return df_webull, df_dime_us, df_dime_th

df_webull, df_dime_us, df_dime_th = load_all_sheets()

tab_net, tab_closed, tab_raw = st.tabs([
    "⚖️ 1. ผลประกอบการสุทธิของแท้ (True Net PnL)", 
    "🎯 2. สรุปเฉพาะไม้ที่ปิดขายไปแล้ว (Realized PnL)", 
    "📜 3. ประวัติคำสั่งซื้อขายทั้งหมด"
])

def color_pnl(val):
    if isinstance(val, (int, float)):
        color = '#00c853' if val > 0 else ('#ff3d00' if val < 0 else '#848e9c')
        return f'color: {color}; font-weight: bold;'
    return ''

# ----------------------------------------------------
# คำนวณ Realized PnL จาก Webull Order History
# ----------------------------------------------------
realized_summary = []
realized_pnl_map = {}

if not df_webull.empty:
    df_w = df_webull.copy()
    df_w.columns = [str(c).strip() for c in df_w.columns]
    
    sym_col = next((c for c in df_w.columns if 'symbol' in c.lower() or 'ticker' in c.lower()), 'Symbol')
    side_col = next((c for c in df_w.columns if 'side' in c.lower() or 'buy/sell' in c.lower()), 'Side')
    qty_col = next((c for c in df_w.columns if 'qty' in c.lower() or 'volume' in c.lower()), 'Qty')
    price_col = next((c for c in df_w.columns if 'price' in c.lower()), 'Price')
    time_col = next((c for c in df_w.columns if 'time' in c.lower() or 'date' in c.lower()), 'Time')

    if all(c in df_w.columns for c in [sym_col, side_col, qty_col, price_col]):
        df_w['Time_Sort'] = pd.to_datetime(df_w[time_col], errors='coerce')
        df_w = df_w.sort_values(by='Time_Sort', na_position='first')

        for symbol, group in df_w.groupby(sym_col):
            sym_clean = str(symbol).strip().upper()
            if not sym_clean or sym_clean == 'NAN': continue

            total_buy_qty = 0.0
            total_buy_cost = 0.0
            total_sell_qty = 0.0
            total_sell_rev = 0.0

            for _, row in group.iterrows():
                side = str(row[side_col]).upper().strip()
                try:
                    q = float(str(row[qty_col]).replace(",", ""))
                    p = float(str(row[price_col]).replace(",", ""))
                except Value:
                    continue

                if q <= 0 or p <= 0: continue

                if "BUY" in side:
                    total_buy_qty += q
                    total_buy_cost += (q * p)
                elif "SELL" in side:
                    total_sell_qty += q
                    total_sell_rev += (q * p)

            # คำนวณเมื่อมีการขายออก
            if total_sell_qty > 0:
                avg_sell = total_sell_rev / total_sell_qty
                
                # ป้องกันกรณี Reverse Split หรือข้อมูล Qty ฝั่ง Buy น้อยกว่า Sell
                # โดยใช้ Cost per Share จากฝั่ง Buy ล่าสุดหรือเฉลี่ย
                avg_buy = (total_buy_cost / total_buy_qty) if total_buy_qty > 0 else avg_sell
                
                # Cost เท่ากับปริมาณหุ้นที่ขาย x ราคาซื้อเฉลี่ย
                matched_cost = total_sell_qty * avg_buy
                pnl = total_sell_rev - matched_cost
                ret_pct = (pnl / matched_cost * 100) if matched_cost > 0 else 0.0

                realized_pnl_map[sym_clean] = pnl
                realized_summary.append({
                    "ชื่อหุ้น": sym_clean,
                    "โบรกเกอร์": "Webull",
                    "จำนวนหุ้นที่ปิดขาย": total_sell_qty,
                    "ราคาซื้อเฉลี่ย": avg_buy,
                    "ราคาขายเฉลี่ย": avg_sell,
                    "กำไร/ขาดทุนสะสม ($)": pnl,
                    "ผลตอบแทน (%)": ret_pct
                })

# ==========================================
# แท็บที่ 1: True Net PnL
# ==========================================
with tab_net:
    st.markdown("### ⚖️ สรุปผลประกอบการที่แท้จริง (True Net PnL)")
    st.caption("คำนวณจาก (กำไรที่ขายไปแล้ว Realized PnL) + (กำไร/ขาดทุนของหุ้นที่ยังถืออยู่ Unrealized PnL)")

    net_list = []

    # 1. หุ้นที่เคยปิดขายไปแล้ว
    for sym, r_pnl in realized_pnl_map.items():
        net_list.append({
            "ชื่อหุ้น": sym,
            "กำไรอดีต (ปิดแล้ว)": r_pnl,
            "สถานะปัจจุบัน (ติดดอย/กำไร)": 0.0,
            "สุทธิของแท้ (Net PnL)": r_pnl
        })

    # 2. หุ้นที่ถือใน Dime US
    if not df_dime_us.empty:
        df_du = df_dime_us.copy()
        df_du.columns = [str(c).strip() for c in df_du.columns]
        s_col = next((c for c in df_du.columns if 'ticker' in c.lower() or 'หุ้น' in c.lower()), None)
        q_col = next((c for c in df_du.columns if 'volume' in c.lower() or 'จำนวน' in c.lower()), None)
        c_col = next((c for c in df_du.columns if 'cost' in c.lower() or 'ต้นทุน' in c.lower()), None)

        if s_col and q_col and c_col:
            for _, r in df_du.iterrows():
                sym = str(r[s_col]).strip().upper()
                try:
                    q = float(str(r[q_col]).replace(",", ""))
                    cost = float(str(r[c_col]).replace(",", ""))
                except Exception: continue

                if sym and q > 0:
                    try:
                        cur_p = yf.Ticker(sym).fast_info.get('last_price') or cost
                    except Exception:
                        cur_p = cost

                    unrealized = q * (cur_p - cost)

                    existing = next((item for item in net_list if item["ชื่อหุ้น"] == sym), None)
                    if existing:
                        existing["สถานะปัจจุบัน (ติดดอย/กำไร)"] += unrealized
                        existing["สุทธิของแท้ (Net PnL)"] = existing["กำไรอดีต (ปิดแล้ว)"] + existing["สถานะปัจจุบัน (ติดดอย/กำไร)"]
                    else:
                        net_list.append({
                            "ชื่อหุ้น": sym,
                            "กำไรอดีต (ปิดแล้ว)": 0.0,
                            "สถานะปัจจุบัน (ติดดอย/กำไร)": unrealized,
                            "สุทธิของแท้ (Net PnL)": unrealized
                        })

    if net_list:
        df_net = pd.DataFrame(net_list)

        sum_realized = df_net["กำไรอดีต (ปิดแล้ว)"].sum()
        sum_unrealized = df_net["สถานะปัจจุบัน (ติดดอย/กำไร)"].sum()
        sum_total_net = df_net["สุทธิของแท้ (Net PnL)"].sum()

        r_class = "pnl-positive" if sum_realized >= 0 else "pnl-negative"
        u_class = "pnl-positive" if sum_unrealized >= 0 else "pnl-negative"
        n_class = "pnl-positive" if sum_total_net >= 0 else "pnl-negative"

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="metric-container"><div class="metric-label">💰 กำไร/ขาดทุนสะสม (ขายแล้ว)</div><div class="metric-value {r_class}">${sum_realized:,.2f}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-container"><div class="metric-label">📉 สถานะค้างพอร์ต (Unrealized)</div><div class="metric-value {u_class}">${sum_unrealized:,.2f}</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-container"><div class="metric-label">⚖️ ผลประกอบการสุทธิรวมทุกตัว</div><div class="metric-value {n_class}">${sum_total_net:,.2f}</div></div>', unsafe_allow_html=True)

        st.markdown("---")

        df_show = df_net.sort_values(by="สุทธิของแท้ (Net PnL)", ascending=True)
        st.dataframe(
            df_show.style.map(color_pnl, subset=["กำไรอดีต (ปิดแล้ว)", "สถานะปัจจุบัน (ติดดอย/กำไร)", "สุทธิของแท้ (Net PnL)"])
            .format({
                "กำไรอดีต (ปิดแล้ว)": "${:,.2f}",
                "สถานะปัจจุบัน (ติดดอย/กำไร)": "${:,.2f}",
                "สุทธิของแท้ (Net PnL)": "${:,.2f}"
            }),
            use_container_width=True
        )
    else:
        st.info("ยังไม่มีข้อมูลคำนวณ Net PnL")

# ==========================================
# แท็บที่ 2: สรุปเฉพาะไม้ที่ปิดขายแล้ว
# ==========================================
with tab_closed:
    st.markdown("### 🎯 สรุปผลกำไร/ขาดทุนเฉพาะหุ้นที่ปิดขายแล้ว (Realized PnL)")
    if realized_summary:
        df_res = pd.DataFrame(realized_summary)
        df_res = df_res.sort_values(by="กำไร/ขาดทุนสะสม ($)", ascending=True)
        st.dataframe(
            df_res.style.map(color_pnl, subset=["กำไร/ขาดทุนสะสม ($)", "ผลตอบแทน (%)"])
            .format({
                "จำนวนหุ้นที่ปิดขาย": "{:,.2f}",
                "ราคาซื้อเฉลี่ย": "${:,.2f}",
                "ราคาขายเฉลี่ย": "${:,.2f}",
                "กำไร/ขาดทุนสะสม ($)": "${:,.2f}",
                "ผลตอบแทน (%)": "{:+.2f}%"
            }),
            use_container_width=True
        )
    else:
        st.info("ยังไม่มีรายการขายปิดไม้")

# ==========================================
# แท็บที่ 3: Raw Order History
# ==========================================
with tab_raw:
    if not df_webull.empty:
        st.dataframe(df_webull, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูล Order History ใน Google Sheet")
