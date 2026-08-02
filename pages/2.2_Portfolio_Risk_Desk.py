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
from PIL import Image
from datetime import datetime, timezone

# ตรวจสอบการ Import google.generativeai
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# ==========================================
# 1. PAGE CONFIG & MODERN DARK CSS
# ==========================================
st.set_page_config(page_title="Portfolio Risk Desk", layout="wide")

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
        padding: 8px 12px !important;
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
        padding: 14px 18px;
        border-radius: 12px;
        border: 1px solid #1a1d24;
        text-align: center;
    }
    .metric-label {
        color: #9ca3af;
        font-size: 11px;
        font-weight: 600;
        margin-bottom: 4px;
        text-transform: uppercase;
    }
    .metric-value {
        font-size: 20px;
        font-weight: 800;
        color: #ffffff;
        font-family: 'JetBrains Mono', monospace;
    }
    .text-green { color: #4ade80 !important; }
    .text-cyan { color: #38bdf8 !important; }

    /* Card Container */
    .chart-card {
        background-color: #0f1115;
        border: 1px solid #1a1d24;
        border-radius: 14px;
        padding: 20px;
        margin-top: 10px;
    }

    /* Custom Input / Select Controls */
    div[data-baseweb="textarea"] > div, div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        background-color: #141822 !important;
        border-color: #1a1d24 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Minimal Header
st.markdown('<div class="page-title-minimal">🛡️ Portfolio Risk Desk Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle-minimal">ระบบวิเคราะห์และประเมินความเสี่ยงพอร์ตโฟลิโอแบบเลือกสเกลด้วย Gemini 2.5 Flash</div>', unsafe_allow_html=True)

# ==========================================
# 2. ROBUST AUTO DATA FETCHING PIPELINE
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

def parse_num(val):
    if pd.isna(val) or val is None:
        return 0.0
    s_val = str(val).replace(",", "").replace("$", "").replace("฿", "").strip()
    try:
        return float(s_val)
    except Exception:
        return 0.0

@st.cache_data(ttl=120)
def fetch_all_portfolio_data():
    portfolio_items = []
    status_logs = []
    
    # 1. Fetch Google Sheets (Dime US & Dime TH)
    gc = get_gspread_client()
    if gc:
        try:
            sh = gc.open("หุ้นของเรา")
            status_logs.append("✅ เชื่อมต่อ Google Sheet 'หุ้นของเรา' สำเร็จ")
            
            # ดึงรายชื่อ Worksheets ทั้งหมดในไฟล์
            worksheets = [ws.title for ws in sh.worksheets()]
            
            # --- 1.1 Dime US (ลองค้นหาชื่อ worksheet ที่เข้าข่าย) ---
            us_sheet_names = [w for w in worksheets if "dime_portfolio" in w.lower() or "dime_us" in w.lower() or "us_portfolio" in w.lower()]
            if not us_sheet_names and "Dime_Portfolio" in worksheets:
                us_sheet_names = ["Dime_Portfolio"]
                
            for ws_name in us_sheet_names:
                try:
                    ws = sh.worksheet(ws_name)
                    records = ws.get_all_records()
                    if records:
                        df_temp = pd.DataFrame(records)
                        cols = [str(c).strip() for c in df_temp.columns]
                        df_temp.columns = cols
                        
                        sym_col = next((c for c in cols if 'ticker' in c.lower() or 'sym' in c.lower() or 'หุ้น' in c), None)
                        qty_col = next((c for c in cols if 'จำนวน' in c or 'qty' in c.lower() or 'volume' in c.lower()), None)
                        val_col = next((c for c in cols if 'มูลค่า' in c or 'value' in c.lower() or 'total' in c.lower()), None)
                        
                        if sym_col:
                            for _, r in df_temp.iterrows():
                                sym = str(r[sym_col]).strip().upper()
                                qty = parse_num(r[qty_col]) if qty_col else 1.0
                                val = parse_num(r[val_col]) if val_col else 0.0
                                if sym and sym != "NAN" and (qty > 0 or val > 0):
                                    portfolio_items.append({"Source": "Dime US", "Symbol": sym, "Qty": qty, "MarketValue": val, "Currency": "USD"})
                            status_logs.append(f"✅ โหลดข้อมูลจาก {ws_name} สำเร็จ ({len(records)} รายการ)")
                except Exception as e:
                    status_logs.append(f"⚠️ ไม่สามารถอ่าน {ws_name}: {str(e)}")

            # --- 1.2 Dime TH ---
            th_sheet_names = [w for w in worksheets if "dime_th" in w.lower() or "th_portfolio" in w.lower()]
            for ws_name in th_sheet_names:
                try:
                    ws = sh.worksheet(ws_name)
                    records = ws.get_all_records()
                    if records:
                        df_temp = pd.DataFrame(records)
                        cols = [str(c).strip() for c in df_temp.columns]
                        df_temp.columns = cols
                        
                        sym_col = next((c for c in cols if 'ticker' in c.lower() or 'sym' in c.lower() or 'หุ้น' in c), None)
                        qty_col = next((c for c in cols if 'จำนวน' in c or 'qty' in c.lower() or 'volume' in c.lower()), None)
                        val_col = next((c for c in cols if 'มูลค่า' in c or 'value' in c.lower() or 'total' in c.lower()), None)
                        
                        if sym_col:
                            for _, r in df_temp.iterrows():
                                sym = str(r[sym_col]).strip().upper()
                                qty = parse_num(r[qty_col]) if qty_col else 1.0
                                val = parse_num(r[val_col]) if val_col else 0.0
                                if sym and sym != "NAN" and (qty > 0 or val > 0):
                                    portfolio_items.append({"Source": "Dime TH", "Symbol": sym, "Qty": qty, "MarketValue": val, "Currency": "THB"})
                            status_logs.append(f"✅ โหลดข้อมูลจาก {ws_name} สำเร็จ ({len(records)} รายการ)")
                except Exception as e:
                    status_logs.append(f"⚠️ ไม่สามารถอ่าน {ws_name}: {str(e)}")

        except Exception as e:
            status_logs.append(f"❌ เชื่อมต่อ Google Sheets ไม่สำเร็จ: {str(e)}")
    else:
        status_logs.append("⚠️ ไม่พบ Google Credentials ใน Secrets")

    # 2. Fetch Webull API
    webull_config = st.secrets.get("Webull", {})
    APP_KEY = webull_config.get("AppKey", "").strip() or webull_config.get("app_key", "").strip()
    APP_SECRET = webull_config.get("AppSecret", "").strip() or webull_config.get("app_secret", "").strip()
    ACCESS_TOKEN = webull_config.get("AccessToken", "").strip()
    ACCOUNT_ID = webull_config.get("AccountId", "").strip() or webull_config.get("account_id", "").strip()
    HOST = "api.webull.co.th"

    if APP_KEY and ACCOUNT_ID:
        try:
            path = "/openapi/assets/positions"
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            nonce = uuid.uuid4().hex
            signing_values = {"host": HOST, "x-app-key": APP_KEY, "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-signature-version": "1.0", "x-timestamp": timestamp, "account_id": ACCOUNT_ID}
            string_1 = "&".join(f"{key}={signing_values[key]}" for key in sorted(signing_values))
            signature = base64.b64encode(hmac.new(f"{APP_SECRET}&".encode("utf-8"), urllib.parse.quote(f"{path}&{string_1}", safe="").encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
            headers = {"Accept": "application/json", "x-app-key": APP_KEY, "x-timestamp": timestamp, "x-signature-version": "1.0", "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-version": "v2", "x-signature": signature, "x-access-token": ACCESS_TOKEN}
            
            conn = http.client.HTTPSConnection(HOST)
            conn.request("GET", f"{path}?account_id={ACCOUNT_ID}", "", headers)
            res = conn.getresponse()
            data = json.loads(res.read().decode("utf-8"))
            if isinstance(data, list):
                wb_count = 0
                for p in data:
                    if p.get("instrument_type") == "EQUITY":
                        sym = str(p.get("symbol", "")).strip().upper()
                        qty = float(p.get("quantity", 0))
                        mkt_p = float(p.get("last_price", p.get("cost_price", 0)))
                        if sym and qty > 0:
                            portfolio_items.append({"Source": "Webull", "Symbol": sym, "Qty": qty, "MarketValue": qty * mkt_p, "Currency": "USD"})
                            wb_count += 1
                status_logs.append(f"✅ โหลดข้อมูลจาก Webull API สำเร็จ ({wb_count} รายการ)")
        except Exception as e:
            status_logs.append(f"⚠️ ยิง Webull API ไม่สำเร็จ: {str(e)}")
    else:
        status_logs.append("⚠️ ไม่พบ Webull API Credentials ใน Secrets")

    return pd.DataFrame(portfolio_items), status_logs

# Load Portfolio Data & Logs
df_all_port, sync_logs = fetch_all_portfolio_data()

# ==========================================
# 3. PORTFOLIO SELECTION DROPDOWN
# ==========================================
st.markdown("### 🎯 เลือกพอร์ตโฟลิโอที่ต้องการวิเคราะห์ความเสี่ยง")

available_sources = ["รวมทุกพอร์ตโฟลิโอ (All Portfolios)"]
if not df_all_port.empty and "Source" in df_all_port.columns:
    unique_sources = df_all_port["Source"].unique().tolist()
    available_sources.extend(unique_sources)

selected_source = st.selectbox(
    "เลือกแหล่งข้อมูลพอร์ตที่ต้องการวิเคราะห์:",
    options=available_sources,
    index=0
)

# Filter Data Based on Selection
if selected_source == "รวมทุกพอร์ตโฟลิโอ (All Portfolios)":
    df_port = df_all_port.copy()
else:
    df_port = df_all_port[df_all_port["Source"] == selected_source].copy() if not df_all_port.empty else pd.DataFrame()

# ==========================================
# 4. PORTFOLIO SUMMARY DASHBOARD
# ==========================================
if not df_port.empty:
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">📦 จำนวนหุ้นในพอร์ตที่เลือก</div><div class="metric-value text-cyan">{len(df_port)} ตัว</div></div>', unsafe_allow_html=True)
    with m2:
        us_val = df_port[df_port["Currency"] == "USD"]["MarketValue"].sum()
        st.markdown(f'<div class="metric-card"><div class="metric-label">💵 มูลค่ารวมฝั่ง US ($)</div><div class="metric-value text-green">${us_val:,.2f}</div></div>', unsafe_allow_html=True)
    with m3:
        th_val = df_port[df_port["Currency"] == "THB"]["MarketValue"].sum()
        st.markdown(f'<div class="metric-card"><div class="metric-label">🇹🇭 มูลค่ารวมฝั่งไทย (฿)</div><div class="metric-value text-green">฿{th_val:,.2f}</div></div>', unsafe_allow_html=True)

    with st.expander(f"🔍 ตรวจสอบตารางหุ้น: {selected_source} (คลิกเพื่อขยาย)"):
        st.dataframe(df_port, use_container_width=True, hide_index=True)
else:
    st.warning(f"⚠️ ไม่พบข้อมูลพอร์ตโฟลิโอสำหรับ `{selected_source}` ในระบบ (สามารถอัปโหลดภาพหรือพิมพ์เงื่อนไขเพิ่มเติมด้านล่างได้)")
    with st.expander("🛠️ ตรวจสอบสถานะการเชื่อมต่อข้อมูล (Debug Logs)"):
        for log in sync_logs:
            st.write(log)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 5. OPTIONAL INPUTS & SCREENSHOT UPLOAD
# ==========================================
col_up, col_cond = st.columns([1, 1])

with col_up:
    st.markdown("### 📷 แนบภาพ Screenshot พอร์ตเพิ่ม (Optional)")
    uploaded_file = st.file_uploader("กรณีมีพอร์ตบัญชีอื่นที่ต้องการวิเคราะห์ร่วมด้วย:", type=["png", "jpg", "jpeg", "webp"])

with col_cond:
    st.markdown("### 📝 เงื่อนไขเฉพาะ / ข้อจำกัด (Optional)")
    user_constraints = st.text_area(
        "ระบุเงื่อนไข เช่น เงิน DCA / หุ้นที่ไม่ต้องการขาย / เป้าหมายลงทุน:",
        placeholder="ตัวอย่าง: เติมเงินเดือนละ 30,000 บาท / ห้ามขาย NVDA / รับขาดทุนได้ไม่เกิน 25%...",
        height=100
    )

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 6. QUICK ACTION SEGMENTED BUTTONS & AI MODES
# ==========================================
st.markdown("### ⚡ เลือกโหมดประมวลผล (Quick Action Buttons)")
st.caption(f"กดปุ่มโหมดวิเคราะห์ที่ต้องการ ระบบจะนำพอร์ต `{selected_source}` ไป Underwrite ความเสี่ยงด้วย Gemini 2.5 Flash ทันที")

col_a1, col_a2, col_a3, col_a4 = st.columns(4)
col_b1, col_b2, col_b3, col_b4 = st.columns(4)

selected_mode = None

with col_a1:
    if st.button("🔥 /full วิเคราะห์เต็มรูปแบบ", type="primary", use_container_width=True):
        selected_mode = "FULL"
with col_a2:
    if st.button("📊 /visual สร้าง Risk Dashboard", use_container_width=True):
        selected_mode = "VISUAL"
with col_a3:
    if st.button("🔍 /xray Look-through ETF/Fund", use_container_width=True):
        selected_mode = "XRAY"
with col_a4:
    if st.button("⚖️ /risk %Capital vs %Risk Weight", use_container_width=True):
        selected_mode = "RISK_WEIGHT"

with col_b1:
    if st.button("💥 /stress Stress Test 4 Scenarios", use_container_width=True):
        selected_mode = "STRESS"
with col_b2:
    if st.button("🔄 /rebalance ออกแบบ Trade List", use_container_width=True):
        selected_mode = "REBALANCE"
with col_b3:
    if st.button("📐 /position ประเมิน Sizing", use_container_width=True):
        selected_mode = "POSITION"

# ==========================================
# 7. GEMINI RISK PROCESSING ENGINE
# ==========================================
gemini_api_key = st.secrets.get("GEMINI_API_KEY", "")
if not gemini_api_key:
    for key in st.secrets:
        if isinstance(st.secrets[key], dict) and "GEMINI_API_KEY" in st.secrets[key]:
            gemini_api_key = st.secrets[key]["GEMINI_API_KEY"]
            break

MODE_PROMPTS = {
    "FULL": "ช่วยวิเคราะห์ความเสี่ยงพอร์ตโฟลิโอภาพรวมอย่างเจาะลึก 360 องศา ทั้ง Sector Concentration, Single Stock Risk, Correlation Risk และให้คำแนะนำการปรับสมดุลพอร์ตอย่างมืออาชีพ",
    "VISUAL": "ช่วยสรุปสัดส่วนความเสี่ยงพอร์ตโฟลิโอออกมาในรูปแบบตารางและสถิติเชิงเปรียบเทียบ Risk Dashboard (Sector breakdown, Beta, Drawdown potential)",
    "XRAY": "ช่วยทำการ Look-through เจาะไส้ในของ ETF/Fund/หุ้นที่ถืออยู่ เพื่อหาความเสี่ยงแฝงและการถือหุ้นซ้ำซ้อน (Overlapping Holdings)",
    "RISK_WEIGHT": "ช่วยเปรียบเทียบ %Capital Sizing (สัดส่วนเงินลงทุน) กับ %Risk Weight (ความเสี่ยงจริงตาม Volatility/Beta) ว่าหุ้นตัวไหนความเสี่ยงเกินขนาดเงิน",
    "STRESS": "ช่วยจำลอง Stress Test พอร์ตโฟลิโอใน 4 สถานการณ์วิกฤต: 1) Fed ขึ้นดอกเบี้ยแรง 2) Tech Sell-off -20% 3) วิกฤตสงคราม/น้ำมันพุ่ง 4) เงินบาทผันผวนหนัก",
    "REBALANCE": "ช่วยวางแผน Trade List สำหรับ Rebalance พอร์ตอย่างละเอียด ตัวไหนควร Trim, ตัวไหนควร Hold, และตัวไหนควร Add พร้อมจุด Cut Loss",
    "POSITION": "ช่วยประเมิน Position Sizing ตามหลัก Risk Management (Volatility Adjust & Kelly Criterion) เพื่อไม่ให้พอร์ตเสียหายเกินเป้าหมาย"
}

if selected_mode:
    if not HAS_GENAI:
        st.error("🚨 ยังไม่ได้ติดตั้ง `google-generativeai` ใน requirements.txt")
    elif not gemini_api_key:
        st.error("🚨 ยังไม่ได้ตั้งค่า `GEMINI_API_KEY` ใน Streamlit Secrets")
    else:
        # เตรียมข้อมูลสำหรับส่งให้ AI
        port_summary_text = f"พอร์ตโฟลิโอที่เลือกวิเคราะห์: {selected_source}\n"
        port_summary_text += "รายการหุ้นในพอร์ตปัจจุบัน:\n"
        if not df_port.empty:
            port_summary_text += df_port.to_string(index=False)
        else:
            port_summary_text += "ไม่มีข้อมูลตารางหุ้นในระบบ (วิเคราะห์จากรูปภาพหรือเงื่อนไขผู้ใช้)\n"

        if user_constraints.strip():
            port_summary_text += f"\n\nเงื่อนไขเฉพาะของผู้ใช้:\n{user_constraints}"

        full_prompt = f"""คุณคือ Chief Risk Officer (CRO) และ Portfolio Risk Manager มืออาชีพ
คำสั่งวิเคราะห์โหมด: {selected_mode}
{MODE_PROMPTS[selected_mode]}

ข้อมูลพอร์ตโฟลิโอ:
{port_summary_text}

ขอให้ตอบเป็นภาษาไทยอย่างกระชับ ตรงประเด็น ใช้ภาษาคนลงทุน และให้คำแนะนำที่ปฏิบัติตามได้จริง (Actionable Insights)"""

        with st.spinner(f"⏳ Gemini 2.5 Flash กำลังประมวลผลวิเคราะห์ความเสี่ยงพอร์ต {selected_source} (โหมด {selected_mode})..."):
            try:
                genai.configure(api_key=gemini_api_key)
                try:
                    model = genai.GenerativeModel('gemini-2.5-flash')
                except Exception:
                    model = genai.GenerativeModel('gemini-1.5-flash')

                contents = [full_prompt]
                if uploaded_file is not None:
                    img = Image.open(uploaded_file)
                    contents.append(img)

                response = model.generate_content(contents)

                st.markdown('<div class="chart-card">', unsafe_allow_html=True)
                st.markdown(f"## 🛡️ ผลการวิเคราะห์ความเสี่ยง: **{selected_source}** (โหมด {selected_mode})")
                st.markdown("---")
                st.markdown(response.text)
                st.markdown('</div>', unsafe_allow_html=True)
                st.success("✅ ประมวลผลวิเคราะห์ความเสี่ยงเสร็จสิ้น!")
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดในการวิเคราะห์: {str(e)}")
