from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetadataBaseSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class SourceInfo(MetadataBaseSchema):
    source_key: str
    source_name: str
    organization_code: str | None = None
    app_name: str
    app_version: str | None = None


class FieldMetadata(MetadataBaseSchema):
    field_name: str
    field_type: str
    db_column: str | None = None
    null: bool
    blank: bool
    required: bool
    primary_key: bool
    unique: bool
    editable: bool
    max_length: int | None = None
    default_value: str | None = None
    choices: list[Any] | None = None
    help_text: str | None = None
    relation_kind: str | None = None
    related_model: str | None = None
    auto_now: bool | None = None
    auto_now_add: bool | None = None


class ModelMetadata(MetadataBaseSchema):
    model_name: str
    model_label: str
    db_table: str
    verbose_name: str | None = None
    verbose_name_plural: str | None = None
    is_managed: bool | None = None
    is_proxy: bool | None = None
    fields: list[FieldMetadata] = Field(default_factory=list)


class AppMetadata(MetadataBaseSchema):
    app_label: str
    app_verbose_name: str | None = None
    models: list[ModelMetadata] = Field(default_factory=list)


class SnapshotMetadata(MetadataBaseSchema):
    generated_at: datetime
    generator_version: str
    apps: list[AppMetadata] = Field(default_factory=list)


class FullMetadataSyncPayload(MetadataBaseSchema):
    source: SourceInfo
    snapshot: SnapshotMetadata


class MetadataSyncResult(MetadataBaseSchema):
    source_key: str
    snapshot_hash: str
    entities_seen: int
    fields_seen: int
    entities_created: int
    entities_updated: int
    entities_deactivated: int
    fields_created: int
    fields_updated: int
    fields_deactivated: int
    sync_run_id: int
    status: str


class MetadataSourceSummary(MetadataBaseSchema):
    source_key: str
    source_name: str
    organization_code: str | None
    app_name: str
    app_version: str | None
    last_sync_at: datetime | None
    active_entities_count: int
    active_fields_count: int
    latest_sync_status: str | None
    latest_snapshot_hash: str | None


class MetadataFieldRead(MetadataBaseSchema):
    field_name: str
    field_type: str
    db_column: str | None
    null: bool
    blank: bool
    required: bool
    primary_key: bool
    unique: bool
    editable: bool
    max_length: int | None
    default_value: str | None
    choices_json: list[Any] | None
    help_text: str | None
    relation_kind: str | None
    related_model: str | None
    auto_now: bool | None
    auto_now_add: bool | None
    metadata_hash: str


class MetadataEntityRead(MetadataBaseSchema):
    app_label: str
    model_name: str
    model_label: str
    db_table: str
    verbose_name: str | None
    verbose_name_plural: str | None
    is_managed: bool | None
    is_proxy: bool | None
    metadata_hash: str


class MetadataEntityDetail(MetadataEntityRead):
    fields: list[MetadataFieldRead] = Field(default_factory=list)
