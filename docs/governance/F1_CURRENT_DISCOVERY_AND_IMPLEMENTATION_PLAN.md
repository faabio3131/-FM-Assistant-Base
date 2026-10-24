# F1 — Current Discovery e Plano de Implementação
## Identity / RBAC / Tenant / License Control Plane

**Data:** 2026-10-17  
**Status:** PREPARAÇÃO — F1 AINDA NÃO PROMOVIDA  
**Bloqueio de promoção:** F0 = BLOCKED_EXTERNAL por GitHub Actions/Billing

---

## 1. Regra

Este documento é preparação permitida pelo AGENTS.md.

Nenhuma implementação F1 deve ser tratada como iniciada/promovida enquanto F0 não
estiver GREEN 100%.

---

## 2. CURRENT confirmado

### Autenticação atual

Existem dois mecanismos:

1. `X-Admin-Key` global para provisionar/revogar credenciais.
2. Bearer API key tenant-scoped para operações do tenant.

A API key:

- recebe prefixo `fma_`;
- é armazenada apenas como HMAC-SHA256 com pepper;
- resolve `tenant_id`, `unit_id`, `credential_id`;
- deixa de funcionar após revogação.

### Autoridade tenant atual

`TenantContext` contém:

- tenant_id;
- unit_id;
- credential_id.

Persona, conversa, mensagem, knowledge e WhatsApp usam esse contexto em consultas
tenant/unit-scoped.

### Schema atual

- assistant_tenant_credentials
- assistant_personas
- assistant_conversations
- assistant_messages
- assistant_knowledge_documents
- assistant_audit_events
- assistant_whatsapp_channels
- assistant_whatsapp_inbound

### Lacunas comerciais

Não existem ainda:

- usuário humano canônico;
- membership;
- organization/tenant como entidade persistente própria;
- unit como entidade persistente própria;
- login/sessão;
- password/provider identity;
- convite;
- recovery;
- RBAC/permissions;
- active unit por sessão;
- plan/license;
- trial;
- entitlements;
- feature flags;
- quotas;
- lifecycle do tenant;
- lifecycle de membership;
- session revocation.

### Risco de autoridade atual

`X-Admin-Key` global é bootstrap técnico e não pode sobreviver como autenticação
administrativa comercial.

`assistant_tenant_credentials` é credencial de API/service access e não deve ser
transformada silenciosamente em identidade humana.

---

## 3. Contradição técnica já identificada

`Settings.validate()` atualmente aceita em production:

- `model_backend=openai_compatible`;
- `model_backend=core`.

O teste `test_production_accepts_strong_openai_compatible_configuration` confirma
explicitamente esse CURRENT.

Isso contradiz ADR-002, que determina Core obrigatório em staging/production.

### Correção planejada

Quando F1 puder iniciar:

- production/staging devem rejeitar `openai_compatible` direto;
- teste atual deve ser substituído por teste negativo;
- development/test podem manter adapter direto;
- exceção comercial futura exige mecanismo formal, não bypass silencioso.

---

## 4. TARGET de identidade

### Entidades canônicas propostas

#### Tenant / Organization

```text
assistant_tenants
- tenant_id PK
- legal/display name
- slug
- status
- created_at
- updated_at
```

#### Unit

```text
assistant_units
- unit_id PK
- tenant_id FK
- display_name
- status
- created_at
- updated_at
```

#### User

```text
assistant_users
- user_id PK
- email canonical/normalized
- display_name
- status
- created_at
- updated_at
```

#### Membership

```text
assistant_memberships
- membership_id PK
- tenant_id FK
- user_id FK
- role
- status
- created_at
- updated_at
```

#### Membership Unit Scope

```text
assistant_membership_units
- membership_id FK
- unit_id FK
- composite unique
```

#### Session

```text
assistant_sessions
- session_id PK
- user_id FK
- tenant_id FK
- active_unit_id FK nullable/validated
- token_hash/session reference
- expires_at
- revoked_at
- created_at
- last_seen_at
```

#### Invitation

```text
assistant_invitations
- invitation_id PK
- tenant_id FK
- email
- role
- token_hash
- expires_at
- accepted_at
- revoked_at
```

#### License / Plan binding

```text
assistant_tenant_licenses
- tenant_id PK/FK
- plan_code
- status
- trial_started_at
- trial_ends_at
- period_started_at
- period_ends_at
- created_at
- updated_at
```

#### Entitlement

```text
assistant_entitlements
- tenant_id FK
- capability
- enabled
- limit_value nullable
- source
- updated_at
```

Feature flags e quotas devem reutilizar a autoridade de entitlement sempre que isso
não criar semântica ambígua.

---

## 5. RBAC inicial aprovado para implementação

Papéis:

- OWNER
- ADMIN
- MANAGER
- SALES_AGENT
- SUPPORT_AGENT
- VIEWER

### Regra

Papel não é autorização final.

Criar permission registry explícito.

Candidatos mínimos:

- tenant.read
- tenant.manage
- unit.read
- unit.manage
- user.read
- user.invite
- user.manage
- role.manage
- persona.read
- persona.manage
- knowledge.read
- knowledge.manage
- conversation.read
- conversation.respond
- conversation.handoff
- integration.read
- integration.manage
- crm.read
- crm.manage
- billing.read
- billing.manage
- analytics.read

OWNER não deve significar bypass universal oculto; sua matriz precisa ser explícita.

---

## 6. Estratégia de autenticação

### Requisito

Não criar autenticação insegura artesanal.

### Implementação alvo

Separar:

- identidade humana;
- sessão web;
- API/service credential.

A API key tenant atual pode permanecer para machine/API access, mas deve ser classificada
e governada separadamente.

Para identidade humana, escolher mecanismo maduro e compatível com Web First.

Antes de adicionar dependência, avaliar:

- segurança;
- sessão;
- passwordless/passkey/MFA futuro;
- recovery;
- portabilidade;
- lock-in;
- integração frontend/backend.

A decisão concreta do provider/library de identidade deve virar ADR técnico dentro de F1
antes do código correspondente.

---

## 7. Active unit

A unidade ativa deve ser derivada da sessão/membership autorizado.

É proibido aceitar `unit_id` arbitrário do browser para obter privilégio.

Troca de unidade:

1. verificar membership;
2. atualizar sessão/contexto;
3. auditar;
4. invalidar elevações/contextos que dependam da unidade, quando aplicável.

---

## 8. Compatibilidade com CURRENT

A migração deve preservar:

- persona;
- conversations;
- messages;
- knowledge;
- WhatsApp;
- API credentials existentes.

Não recriar tabelas funcionais.

Novo tenant/unit authority deve ser introduzido por migration compatível.

Antes de adicionar FK a tabelas existentes:

- backfill controlado;
- validação de órfãos;
- índices;
- compatibilidade SQLite test/PostgreSQL commercial;
- estratégia de rollback.

---

## 9. Sequência técnica proposta quando F1 for liberada

### F1.1

ADR de mecanismo de identidade/sessão.

### F1.2

Domain contracts:

- TenantStatus;
- UserStatus;
- MembershipStatus;
- Role;
- Permission;
- SessionContext;
- UserIdentity.

### F1.3

Migration 0003:

- tenants;
- units;
- users;
- memberships;
- membership_units;
- sessions;
- invitations;
- tenant_licenses;
- entitlements.

Sem migration destrutiva.

### F1.4

Repositories tenant-scoped.

### F1.5

Authorization service deny-by-default.

### F1.6

Session/auth service.

### F1.7

API endpoints mínimos.

### F1.8

Desativar `X-Admin-Key` como autoridade comercial final, mantendo apenas bootstrap
controlado enquanto necessário e explicitamente classificado.

### F1.9

Enforce ADR-002 em Settings:

- staging/prod => core obrigatório.

### F1.10

Testes:

- auth;
- session;
- revoke;
- invitation;
- cross-tenant;
- cross-unit;
- role/permission;
- unauthorized;
- forbidden;
- tenant lifecycle;
- entitlement;
- migration;
- regression WhatsApp/conversation/persona.

---

## 10. Critérios de gate F1

F1 só poderá ser GREEN quando:

- mecanismo de identity/sessão aprovado em ADR;
- schema/migration validados;
- login/sessão funcionais;
- RBAC deny-by-default;
- tenant isolation verde;
- unit isolation verde;
- revoke/session expiry verdes;
- API credential separada de user identity;
- X-Admin-Key não for autoridade comercial final;
- staging/prod rejeitarem provider direto e exigirem Core;
- lint verde;
- testes verdes;
- migration verde;
- CI verde;
- security review verde;
- tracker/documentação atualizados.

---

## 11. STOP conditions F1

- cross-tenant;
- cross-unit;
- session fixation/reuse indevido;
- auth bypass;
- role escalation;
- owner/admin implícito sem permission;
- secret/password/token persistido em claro;
- migration destrutiva;
- duas fontes de verdade para tenant;
- API key tratada como usuário humano;
- Core bypass em staging/prod.

---

## 12. Próxima ação permitida

Restabelecer GitHub Actions/Billing e rerodar F0.

Quando F0 ficar GREEN, marcar F1 `IN_PROGRESS` e executar a sequência F1.1 em diante
automaticamente conforme AGENTS.md.
