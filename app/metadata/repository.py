from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.metadata.models import (
    MetadataEntity,
    MetadataField,
    MetadataSnapshot,
    MetadataSource,
    MetadataSyncRun,
)
from app.metadata.schemas import FieldMetadata, ModelMetadata, SourceInfo

UpsertAction = Literal["created", "updated", "unchanged"]


class MetadataRepository:
    def get_source_by_key(self, session: Session, source_key: str) -> MetadataSource | None:
        return session.scalar(
            select(MetadataSource).where(MetadataSource.source_key == source_key)
        )

    def create_source(self, session: Session, source: SourceInfo) -> MetadataSource:
        source_row = MetadataSource(
            source_key=source.source_key,
            source_name=source.source_name,
            organization_code=source.organization_code,
            app_name=source.app_name,
            app_version=source.app_version,
        )
        session.add(source_row)
        session.flush()
        return source_row

    def update_source(
        self,
        session: Session,
        source_row: MetadataSource,
        *,
        source_name: str,
        organization_code: str | None,
        app_name: str,
        app_version: str | None,
        last_sync_at: datetime | None = None,
    ) -> bool:
        changed = False
        if source_row.source_name != source_name:
            source_row.source_name = source_name
            changed = True
        if source_row.organization_code != organization_code:
            source_row.organization_code = organization_code
            changed = True
        if source_row.app_name != app_name:
            source_row.app_name = app_name
            changed = True
        if source_row.app_version != app_version:
            source_row.app_version = app_version
            changed = True
        if last_sync_at is not None and source_row.last_sync_at != last_sync_at:
            source_row.last_sync_at = last_sync_at
            changed = True
        if changed:
            session.add(source_row)
        return changed

    def create_sync_run(
        self,
        session: Session,
        *,
        source_id: int,
        snapshot_hash: str,
        status: str,
        started_at: datetime,
    ) -> MetadataSyncRun:
        sync_run = MetadataSyncRun(
            source_id=source_id,
            snapshot_hash=snapshot_hash,
            models_count=0,
            fields_count=0,
            status=status,
            started_at=started_at,
        )
        session.add(sync_run)
        session.flush()
        return sync_run

    def finish_sync_run_success(
        self,
        session: Session,
        *,
        sync_run: MetadataSyncRun,
        models_count: int,
        fields_count: int,
        finished_at: datetime,
    ) -> None:
        sync_run.models_count = models_count
        sync_run.fields_count = fields_count
        sync_run.status = "success"
        sync_run.error_message = None
        sync_run.finished_at = finished_at
        session.add(sync_run)

    def finish_sync_run_failure(
        self,
        session: Session,
        *,
        sync_run: MetadataSyncRun,
        error_message: str,
        finished_at: datetime,
    ) -> None:
        sync_run.status = "failed"
        sync_run.error_message = error_message[:4000]
        sync_run.finished_at = finished_at
        session.add(sync_run)

    def create_snapshot(
        self,
        session: Session,
        *,
        source_id: int,
        sync_run_id: int,
        snapshot_hash: str,
        payload_json: object,
    ) -> MetadataSnapshot:
        snapshot = MetadataSnapshot(
            source_id=source_id,
            sync_run_id=sync_run_id,
            snapshot_hash=snapshot_hash,
            payload_json=payload_json,
        )
        session.add(snapshot)
        session.flush()
        return snapshot

    def get_entities_by_source_id(
        self,
        session: Session,
        source_id: int,
    ) -> dict[str, MetadataEntity]:
        entities = list(
            session.scalars(
                select(MetadataEntity).where(MetadataEntity.source_id == source_id)
            ).all()
        )
        return {entity.model_label: entity for entity in entities}

    def get_fields_by_entity_ids(
        self,
        session: Session,
        entity_ids: Iterable[int],
    ) -> dict[tuple[int, str], MetadataField]:
        entity_id_list = list(entity_ids)
        if not entity_id_list:
            return {}
        fields = list(
            session.scalars(
                select(MetadataField).where(MetadataField.entity_id.in_(entity_id_list))
            ).all()
        )
        return {(field.entity_id, field.field_name): field for field in fields}

    def upsert_entity(
        self,
        session: Session,
        *,
        source_id: int,
        app_label: str,
        model: ModelMetadata,
        metadata_hash: str,
        existing_entity: MetadataEntity | None,
    ) -> tuple[MetadataEntity, UpsertAction]:
        if existing_entity is None:
            entity = MetadataEntity(
                source_id=source_id,
                app_label=app_label,
                model_name=model.model_name,
                model_label=model.model_label,
                db_table=model.db_table,
                verbose_name=model.verbose_name,
                verbose_name_plural=model.verbose_name_plural,
                is_managed=model.is_managed,
                is_proxy=model.is_proxy,
                is_active=True,
                metadata_hash=metadata_hash,
            )
            session.add(entity)
            session.flush()
            return entity, "created"

        if existing_entity.metadata_hash == metadata_hash and existing_entity.is_active:
            return existing_entity, "unchanged"

        existing_entity.app_label = app_label
        existing_entity.model_name = model.model_name
        existing_entity.model_label = model.model_label
        existing_entity.db_table = model.db_table
        existing_entity.verbose_name = model.verbose_name
        existing_entity.verbose_name_plural = model.verbose_name_plural
        existing_entity.is_managed = model.is_managed
        existing_entity.is_proxy = model.is_proxy
        existing_entity.is_active = True
        existing_entity.metadata_hash = metadata_hash
        session.add(existing_entity)
        return existing_entity, "updated"

    def upsert_field(
        self,
        session: Session,
        *,
        entity_id: int,
        field: FieldMetadata,
        metadata_hash: str,
        default_value: str | None,
        choices_json: list[object] | None,
        help_text: str | None,
        existing_field: MetadataField | None,
    ) -> tuple[MetadataField, UpsertAction]:
        if existing_field is None:
            field_row = MetadataField(
                entity_id=entity_id,
                field_name=field.field_name,
                field_type=field.field_type,
                db_column=field.db_column,
                null=field.null,
                blank=field.blank,
                required=field.required,
                primary_key=field.primary_key,
                unique=field.unique,
                editable=field.editable,
                max_length=field.max_length,
                default_value=default_value,
                choices_json=choices_json,
                help_text=help_text,
                relation_kind=field.relation_kind,
                related_model=field.related_model,
                auto_now=field.auto_now,
                auto_now_add=field.auto_now_add,
                is_active=True,
                metadata_hash=metadata_hash,
            )
            session.add(field_row)
            session.flush()
            return field_row, "created"

        if existing_field.metadata_hash == metadata_hash and existing_field.is_active:
            return existing_field, "unchanged"

        existing_field.field_type = field.field_type
        existing_field.db_column = field.db_column
        existing_field.null = field.null
        existing_field.blank = field.blank
        existing_field.required = field.required
        existing_field.primary_key = field.primary_key
        existing_field.unique = field.unique
        existing_field.editable = field.editable
        existing_field.max_length = field.max_length
        existing_field.default_value = default_value
        existing_field.choices_json = choices_json
        existing_field.help_text = help_text
        existing_field.relation_kind = field.relation_kind
        existing_field.related_model = field.related_model
        existing_field.auto_now = field.auto_now
        existing_field.auto_now_add = field.auto_now_add
        existing_field.is_active = True
        existing_field.metadata_hash = metadata_hash
        session.add(existing_field)
        return existing_field, "updated"

    def mark_missing_entities_inactive(
        self,
        session: Session,
        *,
        source_id: int,
        seen_model_labels: set[str],
    ) -> int:
        query = select(MetadataEntity).where(
            MetadataEntity.source_id == source_id,
            MetadataEntity.is_active.is_(True),
        )
        if seen_model_labels:
            query = query.where(MetadataEntity.model_label.not_in(seen_model_labels))
        missing_entities = list(session.scalars(query).all())
        for entity in missing_entities:
            entity.is_active = False
            session.add(entity)
        return len(missing_entities)

    def mark_missing_fields_inactive(
        self,
        session: Session,
        *,
        entity_ids_in_scope: set[int],
        seen_field_keys: set[tuple[int, str]],
    ) -> int:
        if not entity_ids_in_scope:
            return 0
        candidate_fields = list(
            session.scalars(
                select(MetadataField).where(
                    MetadataField.entity_id.in_(entity_ids_in_scope),
                    MetadataField.is_active.is_(True),
                )
            ).all()
        )
        deactivated_count = 0
        for field in candidate_fields:
            key = (field.entity_id, field.field_name)
            if key in seen_field_keys:
                continue
            field.is_active = False
            session.add(field)
            deactivated_count += 1
        return deactivated_count
