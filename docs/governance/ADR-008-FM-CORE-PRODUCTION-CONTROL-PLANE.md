# ADR-008 — FM Core Production Control Plane e fronteira de credenciais

**Data:** 2026-10-18
**Status:** APPROVED PARA IMPLEMENTAÇÃO
**Fase:** F3
**Autoridade superior:** System Design Mestre + ADR-002/003/004 + AGENTS.md

## Contexto

O FM Core Base já possui AIModelRouter, adapters Gemini/OpenAI-compatible, fallback,
metering contracts, pricing/cost contracts e API interna. O CURRENT ainda carrega
rotas a partir de `FM_CORE_AI_ROUTES_JSON`, resolve chaves de provider por ambiente e
usa metering/auditoria em memória no composition root do serviço.

Isso é bootstrap técnico, não Control Plane comercial.

Ao mesmo tempo, F1 e F2 estabeleceram no produto:

- Tenant/Unit/License/Entitlements como autoridades do produto;
- Integration & Credential Control Plane universal;
- Credential Vault;
- suporte arquitetural a FM-managed e tenant-managed/BYOK.

F3 precisa tornar o Core data-driven sem criar uma segunda autoridade de cliente,
licença ou segredo.

## Decisão

### 1. Autoridades do FM Core

O FM Core é autoridade para:

- provider catalog;
- model catalog;
- capability map;
- route policy;
- prioridade/fallback;
- timeout policy;
- provider health/circuit state;
- price snapshots;
- AI usage ledger;
- AI FinOps;
- auditoria de alterações cognitivas;
- resolução técnica de credencial por referência.

O FM Core **não** é autoridade para:

- identidade humana;
- membership;
- plano/licença comercial;
- billing do assinante;
- CRM;
- autorização comercial do tenant.

### 2. Escopo de rotas

Rotas podem existir nos escopos:

1. unit;
2. tenant;
3. platform.

Para uma capability, o resolvedor usa o escopo mais específico que possua política
ativa. Não mistura silenciosamente rotas de escopos diferentes.

Prioridades dentro do mesmo conjunto continuam únicas e determinísticas.

### 3. Segredos

O banco do Core armazena **referências**, nunca API keys/tokens em claro.

Uma rota referencia:

- `credential_source = fm_managed | tenant_managed`;
- `secret_reference`.

O valor é obtido por `SecretStore/CredentialResolver` no momento da execução.

FM-managed pode usar secret manager/ambiente no bootstrap atual.

BYOK deve usar uma referência emitida pelo Credential Vault/control plane autorizado.
O Core não duplica o vault do produto.

### 4. Bootstrap versus autoridade canônica

`FM_CORE_AI_ROUTES_JSON` permanece somente para:

- development;
- test;
- bootstrap/seeding controlado.

Em staging/production, após a inicialização do Control Plane, as rotas persistidas são
a autoridade canônica.

Alterar cliente/provider/rota ativa não deve exigir commit ou deploy.

### 5. Admin versus consumer auth

A chave `X-Core-Service-Key` autentica consumidores do runtime cognitivo.

Operações de Control Plane usam credencial administrativa separada
(`X-Core-Admin-Key` ou evolução equivalente), com comparação constante e auditoria.

A mesma chave não deve exercer simultaneamente os dois papéis em produção.

### 6. Usage e FinOps

Todo attempt de provider deve gerar evento persistente com:

- tenant/unit;
- request/correlation;
- capability;
- provider/model;
- rota;
- fallback;
- tokens;
- latência;
- outcome;
- price snapshot;
- custo/moeda quando calculável;
- timestamp.

Preço é versionado por snapshot imutável. Custo desconhecido permanece explicitamente
desconhecido; nunca é inventado.

### 7. Provider health / circuit breaker

Falhas transitórias alimentam health/circuit state. Rotas com circuito aberto não são
selecionadas até a política de recuperação permitir nova tentativa.

Sucesso fecha/recupera o estado conforme política.

### 8. Quotas

Entitlements comerciais permanecem no produto. O Core expõe um `QuotaGuard`/hook
determinístico para receber/aplicar decisões de quota sem duplicar a autoridade de
plano/licença.

### 9. Compatibilidade

O contrato Assistant → Core permanece estável:

- `POST /v1/ai/text`;
- `POST /v1/ai/transcribe`;
- tenant/unit/request/correlation continuam obrigatórios.

A mudança de bootstrap para Control Plane não deve exigir alteração no Assistant para
operações cognitivas normais.

## Consequências

- O Core passa a depender de persistência para seu Control Plane comercial.
- Será necessária migration versionada.
- Provider/model/route/pricing podem ser alterados por dados/API governada.
- Segredos continuam fora do banco do Core.
- BYOK pode evoluir para secret manager compartilhado sem reescrever o Router.
- O produto mantém soberania sobre tenant/licença/billing.
- Homologação real de providers continua gate separado e exige evidência real.
