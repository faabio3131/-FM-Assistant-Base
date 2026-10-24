# F2 — Current Discovery e Plano de Implementação
## Integration & Credential Control Plane

**Data:** 2026-10-18
**Status:** GREEN — CERTIFICADO
**Baseline:** F1 GREEN 100%

## CURRENT no início da F2

WhatsApp V1 possui:

- configuração tenant/unit-scoped;
- `assistant_whatsapp_channels`;
- access token, app secret e verify token cifrados separadamente com Fernet;
- chave mestra externa ao banco;
- channel_id opaco;
- HMAC de webhook;
- idempotência;
- áudio;
- handoff;
- no blind retry;
- reconcile_required.

Limitação arquitetural:

A configuração é específica do WhatsApp. Cada nova integração exigiria schema/repository/API
próprios se esse padrão fosse repetido.

## TARGET aprovado para F2

Criar fabric universal:

- provider catalog;
- integration connection;
- lifecycle;
- capability bindings;
- validation results;
- connection events;
- credential secret versions;
- source FM-managed / tenant-managed;
- vault backend;
- rotação;
- revogação;
- expiração;
- non-disclosure.

Lifecycle aprovado:

```text
DRAFT → VALIDATING → ACTIVE → DEGRADED → DISABLED → REVOKED
```

## Provider inicial

`whatsapp_meta`

Config não secreta:

- phone_number_id;
- business_account_id;
- graph_api_version.

Secrets:

- access_token;
- app_secret;
- verify_token.

Capabilities:

- whatsapp.messaging;
- whatsapp.webhook;
- whatsapp.audio.

## Estratégia de migration

Migration 0004 será aditiva.

As tabelas antigas do WhatsApp não serão removidas.

Para canais existentes:

- connection_id = channel_id existente;
- status ACTIVE/DISABLED preservado;
- config não secreta copiada para config_json;
- ciphertexts existentes serão copiados diretamente para secret versions;
- nenhuma descriptografia/recriptografia será necessária na migration;
- capabilities serão registradas;
- evento de migration será criado.

Depois da F2, o `WhatsAppChannelRepository` passa a resolver dados pelo fabric universal.

## Compatibilidade

Os endpoints `/v1/channels/whatsapp` permanecem como facade compatível.

Configuração feita por essa facade entra no mesmo Integration Control Plane, sem criar
segunda autoridade.

A API universal nova será a rota preferencial para frontend/onboarding futuro.

## Validação

A API universal terá:

- connect;
- validate;
- activate;
- rotate;
- disable;
- revoke;
- list/catalog.

WhatsApp remote validation consultará Meta Graph usando timeout e erros sanitizados.

A facade legada preserva o comportamento certificado e ativa após validação estrutural
local para não quebrar integrações existentes; o fluxo comercial novo usa validate+activate.

## Vault

V1 usa `db_encrypted` com Fernet e master key externa ao banco.

Schema já prevê:

- secret source;
- storage backend;
- secret reference futuro;
- ciphertext;
- version;
- active;
- expiration;
- revoke timestamp.

Nenhuma API de leitura retorna valor secreto.

## Gate F2

- tenant isolation;
- connect;
- remote validate;
- activate;
- rotate;
- disable;
- revoke;
- secret versioning;
- secret non-disclosure;
- migration/backfill;
- WhatsApp regression;
- HMAC/idempotency/audio/no-blind-retry/reconcile preserved;
- secret scan;
- Ruff;
- pip check;
- pytest;
- GitHub Actions GREEN.

## Certificação final F2

**SHA técnico certificado:** `54d1ea67182fd12a182bde1a903ecbc92e0f467d`

Evidência local específica:

- secret scan: PASS;
- `pip check`: PASS;
- Ruff: PASS;
- `git diff --check`: PASS após cleanup;
- control plane/lifecycle: 5/5 PASS;
- revoked-state regression: PASS;
- migration 0004 + regressão WhatsApp: 6/6 PASS.

Evidência remota integral:

- push workflow `39095136709`: SUCCESS;
- pull_request workflow `39095139131`: SUCCESS;
- Install: GREEN;
- Pip check: GREEN;
- Ruff: GREEN;
- `pytest tests/saas`: GREEN.

Falha encontrada e corrigida durante o gate:

- `revoke` marcava `revoked_at` somente na versão ativa;
- corrigido para formalizar revogação em todas as versões ainda não revogadas;
- teste de regressão adicionado.

**Resultado:** F2 = GREEN 100%.
