# Zaraamad Portal BE

Backend API for Zaraamad Portal Phase 1.

Current release: `1.1.0`

## Overview

This backend currently provides:

- OTP-based login
- JWT access authentication
- Form schema service with municipality-aware resolution and remote token introspection
- Customer management
- Customer income summary and bucket import
- User management
- Service project, group, and catalog management
- Customer-specific service pricing and pricing summary
- Customer service purchase selection with stored totals
- Customer bridge health, capability, cached subscription lookup, and remote subscription management
- Standardized API error responses
- Search, sorting, pagination, and soft deactivation

Main domain changes now active in the codebase:

- organization resources use `customer`
- customer users are linked with `customer_id`
- OTP delivery supports development mode and SMS panel integration

## Tech Stack

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Pydantic v2
- JWT via `python-jose`
- pytest

## Project Structure

```text
app/
  common/
    config.py
    database.py
    dtos.py
    enums.py
    exception_handlers.py
    messages.py
    model_registry.py
    pagination.py
    seeds.py
    security/
      dependencies.py
      jwt_service.py
    services/
      otp_provider.py
      sms_service.py
    validators/
      mobile_validator.py
  modules/
    auth/
    customers/
    service_catalog/
    subscriptions/
    users/
  main.py
  version.py
alembic/
  env.py
  versions/
scripts/
  build_version.py
  seed_admin.py
tests/
```

## Quick Start

### Bash

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python scripts/build_version.py
alembic upgrade head
python scripts/seed_admin.py
uvicorn app.main:app --reload
```

### PowerShell

```powershell
Copy-Item .env.example .env
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
python scripts\build_version.py
alembic upgrade head
python scripts\seed_admin.py
uvicorn app.main:app --reload
```

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)  
ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Configuration

Key environment variables:

- `APP_NAME`: application title in OpenAPI docs
- `APP_VERSION`: release version used to generate `app/version.py`
- `APP_ENV`: environment label such as `development`
- `DATABASE_URL`: database connection string
- `FORM_SERVICE_DEBUG`: toggle extra form-service diagnostics when needed
- `JWT_SECRET_KEY`: JWT signing secret
- `JWT_ALGORITHM`: JWT signing algorithm
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: access token lifetime
- `OTP_EXPIRE_SECONDS`: OTP lifetime in seconds
- `OTP_REQUEST_LIMIT_COUNT`: request limit per rate window
- `OTP_REQUEST_LIMIT_WINDOW_SECONDS`: OTP rate-limit window
- `OTP_DEV_MODE`: if `true`, API returns `dev_otp` in OTP response
- `AUTH_INTROSPECTION_URL`: legacy Zaraamad authenticated-user endpoint used for remote bearer token introspection
- `AUTH_INTROSPECTION_TIMEOUT`: timeout in seconds for remote introspection requests
- `AUTH_INTROSPECTION_CACHE_TTL`: success-cache TTL in seconds for remote introspection by bearer token hash
- `AUTH_INTROSPECTION_FAIL_OPEN`: unsafe escape hatch that bypasses remote introspection failures when explicitly enabled
- `IS_FORM_ADMIN`: allows authenticated remote users to call form admin endpoints when set to `true`
- `SMS_API_URL`: SMS provider endpoint
- `SMS_REQUEST_TIMEOUT_SECONDS`: SMS request timeout
- `BRIDGE_API_KEY`: shared secret used for bridge-authenticated API access
- `SMS_PANEL_ORGANIZATION`: SMS panel organization
- `SMS_PANEL_USERNAME`: SMS panel username
- `SMS_PANEL_PASSWORD`: SMS panel password
- `SMS_PANEL_SENDER`: SMS sender number
- `SEED_ADMIN_FULL_NAME`: default seeded admin full name
- `SEED_ADMIN_MOBILE`: default seeded admin mobile number
- `CORS_ALLOWED_ORIGINS`: comma-separated allowed origins
- `CORS_ALLOWED_ORIGIN_REGEX`: regex fallback for origins
- `CORS_ALLOW_CREDENTIALS`: enable credentialed CORS requests

Local frontend origins are allowed by default for:

- `http://localhost:<any-port>`
- `http://127.0.0.1:<any-port>`
- `http://[::1]:<any-port>`

For deployed frontends:

```bash
CORS_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com
```

## Versioning

Version is driven from `.env.example` and generated into `app/version.py`.

Versioning rule for this project:

- Patch bump: small bug fix, small refactor, cleanup, docs/tests/config update, or small adjustment to existing endpoints without a new business capability.
- Minor bump: new feature, new endpoint, new module, new integration, or a clearly user-visible capability added to the system.
- Major bump: large breaking change, removed or renamed APIs, major response/request contract rewrite, or a release that requires significant client migration.

Default:

- If the change is small and you are unsure, use a patch bump.

After changing `APP_VERSION`, regenerate the build version:

```bash
python scripts/build_version.py
```

## Authentication

Flow:

1. Create or seed an active user.
2. Call `POST /auth/request-otp`.
3. In development mode, read `dev_otp` from the response.
4. Call `POST /auth/verify-otp`.
5. Use the returned bearer token for protected endpoints.
6. Call `GET /auth/me` to fetch the authenticated user profile.

OTP delivery modes:

- `OTP_DEV_MODE=true`: OTP is returned in API response for local development
- `OTP_DEV_MODE=false`: OTP is sent through the configured SMS panel

If SMS mode is enabled and panel configuration is missing or delivery fails, the API returns structured `500` or `503` responses.

## Error Response Format

HTTP errors are standardized with this shape:

```json
{
  "message": "Human-readable message",
  "developer_message": "Developer-oriented detail",
  "detail": "Human-readable message"
}
```

Validation errors return:

```json
{
  "message": "Validation summary",
  "developer_message": "Request validation failed.",
  "detail": [
    {
      "loc": ["body", "field_name"],
      "field": "field_name",
      "msg": "Localized validation message",
      "type": "validation_type",
      "developer_message": "body.field_name: raw error"
    }
  ]
}
```

## API Surface

Authentication:

- `POST /auth/request-otp`
- `POST /auth/verify-otp`
- `GET /auth/me`

Customers:

- `POST /customers`
- `GET /customers`
- `GET /customers/income`
- `PUT /customers/income`
- `GET /customers/{customer_id}`
- `GET /customers/{customer_id}/income`
- `PATCH /customers/{customer_id}`
- `DELETE /customers/{customer_id}`

Customer bridge:

- `GET /customers/{customer_id}/bridge`
- `POST /customers/{customer_id}/bridge/refresh-status`
- `PATCH /customers/{customer_id}/bridge`
- `GET /customers/{customer_id}/bridge/health`
- `GET /customers/{customer_id}/bridge/capabilities`
- `GET /customers/{customer_id}/bridge/subscriptions/active`
- `PATCH /customers/{customer_id}/bridge/subscriptions/active`
- `GET /customers/{customer_id}/bridge/subscriptions/messages`
- `PATCH /customers/{customer_id}/bridge/subscriptions/messages`
- `GET /customers/{customer_id}/bridge/subscriptions/config`
- `PATCH /customers/{customer_id}/bridge/subscriptions/config`
- `POST /customers/{customer_id}/bridge/subscriptions/refresh`

Users:

- `POST /users`
- `GET /users`
- `GET /users/{user_id}`
- `PATCH /users/{user_id}`
- `DELETE /users/{user_id}`

Service projects:

- `POST /service-projects`
- `GET /service-projects`
- `GET /service-projects/{project_id}`
- `PATCH /service-projects/{project_id}`
- `DELETE /service-projects/{project_id}`

Service groups:

- `POST /service-groups`
- `GET /service-groups`
- `GET /service-groups/{group_id}`
- `PATCH /service-groups/{group_id}`
- `DELETE /service-groups/{group_id}`

Services:

- `POST /services`
- `GET /services`
- `GET /services/{service_id}`
- `PATCH /services/{service_id}`
- `DELETE /services/{service_id}`

Customer service configuration:

- `GET /customers/{customer_id}/services`
- `PUT /customers/{customer_id}/services`
- `PATCH /customer-service-configs/{config_id}`
- `DELETE /customer-service-configs/{config_id}`
- `GET /customers/{customer_id}/pricing-summary`

Customer service purchases:

- `GET /customers/{customer_id}/service-purchases`
- `POST /customers/{customer_id}/service-purchases`
- `GET /customer-service-purchases/{purchase_id}`
- `PATCH /customer-service-purchases/{purchase_id}`
- `DELETE /customer-service-purchases/{purchase_id}`

Forms:

- `GET /api/forms/`
- `GET /api/forms/{key}/`
- `GET /api/forms/{key}/resolved/`
- `POST /api/admin/forms/`
- `PATCH /api/admin/forms/{form_id}/`
- `DELETE /api/admin/forms/{form_id}/`
- `POST /api/admin/fields/`
- `PATCH /api/admin/fields/{field_id}/`
- `DELETE /api/admin/fields/{field_id}/`

## Form Service

### Remote auth

The form endpoints accept the existing Zaraamad bearer token and validate it remotely through `AUTH_INTROSPECTION_URL`. Successful introspection responses are cached for `AUTH_INTROSPECTION_CACHE_TTL` seconds by token hash. The resolved auth context keeps `user_id`, `user_name`, `municipality_code`, and `municipality`.

Write endpoints under `/api/admin/*` require authenticated remote form-admin access. If `IS_FORM_ADMIN=true`, any authenticated remote user can use those endpoints. Otherwise the introspection payload must indicate form-admin access through admin/staff flags, role, or permissions.

### Resolution

`GET /api/forms/{key}/resolved/` resolves forms in this order:

1. active municipality-scoped form for the authenticated user municipality
2. active municipality-scoped form for the `municipality_code` query parameter
3. active global form with the same key

Read responses return top-level fields under `fields`, and compound parent fields expose nested children under `sub_fields`.

### Seed migrations

Canonical forms are defined in [`app/modules/forms/seeds/forms_seed_data.py`](./app/modules/forms/seeds/forms_seed_data.py) and applied by Alembic revision `20260404_0028`. The seed logic is idempotent, updates existing managed forms, supports nested sub-fields, and removes obsolete managed fields.

### Sample response

```json
{
  "id": 1,
  "key": "blp_property_general_info",
  "title": "اطلاعات عمومی ملک",
  "version": 1,
  "description": "فرم پایه اطلاعات عمومی پرونده ساختمانی",
  "is_active": true,
  "scope_type": "global",
  "scope_value": null,
  "fields": [
    {
      "id": 10,
      "form_id": 1,
      "parent_field_id": null,
      "key": "detail",
      "label": "جزئیات",
      "type": "compound",
      "required": false,
      "order_index": 90,
      "placeholder": null,
      "default_value": null,
      "validation": null,
      "source": null,
      "options": null,
      "binding": "dynamic",
      "sub_fields": [
        {
          "id": 11,
          "form_id": 1,
          "parent_field_id": 10,
          "key": "detail.land_geo_location_id",
          "label": "موقعیت جغرافیایی زمین",
          "type": "select",
          "required": false,
          "order_index": 10,
          "placeholder": null,
          "default_value": null,
          "validation": null,
          "source": {
            "kind": "lookup",
            "key": "land-geo-location"
          },
          "options": null,
          "binding": "dynamic",
          "sub_fields": []
        }
      ]
    }
  ]
}
```

## List, Search, and Pagination

Most list endpoints support:

- `search`
- `sort_by`
- `sort_order`
- `page`
- `page_size`

Pagination metadata is returned in response headers:

- `X-Total-Count`
- `X-Page`
- `X-Page-Size`
- `X-Total-Pages`

## Business Rules

- `admin` users do not require `customer_id`
- `customer` users must provide a valid active `customer_id`
- customer, user, service project, service group, and service deactivation is soft-delete style through `is_active = false`
- `service_groups.project_id` is required
- `services.group_id` is required
- `service_groups.code` can be duplicated
- `services.code` can be duplicated
- `sale_price` is optional and, when provided, must be non-negative
- `support_price` is required and must be non-negative
- bulk upsert on `PUT /customers/{customer_id}/services` works by `service_id`
- omitted items in a bulk upsert remain unchanged
- service, group, customer-config, and pricing-summary responses include project information
- customer users can list service configs for their own customer
- customer service purchases store the selected `customer_service_config_id` rows as purchase snapshots
- purchase totals are persisted from the selected config prices at the time of create/update
- disabled or inactive customer service configs cannot be selected in a purchase
- selected response timestamps are returned as Jalali datetime strings for `feedback.created_at`, `customers.updated_at`, and `customer-service-configs.updated_at`
- customer service selection snapshot responses return Jalali `date` plus snapshot `time` in `HH:MM:SS` format
- customer bridge subscription management resolves the configured `bridge_base_url` and `bridge_api_key` from the requested customer
- subscription bridge date fields use Jalali datetime strings in `YYYY-MM-DD HH:MM:SS` format

Service catalog hierarchy:

```text
service project -> service group -> service
```

## Sample Requests

Request OTP:

```bash
curl -X POST http://localhost:8000/auth/request-otp \
  -H "Content-Type: application/json" \
  -d '{"mobile":"09120000000"}'
```

Example development response:

```json
{
  "message": "OTP generated for 09120000000.",
  "dev_otp": "123456"
}
```

Verify OTP:

```bash
curl -X POST http://localhost:8000/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"mobile":"09120000000","otp_code":"123456"}'
```

Example response:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "full_name": "System Admin",
    "mobile": "09120000000",
    "role": "admin",
    "customer_id": null,
    "is_active": true
  }
}
```

Create customer:

```bash
curl -X POST http://localhost:8000/customers \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Tehran Customer",
    "grade":1
  }'
```

Create customer user:

```bash
curl -X POST http://localhost:8000/users \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name":"Customer One",
    "mobile":"09121112233",
    "role":"customer",
    "customer_id":1
  }'
```

Bulk upsert customer service config:

```bash
curl -X PUT http://localhost:8000/customers/1/services \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "service_id": 10,
        "is_enabled": true,
        "support_price": 1500000,
        "notes": "Initial setup"
      }
    ]
  }'
```

## Running Tests

```bash
pytest
```

## Manual Commands

Export query results from multiple SQL Server instances into Excel:

```bash
python -m app.commands.export_db_results --input ./servers.xlsx --query-file ./query.sql --output ./db_results.xlsx
```
