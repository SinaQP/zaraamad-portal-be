"""add form service tables and seed canonical forms

Revision ID: 20260404_0028
Revises: 20260325_0027
Create Date: 2026-04-04 11:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.forms.service import FormSeedService

revision: str = "20260404_0028"
down_revision: str | None = "20260325_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "form_schemas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "scope_type",
            sa.Enum(
                "global",
                "municipality",
                name="form_scope_type",
            ),
            nullable=False,
        ),
        sa.Column("scope_value", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "(scope_type = 'global' AND scope_value IS NULL) OR "
            "(scope_type = 'municipality' AND scope_value IS NOT NULL)",
            name="ck_form_schemas_scope_value",
        ),
    )
    op.create_index(
        "ix_form_schemas_key_scope_active",
        "form_schemas",
        ["key", "scope_type", "scope_value", "is_active"],
        unique=False,
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_form_schemas_key_scope_value_version "
        "ON form_schemas (key, scope_type, coalesce(scope_value, ''), version)"
    )

    op.create_table(
        "form_fields",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("form_id", sa.Integer(), sa.ForeignKey("form_schemas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_field_id", sa.Integer(), sa.ForeignKey("form_fields.id", ondelete="CASCADE"), nullable=True),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "text",
                "number",
                "checkbox",
                "date",
                "work-holiday",
                "select",
                "certificate-number",
                "radio",
                "text-area",
                "compound",
                "floor-area",
                name="form_field_type",
            ),
            nullable=False,
        ),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("placeholder", sa.String(length=255), nullable=True),
        sa.Column("default_value", sa.JSON(), nullable=True),
        sa.Column("validation", sa.JSON(), nullable=True),
        sa.Column("source", sa.JSON(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column(
            "binding",
            sa.Enum(
                "fixed",
                "dynamic",
                name="form_binding_type",
            ),
            nullable=False,
            server_default="dynamic",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_form_fields_form_id", "form_fields", ["form_id"], unique=False)
    op.create_index("ix_form_fields_parent_field_id", "form_fields", ["parent_field_id"], unique=False)
    op.create_index(
        "uq_form_fields_form_key",
        "form_fields",
        ["form_id", "key"],
        unique=True,
    )

    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        FormSeedService(db_session=session).apply_seed_definitions(commit=False)
        session.flush()
    finally:
        session.close()


def downgrade() -> None:
    op.drop_index("uq_form_fields_form_key", table_name="form_fields")
    op.drop_index("ix_form_fields_parent_field_id", table_name="form_fields")
    op.drop_index("ix_form_fields_form_id", table_name="form_fields")
    op.drop_table("form_fields")

    op.execute("DROP INDEX uq_form_schemas_key_scope_value_version")
    op.drop_index("ix_form_schemas_key_scope_active", table_name="form_schemas")
    op.drop_table("form_schemas")

    bind = op.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == "postgresql":
        op.execute("DROP TYPE IF EXISTS form_binding_type")
        op.execute("DROP TYPE IF EXISTS form_field_type")
        op.execute("DROP TYPE IF EXISTS form_scope_type")
