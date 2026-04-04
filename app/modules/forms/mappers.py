from __future__ import annotations

from app.modules.forms.dtos import FormFieldOut, FormSchemaOut
from app.modules.forms.schemas import FormField, FormSchema


class FormMapper:
    def to_form_out(
        self,
        *,
        form: FormSchema,
        form_fields: list[FormField] | None = None,
    ) -> FormSchemaOut:
        fields = form_fields if form_fields is not None else list(form.fields)
        field_bucket = self._build_field_bucket(fields=fields)
        top_level_fields = field_bucket.get(None, [])
        return FormSchemaOut(
            id=form.id,
            key=form.key,
            title=form.title,
            version=form.version,
            description=form.description,
            is_active=form.is_active,
            scope_type=form.scope_type,
            scope_value=form.scope_value,
            fields=[
                self._to_field_out_from_bucket(field=item, field_bucket=field_bucket)
                for item in top_level_fields
            ],
            created_at=form.created_at,
            updated_at=form.updated_at,
        )

    def to_field_out(
        self,
        *,
        field: FormField,
        form_fields: list[FormField] | None = None,
    ) -> FormFieldOut:
        if form_fields is None:
            return self._to_field_out_from_relationship(field=field)
        field_bucket = self._build_field_bucket(fields=form_fields)
        return self._to_field_out_from_bucket(field=field, field_bucket=field_bucket)

    def _build_field_bucket(
        self,
        *,
        fields: list[FormField],
    ) -> dict[int | None, list[FormField]]:
        bucket: dict[int | None, list[FormField]] = {}
        for field in sorted(fields, key=lambda item: (item.order_index, item.id)):
            bucket.setdefault(field.parent_field_id, []).append(field)
        return bucket

    def _to_field_out_from_bucket(
        self,
        *,
        field: FormField,
        field_bucket: dict[int | None, list[FormField]],
    ) -> FormFieldOut:
        return FormFieldOut(
            id=field.id,
            form_id=field.form_id,
            parent_field_id=field.parent_field_id,
            key=field.key,
            label=field.label,
            type=field.type,
            required=field.required,
            order_index=field.order_index,
            placeholder=field.placeholder,
            default_value=field.default_value,
            validation=field.validation,
            source=field.source,
            options=field.options,
            binding=field.binding,
            sub_fields=[
                self._to_field_out_from_bucket(field=item, field_bucket=field_bucket)
                for item in field_bucket.get(field.id, [])
            ],
            created_at=field.created_at,
            updated_at=field.updated_at,
        )

    def _to_field_out_from_relationship(
        self,
        *,
        field: FormField,
    ) -> FormFieldOut:
        ordered_children = sorted(field.sub_fields, key=lambda item: (item.order_index, item.id))
        return FormFieldOut(
            id=field.id,
            form_id=field.form_id,
            parent_field_id=field.parent_field_id,
            key=field.key,
            label=field.label,
            type=field.type,
            required=field.required,
            order_index=field.order_index,
            placeholder=field.placeholder,
            default_value=field.default_value,
            validation=field.validation,
            source=field.source,
            options=field.options,
            binding=field.binding,
            sub_fields=[
                self._to_field_out_from_relationship(field=item)
                for item in ordered_children
            ],
            created_at=field.created_at,
            updated_at=field.updated_at,
        )


def get_form_mapper() -> FormMapper:
    return FormMapper()
