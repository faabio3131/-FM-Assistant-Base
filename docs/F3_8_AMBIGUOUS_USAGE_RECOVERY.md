# F3 — Governed ambiguous AI usage recovery (internal candidate)

Every provider call requires signed-license quota reserve first. A timeout, 503, unknown usage or failed fallback NEVER proves a zero-charge result. Keep the reservation; never retry the same request or automatically refund uncertain usage.

The internal service `QuotaReservations.reconcile_ambiguous_bundle` requires a fresh, privileged human Command identity, exactly matching tenant/request/metric scope, matching policy revisions, a SHA-256 digest referencing reviewed provider evidence, and a decision of either `provider_usage_confirmed` or `provider_no_charge_confirmed`. A no-charge decision MUST refer to an actual provider-issued confirmation, not missing billing records or an operator guess. The hash is an evidence reference, not proof of the provider's statement.

The caller MUST first verify the signed Command RS256 token through `verify_command_platform_admin`; constructing `VerifiedCommandAdmin` directly at an API boundary is forbidden. No HTTP recovery endpoint is exposed. Every metric in the bundle is settled atomically with a Command audit entry; the unique Command token JTI prevents reuse of the same authorization. PostgreSQL locks protect concurrent resolution; settled requests cannot be reopened. No prompts or API keys are stored in the audit.

Remaining release gates: provider evidence ingestion and verification, immutable evidence retention, authenticated Command recovery API, approval segregation when necessary, and true Command/Assistant/Core multi-process PostgreSQL integration. Until then, it is NOT a production-ready recovery workflow. F3 remains BUILD_IN_PROGRESS. No production deploy, merge, real provider credential or external homologation.


## F3 internal advance — Command-signed optional recovery boundary

Implemented `core/ai_governed_recovery.py` and `core/ai_governed_recovery_api.py`. The recovery command holds ONLY the request/tenant/unit/revisions plus an opaque evidence ID. The command must carry an independently verifiable short-lived RS256 Command platform-admin token with recent step-up; the evidence ID must resolve through an independently trusted `ProviderEvidenceVerifier` implementation. An arbitrary caller-supplied token count/hash/provider JSON is not accepted as provider proof. Core then binds the independently resolved provider receipt to the canonical quota ledger through `reconcile_verified_provider_receipt`, preserving the existing one-time JTI audit and atomic complete-bundle settlement.

The HTTP router is deliberately **opt-in**. It is NOT registered with the default `create_app` because no production-grade `ProviderEvidenceVerifier` has been certified. Enabling a mutation endpoint backed only by a caller-supplied hash or by the provider-search candidate flow is prohibited. F3 remains BUILD_IN_PROGRESS until durable evidence verification/storage and the fully authenticated Command-to-Core integration exist.

Synthetic tests certify JWT scope failures, cross-tenant evidence refusal, optional route behavior and absence from the default Core app. No real provider or externally configured trust anchors were used. External homologation stays deferred until software construction is complete.


## F3 — 2026-10-20 IMMUTABLE GATEWAY-ATTESTED PROVIDER EVIDENCE

- Added `core/ai_provider_evidence_store.py` and additive Alembic revision `f3_0005`. A separate authorized FM evidence connector can sign a request/tenant/unit/provider/model/input/output/cost/digest statement with a segregated 32+-byte HMAC gateway secret. Core verifies exact signature and stores ONLY scoped immutable metadata; duplicate identical evidence is idempotent and altered/foreign evidence is denied. No raw prompts, API tokens or provider response bodies are stored.
- `TrustedProviderEvidenceStore.verify` implements the exact-scoped `ProviderEvidenceVerifier` required by the optional Command recovery router; unreadable or mismatched evidence keeps quota RESERVED. The provider's own independently checked source authenticity is the responsibility of the FM gateway connector, NOT something HMAC proves by itself. The gateway authentication does not constitute proof of actual paid provider usage absent upstream verification.
- Core bootstrap `REQUIRED_REVISION` updated to `f3_0005` so older schemas fail readiness. Synthetic HMAC and immutable-evidence tests added; disposable PostgreSQL migration gate and AI Service CI on functional SHA `3733c25e39d2c9df1203b4c9834604c7c96dbcb8` both SUCCESS (runs `39351947353`, `39351947357`).
- Companion Command branch adds an RS256 recovery token signer, strict one-shot HTTPS client and three-codebase cross-runtime tests. This is opt-in internal construction and must NOT be exposed on production Core until a provider-authenticating gateway verifier is independently certified. Real separate three-service network E2E is not yet proven. No deploy/merge/production migration or external homologation; F3 BUILD_IN_PROGRESS.
