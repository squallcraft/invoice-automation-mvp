"""Add platform, document_date, document_uploaded_at to sales

Revision ID: 005
Revises: 004
Create Date: 2026-02-24

"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"


def upgrade():
    op.add_column("sales", sa.Column("platform", sa.String(32), nullable=False, server_default="Manual"))
    op.add_column("sales", sa.Column("document_date", sa.Date(), nullable=True))
    op.add_column("sales", sa.Column("document_uploaded_at", sa.DateTime(), nullable=True))
    op.add_column("sales", sa.Column("upload_platform_response", sa.Text(), nullable=True))
    # Ampliar status por si acaso
    op.alter_column("sales", "status", existing_type=sa.String(20), type_=sa.String(32), existing_nullable=False)


def downgrade():
    op.alter_column("sales", "status", existing_type=sa.String(32), type_=sa.String(20), existing_nullable=False)
    op.drop_column("sales", "upload_platform_response")
    op.drop_column("sales", "document_uploaded_at")
    op.drop_column("sales", "document_date")
    op.drop_column("sales", "platform")
