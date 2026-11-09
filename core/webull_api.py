"""Webull Thailand OpenAPI client.

Docs: https://developer.webull.co.th/apis/docs/
This module has no Streamlit dependency so it can be reused by a future backend API.
"""
import base64
import hashlib
import hmac
import json
import urllib.parse
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

PROD_HOST = "api.webull.co.th"
UAT_HOST = "th-api.uat.webullbroker.com"

# Current (v3) endpoints from the Webull TH reference docs.
PATH_ACCOUNTS = "/trading/accounts/list"
PATH_BALANCE = "/trading/assets/balances/get"
PATH_POSITIONS = "/trading/assets/positions/list"
PATH_SNAPSHOTS = "/market-data/stocks/snapshots/list"
# Legacy v2 endpoint the app used before; kept as a fallback for older app keys.
PATH_POSITIONS_LEGACY = "/openapi/assets/positions"


class WebullAPIError(Exception):
    def __init__(self, status, message, path=""):
        super().__init__(f"[{status}] {path}: {message}")
        self.status = status
        self.path = path


@dataclass
class WebullConfig:
    app_key: str = ""
    app_secret: str = ""
    access_token: str = ""
    account_id: str = ""
    host: str = PROD_HOST

    @classmethod
    def from_mapping(cls, mapping):
        """Build from st.secrets["Webull"] (accepts both CamelCase and snake_case keys)."""
        mapping = mapping or {}

        def pick(*keys):
            for key in keys:
                value = mapping.get(key)
                if value:
                    return str(value).strip()
            return ""

        return cls(
            app_key=pick("AppKey", "app_key"),
            app_secret=pick("AppSecret", "app_secret"),
            access_token=pick("AccessToken", "access_token"),
            account_id=pick("AccountId", "account_id"),
            host=pick("Host", "host") or PROD_HOST,
        )

    @property
    def is_configured(self):
        return bool(self.app_key and self.app_secret)


def build_signature(path, query, body, app_key, app_secret, host, timestamp, nonce,
                    algorithm="HMAC-SHA256"):
    """Signature per https://developer.webull.co.th/apis/docs/authentication/signature"""
    params = {str(k): str(v) for k, v in (query or {}).items()}
    params.update({
        "x-app-key": app_key,
        "x-timestamp": timestamp,
        "x-signature-algorithm": algorithm,
        "x-signature-version": "1.0",
        "x-signature-nonce": nonce,
        "host": host,
    })
    str1 = "&".join(f"{k}={params[k]}" for k in sorted(params))
    use_sha256 = algorithm == "HMAC-SHA256"
    if body:
        body_hash = (hashlib.sha256 if use_sha256 else hashlib.md5)(body.encode("utf-8")).hexdigest().upper()
        str3 = f"{path}&{str1}&{body_hash}"
    else:
        str3 = f"{path}&{str1}"
    encoded = urllib.parse.quote(str3, safe="")
    digest = hmac.new(f"{app_secret}&".encode("utf-8"), encoded.encode("utf-8"),
                      hashlib.sha256 if use_sha256 else hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


def _unwrap(payload):
    if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], (list, dict)):
        return payload["data"]
    return payload


def to_float(value, default=0.0):
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


class WebullClient:
    def __init__(self, config, timeout=10, session=None):
        self.config = config
        self.timeout = timeout
        self.session = session or requests.Session()

    def _request(self, method, path, query=None, body=None, version="v3", algorithm="HMAC-SHA256"):
        cfg = self.config
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        nonce = uuid.uuid4().hex
        body_str = json.dumps(body, separators=(",", ":")) if body else None
        headers = {
            "Accept": "application/json",
            "x-app-key": cfg.app_key,
            "x-timestamp": timestamp,
            "x-signature-algorithm": algorithm,
            "x-signature-version": "1.0",
            "x-signature-nonce": nonce,
            "x-version": version,
            "x-signature": build_signature(path, query, body_str, cfg.app_key, cfg.app_secret,
                                           cfg.host, timestamp, nonce, algorithm),
        }
        if cfg.access_token:
            headers["x-access-token"] = cfg.access_token
        if body_str:
            headers["Content-Type"] = "application/json"

        try:
            resp = self.session.request(method, f"https://{cfg.host}{path}", params=query,
                                        data=body_str, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise WebullAPIError("network", str(exc), path) from exc
        if resp.status_code != 200:
            raise WebullAPIError(resp.status_code, resp.text[:300], path)
        try:
            return _unwrap(resp.json())
        except ValueError as exc:
            raise WebullAPIError(resp.status_code, "invalid JSON response", path) from exc

    # ---- Account -------------------------------------------------------
    def list_accounts(self):
        data = self._request("GET", PATH_ACCOUNTS)
        return data if isinstance(data, list) else []

    def resolve_account_id(self):
        if self.config.account_id:
            return self.config.account_id
        accounts = self.list_accounts()
        if not accounts:
            raise WebullAPIError("no-account", "account list is empty", PATH_ACCOUNTS)
        self.config.account_id = str(accounts[0].get("account_id", ""))
        return self.config.account_id

    def get_balance(self, account_id=None):
        account_id = account_id or self.resolve_account_id()
        data = self._request("GET", PATH_BALANCE, {"account_id": account_id})
        return data if isinstance(data, dict) else {}

    def get_positions(self, account_id=None):
        account_id = account_id or self.resolve_account_id()
        try:
            data = self._request("GET", PATH_POSITIONS, {"account_id": account_id})
        except WebullAPIError as v3_error:
            try:
                data = self._request("GET", PATH_POSITIONS_LEGACY, {"account_id": account_id},
                                     version="v2", algorithm="HMAC-SHA1")
            except WebullAPIError:
                raise v3_error
        return data if isinstance(data, list) else []

    # ---- Market data ---------------------------------------------------
    def get_snapshots(self, symbols, category="US_STOCK"):
        symbols = [s for s in dict.fromkeys(symbols) if s]
        rows = []
        for i in range(0, len(symbols), 100):  # API limit: 100 symbols per call
            data = self._request("GET", PATH_SNAPSHOTS, {
                "symbols": ",".join(symbols[i:i + 100]),
                "category": category,
                "extend_hour_required": "false",
                "overnight_required": "false",
            })
            if isinstance(data, list):
                rows.extend(data)
        return rows


def normalize_positions(positions):
    """Webull position payload -> list of dicts with the dashboard's holding schema."""
    rows = []
    for pos in positions:
        if "OPTION" in str(pos.get("instrument_type", "")).upper():
            continue
        symbol = str(pos.get("symbol", "")).strip().upper()
        qty = to_float(pos.get("quantity"))
        if not symbol or qty <= 0:
            continue
        cost = to_float(pos.get("cost_price"))
        rows.append({
            "Symbol": symbol,
            "Qty": qty,
            "Cost": cost,
            "Price": to_float(pos.get("last_price"), cost),
            "Currency": str(pos.get("currency") or "USD").upper(),
        })
    return rows
