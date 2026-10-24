# F3.7.4 — PostgreSQL 16: replay, concorrência, revogação e schema

**Data:** 2026-10-18  
**Estado:** GREEN INTERMEDIÁRIO — duas execuções independentes de CI no SHA funcional `6dd2d9f7ebf84fa140ae7380f6f0386387500ca9`. F3 global permanece IN_PROGRESS.

## Contexto

Os gates SQLite já estavam verdes, mas o contrato de autorização de identidades de serviço precisa de evidências em PostgreSQL, onde constraints FK, isolamento de transações e locks diferem do SQLite. O teste usa somente banco efêmero de CI, `assistant_f3`, e credenciais exclusivamente sintéticas.

## Novo gate obrigatório

Workflow: `.github/workflows/f3-postgres-core-bridge.yml`, PostgreSQL 16 em service container, Psycopg3 e Alembic `upgrade head` no banco descartável de teste.

Teste: `tests/saas/test_core_bridge_postgres.py`.

### Cenários aprovados

1. Duas tentativas simultâneas com o **mesmo nonce**: exatamente uma resposta libera a credencial sintética e a outra é negada. O audit SQL registra somente uma liberação.
2. Chamada Core autorizada, seguida de revogação do grant via Command e outra chamada Core negada. Identidade, grant, decisões e evento administrativo persistem no PostgreSQL.
3. Revogação da identidade Core impede acesso posterior, revoga seus grants e bloqueia o re-provisionamento do mesmo ID.
4. Schema `20261018_0006` é aplicado por Alembic em Postgres de teste; não há provisionamento automático de identidade, segredo ou grants de produção.
5. Ruff dos testes e suíte SaaS + contrato E2E continuam verdes no mesmo commit.

### Evidências

- PostgreSQL Gate PUSH: **39139495756 SUCCESS**.
- PostgreSQL Gate PR: **39139500097 SUCCESS**.
- SaaS Foundation CI PUSH: **39139495725 SUCCESS**.
- SaaS Foundation CI PR: **39139500051 SUCCESS**.
- Core Assistant Bridge Contract PUSH: **39139495839 SUCCESS**.
- Core Assistant Bridge Contract PR: **39139500205 SUCCESS**.
- HEAD verificado: `6dd2d9f7ebf84fa140ae7380f6f0386387500ca9`.

### Histórico de falhas preservado

As primeiras execuções ficaram RED por erros no **fixture sintético**, corrigidos sem remover ou enfraquecer testes:

- imports e assert genérico proibido pelo Ruff;
- flush de FK para tenant, unidade, provider e integração, detectado por PostgreSQL e não por SQLite;
- request ID inicialmente gerado com formato variável que por vezes violava a regex do próprio Command; substituído por UUID, alinhado ao Command real.

O gate foi executado novamente após cada correção e aprovado em duas execuções separadas. Não há alegação de que a falha original era do serviço de produção.

## TARGET / pendências

Este gate **não** comprova revogação durante latência de rede, rate limits, pentest, alta carga, Vault externo, segredos reais, homologação de provider ou infraestrutura com TLS/ACL/mTLS.

Permanece obrigatório antes do fechamento de F3:

- GitHub Actions do FM Command (PR #90) executar efetivamente lint/typecheck/tests/build e ficar verde; os workflows atuais falham sem steps, portanto permanecem `BLOCKED_EXTERNAL`;
- revisão independente de segurança e E2E Node Command→Python Assistant;
- validação end-to-end de segredo via Vault externo e autorização governada, com rotação/revogação;
- hardening de rede, rate limiting e tracing sem segredos;
- catálogo de providers AI reais, health/circuit breaker, quotas/FinOps e homologação;
- gates adicionais do System Design e do Prompt Mestre.

Nenhuma migration em banco real foi executada. Nenhum segredo real, deploy, cutover ou merge. **F3 global = IN_PROGRESS; F4 = NOT_STARTED.**
