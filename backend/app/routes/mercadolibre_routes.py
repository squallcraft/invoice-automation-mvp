"""
Mercado Libre: OAuth (inicio + callback) y subida de documento fiscal.

Variables de entorno requeridas:
  ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REDIRECT_URI (exactamente la URL registrada en la app ML).
  ML_AUTH_BASE: dominio de autorización por país
    - Chile:     https://auth.mercadolibre.cl
    - Argentina: https://auth.mercadolibre.com.ar
"""
import base64
import logging
import os
from typing import Optional, Tuple

import requests as http_requests
from flask import Blueprint, request, jsonify, redirect
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.crypto_utils import decrypt_value, encrypt_value
from app.models import User
from app.services.mercadolibre_client import MercadoLibreClient, refresh_ml_token
from app.utils import err, require_user

logger = logging.getLogger(__name__)
ml_bp = Blueprint("mercado_libre", __name__)

ML_AUTH_BASE = os.environ.get("ML_AUTH_BASE", "https://auth.mercadolibre.com")


# ── Helpers ────────────────────────────────────────────────────────────────

def _ml_credentials() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    return (
        os.environ.get("ML_CLIENT_ID"),
        os.environ.get("ML_CLIENT_SECRET"),
        os.environ.get("ML_REDIRECT_URI"),
    )


def _frontend_url() -> str:
    return os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")


def _build_auth_url() -> Tuple[Optional[str], Optional[str]]:
    """Construye la URL de autorización ML con state=base64(user_id)."""
    client_id, _, redirect_uri = _ml_credentials()
    if not client_id or not redirect_uri:
        return None, "ML_CLIENT_ID y ML_REDIRECT_URI deben estar configurados en el servidor"
    user_id = get_jwt_identity()
    state = base64.urlsafe_b64encode(str(user_id).encode()).decode().rstrip("=")
    url = (
        f"{ML_AUTH_BASE}/authorization"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )
    return url, None


def _decode_state(state: Optional[str]) -> Optional[int]:
    """Decodifica state=base64(user_id) → int, o None si falla."""
    try:
        pad = 4 - len(state or "") % 4
        padded = (state or "") + ("=" * pad if pad != 4 else "")
        return int(base64.urlsafe_b64decode(padded))
    except Exception:
        return None


def _get_client(user: User) -> Tuple[Optional[MercadoLibreClient], Optional[Tuple]]:
    """
    Devuelve un MercadoLibreClient listo.
    Si el token expiró (401) lo refresca automáticamente y lo guarda en la BD.
    """
    if not user.ml_access_token_enc:
        return None, err("Conecta tu cuenta de Mercado Libre en Configuración (OAuth).")

    try:
        access_token = decrypt_value(user.ml_access_token_enc)
    except ValueError as e:
        return None, err(str(e))

    return MercadoLibreClient(access_token), None


def _refresh_token_for_user(user: User) -> Tuple[Optional[MercadoLibreClient], Optional[Tuple]]:
    """Intenta refrescar el token ML cuando la llamada principal devuelve 401."""
    client_id, client_secret, _ = _ml_credentials()
    if not (client_id and client_secret and user.ml_refresh_token_enc):
        return None, err(
            "Token de Mercado Libre expirado. Vuelve a conectar tu cuenta en Configuración."
        )
    try:
        refresh_token = decrypt_value(user.ml_refresh_token_enc)
    except ValueError as e:
        return None, err(str(e))

    result = refresh_ml_token(client_id, client_secret, refresh_token)
    if not result.get("success"):
        return None, err(
            "Token de Mercado Libre expirado. Vuelve a conectar tu cuenta en Configuración."
        )

    new_access  = result["data"]["access_token"]
    new_refresh = result["data"].get("refresh_token", refresh_token)
    user.ml_access_token_enc  = encrypt_value(new_access)
    user.ml_refresh_token_enc = encrypt_value(new_refresh)
    db.session.commit()
    return MercadoLibreClient(new_access), None


# ── OAuth ──────────────────────────────────────────────────────────────────

@ml_bp.route("/auth-url", methods=["GET"])
@jwt_required()
def auth_url():
    """Devuelve la URL de autorización ML para que el frontend redirija (evita CORS)."""
    url, error = _build_auth_url()
    if error:
        return jsonify({"error": error}), 503
    return jsonify({"url": url})


@ml_bp.route("/auth", methods=["GET"])
@jwt_required()
def start_auth():
    """Redirige al usuario a Mercado Libre para autorizar la app."""
    url, error = _build_auth_url()
    if error:
        return jsonify({"error": error}), 503
    return redirect(url)


@ml_bp.route("/callback", methods=["GET"])
def oauth_callback():
    """
    ML redirige aquí con ?code=...&state=...
    Intercambia el code por tokens y los guarda encriptados.
    """
    client_id, client_secret, redirect_uri = _ml_credentials()
    if not all([client_id, client_secret, redirect_uri]):
        return redirect(f"{_frontend_url()}/config?ml_error=server_config")

    code  = request.args.get("code")
    state = request.args.get("state")
    if not code:
        return redirect(f"{_frontend_url()}/config?ml_error=no_code")

    our_user_id = _decode_state(state)
    if our_user_id is None:
        return redirect(f"{_frontend_url()}/config?ml_error=invalid_state")

    user = db.session.get(User, our_user_id)
    if not user:
        return redirect(f"{_frontend_url()}/config?ml_error=user_not_found")

    try:
        resp = http_requests.post(
            "https://api.mercadolibre.com/oauth/token",
            data={
                "grant_type":    "authorization_code",
                "client_id":     client_id,
                "client_secret": client_secret,
                "code":          code,
                "redirect_uri":  redirect_uri,
            },
            headers={
                "Accept":       "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except http_requests.RequestException:
        return redirect(f"{_frontend_url()}/config?ml_error=token_exchange")

    access_token  = data.get("access_token")
    refresh_token = data.get("refresh_token")
    if not access_token or not refresh_token:
        return redirect(f"{_frontend_url()}/config?ml_error=no_tokens")

    user.ml_access_token_enc  = encrypt_value(access_token)
    user.ml_refresh_token_enc = encrypt_value(refresh_token)
    user.ml_user_id           = str(data.get("user_id", ""))
    db.session.commit()
    return redirect(f"{_frontend_url()}/config?ml_connected=1")


# ── Operaciones ────────────────────────────────────────────────────────────

@ml_bp.route("/disconnect", methods=["POST"])
@jwt_required()
def disconnect():
    """Desconecta la cuenta ML del usuario (borra tokens)."""
    user, error = require_user()
    if error:
        return error

    user.ml_access_token_enc  = None
    user.ml_refresh_token_enc = None
    user.ml_user_id           = None
    db.session.commit()
    return jsonify({"message": "Mercado Libre desconectado"})


@ml_bp.route("/orders", methods=["GET"])
@jwt_required()
def get_orders():
    """GET /mercado-libre/orders?limit=30&offset=0"""
    user, error = require_user()
    if error:
        return error

    client, error = _get_client(user)
    if error:
        return error

    try:
        limit  = int(request.args.get("limit", 30))
        offset = int(request.args.get("offset", 0))
    except (ValueError, TypeError):
        return err("limit y offset deben ser enteros")

    result = client.get_orders(limit=limit, offset=offset)

    # Refresco automático si el token expiró
    if not result.get("success") and "401" in str(result.get("error", "")):
        client, error = _refresh_token_for_user(user)
        if error:
            return error
        result = client.get_orders(limit=limit, offset=offset)

    if not result.get("success"):
        return jsonify({"error": result.get("error"), "details": result}), 502
    return jsonify(result.get("data", result))


@ml_bp.route("/upload-invoice", methods=["POST"])
@jwt_required()
def upload_invoice():
    """
    Sube el PDF de la boleta/factura al pack de ML.
    Body JSON: { pack_id, pdf_base64 }  o  multipart: { pack_id/order_id, fiscal_document }.
    """
    user, error = require_user()
    if error:
        return error

    client, error = _get_client(user)
    if error:
        return error

    pack_id     = None
    pdf_content = None

    if request.is_json:
        data    = request.get_json() or {}
        pack_id = data.get("pack_id")
        if not pack_id and data.get("order_id"):
            order_resp = client.get_order(str(data["order_id"]))
            if not order_resp.get("success"):
                return jsonify({"error": order_resp.get("error", "Orden no encontrada")}), 502
            pack_id = order_resp.get("pack_id") or data["order_id"]
        if data.get("pdf_base64"):
            try:
                pdf_content = base64.b64decode(data["pdf_base64"])
            except Exception as e:
                return err(f"PDF base64 inválido: {e}")
    else:
        pack_id = request.form.get("pack_id") or request.form.get("order_id")
        if "fiscal_document" in request.files:
            pdf_content = request.files["fiscal_document"].read()

    if not pack_id:
        return err("Indica pack_id o order_id")
    if not pdf_content:
        return err("Indica el PDF (pdf_base64 en JSON o fiscal_document en form)")

    result = client.upload_fiscal_document(str(pack_id), pdf_content)
    if not result.get("success"):
        return jsonify({"error": result.get("error"), "details": result}), 502
    return jsonify(result.get("data", result))
