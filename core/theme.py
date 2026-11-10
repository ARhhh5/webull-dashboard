"""Shared dark fintech styling and Plotly defaults."""
import streamlit as st

UP, DOWN = "#22c55e", "#ef4444"
ACCENT = "#38bdf8"
PALETTE = ["#38bdf8", "#818cf8", "#a78bfa", "#f472b6", "#fb923c", "#facc15",
           "#4ade80", "#2dd4bf", "#60a5fa", "#e879f9", "#94a3b8"]
PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');
html, body, .stApp, .stMarkdown, button, input { font-family: 'Inter', sans-serif !important; }
.stApp { background: radial-gradient(1100px 520px at 0% -10%, rgba(56,189,248,.08), transparent 60%), #0E1117; }
.block-container { padding-top: 2.6rem; max-width: 1500px; }
#MainMenu, footer { visibility: hidden; }

[data-testid="stSidebar"] { background: #0b0d12; border-right: 1px solid #1c2130; }

[data-testid="stMetric"] {
    background: linear-gradient(180deg, #171b26 0%, #131722 100%);
    border: 1px solid #232a3b; border-radius: 16px; padding: 16px 20px;
    box-shadow: 0 10px 30px rgba(0,0,0,.35);
}
[data-testid="stMetricLabel"] p { color: #8b93a7 !important; font-size: .78rem !important;
    font-weight: 700 !important; letter-spacing: .05em; text-transform: uppercase; }
[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; font-weight: 700;
    font-size: 1.7rem !important; color: #f8fafc; }

div[class*="st-key-card-"] {
    background: linear-gradient(180deg, #171b26 0%, #131722 100%);
    border: 1px solid #232a3b; border-radius: 16px; padding: 16px 18px;
    box-shadow: 0 10px 30px rgba(0,0,0,.35);
}
.card-title { color: #cbd5e1; font-weight: 700; font-size: .95rem; margin-bottom: 2px; }
.card-sub { color: #64748b; font-size: .78rem; }
.hero-title { font-size: 1.9rem; font-weight: 800; color: #f8fafc; letter-spacing: -.5px; line-height: 1.1; }
.hero-sub { color: #64748b; font-size: .88rem; margin-top: 4px; }
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px;
    font-size: .72rem; font-weight: 700; border: 1px solid #263044; background: #121620; color: #cbd5e1; }
.pill .dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
[data-testid="stDataFrame"] { border: 1px solid #232a3b; border-radius: 12px; overflow: hidden; }
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def card(name, title, subtitle=""):
    box = st.container(key=f"card-{name}")
    box.markdown(f'<div class="card-title">{title}</div><div class="card-sub">{subtitle}</div>',
                 unsafe_allow_html=True)
    return box


def style_fig(fig, height=360):
    fig.update_layout(
        template="plotly_dark", height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#9ca3af", size=12),
        margin=dict(t=10, b=10, l=10, r=10),
        hoverlabel=dict(bgcolor="#1e222d", bordercolor="#2a2e39", font=dict(color="#e2e8f0")),
    )
    fig.update_xaxes(gridcolor="#1c2130", zeroline=False)
    fig.update_yaxes(gridcolor="#1c2130", zeroline=False)
    return fig
