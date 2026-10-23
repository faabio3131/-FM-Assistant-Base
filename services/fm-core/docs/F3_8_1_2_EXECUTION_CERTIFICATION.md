# F3.8.1–F3.8.2 — Execução incremental e evidências

**Data:** 2026-10-18
**Status:** GREEN INTERMEDIÁRIO para máquina de estados e ledger de reservas,
não para F3.8 completo, runtime produtivo ou F3 global.

## Autoridade reconciliada

Revisados: System Design Mestre do Assistant, Prompt Mestre F3 e
`ADR-008-FM-CORE-PRODUCTION-CONTROL-PLANE.md` / `ADR-004-BYOK-E-IA-GERENCIADA-PELA-FM.md`.

- O Core governa rotas, circuitos e consumo técnico.
- Tenant, plano, licença, limites comerciais e permissão de gastar continuam
  sob autoridade canônica do Assistant/control plane do produto.
- `core_ai_quota_policies` é uma **projeção técnica governada** de decisões
  recebidas de autoridade autorizada, não um novo motor de billing/licença.
- Nenhuma API mutável de quotas foi criada nesta entrega.
- Credenciais BYOK e FM-managed não são gravadas no ledger de quota.

## F3.8.1 — Máquina de estados circuit breaker

`core/ai_circuit_breaker.py` contém transições puras, sem acesso a rede e
sem ativação no runtime. Política explícita tem threshold, cooldown e prazo
de probe; CLOSED abre após falhas transitórias; OPEN só admite probe após
cooldown; HALF_OPEN admite um identificador de probe e exige correspondência
no resultado; sucesso fecha, falha volta a abrir; prazo expirado requer
reabertura conservadora. Resultado definitivo não é contado como falha
transitória em CLOSED.

`tests/service/test_ai_circuit_breaker.py` prova transições, cooldown,
single-probe lógico, falsificação/resultado atrasado, recuperação conservadora,
parâmetros inválidos e timestamps timezone-aware.

**Limite:** isso é uma máquina de estados *pura*, **não** um circuit breaker
distribuído. Faltam estado persistido, leasing/fencing atômico, política de
janela de falhas e integração com o `AIModelRouter`. Nenhum resultado deve
ser interpretado como provider real protegido.

## F3.8.2 — Reservas transacionais de unidades de quota

`core/ai_quota_store.py` implementa `reserve` e `settle` com uma
transação SQLAlchemy e bloqueio `SELECT FOR UPDATE` da política
(tenant, unidade, capability), serializando reservas concorrentes no
PostgreSQL. A soma de reservas abertas e unidades liquidadas é comparada
contra `limit_units`. Retentativas do mesmo `request_id` e escopo são
idempotentes, mas alterações incompatíveis são negadas. Liquidação ajusta
a capacidade com as unidades efetivamente usadas, sem contabilização dupla.
A ausência de política falha fechada.

Migration aditiva `f3_0003` cria `core_ai_quota_policies` e
`core_ai_quota_reservations`; o bootstrap passa a exigir essa revisão,
sem aplicar migrations automaticamente. O período utiliza timestamps UTC;
não mistura quotas entre tenant/unidade/capability.

Testes:
- SQLite sequencial: reserva, limites, idempotência, refunds por settlement,
  scope isolado, janela e validação de entrada.
- PostgreSQL 16 descartável: duas reservas simultâneas disputando o último
  slot (exatamente uma aceita) e duas reservas simultâneas com mesmo
  `request_id` (um registro idempotente).
- Alembic upgrade/downgrade em banco descartável e suite geral Core.

**Limites:** quota técnica aqui é medida em unidades inteiras abstratas.
Ainda não existem provisionamento da projeção a partir de entitlement
autorizado, reserva preventiva no runtime, token/cost preflight, antifraude,
tratamento de gasto desconhecido, compensação de reservas abandonadas,
rate limit, observabilidade/alerta ou reconciliação com provider real.
Não converter limite técnico em plano/billing do cliente.

## Certificação e rastreabilidade

HEAD funcional inicial `3dbab732d8fa9c2425d6ebaa8d560cd6b1fbcf21`:
- AI Service CI: push `39153783479` / PR `39153787266` = SUCCESS.
- F3 Quota PostgreSQL Security Gate: push `39153783598` /
  PR `39153787264` = SUCCESS.

Falhas corrigidas, preservadas em Actions:
- Ruff imports incorretos → reordenação, sem suprimir gate.
- Fixture cross-scope esperava motivo de negativa errado ao consultar
  política ausente → inclusão de política explícita na fixture.
Nenhum teste foi removido ou desabilitado.

## Próximas dependências F3.8

1. Persistir circuit breaker compartilhado, CAS/locks e lease/fencing com
   PostgreSQL 16 sob falhas e concorrência, sem bypass de BYOK.
2. Conectar quota preflight ao caminho de execução, recebendo decisão
   autorizada do Assistant, e impedir provider call sem reserva válida.
3. Medir/conciliar tokens e custo por snapshot de preço, inclusive fallback,
   timeout e custo desconhecido (unknown **não** é zero).
4. Implementar quotas de custo, limits/alertas, recuperação de reserva
   abandonada, health/circuit automático e instrumentação.
5. Revisão independente de segurança e homologação real autorizada,
   com TLS/ACL/Vault, staging isolado e providers, antes de F3 GREEN.

**STOP:** nenhuma PR mergeada, nenhum deploy, segredo real, provider real,
migration de staging/produção ou ação irreversível autorizada por este gate.
F3 continua `IN_PROGRESS`; F4 `NOT_STARTED`.
