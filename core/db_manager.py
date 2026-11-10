"""SQLite storage for manually recorded Dime trades (built-in sqlite3, no external services)."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path(os.environ.get("PORTFOLIO_DB_PATH", Path(__file__).resolve().parent.parent / "portfolio.db"))

ACCOUNTS = ("Dime TH", "Dime US")
TRADE_TYPES = ("Buy", "Sell")
ACCOUNT_CURRENCY = {"Dime TH": "THB", "Dime US": "USD"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dime_trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT    NOT NULL,
    account_type TEXT    NOT NULL CHECK (account_type IN ('Dime TH', 'Dime US')),
    symbol       TEXT    NOT NULL,
    trade_type   TEXT    NOT NULL CHECK (trade_type IN ('Buy', 'Sell')),
    shares       REAL    NOT NULL CHECK (shares > 0),
    price        REAL    NOT NULL CHECK (price >= 0)
);
CREATE INDEX IF NOT EXISTS idx_dime_trades_account_symbol ON dime_trades (account_type, symbol);
"""

HOLDING_COLUMNS = ["account_type", "symbol", "shares", "avg_cost", "cost_basis", "realized_pnl", "currency"]
# Tolerance for float leftovers from fractional shares.
_EPS = 1e-9


def _connect(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    """Create portfolio.db and the dime_trades table if they don't exist."""
    with closing(_connect(db_path)) as conn, conn:
        conn.executescript(_SCHEMA)


def _normalize_symbol(symbol, account_type):
    symbol = str(symbol or "").strip().upper()
    if account_type == "Dime TH" and symbol.endswith(".BK"):
        symbol = symbol[:-3]
    return symbol


def insert_trade(account_type, trade_type, symbol, shares, price, timestamp=None, db_path=None):
    """Validate and insert one trade. Returns the new row id. Raises ValueError on bad input."""
    if account_type not in ACCOUNTS:
        raise ValueError(f"account_type must be one of {ACCOUNTS}")
    if trade_type not in TRADE_TYPES:
        raise ValueError(f"trade_type must be one of {TRADE_TYPES}")
    symbol = _normalize_symbol(symbol, account_type)
    if not symbol:
        raise ValueError("Symbol is required")
    shares, price = float(shares), float(price)
    if shares <= 0:
        raise ValueError("Shares must be greater than 0")
    if price < 0:
        raise ValueError("Price cannot be negative")

    init_db(db_path)
    if trade_type == "Sell":
        held = get_position_shares(account_type, symbol, db_path)
        if shares > held + _EPS:
            raise ValueError(f"Cannot sell {shares:g} {symbol}: only {held:g} shares held in {account_type}")

    ts = (timestamp or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    with closing(_connect(db_path)) as conn, conn:
        cur = conn.execute(
            "INSERT INTO dime_trades (timestamp, account_type, symbol, trade_type, shares, price) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, account_type, symbol, trade_type, shares, price),
        )
        return cur.lastrowid


def delete_trade(trade_id, db_path=None):
    init_db(db_path)
    with closing(_connect(db_path)) as conn, conn:
        return conn.execute("DELETE FROM dime_trades WHERE id = ?", (int(trade_id),)).rowcount


def fetch_trades(account_type=None, db_path=None):
    init_db(db_path)
    query = "SELECT * FROM dime_trades"
    params = ()
    if account_type:
        query += " WHERE account_type = ?"
        params = (account_type,)
    with closing(_connect(db_path)) as conn:
        df = pd.read_sql_query(query + " ORDER BY timestamp, id", conn, params=params)
    return df


def get_position_shares(account_type, symbol, db_path=None):
    init_db(db_path)
    with closing(_connect(db_path)) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(CASE trade_type WHEN 'Buy' THEN shares ELSE -shares END), 0) "
            "FROM dime_trades WHERE account_type = ? AND symbol = ?",
            (account_type, _normalize_symbol(symbol, account_type)),
        ).fetchone()
    return float(row[0])


def get_holdings(db_path=None):
    """Current holdings per (account, symbol) using the average-cost method.

    Sells reduce shares at the running average cost and book the difference as realized PnL.
    """
    trades = fetch_trades(db_path=db_path)
    positions = {}
    for t in trades.itertuples(index=False):
        key = (t.account_type, t.symbol)
        pos = positions.setdefault(key, {"shares": 0.0, "cost_basis": 0.0, "realized_pnl": 0.0})
        if t.trade_type == "Buy":
            pos["shares"] += t.shares
            pos["cost_basis"] += t.shares * t.price
        else:
            sold = min(t.shares, pos["shares"])
            avg = pos["cost_basis"] / pos["shares"] if pos["shares"] > _EPS else 0.0
            pos["realized_pnl"] += sold * (t.price - avg)
            pos["shares"] -= sold
            pos["cost_basis"] -= sold * avg

    rows = []
    for (account, symbol), pos in positions.items():
        if pos["shares"] <= _EPS:
            continue
        rows.append({
            "account_type": account, "symbol": symbol, "shares": pos["shares"],
            "avg_cost": pos["cost_basis"] / pos["shares"], "cost_basis": pos["cost_basis"],
            "realized_pnl": pos["realized_pnl"], "currency": ACCOUNT_CURRENCY[account],
        })
    return pd.DataFrame(rows, columns=HOLDING_COLUMNS).sort_values(
        ["account_type", "cost_basis"], ascending=[True, False]).reset_index(drop=True)
