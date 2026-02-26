"""
Sincroniza ventas desde Falabella y Mercado Libre.
Se ejecuta cada 30 min por APScheduler o vía GET /internal/sync-sales (cron).
"""
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import and_, or_

from app import db
from app.crypto_utils import decrypt_value
from app.models import Sale, User
from app.services.falabella_client import FalabellaClient
from app.services.mercadolibre_client import MercadoLibreClient
from app.utils import parse_date

logger = logging.getLogger(__name__)

SYNC_DAYS = 7


def _fetch_and_upsert_falabella(user: User) -> int:
    if not user.falabella_api_key_enc or not user.falabella_user_id:
        return 0
    try:
        key = decrypt_value(user.falabella_api_key_enc)
    except ValueError as e:
        logger.warning("Falabella decrypt user %s: %s", user.id, e)
        return 0

    since  = (datetime.now(timezone.utc) - timedelta(days=SYNC_DAYS)).strftime("%Y-%m-%dT00:00:00+00:00")
    client = FalabellaClient(user_id=user.falabella_user_id, api_key=key)
    result = client.get_orders(created_after=since, updated_after=since, limit=100)
    if not result.get("success"):
        logger.warning("Falabella get_orders user %s: %s", user.id, result.get("error"))
        return 0

    body   = result.get("data", {}).get("Body") or result.get("data", {})
    raw    = (body.get("Orders") or {}).get("Order") or body.get("Order") or []
    orders = raw if isinstance(raw, list) else ([raw] if raw else [])
    count  = 0

    for o in orders:
        if not isinstance(o, dict) or "OrderId" not in o:
            continue
        id_venta = str(o["OrderId"])
        monto    = float(o.get("Price", 0) or 0)
        if not id_venta or monto <= 0:
            continue
        doc_date = parse_date(o.get("CreatedAt") or o.get("OrderDate")) or datetime.utcnow().date()
        sale     = Sale.query.filter_by(user_id=user.id, id_venta=id_venta).first()
        if sale:
            if not sale.document_date:
                sale.document_date = doc_date
            continue
        db.session.add(Sale(
            user_id=user.id,
            id_venta=id_venta,
            monto=monto,
            tipo_doc="Boleta",
            status="Pendiente",
            platform="Falabella",
            document_date=doc_date,
        ))
        count += 1

    return count


def _fetch_and_upsert_ml(user: User) -> int:
    if not user.ml_access_token_enc:
        return 0
    try:
        token = decrypt_value(user.ml_access_token_enc)
    except ValueError:
        return 0

    client = MercadoLibreClient(access_token=token)
    result = client.get_orders(seller_id=user.ml_user_id, limit=50)
    if not result.get("success"):
        logger.warning("ML get_orders user %s: %s", user.id, result.get("error"))
        return 0

    results = (result.get("data") or {}).get("results") or []
    count   = 0

    for r in results:
        order_id = str(r.get("id", ""))
        if not order_id:
            continue
        if Sale.query.filter_by(user_id=user.id, id_venta=order_id).first():
            continue

        monto = 0.0
        orders_list = r.get("orders") or []
        if orders_list and isinstance(orders_list[0], dict):
            monto = float(orders_list[0].get("total", 0) or 0)
        if monto <= 0:
            detail = client.get_order(order_id)
            if detail.get("success"):
                monto = float((detail.get("data") or {}).get("total", 0) or 0)
        monto = monto or 0.01

        doc_date = parse_date(r.get("date_created") or r.get("date_last_updated")) or datetime.utcnow().date()
        db.session.add(Sale(
            user_id=user.id,
            id_venta=order_id,
            monto=monto,
            tipo_doc="Boleta",
            status="Pendiente",
            platform="Mercado Libre",
            document_date=doc_date,
        ))
        count += 1

    return count


def run_sync_sales() -> dict:
    """Sincroniza todos los usuarios que tengan al menos una integración activa."""
    has_any = User.query.filter(
        or_(
            and_(User.falabella_user_id.isnot(None), User.falabella_api_key_enc.isnot(None)),
            User.ml_access_token_enc.isnot(None),
        )
    ).first()

    if not has_any:
        logger.debug("sync_sales: ningún usuario con integraciones, omitiendo.")
        return {"ok": True, "falabella": 0, "mercado_libre": 0}

    total_f = total_m = 0
    for user in User.query.all():
        total_f += _fetch_and_upsert_falabella(user)
        total_m += _fetch_and_upsert_ml(user)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception("sync_sales commit: %s", e)
        return {"ok": False, "error": str(e), "falabella": total_f, "mercado_libre": total_m}

    logger.info("sync_sales: falabella=%d ml=%d", total_f, total_m)
    return {"ok": True, "falabella": total_f, "mercado_libre": total_m}
