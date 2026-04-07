from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

from app.metadata.schemas import FieldMetadata, FullMetadataSyncPayload, ModelMetadata


def canonical_json_dumps(value: Any) -> str:
    """Serialize values into a deterministic JSON string."""
    normalized = _to_json_safe(value)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def compute_snapshot_hash(payload: FullMetadataSyncPayload | Mapping[str, Any]) -> str:
    """
    Compute a deterministic hash from source + snapshot metadata.

    Snapshot hash intentionally includes source and the full snapshot payload
    (including generated timestamps) so each source snapshot identity is explicit.
    """
    payload_obj = _as_payload(payload)
    normalized = payload_obj.model_dump(mode="python")
    snapshot = normalized["snapshot"]
    normalized_apps: list[dict[str, Any]] = []
    for app_item in snapshot["apps"]:
        models = sorted(app_item["models"], key=lambda item: item["model_label"])
        normalized_models: list[dict[str, Any]] = []
        for model_item in models:
            fields = sorted(model_item["fields"], key=lambda item: item["field_name"])
            normalized_model = {**model_item, "fields": fields}
            normalized_models.append(normalized_model)
        normalized_apps.append({**app_item, "models": normalized_models})
    snapshot["apps"] = sorted(normalized_apps, key=lambda item: item["app_label"])
    normalized["snapshot"] = snapshot
    return _sha256_hex(canonical_json_dumps(normalized))


def compute_entity_hash(model_metadata: ModelMetadata | Mapping[str, Any]) -> str:
    model_obj = (
        model_metadata
        if isinstance(model_metadata, ModelMetadata)
        else ModelMetadata.model_validate(model_metadata)
    )
    app_label = ""
    if "." in model_obj.model_label:
        app_label = model_obj.model_label.split(".", 1)[0]
    normalized = {
        "app_label": app_label,
        "model_name": model_obj.model_name,
        "model_label": model_obj.model_label,
        "db_table": model_obj.db_table,
        "verbose_name": model_obj.verbose_name,
        "verbose_name_plural": model_obj.verbose_name_plural,
        "is_managed": model_obj.is_managed,
        "is_proxy": model_obj.is_proxy,
    }
    return _sha256_hex(canonical_json_dumps(normalized))


def compute_field_hash(field_metadata: FieldMetadata | Mapping[str, Any]) -> str:
    field_obj = (
        field_metadata
        if isinstance(field_metadata, FieldMetadata)
        else FieldMetadata.model_validate(field_metadata)
    )
    normalized = {
        "field_name": field_obj.field_name,
        "field_type": field_obj.field_type,
        "db_column": field_obj.db_column,
        "null": field_obj.null,
        "blank": field_obj.blank,
        "required": field_obj.required,
        "primary_key": field_obj.primary_key,
        "unique": field_obj.unique,
        "editable": field_obj.editable,
        "max_length": field_obj.max_length,
        "default_value": normalize_default_value(field_obj.default_value),
        "choices": normalize_choices(field_obj.choices),
        "help_text": normalize_help_text(field_obj.help_text),
        "relation_kind": field_obj.relation_kind,
        "related_model": field_obj.related_model,
        "auto_now": field_obj.auto_now,
        "auto_now_add": field_obj.auto_now_add,
    }
    return _sha256_hex(canonical_json_dumps(normalized))


def normalize_default_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        normalized = _to_json_safe(value)
        if isinstance(normalized, str):
            return normalized
        return canonical_json_dumps(normalized)
    except Exception:
        value_type = value.__class__
        return f"<unsupported:{value_type.__module__}.{value_type.__qualname__}>"


def normalize_choices(value: Any) -> list[Any] | None:
    if value is None:
        return None
    try:
        normalized = _to_json_safe(value)
    except Exception:
        return None
    if isinstance(normalized, list):
        return normalized
    if isinstance(normalized, dict):
        return [
            {"key": item_key, "value": item_value}
            for item_key, item_value in sorted(normalized.items(), key=lambda item: item[0])
        ]
    return [normalized]


def normalize_help_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _as_payload(payload: FullMetadataSyncPayload | Mapping[str, Any]) -> FullMetadataSyncPayload:
    if isinstance(payload, FullMetadataSyncPayload):
        return payload
    return FullMetadataSyncPayload.model_validate(payload)


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        normalized_dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return normalized_dt.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return _to_json_safe(value.value)
    if isinstance(value, Mapping):
        return {str(key): _to_json_safe(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return _to_json_safe(value.model_dump(mode="python"))
    if isinstance(value, (set, frozenset)):
        normalized_values = [_to_json_safe(item) for item in value]
        return sorted(normalized_values, key=canonical_json_dumps)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_to_json_safe(item) for item in value]
    value_type = value.__class__
    return f"<unsupported:{value_type.__module__}.{value_type.__qualname__}>"
