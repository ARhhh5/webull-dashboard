import streamlit as st
import pandas as pd

st.title("🛡️ ระบบบริหารเงินและควบคุมความเสี่ยง (Money Management)")
st.markdown("---")

st.subheader("🧮 เครื่องมือคำนวณขนาดไม้เทรด (Position Sizing Calculator)")

# ช่องสำหรับป้อนข้อมูลเพื่อคำนวณ
col1, col2 = st.columns(2)

with col1:
    portfolio_value = st.number_input("💵 ขนาดทุนของพอร์ตโดยรวม ($ USD)", min_value=100.0, value=25000.0, step=500.0)
    risk_percent = st.slider("🎯 ความเสี่ยงที่ยอมรับได้ต่อ 1 ไม้เทรด (%)", min_value=0.5, max_value=5.0, value=1.0, step=0.5)

with col2:
    entry_price = st.number_input("📈 ราคาเข้าซื้อหุ้นที่เล็งไว้ ($ต่อหุ้น)", min_value=0.01, value=100.0, step=1.0)
    stop_loss_price = st.number_input("🛑 ราคาที่จะคัตทิ้ง / Stop Loss ($ต่อหุ้น)", min_value=0.00, value=95.0, step=1.0)

# คำนวณตรรกะ MM
if stop_loss_price >= entry_price:
    st.error("❌ ราคา Stop Loss จะต้องต่ำกว่าราคาเข้าซื้อ (Entry Price) นะเพื่อน!")
else:
    # 1. จำนวนเงินสูงสุดที่ยอมสูญเสียได้ในไม้นี้
    max_risk_amount = portfolio_value * (risk_percent / 100)
    
    # 2. ระยะห่างของราคาคัตทิ้งต่อหุ้น
    risk_per_share = entry_price - stop_loss_price
    risk_per_share_pct = (risk_per_share / entry_price) * 100
    
    # 3. จำนวนหุ้นสูงสุดที่ซื้อได้
    max_shares_to_buy = max_risk_amount / risk_per_share
    
    # 4. จำนวนเงินลงทุนรวมที่ต้องใช้กดซื้อไม้นี้
    total_position_size = max_shares_to_buy * entry_price
    
    st.markdown("---")
    st.subheader("📊 ผลการวิเคราะห์หน้าตัก (Trading Plan)")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(label="💸 ยอมเจ๊งได้สูงสุดในไม้นี้", value=f"${max_risk_amount:,.2f}")
    with c2:
        st.metric(label="🛍️ จำนวนหุ้นสูงสุดที่ควรซื้อ", value=f"{max_shares_to_buy:,.2f} หุ้น")
    with c3:
        st.metric(label="💰 ขนาดเงินทุนที่ต้องใช้ยิง", value=f"${total_position_size:,.2f}")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # สรุปแผนแบบเน้นปฏิบัติ
    st.info(f"""
    💡 **สรุปแผนการเทรด:** 
    - ไม้นี้ถ้านายกดซื้อที่ราคา **${entry_price:,.2f}** ให้กดจำนวน **{max_shares_to_buy:,.2f} หุ้น** (ใช้เงินรวม **${total_position_size:,.2f}**)
    - ถ้าราคาหุ้นผิดทางร่วงลงไปแตะ **${stop_loss_price:,.2f}** (-{risk_per_share_pct:,.2f}%) ให้คัตทิ้งทันที! 
    - นายจะขาดทุนไป **${max_risk_amount:,.2f}** ซึ่งเป็นไปตามกฎ {risk_percent}% ของพอร์ต พอร์ตปลอดภัยไม่ระเบิดแน่นอนเพื่อน!
    """)
