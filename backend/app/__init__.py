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

    CORS(app, origins=["http://localhost:3000"], supports_credentials=True)
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    from app.routes import auth_bp, config_bp, auto_bp, semi_bp, dashboard_bp
    from app.routes.falabella_routes import falabella_bp
    from app.routes.mercadolibre_routes import ml_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(config_bp, url_prefix="/config")
    app.register_blueprint(auto_bp, url_prefix="/auto")
    app.register_blueprint(semi_bp, url_prefix="/semi")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(falabella_bp, url_prefix="/falabella")
    app.register_blueprint(ml_bp, url_prefix="/mercado-libre")

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app
