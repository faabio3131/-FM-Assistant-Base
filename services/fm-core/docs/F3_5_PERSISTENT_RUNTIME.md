# F3.5 — Persistent Core Startup & Fail-Closed Service Boundary

**Status:** implementation candidate, F3 not certified.

- `FM_CORE_CONTROL_PLANE_DATABASE_URL` is the explicit opt-in for persistent Core routing in dev/test and mandatory in staging/production.
- Staging/production demand PostgreSQL plus distinct strong `FM_CORE_SERVICE_KEY` and `FM_CORE_ADMIN_KEY`.
- Commercial startup rejects direct `FM_CORE_AI_ROUTES_JSON` routing, and requires preexisting schema at Alembic revision `f3_0002` (F3.6.2 administrative audit ledger; earlier F3.5 used `f3_0001`).
- No migrations run automatically, no database, provider or secret mutations occur on boot.
- The existing `AIModelRouter` is reused; a fresh scoped route policy and FM-managed secret reference are resolved per request.
- Metering is written through `PersistentAIFinOps` (no in-memory commercial default).
- Without a shared tenant-scoped credential resolver, BYOK fails closed.
- The `/ready` endpoint checks DB connectivity, schema and revision; `/health` does not reveal tenant/route/provider inventory for Control Plane mode.
- Errors resolving routes, secrets or database are mapped to generic 503 dependency unavailability, with no private error detail.

**Unfinished:** admin API and RBAC, vault adapter, quotas, circuit operations, PostgreSQL actual rehearsal, consumer identity/tenant authority and live-provider homologation. A service key authenticates the caller, but caller-to-tenant authorization needs its own approved control before production deployment.

Production deploy, production DB migrations, and merging remain governed by AGENTS.md.
