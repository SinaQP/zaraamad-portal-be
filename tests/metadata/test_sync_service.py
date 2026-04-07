from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.metadata.models import (
    MetadataEntity,
    MetadataField,
    MetadataSnapshot,
    MetadataSource,
    MetadataSyncRun,
)
from app.metadata.schemas import FullMetadataSyncPayload
from app.metadata.service import MetadataSyncService


def _build_payload(
    *,
    app_version: str = "1.0.0",
    include_second_field: bool = True,
    include_second_model: bool = False,
    name_max_length: int = 255,
    name_required: bool = True,
) -> FullMetadataSyncPayload:
    invoice_fields = [
        {
            "field_name": "id",
            "field_type": "AutoField",
            "db_column": "id",
            "null": False,
            "blank": False,
            "required": True,
            "primary_key": True,
            "unique": True,
            "editable": False,
            "max_length": None,
            "default_value": None,
            "choices": None,
            "help_text": None,
            "relation_kind": None,
            "related_model": None,
            "auto_now": None,
            "auto_now_add": None,
        }
    ]
    if include_second_field:
        invoice_fields.append(
            {
                "field_name": "name",
                "field_type": "CharField",
                "db_column": "name",
                "null": False,
                "blank": False,
                "required": name_required,
                "primary_key": False,
                "unique": False,
                "editable": True,
                "max_length": name_max_length,
                "default_value": None,
                "choices": None,
                "help_text": "Invoice name",
                "relation_kind": None,
                "related_model": None,
                "auto_now": None,
                "auto_now_add": None,
            }
        )
    models = [
        {
            "model_name": "Invoice",
            "model_label": "sales.Invoice",
            "db_table": "sales_invoice",
            "verbose_name": "Invoice",
            "verbose_name_plural": "Invoices",
            "is_managed": True,
            "is_proxy": False,
            "fields": invoice_fields,
        }
    ]
    if include_second_model:
        models.append(
            {
                "model_name": "Customer",
                "model_label": "sales.Customer",
                "db_table": "sales_customer",
                "verbose_name": "Customer",
                "verbose_name_plural": "Customers",
                "is_managed": True,
                "is_proxy": False,
                "fields": [
                    {
                        "field_name": "id",
                        "field_type": "AutoField",
                        "db_column": "id",
                        "null": False,
                        "blank": False,
                        "required": True,
                        "primary_key": True,
                        "unique": True,
                        "editable": False,
                        "max_length": None,
                        "default_value": None,
                        "choices": None,
                        "help_text": None,
                        "relation_kind": None,
                        "related_model": None,
                        "auto_now": None,
                        "auto_now_add": None,
                    }
                ],
            }
        )
    return FullMetadataSyncPayload.model_validate(
        {
            "source": {
                "source_key": "org-12-zaraamad",
                "source_name": "Org 12 Zaraamad",
                "organization_code": "org-12",
                "app_name": "zaraamad",
                "app_version": app_version,
            },
            "snapshot": {
                "generated_at": datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
                "generator_version": "metadata-gen/1.0.0",
                "apps": [
                    {
                        "app_label": "sales",
                        "app_verbose_name": "Sales",
                        "models": models,
                    }
                ],
            },
        }
    )


def test_initial_sync_creates_source_entities_and_fields(db_session: Session) -> None:
    service = MetadataSyncService()
    payload = _build_payload(include_second_field=True, include_second_model=False)

    result = service.sync_full_snapshot(db_session, payload)

    assert result.status == "success"
    assert result.entities_seen == 1
    assert result.fields_seen == 2
    assert result.entities_created == 1
    assert result.fields_created == 2
    assert result.entities_updated == 0
    assert result.fields_updated == 0
    assert result.entities_deactivated == 0
    assert result.fields_deactivated == 0

    source = db_session.scalar(select(MetadataSource).where(MetadataSource.source_key == "org-12-zaraamad"))
    assert source is not None
    assert source.last_sync_at is not None


def test_repeated_idempotent_sync_does_not_rewrite_rows(db_session: Session) -> None:
    service = MetadataSyncService()
    payload = _build_payload()

    first_result = service.sync_full_snapshot(db_session, payload)
    second_result = service.sync_full_snapshot(db_session, payload)

    assert first_result.entities_created == 1
    assert first_result.fields_created == 2
    assert second_result.entities_created == 0
    assert second_result.entities_updated == 0
    assert second_result.entities_deactivated == 0
    assert second_result.fields_created == 0
    assert second_result.fields_updated == 0
    assert second_result.fields_deactivated == 0

    entities = list(db_session.scalars(select(MetadataEntity)).all())
    fields = list(db_session.scalars(select(MetadataField)).all())
    assert len(entities) == 1
    assert len(fields) == 2


def test_field_removed_is_marked_inactive(db_session: Session) -> None:
    service = MetadataSyncService()
    payload_with_two_fields = _build_payload(include_second_field=True)
    payload_with_one_field = _build_payload(include_second_field=False)

    service.sync_full_snapshot(db_session, payload_with_two_fields)
    result = service.sync_full_snapshot(db_session, payload_with_one_field)

    assert result.fields_deactivated == 1
    removed_field = db_session.scalar(
        select(MetadataField).where(MetadataField.field_name == "name")
    )
    assert removed_field is not None
    assert removed_field.is_active is False


def test_entity_removed_is_marked_inactive(db_session: Session) -> None:
    service = MetadataSyncService()
    first_payload = _build_payload(include_second_model=True)
    second_payload = _build_payload(include_second_model=False)

    service.sync_full_snapshot(db_session, first_payload)
    result = service.sync_full_snapshot(db_session, second_payload)

    assert result.entities_deactivated == 1
    removed_entity = db_session.scalar(
        select(MetadataEntity).where(MetadataEntity.model_label == "sales.Customer")
    )
    assert removed_entity is not None
    assert removed_entity.is_active is False


def test_field_changed_updates_hash_and_count(db_session: Session) -> None:
    service = MetadataSyncService()
    initial_payload = _build_payload(name_max_length=255, name_required=True)
    changed_payload = _build_payload(name_max_length=128, name_required=False)

    service.sync_full_snapshot(db_session, initial_payload)
    original_field = db_session.scalar(
        select(MetadataField).where(MetadataField.field_name == "name")
    )
    assert original_field is not None
    original_hash = original_field.metadata_hash

    result = service.sync_full_snapshot(db_session, changed_payload)
    updated_field = db_session.scalar(
        select(MetadataField).where(MetadataField.field_name == "name")
    )
    assert updated_field is not None

    assert result.fields_updated == 1
    assert updated_field.metadata_hash != original_hash
    assert updated_field.max_length == 128
    assert updated_field.required is False


def test_source_metadata_changes_without_rewriting_entities_fields(db_session: Session) -> None:
    service = MetadataSyncService()
    initial_payload = _build_payload(app_version="1.0.0")
    second_payload = _build_payload(app_version="1.1.0")

    service.sync_full_snapshot(db_session, initial_payload)
    result = service.sync_full_snapshot(db_session, second_payload)

    source = db_session.scalar(select(MetadataSource).where(MetadataSource.source_key == "org-12-zaraamad"))
    assert source is not None
    assert source.app_version == "1.1.0"
    assert result.entities_created == 0
    assert result.entities_updated == 0
    assert result.fields_created == 0
    assert result.fields_updated == 0


def test_snapshot_history_and_sync_runs_are_created_per_sync(db_session: Session) -> None:
    service = MetadataSyncService()
    payload = _build_payload()
    second_payload_data = deepcopy(payload.model_dump(mode="python"))
    second_payload_data["snapshot"]["generated_at"] = datetime(2026, 4, 6, 9, 5, tzinfo=UTC)
    second_payload = FullMetadataSyncPayload.model_validate(second_payload_data)

    first_result = service.sync_full_snapshot(db_session, payload)
    second_result = service.sync_full_snapshot(db_session, second_payload)

    runs = list(db_session.scalars(select(MetadataSyncRun).order_by(MetadataSyncRun.id.asc())).all())
    snapshots = list(
        db_session.scalars(select(MetadataSnapshot).order_by(MetadataSnapshot.id.asc())).all()
    )

    assert len(runs) == 2
    assert len(snapshots) == 2
    assert runs[0].id == first_result.sync_run_id
    assert runs[1].id == second_result.sync_run_id
    assert snapshots[0].sync_run_id == runs[0].id
    assert snapshots[1].sync_run_id == runs[1].id
