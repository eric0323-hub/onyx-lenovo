"""Add external retrieval sources

Revision ID: c4d5e6f7a8b9
Revises: b6f3a8c9d2e1
Create Date: 2026-06-08 14:05:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c4d5e6f7a8b9"
down_revision = "b6f3a8c9d2e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_retrieval_source",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("adapter_type", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("credentials", sa.LargeBinary(), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("timeout_ms", sa.Integer(), nullable=False),
        sa.Column("max_results", sa.Integer(), nullable=False),
        sa.Column("source_weight", sa.Float(), nullable=False),
        sa.Column("min_confidence", sa.Float(), nullable=True),
        sa.Column("call_strategy", sa.String(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "time_created",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "time_updated",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "external_retrieval_source__document_set",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_retrieval_source_id", sa.Integer(), nullable=False),
        sa.Column("document_set_id", sa.Integer(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_set_id"], ["document_set.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["external_retrieval_source_id"],
            ["external_retrieval_source.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "external_retrieval_source_id",
            "document_set_id",
            name="uq_external_retrieval_source_document_set",
        ),
    )


def downgrade() -> None:
    op.drop_table("external_retrieval_source__document_set")
    op.drop_table("external_retrieval_source")

