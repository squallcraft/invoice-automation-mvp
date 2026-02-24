"""
Flujo automático: capturar ventas Falabella y Mercado Libre, emitir vía Haulmer, subir a la plataforma.
Procedimiento principal: 1º comprobar si en la plataforma ya hay documento cargado → no reemitir.
"""
import logging
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import requests

from app import db
from app.models import User, Sale, Document
from app.crypto_utils import decrypt_value
from app.services.haulmer_client import HaulmerClient
from app.services.falabella_client import FalabellaClient
from app.services.mercadolibre_client import MercadoLibreClient

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
    ml_access_token = None
    if getattr(user, "ml_access_token_enc", None):
        try:
            ml_access_token = decrypt_value(user.ml_access_token_enc)
        except Exception:
            pass

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
            # Normalizar formato Falabella (OrderId, Price, CreatedAt) a id_venta, monto, document_date, platform
            for o in orders:
                if isinstance(o, dict) and "OrderId" in o:
                    o["id_venta"] = str(o.get("OrderId", ""))
                    o["monto"] = float(o.get("Price", 0) or 0)
                    o["platform"] = "Falabella"
                    # Fecha orden/documento si viene en la API
                    created = o.get("CreatedAt") or o.get("OrderDate") or o.get("CreatedDate")
                    if created:
                        try:
                            if "T" in str(created):
                                o["document_date"] = datetime.fromisoformat(str(created).replace("Z", "+00:00")).date()
                            else:
                                o["document_date"] = datetime.strptime(str(created)[:10], "%Y-%m-%d").date()
                        except Exception:
                            o["document_date"] = None
                    else:
                        o["document_date"] = None

    # Obtener órdenes de Mercado Libre si está conectado (GET /marketplace/orders/search)
    if ml_access_token and user.ml_user_id:
        client_ml = MercadoLibreClient(access_token=ml_access_token)
        result_ml = client_ml.get_orders(seller_id=user.ml_user_id, limit=50)
        if result_ml.get("success"):
            data_ml = result_ml.get("data") or {}
            results_ml = data_ml.get("results") or []
            for r in results_ml:
                order_id = str(r.get("id", ""))
                if not order_id:
                    continue
                # Resolver monto y pack_id con GET /orders/{id}
                detail = client_ml.get_order(order_id)
                if not detail.get("success"):
                    continue
                monto = float(detail.get("data", {}).get("total", 0) or 0)
                pack_id = detail.get("pack_id") or order_id
                created = (detail.get("data") or {}).get("date_created") or r.get("date_created")
                doc_date = None
                if created:
                    try:
                        s = str(created)
                        if "T" in s:
                            doc_date = datetime.fromisoformat(s.replace("Z", "+00:00")).date()
                        else:
                            doc_date = datetime.strptime(s[:10], "%Y-%m-%d").date()
                    except Exception:
                        pass
                if not doc_date:
                    doc_date = datetime.utcnow().date()
                orders.append({
                    "id_venta": order_id,
                    "monto": monto if monto > 0 else 0.01,
                    "platform": "Mercado Libre",
                    "document_date": doc_date,
                    "pack_id": str(pack_id),
                })

    # Si no hay órdenes por API, aceptar body con lista de ventas para procesar
    if not orders and request.get_json():
        body_orders = request.get_json().get("orders", [])
        for o in body_orders:
            o["platform"] = o.get("platform") or "Manual"
            o["document_date"] = o.get("document_date")  # opcional
        orders = body_orders

    if not orders:
        return jsonify({"message": "No hay órdenes para procesar", "processed": 0}), 200

    haulmer = HaulmerClient(haulmer_key)
    falabella = FalabellaClient(user_id=falabella_user_id, api_key=falabella_key) if (falabella_key and falabella_user_id) else None
    ml_client = MercadoLibreClient(access_token=ml_access_token) if ml_access_token else None
    processed = 0
    errors = []

    for order in orders:
        id_venta = str(order.get("id") or order.get("id_venta") or order.get("order_id", ""))
        monto = float(order.get("monto") or order.get("total", 0))
        tipo_doc = (order.get("tipo_documento") or order.get("tipo_doc") or "Boleta").strip()

        if not id_venta or monto <= 0:
            errors.append({"id_venta": id_venta, "error": "id_venta o monto inválido"})
            continue

        # Primero: si es Falabella y ya tiene documento cargado en la plataforma, no reemitir
        if falabella and order.get("platform") == "Falabella":
            already = falabella.invoice_uploaded(id_venta)
            if already is True:
                sale = Sale.query.filter_by(user_id=user.id, id_venta=id_venta).first()
                if sale and not sale.document_uploaded_at:
                    sale.document_uploaded_at = datetime.utcnow()  # marcar como cargado
                continue

        # Primero: si es Mercado Libre y ya tiene documento fiscal en la plataforma, no reemitir
        if ml_client and order.get("platform") == "Mercado Libre":
            pack_id = order.get("pack_id")
            if not pack_id:
                order_resp = ml_client.get_order(id_venta)
                if order_resp.get("success"):
                    pack_id = order_resp.get("pack_id") or id_venta
            if pack_id and ml_client.fiscal_document_uploaded(str(pack_id)) is True:
                sale = Sale.query.filter_by(user_id=user.id, id_venta=id_venta).first()
                if sale and not sale.document_uploaded_at:
                    sale.document_uploaded_at = datetime.utcnow()
                continue

        # Idempotencia: si ya existe Sale con este user_id + id_venta, skip o retry según status
        sale = Sale.query.filter_by(user_id=user.id, id_venta=id_venta).first()
        if sale:
            if getattr(sale, "document_uploaded_at", None):
                continue  # ya cargado en Falabella/ML, no reemitir
            if sale.status == "Éxito":
                continue
            if sale.status == "Error" and request.get_json() and request.get_json().get("retry"):
                pass  # Reintentar
            else:
                continue

        platform = order.get("platform") or "Manual"
        document_date = order.get("document_date")  # puede ser date o str ISO
        if document_date and hasattr(document_date, "isoformat"):
            pass
        elif document_date and isinstance(document_date, str):
            try:
                document_date = datetime.fromisoformat(document_date[:10]).date()
            except Exception:
                document_date = None
        else:
            document_date = None

        if not sale:
            sale = Sale(
                user_id=user.id,
                id_venta=id_venta,
                monto=monto,
                tipo_doc=tipo_doc,
                status="Pendiente",
                platform=platform,
                document_date=document_date,
            )
            db.session.add(sale)
            db.session.flush()
        else:
            if platform and not sale.platform:
                sale.platform = platform
            if document_date and not sale.document_date:
                sale.document_date = document_date

        result = haulmer.emit_document(tipo_doc=tipo_doc, id_venta=id_venta, monto=monto)
        if result.get("success"):
            sale.status = "Éxito"
            if not sale.document_date:
                sale.document_date = datetime.utcnow().date()
            doc = Document(
                user_id=user.id,
                sale_id=sale.id,
                pdf_url=result.get("pdf_url"),
                xml_url=result.get("xml_url"),
                haulmer_response=str(result.get("raw", "")),
            )
            db.session.add(doc)
            if falabella and order.get("platform") == "Falabella" and result.get("pdf_url"):
                upload = falabella.upload_document(id_venta, b"", "document.pdf")
                if upload.get("success"):
                    sale.document_uploaded_at = datetime.utcnow()
                    sale.upload_platform_response = str(upload.get("data", ""))[:2000]
                else:
                    logger.warning("Falabella upload failed for %s: %s", id_venta, upload.get("error"))
            if ml_client and order.get("platform") == "Mercado Libre" and result.get("pdf_url"):
                pack_id = order.get("pack_id") or (ml_client.get_order(id_venta).get("pack_id") or id_venta)
                try:
                    pdf_resp = requests.get(result["pdf_url"], timeout=30)
                    pdf_resp.raise_for_status()
                    pdf_content = pdf_resp.content
                except Exception as e:
                    logger.warning("Download PDF for ML upload %s: %s", id_venta, e)
                    pdf_content = None
                if pdf_content:
                    upload = ml_client.upload_fiscal_document(str(pack_id), pdf_content, "documento.pdf")
                    if upload.get("success"):
                        sale.document_uploaded_at = datetime.utcnow()
                        sale.upload_platform_response = str(upload.get("data", ""))[:2000]
                    else:
                        logger.warning("ML upload failed for %s: %s", id_venta, upload.get("error"))
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
