"""
Helpers compartidos por todos los blueprints: respuestas de error, acceso a usuario,
parseo de fechas.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, date
from typing import Any, Optional, Tuple, Union

from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from werkzeug.exceptions import HTTPException

from app import db
from app.models import User

logger = logging.getLogger(__name__)


# ── Respuestas de error ────────────────────────────────────────────────────

def err(message: str, code: int = 400) -> Tuple[Any, int]:
    """Devuelve una respuesta JSON de error estándar: {"error": message}."""
    return jsonify({"error": message}), code


# ── Acceso a usuario ───────────────────────────────────────────────────────

def current_user() -> Optional[User]:
    """Devuelve el User del JWT actual, o None si no existe."""
    try:
        uid = int(get_jwt_identity())
    except (TypeError, ValueError):
        return None
    return db.session.get(User, uid)


def require_user() -> Tuple[Optional[User], Optional[Tuple]]:
    """
    Devuelve (user, None) si el usuario existe, o (None, error_response) si no.
    Uso:
        user, error = require_user()
        if error:
            return error
    """
    user = current_user()
    if not user:
        return None, err("Usuario no encontrado", 404)
    return user, None


# ── Fechas ─────────────────────────────────────────────────────────────────

def parse_date(value: Any) -> Optional[date]:
    """Parsea str/date/datetime a date. Devuelve None si falla."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


# ── URL segura (sin contraseñas) ───────────────────────────────────────────

def safe_db_url(url: str) -> str:
    """Oculta la contraseña de una DATABASE_URL para loguear."""
    return re.sub(r":([^/@]+)@", ":***@", url)
