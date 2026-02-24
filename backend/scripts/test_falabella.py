#!/usr/bin/env python3
"""
Script para probar conexión a Falabella Seller Center API.
Solo requiere: pip install requests
Uso: cd backend && python3 scripts/test_falabella.py
"""
import sys
import hmac
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

API_URL = "https://sellercenter-api.falabella.com"
USER_ID = "contemplari.cl@gmail.com"
API_KEY = "a1367c78face3914ea933f96ff1113af933ff755"


def rfc3986_encode(s):
    return quote(str(s), safe="-_.~")


def build_signature(parameters, api_key):
    sorted_keys = sorted(parameters.keys())
    pairs = [f"{rfc3986_encode(k)}={rfc3986_encode(parameters[k])}" for k in sorted_keys]
    string_to_sign = "&".join(pairs)
    return hmac.new(
        api_key.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def iso8601_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def get_orders(user_id, api_key, base_url, created_after, limit=30):
    params = {
        "Action": "GetOrders",
        "Format": "JSON",
        "Timestamp": iso8601_timestamp(),
        "UserID": user_id,
        "Version": "1.0",
        "CreatedAfter": created_after,
        "Limit": limit,
    }
    signature = build_signature(params, api_key)
    params["Signature"] = signature
    query_parts = [f"{quote(k)}={quote(str(v), safe='')}" for k, v in sorted(params.items())]
    url = f"{base_url}/?{'&'.join(query_parts)}"
    headers = {"User-Agent": "SELLER/Python/3/INVOICE_MVP/FACL"}
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()


def main():
    since = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT00:00:00+00:00")
    print("Probando GetOrders (created_after = últimos 10 días)...")
    print(f"URL: {API_URL}")
    print(f"User ID: {USER_ID}")
    try:
        data = get_orders(USER_ID, API_KEY, API_URL, since, limit=30)
    except requests.RequestException as e:
        print("ERROR de red:", e)
        if hasattr(e, "response") and e.response is not None:
            try:
                print("Respuesta:", e.response.text[:500])
            except Exception:
                pass
        return 1

    if "SuccessResponse" in data:
        print("OK - Conexión exitosa.")
        body = data.get("SuccessResponse", {}).get("Body") or data.get("SuccessResponse", {})
        orders = (body.get("Orders") or {}).get("Order") or body.get("Order") or []
        if not isinstance(orders, list):
            orders = [orders] if orders else []
        print(f"Órdenes encontradas: {len(orders)}")
        for o in orders[:20]:
            if isinstance(o, dict):
                print(f"  - OrderId: {o.get('OrderId')}, OrderNumber: {o.get('OrderNumber')}, Price: {o.get('Price')}")
        if len(orders) > 20:
            print(f"  ... y {len(orders) - 20} más")
        return 0
    if "ErrorResponse" in data:
        head = data["ErrorResponse"].get("Head", {})
        print("ERROR API:", head.get("ErrorMessage", data))
        print("Código:", head.get("ErrorCode"))
        return 1
    print("Respuesta inesperada:", data)
    return 1


if __name__ == "__main__":
    sys.exit(main())
