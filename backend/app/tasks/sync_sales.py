"""
Sincroniza ventas desde Falabella y Mercado Libre: crea/actualiza Sales con platform y document_date.
Se ejecuta cada 10 min por APScheduler o por GET /internal/sync-sales (cron).
"""
import logging
from datetime import datetime, timezone, timedelta

from app import db
from app.models import User, Sale
from app.crypto_utils import decrypt_value
from app.services.falabella_client import FalabellaClient
from app.services.mercadolibre_client import MercadoLibreClient

logger = logging.getLogger(__name__)

# Últimos N días para traer órdenes
SYNC_DAYS = 7


def _parse_date(value):
    if not value:
        return None
    try:
        s = str(value)
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def sync_user_falabella(user):
    """Trae órdenes de Falabella y crea Sales (platform=Falabella) si no existen."""
    if not user.falabella_api_key_enc or not user.falabella_user_id:
        return 0
    try:
        key = decrypt_value(user.falabella_api_key_enc)
    except Exception as e:
        logger.warning("Falabella decrypt for user %s: %s", user.id, e)
        return 0
    client = FalabellaClient(user_id=user.falabella_user_id, api_key=key)
    since = (datetime.now(timezone.utc) - timedelta(days=SYNC_DAYS)).strftime("%Y-%m-%dT00:00:00+00:00")
    result = client.get_orders(created_after=since, updated_after=since, limit=100)
    if not result.get("success"):
        logger.warning("Falabella get_orders user %s: %s", user.id, result.get("error"))
        return 0
    body = result.get("data", {}).get("Body") or result.get("data", {})
    orders_raw = (body.get("Orders") or {}).get("Order") or body.get("Order") or []
    orders = orders_raw if isinstance(orders_raw, list) else [orders_raw] if orders_raw else []
    created = 0
    for o in orders:
        if not isinstance(o, dict) or "OrderId" not in o:
            continue
        id_venta = str(o.get("OrderId", ""))
        monto = float(o.get("Price", 0) or 0)
        if not id_venta or monto <= 0:
            continue
        sale = Sale.query.filter_by(user_id=user.id, id_venta=id_venta).first()
        if sale:
            if not sale.document_date:
                created_at = o.get("CreatedAt") or o.get("OrderDate")
                sale.document_date = _parse_date(created_at) or datetime.utcnow().date()
            continue
        doc_date = _parse_date(o.get("CreatedAt") or o.get("OrderDate")) or datetime.utcnow().date()
        sale = Sale(
            user_id=user.id,
            id_venta=id_venta,
            monto=monto,
            tipo_doc="Boleta",
            status="Pendiente",
            platform="Falabella",
            document_date=doc_date,
        )
        db.session.add(sale)
        created += 1
    return created


def sync_user_mercadolibre(user, ml_access_token):
    """Trae órdenes de ML y crea Sales (platform=Mercado Libre) si no existen."""
    if not ml_access_token:
        return 0
    client = MercadoLibreClient(access_token=ml_access_token)
    result = client.get_orders(seller_id=user.ml_user_id, limit=50)
    if not result.get("success"):
        logger.warning("ML get_orders user %s: %s", user.id, result.get("error"))
        return 0
    data = result.get("data") or {}
    results = data.get("results") or []
    created = 0
    for r in results:
        order_id = str(r.get("id", ""))
        if not order_id:
            continue
        sale = Sale.query.filter_by(user_id=user.id, id_venta=order_id).first()
        if sale:
            continue
        # Intentar monto desde orders anidados o payments
        monto = 0.0
        orders_list = r.get("orders") or []
        if orders_list and isinstance(orders_list[0], dict):
            # Puede haber total en el order
            monto = float(orders_list[0].get("total", 0) or 0)
        if monto <= 0:
            detail = client.get_order(order_id)
            if detail.get("success") and detail.get("data"):
                monto = float(detail["data"].get("total", 0) or 0)
        if monto <= 0:
            monto = 0.01  # placeholder para que la venta aparezca
        doc_date = _parse_date(r.get("date_created") or r.get("date_last_updated")) or datetime.utcnow().date()
        sale = Sale(
            user_id=user.id,
            id_venta=order_id,
            monto=monto,
            tipo_doc="Boleta",
            status="Pendiente",
            platform="Mercado Libre",
            document_date=doc_date,
        )
        db.session.add(sale)
        created += 1
    return created


def run_sync_sales():
    """Ejecuta la sincronización para todos los usuarios con Falabella o ML."""
    users = User.query.all()
    total_f = 0
    total_m = 0
    for user in users:
        n_f = sync_user_falabella(user)
        total_f += n_f
        ml_token = None
        if user.ml_access_token_enc:
            try:
                ml_token = decrypt_value(user.ml_access_token_enc)
            except Exception:
                pass
        if ml_token:
            n_m = sync_user_mercadolibre(user, ml_token)
            total_m += n_m
    try:
        db.session.commit()
    except Exception as e:
        logger.exception("sync_sales commit: %s", e)
        db.session.rollback()
        return {"ok": False, "error": str(e), "falabella": total_f, "mercado_libre": total_m}
    return {"ok": True, "falabella": total_f, "mercado_libre": total_m}
