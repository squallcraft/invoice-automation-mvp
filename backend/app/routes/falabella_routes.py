"""
Rutas para Falabella Seller Center: órdenes, ítems y etiquetas de envío.
"""
import base64
import io
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.crypto_utils import decrypt_value
from app.models import User
from app.services.falabella_client import FalabellaClient, parse_order_items_response
from app.utils import err, require_user

logger = logging.getLogger(__name__)
falabella_bp = Blueprint("falabella", __name__)


def _get_client(user: User) -> Tuple[Optional[FalabellaClient], Optional[Tuple]]:
    """Devuelve (client, None) o (None, error_response)."""
    if not user.falabella_user_id or not user.falabella_api_key_enc:
        return None, err(
            "Configura Falabella: User ID (email Seller Center) y API Key en Configuración"
        )
    try:
        api_key = decrypt_value(user.falabella_api_key_enc)
    except ValueError as e:
        return None, err(str(e))
    return FalabellaClient(user_id=user.falabella_user_id, api_key=api_key), None


@falabella_bp.route("/orders", methods=["GET"])
@jwt_required()
def get_orders():
    """
    Lista órdenes de Falabella Seller Center.
    Query: created_after, updated_after, status, limit, offset, shipping_type.
    """
    user, error = require_user()
    if error:
        return error
    client, error = _get_client(user)
    if error:
        return error

    created_after  = request.args.get("created_after")
    updated_after  = request.args.get("updated_after")
    if not created_after and not updated_after:
        default = (datetime.now(timezone.utc) - timedelta(days=10)).strftime(
            "%Y-%m-%dT00:00:00+00:00"
        )
        created_after = updated_after = default

    try:
        limit = min(int(request.args.get("limit", 30)), 100)
        offset = int(request.args.get("offset", 0))
    except (ValueError, TypeError):
        return err("limit y offset deben ser enteros")

    result = client.get_orders(
        created_after=created_after,
        updated_after=updated_after,
        status=request.args.get("status"),
        limit=limit,
        offset=offset,
        shipping_type=request.args.get("shipping_type"),
    )
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Error Falabella"), "details": result}), 502
    return jsonify(result.get("data", result))


@falabella_bp.route("/orders/<order_id>/items", methods=["GET"])
@jwt_required()
def get_order_items(order_id):
    """Ítems de una orden (OrderItemId, Status, etc.)."""
    user, error = require_user()
    if error:
        return error
    client, error = _get_client(user)
    if error:
        return error

    result = client.get_order_items(order_id)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Error Falabella"), "details": result}), 502
    return jsonify({
        "order_id": order_id,
        "items":    parse_order_items_response(result),
        "raw":      result.get("data"),
    })


@falabella_bp.route("/labels", methods=["POST"])
@jwt_required()
def get_labels():
    """
    Etiquetas de envío (shipping labels).
    Body: { order_item_ids: [123, 456] }  o  { order_id: 1234 }.
    Query: download=1 para descarga directa.
    Los ítems deben estar en ReadyToShip antes de llamar.
    """
    user, error = require_user()
    if error:
        return error
    client, error = _get_client(user)
    if error:
        return error

    data           = request.get_json() or {}
    order_item_ids = data.get("order_item_ids")
    order_id       = data.get("order_id")

    if order_item_ids is None and order_id is not None:
        items_result = client.get_order_items(str(order_id))
        if not items_result.get("success"):
            return jsonify({"error": items_result.get("error", "Error al obtener ítems")}), 502
        order_item_ids = [
            int(it["OrderItemId"])
            for it in parse_order_items_response(items_result)
            if it.get("OrderItemId") is not None
        ]

    if not order_item_ids:
        return err("Indica order_item_ids o order_id en el body")

    result = client.get_document(order_item_ids=order_item_ids, document_type="shippingParcel")
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Error al obtener etiqueta"), "details": result}), 502

    file_b64  = result.get("file_base64")
    mime_type = result.get("mime_type") or "application/pdf"
    if not file_b64:
        return jsonify({"error": "La API no devolvió archivo de etiqueta", "response": result}), 502

    if request.args.get("download"):
        try:
            raw = base64.b64decode(file_b64)
        except Exception as e:
            return err(f"Error decodificando base64: {e}", 500)
        extension = "pdf" if "pdf" in mime_type else "txt"
        return send_file(
            io.BytesIO(raw),
            mimetype=mime_type,
            as_attachment=True,
            download_name=f"etiqueta_falabella.{extension}",
        )

    return jsonify({
        "success":        True,
        "mime_type":      mime_type,
        "file_base64":    file_b64,
        "order_item_ids": order_item_ids,
    })
