# Bridge Instance Registry

## Purpose
`Bridge` is the Portal source of truth for resolving a Zaraamad target instance per customer.

Each row represents one customer-scoped Zaraamad instance and stores routing + instance-auth metadata only.

## Canonical Bridge Fields

Required for Portal -> Zaraamad routing/auth:

- `customer_id`
- `instance_id`
- `base_url_internal`
- `audience`
- `tenant_id`
- `status`

Optional request behavior metadata:

- `request_timeout_seconds`
- `request_retry_count`
- `request_retry_backoff_seconds`

Transitional legacy field:

- `bridge_api_key` (optional fallback only; not required in the new flow)

## Portal -> Zaraamad Resolution

Portal resolves Bridge by `customer_id` and optional `instance_id`:

1. Read the Bridge row.
2. Validate row readiness (`status=active` + required canonical fields).
3. Route request to `Bridge.base_url_internal`.
4. Mint outbound bearer JWT from Portal signing config and Bridge claims:
   - `aud` from `Bridge.audience`
   - `tenant_id` from `Bridge.tenant_id`
   - `instance_id` from `Bridge.instance_id`
5. Apply timeout/retry from Bridge row when present, otherwise service defaults.

## What Belongs In Bridge

- Instance routing metadata (`base_url_internal`, `status`)
- Instance auth context for outbound service tokens (`audience`, `tenant_id`, `instance_id`)
- Per-instance transport behavior overrides (timeout/retry)
- Optional transitional per-instance integration secret (`bridge_api_key`)

## What Does Not Belong In Bridge

- Portal JWT signing private keys
- End-user auth/session data
- Business-domain state (orders, subscriptions, service rules, etc.)
- Cross-instance global secrets shared by all Zaraamad instances
