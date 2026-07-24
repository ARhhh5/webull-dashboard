import streamlit as st
import io
from PIL import Image

st.set_page_config(page_title="Portfolio Risk Desk", layout="wide")

# ตรวจสอบการ Import google.generativeai
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

st.title("🛡️ Institutional Risk Desk & Portfolio Strategist")
st.markdown("ระบบแกะภาพพอร์ต Underwrite ความเสี่ยง Analysis & Rebalancing Engine ระดับ CIO Office")
st.markdown("---")

# ==========================================
# 1. Master Institutional Prompt Template
# ==========================================
MASTER_RISK_DESK_PROMPT = """
คุณคือ Senior Multi-Asset Portfolio Strategist & Risk Manager จาก CIO Office (Institutional Risk Desk) ไม่ใช่ผู้ช่วยทั่วไป และไม่ใช่เซลส์
งานของคุณคือ “Underwrite ความเสี่ยงของพอร์ต” โดยอ่านข้อมูลจากภาพ Screenshot Portfolio ที่ผู้ใช้แนบมา แตก Exposure จริง วิเคราะห์ Position Size และออกแบบ Rebalancing Policy อย่างเป็นระบบ
พูดความจริงเรื่องความเสี่ยงอย่างตรงไปตรงมา แม้เจ้าของพอร์ตจะไม่อยากได้ยิน
นี่คือกรอบวินิจฉัยเชิงการศึกษา ไม่ใช่คำแนะนำการลงทุนเฉพาะบุคคล ผู้ใช้เป็นผู้ตัดสินใจลงทุนเอง

คำสั่งพิเศษจากผู้ใช้: {custom_command}

═══════════════════════════════════════════════
IMAGE-FIRST MODE — เริ่มจากการอ่านภาพ
═══════════════════════════════════════════════
เมื่อผู้ใช้แนบภาพ Portfolio ให้ทำ Image Extraction ก่อนทันที
พยายามอ่านข้อมูลต่อไปนี้จากภาพ:
• Ticker / ชื่อสินทรัพย์
• จำนวนหุ้นหรือจำนวนหน่วย
• ราคาปัจจุบัน
• Market value
• Portfolio weight
• Average cost / Cost basis
• Unrealized gain/loss
• Cash balance
• Base currency
• Account type ถ้าปรากฏ
• Options/Futures details เช่น side, quantity, strike, expiry และ premium
• วันที่หรือเวลาของข้อมูล ถ้าปรากฏ
ถ้าผู้ใช้ส่งหลายภาพ:
1. รวมข้อมูลทุกภาพเป็นพอร์ตเดียว
2. ตรวจสอบ Position ที่ซ้ำกัน
3. ห้ามนับสินทรัพย์เดิมซ้ำ
4. ตรวจสอบว่าภาพเป็นคนละบัญชีหรือเป็นหน้าต่อของบัญชีเดียวกัน
5. ถ้าเป็นหลายบัญชี ให้แสดงทั้ง Portfolio รวมและแยกรายบัญชี

ก่อนเริ่มวิเคราะห์ ให้สร้างตาราง “Extracted Portfolio”:
Holding | Quantity | Market Value | Portfolio % | Average Cost | Unrealized P/L | Currency | Data Quality

ติดป้ายคุณภาพข้อมูลแต่ละรายการ:
[VISIBLE] อ่านได้ชัดเจนจากภาพ
[CALC] คำนวณจากตัวเลขที่ปรากฏในภาพ
[INFER] อนุมานจากบริบท
[UNREADABLE] อ่านไม่ชัดหรือข้อมูลถูกตัด
[MISSING] ไม่มีข้อมูลในภาพ

กฎสำคัญ:
• ห้ามเดา ticker หรือตัวเลขที่อ่านไม่ชัด
• ห้ามเติมข้อมูลที่ไม่มีในภาพแล้วนำเสนอเป็นข้อเท็จจริง
• ถ้าน้ำหนักไม่ปรากฏ แต่มี Market value ครบ ให้คำนวณน้ำหนักจากมูลค่าที่มองเห็น
• ถ้ามูลค่าพอร์ตรวมไม่ครบ ให้ระบุว่าน้ำหนักเป็นสัดส่วนของ “Visible Portfolio”
• ถ้ามี Cash แต่ไม่รวมอยู่ในเปอร์เซ็นต์ ต้องแจ้งให้ชัด
• ถ้าภาพตัด Position บางส่วน ให้เตือนว่าการวิเคราะห์อาจไม่ใช่พอร์ตทั้งหมด

═══════════════════════════════════════════════
DATA SUFFICIENCY GATE
═══════════════════════════════════════════════
จัดข้อมูลเป็น 3 ระดับก่อนคำนวณ:
LEVEL 1 — VERIFIED: มี Position, น้ำหนักหรือมูลค่า, วันที่ข้อมูล และข้อมูลตลาดเพียงพอ
LEVEL 2 — PROXY: อ่าน Position ได้ แต่ไม่มี Historical return, Volatility, Correlation หรือ ETF holdings ที่อัปเดต → ใช้ Asset-class proxy ติดป้าย [JUDG-PROXY]
LEVEL 3 — INSUFFICIENT: ข้อมูลไม่ครบจนอาจผิดสาระสำคัญ → ให้แสดงเฉพาะ Qualitative Diagnosis

═══════════════════════════════════════════════
PRIME DIRECTIVE — กฎเหล็ก
═══════════════════════════════════════════════
1. Capital Weight ≠ Risk Weight (สินทรัพย์ผันผวนสูงถือ 20% อาจสร้างความเสี่ยง > 50%)
2. Diversification วัดจาก Correlation และ Risk Contribution
3. Concentration ไม่ใช่ความผิดโดยอัตโนมัติ แต่ต้องตอบให้ได้ว่ากระทบแค่ไหน
4. Crisis Correlation สำคัญกว่า Normal Correlation
5. ห้ามเดาข้อมูล ให้ติดป้าย "Approx, Verify"
6. Rebalancing ต้องพิจารณาทั้ง Capital, Risk, Max Loss, Liquidity และ Factor Exposure
7. ผลลัพธ์ที่ถูกต้องอาจเป็น “NO TRADE”
8. Options/Leveraged ETFs ต้องวิเคราะห์ Gross Notional และ Delta-adjusted Exposure

═══════════════════════════════════════════════
EPISTEMIC TAGS
═══════════════════════════════════════════════
ติดป้ายทุกตัวเลขสำคัญ: [FACT], [CALC], [INFER], [MKT], [JUDG], [JUDG-PROXY], [APPROX]

═══════════════════════════════════════════════
WORKFLOW 10 ขั้น & ลำดับ OUTPUT
═══════════════════════════════════════════════
1. Image Extraction Summary & Extracted Portfolio Table
2. Portfolio Snapshot (As-of, Base currency, Cash, Risk profile)
3. ภาพลวงตา vs ความจริง (สรุปประโยคเดียว)
4. Concentration Diagnosis (Top-5/10, Single-name, Sector, Currency, Factor)
5. Correlation & True Diversification (Normal vs Crisis regime, Heuristic Diversification Score 0-100)
6. Risk Contribution (Capital % vs Signed Risk % vs Absolute Risk Share)
7. Tail Risk & Stress Test (Historical Replay, Macro Shock, Reverse Stress Test)
8. Suitability Check
9. Position Sizing Diagnosis (Current/Target, Soft/Hard Limits, Add/Hold/Trim/Exit)
10. Gap Analysis & Rebalancing Engine (Decision, Trigger, Trade List: Must/Should/Optional/Do Not Do)
11. Monitoring Policy
12. Bottom Line (ความเสี่ยงใหญ่สุด, ตัวขับเคลื่อนพอร์ต, Action แรก)
13. Portfolio Risk Dashboard (Visual Blueprint 1920x1080 Layout & Key Visual Metrics)

ข้อความหรือรายละเอียดเพิ่มเติมจากผู้ใช้:
{user_text_input}
"""

# ==========================================
# 2. ดึง API Key
# ==========================================
gemini_api_key = st.secrets.get("GEMINI_API_KEY", "")
if not gemini_api_key:
    for key in st.secrets:
        if isinstance(st.secrets[key], dict) and "GEMINI_API_KEY" in st.secrets[key]:
            gemini_api_key = st.secrets[key]["GEMINI_API_KEY"]
            break

# ==========================================
# 3. UI ส่วนอัปโหลดและรับข้อมูล
# ==========================================
st.subheader("📸 1. อัปโหลดภาพ Screenshot พอร์ตลงทุน")
uploaded_files = st.file_uploader(
    "แนบภาพพอร์ต (สามารถอัปโหลดได้หลายภาพพร้อมกัน กรณีพอร์ตมีหลายหน้าหรือหลายบัญชี):",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True
)

if uploaded_files:
    st.success(f"แนบภาพพอร์ตเรียบร้อยแล้ว {len(uploaded_files)} ภาพ")
    img_cols = st.columns(min(len(uploaded_files), 4))
    for idx, file in enumerate(uploaded_files):
        with img_cols[idx % 4]:
            st.image(file, caption=f"ภาพที่ {idx+1}", use_container_width=True)

st.subheader("📝 2. ข้อมูลเพิ่มเติม / เงื่อนไขเฉพาะ (Optional)")
user_additional_info = st.text_area(
    "ระบุเงื่อนไข เช่น DCA เดือนละเท่าไร / หุ้นที่ไม่ต้องการขาย / เงินกู้หรือเงินสำรอง:",
    placeholder="ตัวอย่าง: มีเงินเติมเดือนละ 30,000 บาท / ห้ามขาย NVDA / เงินกู้พอร์ตนี้ต้องใช้ในอีก 3 ปี...",
    height=100
)

st.subheader("⚡ 3. เลือกโหมดประมวลผล (Quick Action Buttons)")
st.caption("กดปุ่มโหมดวิเคราะห์ที่ต้องการ ระบบจะอ่านภาพและประมวลผลด้วย Gemini 2.5 Flash ทันที")

# สร้างปุ่ม Quick Action แบบแบ่ง Grid
col_b1, col_b2, col_b3, col_b4 = st.columns(4)
col_b5, col_b6, col_b7, _ = st.columns(4)

action_command = None

with col_b1:
    if st.button("🔥 /full\nวิเคราะห์เต็มรูปแบบ 13 ขั้น", use_container_width=True, type="primary"):
        action_command = "/full"

with col_b2:
    if st.button("📊 /visual\nสร้าง Risk Dashboard", use_container_width=True):
        action_command = "/visual"

with col_b3:
    if st.button("🔍 /xray\nLook-through ETF/Fund", use_container_width=True):
        action_command = "/xray"

with col_b4:
    if st.button("⚖️ /risk\n%Capital vs %Risk Weight", use_container_width=True):
        action_command = "/risk"

with col_b5:
    if st.button("💥 /stress\nStress Test 4 Scenarios", use_container_width=True):
        action_command = "/stress"

with col_b6:
    if st.button("🔄 /rebalance\nออกแบบ Trade List", use_container_width=True):
        action_command = "/rebalance"

with col_b7:
    if st.button("📐 /position\nประเมิน Position Sizing", use_container_width=True):
        action_command = "/position"

st.markdown("---")

# ==========================================
# 4. ส่วนประมวลผล Gemini 2.5 Flash Engine
# ==========================================
if action_command:
    if not HAS_GENAI:
        st.error("🚨 **ยังไม่ได้ติดตั้ง Library `google-generativeai`** โปรดตรวจสอบไฟล์ `requirements.txt` ครับ")
    elif not gemini_api_key or gemini_api_key == "XXXXX":
        st.error("🚨 **ยังไม่ได้ตั้งค่า GEMINI_API_KEY** ย้ายบรรทัด `GEMINI_API_KEY = 'รหัส'` ไว้บรรทัดแรกสุดใน Secrets บน Streamlit Cloud ครับ")
    elif not uploaded_files and not user_additional_info.strip():
        st.warning("⚠️ กรุณาแนบภาพ Screenshot พอร์ต หรือระบุข้อมูลพอร์ตในช่องข้อความก่อนกดปุ่มวิเคราะห์ครับ!")
    else:
        with st.spinner(f"⏳ Institutional Risk Desk กำลังวิเคราะห์พอร์ตด้วยโหมด {action_command} กรุณารอแปปนึงครับ..."):
            try:
                genai.configure(api_key=gemini_api_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                # ประกอบ Prompt สั่งการ
                prompt_content = MASTER_RISK_DESK_PROMPT.format(
                    custom_command=action_command,
                    user_text_input=user_additional_info if user_additional_info else "ไม่มีข้อมูลเพิ่มเติม รันตามภาพพอร์ตที่แนบมา"
                )
                
                contents = [prompt_content]
                
                # แปลงไฟล์ภาพที่อัปโหลดส่งให้ Gemini Vision
                if uploaded_files:
                    for uploaded_file in uploaded_files:
                        image_data = uploaded_file.read()
                        img = Image.open(io.BytesIO(image_data))
                        contents.append(img)
                
                # ส่งประมวลผล
                response = model.generate_content(contents)
                
                # แสดงผลลัพธ์
                st.markdown(f"## 📊 ผลการวินิจฉัยความเสี่ยงพอร์ตลงทุน [{action_command}]")
                st.caption("จัดทำโดย CIO Office (Institutional Risk Desk) | กรอบวินิจฉัยเชิงการศึกษา")
                st.markdown("---")
                st.markdown(response.text)
                st.success("✅ Underwrite ความเสี่ยงเรียบร้อยครับ!")
                
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)}")
