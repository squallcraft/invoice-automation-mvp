"""
Rutas para integración con Falabella Seller Center: órdenes, ítems y etiquetas.
Objetivo inicial: poder obtener las etiquetas desde Falabella Center.
"""
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
import base64
import io
from app.models import User
from app.crypto_utils import decrypt_value
from app.services.falabella_client import (
    FalabellaClient,
    parse_order_items_response,
)

falabella_bp = Blueprint("falabella", __name__)


def _get_falabella_client(user_id_int):
    """Obtiene cliente Falabella si el usuario tiene UserID y API Key configurados."""
    user = User.query.get(int(user_id_int))
    if not user:
        return None, "Usuario no encontrado"
    if not user.falabella_user_id or not user.falabella_api_key_enc:
        return None, "Configura Falabella: User ID (email Seller Center) y API Key en Configuración"
    api_key = decrypt_value(user.falabella_api_key_enc)
    return FalabellaClient(user_id=user.falabella_user_id, api_key=api_key), None


@falabella_bp.route("/orders", methods=["GET"])
@jwt_required()
def get_orders():
    """
    Lista órdenes desde Falabella Seller Center.
    Query: created_after (ISO 8601), updated_after, status, limit, offset, shipping_type.
    """
    client, err = _get_falabella_client(get_jwt_identity())
    if err:
        return jsonify({"error": err}), 400
    created_after = request.args.get("created_after")
    updated_after = request.args.get("updated_after")
    if not created_after and not updated_after:
        # Por defecto: últimos 10 días
        default_since = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT00:00:00+00:00")
        created_after = default_since
        updated_after = default_since
    result = client.get_orders(
        created_after=created_after,
        updated_after=updated_after,
        status=request.args.get("status"),
        limit=min(int(request.args.get("limit", 30)), 100),
        offset=int(request.args.get("offset", 0)),
        shipping_type=request.args.get("shipping_type"),
    )
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Error Falabella"), "details": result}), 502
    return jsonify(result.get("data", result))


@falabella_bp.route("/orders/<order_id>/items", methods=["GET"])
@jwt_required()
def get_order_items(order_id):
    """Obtiene los ítems de una orden (OrderItemId, Status, etc.). Necesarios para pedir etiquetas."""
    client, err = _get_falabella_client(get_jwt_identity())
    if err:
        return jsonify({"error": err}), 400
    result = client.get_order_items(order_id)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Error Falabella"), "details": result}), 502
    items = parse_order_items_response(result)
    return jsonify({"order_id": order_id, "items": items, "raw": result.get("data")})


@falabella_bp.route("/labels", methods=["POST"])
@jwt_required()
def get_labels():
    """
    Obtiene las etiquetas de envío (shipping labels) desde Falabella Center.

    Body (JSON):
      - order_item_ids: [123, 456]  → etiquetas para esos OrderItemIds
      - order_id: 1127812574        → obtiene ítems de la orden y luego etiquetas de todos

    Los ítems deben estar empaquetados (SetStatusToReadyToShip) antes de poder obtener la etiqueta.
    Respuesta: PDF en base64 o descarga según Accept/query.
    """
    client, err = _get_falabella_client(get_jwt_identity())
    if err:
        return jsonify({"error": err}), 400

    data = request.get_json() or {}
    order_item_ids = data.get("order_item_ids")
    order_id = data.get("order_id")

    if order_item_ids is None and order_id is not None:
        # Obtener ítems de la orden primero
        result = client.get_order_items(str(order_id))
        if not result.get("success"):
            return jsonify({"error": result.get("error", "Error al obtener ítems")}), 502
        items = parse_order_items_response(result)
        order_item_ids = []
        for it in items:
            oid = it.get("OrderItemId") or it.get("OrderItemID")
            if oid is not None:
                order_item_ids.append(int(oid))

    if not order_item_ids:
        return jsonify({"error": "Indica order_item_ids o order_id en el body"}), 400

    result = client.get_document(order_item_ids=order_item_ids, document_type="shippingParcel")
    if not result.get("success"):
        return jsonify({
            "error": result.get("error", "Error al obtener etiqueta"),
            "details": result,
        }), 502

    file_base64 = result.get("file_base64")
    mime_type = result.get("mime_type") or "application/pdf"
    if not file_base64:
        return jsonify({"error": "La API no devolvió archivo de etiqueta", "response": result}), 502

    # Descarga directa si piden download=1
    if request.args.get("download"):
        try:
            raw = base64.b64decode(file_base64)
        except Exception as e:
            return jsonify({"error": f"Error decodificando base64: {e}"}), 500
        extension = "pdf" if "pdf" in mime_type else "txt"
        return send_file(
            io.BytesIO(raw),
            mimetype=mime_type,
            as_attachment=True,
            download_name=f"etiqueta_falabella.{extension}",
        )

    return jsonify({
        "success": True,
        "mime_type": mime_type,
        "file_base64": file_base64,
        "order_item_ids": order_item_ids,
    })
