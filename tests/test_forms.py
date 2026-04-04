from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.messages import INVALID_AUTH_TOKEN
from app.common.security.remote_auth import (
    RemoteAuthCache,
    RemoteAuthPayloadExtractor,
    RemoteAuthUnauthorizedError,
    RemoteAuthenticatedUser,
    RemoteBearerAuthenticator,
    get_optional_remote_authenticated_user,
)
from app.common.config import Settings
from app.main import app
from app.modules.forms.constants import FormBindingType, FormFieldType, FormScopeType
from app.modules.forms.schemas import FormField, FormSchema
from app.modules.forms.service import FormSeedService
from app.modules.forms.seeds.forms_seed_data import FORM_SEED_DEFINITIONS


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


def test_resolved_form_uses_authenticated_user_municipality_first(
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
    app.dependency_overrides[get_optional_remote_authenticated_user] = lambda: RemoteAuthenticatedUser(
        user_id=9,
        user_name="Ali",
        municipality_code="sirjan",
        municipality={"code": "sirjan", "name": "Sirjan"},
        raw_payload={"user_id": 9, "municipality_code": "sirjan"},
    )

    response = client.get("/api/forms/resolved-form/resolved/?municipality_code=zarand")

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


class SuccessfulIntrospectionClient:
    def __init__(self) -> None:
        self.calls = 0

    def introspect(
        self,
        *,
        url: str,
        authorization_header: str,
        timeout_seconds: int,
    ) -> dict[str, object]:
        self.calls += 1
        assert url == "https://legacy.example.com/upm/users/get_authenticated_user/"
        assert authorization_header == "Bearer good-token"
        assert timeout_seconds == 3
        return {
            "user_id": 42,
            "user_name": "Remote User",
            "municipality_code": "sirjan",
            "municipality": {"code": "sirjan", "name": "Sirjan"},
        }


class UnauthorizedIntrospectionClient:
    def introspect(
        self,
        *,
        url: str,
        authorization_header: str,
        timeout_seconds: int,
    ) -> dict[str, object]:
        del url, authorization_header, timeout_seconds
        raise RemoteAuthUnauthorizedError(status_code=401)


def _build_remote_authenticator(client: object) -> RemoteBearerAuthenticator:
    return RemoteBearerAuthenticator(
        settings=Settings(
            auth_introspection_url="https://legacy.example.com/upm/users/get_authenticated_user/",
            auth_introspection_timeout=3,
            auth_introspection_cache_ttl=60,
            auth_introspection_fail_open=False,
        ),
        introspection_client=client,  # type: ignore[arg-type]
        payload_extractor=RemoteAuthPayloadExtractor(),
        cache=RemoteAuthCache(),
    )


def test_remote_authenticator_succeeds_and_caches_result() -> None:
    client = SuccessfulIntrospectionClient()
    authenticator = _build_remote_authenticator(client)

    first_user = authenticator.authenticate("good-token")
    second_user = authenticator.authenticate("good-token")

    assert first_user.user_id == 42
    assert first_user.user_name == "Remote User"
    assert first_user.municipality_code == "sirjan"
    assert first_user.municipality == {"code": "sirjan", "name": "Sirjan"}
    assert second_user == first_user
    assert client.calls == 1


def test_remote_authenticator_rejects_invalid_token() -> None:
    authenticator = _build_remote_authenticator(UnauthorizedIntrospectionClient())

    with pytest.raises(HTTPException) as exc_info:
        authenticator.authenticate("bad-token")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["message"] == INVALID_AUTH_TOKEN


def test_remote_authenticator_extracts_municipality_code_from_nested_payload() -> None:
    class NestedPayloadClient:
        def introspect(
            self,
            *,
            url: str,
            authorization_header: str,
            timeout_seconds: int,
        ) -> dict[str, object]:
            del url, authorization_header, timeout_seconds
            return {
                "data": {
                    "user": {
                        "id": 7,
                        "full_name": "Nested User",
                        "municipality": {
                            "code": "zarand",
                            "name": "Zarand",
                        },
                    }
                }
            }

    authenticator = _build_remote_authenticator(NestedPayloadClient())

    user = authenticator.authenticate("nested-token")

    assert user.user_id == 7
    assert user.user_name == "Nested User"
    assert user.municipality_code == "zarand"
    assert user.municipality == {"code": "zarand", "name": "Zarand"}
