from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.common.database import get_db_session
from app.common.messages import (
    DATA_INTEGRITY_ERROR,
    FORM_FIELD_NOT_FOUND,
    FORM_FIELD_PARENT_INVALID,
    FORM_NOT_FOUND,
)
from app.modules.forms.constants import FormScopeType
from app.modules.forms.dtos import (
    FormFieldCreate,
    FormFieldNestedCreate,
    FormFieldUpdate,
    FormSchemaCreate,
    FormSchemaUpdate,
)
from app.modules.forms.schemas import FormField, FormSchema
from app.modules.forms.seeds.forms_seed_data import FORM_SEED_DEFINITIONS, FormSeedDefinition

_FORM_MUTABLE_FIELDS = (
    "key",
    "title",
    "version",
    "description",
    "is_active",
    "scope_type",
    "scope_value",
)
_FORM_FIELD_MUTABLE_FIELDS = (
    "key",
    "label",
    "type",
    "required",
    "order_index",
    "placeholder",
    "default_value",
    "validation",
    "source",
    "options",
    "binding",
)


@dataclass(frozen=True)
class FormFieldTreeResult:
    field: FormField
    form_fields: list[FormField]


class FormQueryBuilder:
    def build_list_query(
        self,
        *,
        key: str | None,
        scope_type: FormScopeType | None,
        scope_value: str | None,
        municipality_code: str | None,
        include_inactive: bool,
    ) -> Select[tuple[FormSchema]]:
        normalized_scope_type, normalized_scope_value = self._normalize_scope_filters(
            scope_type=scope_type,
            scope_value=scope_value,
            municipality_code=municipality_code,
        )
        query = select(FormSchema).options(selectinload(FormSchema.fields))
        if key:
            query = query.where(FormSchema.key == key)
        if normalized_scope_type is not None:
            query = query.where(FormSchema.scope_type == normalized_scope_type)
        if normalized_scope_value is not None:
            query = query.where(FormSchema.scope_value == normalized_scope_value)
        if not include_inactive:
            query = query.where(FormSchema.is_active.is_(True))
        return query.order_by(
            FormSchema.key.asc(),
            FormSchema.scope_type.asc(),
            FormSchema.scope_value.asc(),
            FormSchema.version.desc(),
            FormSchema.id.desc(),
        )

    def build_exact_query(
        self,
        *,
        key: str,
        scope_type: FormScopeType | None,
        scope_value: str | None,
        municipality_code: str | None,
    ) -> Select[tuple[FormSchema]]:
        return self.build_list_query(
            key=key,
            scope_type=scope_type,
            scope_value=scope_value,
            municipality_code=municipality_code,
            include_inactive=False,
        )

    def _normalize_scope_filters(
        self,
        *,
        scope_type: FormScopeType | None,
        scope_value: str | None,
        municipality_code: str | None,
    ) -> tuple[FormScopeType | None, str | None]:
        normalized_scope_type = scope_type
        normalized_scope_value = scope_value
        if municipality_code and normalized_scope_type is None:
            normalized_scope_type = FormScopeType.MUNICIPALITY
        if municipality_code and normalized_scope_value is None:
            normalized_scope_value = municipality_code
        return normalized_scope_type, normalized_scope_value


class FormLookupService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def get_form_or_404(self, *, form_id: int) -> FormSchema:
        form = self._db_session.get(FormSchema, form_id)
        if form is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=FORM_NOT_FOUND,
            )
        return form

    def get_field_or_404(self, *, field_id: int) -> FormField:
        field = self._db_session.get(FormField, field_id)
        if field is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=FORM_FIELD_NOT_FOUND,
            )
        return field


class FormFieldTreeSynchronizer:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._lookup_service = FormLookupService(db_session=db_session)

    def sync_form_fields(
        self,
        *,
        form_id: int,
        field_payloads: list[dict[str, Any]],
    ) -> None:
        self._sync_children(
            form_id=form_id,
            parent_field_id=None,
            field_payloads=field_payloads,
        )

    def sync_direct_children(
        self,
        *,
        form_id: int,
        parent_field_id: int | None,
        field_payloads: list[dict[str, Any]],
    ) -> None:
        self._sync_children(
            form_id=form_id,
            parent_field_id=parent_field_id,
            field_payloads=field_payloads,
        )

    def validate_parent_assignment(
        self,
        *,
        form_id: int,
        parent_field_id: int | None,
        current_field_id: int | None = None,
    ) -> FormField | None:
        if parent_field_id is None:
            return None

        parent_field = self._lookup_service.get_field_or_404(field_id=parent_field_id)
        if parent_field.form_id != form_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=FORM_FIELD_PARENT_INVALID,
            )
        if current_field_id is None:
            return parent_field

        current_parent = parent_field
        while current_parent is not None:
            if current_parent.id == current_field_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=FORM_FIELD_PARENT_INVALID,
                )
            current_parent = current_parent.parent_field
        return parent_field

    def _sync_children(
        self,
        *,
        form_id: int,
        parent_field_id: int | None,
        field_payloads: list[dict[str, Any]],
    ) -> None:
        existing_children = list(
            self._db_session.scalars(
                select(FormField)
                .where(
                    FormField.form_id == form_id,
                    FormField.parent_field_id == parent_field_id,
                )
                .order_by(FormField.order_index.asc(), FormField.id.asc())
            ).all()
        )
        existing_by_key = {field.key: field for field in existing_children}
        expected_keys: set[str] = set()

        for index, payload in enumerate(field_payloads):
            normalized_payload = dict(payload)
            sub_fields = list(normalized_payload.pop("sub_fields", []))
            field_key = normalized_payload["key"]
            expected_keys.add(field_key)

            field = existing_by_key.get(field_key)
            if field is None:
                field = FormField(
                    form_id=form_id,
                    parent_field_id=parent_field_id,
                )
                self._db_session.add(field)
            else:
                field.parent_field_id = parent_field_id

            if normalized_payload.get("order_index") is None:
                normalized_payload["order_index"] = index
            self._apply_mutable_field_values(field=field, payload=normalized_payload)
            self._db_session.flush()

            self._sync_children(
                form_id=form_id,
                parent_field_id=field.id,
                field_payloads=sub_fields,
            )

        obsolete_fields = [
            field
            for field in existing_children
            if field.key not in expected_keys
        ]
        for field in obsolete_fields:
            self._db_session.delete(field)

    def _apply_mutable_field_values(
        self,
        *,
        field: FormField,
        payload: dict[str, Any],
    ) -> None:
        for field_name in _FORM_FIELD_MUTABLE_FIELDS:
            if field_name in payload:
                setattr(field, field_name, payload[field_name])


class FormSchemaService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = FormQueryBuilder()
        self._lookup_service = FormLookupService(db_session=db_session)

    def list_forms(
        self,
        *,
        key: str | None,
        scope_type: FormScopeType | None,
        scope_value: str | None,
        municipality_code: str | None,
        include_inactive: bool,
    ) -> list[FormSchema]:
        query = self._query_builder.build_list_query(
            key=key,
            scope_type=scope_type,
            scope_value=scope_value,
            municipality_code=municipality_code,
            include_inactive=include_inactive,
        )
        return list(self._db_session.scalars(query).all())

    def list_by_key(
        self,
        *,
        key: str,
        scope_type: FormScopeType | None,
        scope_value: str | None,
        municipality_code: str | None,
    ) -> list[FormSchema]:
        query = self._query_builder.build_exact_query(
            key=key,
            scope_type=scope_type,
            scope_value=scope_value,
            municipality_code=municipality_code,
        )
        return list(self._db_session.scalars(query).all())

    def resolve_form(
        self,
        *,
        key: str,
        municipality_code: str | None,
    ) -> FormSchema:
        if municipality_code:
            municipality_form = self._db_session.scalar(
                select(FormSchema)
                .options(selectinload(FormSchema.fields))
                .where(
                    FormSchema.key == key,
                    FormSchema.scope_type == FormScopeType.MUNICIPALITY,
                    FormSchema.scope_value == municipality_code,
                    FormSchema.is_active.is_(True),
                )
                .order_by(FormSchema.version.desc(), FormSchema.id.desc())
                .limit(1)
            )
            if municipality_form is not None:
                return municipality_form

        global_form = self._db_session.scalar(
            select(FormSchema)
            .options(selectinload(FormSchema.fields))
            .where(
                FormSchema.key == key,
                FormSchema.scope_type == FormScopeType.GLOBAL,
                FormSchema.is_active.is_(True),
            )
            .order_by(FormSchema.version.desc(), FormSchema.id.desc())
            .limit(1)
        )
        if global_form is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=FORM_NOT_FOUND,
            )
        return global_form

    def create(self, *, dto: FormSchemaCreate) -> FormSchema:
        form = FormSchema()
        payload = dto.model_dump(exclude_none=False)
        for field_name in _FORM_MUTABLE_FIELDS:
            setattr(form, field_name, payload[field_name])
        self._db_session.add(form)
        self._commit_with_integrity_guard()
        self._db_session.refresh(form)
        return self._load_form(form_id=form.id)

    def update(self, *, form_id: int, dto: FormSchemaUpdate) -> FormSchema:
        form = self._lookup_service.get_form_or_404(form_id=form_id)
        payload = dto.model_dump(exclude_unset=True, exclude_none=False)
        for field_name in _FORM_MUTABLE_FIELDS:
            if field_name in payload:
                setattr(form, field_name, payload[field_name])
        self._commit_with_integrity_guard()
        return self._load_form(form_id=form_id)

    def delete(self, *, form_id: int) -> None:
        form = self._lookup_service.get_form_or_404(form_id=form_id)
        self._db_session.delete(form)
        self._db_session.commit()

    def _load_form(self, *, form_id: int) -> FormSchema:
        form = self._db_session.scalar(
            select(FormSchema)
            .options(selectinload(FormSchema.fields))
            .where(FormSchema.id == form_id)
        )
        if form is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=FORM_NOT_FOUND,
            )
        return form

    def _commit_with_integrity_guard(self) -> None:
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc


class FormFieldService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._lookup_service = FormLookupService(db_session=db_session)
        self._field_tree_synchronizer = FormFieldTreeSynchronizer(db_session=db_session)

    def create(self, *, dto: FormFieldCreate) -> FormFieldTreeResult:
        form = self._lookup_service.get_form_or_404(form_id=dto.form_id)
        parent_field = self._field_tree_synchronizer.validate_parent_assignment(
            form_id=form.id,
            parent_field_id=dto.parent_field_id,
        )

        field = FormField(
            form_id=form.id,
            parent_field_id=parent_field.id if parent_field is not None else None,
        )
        self._db_session.add(field)
        self._apply_mutable_field_values(
            field=field,
            payload=dto.model_dump(exclude={"form_id", "parent_field_id", "sub_fields"}),
        )
        self._db_session.flush()

        child_payloads = [
            self._nested_field_to_payload(item)
            for item in dto.sub_fields
        ]
        self._field_tree_synchronizer.sync_direct_children(
            form_id=form.id,
            parent_field_id=field.id,
            field_payloads=child_payloads,
        )
        self._commit_with_integrity_guard()
        return self.get_tree(field_id=field.id)

    def update(self, *, field_id: int, dto: FormFieldUpdate) -> FormFieldTreeResult:
        field = self._lookup_service.get_field_or_404(field_id=field_id)
        original_form_id = field.form_id
        payload = dto.model_dump(exclude_unset=True, exclude_none=False)
        sub_fields = payload.pop("sub_fields", None)
        target_form_id = payload.get("form_id", field.form_id)
        target_parent_field_id = (
            payload["parent_field_id"]
            if "parent_field_id" in payload
            else field.parent_field_id
        )

        self._lookup_service.get_form_or_404(form_id=target_form_id)
        parent_field = self._field_tree_synchronizer.validate_parent_assignment(
            form_id=target_form_id,
            parent_field_id=target_parent_field_id,
            current_field_id=field.id,
        )
        field.form_id = target_form_id
        field.parent_field_id = parent_field.id if parent_field is not None else None
        self._apply_mutable_field_values(field=field, payload=payload)
        self._db_session.flush()

        if target_form_id != original_form_id:
            self._move_subtree_to_form(
                parent_field_id=field.id,
                form_id=target_form_id,
            )

        if sub_fields is not None:
            normalized_sub_fields = [
                self._nested_field_to_payload(item)
                for item in sub_fields
            ]
            self._field_tree_synchronizer.sync_direct_children(
                form_id=field.form_id,
                parent_field_id=field.id,
                field_payloads=normalized_sub_fields,
            )

        self._commit_with_integrity_guard()
        return self.get_tree(field_id=field.id)

    def delete(self, *, field_id: int) -> None:
        field = self._lookup_service.get_field_or_404(field_id=field_id)
        self._db_session.delete(field)
        self._db_session.commit()

    def get_tree(self, *, field_id: int) -> FormFieldTreeResult:
        field = self._lookup_service.get_field_or_404(field_id=field_id)
        form_fields = list(
            self._db_session.scalars(
                select(FormField)
                .where(FormField.form_id == field.form_id)
                .order_by(FormField.order_index.asc(), FormField.id.asc())
            ).all()
        )
        refreshed_field = next(item for item in form_fields if item.id == field.id)
        return FormFieldTreeResult(
            field=refreshed_field,
            form_fields=form_fields,
        )

    def _apply_mutable_field_values(
        self,
        *,
        field: FormField,
        payload: dict[str, Any],
    ) -> None:
        for field_name in _FORM_FIELD_MUTABLE_FIELDS:
            if field_name in payload:
                setattr(field, field_name, payload[field_name])

    def _nested_field_to_payload(
        self,
        dto: FormFieldNestedCreate,
    ) -> dict[str, Any]:
        payload = dto.model_dump(exclude_none=False)
        payload["sub_fields"] = [
            self._nested_field_to_payload(item)
            for item in dto.sub_fields
        ]
        return payload

    def _move_subtree_to_form(
        self,
        *,
        parent_field_id: int,
        form_id: int,
    ) -> None:
        child_fields = list(
            self._db_session.scalars(
                select(FormField).where(FormField.parent_field_id == parent_field_id)
            ).all()
        )
        for child_field in child_fields:
            child_field.form_id = form_id
            self._move_subtree_to_form(
                parent_field_id=child_field.id,
                form_id=form_id,
            )

    def _commit_with_integrity_guard(self) -> None:
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc


class FormSeedService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._field_tree_synchronizer = FormFieldTreeSynchronizer(db_session=db_session)

    def apply_seed_definitions(
        self,
        *,
        seed_definitions: tuple[FormSeedDefinition, ...] = FORM_SEED_DEFINITIONS,
        commit: bool = True,
    ) -> None:
        for seed_definition in seed_definitions:
            self._upsert_form(seed_definition=seed_definition)
        if commit:
            self._db_session.commit()

    def _upsert_form(self, *, seed_definition: FormSeedDefinition) -> None:
        form_payload = seed_definition.to_payload()
        fields = form_payload.pop("fields")

        query = select(FormSchema).where(
            FormSchema.key == form_payload["key"],
            FormSchema.scope_type == form_payload["scope_type"],
            FormSchema.version == form_payload["version"],
        )
        if form_payload["scope_value"] is None:
            query = query.where(FormSchema.scope_value.is_(None))
        else:
            query = query.where(FormSchema.scope_value == form_payload["scope_value"])

        form = self._db_session.scalar(query)
        if form is None:
            form = FormSchema()
            self._db_session.add(form)

        for field_name in _FORM_MUTABLE_FIELDS:
            setattr(form, field_name, form_payload[field_name])
        self._db_session.flush()
        self._field_tree_synchronizer.sync_form_fields(
            form_id=form.id,
            field_payloads=fields,
        )


def seed_forms(db_session: Session) -> None:
    FormSeedService(db_session=db_session).apply_seed_definitions()


def get_form_schema_service(
    db_session: Session = Depends(get_db_session),
) -> FormSchemaService:
    return FormSchemaService(db_session=db_session)


def get_form_field_service(
    db_session: Session = Depends(get_db_session),
) -> FormFieldService:
    return FormFieldService(db_session=db_session)


def get_form_seed_service(
    db_session: Session = Depends(get_db_session),
) -> FormSeedService:
    return FormSeedService(db_session=db_session)
