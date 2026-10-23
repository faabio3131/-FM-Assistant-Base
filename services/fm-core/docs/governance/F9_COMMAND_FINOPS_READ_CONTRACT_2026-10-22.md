# VendeAtendeIA — F9 Internal FinOps Read Contract (Core → FM Command)

**Status:** internal implementation candidate; *not* production-connected or externally homologated. The canonical AI consumption ledger is Core's `core_ai_usage_events`, NOT the FM Command billing ledger.

## Scope and authority

The `core.ai_command_finops_api.command_finops_router` exports a disabled-by-default FastAPI router. It is activated only when the trusted composition root explicitly mounts it and injects:

- `PersistentAIFinOps(sessions)` pointing at an already provisioned/migrated Core DB.
- `shared_secret` **isolated** from Command's user JWTs, payment gateway secrets, Core model keys and other S2S identities, at least 32 bytes long.

A Command backend with corporate FinOps permissions and own application authentication signs exactly the UTF-8 JSON bytes:

`HMAC_SHA256(secret, "POST\\n/internal/v1/command/ai/finops/report\\n" + raw_body)`

with header `X-FM-Command-FinOps-Signature`. Request JSON contains exactly:

```json
{
  "schema": "fm.core.finops.read.v1",
  "tenant_id": "tenant-a",
  "unit_id": "unit-a",
  "start_date": "2026-10-01",
  "end_date": "2026-10-22",
  "issued_at": 1792627200,
  "nonce": "long-unguessable-service-request-nonce"
}
```

Dates must be UTC civil dates; time window at most **31 days**, no future dates. Timestamp must be within 30 seconds of Core local UTC clock. Duplicate JSON fields, unknown properties, mismatched HMAC, invalid tenant/unit/nonce, large bodies and time skew are rejected before reading ledger.

**No browser or tenant self-service caller may hold this key or select a foreign tenant.** FM Command must enforce corporate permission and product-to-tenant binding before signing. Use TLS, private service ingress, network allowlists, rate limits, secret rotation and origin isolation in external configuration. These steps require deployment/homologation *later*, not before internal build completeness.

## Read semantics

Response is `Cache-Control: no-store`. It returns deterministic buckets by date/provider/model/capability/outcome/currency. It never returns individual event IDs, customer identifiers, prompts, audio, tokens/secrets, raw references or invoice records. Each bucket has:

- `known_cost_subtotal`: **string-encoded Decimal**, and `currency`; currency aggregation across USD and BRL is forbidden without explicit exchange-rate policy.
- `known_cost_events`, `unknown_cost_events`, `attempts`, `fallback_attempts`, and observed token/latency counters.
- `actual_provider_spend_verified: false` and `token_counters_complete: false`; tariff-based Core prices are not PSP/provider settlement evidence.

Report-level `coverage` is one of:

- `no_observations`: no durable observations. **Not** proof of zero provider spend.
- `partial_unknown_costs`: at least one attempt lacks known cost. Subtotals **must not** be interpreted as total spend.
- `priced_internal_observations`: all recorded attempts in the selected buckets have Core-known estimates. Still no proof of actual provider spend.

All data is read-only. Unsupported or inconsistent ledger entries cause 409, source outage causes sanitized 503. Response limits: 500 buckets, no unlimited full-history request. The architecture explicitly keeps AI costs with FM Tecnologia and commercial subscription revenue in FM Command, never on the customer's invoice.

## Internal gates

`pytest tests/test_ai_command_finops_api.py` (actual transient in-memory API and isolated SQLite persistent Core ledger). Covers HMAC tampering, tenant scope, stale requests, duplicate fields, oversized bodies, capped period, mixed currencies, historical subtotal uncertainty, data source outage, untrusted bucket scope and empty ledger.

**Missing for final Prompt Mestre P01/F9 completion:** the FM Command corporate FinOps server route and authenticated HTTPS adapter, UI with accounting provenance, unit/product binding reconciliation, full cross-repo telemetry and performance certification. This read port is not a declaration of all F9 green. It is not auto-mounted and does not connect to outside systems.

## Rollback

Omit the router from the composition root or revert this isolated branch. No schema migration, external call, secrets, payment mutation or ledger write is introduced by this contract.
