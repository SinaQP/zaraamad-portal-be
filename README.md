# Zaraamad Portal BE (Phase 1)

Phase 1 includes:
- User management
- OTP login (mock/dev mode + single SMS panel integration)
- JWT access authentication
- Customer management
- Assign users to customers
- Service catalog management
- Service project management
- Service group management
- Customer-specific service pricing

Refresh token is not implemented in this phase to keep authentication flow minimal and focused on access-token based APIs.

## Tech Stack

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Pydantic v2
- JWT (python-jose)
- pytest

## Project Structure

```text
app/
  common/
    config.py
    database.py
    dtos.py
    enums.py
    model_registry.py
    seeds.py
    security/
      dependencies.py
      jwt_service.py
    services/
      otp_provider.py
    validators/
      mobile_validator.py
  modules/
    auth/
    customers/
    users/
  main.py
alembic/
  env.py
  versions/
scripts/
  seed_admin.py
tests/
```

## Setup

```bash
cp .env.example .env | copy /Y .env.example .env
python -m venv .venv
source .venv/bin/activate | .venv\Scripts\activate
pip install -e .[dev]
```

## Run Migrations

```bash
alembic upgrade head
```

## Seed Default Admin

```bash
python scripts/seed_admin.py
```

## Run API

```bash
uvicorn app.main:app --reload
```

## Frontend Origin Access

Browser clients need CORS enabled. This API now allows local frontend dev origins by default:
- `http://localhost:<any-port>`
- `http://127.0.0.1:<any-port>`
- `http://[::1]:<any-port>`

For deployed frontends, add your app URL in `.env`:

```bash
CORS_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com
```

OTP delivery modes:
- `OTP_DEV_MODE=true`: OTP is returned in the API response for local development.
- `OTP_DEV_MODE=false`: OTP is sent by SMS.
- Configure the single SMS panel with `SMS_PANEL_ORGANIZATION`, `SMS_PANEL_USERNAME`, `SMS_PANEL_PASSWORD`.
- Optional overrides: `SMS_API_URL`, `SMS_PANEL_SENDER`, `SMS_REQUEST_TIMEOUT_SECONDS`.

## Run Tests

```bash
pytest
```

## Key Endpoints

- `POST /auth/request-otp`
- `POST /auth/verify-otp`
- `GET /auth/me`
- `POST /customers`
- `GET /customers`
- `GET /customers/{id}`
- `PATCH /customers/{id}`
- `DELETE /customers/{id}`
- `POST /users`
- `GET /users`
- `GET /users/{id}`
- `PATCH /users/{id}`
- `DELETE /users/{id}`
- `POST /service-projects`
- `GET /service-projects`
- `GET /service-projects/{id}`
- `PATCH /service-projects/{id}`
- `DELETE /service-projects/{id}`
- `POST /services`
- `GET /services`
- `GET /services/{id}`
- `PATCH /services/{id}`
- `DELETE /services/{id}`
- `POST /service-groups`
- `GET /service-groups`
- `GET /service-groups/{id}`
- `PATCH /service-groups/{id}`
- `DELETE /service-groups/{id}`
- `GET /customers/{customer_id}/services`
- `PUT /customers/{customer_id}/services`
- `PATCH /customer-service-configs/{id}`
- `GET /customers/{customer_id}/pricing-summary`

List API query options (available on list endpoints):
- `search`: free-text search on relevant fields
- `sort_by`: field name (endpoint-specific allowed values)
- `sort_order`: `asc` or `desc`
- `page`: page number (starts at `1`)
- `page_size`: page size (`1..100`)

Pagination metadata is returned in response headers:
- `X-Total-Count`
- `X-Page`
- `X-Page-Size`
- `X-Total-Pages`

Bulk upsert behavior for `PUT /customers/{customer_id}/services`:
- Upserts provided `service_id` rows
- Creates missing rows
- Updates existing rows
- Items omitted from request remain unchanged

Service catalog hierarchy:
- `service project -> service group -> service`
- `service_groups.project_id` is required
- service, group, customer-config, and pricing-summary responses now include project information

Pricing fields for customer service config:
- `sale_price` is required
- `support_price` is optional (`null` is valid)

User role and customer rule:
- `admin` users do not require `customer_id` (it is stored as `null`)
- `customer` users must provide `customer_id`

Catalog code behavior:
- `service_groups.code` can be duplicated
- `services.code` can be duplicated

## Sample Requests

### Request OTP

```bash
curl -X POST http://localhost:8000/auth/request-otp \
  -H "Content-Type: application/json" \
  -d '{"mobile":"09120000000"}'
```

Response (dev mode):

```json
{
  "message": "OTP generated for 09120000000.",
  "dev_otp": "123456"
}
```

### Verify OTP

```bash
curl -X POST http://localhost:8000/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"mobile":"09120000000","otp_code":"123456"}'
```

Response:

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

### Create Customer (Admin)

```bash
curl -X POST http://localhost:8000/customers \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Tehran Customer",
    "grade":1
  }'
```

### Create Customer User (Admin)

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
