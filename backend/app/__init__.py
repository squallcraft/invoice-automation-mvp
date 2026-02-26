"""
Invoice Automation MVP – Flask Application Factory.
"""
import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
logger = logging.getLogger(__name__)


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    # ── Configuración ──────────────────────────────────────────────────────
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key"),
        JWT_SECRET_KEY=os.environ.get(
            "JWT_SECRET_KEY", os.environ.get("SECRET_KEY", "jwt-secret")
        ),
        JWT_ACCESS_TOKEN_EXPIRES=3600 * 24,  # 24 h
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", "postgresql://localhost/invoice_automation"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # ── Pool settings ──────────────────────────────────────────────────
        # pool_pre_ping: testea la conexión antes de usarla del pool → evita
        # "connection already closed" tras reinicios de Docker o inactividad.
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_pre_ping": True,
            "pool_recycle": 280,     # recicla conexiones cada ~5 min
            "pool_timeout": 20,
            "pool_size": 5,
            "max_overflow": 10,
        },
    )

    if config:
        app.config.update(config)

    _warn_short_secret(app)

    # ── Extensiones ────────────────────────────────────────────────────────
    _setup_cors(app)
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # ── JWT errors → siempre JSON (evita 422) ──────────────────────────────
    @jwt.expired_token_loader
    def _expired(_header, _payload):
        return jsonify({"error": "Token expirado. Vuelve a iniciar sesión."}), 401

    @jwt.invalid_token_loader
    def _invalid(_err):
        return jsonify({"error": "Token inválido. Vuelve a iniciar sesión."}), 401

    @jwt.unauthorized_loader
    def _missing(_err):
        return jsonify({"error": "Autenticación requerida."}), 401

    # ── Error handlers globales ────────────────────────────────────────────
    @app.errorhandler(404)
    def _not_found(_e):
        return jsonify({"error": "Recurso no encontrado"}), 404

    @app.errorhandler(405)
    def _method_not_allowed(_e):
        return jsonify({"error": "Método no permitido"}), 405

    @app.errorhandler(500)
    def _server_error(e):
        logger.exception("Unhandled error: %s", e)
        return jsonify({"error": "Error interno del servidor"}), 500

    # ── Blueprints ─────────────────────────────────────────────────────────
    from app.routes import auth_bp, config_bp, auto_bp, dashboard_bp
    from app.routes.falabella_routes import falabella_bp
    from app.routes.mercadolibre_routes import ml_bp
    from app.routes.internal import internal_bp

    app.register_blueprint(auth_bp,      url_prefix="/auth")
    app.register_blueprint(config_bp,    url_prefix="/config")
    app.register_blueprint(auto_bp,      url_prefix="/auto")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(falabella_bp, url_prefix="/falabella")
    app.register_blueprint(ml_bp,        url_prefix="/mercado-libre")
    app.register_blueprint(internal_bp,  url_prefix="/internal")

    # ── Health ─────────────────────────────────────────────────────────────
    @app.route("/health")
    def health():
        try:
            db.session.execute(db.text("SELECT 1"))
            return jsonify({"status": "ok", "db": "ok"})
        except Exception as e:
            logger.error("Health DB check failed: %s", e)
            return jsonify({"status": "error", "db": str(e)}), 500

    # ── Scheduler (sincronización periódica) ───────────────────────────────
    _start_scheduler(app)

    return app


# ── Helpers privados ───────────────────────────────────────────────────────

def _warn_short_secret(app: Flask) -> None:
    secret = app.config.get("JWT_SECRET_KEY") or ""
    if len(secret) < 32:
        logger.warning(
            "JWT_SECRET_KEY tiene %d caracteres (mínimo recomendado: 32). "
            "Genera una con: python -c \"import secrets; print(secrets.token_hex(32))\"",
            len(secret),
        )


def _setup_cors(app: Flask) -> None:
    frontend_origin = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    origins = [frontend_origin]
    if "localhost:3000" in frontend_origin:
        origins.append("http://127.0.0.1:3000")
    CORS(
        app,
        origins=origins,
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )


def _start_scheduler(app: Flask) -> None:
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from app.tasks.sync_sales import run_sync_sales

        scheduler = BackgroundScheduler()

        def _job():
            with app.app_context():
                run_sync_sales()

        scheduler.add_job(_job, "interval", minutes=30, id="sync_sales")
        scheduler.start()
        logger.info("Scheduler iniciado: sync_sales cada 30 min.")
    except Exception as e:
        logger.warning(
            "Scheduler no iniciado: %s. "
            "Usa cron: GET /internal/sync-sales cada 10 min.",
            e,
        )
