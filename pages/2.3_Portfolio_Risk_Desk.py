import streamlit as st
import pandas as pd
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
st.markdown("ระบบ Underwrite ความเสี่ยง Analysis & Rebalancing Engine ระดับ CIO Office")
st.markdown("---")

# ==========================================
# 1. Master Institutional Prompt Template
# ==========================================
MASTER_RISK_DESK_PROMPT = """
คุณคือ Senior Multi-Asset Portfolio Strategist & Risk Manager จาก CIO Office (Institutional Risk Desk) ไม่ใช่ผู้ช่วยทั่วไป และไม่ใช่เซลส์
งานของคุณคือ “Underwrite ความเสี่ยงของพอร์ต” โดยนำข้อมูลพอร์ตที่มี แตก Exposure จริง วิเคราะห์ Position Size และออกแบบ Rebalancing Policy อย่างเป็นระบบ
พูดความจริงเรื่องความเสี่ยงอย่างตรงไปตรงมา แม้เจ้าของพอร์ตจะไม่อยากได้ยิน
นี่คือกรอบวินิจฉัยเชิงการศึกษา ไม่ใช่คำแนะนำการลงทุนเฉพาะบุคคล ผู้ใช้เป็นผู้ตัดสินใจลงทุนเอง

คำสั่งพิเศษจากผู้ใช้: {custom_command}

ข้อมูลพอร์ตปัจจุบันที่ดึงมาจากระบบ (Consolidated Portfolio Data):
{portfolio_data_text}

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
WORKFLOW & ลำดับ OUTPUT (เริ่มวิเคราะห์จากข้อมูลที่มีทันที)
═══════════════════════════════════════════════
1. Portfolio Snapshot (As-of, Base currency, Cash, Risk profile)
2. ภาพลวงตา vs ความจริง (สรุปประโยคเดียวคมๆ)
3. Portfolio X-Ray — Look-Through Exposure (Top-10 Single-name, Asset Class, Sector, Country, Currency, Factor)
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
# 3. ดึงข้อมูลพอร์ตอัตโนมัติจาก Session State
# ==========================================
st.subheader("📌 1. ข้อมูลพอร์ตหุ้นในระบบ (Consolidated Holdings)")

auto_portfolio_df = None

# ตรวจสอบ Session state ตามลำดับ
if "us_consolidated_df" in st.session_state and isinstance(st.session_state["us_consolidated_df"], pd.DataFrame) and not st.session_state["us_consolidated_df"].empty:
    auto_portfolio_df = st.session_state["us_consolidated_df"]
elif "all_holdings_df" in st.session_state and isinstance(st.session_state["all_holdings_df"], pd.DataFrame) and not st.session_state["all_holdings_df"].empty:
    auto_portfolio_df = st.session_state["all_holdings_df"]

if auto_portfolio_df is not None:
    st.success("✅ เชื่อมต่อข้อมูลพอร์ตจากระบบอัตโนมัติเรียบร้อยแล้ว!")
    with st.expander("🔍 คลิกเพื่อดูรายการหุ้นในพอร์ตที่ดึงมาจากระบบ", expanded=True):
        st.dataframe(auto_portfolio_df, use_container_width=True)
else:
    st.info("💡 **ไม่พบข้อมูลพอร์ตในความจำชั่วคราว** (เกิดจากการกดรีเฟรชหน้าเว็บ หรือยังไม่ได้เปิดไปที่หน้า `Portfolio`) คุณสามารถเปิดหน้า `Portfolio` ก่อนหนึ่งครั้ง หรือแนบภาพ/ระบุข้อมูลพอร์ตเพิ่มเติมด้านล่างได้เลยครับ")

# ==========================================
# 4. ส่วนแนบภาพ/ระบุข้อมูลเพิ่มเติม (Optional)
# ==========================================
col_opt1, col_opt2 = st.columns([1, 1])

with col_opt1:
    st.subheader("📸 แนบภาพ Screenshot พอร์ตเพิ่ม (Optional)")
    uploaded_files = st.file_uploader(
        "กรณีมีพอร์ตบัญชีอื่นที่ต้องการวิเคราะห์ร่วมด้วย:",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True
    )

with col_opt2:
    st.subheader("📝 เงื่อนไขเฉพาะ / ข้อจำกัด (Optional)")
    user_additional_info = st.text_area(
        "ระบุเงื่อนไข เช่น เงิน DCA / หุ้นที่ไม่ต้องการขาย / เป้าหมายลงทุน:",
        placeholder="ตัวอย่าง: เติมเงินเดือนละ 30,000 บาท / ห้ามขาย NVDA / รับขาดทุนได้ไม่เกิน 25%...",
        height=100
    )

st.subheader("⚡ 2. เลือกโหมดประมวลผล (Quick Action Buttons)")
st.caption("กดปุ่มโหมดวิเคราะห์ที่ต้องการ ระบบจะนำพอร์ตทั้งหมดไป Underwrite ความเสี่ยงด้วย Gemini 2.5 Flash ทันที")

# สร้างปุ่ม Quick Action แบบแบ่ง Grid
col_b1, col_b2, col_b3, col_b4 = st.columns(4)
col_b5, col_b6, col_b7, _ = st.columns(4)

action_command = None

with col_b1:
    if st.button("🔥 /full\nวิเคราะห์เต็มรูปแบบ", use_container_width=True, type="primary"):
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
# 5. ส่วนประมวลผล Gemini 2.5 Flash Engine
# ==========================================
if action_command:
    if not HAS_GENAI:
        st.error("🚨 **ยังไม่ได้ติดตั้ง Library `google-generativeai`** โปรดตรวจสอบไฟล์ `requirements.txt` ครับ")
    elif not gemini_api_key or gemini_api_key == "XXXXX":
        st.error("🚨 **ยังไม่ได้ตั้งค่า GEMINI_API_KEY** ย้ายบรรทัด `GEMINI_API_KEY = 'รหัส'` ไว้บรรทัดแรกสุดใน Secrets บน Streamlit Cloud ครับ")
    elif auto_portfolio_df is None and not uploaded_files and not user_additional_info.strip():
        st.warning("⚠️ ไม่พบข้อมูลพอร์ต! กรุณาคลิกไปหน้า `Portfolio` ก่อนหนึ่งครั้ง หรือแนบภาพ/ระบุข้อมูลพอร์ตในช่องด้านบนครับ")
    else:
        with st.spinner(f"⏳ Institutional Risk Desk กำลังวิเคราะห์พอร์ตด้วยโหมด {action_command} กรุณารอแปปนึงครับ..."):
            try:
                genai.configure(api_key=gemini_api_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                # แปลง DataFrame พอร์ตเป็นข้อความ
                portfolio_text = ""
                if auto_portfolio_df is not None:
                    portfolio_text = auto_portfolio_df.to_string(index=False)
                else:
                    portfolio_text = "ใช้อ่านข้อมูลจากภาพ Screenshot หรือข้อความที่แนบมา"
                
                # ประกอบ Prompt สั่งการ
                prompt_content = MASTER_RISK_DESK_PROMPT.format(
                    custom_command=action_command,
                    portfolio_data_text=portfolio_text,
                    user_text_input=user_additional_info if user_additional_info else "ไม่มีข้อมูลเพิ่มเติม"
                )
                
                contents = [prompt_content]
                
                # แปลงไฟล์ภาพที่อัปโหลดส่งให้ Gemini Vision (ถ้ามี)
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
