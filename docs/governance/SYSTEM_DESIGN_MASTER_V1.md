# System Design Mestre — FM Assistant + Sales AI V1

**Versão:** 1.0  
**Data:** 2026-10-17  
**Status:** APROVADO PARA EXECUÇÃO  
**Produto:** FM Assistant + Sales AI V1  
**Arquitetura-alvo:** plataforma SaaS multi-tenant de atendimento e vendas por IA  
**Normas superiores:** Documento Mestre Nova FM v2.0 + Padrões de Construção Nova FM

---

## 1. Objetivo

Transformar a fundação atual do FM Assistant Base em um produto comercial Web-first, cloud-first, multi-tenant e governado, capaz de atender e vender por múltiplos canais, começando por WhatsApp, sem reconstrução posterior e sem exigir alteração de código para onboarding/configuração de novos clientes.

O produto V1 deve combinar:

- atendimento conversacional;
- conhecimento empresarial;
- WhatsApp oficial;
- áudio;
- handoff humano;
- CRM/lead;
- pipeline comercial;
- qualificação;
- follow-up;
- proposta/CTA/agendamento;
- conversão;
- painel Web;
- billing/entitlements;
- FM Core obrigatório para cognição.

---

## 2. Princípios obrigatórios

1. **Novo cliente é configuração/dados, nunca código.**
2. **Nenhuma chave, token ou credencial específica de assinante pode exigir commit/deploy.**
3. **Toda cognição comercial em staging/produção passa pelo FM Core Base.**
4. **IA não substitui autoridade determinística.**
5. **Tenant/unidade são escopo autoritativo e nunca dados decorativos.**
6. **Secrets não retornam em APIs nem ficam em frontend/repositório.**
7. **`src/fm_assistant` é a linha canônica do produto.**
8. **Kordena é somente referência/read-only.**
9. **Frontend comercial será a linha final, não protótipo descartável.**
10. **Current e Target devem permanecer explicitamente separados.**
11. **Falha crítica é fail-closed.**
12. **Toda mutação relevante deve ser auditável e idempotente quando aplicável.**

---

## 3. CURRENT confirmado

### FM Assistant Base

Já existe:

- FastAPI;
- SQLAlchemy;
- Alembic;
- credenciais tenant API;
- persona por tenant/unidade;
- knowledge textual simples;
- conversation engine;
- histórico;
- handoff state;
- WhatsApp Meta adapter;
- webhook challenge;
- assinatura HMAC;
- inbound idempotency;
- outbound safe handling;
- áudio;
- secret encryption do canal;
- CoreModelGateway;
- CoreAudioTranscriber;
- auditoria;
- testes SaaS;
- CI.

### FM Core Base

Já existe:

- AIModelRouter;
- capability routing;
- prioridade;
- fallback;
- Gemini adapter;
- OpenAI-compatible adapter;
- texto;
- transcrição/áudio;
- metering em memória;
- pricing/cost/FinOps contracts;
- security/event/runtime foundation;
- API interna autenticada;
- testes;
- CI.

### Ainda não existe comercialmente

- login humano/sessão;
- RBAC completo;
- painel Web final;
- Control Plane de cliente/licença;
- Integration Fabric universal;
- Credential Vault comercial;
- CRM/Sales Pack;
- billing;
- quotas;
- RAG avançado;
- console humano;
- observabilidade completa;
- staging/homologação real;
- backup/restore;
- Gate Final de Segurança.

---

## 4. TARGET arquitetural

```text
                              ┌───────────────────────────────┐
                              │        FM COMMAND             │
                              │ visão executiva / operação FM │
                              └──────────────┬────────────────┘
                                             │ eventos/métricas
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FM ASSISTANT + SALES AI                              │
│                                                                             │
│  Web App / WhatsApp / API / futuros canais                                 │
│          │                                                                  │
│          ▼                                                                  │
│  Identity + Session + RBAC                                                  │
│          │                                                                  │
│          ▼                                                                  │
│  Tenant / Unit / License / Entitlements Control Plane                       │
│          │                                                                  │
│   ┌──────┼────────┬──────────────┬──────────────┬────────────────────┐       │
│   ▼      ▼        ▼              ▼              ▼                    ▼       │
│ Persona Knowledge Conversation  Human Inbox   Sales/CRM       Integration   │
│                     Engine                         Pack           Fabric     │
│                       │                             │               │         │
│                       └──────────────┬──────────────┘               │         │
│                                      ▼                              │         │
│                            Deterministic Services                    │         │
│                                      │                              │         │
└──────────────────────────────────────┼──────────────────────────────┼─────────┘
                                       │ cognitive request            │ providers
                                       ▼                              ▼
                         ┌────────────────────────┐          ┌──────────────────┐
                         │      FM CORE BASE      │          │ Credential Vault │
                         │ routing/fallback/cost  │          │ secret refs      │
                         └────────────┬───────────┘          └──────────────────┘
                                      │
                          ┌───────────┼────────────┐
                          ▼           ▼            ▼
                       Gemini       OpenAI      NVIDIA/otros
```

---

## 5. Bounded contexts / módulos

### 5.1 Identity & Access

Responsável por:

- usuários humanos;
- login;
- sessões;
- MFA/passkey quando aprovado;
- recuperação;
- convites;
- RBAC/ABAC;
- papéis;
- permissões;
- escopo tenant/unidade.

Papéis iniciais candidatos:

- OWNER;
- ADMIN;
- MANAGER;
- SALES_AGENT;
- SUPPORT_AGENT;
- VIEWER.

Nenhum papel deve herdar autoridade implícita não documentada.

### 5.2 Tenant & License Control Plane

Autoridade canônica para:

- tenant;
- organização;
- unidade;
- licença;
- plano;
- status;
- trial;
- entitlements;
- feature flags;
- quotas;
- lifecycle.

### 5.3 Persona

Configuração por tenant/unidade:

- nome público;
- idioma;
- tom;
- instruções;
- políticas conversacionais;
- status.

### 5.4 Conversation Engine

Autoridade para:

- conversa;
- participantes;
- mensagens;
- estado;
- histórico;
- channel binding;
- correlation;
- lifecycle.

Estados mínimos:

- OPEN;
- HUMAN_HANDOFF;
- CLOSED.

Estados futuros devem entrar por migration/ADR, não ad hoc.

### 5.5 Knowledge

V1 atual simples; Target:

- documento;
- URL;
- arquivo;
- chunking;
- metadata;
- versionamento;
- proveniência;
- retrieval;
- reranking;
- expiração/inativação.

O modelo nunca deve receber dados de outro tenant.

### 5.6 Human Inbox

Responsável por:

- fila;
- assignee;
- status;
- SLA;
- takeover;
- transfer;
- notes;
- return-to-AI;
- audit.

### 5.7 Sales/CRM Pack

Entidades mínimas:

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

LLM pode interpretar, classificar e sugerir. Serviços determinísticos alteram estado.

### 5.8 Integration Fabric

Modelo universal para qualquer integração de cliente.

Entidades:

- IntegrationConnection;
- IntegrationProvider;
- CredentialReference;
- CapabilityBinding;
- ValidationResult;
- ConnectionStatus;
- RotationMetadata.

Lifecycle:

```text
DRAFT → VALIDATING → ACTIVE → DEGRADED → DISABLED → REVOKED
```

Operações:

- connect;
- validate;
- activate;
- update non-secret config;
- rotate secret;
- revoke;
- disconnect;
- health test.

WhatsApp deve migrar para este fabric sem perder comportamento certificado.

### 5.9 Credential Vault

Regras:

- valor secreto nunca volta em GET;
- banco guarda referência/ciphertext aprovado, não segredo exposto;
- rotação auditável;
- access least privilege;
- secret version;
- revogação;
- expiração quando aplicável;
- plataforma e tenant separados.

Fontes:

- FM-managed secret;
- tenant-managed secret (BYOK);
- provider OAuth/token;
- future external secret manager.

### 5.10 Billing & Entitlements

Responsável por:

- plano;
- assinatura;
- trial;
- status;
- features;
- quotas;
- usage;
- overage;
- suspensão governada;
- upgrade/downgrade.

Billing não deve ser confundido com FinOps de IA.

### 5.11 Observability

Padrões:

- structured logs;
- correlation ID;
- request ID;
- tenant-safe telemetry;
- metrics;
- health/liveness/readiness;
- provider health;
- integration health;
- alerts;
- tracing quando justificado;
- audit trail.

PII/secrets devem ser redigidos.

---

## 6. FM Core Base

### 6.1 Papel

FM Core Base é a autoridade de:

- roteamento cognitivo;
- seleção de provider/modelo por capability;
- fallback;
- metering;
- custo;
- model policy;
- provider health;
- future competence map.

Não é autoridade para:

- mutar CRM diretamente;
- aprovar pagamento;
- alterar permissão;
- criar usuário;
- revogar segredo;
- executar integração crítica fora de contrato.

### 6.2 Produção

Em staging/produção:

- backend cognitivo normal = `core`;
- adapter direto de provider no Assistant é proibido salvo exceção formal;
- service-to-service auth obrigatório;
- service key atual deve evoluir para mecanismo rotacionável/managed secret;
- timeout/circuit breaker/backoff devem ser governados.

### 6.3 BYOK

BYOK é suportado como Target.

A decisão de usar:

- provider FM;
- provider tenant;

é política/entitlement, não branch de código.

O Core recebe uma rota resolvida por configuração governada, sem expor segredo ao Assistant.

---

## 7. Dados e tenancy

Toda tabela comercial sensível deve possuir ownership explícito.

Padrão:

- tenant_id obrigatório;
- unit_id quando entidade for unit-scoped;
- foreign keys;
- índices compostos;
- constraints;
- timestamps;
- audit metadata conforme criticidade.

Cross-tenant access = STOP DE PRODUÇÃO.

O frontend nunca é a única barreira de tenancy.

---

## 8. APIs

Regras:

- versionamento `/v1`;
- contracts Pydantic/OpenAPI;
- erros estruturados;
- correlation ID;
- rate limits;
- request size limits;
- idempotency key em mutações que exigirem;
- authn/authz server-side;
- nenhuma resposta com secrets;
- paginação;
- filtros autorizados;
- compatibility policy.

---

## 9. Canais

### WhatsApp V1

Preservar:

- Meta Cloud API;
- HMAC signature;
- challenge;
- channel binding;
- idempotency;
- sender HMAC;
- audio;
- no blind POST retry;
- reconcile_required;
- handoff.

Evoluir:

- templates;
- opt-in/opt-out;
- media;
- status delivery/read;
- provider health;
- quotas;
- billing/metering;
- connection lifecycle no Integration Fabric.

### Webchat

Construir como canal do mesmo Conversation Engine.

Não criar segundo motor conversacional.

---

## 10. Frontend comercial

Módulos mínimos:

1. Login/recuperação.
2. Onboarding.
3. Dashboard.
4. Persona.
5. Knowledge.
6. Integrações.
7. WhatsApp.
8. Inbox humano.
9. Contatos/Leads.
10. Pipeline.
11. Follow-ups.
12. Agenda.
13. Analytics.
14. Equipe/RBAC.
15. Plano/Uso/Billing.
16. Configurações.

Requisitos:

- responsivo;
- acessível;
- estados loading/empty/error/forbidden;
- design system;
- premium;
- sem regras críticas duplicadas;
- sem secrets no browser.

---

## 11. Segurança

Obrigatório antes de produção:

- authn/authz;
- tenant isolation;
- RBAC;
- CSRF quando aplicável;
- secure cookies quando houver sessão;
- secret scan;
- dependency scan;
- rate limiting;
- abuse controls;
- input limits;
- webhook replay/idempotency;
- PII policy;
- retention;
- audit sanitation;
- adversarial tests;
- Gate Final de Segurança independente.

---

## 12. Observabilidade e operação

Readiness deve verificar:

- app;
- database;
- Core;
- configured critical integrations.

Health superficial que retorna 200 com dependência crítica indisponível não é readiness.

Runbooks necessários:

- deploy;
- rollback;
- migration;
- provider outage;
- Meta outage;
- credential rotation;
- tenant lock;
- backup/restore;
- incident.

---

## 13. Ambientes

Mesma linha arquitetural:

- development;
- test;
- preview;
- staging;
- production.

Diferenças somente de configuração, credenciais, endpoints, capacidade e políticas.

Produção:

- PostgreSQL;
- managed secrets;
- HTTPS;
- observability;
- controlled migrations;
- backups;
- restore test;
- health checks.

---

## 14. CI/CD alvo

Gates progressivos:

- lint;
- typecheck;
- unit;
- integration;
- contract;
- migration;
- tenant isolation;
- security;
- secret scan;
- dependency scan;
- frontend test;
- build;
- E2E critical;
- smoke;
- deployment verification.

Gate vermelho bloqueia progressão.

---

## 15. Definition of Done comercial

O produto só pode ser chamado **COMERCIALMENTE DISPONÍVEL** quando:

- System Design e ADRs estão reconciliados;
- backend, DB e migrations certificados;
- frontend final funcional;
- auth/RBAC certificados;
- tenant isolation certificado;
- Core production path certificado;
- integrations control plane funcional;
- WhatsApp real homologado;
- providers reais homologados;
- CRM/Sales Pack funcional;
- human inbox funcional;
- billing/entitlements funcional;
- quotas/rate limits ativos;
- observability/alerts ativos;
- backup + restore comprovados;
- security gate aprovado;
- staging E2E verde;
- smoke pós-deploy verde;
- documentação/runbooks atualizados;
- release formal aprovado.

---

## 16. Estratégia de evolução

Nenhuma reescrita total.

Fases incrementais descritas no `PROMPT_MESTRE_EXECUCAO_INTEGRAL_V1.md`.

A linha `src/fm_assistant` evolui até produto final.

Baseline extraído do Kordena será preservado como proveniência e retirado da linha comercial somente depois de certificação explícita de paridade necessária.
