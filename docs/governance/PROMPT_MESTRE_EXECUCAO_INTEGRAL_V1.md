# PROMPT MESTRE DE EXECUÇÃO INTEGRAL
## FM Assistant + Sales AI V1

**Versão:** 1.0  
**Data:** 2026-10-17  
**Status:** APROVADO PARA EXECUÇÃO POR FASES  
**Executor:** FM SaaS Builder / executor autorizado  
**Auditoria final:** FM Audit & Fix / Security / QA / DevOps conforme gates

---

# 0. MISSÃO

Concluir a transformação do FM Assistant Base em um SaaS Web comercial de **Atendimento + Vendas por IA**, aderente à Fundação Nova FM, sem reconstruções previsíveis e sem alterar o Kordena.

O produto deve poder receber novos assinantes sem mudança de código, com configurações, integrações, credenciais, planos e capabilities dirigidos por dados.

---

# 1. AUTORIDADES

Antes de qualquer implementação, ler e obedecer:

1. Documento Mestre Nova FM Tecnologia v2.0.
2. Padrões de Construção Nova FM.
3. `docs/governance/AUDITORIA_CONFORMIDADE_FUNDACAO_NOVA_FM_2026-10-17.md`
4. `docs/governance/SYSTEM_DESIGN_MASTER_V1.md`
5. ADR-001 a ADR-006.
6. CURRENT técnico dos repositórios.

Hierarquia:

```text
Documento Mestre
→ Padrões Nova FM
→ System Design/ADRs
→ contratos
→ implementação
→ evidência
```

---

# 2. REPOSITÓRIOS E REGRAS ABSOLUTAS

## FM Assistant Base

`faabio3131/-FM-Assistant-Base`

Linha canônica:

`src/fm_assistant`

## FM Core Base

`faabio3131/FM-Core-Base-`

## Kordena

`faabio3131/fm-ai-platform`

**KORDENA É READ-ONLY.**

É proibido no Kordena:

- commit;
- branch;
- PR;
- config;
- migration;
- banco;
- deploy;
- refactor;
- qualquer escrita.

Pode apenas ser consultado como referência.

---

# 3. DECISÕES JÁ APROVADAS — NÃO REDISCUTIR DURANTE EXECUÇÃO

1. V1 = Atendente + Vendedor IA.
2. Core obrigatório em staging/produção.
3. Integration & Credential Control Plane universal.
4. BYOK suportado.
5. `src/fm_assistant` é linha canônica.
6. Frontend Web comercial definitivo.

Se surgir necessidade real de alterar uma dessas decisões, parar e escalar; não modificar silenciosamente.

---

# 4. REGRA DE CONFIGURAÇÃO POR CLIENTE

**REGRA CONSTITUCIONAL DO PRODUTO:**

Novo cliente, nova unidade, nova chave, token, credencial, provider, integração, canal, política, plano ou configuração tenant-specific **não pode exigir alteração de código, branch ou deploy**.

Tudo deve ser resolvido por:

- dados;
- configuração;
- control plane;
- feature flags;
- entitlements;
- credential vault;
- adapters existentes.

Novo código só é aceitável quando surge **nova capability ou novo tipo de integração do produto**, não para cadastrar uma instância de cliente.

---

# 5. MÉTODO DE EXECUÇÃO

Para cada fase:

```text
CURRENT
→ Target
→ critérios de aceite
→ impacto
→ implementação
→ testes
→ diff review
→ segurança
→ evidência
→ atualização documental
→ gate
```

Se gate verde: avançar automaticamente para a próxima tarefa da mesma fase.

Se gate vermelho: corrigir e repetir.

Não pedir autorização a cada teste/correção interna já coberta por este Prompt.

Autonomia operacional autorizada:

- correções internas;
- criação/edição de código dentro da arquitetura aprovada;
- testes;
- migrations não destrutivas;
- commits;
- pushes;
- atualização de PR;
- repetição de gates;
- avanço de fase quando o gate anterior estiver GREEN 100%;
- **merge quando todos os critérios obrigatórios aplicáveis estiverem GREEN 100%**.

Bloqueio humano obrigatório permanece para:

- deploy/cutover de produção;
- migration de produção como parte do release;
- ativação de credenciais reais que efetivamente coloquem produção em operação;
- ação irreversível equivalente de produção;
- mudança material das decisões arquiteturais aprovadas.

A regra detalhada está no `AGENTS.md`.

---

# 6. FASE 0 — RECONCILIAÇÃO INSTITUCIONAL

## Objetivo

Eliminar dívida documental e arquitetural antes de expandir funcionalidade.

## Executar

- atualizar README;
- reconciliar `SAAS_ARCHITECTURE_V1.md`;
- reconciliar `WHATSAPP_CHANNEL_V1.md`;
- reconciliar `CORE_INTEGRATION_V1.md`;
- registrar System Design/ADRs;
- criar inventário Current/Target;
- registrar Definition of Done;
- declarar linha canônica;
- definir estratégia de arquivamento do baseline Kordena;
- registrar Assistant/Core na fonte organizacional Nova FM quando acesso local estiver disponível;
- preparar handoff auditável.

## Gate F0

- nenhuma documentação vigente contradiz Current;
- ADRs aprovados presentes;
- sem Target apresentado como Current;
- PRs continuam Draft;
- CI atual verde.

---

# 7. FASE 1 — IDENTITY, RBAC, TENANT E LICENSE CONTROL PLANE

## Objetivo

Criar autoridade comercial de identidade/tenant/licenciamento antes do frontend.

## Implementar

### Identity

- user;
- credential/login;
- session;
- invitation;
- recovery;
- status.

### RBAC

Papéis iniciais:

- OWNER;
- ADMIN;
- MANAGER;
- SALES_AGENT;
- SUPPORT_AGENT;
- VIEWER.

Criar permissions explícitas; não usar papel como autorização mágica.

### Tenant

- organization/tenant;
- units;
- memberships;
- active unit;
- tenant lifecycle.

### License/Entitlements

- plan reference;
- trial;
- subscription status;
- features;
- quotas;
- capabilities;
- feature flags.

## Segurança

- password hashing/provider auth aprovado;
- session security;
- tenant isolation;
- server-side authorization;
- revoke session;
- no shared admin password;
- no global `X-Admin-Key` como auth comercial final.

## Gate F1

- testes unit/integration;
- tenant cross-access negativo;
- RBAC negative paths;
- migrations verdes;
- CI verde;
- security review de auth.

---

# 8. FASE 2 — INTEGRATION & CREDENTIAL CONTROL PLANE

## Objetivo

Transformar integrações em configuração data-driven universal.

## Modelo

Criar:

- integration_connections;
- integration_providers;
- credential_references;
- capability_bindings;
- validation_results;
- connection_events.

## Lifecycle

```text
DRAFT
→ VALIDATING
→ ACTIVE
→ DEGRADED
→ DISABLED
→ REVOKED
```

## Credential Vault

Suportar:

- FM-managed;
- tenant-managed/BYOK;
- encrypted/secret reference;
- version;
- rotation;
- revoke;
- expiration;
- audit.

Nunca retornar segredo em GET/list.

## Migrar WhatsApp

O comportamento atual deve ser preservado:

- HMAC;
- channel_id;
- idempotency;
- sender hash;
- audio;
- reconcile_required;
- no blind retry.

## Gate F2

- tenant isolation;
- connect/validate/activate/rotate/revoke;
- secret non-disclosure tests;
- WhatsApp regression 100% verde;
- migration test;
- CI/security green.

---

# 9. FASE 3 — FM CORE PRODUCTION CONTROL PLANE

## Objetivo

Transformar o Core multimodelo atual em serviço comercial governado.

## Implementar

- provider catalog;
- model catalog;
- capability map;
- route policy persistence;
- priority;
- fallback;
- provider health;
- circuit breaker;
- timeout policy;
- usage persistence;
- FinOps persistence;
- price snapshots persistentes;
- quota hooks;
- BYOK resolution;
- FM-managed resolution;
- audit;
- observability.

## Produção

Assistant comercial deve recusar backend cognitivo diferente de `core`, salvo exceção explícita.

## Homologar

Pelo menos:

- Gemini;
- um provider OpenAI-compatible real.

NVIDIA/Nemotron e Anthropic entram somente com capability/adapter e teste real aprovado.

## Gate F3

- provider real homologado;
- fallback real ou sandbox representativo aprovado;
- usage/cost persistido;
- secrets externos seguros;
- health/circuit breaker testados;
- CI green.

---

# 10. FASE 4 — KNOWLEDGE & RETRIEVAL

## Objetivo

Evoluir knowledge simples sem quebrar Conversation Engine.

## Implementar

- documents;
- URLs;
- file ingestion;
- metadata;
- chunking;
- version;
- activate/deactivate/delete;
- provenance;
- hybrid retrieval quando justificado;
- reranking;
- Context Pack mínimo;
- tenant isolation;
- retrieval audit.

Embeddings não são obrigatórios se busca híbrida equivalente atender melhor.

## Gate F4

- relevance tests;
- tenant isolation;
- no cross-tenant retrieval;
- no raw secret/PII leak;
- insufficient-context behavior;
- regression conversation.

---

# 11. FASE 5 — HUMAN INBOX

## Implementar

- queue;
- assignment;
- takeover;
- transfer;
- notes;
- SLA fields;
- return-to-AI;
- operator presence/status;
- conversation locks/concurrency;
- audit.

IA não responde enquanto humano detiver takeover ativo.

## Gate F5

- concurrency;
- takeover;
- transfer;
- return-to-AI;
- unauthorized operator;
- cross-tenant negative;
- audit green.

---

# 12. FASE 6 — SALES/CRM PACK

## Objetivo

Transformar atendente em vendedor governado.

## Entidades

- Contact/Lead;
- Opportunity;
- Pipeline;
- Stage;
- Qualification;
- Score;
- Activity;
- FollowUp;
- Appointment;
- Proposal/Quote;
- Conversion;
- LossReason.

## Regras

IA pode:

- interpretar;
- sugerir;
- classificar;
- resumir;
- recomendar próxima ação.

Serviços determinísticos executam:

- criar/alterar oportunidade;
- mover estágio;
- agendar;
- criar follow-up;
- registrar proposta;
- registrar conversão.

Ações mutáveis exigem autorização, idempotência e audit.

## Gate F6

- pipeline state machine;
- tenant isolation;
- duplicate event handling;
- qualification contract;
- deterministic mutation service;
- negative auth;
- audit.

---

# 13. FASE 7 — FOLLOW-UP / CADENCES / AGENDA

## Implementar

- follow-up rules;
- cadence;
- scheduler/jobs;
- retries;
- idempotency;
- opt-out;
- quiet hours;
- appointment slots;
- reminders;
- dead-letter/recovery;
- audit.

Nenhum job pode desaparecer silenciosamente.

## Gate F7

- duplicate prevention;
- retry;
- DLQ/recovery;
- opt-out;
- scheduling correctness;
- tenant isolation.

---

# 14. FASE 8 — FRONTEND WEB COMERCIAL

## Regra

Construir **a UI definitiva**, não painel provisório.

## Módulos

- auth;
- onboarding;
- dashboard;
- persona;
- knowledge;
- integrations;
- WhatsApp;
- inbox;
- leads/contacts;
- pipeline;
- follow-ups;
- agenda;
- analytics;
- team/RBAC;
- usage/plan/billing;
- settings.

## UX

- desktop/notebook/mobile quando aplicável;
- loading;
- empty;
- success;
- partial;
- error;
- unavailable;
- unauthorized;
- forbidden;
- accessible;
- design system;
- premium.

## Gate F8

- lint;
- typecheck;
- build;
- component tests;
- auth tests;
- accessibility;
- responsive checks;
- critical E2E.

---

# 15. FASE 9 — BILLING, PLANS, QUOTAS E USAGE

## Implementar

- plans;
- entitlements;
- subscription;
- trial;
- usage ledger;
- message/audio/token/storage/users/integrations quotas;
- overage policy;
- upgrade/downgrade;
- suspension policy;
- billing provider adapter.

Separar:

- customer billing;
- AI FinOps;
- provider cost;
- margin.

## Gate F9

- deterministic usage;
- duplicate event protection;
- webhook idempotency;
- billing tenant isolation;
- provider reconciliation;
- audit.

---

# 16. FASE 10 — OBSERVABILITY / SRE

## Implementar

- structured logging;
- redaction;
- metrics;
- readiness;
- liveness;
- dependency health;
- alerts;
- tracing quando útil;
- dashboards;
- incident events;
- provider/integration health;
- SLO candidates.

## Gate F10

Health/readiness deve detectar indisponibilidade de dependência crítica.

---

# 17. FASE 11 — SECURITY HARDENING

Executar auditoria dedicada:

- auth;
- RBAC;
- tenant;
- sessions;
- API;
- PII;
- secrets;
- integration config;
- webhooks;
- replay;
- abuse;
- rate limits;
- dependency/supply chain;
- logs;
- migrations;
- destructive actions;
- billing;
- prompt/tool injection;
- Core authority boundary.

STOP:

- cross-tenant;
- auth bypass;
- privilege escalation;
- secret exposure;
- relevant data leak;
- critical fraud;
- corruption;
- unauthorized destructive action.

## Gate F11

Nenhum STOP aberto.

---

# 18. FASE 12 — BACKUP / RESTORE / INCIDENTS

Implementar e comprovar:

- PostgreSQL backup;
- retention;
- restore;
- restore smoke;
- recovery runbook;
- incident runbook;
- rollback;
- credential compromise runbook;
- provider outage runbook.

## Gate F12

Restore precisa ser testado; backup existente não basta.

---

# 19. FASE 13 — STAGING / HOMOLOGAÇÃO

Configurar:

- cloud staging;
- PostgreSQL;
- HTTPS;
- managed secrets;
- Core;
- Assistant;
- frontend;
- Meta sandbox/real controlled test;
- provider real;
- observability.

Executar:

- migrations;
- critical E2E;
- real WhatsApp text;
- real WhatsApp audio;
- handoff;
- CRM journey;
- follow-up;
- billing sandbox;
- tenant isolation;
- failover;
- smoke.

Nenhum deploy de produção nesta fase.

---

# 20. FASE 14 — FINAL COMMERCIAL READINESS

Checklist:

- Product/Market document;
- pricing;
- onboarding;
- support;
- terms/privacy/LGPD interfaces quando aplicável;
- documentation;
- runbooks;
- status page/incident flow se aprovado;
- sales materials;
- operational ownership;
- final security gate;
- final QA;
- final SRE;
- release certification.

Somente então pode ser usado o estado:

**PRONTO PARA PRODUÇÃO**

Produção real ainda exige autorização explícita.

---

# 21. FASE 15 — MERGE / PRODUÇÃO

## Merge

**MERGE ESTÁ PRÉ-AUTORIZADO** quando todos os gates obrigatórios aplicáveis estiverem
`GREEN` 100%, sem STOP condition, com CI verde, diff revisado, documentação/tracker
atualizados e PR mergeable.

Após merge:

- verificar CI pós-merge;
- registrar SHA;
- verificar regressões;
- atualizar o tracker.

Se qualquer gate estiver RED, BLOCKED_EXTERNAL, ausente ou contraditório, merge é proibido.

## Produção

**DEPLOY/CUTOVER DE PRODUÇÃO NÃO ESTÁ PRÉ-AUTORIZADO.**

Exigir autorização humana explícita para:

- deploy em produção;
- migration de produção como parte do release;
- domínio/cutover/tráfego;
- ativação de credenciais reais que coloquem produção em operação;
- produção comercial.

---

# 22. EVIDÊNCIA OBRIGATÓRIA POR FASE

Registrar:

- objetivo;
- Current;
- mudanças;
- arquivos;
- migrations;
- testes;
- resultados;
- CI;
- riscos;
- pendências;
- commit;
- PR;
- gate final.

Não declarar concluído sem evidência.

---

# 23. PROIBIÇÕES

- tocar no Kordena;
- hardcode por cliente;
- segredos no código;
- segundo sistema de tenant;
- segundo motor conversacional;
- UI descartável conhecida;
- provider direto no domínio;
- bypass do Core comercial;
- regra crítica só no frontend;
- teste removido para passar CI;
- migration destrutiva improvisada;
- Target tratado como Current;
- merge/deploy sem autorização;
- declarar homologado sem prova.

---

# 24. CONDIÇÃO DE CONCLUSÃO DO PROMPT

O Prompt Mestre só está concluído quando:

1. F0–F14 estão verdes com evidência;
2. nenhuma STOP condition permanece aberta;
3. documentação reflete Current;
4. produto está formalmente classificado como **PRONTO PARA PRODUÇÃO**;
5. merge pode ocorrer automaticamente quando 100% dos gates obrigatórios estiverem verdes;
6. deploy/produção continuam aguardando autorização humana específica.

Até lá, o executor deve avançar fase a fase dentro das autorizações deste documento, corrigindo gates vermelhos antes de progredir.

# 25. ADITIVO EXECUTIVO — BUILD FIRST (DECISÃO DE 18/10/2026)

Esta instrução posterior e expressa do proprietário **altera a ordem de execução**, mantendo os objetivos e a integridade de todas as fases.

1. **Primeiro concluir 100% da construção do software:** executar autonomamente F0–F12, construir também todas as peças internas de F14 (interfaces, onboarding, runbooks, segurança, QA, operações e materiais que não dependem de prova real) e concluir os testes executáveis com dados fictícios e bancos descartáveis.
2. **Depois homologar externamente:** as etapas F13 de cloud staging, terceiros, WhatsApp, credenciais, Vault, gateway, TLS, DNS e demais provas reais passam para a fase única de homologação de conclusão, executada **após** BUILD_COMPLETE_INTERNAL_GREEN. A certificação comercial real e o cutover continuam dependentes de evidência e consentimento.
3. **Sem paralisia de execução:** ausência de conta externa, chave, provedor, ambiente de produção ou aprovação de parceiro é `EXTERNAL_HOMOLOGATION_DEFERRED`; registrar e avançar para a próxima tarefa de software. Não tratar como GREEN nem como impeditivo da construção ou do próximo módulo/fase técnica.
4. **Gates internos continuam obrigatórios:** lint, typecheck, build, testes, segurança, RBAC, isolamento, contratos, migrations em banco descartável, concorrência PostgreSQL, E2E simulados, CI e documentação devem ficar verdes antes de declarar construção completa.
5. **Merge:** aplicar autorização prévia somente quando gates internos do conjunto a integrar estiverem completos e quando não houver publicação, deployment ou migração automática decorrente do merge. Caso isso não esteja demonstrado, manter PR isolada; não confundir merge de código com lançamento.
6. **Estados distintos e verificáveis:** `BUILD_IN_PROGRESS`, `BUILD_COMPLETE_INTERNAL_GREEN`, `EXTERNAL_HOMOLOGATION_DEFERRED` e `REAL_HOMOLOGATION_APPROVED`. Apenas o último, com demais gates finais e autorização humana, permite declarar o produto pronto para uso real.
7. **Autonomia integral:** implementar, corrigir e prosseguir pelo cronograma sem pedir confirmação para tarefas internas; interromper apenas por risco crítico ou ação real irreversível que exija consentimento específico.

Referência canônica: `docs/governance/F3_BUILD_FIRST_EXTERNAL_HOMOLOGATION_LAST_2026-10-18.md`. Nenhum requisito funcional, proteção de dados, autoridade humana ou controle de segurança foi removido; somente a dependência temporal de provas externas foi adiada.
