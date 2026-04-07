"""add metadata registry tables

Revision ID: 20260406_0030
Revises: 20260405_0029
Create Date: 2026-04-06 12:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260406_0030"
down_revision: str | None = "20260405_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metadata_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_key", sa.String(length=255), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("organization_code", sa.String(length=255), nullable=True),
        sa.Column("app_name", sa.String(length=255), nullable=False),
        sa.Column("app_version", sa.String(length=255), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_metadata_sources_source_key", "metadata_sources", ["source_key"], unique=True)

    op.create_table(
        "metadata_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("metadata_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("models_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fields_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_metadata_sync_runs_source_id", "metadata_sync_runs", ["source_id"], unique=False)
    op.create_index(
        "ix_metadata_sync_runs_snapshot_hash",
        "metadata_sync_runs",
        ["snapshot_hash"],
        unique=False,
    )

    op.create_table(
        "metadata_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("metadata_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "sync_run_id",
            sa.Integer(),
            sa.ForeignKey("metadata_sync_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_metadata_snapshots_source_id", "metadata_snapshots", ["source_id"], unique=False)
    op.create_index("ix_metadata_snapshots_sync_run_id", "metadata_snapshots", ["sync_run_id"], unique=False)
    op.create_index("ix_metadata_snapshots_snapshot_hash", "metadata_snapshots", ["snapshot_hash"], unique=False)

    op.create_table(
        "metadata_entities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("metadata_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("app_label", sa.String(length=255), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_label", sa.String(length=255), nullable=False),
        sa.Column("db_table", sa.String(length=255), nullable=False),
        sa.Column("verbose_name", sa.String(length=255), nullable=True),
        sa.Column("verbose_name_plural", sa.String(length=255), nullable=True),
        sa.Column("is_managed", sa.Boolean(), nullable=True),
        sa.Column("is_proxy", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("metadata_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_id", "model_label", name="uq_metadata_entities_source_model_label"),
    )
    op.create_index("ix_metadata_entities_source_id", "metadata_entities", ["source_id"], unique=False)
    op.create_index("ix_metadata_entities_app_label", "metadata_entities", ["app_label"], unique=False)
    op.create_index("ix_metadata_entities_model_label", "metadata_entities", ["model_label"], unique=False)
    op.create_index("ix_metadata_entities_metadata_hash", "metadata_entities", ["metadata_hash"], unique=False)

    op.create_table(
        "metadata_fields",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_id", sa.Integer(), sa.ForeignKey("metadata_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("field_type", sa.String(length=255), nullable=False),
        sa.Column("db_column", sa.String(length=255), nullable=True),
        sa.Column("null", sa.Boolean(), nullable=False),
        sa.Column("blank", sa.Boolean(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("primary_key", sa.Boolean(), nullable=False),
        sa.Column("unique", sa.Boolean(), nullable=False),
        sa.Column("editable", sa.Boolean(), nullable=False),
        sa.Column("max_length", sa.Integer(), nullable=True),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("choices_json", sa.JSON(), nullable=True),
        sa.Column("help_text", sa.Text(), nullable=True),
        sa.Column("relation_kind", sa.String(length=100), nullable=True),
        sa.Column("related_model", sa.String(length=255), nullable=True),
        sa.Column("auto_now", sa.Boolean(), nullable=True),
        sa.Column("auto_now_add", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("metadata_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("entity_id", "field_name", name="uq_metadata_fields_entity_field_name"),
    )
    op.create_index("ix_metadata_fields_entity_id", "metadata_fields", ["entity_id"], unique=False)
    op.create_index("ix_metadata_fields_field_name", "metadata_fields", ["field_name"], unique=False)
    op.create_index("ix_metadata_fields_metadata_hash", "metadata_fields", ["metadata_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_metadata_fields_metadata_hash", table_name="metadata_fields")
    op.drop_index("ix_metadata_fields_field_name", table_name="metadata_fields")
    op.drop_index("ix_metadata_fields_entity_id", table_name="metadata_fields")
    op.drop_table("metadata_fields")

    op.drop_index("ix_metadata_entities_metadata_hash", table_name="metadata_entities")
    op.drop_index("ix_metadata_entities_model_label", table_name="metadata_entities")
    op.drop_index("ix_metadata_entities_app_label", table_name="metadata_entities")
    op.drop_index("ix_metadata_entities_source_id", table_name="metadata_entities")
    op.drop_table("metadata_entities")

    op.drop_index("ix_metadata_snapshots_snapshot_hash", table_name="metadata_snapshots")
    op.drop_index("ix_metadata_snapshots_sync_run_id", table_name="metadata_snapshots")
    op.drop_index("ix_metadata_snapshots_source_id", table_name="metadata_snapshots")
    op.drop_table("metadata_snapshots")

    op.drop_index("ix_metadata_sync_runs_snapshot_hash", table_name="metadata_sync_runs")
    op.drop_index("ix_metadata_sync_runs_source_id", table_name="metadata_sync_runs")
    op.drop_table("metadata_sync_runs")

    op.drop_index("ix_metadata_sources_source_key", table_name="metadata_sources")
    op.drop_table("metadata_sources")
