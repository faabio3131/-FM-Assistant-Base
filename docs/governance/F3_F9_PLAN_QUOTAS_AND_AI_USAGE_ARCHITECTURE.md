# FM Assistant + FM Core — Planos, quotas e consumo de IA

**Data:** 2026-10-18  
**Status:** construção em andamento; sem valores comerciais fixados. ADR-009 obriga acesso a todas as funções em todos os planos.  
**Autoridade:** FM Command (FM define preços e franquias dos planos) → FM Assistant (licença do tenant e revisão do plano) → FM Core (enforcement técnico, medição e FinOps).

## Princípio econômico

**A FM Tecnologia fornece e paga pelos modelos de IA.** O cliente adquire uma
assinatura do software com **todas as funcionalidades disponíveis**, não uma conta pessoal em cada provedor. O custo técnico
é interno à FM, rastreado por tenant, unidade, produto, capability, modelo e
tentativa. A cobrança comercial de mensalidade, overage eventual e planos
pertence ao Assistant/billing e jamais é confundida com gasto técnico do Core.

## Configuração comercial sem hardcoding de níveis

O catálogo admite qualquer quantidade de planos (exemplos comerciais a
definir posteriormente: Essencial / Profissional / Empresarial). Cada
`plan_code` suporta múltiplas revisões **imutáveis**, para modificar somente
franquias, limites quantitativos, preço e prazos sem editar código. **Não é
permitido bloquear funcionalidades por categoria de plano.** Cada cliente fixa
`plan_code + plan_revision` em sua licença, evitando que uma edição de plano
mude silenciosamente as regras de assinantes existentes.

**Apenas a FM Tecnologia**, pela autoridade corporativa do Command,
pode cadastrar e alterar os preços, unidades de franquia, períodos e
limites quantitativos. As permissões de funções são iguais em TODOS os
planos. Segurança, RBAC e assinatura válida permanecem obrigatórios
independentemente do plano.

Métricas candidatas configuráveis, por capacidade e período:

| Recurso | Unidade medida | Escopo possível |
|---|---|---|
| `ai.requests` | requisições lógicas | tenant / unidade |
| `ai.total_tokens` | tokens de entrada, saída e tentativas de fallback | tenant / unidade |
| `ai.input_tokens`, `ai.output_tokens`, `ai.cached_tokens` | tokens por categoria | tenant / unidade |
| `ai.cost_usd_microunits` | orçamento técnico interno em milionésimos de USD | tenant |
| `audio.seconds` | segundos processados | tenant / unidade |
| `whatsapp.messages` | mensagens elegíveis | tenant / unidade |
| `crm.leads`, `automation.executions` | unidades de funcionalidade | tenant / unidade |
| `storage.bytes`, `users.seats`, `units.active` | capacidade de operação | tenant |

Não definir números, preços ou limites de mercado até decisão comercial.
Para IA, limites ausentes devem negar a operação **quando o controle estiver
ativado**; `NULL` nunca significa ilimitado.

**Períodos:** diário/semanal/mensal/ciclo de assinatura conforme policy
versionada. O período efetivo precisa permanecer contido no intervalo
válido da licença; `trial`, `active`, `suspended`, `canceled` e expiração
são tratados pelo Assistant.

## Fluxo de execução comercial (alvo técnico)

1. Assistant valida tenant/unidade e assinatura ativa/trial, obtém revision
   fixada e resolve as cotas para o recurso solicitado.
2. Entitlement projetado para Core por **contrato de serviço autenticado,
   versionado, com integridade, expiração, revogação e isolamento de escopo**.
   Nenhum tenant publica ou eleva suas próprias quotas.
3. Core valida token de autoridade e policy vigente, calcula orçamento
   conservador de chamadas e fallback, reserva atomicamente as métricas
   **compartilhadas por tenant e por unidade** antes de cada execução.
4. Caso o saldo de qualquer métrica termine, a transação toda é rejeitada
   (por exemplo `PLAN_LIMIT_REACHED`), sem nova chamada ao provedor ou
   cobrança técnica adicional provocada pelo bloqueio.
5. Para operações aceitas, adapter aplica teto de geração e emite eventos
   de uso por tentativa (inclusive fallback, timeout e erro). O Core
   concilia o consumo real, confirma settlement e libera somente a parte
   da reserva que foi comprovadamente não utilizada.
6. Em uso ambíguo o orçamento permanece reservado, com alerta e workflow
   administrativo de reconciliação. Nunca assumir custo zero sem prova.
7. Assistant disponibiliza consumo, saldo, % utilizado, data de renovação,
   aviso antecipado e caminho para upgrade; Command consolida receita, custo
   interno da IA, margem e risco, por produto e organização.

**Eventos importantes:** `quota_reserved`, `quota_denied`,
`usage_observed`, `usage_unknown`, `quota_settled`,
`period_reset`, `plan_changed`, `license_suspended`,
`quota_warning_80_percent`. Percentuais são exemplos configuráveis
de alerta, não limiares comerciais definitivos.

**Overage:** por padrão, hard stop. Comprar excedentes, carry-over,
burst, throttling ou upgrade automático serão decisões explícitas do
produto e do plano; jamais consumo ilimitado implícito.

## CURRENT implementado, sem alegação de homologação

- `assistant_plan_versions`, `assistant_plan_limits`: catálogo versionado
  e limites positivos por métrica e escopo.
- `assistant_tenant_licenses.plan_revision`: fixação de revisão por licença,
  opcional para retrocompatibilidade. Sem revisão, leitor nega uso de
  quota, não inventa regra.
- `PlanLimitResolver`: valida tenant/unidade, status, validade e plano
  antes de resolver limite publicado/revisionado.
- No Core, `QuotaReservations.reserve_bundle` e `settle_bundle`
  transacionam métricas em conjunto, com row lock de políticas, soma de
  reservas/consumo, idempotência, bloqueio de replay e rollback total.
  Um identificador técnico `__tenant__` é usado em testes internos para
  o orçamento agregado do tenant; o **projetor confiável** deve produzir
  essa chave, jamais confiar no ID fornecido pelo cliente.
- Testes de concorrência PostgreSQL16 provam que duas unidades simultâneas
  não conseguem ultrapassar o mesmo orçamento técnico.
- `QuotaReservations.usage_snapshot` fornece saldo por recurso e escopo:
  limite, consumido, reservado/pendente, saldo restante, revisão e fim da
  janela, sem misturar consumo entre tenants.
- Adapters Gemini e OpenAI-compatible transmitem teto de tokens de saída
  configurado no payload (`maxOutputTokens` / `max_tokens`); testes
  sintéticos verificam presença e rejeição de limites inválidos. Até
  completar guarda de input e ingestão de policies, não considerar teto
  isolado garantia de orçamento máximo.

**PENDÊNCIAS DE CONSTRUÇÃO, executar antes da homologação externa:**
provisionamento assinado/revisionado Command→Assistant→Core; cadastro e alteração
de preço/limite por FM, sem feature gating e com auditoria; vinculação de licença,
suspensão/expiração imediata de orçamento; implementação do guard obrigatório
no composition root; preflight com limites reais nos adapters; conciliação
oficial de tentativas/tokens/custo, dashboards e alertas; F9 billing/upgrade
e SaaS entitlements UI; teste E2E sintético ponta a ponta.

**CONFIGURAÇÕES EXTERNAS ADIADAS:** credenciais de modelos, Vault, ambientes
reais, gateways de assinatura, pagamentos reais, rede/TLS e homologação
com terceiros. Essas pendências **não impedem** a construção integral.

**Não classificar software como 100% concluído antes dos gates internos.**

## Referência FinOps de Kordena (aproveitamento seletivo)

Auditoria de leitura e decisão de negócio em
`docs/governance/ADR-009-ALL-FEATURES-PLAN-CONSUMPTION-AND-KORDENA-FINOPS.md`.
O cálculo de custo e o pricing provider-neutral do Kordena já foram reutilizados
sem diferença de conteúdo no FM Core. O dashboard/projetor são referências
para consumo e margem, **não** para autorizar requisições. Os limites precisam
ser garantidos pelo ledger transacional do Core e **apenas a FM** configura
planos e preços pelo Command. Uma mesma função nunca é exclusiva de um tier.
