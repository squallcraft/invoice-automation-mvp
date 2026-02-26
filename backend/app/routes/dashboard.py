"""
Dashboard: historial de ventas con paginación, filtros y ordenamiento.
"""
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import asc, desc

from app.models import Sale
from app.utils import err

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)

_SORT_COLUMNS = {
    "document_date": Sale.document_date,
    "fecha_venta":   Sale.document_date,
    "platform":      Sale.platform,
    "plataforma":    Sale.platform,
    "id_venta":      Sale.id_venta,
    "status":        Sale.status,
    "estado_orden":  Sale.status,
    "documento":     Sale.document_uploaded_at,
    "created_at":    Sale.created_at,
}


def _doc_estado(sale: Sale) -> str:
    if sale.document_uploaded_at:
        return "Cargado"
    if sale.status == "Éxito":
        return "Emitido"
    return "Por emitir"


def _sale_dict(s: Sale) -> dict:
    return {
        "id":                   s.id,
        "platform":             s.platform or "Manual",
        "id_venta":             s.id_venta,
        "id_orden":             s.id_venta,
        "document_date":        s.document_date.isoformat() if s.document_date else None,
        "monto":                float(s.monto),
        "tipo_doc":             s.tipo_doc,
        "status":               s.status,
        "documento":            _doc_estado(s),
        "documento_cargado":    s.document_uploaded_at is not None,
        "document_uploaded_at": s.document_uploaded_at.isoformat() if s.document_uploaded_at else None,
        "error_message":        s.error_message,
        "created_at":           s.created_at.isoformat() if s.created_at else None,
    }


@dashboard_bp.route("/sales", methods=["GET"])
@jwt_required()
def sales():
    """
    Query params: page, per_page, sort_by, sort_order (asc|desc),
                  platform, document_status, search.
    """
    user_id = int(get_jwt_identity())

    try:
        page     = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 30))))
    except (ValueError, TypeError):
        return err("page y per_page deben ser enteros")

    platform_filter = request.args.get("platform", "").strip()
    doc_status      = request.args.get("document_status", "").strip()
    search          = request.args.get("search", "").strip()
    sort_by         = request.args.get("sort_by", "document_date")
    sort_order      = (request.args.get("sort_order") or "desc").lower()
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    q = Sale.query.filter_by(user_id=user_id)

    if platform_filter:
        q = q.filter(Sale.platform == platform_filter)
    if search:
        q = q.filter(Sale.id_venta.ilike(f"%{search}%"))
    if doc_status == "Cargado":
        q = q.filter(Sale.document_uploaded_at.isnot(None))
    elif doc_status == "Emitido":
        q = q.filter(Sale.status == "Éxito", Sale.document_uploaded_at.is_(None))
    elif doc_status == "Por emitir":
        q = q.filter(Sale.document_uploaded_at.is_(None), Sale.status != "Éxito")

    col = _SORT_COLUMNS.get(sort_by) or _SORT_COLUMNS["document_date"]
    q = q.order_by(
        asc(col).nulls_last() if sort_order == "asc" else desc(col).nulls_first()
    )

    total  = q.count()
    offset = (page - 1) * per_page
    items  = q.offset(offset).limit(per_page).all()

    return jsonify({
        "sales":       [_sale_dict(s) for s in items],
        "total":       total,
        "page":        page,
        "per_page":    per_page,
        "total_pages": (total + per_page - 1) // per_page if total else 0,
    })


@dashboard_bp.route("/sales/<int:sale_id>/retry", methods=["POST"])
@jwt_required()
def retry_sale(sale_id):
    """Indica cómo reintentar una venta en estado Error."""
    user_id = int(get_jwt_identity())
    sale = Sale.query.filter_by(id=sale_id, user_id=user_id).first()
    if not sale:
        return err("Venta no encontrada", 404)
    if sale.status != "Error":
        return err("Solo se puede reintentar ventas en estado Error")
    return jsonify({
        "message": (
            "Usa POST /auto/process con body: "
            f'{{\"orders\": [{{\"id_venta\": \"{sale.id_venta}\", '
            f'\"monto\": {float(sale.monto)}, \"tipo_documento\": \"{sale.tipo_doc}\"}}], '
            f'\"retry\": true}}'
        ),
        "sale_id": sale.id,
    })
