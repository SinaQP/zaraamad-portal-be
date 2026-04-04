from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Index, Integer, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.database import Base, TimestampMixin
from app.modules.forms.constants import FormBindingType, FormFieldType, FormScopeType


class FormSchema(Base, TimestampMixin):
    __tablename__ = "form_schemas"
    __table_args__ = (
        CheckConstraint(
            "(scope_type = 'global' AND scope_value IS NULL) OR "
            "(scope_type = 'municipality' AND scope_value IS NOT NULL)",
            name="ck_form_schemas_scope_value",
        ),
        Index(
            "ix_form_schemas_key_scope_active",
            "key",
            "scope_type",
            "scope_value",
            "is_active",
        ),
        Index(
            "uq_form_schemas_key_scope_value_version",
            "key",
            "scope_type",
            text("coalesce(scope_value, '')"),
            "version",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    scope_type: Mapped[FormScopeType] = mapped_column(
        Enum(
            FormScopeType,
            name="form_scope_type",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    scope_value: Mapped[str | None] = mapped_column(String(255), nullable=True)

    fields: Mapped[list["FormField"]] = relationship(
        "FormField",
        back_populates="form",
        cascade="all, delete-orphan",
        foreign_keys="FormField.form_id",
        order_by=lambda: (FormField.order_index, FormField.id),
    )


class FormField(Base, TimestampMixin):
    __tablename__ = "form_fields"
    __table_args__ = (
        Index(
            "uq_form_fields_form_key",
            "form_id",
            "key",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    form_id: Mapped[int] = mapped_column(
        ForeignKey("form_schemas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_field_id: Mapped[int | None] = mapped_column(
        ForeignKey("form_fields.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[FormFieldType] = mapped_column(
        Enum(
            FormFieldType,
            name="form_field_type",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    placeholder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_value: Mapped[object | None] = mapped_column(JSON(), nullable=True)
    validation: Mapped[object | None] = mapped_column(JSON(), nullable=True)
    source: Mapped[object | None] = mapped_column(JSON(), nullable=True)
    options: Mapped[object | None] = mapped_column(JSON(), nullable=True)
    binding: Mapped[FormBindingType] = mapped_column(
        Enum(
            FormBindingType,
            name="form_binding_type",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=FormBindingType.DYNAMIC,
        server_default=FormBindingType.DYNAMIC.value,
    )

    form: Mapped[FormSchema] = relationship(
        "FormSchema",
        back_populates="fields",
        foreign_keys=[form_id],
    )
    parent_field: Mapped["FormField | None"] = relationship(
        "FormField",
        back_populates="sub_fields",
        remote_side="FormField.id",
        foreign_keys=[parent_field_id],
    )
    sub_fields: Mapped[list["FormField"]] = relationship(
        "FormField",
        back_populates="parent_field",
        cascade="all, delete-orphan",
        foreign_keys="FormField.parent_field_id",
        order_by=lambda: (FormField.order_index, FormField.id),
    )
