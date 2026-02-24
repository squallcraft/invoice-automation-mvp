"""Add is_admin to users

Revision ID: 004
Revises: 003
Create Date: 2026-02-24

"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"


def upgrade():
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("users", "is_admin")
