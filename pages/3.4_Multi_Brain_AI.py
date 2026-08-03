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
st.set_page_config(page_title="Multi-Brain Guru AI", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

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

    /* Card Container */
    .brain-card {
        background-color: #0f1115;
        border: 1px solid #1a1d24;
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 15px;
    }

    .chat-bubble-user {
        background-color: #1e293b;
        color: #f8fafc;
        padding: 12px 16px;
        border-radius: 12px 12px 2px 12px;
        margin-bottom: 10px;
        max-width: 80%;
        margin-left: auto;
    }

    .chat-bubble-ai {
        background-color: #0f172a;
        border: 1px solid #1e293b;
        color: #e2e8f0;
        padding: 14px 18px;
        border-radius: 12px 12px 12px 2px;
        margin-bottom: 15px;
        max-width: 90%;
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
st.markdown('<div class="page-title-minimal">🧠 3.4 Multi-Brain Guru AI Council</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle-minimal">ระบบโคลนสมองกูรูระดับโลก ประเมินและเปรียบเทียบมุมมองการลงทุนต่างแนวคิด</div>', unsafe_allow_html=True)

# ==========================================
# 2. GURU BRAIN PROMPTS & KNOWLEDGE BASE
# ==========================================
GURU_PROMPTS = {
    "CK Cheong (Fastwork)": """คุณคือ CK Cheong (CEO ของ Fastwork)
สไตล์การพูด: ตรงไปตรงมา, ดุดัน, ดึงสติ, เน้น Execution, แคร์เรื่อง Cashflow, Business Model และ Unit Economics เป็นหลัก
เน้นย้ำเรื่อง: "อย่าเพ้อฝัน ให้ดูความเป็นจริง Value คืออะไร? ถ้ารักษารายได้และ Cash flow ไม่ได้ ก็เป็นได้แค่ไอเดียเพ้อฝัน"
ภารกิจ: วิเคราะห์หุ้นหรือโมเดลธุรกิจตามมุมมองของ CK Cheong
""",
    "Warren Buffett (Value Investor)": """คุณคือ Warren Buffett (Berkshire Hathaway)
สไตล์การพูด: สุภาพ, ถ่อมตน, มีอารมณ์ขันแบบผู้ใหญ่, เน้นเข้าใจง่าย
เน้นย้ำเรื่อง: Economic Moat (คูเมืองทางธุรกิจ), Circle of Competence, FCF, Management Integrity และการซื้อหุ้นที่ดีในราคาที่เหมาะสมเพื่อถือยาว 20 ปีขึ้นไป
ภารกิจ: วิเคราะห์หุ้นหรือโมเดลธุรกิจตามหลักการ Value Investing ของ Warren Buffett
""",
    "Cathie Wood (ARK Invest)": """คุณคือ Cathie Wood (ARK Invest)
สไตล์การพูด: มั่นใจ, มองการณ์ไกล, ตื่นเต้นกับนวัตกรรมเปลี่ยนโลก
เน้นย้ำเรื่อง: Disruptive Innovation, Wright's Law, AI/Automation, Gene Editing, Autonomous Tech และตลาดขนาดมหึมา (TAM)
ภารกิจ: วิเคราะห์หุ้นหรือโมเดลธุรกิจตามมุมมองการลงทุนในนวัตกรรมของ Cathie Wood
"""
}

# ==========================================
# 3. SECRETS & SETUP
# ==========================================
gemini_api_key = st.secrets.get("GEMINI_API_KEY", "")
if not gemini_api_key:
    for key in st.secrets:
        if isinstance(st.secrets[key], dict) and "GEMINI_API_KEY" in st.secrets[key]:
            gemini_api_key = st.secrets[key]["GEMINI_API_KEY"]
            break

# ==========================================
# 4. UI LAYOUT & BRAIN SELECTION
# ==========================================
col_setup, col_chat = st.columns([1.2, 2.8])

with col_setup:
    st.markdown('<div class="brain-card">', unsafe_allow_html=True)
    st.subheader("⚙️ ตั้งค่าสมอง AI")
    
    selected_guru = st.selectbox(
        "เลือกสมองกูรูผู้ช่วยหลัก:",
        list(GURU_PROMPTS.keys())
    )
    
    mode = st.radio(
        "โหมดการวิเคราะห์:",
        ["💬 สนทนาเดี่ยว (Single Guru)", "⚔️ เปรียบเทียบมุมมอง (Guru Debate)"]
    )
    
    st.markdown("---")
    st.markdown("🔗 **เสริมข้อมูลสดจาก YouTube (Optional):**")
    yt_url = st.text_input("วางลิงก์ YouTube เพิ่มเติม (ถ้ามี):", placeholder="https://www.youtube.com/watch?v=...")
    st.caption("ระบบจะดึงเนื้อหาในลิงก์มาประมวลผลร่วมกับสมองของกูรูทันที")
    st.markdown('</div>', unsafe_allow_html=True)

with col_chat:
    st.markdown('<div class="brain-card">', unsafe_allow_html=True)
    st.subheader(f"🎯 สนทนากับสมอง: {selected_guru if mode == '💬 สนทนาเดี่ยว (Single Guru)' else 'สภาสแกนหุ้น (Guru Council)'}")
    
    # User Input
    user_query = st.text_area("พิมพ์โจทย์ หุ้น หรือโมเดลธุรกิจที่ต้องการให้วิเคราะห์:", height=100, placeholder="ตัวอย่าง: อยากลงทุนในหุ้น NVDA ยอดขายโตดีมาก แต่มูลค่าเริ่มแพง คุณคิดอย่างไร?")
    
    if st.button("🚀 ส่งคำถามให้ AI ประมวลผล", type="primary", use_container_width=True):
        if not user_query.strip():
            st.warning("⚠️ กรุณาพิมพ์คำถามหรือระบุหุ้นก่อนครับ")
        elif not HAS_GENAI or not gemini_api_key:
            st.error("🚨 กรุณาตรวจสอบการตั้งค่า GEMINI_API_KEY หรือ Library google-generativeai")
        else:
            with st.spinner("🧠 AI กำลังใช้ประมวลผลทางความคิด..."):
                try:
                    genai.configure(api_key=gemini_api_key)
                    try:
                        model = genai.GenerativeModel('gemini-2.5-flash')
                    except Exception:
                        model = genai.GenerativeModel('gemini-1.5-flash')

                    context_addon = f"\n[ลิงก์อ้างอิงเพิ่มเติม: {yt_url}]" if yt_url else ""

                    if mode == "💬 สนทนาเดี่ยว (Single Guru)":
                        system_prompt = GURU_PROMPTS[selected_guru]
                        full_prompt = f"{system_prompt}\n\nโจทย์จากผู้ใช้: {user_query}{context_addon}"
                        response = model.generate_content(full_prompt)
                        
                        st.markdown(f"### 🤖 มุมมองจาก {selected_guru}")
                        st.markdown("---")
                        st.markdown(response.text)

                    else: # Guru Debate Mode
                        st.markdown("### ⚔️ สรุปเปรียบเทียบมุมมอง 3 กูรู")
                        st.markdown("---")
                        
                        for guru_name, persona_prompt in GURU_PROMPTS.items():
                            full_prompt = f"{persona_prompt}\n\nโจทย์จากผู้ใช้: {user_query}{context_addon}"
                            res = model.generate_content(full_prompt)
                            
                            with st.expander(f"🧠 มุมมองของ {guru_name}", expanded=True):
                                st.markdown(res.text)

                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")
                    
    st.markdown('</div>', unsafe_allow_html=True)
