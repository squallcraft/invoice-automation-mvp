# Blueprints
from app.routes.auth import auth_bp
from app.routes.config import config_bp
from app.routes.auto import auto_bp
from app.routes.dashboard import dashboard_bp
from app.routes.falabella_routes import falabella_bp

__all__ = ["auth_bp", "config_bp", "auto_bp", "dashboard_bp", "falabella_bp"]
