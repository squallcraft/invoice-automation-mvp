"""
Dashboard: historial de ventas con paginación, orden, filtros y búsqueda.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Sale
from sqlalchemy import asc, desc

dashboard_bp = Blueprint("dashboard", __name__)

# Columnas por las que se puede ordenar (clave -> atributo o expresión)
SORT_COLUMNS = {
    "document_date": Sale.document_date,
    "fecha_venta": Sale.document_date,
    "platform": Sale.platform,
    "plataforma": Sale.platform,
    "id_venta": Sale.id_venta,
    "status": Sale.status,
    "estado_orden": Sale.status,
    "documento": Sale.document_uploaded_at,  # null = Por emitir, no null = Cargado (Emitido lógico viene de status)
    "created_at": Sale.created_at,
}


def _documento_estado(sale):
    """Estado del documento tributario: Por emitir | Emitido | Cargado."""
    if getattr(sale, "document_uploaded_at", None):
        return "Cargado"
    if sale.status == "Éxito":
        return "Emitido"
    return "Por emitir"


@dashboard_bp.route("/sales", methods=["GET"])
@jwt_required()
def sales():
    """
    Lista ventas del usuario con paginación, orden, filtros y búsqueda.
    Query params:
      - page: número de página (1-based), default 1
      - per_page: por página (default 30, max 100)
      - sort_by: document_date | platform | id_venta | status | documento
      - sort_order: asc | desc
      - platform: Falabella | Mercado Libre | Manual (opción vacía = todas)
      - document_status: Por emitir | Emitido | Cargado (opción vacía = todos)
      - search: busca en id_venta (ID de venta / ID de orden)
    """
    user_id = int(get_jwt_identity())
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 30))))
    platform_filter = request.args.get("platform", "").strip()
    document_status_filter = request.args.get("document_status", "").strip()
    search = request.args.get("search", "").strip()
    sort_by = request.args.get("sort_by", "document_date")
    sort_order = (request.args.get("sort_order") or "desc").lower()
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    q = Sale.query.filter_by(user_id=user_id)

    if platform_filter:
        q = q.filter(Sale.platform == platform_filter)

    if search:
        q = q.filter(Sale.id_venta.ilike(f"%{search}%"))

    # Filtro por estado de documento (Por emitir | Emitido | Cargado)
    if document_status_filter == "Cargado":
        q = q.filter(Sale.document_uploaded_at.isnot(None))
    elif document_status_filter == "Emitido":
        q = q.filter(Sale.status == "Éxito", Sale.document_uploaded_at.is_(None))
    elif document_status_filter == "Por emitir":
        q = q.filter(Sale.document_uploaded_at.is_(None)).filter(Sale.status != "Éxito")

    # Orden
    order_col = SORT_COLUMNS.get(sort_by) or SORT_COLUMNS["document_date"]
    if sort_order == "asc":
        q = q.order_by(asc(order_col).nulls_last())
    else:
        q = q.order_by(desc(order_col).nulls_first())

    total = q.count()
    offset = (page - 1) * per_page
    items = q.offset(offset).limit(per_page).all()

    def _sale_to_dict(s):
        return {
            "platform": s.platform or "Manual",
            "id": s.id,
            "id_venta": s.id_venta,
            "id_orden": s.id_venta,  # mismo que id_venta por ahora
            "document_date": s.document_date.isoformat() if s.document_date else None,
            "monto": float(s.monto),
            "tipo_doc": s.tipo_doc,
            "status": s.status,
            "documento": _documento_estado(s),
            "documento_cargado": s.document_uploaded_at is not None,
            "document_uploaded_at": s.document_uploaded_at.isoformat() if s.document_uploaded_at else None,
            "error_message": s.error_message,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }

    return jsonify({
        "sales": [_sale_to_dict(s) for s in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total else 0,
    })


@dashboard_bp.route("/sales/<int:sale_id>/retry", methods=["POST"])
@jwt_required()
def retry_sale(sale_id):
    """Reintenta una venta en estado Error."""
    user_id = int(get_jwt_identity())
    sale = Sale.query.filter_by(id=sale_id, user_id=user_id).first()
    if not sale:
        return jsonify({"error": "Venta no encontrada"}), 404
    if sale.status != "Error":
        return jsonify({"error": "Solo se puede reintentar ventas en estado Error"}), 400
    return jsonify({
        "message": "Usa POST /auto/process con body: {\"orders\": [{\"id_venta\": \"%s\", \"monto\": %s, \"tipo_documento\": \"%s\"}], \"retry\": true}"
        % (sale.id_venta, float(sale.monto), sale.tipo_doc),
        "sale_id": sale.id,
    })
