# Evolution API v2.3.7 — FM Assistant contract baseline (internal)

Status: **CODE + SYNTHETIC CONTRACT FIXTURES; EXTERNAL COMPATIBILITY NOT VERIFIED**.
Family: `evolution_v2_whatsapp_baileys`. Version candidate pinned:
`v2.3.7` (release tag from evolution-foundation/evolution-api). Do **not**
substitute Evolution Go or any `2.4.0-rc*` release.

## FM-managed integration endpoints

- `POST /instance/create` — individual Baileys instance identifier; redact returned credential.
- `POST /webhook/set/{instance}` — HTTPS per-instance target, `MESSAGES_UPSERT`
  and `CONNECTION_UPDATE` only, FM-generated encrypted credential via custom header.
- `GET /instance/connect/{instance}` — PNG QR payload; no assumption of TTL from FM.
- `GET /instance/connectionState/{instance}` — allow `open|close|connecting` only.
- `POST /message/sendText/{instance}` — one attempt with individual token; no blind retry.
- `DELETE /instance/logout/{instance}` — confirm provider success before token revocation.

Provider webhook **origin proof** uses possession of a unique FM-issued source
credential inserted into outgoing headers; the provider does not sign each
payload with an independently verifiable native signature under this contract.
The FM ingress validates that source credential first and then signs the raw
payload for the separate internal broker. Provider global webhook MUST NOT be
used without equivalent security controls. The signed internal ingress MUST
NOT be exposed on the public edge.

## Release compatibility gates

1. Match deployed provider image digest/tag to approved specific version and
   verify actual API request/response schemas, including nested webhook response.
2. Validate TLS, network-origin controls, refusal of unsigned and malformed
   events, and prevention of leakage through proxy access logs.
3. Run real test-instance lifecycle provisioning, QR reading, state changes,
   message delivery, logout, and reconnection ONLY after full software construction.
4. Run PostgreSQL distributed concurrency/chaos load tests, timeouts and
   recovery with isolated credentials and controlled loss injection.
5. Require formal approval prior to release promotion.

None of these **external** gates is reported as passed by offline CI.
No token, live WhatsApp phone, production migration, merge or deploy performed.

Reference URLs:
- https://github.com/evolution-foundation/evolution-api/releases
- https://github.com/evolution-foundation/docs-evolution/pull/22
- https://docs.evoapicloud.com/api-reference/webhook/set
