from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.metadata.models import MetadataEntity, MetadataField, MetadataSource, MetadataSyncRun
from app.metadata.repository import MetadataRepository
from app.metadata.schemas import (
    MetadataEntityDetail,
    MetadataEntityRead,
    MetadataFieldRead,
    MetadataSourceSummary,
)


class MetadataQueryService:
    def __init__(self, repository: MetadataRepository | None = None) -> None:
        self._repository = repository or MetadataRepository()

    def get_source_summary(self, session: Session, source_key: str) -> MetadataSourceSummary | None:
        source = self._repository.get_source_by_key(session, source_key)
        if source is None:
            return None
        latest_sync = session.scalar(
            select(MetadataSyncRun)
            .where(MetadataSyncRun.source_id == source.id)
            .order_by(MetadataSyncRun.started_at.desc(), MetadataSyncRun.id.desc())
            .limit(1)
        )
        active_entities_count = int(
            session.scalar(
                select(func.count(MetadataEntity.id)).where(
                    MetadataEntity.source_id == source.id,
                    MetadataEntity.is_active.is_(True),
                )
            )
            or 0
        )
        active_fields_count = int(
            session.scalar(
                select(func.count(MetadataField.id))
                .join(MetadataEntity, MetadataField.entity_id == MetadataEntity.id)
                .where(
                    MetadataEntity.source_id == source.id,
                    MetadataEntity.is_active.is_(True),
                    MetadataField.is_active.is_(True),
                )
            )
            or 0
        )
        return MetadataSourceSummary(
            source_key=source.source_key,
            source_name=source.source_name,
            organization_code=source.organization_code,
            app_name=source.app_name,
            app_version=source.app_version,
            last_sync_at=source.last_sync_at,
            active_entities_count=active_entities_count,
            active_fields_count=active_fields_count,
            latest_sync_status=latest_sync.status if latest_sync is not None else None,
            latest_snapshot_hash=latest_sync.snapshot_hash if latest_sync is not None else None,
        )

    def list_active_entities_for_source(
        self,
        session: Session,
        source_key: str,
    ) -> list[MetadataEntityRead]:
        source = self._repository.get_source_by_key(session, source_key)
        if source is None:
            return []
        entities = list(
            session.scalars(
                select(MetadataEntity)
                .where(
                    MetadataEntity.source_id == source.id,
                    MetadataEntity.is_active.is_(True),
                )
                .order_by(MetadataEntity.app_label.asc(), MetadataEntity.model_name.asc())
            ).all()
        )
        return [
            MetadataEntityRead(
                app_label=item.app_label,
                model_name=item.model_name,
                model_label=item.model_label,
                db_table=item.db_table,
                verbose_name=item.verbose_name,
                verbose_name_plural=item.verbose_name_plural,
                is_managed=item.is_managed,
                is_proxy=item.is_proxy,
                metadata_hash=item.metadata_hash,
            )
            for item in entities
        ]

    def get_active_entity_detail(
        self,
        session: Session,
        source_key: str,
        model_label: str,
    ) -> MetadataEntityDetail | None:
        source = self._repository.get_source_by_key(session, source_key)
        if source is None:
            return None
        entity = session.scalar(
            select(MetadataEntity).where(
                MetadataEntity.source_id == source.id,
                MetadataEntity.model_label == model_label,
                MetadataEntity.is_active.is_(True),
            )
        )
        if entity is None:
            return None
        fields = list(
            session.scalars(
                select(MetadataField)
                .where(
                    MetadataField.entity_id == entity.id,
                    MetadataField.is_active.is_(True),
                )
                .order_by(MetadataField.field_name.asc())
            ).all()
        )
        return MetadataEntityDetail(
            app_label=entity.app_label,
            model_name=entity.model_name,
            model_label=entity.model_label,
            db_table=entity.db_table,
            verbose_name=entity.verbose_name,
            verbose_name_plural=entity.verbose_name_plural,
            is_managed=entity.is_managed,
            is_proxy=entity.is_proxy,
            metadata_hash=entity.metadata_hash,
            fields=[
                MetadataFieldRead(
                    field_name=item.field_name,
                    field_type=item.field_type,
                    db_column=item.db_column,
                    null=item.null,
                    blank=item.blank,
                    required=item.required,
                    primary_key=item.primary_key,
                    unique=item.unique,
                    editable=item.editable,
                    max_length=item.max_length,
                    default_value=item.default_value,
                    choices_json=item.choices_json if isinstance(item.choices_json, list) else None,
                    help_text=item.help_text,
                    relation_kind=item.relation_kind,
                    related_model=item.related_model,
                    auto_now=item.auto_now,
                    auto_now_add=item.auto_now_add,
                    metadata_hash=item.metadata_hash,
                )
                for item in fields
            ],
        )


def get_source_summary(
    session: Session,
    source_key: str,
) -> MetadataSourceSummary | None:
    return MetadataQueryService().get_source_summary(session, source_key)


def list_active_entities_for_source(
    session: Session,
    source_key: str,
) -> list[MetadataEntityRead]:
    return MetadataQueryService().list_active_entities_for_source(session, source_key)


def get_active_entity_detail(
    session: Session,
    source_key: str,
    model_label: str,
) -> MetadataEntityDetail | None:
    return MetadataQueryService().get_active_entity_detail(session, source_key, model_label)
