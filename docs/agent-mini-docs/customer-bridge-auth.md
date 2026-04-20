# Customer Bridge Auth Mini-Doc

## Purpose

This note explains how Portal authenticates outbound requests to Zaraamad bridge endpoints.
Agents must read this before editing customer bridge auth or bridge request flow.

## Source Files

- `app/modules/customers/service.py`
- `app/modules/customers/portal_bridge_pilot_service.py`
- `app/common/services/bridge_client.py`
- `app/modules/customers/controller.py`
- `app/modules/customers/dtos.py`

## Current Auth Model (Mandatory)

- Portal -> Zaraamad bridge calls use `Authorization: Bearer <portal-jwt>`.
- `X-Bridge-Key` is not used for outbound bridge calls.
- Bridge config completeness for outbound calls requires:
  - `bridge_is_enabled = true`
  - non-empty `bridge_base_url`
- `bridge_api_key` is not required in runtime request resolution.

## JWT Signing Rules

- Algorithm: `RS256`
- Private key source: `JWT_PRIVATE_KEY`
- Issuer: `JWT_ISSUER`
- TTL seconds: `JWT_TTL_SECONDS`
- Core claims sent by bridge service:
  - `iss`
  - `sub` (service subject for bridge requests)
  - `bridge_id`
  - `customer_id`
  - `iat`
  - `exp`
  - `jti`

## Error Handling Expectations

- Missing/invalid bridge config -> `409` with `CUSTOMER_BRIDGE_NOT_CONFIGURED`
- Missing private key / JWT signing failure -> `503` with `CUSTOMER_BRIDGE_REQUEST_FAILED`
- Upstream unauthorized -> `502` with `CUSTOMER_BRIDGE_AUTH_FAILED`
- Upstream connection issues -> `503` with `CUSTOMER_BRIDGE_UNAVAILABLE`

## Update Checklist (Required After Any Related Change)

- Verify this file still matches:
  - required config fields
  - auth headers used in outbound calls
  - JWT claim set and algorithm
  - mapped HTTP statuses/messages
- Update tests in:
  - `tests/test_customer_bridge.py`
  - `tests/test_portal_bridge_pilot.py`
