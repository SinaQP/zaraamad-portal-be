---
description: "FastAPI architecture: modular structure, service-based logic, strict separation of DB schemas vs API DTOs, common module, and scalable folder splits."
alwaysApply: true
globs: ["app/**/*.py"]
---

# Architecture Rules (FastAPI)

## Module structure (mandatory)
- Every feature lives under `app/modules/<name>/`.
- Each module MUST contain (at minimum):
  - `module.py`
  - `controller.py` OR `controller/` (folder split allowed)
  - `service.py` OR `service/` (folder split allowed)
  - `dtos.py` (API DTOs only)
  - `schemas.py` (DB models only)
- Optional: `mappers.py`, `constants.py`, `clients.py`, `validators.py`

## Strict separation: DB schemas vs API DTOs (mandatory)
- `schemas.py` contains only database-layer models.
  - DB model class names MUST be domain names only (e.g., `Ingestion`, `RawMeasurement`) and MUST NOT end with `Entity`.
- `dtos.py` contains only Pydantic models used for API requests/responses.
- DO NOT define DB models in `dtos.py`.
- DO NOT define API DTOs in `schemas.py`.

## Mapping rules (mandatory)
- Mapping between DB models and DTOs MUST be explicit:
  - Prefer `mappers.py` (recommended) OR small mapping helpers inside `service.py`.
- Controllers MUST NOT contain mapping logic.

## No Repository layer
- Do NOT create a `repository.py` layer.
- Data access lives in `service.py` (isolated into helper methods/classes).

## Controller rules
- Controllers define routes only and call services.
- Controllers MUST use DTOs from `dtos.py` for request bodies and `response_model`.

## Swagger / OpenAPI documentation (mandatory)
- Every endpoint MUST include `summary` and `description`.
- Use `response_model` for success responses.
- Define error responses via `responses={...}` when relevant.
- DTO fields MUST include `Field(..., description="...", examples=[...])`.
- Tag routes consistently via module router configuration.

## Common module (mandatory)
- A shared module MUST exist at `app/common/`.
- Any cross-module reusable code MUST live in `app/common/` (no duplication).
- Modules MUST NOT import from each other directly; extract shared contracts to `app/common/`.

## Large-file split rule (mandatory)
- If `controller.py` or `service.py` grows large, convert it into a folder:
  - `controller/__init__.py` re-exports a single `router`
  - `service/__init__.py` re-exports the service public API (`get_<x>_service`, service class)
- `module.py` MUST import only the public `router` from `controller` (file or package).
