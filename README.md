# Zaraamad Portal BE

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

In the current codebase, `customer` is a user role. The public resource name for organizations is still `municipality`, and the active API routes use `/municipalities/...`.

Refresh tokens and external SMS delivery are not implemented in the current runtime.

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
    validators/
      mobile_validator.py
  modules/
    auth/
    customers/
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

Windows PowerShell equivalents:

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

Swagger UI is available at [http://localhost:8000/docs](http://localhost:8000/docs) and ReDoc at [http://localhost:8000/redoc](http://localhost:8000/redoc).

## Configuration

Key environment variables:

- `APP_NAME`: API title shown in OpenAPI docs.
- `APP_VERSION`: release number stored in `.env.example` and used to generate `app/version.py`.
- `APP_ENV`: environment label such as `development`.
- `DATABASE_URL`: SQLAlchemy connection string. Default expects local PostgreSQL with `psycopg`.
- `JWT_SECRET_KEY`: secret used to sign access tokens.
- `JWT_ALGORITHM`: JWT signing algorithm. Default is `HS256`.
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: access token lifetime in minutes.
- `OTP_EXPIRE_SECONDS`: OTP lifetime.
- `OTP_REQUEST_LIMIT_COUNT`: max OTP requests within the rate-limit window.
- `OTP_REQUEST_LIMIT_WINDOW_SECONDS`: OTP rate-limit window in seconds.
- `OTP_DEV_MODE`: when `true`, `POST /auth/request-otp` returns `dev_otp` in the response.
- `SEED_ADMIN_FULL_NAME`: display name for the seeded admin.
- `SEED_ADMIN_MOBILE`: mobile number for the seeded admin.
- `CORS_ALLOWED_ORIGINS`: comma-separated frontend origins.
- `CORS_ALLOWED_ORIGIN_REGEX`: regex fallback for allowed origins.
- `CORS_ALLOW_CREDENTIALS`: whether credentialed CORS requests are allowed.

Local frontend origins are already allowed by default for:

- `http://localhost:<any-port>`
- `http://127.0.0.1:<any-port>`
- `http://[::1]:<any-port>`

For deployed frontends, set:

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
python scripts/build_version.py
```

## Authentication Flow

1. Create or seed an active user.
2. Call `POST /auth/request-otp` with the user's mobile number.
3. If `OTP_DEV_MODE=true`, the response includes `dev_otp`.
4. Call `POST /auth/verify-otp` with `mobile` and `otp_code`.
5. Use the returned bearer token for protected endpoints.
6. Call `GET /auth/me` to fetch the authenticated user profile.

Important:

- The current OTP provider is mock-based.
- When `OTP_DEV_MODE=false`, the API stops returning `dev_otp`, but it still does not send a real SMS through an external provider.
- This means the current runtime is suitable for development and internal testing, not production-grade OTP delivery.

## API Surface

Authentication:

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
- `GET /service-groups/{id}`
- `PATCH /service-groups/{id}`
- `DELETE /service-groups/{id}`
- `GET /customers/{customer_id}/services`
- `PUT /customers/{customer_id}/services`
- `PATCH /customer-service-configs/{id}`
- `GET /customers/{customer_id}/pricing-summary`

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

Request OTP:

```bash
curl -X POST http://localhost:8000/auth/request-otp \
  -H "Content-Type: application/json" \
  -d '{"mobile":"09120000000"}'
```

Example response in development mode:

```json
{
  "message": "...",
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

Bulk upsert municipality service config:

```bash
curl -X PUT http://localhost:8000/municipalities/1/services \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "service_id": 10,
        "is_enabled": true,
        "sale_price": 5000000,
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
