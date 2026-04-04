from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, Field

from app.common.dtos import MongoDTO, WithId
from app.modules.forms.constants import FormBindingType, FormFieldType, FormScopeType

JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None


class FormFieldBase(MongoDTO):
    key: str = Field(..., description="Stable field key.", examples=["license_number"])
    label: str = Field(..., description="Field display label.", examples=["شماره پروانه"])
    type: FormFieldType = Field(..., description="Field type.")
    required: bool = Field(default=False, description="Whether the field is required.", examples=[True])
    order_index: int = Field(
        default=0,
        validation_alias=AliasChoices("order_index", "orderIndex"),
        description="Field order inside its parent container.",
        examples=[10],
    )
    placeholder: str | None = Field(
        default=None,
        description="Optional placeholder text.",
        examples=["شماره را وارد کنید"],
    )
    default_value: JsonValue = Field(
        default=None,
        validation_alias=AliasChoices("default_value", "defaultValue"),
        description="Optional default JSON value.",
    )
    validation: JsonValue = Field(
        default=None,
        description="Validation metadata returned as-is.",
    )
    source: JsonValue = Field(
        default=None,
        description="Lookup or source metadata returned as-is.",
    )
    options: JsonValue = Field(
        default=None,
        description="Inline options metadata returned as-is.",
    )
    binding: FormBindingType = Field(
        default=FormBindingType.DYNAMIC,
        description="Field binding strategy.",
    )


class FormFieldNestedCreate(FormFieldBase):
    sub_fields: list["FormFieldNestedCreate"] = Field(
        default_factory=list,
        validation_alias=AliasChoices("sub_fields", "subFields"),
        description="Nested child fields.",
    )


class FormFieldCreate(FormFieldBase):
    form_id: int = Field(..., description="Owning form id.", examples=[1])
    parent_field_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices("parent_field_id", "parentFieldId"),
        description="Optional parent field id.",
        examples=[5],
    )
    sub_fields: list[FormFieldNestedCreate] = Field(
        default_factory=list,
        validation_alias=AliasChoices("sub_fields", "subFields"),
        description="Nested child fields to create under this field.",
    )


class FormFieldUpdate(MongoDTO):
    form_id: int | None = Field(default=None, description="Owning form id.", examples=[1])
    parent_field_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices("parent_field_id", "parentFieldId"),
        description="Optional parent field id.",
        examples=[5],
    )
    key: str | None = Field(default=None, description="Stable field key.", examples=["detail.shop_area"])
    label: str | None = Field(default=None, description="Field display label.", examples=["مساحت مغازه"])
    type: FormFieldType | None = Field(default=None, description="Field type.")
    required: bool | None = Field(default=None, description="Whether the field is required.", examples=[False])
    order_index: int | None = Field(
        default=None,
        validation_alias=AliasChoices("order_index", "orderIndex"),
        description="Field order inside its parent container.",
        examples=[20],
    )
    placeholder: str | None = Field(default=None, description="Optional placeholder text.")
    default_value: JsonValue = Field(
        default=None,
        validation_alias=AliasChoices("default_value", "defaultValue"),
        description="Optional default JSON value.",
    )
    validation: JsonValue = Field(default=None, description="Validation metadata returned as-is.")
    source: JsonValue = Field(default=None, description="Lookup or source metadata returned as-is.")
    options: JsonValue = Field(default=None, description="Inline options metadata returned as-is.")
    binding: FormBindingType | None = Field(default=None, description="Field binding strategy.")
    sub_fields: list[FormFieldNestedCreate] | None = Field(
        default=None,
        validation_alias=AliasChoices("sub_fields", "subFields"),
        description="Replacement child fields for this field when provided.",
    )


class FormFieldOut(WithId, FormFieldBase):
    form_id: int = Field(..., description="Owning form id.", examples=[1])
    parent_field_id: int | None = Field(
        default=None,
        description="Optional parent field id.",
        examples=[5],
    )
    sub_fields: list["FormFieldOut"] = Field(
        default_factory=list,
        description="Nested child fields.",
    )
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class FormSchemaBase(MongoDTO):
    key: str = Field(..., description="Stable form key.", examples=["blp_property_general_info"])
    title: str = Field(..., description="Form display title.", examples=["اطلاعات عمومی ملک"])
    version: int = Field(default=1, ge=1, description="Form schema version.", examples=[1])
    description: str | None = Field(
        default=None,
        description="Optional form description.",
        examples=["فرم اطلاعات پایه پرونده ساختمانی"],
    )
    is_active: bool = Field(
        default=True,
        validation_alias=AliasChoices("is_active", "isActive"),
        description="Whether the form is active.",
        examples=[True],
    )
    scope_type: FormScopeType = Field(
        default=FormScopeType.GLOBAL,
        validation_alias=AliasChoices("scope_type", "scopeType"),
        description="Scope type for the form.",
    )
    scope_value: str | None = Field(
        default=None,
        validation_alias=AliasChoices("scope_value", "scopeValue"),
        description="Scope value for municipality forms.",
        examples=["sirjan"],
    )


class FormSchemaCreate(FormSchemaBase):
    pass


class FormSchemaUpdate(MongoDTO):
    key: str | None = Field(default=None, description="Stable form key.", examples=["trade-license"])
    title: str | None = Field(default=None, description="Form display title.", examples=["پروانه کسب"])
    version: int | None = Field(default=None, ge=1, description="Form schema version.", examples=[2])
    description: str | None = Field(default=None, description="Optional form description.")
    is_active: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("is_active", "isActive"),
        description="Whether the form is active.",
    )
    scope_type: FormScopeType | None = Field(
        default=None,
        validation_alias=AliasChoices("scope_type", "scopeType"),
        description="Scope type for the form.",
    )
    scope_value: str | None = Field(
        default=None,
        validation_alias=AliasChoices("scope_value", "scopeValue"),
        description="Scope value for municipality forms.",
    )


class FormSchemaOut(WithId, FormSchemaBase):
    fields: list[FormFieldOut] = Field(
        default_factory=list,
        description="Top-level form fields with nested sub-fields.",
    )
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


FormFieldNestedCreate.model_rebuild()
FormFieldOut.model_rebuild()
