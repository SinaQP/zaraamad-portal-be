from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.common.security.dependencies import require_admin, require_admin_or_bridge_access

from app.modules.forms.constants import FormScopeType
from app.modules.forms.dtos import (
    FormFieldCreate,
    FormFieldOut,
    FormFieldUpdate,
    FormSchemaCreate,
    FormSchemaOut,
    FormSchemaUpdate,
)
from app.modules.forms.mappers import FormMapper, get_form_mapper
from app.modules.forms.service import (
    FormFieldService,
    FormSchemaService,
    get_form_field_service,
    get_form_schema_service,
)

FORMS_TAG = "forms"
FORMS_ADMIN_TAG = "form-admin"

router = APIRouter()
forms_router = APIRouter(
    prefix="/api/forms",
    tags=[FORMS_TAG],
    dependencies=[Depends(require_admin_or_bridge_access)],
)
forms_admin_router = APIRouter(
    prefix="/api/admin",
    tags=[FORMS_ADMIN_TAG],
    dependencies=[Depends(require_admin)],
)


@forms_router.get(
    "/",
    response_model=list[FormSchemaOut],
    summary="List forms",
    description=(
        "Return form schemas with nested fields and optional scope filtering. "
        "Accessible by admin users or bridge-authenticated clients."
    ),
    responses={
        200: {"description": "Form schemas returned."},
        401: {"description": "Authorization bearer token or valid X-Bridge-Key is required."},
        403: {"description": "Admin access required for JWT-authenticated users."},
    },
)
def list_forms(
    key: str | None = Query(default=None, description="Filter by exact form key."),
    scope_type: FormScopeType | None = Query(default=None, description="Filter by scope type."),
    scope_value: str | None = Query(default=None, description="Filter by scope value."),
    municipality_code: str | None = Query(default=None, description="Municipality code convenience filter."),
    include_inactive: bool = Query(default=False, description="Include inactive forms when true."),
    service: FormSchemaService = Depends(get_form_schema_service),
    mapper: FormMapper = Depends(get_form_mapper),
) -> list[FormSchemaOut]:
    forms = service.list_forms(
        key=key,
        scope_type=scope_type,
        scope_value=scope_value,
        municipality_code=municipality_code,
        include_inactive=include_inactive,
    )
    return [mapper.to_form_out(form=item) for item in forms]


@forms_router.get(
    "/{key}/resolved/",
    response_model=FormSchemaOut,
    summary="Resolve form by key",
    description=(
        "Resolve the active municipality-scoped form for the provided municipality code, "
        "then fallback to the active global form with the same key. "
        "Accessible by admin users or bridge-authenticated clients."
    ),
    responses={
        200: {"description": "Resolved form returned."},
        404: {"description": "Form was not found."},
        401: {"description": "Authorization bearer token or valid X-Bridge-Key is required."},
        403: {"description": "Admin access required for JWT-authenticated users."},
    },
)
def resolve_form(
    key: str,
    municipality_code: str | None = Query(default=None, description="Fallback municipality code."),
    service: FormSchemaService = Depends(get_form_schema_service),
    mapper: FormMapper = Depends(get_form_mapper),
) -> FormSchemaOut:
    form = service.resolve_form(
        key=key,
        municipality_code=municipality_code,
    )
    return mapper.to_form_out(form=form)


@forms_router.get(
    "/{key}/",
    response_model=list[FormSchemaOut],
    summary="Get forms by key",
    description=(
        "Return active form schemas for the provided key and optional scope filters. "
        "Accessible by admin users or bridge-authenticated clients."
    ),
    responses={
        200: {"description": "Matching forms returned."},
        401: {"description": "Authorization bearer token or valid X-Bridge-Key is required."},
        403: {"description": "Admin access required for JWT-authenticated users."},
    },
)
def get_forms_by_key(
    key: str,
    scope_type: FormScopeType | None = Query(default=None, description="Filter by scope type."),
    scope_value: str | None = Query(default=None, description="Filter by scope value."),
    municipality_code: str | None = Query(default=None, description="Municipality code convenience filter."),
    service: FormSchemaService = Depends(get_form_schema_service),
    mapper: FormMapper = Depends(get_form_mapper),
) -> list[FormSchemaOut]:
    forms = service.list_by_key(
        key=key,
        scope_type=scope_type,
        scope_value=scope_value,
        municipality_code=municipality_code,
    )
    return [mapper.to_form_out(form=item) for item in forms]


@forms_admin_router.post(
    "/forms/",
    response_model=FormSchemaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create form schema",
    description="Create a form schema record. Only admin users can access this endpoint.",
    responses={
        201: {"description": "Form schema created."},
        401: {"description": "Authorization bearer token is required."},
        403: {"description": "Admin access required."},
        409: {"description": "Data integrity error."},
    },
)
def create_form(
    payload: FormSchemaCreate,
    service: FormSchemaService = Depends(get_form_schema_service),
    mapper: FormMapper = Depends(get_form_mapper),
) -> FormSchemaOut:
    form = service.create(dto=payload)
    return mapper.to_form_out(form=form)


@forms_admin_router.patch(
    "/forms/{form_id}/",
    response_model=FormSchemaOut,
    summary="Update form schema",
    description="Update a form schema record by id. Only admin users can access this endpoint.",
    responses={
        200: {"description": "Form schema updated."},
        401: {"description": "Authorization bearer token is required."},
        403: {"description": "Admin access required."},
        404: {"description": "Form schema was not found."},
        409: {"description": "Data integrity error."},
    },
)
def update_form(
    form_id: int,
    payload: FormSchemaUpdate,
    service: FormSchemaService = Depends(get_form_schema_service),
    mapper: FormMapper = Depends(get_form_mapper),
) -> FormSchemaOut:
    form = service.update(form_id=form_id, dto=payload)
    return mapper.to_form_out(form=form)


@forms_admin_router.delete(
    "/forms/{form_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete form schema",
    description="Delete a form schema and all of its fields. Only admin users can access this endpoint.",
    responses={
        204: {"description": "Form schema deleted."},
        401: {"description": "Authorization bearer token is required."},
        403: {"description": "Admin access required."},
        404: {"description": "Form schema was not found."},
    },
)
def delete_form(
    form_id: int,
    service: FormSchemaService = Depends(get_form_schema_service),
) -> Response:
    service.delete(form_id=form_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@forms_admin_router.post(
    "/fields/",
    response_model=FormFieldOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create form field",
    description=(
        "Create a field under a form or parent field, optionally with nested sub-fields. "
        "Only admin users can access this endpoint."
    ),
    responses={
        201: {"description": "Form field created."},
        401: {"description": "Authorization bearer token is required."},
        403: {"description": "Admin access required."},
        404: {"description": "Form or parent field was not found."},
        409: {"description": "Data integrity error."},
    },
)
def create_field(
    payload: FormFieldCreate,
    service: FormFieldService = Depends(get_form_field_service),
    mapper: FormMapper = Depends(get_form_mapper),
) -> FormFieldOut:
    result = service.create(dto=payload)
    return mapper.to_field_out(field=result.field, form_fields=result.form_fields)


@forms_admin_router.patch(
    "/fields/{field_id}/",
    response_model=FormFieldOut,
    summary="Update form field",
    description=(
        "Update a field by id and optionally replace its direct child fields. "
        "Only admin users can access this endpoint."
    ),
    responses={
        200: {"description": "Form field updated."},
        401: {"description": "Authorization bearer token is required."},
        403: {"description": "Admin access required."},
        404: {"description": "Form field was not found."},
        409: {"description": "Data integrity error."},
        422: {"description": "Parent assignment was invalid."},
    },
)
def update_field(
    field_id: int,
    payload: FormFieldUpdate,
    service: FormFieldService = Depends(get_form_field_service),
    mapper: FormMapper = Depends(get_form_mapper),
) -> FormFieldOut:
    result = service.update(field_id=field_id, dto=payload)
    return mapper.to_field_out(field=result.field, form_fields=result.form_fields)


@forms_admin_router.delete(
    "/fields/{field_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete form field",
    description="Delete a field and its nested child fields. Only admin users can access this endpoint.",
    responses={
        204: {"description": "Form field deleted."},
        401: {"description": "Authorization bearer token is required."},
        403: {"description": "Admin access required."},
        404: {"description": "Form field was not found."},
    },
)
def delete_field(
    field_id: int,
    service: FormFieldService = Depends(get_form_field_service),
) -> Response:
    service.delete(field_id=field_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


router.include_router(forms_router)
router.include_router(forms_admin_router)
