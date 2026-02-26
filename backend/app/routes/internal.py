"""
Rutas internas: sincronización de ventas (cron o scheduler).
Protección: header X-Cron-Secret o solo localhost.
"""
import logging
import os

from flask import Blueprint, request, jsonify

from app.tasks.sync_sales import run_sync_sales
from app.utils import err

logger = logging.getLogger(__name__)
internal_bp = Blueprint("internal", __name__)


def _is_allowed() -> bool:
    secret = os.environ.get("CRON_SECRET")
    if secret:
        return request.headers.get("X-Cron-Secret") == secret
    return request.remote_addr in ("127.0.0.1", "::1", None)


@internal_bp.route("/sync-sales", methods=["GET", "POST"])
def sync_sales():
    """
    Sincroniza ventas desde Falabella y ML para todos los usuarios.
    Llamar por cron cada 10 min:
      curl -H "X-Cron-Secret: TU_SECRET" http://localhost:5000/internal/sync-sales
    """
    if not _is_allowed():
        return err("Forbidden", 403)
    try:
        return jsonify(run_sync_sales())
    except Exception as e:
        logger.exception("sync_sales: %s", e)
        return err(str(e), 500)
