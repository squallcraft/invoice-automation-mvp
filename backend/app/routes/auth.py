"""
Auth: registro y login con JWT.
- Contraseñas nuevas: werkzeug generate_password_hash (pbkdf2:sha256).
- Compatibilidad con hashes legados sha256+salt (migración transparente al primer login).
"""
import hashlib
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models import User
from app.utils import err

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

_LEGACY_SALT = "invoice_mvp_salt"


def _legacy_hash(password: str) -> str:
    return hashlib.sha256((password + _LEGACY_SALT).encode()).hexdigest()


def _verify_password(plain: str, stored_hash: str) -> bool:
    """Verifica contra werkzeug o el hash legado sha256."""
    if stored_hash.startswith("pbkdf2:") or stored_hash.startswith("scrypt:"):
        return check_password_hash(stored_hash, plain)
    return stored_hash == _legacy_hash(plain)


def _make_token(user: User) -> dict:
    return {
        "access_token": create_access_token(identity=user.id),
        "user_id": user.id,
        "email": user.email,
    }


@auth_bp.route("/register", methods=["OPTIONS", "POST"])
def register():
    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return err("email y password son requeridos")
    if len(password) < 6:
        return err("El password debe tener al menos 6 caracteres")
    if User.query.filter_by(email=email).first():
        return err("El email ya está registrado", 409)

    user = User(
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({**_make_token(user), "message": "Usuario registrado"}), 201


@auth_bp.route("/login", methods=["OPTIONS", "POST"])
def login():
    if request.method == "OPTIONS":
        return "", 204

    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        user = User.query.filter_by(email=email).first()
        if not user or not _verify_password(password, user.password_hash):
            return err("Credenciales inválidas", 401)

        # Migración transparente: reemplaza hash legado por werkzeug
        if not user.password_hash.startswith(("pbkdf2:", "scrypt:")):
            user.password_hash = generate_password_hash(password)
            db.session.commit()

        return jsonify(_make_token(user))

    except Exception as e:
        logger.exception("Login error: %s", e)
        return err("Error interno en login", 500)
