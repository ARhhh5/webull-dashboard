"""Base-currency (USD) conversion with an explicit FX source and timestamp.

Calculations convert into USD exactly once via to_usd(). Display in another currency goes through
from_usd() at render time only, so switching the display never feeds back into calculations.
"""
import math
from dataclasses import dataclass
from datetime import datetime, timezone

import streamlit as st

BASE_CURRENCY = "USD"
SYMBOLS = {"USD": "$", "THB": "฿"}
YAHOO_SOURCE = "Yahoo Finance THB=X"
ESTIMATED_SOURCE = "Estimated FX (Webull account total ÷ Σ position market value)"


@dataclass(frozen=True)
class FxRate:
    """USD/THB quote: THB per 1 USD."""
    rate: float
    source: str
    as_of: datetime
    estimated: bool = False

    def label(self, tz=None):
        when = self.as_of.astimezone(tz) if tz else self.as_of
        prefix = "Estimated FX " if self.estimated else ""
        return f"{prefix}USD/THB {self.rate:,.4f} · {self.source} · {when:%Y-%m-%d %H:%M %Z}"


def _valid(x):
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def fetch_usd_thb():
    """Latest USD/THB from Yahoo Finance with the bar's own timestamp, or None if unavailable."""
    try:
        import yfinance as yf

        hist = yf.Ticker("THB=X").history(period="5d", interval="1h")
        closes = hist["Close"].dropna()
        if closes.empty:
            return None
        rate, ts = float(closes.iloc[-1]), closes.index[-1]
    except Exception:
        return None
    if not _valid(rate) or rate <= 0:
        return None
    ts = ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")
    return FxRate(rate=rate, source=YAHOO_SOURCE, as_of=ts.to_pydatetime())


@st.cache_data(ttl=900, show_spinner=False)
def get_usd_thb():
    return fetch_usd_thb()


def estimate_fx(account_amount, account_currency, usd_amount, as_of=None):
    """Fallback only: implied THB/USD from an account total and the same holdings valued in USD."""
    if (account_currency or "").upper() != "THB" or not _valid(account_amount) or not _valid(usd_amount):
        return None
    if account_amount <= 0 or usd_amount <= 0:
        return None
    return FxRate(rate=account_amount / usd_amount, source=ESTIMATED_SOURCE,
                  as_of=as_of or datetime.now(timezone.utc), estimated=True)


def to_usd(amount, currency, fx):
    """Convert an amount into USD once. Returns None when the currency or FX is unknown (never assumes USD)."""
    if amount is None or (isinstance(amount, float) and math.isnan(amount)):
        return None
    ccy = (currency or "").upper()
    if ccy == "USD":
        return float(amount)
    if ccy == "THB" and fx is not None:
        return float(amount) / fx.rate
    return None


def usd_factor(currency, fx):
    """Multiplier from `currency` to USD, or None when unknown."""
    return to_usd(1.0, currency, fx)


def from_usd(amount_usd, display_currency, fx):
    """Presentation only: USD amount in the display currency, or None when FX is missing."""
    if amount_usd is None:
        return None
    if display_currency == "USD":
        return amount_usd
    if display_currency == "THB" and fx is not None:
        return amount_usd * fx.rate
    return None


FALLBACK_USD_THB = 35.0
FALLBACK_SOURCE = "Fallback constant (no live quote)"


def rate_or_fallback(rate, now=None):
    """`rate` if available, else a labelled estimated constant so display still works without a live quote."""
    if rate is not None:
        return rate
    return FxRate(rate=FALLBACK_USD_THB, source=FALLBACK_SOURCE, as_of=now or datetime.now(timezone.utc),
                  estimated=True)
