import os
import json
import re
import base64
import importlib.util
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ตรวจสอบการ Import gspread สำหรับจัดการ Google Sheets
try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# ==========================================
# 1. PAGE CONFIGURATION & GLOBAL STYLE
# ==========================================
st.set_page_config(
    page_title="Executive Dashboard - Webull Desk",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

def inject_custom_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            background-color: #08090b !important;
            color: #d1d5db;
        }

        .stApp {
            background-color: #08090b;
        }

        /* HIDE STREAMLIT DEFAULT NAVIGATION */
        [data-testid="stSidebarNav"] {
            display: none !important;
        }

        /* Custom Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #0d0e12 !important;
            border-right: 1px solid #181a20 !important;
        }

        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1rem;
        }

        .sidebar-brand {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.1rem;
            font-weight: 800;
            color: #38bdf8;
            padding: 10px 0px 15px 0px;
            letter-spacing: 1px;
            display: flex;
            align-items: center;
            gap: 8px;
            border-bottom: 1px solid #181a20;
            margin-bottom: 15px;
        }

        div[data-testid="stSidebar"] .stButton > button {
            background-color: #111318;
            color: #9ca3af;
            border: 1px solid #1f232d;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.85rem;
            transition: all 0.2s ease;
            text-align: left;
            padding: 8px 12px;
            margin-bottom: 2px;
        }

        div[data-testid="stSidebar"] .stButton > button:hover {
            border-color: #38bdf8;
            color: #38bdf8;
            background-color: #161a23;
        }

        div[data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: linear-gradient(90deg, #0284c7 0%, #0369a1 100%) !important;
            color: #ffffff !important;
            border: 1px solid #38bdf8 !important;
            box-shadow: 0 4px 12px rgba(56, 189, 248, 0.2);
        }

        div[data-testid="stSidebar"] .streamlit-expanderHeader {
            background-color: #111318 !important;
            border: 1px solid #1f232d !important;
            border-radius: 8px !important;
            color: #e2e8f0 !important;
            font-size: 0.88rem !important;
            font-weight: 700 !important;
            padding: 8px 12px !important;
        }

        div[data-testid="stSidebar"] .streamlit-expanderContent {
            background-color: transparent !important;
            border: none !important;
            padding: 8px 0px 0px 8px !important;
        }

        /* TICKER MARQUEE STYLING (MODERN CARD PILL DESIGN) */
        .ticker-container {
            width: 100%;
            overflow: hidden;
            background-color: #0b0c0e;
            border: 1px solid #181b22;
            border-radius: 12px;
            padding: 10px 0;
            margin-bottom: 25px;
            white-space: nowrap;
        }

        .ticker-track {
            display: inline-flex;
            gap: 16px;
            animation: marquee 35s linear infinite;
        }

        .ticker-container:hover .ticker-track {
            animation-play-state: paused;
        }

        @keyframes marquee {
            0% { transform: translateX(0%); }
            100% { transform: translateX(-50%); }
        }

        .ticker-card-pill {
            background: linear-gradient(145deg, #12151c 0%, #0d0f14 100%);
            border: 1px solid #222733;
            border-radius: 10px;
            padding: 8px 16px;
            font-size: 0.85rem;
            font-family: 'JetBrains Mono', monospace;
            display: inline-flex;
            align-items: center;
            gap: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }

        .ticker-card-symbol { font-weight: 800; color: #ffffff; letter-spacing: 0.5px; }
        .ticker-card-price { color: #e2e8f0; font-weight: 600; }
        .badge-mini-pos { background-color: rgba(34, 197, 94, 0.18); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); padding: 3px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; }
        .badge-mini-neg { background-color: rgba(239, 68, 68, 0.18); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 3px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; }

        .dash-card {
            background-color: #0e1015;
            border: 1px solid #1c202a;
            border-radius: 14px;
            padding: 22px;
            margin-bottom: 15px;
        }

        .card-header-title {
            color: #9ca3af;
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .big-value {
            font-family: 'Plus Jakarta Sans', sans-serif;
            font-size: 2.3rem;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -1px;
            line-height: 1.1;
        }

        .badge-delta-neg { background-color: rgba(239, 68, 68, 0.12); color: #f87171; padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
        .badge-delta-pos { background-color: rgba(34, 197, 94, 0.12); color: #4ade80; padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; }

        .allocation-bar-container {
            display: flex;
            height: 10px;
            border-radius: 5px;
            overflow: hidden;
            margin: 16px 0px;
            background-color: #1a1d24;
        }
        .bar-segment { height: 100%; }

        .asset-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            font-size: 0.88rem;
            border-bottom: 1px solid #161922;
        }
        .asset-label { display: flex; align-items: center; gap: 10px; color: #cbd5e1; }
        .dot { width: 8px; height: 8px; border-radius: 50%; }
        .asset-val { font-family: 'JetBrains Mono', monospace; font-weight: 600; color: #ffffff; }

        .stock-grid-card {
            background-color: #0e1015;
            border: 1px solid #1c202a;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 10px;
        }
        .stock-symbol { font-weight: 800; color: #ffffff; font-size: 0.95rem; }
        .stock-price { font-family: 'JetBrains Mono', monospace; font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-top: 8px; }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ==========================================
# 2. GOOGLE SHEETS DATA PIPELINE
# ==========================================
def get_gspread_client():
    """เชื่อมต่อ Google Sheets API โดยสแกนหา Credentials จาก Secrets ทุกตำแหน่งที่เป็นไปได้"""
    if not HAS_GSPREAD:
        return None
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds_dict = None
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
        elif "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            creds_dict = dict(st.secrets["connections"]["gsheets"])
        elif "type" in st.secrets and st.secrets["type"] == "service_account":
            creds_dict = dict(st.secrets)

        if creds_dict:
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            return gspread.authorize(creds)
    except Exception:
        pass
    return None

def sync_portfolio_snapshot_to_gsheet(market_val, invested_val, pnl_val, pnl_pct):
    """บันทึกแถวใหม่ลงใน Sheet Portfolio_History"""
    client = get_gspread_client()
    if not client:
        return False, "ไม่พบการตั้งค่า Service Account ใน st.secrets"
    
    sheet_title = st.secrets.get("SPREADSHEET_NAME", "")
    if not sheet_title and "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
        sheet_title = st.secrets["connections"]["gsheets"].get("spreadsheet", "")
    if not sheet_title:
        sheet_title = "Webull_Portfolio"

    try:
        try:
            sh = client.open(sheet_title)
        except Exception:
            sh = client.open_by_key(sheet_title) if len(sheet_title) > 20 else client.open_by_url(sheet_title)

        worksheet = sh.worksheet("Portfolio_History")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        new_row = [now_str, round(market_val, 2), round(invested_val, 2), round(pnl_val, 2), f"{pnl_pct:.2f}%"]
        worksheet.append_row(new_row)
        return True, "บันทึกประวัติลง Google Sheets สำเร็จ!"
    except Exception as e:
        return False, f"เชื่อมต่อ Google Sheets ไม่สำเร็จ: {str(e)}"

def load_history_from_gsheet():
    """ดึงข้อมูลประวัติย้อนหลังเพื่อวาดกราฟ"""
    client = get_gspread_client()
    if not client:
        return None
    try:
        sheet_title = st.secrets.get("SPREADSHEET_NAME", "Webull_Portfolio")
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            sheet_title = st.secrets["connections"]["gsheets"].get("spreadsheet", sheet_title)
            
        try:
            sh = client.open(sheet_title)
        except Exception:
            sh = client.open_by_key(sheet_title) if len(sheet_title) > 20 else client.open_by_url(sheet_title)

        worksheet = sh.worksheet("Portfolio_History")
        data = worksheet.get_all_values()
        
        if len(data) > 0:
            df = pd.DataFrame(data)
            first_val = str(df.iloc[0, 0]).strip()
            if not first_val.replace("-", "").replace(":", "").replace(" ", "").isdigit():
                df = df.iloc[1:].reset_index(drop=True)
                
            df.columns = ["Timestamp", "MarketValue", "Invested", "PnL", "PnLPct"][:len(df.columns)]
            
            def clean_num(val):
                if pd.isna(val): return 0.0
                val_str = str(val).replace(",", "").replace("%", "").strip()
                try: return float(val_str)
                except: return 0.0

            df["MarketValue"] = df["MarketValue"].apply(clean_num)
            return df
    except Exception:
        pass
    return None

# ==========================================
# 3. DASHBOARD MAIN RENDER FUNCTION
# ==========================================
def render_dashboard():
    # โชว์ Marquee แถบวิ่งราคาหุ้น Top Holdings ดึงสไตล์ Modern Dark Pill Cards
    sample_stocks = [
        ("NU", 18.48, 18.48), 
        ("SVCO", 7.93, 123.38), 
        ("CV", 6.58, 31.60),
        ("DVLT", 0.34, -86.67), 
        ("SUSCO", 3.85, 5.00), 
        ("YMAG", 15.80, -0.19)
    ]
    
    ticker_cards_html = ""
    for sym, price, pnl in sample_stocks:
        badge_cls = "badge-mini-pos" if pnl >= 0 else "badge-mini-neg"
        sign = "+" if pnl >= 0 else ""
