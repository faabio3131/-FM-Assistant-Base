# ADR-007 — Identity, Session e RBAC

**Data:** 2026-10-17  
**Status:** APPROVED FOR F1 IMPLEMENTATION

## Contexto

A fundação atual autentica tenants por API key e usa `X-Admin-Key` como bootstrap
técnico. Isso é suficiente para a fundação API-first, mas não para o produto Web
comercial. A V1 precisa de usuários humanos, sessões, memberships, unidade ativa e
RBAC explícito sem transformar API credential em identidade humana.

## Decisão

A identidade comercial será first-party no domínio da plataforma, com:

- email canônico por usuário;
- password hash Argon2 via biblioteca madura `argon2-cffi`;
- sessão opaca aleatória;
- somente hash HMAC da sessão persistido;
- cookie `HttpOnly`, `SameSite=Strict` e `Secure` em staging/produção;
- membership por tenant;
- unit scope explícito;
- role + permission registry deny-by-default;
- revogação e expiração de sessão;
- API credentials mantidas como principal separado para machine access.

`X-Admin-Key` permanece somente como bootstrap de plataforma/compatibilidade
controlada e não constitui autenticação administrativa comercial do tenant.

## Papéis iniciais

- OWNER
- ADMIN
- MANAGER
- SALES_AGENT
- SUPPORT_AGENT
- VIEWER

Permissões são registradas explicitamente. Não existe wildcard implícito de OWNER.

## Convites

Convites usam token opaco retornado uma única vez no estágio atual. O token persistido
é apenas HMAC. O canal de entrega de email será conectado ao Integration Fabric em
fase posterior sem alterar o contrato de identidade.

## Core obrigatório

Como parte de F1, staging/produção passam a rejeitar backend cognitivo direto de
provider. O único backend comercial normal é `core`, conforme ADR-002.

## Consequências

- Migration 0003 cria tenant/unit/user/membership/session/invitation/license/entitlement.
- Tenant e unit tornam-se autoridades explícitas.
- API key existente continua compatível, mas com permission set de machine principal.
- Frontend futuro pode utilizar sessão humana sem duplicar autorização.
- Cross-tenant, cross-unit e privilege escalation são STOP conditions.
