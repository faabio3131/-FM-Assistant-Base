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


2026-10-18 — AUTORIZACAO EXPlicITA DE MERGE RECONFIRMADA EM 2026-10-18
DECISAO DO PROPRIETARIO:
- o executor tem autorizacao para efetuar merge de PRs quando estiverem aptas para integracao.
INTERPRETACAO OPERACIONAL VINCULADA AO AGENTS.md:
- GitHub mergeable=true e condicao necessaria, mas nao suficiente;
- so efetuar merge quando a entrega/fase correspondente e TODOS os gates obrigatorios aplicaveis estiverem GREEN 100%: testes, seguranca, migrations, CI, revisao do diff, ausencia de STOP e tracker atualizado;
- PR em Draft nao deve ser mergeada sem passar por todos os criterios e promover para ready-for-review quando cabivel;
- em caso de RED, BLOCKED_EXTERNAL ou verificacao inconclusiva, nao fazer merge; corrigir e validar;
- apos merge, verificar CI pos-merge e registrar SHA;
- deploy/cutover/producao seguem dependendo de autorizacao humana explicita distinta.
EVIDENCIA DE ESTADO NA DATA:
- Assistant PR #1: mergeable=true, draft=true, merged=false;
- Core PR #1: mergeable=true, draft=true, merged=false;
- F3 permanece IN_PROGRESS, portanto estas PRs nao estao prontas para merge por governanca, embora GitHub indique mergeability tecnica.
RESULTADO: AUTORIZACAO CONFIRMADA, NENHUM MERGE EXECUTADO.


2026-10-18 — F3.5 PERSISTENT RUNTIME CERTIFICADO
FASE: F3 — IN_PROGRESS; apenas F3.5 = GREEN INTERMEDIÁRIO.
CORE BRANCH/HEAD: feat/ai-service-v1 / 8de891435c1c93ef23ac4d3bd46f7cbfe3f13d14
ACOES:
- Integração do Control Plane persistente ao bootstrap do Core, resolvendo rotas/segredos por requisicao sem duplicar AIModelRouter;
- produção/staging exigem PostgreSQL e Control Plane persistente, rejeitam rotas estáticas e chaves padrão;
- credenciais de serviço/admin distintas, min 32 caracteres em runtime comercial; secret repr sanitizado;
- metering usa PersistentAIFinOps na operação persistente;
- startup exige revisão Alembic f3_0001 preexistente, nunca migra banco automaticamente;
- readiness verifica conectividade, tabelas e versionamento; erro de dependência retorna 503 sem detalhes sensíveis;
- testes para bootstrap, schema ausente, uso/custo persistido e segredo indisponível;
- correção autônoma de falha inicial Ruff por imports/SIM117.
EVIDÊNCIA:
- implementation 4f38151c70b52272d6dd5db2b92d4a721818afe0;
- fix 8de891435c1c93ef23ac4d3bd46f7cbfe3f13d14;
- Core GitHub Actions push #39104485612 = SUCCESS;
- Core GitHub Actions pull_request #39104487912 = SUCCESS;
- Ruff PASS; pytest 49 PASS, 0 FAIL, 5 warnings (revisar).
GATE: F3.5 GREEN; F3 GLOBAL IN_PROGRESS; F4 NOT_STARTED.
PENDÊNCIAS: Admin API autenticada e auditada, controle de autoridade por tenant/consumidor, BYOK shared vault, quota/circuit breaker, testes PostgreSQL e integração Assistant, gates completos.
RESTRICOES: sem merge desta PR até critérios integrais aplicáveis; sem deploy, sem migration de produção; Kordena read-only.
PROXIMO PASSO: F3.6 administração governada e autorização diferenciada, com testes e CI.


2026-10-18 — F3.5 LAZY-CREDENTIAL CORRECTION
FASE: F3, melhoria de regressao pos-F3.5, F3 global ainda IN_PROGRESS.
CORE HEAD CERTIFICADO: 1243c41e0943bc61a35761040af4409be034d99c
AÇÃO:
- Credential resolver mudou de eager para lazy: segredo resolvido somente quando a rota é efetivamente tentada;
- evita negar sucesso da rota primária por falta de credencial de fallback;
- erro de segredo ausente tratado por codigo externo generico, sem referencia sensivel;
- Alembic path_separator atualizado para reduzir warnings de deprecacao;
- falhas intermediarias Ruff e contrato de erro foram corrigidas, sem suprimir testes.
EVIDENCIA:
- primeira mudança: c44b309845274465893a293fe1537d6733ae7738;
- lint fix: 6d8555f5fb76b6a9e46eaf819895817629631d4e;
- API contract fix: 1243c41e0943bc61a35761040af4409be034d99c;
- Core push #39104780301 = SUCCESS;
- Core PR #39104782604 = SUCCESS;
- 50 pytest PASS, 0 FAIL, 1 warning de dependencia externa;
- Ruff PASS.
GATE: correção de F3.5 GREEN, mantendo F3 = IN_PROGRESS.
PROXIMO PASSO: F3.6 admin API governada (autoridade de plataforma e auditoria), depois demais gates F3.
NAO: merge antes de F3/criterios completos, deploy, migration em producao.


2026-10-18 — F3.6.1 OPERATOR READONLY
FASE: F3 — EM ANDAMENTO. F3.6.1 = GREEN INTERMEDIARIO, NAO F3 COMPLETO.
CORE HEAD CERTIFICADO: 98694f0f788dc415d662cfc7ab4222103ceabf1f
ACOES:
- criadas APIs read-only /v1/admin/ai/providers/health, /v1/admin/ai/routes, /v1/admin/ai/usage;
- protecao obrigatoria com X-Core-Admin-Key distinta da X-Core-Service-Key dos consumidores;
- sem admin key, endpoints tecnicos ficam desabilitados; somente leitura, nenhum POST administrativo publicado;
- respostas nao divulgam secret_reference, api_key, base_url ou raw conversation;
- consultas FinOps exigem tenant/unit e mantem desconhecimento de custos;
- identidade humana platform_admin e mutation audit AINDA NAO IMPLEMENTADAS; proibido autorizar mutacoes apenas pela admin service key;
- Ruff corrigido com ajuste cirurgico de imports.
EVIDENCIAS:
- core commits ac876c63a100f2375aeb65232d4a093e99ba5da4, 98694f0f788dc415d662cfc7ab4222103ceabf1f;
- Core push CI #39105011331 SUCCESS;
- Core PR CI #39105014625 SUCCESS;
- Ruff GREEN, pytest 52 PASS, 0 FAIL, 1 warning de terceiro.
GATE: F3.6.1 GREEN; F3 GLOBAL IN_PROGRESS, F4 NOT_STARTED.
PROXIMO PASSO: F3.6.2 autenticacao/autorizacao de autoridade humana e auditoria append-only para mutacoes, F3.7 BYOK shared vault, quota/circuit, PostgreSQL integration e contract tests Assistant -> Core.
RESTRICOES: sem merge das PRs até gates e fase final aplicaveis verdes; sem deploy/migration de producao; Kordena read-only.


2026-10-18 — F3.6.2 SIGNED COMMAND AUTHORITY + TRANSACTIONAL AUDIT
FASE: F3 — IN_PROGRESS; somente verificador e ledger = GREEN INTERMEDIÁRIO.
CORE BRANCH: feat/ai-service-v1
CORE HEAD FUNCIONAL CERTIFICADO: ec95f02b38decffdaf06f6ebc7a8e7a77af5aa5f
AÇÕES:
- verificador de identidade humana delegada pelo Command com JWT RS256;
- audience/issuer/role/permission/scope/session/jti/step-up e TTL validados;
- negação uniforme para token falso, expirado, sem permissão, token técnico ou assinatura inválida;
- ledger de auditoria transacional core_ai_admin_mutation_audit, Alembic f3_0002;
- jti único, digest da requisição e rollback conjunto no caso de replay/falha;
- readiness passou a exigir f3_0002 e não executa migrations automaticamente;
- novos testes e CI atualizados.
EVIDÊNCIA:
- Core functional SHA ec95f02b38decffdaf06f6ebc7a8e7a77af5aa5f;
- GitHub Actions push 39128801541 SUCCESS;
- GitHub Actions PR 39128805551 SUCCESS;
- Ruff e testes AI service GREEN;
- documentação detalhada em docs/F3_6_2_COMMAND_HUMAN_AUTHORITY_AUDIT.md no Core.
LIMITES:
- NENHUMA API de mutação administrativa foi habilitada;
- nenhuma identidade real do Command ou credential produtiva foi conectada;
- faltam contrato de emissão/rotação/revogação, integração do Command, autorização de escrita, PostgreSQL, BYOK, quotas/circuit, regressão Assistant->Core e gates finais.
GATE: GREEN INTERMEDIÁRIO; F3 GLOBAL IN_PROGRESS; F4 NOT_STARTED.
PRÓXIMO PASSO: concluir F3.6.2 integrando autoridade real do Command e mutações com auditabilidade, após definição de contrato; continuar F3.7 BYOK/shared vault e demais gates F3.
RESTRIÇÕES: sem merge da PR enquanto F3 e todos os gates aplicáveis não estiverem 100% verdes; sem deploy ou migration real; Kordena read-only.


2026-10-18 — F3.7 BYOK TENANT GATEWAY PORT + ROUTING SECURITY
FASE: F3 — IN_PROGRESS; F3.7 CONTRATO/BOOTSTRAP = GREEN INTERMEDIÁRIO.
CORE FUNCIONAL HEAD: 5ee93dbe3d43baf7503ccc211ecf6b8989e4f176
ACOES:
- CoreCredentialResolver com porta TenantCredentialGateway explícita, sem dependência vertical ou acesso direto ao banco Assistant;
- GovernedCredentialResolver separa FM-managed de tenant-managed, rejeitando origem ambígua;
- validação estrita de integration:<tenant_id>:<opaque_id>;
- BYOK negado/revogado falha definitivamente no roteador e NÃO troca para rota FM-managed;
- bootstrap Core aceita injeção controlada de gateway, mas BYOK continua desabilitado por padrão;
- testes de cross-tenant, referência falsa, segredo revogado, bloqueio do FM fallback e bootstrap.
EVIDENCIA REMOTA:
- Core GitHub Actions push 39132968727 SUCCESS;
- Core GitHub Actions pull_request 39132973708 SUCCESS;
- Ruff e AI service tests PASS;
- documentação Core docs/F3_7_BYOK_GATEWAY_BOUNDARY.md.
GATE:
- F3.7 port e política de fallback: GREEN INTERMEDIÁRIO;
- F3.7 integração real Assistant/Core: PENDENTE;
- F3 GLOBAL: IN_PROGRESS; F4 NOT_STARTED.
PENDENCIAS:
- gateway real com identidade serviço autorizada e contrato de secret resolution tenant/unit/capability/entitlement;
- rotação, revogação, concurrency, security audit, E2E, Vault real;
- F3 demais gates: Command real, gestão admin, quotas/circuit, PostgreSQL, provider homologation.
RESTRICOES:
- merge somente após 100% gates aplicáveis da entrega/fase;
- deploy/segredos reais/migrations de produção exigem autorização humana;
- Kordena read-only.


2026-10-18 — F3.7 ASSISTANT INTERNAL BYOK ELIGIBILITY
FASE: F3 IN_PROGRESS; elegibilidade local de credenciais BYOK = GREEN INTERMEDIÁRIO.
ASSISTANT FUNCTIONAL HEAD: 7cfa15452be7fbf3cd4333b40420071d6cd90aa8
ACOES:
- política CoreBYOKReleasePolicy, somente leitura e decisão bool, sem decifrar ou expor segredos;
- validação cumulativa tenant/unidade/assinatura/trial/entitlement ai.byok/provider ai/capability/connection ACTIVE/secret ativo e vigente;
- cobertura de cross-tenant e cross-unit, integracao draft/revogada, origem FM, credencial revogada ou expirada, licença e trial expirados;
- documentação de riscos e fronteira em docs/governance/F3_7_ASSISTANT_BYOK_RELEASE_POLICY.md.
EVIDENCIA REMOTA DO HEAD FUNCIONAL:
- Assistant Actions push 39133544960 SUCCESS;
- Assistant Actions PR 39133548475 SUCCESS;
- Ruff e suíte SaaS integral GREEN.
GATE:
- política interna de elegibilidade: GREEN INTERMEDIÁRIO;
- serviço de entrega de segredo Core↔Assistant: NÃO IMPLEMENTADO / NÃO HOMOLOGADO;
- F3 global: IN_PROGRESS; F4 NOT_STARTED.
PENDENCIAS:
- identidade do serviço Core e vinculação autoritativa tenant/unit/capability;
- entrega de segredo limitada a conexão autorizada, com replay/expiry/revoke/concurrency;
- Integration Catalog AI providers, Vault externo, BYOK real e E2E em PostgreSQL;
- gates finais F3 restantes.
MERGE: NÃO PERMITIDO ENQUANTO F3/GATES OBRIGATORIOS NAO ESTIVEREM 100% GREEN.
DEPLOY/SEGREDOS REAIS/MIGRATION PRODUCAO: EXIGEM AUTORIZAÇÃO HUMANA.
KORDENA: READ-ONLY.


2026-10-18 — F3.7.2 AUTHENTICATED CORE ↔ ASSISTANT BRIDGE
FASE: F3 IN_PROGRESS; BRIDGE CONTRATO E E2E SINTÉTICO = GREEN INTERMEDIÁRIO.
HEAD FUNCIONAL ASSISTANT: 21406566f71f31e903e13348d526b5d1c34973f1
HEAD CORE FUNCIONAL: da05ca3e736197069ac87695e2859671fca142e0
AÇÕES:
- identidade plataforma Core com key_id ativo/revogável persistido no Assistant;
- grants exatos por tenant/unidade/capability;
- HMAC-SHA256 por corpo bruto, TTL 60s, nonce criptográfico único e anti-replay de banco;
- migration Assistant 20261018_0005 aditiva, sem criar credencial/identidade real;
- transação conjunta para autorização + auditoria de nonce e leitura de versão do segredo;
- HTTPS obrigatório no cliente Core, timeout limitado, sem redirect/retry e sem fallback FM em BYOK negado;
- Core passa unidade+capability à resolução autenticada;
- configuração opt-in via secret manager, desabilitada por padrão.
EVIDÊNCIAS:
- Assistant Actions push 39135485241 SUCCESS, PR 39135488843 SUCCESS (schema/tests);
- Assistant Core-Bridge Contract push 39135485263 SUCCESS, PR 39135488877 SUCCESS (E2E);
- Core Actions push 39135214051 SUCCESS, PR 39135217217 SUCCESS (contrato cliente);
- documentação: docs/governance/F3_7_2_CORE_ASSISTANT_SIGNED_BRIDGE.md;
- Core documentação: docs/F3_7_2_CORE_ASSISTANT_BRIDGE_CLIENT.md;
- testes de HMAC real Core→Assistant, cross-tenant/unit/capability, grant revogado, nonce replay,
  identidade revogada, rotação, audit, migration additive.
GATE: implementação de bridge sintética GREEN INTERMEDIÁRIO;
F3 GLOBAL: IN_PROGRESS; F4 NOT_STARTED; sem merge global.
PENDÊNCIAS OBRIGATÓRIAS:
- provisionamento governado de identidades/grants pelo Command;
- infraestrutura de rede privada, TLS/ACL/rate limit e segredos de serviço reais;
- integração de AI providers tenant-scoped e Vault externo;
- testes PostgreSQL reais para locking/revoke/nonce sob concorrência;
- incident response, observabilidade, security gate e homologação de provider/credenciais.
PROIBIÇÕES:
- não executar migrations no banco real, deploy/cutover ou ativar credencial real sem autorização humana;
- não alterar Kordena; não tratar simulação E2E como homologação produtiva.


2026-10-18 — F3.7.3 COMMAND-GOVERNED CORE SERVICE IDENTITIES
STATUS: F3 IN_PROGRESS; IMPLEMENTAÇÃO/TESTES SINTÉTICOS ASSISTANT GREEN INTERMEDIÁRIO; COMMAND CI BLOCKED_EXTERNAL.
CÓDIGO E FONTES:
- Command corporativo verdadeiro: faabio3131/FM-CONTROL-CENTER, branch feat/f3-command-core-bridge-governance, PR #90 Draft;
- Assistant: src/fm_assistant/command_bridge_control_service.py, API interna governada, ORM audit;
- Assistant migration aditiva 20261018_0006, sem provisionamento automático.
FEATURES:
- Command exige Better Auth da organização corporativa FM + owner/admin + password step-up matching human;
- Command assina HMAC exclusivo S2S ao Assistant; actor e target core ID são server-side e não input cliente;
- Assistant verifica organização, step-up recente, HMAC, TTL, nonce, identidade alvo exata;
- ações provision/grant/revoke_grant/revoke_identity com isolamento tenant/unit/capability;
- auditoria append-only única/transactional e revogação irreversível de identity/grant; sem chaves reais;
- segredos de Command, Core e Vault não podem ser reutilizados.
TESTES:
- Assistant CI SaaS + bridge E2E verde no SHA funcional a2c312f4b37a73b54c82a78b7982e1fd6219fec2;
- HMAC interlinguagem Node/Python test vector, forged key, old step-up, cross-org, replay, revoke e provision;
- Command tests: tests/f3-command-core-bridge-*.
BLOCKER EXTERNO:
- Command PR #90 GitHub Actions FMCC Foundation Gate/F21 Operational Readiness encerram sem steps, sem executar lint/typecheck/test/build. NÃO contar como GREEN nem realizar merge.
PENDENTE:
- CI Command efetivamente executado, revisão independente de segurança, Node Command→Assistant E2E;
- PostgreSQL real concurrency/revocation, secret manager, TLS/ACL, runbook rotation;
- autorização específica para deploy/migration/segredos reais.
STATUS GLOBAL: F3 IN_PROGRESS, F4 NOT_STARTED.
MERGE: BLOQUEADO POR CI COMMAND NÃO VERDE E DEMAIS GATES.
KORDENA: READ-ONLY. NENHUM DEPLOY REAL.

2026-10-18 — F3.7.4 POSTGRESQL CONCURRENCY / REVOKE / REPLAY GATE
FASE: F3 IN_PROGRESS; F3.7.4 = GREEN INTERMEDIÁRIO. F4 NOT_STARTED.
ASSISTANT HEAD FUNCIONAL: 6dd2d9f7ebf84fa140ae7380f6f0386387500ca9
AÇÕES:
- adicionado workflow .github/workflows/f3-postgres-core-bridge.yml com PostgreSQL 16 descartável;
- migrations Alembic executadas em banco de teste, não em produção;
- testes reais com duas requisições simultâneas mesmo nonce (1 liberada sintética, 1 negada);
- revogação do grant e da identidade pela autoridade Command com verificação da negativa subsequente;
- audit e constraints reais no banco; sem acesso a segredos reais;
- corrigido o fixture PostgreSQL preservando FK fortes e request ID UUID no formato do Command.
EVIDÊNCIA:
- F3 PG CI push 39139495756 SUCCESS; PR 39139500097 SUCCESS;
- SaaS Foundation CI push 39139495725 SUCCESS; PR 39139500051 SUCCESS;
- Core Assistant Contract push 39139495839 SUCCESS; PR 39139500205 SUCCESS;
- doc docs/governance/F3_7_4_POSTGRES_REPLAY_REVOCATION_CERTIFICATION.md.
HISTÓRICO RED:
- regressões de fixture captadas pelo Postgres antes de promover; correções por ordem FK e UUID;
- não confundir reexecução verde com ocultação da falha anterior.
BLOCKERS:
- FM Command corporativo PR #90 (FM-CONTROL-CENTER) CI não executou jobs/steps: BLOCKED_EXTERNAL / NOT_TESTED;
- E2E Command real→Assistant, segurança independente, Vault externo, TLS/ACL/mTLS/rate limits, provider/quotas/circuit/homologação.
GATE: F3.7.4 GREEN INTERMEDIÁRIO, F3 GLOBAL IN_PROGRESS.
MERGE: proibido enquanto gates inter-repositórios obrigatórios não estiverem todos GREEN 100%.
DEPLOY/SEGREDOS REAIS/MIGRATION PRODUTIVA: sem autorização; não executados.
KORDENA READ-ONLY; MCP Commander não usado.

2026-10-18 — F3.7.4 REGRESSION HARDENING / FINAL RETEST
FASE: F3 IN_PROGRESS; PostgreSQL gate GREEN INTERMEDIÁRIO (mantido).
ASSISTANT SHA FUNCIONAL: 45b35a6900c59825a987d9db47e98ad18073dec2
FALHA NOVA NO HEAD DOCUMENTAL ANTERIOR:
- run SaaS Foundation CI 39139738788 encontrou teste de replay intermitente: command_request_id de fixture SQLite tinha formato aleatório capaz de começar com _ ou -, mas o contrato exige primeiro caractere alfanumérico;
- a falha foi real na suíte, não no Postgres. Nenhum teste foi desabilitado/afrouxado.
CORREÇÃO:
- tests/saas/test_core_bridge_service.py utiliza UUID, como o FM Command corporativo;
- nenhum contrato de produção, segredo, banco ou regra de autorização foi alterado.
EVIDÊNCIA NO NOVO HEAD FUNCIONAL:
- Assistant SaaS CI push 39139876188 SUCCESS / PR 39139880261 SUCCESS;
- F3 PostgreSQL 16 gate push 39139876172 SUCCESS / PR 39139880254 SUCCESS;
- Core Assistant Contract push 39139876135 SUCCESS / PR 39139880264 SUCCESS;
- 6/6 workflows SUCCESS, todos no SHA 45b35a6900c59825a987d9db47e98ad18073dec2.
GATES REMANESCENTES:
- CI Command PR #90, efetivo lint/typecheck/test/build, continua BLOCKED_EXTERNAL (jobs sem steps);
- E2E Node Command→Python Assistant, security review independente, TLS/ACL/rate limits, Vault externo, providers, quotas/circuit/FinOps, homologações.
RESULTADO: F3.7.4 GREEN INTERMEDIÁRIO; F3 GLOBAL IN_PROGRESS; F4 NOT_STARTED.
PROIBIÇÕES: sem merge prematuro, segredo real, banco/deploy produtivo ou escrita Kordena.


2026-10-18 — F3.7.5 COMMAND NEGATIVE AUDIT + NODE/PYTHON CROSS-RUNTIME GATE
FASE: F3 = IN_PROGRESS; F4 NOT_STARTED; Command gate = NOT_TESTED/BLOCKED_EXTERNAL.
REPOSITÓRIOS:
- Command corporativo faabio3131/FM-CONTROL-CENTER PR #90 Draft na branch feat/f3-command-core-bridge-governance;
- Assistant faabio3131/-FM-Assistant-Base PR #1 Draft; Core PR #1 Draft;
- fm-command-v2 não é o controlador corporativo; Kordena read-only.
ALTERAÇÕES NO COMMAND:
- audit de negativas corporativas e payload inválido: commits ff150ef3 e 021cdef1;
- cliente REAL Node assina envelope, entregue ao FastAPI ASGI REAL do Assistant com fixture sintética: teste tests/f3_command_assistant_cross_runtime.py no Command e helper .mts (commits c5790c9,1693a93);
- Command Foundation workflow estendido para checkout Assistant público PINNED no SHA funcional 45b35a6900c59825a987d9db47e98ad18073dec2, rodar Python 3.12+pytest após suite Node (commit 0451681);
- docs e AGENTS do Command atualizados; nenhum segredo/credencial real criado.
ESCOPO DA PROVA PROPOSTA:
- autoridade/escopo assinado, provision, grant, anti-replay, Core release, revoke_grant, revoke_identity e auditoria;
- usa transporte capturado antes da rede e FastAPI TestClient: NÃO comprova HTTPS real, TLS, ACL, Vault, provider nem produção.
EVIDÊNCIA CI:
- Command SHA funcional 045168112162902111972c7bda819e436a5e7e69:
  Foundation 39141682746, F21 39141682831, Cognitive 39141682750 concluíram FAIL sem steps;
- re-run Foundation anterior 39139780483 (attempt 2) também falhou sem steps;
- nenhuma execução do novo teste Python/Node foi confirmada; status NOT_TESTED / BLOCKED_EXTERNAL.
RISCO TÉCNICO A FECHAR:
- mutation pode persistir no Assistant antes da tentativa de auditoria Command; documentar reconciliação segura por command_request_id sem retry cego;
- revisão independente, CI real, Vault, rede, quotas/circuit/FinOps, observabilidade e providers ainda pendentes.
DECISÃO: NÃO mergear PR #90 ou PRs #1; não iniciar F4, não fazer deploy/credential real/migration produtiva.
PRÓXIMO PASSO: obter CI Command executando steps e corrigir até 100% GREEN; passar teste cruzado e revisão independente; concluir gates restantes da F3 antes da promoção.


2026-10-18 — F3.7.6 COMMAND PRE-MUTATION AUDIT INTENT
FASE: F3 IN_PROGRESS; F4 NOT_STARTED.
ACHADO: o Command emitia request_id somente dentro do cliente S2S e registrava auditoria depois da mutation; em falha do audit writer, o Assistant poderia ter confirmado sem referência durável no Command.
CORREÇÃO EM BRANCH COMMAND PR #90:
- Command persiste previamente evento .requested no ledger corporativo; se falhar, NÃO envia mutation.
- UUID produzido server-side e persistido é encaminhado ao Assistant como command_request_id coberto pelo HMAC, e também registrado em sucesso/falha no Command.
- Testes de falha do audit-intent, resultado posterior ambíguo, validação de request_id e mesmo UUID em corpo/audit.
- Commits Command: efa3f349 (client), 35210452 (route), ea5ca271 e 5823b3d (tests), 0ba4ac7 (docs), af21aecc (AGENTS).
LIMITES: implementado, NÃO certificado porque GitHub Actions Command segue sem executar steps. O mecanismo de consulta/reconciliação read-only de status e prova no Assistant permanece pendente; não é transação distribuída.
GATE: NOT_TESTED / BLOCKED_EXTERNAL Command; Assistant/Core próprios CIs continuaram GREEN no checkpoint anterior, mas não substituem o Command.
MERGE: NÃO. DEPLOY/PROD/MIGRATION REAL: NÃO. Kordena read-only.
PRÓXIMO PASSO: desbloquear CI Command, executar suites completas inclusive cross-runtime e auditoria; corrigir falhas; implementar e certificar reconciliação segura sem reenvio automático.


2026-10-18 — F3.7.7 SIGNED RECONCILIATION CHECKPOINT
FASE: F3 IN_PROGRESS, F4 NOT_STARTED; nenhuma PR mergeada.
IMPLEMENTADO NO ASSISTANT:
- Migration aditiva 20261018_0007: unique index em assistant_command_bridge_control_events.command_request_id; rollback integral de uma mutation duplicada.
- Serviço/endpoint POST /internal/v1/command/core-bridge/status, HMAC com domínio separado da rota /manage, same actor/org/tenant/unit/capability/target e recent step-up.
- Consulta de resultado status applied + exact outcome / denied / unknown; nenhum secret retornado ou mutation executada; unknown nunca autoriza retry.
- Testes de unicidade, replay, HMAC path, cross-scope/actor, schema e integridade. Evidência Assistant SHA c65f05f73546380f1641611d96d6a3bd74c3a0b3: 6/6 CI SUCCESS (push+PR em SaaS, Postgres16 e bridge).
IMPLEMENTADO NO COMMAND PRIVADO (PR #90 Draft):
- cliente de consulta HMAC e rota de status com sessão Better Auth corporativa, owner/admin, step-up, consulta de intent do próprio ator no audit event; scope vem do intent e não do caller.
- unit tests para consulta e security, e Node signed status -> Assistant ASGI cross-runtime extendido; checkout Assistant c65f05f7 pinado.
- CI Command privado ainda finaliza antes de steps; novo código/testes = NOT_TESTED/BLOCKED_EXTERNAL e NÃO HOMOLOGADO.
BLOQUEIOS: corrigir account runner/billing/configuração GitHub Actions; executar CI integral real, revisão independente; Vault/TLS/ACL/rate limits/quotas/observabilidade/providers e homologações.
AÇÃO DO PROPRIETÁRIO QUANDO NECESSÁRIO: conferir GitHub Billing & licensing → Payment information e Budgets & alerts/erros de Actions; não compartilhar cartão/segredos; providenciar aprovação expressa antes de qualquer credencial real/deploy não descartável.
MERGE NÃO. DEPLOY NÃO. KORDENA READ-ONLY.


2026-10-18 — F3.7.8 COMMAND CI DESBLOQUEADO E CERTIFICADO EM HEAD FUNCIONAL
FASE: F3 IN_PROGRESS; F4 NOT_STARTED.
PROVA: GitHub repositório FM-CONTROL-CENTER passou a público; annotation prévia dizia pagamentos recentes falhos OU aumento de spending limit; após mudança, jobs iniciaram com steps reais.
COMMAND PR #90 HEAD FUNCIONAL: efd7a89e15a7e02ded3e21e962bce8e5279b00ee.
GATES COMMAND NESTE SHA:
- Foundation 39145954696 = SUCCESS: lint/typecheck/migrations/Vitest/Node signer ↔ Assistant ASGI sintético/secret scan/build/Playwright/runtime smoke/Docker/audit.
- F21 39145954712 = SUCCESS: tenant/security, PostgreSQL backup restore, scan e auditoria.
- Cognitive 39145954655 = SUCCESS: segurança de regressão, suite cognitiva, build e git diff check.
CORREÇÕES ORIENTADAS POR LOGS:
- b964dbcf = testes de config exigiam NODE_ENV para ProcessEnv;
- ac870b30 = remoção de trailing whitespace em doc F3;
- efd7a89e = checkout temporário Assistant retirado da árvore Next.js após E2E antes de build, sem desabilitar checks.
GATE: Command CI funcional GREEN nesse SHA, mas revisão independente + homologação infraestrutura/Vault/TLS/ACL/quotas/providers pendem; F3 GLOBAL IN_PROGRESS, não promover F4.
CI documental do HEAD posterior deve ser revalidado. Sem merge, deploy, credenciais reais, migrations produtivas; Kordena read-only.

2026-10-18 — F3.7.9 COMMAND STATUS NONCE REPLAY PROTECTION
STATUS: F3 IN_PROGRESS, F4 NOT_STARTED; melhoria de segurança GREEN no HEAD funcional Assistant.
PR ASSISTANT #1: 303747d8efe33536af796d75c698bf01864409a5.
- Migration aditiva 20261018_0008 cria assistant_command_bridge_status_nonce, sem credencial real, identidade ou grant ativo.
- Serviço status passa a consumir nonce válido de cada consulta HMAC por inserção transacional com UNIQUE PK, inclusive outcome unknown; concorrência e replay retornam negativa 401 sem alterar grants/identity.
- Teste SQLite para retorno unknown, replay e MAC inválido sem consumo; teste PostgreSQL 16 em concorrência comprova exatamente uma leitura válida/uma negada e nenhuma alteração no ledger de mutações; validação de upgrade Alembic.
CI CERTIFICADO:
- SaaS Foundation push 39147372675 SUCCESS, PR 39147376449 SUCCESS.
- Core Assistant Bridge push 39147372436 SUCCESS, PR 39147376462 SUCCESS.
- F3 PostgreSQL16 push 39147372438 SUCCESS, PR 39147376482 SUCCESS.
HISTÓRICO DE CORREÇÕES:
- Ruff isort falhou no primeiro gate, corrigido sem relaxar linter.
- Teste PostgreSQL anterior exigia ledger vazio após outros testes; substituído por contagem delta de eventos preexistentes, sem reduzir prova anti-replay.
COMMAND:
- PR #90 mantém CI anterior GREEN em 811f0cf5d7d99ec078577b1fa35948a1120a921e; runbook documental de staging isolado docs/FMCC_F3_CONTROLLED_STAGING_VALIDATION_RUNBOOK.md criado no Command.
RESTRIÇÕES: F3 GLOBAL IN_PROGRESS, Command e Core não sofrem deploy. Falta reviewer independente, ambiente/credenciais governados, TLS/ACL/Vault, quotas/circuit/FinOps, política de retenção para nonces e homologação controlada. Não promover PRs, F4 ou produção antecipadamente.

2026-10-18 — F3.8 GOVERNED QUOTAS/CIRCUIT/FINOPS DESIGN CANDIDATE
FASE: F3 IN_PROGRESS, F4 NOT_STARTED.
CORE: docs/F3_8_QUOTAS_CIRCUIT_FINOPS_DESIGN_CANDIDATE.md criado na branch feat/ai-service-v1.
CURRENT: provider health/circuit configuráveis e leitura de rotas fechadas/saudáveis; não há prova de circuit breaker distribuído automático, reserva preventiva de quotas, single half-open probe e settlement reconciliável entre retries/fallback.
TARGET (NÃO IMPLEMENTADO): quota transaction reserve/settle/refund por tenant/unidade/capability e request_id; circuit persistent state/lease/fencing; fallback governado compatível com BYOK e teto de custo; observabilidade/FinOps sem inventar custo desconhecido.
GATE: somente proposta para revisão técnica; sem alterar política de custo, aplicação produtiva ou classificação F3.8 GREEN.
PENDÊNCIAS: revisão ADR/System Design, state machine, migrations aditivas, testes de concorrência PostgreSQL, integração ao runtime, CI Core/Assistant, revisão independente, providers reais e Vault/rede.


2026-10-18 — F3.8.1-2 CORE CIRCUIT AND QUOTA INCREMENTAL GATE
FASE: F3 IN_PROGRESS; F4 NOT_STARTED. SUBGATES F3.8.1/2 = GREEN INTERMEDIÁRIO.
AUDITORIA DE PROVENIÊNCIA: System Design Mestre, Prompt Mestre F3 e ADR-008/ADR-004 revisados. O Core NÃO assume autorização de plano/licença ou billing do Assistant.
CORE: PR #1 Draft, branch feat/ai-service-v1. HEAD funcional 3dbab732d8fa9c2425d6ebaa8d560cd6b1fbcf21.
IMPLEMENTADO:
- Máquina de estados pura em core/ai_circuit_breaker.py com CLOSED/OPEN/HALF_OPEN, threshold, cooldown, lease token lógico, resultado tardio negado e recuperação fail-closed para probe expirada. Sem uso no runtime.
- Ledger de quota SQLAlchemy core/ai_quota_store.py, policy tenant/unidade/capability, request idempotente, reserve/settle/refund lógico, lock em policy row. Sem alterar licenças/billing e sem ativar providers.
- Migration f3_0003 aditiva, novo bootstrap exige revisão correta; nenhuma migration em banco não descartável foi executada.
- Novo gate PostgreSQL 16 descartável executa duas reservas concorrentes com mesmo budget, confirmando apenas uma admitida, e duas reservas idempotentes com o mesmo request ID.
EVIDÊNCIAS FUNCIONAIS CORE:
- AI Service CI push 39153783479 SUCCESS e PR 39153787266 SUCCESS.
- F3 Quota PostgreSQL Security Gate push 39153783598 SUCCESS e PR 39153787264 SUCCESS.
- Falhas antigas de Ruff imports e fixture cross-scope preservadas no histórico de Actions, corrigidas sem enfraquecer testes.
DOCUMENTAÇÃO: docs/F3_8_1_2_EXECUTION_CERTIFICATION.md no Core. HEAD após docs deve ser revalidado.
PENDÊNCIAS:
- Circuit breaker compartilhado: persistência, row locks, half-open probe com fencing atômico e transições automáticas.
- Hook de preflight quota no runtime apenas após autoridade/entitlement do Assistant, política de limite configurável e mecanismos de expiração.
- FinOps de custo/token real, preço desconhecido auditado (nunca zero fictício), fallback seguro BYOK/FM, observabilidade, revisão independente e homologação de provedores/TLS/ACL/Vault.
- Real PostgreSQL de staging/credenciais/provedores exige autorização humana específica.
RESTRIÇÕES: sem merge das PRs F3, deploy, migration real, mudança produtiva de secret ou promoção de F4. Kordena read-only.

2026-10-18 — F3.8.3 PERSISTENT CIRCUIT AND GUARDED RUNTIME
F3=IN_PROGRESS; F4=NOT_STARTED. FM Core PR #1 implemented provider circuit state locking/fencing with migration f3_0004 and PostgreSQL16 single-probe concurrency tests. CoreControlPlaneAIRuntime supports opt-in quota request admission (one technical request unit, not monetary spend), unique execution replay denial, conservative timeout retention, and provider circuit enforcement. BYOK is rejected under provider-wide breaker until tenant/credential partitioning; mixed BYOK/FM fallback is prohibited. Guards are NOT automatically enabled in production. Source: FM Core docs/F3_8_3_PERSISTENT_CIRCUIT_QUOTA_RUNTIME.md and AGENTS.md. Pending: authoritative Assistant quota projection, provider cost/token settlement, real FinOps, retention, security review, TLS/ACL/Vault and staging. No merge, deployment, real credentials or persistent migration.

2026-10-18 — F3.8.4 QUOTA OUTCOME REVIEW (INTERMEDIATE)
Core PR #1 implemented scoped, read-only pending_for_reconciliation for ambiguous request reservations, with regression ensuring no cross-tenant access and no refund/retry side effects. This is NOT financial settlement and does NOT infer unknown costs are zero. Circuit and quota guards remain opt-in; Assistant entitlement policy propagation is still pending. Continue F3 IN_PROGRESS and F4 NOT_STARTED, no merge/deploy/real secrets/staging migration. Source: Core docs/F3_8_3_PERSISTENT_CIRCUIT_QUOTA_RUNTIME.md and AGENTS.md. Validate CI HEAD before certification.

2026-10-18 — BUILD-FIRST DECISION AND FINOPS INTERNAL GATE
AUTHORITY: explicit owner decision dated 2026-10-18, documented in docs/governance/F3_BUILD_FIRST_EXTERNAL_HOMOLOGATION_LAST_2026-10-18.md and all three AGENTS.md.
ACTIVE SEQUENCE: finish 100% of internal software construction, including F3 and later phases, without requesting external credentials or real service validation along the way. External Vault/provider/DNS/TLS/production tests are catalogued separately as EXTERNAL_HOMOLOGATION_DEFERRED; they may not stop construction or next software phase. Never label them green.
INTERNAL GATES: software correctness, authorization, tenant isolation, audit, migrations against disposable DB, concurrency, lint, build, security regression, CI and versioned evidence. Merge allowed by standing owner authorization only if software gates complete and confirmed to have no automatic deploy/mutation side effects. No production secret/deploy/non-disposable migration without specific consent.
F3.8 CORE WORK: core/ai_usage_ledger.py now includes request-scoped, known-subtotal versus unknown-attempt FinOps reconciliation; missing costs are explicitly counted. core/ai_finops_preflight.py calculates deterministic worst-case provider fallback token costs against immutable price snapshot and explicit monetary limit, failing closed for missing/invalid pricing, currency mismatch, or budget exceed. Both are BUILD_IN_PROGRESS internal components, not provider-verified spend caps and not real homologation.
BUILD GAPS NEXT: authorized Assistant entitlement-to-Core projection; monetary budget reservations/settlement and provider attempt lifecycle; enforced provider output token ceilings; completed circuit/quotas/FinOps runtime wiring with test fixtures; end-to-end internal certification; other master phases through completion.
EXTERNAL GAPS DEFERRED TO FINAL: provider keys and live requests, hosted Vault/network/TLS, production deploy, provider contracts, financial gateways, real acceptance/homologation and independent external verification. F3/F4 progression depends only on completed internal implementation and internal CI, not these deferred tasks.

2026-10-18 — F3/F9 PLANS, TOKEN QUOTAS AND PER-TENANT BUDGETS
OWNER REQUIREMENT: Planos comercializados devem possuir limites versionados por plano, tenant e unidade, incluindo requests/tokens/áudio/mensagens e custos internos de IA; FM paga os provedores de IA (modo FM-managed), cobrança do cliente é assinatura SaaS independente.
ASSISTANT IMPLEMENTED:
- Migration aditiva 20261018_0009 cria assistant_plan_versions e assistant_plan_limits e adiciona tenant license plan_revision (nullable para retrocompatibilidade).
- PlanLimitResolver lê unicamente licença canônica: tenant/unidade ativos, licença active/trial vigente, revisão fixada, recurso presente, janela/limite positivo. Falha fechada sem licença válida ou quota.
- Testes de plano revision-pinned, tenant isolation, trial suspenso/expirado e recurso ausente; migration de schema atualizada e CI integrado.
CORE IMPLEMENTED:
- QuotaReservations.reserve_bundle/settle_bundle bloqueia/reserva atomicamente todas as dimensões do plano. Suporta orçamento agregado de tenant (scope técnico __tenant__) e limite por unidade com lock de políticas; concorrência PG16 confirma que apenas uma das unidades concorrentes consome saldo global.
- ProviderRouteSettings.max_output_tokens configurável e validado; OpenAI-compatible envia max_tokens e Gemini maxOutputTokens; testes sintéticos dos adapters. FinOps request reconciliation distingue custos conhecidos/desconhecidos.
- Testes de rollback integral em limite excedido, replay de request, settlement idempotente, scope e concorrência multiunidade.
COMMAND DOCUMENTED: docs/FMCC_F3_F9_COMMERCIAL_PLANS_AND_AI_COST_CONTROL.md define responsabilidades corporativas product_id+tenant_id+plan_code+revision, custos IA da FM, margem, limites e governança.
REFERENCE: docs/governance/F3_F9_PLAN_QUOTAS_AND_AI_USAGE_ARCHITECTURE.md.
CURRENT STATUS: BUILD_IN_PROGRESS (subcomponentes CI a certificar no HEAD atual). Ainda faltam sincronização assinada de quotas/entitlements Assistant→Core, política de expiração/revogação no Core, guard obrigatório no runtime, limitação segura de input tokens, conciliação oficial de tokens/custo e UI/plano/upgrade/downgrade no F9, dashboard.
REAL HOMOLOGATION: EXTERNAL_HOMOLOGATION_DEFERRED; não impede próximos passos de software. Sem segredos reais, produção, deploy ou migrations em banco não descartável.

2026-10-18 — ADR-009 KORDENA FINOPS REVIEW / ALL FUNCTIONS FOR ALL PLANS
OWNER DECISION: all tiers get 100% of product functionality, no feature gating by subscription tier. Plans differ only by FM-defined commercial price, quantity/usage ceiling and period; FM Command corporate authority exclusively manages values, revisions and pricing. Client cannot alter entitlement or prices. RBAC/security and valid subscription are tier-independent.
KORDENA READ-ONLY AUDIT: faabio3131/fm-ai-platform default main SHA 9a047f98d45574eb7dbf171a9fff8fe5a79fcb2d; no writes. Inspected core/ai_cost.py, core/ai_pricing.py, infra/ai_metering.py, infra/ai_finops_projector.py, infra/ai_finops_models.py, infra/ai_finops_read_model.py, application/ai_finops_dashboard.py, infra/streamlit_app/ai_finops.py, tests/fitness AF23/25/27/28/29/30 and durable-metering tests. Kordena main provides analytics/projection/dashboard; additionally the Draft PR #230 at SHA 691ba84edd1cd663278fb868035b6d1169e90610 implements a CANDIDATE AIFranchiseBudgetGuard, transactional Decimal per-attempt budget ledger, subscription lifecycle provision, pricing config and customer threshold view. PR #230 is not merged/certified (multiple failed workflows). This candidate must be studied for reuse, not treated as an active canonical service. Its budget is USD scoped initially by unit/capability; VendeAtendeIA requires dynamic FM-only plan prices and tenant-wide as well as unit-specific request/token and cost ceilings, with zero feature gating. Its cost/pricing module git blob SHAs match FM Core exactly. Event id omits route/attempt identity; aggregated token None becomes 0, so do not use that read model for authoritative spend limits.
ADR: docs/governance/ADR-009-ALL-FEATURES-PLAN-CONSUMPTION-AND-KORDENA-FINOPS.md. Updated F3_F9 plan architecture plus 3 AGENTS. Status APPROVED DECISION / BUILD_IN_PROGRESS (governed Command plan admin publisher/price editing not yet implemented; authorized plan revisions/projection and hard stop runtime incomplete). Kordena remains read-only.
NEXT SOFTWARE: build FM Command sole pricing/limit editor, published versioned plans, signed Command→Assistant→Core projections, full accounting and authorization; customer dashboard/upgrade, all-feature parity tests. EXTERNAL_HOMOLOGATION_DEFERRED until build 100% completed. No production actions.

2026-10-18 — COMPLEMENTO ADR-009: Command Kordena pricing editor PR #91 DRAFT, head 7fde1e1c95d7e77547e5b6f088939311be06518f, 3/3 workflows internos SUCCESS no instante da inspeção. Editor FM prepara preços BRL e franquias em USD, valida decimal sem float, versionamento e step-up; não publica automaticamente nem representa recurso pronto para VendeAtendeIA. Reutilizar padrão no Command para produto próprio, sem fixar quatro códigos Kordena e sem feature gating. Kordena PR #230 mantém falhas em múltiplos workflows e ainda é Draft. Kordena read-only; nenhum merge/produção/segredo.

2026-10-18 — F3/F9 LICENSE BIND + CUSTOMER LIVE QUOTA READER
BUILD STAGE: F3/F9 incremental, implementation and internal certification; F3 GLOBAL remains BUILD_IN_PROGRESS, F4 NOT_STARTED, production/homologation external deferred.
CORE PR #1: GET /v1/plan/usage authenticated by service key, exact-scope ledger balance with policy revision, window, limit, consumed/reserved/remaining and observation timestamp; missing persistent ledger/policy returns 503 rather than fake zero. Synthetic Core API tests + real disposable PostgreSQL gates. Code HEAD (before AGENTS) 7cb9bea7d5a3483da68883d749f3c5b7b716bd13 passed 4/4 workflows; AGENTS changed and current HEAD needs recheck.
ASSISTANT PR #1: governed signed initial plan/license binding endpoint, HMAC separated from plan publication, anti-replay nonce, active/valid license and published revision, retention of original trial/paid deadlines, immutable audit in migration 0011. Reassignment/upgrade requires governed transition, no silent plan reset.
ASSISTANT CUSTOMER PANEL: JSON GET /v1/plan/consumption and rendered GET /v1/plan/consumption/dashboard use authenticated human billing.read tenant/unit; no browser-supplied scope, no FM provider internal costs. CoreUsageHTTPReader validates HTTPS, exact tenant/unit/metric/scope/revision/limit/window and fresh observation; unknown/failed traffic shows metering_unavailable/null balance, not zero. Server-rendered responsive HTML no-store + CSP, test coverage.
COMMAND PR #90: signAssistantPlanLicenseBind pure HMAC path-scoped helper with FM company authority, synthetic unit coverage; does not dispatch yet. Commercial editor and published plan outbox remain separate; no external provider call made.
NEXT INTERNAL CONSTRUCTION: actual Command billing grant -> outbox dispatch of license grants; signed Assistant entitlement/policy -> Core policy projection and active PlanUsageGuard default; comprehensive token/cost/fallback reconciliation, revision upgrades at cycle boundary, consolidated dashboards/alerts and security gates. No external config needed for software.
QUALITY: Ruff/test/API/SQL/contract workflow evidence tied to current HEADs; fix failures without bypassing gates. Kordena read-only. None merged/deployed or migrated persistent DB.

2026-10-18 — F3/F9 CUSTOMER USAGE ALERT + LICENSE MANIFEST SUBGATE
SOURCE: src/fm_assistant/plan_consumption_view.py, plan_consumption_dashboard.py, plan_policy_manifest.py; tests/saas/test_plan_consumption_view.py, test_plan_limits.py. Customer consumption now includes committed=consumed+reserved, percentage and 70/90/100 percent warning bands; unavailable Core metering remains unknown/null, no fake remaining budget. LicensedQuotaManifestService resolves only revisioned quotas from active canonical tenant license, rejects suspension/expired or essential missing metrics. This is read-only domain construction; no provider activation or untrusted self-upgrade. Pending internal: signed Assistant→Core quota deployment and revocation, transactional policy sync, actual plan-driven provider caps, full lifecycle E2E. External homologation remains deferred until 100% build. CI HEAD verification required.


2026-10-18 — F3/F9 CORE LICENSE REVISION FENCE, INTERNAL SECURITY SUBGATE
- Repo `faabio3131/FM-Core-Base-`, PR #1 Draft; functional SHA `ca378e54226bb2925cd57e5f367f7bb27585d149`.
- `PlanUsageGuard` now supplies `policy_revision` in atomic quota reserve/settle; DB policy row revision must match the licensed revision. Stale license/policy, invalid boolean revision, negative usage attempts and incoherent cached-token readings fail closed rather than miscrediting quota.
- Core AI Service CI `39189526526` SUCCESS; Core F3 Quota PostgreSQL Security Gate `39189526538` SUCCESS on functional SHA. No external provider, production migration or real credentials involved.
- This is a functional safety subgate, **NOT** automatic Assistant→Core policy synchronization or production quota enforcement. Pending: signed/version-monotonic policy transport, revocation/expiry, composition-root enforcement, per-attempt token/cost settlement, multi-service E2E and remaining F3 internal gates.
- FM Command V2 untouched. Corporate FM-CONTROL-CENTER remains sole commercial management authority; Kordena read-only. F3 BUILD_IN_PROGRESS, F4 NOT_STARTED; EXTERNAL_HOMOLOGATION_DEFERRED. No merge/deploy.


2026-10-18 — F3/F9 AUTHENTICATED CORE PLAN GRANT READ-THROUGH (INTERNAL SUBGATE)
- CORE `faabio3131/FM-Core-Base-` PR #1 Draft, functional SHA `cf1fd77fd7271b7eae8aa589f58a79bc78f61882`: dynamic challenge-bound signed grant verifier and explicit HTTPS no-redirect transport. Internal AI Service CI #39190989920 SUCCESS; quota PostgreSQL security #39190990006 SUCCESS.
- ASSISTANT `faabio3131/-FM-Assistant-Base` PR #1 Draft, functional SHA `9b971d64ed8224641c58a3be5def886f7fb6d16d`: private request-signature verified plan-grant route, canonical live licensed manifest, 30s response signature/challenge, separate plan signing key. SaaS CI #39190924170 SUCCESS; cross-service bridge #39190924237 SUCCESS; PG16 bridge #39190924161 SUCCESS.
- All referenced checks use synthetic credentials/disposable databases/mocked HTTPS or internal contracts. No real provider/Vault/production network tested.
- NEXT INTERNAL BUILD: trusted composition of `SignedAssistantPlanAuthority` into mandatory persistent Core runtime; signed versioned/revocable quota-policy projection into PostgreSQL, bounded provider input/output/attempt accounting, hard stops and immediate revocation checks, cross-runtime E2E and independent security review. Do not describe the contract as automatic production enforcement.
- F3 `BUILD_IN_PROGRESS`; F4 `NOT_STARTED`; external F13 homologation `EXTERNAL_HOMOLOGATION_DEFERRED`. Kordena read-only; Command V2 untouched; no deploy, non-disposable migration or merge.


2026-10-19 — F3/F9 COMMERCIAL BOOTSTRAP PLAN ENFORCEMENT SUBGATE
- FM Core PR #1 `feat/ai-service-v1` functional SHA `0569a451d3d6d27448a0e25d10f9856f10acdd59`, CI `39193067739` SUCCESS, PostgreSQL quota `39193067850` SUCCESS. Commercial staging/production settings now mandate separate signed Assistant authority URL/key; API runtime composes that read-through authority into persistent Core quota guard for text and audio.
- FM Assistant PR #1 remains at previous certified `69689c1570ffc64e53e2ccf56ea6c1f74ab907eb` (3/3 gates green); the existing signed license grant route is not replaced or duplicated. No deploy or production secrets.
- NEXT: signed complete allowance/limit projection + revision/atomic reservations in Core PostgreSQL, provider hard token caps and reliable reconciliation, tests for suspension/rotation/no-policy/over-quota; finish internal integration before any external homologation.
- STATUS: F3 `BUILD_IN_PROGRESS`, PRs DRAFT; no merge/deploy; do not touch Kordena or `fm-command-v2`.


2026-10-19 — F3/F9 SIGNED FULL QUOTA PROJECTION AND PROVIDER CAP (INTERNAL SUBGATE)
- Assistant functional SHA `63a1be2e99a32d40503e38b009533a3964663b3e`: signed tenant/unit license grant now carries every allowed metric's exact limit and window, with regression proof. SaaS/Foundation, bridge HMAC contract and PostgreSQL security CI completed 3/3 SUCCESS.
- Core functional SHA `4bacb3fbac84997de6dbe02744d2c2e805f1c7a7`: strict grant decoding, monotonic atomic quota projection to PostgreSQL/SQLAlchemy, pre-provider quota reservations, per-request provider output-token cap, and simulated usage reconciliation. AI Service CI `39194025504` SUCCESS, F3 Quota PG `39194025523` SUCCESS.
- Internal coverage is synthetic and CI-focused; not an approved production load/finops certification. NEXT: remaining input cap + fallback-attempt metering hardening, policy window/revision rotation under outstanding work, financially safe reconciliation & provider cost ledger, per-capability FM-controlled bounds, complete Core/Assistant PostgreSQL E2E including revocations. F3 BUILD_IN_PROGRESS. PRs DRAFT; no deploy/merge/secrets; external homologation deferred. Kordena and `fm-command-v2` remain untouched.


2026-10-19 — F3 BACKEND SAFETY HARDENING / FALLBACK CONTROL — GREEN INTERMEDIATE ONLY
- FM Core has added window-change fencing over prior quota usage (atomic rollback), per-provider attempt-budget reservation before external contact, router attempt count fencing and cumulative usage accounting. Revoked license refuses provider and credential resolution. FM-settable text/audio token ceilings using validated `FM_CORE_ASSISTANT_PLAN_BOUNDS_JSON`. Synthetic Core E2E for HTTP transient fallback leaves ambiguous reservation held, not silently refunded.
- Core validated functional checkpoint `3b6dced79b932face017d7c87a4f507c6b1f4b4d`, AI Service CI `39270774348` SUCCESS and quota PG `39270774530` SUCCESS. Previous FM-configurable budget checkpoint `a284e0e0` CI `39270629034` + PG `39270628943` SUCCESS. FM Assistant code remains on prior internally green state, no change of catalog/license semantics here.
- Remaining F3: provider-specific reliable input/audio token gating, accountable ambiguous charge reconciliation, governed window migration, cross-runtime concurrency/CLI E2E, outstanding Command↔Assistant↔Core identity/governance and independent security review. F3 IN_PROGRESS, F4 NOT_STARTED; external homologation deferred by user until software 100% built, not an internal development blocker. No merge/deploy/real provider keys or Command V2/Kordena modification.


2026-10-19 — F3 RECHECK CROSS-REPOSITORY GATES AND POSTGRESQL ROTATION
- Core `3b638e4800aa0925a27d340321a8036022198f68`: disposable PostgreSQL regression for atomic refusal to change quota window over outstanding usage, CI `39271248172` SUCCESS and F3 quota PostgreSQL gate `39271248045` SUCCESS. HEAD `41567e33` updates AGENTS.md only and has its own workflow recheck.
- Corporate `FM-CONTROL-CENTER` PR #90 (NOT `fm-command-v2`) functional HEAD `626be1432cbd753edf3bf547dbe288dde3199b25`, 4/4 currently green; cross-service execution is not fully certified. Assistant previous signed policy contract remains internally green.
- Outstanding internal F3: deterministic/provider-validated input token admission for text/audio; governed reconciliation and recovery for ambiguous provider charges; migration of plan period changes with historical usage; complete Assistant/Core/Command multi-process PostgreSQL E2E and independent security review. Do NOT promote F3 or merge on partial evidence. Real external credentials/homologation deferred until full software built. No production deployment or Kordena/fm-command-v2 changes.


2026-10-19 — F3 COMMERCIAL TEXT INPUT PRE-ADMISSION SUBGATE
- Core functional `d63621cf916ad47a1de8b70385196d9bb1359f0e`: conservative byte-envelope text request validation (including Unicode and system/user messages) denies oversized input before tenant quota reservation and provider credentials; tests certified AI Service CI `39273574128` SUCCESS, PostgreSQL Security Gate `39273575267` SUCCESS.
- Canonical status `F3 = IN_PROGRESS`; this is not exact provider tokenization. Remaining work: provider/model-aware input counters, full audio bound and accounting, governed post-provider uncertain-cost resolution, cross-system Command/Assistant/Core end-to-end with disposable PostgreSQL and negative-security tests, independent security review. Defer only real external credentials and homologation until software 100% built; internal work continues. No merge/deploy, do not modify Kordena or fm-command-v2.


2026-10-19 — F3 INTERNAL AUDIO PAYLOAD SAFETY SUBGATE
- Core functional SHA `a343b3af2374cc5ceae08b65ffe72f12841a12ac`, AI Service CI `39274933331` SUCCESS, PG security `39274933453` SUCCESS. FM-managed maximum audio upload bytes now validates settings and denies oversized audio pre-quota; 10MiB default, 64MiB upper configuration bound, strict false-positive-free byte limit. Audio bytes are NOT token accounting.
- Core and Assistant production homologation remains deferred until software construction complete. F3 IN_PROGRESS: model-specific token accounting, ambiguous usage reconciliation, Command/Assistant/Core PostgreSQL E2E, independent security review. PRs remain Draft without merge/deploy, Kordena and fm-command-v2 unchanged.


2026-10-19 — F3 AMBIGUOUS PROVIDER CONSUMPTION GOVERNED RECOVERY: IMPLEMENTED, PENDING FINAL CI
- Core `QuotaReservations.reconcile_ambiguous_bundle` now stages verified human-admin recovery with provider evidence reference and exact all-metrics quota settlement atomically with the Command admin audit. No auto-refund on provider timeout/unknown usage; rejects incomplete or repeated settlement.
- SQLite negative/positive cases added; concurrent PostgreSQL two-worker regression added. `docs/F3_8_AMBIGUOUS_USAGE_RECOVERY.md` formalizes the required provider-issued no-charge evidence, proof retention and guarded release conditions. No externally reachable API was implemented.
- Initial functional CI `39277663167` SUCCESS and PG `39277662911` SUCCESS. Latest tests (including multiworker PG) were queued when checked; final certification remains pending. Follow-up: confirm latest workflows, verify signed Command boundary and independent provider evidence ingestion/retention. F3 BUILD_IN_PROGRESS, F4 NOT_STARTED; no merge, deploy or external homologation.


2026-10-19 — NEW CUSTOMER WHATSAPP QR ONBOARDING, INTEGRATION FABRIC ADAPTER
- Scope is new VendeAtendeIA signup/channel connection UX, not F3 Core closure. Evolution candidate provider added to existing universal Integration/Credential Control Plane. FM master key configured separately and kept server-side; individual token encrypted via existing Vault; instance ID opaque, tenant/unit scope and audit trail.
- Customer endpoints provide scoped provision and time-limited QR inspection with no-store response; tenant cannot inject instance names/tokens through generic Integration API. Remote uncertain creation is not automatically retried, and concurrent first provisioning is transactionally serialized in PostgreSQL.
- Tests written for mocked provider, malformed QR, tenant isolation, no-store, no VPS key leak, duplicate/ambiguous create, and generic mutation bypass. Functional and documentation CI is QUEUED at recording time, not yet GREEN. Full webhook bridge, lifecycle, outbound messages and visual QR onboarding remain NOT_DONE and must not be conflated with this foundation.
- See `docs/governance/WHATSAPP_QR_FM_MANAGED_ONBOARDING.md`. External VPS credential/homologation deferred until software build complete. F3 remains BUILD_IN_PROGRESS at separate prior checkpoint; no merge/deploy or changes to Kordena/Command V2.


2026-10-19 — WHATSAPP QR CUSTOMER DASHBOARD + SIGNED MESSAGING E2E — INTERNAL FUNCTIONAL GATES GREEN
- Reused FM Assistant Integration/Credential Control Plane and Conversation Engine. Implemented customer QR panel with authorized session, nonce CSP, 8s polling, current status API, encrypted per-instance token, and FM-managed one-shot sender. Signed FM ingress contract only; native Evolution webhook authenticity **not yet implemented**.
- Signed connection events drive scoped active/degraded status. Signed inbound text messages claim unique channel/message ID before model and outbound execution; HMAC sender hash, cross-tenant barriers, no duplicate answer on repeated webhook. Ambiguous provider returns mark `reconcile_required` and remain held, with no blind resend.
- Functional SHA `85d49c4f0ce95a26a79c78f5c63ee07234a37c55`: SaaS Foundation CI `39291893839` SUCCESS, PostgreSQL F3 bridge `39291893849` SUCCESS, signed Core/Assistant `39291895488` SUCCESS.
- Remain IN_PROGRESS for customer channel readiness: genuine native provider-edge signature/credential validation broker, provider edition/version contract, durable event inbox/outbox and asynchronous worker/crash recovery, remote disconnect/revocation/reconnect ownership verification, more robust UI, and independent security/cost gates. No real VPS, phone, credentials, production deploy, merge or external homologation. F3 original global milestone remains BUILD_IN_PROGRESS and unchanged.


2026-10-19 — WHATSAPP QR INBOUND RESILIENCE BATCH COMPLETED, CERTIFIED
- Delivered bounded tenant-scoped `processing` stale quarantine and no-blind-retry recovery; PostgreSQL SKIP LOCKED and conditional update, with SQLite synthetic isolation tests. Verified duplicate event still cannot cause another model/provider execution after quarantine.
- SHA `2f7700bdb2bc7cdfb835d02baa2fd172c4dac86b`: SaaS `39297829882` SUCCESS, PostgreSQL `39297829871` SUCCESS, Core/Assistant bridge `39297829914` SUCCESS.
- FM Command cross-SaaS configuration/data-ingestion architecture is deliberately held for user review. No new Command integration claims or dynamic QR policy synchronization. Keep approved 45s fallback in Assistant. Native Evolution ingress proof, queues/workers, real provider pinning and remote lifecycle are NOT_DONE, external homologation only after build completion.


2026-10-19 — WHATSAPP QR LOCAL CHANNEL PAUSE CONSTRUCTION
- Add customer-local pause endpoint protected by tenant/unit integration.manage, revision and event audit. No remote logout is implied and restart is blocked pending governed resume implementation. UI respects disabled status and avoids misleading connected indicators. Regression test demonstrates signed stale "open" webhook cannot reactivate locally disabled channel.
- Separate upstream native Evolution authentication, real remote disconnect/reconnect, durable inbox/worker and cross-SaaS Command policy delivery remain NOT_DONE; Command architectural review held by user; no real VPS credentials or homologation.


2026-10-19 — QR WHATSAPP SIGNED LIFECYCLE REPLAY PROTECTION
- Evolution `connection.update` signed-event replay receipts now persist across workers using composite unique key and additive migration `20261019_0012`. Exact duplicate signed lifecycle payloads cannot reapply state after new transitions. Event body/timestamp are digested; no raw WhatsApp payload or sensitive token is persisted in the receipt.
- Additional test replays an earlier signed `open` after `degraded` and asserts it cannot reactivate; a genuinely distinct authenticated event may activate. Remains fail-closed pending authentic upstream FM broker, provider event ordering and durable work queue/outbox.
- Continue software construction and internal CI first. No external homologation, production migrations, merges, or changes to the Command cross-SaaS architecture.


2026-10-19 — WhatsApp QR F3 encrypted durable asynchronous ingress — BUILD IN PROGRESS
- Implemented `EvolutionInboundQueue`, add-only migration `20261019_0013`, per-connection unique message keys, encrypted sender/text, transactional worker claim (PG skip-locked; conditional state transition), bounded worker `python -m fm_assistant.evolution_worker`, and conservative stale quarantine at every polling cycle. Hooked API app composition to enqueue after HMAC-normalized event verification; no AI or remote send on webhook HTTP request. Synthetic tests prove ACK-before-work and exactly-once claimed processing, duplicate webhook suppression, encrypted persistence and no retry of stale claims.
- Remains **NOT externally certified / NOT production-ready**: native provider origin authentication, provider API pinning, remote revoke/reconnect, backpressure and full concurrency/fault injection. FM Command cross-SaaS architecture is held for user's review; do not change Command or claim dynamic policy sync. Never apply prod migrations, deploy, merge or expose secrets.


2026-10-19 — ADVANCE: Durable inbound queue + guarded remote logout / Evolution v2 adapter (INTERNAL BUILD)
- Persistent queue `20261019_0013` with Fernet ciphertext, bounded worker and old processing quarantine. API broker webhook stores signed message without calling AI; standalone worker invokes existing Assistant/Core with unique inbox claim, single outbound attempt, and fail-closed quarantine. Tests synthetic only; no production scheduler/deploy.
- Remote control adapter supports `connectionState` read and `logout` per Evolution-v2-style API. Customer logout is locally disabled before provider request; token revoked and status marked REVOKED only on explicit provider confirmation, remote ambiguity requires reconciliation. Added API/UI and tenant-isolation tests, plus outbound status/revision recheck after model inference.
- **NEXT**: upstream-native identity verification/signing broker, provider release pin, webhook sequencing and async throughput controls, remote reconnect/new instance after logout, integration/chaos/race tests. Command universal policy ingestion remains held for separate architecture review. No external homologation, real creds, production migrations, merge or deploy.


2026-10-19 — QR resume after local pause: tenant-scoped POST /resume verifies remote Evolution instance state `open` with encrypted per-instance credential before local ACTIVE. If remote closed/unreachable, channel stays disabled; revoked cannot resume. UI and synthetic regression tests added. Version-specific provider contract and real edge-origin authentication remain pending separate gates.


2026-10-19 — Evol v2 native source-authenticated ingress / post-logout relink / concurrent workers — internally GREEN
- Version-family gate `evolution_v2_whatsapp_baileys`, HTTPS per-instance webhook with separate encrypted header secret, independent bearer-header validation at `/webhooks/evolution-native/{connection_id}`, normalized signed FM broker forwarding, native setup fail closed with no uncertain retries. Verified in tests with no real Evolution/WhatsApp accounts. Do not confuse per-instance shared-secret header possession with provider-native cryptographic signature. Exact release pin/homologation remains future.
- Confirmed logout permits fresh provisioning while retaining revoked historical connection and invalidating previous secret; ambiguous logout/relink cannot auto-promote. Two-thread worker synthetic race asserts at most one claim of one queued message; SQLite database lock yields no claim and cannot initiate duplicate AI/send.
- Tests certified at SHA `c39ade7ac607cdb120332001721710a4d4cf00f2`: SaaS `39330977685` SUCCESS; F3 PostgreSQL `39330977553` SUCCESS; Core/Assistant `39330977550` SUCCESS. No Command changes, merge, deploy, real credentials, or external homologation. Remaining risk: verify exact API contract/version and proxy TLS/network policy after software is complete; add PostgreSQL fault-injection/concurrency under stress and operational reconciliation.


2026-10-19 — Evolution v2.3.7 candidate contract / bounded queue / operator board / distributed PostgreSQL test batch
- Implemented per-connection queue cap default 250 (FM-only config), transaction serialization with PG advisory lock, HTTP 429 Retry-After on capacity, duplicate idempotency. Scoped reconciliation GET/POST with `integration.read` / `integration.manage`, audit and terminal reviewed status (no replay); owner panel includes XSS-safe monitoring and review action.
- Tested PG 2 concurrent producers and 8 concurrent workers in isolated test DB, plus provider-uncertain no-redelivery and synthetic webhook 429. Pinned Evolution v2.3.7 **contract baseline** with nested webhook response fixture; it does NOT confirm installed server image compatibility. Added Nginx security reference config denying public internal HMAC route, native TLS/rate/body controls, but not deployed.
- Source SHA `8abbb90824cc7cc59a040ee9a718d498a6c13d83` CI: SaaS `39334496416` SUCCESS; PG `39334496577` SUCCESS; bridge `39334496427` SUCCESS. CI of documentation HEAD pending until checked.
- Distinguish completed SOFTWARE INTERNAL TESTS from still-required EXTERNAL homologation and operational field tests: pinned real Evolution instance, proxy/TLS/certificate/edge configuration, real WhatsApp message delivery, load and chaos at production-like scale. Command universal architecture review held by owner. No live operations / merging.


2026-10-19 — WHATSAPP F3 WORKER LEASE FRESHNESS AND BACKLOG VISIBILITY — INTERNALLY CERTIFIED
- Added pre-send freshness check for a still-current, non-expired worker claim; stale/quarantined work fails closed and never triggers an automatic resend. Concurrent sweeper terminal status is respected rather than reopened. Owner operational monitor shows the oldest pending age and counts without exposing payload content.
- 3/3 gates on functional SHA `4bf8e0fdfece45c7436d3a364630a4941f9647b8`: SaaS CI `39337851841`, real PostgreSQL F3 `39337851787`, Core/Assistant contract `39337851775` SUCCESS.
- NEXT internal work: renewable worker leases, durable outbound provider fencing/reconciliation, visibility of end-to-end message lifecycle, then further existing Master Schedule features. Provider live compatibility, TLS proxy and real WhatsApp remain deferred homologation gates after construction. No Command code modified; PR #1 remains Draft.


2026-10-19 — F3 GENERATION-FENCED LEASE PRIMITIVE — INTERNAL BUILD, NOT YET CI-CERTIFIED
- After certified checkpoint `0675ff1413c2ec2726e8b3397f7b8b9514a18bdf`, next incremental worker-safety implementation uses existing `attempt_count` as monotonic claim generation, adds guarded atomic renewal with expiry/state/generation conditions, and supplies generation to pre-send freshness/terminal completion checks. No database schema or production migration needed. Regression tests added for foreign/expired generation.
- Source code commits `a9ca48bc`, `baf5ede7`, `c7bfc2ca`, `580d2eaf`. No successful current-HEAD workflows observed at documentation time; preserve previous 3/3 SUCCESS only as prior baseline.
- NEXT: certify exact HEAD; implement periodic renewal during long AI calls, durable outbound delivery-intent fence and uncertain-provider reconciliation; then end-to-end lifecycle tracking and remaining Master Schedule. Do not claim atomic network sends/exactly-once delivery.
- State stays F3 BUILD_IN_PROGRESS and PR #1 Draft; NO merge/deploy or changes to Command universal architecture. External provider credentials, pinned actual Evolution instance, edge TLS and WhatsApp field tests remain deferred release/homologation gates after complete software build and must NOT block internal development.


2026-10-19 — WHATSAPP F3 HEARTBEAT + DURABLE OUTBOUND INTENT — INTERNAL IMPLEMENTATION, CI PENDING
- F3 next increment built on previously green generation-fenced lease: background 30s heartbeat renews the current worker claim during long model/provider calls, strictly CAS-guarded by claim generation and expiry; lease loss fails closed. Prevents normal long AI latency from expiring the worker lease, without claiming atomic third-party delivery.
- Add-only Alembic 20261019_0014: provider operation identifier, outbound status, provider receipt reference, send-start timestamp and 'sending' state; a single transaction commits one send-intent BEFORE invoking HTTP. Durable intent denies second outbound attempt, and crash/timeout during 'sending' is reconciled instead of automatically resent. PostgreSQL/SQLite compatible batch migration; no non-test migration applied.
- Queue reconciliation snapshot includes non-payload attempt metadata; existing tenant/user authorization remains mandatory. Added regressions for single-winner concurrent send intent, replay exclusion, stale send quarantine and bounded provider receipt. No actual provider receipt verification or cryptographic proof of WhatsApp delivery implied.
- Functional implementation commits: 5e7f45ac, 3840660b, 42d5af30, 8f6b7397, c3b6e22b, 2548acf7. CI remains unverified until all 3 exact-HEAD gates report GREEN. NEXT: fix any CI regression, formalize provider reconciliation evidence and lifecycle visibility, broaden failure/chaos and ownership tests.
- F3 remains BUILD_IN_PROGRESS, PR #1 DRAFT. External Evolution live version, real proxy/VPS/phone credentials, WhatsApp delivery and field load remain POST-CONSTRUCTION HOMOLOGATION; these do not block next internal build phases. No production deploy, merge, live secrets, Kordena or Command architecture modifications.


2026-10-19 — WHATSAPP F3 HEARTBEAT / OUTBOUND INTENT / RECONCILIATION — INTERNALLY CERTIFIED
- Functional HEAD `623e2b0b2af26375b23ee088a194081e16d7ece8`. GitHub Actions on this exact SHA: SaaS Foundation CI run `39342275837` SUCCESS; PostgreSQL F3 Security Gate `39342275941` SUCCESS; Core↔Assistant Contract `39342276035` SUCCESS. Functional internal subgate **3/3 GREEN**.
- Implemented worker claim renewal every 30 seconds with generation check and fail-closed loss signaling. Persistent outbound intent is transactionally written before Evolution HTTP call; only one state transition processing→sending per job, and stored provider result is matched to its unique operation ID. A sending worker that expires/vanishes is quarantined to reconcile_required, never requeued blindly. Operator snapshot surfaces non-message provider reference and uncertain intent for governed follow-up. Added migration 20261019_0014 and regression scenarios for concurrent intent, expired sending and immutable dedup.
- Failures corrected during gates: Ruff broad-exception annotations, and legacy Alembic-head assertion updated from 0013 to 0014. Green suite includes 160+ SaaS tests; external network not used.
- Important limits: no proof of true provider-side exactly-once delivery or signed provider delivery receipt; inbound pause/send atomicity and independent chaos at production scale remain separate engineering/security review issues. No external Evolution 2.3.7 instance, real WhatsApp delivery, TLS gateway, VPS credentials or production migration was tested. External configuration/homologation waits until COMPLETE SOFTWARE BUILD and DOES NOT block unrelated internal construction.
- Status F3 BUILD_IN_PROGRESS. PR #1 remains Draft, no merge/deploy; Command universal policy architecture held for separate owner review. Next phase as ordered in Master Schedule: strengthen lifecycle observability and independently audit provider reconciliation, race between pause/revoke and send, then remaining F3 cross-system gates.


2026-10-19 — F3 WHATSAPP LIFECYCLE VISIBILITY / RECONCILIATION SAFETY — INTERNALLY GREEN
- Functional SHA `13add8dc9193a6169ecd5f51b45658a73ee88b01`. GitHub Actions: SaaS Foundation CI `39343758194` SUCCESS; F3 PostgreSQL Core Bridge Security Gate `39343757959` SUCCESS; Core Assistant Authenticated Bridge Contract `39343757968` SUCCESS. 3/3 functional gates GREEN.
- Extended existing tenant-scoped operation snapshot with bounded, no-payload lifecycle data: received/claimed/send-start/last-transition timestamps, processing state, attempted operation id, acknowledgement reference, and manual review requirement. `provider_delivery_confirmed` is deliberately always false; a provider send receipt does not prove final WhatsApp delivery.
- Enforced fail-closed terminal completion: a `sending` row cannot be marked `complete` without previously stored provider acknowledgement. Operations with uncertain send remain quarantined for operator review and cannot be automatically replayed.
- Worker now revalidates connection ACTIVE status and revision after durable intent transaction, immediately before outbound HTTP; if pause/revoke occurred, it refuses the send and leaves the attempt for reconciliation. Race between this check and non-transactional third-party HTTP is NOT fully eliminated.
- Added synthetic regression for lifecycle privacy, tenant/connection isolation, erroneous success transition on unknown send, scoped operations API and concurrent manual review one-winner. No full independent security audit or production-scale chaos certification is claimed.
- F3 remains BUILD_IN_PROGRESS, PR #1 Draft. NEXT: formal provider delivery status correlation and evidence-qualified reconciliation, broader race/chaos coverage for pause/revocation versus outbound, and remaining internal F3 tasks. External TLS/VPS/real WhatsApp/Evolution certification deferred to POST-CONSTRUCTION HOMOLOGATION and must not block internal development. No merge/deploy, production migration, real secrets, Kordena or Command governance changes.


2026-10-19 — F3 EVOLUTION DELIVERY CORRELATION / EVIDENCE-GATED REVIEW / PAUSE-REVOKE RACES — INTERNALLY CERTIFIED
- Certified functional HEAD `1955ce88609a2f16ac62b046392b778200f8f49b`: SaaS Foundation CI `39345728463` SUCCESS, PostgreSQL F3 Security Gate `39345728494` SUCCESS, Core↔Assistant Contract `39345728413` SUCCESS; 3/3 exact functional SHA gates GREEN.
- Evolution v2 per-instance webhook subscription now includes MESSAGES_UPDATE. Only an already authenticated FM-signed event (native edge also checks distinct per-instance bearer credential) can correlate a provider-generated outbound message reference with one and only one existing scoped queue attempt. It stores normalized monotonic sent/delivered/read states and SHA-256 digest of authenticated event bytes, no raw webhook body, no phone or message contents. Missing/ambiguous/foreign references and forged signatures cannot change delivery state. Migration `20261019_0015` adds nullable delivery status/digest/timestamp fields.
- Governed review now denies resolving a `reconcile_required` job that had a durable provider-send intent until it also has correlated authenticated provider delivery-status evidence; operator acknowledgement never retries or claims false delivery. Intent without provider ID/evidence intentionally REMAINS quarantined, requires a later separately authenticated evidence-acquisition pathway, not an invented delivery result.
- A locally DISABLED channel may ingest *status-only* callbacks for already attempted messages after credential authentication; all inbound and connection-open events remain denied, and REVOKED connections deny all callbacks. Added synthetic tests of signed/forged/regressive delivery events; cross-connection isolation; evidence-gated review; pause and revocation races injected between committed send intent and outbound HTTP. These are bounded internal regressions, not a proof of all possible race interleavings.
- Not resolved / separate internal security engineering: atomic pause/revoke vs external HTTP final micro-race remains (the final state check cannot transact with a third-party network call); no exactly-once provider guarantee. No independent adversarial review or production-scale chaos certification claimed. A provider-acknowledged callback establishes evidence accepted by the FM trust boundary, NOT a vendor-native cryptographic signature nor third-party verified delivery. Offline v2.3.7 contract is a candidate, not confirmed against installed server.
- F3 global remains BUILD_IN_PROGRESS; PR #1 DRAFT. No merge, deploy, real VPS keys, migrations outside disposable CI, production WhatsApp or Command universal policy changes. All external provider version/certificate/proxy/network/real WhatsApp homologations remain POST-100%-BUILD gates and must NOT block further software construction.


2026-10-19 — F3 UNCERTAIN PROVIDER EVIDENCE INVESTIGATION + POSTGRESQL SEND SERIALIZATION
- Functional implementation on Assistant Draft PR #1 follows certified `e1a4e11e509631059260cb713e498d7eb28e16fd`. Added read-only `POST /chat/findMessages/{instance}` adapter lookup with per-instance credential and strict exact outbound `key.id/fromMe` match. New tenant/unit-authorized `POST /v1/channels/whatsapp/qr/{connection_id}/operations/{message_id}/investigate` requires matching persisted operation ID; rejects foreign tenant/unknown or already investigated attempt. Bounded response and no-stored-plaintext hash from actual provider record. Migration `20261019_0016` stores ONLY candidate provider reference/hash/timestamp. Candidate evidence is explicitly INSUFFICIENT to prove that a previously ambiguous send created that message; it never changes reconcile_required, never retries, refunds, activates a channel or promotes delivery. No automatic approval if reference is missing. Live provider response compatibility remains an external homologation gate AFTER software build.
- Added PostgreSQL transaction-scoped `FOR UPDATE` of the integration connection row during actual bounded provider HTTP send in worker. The mutating `IntegrationRepository.update_connection` now takes the same row lock before pause/revoke/revision updates. This serializes send window against state transitions on PostgreSQL, so a pause/revoke must wait for an already-started provider send; it cannot cancel a network request already begun. SQLite's FOR UPDATE is a no-op; synthetic SQLite tests must not be advertised as proof of distributed locking. Transaction lock is deliberately released on both success and failure. All other integrations using this update path continue to use existing scope and protections.
- Internal regression coverage added for foreign operation, missing provider, no automatic replay, strict read-only provider query and connection revision/pause guard. Mocked provider evidence is only a candidate; no provider-side cryptographic signature or definitive link to the unknown send is invented.
- Last 3/3 internally GREEN functional checkpoint `9a7f683e1a1427c5fa9ea01a1002affe96c6af24`: SaaS Foundation `39346805176`, PostgreSQL security `39346805213`, Core bridge `39346805316` SUCCESS. Later test-only commit `ceaedb31ea6a941479f9f2337d32093745b1d433` needs own current-HEAD certification; do NOT label the documentation HEAD certified without verified workflows.
- F3 still BUILD_IN_PROGRESS, PR #1 Draft; no merge/deploy, external credentials, production migrations, Command universal policy changes. Further internal requirements: independent distributed PostgreSQL chaos/lock contention certification with actual overlapping HTTP send and pause/revoke, Command/Assistant/Core multi-process end-to-end, reviewed charge reconciliation and provider-specific token accounting. External Evolution real VPS/TLS/WhatsApp compatibility/homologation ONLY AFTER complete software construction.


2026-10-19 — F3 DISTRIBUTED POSTGRESQL SEND LOCK + FINOPS RECEIPT CLASSIFICATION / CROSS-COMPONENT CONTRACT TESTS
- Functional SHA `c4d0d1cac9ef417aa41734c76116886bd26b1aca`, exact-SHA GitHub Actions: SaaS Foundation CI #39347964117 SUCCESS, PostgreSQL F3 Core Bridge Security Gate #39347964105 SUCCESS, Core↔Assistant authenticated contract #39347964171 SUCCESS; 3/3 green. Testing was on isolated synthetic databases only.
- NEW actual PostgreSQL concurrent lock-contention test in `tests/saas/test_core_bridge_postgres.py`: two independent sessions/threads exercise `EvolutionInboundQueue.outbound_connection_guard` versus `IntegrationRepository.update_connection` for both DISABLED and REVOKED states. While send holds the DB row lock, terminal state mutation does not commit; after release it does, and stale revision cannot obtain send guard. This tests database ordering, NOT remote HTTP behavior or guaranteed WhatsApp cancellation.
- NEW `provider_usage_reconciliation.py` models FM-private provider/model/request usage receipts with exact nonnegative integer input/output token units and nonnegative finite Decimal USD cost; preserves unknown tokens/cost on uncertain execution, rejects conflicting confirmations and mismatched request/provider/model. No estimated token usage or monetary conversion is invented. This is a **pure internal classification/reconciliation primitive**, NOT an integrated durable accounting ledger or finished provider-specific billing. Core retains authoritative quota/charges. Tests cover uncertain/confirmed/duplicate/malformed receipts.
- NEW `tests/saas/test_f3_command_assistant_core_usage_contract.py` validates with mocked Core HTTP endpoints that requests carry authenticated service identity and fixed tenant/unit, and the trusted metering read rejects foreign-tenant response. This is a synthetic adapter contract test, **NOT** real end-to-end three-running-service Command↔Assistant↔Core certification.
- STILL OPEN INTERNAL F3 construction (does not depend on external homologation): integrate canonical provider usage receipts with Core's persistent economic ledger and provisionally reserved/uncertain usage recovery; versioned provider token usage rules with Core routing/fallback and platform-only cost visibility; perform real multi-process Command↔Assistant↔Core workflow with all three repositories, including corrupted/missing meter readings, tenant boundaries, revoked grants and payment/license attribution. Do NOT certify these from current contract tests.
- F3 BUILD_IN_PROGRESS; Assistant PR #1 DRAFT; no merge, deploy, production migrations, real secrets or real provider homologation. External Evolution/WhatsApp/proxy version tests deferred until 100%-built software.


2026-10-19 — F3 CORE CANONICAL USAGE RECONCILIATION INTEGRATION CHECKPOINT
- Companion FM Core Base branch `feat/ai-service-v1` functional SHA `0f4d6b5df71cb4f606dd40bdc1e68334827dfbe8`: `VerifiedProviderUsageReceipt` normalization and `QuotaReservations.reconcile_verified_provider_receipt` route verified token usage to the EXISTING canonical reserved/settled ledger, not another Assistant ledger. Exact-SHA Core AI Service CI run `39348829313` SUCCESS and Core PostgreSQL F3 gate `39348829333` SUCCESS.
- Only independently verified provider evidence and authorized fresh Command `VerifiedCommandAdmin` can settle a complete request bundle once, with persistent audit/JTI; timeout never implies free usage. Provider cost remains FM-private. Assistant-side provider reconciliation remains a validation primitive, never an independent accounting authority.
- Previously certified Assistant tests validate Core generation and quota read with synthetically mocked HTTP; NO actual three-process Command↔Assistant↔Core PostgreSQL E2E completed in this checkpoint. Provider evidence verification and Command recovery HTTP interface remain OPEN internal construction. External providers and credentials after 100% software construction.
- Assistant PR #1 Draft; no merge/deploy/real secrets; F3 BUILD_IN_PROGRESS.


2026-10-19 — F3 GOVERNED COMMAND RECOVERY BOUNDARY CONTINUATION
- Companion Core branch `feat/ai-service-v1` introduced signed human Command RS256 recovery orchestration, independently injected provider evidence verification and an opt-in internal recovery router. It is NOT mounted in the default Core app, because durable trusted provider evidence verification is still an INTERNAL CONSTRUCTION prerequisite. An opaque candidate reference or untrusted SHA-256 cannot autonomously settle a quota reservation.
- Functional Core SHA `9e8d01f4fc4b68e053825493597e810582d98c2e`, AI Service CI `39350176109` SUCCESS and PostgreSQL gate `39350176117` SUCCESS. New Core documentation HEAD is under its own gate; verify independently. Existing Assistant/SaaS quotas and plan pricing authority unchanged.
- Cross-process Command↔Assistant↔Core execution and independent durable evidence verifier still OPEN; synthetic Command JWT and Core recovery router unit tests are NOT a three-service E2E certification. Next internal work: protected evidence ingestion/verification and isolated multi-process test harness with tenant, plan revocation, reserve, settle, uncertain failure and retry/replay controls. External credentials/HTTPS/VPS/WhatsApp homologation deferred until software 100% built. Assistant PR #1 stays Draft; no merge/deploy.


2026-10-20 — F3 COMMAND ASSISTANT CORE RECOVERY CROSS-CODEBASE CERTIFICATION
- Companion FM Command corporate branch `feat/f3-command-core-bridge-governance` implements actual RS256 corporate human recovery signer and no-retry HTTPS internal client. Companion Core `feat/ai-service-v1` uses canonical quota ledger + optional RS256 Command recovery route backed by immutable HMAC-authenticated FM gateway evidence table `f3_0005`.
- Command Foundation Gate now pins Assistant source `ab30a89bfe4d15937b15ab0cc7ebb033030af803` and certified Core functional `3733c25e39d2c9df1203b4c9834604c7c96dbcb8`, exercising real Command Node signing, Assistant FastAPI ASGI identity revocation, Core deterministic quota reserve/reconciliation, persisted scoped evidence and duplicate-settlement rejection with synthetic secrets. CI completion must be checked against exact Command HEAD before claiming GREEN.
- These are **three codebases** connected through a test harness, NOT 3 independently running service processes over network with PostgreSQL shared across end-to-end calls. Command signer alone is NOT a deployment; provider-source verification beyond authenticated FM evidence gateway and opt-in recovery API activation remain internal construction gates. The authenticated FM gateway key only proves the internal attestation source, not the external provider invoice.
- No merge/deploy/production schema updates. Command plan/licensing and FM-only AI cost model unchanged. F3 BUILD_IN_PROGRESS. External provider homologation postponed until complete software construction.


2026-10-19 — F3 SOURCE-VERIFIED EVIDENCE + ISOLATED NETWORK GATE / MASTER RECONCILIATION
- Added a precise work-item matrix at `docs/governance/F3_INTERNAL_GATE_RECONCILIATION_2026-10-19.md`; read it before marking any F3/F9 phase complete. Companion Core `feat/ai-service-v1` now has `verified_signed_usage_source` with independently pinned Ed25519 signer, payload freshness, exact request/tenant/unit and upstream digest, plus `TrustedProviderEvidenceStore.record_verified_source`; a plain unsigned provider response is NEVER independently verified. Functional Core SHA `78885dc4383255678b7639163c9c33975dfb793a`, AI Service CI `39353714999` and PostgreSQL Security Gate `39353715201` SUCCESS.
- Companion Command Foundation Gate now launches separate Assistant and Core uvicorn instances and a Node Command signer subprocess on loopback, uses a disposable PostgreSQL database for Core, verifies signed scoped upstream fixture, then tests Command↔Assistant revocation, Core reservation, signed recovery and duplicate settlement. Exact Command functional commit and CI must be verified separately. This does not certify HTTPS, deployment, a permanently running Command HTTP server nor atomicity of two databases. External integration remains AFTER software completion.
- Master Schedule still lists internal build blockers: billing subscription outbox integration; signed/monotonic Assistant→Core quota projection/revocation connected to runtime; provider metering and fallback/cost reconciliation at every attempt; non-signing provider verification adapters and full license/payment attribution under failure; wider adversarial tests and final code reviews. F3 remains `BUILD_IN_PROGRESS` even if source and loopback network tests pass. Do not declare `BUILD_COMPLETE_INTERNAL_GREEN` early. No merge/deploy/real keys or production DB changes.


2026-10-19 — F3/F9 COMMERCIAL BILLING TO LICENSE TO CORE QUOTA INTERNAL GATE
- Companion FM Command branch `feat/f3-command-core-bridge-governance` added Drizzle `0014_vende_paid_license_outbox`, unique scoped paid-invoice outbox and canonical billing transaction that checks persisted payment, Vende product, FM-published quota plan and actual SaaS customer mapping, atomically enqueues delivery intent/audit. A single-shot signed /bind dispatch plus bounded worker drain denies duplicates and does not re-send after uncertain timeout/reversed invoice. No automatic customer-initiated quota elevation.
- The signing implementation was refactored into pure Node `assistant-plan-license-signer.ts`, using the exact existing HMAC contract. Cross-repository test `tests/f3_command_license_quota_journey.py` checks real Command signer -> existing Assistant `GovernedPlanLicenseBinding` -> live `LicensedQuotaManifestService` -> Core existing `SignedAssistantPlanAuthority`/`PlanUsageGuard`: atomic 180-token reserve, replay denial and next request fail-closed after license suspension. It is **synthetic SQLite for license/quota test**; Command's isolated PostgreSQL billing gate separately validates real paid invoice/outbox/claim.
- Command functional SHA `13621d4b6c103e857e98fd1e32fb42460cf8142a`: Foundation `39358095382` SUCCESS; Billing PG `39358095405` SUCCESS; F21 `39358095433` SUCCESS; Cognitive `39358095442` SUCCESS (4/4). This is not a provider-certified paid checkout nor distributed atomicity across Command/Assistant/Core. Core's preexisting signed authority/guard was preserved; a redundant parallel quota implementation was deleted after architectural inspection.
- Still `BUILD_IN_PROGRESS`: authorized worker/scheduler delivery, reconciliation of blocked intents, subscription grant/trial linkage, upgrade/downgrade/renewal effective periods, signed/revocable policy sync for each runtime path, official attempt-level provider metering/cost and remaining F3 gates. No merge/deploy, live credentials or production migrations; external homologations must not block further internal construction.


2026-10-20 — F3 COMMERCIAL LICENSING OUTBOX GOVERNED RECOVERY — INTERNAL CHECKPOINT
- Added Command-only signed read-only `POST /internal/v1/command/assistant-plans/binding-status` with replay-resistant HMAC and dedicated path domain, trusted corporate issuer and exact tenant/plan/revision plus persisted **operation nonce**. Only a matching `PlanBindingAuditORM` entry permits `bound_confirmed`; a pre-existing plan with no audit matching the original attempt is NOT delivery proof. No plan mutation, resend, extension or quota elevation occurs during the query. Synthetic tests cover exact nonce, foreign/forged signature and replay.
- Exact Assistant code HEAD `c41e640c5be8a7d5f6db3d9c505226f10de95ffd`: SaaS Foundation `39425361539`, PostgreSQL security `39425361484`, Core/Assistant contract `39425361529` all SUCCESS (3/3).
- FM Command companion PR #90 adds stable claimToken as signed original bind nonce, signed read-only status inquiry and CAS blocked-to-delivered only on exact scoped audit proof; also quarantines crashed `processing` claims without replay. Cross-runtime Command Node→Assistant status and PostgreSQL outbox tests added. Latest Command HEAD still has NO matching new workflow runs; DO NOT claim GREEN or merge on prior SHA. PR #90 remains Draft and GitHub reports mergeable=false.
- Still incomplete internal F3 commercial lifecycle: scheduled worker activation, human reconciliation when proof absent, renewal/upgrade/downgrade/expiration governance, authoritative cross-service revocation/fresh quotas in all runtime paths, provider/model/attempt financial reconciliation including audio and unknowns, WhatsApp recovery edge cases, independent security review and final whole-product regression. Existing Core guarded execution/pricing and QR queue controls must be reused, not recreated.
- F3 BUILD_IN_PROGRESS, F4 as scheduled only after its formal gates. No actual provider credentials, migrations in permanent DB, production deployment or external homologation. Do not promote BUILD_COMPLETE_INTERNAL_GREEN or merge until all gates green on exact HEAD.


2026-10-20 — F3 / EVOLUTION v2.3.7 — PREPARAÇÃO SEGURA DE INFRAESTRUTURA (INTERNA)
- Escopo único: criar modelo de Docker Compose para Evolution v2.3.7 **sem subir servidor, contato com WhatsApp ou credenciais reais**. A implantação no host é tarefa distinta e proibida nesta etapa.
- Arquivos: `deploy/evolution/docker-compose.yml`, `deploy/evolution/.env.example`, `deploy/evolution/README.md` e `tests/saas/test_evolution_deployment_template.py`. CI SaaS agora executa `docker compose --env-file deploy/evolution/.env.example -f deploy/evolution/docker-compose.yml config --quiet` (somente validação).
- Evolution oficial de referência `evoapicloud/evolution-api:v2.3.7`, sem `:latest`. Porta 8080 apenas em `127.0.0.1`; Redis/PostgreSQL sem portas publicadas; três volumes persistentes; healthchecks. A única entrada real futura exige proxy HTTPS/ACL governada. A chave global FM fica em variáveis do ambiente de destino, não na UI, webhook ou Git. Cada instância usa token exclusivo via código atual do Assistant.
- Validações: testes offline de isolamento, imagem fixa, volumes e placeholders; parser `docker compose config --quiet` no GitHub Actions. Consultar HEAD exato e conclusões dos workflows antes de elevar certificação. Sem live Docker, backups reais, rede, TLS, domínio, provider, segredo ou deploy.
- F3 ainda **BUILD_IN_PROGRESS**: arquitetura Command/Assistant/Core, ciclo de vida de licença/revogação, quotas, consumo, QR policy dinâmica e documentação final continuam pendentes. F4–F12 não certificados. `EXTERNAL_HOMOLOGATION_DEFERRED` permanece distinto do build.


2026-10-20 — F3 / C04 — QR CORPORATE SIGNED PROJECTION (INTERNAL BUILD)
- Earlier same-turn VPS reference and pinned Evolution v2.3.7 Compose tested in Foundation CI `39464503880` SUCCESS, Core bridge `39464503237` SUCCESS and PG gate `39464503105` SUCCESS for HEAD `2db75c11c0ef0738eb0e68dc488f96c0e5d61ec4`. That SHA precedes the new QR runtime code; do **not** inherit its test status.
- New unit: add `CommandQrDisplayPolicyService` with HMAC verification for `/internal/v1/command/whatsapp-qr/policy`, replay table, scoped versioned SQL projection `assistant_whatsapp_qr_display_policy` via Alembic `20261020_0017`, and read-only QR-panel cap updated without resetting QR age. Companion corporate signer/manual step-up sync code resides in a separate FMCC branch; OFF by default. No Evolution HTTP required for testing.
- Coverage: strict approved issuer, product, revision, actor, nonce anti-replay, signed body and freshness, no stale policy and UI 45s fallback. The receiver does not grant tenant entitlements or modify WhatsApp provider TTL. Policy data is read from source-of-truth Command and cached locally in Assistant only via authenticated publication.
- This increment remains BUILD_IN_PROGRESS until **all final-HEAD workflows** and independent review. No merge, production migration, real credentials, Docker deploy or external tests.


2026-10-20 — F3 / LICENSE CURRENT-STATUS PROOF GATE
- The signed Command `/binding-status` check previously confirmed only the historical bind audit and plan tuple, even after a license suspension/expiry or tenant deactivation. Corrected `GovernedPlanLicenseBinding.binding_status`: validate CURRENT tenant `active`, license `active|trial`, matching plan revision, non-expired current period, and persistent bind nonce before returning `bound_confirmed`. `TenantLicenseORM` selected FOR UPDATE on PostgreSQL to serialize against license state changes. Historical evidence by itself cannot reinstate an entitlement.
- Added synthetic SQLAlchemy tests: suspend, expire trial, disable tenant, paid period unset, resume valid period, fresh nonce anti-replay. No provider or real license mutation occurred.
- HEAD functional `419bc942cc9dc02d9125288ec5200a76aaa52bc9`: SaaS Foundation `39470488809` SUCCESS, Core↔Assistant `39470489181` SUCCESS, F3 PostgreSQL `39470489116` SUCCESS.
- Companion Core `7154020f45da7b82f847b7644ebaeb73f0565b76` (2/2 green) fixes guarded audio and exact provider-token integer parsing. Command PR #119 pins both to test signed corporate license status → Assistant current-state denial → Core quota denial in disposable integration.
- This is not native lifecycle C06 nor Command→Assistant automatic suspend/revoke, external provider attestation or whole-F3 closure. Keep F3 BUILD_IN_PROGRESS, external VPS/keys/Evolution/provider trials deferred, never change Kordena.


2026-10-20 — F3 / SIGNED SECURITY HOLD RECEIVER
- Novo `POST /internal/v1/command/assistant-plans/security-hold` aceita somente pacote FM assinado dentro de janela curta, inclui tenant/ator/request ID/plan revision/lease cutoff, step-up corporativo, nonce consumido atomicamente, transição ativa/trial → suspended e evidência append-only. Reusa HMAC/Command trust já existente e a proteção `PlanSyncNonceORM`; nenhum token de cliente pode invocar o método por si só.
- Migration aditiva `20261020_0018_license_security_hold_audit.py`: somente esquema para evidência de suspensão, sem backfill ou alteração financeira. Testes offline provam alteração, anti-replay, forja/escopo cruzado e política estritamente de segurança. `tests/saas/test_core_bridge_migration.py` atualizado para Alembic head 0018.
- Companion FMCC PR #121: produtor do envelope assinado e integração testada contra receptor real, **sem rota pública de envio**. Para concluir revogação E2E real ainda precisa prova da licença corrente/autorização FM e reconciliação de ACK, aprovações humanas quando financeiras e certificação conjunta. F3 geral BUILD_IN_PROGRESS; não afirmar live de ERP, IA, Evolution, VPS, gateway ou provider.
- Gates do HEAD desta atualização e review independente devem ser certificados antes de merge. Ambiente real sem deploy, migration, secret ou cliente afetado.

---

## 2026-10-20 — DECISÃO EXECUTIVA: AUTONOMIA POR BLOCO + MERGE AUTOMÁTICO COM GATE

**Fonte de autoridade:** proprietário da FM Tecnologia; seção 26 do Prompt Mestre, nova regra ao final de `AGENTS.md`. Substitui exigência de perguntar a cada tarefa e o bloqueio artificial de integração de um WP isolado só porque uma fase maior está IN_PROGRESS. **Não substitui** testes, revisão aplicável, proteção de branches ou autorização para produção.

### CURRENT apurado antes desta atualização documental

| Repositório / candidato | HEAD anterior verificado | CI no HEAD anterior | Gate para merge |
|---|---|---|---|
| Assistant PR #1 Draft | `2af123ab3f4df69d4573da0dc533e99c019b19ab` | SaaS CI, PostgreSQL F3, Core Bridge **3/3 SUCCESS** | F3 global ainda `IN_PROGRESS`; PR #1 monolítica com entregas incompletas, NÃO elegível só por 3/3 |
| FM Core PR #1 Draft | `6596b8aa338d960ba72c02fc09f99d0b81662d77` | AI Service e Quota PostgreSQL **2/2 SUCCESS** | Gate do conjunto ainda deve ser revisado; sem merge/deploy automático |
| FM Command PR #124 | `c0083aa8acb9fe2c668e9c078a0792ca78296f1b` | Billing PG, Cognitive, F21, Foundation **4/4 SUCCESS** | PR comercial tem ressalvas de conciliação/execução e PRs correlatas; sem merge prematuro |

Estes resultados pertencem aos **SHAs anteriores**, não validam automaticamente o novo HEAD documental do Assistant. A atualização aqui **não** afirma que F3 ou F4–F12 tenham encerrado.

### Motor de execução obrigatório

1. Reconciliar CURRENT de cada WP, consultar arquivo real, dependências, PRs atuais, `AGENTS.md` e evidência de CI. Reusar código do Kordena/Assistant/Core/Command quando compatível; não classificar uma funcionalidade como ausente só porque a fase formal não foi fechada.
2. Trabalhar no WP técnico mais próximo desbloqueado, com branch/PR pequena a partir de `main` atual sempre que possível. **Não** iniciar outra cadeia de dezenas de PRs dependentes sem reconciliação/integração.
3. Implementar → testar → revisar. Se RED: preservar prova, diagnosticar, corrigir, repetir. Quando o WP completo estiver 100% GREEN em HEAD exato, sem STOP, com revisão obrigatória e PR mergeable, **MERGE AUTORIZADO SEM NOVA CONSULTA**. Checar CI e SHA da `main` pós-merge; registrar `WP=MERGED`; iniciar o seguinte.
4. Se o WP tem `BLOCKED_EXTERNAL`, CI não executado, revisão realmente independente pendente, erro de segurança ou falta de prova interna, **NÃO MERGEAR**. Só avançar para construção independente ainda desbloqueada, mantendo a fase como `IN_PROGRESS`; não inventar aprovação.
5. Se integração/merge disparar deploy ou migration real, desligar gatilho via mudança governada e validada **antes** de qualquer merge; na impossibilidade, pedir autorização humana específica. Merge não equivale a release; homologações externas só após build 100% pronto.
6. Em cada avanço registrar WP, HEAD, PR, testes, CI, segurança, auditoria, merge e rollback. Na conclusão da fase, revalidar a matriz inteira e somente então promover `BUILD_COMPLETE_INTERNAL_GREEN`.

### Próxima unidade de trabalho interna, sem recomeçar fase

Continuar **F3** pelos gaps confirmados no `F3_INTERNAL_GATE_RECONCILIATION_2026-10-19.md`: vinculação billing→licença→quotas, reconciliação de consumo/custo/fallback por provider, regras de recuperação e testes adversariais entre Command/Assistant/Core. Considerar a evolução já presente nas PRs do Command antes de codificar, preservar correções existentes e separar código de verificação real de Asaas/Evolution. O primeiro WP escolhido deve ter critérios de aceite explícitos e gates proporcionais. F4–F12 seguem formalmente não encerradas, mas partes implementadas devem ser aproveitadas; sua extensão real será reavaliada por artefatos/testes antes de gerar trabalho novo.

**Autorização contínua:** código, correções, CI, commits, PRs e **merge de WPs internos elegíveis**. **Não autorizados implicitamente:** deploy, cutover, migrations em dados permanentes, credenciais reais, cobranças reais, gasto novo, alteração da política comercial/arquitetura nem homologação externa.


2026-10-20 — F3 / CORE RECOVERY STRICT CONTRACT — INTERNAL WP GREEN
- CURRENT reconciliado antes de editar: Core bb5983c605ffced58a767099a2778745a8a43216 já exigia JWT humano RS256 + chave técnica segregada e teste PostgreSQL concorrente, com CI 2/2 SUCCESS. Não repetir implementação anterior.
- Novo Core HEAD aea8523ce34c9011a1fc11802c94e8c43ece45f7: payload de recuperação extra=forbid/strict=True; revisão bool/string/float/null/zero/negativa e campos de custo/tokens/no_charge/principal/scope fornecidos pelo cliente são rejeitados com 422 antes de liquidação. CI Ruff inclui explicitamente recovery, evidence, source verifier, receipt e migration f3_0005; imports corrigidos sem mudança de autoridade.
- LOCAL: 268 passed, 7 skipped (PostgreSQL não configurado localmente), Ruff integral do workflow PASS, diff --check PASS. Primeira execução local teve 3 falhas de ambiente por socksio ausente no proxy; instalado suporte de transporte e repetida suíte completa, sem alterar código para mascarar falhas.
- REMOTO no HEAD Core exato: AI Service CI 39533829211 SUCCESS; PostgreSQL Security Gate 39533829250 SUCCESS (containers, migration e concorrência realmente executados). WP GREEN INTERMEDIÁRIO, sem declarar revisão independente ou F3 integral concluídas.
- AGENTS Core atualizado no mesmo commit. PR Core #1 continua Draft por conter outros WPs incompletos; nenhum merge/deploy, segredo real ou migration produtiva. Rollback deste WP: reverter aea8523 preservando o ledger. Próximo: concluir verificadores específicos e integração de consumo/custo por tentativa conforme matriz F3; homologações externas ficam para após build completo.
- Esta atualização documental do Assistant não herda o CI do Core; verificar seus próprios workflows no novo HEAD antes de promoção/merge.

2026-10-20 — AUDITORIA DE CONCLUSÃO E NOVO CRONOGRAMA 100% INTERNO
DECISÃO DO PROPRIETÁRIO:
- concluir integralmente software e validação interna antes de homologação real;
- tudo que depende de terceiro deve ser configurável e possuir adapters/fakes/testes agora;
- autonomia contínua para corrigir, integrar WPs verdes e avançar até a conclusão.
EVIDÊNCIA CURRENT:
- Assistant HEAD 503a92743e042f17af389a021e169b82c3e52c12: 3/3 workflows SUCCESS;
- Core HEAD aea8523ce34c9011a1fc11802c94e8c43ece45f7: 2/2 workflows SUCCESS;
- Command PR #124 HEAD 98650de9bd547ab592e4ce5baab438e4213b8349: 4/4 workflows SUCCESS;
- auditoria de arquivos, módulos, migrations, testes, cronogramas e PRs abertas executada nos três repositórios.
RESULTADO:
- F0/F1/F2 = GREEN_INTERNO;
- F3 e F9 = IN_PROGRESS com base substancial;
- F4/F5/F7/F12 = NOT_BUILT na linha SaaS canônica;
- F6/F8/F10/F14 = PARCIAL_REUTILIZÁVEL;
- F11 = IN_PROGRESS, sem auditoria final;
- F13 = EXTERNAL_HOMOLOGATION_DEFERRED; F15 produção bloqueada por autorização específica.
- Criado docs/governance/CRONOGRAMA_MESTRE_CONSTRUCAO_100_INTERNA.md com B0→B12, Definition of Done, autonomia e separação obrigatória de build/homologação.
- Corrigido Prompt Mestre: provider real deixa de bloquear gate interno F3 e passa formalmente para F13.
GATE: DOCUMENTAÇÃO/GOVERNANÇA EM VALIDAÇÃO DE CI NO NOVO HEAD.
PRÓXIMO PASSO:
- B0: reconciliar PRs/branches Command #114/#118–#124 e candidatas F3, fechar baseline canônica, executar gates cross-repo e integrar WPs verdes antes de construir lacunas F3/F9.

---

## 2026-10-22 — B1/F3 CURRENT reconciliado após integração F3/P01 (fonte: GitHub exato)

**Decisão humana mais recente:** Core + Assistant são UM ÚNICO produto VendeAtendeIA (nome de trabalho); o FM Command é o Control Plane corporativo independente e também SaaS separado. Manter estrutura/repositórios atuais até conclusão; não criar terceiro repositório nem reorganizar ou recriar bases neste ciclo. A matriz original dos repositórios era reutilizável, mas o proprietário determinou preservar o trabalho atual. Não confundir três repositórios técnicos com três SaaS.

**Source of truth:** cronograma B0–B11 aprovado em docs/governance/CRONOGRAMA_MESTRE_CONSTRUCAO_100_INTERNA.md; F3 e subset F9 continuam **IN_PROGRESS**, F4 não se inicia como fase final antes do gate B1. Não inventar BUILD_COMPLETE_INTERNAL_GREEN. Homologações reais de Asaas/Evolution/IA, credenciais, infraestrutura e tráfego externo continuam EXTERNAL_DEFERRED.

**FM Command (faabio3131/FM-CONTROL-CENTER):** depois da baseline P01 #152, PR #153 integrada `0c3c328929b067e1de8dfc0ed79cd1f182365364` (ciclo de licença e quotas compartilhadas); PR #154 integrada `3fc44b2cfac3832cc4c36f48c197a30ec3708e2e` (readback quota HMAC por unidade); PR #155 integrada `f163bf62b07ea61d9224fe1a5c8c40c085ed3db0` (pin Core cross-runtime e teste real); PR #156 integrada `2fb26e5449ad0cb2c00252428638717cdbfad7a9` (classificação de risco e allowlist); PR #157 integrada `a67702007538f5fc71ab683e298912d17d7d1d4b` (histórico de evidência P01); PR #158 integrada `759ffbc529733ed50f2c14fd58624896708664d7` (audit npm com retry fail-closed); PR #159 integrada `0aefac3c587a896366d9a635c31a10ba08d04249` (pin do Core realmente montado e testes end-to-end). PRs antigas #146,#147,#148,#149,#150 fechadas como superseded quando aplicável. A PR #159 teve 3/3 gates **APLICÁVEIS** GREEN em HEAD; Billing PG não foi disparado porque alterou somente workflow/docs. `main` idêntica ao SHA merge; workflows `push` pós-merge não foram retornados pelo conector e não são falsamente declarados verde.

**Core (faabio3131/FM-Core-Base-):** PR #3 integrada à branch candidata F3, seguida da PR #4 integrada em `c03ec3162d0fc55f061ce71cd5df2591c37ad919`, 2/2 gates AI Service + F3 PostgreSQL GREEN em HEAD e após merge no candidato. Foi corrigido bug real: router HMAC já existia isolado mas não estava montado em `create_app`. Agora registrado só com opt-in FM, segredo segregado, Assistant grant fresco, ledger Core transacional read-only e testes de runtime executados explicitamente na CI. A PR principal Core #1 permanece **Draft e não mergeada na main**, não é prova de produção real.

**Assistant (este repositório):** PR principal #1 permanece **Draft**, HEAD anterior `8279f3c10993ace277f713c01688a3412fc3e92a` (3/3 gates verdes no SHA anterior, *não no HEAD deste checkpoint*). Não duplicar lifecycle, licença, fontes de quota nem status que Command/Core já implementaram. O teste de três serviços real usa o Assistant nesse SHA pinado via Command Foundation e bancos descartáveis. Atualizar pin somente com CI cross-repo e análise de compatibilidade; o código de produção atual ainda não foi homologado externamente.

**Pendências internas F3/B1 NÃO eliminadas:** revisão de todo o pacote monolítico Core/Assistant Draft, metering/fallback por tentativa e reconciliação de uso/custo incerto de providers sem recibo criptográfico, ligação completa do consumo às rotas reais sob fault injection, auditoria adversarial end-to-end e CI final nos SHAs integrados. Depois B1 GREEN, iniciar B2/F4 Knowledge, B3/F5 Human Inbox, B4/F6 CRM, B5/F7 Cadências e demais blocos até B11.

**Padrão executor:** conferir primeiro este CURRENT + AGENTS + cronograma + PRs recentes; diferenciar código/testes internos de endpoints realmente ativados; preservar flags OFF e aprovação humana de deploy. Merges WPs sem STOP são autorizados por gate no SHA e revisão interna FM aceita pelo proprietário; não apresentar autoauditoria como independente de terceiro.


### 2026-10-22 — F4/WP1 preparação independente enquanto F3/F9 seguem em consolidação

Reutilização canônica KnowledgeDocumentORM/KnowledgeRepository + capability de conversação da própria Assistant. Implementado retriever lexical question-aware por tenant/unidade e active, Context Pack com id/timestamp de fonte, budget e ausência de match fail-closed, ativação opt-in OFF e testes SQLAlchemy de isolamento/ranking. Docs: F4_WP1_SCOPED_KNOWLEDGE_CONTEXT_PACK_2026-10-22.md. WP aguardará CI da branch e posterior merge elegível; F4 global IN_PROGRESS. A base grande Assistant PR #1 ainda Draft, não promover toda a PR só porque um WP novo passou. F13/credenciais/homologação real adiados. 


---

## 2026-10-22 — F4/WP2a: governança de revogação de fontes de conhecimento (candidata)

- **Status:** `IN_PROGRESS / PENDING_CI`; não promover F4 global nem B2 e não confundir com produção.
- Base da candidata Assistant F3/F4: `9ad92d0508911782bd4029a1ff94b4d2ede63682`, PR #1 ainda Draft e `main` não integrada.
- O WP preenche lacuna do ciclo de vida das fontes locais: revogação `knowledge.manage` por tenant/unidade, marcação `active=false`, auditoria append-only transacional e 204 idempotente; escopo estrangeiro 404. Sem migration adicional, sem credenciais nem providers.
- Teste adicional `tests/saas/test_f4_knowledge_revocation.py`: SQLAlchemy real descartável e HTTP autenticado; falha fechada, auditoria única, visibilidade revogada e negativos cross-tenant/unit.
- Contrato, limites e rollback: `docs/governance/F4_WP2A_KNOWLEDGE_REVOCATION_2026-10-22.md`.
- **Antes de merge:** verificar Ruff, teste SaaS, contrato Core↔Assistant e PostgreSQL-bridge completos no HEAD final, revisar diff/segredos/STOP, conferir `main` candidata e merge sem ativar deploy externo.
- B1/F3, FinOps F9, ingestão URL/arquivo, versionamento imutável/chunks, UI e certificação B2 continuam explicitamente pendentes. Homologações reais só após `BUILD_COMPLETE_INTERNAL_GREEN`.

### 2026-10-22 — F4/WP2 versionamento de fontes e chunks

Construção interna sobre o WP1 integrado no Assistant: schema aditivo 0020 com versões e chunks imutáveis por tenant/unidade, conteúdo original preservado por bootstrap obrigatório, ingestão textual versionada por CAS, API permissionada e flag OFF, testes Alembic/SQLAlchemy/HTTP negativos. Gate CI no SHA da PR; nenhuma migration real. F4 permanece IN_PROGRESS: retrieval por chunks, ingestão de arquivos/URLs, UI, fontes versionadas externamente e busca híbrida ainda faltam. Não promover PR monolítica #1 indevidamente.


## 2026-10-24 — F6 / CRM operacional — WP inicial PR #32

- Base: Assistant+Core unificados na main após F4 PR #31 merge 09e89bc50f55943fee4a7542359a0504af37ca76; nenhuma reconstrução de F4/F5.
- Construção: contatos com e-mail cifrado e deduplicação por HMAC em tenant/unidade; oportunidades em centavos e pipeline transacional CAS com auditoria; APIs humanas RBAC e interface /app/crm com CSP, no-store e navegação.
- DB: migration aditiva 20261024_0025 e teste em banco descartável. Sem migração externa, credenciais reais, deploy ou cobrança.
- Gate: testes de tenancy/PII/RBAC/CSRF/revisão/estados e 5 workflows aplicáveis no HEAD exato da PR #32. Merge somente após verde integral e revisão; CI pós-merge deve ser checada.
- F6 total continua IN_PROGRESS: integração conversa→lead, qualificação, propostas, analytics e demais capacidades continuam pendentes.


## 2026-10-24 — F6 CRM — vínculo conversacional, qualificação, propostas e atividades

- Main base PR #32 `836715269f530e077a6ed0fb1dd3d82fd80b4765`, 5/5 gates pós-merge verificados.
- PR #33: link conversa→contato/oportunidade por escopo e revisão CAS; score determinístico 0–100 separado de estágio; propostas cifradas com valor imutável herdado e aprovação interna sem envio/cobrança; timeline de ações cifradas e API/UI integradas.
- Migração `20261024_0026` aditiva, teste com base descartável, testes de segurança/tenant/revisão no SHA da PR; F6 global continua IN_PROGRESS.
- Somente merge com 5/5 CI verde no HEAD exato, revisão de diff e ausência de STOP; deploy, migração produtiva, homologação e credenciais reais permanecem diferidos.
