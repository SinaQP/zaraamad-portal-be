---
description: "Engineering rules: SOLID-first design, minimal changes, and do-not-add-unrequested APIs/features."
alwaysApply: true
globs: ["app/**/*.py"]
---

# Engineering Rules

## SOLID is mandatory
- Apply SOLID principles in design and refactors:
  - Single Responsibility: keep functions/classes focused.
  - Open/Closed: extend via composition/configuration, avoid breaking changes.
  - Liskov: subclasses must remain substitutable.
  - Interface Segregation: avoid large god-interfaces; keep contracts small.
  - Dependency Inversion: depend on abstractions where it reduces coupling.

## DTO design rules
- Prefer inheritance/mixins to reduce duplication in DTOs:
  - Define shared base DTOs (e.g., `MongoDTO`, `WithId`, `<Model>Base`) and derive `Create/Out` from them.
- DTOs are API contracts; DO NOT auto-couple them to DB schemas.
- Ensure alignment via explicit mappers and tests (not implicit mirroring).

## Frontend message language
- Every runtime message returned to frontend clients MUST be Persian.
- This applies to success payload messages, `HTTPException.detail`, and validation error texts.
- Do not introduce new English user-facing messages in API responses.
- User-facing messages must be understandable for non-technical users and must not expose raw field names like `customer_id`, `project_id`, or similar implementation details.
- Error responses must also include a separate developer-oriented explanation so frontend/backend developers can diagnose the failure without relying on the user-facing text.

## Scope control (mandatory)
- Do NOT create new endpoints, routes, modules, background jobs, or extra features unless explicitly requested by the user.
- Implement only what is directly asked.
- If a requirement is missing, implement the smallest compliant change and leave a clear TODO comment rather than inventing behavior.
