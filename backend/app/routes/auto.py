"""
Flujo automático: capturar ventas Falabella, emitir vía Haulmer, opcional subir a Falabella.
"""
import logging
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, Sale, Document
from app.crypto_utils import decrypt_value
from app.services.haulmer_client import HaulmerClient
from app.services.falabella_client import FalabellaClient

logger = logging.getLogger(__name__)
auto_bp = Blueprint("auto", __name__)


def _get_user_with_keys(user_id):
    user = User.query.get(int(user_id))
    if not user or not user.haulmer_api_key_enc:
        return None, "Configura tu API key de Haulmer en /config/keys"
    return user, None


@auto_bp.route("/process", methods=["POST"])
@jwt_required()
def process():
    """
    Procesa ventas pendientes: obtiene órdenes aprobadas de Falabella (si hay key),
    emite en Haulmer, y opcionalmente sube documento a Falabella.
    Idempotencia: por cada id_venta solo se crea una Sale (unique user_id + id_venta).
    """
    user, err = _get_user_with_keys(get_jwt_identity())
    if err:
        return jsonify({"error": err}), 400

    haulmer_key = decrypt_value(user.haulmer_api_key_enc)
    falabella_key = decrypt_value(user.falabella_api_key_enc) if user.falabella_api_key_enc else None
    falabella_user_id = user.falabella_user_id if user.falabella_user_id else None

    # Obtener órdenes de Falabella si está configurado (Seller Center API: GetOrders)
    orders = []
    if falabella_key and falabella_user_id:
        client_f = FalabellaClient(user_id=falabella_user_id, api_key=falabella_key)
        since = request.args.get("since") or (request.get_json() or {}).get("since")
        if not since:
            since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00+00:00")
        result = client_f.get_orders(created_after=since, updated_after=since, limit=100)
        if result.get("success"):
            body = result.get("data", {}).get("Body") or result.get("data", {})
            orders_raw = (body.get("Orders") or {}).get("Order") or body.get("Order") or []
            orders = orders_raw if isinstance(orders_raw, list) else [orders_raw] if orders_raw else []
            # Normalizar formato Falabella (OrderId, Price) a id_venta, monto
            for o in orders:
                if isinstance(o, dict) and "OrderId" in o:
                    o["id_venta"] = str(o.get("OrderId", ""))
                    o["monto"] = float(o.get("Price", 0) or 0)

    # Si no hay órdenes por API, aceptar body con lista de ventas para procesar
    if not orders and request.get_json():
        orders = request.get_json().get("orders", [])

    if not orders:
        return jsonify({"message": "No hay órdenes para procesar", "processed": 0}), 200

    haulmer = HaulmerClient(haulmer_key)
    falabella = FalabellaClient(user_id=falabella_user_id, api_key=falabella_key) if (falabella_key and falabella_user_id) else None
    processed = 0
    errors = []

    for order in orders:
        id_venta = str(order.get("id") or order.get("id_venta") or order.get("order_id", ""))
        monto = float(order.get("monto") or order.get("total", 0))
        tipo_doc = (order.get("tipo_documento") or order.get("tipo_doc") or "Boleta").strip()

        if not id_venta or monto <= 0:
            errors.append({"id_venta": id_venta, "error": "id_venta o monto inválido"})
            continue

        # Idempotencia: si ya existe Sale con este user_id + id_venta, skip o retry según status
        sale = Sale.query.filter_by(user_id=user.id, id_venta=id_venta).first()
        if sale:
            if sale.status == "Éxito":
                continue
            if sale.status == "Error" and request.get_json() and request.get_json().get("retry"):
                pass  # Reintentar
            else:
                continue

        if not sale:
            sale = Sale(
                user_id=user.id,
                id_venta=id_venta,
                monto=monto,
                tipo_doc=tipo_doc,
                status="Pendiente",
            )
            db.session.add(sale)
            db.session.flush()

        result = haulmer.emit_document(tipo_doc=tipo_doc, id_venta=id_venta, monto=monto)
        if result.get("success"):
            sale.status = "Éxito"
            doc = Document(
                user_id=user.id,
                sale_id=sale.id,
                pdf_url=result.get("pdf_url"),
                xml_url=result.get("xml_url"),
                haulmer_response=str(result.get("raw", "")),
            )
            db.session.add(doc)
            if falabella and result.get("pdf_url"):
                # Opcional: descargar PDF y subir a Falabella (aquí simplificado)
                upload = falabella.upload_document(id_venta, b"", "document.pdf")
                if not upload.get("success"):
                    logger.warning("Falabella upload failed for %s: %s", id_venta, upload.get("error"))
            processed += 1
        else:
            sale.status = "Error"
            sale.error_message = result.get("error", "Unknown")
            errors.append({"id_venta": id_venta, "error": result.get("error")})

    db.session.commit()
    return jsonify({
        "message": f"Procesadas {processed} ventas",
        "processed": processed,
        "errors": errors,
    })
