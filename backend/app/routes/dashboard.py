"""
Dashboard: historial de ventas procesadas con estados (Éxito/Error/Pendiente) y reintento.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Sale
from sqlalchemy import or_

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/sales", methods=["GET"])
@jwt_required()
def sales():
    """
    Lista ventas del usuario con filtros por status.
    Query params: status (Éxito|Error|Pendiente), limit, offset.
    """
    user_id = int(get_jwt_identity())
    status_filter = request.args.get("status")
    limit = min(int(request.args.get("limit", 50)), 100)
    offset = int(request.args.get("offset", 0))

    q = Sale.query.filter_by(user_id=user_id).order_by(Sale.created_at.desc())
    if status_filter:
        q = q.filter(Sale.status == status_filter)
    total = q.count()
    items = q.offset(offset).limit(limit).all()

    return jsonify({
        "sales": [
            {
                "id": s.id,
                "id_venta": s.id_venta,
                "monto": float(s.monto),
                "tipo_doc": s.tipo_doc,
                "status": s.status,
                "error_message": s.error_message,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@dashboard_bp.route("/sales/<int:sale_id>/retry", methods=["POST"])
@jwt_required()
def retry_sale(sale_id):
    """Reintenta una venta en estado Error. Llama al flujo de emisión de nuevo."""
    user_id = int(get_jwt_identity())
    sale = Sale.query.filter_by(id=sale_id, user_id=user_id).first()
    if not sale:
        return jsonify({"error": "Venta no encontrada"}), 404
    if sale.status != "Error":
        return jsonify({"error": "Solo se puede reintentar ventas en estado Error"}), 400

    # El cliente puede llamar a POST /auto/process con body { "orders": [{ "id_venta": sale.id_venta, "monto": sale.monto, "tipo_documento": sale.tipo_doc }], "retry": true }
    return jsonify({
        "message": "Usa POST /auto/process con body: {\"orders\": [{\"id_venta\": \"%s\", \"monto\": %s, \"tipo_documento\": \"%s\"}], \"retry\": true}"
        % (sale.id_venta, float(sale.monto), sale.tipo_doc),
        "sale_id": sale.id,
    })
