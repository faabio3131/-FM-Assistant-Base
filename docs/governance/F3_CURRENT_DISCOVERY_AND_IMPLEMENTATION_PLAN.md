# F3 — Current Discovery e Plano de Implementação
## FM Core Production Control Plane

**Data:** 2026-10-18
**Status:** IN_PROGRESS
**Baseline Assistant:** F2 GREEN 100%
**Baseline Core:** `bd6a93e64a92f327a576aa72c578d90378e294e5`
**ADR:** ADR-008

## CURRENT confirmado

O FM Core Base já possui:

- `AIModelRouter` provider-neutral;
- capability routing;
- prioridades únicas por capability;
- fallback apenas em falhas transitórias;
- Gemini REST;
- OpenAI-compatible;
- texto;
- transcrição/áudio;
- service-to-service key;
- `tenant_id`, `unit_id`, request e correlation no contrato;
- contratos de pricing/cost;
- contrato FinOps;
- SecretStore por referência;
- SQLAlchemy disponível;
- runtime database foundation;
- testes de router/service;
- CI.

## Limitações CURRENT

1. Rotas vêm de `FM_CORE_AI_ROUTES_JSON`.
2. API keys são resolvidas do ambiente no bootstrap.
3. `CoreAIRuntime` materializa rotas fixas ao iniciar.
4. Metering default = memória.
5. Router registra custo como `None`.
6. Pricing catalog default não é persistente.
7. FinOps é apenas contrato/read-model interface.
8. Auditoria do Core é in-memory.
9. Não existe provider/model catalog persistente.
10. Não existe route policy persistente por platform/tenant/unit.
11. Não existe provider health/circuit breaker persistente.
12. Não existe admin API do Control Plane.
13. Não existe readiness de banco/control plane/provider.
14. Não existe resolução BYOK real por referência de Vault compartilhado.
15. Não há homologação real de provider no novo Control Plane.

## TARGET F3

Implementar, sem duplicar Tenant/License authority:

- persistence/migrations do AI Control Plane;
- provider catalog;
- model catalog;
- model-capability map;
- route policy por platform/tenant/unit;
- deterministic scope resolution;
- secret reference + credential source;
- FM-managed resolution;
- tenant-managed/BYOK resolver protocol;
- immutable price snapshots/tariffs;
- persistent usage ledger;
- deterministic cost enrichment;
- persistent FinOps read model;
- provider health;
- circuit breaker;
- timeout policy por rota;
- quota hook;
- audit events;
- admin Control Plane API com chave separada;
- readiness;
- bootstrap/seeding compatível com CURRENT;
- regression do contrato Assistant → Core.

## Schema candidato

- `core_ai_providers`
- `core_ai_models`
- `core_ai_model_capabilities`
- `core_ai_route_policies`
- `core_ai_price_snapshots`
- `core_ai_price_tariffs`
- `core_ai_usage_events`
- `core_ai_provider_health`
- `core_ai_audit_events`

Nenhum desses objetos vira autoridade de plano/licença do assinante.

## Resolução de rota

Para cada tenant/unit/capability:

1. procurar políticas ativas unit-scoped;
2. se inexistentes, procurar tenant-scoped;
3. se inexistentes, usar platform-scoped;
4. ordenar por prioridade;
5. falhar fechado em prioridade ambígua;
6. excluir rota com provider/circuit não elegível;
7. resolver segredo somente no momento da execução.

## Compatibilidade

O Assistant continua chamando os endpoints atuais.

Nenhuma alteração de provider/modelo deve ser exigida no Assistant.

`FM_CORE_AI_ROUTES_JSON` permanece bootstrap de dev/test e mecanismo de seed controlado,
não authority comercial final.

## Gates F3

- migration up/down em banco descartável;
- provider/model/capability CRUD/control plane;
- route scope resolution;
- priority/fallback regression;
- FM-managed secret reference;
- BYOK resolver testado sem raw secret em DB/API/log;
- pricing persistence;
- usage persistence;
- FinOps query;
- provider health/circuit breaker;
- quota hook;
- audit sanitization;
- readiness;
- service/admin auth separation;
- Assistant ↔ Core contract regression;
- secret scan;
- pip check;
- Ruff;
- pytest;
- GitHub Actions GREEN;
- provider real homologado quando credencial/ambiente real autorizado estiver disponível.

## STOP

- raw API key persistida no banco;
- BYOK retornado por API;
- Core duplicando license/entitlement authority;
- cross-tenant route resolution;
- rota de circuito aberto selecionada;
- custo inventado;
- mutation admin com consumer key;
- provider declarado homologado sem chamada real comprovada.
