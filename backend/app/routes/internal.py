"""
Rutas internas: sync de ventas (llamable por cron o scheduler).
Protección: header X-Cron-Secret o solo localhost.
"""
import os
import logging
from flask import Blueprint, request, jsonify

from app.tasks.sync_sales import run_sync_sales

logger = logging.getLogger(__name__)
internal_bp = Blueprint("internal", __name__)


def _is_allowed():
    secret = os.environ.get("CRON_SECRET")
    if secret:
        return request.headers.get("X-Cron-Secret") == secret
    return request.remote_addr in ("127.0.0.1", "::1", None)


@internal_bp.route("/sync-sales", methods=["GET", "POST"])
def sync_sales():
    """
    Sincroniza ventas desde Falabella y Mercado Libre (crea Sales con platform y document_date).
    Llamar cada 10 min por cron: curl -H "X-Cron-Secret: TU_SECRET" http://localhost:5000/internal/sync-sales
    """
    if not _is_allowed():
        return jsonify({"error": "Forbidden"}), 403
    try:
        result = run_sync_sales()
        return jsonify(result)
    except Exception as e:
        logger.exception("sync_sales: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500
