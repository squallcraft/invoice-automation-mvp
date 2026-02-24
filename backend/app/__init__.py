"""
Invoice Automation MVP - Flask Application Factory.
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", "postgresql://localhost/invoice_automation"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", os.environ.get("SECRET_KEY", "jwt-secret")),
        JWT_ACCESS_TOKEN_EXPIRES=3600 * 24,  # 24 horas
    )
    if config:
        app.config.update(config)

    frontend_origin = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    CORS(app, origins=[frontend_origin.rstrip("/")], supports_credentials=True)
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    from app.routes import auth_bp, config_bp, auto_bp, dashboard_bp
    from app.routes.falabella_routes import falabella_bp
    from app.routes.mercadolibre_routes import ml_bp
    from app.routes.internal import internal_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(config_bp, url_prefix="/config")
    app.register_blueprint(auto_bp, url_prefix="/auto")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(falabella_bp, url_prefix="/falabella")
    app.register_blueprint(ml_bp, url_prefix="/mercado-libre")
    app.register_blueprint(internal_bp, url_prefix="/internal")

    @app.route("/health")
    def health():
        return {"status": "ok"}

    # Tarea programada: traer ventas de Falabella/ML cada 10 min (solo si no hay múltiples workers)
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from app.tasks.sync_sales import run_sync_sales
        scheduler = BackgroundScheduler()
        def _job():
            with app.app_context():
                run_sync_sales()
        scheduler.add_job(_job, "interval", minutes=10, id="sync_sales")
        scheduler.start()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Scheduler no iniciado: %s. Usa cron: GET /internal/sync-sales cada 10 min.", e)

    return app
