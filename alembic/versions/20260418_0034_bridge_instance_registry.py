"""promote bridge config table into instance registry

Revision ID: 20260418_0034
Revises: 20260416_0033
Create Date: 2026-04-18 10:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260418_0034"
down_revision: str | None = "20260416_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if _has_table("customer_bridge_configs") and not _has_table("Bridge"):
        op.rename_table("customer_bridge_configs", "Bridge")

    if not _has_table("Bridge"):
        op.create_table(
            "Bridge",
            sa.Column(
                "customer_id",
                sa.Integer(),
                sa.ForeignKey("customers.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column(
                "instance_id",
                sa.String(length=255),
                nullable=False,
                server_default=sa.text("'default'"),
            ),
            sa.Column("base_url_internal", sa.String(length=500), nullable=True),
            sa.Column("audience", sa.String(length=255), nullable=True),
            sa.Column("tenant_id", sa.String(length=255), nullable=True),
            sa.Column(
                "status",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'inactive'"),
            ),
            sa.Column("request_timeout_seconds", sa.Integer(), nullable=True),
            sa.Column("request_retry_count", sa.Integer(), nullable=True),
            sa.Column("request_retry_backoff_seconds", sa.Float(), nullable=True),
            sa.Column("bridge_api_key", sa.String(length=255), nullable=True),
            sa.Column("last_online_status", sa.Boolean(), nullable=True),
            sa.Column("last_health_checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_health_error", sa.String(length=1000), nullable=True),
            sa.Column("cached_subscription_start_date", sa.String(length=50), nullable=True),
            sa.Column("cached_subscription_end_date", sa.String(length=50), nullable=True),
            sa.Column("cached_subscription_grace_period_end_date", sa.String(length=50), nullable=True),
            sa.Column("cached_subscription_is_active", sa.Boolean(), nullable=True),
            sa.Column("cached_subscription_status_message", sa.String(length=1000), nullable=True),
            sa.Column("last_subscription_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_subscription_error", sa.String(length=1000), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        return

    bridge_columns = _column_names("Bridge")
    if "instance_id" not in bridge_columns:
        op.add_column("Bridge", sa.Column("instance_id", sa.String(length=255), nullable=True))
    bridge_columns = _column_names("Bridge")
    if "base_url_internal" not in bridge_columns:
        if "bridge_base_url" in bridge_columns:
            op.alter_column(
                "Bridge",
                "bridge_base_url",
                new_column_name="base_url_internal",
                existing_type=sa.String(length=500),
                existing_nullable=True,
            )
        else:
            op.add_column("Bridge", sa.Column("base_url_internal", sa.String(length=500), nullable=True))
    bridge_columns = _column_names("Bridge")
    if "audience" not in bridge_columns:
        op.add_column("Bridge", sa.Column("audience", sa.String(length=255), nullable=True))
    if "tenant_id" not in bridge_columns:
        op.add_column("Bridge", sa.Column("tenant_id", sa.String(length=255), nullable=True))
    if "status" not in bridge_columns:
        op.add_column("Bridge", sa.Column("status", sa.String(length=50), nullable=True))
    if "request_timeout_seconds" not in bridge_columns:
        op.add_column("Bridge", sa.Column("request_timeout_seconds", sa.Integer(), nullable=True))
    if "request_retry_count" not in bridge_columns:
        op.add_column("Bridge", sa.Column("request_retry_count", sa.Integer(), nullable=True))
    if "request_retry_backoff_seconds" not in bridge_columns:
        op.add_column("Bridge", sa.Column("request_retry_backoff_seconds", sa.Float(), nullable=True))

    bridge_columns = _column_names("Bridge")
    if "instance_id" in bridge_columns:
        op.execute(
            sa.text(
                """
                UPDATE "Bridge"
                SET instance_id = :default_instance_id
                WHERE instance_id IS NULL OR btrim(instance_id) = ''
                """
            ).bindparams(default_instance_id="default")
        )
        op.alter_column(
            "Bridge",
            "instance_id",
            existing_type=sa.String(length=255),
            nullable=False,
            server_default=sa.text("'default'"),
        )

    if "status" in bridge_columns:
        if "bridge_is_enabled" in bridge_columns:
            op.execute(
                """
                UPDATE "Bridge"
                SET status = CASE
                    WHEN bridge_is_enabled THEN 'active'
                    ELSE 'inactive'
                END
                WHERE status IS NULL OR btrim(status) = ''
                """
            )
        op.execute(
            """
            UPDATE "Bridge"
            SET status = 'inactive'
            WHERE status IS NULL OR btrim(status) = ''
            """
        )
        op.alter_column(
            "Bridge",
            "status",
            existing_type=sa.String(length=50),
            nullable=False,
            server_default=sa.text("'inactive'"),
        )

    bridge_columns = _column_names("Bridge")
    if "audience" in bridge_columns:
        op.execute(
            """
            UPDATE "Bridge"
            SET audience = CONCAT('zaraamad:', COALESCE(NULLIF(instance_id, ''), 'default'))
            WHERE audience IS NULL OR btrim(audience) = ''
            """
        )
    if "tenant_id" in bridge_columns:
        op.execute(
            """
            UPDATE "Bridge"
            SET tenant_id = CAST(customer_id AS text)
            WHERE tenant_id IS NULL OR btrim(tenant_id) = ''
            """
        )

    bridge_columns = _column_names("Bridge")
    if "bridge_is_enabled" in bridge_columns:
        op.drop_column("Bridge", "bridge_is_enabled")


def downgrade() -> None:
    if not _has_table("Bridge"):
        return

    bridge_columns = _column_names("Bridge")
    if "bridge_is_enabled" not in bridge_columns:
        op.add_column(
            "Bridge",
            sa.Column(
                "bridge_is_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
        op.execute(
            """
            UPDATE "Bridge"
            SET bridge_is_enabled = CASE
                WHEN lower(coalesce(status, 'inactive')) = 'active' THEN true
                ELSE false
            END
            """
        )

    bridge_columns = _column_names("Bridge")
    if "base_url_internal" in bridge_columns and "bridge_base_url" not in bridge_columns:
        op.alter_column(
            "Bridge",
            "base_url_internal",
            new_column_name="bridge_base_url",
            existing_type=sa.String(length=500),
            existing_nullable=True,
        )

    for column_name in (
        "request_retry_backoff_seconds",
        "request_retry_count",
        "request_timeout_seconds",
        "status",
        "tenant_id",
        "audience",
        "instance_id",
    ):
        bridge_columns = _column_names("Bridge")
        if column_name in bridge_columns:
            op.drop_column("Bridge", column_name)

    if _has_table("Bridge") and not _has_table("customer_bridge_configs"):
        op.rename_table("Bridge", "customer_bridge_configs")
