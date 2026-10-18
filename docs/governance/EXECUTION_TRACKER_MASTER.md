# EXECUTION TRACKER MASTER — FM Assistant + Sales AI V1

**Data de criação:** 2026-10-17  
**Autoridade operacional:** AGENTS.md + Prompt Mestre  
**Regra:** somente uma fase pode ser considerada fechada quando seu gate estiver GREEN 100%.

## Estados

- NOT_STARTED
- IN_PROGRESS
- RED
- BLOCKED_EXTERNAL
- GREEN

---

## Baseline

- Assistant PR: #1 Draft
- Assistant branch: `feat/saas-foundation-v1`
- Assistant HEAD documental na criação deste tracker: `823ad9e385ae5edf156df07c3561a335b12a0bd4`
- Core PR: #1 Draft
- Core branch: `feat/ai-service-v1`
- Core HEAD documental na criação deste tracker: `41617b70e2126c8a2d76e7325e68541c7d045a07`
- Kordena: read-only

---

## F0 — Reconciliação institucional

**Status:** GREEN

### Concluído

- [x] Auditoria de conformidade criada.
- [x] System Design Mestre criado.
- [x] ADR-001 a ADR-006 criados.
- [x] Prompt Mestre criado.
- [x] SAAS_ARCHITECTURE reconciliado com CURRENT.
- [x] WHATSAPP_CHANNEL reconciliado com CURRENT.
- [x] CORE_INTEGRATION reconciliado.
- [x] AI_SERVICE do Core reconciliado.
- [x] README Assistant atualizado.
- [x] README Core atualizado.
- [x] Projetos registrados em `C:\Nova-FM-Tecnologia\04-Projetos`.
- [x] seis decisões registradas no ledger institucional.
- [x] diff comprovou alterações documentais, sem código funcional desde os últimos SHAs certificados.

### Gate final

- [x] Assistant CI remoto verde.
- [x] Core CI remoto verde.
- [x] F0 encerrada com evidência antes da promoção de F1.

---

## F1 — Identity / RBAC / Tenant / License Control Plane

**Status:** GREEN

## F2 — Integration & Credential Control Plane

**Status:** GREEN

## F3 — FM Core Production Control Plane

**Status:** IN_PROGRESS

## F4 — Knowledge & Retrieval

**Status:** NOT_STARTED

## F5 — Human Inbox

**Status:** NOT_STARTED

## F6 — Sales / CRM Pack

**Status:** NOT_STARTED

## F7 — Follow-up / Cadences / Agenda

**Status:** NOT_STARTED

## F8 — Frontend Web Comercial

**Status:** NOT_STARTED

## F9 — Billing / Plans / Quotas / Usage

**Status:** NOT_STARTED

## F10 — Observability / SRE

**Status:** NOT_STARTED

## F11 — Security Hardening

**Status:** NOT_STARTED

## F12 — Backup / Restore / Incidents

**Status:** NOT_STARTED

## F13 — Staging / Homologação

**Status:** NOT_STARTED

## F14 — Final Commercial Readiness

**Status:** NOT_STARTED

## F15 — Merge / Production

**Status:** NOT_STARTED

### Regra atualizada de autorização

- Merge: pré-autorizado quando todos os gates aplicáveis estiverem GREEN 100%.
- Deploy/produção: bloqueado até autorização humana explícita.

---

## Registro de execução

Adicionar entradas sem apagar histórico.

Formato:

```text
YYYY-MM-DD HH:MM
FASE:
HEAD:
AÇÃO:
EVIDÊNCIA:
RESULTADO:
GATE:
PRÓXIMO PASSO:
```


2026-10-17 22:50-23:00 BRT
FASE: F0
HEAD ASSISTANT: 016656d7498c91601aca1e310af17136663fbc28
HEAD CORE: bd6a93e64a92f327a576aa72c578d90378e294e5
AÇÃO:
- criado AGENTS.md na raiz do FM Assistant Base;
- criado AGENTS.md na raiz do FM Core Base;
- criado Execution Tracker canônico;
- Prompt Mestre atualizado para correção autônoma e merge pré-autorizado com 100% GREEN;
- decisão institucional registrada em C:\Nova-FM-Tecnologia\.fm\APPROVED_DECISIONS.md.
EVIDÊNCIA:
- Assistant workflow runs mais recentes no HEAD atual: 39089172739 / 39089175534;
- Core workflow runs mais recentes no HEAD atual: 39089190930 / 39089193385.
RESULTADO:
- jobs remotos continuam sem validação verde;
- F0 permanece BLOCKED_EXTERNAL até CI obrigatório executar e passar.
GATE: BLOCKED_EXTERNAL
PRÓXIMO PASSO:
- restabelecer capacidade do GitHub Actions/Billing;
- rerodar CI nos HEADs atuais;
- se 100% GREEN, marcar F0 GREEN e avançar automaticamente para F1.


2026-10-17 23:00+ BRT
FASE: F0 / preparação permitida de F1
HEAD ASSISTANT: 34f8b71017598cad7510cbed2518d23535277896
AÇÃO:
- gate F0 revalidado;
- GitHub Actions continua impedido de iniciar por Billing/Plans;
- executado Current Discovery preparatório de F1;
- criado docs/governance/F1_CURRENT_DISCOVERY_AND_IMPLEMENTATION_PLAN.md;
- identificada contradição CURRENT: production ainda aceita openai_compatible direto;
- planejada correção para enforcement do ADR-002 quando F1 for liberada;
- planejado schema Identity/RBAC/Tenant/License sem destruir estruturas existentes.
EVIDÊNCIA:
- workflow Assistant 39089221034: job não iniciado por Billing/Plans;
- workflow Core 39089193385: job não iniciado por Billing/Plans;
- código atual verificado em api.py, security.py, db.py, repositories.py, domain.py, settings.py;
- migrations 0001/0002 e testes atuais inspecionados.
RESULTADO:
- F0 permanece BLOCKED_EXTERNAL;
- F1 permanece NOT_STARTED para promoção/implementação;
- preparação técnica de F1 concluída e pronta para execução após GREEN de F0.
GATE: BLOCKED_EXTERNAL
PRÓXIMO PASSO:
- corrigir/restabelecer GitHub Billing/Actions;
- rerodar CI nos HEADs atuais;
- se GREEN 100%, marcar F0 GREEN e iniciar F1.1 automaticamente.


2026-10-17 23:30+ BRT
FASE: F0
HEAD ASSISTANT VALIDADO: f2cadbd262ab88c4e8a9184f49d9c8b44756e1ef
AÇÃO:
- repositório FM Assistant Base alterado para público pelo proprietário;
- rerun do GitHub Actions executado;
- workflow 39089505677, attempt 2, executou de fato em runner público.
EVIDÊNCIA:
- checkout: GREEN;
- setup-python: GREEN;
- install: GREEN;
- Ruff: GREEN;
- Pytest: GREEN;
- job test concluído com SUCCESS em 19s.
RESULTADO:
- gate CI do Assistant = GREEN;
- FM Core Base continua privado;
- rerun do Core 39089193385 continua bloqueado por Billing/Plans;
- F0 geral permanece BLOCKED_EXTERNAL exclusivamente pelo CI obrigatório do Core.
GATE: BLOCKED_EXTERNAL
PRÓXIMO PASSO:
- tornar FM Core Base público ou regularizar Billing/Plans;
- rerodar AI Service CI do Core;
- se Core GREEN e nenhum outro gate pendente, marcar F0 GREEN e iniciar F1 automaticamente.


2026-10-17 23:35+ BRT
FASE: F0 -> F1
HEAD ASSISTANT VALIDADO F0: b5d0f4d3bd2a75357181c5d2945b16e787c16bf1
HEAD CORE VALIDADO F0: bd6a93e64a92f327a576aa72c578d90378e294e5
EVIDÊNCIA:
- Assistant workflow 39090563065: SUCCESS no HEAD b5d0f4d3...;
- Core workflow 39089193385 attempt 3: SUCCESS no HEAD bd6a93e...;
- Core steps: checkout/install/Ruff/AI service tests/complete job = SUCCESS.
RESULTADO:
- F0 = GREEN 100%;
- F1 promovida para IN_PROGRESS conforme AGENTS.md.
PRÓXIMO PASSO:
- F1.1 ADR de identidade/sessão;
- F1.2 contratos de domínio;
- F1.3 migration 0003;
- enforcement ADR-002 em runtime comercial.


2026-10-18 — F1 IMPLEMENTATION LOCAL GATE
FASE: F1
AÇÃO:
- ADR-007 Identity/Session/RBAC implementado;
- Identity/RBAC/Tenant/Unit/Session/Invitation/Recovery/License/Entitlement implementados;
- API credential separada de identidade humana;
- migration 0003 aditiva + backfill implementada;
- ADR-002 enforced: staging/production exigem FM Core;
- workflow reforçado com pip check + Ruff da migration.
EVIDÊNCIA LOCAL:
- secret scan: NO_SECRET_PATTERN_MATCHES;
- Ruff: PASS;
- pip check: PASS;
- git diff --check: PASS;
- identity/RBAC/recovery pós-correção: 10/10 PASS;
- suíte tests/saas final: 27/27 PASS;
- migration/backfill: PASS.
FALHA CORRIGIDA:
- patch de recovery inseriu PasswordResetORM em chamadas SQLAlchemy;
- cinco testes ficaram RED;
- causa raiz corrigida;
- subset e suíte integral rerodados verdes.
RESULTADO:
- implementação F1 local = GREEN;
- F1 geral permanece IN_PROGRESS até CI remoto validar o SHA do commit.
PRÓXIMO PASSO:
- commit/push;
- validar GitHub Actions;
- se GREEN 100%, fechar F1 e promover F2 automaticamente.


2026-10-18 — F1 FINAL REMOTE GATE
FASE: F1 -> F2
SHA F1: 678ea0c7d201af1c61ffcf5cc689b4b2eca8c6d1
EVIDÊNCIA REMOTA:
- GitHub Actions pull_request 39091973547: SUCCESS;
- GitHub Actions push 39091970851: SUCCESS;
- Install: GREEN;
- Pip check: GREEN;
- Ruff: GREEN;
- Pytest: GREEN.
EVIDÊNCIA LOCAL:
- secret scan: NO_SECRET_PATTERN_MATCHES;
- Ruff: PASS;
- pip check: PASS;
- git diff --check: PASS;
- pytest tests/saas: 27/27 PASS;
- migration 0003/backfill: PASS;
- security identity/RBAC/recovery: PASS.
RESULTADO:
- F1 = GREEN 100%;
- F2 promovida para IN_PROGRESS conforme AGENTS.md.
PRÓXIMO PASSO:
- executar Current Discovery do WhatsApp/segredos/configuração;
- desenhar e implementar Integration & Credential Control Plane universal;
- migrar WhatsApp preservando HMAC/idempotência/reconcile_required/no-blind-retry.

2026-10-18 — F2 IMPLEMENTATION LOCAL GATE
FASE: F2
BASELINE: e580ee3cc36f979d633c0618b329a025f01fa6bd
AÇÃO:
- Integration & Credential Control Plane universal implementado;
- provider catalog inicial whatsapp_meta;
- Credential Vault abstraction + db_encrypted/Fernet backend;
- lifecycle DRAFT/VALIDATING/ACTIVE/DEGRADED/DISABLED/REVOKED;
- connect/config/validate/activate/rotate/disable/revoke/list/catalog API;
- secret metadata sem disclosure de valor/ciphertext;
- secret versioning e revogação integral;
- migration 0004 aditiva com backfill do WhatsApp sem recriptografia;
- WhatsAppChannelRepository migrado para facade sobre Integration Fabric;
- inbound idempotency migrado para ledger universal;
- workflow atualizado para lintar migration 0004.
EVIDÊNCIA LOCAL:
- secret scan: NO_SECRET_PATTERN_MATCHES;
- pip check: PASS;
- Ruff: PASS;
- git diff --check: PASS após cleanup;
- Integration lifecycle/control plane: 5/5 PASS;
- revoked-state regression adicional: PASS;
- migration 0004 + WhatsApp regression: 6/6 PASS.
FALHA CORRIGIDA:
- revoke marcava revoked_at apenas na versão ativa;
- corrigido para revogar todas as versões ainda não formalmente revogadas.
RESULTADO:
- implementação F2 local específica = GREEN.
GATE: GREEN local / aguardava CI remoto integral.

2026-10-18 — F2 FINAL REMOTE GATE
FASE: F2 -> F3
SHA F2: 54d1ea67182fd12a182bde1a903ecbc92e0f467d
EVIDÊNCIA REMOTA:
- GitHub Actions push 39095136709: SUCCESS;
- GitHub Actions pull_request 39095139131: SUCCESS;
- Install: GREEN;
- Pip check: GREEN;
- Ruff: GREEN;
- Pytest tests/saas integral: GREEN.
RESULTADO:
- F2 = GREEN 100%;
- F3 promovida para IN_PROGRESS conforme AGENTS.md.
PRÓXIMO PASSO:
- executar Current Discovery do FM Core Production Control Plane;
- persistir catálogo/rotas/usage/FinOps;
- governar FM-managed/BYOK;
- provider health/circuit breaker/timeout;
- validar contratos Assistant ↔ Core;
- homologação real somente com credenciais/ambiente autorizados.


2026-10-18 — F3.1 A F3.4 EXECUCAO E CERTIFICACAO INTERMEDIARIA
FASE: F3 — FM Core Production Control Plane
CORE BRANCH: feat/ai-service-v1
CORE HEAD VALIDADO: 2f5300fb55e7885cc649b6f87ada4158e1de7681
ASSISTANT STATUS: F2 GREEN; F3 EM ANDAMENTO
ACOES:
- F3.1 catalogos persistentes de provider/model/capability, route policies platform/tenant/unit e provider-health;
- politica de escopo unit > tenant > platform, fail-closed para prioridade ambigua e health/circuit indisponiveis;
- somente referencias opacas de segredo FM-managed e BYOK, verificacao de isolamento BYOK;
- F3.2 runtime bridge ligado ao AIModelRouter existente, resolucao de rotas por request, sem segundo motor cognitivo;
- adapter FM-managed, porta BYOK governada (integracao real ainda pendente);
- redaction de API key no repr de ProviderRouteSettings;
- F3.3 catalogo de price snapshots imutaveis na API e ledger persistente de eventos de uso;
- estimativa de custo deterministica so com snapshot e tokens validos; custo desconhecido explicitamente registrado;
- read model FinOps tenant/unidade e deduplicacao por tentativa de request;
- F3.4 Alembic f3_0001 aditivo e downgrade reversivel em banco descartavel;
- falha Ruff por ordem de imports registrada e corrigida sem enfraquecer regras.
EVIDENCIA:
- commits Core: e2e0b012c304cd385d68e784d7af78f285620536;
  6fbfcef71e2a951ebc7d229877296bf025323e8d;
  3862d2946fa12010f97d5f166f63e54778564cfc;
  e7597edae32d3b389adb7576210b20de33ba7261;
  fix 2f5300fb55e7885cc649b6f87ada4158e1de7681.
- GitHub Actions Core push #39103858031 = SUCCESS;
- GitHub Actions Core pull_request #39103860464 = SUCCESS;
- Ruff, testes AI Router e testes service (inclusive Alembic upgrade/downgrade) = GREEN.
GATE: GREEN INTERMEDIARIO; F3 GLOBAL = IN_PROGRESS (NAO PROMOVER F4).
PENDENCIAS OBRIGATORIAS:
- ligar Control Plane e metering persistente ao startup comercial de forma governada;
- adapter do Credential Vault real compartilhado com Assistant e BYOK de tenant;
- separar e proteger API administrativa, CRUD com autorizacao canônica;
- pricing/usage quota hook, auditoria administrativa persistente, readiness e circuit breaker operacionais;
- migration/rollback e integridade comprovados em PostgreSQL descartavel;
- regressao ponta a ponta Assistant -> Core, observabilidade, varreduras e security gates completos;
- homologacao de provider real somente com credenciais/ambiente autorizados.
PROIBICOES: merge sem todos os gates; nenhum deploy/producao; Kordena read-only.
PROXIMO PASSO: seguir F3.5 a F3.n, corrigindo e retestando autonomamente, sem declarar F3 encerrada antecipadamente.
