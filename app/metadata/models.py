from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.database import Base, TimestampMixin


class MetadataSource(Base, TimestampMixin):
    __tablename__ = "metadata_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    app_name: Mapped[str] = mapped_column(String(255), nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sync_runs: Mapped[list["MetadataSyncRun"]] = relationship(
        "MetadataSyncRun",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    snapshots: Mapped[list["MetadataSnapshot"]] = relationship(
        "MetadataSnapshot",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    entities: Mapped[list["MetadataEntity"]] = relationship(
        "MetadataEntity",
        back_populates="source",
        cascade="all, delete-orphan",
    )


class MetadataSyncRun(Base):
    __tablename__ = "metadata_sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("metadata_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    models_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    fields_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source: Mapped[MetadataSource] = relationship("MetadataSource", back_populates="sync_runs")
    snapshots: Mapped[list["MetadataSnapshot"]] = relationship(
        "MetadataSnapshot",
        back_populates="sync_run",
        cascade="all, delete-orphan",
    )


class MetadataSnapshot(Base):
    __tablename__ = "metadata_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("metadata_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sync_run_id: Mapped[int] = mapped_column(
        ForeignKey("metadata_sync_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[object] = mapped_column(JSON(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    source: Mapped[MetadataSource] = relationship("MetadataSource", back_populates="snapshots")
    sync_run: Mapped[MetadataSyncRun] = relationship("MetadataSyncRun", back_populates="snapshots")


class MetadataEntity(Base, TimestampMixin):
    __tablename__ = "metadata_entities"
    __table_args__ = (
        Index("uq_metadata_entities_source_model_label", "source_id", "model_label", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("metadata_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    app_label: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_label: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    db_table: Mapped[str] = mapped_column(String(255), nullable=False)
    verbose_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verbose_name_plural: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_managed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_proxy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    metadata_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    source: Mapped[MetadataSource] = relationship("MetadataSource", back_populates="entities")
    fields: Mapped[list["MetadataField"]] = relationship(
        "MetadataField",
        back_populates="entity",
        cascade="all, delete-orphan",
    )


class MetadataField(Base, TimestampMixin):
    __tablename__ = "metadata_fields"
    __table_args__ = (
        Index("uq_metadata_fields_entity_field_name", "entity_id", "field_name", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("metadata_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    field_type: Mapped[str] = mapped_column(String(255), nullable=False)
    db_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    null: Mapped[bool] = mapped_column(Boolean, nullable=False)
    blank: Mapped[bool] = mapped_column(Boolean, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    primary_key: Mapped[bool] = mapped_column(Boolean, nullable=False)
    unique: Mapped[bool] = mapped_column(Boolean, nullable=False)
    editable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    max_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_value: Mapped[str | None] = mapped_column(Text(), nullable=True)
    choices_json: Mapped[object | None] = mapped_column(JSON(), nullable=True)
    help_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    relation_kind: Mapped[str | None] = mapped_column(String(100), nullable=True)
    related_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auto_now: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    auto_now_add: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    metadata_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    entity: Mapped[MetadataEntity] = relationship("MetadataEntity", back_populates="fields")
