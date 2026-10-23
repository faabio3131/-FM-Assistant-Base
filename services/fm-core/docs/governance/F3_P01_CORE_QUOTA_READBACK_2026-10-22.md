# F3/P01 — FM Command → FM Core signed quota readback (internal contract)

**Status:** opt-in FastAPI router implementation on Core candidate branch; external configuration and homologation deferred until software construction is fully certified.

## Authority chain

FM Command corporate owner/admin authenticates an independent P01 correction intent, the current paid invoice, delivered reactivation C06 and signed Assistant readback. Command then selects the **external tenant ID from its own canonical C06 command** and an explicitly supplied unit ID. The unit cannot be invented by a customer: Core independently asks Assistant for a FRESH signed policy for that exact `tenant_id,unit_id,capability`.

The opt-in Core route is `POST /internal/v1/command/ai/quota-readback`. Input: exact keys `schema,tenant_id,unit_id,capability,issued_at,nonce`; schema `fm.core.ai.quota-readback.v1`, supported capabilities `atendimento_interpretacao` and `atendimento_transcricao`. It enforces the separate HMAC `HMAC_SHA256(secret, b"POST\n" + path + b"\n" + exact_body)`, 30s UTC timestamp window, 2048-byte ceiling even for chunked streams, UUID-independent tenancy identifiers, no duplicate JSON fields. The key must be ≥32 random bytes, distinct from Command/Assistant license signer, FinOps secret, AI provider secrets and browser tokens. Use TLS, restricted network, rate limiting and key rotation in the **post-build** environment. No mount into the Core application by default.

## Read semantics

- Fresh Assistant grant verifies active, unexpired, tenant/unit-bound licensed plan; **no cached historic grant**.
- The Core reads existing signed-grant policy and transactional quota snapshots **without projecting grants or inserting reservations**. It verifies plan revision and exact limits/windows for every metric, ensures mandatory `ai.requests` and `ai.total_tokens` are present, and reconciles reserved+consumed+remaining=limit. Policy not yet projected returns explicit 409, not a fabricated zero.
- 200 returns `license_freshly_verified=true`, `core_policy_matches_signed_grant=true`, bounded `quota_metrics`, `reservation_created=false`, `provider_called=false`, `case_resolved=false`, `Cache-Control:no-store`.
- 409 means *no proof* (Assistant license unavailable, suspended, mismatched/absent quota projection). 503 means source error. These results cannot be transformed to a green license badge by Command.
- Readback is for the **specified unit and capability** at that instant; never claim all tenants/units or actual provider settlement, nor guarantee that the next AI request will have sufficient tokens.

Tests: `pytest tests/test_ai_command_quota_readback.py`, signed/unsigned/tampered payload, replay-window, duplicate JSON, wrong tenant/unit, suspension/outage, mismatch vs Core ledger, actual SQLite reservation before read, read twice without balance change.

**P01 remains open** until FM Command integrates this proof into its own authorized correction workflow; even a positive readback cannot automatically mark a financial case resolved. No real-provider/PSP/WhatsApp testing or production deployment during construction.

## B1/F3 runtime composition — opt-in readiness closure (22/10/2026)

The previous Core PR #3 built and tested the HMAC APIRouter but **did not mount the router into `create_app()`**. Thus Command PR #154 could compile while live runtime lacked the endpoint. The corrected build now registers it in the FastAPI application only when `FM_CORE_COMMAND_QUOTA_READBACK_ENABLED=true`, validated at startup against the independent `FM_CORE_COMMAND_QUOTA_READBACK_SECRET` (32–256 UTF-8 bytes). Enabled mode requires persistent DB, a configured Assistant plan signer/trusted HTTPS origin and a key separate from service, admin, Assistant plan/bridge and governed-recovery keys. Setting a secret while OFF fails validation.

During the application's lifespan, the same freshly authenticated `SignedAssistantPlanAuthority` and canonical persistent `QuotaReservations` ledger used for AI admission are bound to the HMAC read-only handler. Missing/unavailable authority or ledger fails closed. No tenant or browser can provide signing secrets, plan revision or source-of-truth balance. No provider request or artificial quota admission is performed. Without enabled configuration the route is **not present**, even with a valid Command signature.

Test: `tests/test_ai_command_quota_runtime_mount.py` checks default absence, invalid/missing/reused keys, unique mounted route, actual read-only FastAPI request with the Core SQLite ledger and simulated license suspension/failure. Original `tests/test_ai_command_quota_readback.py` continues to cover parser, HMAC, schema, scoped policy match and no-reservation behavior.

Feature flag and credentials remain OFF/unset on any real deployment until after BUILD_COMPLETE_INTERNAL_GREEN and express activation approval. Never present this as live TLS/PSP/provider homologation.
