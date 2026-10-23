# F3.1 — Persisted routing foundation (candidate, NOT F3 certification)

Date: 2026-10-18
Branch: feat/ai-service-v1
Status: F3 IN_PROGRESS

This increment adds a SQLAlchemy schema and repository for:
- provider catalog and model catalog;
- model capability map;
- platform / tenant / unit scoped route policies;
- opaque FM-managed and BYOK secret references;
- explicit provider health and circuit eligibility.

Important design decisions:
- Unit policies override tenant policies, which override platform policies.
- If a more-specific policy exists but is unavailable, routing fails closed
  rather than silently escaping its scope or choosing a weaker policy.
- Equal priorities inside an effective scope fail closed.
- Provider health must be explicitly healthy, with closed circuit.
- BYOK references are scoped to their tenant. No raw provider keys are stored.
- Mutation methods are internal repositories; **they must not be exposed to
  user-facing APIs without distinct admin authentication and authorization**.

This is an isolated persistence building block. The production runtime is NOT
switched from the current static bootstrap yet. Do not call this a complete F3.

Remaining mandatory work before F3 GREEN:
- versioned Alembic migration up/down and PostgreSQL rehearsal;
- integration with active CoreAIRuntime and safe secret-resolution ports;
- immutable pricing and cost calculation;
- persistent usage ledger / FinOps queries;
- quota hooks, audit, health/circuit management and readiness;
- separate admin service key and governed CRUD API;
- end-to-end Assistant/Core regression, complete security gates and CI;
- live provider homologation only when credential/approval exists.

No production deploy and no merge.
