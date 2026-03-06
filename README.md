# Zaraamad Portal BE (Phase 1)

Phase 1 includes:
- User management
- OTP login (mock/dev mode)
- JWT access authentication
- Municipality management
- Assign users to municipalities

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
    municipalities/
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
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
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

## Run Tests

```bash
pytest
```

## Key Endpoints

- `POST /auth/request-otp`
- `POST /auth/verify-otp`
- `GET /auth/me`
- `POST /municipalities`
- `GET /municipalities`
- `GET /municipalities/{id}`
- `PATCH /municipalities/{id}`
- `DELETE /municipalities/{id}`
- `POST /users`
- `GET /users`
- `GET /users/{id}`
- `PATCH /users/{id}`
- `DELETE /users/{id}`

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
    "email": null,
    "role": "admin",
    "municipality_id": null,
    "is_active": true
  }
}
```

### Create Municipality (Admin)

```bash
curl -X POST http://localhost:8000/municipalities \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Tehran Municipality",
    "code":"THR-001",
    "province":"Tehran",
    "city":"Tehran"
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
    "email":"customer@example.com",
    "role":"customer",
    "municipality_id":1
  }'
```
