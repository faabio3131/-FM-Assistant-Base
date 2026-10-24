# VendeAtendeIA — WhatsApp QR FM-managed onboarding (construction)

Status: **INTERNAL IMPLEMENTATION / CI PENDING**. This is the new SaaS horizontal WhatsApp onboarding, not a modification of Kordena and not a resumption/promotion of F3. Meta Cloud API remains a separate official channel.

## Architecture
- Existing `Integration & Credential Control Plane` remains canonical; `whatsapp_evolution` is an additional provider in its catalogue, with `connection_id` and opaque random instance identifier, tenant/unit scope, audit records, immutable revision and FM-controlled encrypted secrets.
- `EvolutionClient` isolates the provider's API behind strictly configured HTTPS origin and a distinct FM global key. No browser receives that key or the instance token. No arbitrary tenant URL is accepted.
- `EvolutionOnboarding.provision` creates a draft tenant-bound integration first, then makes **one** external provisioning attempt, then encrypts and stores the individual instance token in the existing Vault. A failed/ambiguous remote response keeps the draft and blocks blind repeat. PostgreSQL first-instance creation is serialized across workers with a transaction-level advisory lock.
- `POST /v1/channels/whatsapp/qr/provision` requires existing `integration.manage` authority; `GET /v1/channels/whatsapp/qr/{connection_id}` requires `integration.read`, verifies tenant/unit ownership and returns a bounded PNG QR data URL with `Cache-Control: no-store`.
- `FM_ASSISTANT_EVOLUTION_ORIGIN` and `FM_ASSISTANT_EVOLUTION_GLOBAL_KEY` are both opt-in FM configuration. Missing one, insecure origin, weak/reused key or unsupported port cause startup rejection. When disabled, onboarding returns 503.
- Generic tenant-created `whatsapp_evolution` integrations and generic mutation/rotation/validation/disable/revoke paths are denied: the lifecycle remains in the specialized FM manager.

## Tests (synthetic, no real VPS)
- HTTPS and identity restrictions; global key does not leak to request body or responses.
- Provider fixture: instance creation and QR retrieval, malformed/oversized QR failure.
- API: unauthenticated/unauthorized and cross-tenant access, independent FM-managed credential, no-store response, one-instance rule and ambiguous remote failure no blind retry.
- GitHub workflow status must be checked on the latest code HEAD before claiming a green gate.

## Pending construction — do not call this customer-ready yet
1. **Pin an exact Evolution API edition/version** and certify its create/connect/state/webhook schemas with a local mock contract. Endpoint shapes and QR payloads change across releases; reject mismatched schemas.
2. Create an authenticated provider ingress gateway that proves event origin **before** parsing and routing a webhook. Use separate per-instance signed callbacks or trusted-proxy HMAC, replay protection, and payload limits. Never accept an unauthenticated `instance` field as tenant authority; never expose the FM master key on callbacks.
3. Persist inbound events and deduplicate by `connection_id + event_id` in a transaction; enqueue messages to the existing Assistant Conversation Engine, with safe retry/dead-letter policies. Reuse the shared provider-independent runtime; do not create a second AI brain.
4. Implement outbound messages, delivery reconciliation, remote disconnect/revoke/cleanup, QR expiration and refreshing, number-ownership verification and automatic status machine, including suspension when integration or license is revoked.
5. Integrate QR connection UI in the SaaS frontend (owner/manager with RBAC), accessible loading/connected/reconnect states, refresh and support instructions. No VPS details or individual tokens shown.
6. Complete concurrency/negative-security PostgreSQL E2E on isolated runtime, cost observability under FM Command and independent security review.
7. **After** 100% internal software construction, perform controlled real VPS/WhatsApp qualification and compare account/platform policy risk against Meta official Cloud API. This external homologation is deferred by project policy, never allowed to block internal building.

## Security and support notes
Evolution/Baileys-style connectivity may rely on nonofficial automation. This entails account/platform restriction and stability risk. Do not promise access is guaranteed; keep the official Meta Cloud API alternative. FM pays infrastructure and AI/provider costs, plans limit usage/franchises rather than feature availability.


## FM Corporate QR display policy — 2026-10-19
- Approved default **45 seconds**, set by FM Command corporate admin, no customer override. This is a **visual cap**, not an assertion of actual WhatsApp/Evolution token validity. Effective cap must be the minimum of FM display seconds and remaining provider seconds where reliable metadata exists.
- Current Assistant onboarding UI enforces 45s from first receipt of a QR image; polls every 8s, hides an unchanged code after 45s and does not display the same expired image as newly valid. A changed QR image starts a fresh display window.
- Command owns the versioned persistent policy. Candidate internal construction now includes the signed Command→Assistant projection endpoint, a monotonic PostgreSQL read model, and QR panel consumption of the approved revision; the 45-second fallback is used until a published revision is received. This has **not** been deployed or externally homologated. An authenticated manual Command sync remains opt-in/OFF by default; never confuse the visual cap with actual provider TTL. No provider expiration contract has been pinned; external real homologation follows software construction.


## C04 / F3 incremental — política QR corporativa autenticada (2026-10-20)
- New Assistant endpoint `POST /internal/v1/command/whatsapp-qr/policy` with exact HMAC-signed body/nonce/key ID/timestamp/issuer and separate path domain, not public tenant mutation.
- `CommandQrDisplayPolicyService` stores a monotonic `revision`, FM approval actor/time and display window 15–120s in `assistant_whatsapp_qr_display_policy` (Alembic aditiva `20261020_0017`). Reuses the global Command nonce table as replay barrier. Stale/reordered/conflicting requests fail closed; retransmission of identical revision is idempotent.
- Read model is included in the existing authorized `GET /v1/channels/whatsapp/qr/current`. UI dynamically updates the countdown **without resetting** the first-received timestamp of an unchanged image. Default 45 seconds remains when no signed policy is present; never assume Evolution QR token validity.
- Command twin candidate is `feat/c04-command-assistant-signed-qr-policy-20261020` in `faabio3131/FM-CONTROL-CENTER`, opt-in `FM_COMMAND_VENDE_QR_POLICY_SYNC_ENABLED`, with FM reauthentication and audit. No unauthenticated customer update, bypass of FM authority or real sender activation.
- Internal tests cover nonce replay, HMAC path isolation, source/org/product spoofing, wrong revisions, 15/120 boundaries and UI behaviour. **Check HEAD CI before calling certified.** F3 globally remains incomplete; external provider/WhatsApp/VPS homologation postponed.
