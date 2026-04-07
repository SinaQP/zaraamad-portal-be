from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.metadata.constants import SYNC_STATUS_FAILED, SYNC_STATUS_IN_PROGRESS, SYNC_STATUS_SUCCESS
from app.metadata.repository import MetadataRepository
from app.metadata.schemas import FullMetadataSyncPayload, MetadataSyncResult
from app.metadata.utils import (
    compute_entity_hash,
    compute_field_hash,
    compute_snapshot_hash,
    normalize_choices,
    normalize_default_value,
    normalize_help_text,
)


@dataclass
class _SyncCounters:
    entities_seen: int = 0
    fields_seen: int = 0
    entities_created: int = 0
    entities_updated: int = 0
    entities_deactivated: int = 0
    fields_created: int = 0
    fields_updated: int = 0
    fields_deactivated: int = 0


class MetadataSyncService:
    def __init__(self, repository: MetadataRepository | None = None) -> None:
        self._repository = repository or MetadataRepository()

    def sync_full_snapshot(
        self,
        session: Session,
        payload: FullMetadataSyncPayload,
    ) -> MetadataSyncResult:
        validated_payload = FullMetadataSyncPayload.model_validate(payload)
        snapshot_hash = compute_snapshot_hash(validated_payload)
        source_info = validated_payload.source

        source = self._repository.get_source_by_key(session, source_info.source_key)
        if source is None:
            source = self._repository.create_source(session, source_info)
        else:
            self._repository.update_source(
                session,
                source,
                source_name=source_info.source_name,
                organization_code=source_info.organization_code,
                app_name=source_info.app_name,
                app_version=source_info.app_version,
            )

        started_at = self._utc_now()
        sync_run = self._repository.create_sync_run(
            session,
            source_id=source.id,
            snapshot_hash=snapshot_hash,
            status=SYNC_STATUS_IN_PROGRESS,
            started_at=started_at,
        )
        self._repository.create_snapshot(
            session,
            source_id=source.id,
            sync_run_id=sync_run.id,
            snapshot_hash=snapshot_hash,
            payload_json=validated_payload.model_dump(mode="json"),
        )

        try:
            with session.begin_nested():
                counters = self._run_full_sync(
                    session=session,
                    source_id=source.id,
                    payload=validated_payload,
                )
                finished_at = self._utc_now()
                self._repository.update_source(
                    session,
                    source,
                    source_name=source_info.source_name,
                    organization_code=source_info.organization_code,
                    app_name=source_info.app_name,
                    app_version=source_info.app_version,
                    last_sync_at=finished_at,
                )
                self._repository.finish_sync_run_success(
                    session,
                    sync_run=sync_run,
                    models_count=counters.entities_seen,
                    fields_count=counters.fields_seen,
                    finished_at=finished_at,
                )
        except Exception as exc:
            self._repository.finish_sync_run_failure(
                session,
                sync_run=sync_run,
                error_message=str(exc),
                finished_at=self._utc_now(),
            )
            session.commit()
            raise

        session.commit()
        return MetadataSyncResult(
            source_key=source.source_key,
            snapshot_hash=snapshot_hash,
            entities_seen=counters.entities_seen,
            fields_seen=counters.fields_seen,
            entities_created=counters.entities_created,
            entities_updated=counters.entities_updated,
            entities_deactivated=counters.entities_deactivated,
            fields_created=counters.fields_created,
            fields_updated=counters.fields_updated,
            fields_deactivated=counters.fields_deactivated,
            sync_run_id=sync_run.id,
            status=SYNC_STATUS_SUCCESS,
        )

    def _run_full_sync(
        self,
        *,
        session: Session,
        source_id: int,
        payload: FullMetadataSyncPayload,
    ) -> _SyncCounters:
        counters = _SyncCounters()
        existing_entities = self._repository.get_entities_by_source_id(session, source_id)
        existing_fields = self._repository.get_fields_by_entity_ids(
            session,
            [entity.id for entity in existing_entities.values()],
        )
        seen_model_labels: set[str] = set()
        seen_entity_ids: set[int] = set()
        seen_field_keys: set[tuple[int, str]] = set()

        for app_metadata in payload.snapshot.apps:
            for model_metadata in app_metadata.models:
                counters.entities_seen += 1
                existing_entity = existing_entities.get(model_metadata.model_label)
                entity_hash = compute_entity_hash(model_metadata)
                entity, entity_action = self._repository.upsert_entity(
                    session,
                    source_id=source_id,
                    app_label=app_metadata.app_label,
                    model=model_metadata,
                    metadata_hash=entity_hash,
                    existing_entity=existing_entity,
                )
                existing_entities[model_metadata.model_label] = entity
                seen_model_labels.add(model_metadata.model_label)
                seen_entity_ids.add(entity.id)
                if entity_action == "created":
                    counters.entities_created += 1
                elif entity_action == "updated":
                    counters.entities_updated += 1

                for field_metadata in model_metadata.fields:
                    counters.fields_seen += 1
                    field_hash = compute_field_hash(field_metadata)
                    field_key = (entity.id, field_metadata.field_name)
                    existing_field = existing_fields.get(field_key)
                    field_row, field_action = self._repository.upsert_field(
                        session,
                        entity_id=entity.id,
                        field=field_metadata,
                        metadata_hash=field_hash,
                        default_value=normalize_default_value(field_metadata.default_value),
                        choices_json=normalize_choices(field_metadata.choices),
                        help_text=normalize_help_text(field_metadata.help_text),
                        existing_field=existing_field,
                    )
                    existing_fields[field_key] = field_row
                    seen_field_keys.add(field_key)
                    if field_action == "created":
                        counters.fields_created += 1
                    elif field_action == "updated":
                        counters.fields_updated += 1

        counters.entities_deactivated = self._repository.mark_missing_entities_inactive(
            session,
            source_id=source_id,
            seen_model_labels=seen_model_labels,
        )
        counters.fields_deactivated = self._repository.mark_missing_fields_inactive(
            session,
            entity_ids_in_scope=seen_entity_ids,
            seen_field_keys=seen_field_keys,
        )
        return counters

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)
