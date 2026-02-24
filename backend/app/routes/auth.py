"""
Auth: registro y login. Almacenamiento seguro de credentials.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app import db
from app.models import User
from app.crypto_utils import encrypt_value
import hashlib

auth_bp = Blueprint("auth", __name__)


def _hash_password(password: str) -> str:
    return hashlib.sha256((password + "invoice_mvp_salt").encode()).hexdigest()


@auth_bp.route("/register", methods=["POST"])
def register():
    """Registro de usuario nuevo. Guarda email y password hash."""
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email y password requeridos"}), 400
    if len(password) < 6:
        return jsonify({"error": "password mínimo 6 caracteres"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email ya registrado"}), 409

    user = User(
        email=email,
        password_hash=_hash_password(password),
    )
    db.session.add(user)
    db.session.commit()
    access_token = create_access_token(identity=user.id)
    return jsonify({
        "message": "Usuario registrado",
        "user_id": user.id,
        "email": user.email,
        "access_token": access_token,
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login: devuelve JWT si credentials correctas."""
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or user.password_hash != _hash_password(password):
        return jsonify({"error": "Credenciales inválidas"}), 401

    access_token = create_access_token(identity=user.id)
    return jsonify({
        "access_token": access_token,
        "user_id": user.id,
        "email": user.email,
    })
