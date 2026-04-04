from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.forms.constants import FormBindingType, FormFieldType, FormScopeType


@dataclass(frozen=True)
class FieldSeedDefinition:
    key: str
    label: str
    type: FormFieldType
    required: bool = False
    order_index: int = 0
    placeholder: str | None = None
    default_value: Any | None = None
    validation: Any | None = None
    source: Any | None = None
    options: Any | None = None
    binding: FormBindingType = FormBindingType.DYNAMIC
    sub_fields: tuple["FieldSeedDefinition", ...] = field(default_factory=tuple)

    def to_payload(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "order_index": self.order_index,
            "placeholder": self.placeholder,
            "default_value": self.default_value,
            "validation": self.validation,
            "source": self.source,
            "options": self.options,
            "binding": self.binding,
            "sub_fields": [item.to_payload() for item in self.sub_fields],
        }


@dataclass(frozen=True)
class FormSeedDefinition:
    key: str
    title: str
    version: int = 1
    description: str | None = None
    is_active: bool = True
    scope_type: FormScopeType = FormScopeType.GLOBAL
    scope_value: str | None = None
    fields: tuple[FieldSeedDefinition, ...] = field(default_factory=tuple)

    def to_payload(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "version": self.version,
            "description": self.description,
            "is_active": self.is_active,
            "scope_type": self.scope_type,
            "scope_value": self.scope_value,
            "fields": [item.to_payload() for item in self.fields],
        }


def _lookup_source(key: str) -> dict[str, str]:
    return {
        "kind": "lookup",
        "key": key,
    }


def _detail_group(*sub_fields: FieldSeedDefinition) -> FieldSeedDefinition:
    return FieldSeedDefinition(
        key="detail",
        label="جزئیات",
        type=FormFieldType.COMPOUND,
        order_index=90,
        binding=FormBindingType.DYNAMIC,
        sub_fields=sub_fields,
    )


_TRADE_OCCUPATION_BASE_FIELDS = (
    FieldSeedDefinition(
        key="license_number",
        label="شماره پروانه",
        type=FormFieldType.TEXT,
        required=True,
        order_index=10,
        binding=FormBindingType.FIXED,
    ),
    FieldSeedDefinition(
        key="license_issue_date",
        label="تاریخ صدور پروانه",
        type=FormFieldType.DATE,
        required=True,
        order_index=20,
        binding=FormBindingType.FIXED,
    ),
    FieldSeedDefinition(
        key="trade_is_active",
        label="وضعیت فعال بودن صنف",
        type=FormFieldType.CHECKBOX,
        order_index=30,
        binding=FormBindingType.FIXED,
        default_value=False,
    ),
    FieldSeedDefinition(
        key="trade_type_id",
        label="نوع صنف",
        type=FormFieldType.SELECT,
        required=True,
        order_index=40,
        source=_lookup_source("trade-types"),
    ),
    FieldSeedDefinition(
        key="trade_ownership_type_id",
        label="نوع مالکیت",
        type=FormFieldType.SELECT,
        order_index=50,
        source=_lookup_source("trade-ownership-types"),
    ),
    FieldSeedDefinition(
        key="trade_activity_type_id",
        label="نوع فعالیت",
        type=FormFieldType.SELECT,
        order_index=60,
        source=_lookup_source("trade-activity-types"),
    ),
    FieldSeedDefinition(
        key="trade_license_status_id",
        label="وضعیت پروانه",
        type=FormFieldType.RADIO,
        order_index=70,
        source=_lookup_source("trade-licenses-status"),
    ),
    _detail_group(
        FieldSeedDefinition(
            key="detail.trade_location_id",
            label="محل فعالیت",
            type=FormFieldType.SELECT,
            required=True,
            order_index=10,
            source=_lookup_source("trade-locations"),
        ),
        FieldSeedDefinition(
            key="detail.shop_area",
            label="مساحت واحد",
            type=FormFieldType.FLOOR_AREA,
            order_index=20,
            validation={"minimum": 0},
        ),
        FieldSeedDefinition(
            key="detail.is_representative",
            label="نماینده قانونی",
            type=FormFieldType.CHECKBOX,
            order_index=30,
            default_value=False,
        ),
        FieldSeedDefinition(
            key="detail.floor_type_id",
            label="نوع طبقه",
            type=FormFieldType.SELECT,
            order_index=40,
            source=_lookup_source("trade-floor-type"),
        ),
        FieldSeedDefinition(
            key="detail.location_coefficient",
            label="ضریب موقعیت",
            type=FormFieldType.NUMBER,
            order_index=50,
            validation={"minimum": 0},
        ),
    ),
)

_TRADE_LICENSE_BASE_FIELDS = (
    FieldSeedDefinition(
        key="license_number",
        label="شماره پروانه",
        type=FormFieldType.TEXT,
        required=True,
        order_index=10,
        binding=FormBindingType.FIXED,
    ),
    FieldSeedDefinition(
        key="license_issue_date",
        label="تاریخ صدور پروانه",
        type=FormFieldType.DATE,
        order_index=20,
        binding=FormBindingType.FIXED,
    ),
    FieldSeedDefinition(
        key="certificate_number",
        label="شماره گواهی",
        type=FormFieldType.CERTIFICATE_NUMBER,
        order_index=30,
    ),
    FieldSeedDefinition(
        key="trade_activity_type_id",
        label="نوع فعالیت",
        type=FormFieldType.SELECT,
        order_index=40,
        source=_lookup_source("trade-activity-types"),
    ),
    FieldSeedDefinition(
        key="work_schedule",
        label="نوع فعالیت در ایام تعطیل",
        type=FormFieldType.WORK_HOLIDAY,
        order_index=50,
    ),
    _detail_group(
        FieldSeedDefinition(
            key="detail.trade_location_id",
            label="محل فعالیت",
            type=FormFieldType.SELECT,
            order_index=10,
            source=_lookup_source("trade-locations"),
        ),
        FieldSeedDefinition(
            key="detail.shop_area",
            label="مساحت محل کسب",
            type=FormFieldType.FLOOR_AREA,
            order_index=20,
            validation={"minimum": 0},
        ),
        FieldSeedDefinition(
            key="detail.is_representative",
            label="نماینده قانونی",
            type=FormFieldType.CHECKBOX,
            order_index=30,
            default_value=False,
        ),
    ),
)

_BLP_GENERAL_FIELDS = (
    FieldSeedDefinition(
        key="owner_name",
        label="نام مالک",
        type=FormFieldType.TEXT,
        required=True,
        order_index=10,
    ),
    FieldSeedDefinition(
        key="license_number",
        label="شماره پرونده",
        type=FormFieldType.TEXT,
        order_index=20,
        binding=FormBindingType.FIXED,
    ),
    FieldSeedDefinition(
        key="license_issue_date",
        label="تاریخ تشکیل پرونده",
        type=FormFieldType.DATE,
        order_index=30,
        binding=FormBindingType.FIXED,
    ),
    FieldSeedDefinition(
        key="usage_type_id",
        label="نوع کاربری",
        type=FormFieldType.SELECT,
        order_index=40,
        source=_lookup_source("usage-types"),
    ),
    _detail_group(
        FieldSeedDefinition(
            key="detail.land_geo_location_id",
            label="موقعیت جغرافیایی زمین",
            type=FormFieldType.SELECT,
            order_index=10,
            source=_lookup_source("land-geo-location"),
        ),
        FieldSeedDefinition(
            key="detail.passage_id",
            label="معبر",
            type=FormFieldType.SELECT,
            order_index=20,
            source=_lookup_source("passage"),
        ),
        FieldSeedDefinition(
            key="detail.floor_area",
            label="مساحت عرصه",
            type=FormFieldType.FLOOR_AREA,
            order_index=30,
            validation={"minimum": 0},
        ),
    ),
)

_BLP_FINANCIAL_FIELDS = (
    FieldSeedDefinition(
        key="estimated_construction_cost",
        label="برآورد هزینه ساخت",
        type=FormFieldType.NUMBER,
        required=True,
        order_index=10,
        validation={"minimum": 0},
    ),
    FieldSeedDefinition(
        key="payable_fee",
        label="عوارض قابل پرداخت",
        type=FormFieldType.NUMBER,
        order_index=20,
        validation={"minimum": 0},
    ),
    FieldSeedDefinition(
        key="reference_certificate",
        label="شماره گواهی مرجع",
        type=FormFieldType.CERTIFICATE_NUMBER,
        order_index=30,
    ),
    FieldSeedDefinition(
        key="payment_method",
        label="روش پرداخت",
        type=FormFieldType.RADIO,
        order_index=40,
        options=[
            {"label": "نقدی", "value": "cash"},
            {"label": "تقسیط", "value": "installment"},
        ],
    ),
    FieldSeedDefinition(
        key="discount_reason",
        label="شرح تخفیف",
        type=FormFieldType.TEXT_AREA,
        order_index=50,
    ),
)

FORM_SEED_DEFINITIONS: tuple[FormSeedDefinition, ...] = (
    FormSeedDefinition(
        key="blp_property_general_info",
        title="اطلاعات عمومی ملک",
        description="فرم پایه اطلاعات عمومی پرونده ساختمانی",
        scope_type=FormScopeType.GLOBAL,
        fields=_BLP_GENERAL_FIELDS,
    ),
    FormSeedDefinition(
        key="blp_financial",
        title="اطلاعات مالی پرونده ساختمانی",
        description="فرم پایه اطلاعات مالی پرونده ساختمانی",
        scope_type=FormScopeType.GLOBAL,
        fields=_BLP_FINANCIAL_FIELDS,
    ),
    FormSeedDefinition(
        key="sirjan-trd-occupation-place-info",
        title="اطلاعات محل اشتغال سیرجان",
        description="فرم محل اشتغال واحد صنفی برای شهرداری سیرجان",
        scope_type=FormScopeType.MUNICIPALITY,
        scope_value="sirjan",
        fields=_TRADE_OCCUPATION_BASE_FIELDS,
    ),
    FormSeedDefinition(
        key="sirjan-trd-license-commercial-permit",
        title="مجوز پروانه کسب سیرجان",
        description="فرم مجوز پروانه کسب برای شهرداری سیرجان",
        scope_type=FormScopeType.MUNICIPALITY,
        scope_value="sirjan",
        fields=_TRADE_LICENSE_BASE_FIELDS,
    ),
    FormSeedDefinition(
        key="zarand-trd-occupation-place-info",
        title="اطلاعات محل اشتغال زرند",
        description="فرم محل اشتغال واحد صنفی برای شهرداری زرند",
        scope_type=FormScopeType.MUNICIPALITY,
        scope_value="zarand",
        fields=_TRADE_OCCUPATION_BASE_FIELDS,
    ),
    FormSeedDefinition(
        key="zarand-trd-license-commercial-permit",
        title="مجوز پروانه کسب زرند",
        description="فرم مجوز پروانه کسب برای شهرداری زرند",
        scope_type=FormScopeType.MUNICIPALITY,
        scope_value="zarand",
        fields=_TRADE_LICENSE_BASE_FIELDS,
    ),
    FormSeedDefinition(
        key="javadiyeh-trd-occupation-place-info",
        title="اطلاعات محل اشتغال جوادیه",
        description="فرم محل اشتغال واحد صنفی برای شهرداری جوادیه",
        scope_type=FormScopeType.MUNICIPALITY,
        scope_value="javadiyeh",
        fields=_TRADE_OCCUPATION_BASE_FIELDS
        + (
            FieldSeedDefinition(
                key="non_union_subject",
                label="موضوع غیراتحادیه‌ای",
                type=FormFieldType.TEXT,
                order_index=80,
            ),
        ),
    ),
    FormSeedDefinition(
        key="javadiyeh-trd-license-commercial-permit",
        title="مجوز پروانه کسب جوادیه",
        description="فرم مجوز پروانه کسب برای شهرداری جوادیه",
        scope_type=FormScopeType.MUNICIPALITY,
        scope_value="javadiyeh",
        fields=_TRADE_LICENSE_BASE_FIELDS,
    ),
    FormSeedDefinition(
        key="javadiyeh_blp_property_general_info",
        title="اطلاعات عمومی ملک جوادیه",
        description="فرم اطلاعات عمومی ملک ویژه شهرداری جوادیه",
        scope_type=FormScopeType.MUNICIPALITY,
        scope_value="javadiyeh",
        fields=_BLP_GENERAL_FIELDS,
    ),
    FormSeedDefinition(
        key="narmashir_blp_property_general_info",
        title="اطلاعات عمومی ملک نرماشیر",
        description="فرم اطلاعات عمومی ملک ویژه شهرداری نرماشیر",
        scope_type=FormScopeType.MUNICIPALITY,
        scope_value="narmashir",
        fields=_BLP_GENERAL_FIELDS,
    ),
)
