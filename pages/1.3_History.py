import os
import json
import base64
import urllib.parse
import http.client
import uuid
import hmac
import hashlib
import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timezone

# ==========================================
# 1. PAGE CONFIG & MODERN DARK CSS
# ==========================================
st.set_page_config(page_title="Trade History & Realized PnL", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    /* Minimal Header */
    .page-title-minimal {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 1.4rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.5px;
        margin-bottom: 2px;
    }
    .page-subtitle-minimal {
        color: #6b7280;
        font-size: 0.85rem;
        margin-bottom: 18px;
    }

    /* Modern Pill Action Buttons */
    div[data-testid="stColumn"] div.stButton > button {
        background-color: #0f1115 !important;
        border: 1px solid #1a1d24 !important;
        border-radius: 10px !important;
        padding: 8px 14px !important;
        color: #9ca3af !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        transition: all 0.25s ease !important;
        width: 100% !important;
    }

    div[data-testid="stColumn"] div.stButton > button:hover {
        border-color: #38bdf8 !important;
        color: #ffffff !important;
        background-color: #141822 !important;
    }

    /* Active Segmented Button Highlight */
    div[data-testid="stColumn"] div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
        border: 1px solid #38bdf8 !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(56, 189, 248, 0.25) !important;
    }

    /* Metric Cards */
    .metric-card {
        background-color: #0f1115;
        padding: 16px 20px;
        border-radius: 12px;
        border: 1px solid #1a1d24;
        text-align: center;
    }
    .metric-label {
        color: #9ca3af;
        font-size: 12px;
        font-weight: 600;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: 800;
        color: #ffffff;
        font-family: 'JetBrains Mono', monospace;
    }
    .text-green { color: #4ade80 !important; }
    .text-red { color: #f87171 !important; }
    .text-cyan { color: #38bdf8 !important; }

    /* Custom Input / Select Controls */
    div[data-baseweb="select"] > div {
        background-color: #0f1115 !important;
        border-color: #1a1d24 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Header Section
st.markdown('<div class="page-title-minimal">ประวัติการขาย & กำไร/ขาดทุนที่เกิดขึ้นจริง (Realized PnL)</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle-minimal">วิเคราะห์ผลตอบแทนจากการปิดออเดอร์ขาย ตัดคำนวณต้นทุน FIFO รายตัว</div>', unsafe_allow_html=True)

# รายชื่อหุ้นที่มี Reverse Split หรือ Corporate Actions
SPLIT_STOCKS = ["ULTY"]

# Helper color formatting
def color_pnl(val):
    if isinstance(val, (int, float)):
        color = '#4ade80' if val > 0 else ('#f87171' if val < 0 else '#9ca3af')
        return f'color: {color}; font-weight: bold;'
    return ''

# ==========================================
# 2. WEBULL API & GOOGLE SHEETS PIPELINE
# ==========================================
def get_gspread_client():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64: return None
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        return gspread.service_account_from_dict(cred_dict)
    except Exception:
        return None

def normalize_sheet_values(data, expected_cols=7):
    """ปรับขนาดความกว้างของทุกแถวให้เท่ากันเพื่อป้องกัน ValueError ใน Pandas"""
    if not data:
        return []
    normalized = []
    for row in data:
        new_row = list(row)
        if len(new_row) < expected_cols:
            new_row.extend([""] * (expected_cols - len(new_row)))
        elif len(new_row) > expected_cols:
            new_row = new_row[:expected_cols]
        normalized.append(new_row)
    return normalized

def sync_webull_to_gsheet():
    gc = get_gspread_client()
    if not gc:
        return False, "❌ ไม่สามารถเชื่อมต่อ Google Sheets API"

    try:
        sheet_title = st.secrets.get("SPREADSHEET_NAME", "หุ้นของเรา")
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            sheet_title = st.secrets["connections"]["gsheets"].get("spreadsheet", sheet_title)
            
        try:
            sh = gc.open(sheet_title)
        except Exception:
            sh = gc.open_by_key(sheet_title) if len(sheet_title) > 20 else gc.open_by_url(sheet_title)

        try:
            worksheet = sh.worksheet("Webull_Order_History")
        except Exception:
            worksheet = sh.add_worksheet(title="Webull_Order_History", rows="1000", cols="10")
            worksheet.append_row(["Order ID", "Time", "Sym", "Side", "Qty", "Pr", "สถานะหุ้น"])
    except Exception as e:
        return False, f"❌ ไม่สามารถเปิด Google Sheet ได้: {str(e)}"

    try:
        raw_vals = worksheet.get_all_values()
        if len(raw_vals) > 0:
            norm_vals = normalize_sheet_values(raw_vals, expected_cols=7)
            df_existing = pd.DataFrame(norm_vals[1:], columns=norm_vals[0]) if len(norm_vals) > 1 else pd.DataFrame()
        else:
            df_existing = pd.DataFrame()
    except Exception:
        df_existing = pd.DataFrame()

    if df_existing.empty:
        worksheet.clear()
        worksheet.append_row(["Order ID", "Time", "Sym", "Side", "Qty", "Pr", "สถานะหุ้น"])

    existing_ids = set()
    existing_combos = set()
    symbol_positions = {}

    if not df_existing.empty:
        cols = [str(c).strip() for c in df_existing.columns]
        sym_col = next((c for c in cols if 'sym' in c.lower() or 'ticker' in c.lower() or 'หุ้น' in c), cols[2] if len(cols) > 2 else 'Sym')
        side_col = next((c for c in cols if 'side' in c.lower() or 'ฝั่ง' in c), cols[3] if len(cols) > 3 else 'Side')
        qty_col = next((c for c in cols if 'qty' in c.lower() or 'volume' in c.lower() or 'จำนวน' in c), cols[4] if len(cols) > 4 else 'Qty')
        
        for _, row in df_existing.iterrows():
            oid = str(row.get("Order ID", "")).strip()
            if oid:
                existing_ids.add(oid)
            combo = f"{str(row.get('Time',''))}_{str(row.get(sym_col,''))}_{str(row.get(side_col,''))}_{str(row.get(qty_col,''))}_{str(row.get('Pr', row.get('Price','')))}"
            existing_combos.add(combo)
            
            s_name = str(row.get(sym_col, "")).strip().upper()
            s_side = str(row.get(side_col, "BUY")).strip().upper()
            try: s_qty = float(str(row.get(qty_col, 0)).replace(",", "").replace("$", ""))
            except: s_qty = 0.0
            
            if s_name:
                if "SELL" in s_side or "ขาย" in s_side:
                    symbol_positions[s_name] = symbol_positions.get(s_name, 0.0) - s_qty
                else:
                    symbol_positions[s_name] = symbol_positions.get(s_name, 0.0) + s_qty

    webull_config = st.secrets.get("Webull", {})
    APP_KEY = webull_config.get("AppKey", "").strip() or webull_config.get("app_key", "").strip()
    APP_SECRET = webull_config.get("AppSecret", "").strip() or webull_config.get("app_secret", "").strip()
    ACCOUNT_ID = webull_config.get("AccountId", "").strip() or webull_config.get("account_id", "").strip()
    HOST = "api.webull.co.th"

    if not APP_KEY or not APP_SECRET or not ACCOUNT_ID:
        return False, "❌ ไม่พบข้อมูล Webull API Key ใน Secrets"

    try:
        path = "/openapi/assets/positions"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        nonce = uuid.uuid4().hex
        
        signing_values = {
            "host": HOST,
            "x-app-key": APP_KEY,
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-nonce": nonce,
            "x-signature-version": "1.0",
            "x-timestamp": timestamp,
            "account_id": ACCOUNT_ID
        }
        string_1 = "&".join(f"{key}={signing_values[key]}" for key in sorted(signing_values))
        signature = base64.b64encode(
            hmac.new(
                f"{APP_SECRET}&".encode("utf-8"),
                urllib.parse.quote(f"{path}&{string_1}", safe="").encode("utf-8"),
                hashlib.sha1
            ).digest()
        ).decode("utf-8")

        headers = {
            "Accept": "application/json",
            "x-app-key": APP_KEY,
            "x-timestamp": timestamp,
            "x-signature-version": "1.0",
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-nonce": nonce,
            "x-version": "v2",
            "x-signature": signature,
            "x-access-token": webull_config.get("AccessToken", "").strip()
        }

        conn = http.client.HTTPSConnection(HOST)
        conn.request("GET", f"{path}?account_id={ACCOUNT_ID}", "", headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()

        orders = json.loads(data.decode("utf-8"))
        if not isinstance(orders, list):
            orders = []

    except Exception as e:
        return False, f"⚠️ ยิง Webull API ไม่สำเร็จ: {str(e)}"

    new_rows = []
    for order in orders:
        order_id = str(order.get("order_id", order.get("orderId", uuid.uuid4().hex[:8])))
        symbol = str(order.get("symbol", "")).upper()
        
        # O-Lieng Fix: Fallback for empty side from positions endpoint
        action = str(order.get("action", order.get("side", ""))).upper()
        qty = float(order.get("quantity", order.get("filledQuantity", 0)))
        
        if not action:
            action = "BUY" if qty >= 0 else "SELL"
            
        side_formatted = "BUY" if "BUY" in action else ("SELL" if "SELL" in action else action)
        
        price = float(order.get("cost_price", order.get("avgFilledPrice", 0)))
        order_time = order.get("create_time", datetime.now().strftime("%Y-%m-%d"))

        full_order_id = f"{order_id}_{symbol}_{side_formatted}"
        combo_check = f"{order_time}_{symbol}_{side_formatted}_{qty}_{price}"

        if full_order_id not in existing_ids and combo_check not in existing_combos:
            if qty > 0 and price > 0:
                current_net_qty = symbol_positions.get(symbol, 0.0)
                if "SELL" in side_formatted:
                    current_net_qty -= qty
                else:
                    current_net_qty += qty
                
                status_flag = "O" if current_net_qty > 0.0001 else "C"
                new_rows.append([full_order_id, order_time, symbol, side_formatted, qty, price, status_flag])

    if new_rows:
        try:
            # O-Lieng Fix: Bulk insert to prevent diagonal shifting bug in Google Sheets API
            worksheet.append_rows(new_rows, value_input_option='USER_ENTERED')
            return True, f"✅ Auto Sync สำเร็จ! เพิ่มรายการใหม่ลง Google Sheet {len(new_rows)} รายการ"
        except Exception as e:
            return False, f"❌ เกิดข้อผิดพลาดขณะเขียนข้อมูลลง Sheet: {str(e)}"
    else:
        return True, "ℹ️ ข้อมูลล่าสุดตรงกันแล้ว ไม่มีรายการใหม่ต้องเพิ่ม"

def load_sheet_to_df_safe(worksheet, expected_cols=7):
    """อ่าน Worksheet และทำ Normalize แถว ป้องกัน ValueError"""
    try:
        data = worksheet.get_all_values()
        if len(data) > 1:
            norm_data = normalize_sheet_values(data, expected_cols=expected_cols)
            df = pd.DataFrame(norm_data[1:], columns=norm_data[0])
            df.columns = [str(c).strip() for c in df.columns]
            return df
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=60)
def load_all_history_sheets():
    gc = get_gspread_client()
    if not gc:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    df_webull_orders = pd.DataFrame()
    df_dime_closed = pd.DataFrame()
    df_dime_us_port = pd.DataFrame()
    df_dime_th_port = pd.DataFrame()
    
    try:
        sheet_title = st.secrets.get("SPREADSHEET_NAME", "หุ้นของเรา")
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            sheet_title = st.secrets["connections"]["gsheets"].get("spreadsheet", sheet_title)

        try: sh = gc.open(sheet_title)
        except: sh = gc.open_by_key(sheet_title) if len(sheet_title) > 20 else gc.open_by_url(sheet_title)

        try: df_webull_orders = load_sheet_to_df_safe(sh.worksheet("Webull_Order_History"), expected_cols=7)
        except: pass
        try: df_dime_closed = load_sheet_to_df_safe(sh.worksheet("Dime_Closed_Orders"), expected_cols=7)
        except: pass
        try: df_dime_us_port = load_sheet_to_df_safe(sh.worksheet("Dime_Portfolio"), expected_cols=4)
        except: pass
        try: df_dime_th_port = load_sheet_to_df_safe(sh.worksheet("Dime_TH_Portfolio"), expected_cols=4)
        except: pass
    except Exception:
        pass

    return df_webull_orders, df_dime_closed, df_dime_us_port, df_dime_th_port

df_webull, df_dime_closed, df_dime_us, df_dime_th = load_all_history_sheets()

# ==========================================
# 3. EXPANDER & CONTROL BUTTONS
# ==========================================
with st.expander("🔄 แผงควบคุม Auto Sync ข้อมูลจาก Webull API", expanded=False):
    col_sync1, col_sync2 = st.columns([3, 1])
    with col_sync1:
        st.write("กดปุ่มเพื่อดึงออเดอร์ล่าสุดจาก Webull API บันทึกเติมลง Google Sheet พร้อมปั๊มสถานะ O=มีอยู่ / C=หมดแล้ว อัตโนมัติ")
    with col_sync2:
        if st.button("🚀 กด Sync ตอนนี้", type="primary", use_container_width=True):
            with st.spinner("⏳ กำลัง Sync ออเดอร์..."):
                success, msg = sync_webull_to_gsheet()
                if success:
                    st.success(msg)
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(msg)

st.markdown("<br>", unsafe_allow_html=True)

# Navigation Segmented Buttons
if "hist_tab_mode" not in st.session_state:
    st.session_state["hist_tab_mode"] = "US_REALIZED"

tab_mode = st.session_state["hist_tab_mode"]

c_b1, c_b2, c_b3, c_b4 = st.columns(4)

with c_b1:
    b1_type = "primary" if tab_mode == "US_REALIZED" else "secondary"
    if st.button("🎯 กำไรขายจริง หุ้น US", key="btn_h_us", type=b1_type, use_container_width=True):
        st.session_state["hist_tab_mode"] = "US_REALIZED"
        st.rerun()

with c_b2:
    b2_type = "primary" if tab_mode == "TH_REALIZED" else "secondary"
    if st.button("🎯 กำไรขายจริง หุ้นไทย", key="btn_h_th", type=b2_type, use_container_width=True):
        st.session_state["hist_tab_mode"] = "TH_REALIZED"
        st.rerun()

with c_b3:
    b3_type = "primary" if tab_mode == "RAW_LOGS" else "secondary"
    if st.button("📜 ประวัติสั่งซื้อขายดิบ", key="btn_h_raw", type=b3_type, use_container_width=True):
        st.session_state["hist_tab_mode"] = "RAW_LOGS"
        st.rerun()

with c_b4:
    b4_type = "primary" if tab_mode == "REVERSE_SPLIT" else "secondary"
    if st.button("🔄 หุ้นที่มีการรวมหุ้น", key="btn_h_split", type=b4_type, use_container_width=True):
        st.session_state["hist_tab_mode"] = "REVERSE_SPLIT"
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 4. TAB CONTENTS & DYNAMIC CALCULATIONS
# ==========================================

# ---------------------------------------------------
# TAB 1: US REALIZED PnL
# ---------------------------------------------------
if tab_mode == "US_REALIZED":
    st.markdown("### 📊 กำไร/ขาดทุนสุทธิเฉพาะไม้ออเดอร์ที่ขายปิดจบแล้ว (หุ้น US - $)")
    
    us_closed_summary = []
    
    if not df_webull.empty:
        df_w = df_webull.copy()
        
        cols = list(df_w.columns)
        sym_c = next((c for c in cols if 'sym' in c.lower() or 'ticker' in c.lower() or 'หุ้น' in c), cols[2] if len(cols) > 2 else 'Sym')
        side_c = next((c for c in cols if 'side' in c.lower() or 'buy/sell' in c.lower() or 'ฝั่ง' in c), cols[3] if len(cols) > 3 else 'Side')
        qty_c = next((c for c in cols if 'qty' in c.lower() or 'volume' in c.lower() or 'จำนวน' in c), cols[4] if len(cols) > 4 else 'Qty')
        price_c = next((c for c in cols if 'pr' in c.lower() or 'price' in c.lower() or 'ราคา' in c.lower()), cols[5] if len(cols) > 5 else 'Pr')
        time_c = next((c for c in cols if 'time' in c.lower() or 'date' in c.lower() or 'เวลา' in c.lower()), cols[1] if len(cols) > 1 else 'Time')
        
        if sym_c in df_w.columns and side_c in df_w.columns:
            for symbol, group in df_w.groupby(sym_c):
                symbol_clean = str(symbol).strip().upper()
                if not symbol_clean or symbol_clean == 'NAN' or symbol_clean in SPLIT_STOCKS: continue
                
                group_sorted = group.copy()
                if time_c in group_sorted.columns:
                    group_sorted['parsed_time'] = pd.to_datetime(group_sorted[time_c], errors='coerce')
                    group_sorted = group_sorted.sort_values(by='parsed_time', ascending=True)

                buy_queue = []
                total_realized_pnl = 0.0
                total_matched_qty = 0.0
                total_buy_cost = 0.0
                total_sell_rev = 0.0
                
                for _, row in group_sorted.iterrows():
                    raw_side = str(row[side_c]).upper().strip()
                    try:
                        qty = float(str(row[qty_c]).replace(",", "").replace("$", "").strip())
                        price = float(str(row[price_c]).replace(",", "").replace("$", "").strip())
                    except: continue
                    
                    if qty <= 0 or price <= 0: continue

                    if "BUY" in raw_side or "ซื้อ" in raw_side:
                        buy_queue.append({'qty': qty, 'price': price})
                    elif "SELL" in raw_side or "ขาย" in raw_side:
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
                                
                if total_matched_qty > 0:
                    avg_buy = total_buy_cost / total_matched_qty
                    avg_sell = total_sell_rev / total_matched_qty
                    ret_pct = (total_realized_pnl / total_buy_cost * 100) if total_buy_cost > 0 else 0.0
                    
                    remaining_in_queue = sum(b['qty'] for b in buy_queue)
                    status_text = "ปิดขายเกลี้ยงแล้ว" if remaining_in_queue < 0.01 else "ขายแล้วบางส่วน"
                    
                    us_closed_summary.append({
                        "ชื่อหุ้น": symbol_clean,
                        "โบรกเกอร์": "Webull",
                        "จำนวนหุ้นที่ปิดขายแล้ว": total_matched_qty,
                        "ราคาซื้อเฉลี่ย ($)": avg_buy,
                        "ราคาขายเฉลี่ย ($)": avg_sell,
                        "กำไร/ขาดทุนสุทธิ ($)": total_realized_pnl,
                        "ผลตอบแทน (%)": ret_pct,
                        "สถานะ": status_text
                    })

    if not df_dime_closed.empty:
        df_dc = df_dime_closed.copy()
        df_dc_us = df_dc[df_dc["ตลาด (US/TH)"].astype(str).str.strip().str.upper() == "US"] if "ตลาด (US/TH)" in df_dc.columns else df_dc
        
        us_port_map = {}
        if not df_dime_us.empty:
            df_us_clean = df_dime_us.copy()
            sym_col = next((c for c in df_us_clean.columns if 'หุ้น' in c or 'ticker' in c.lower() or 'sym' in c.lower()), None)
            vol_col = next((c for c in df_us_clean.columns if 'จำนวน' in c or 'volume' in c.lower() or 'qty' in c.lower()), None)
            if sym_col and vol_col:
                for _, p_row in df_us_clean.iterrows():
                    p_sym = str(p_row[sym_col]).strip().upper()
                    try: p_qty = float(str(p_row[vol_col]).replace(",", "").replace("$", ""))
                    except: p_qty = 0.0
                    if p_sym: us_port_map[p_sym] = us_port_map.get(p_sym, 0.0) + p_qty

        for _, r in df_dc_us.iterrows():
            sym = str(r.get('หุ้น (Ticker)') or r.get('Ticker') or r.get('Symbol', '')).strip().upper()
            if not sym or sym in SPLIT_STOCKS: continue
            
            try:
                qty = float(str(r.get('จำนวนหุ้น (Qty)') or r.get('Qty', 0)).replace(",", "").replace("$", ""))
                buy_p = float(str(r.get('ราคาซื้อเฉลี่ย (Buy Price)') or r.get('Buy Price', 0)).replace(",", "").replace("$", ""))
                sell_p = float(str(r.get('ราคาขายจริง (Sell Price)') or r.get('Sell Price', 0)).replace(",", "").replace("$", ""))
            except: continue
            
            if qty > 0 and buy_p > 0 and sell_p > 0:
                pnl = qty * (sell_p - buy_p)
                ret_pct = ((sell_p - buy_p) / buy_p * 100)
                rem_qty = us_port_map.get(sym, 0.0)
                status_text = "ขายแล้วบางส่วน" if rem_qty > 0.0001 else "ปิดขายเกลี้ยงแล้ว"
                
                us_closed_summary.append({
                    "ชื่อหุ้น": sym,
                    "โบรกเกอร์": "Dime US",
                    "จำนวนหุ้นที่ปิดขายแล้ว": qty,
                    "ราคาซื้อเฉลี่ย ($)": buy_p,
                    "ราคาขายเฉลี่ย ($)": sell_p,
                    "กำไร/ขาดทุนสุทธิ ($)": pnl,
                    "ผลตอบแทน (%)": ret_pct,
                    "สถานะ": status_text
                })

    if us_closed_summary:
        df_us_res = pd.DataFrame(us_closed_summary).sort_values(by="กำไร/ขาดทุนสุทธิ ($)", ascending=True)
        total_us_pnl = df_us_res["กำไร/ขาดทุนสุทธิ ($)"].sum()
        pnl_class = "text-green" if total_us_pnl >= 0 else "text-red"
        pnl_prefix = "+" if total_us_pnl >= 0 else ""
        
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🎯 กำไร/ขาดทุนสะสมรวมหุ้น US (Realized PnL)</div><div class="metric-value {pnl_class}">{pnl_prefix}${total_us_pnl:,.2f}</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🎯 จำนวนหุ้น US ที่มีรายการขาย</div><div class="metric-value text-cyan">{len(df_us_res)} ตัว</div></div>', unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)

        st.dataframe(
            df_us_res.style.map(color_pnl, subset=["กำไร/ขาดทุนสุทธิ ($)", "ผลตอบแทน (%)"])
            .format({
                "จำนวนหุ้นที่ปิดขายแล้ว": "{:,.4f}",
                "ราคาซื้อเฉลี่ย ($)": "${:,.2f}",
                "ราคาขายเฉลี่ย ($)": "${:,.2f}",
                "กำไร/ขาดทุนสุทธิ ($)": "${:,.2f}",
                "ผลตอบแทน (%)": "{:+.2f}%"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        m1, m2 = st.columns(2)
        with m1:
            st.markdown('<div class="metric-card"><div class="metric-label">🎯 กำไร/ขาดทุนสะสมรวมหุ้น US (Realized PnL)</div><div class="metric-value text-green">$0.00</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown('<div class="metric-card"><div class="metric-label">🎯 จำนวนหุ้น US ที่มีรายการขาย</div><div class="metric-value text-cyan">0 ตัว</div></div>', unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("💡 ไม่พบประวัติรายการขาย หรือยังไม่มีการปิดออเดอร์ในพอร์ตหุ้น US")

# ---------------------------------------------------
# TAB 2: TH REALIZED PnL
# ---------------------------------------------------
elif tab_mode == "TH_REALIZED":
    st.markdown("### 📊 กำไร/ขาดทุนสุทธิเฉพาะไม้ออเดอร์ที่ขายปิดจบแล้ว (หุ้นไทย - ฿)")
    
    th_closed_summary = []
    
    th_port_map = {}
    if not df_dime_th.empty:
        df_th_clean = df_dime_th.copy()
        sym_col = next((c for c in df_th_clean.columns if 'หุ้น' in c or 'ticker' in c.lower() or 'sym' in c.lower()), None)
        vol_col = next((c for c in df_th_clean.columns if 'จำนวน' in c or 'volume' in c.lower() or 'qty' in c.lower()), None)
        if sym_col and vol_col:
            for _, p_row in df_th_clean.iterrows():
                p_sym = str(p_row[sym_col]).strip().upper()
                try: p_qty = float(str(p_row[vol_col]).replace(",", "").replace("฿", ""))
                except: p_qty = 0.0
                if p_sym: th_port_map[p_sym] = th_port_map.get(p_sym, 0.0) + p_qty

    if not df_dime_closed.empty:
        df_dc = df_dime_closed.copy()
        df_dc_th = df_dc[df_dc["ตลาด (US/TH)"].astype(str).str.strip().str.upper() == "TH"] if "ตลาด (US/TH)" in df_dc.columns else pd.DataFrame()
        
        if not df_dc_th.empty:
            for _, r in df_dc_th.iterrows():
                sym = str(r.get('หุ้น (Ticker)') or r.get('Ticker') or r.get('Symbol', '')).strip().upper()
                if not sym: continue
                
                try:
                    qty = float(str(r.get('จำนวนหุ้น (Qty)') or r.get('Qty', 0)).replace(",", "").replace("฿", ""))
                    buy_p = float(str(r.get('ราคาซื้อเฉลี่ย (Buy Price)') or r.get('Buy Price', 0)).replace(",", "").replace("฿", ""))
                    sell_p = float(str(r.get('ราคาขายจริง (Sell Price)') or r.get('Sell Price', 0)).replace(",", "").replace("฿", ""))
                except: continue
                
                if qty > 0 and buy_p > 0 and sell_p > 0:
                    pnl = qty * (sell_p - buy_p)
                    ret_pct = ((sell_p - buy_p) / buy_p * 100)
                    rem_qty = th_port_map.get(sym, 0.0)
                    status_text = "ขายแล้วบางส่วน" if rem_qty > 0.0001 else "ปิดขายเกลี้ยงแล้ว"
                    
                    th_closed_summary.append({
                        "ชื่อหุ้น": sym,
                        "โบรกเกอร์": "Dime TH",
                        "จำนวนหุ้นที่ปิดขายแล้ว": qty,
                        "ราคาซื้อเฉลี่ย (฿)": buy_p,
                        "ราคาขายเฉลี่ย (฿)": sell_p,
                        "กำไร/ขาดทุนสุทธิ (฿)": pnl,
                        "ผลตอบแทน (%)": ret_pct,
                        "สถานะ": status_text
                    })

    if th_closed_summary:
        df_th_res = pd.DataFrame(th_closed_summary).sort_values(by="กำไร/ขาดทุนสุทธิ (฿)", ascending=True)
        total_th_pnl = df_th_res["กำไร/ขาดทุนสุทธิ (฿)"].sum()
        pnl_class = "text-green" if total_th_pnl >= 0 else "text-red"
        pnl_prefix = "+" if total_th_pnl >= 0 else ""
        
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🎯 กำไร/ขาดทุนสะสมรวมหุ้นไทย (Realized PnL)</div><div class="metric-value {pnl_class}">{pnl_prefix}฿{total_th_pnl:,.2f}</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🎯 จำนวนหุ้นไทยที่มีรายการขาย</div><div class="metric-value text-cyan">{len(df_th_res)} ตัว</div></div>', unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)

        st.dataframe(
            df_th_res.style.map(color_pnl, subset=["กำไร/ขาดทุนสุทธิ (฿)", "ผลตอบแทน (%)"])
            .format({
                "จำนวนหุ้นที่ปิดขายแล้ว": "{:,.2f}",
                "ราคาซื้อเฉลี่ย (฿)": "฿{:,.2f}",
                "ราคาขายเฉลี่ย (฿)": "฿{:,.2f}",
                "กำไร/ขาดทุนสุทธิ (฿)": "฿{:,.2f}",
                "ผลตอบแทน (%)": "{:+.2f}%"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        m1, m2 = st.columns(2)
        with m1:
            st.markdown('<div class="metric-card"><div class="metric-label">🎯 กำไร/ขาดทุนสะสมรวมหุ้นไทย (Realized PnL)</div><div class="metric-value text-green">฿0.00</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown('<div class="metric-card"><div class="metric-label">🎯 จำนวนหุ้นไทยที่มีรายการขาย</div><div class="metric-value text-cyan">0 ตัว</div></div>', unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("💡 ไม่พบประวัติรายการขาย หรือยังไม่มีการปิดออเดอร์ในพอร์ตหุ้นไทย")

# ---------------------------------------------------
# TAB 3: RAW LOGS
# ---------------------------------------------------
elif tab_mode == "RAW_LOGS":
    st.markdown("### 📜 ประวัติคำสั่งซื้อขายดิบแยกตาม Worksheet")
    
    sub1, sub2, sub3, sub4 = st.tabs([
        "1. Webull_Order_History", 
        "2. Dime_Closed_Orders", 
        "3. Dime_Portfolio (US)", 
        "4. Dime_TH_Portfolio (TH)"
    ])
    
    with sub1:
        st.subheader("📋 1. Webull_Order_History")
        if not df_webull.empty:
            st.dataframe(df_webull, use_container_width=True, hide_index=True)
        else:
            st.info("ไม่พบข้อมูลในชีท Webull_Order_History")
            
    with sub2:
        st.subheader("📝 2. Dime_Closed_Orders")
        if not df_dime_closed.empty:
            st.dataframe(df_dime_closed, use_container_width=True, hide_index=True)
        else:
            st.info("ยังไม่มีข้อมูลบันทึกในชีท Dime_Closed_Orders")
            
    with sub3:
        st.subheader("🇺🇸 3. Dime_Portfolio (หุ้น US ปัจจุบัน)")
        if not df_dime_us.empty:
            st.dataframe(df_dime_us, use_container_width=True, hide_index=True)
        else:
            st.info("ไม่พบข้อมูลในชีท Dime_Portfolio")
            
    with sub4:
        st.subheader("🇹🇭 4. Dime_TH_Portfolio (หุ้นไทยปัจจุบัน)")
        if not df_dime_th.empty:
            st.dataframe(df_dime_th, use_container_width=True, hide_index=True)
        else:
            st.info("ไม่พบข้อมูลในชีท Dime_TH_Portfolio")

# ---------------------------------------------------
# TAB 4: REVERSE SPLIT TRACKER
# ---------------------------------------------------
elif tab_mode == "REVERSE_SPLIT":
    st.markdown("### 🔄 คำนวณเฉพาะหุ้นที่มีการรวมหุ้น (Reverse Split / Corporate Actions)")
    st.caption("💡 คิดจากกระแสเงินสดจริง (Total Buy Cash vs Total Sell Cash) ป้องกันตัวเลขเพี้ยนจากการเปลี่ยนจำนวนหุ้น")
    
    split_summary = []
    
    if not df_webull.empty:
        df_w = df_webull.copy()
        
        cols = list(df_w.columns)
        sym_c = next((c for c in cols if 'sym' in c.lower() or 'ticker' in c.lower() or 'หุ้น' in c), cols[2] if len(cols) > 2 else 'Sym')
        side_c = next((c for c in cols if 'side' in c.lower() or 'buy/sell' in c.lower() or 'ฝั่ง' in c), cols[3] if len(cols) > 3 else 'Side')
        qty_c = next((c for c in cols if 'qty' in c.lower() or 'volume' in c.lower() or 'จำนวน' in c), cols[4] if len(cols) > 4 else 'Qty')
        price_c = next((c for c in cols if 'pr' in c.lower() or 'price' in c.lower() or 'ราคา' in c.lower()), cols[5] if len(cols) > 5 else 'Pr')
        
        if sym_c in df_w.columns and side_c in df_w.columns:
            for symbol in SPLIT_STOCKS:
                group = df_w[df_w[sym_c].astype(str).str.strip().str.upper() == symbol]
                if group.empty: continue
                
                total_buy_cash = 0.0
                total_sell_cash = 0.0
                
                for _, row in group.iterrows():
                    raw_side = str(row[side_c]).upper().strip()
                    try:
                        qty = float(str(row[qty_c]).replace(",", "").replace("$", "").strip())
                        price = float(str(row[price_c]).replace(",", "").replace("$", "").strip())
                    except: continue
                    
                    if qty <= 0 or price <= 0: continue
                    trade_val = qty * price

                    if "BUY" in raw_side or "ซื้อ" in raw_side:
                        total_buy_cash += trade_val
                    elif "SELL" in raw_side or "ขาย" in raw_side:
                        total_sell_cash += trade_val
                
                if total_sell_cash > 0:
                    realized_pnl = total_sell_cash - total_buy_cash
                    ret_pct = (realized_pnl / total_buy_cash * 100) if total_buy_cash > 0 else 0.0
                    
                    split_summary.append({
                        "ชื่อหุ้น": symbol,
                        "โบรกเกอร์": "Webull",
                        "เงินลงทุนซื้อรวม ($)": total_buy_cash,
                        "เงินขายได้คืนรวม ($)": total_sell_cash,
                        "กำไร/ขาดทุนสุทธิจริง ($)": realized_pnl,
                        "ผลตอบแทน (%)": ret_pct,
                        "หมายเหตุ": "รวมหุ้น (Reverse Split)"
                    })

    if split_summary:
        df_split_res = pd.DataFrame(split_summary)
        st.dataframe(
            df_split_res.style.map(color_pnl, subset=["กำไร/ขาดทุนสุทธิจริง ($)", "ผลตอบแทน (%)"])
            .format({
                "เงินลงทุนซื้อรวม ($)": "${:,.2f}",
                "เงินขายได้คืนรวม ($)": "${:,.2f}",
                "กำไร/ขาดทุนสุทธิจริง ($)": "${:,.2f}",
                "ผลตอบแทน (%)": "{:+.2f}%"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("💡 ยังไม่มีข้อมูลหุ้นกลุ่มรวมหุ้น (Reverse Split) ที่มีรายการขาย")
