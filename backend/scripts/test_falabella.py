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


def _get_documento_estado_by_order(orders):
    """Si hay DB, devuelve dict id_venta -> documento_estado (Por emitir | Emitido | Cargado)."""
    try:
        import os
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        os.chdir(backend_dir)
        from app import create_app
        from app.models import Sale, User
        app = create_app()
        with app.app_context():
            user = User.query.filter_by(falabella_user_id=USER_ID).first()
            if not user:
                return {}
            out = {}
            for o in orders:
                if not isinstance(o, dict):
                    continue
                id_venta = str(o.get("OrderId", ""))
                sale = Sale.query.filter_by(user_id=user.id, id_venta=id_venta).first()
                if not sale:
                    out[id_venta] = "Por emitir"
                elif getattr(sale, "document_uploaded_at", None):
                    out[id_venta] = "Cargado"
                elif sale.status == "Éxito":
                    out[id_venta] = "Emitido"
                else:
                    out[id_venta] = "Por emitir"
            return out
    except Exception:
        return {}


def _falabella_documento_cargado(orders, user_id, api_key, base_url):
    """
    Primera comprobación: ¿en Falabella ya existe un documento cargado para cada orden?
    Devuelve dict id_venta -> True si ya está cargado en Falabella, no reemitir.
    - Llama a la API (GetInvoice si existe).
    - Opcional: FALABELLA_ORDER_IDS_CARGADOS=1143359769,1143487176 marca esos OrderIds como cargados (p. ej. cuando la API no expone GetInvoice).
    """
    import os
    out = {}
    # Órdenes que se saben ya cargadas en Falabella (evitar reemitir)
    env_ids = os.environ.get("FALABELLA_ORDER_IDS_CARGADOS", "").strip()
    if env_ids:
        for id_venta in env_ids.replace(",", " ").split():
            id_venta = id_venta.strip()
            if id_venta:
                out[id_venta] = True
    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        os.chdir(backend_dir)
        from app.services.falabella_client import FalabellaClient
        client = FalabellaClient(user_id, api_key, base_url)
        for o in orders:
            if not isinstance(o, dict):
                continue
            id_venta = str(o.get("OrderId", ""))
            if not id_venta or id_venta in out:
                continue
            if client.invoice_uploaded(id_venta) is True:
                out[id_venta] = True
        return out
    except Exception:
        return out


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
        # Primera comprobación: ¿ya existe documento cargado en Falabella? (evita reemitir)
        falabella_cargado = _falabella_documento_cargado(orders[:20], USER_ID, API_KEY, API_URL)
        # Estado desde nuestra DB (Emitido / Por emitir / Cargado por nosotros)
        doc_estados = _get_documento_estado_by_order(orders)
        if doc_estados:
            print("(Estado Documento: 1º Falabella cargado, 2º base de datos local)")
        # Mostrar campos disponibles en la primera orden (para debug)
        if orders and isinstance(orders[0], dict):
            print("Campos en la respuesta:", list(orders[0].keys()))
        # Tabla: Plataforma | ID Orden (32...) | ID Venta | Fecha doc. | Monto | Estado (orden) | Documento
        print()
        print(f"{'Plataforma':<12} | {'ID Orden':<12} | {'ID Venta':<12} | {'Fecha doc.':<12} | {'Monto':>10} | {'Estado (orden)':<14} | Documento")
        print("-" * 100)
        for o in orders[:20]:
            if isinstance(o, dict):
                platform = "Falabella"
                id_orden = str(o.get("OrderNumber", ""))  # Número que comienza con 32
                id_venta = str(o.get("OrderId", ""))
                raw_date = o.get("CreatedAt") or o.get("OrderDate") or o.get("CreatedDate") or o.get("Date")
                if raw_date:
                    try:
                        s = str(raw_date)
                        if "T" in s:
                            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                        else:
                            dt = datetime.strptime(s[:10], "%Y-%m-%d")
                        fecha_doc = dt.strftime("%Y-%m-%d")
                    except Exception:
                        fecha_doc = str(raw_date)[:10] if raw_date else "—"
                else:
                    fecha_doc = "—"
                monto = o.get("Price")
                monto_str = f"${float(monto):,.0f}" if monto is not None else "—"
                raw_status = o.get("Status") or o.get("OrderStatus") or o.get("Statuses")
                if isinstance(raw_status, list) and raw_status:
                    first = raw_status[0]
                    estado_orden = first.get("Status", first) if isinstance(first, dict) else str(first)
                    if len(raw_status) > 1:
                        estado_orden = str(estado_orden) + f" (+{len(raw_status)-1})"
                elif isinstance(raw_status, dict):
                    estado_orden = raw_status.get("Status", list(raw_status.values())[0] if raw_status else "—")
                else:
                    estado_orden = str(raw_status) if raw_status is not None else "—"
                estado_orden = (estado_orden or "—")[:14]
                # Lo primero: si en Falabella ya hay documento cargado → Cargado (no reemitir)
                if falabella_cargado.get(id_venta):
                    documento = "Cargado"
                else:
                    documento = doc_estados.get(id_venta, "Por emitir")
                print(f"{platform:<12} | {id_orden:<12} | {id_venta:<12} | {fecha_doc:<12} | {monto_str:>10} | {estado_orden:<14} | {documento}")
        if len(orders) > 20:
            print(f"  ... y {len(orders) - 20} más")
        print()
        print("Documento: 1º Si en Falabella ya está cargado → Cargado (no reemitir). 2º Si no: Por emitir | Emitido | Cargado (subido por nuestra plataforma).")
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
