"""
Mercado Libre: OAuth (inicio + callback) y subida de documento fiscal.

Requiere en .env: ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REDIRECT_URI (exactamente la URL registrada en la app ML).
"""

import os
import requests
from flask import Blueprint, request, jsonify, redirect, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import base64

from app import db
from app.models import User
from app.crypto_utils import encrypt_value, decrypt_value
from app.services.mercadolibre_client import MercadoLibreClient, refresh_ml_token

ml_bp = Blueprint("mercado_libre", __name__)

# Dominio auth por país (ej. Chile: auth.mercadolibre.cl)
ML_AUTH_BASE = os.environ.get("ML_AUTH_BASE", "https://auth.mercadolibre.com.ar")


def _get_ml_credentials():
    cid = os.environ.get("ML_CLIENT_ID")
    secret = os.environ.get("ML_CLIENT_SECRET")
    redirect_uri = os.environ.get("ML_REDIRECT_URI")
    return cid, secret, redirect_uri


def _build_ml_auth_url():
    """Construye la URL de autorización ML con state=base64(user_id)."""
    client_id, _, redirect_uri = _get_ml_credentials()
    if not client_id or not redirect_uri:
        return None, "ML_CLIENT_ID y ML_REDIRECT_URI deben estar configurados en el servidor"
    user_id = get_jwt_identity()
    state = base64.urlsafe_b64encode(str(user_id).encode()).decode().rstrip("=")
    auth_url = (
        f"{ML_AUTH_BASE}/authorization"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )
    return auth_url, None


@ml_bp.route("/auth-url", methods=["GET"])
@jwt_required()
def auth_url():
    """
    GET: devuelve la URL de Mercado Libre para autorizar la app (para que el frontend redirija).
    Evita problemas de CORS con redirect 302.
    """
    auth_url_val, err = _build_ml_auth_url()
    if err:
        return jsonify({"error": err}), 500
    return jsonify({"url": auth_url_val})


@ml_bp.route("/auth", methods=["GET"])
@jwt_required()
def start_auth():
    """
    Redirige al usuario a Mercado Libre para autorizar la app.
    state = base64(user_id) para que el callback sepa a qué usuario asociar los tokens.
    """
    auth_url_val, err = _build_ml_auth_url()
    if err:
        return jsonify({"error": err}), 500
    return redirect(auth_url_val)


@ml_bp.route("/callback", methods=["GET"])
def oauth_callback():
    """
    ML redirige aquí con ?code=...&state=...
    Intercambia code por access_token y refresh_token, los guarda encriptados para el usuario.
    Como no tenemos state guardado por usuario, identificamos al usuario por el token que ML devuelve (user_id).
    Problema: en el callback no tenemos JWT. Opciones: (1) state = JWT o token temporal con user_id,
    (2) redirect_uri incluye frontend y el frontend envía code + user al backend. Aquí asumimos que el
    usuario que autorizó es el que tiene sesión; pero ML no redirige con user_id en query.
    Solución típica: state = encrypt(user_id) o un token de una sola vez que mapee a user_id.
    """
    client_id, client_secret, redirect_uri = _get_ml_credentials()
    if not all([client_id, client_secret, redirect_uri]):
        return redirect(f"{_frontend_url()}/config?ml_error=server_config")
    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        return redirect(f"{_frontend_url()}/config?ml_error=no_code")
    # state podría ser un token que contiene user_id (ej. JWT corto o id encriptado)
    # Por ahora: asumir un único usuario o pasar user_id en state (base64). Para multi-usuario
    # el frontend debe abrir /mercado-libre/auth con el usuario logueado y guardar state->user_id en cache.
    try:
        resp = requests.post(
            "https://api.mercadolibre.com/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return redirect(f"{_frontend_url()}/config?ml_error=token_exchange")
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    user_id_ml = str(data.get("user_id", ""))
    if not access_token or not refresh_token:
        return redirect(f"{_frontend_url()}/config?ml_error=no_tokens")
    # Recuperar user_id de nuestra app desde state (state = base64(user_id))
    try:
        pad = 4 - len(state or "") % 4
        if pad != 4:
            state = (state or "") + "=" * pad
        our_user_id = int(base64.urlsafe_b64decode(state or ""))
    except Exception:
        our_user_id = None
    if our_user_id is None:
        return redirect(f"{_frontend_url()}/config?ml_error=invalid_state")
    user = User.query.get(our_user_id)
    if not user:
        return redirect(f"{_frontend_url()}/config?ml_error=user_not_found")
    user.ml_access_token_enc = encrypt_value(access_token)
    user.ml_refresh_token_enc = encrypt_value(refresh_token)
    user.ml_user_id = user_id_ml
    db.session.commit()
    return redirect(f"{_frontend_url()}/config?ml_connected=1")


def _frontend_url():
    return os.environ.get("FRONTEND_URL", "http://localhost:3000")


def _get_client_for_user(user_id_int):
    user = User.query.get(int(user_id_int))
    if not user or not user.ml_access_token_enc:
        return None, "Conecta tu cuenta de Mercado Libre en Configuración (OAuth)."
    access_token = decrypt_value(user.ml_access_token_enc)
    # Opcional: si el token expiró (6h), usar refresh_token aquí
    return MercadoLibreClient(access_token), None


@ml_bp.route("/disconnect", methods=["POST"])
@jwt_required()
def disconnect():
    """Desconecta la cuenta de Mercado Libre del usuario (borra tokens)."""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    user.ml_access_token_enc = None
    user.ml_refresh_token_enc = None
    user.ml_user_id = None
    db.session.commit()
    return jsonify({"message": "Mercado Libre desconectado"})


@ml_bp.route("/orders", methods=["GET"])
@jwt_required()
def get_orders():
    """GET /mercado-libre/orders?limit=30&offset=0"""
    client, err = _get_client_for_user(get_jwt_identity())
    if err:
        return jsonify({"error": err}), 400
    result = client.get_orders(
        limit=int(request.args.get("limit", 30)),
        offset=int(request.args.get("offset", 0)),
    )
    if not result.get("success"):
        return jsonify({"error": result.get("error"), "details": result}), 502
    return jsonify(result.get("data", result))


@ml_bp.route("/upload-invoice", methods=["POST"])
@jwt_required()
def upload_invoice():
    """
    POST: sube el PDF de la boleta/factura al pack de ML.
    Body: pack_id (obligatorio), o order_id (se resuelve pack_id con GET /orders/{id}).
    Form-data o JSON con pdf en base64, o multipart file.
    """
    client, err = _get_client_for_user(get_jwt_identity())
    if err:
        return jsonify({"error": err}), 400
    pack_id = None
    pdf_content = None
    if request.is_json:
        data = request.get_json() or {}
        pack_id = data.get("pack_id")
        order_id = data.get("order_id")
        if not pack_id and order_id:
            order_resp = client.get_order(str(order_id))
            if not order_resp.get("success"):
                return jsonify({"error": order_resp.get("error", "Orden no encontrada")}), 502
            pack_id = order_resp.get("pack_id") or order_id
        pdf_b64 = data.get("pdf_base64")
        if pdf_b64:
            try:
                pdf_content = base64.b64decode(pdf_b64)
            except Exception as e:
                return jsonify({"error": f"PDF base64 inválido: {e}"}), 400
    else:
        pack_id = request.form.get("pack_id") or request.form.get("order_id")
        if request.files and "fiscal_document" in request.files:
            pdf_content = request.files["fiscal_document"].read()
        if not pack_id and request.form.get("order_id"):
            order_resp = client.get_order(request.form["order_id"])
            if order_resp.get("success"):
                pack_id = order_resp.get("pack_id") or request.form["order_id"]
    if not pack_id:
        return jsonify({"error": "Indica pack_id o order_id"}), 400
    if not pdf_content:
        return jsonify({"error": "Indica el PDF (pdf_base64 en JSON o fiscal_document en form)"}), 400
    result = client.upload_fiscal_document(str(pack_id), pdf_content)
    if not result.get("success"):
        return jsonify({"error": result.get("error"), "details": result}), 502
    return jsonify(result.get("data", result))
