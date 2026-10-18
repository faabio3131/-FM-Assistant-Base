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
