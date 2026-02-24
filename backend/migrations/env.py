# Alembic env - usar el mismo db que la app
from logging.config import fileConfig
from flask import Flask
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app, db
from app.models import User, Sale, Document
from alembic import context

config = context.config
# alembic.ini está en la raíz del backend, no dentro de migrations/
config_ini = config.config_file_name
if config_ini and not os.path.isabs(config_ini):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(root, "alembic.ini")
    if os.path.isfile(candidate):
        config_ini = candidate
if config_ini and os.path.isfile(config_ini):
    fileConfig(config_ini)
app = create_app()
target_metadata = db.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    from sqlalchemy import create_engine
    from app import create_app
    app = create_app()
    connectable = app.config["SQLALCHEMY_DATABASE_URI"]
    connectable = connectable.replace("postgres://", "postgresql://")
    engine = create_engine(connectable)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
