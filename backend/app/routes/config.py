"""
Config: guardar credenciales Haulmer y Falabella de forma segura (encriptadas).
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User
from app.crypto_utils import encrypt_value

config_bp = Blueprint("config", __name__)


@config_bp.route("/keys", methods=["GET", "PUT"])
@jwt_required()
def keys():
    """
    GET: indica si el usuario tiene keys configuradas (no devuelve valores).
    PUT: guarda haulmer_api_key y/o falabella_api_key encriptadas.
    """
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    if request.method == "GET":
        return jsonify({
            "haulmer_configured": bool(user.haulmer_api_key_enc),
            "falabella_configured": bool(user.falabella_api_key_enc and user.falabella_user_id),
            "falabella_user_id": user.falabella_user_id or "",
            "mercado_libre_configured": bool(user.ml_access_token_enc),
            "ml_user_id": (user.ml_user_id or "") if user.ml_access_token_enc else "",
        })

    data = request.get_json() or {}
    if "haulmer_api_key" in data and data["haulmer_api_key"]:
        user.haulmer_api_key_enc = encrypt_value(data["haulmer_api_key"].strip())
    if "falabella_user_id" in data:
        user.falabella_user_id = (data["falabella_user_id"] or "").strip() or None
    if "falabella_api_key" in data and data["falabella_api_key"]:
        user.falabella_api_key_enc = encrypt_value(data["falabella_api_key"].strip())
    db.session.commit()
    return jsonify({
        "message": "Credenciales actualizadas",
        "haulmer_configured": bool(user.haulmer_api_key_enc),
        "falabella_configured": bool(user.falabella_api_key_enc and user.falabella_user_id),
        "mercado_libre_configured": bool(user.ml_access_token_enc),
    })
