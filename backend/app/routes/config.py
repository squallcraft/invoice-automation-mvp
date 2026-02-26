"""
Config: guardar y consultar credenciales de Haulmer y Falabella (encriptadas).
"""
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app import db
from app.crypto_utils import encrypt_value
from app.utils import err, require_user

logger = logging.getLogger(__name__)
config_bp = Blueprint("config", __name__)


@config_bp.route("/keys", methods=["GET", "PUT"])
@jwt_required()
def keys():
    """
    GET  → indica si las keys están configuradas (sin exponer valores).
    PUT  → guarda haulmer_api_key, falabella_user_id y/o falabella_api_key encriptadas.
    """
    user, error = require_user()
    if error:
        return error

    if request.method == "GET":
        return jsonify(_keys_status(user))

    try:
        data = request.get_json() or {}
        _apply_keys(user, data)
        db.session.commit()
        return jsonify({"message": "Credenciales actualizadas", **_keys_status(user)})
    except ValueError as e:
        logger.exception("Config keys ValueError: %s", e)
        return err(str(e))
    except Exception as e:
        logger.exception("Config keys error: %s", e)
        return err(f"Error al guardar: {e}", 500)


def _keys_status(user) -> dict:
    return {
        "haulmer_configured":         bool(user.haulmer_api_key_enc),
        "falabella_configured":        bool(user.falabella_api_key_enc and user.falabella_user_id),
        "falabella_user_id":           user.falabella_user_id or "",
        "mercado_libre_configured":    bool(user.ml_access_token_enc),
        "ml_user_id":                  (user.ml_user_id or "") if user.ml_access_token_enc else "",
    }


def _apply_keys(user, data: dict) -> None:
    if data.get("haulmer_api_key"):
        user.haulmer_api_key_enc = encrypt_value(data["haulmer_api_key"].strip())
    if "falabella_user_id" in data:
        user.falabella_user_id = (data["falabella_user_id"] or "").strip() or None
    if data.get("falabella_api_key"):
        user.falabella_api_key_enc = encrypt_value(data["falabella_api_key"].strip())
