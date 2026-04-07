from datetime import UTC, datetime

from app.metadata.schemas import FieldMetadata, FullMetadataSyncPayload, ModelMetadata
from app.metadata.utils import (
    canonical_json_dumps,
    compute_entity_hash,
    compute_field_hash,
    compute_snapshot_hash,
    normalize_default_value,
)


def test_canonical_json_dumps_is_stable_for_dict_order() -> None:
    first = {"b": 2, "a": {"d": 4, "c": 3}}
    second = {"a": {"c": 3, "d": 4}, "b": 2}

    assert canonical_json_dumps(first) == canonical_json_dumps(second)


def test_snapshot_hash_is_stable_for_ordered_apps_models_and_fields() -> None:
    payload_one = FullMetadataSyncPayload.model_validate(
        {
            "source": {
                "source_key": "org-12-zaraamad",
                "source_name": "Zaraamad",
                "organization_code": "org-12",
                "app_name": "zaraamad",
                "app_version": "1.0.0",
            },
            "snapshot": {
                "generated_at": datetime(2026, 4, 6, 8, 0, tzinfo=UTC),
                "generator_version": "v1",
                "apps": [
                    {
                        "app_label": "sales",
                        "models": [
                            {
                                "model_name": "Invoice",
                                "model_label": "sales.Invoice",
                                "db_table": "sales_invoice",
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
                                    },
                                    {
                                        "field_name": "name",
                                        "field_type": "CharField",
                                        "db_column": "name",
                                        "null": False,
                                        "blank": False,
                                        "required": True,
                                        "primary_key": False,
                                        "unique": False,
                                        "editable": True,
                                        "max_length": 255,
                                        "default_value": None,
                                        "choices": None,
                                        "help_text": "Name",
                                        "relation_kind": None,
                                        "related_model": None,
                                        "auto_now": None,
                                        "auto_now_add": None,
                                    },
                                ],
                            }
                        ],
                    },
                    {
                        "app_label": "crm",
                        "models": [
                            {
                                "model_name": "Customer",
                                "model_label": "crm.Customer",
                                "db_table": "crm_customer",
                                "fields": [],
                            }
                        ],
                    },
                ],
            },
        }
    )

    payload_two = FullMetadataSyncPayload.model_validate(
        {
            "source": payload_one.source.model_dump(),
            "snapshot": {
                "generated_at": payload_one.snapshot.generated_at,
                "generator_version": "v1",
                "apps": [
                    {
                        "app_label": "crm",
                        "models": [
                            {
                                "model_name": "Customer",
                                "model_label": "crm.Customer",
                                "db_table": "crm_customer",
                                "fields": [],
                            }
                        ],
                    },
                    {
                        "app_label": "sales",
                        "models": [
                            {
                                "model_name": "Invoice",
                                "model_label": "sales.Invoice",
                                "db_table": "sales_invoice",
                                "fields": [
                                    {
                                        "field_name": "name",
                                        "field_type": "CharField",
                                        "db_column": "name",
                                        "null": False,
                                        "blank": False,
                                        "required": True,
                                        "primary_key": False,
                                        "unique": False,
                                        "editable": True,
                                        "max_length": 255,
                                        "default_value": None,
                                        "choices": None,
                                        "help_text": "Name",
                                        "relation_kind": None,
                                        "related_model": None,
                                        "auto_now": None,
                                        "auto_now_add": None,
                                    },
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
                                    },
                                ],
                            }
                        ],
                    },
                ],
            },
        }
    )

    assert compute_snapshot_hash(payload_one) == compute_snapshot_hash(payload_two)


def test_entity_and_field_hashes_are_stable() -> None:
    model = ModelMetadata.model_validate(
        {
            "model_name": "Invoice",
            "model_label": "sales.Invoice",
            "db_table": "sales_invoice",
            "verbose_name": "Invoice",
            "verbose_name_plural": "Invoices",
            "is_managed": True,
            "is_proxy": False,
            "fields": [],
        }
    )
    field = FieldMetadata.model_validate(
        {
            "field_name": "status",
            "field_type": "CharField",
            "db_column": "status",
            "null": False,
            "blank": False,
            "required": True,
            "primary_key": False,
            "unique": False,
            "editable": True,
            "max_length": 32,
            "default_value": "draft",
            "choices": [["draft", "Draft"], ["published", "Published"]],
            "help_text": "  current status  ",
            "relation_kind": None,
            "related_model": None,
            "auto_now": None,
            "auto_now_add": None,
        }
    )

    model_hash_one = compute_entity_hash(model)
    model_hash_two = compute_entity_hash(model.model_dump())
    field_hash_one = compute_field_hash(field)
    field_hash_two = compute_field_hash(field.model_dump())

    assert model_hash_one == model_hash_two
    assert field_hash_one == field_hash_two


def test_normalize_default_value_fails_softly_for_unknown_object() -> None:
    class WeirdDefault:
        pass

    normalized = normalize_default_value(WeirdDefault())

    assert normalized is not None
    assert normalized.startswith("<unsupported:")
