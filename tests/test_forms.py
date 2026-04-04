from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.forms.constants import FormBindingType, FormFieldType, FormScopeType
from app.modules.forms.schemas import FormField, FormSchema
from app.modules.forms.seeds.forms_seed_data import FORM_SEED_DEFINITIONS
from app.modules.forms.service import FormSeedService


def _create_form(
    db_session: Session,
    *,
    key: str,
    title: str,
    scope_type: FormScopeType,
    scope_value: str | None,
    version: int = 1,
    is_active: bool = True,
) -> FormSchema:
    form = FormSchema(
        key=key,
        title=title,
        version=version,
        is_active=is_active,
        scope_type=scope_type,
        scope_value=scope_value,
    )
    db_session.add(form)
    db_session.commit()
    db_session.refresh(form)
    return form


def _create_field(
    db_session: Session,
    *,
    form_id: int,
    key: str,
    label: str,
    field_type: FormFieldType,
    parent_field_id: int | None = None,
    order_index: int = 0,
) -> FormField:
    field = FormField(
        form_id=form_id,
        parent_field_id=parent_field_id,
        key=key,
        label=label,
        type=field_type,
        order_index=order_index,
        binding=FormBindingType.DYNAMIC,
    )
    db_session.add(field)
    db_session.commit()
    db_session.refresh(field)
    return field


def test_form_schema_unique_constraint_handles_global_scope_value_null(db_session: Session) -> None:
    _create_form(
        db_session,
        key="global-form",
        title="Global Form",
        scope_type=FormScopeType.GLOBAL,
        scope_value=None,
    )

    duplicate_form = FormSchema(
        key="global-form",
        title="Duplicate",
        version=1,
        scope_type=FormScopeType.GLOBAL,
        scope_value=None,
        is_active=True,
    )
    db_session.add(duplicate_form)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_form_field_unique_constraint_is_enforced_per_form(db_session: Session) -> None:
    form = _create_form(
        db_session,
        key="field-form",
        title="Field Form",
        scope_type=FormScopeType.GLOBAL,
        scope_value=None,
    )
    _create_field(
        db_session,
        form_id=form.id,
        key="license_number",
        label="شماره پروانه",
        field_type=FormFieldType.TEXT,
    )

    duplicate_field = FormField(
        form_id=form.id,
        key="license_number",
        label="Duplicate",
        type=FormFieldType.TEXT,
        order_index=2,
        binding=FormBindingType.DYNAMIC,
    )
    db_session.add(duplicate_field)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_forms_endpoint_returns_nested_sub_fields(client: TestClient, db_session: Session) -> None:
    form = _create_form(
        db_session,
        key="nested-form",
        title="Nested Form",
        scope_type=FormScopeType.GLOBAL,
        scope_value=None,
    )
    parent_field = _create_field(
        db_session,
        form_id=form.id,
        key="detail",
        label="جزئیات",
        field_type=FormFieldType.COMPOUND,
        order_index=10,
    )
    child_field = _create_field(
        db_session,
        form_id=form.id,
        parent_field_id=parent_field.id,
        key="detail.shop_area",
        label="مساحت",
        field_type=FormFieldType.FLOOR_AREA,
        order_index=20,
    )

    response = client.get("/api/forms/nested-form/")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["fields"][0]["key"] == "detail"
    assert body[0]["fields"][0]["sub_fields"] == [
        {
            "id": child_field.id,
            "form_id": form.id,
            "parent_field_id": parent_field.id,
            "key": "detail.shop_area",
            "label": "مساحت",
            "type": "floor-area",
            "required": False,
            "order_index": 20,
            "placeholder": None,
            "default_value": None,
            "validation": None,
            "source": None,
            "options": None,
            "binding": "dynamic",
            "sub_fields": [],
            "created_at": child_field.created_at.isoformat(),
            "updated_at": child_field.updated_at.isoformat(),
        }
    ]


def test_resolved_form_falls_back_to_global_when_municipality_form_missing(
    client: TestClient,
    db_session: Session,
) -> None:
    global_form = _create_form(
        db_session,
        key="shared-form",
        title="Global Shared Form",
        scope_type=FormScopeType.GLOBAL,
        scope_value=None,
    )
    _create_form(
        db_session,
        key="shared-form",
        title="Inactive Municipality Form",
        scope_type=FormScopeType.MUNICIPALITY,
        scope_value="sirjan",
        is_active=False,
    )

    response = client.get("/api/forms/shared-form/resolved/?municipality_code=sirjan")

    assert response.status_code == 200
    assert response.json()["id"] == global_form.id
    assert response.json()["scope_type"] == "global"


def test_resolved_form_uses_query_param_municipality_scope(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_form(
        db_session,
        key="resolved-form",
        title="Global Resolved Form",
        scope_type=FormScopeType.GLOBAL,
        scope_value=None,
    )
    municipality_form = _create_form(
        db_session,
        key="resolved-form",
        title="Sirjan Form",
        scope_type=FormScopeType.MUNICIPALITY,
        scope_value="sirjan",
    )
    response = client.get("/api/forms/resolved-form/resolved/?municipality_code=sirjan")

    assert response.status_code == 200
    assert response.json()["id"] == municipality_form.id
    assert response.json()["scope_value"] == "sirjan"


def test_seed_service_is_idempotent_and_removes_obsolete_fields(db_session: Session) -> None:
    seed_service = FormSeedService(db_session=db_session)

    seed_service.apply_seed_definitions()
    initial_form_count = db_session.scalar(select(func.count()).select_from(FormSchema))

    blp_form = db_session.scalar(
        select(FormSchema).where(FormSchema.key == "blp_financial")
    )
    assert blp_form is not None

    obsolete_field = FormField(
        form_id=blp_form.id,
        key="obsolete_field",
        label="Obsolete",
        type=FormFieldType.TEXT,
        order_index=999,
        binding=FormBindingType.DYNAMIC,
    )
    db_session.add(obsolete_field)
    db_session.commit()

    seed_service.apply_seed_definitions()

    final_form_count = db_session.scalar(select(func.count()).select_from(FormSchema))
    obsolete_count = db_session.scalar(
        select(func.count()).select_from(FormField).where(
            FormField.form_id == blp_form.id,
            FormField.key == "obsolete_field",
        )
    )

    assert initial_form_count == len(FORM_SEED_DEFINITIONS)
    assert final_form_count == len(FORM_SEED_DEFINITIONS)
    assert obsolete_count == 0
