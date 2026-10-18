# F3.8.5 — FinOps interno: conciliação por requisição e preflight de custo

**Data:** 18/10/2026  
**Status:** implementação de domínio e testes internos; não equivale a monetização completa, limite monetário de produção ou homologação de provedor.

## Implementado

1. `PersistentAIFinOps.reconcile_request` produz resumo segregado por tenant, unidade e request_id, incluindo total de tentativas gravadas, fallbacks, quantidade de custos conhecidos e desconhecidos e subtotal conhecido por moeda. Não pode reportar custo desconhecido como zero. `all_recorded_costs_known` significa apenas que os **eventos já registrados** têm custo calculável; não afirma fechamento definitivo no provedor.
2. A identificação idempotente do usage ledger considera a rota e o snapshot de preço. Duas tentativas distintas de fallback com o mesmo provider/model são contabilizadas separadamente; replay idêntico não duplica evento.
3. `verify_cost_preflight` calcula, de forma pura, o custo potencial da soma de **todas as rotas de fallback declaradas**, com snapshots versionados, limites de tokens explícitos e teto de custo Decimal. Sem preço, tarifa, modelo/currency/vigência compatível, cobertura integral ou orçamento suficiente, o resultado é negativa determinística e sem chamada externa.
4. Novos testes internos cobrem isolamento, custos desconhecidos, idempotência, fallback, currencies incompatíveis, snapshots ausentes, limites inválidos e orçamento excedido.

## Limitações de engenharia ainda a construir

- A previsão depende de **limites de tokens verificados** e de suporte efetivo a esses limites no adapter do provedor; os parâmetros ainda não são impostos por todos os adapters. Não usar previsão isolada como garantia de gasto máximo.
- Falta armazenar e reservar orçamento financeiro de forma transacional entre workers, reconciliar custos estimados/oficiais e definir limites por tenant/unidade/capability com origem na autoridade comercial do Assistant.
- Faltam a política de custo desconhecido, resolução de eventos ambíguos, conversão de moeda (quando aprovada), conciliação oficial do provedor e alertas FinOps.
- Essas são **tarefas de construção de software** e devem continuar agora com mocks/fixtures. Credenciais reais, provedores vivos, Vault, TLS, publicação e homologação ficam somente para a etapa externa final.

## Sequência técnica seguinte

1. Projetar e implementar ingestão autenticada/revisionada das políticas de quota e orçamento do Assistant para o Core, com replay protection, isolamento e testes.
2. Implementar saldo/reserva/settlement monetário persistente, inclusive concorrência e fallback.
3. Integrar preflight aos adapters com limites de tokens de fato respeitados e ledger de attempts.
4. Encerrar todos os gates de software da F3; avançar para construção da F4, sem aguardar a homologação externa.

**Fonte de autoridade:** decisão Build First em `faabio3131/-FM-Assistant-Base/docs/governance/F3_BUILD_FIRST_EXTERNAL_HOMOLOGATION_LAST_2026-10-18.md`. Sem merge, deploy ou uso de segredo real implícito.
