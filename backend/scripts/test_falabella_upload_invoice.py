#!/usr/bin/env python3
"""
Prueba de subida de documento tributario (SetInvoicePDF) a Falabella.

Requisitos:
  - Orden en estado ready_to_ship (o superior).
  - Orden FBS (Fulfilled by Seller), no Own Warehouse.
  - PDF de boleta/factura real; número y fecha deben coincidir con el documento.

Uso:
  cd backend
  python3 scripts/test_falabella_upload_invoice.py \\
    --order-id 1140726828 \\
    --pdf ruta/a/boleta.pdf \\
    --invoice-number 12345 \\
    --invoice-date 2025-02-20 \\
    [--invoice-type BOLETA] \\
    [--operator-code FACL]

Variables de entorno (opcional): FALABELLA_USER_ID, FALABELLA_API_KEY
"""
import argparse
import base64
import hmac
import hashlib
import os
import sys
from datetime import datetime, timezone
from urllib.parse import quote

import requests

API_URL = os.environ.get("FALABELLA_API_URL", "https://sellercenter-api.falabella.com")
USER_ID = os.environ.get("FALABELLA_USER_ID", "contemplari.cl@gmail.com")
API_KEY = os.environ.get("FALABELLA_API_KEY", "a1367c78face3914ea933f96ff1113af933ff755")


def rfc3986(s):
    return quote(str(s), safe="-_.~")


def sign_params(params, api_key):
    sorted_keys = sorted(params.keys())
    s = "&".join(f"{rfc3986(k)}={rfc3986(params[k])}" for k in sorted_keys)
    return hmac.new(api_key.encode("utf-8"), s.encode("utf-8"), hashlib.sha256).hexdigest()


def iso_ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def get_order_items(order_id):
    """GetOrderItems para obtener OrderItemIds de la orden."""
    params = {
        "Action": "GetOrderItems",
        "Format": "JSON",
        "Timestamp": iso_ts(),
        "UserID": USER_ID,
        "Version": "1.0",
        "OrderId": str(order_id),
    }
    params["Signature"] = sign_params(params, API_KEY)
    qs = "&".join(f"{quote(k)}={quote(str(v), safe='')}" for k, v in sorted(params.items()))
    url = f"{API_URL.rstrip('/')}/?{qs}"
    r = requests.get(url, headers={"User-Agent": "SELLER/Python/3/INVOICE_MVP/FACL"}, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "ErrorResponse" in data:
        head = data["ErrorResponse"].get("Head", {})
        raise RuntimeError(head.get("ErrorMessage", data))
    body = data.get("SuccessResponse", {}).get("Body") or data.get("SuccessResponse", {})
    items = (body.get("OrderItems") or {}).get("OrderItem") or body.get("OrderItem") or []
    if not isinstance(items, list):
        items = [items] if items else []
    ids = []
    for it in items:
        oid = it.get("OrderItemId") or it.get("OrderItemID")
        if oid is not None:
            ids.append(int(oid))
    return ids


def set_invoice_pdf(order_item_ids, invoice_number, invoice_date, invoice_type, operator_code, pdf_base64):
    """SetInvoicePDF: sube el PDF del documento tributario."""
    url = f"{API_URL.rstrip('/')}/v1/marketplace-sellers/invoice/pdf"
    params = {
        "Action": "SetInvoicePDF",
        "Format": "JSON",
        "Service": "Invoice",
        "Timestamp": iso_ts(),
        "UserID": USER_ID,
        "Version": "1.0",
    }
    sig = sign_params(params, API_KEY)
    headers = {
        "User-Agent": "SELLER/Python/3/INVOICE_MVP/FACL",
        "Content-Type": "application/json",
        "Accept": "application/json",
        **params,
        "Signature": quote(sig, safe=""),
    }
    body = {
        "orderItemIds": [str(x) for x in order_item_ids],
        "invoiceNumber": str(invoice_number),
        "invoiceDate": str(invoice_date),
        "invoiceType": invoice_type.upper(),
        "operatorCode": operator_code.upper(),
        "invoiceDocumentFormat": "pdf",
        "invoiceDocument": pdf_base64,
    }
    r = requests.post(url, headers=headers, json=body, timeout=60)
    data = r.json() if r.content else {}
    return r.ok, data, r.status_code


def main():
    ap = argparse.ArgumentParser(description="Prueba SetInvoicePDF en Falabella")
    ap.add_argument("--order-id", required=True, help="OrderId de la orden (ej. 1140726828)")
    ap.add_argument("--pdf", required=True, help="Ruta al archivo PDF de la boleta/factura")
    ap.add_argument("--invoice-number", required=True, help="Número del documento (debe coincidir con el PDF)")
    ap.add_argument("--invoice-date", required=True, help="Fecha del documento YYYY-MM-DD")
    ap.add_argument("--invoice-type", default="BOLETA", choices=["BOLETA", "FACTURA", "NOTA_DE_CREDITO"])
    ap.add_argument("--operator-code", default="FACL", choices=["FACL", "FACO", "FAPE"])
    args = ap.parse_args()

    if not os.path.isfile(args.pdf):
        print(f"ERROR: No existe el archivo: {args.pdf}")
        return 1

    print("1. Obteniendo ítems de la orden", args.order_id, "...")
    try:
        order_item_ids = get_order_items(args.order_id)
    except Exception as e:
        print("ERROR obteniendo ítems:", e)
        return 1
    if not order_item_ids:
        print("ERROR: La orden no tiene ítems o no se pudieron leer.")
        return 1
    print("   OrderItemIds:", order_item_ids)

    print("2. Leyendo PDF y codificando en base64...")
    with open(args.pdf, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode("ascii")
    print("   Tamaño base64:", len(pdf_b64), "caracteres")

    print("3. Enviando SetInvoicePDF a Falabella...")
    ok, data, status = set_invoice_pdf(
        order_item_ids,
        args.invoice_number,
        args.invoice_date,
        args.invoice_type,
        args.operator_code,
        pdf_b64,
    )
    if ok:
        print("OK - Documento subido correctamente.")
        print("   Respuesta:", data)
        return 0
    print("ERROR - Falabella rechazó la subida (status %s)." % status)
    print("   Respuesta:", data)
    return 1


if __name__ == "__main__":
    sys.exit(main())
