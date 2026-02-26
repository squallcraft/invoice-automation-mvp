"""
Flujo automático: capturar órdenes de Falabella/ML, emitir vía Haulmer y subir el documento.
Idempotencia: por cada (user_id, id_venta) solo se crea una Sale.
"""
import base64
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

import requests as http_requests
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.crypto_utils import decrypt_value
from app.models import Document, Sale, User
from app.services.falabella_client import FalabellaClient, parse_order_items_response
from app.services.haulmer_client import HaulmerClient
from app.services.mercadolibre_client import MercadoLibreClient
from app.utils import err, parse_date, require_user

logger = logging.getLogger(__name__)
auto_bp = Blueprint("auto", __name__)


# ── Helpers de negocio ─────────────────────────────────────────────────────

def _falabella_client(user: User) -> Optional[FalabellaClient]:
    if not user.falabella_api_key_enc or not user.falabella_user_id:
        return None
    try:
        key = decrypt_value(user.falabella_api_key_enc)
    except ValueError:
        return None
    return FalabellaClient(user_id=user.falabella_user_id, api_key=key)


def _ml_client(user: User) -> Tuple[Optional[MercadoLibreClient], Optional[str]]:
    """Devuelve (client, ml_user_id) o (None, None) si no hay token."""
    if not user.ml_access_token_enc:
        return None, None
    try:
        token = decrypt_value(user.ml_access_token_enc)
    except ValueError:
        return None, None
    return MercadoLibreClient(access_token=token), user.ml_user_id


def _fetch_falabella_orders(client: FalabellaClient, since: str) -> List[dict]:
    """Devuelve lista de órdenes normalizadas de Falabella."""
    result = client.get_orders(created_after=since, updated_after=since, limit=100)
    if not result.get("success"):
        logger.warning("Falabella get_orders: %s", result.get("error"))
        return []
    body = result.get("data", {}).get("Body") or result.get("data", {})
    raw  = (body.get("Orders") or {}).get("Order") or body.get("Order") or []
    orders = raw if isinstance(raw, list) else [raw] if raw else []

    normalized = []
    for o in orders:
        if not isinstance(o, dict) or "OrderId" not in o:
            continue
        created = o.get("CreatedAt") or o.get("OrderDate") or o.get("CreatedDate")
        normalized.append({
            "id_venta":      str(o["OrderId"]),
            "monto":         float(o.get("Price", 0) or 0),
            "platform":      "Falabella",
            "document_date": parse_date(created),
        })
    return normalized


def _fetch_ml_orders(client: MercadoLibreClient, ml_user_id: str) -> List[dict]:
    """Devuelve lista de órdenes normalizadas de Mercado Libre."""
    result = client.get_orders(seller_id=ml_user_id, limit=50)
    if not result.get("success"):
        logger.warning("ML get_orders: %s", result.get("error"))
        return []
    results = (result.get("data") or {}).get("results") or []
    orders  = []
    for r in results:
        order_id = str(r.get("id", ""))
        if not order_id:
            continue
        detail  = client.get_order(order_id)
        monto   = float((detail.get("data") or {}).get("total", 0) or 0) if detail.get("success") else 0
        pack_id = detail.get("pack_id") or order_id if detail.get("success") else order_id
        orders.append({
            "id_venta":      order_id,
            "monto":         max(monto, 0.01),
            "platform":      "Mercado Libre",
            "document_date": parse_date((detail.get("data") or {}).get("date_created") or r.get("date_created")),
            "pack_id":       str(pack_id),
        })
    return orders


def _upload_to_falabella(falabella: FalabellaClient, id_venta: str, pdf_url: str) -> bool:
    """Descarga el PDF de Haulmer y lo sube a Falabella. Devuelve True si tuvo éxito."""
    try:
        resp = http_requests.get(pdf_url, timeout=30)
        resp.raise_for_status()
        pdf_b64 = base64.b64encode(resp.content).decode()
    except Exception as e:
        logger.warning("Download PDF for Falabella %s: %s", id_venta, e)
        return False

    items_result = falabella.get_order_items(id_venta)
    items        = parse_order_items_response(items_result)
    item_ids     = [int(it["OrderItemId"]) for it in items if it.get("OrderItemId")]
    if not item_ids:
        logger.warning("No OrderItemIds for Falabella order %s", id_venta)
        return False

    upload = falabella.set_invoice_pdf(
        order_item_ids=item_ids,
        invoice_number=id_venta,
        invoice_date=datetime.utcnow().strftime("%Y-%m-%d"),
        invoice_type="BOLETA",
        operator_code="FACL",
        pdf_base64=pdf_b64,
    )
    if not upload.get("success"):
        logger.warning("Falabella upload failed for %s: %s", id_venta, upload.get("error"))
    return upload.get("success", False)


def _upload_to_ml(ml_client: MercadoLibreClient, id_venta: str, pack_id: str, pdf_url: str) -> bool:
    """Descarga el PDF de Haulmer y lo sube a Mercado Libre. Devuelve True si tuvo éxito."""
    try:
        resp = http_requests.get(pdf_url, timeout=30)
        resp.raise_for_status()
        pdf_content = resp.content
    except Exception as e:
        logger.warning("Download PDF for ML %s: %s", id_venta, e)
        return False

    upload = ml_client.upload_fiscal_document(pack_id, pdf_content)
    if not upload.get("success"):
        logger.warning("ML upload failed for %s: %s", id_venta, upload.get("error"))
    return upload.get("success", False)


# ── Ruta ───────────────────────────────────────────────────────────────────

@auto_bp.route("/process", methods=["POST"])
@jwt_required()
def process():
    """
    Procesa ventas pendientes:
    1. Obtiene órdenes de Falabella y/o ML (si están configurados).
    2. Acepta lista explícita en body: { orders: [...], retry: true }.
    3. Emite en Haulmer, guarda en BD, sube documento a la plataforma.
    Idempotencia: no reemite ventas ya en estado Éxito o ya cargadas.
    """
    user, error = require_user()
    if error:
        return error

    if not user.haulmer_api_key_enc:
        return err("Configura tu API key de Haulmer en /config/keys")

    haulmer_key = decrypt_value(user.haulmer_api_key_enc)
    body        = request.get_json() or {}
    is_retry    = bool(body.get("retry"))
    since       = body.get("since") or request.args.get("since") or (
        (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00+00:00")
    )

    # ── Recolectar órdenes ────────────────────────────────────────────────
    orders: List[dict] = []

    falabella = _falabella_client(user)
    if falabella:
        orders.extend(_fetch_falabella_orders(falabella, since))

    ml_client, ml_user_id = _ml_client(user)
    if ml_client and ml_user_id:
        orders.extend(_fetch_ml_orders(ml_client, ml_user_id))

    # Órdenes manuales del body (cuando no hay API o retry)
    if not orders and body.get("orders"):
        for o in body["orders"]:
            orders.append({
                "id_venta":      str(o.get("id_venta") or o.get("id") or ""),
                "monto":         float(o.get("monto") or o.get("total", 0)),
                "platform":      o.get("platform") or "Manual",
                "document_date": parse_date(o.get("document_date")),
                "tipo_doc":      o.get("tipo_documento") or o.get("tipo_doc") or "Boleta",
                "pack_id":       o.get("pack_id"),
            })

    if not orders:
        return jsonify({"message": "No hay órdenes para procesar", "processed": 0}), 200

    haulmer   = HaulmerClient(haulmer_key)
    processed = 0
    errors    = []

    for order in orders:
        id_venta  = order.get("id_venta", "")
        monto     = float(order.get("monto", 0))
        tipo_doc  = order.get("tipo_doc") or "Boleta"
        platform  = order.get("platform") or "Manual"
        pack_id   = order.get("pack_id")
        doc_date  = order.get("document_date")

        if not id_venta or monto <= 0:
            errors.append({"id_venta": id_venta, "error": "id_venta o monto inválido"})
            continue

        # Idempotencia: no reemitir si ya fue cargado o emitido con éxito
        sale = Sale.query.filter_by(user_id=user.id, id_venta=id_venta).first()
        if sale:
            if sale.document_uploaded_at or (sale.status == "Éxito" and not is_retry):
                continue

        # Verificación en plataforma antes de emitir
        if platform == "Falabella" and falabella:
            already = falabella.invoice_uploaded(id_venta)
            if already is True:
                if sale and not sale.document_uploaded_at:
                    sale.document_uploaded_at = datetime.utcnow()
                continue
        if platform == "Mercado Libre" and ml_client and pack_id:
            if ml_client.fiscal_document_uploaded(pack_id) is True:
                if sale and not sale.document_uploaded_at:
                    sale.document_uploaded_at = datetime.utcnow()
                continue

        # Crear o actualizar Sale
        if not sale:
            sale = Sale(
                user_id=user.id,
                id_venta=id_venta,
                monto=monto,
                tipo_doc=tipo_doc,
                status="Pendiente",
                platform=platform,
                document_date=doc_date,
            )
            db.session.add(sale)
            db.session.flush()
        else:
            if platform and not sale.platform:
                sale.platform = platform
            if doc_date and not sale.document_date:
                sale.document_date = doc_date

        # Emitir en Haulmer
        result = haulmer.emit_document(tipo_doc=tipo_doc, id_venta=id_venta, monto=monto)

        if result.get("success"):
            sale.status = "Éxito"
            if not sale.document_date:
                sale.document_date = datetime.utcnow().date()

            db.session.add(Document(
                user_id=user.id,
                sale_id=sale.id,
                pdf_url=result.get("pdf_url"),
                xml_url=result.get("xml_url"),
                haulmer_response=str(result.get("raw", ""))[:4000],
            ))

            pdf_url = result.get("pdf_url")
            if pdf_url:
                if platform == "Falabella" and falabella:
                    if _upload_to_falabella(falabella, id_venta, pdf_url):
                        sale.document_uploaded_at = datetime.utcnow()
                elif platform == "Mercado Libre" and ml_client:
                    if not pack_id:
                        ord_resp = ml_client.get_order(id_venta)
                        pack_id  = ord_resp.get("pack_id") or id_venta if ord_resp.get("success") else id_venta
                    if _upload_to_ml(ml_client, id_venta, str(pack_id), pdf_url):
                        sale.document_uploaded_at = datetime.utcnow()

            processed += 1
        else:
            sale.status        = "Error"
            sale.error_message = result.get("error", "Unknown")
            errors.append({"id_venta": id_venta, "error": result.get("error")})

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception("Error al guardar ventas procesadas: %s", e)
        return err(f"Error al guardar en base de datos: {e}", 500)

    return jsonify({
        "message":   f"Procesadas {processed} ventas",
        "processed": processed,
        "errors":    errors,
    })
