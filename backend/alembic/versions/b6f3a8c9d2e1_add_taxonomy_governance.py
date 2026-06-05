"""add taxonomy governance tables

Revision ID: b6f3a8c9d2e1
Revises: ea418a384b9d
Create Date: 2026-06-04 10:20:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b6f3a8c9d2e1"
down_revision = "ea418a384b9d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "taxonomy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), server_default="enterprise", nullable=False),
        sa.Column("active_version_id", sa.Integer(), nullable=True),
        sa.Column("default_language", sa.String(), nullable=True),
        sa.Column("industry_context", sa.Text(), nullable=True),
        sa.Column("company_description", sa.Text(), nullable=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "taxonomy_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("taxonomy_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), server_default="draft", nullable=False),
        sa.Column("parent_version_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(), server_default="manual", nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confirmed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("health_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id"], ["taxonomy_version.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["taxonomy_id"], ["taxonomy.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "taxonomy_id", "version_number", name="uq_taxonomy_version_number"
        ),
    )
    op.create_index(
        op.f("ix_taxonomy_version_status"), "taxonomy_version", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_taxonomy_version_taxonomy_id"),
        "taxonomy_version",
        ["taxonomy_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_taxonomy_active_version_id",
        "taxonomy",
        "taxonomy_version",
        ["active_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "taxonomy_node",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("level", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("full_path", sa.Text(), nullable=False),
        sa.Column("path_node_ids", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("applicability", sa.Text(), nullable=False),
        sa.Column("exclusion", sa.Text(), nullable=True),
        sa.Column("positive_examples", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("negative_examples", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("synonyms", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("tagging_guidance", sa.Text(), nullable=True),
        sa.Column("conflict_rules", sa.Text(), nullable=True),
        sa.Column("source", sa.String(), server_default="manual", nullable=False),
        sa.Column("source_detail", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), server_default="draft", nullable=False),
        sa.Column("replacement_node_id", sa.String(), nullable=True),
        sa.Column("disabled_reason", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["taxonomy_node.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["taxonomy_version.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "code", name="uq_taxonomy_node_version_code"),
    )
    op.create_index(
        op.f("ix_taxonomy_node_level"), "taxonomy_node", ["level"], unique=False
    )
    op.create_index(
        op.f("ix_taxonomy_node_parent_id"),
        "taxonomy_node",
        ["parent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_taxonomy_node_status"), "taxonomy_node", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_taxonomy_node_version_id"),
        "taxonomy_node",
        ["version_id"],
        unique=False,
    )
    op.create_index(
        "ix_taxonomy_node_version_level_status",
        "taxonomy_node",
        ["version_id", "level", "status"],
        unique=False,
    )
    op.create_index(
        "ix_taxonomy_node_version_parent",
        "taxonomy_node",
        ["version_id", "parent_id"],
        unique=False,
    )

    op.create_table(
        "document_taxonomy_summary",
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("is_manual", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("model_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index(
        op.f("ix_document_taxonomy_summary_status"),
        "document_taxonomy_summary",
        ["status"],
        unique=False,
    )

    op.create_table(
        "taxonomy_tagging_task",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("source", sa.String(), server_default="summary", nullable=False),
        sa.Column("enable_optimization", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("optimization_strength", sa.String(), nullable=True),
        sa.Column("total_docs", sa.Integer(), nullable=False),
        sa.Column("processed_docs", sa.Integer(), nullable=False),
        sa.Column("failed_docs", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["taxonomy_version.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_taxonomy_tagging_task_status"),
        "taxonomy_tagging_task",
        ["status"],
        unique=False,
    )

    op.create_table(
        "document_taxonomy_tag",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("leaf_node_id", sa.String(), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("full_path_snapshot", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(), server_default="ai_recommended", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("unmatched_reason", sa.Text(), nullable=True),
        sa.Column("tagging_source_content", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("model_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("review_status", sa.String(), server_default="unconfirmed", nullable=False),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("invalidation_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["leaf_node_id"], ["taxonomy_node.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["taxonomy_tagging_task.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["taxonomy_version.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_document_taxonomy_tag_document_id"),
        "document_taxonomy_tag",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_taxonomy_tag_doc_status",
        "document_taxonomy_tag",
        ["document_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_document_taxonomy_tag_leaf_status",
        "document_taxonomy_tag",
        ["leaf_node_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_taxonomy_tag_leaf_node_id"),
        "document_taxonomy_tag",
        ["leaf_node_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_taxonomy_tag_status"),
        "document_taxonomy_tag",
        ["status"],
        unique=False,
    )

    op.create_table(
        "taxonomy_candidate_label",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("candidate_path", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), server_default="pending_review", nullable=False),
        sa.Column("redundancy_result", sa.Text(), nullable=False),
        sa.Column("suggested_reuse_node_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["suggested_reuse_node_id"], ["taxonomy_node.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["taxonomy_tagging_task.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_taxonomy_candidate_label_document_id"),
        "taxonomy_candidate_label",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_taxonomy_candidate_label_status"),
        "taxonomy_candidate_label",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_taxonomy_candidate_label_task_id"),
        "taxonomy_candidate_label",
        ["task_id"],
        unique=False,
    )

    op.create_table(
        "taxonomy_change_record",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("node_id", sa.String(), nullable=True),
        sa.Column("change_type", sa.String(), nullable=False),
        sa.Column("before_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("semantic_impact", sa.String(), nullable=True),
        sa.Column("affected_document_count", sa.Integer(), nullable=False),
        sa.Column("affected_leaf_count", sa.Integer(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confirmed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["node_id"], ["taxonomy_node.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["taxonomy_version.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_taxonomy_change_record_change_type"),
        "taxonomy_change_record",
        ["change_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_taxonomy_change_record_change_type"), table_name="taxonomy_change_record")
    op.drop_table("taxonomy_change_record")
    op.drop_index(op.f("ix_taxonomy_candidate_label_task_id"), table_name="taxonomy_candidate_label")
    op.drop_index(op.f("ix_taxonomy_candidate_label_status"), table_name="taxonomy_candidate_label")
    op.drop_index(op.f("ix_taxonomy_candidate_label_document_id"), table_name="taxonomy_candidate_label")
    op.drop_table("taxonomy_candidate_label")
    op.drop_index(op.f("ix_document_taxonomy_tag_status"), table_name="document_taxonomy_tag")
    op.drop_index(op.f("ix_document_taxonomy_tag_leaf_node_id"), table_name="document_taxonomy_tag")
    op.drop_index("ix_document_taxonomy_tag_leaf_status", table_name="document_taxonomy_tag")
    op.drop_index("ix_document_taxonomy_tag_doc_status", table_name="document_taxonomy_tag")
    op.drop_index(op.f("ix_document_taxonomy_tag_document_id"), table_name="document_taxonomy_tag")
    op.drop_table("document_taxonomy_tag")
    op.drop_index(op.f("ix_taxonomy_tagging_task_status"), table_name="taxonomy_tagging_task")
    op.drop_table("taxonomy_tagging_task")
    op.drop_index(op.f("ix_document_taxonomy_summary_status"), table_name="document_taxonomy_summary")
    op.drop_table("document_taxonomy_summary")
    op.drop_index("ix_taxonomy_node_version_parent", table_name="taxonomy_node")
    op.drop_index("ix_taxonomy_node_version_level_status", table_name="taxonomy_node")
    op.drop_index(op.f("ix_taxonomy_node_version_id"), table_name="taxonomy_node")
    op.drop_index(op.f("ix_taxonomy_node_status"), table_name="taxonomy_node")
    op.drop_index(op.f("ix_taxonomy_node_parent_id"), table_name="taxonomy_node")
    op.drop_index(op.f("ix_taxonomy_node_level"), table_name="taxonomy_node")
    op.drop_table("taxonomy_node")
    op.drop_constraint("fk_taxonomy_active_version_id", "taxonomy", type_="foreignkey")
    op.drop_index(op.f("ix_taxonomy_version_taxonomy_id"), table_name="taxonomy_version")
    op.drop_index(op.f("ix_taxonomy_version_status"), table_name="taxonomy_version")
    op.drop_table("taxonomy_version")
    op.drop_table("taxonomy")
