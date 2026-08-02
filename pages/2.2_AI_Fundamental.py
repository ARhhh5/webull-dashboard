import streamlit as st

st.set_page_config(page_title="AI Fundamental Analyzer", layout="wide")

# ตรวจสอบการ Import google.generativeai
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

st.title("🧠 AI Fundamental Analyzer Engine")
st.markdown("ระบบวิเคราะห์งบการเงินและปัจจัยพื้นฐานหุ้นรายตัวแบบเจาะลึก 12 หัวข้อ ด้วย **Gemini 2.5 Flash**")
st.markdown("---")

# ==========================================
# 1. แม่แบบ Prompt (12 หัวข้อ)
# ==========================================
PROMPT_TEMPLATE = """ช่วยวิเคราะห์หุ้นตัวนี้แบบ Fundamental สำหรับมือใหม่ โดยอธิบายจากข้อมูลงบการเงินล่าสุด, annual report / 10-K / 20-F, earnings presentation, earnings call และข้อมูลธุรกิจล่าสุด

หุ้นที่ต้องการวิเคราะห์คือ: {ticker}

ขอให้ตอบเป็นภาษาไทยแบบเข้าใจง่าย แต่ข้อมูลต้องครบและลึกพอให้ใช้ตัดสินใจเบื้องต้นได้ โดยจัดคำตอบตามหัวข้อนี้:

1) บริษัทนี้ทำธุรกิจอะไร
- หาเงินจากอะไร
- สินค้าหรือบริการหลักคืออะไร
- รายได้แบ่งเป็นกี่ส่วน
- ส่วนไหนเป็นรายได้หลักสุด
- ธุรกิจนี้เข้าใจง่ายแบบคนทั่วไปฟังแล้วเห็นภาพ

2) ลูกค้าของบริษัทคือใคร
- ลูกค้าหลักเป็นใคร เช่น บุคคลทั่วไป, ธุรกิจ, รัฐบาล, โรงพยาบาล, นักพัฒนา, องค์กรขนาดใหญ่
- บริษัทพึ่งลูกค้ารายใหญ่ไม่กี่รายหรือกระจายดี
- ลูกค้าเปลี่ยนเจ้าง่ายไหม
- อะไรทำให้ลูกค้าอยู่กับบริษัทต่อ

3) โมเดลรายได้และคุณภาพรายได้
- รายได้เป็นแบบขายครั้งเดียวหรือ recurring revenue
- รายได้มีความสม่ำเสมอไหม
- ธุรกิจโตจาก volume, price, subscription, ads, commission, software license หรืออะไร
- รายได้แบบไหนคุณภาพดี และของบริษัทนี้ถือว่าดีไหม

4) ภาพรวมงบการเงินล่าสุด
- รายได้โตไหม
- กำไรโตไหม
- margin ดีขึ้นหรือแย่ลง
- กระแสเงินสดจากการดำเนินงานเป็นยังไง
- free cash flow ดีไหม
- หหนี้เยอะไหม
- บริษัทมีเงินสดพอไหม
- ถ้าดูคร่าว ๆ บริษัทแข็งแรงหรือเปราะบาง

5) เช็คคุณภาพพื้นฐานแบบง่าย
ช่วยประเมินทีละข้อและบอกเหตุผลแบบสั้นแต่ชัด:
- รายได้โตจริงไหม
- กำไรโตตามรายได้ไหม
- กระแสเงินสดดีไหม
- หนี้น่ากังวลไหม
- margin ดีหรือไม่
- ROIC / ROE / ROA ถ้ามี ควรอ่านว่ายังไง
- บริษัทมีโอกาสโตต่อหรือเริ่มตัน
- สุดท้ายให้สรุปว่า “พื้นฐานดี”, “ดีแต่มีจุดต้องระวัง”, หรือ “ยังไม่แข็งแรง”

6) จุดแข็งของธุรกิจ
- บริษัทมี moat หรือความได้เปรียบอะไร
- แบรนด์, network effect, switching cost, scale, cost advantage, data, technology, regulation มีไหม
- จุดแข็งนี้ของจริงหรือแค่ story

7) Optionality หรือโอกาสโตในอนาคต
- บริษัทมีทางโตเพิ่มจากอะไร
- มีสินค้าใหม่ ตลาดใหม่ ประเทศใหม่ AI / software / ecosystem / upsell / cross-sell หรือไม่
- อะไรคือ upside ที่ตลาดอาจยังมองไม่เต็ม
- optionality นี้ใกล้เกิดจริงหรือยังเป็นแค่ความหวัง

8) ความเสี่ยงที่ต้องรู้
- ความเสี่ยงจากการแข่งขัน
- ความเสี่ยงจากลูกค้ากระจุกตัว
- ความเสี่ยงจากกฎระเบียบ
- ความเสี่ยงจากเศรษฐกิจ
- ความเสี่ยงจาก margin ลด
- ความเสี่ยงจาก valuation แพงเกินไป
- ความเสี่ยงที่มือใหม่มักมองข้าม

9) ผู้บริหารและการเล่าเรื่องของบริษัท
- ผู้บริหารเก่งเรื่องอะไร
- พูดแล้วทำได้จริงไหม
- บริษัทมีประวัติ execute ดีไหม
- สิ่งที่ผู้บริหารพูดใน earnings call สอดคล้องกับตัวเลขหรือไม่

10) สรุปให้มือใหม่ตัดสินใจ
ช่วยสรุปแบบตรงไปตรงมาเป็น 3 ส่วน:
- หุ้นตัวนี้เป็นธุรกิจแบบไหนในภาษาคนทั่วไป
- จุดเด่น 3 ข้อ
- จุดเสี่ยง 3 ข้อ
- เหมาะกับนักลงทุนสายไหน เช่น สายโต, สายคุณภาพ, สายปันผล, สาย turnaround, สายเสี่ยงสูง
- ถ้าจะศึกษาต่อ ควรไปอ่านอะไรเพิ่มอีก

11) ให้คะแนนแบบง่าย
ช่วยให้คะแนน 1-10 พร้อมเหตุผลสั้น ๆ ในหัวข้อต่อไปนี้
- ความเข้าใจง่ายของธุรกิจ
- คุณภาพรายได้
- ความแข็งแรงของงบ
- ความสามารถในการเติบโต
- ความเสี่ยง
- ความน่าสนใจโดยรวม

12) Final Verdict
ปิดท้ายด้วยสรุปสั้น ๆ ว่า
- หุ้นนี้ “น่าศึกษาต่อไหม”
- “พื้นฐานดีจริงไหม”
- “ถ้าเป็นมือใหม่ควรดูอะไรเพิ่มก่อนซื้อ”

เงื่อนไขสำคัญ
- อย่าตอบกว้าง ๆ หรือชมสวยหรู
- อย่าทะลึ่ง มั่วข้อมูล คิดเองเออเองต้องอยู่บน Fact จาก Data
- ถ้าข้อมูลบางจุดไม่ชัด ให้บอกตรง ๆ ว่าไม่ชัด
- ใช้ตัวเลขล่าสุดเท่าที่หาได้
- ถ้ามีข้อมูลเปลี่ยนแปลงล่าสุด ให้เน้นข้อมูลใหม่ก่อน
- อธิบายศัพท์ยากเป็นภาษาง่ายในวงเล็บ
- ตอบแบบภาษาคนลงทุน ไม่ใช่ภาษาทางการแข็ง ๆ
"""

# ==========================================
# 2. ส่วนรับข้อมูล Ticker
# ==========================================
st.subheader("🔎 ระบุหุ้นที่ต้องการวิเคราะห์")
col_input, col_btn = st.columns([3, 1])

with col_input:
    ticker_input = st.text_input(
        "พิมพ์ชื่อ Ticker หุ้น (เช่น NVDA, MU, TSLA, AAPL):",
        value="",
        placeholder="ตัวอย่าง: NVDA"
    )

clean_ticker = ticker_input.strip().upper()

# ดึง API Key จาก Secrets (ค้นหาทุกจุดป้องกันปัญหา TOML section)
gemini_api_key = st.secrets.get("GEMINI_API_KEY", "")
if not gemini_api_key:
    # ลองค้นหาจากทุก sub-keys ใน secrets
    for key in st.secrets:
        if isinstance(st.secrets[key], dict) and "GEMINI_API_KEY" in st.secrets[key]:
            gemini_api_key = st.secrets[key]["GEMINI_API_KEY"]
            break

# ==========================================
# 3. โหมดการทำงาน (Live Analysis vs Raw Prompt)
# ==========================================
tab_live, tab_prompt = st.tabs(["🤖 วิเคราะห์สดบนหน้าเว็บ (Gemini 2.5 Flash)", "📋 ก๊อปปี้ Prompt ไปใช้ภายนอก"])

with tab_live:
    if not HAS_GENAI:
        st.error("🚨 **ยังไม่ได้ติดตั้ง Library `google-generativeai`**")
        st.info("💡 **วิธีแก้:** เพิ่มบรรทัด `google-generativeai` ในไฟล์ `requirements.txt` แล้วทำ Re-deploy หรือ Commit ขึ้น GitHub ครับ")
    elif clean_ticker:
        if not gemini_api_key or gemini_api_key == "XXXXX":
            st.error("🚨 **ยังไม่ได้ตั้งค่า GEMINI_API_KEY หรือใช้ค่าเริ่มต้น**")
            st.info("""
            **วิธีแก้ไข:**
            นำบรรทัด `GEMINI_API_KEY = "รหัสของคุณ"` ย้ายขึ้นไปวางไว้ที่ **บรรทัดแรกสุด** ในหน้า Streamlit Secrets ครับ
            """)
        else:
            if st.button(f"🚀 เริ่มวิเคราะห์ปัจจัยพื้นฐานหุ้น {clean_ticker}", type="primary", use_container_width=True):
                with st.spinner(f"⏳ Gemini 2.5 Flash กำลังอ่านงบการเงินและวิเคราะห์หุ้น {clean_ticker} กรุณารอแปปนึงครับ..."):
                    try:
                        genai.configure(api_key=gemini_api_key)
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        
                        prompt_text = PROMPT_TEMPLATE.format(ticker=clean_ticker)
                        response = model.generate_content(prompt_text)
                        
                        st.markdown(f"## 📊 ผลการวิเคราะห์ปัจจัยพื้นฐาน: **{clean_ticker}**")
                        st.markdown("---")
                        st.markdown(response.text)
                        st.success("✅ วิเคราะห์เสร็จสิ้น!")
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในการเรียกใช้ AI: {str(e)}")
    else:
        st.info("👈 พิมพ์ชื่อ Ticker หุ้นในช่องด้านบน แล้วกดปุ่มเพื่อเริ่มวิเคราะห์สดได้เลยครับ!")

with tab_prompt:
    if clean_ticker:
        generated_prompt = PROMPT_TEMPLATE.format(ticker=clean_ticker)
        st.subheader(f"📋 Prompt สำเร็จรูปสำหรับ: {clean_ticker}")
        st.caption("คลิกที่มุมขวาบนของกล่องด้านล่างเพื่อก๊อปปี้ไปวางใน ChatGPT / Claude / Gemini Advanced")
        st.code(generated_prompt, language="text")
    else:
        st.info("👈 พิมพ์ชื่อ Ticker หุ้นในช่องด้านบน เพื่อดูตัวอย่าง Prompt ฉบับเต็ม")
