import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# Global Style Injection (Ensure Page Theme Consistency)
st.set_page_config(page_title="Portfolio - Webull Pro", layout="wide")

st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #0d0f12 !important;
        color: #e2e8f0;
    }
    .stApp { background-color: #0d0f12; }
    [data-testid="stSidebar"] { background-color: #131722 !important; border-right: 1px solid #1e222d; }
</style>
""", unsafe_allow_html=True)

st.title("💼 Portfolio Breakdown")
st.caption("สรุปสัดส่วนสินทรัพย์และการเติบโตของพอร์ตการลงทุน")

# Layout Column
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("Asset Allocation")
    
    # Donut Chart for Portfolio Allocation
    labels = ['Stocks', 'Crypto', 'Bonds', 'Cash']
    values = [65, 20, 10, 5]
    colors = ['#6366f1', '#a855f7', '#3b82f6', '#10b981']

    fig_donut = go.Figure(data=[go.Pie(
        labels=labels, 
        values=values, 
        hole=.6,
        marker=dict(colors=colors),
        textinfo='label+percent',
        textfont_size=12,
        insidetextorientation='radial'
    )])
    
    fig_donut.update_layout(
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#ffffff'),
        margin=dict(t=20, b=20, l=20, r=20),
        height=320
    )
    
    st.plotly_chart(fig_donut, use_container_width=True)

with col_right:
    st.subheader("Portfolio Growth Trend")
    
    # Line Chart Trend
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    portfolio_values = [280000, 295000, 290000, 310000, 318000, 325980]
    
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=months, 
        y=portfolio_values,
        mode='lines+markers',
        line=dict(color='#6366f1', width=3, shape='spline'),
        fill='tozeroy',
        fillcolor='rgba(99, 102, 241, 0.1)'
    ))
    
    fig_line.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#8b949e'),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor='#1e222d', zeroline=False),
        margin=dict(t=20, b=20, l=10, r=10),
        height=320
    )
    
    st.plotly_chart(fig_line, use_container_width=True)

st.divider()

# Holdings Table Section
st.subheader("Current Holdings")

data = {
    "Symbol": ["AAPL", "NVDA", "MSFT", "TSLA", "BTC-USD"],
    "Asset Name": ["Apple Inc.", "NVIDIA Corp.", "Microsoft Corp.", "Tesla Inc.", "Bitcoin"],
    "Shares": [150, 45, 80, 60, 0.85],
    "Avg Price": ["$165.00", "$420.00", "$380.00", "$240.00", "$52,000.00"],
    "Current Price": ["$182.50", "$875.20", "$420.10", "$215.30", "$64,200.00"],
    "Profit / Loss": ["+$2,625.00", "+$20,484.00", "+$3,208.00", "-$1,482.00", "+$10,370.00"],
    "Return (%)": ["+10.6%", "+108.3%", "+10.5%", "-10.2%", "+23.4%"]
}

df = pd.DataFrame(data)
st.dataframe(df, use_container_width=True, hide_index=True)
