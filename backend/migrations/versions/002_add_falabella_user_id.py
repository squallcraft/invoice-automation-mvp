"""Add falabella_user_id to users

Revision ID: 002
Revises: 001
Create Date: 2025-02-22

"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"


def upgrade():
    op.add_column("users", sa.Column("falabella_user_id", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("users", "falabella_user_id")
