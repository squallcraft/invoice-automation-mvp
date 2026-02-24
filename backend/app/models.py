"""
Modelos de base de datos - PostgreSQL con SQLAlchemy.
Idempotencia: id_venta único por usuario para evitar duplicados.
"""
from datetime import datetime
from app import db


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    haulmer_api_key_enc = db.Column(db.LargeBinary, nullable=True)  # Encriptada con Fernet
    falabella_user_id = db.Column(db.String(255), nullable=True)  # Email Seller Center (UserID)
    falabella_api_key_enc = db.Column(db.LargeBinary, nullable=True)
    # Mercado Libre OAuth (encriptados)
    ml_access_token_enc = db.Column(db.LargeBinary, nullable=True)
    ml_refresh_token_enc = db.Column(db.LargeBinary, nullable=True)
    ml_user_id = db.Column(db.String(64), nullable=True)  # ML user_id numérico
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sales = db.relationship("Sale", backref="user", lazy="dynamic")
    documents = db.relationship("Document", backref="user", lazy="dynamic", foreign_keys="Document.user_id")


class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    id_venta = db.Column(db.String(120), nullable=False)  # ID externo (Falabella, etc.)
    monto = db.Column(db.Numeric(12, 2), nullable=False)
    tipo_doc = db.Column(db.String(20), nullable=False)  # 'Boleta' | 'Factura'
    status = db.Column(db.String(20), nullable=False, default="Pendiente")  # Pendiente | Éxito | Error
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constraint único por usuario + id_venta para idempotencia
    __table_args__ = (db.UniqueConstraint("user_id", "id_venta", name="uq_user_id_venta"),)

    documents = db.relationship("Document", backref="sale", uselist=True, lazy="dynamic")


class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    pdf_url = db.Column(db.String(500), nullable=True)
    xml_url = db.Column(db.String(500), nullable=True)
    haulmer_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
