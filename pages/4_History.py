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

st.set_page_config(page_title="Trade History & Realized PnL", layout="wide")

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

st.title("📜 ประวัติการขาย & กำไร/ขาดทุนที่เกิดขึ้นจริง (Realized PnL)")
st.markdown("---")

# ==========================================
# ฟังก์ชันสำหรับ Sync ข้อมูลจาก Webull ลง Google Sheet
# ==========================================
def sync_webull_to_gsheet():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64:
            return False, "❌ ไม่พบกุญแจ Google ใน Secrets"
            
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Webull_Order_History")
    except Exception as e:
        return False, f"❌ ไม่สามารถเชื่อมต่อ Google Sheet ได้: {str(e)}"

    existing_records = worksheet.get_all_records()
    df_existing = pd.DataFrame(existing_records)
    
    existing_ids = set()
    existing_combos = set()
    
    if not df_existing.empty:
        for _, row in df_existing.iterrows():
            oid = str(row.get("Order ID", "")).strip()
            if oid:
                existing_ids.add(oid)
            
            combo = f"{str(row.get('Time',''))}_{str(row.get('Symbol',''))}_{str(row.get('Buy/Sell', row.get('Side','')))}_\
{str(row.get('Qty',''))}_{str(row.get('Price',''))}"
            existing_combos.add(combo)

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
        action = str(order.get("action", order.get("side", ""))).upper()
        side_formatted = "BUY" if "BUY" in action else ("SELL" if "SELL" in action else action)
        
        qty = float(order.get("quantity", order.get("filledQuantity", 0)))
        price = float(order.get("cost_price", order.get("avgFilledPrice", 0)))
        order_time = order.get("create_time", datetime.now().strftime("%Y-%m-%d"))

        full_order_id = f"{order_id}_{symbol}_{side_formatted}"
        combo_check = f"{order_time}_{symbol}_{side_formatted}_{qty}_{price}"

        if full_order_id not in existing_ids and combo_check not in existing_combos:
            if qty > 0 and price > 0:
                new_rows.append([full_order_id, order_time, symbol, side_formatted, qty, price])

    if new_rows:
        worksheet.append_rows(new_rows)
        return True, f"✅ Auto Sync สำเร็จ! เพิ่มรายการใหม่ลง Google Sheet ทั้งหมด {len(new_rows)} รายการ"
    else:
        return True, "ℹ️ ข้อมูลล่าสุดตรงกันแล้ว ไม่มีรายการใหม่ต้องเพิ่ม"

# ==========================================
# 🎯 ส่วนปุ่ม Auto Sync ด้านบนสุด
# ==========================================
with st.expander("🔄 แผงควบคุม Auto Sync ข้อมูลจาก Webull API", expanded=False):
    col_sync1, col_sync2 = st.columns([3, 1])
    with col_sync1:
        st.write("กดปุ่มเพื่อดึงออเดอร์ล่าสุดจาก Webull บันทึกเติมลง Google Sheet อัตโนมัติ")
    with col_sync2:
        if st.button("🚀 กด Sync ตอนนี้", type="primary", use_container_width=True):
            with st.spinner("⏳ กำลัง Sync ออเดอร์..."):
                success, msg = sync_webull_to_gsheet()
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# ดึงข้อมูลจาก Google Sheet
# ==========================================
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

tab_closed_only, tab_raw_logs = st.tabs([
    "🎯 1. ตารางสรุปกำไรจากการขายจริง (Realized PnL)", 
    "📜 2. ประวัติคำสั่งซื้อขายดิบแยกตาม Sheet"
])

# ==========================================
# แถบที่ 1: คำนวณ PnL ตาม Cash Flow จริง ชัดเจน 100%
# ==========================================
with tab_closed_only:
    st.markdown("### 📊 กำไร/ขาดทุนสุทธิเฉพาะไม้ออเดอร์ที่ขายปิดจบแล้ว (Realized PnL)")
    
    closed_summary = []
    
    if not df_webull.empty:
        df_w = df_webull.copy()
        df_w.columns = [str(c).strip() for c in df_w.columns]
        
        sym_c = next((c for c in df_w.columns if 'sym' in str(c).lower() or 'ticker' in str(c).lower() or 'หุ้น' in str(c)), 'Symbol')
        side_c = next((c for c in df_w.columns if 'side' in str(c).lower() or 'buy/sell' in str(c).lower() or 'ฝั่ง' in str(c)), 'Side')
        qty_c = next((c for c in df_w.columns if 'qty' in str(c).lower() or 'volume' in str(c).lower() or 'จำนวน' in str(c)), 'Qty')
        price_c = next((c for c in df_w.columns if 'price' in str(c).lower() or 'ราคา' in str(c).lower()), 'Price')
        
        if all(c in df_w.columns for c in [sym_c, side_c, qty_c, price_c]):
            for symbol, group in df_w.groupby(sym_c):
                symbol_clean = str(symbol).strip().upper()
                if not symbol_clean or symbol_clean == 'NAN': continue
                
                total_buy_cash = 0.0
                total_buy_qty = 0.0
                total_sell_cash = 0.0
                total_sell_qty = 0.0
                
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
                        total_buy_qty += qty
                    elif "SELL" in raw_side or "ขาย" in raw_side:
                        total_sell_cash += trade_val
                        total_sell_qty += qty
                
                # มีรายการขายเกิดขึ้นจริง
                if total_sell_qty > 0:
                    avg_sell = total_sell_cash / total_sell_qty if total_sell_qty > 0 else 0.0
                    avg_buy = (total_buy_cash / total_buy_qty) if total_buy_qty > 0 else avg_sell

                    # สรุปผลกำไร/ขาดทุนจากเงินสดเข้า-ออกจริง
                    realized_pnl = total_sell_cash - total_buy_cash
                    ret_pct = (realized_pnl / total_buy_cash * 100) if total_buy_cash > 0 else 0.0
                    
                    closed_summary.append({
                        "ชื่อหุ้น": symbol_clean,
                        "โบรกเกอร์": "Webull",
                        "จำนวนหุ้นที่ปิดขายแล้ว": total_sell_qty,
                        "ราคาซื้อเฉลี่ย": avg_buy,
                        "ราคาขายเฉลี่ย": avg_sell,
                        "กำไร/ขาดทุนสุทธิ ($)": realized_pnl,
                        "ผลตอบแทน (%)": ret_pct,
                        "สถานะ": "ปิดขายเกลี้ยงแล้ว"
                    })

    if not df_dime_closed.empty:
        df_dc = df_dime_closed.copy()
        df_dc.columns = [str(c).strip() for c in df_dc.columns]
        for _, r in df_dc.iterrows():
            sym = str(r.get('หุ้น (Ticker)') or r.get('Ticker') or r.get('Symbol', '')).strip().upper()
            if not sym: continue
            
            try:
                qty = float(str(r.get('จำนวนหุ้น (Qty)') or r.get('Qty', 0)).replace(",", "").replace("$", ""))
                buy_p = float(str(r.get('ราคาซื้อเฉลี่ย (Buy Price)') or r.get('Buy Price', 0)).replace(",", "").replace("$", ""))
                sell_p = float(str(r.get('ราคาขายจริง (Sell Price)') or r.get('Sell Price', 0)).replace(",", "").replace("$", ""))
            except: continue
            
            if qty > 0 and buy_p > 0 and sell_p > 0:
                pnl = qty * (sell_p - buy_p)
                ret_pct = ((sell_p - buy_p) / buy_p * 100)
                closed_summary.append({
                    "ชื่อหุ้น": sym,
                    "โบรกเกอร์": "Dime",
                    "จำนวนหุ้นที่ปิดขายแล้ว": qty,
                    "ราคาซื้อเฉลี่ย": buy_p,
                    "ราคาขายเฉลี่ย": sell_p,
                    "กำไร/ขาดทุนสุทธิ ($)": pnl,
                    "ผลตอบแทน (%)": ret_pct,
                    "สถานะ": "ปิดขายเกลี้ยงแล้ว"
                })

    if closed_summary:
        df_closed_res = pd.DataFrame(closed_summary).sort_values(by="กำไร/ขาดทุนสุทธิ ($)", ascending=True)
        
        total_pnl = df_closed_res["กำไร/ขาดทุนสุทธิ ($)"].sum()
        pnl_class = "pnl-positive" if total_pnl >= 0 else "pnl-negative"
        pnl_prefix = "+" if total_pnl >= 0 else ""
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="metric-container"><div class="metric-label">💰 กำไร/ขาดทุนสะสมรวมจากการขายจริง (Realized PnL)</div><div class="metric-value {pnl_class}">{pnl_prefix}${total_pnl:,.2f}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-container"><div class="metric-label">🎯 จำนวนหุ้นที่มีรายการขายสะสม</div><div class="metric-value">{len(df_closed_res)} ตัว</div></div>', unsafe_allow_html=True)
            
        st.markdown("---")
        
        def color_pnl(val):
            if isinstance(val, (int, float)):
                color = '#00c853' if val > 0 else ('#ff3d00' if val < 0 else '#848e9c')
                return f'color: {color}; font-weight: bold;'
            return ''

        st.dataframe(
            df_closed_res.style.map(color_pnl, subset=["กำไร/ขาดทุนสุทธิ ($)", "ผลตอบแทน (%)"])
            .format({
                "จำนวนหุ้นที่ปิดขายแล้ว": "{:,.2f}",
                "ราคาซื้อเฉลี่ย": "${:,.2f}",
                "ราคาขายเฉลี่ย": "${:,.2f}",
                "กำไร/ขาดทุนสุทธิ ($)": "${:,.2f}",
                "ผลตอบแทน (%)": "{:+.2f}%"
            }),
            use_container_width=True
        )
    else:
        st.info("💡 ไม่พบรายการหุ้นที่มีการขายเกิดขึ้นในประวัติ")

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
