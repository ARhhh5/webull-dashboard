"""Fintech dark UI kit: global CSS, KPI cards, broker badges and TradingView-style charts."""
import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

UP, DOWN = "#26a69a", "#ef5350"  # TradingView candle colors
GRID = "#1c2030"
CHART_CONFIG = {"scrollZoom": True, "displaylogo": False,
                "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Sans+Thai:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, select {
    font-family: 'Plus Jakarta Sans', 'IBM Plex Sans Thai', sans-serif !important;
}
.stApp { background: radial-gradient(1200px 600px at 10% -10%, rgba(56,189,248,0.06), transparent 60%), #0E1117; }
.block-container { padding-top: 3.2rem; padding-bottom: 3rem; max-width: 1600px; }
#MainMenu, footer { visibility: hidden; }
[data-testid="stSidebarNav"] { display: none !important; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background-color: #0b0d12 !important; border-right: 1px solid #1a1e29 !important; }
.sidebar-brand {
    font-family: 'JetBrains Mono', monospace; font-size: 1.05rem; font-weight: 800; color: #38bdf8;
    padding: 6px 0 14px 0; letter-spacing: 1px; border-bottom: 1px solid #1a1e29; margin-bottom: 14px;
}
.sidebar-brand small { display:block; color:#64748b; font-size:0.68rem; font-weight:500; letter-spacing:0; margin-top:2px; }
div[data-testid="stSidebar"] .stButton > button {
    background-color: transparent; color: #9ca3af; border: 1px solid transparent; border-radius: 8px;
    font-weight: 600; font-size: 0.85rem; justify-content: flex-start; padding: 6px 10px; transition: all .15s ease;
}
div[data-testid="stSidebar"] .stButton > button:hover { background-color: #141823; color: #e2e8f0; border-color: #1f2533; }
div[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: linear-gradient(90deg, rgba(2,132,199,.35), rgba(2,132,199,.08)) !important;
    color: #fff !important; border: 1px solid rgba(56,189,248,.45) !important;
}
div[data-testid="stSidebar"] [data-testid="stExpander"] details { border: 1px solid #1a1e29; border-radius: 10px; background:#0e1118; }

/* ---------- Floating cards ---------- */
/* card() containers get a "st-key-card-*" class from their key */
div[class*="st-key-card-"],
.card {
    background: linear-gradient(180deg, #161a24 0%, #131722 100%);
    border: 1px solid #222838 !important; border-radius: 14px !important;
    box-shadow: 0 8px 24px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.03);
}
.card { padding: 18px 20px; margin-bottom: 14px; }
div[class*="st-key-card-"] { padding: 16px 18px; }
.card-title { color:#9ca3af; font-size:.8rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
    display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }

/* ---------- st.metric as KPI cards ---------- */
[data-testid="stMetric"] {
    background: linear-gradient(180deg, #161a24 0%, #131722 100%); border: 1px solid #222838; border-radius: 14px;
    padding: 14px 18px; box-shadow: 0 8px 24px rgba(0,0,0,.35);
}
[data-testid="stMetricLabel"] p { color:#8b93a7 !important; font-size:.78rem !important; font-weight:700 !important; letter-spacing:.04em; text-transform: uppercase; }
[data-testid="stMetricValue"] { font-family:'JetBrains Mono', monospace !important; font-weight:700; font-size:1.65rem !important; color:#f8fafc; }
[data-testid="stMetricDelta"] { font-family:'JetBrains Mono', monospace !important; font-weight:600; }

/* ---------- Header / chips ---------- */
.page-title { font-size: 1.7rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px; line-height:1.1; }
.page-sub { color: #64748b; font-size: .85rem; margin-top: 4px; }
.chip { display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:999px; font-size:.72rem; font-weight:700;
    border:1px solid #232a3a; background:#121620; color:#cbd5e1; margin-right:6px; white-space:nowrap; }
.chip .dot { width:7px; height:7px; border-radius:50%; display:inline-block; }
.broker-badge { display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:6px; font-size:.75rem; font-weight:800; }
.demo-banner { background: rgba(250,204,21,.08); border:1px solid rgba(250,204,21,.35); color:#fde68a; padding:8px 14px;
    border-radius:10px; font-size:.82rem; margin-bottom:12px; }

/* ---------- Ticker tape ---------- */
.ticker-container { width:100%; overflow:hidden; background:#0b0d12; border:1px solid #1a1e29; border-radius:10px; padding:7px 0; margin:6px 0 16px 0; white-space:nowrap; }
.ticker-track { display:inline-flex; gap:10px; animation: marquee 40s linear infinite; }
.ticker-container:hover .ticker-track { animation-play-state: paused; }
@keyframes marquee { 0% { transform: translateX(0%);} 100% { transform: translateX(-50%);} }
.ticker-pill { background:#121620; border:1px solid #1f2533; border-radius:8px; padding:5px 12px; font-size:.8rem;
    font-family:'JetBrains Mono', monospace; display:inline-flex; align-items:center; gap:10px; }
.ticker-pill b { color:#fff; }
.pos { color:#26a69a; } .neg { color:#ef5350; }
.badge-pos { background: rgba(38,166,154,.15); color:#4fd1c5; padding:2px 7px; border-radius:5px; font-weight:700; font-size:.74rem; font-family:'JetBrains Mono', monospace; }
.badge-neg { background: rgba(239,83,80,.15); color:#f87171; padding:2px 7px; border-radius:5px; font-weight:700; font-size:.74rem; font-family:'JetBrains Mono', monospace; }

/* ---------- Rows inside cards ---------- */
.row { display:flex; justify-content:space-between; align-items:center; padding:9px 0; font-size:.86rem; border-bottom:1px solid #1c2130; }
.row:last-child { border-bottom:none; }
.row .lbl { display:flex; align-items:center; gap:10px; color:#cbd5e1; }
.row .val { font-family:'JetBrains Mono', monospace; font-weight:600; color:#fff; text-align:right; }
.row .sub { color:#64748b; font-size:.72rem; }
.alloc-bar { display:flex; height:8px; border-radius:4px; overflow:hidden; margin:10px 0 6px 0; background:#1a1d24; }
.big-value { font-family:'JetBrains Mono', monospace; font-size:2rem; font-weight:700; color:#fff; letter-spacing:-1px; }

/* ---------- Widgets ---------- */
[data-testid="stDataFrame"] { border:1px solid #222838; border-radius:12px; overflow:hidden; }
div[data-baseweb="select"] > div { background-color:#121620; border-color:#232a3a; }
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] { background:#121620; border:1px solid #1f2533; border-radius:8px; padding:6px 14px; }
.stTabs [aria-selected="true"] { background:rgba(56,189,248,.12); border-color:rgba(56,189,248,.5); }
</style>
"""


def inject_theme():
    st.markdown(CSS, unsafe_allow_html=True)


def fmt_money(value, symbol="$", signed=False, decimals=2):
    sign = ("+" if value >= 0 else "-") if signed else ("-" if value < 0 else "")
    return f"{sign}{symbol}{abs(value):,.{decimals}f}"


def pct_badge(pct):
    cls = "badge-pos" if pct >= 0 else "badge-neg"
    return f'<span class="{cls}">{pct:+.2f}%</span>'


def broker_badge(broker, meta):
    color = meta["color"]
    return (f'<span class="broker-badge" style="background:{color}22;color:{color};border:1px solid {color}55">'
            f'{meta["icon"]} {broker}</span>')


def status_chip(label, ok, detail=""):
    color = "#26a69a" if ok else "#64748b"
    title = f' title="{html.escape(detail)}"' if detail else ""
    return f'<span class="chip"{title}><span class="dot" style="background:{color}"></span>{label}</span>'


def card(name, title=None, right_html=""):
    """Floating card container; use as `with card("x", "Title"):`."""
    box = st.container(key=f"card-{name}")
    if title:
        box.markdown(f'<div class="card-title"><span>{title}</span>{right_html}</div>', unsafe_allow_html=True)
    return box


def page_header(title, subtitle=""):
    st.markdown(f'<div class="page-title">{title}</div><div class="page-sub">{subtitle}</div>', unsafe_allow_html=True)


def ticker_tape(df):
    """df with Symbol, Price, DayChange_Pct, Currency."""
    if df.empty:
        return
    pills = ""
    for _, r in df.iterrows():
        cur = "฿" if r["Currency"] == "THB" else "$"
        pills += (f'<div class="ticker-pill"><b>{r["Symbol"]}</b><span>{cur}{r["Price"]:,.2f}</span>'
                  f'{pct_badge(r["DayChange_Pct"])}</div>')
    st.markdown(f'<div class="ticker-container"><div class="ticker-track">{pills}{pills}</div></div>',
                unsafe_allow_html=True)


def _base_layout(fig, height):
    fig.update_layout(
        template="plotly_dark", height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#8b93a7", family="Plus Jakarta Sans, sans-serif", size=11),
        margin=dict(t=10, b=10, l=10, r=10), hovermode="x unified", dragmode="pan",
        hoverlabel=dict(bgcolor="#1e222d", bordercolor="#2a2e39", font=dict(color="#e2e8f0")),
        legend=dict(orientation="h", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID, zeroline=False, showspikes=True, spikemode="across",
                     spikethickness=1, spikedash="dot", spikecolor="#64748b", rangeslider_visible=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, side="right", showspikes=True,
                     spikethickness=1, spikedash="dot", spikecolor="#64748b")
    return fig


def candlestick_chart(ohlc, height=460, sma=(20, 50), currency="$"):
    """TradingView-style candles + volume + SMA overlays. ohlc: DataFrame[Open, High, Low, Close, Volume]."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22], vertical_spacing=0.02)
    fig.add_trace(go.Candlestick(
        x=ohlc.index, open=ohlc["Open"], high=ohlc["High"], low=ohlc["Low"], close=ohlc["Close"], name="Price",
        increasing=dict(line=dict(color=UP), fillcolor=UP), decreasing=dict(line=dict(color=DOWN), fillcolor=DOWN),
    ), row=1, col=1)
    for n, color in zip(sma, ("#f59e0b", "#a78bfa", "#38bdf8")):
        if len(ohlc) >= n:
            fig.add_trace(go.Scatter(x=ohlc.index, y=ohlc["Close"].rolling(n).mean(), name=f"SMA {n}",
                                     line=dict(color=color, width=1.3), hoverinfo="skip"), row=1, col=1)
    vol_colors = [UP if c >= o else DOWN for o, c in zip(ohlc["Open"], ohlc["Close"])]
    fig.add_trace(go.Bar(x=ohlc.index, y=ohlc["Volume"], marker_color=vol_colors, opacity=0.5, name="Volume",
                         showlegend=False), row=2, col=1)
    _base_layout(fig, height)
    fig.update_yaxes(tickprefix=currency, row=1, col=1)
    fig.update_yaxes(showticklabels=False, row=2, col=1)
    # Hide weekends so candles sit side by side like TradingView.
    if len(ohlc) > 1 and (ohlc.index[1] - ohlc.index[0]) >= pd.Timedelta(days=1):
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    return fig


def area_chart(x, y, height=300, prefix="$"):
    up = len(y) < 2 or y[-1] >= y[0]
    color = UP if up else DOWN
    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="lines", line=dict(color=color, width=2.2), fill="tozeroy",
        fillcolor="rgba(38,166,154,0.10)" if up else "rgba(239,83,80,0.10)",
        hovertemplate=f"%{{x|%Y-%m-%d %H:%M}}<br>{prefix}%{{y:,.2f}}<extra></extra>",
    ))
    _base_layout(fig, height)
    if len(y):
        lo, hi = min(y), max(y)
        pad = (hi - lo) * 0.15 or hi * 0.05 or 1
        fig.update_yaxes(range=[lo - pad, hi + pad], tickprefix=prefix)
    fig.update_layout(hovermode="x")
    return fig


def bar_chart(labels, values, height=300, prefix="$"):
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h", marker=dict(color="#38bdf8", opacity=0.85),
        hovertemplate=f"<b>%{{y}}</b><br>{prefix}%{{x:,.2f}}<extra></extra>",
    ))
    _base_layout(fig, height)
    fig.update_layout(hovermode="closest", dragmode=False)
    fig.update_xaxes(tickprefix=prefix, showspikes=False)
    fig.update_yaxes(side="left", showspikes=False, showgrid=False)
    return fig


def donut_chart(labels, values, colors, height=260, prefix="$"):
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.68, sort=False, textinfo="percent",
        marker=dict(colors=colors, line=dict(color="#131722", width=2)),
        hovertemplate=f"<b>%{{label}}</b><br>{prefix}%{{value:,.2f}}<br>%{{percent}}<extra></extra>",
    ))
    fig.update_layout(height=height, paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=5, b=5, l=5, r=5),
                      font=dict(color="#8b93a7", family="Plus Jakarta Sans"), showlegend=False)
    return fig


def show_chart(fig):
    st.plotly_chart(fig, width="stretch", theme=None, config=CHART_CONFIG)


def pnl_style(val):
    try:
        num = float(val)
    except (TypeError, ValueError):
        return ""
    if num > 0:
        return "color: #26a69a; font-weight: 700;"
    if num < 0:
        return "color: #ef5350; font-weight: 700;"
    return "color: #9ca3af;"
