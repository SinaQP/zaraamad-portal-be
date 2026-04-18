# Portal <-> Zaraamad Minimal B2B Auth (Phase 1)

## Scope Implemented Now

- User authenticates only with Portal.
- Frontend calls only Portal APIs.
- Portal proxies one pilot call to Zaraamad: `GET /internal/portal/pilot/ping`.
- Portal resolves target Zaraamad instance from existing Bridge table (`customer_bridge_configs`) using `customer_id`.
- Portal mints a short-lived RS256 JWT per request and sends it as `Authorization: Bearer <token>` to Zaraamad.
- Zaraamad validates the Portal JWT on the pilot endpoint and does not require a separate Zaraamad user login/session.

## Bridge Usage in This Phase

Bridge source of truth is the existing `customer_bridge_configs` row:

- `customer_id`: lookup key for the target instance.
- `bridge_base_url`: internal Zaraamad base URL for routing.
- `bridge_is_enabled`: whether routing to Zaraamad is allowed.

Notes:

- In the current schema, `bridge_id` in the token is the bridge row identifier (`customer_id`).
- Existing Bridge records are reused as-is; no Bridge schema redesign was introduced.

## Portal-Issued JWT (Phase 1)

Portal creates a minimal RS256 token with:

- `iss = zaravand-portal` (configurable by `PORTAL_BRIDGE_JWT_ISSUER`)
- `sub = user:<portal_user_id>`
- `bridge_id = <customer_id>`
- `customer_id = <customer_id>` (optional helper claim)
- `iat`
- `exp` (short TTL via `PORTAL_BRIDGE_JWT_TTL_SECONDS`)
- `jti`

## What Belongs in Bridge (Now)

- Instance routing metadata (`customer_id`, target base URL, enabled status).
- Bridge/instance selection for Portal -> Zaraamad calls.

## What Does Not Belong in Bridge (Now)

- Portal JWT signing private keys.
- User authentication state or sessions.
- Zaraamad business logic.
- A shared secret that treats Zaraamad as one global target.

## Intentionally Postponed

Not implemented in this phase:

- `audience`, `tenant_id`, `instance_id` Bridge columns and validations.
- Instance-scoped audience/tenant claim enforcement.
- Timeout/retry policy frameworks or operational abstractions.
- Registry redesign / generic bridge framework.
- Multi-endpoint proxy expansion beyond the single pilot endpoint.
