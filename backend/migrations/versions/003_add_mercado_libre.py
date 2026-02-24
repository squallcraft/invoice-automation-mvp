"""Add Mercado Libre OAuth token fields to users

Revision ID: 003
Revises: 002
Create Date: 2025-02-23

"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"


def upgrade():
    op.add_column("users", sa.Column("ml_access_token_enc", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("ml_refresh_token_enc", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("ml_user_id", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("users", "ml_user_id")
    op.drop_column("users", "ml_refresh_token_enc")
    op.drop_column("users", "ml_access_token_enc")
