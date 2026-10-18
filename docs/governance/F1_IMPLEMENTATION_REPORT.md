# F1 — Implementation Report
## Identity / RBAC / Tenant / License Control Plane

**Data:** 2026-10-17/18  
**Status:** IMPLEMENTADO E TESTADO LOCALMENTE — CI REMOTO PENDENTE  
**Branch:** `feat/saas-foundation-v1`

## Escopo entregue

### Identity e sessão

- usuário humano canônico;
- email normalizado;
- senha Argon2 via `argon2-cffi`;
- sessão opaca aleatória;
- somente HMAC SHA-256 do token persistido;
- cookie HttpOnly + SameSite=Strict;
- Secure em staging/produção;
- expiração e revogação;
- logout;
- unidade ativa autorizada;
- troca de unidade com validação de membership.

### RBAC

Papéis:

- OWNER;
- ADMIN;
- MANAGER;
- SALES_AGENT;
- SUPPORT_AGENT;
- VIEWER.

Permissões são explícitas e deny-by-default.

Foi implementada proteção contra escalada de papel por atores sem autoridade.

### Tenant / Unit

Novas autoridades persistentes:

- `assistant_tenants`;
- `assistant_units`;
- `assistant_memberships`;
- `assistant_membership_units`.

O contexto humano deriva tenant/unidade da sessão validada.

### API credentials

As API keys existentes foram preservadas como principal separado de machine access.

Não foram transformadas em identidade humana.

Novos endpoints tenant-scoped permitem criação/revogação de API credential por
usuário humano autorizado.

### Convites

- token opaco;
- somente HMAC persistido;
- expiração;
- role assignment governado;
- aceite para usuário novo ou usuário existente autenticado por senha.

A entrega externa do convite pertence ao futuro Integration Fabric; nesta fase o
contrato/lifecycle de identidade está implementado.

### Recuperação

- token opaco one-time;
- somente HMAC persistido;
- expiração;
- troca de senha Argon2;
- token não reutilizável;
- todas as sessões ativas são revogadas após recuperação;
- endpoint de solicitação não revela existência de conta;
- token só é devolvido diretamente em ambiente não comercial para harness/onboarding
  controlado.

A entrega de recovery por email/SMS será adapter do Integration Fabric e não deve ser
confundida com CURRENT desta fase.

### License / Entitlements

Foram introduzidas autoridades de schema para:

- `assistant_tenant_licenses`;
- `assistant_entitlements`.

A gestão comercial completa de planos/quotas continua na F9. F1 estabelece a autoridade
de dados necessária para RBAC/control plane.

### Core obrigatório

`staging` e `production` agora rejeitam backend cognitivo direto.

O backend comercial válido é `core`, conforme ADR-002.

`openai_compatible` direto permanece permitido apenas em development/test.

### Legacy admin bootstrap

`X-Admin-Key` não é identidade administrativa comercial.

Endpoints legados de provisionamento/revogação ficam desabilitados em ambiente
production-like e preservados apenas para bootstrap/compatibilidade de dev/test.

## Migration

Criada:

`20261017_0003_identity_tenant_rbac.py`

A migration é aditiva e não destrói as tabelas existentes.

Backfill validado:

- tenant existente;
- unidade existente;
- licença `legacy_foundation`.

Teste real executa:

`0001 → 0002 → insert legacy scope → 0003/head`

e comprova preservação/promoção do escopo existente.

## Evidência local

Gate final executado no working tree:

- Secret-pattern scan: **NO_SECRET_PATTERN_MATCHES**
- Ruff: **PASS**
- pip check: **PASS**
- git diff --check: **PASS**
- pytest `tests/saas`: **27/27 PASS**
- migration/backfill test: **PASS**
- identity/RBAC/recovery subset pós-correção: **10/10 PASS**

## Falha encontrada e corrigida

Durante a implementação de recovery, um patch automático inseriu
`PasswordResetORM` indevidamente dentro de duas chamadas SQLAlchemy.

Resultado:

- cinco testes de sessão falharam.

Tratamento conforme AGENTS.md:

1. falha preservada;
2. causa raiz identificada;
3. inserções indevidas removidas;
4. imports corretos preservados;
5. subset rerodado;
6. 10/10 PASS;
7. suíte completa rerodada;
8. 27/27 PASS.

Nenhum teste foi removido ou afrouxado para obter verde.

## Warning conhecido

Starlette/FastAPI TestClient emite warning de depreciação relacionado à integração
httpx atual.

Não há falha funcional associada nesta fase. Deve entrar no backlog técnico de
atualização de dependência/harness, sem ser ocultado.

## Gate de segurança F1

Comprovado localmente:

- cross-tenant negativo;
- cross-unit negativo;
- role escalation negativo;
- sessão revogável;
- token de sessão não persistido em claro;
- recovery one-time;
- recovery revoga sessões;
- API credential separada de user identity;
- Core obrigatório em staging/produção;
- secret scan sem achados.

## Pendente para GREEN final de F1

- commit/push;
- GitHub Actions no SHA exato;
- CI obrigatório 100% verde;
- registro final no Execution Tracker.

Somente depois disso F1 pode ser marcada `GREEN` e F2 promovida a `IN_PROGRESS`.
