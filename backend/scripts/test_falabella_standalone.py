import requests
import hmac
import hashlib
import os
import json
import logging
from datetime import datetime, timezone
from urllib.parse import quote
from typing import Dict, Any, Optional

# Configurar logging básico
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# URL oficial Falabella Seller Center
DEFAULT_BASE_URL = "https://sellercenter-api.falabella.com"

def _rfc3986_encode(s: str) -> str:
    """Codificación tipo RFC 3986 para nombres y valores en la firma."""
    return quote(str(s), safe="-_.~")

def _build_signature(parameters: Dict[str, str], api_key: str) -> str:
    """
    Firma HMAC-SHA256 del string de parámetros (orden alfabético, name=value con &).
    """
    sorted_keys = sorted(parameters.keys())
    pairs = [f"{_rfc3986_encode(k)}={_rfc3986_encode(parameters[k])}" for k in sorted_keys]
    string_to_sign = "&".join(pairs)
    sig = hmac.new(
        api_key.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return sig

def _iso8601_timestamp() -> str:
    """Timestamp en formato ISO 8601 UTC para la API."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

class SimpleFalabellaClient:
    def __init__(self, user_id: str, api_key: str):
        self.user_id = user_id.strip()
        self.api_key = api_key
        self.base_url = DEFAULT_BASE_URL.rstrip("/")
        self.user_agent = "SELLER/Python/3/TEST_SCRIPT/FACL"

    def _request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Preparar parámetros para firma
        str_params = {}
        for k, v in params.items():
            if v is None: continue
            if isinstance(v, list):
                str_params[k] = ",".join(str(x) for x in v)
            else:
                str_params[k] = str(v)

        signature = _build_signature(str_params, self.api_key)
        str_params["Signature"] = signature

        # Construir query string
        query_parts = []
        for k in sorted(str_params.keys()):
            v = str_params[k]
            if k == "Signature":
                query_parts.append(f"Signature={quote(signature, safe='')}")
                continue
            if k in params and isinstance(params[k], list):
                for item in params[k]:
                    query_parts.append(f"{quote(k)}={quote(str(item), safe='')}")
            else:
                query_parts.append(f"{quote(k)}={quote(str(v), safe='')}")
        query_string = "&".join(query_parts)

        url = f"{self.base_url}/?{query_string}"
        headers = {"User-Agent": self.user_agent}

        print(f"Llamando a: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error HTTP: {e}")
            if 'resp' in locals() and resp.content:
                try:
                    return resp.json()
                except:
                    return {"error_text": resp.text}
            return {"error": str(e)}

    def get_orders(self, created_after: str) -> Dict[str, Any]:
        params = {
            "Action": "GetOrders",
            "Format": "JSON",
            "Timestamp": _iso8601_timestamp(),
            "UserID": self.user_id,
            "Version": "1.0",
            "CreatedAfter": created_after,
            "Limit": "10"
        }
        return self._request(params)

def _orders_to_table(result: Dict[str, Any]) -> str:
    """Convierte la respuesta GetOrders en una tabla de texto."""
    try:
        body = result.get("SuccessResponse", {}).get("Body", {})
        orders_data = body.get("Orders", {})
        orders = orders_data.get("Order", [])
        if not orders:
            return "No hay órdenes."
        if isinstance(orders, dict):
            orders = [orders]
        total = result.get("SuccessResponse", {}).get("Head", {}).get("TotalCount", str(len(orders)))
    except Exception:
        return "No se pudo parsear la respuesta."

    # Cabeceras y anchos
    cols = [
        ("OrderId", 12),
        ("OrderNumber", 12),
        ("CreatedAt", 19),
        ("Status", 12),
        ("GrandTotal", 12),
        ("Cliente", 25),
    ]
    sep = "+" + "+".join("-" * (w + 2) for _, w in cols) + "+"
    head = "|" + "|".join(f" {c[0].ljust(c[1])} " for c in cols) + "|"

    lines = [sep, head, sep]
    for o in orders:
        statuses = o.get("Statuses") or {}
        status = statuses.get("Status", "") if isinstance(statuses, dict) else str(statuses)
        cliente = (o.get("CustomerFirstName", "") or "") + " " + (o.get("CustomerLastName", "") or "")
        cliente = (cliente[:23] + "..") if len(cliente) > 25 else cliente
        row = [
            str(o.get("OrderId", ""))[:12].ljust(12),
            str(o.get("OrderNumber", ""))[:12].ljust(12),
            str(o.get("CreatedAt", ""))[:19].ljust(19),
            str(status)[:12].ljust(12),
            str(o.get("GrandTotal", ""))[:12].ljust(12),
            cliente[:25].ljust(25),
        ]
        lines.append("|" + "|".join(f" {c} " for c in row) + "|")
    lines.append(sep)
    lines.append(f"Total órdenes: {total}")
    return "\n".join(lines)


def main():
    user_id = os.environ.get("FALABELLA_USER_ID")
    api_key = os.environ.get("FALABELLA_API_KEY")

    if not user_id or not api_key:
        print("Falta FALABELLA_USER_ID o FALABELLA_API_KEY en variables de entorno.")
        return

    client = SimpleFalabellaClient(user_id, api_key)

    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00+00:00")

    print(f"Consultando órdenes creadas después de: {since}\n")
    result = client.get_orders(created_after=since)

    if "SuccessResponse" in result:
        print(_orders_to_table(result))
    else:
        print("Respuesta (error o formato inesperado):")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
