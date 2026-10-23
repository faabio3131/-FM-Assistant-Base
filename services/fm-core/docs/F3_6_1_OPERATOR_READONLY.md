# F3.6.1 — Read-only Core operator endpoints

`/v1/admin/ai/providers/health`, `/v1/admin/ai/routes`, and
`/v1/admin/ai/usage` are **read-only** APIs protected by a dedicated
`X-Core-Admin-Key` header. The consumer `X-Core-Service-Key` cannot
authorize them. Admin key is disabled by default in dev/test.

The interface returns operational metadata and aggregated usage with known/
unknown costs, but never plaintext credentials, secret references, base URLs,
raw prompts, messages or conversation contents. No mutating admin endpoint
is exposed here.

This API is limited to a trusted technical operator. Possession of a static
key does **not** establish a human platform-admin identity and must never
authorize route, provider, model, policy, pricing or credential changes.
Human authority will be delegated from Command with authenticated and
audited identity before writable administration is enabled.

Production deploy remains blocked. Core F3 remains IN_PROGRESS.
