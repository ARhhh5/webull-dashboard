import base64
import json
import streamlit as st

# ตรวจสอบการ Import google.generativeai
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# ==========================================
# 1. PAGE CONFIG & MODERN DARK CSS
# ==========================================
st.set_page_config(page_title="AI Buying Decision Engine", layout="wide")

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
        font-size: 0.85rem !important;
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

    /* Card Container */
    .chart-card {
        background-color: #0f1115;
        border: 1px solid #1a1d24;
        border-radius: 14px;
        padding: 24px;
        margin-top: 10px;
    }

    /* Custom Input Controls */
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        background-color: #141822 !important;
        border-color: #1a1d24 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Minimal Header
st.markdown('<div class="page-title-minimal">🧠 3.0 AI Target Stock Analyzer (GOD MODE)</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle-minimal">ระบบ AI ช่วยสแกนวิเคราะห์หุ้นเป้าหมายที่ต้องการจะเข้าซื้อ โดย "โอเลี้ยง GOD MODE Framework"</div>', unsafe_allow_html=True)

# ==========================================
# 2. GOD MODE PROMPT TEMPLATES
# ==========================================
GOD_MODE_PROMPT = """คุณคือ "โอเลี้ยง GOD MODE" — Global Growth Fund OS + Lazy Long-term Holder
คุณเป็น Global Growth Fund Manager ที่ขี้เกียจแต่เฉียบคมที่สุดในโลก เน้นถือยาวแบบมีวินัยสูงสุด

หลักปรัชญาที่คุณยึดถือ:
- William O'Neil (CANSLIM)
- Stan Weinstein (Stage Analysis)
- Aswath Damodaran (ROIC > WACC + Reverse DCF)
- Peter Lynch + Early-Stage Growth Investing
ปรัชญาหลัก: "ซื้อ Early Winner ตอน Story ยังไม่ถูกพิสูจน์เต็มที่ -> เพิ่มน้ำหนักเมื่อกลายเป็น Leader -> ถือยาวถ้า Stage 2 + Moat ยังแข็งแรง -> ขายทันทีเมื่อ Story/Trend/Quality พัง"

หุ้นเป้าหมายที่ต้องการให้วิเคราะห์ก่อนตัดสินใจเข้าซื้อคือ Ticker: {ticker}

จงวิเคราะห์หุ้นตัวนี้อย่างรอบด้านและเด็ดขาด โดยปฏิบัติตามโครงสร้างและกฎเหล็กต่อไปนี้:

---
### STEP 0 — Enhanced Pre-Analysis (ต้องทำก่อนเสมอ)
0.1 Macro Checklist (วิเคราะห์ Macro Regime ปัจจุบัน):
- ดัชนีหลัก (S&P 500, Nasdaq, SET) อยู่เหนือ/ใต้ SMA 50/200
- Market Breadth, Volatility (VIX), Bond Yield, DXY, Liquidity, Interest Rate Cycle, Commodity Prices, Geopolitical Risk
- Regime Classification: 🟢 Risk ON / 🟡 Neutral / 🟠 Late Cycle / 🔴 Risk OFF (ระบุชัดว่าควรถือหุ้นกี่ %, Cash กี่ %, IPO Basket กี่ %)
0.2 Mode Detection:
- 🐣 IPO / Pre-Proven (< 3 ปี)
- 🚀 Hybrid (1–5 ปี)
- 🧠 CANSLIM Leader (>= 3 ปี)
- 🏰 Compounder
0.3 Sector Rotation:
- Top 3 Leading Sector + 3 Weak Sector + Overweight / Underweight Recommendation

---
### โครงสร้างการวิเคราะห์หลัก
STEP 1 — Executive Summary (Ticker + ราคา + Market Cap + ธุรกิจ + วัน IPO + อายุ + โหมด + Macro Regime + Verdict)
STEP 2 — Dual Quality Scan (Pass/Fail)
STEP 3 — Alpha Score 0–100 (Growth 20 / Quality 20 / Story-TAM 15 / Technical-Stage 20 / Valuation 15 / Management 10)
STEP 4 — Stage Analysis (Weinstein Stage 1-4)
STEP 5 — IPO Deep Framework (ถ้าเป็น IPO/Hybrid)
STEP 6 — CANSLIM + Moat Check
STEP 7 — Valuation Reality Check (ROIC vs WACC / Reverse DCF)
STEP 8 — Risk Map (Enhanced) + Correlation Risk กับพอร์ต
STEP 9 — Portfolio Action & Exposure (Position Size %, Entry/Stop/Add/Trim, Review Date)
STEP 10 — One-Page Lazy Summary

---
### กฎเหล็กห้ามละเมิดเด็ดขาด:
1. ห้ามกุข้อมูลเด็ดขาด
2. ต้องทำ Macro Checklist + Regime ทุกครั้ง
3. ต้องประกาศ Mode + Regime + Stage + Alpha Score ให้ชัดเจน
4. CANSLIM <5/7 หรือ IPO <3/5 = หยุด/ไม่ซื้อ
5. Stage 4 = ขายทันที
6. IPO <= 3–5% ต่อตัว (Basket <=15%)
7. Alpha Score <70 = ไม่ซื้อ
8. ต้องพิจารณา Portfolio Exposure + Correlation Risk
9. ใช้ภาษาคน อ่านง่าย แต่คิดระดับกองทุน
10. Disclaimer: การวิเคราะห์ทั้งหมดมาจากข้อมูลสาธารณะ ไม่ใช่คำแนะนำการลงทุน
"""

TOOL_PROMPTS = {
    "1️⃣ สแกนสุขภาพการเงินบริษัท": "ช่วยอ่านงบการเงินล่าสุดของหุ้น {ticker} แล้วสรุป: สุขภาพโดยรวม, แนวโน้มรายได้-กำไร, ภาระหนี้+กระแสเงินสด, จุดเด่น 3 ข้อ, Red flags 3 ข้อ, และคำถามที่ควรหาคำตอบเพิ่มก่อนซื้อ",
    "2️⃣ แกะข่าวว่ากระทบหุ้นยังไง": "ช่วยแกะข่าวและประเด็นล่าสุดของหุ้น {ticker}: สรุปใจความข่าว -> ผลกระทบระยะสั้น/ยาว -> ใครได้-เสีย -> แยกข้อเท็จจริง vs การคาดเดา",
    "3️⃣ เทียบหุ้นในกลุ่มเดียวกัน": "ช่วยเปรียบเทียบหุ้น {ticker} กับ Peers ในกลุ่มเดียวกันด้วยตาราง -> ตัวไหนเด่นเรื่องอะไร -> เหมาะกับนักลงทุนแบบไหน",
    "4️⃣ ฟังทั้งสองฝั่ง (Bull vs Bear)": "สวมบทบาทวิเคราะห์หุ้น {ticker} ทั้งสองฝั่ง: ฝั่ง Bull (มุมมองบวก) vs ฝั่ง Bear (มุมมองลบ) -> สรุปปัจจัยชี้ขาดที่จะตัดสินว่าฝั่งไหนชนะ",
    "5️⃣ เช็กลิสต์ความเสี่ยงก่อนลงเงิน": "ทำเช็กลิสต์ความเสี่ยงก่อนลงเงินในหุ้น {ticker}: แยกเป็นหมวด + ระดับความเสี่ยง (ต่ำ/กลาง/สูง) + สิ่งที่ต้องเกิดขึ้นถึงจะทำให้ธุรกิจพัง",
    "6️⃣ สรุปงบ / Earnings Call ใน 2 นาที": "ดึงประเด็นสำคัญจากการรายงานงบ / Earnings Call ล่าสุดของหุ้น {ticker} ใน 2 นาที: ตัวเลข vs คาดการณ์, Guidance, น้ำเสียงผู้บริหาร, Surprise, และประเด็นที่ผู้บริหารพยายามเลี่ยง",
    "7️⃣ กรอบช่วยตัดสินใจ ซื้อ/ขาย/ถือ": "ตั้งคำถามย้อน 5 ข้อสำหรับหุ้น {ticker} -> แนะนำการแบ่งไม้เข้าซื้อ -> กำหนดเงื่อนไข ซื้อ/ขาย/ตัดขาดทุน -> และคำเตือนด้านอารมณ์ในการเทรด"
}

# ==========================================
# 3. INPUT CONTROL & SECRETS
# ==========================================
st.markdown("### 🔎 ระบุ Ticker หุ้นเป้าหมายที่ต้องการวิเคราะห์ก่อนซื้อ")
col_input, col_space = st.columns([2.5, 2.5])

with col_input:
    ticker_input = st.text_input(
        "พิมพ์ชื่อ Ticker หุ้นเป้าหมาย (เช่น NVDA, TSLA, PLTR, PTT):",
        value="",
        placeholder="ตัวอย่าง: NVDA"
    )

clean_ticker = ticker_input.strip().upper()

# ดึง GEMINI_API_KEY จาก Secrets
gemini_api_key = st.secrets.get("GEMINI_API_KEY", "")
if not gemini_api_key:
    for key in st.secrets:
        if isinstance(st.secrets[key], dict) and "GEMINI_API_KEY" in st.secrets[key]:
            gemini_api_key = st.secrets[key]["GEMINI_API_KEY"]
            break

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 4. NAVIGATION CONTROL
# ==========================================
if "ai_buy_mode" not in st.session_state:
    st.session_state["ai_buy_mode"] = "FULL_GOD"

nav_mode = st.session_state["ai_buy_mode"]

c_b1, c_b2, c_b3 = st.columns([1.5, 1.5, 1.5])

with c_b1:
    b1_type = "primary" if nav_mode == "FULL_GOD" else "secondary"
    if st.button("👑 GOD MODE Buy Decision", key="btn_buy_full", type=b1_type, use_container_width=True):
        st.session_state["ai_buy_mode"] = "FULL_GOD"
        st.rerun()

with c_b2:
    b2_type = "primary" if nav_mode == "EXTRA_TOOLS" else "secondary"
    if st.button("🛠️ 7 เครื่องมือวิเคราะห์ก่อนซื้อ", key="btn_buy_tools", type=b2_type, use_container_width=True):
        st.session_state["ai_buy_mode"] = "EXTRA_TOOLS"
        st.rerun()

with c_b3:
    b3_type = "primary" if nav_mode == "RAW_PROMPT" else "secondary"
    if st.button("📋 ก๊อปปี้ Prompt ไปใช้ภายนอก", key="btn_buy_prompt", type=b3_type, use_container_width=True):
        st.session_state["ai_buy_mode"] = "RAW_PROMPT"
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 5. EXECUTION & DISPLAY
# ==========================================
if nav_mode == "FULL_GOD":
    if not HAS_GENAI:
        st.error("🚨 **ยังไม่ได้ติดตั้ง Library `google-generativeai`**")
        st.info("💡 **วิธีแก้:** เพิ่ม `google-generativeai` ในไฟล์ `requirements.txt` แล้ว Re-deploy ครับ")
    elif clean_ticker:
        if not gemini_api_key or gemini_api_key == "XXXXX":
            st.error("🚨 **ยังไม่ได้ตั้งค่า GEMINI_API_KEY ใน Secrets**")
        else:
            if st.button(f"🚀 เริ่มการวิเคราะห์ decision หุ้นเป้าหมาย {clean_ticker}", type="primary", use_container_width=True):
                with st.spinner(f"⏳ โอเลี้ยง GOD MODE กำลังประมวลผลวิเคราะห์หุ้น {clean_ticker} กรุณารอสักครู่..."):
                    try:
                        genai.configure(api_key=gemini_api_key)
                        try:
                            model = genai.GenerativeModel('gemini-2.5-flash')
                        except Exception:
                            model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        prompt_text = GOD_MODE_PROMPT.format(ticker=clean_ticker)
                        response = model.generate_content(prompt_text)
                        
                        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
                        st.markdown(f"## 🏆 GOD MODE Target Analysis: **{clean_ticker}**")
                        st.markdown("---")
                        st.markdown(response.text)
                        st.markdown('</div>', unsafe_allow_html=True)
                        st.success("✅ ประมวลผลวิเคราะห์การเข้าซื้อเสร็จสิ้น!")
                    except Exception as e:
                        st.error(f"❌ เกิดข้อผิดพลาดในการเรียกใช้ AI: {str(e)}")
    else:
        st.info("👈 พิมพ์ชื่อ Ticker หุ้นเป้าหมายด้านบน แล้วกดปุ่มเพื่อเริ่มวิเคราะห์ได้ทันทีครับ!")

elif nav_mode == "EXTRA_TOOLS":
    selected_tool = st.selectbox("เลือกเครื่องมือวิเคราะห์เสริมที่ต้องการ:", list(TOOL_PROMPTS.keys()))
    
    if clean_ticker:
        if st.button(f"⚡ รันเครื่องมือ {selected_tool} สำหรับ {clean_ticker}", type="primary", use_container_width=True):
            if not gemini_api_key:
                st.error("🚨 กรุณาตั้งค่า GEMINI_API_KEY ใน Secrets ก่อนครับ")
            else:
                with st.spinner(f"⏳ กำลังประมวลผล {selected_tool}..."):
                    try:
                        genai.configure(api_key=gemini_api_key)
                        try:
                            model = genai.GenerativeModel('gemini-2.5-flash')
                        except Exception:
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            
                        tool_prompt = TOOL_PROMPTS[selected_tool].format(ticker=clean_ticker)
                        response = model.generate_content(tool_prompt)
                        
                        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
                        st.markdown(f"### 🛠️ ผลการวิเคราะห์: {selected_tool} ({clean_ticker})")
                        st.markdown("---")
                        st.markdown(response.text)
                        st.markdown('</div>', unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")
    else:
        st.info("👈 พิมพ์ชื่อ Ticker หุ้นเป้าหมายด้านบนก่อนใช้งานเครื่องมือเสริมครับ")

else: # RAW_PROMPT
    if clean_ticker:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.subheader(f"📋 GOD MODE Full Prompt สำหรับ {clean_ticker}")
        st.caption("ก๊อปปี้ Prompt ฉบับเต็มไปใช้ใน Gemini Advanced, ChatGPT หรือ Claude ได้ทันที")
        st.code(GOD_MODE_PROMPT.format(ticker=clean_ticker), language="text")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("👈 พิมพ์ชื่อ Ticker หุ้นด้านบนเพื่อรับ Prompt สำเร็จรูปครับ")
