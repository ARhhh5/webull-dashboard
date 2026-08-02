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
st.set_page_config(page_title="Diamond Hunter OS v3.0", layout="wide")

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
st.markdown('<div class="page-title-minimal">💎 3.2 Diamond Hunter OS — Hybrid v3.0 Final</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle-minimal">Venture Capital Partner Level OS — สแกนค้นหาบริษัทผู้นำโลกในอีก 10–30 ปีข้างหน้า</div>', unsafe_allow_html=True)

# ==========================================
# 2. DIAMOND HUNTER PROMPT TEMPLATES
# ==========================================
DIAMOND_HUNTER_PROMPT = """คุณคือ Diamond Hunter OS — Venture Capital Partner ระดับโลก
ภารกิจเดียวของคุณคือ ค้นหาบริษัทที่จะเป็นผู้นำโลกใน 10–30 ปีข้างหน้า
คิดแบบ Sequoia + a16z + Founders Fund + Berkshire Hathaway + GO-AI Discipline

ปรัชญาหลัก:
มองข้ามราคาหุ้นระยะสั้น มองข้าม hype
โฟกัสที่ Business Quality, Founder Quality, TAM, Moat, Execution, Optionality

Golden Rule (บังคับตอบทุกครั้ง):
"If I bought this company today and forgot my password for 20 years… Would I still be happy I owned it?"

หุ้นเป้าหมายที่ต้องการให้วิเคราะห์คือ Ticker: {ticker}

จงวิเคราะห์หุ้นตัวนี้อย่างรอบด้านและเด็ดขาด ตามโครงสร้าง Diamond Framework v3.0 ด้านล่างนี้:

---
### STEP 0 — Pre-Analysis (บังคับ)
- Mega Trend Scanner — จัดอันดับธีมโลก (★★★★★ ถึง ★★★☆☆)
- Macro Regime — Risk ON / Neutral / Late Cycle / Risk OFF + Allocation Suggestion

---
### STEP 1 — Executive Summary
(Ticker + ราคา + Market Cap + ธุรกิจหลัก + Mode + Regime)

---
### STEP 2 — DNA Scoring (100 คะแนน)
จงประเมินและให้คะแนนตามเกณฑ์หลัก:
1. Founder DNA (18 คะแนน): Founder เป็น CEO? Ownership สูง? Track record + Capital Allocation
2. TAM DNA (18 คะแนน): ขนาดตลาด 10–30 ปี (ต้องใหญ่พอสำหรับ 10x–100x)
3. Moat DNA (15 คะแนน): Network Effect, Technology, Data, Brand, Scale, Switching Cost
4. Execution & Growth DNA (15 คะแนน): Revenue growth, Margin, Recurring Revenue, Customer Retention
5. Innovation + Disruption + Optionality (12 คะแนน): Disrupt ใคร? Innovation Culture? โอกาสธุรกิจใหม่
6. Financial Survival DNA (12 คะแนน): Cash, Debt, Runway, FCF, Recession Survival
7. Technical & Stage (10 คะแนน): Stage Analysis + Momentum

---
### STEP 3 — Special Tests
- 100 Bagger Test
- AI Impact Analysis
- Risk Map (Technology, Competition, Regulatory, Founder, Macro)
- Probability Model (10x / 25x / 50x / 100x)

---
### STEP 4 — Portfolio Action
- Diamond Rank + Position Size
- Action Recommendation
- Review Date (ทุกไตรมาส)

---
### รูปแบบการตอบมาตรฐาน (บังคับใช้ท้ายการวิเคราะห์เสมอ):
💎 Diamond Score : XX/100
🧬 DNA Rank : Legendary / Rare / Emerging / Reject
🎯 Theme : [ธีมหลัก] ★★★★★
📈 Probability
10x : XX%
25x : XX%
50x : XX%
100x : XX%
🟢 Action : BUY / DCA / WATCH / REJECT
🔥 Why this could become the next giant
1.
2.
3.
⚠ Story Breakers
1.
2.
3.
📅 Next Catalysts
...
⭐ Golden Rule
"If I bought this company today and forgot my password for 20 years…" → YES / NO + เหตุผลสั้น ๆ
Review : Quarterly
Disclaimer: การวิเคราะห์จากข้อมูลสาธารณะ ไม่ใช่คำแนะนำการลงทุน
"""

TOOL_PROMPTS = {
    "🧬 Founder & Capital Allocation Check": "เจาะลึกวิเคราะห์ Founder & CEO ของหุ้น {ticker}: การถือหุ้น (Ownership), ประวัติการบริหารเงินทุน (Capital Allocation), Vision และจุดตายของทีมบริหาร",
    "🌍 10-30 Years TAM & Megatrend Scan": "ประเมิน Total Addressable Market (TAM) ในอีก 10-30 ปีข้างหน้าของหุ้น {ticker}: ขนาดตลาดที่จะโตได้, Megatrend ที่สนับสนุน, และความเป็นไปได้ในการโตระดับ 10x-100x",
    "🏰 Deep Moat & Network Effect Test": "ทดสอบคูเมืองทางธุรกิจ (Moat) ของหุ้น {ticker}: Network Effect, Switching Cost, Brand/Data Advantage แข็งแกร่งพอจะรอดในอีก 20 ปีหรือไม่",
    "🤖 AI Impact & Disruption Risk": "ประเมินผลกระทบจาก AI ต่อหุ้น {ticker}: AI เป็นตัวเร่งการเติบโต (Tailwind) หรือเป็นภัยคุกคามที่จะมาดิสรัปท์ธุรกิจ (Headwind)",
    "🎯 100-Bagger Potential Probability Model": "ประเมินโอกาสสร้างผลตอบแทนเปลี่ยนชีวิตของหุ้น {ticker}: คำนวณ Probability Model สำหรับโอกาส 10x, 25x, 50x และ 100x พร้อมเงื่อนไขสำคัญ"
}

# ==========================================
# 3. INPUT CONTROL & SECRETS
# ==========================================
st.markdown("### 🔎 ระบุ Ticker หุ้นเปลี่ยนชีวิตที่ต้องการค้นหา (Diamond Target)")
col_input, col_space = st.columns([2.5, 2.5])

with col_input:
    ticker_input = st.text_input(
        "พิมพ์ชื่อ Ticker หุ้นเป้าหมาย (เช่น NVDA, PLTR, TSLA, ASML, ASTS):",
        value="",
        placeholder="ตัวอย่าง: ASTS"
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
if "diamond_buy_mode" not in st.session_state:
    st.session_state["diamond_buy_mode"] = "FULL_DIAMOND"

nav_mode = st.session_state["diamond_buy_mode"]

c_b1, c_b2, c_b3 = st.columns([1.5, 1.5, 1.5])

with c_b1:
    b1_type = "primary" if nav_mode == "FULL_DIAMOND" else "secondary"
    if st.button("💎 Diamond Hunter v3.0 Analysis", key="btn_diamond_full", type=b1_type, use_container_width=True):
        st.session_state["diamond_buy_mode"] = "FULL_DIAMOND"
        st.rerun()

with c_b2:
    b2_type = "primary" if nav_mode == "EXTRA_TOOLS" else "secondary"
    if st.button("🛠️ เครื่องมือสแกน VC Deep-Dive", key="btn_diamond_tools", type=b2_type, use_container_width=True):
        st.session_state["diamond_buy_mode"] = "EXTRA_TOOLS"
        st.rerun()

with c_b3:
    b3_type = "primary" if nav_mode == "RAW_PROMPT" else "secondary"
    if st.button("📋 ก๊อปปี้ Prompt ไปใช้ภายนอก", key="btn_diamond_prompt", type=b3_type, use_container_width=True):
        st.session_state["diamond_buy_mode"] = "RAW_PROMPT"
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 5. EXECUTION & DISPLAY
# ==========================================
if nav_mode == "FULL_DIAMOND":
    if not HAS_GENAI:
        st.error("🚨 **ยังไม่ได้ติดตั้ง Library `google-generativeai`**")
        st.info("💡 **วิธีแก้:** เพิ่ม `google-generativeai` ในไฟล์ `requirements.txt` แล้ว Re-deploy ครับ")
    elif clean_ticker:
        if not gemini_api_key or gemini_api_key == "XXXXX":
            st.error("🚨 **ยังไม่ได้ตั้งค่า GEMINI_API_KEY ใน Secrets**")
        else:
            if st.button(f"🚀 เริ่มการสแกน Diamond Hunter v3.0 สำหรับ {clean_ticker}", type="primary", use_container_width=True):
                with st.spinner(f"⏳ Diamond Hunter OS กำลังใช้ VC Framework สแกนหุ้น {clean_ticker}..."):
                    try:
                        genai.configure(api_key=gemini_api_key)
                        try:
                            model = genai.GenerativeModel('gemini-2.5-flash')
                        except Exception:
                            model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        prompt_text = DIAMOND_HUNTER_PROMPT.format(ticker=clean_ticker)
                        response = model.generate_content(prompt_text)
                        
                        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
                        st.markdown(f"## 💎 Diamond Hunter OS v3.0 Report: **{clean_ticker}**")
                        st.markdown("---")
                        st.markdown(response.text)
                        st.markdown('</div>', unsafe_allow_html=True)
                        st.success("✅ ประมวลผลสแกน Diamond Hunter เสร็จสิ้น!")
                    except Exception as e:
                        st.error(f"❌ เกิดข้อผิดพลาดในการเรียกใช้ AI: {str(e)}")
    else:
        st.info("👈 พิมพ์ชื่อ Ticker หุ้นเป้าหมายด้านบน แล้วกดปุ่มเพื่อเริ่มสแกนได้ทันทีครับ!")

elif nav_mode == "EXTRA_TOOLS":
    selected_tool = st.selectbox("เลือกเครื่องมือสแกน VC เสริมที่ต้องการ:", list(TOOL_PROMPTS.keys()))
    
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
                        st.markdown(f"### 🛠️ ผลการวิเคราะห์ VC: {selected_tool} ({clean_ticker})")
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
        st.subheader(f"📋 Diamond Hunter v3.0 Full Prompt สำหรับ {clean_ticker}")
        st.caption("ก๊อปปี้ Prompt ฉบับเต็มไปใช้ใน Gemini Advanced, ChatGPT หรือ Claude ได้ทันที")
        st.code(DIAMOND_HUNTER_PROMPT.format(ticker=clean_ticker), language="text")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("👈 พิมพ์ชื่อ Ticker หุ้นด้านบนเพื่อรับ Prompt สำเร็จรูปครับ")
