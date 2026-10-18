# ADR-009 — Todos os recursos em todos os planos, com franquias e preços governados pela FM

**Decisão do proprietário:** 2026-10-18  
**Estado:** APPROVED para construção interna, sem configuração externa  
**Referências:** ADR-004, ADR-008, F3/F9, Kordena `faabio3131/fm-ai-platform` (leitura, sem modificação)

## Regra comercial constitucional do produto

**Todos os planos do VendeAtendeIA oferecem as mesmas funcionalidades.**
Não haverá feature gating por plano, menu bloqueado, agente exclusivo,
módulo premium inacessível ou upgrade exigido para *abrir* uma função.
Um cliente com licença válida poderá acessar todas as funções sujeitas
apenas a RBAC, requisitos de segurança e disponibilidade do próprio produto.

**A distinção entre planos é exclusivamente quantitativa:**
franquias de consumo, capacidade/volume e seu preço comercial.
Exemplos de medição: requests de IA, tokens imput/output/cache, tempo
de áudio, mensagens, armazenamento, quantidade de operações, usuários e
unidades. Limite de volume consumido pode bloquear **a próxima operação
mensurável** após esgotar a franquia, nunca desabilitar uma funcionalidade
inteira previamente por um `plan_code`.

**Preços e limites são exclusivamente editáveis pela FM Tecnologia**
por operadores corporativos autorizados (Command).
Os valores NÃO são fornecidos/editáveis pelo tenant, navegador,
provider de IA nem hardcoded no código. Não existe preço/quantidade
padrão nesta ADR. A FM poderá criar, publicar, retirar e alterar
valores por **novas revisões versionadas** com histórico e auditoria.
Planos já contratados permanecem pinados à revisão correspondente até
migração governada. O cliente visualiza, não edita, sua franquia.

## Autoridade e fluxo único

1. **Command/FM corporativa**: define `product_id`, `plan_code`,
   `plan_revision`, moeda, preço comercial, periodicidade, franquias,
   limites operacionais, política de overage (padrão: hard stop), e
   alteração futura. Exigir RBAC corporativo, step-up e auditoria.
2. **Assistant SaaS**: mantém a assinatura/tenant, revisão vinculada,
   período, estado da licença, alterações de contratação, quotas
   autorizadas e políticas de vigência; entrega ao Core apenas uma
   projeção autenticada e expirada das permissões de consumir.
3. **FM Core**: roteia chamadas, aplica quota transacional antes da
   operação, mede todos os attempts/rotas, tokens e gasto interno,
   efetua liquidação conservadora de uso; não decide preço do SaaS.
4. **Cliente**: utiliza todas as funções, acompanha saldo e
   notificações, solicita plano superior ou franquia extra
   quando ofertada. Nunca pode autoelevar cota ou alterar preço.

Se a assinatura não estiver válida, o acesso às operações sujeitas à
licença será negado; isso é regra de licença, não discriminação de função
por tier. Papéis e controles de segurança continuam independentes.

O custo de modelo (FM-managed) é despesa **da FM Tecnologia**. Separar
`commercial_revenue`, `provider_cost_known`,
`provider_cost_unknown`, `infrastructure_cost`, `gross_margin`,
`taxes` e `net_margin`. Sem contabilizar desconhecido como zero.
Se houver BYOK opcional, tratar como modo distinto, sem misturar suas
obrigações/custos na receita de assinatura FM-managed.

## Auditoria de leitura — FinOps do Kordena

Referência GitHub (somente leitura):
`https://github.com/faabio3131/fm-ai-platform`.

**Partes compatíveis e aproveitáveis:**
- `core/ai_pricing.py` — snapshots imutáveis de tarifas por provider/modelo,
  vigência e moeda; já **idêntico** no FM Core.
- `core/ai_cost.py` — cálculo determinístico Decimal, custo oficial,
  estimado e indisponível; já **idêntico** no FM Core.
- `infra/ai_metering.py` — eventos técnicos persistidos por tenant/unidade,
  request/correlation, tokens, resultado, latência e snapshot.
- `infra/ai_finops_projector.py` — projeção incremental em lotes de
  usage bruto para agregados diários, com idempotência por evento.
- `infra/ai_finops_models.py` e `infra/ai_finops_read_model.py` —
  dados agregados, segregação e leitura leve sem full scan.
- `application/ai_finops_dashboard.py` e
  `infra/streamlit_app/ai_finops.py` — tokens, eficiência, fallback,
  cobertura de custo conhecido/ausente e visão por provedor.

**Distinguir o patrimônio da main do desenvolvimento recente:**
- `main` SHA `9a047f98d45574eb7dbf171a9fff8fe5a79fcb2d`
  continha o FinOps analítico/read-model e não o mecanismo completo
  de admissão comercial; essa era a constatação da primeira leitura.
- **PR #230 Draft**, branch `feat/kordena-finops-pricing-metering-20261018`,
  HEAD `691ba84edd1cd663278fb868035b6d1169e90610`,
  **já implementa um Budget Guard candidato** (`infra/ai_budget_guard.py`),
  ledger monetário transacional PostgreSQL por tenant/unidade/capability
  e ciclo de assinatura (`infra/ai_budget_sqlalchemy.py`), pré-reserva
  por attempt do AIModelRouter, liquidação com Decimal, pendência no
  timeout, replay fail-closed e provisionamento a partir da assinatura
  (`application/ai_budget_provision.py`).
- A mesma PR implementa catálogo de tarifas configurado em control plane
  (`application/ai_pricing_runtime.py`), consulta segura de franquia ao
  cliente com alertas 70/90/100% sem expor USD ou custo interno
  (`application/ai_franchise_customer_view.py`) e contrato detalhado em
  `docs/commercial-platform/AI_FINOPS_FRANCHISE_RUNTIME_CONTRACT_2026-10-18.md`.
  O cadastro de preço comercial e franquia foi planejado para o Command.
- Essa versão ainda está **Draft com workflows falhando** na PR #230,
  sem certificação integral, merge ou homologação real comprovada.
  Não copiar nem declarar operação pronta sem corrigir/reexecutar
  os testes pertinentes e revisar as fronteiras de autoridade.
- **FM Command PR #91**, branch candidata com SHA
  `7fde1e1c95d7e77547e5b6f088939311be06518f`,
  também **Draft**: editor de preço/periodicidade em BRL e franquia
  `ai.budget.<capability>` em USD interno, validação de valores
  decimais sem float, preview, step-up e workflows corporativos
  de `plan_version.*` / `price.*`. Seus 3 workflows exibidos
  estavam SUCCESS na inspeção, porém a PR permanece aberta, não
  representa publicação nem homologação. **Reaproveitar o padrão**
  de editor versionado/autoridade FM, adaptando-o a
  `product_id=VENDEATENDEIA`, planos sem feature gating, preços
  configuráveis e quotas de tokens/requests além do orçamento em USD.
  Não copiar IDs fixos de quatro planos do Kordena.
- **Diferença para VendeAtendeIA:** o budget inicial do Kordena é em
  USD por **unidade** e por capability; nosso SaaS também exige tetos
  de tokens, requests, capacidades e, quando configurado, orçamento
  agregado por tenant compartilhado entre unidades. Entitlements
  `enabled` por capability no Kordena **não podem ser traduzidos
  em feature gating**: no VendeAtendeIA todas as funções são acessíveis
  em qualquer plano, limitada apenas a quantidade consumida.
- Em `infra/ai_finops_projector.py`, tokens ausentes são somados como
  `0` nos agregados: o Core não deve confundir tokens desconhecidos com
  uso real zero para enforcement.
- O `_event_id` do metering original não usa ID específico de attempt,
  rota nem snapshot: rotas distintas do mesmo provider/model com mesmo
  instante podem colidir. O Core deve preservar ID de tentativa único
  e deduplicação exata, nunca suprimir consumo de fallback.
- Conforme o provedor, `cached_tokens` pode ser **subconjunto dos
  input_tokens**, não uma terceira quantidade adicional ao total:
  a regra de medição por modelo deve definir como interpretar cache
  para evitar dupla contagem no teto comercial e cálculo financeiro.
  Uso `None` de tokens nunca autoriza reembolso automático nem
  permite afirmar consumo zero.
- O limite de tokens de saída precisa ser mandado ao provider antes
  da chamada; limites de input e contagem de áudio exigem contrato e
  estimador apropriados por adapter/capability para reserva conservadora.
- O projetor agrega por dia e serve dashboard, mas **não é fonte de
  verdade transacional** para autorizar nova chamada concorrente.
  Não usar read-model atrasado para calcular saldo disponível em
  tempo real.
- Kordena agrega custo por moeda (correto); FX não deve ser feita
  implicitamente, e relatórios da FM precisam também de `product_id`
  e visão cross-SaaS, ausentes nos buckets de Kordena.

**Decisão de reutilização:** preservar Kordena inalterado;
reaproveitar da PR #230 **os padrões** de Budget Guard, ledger monetário
Decimal transacional por attempt, autorização anterior ao provedor,
reconciliação de timeout, sincronização da assinatura com o orçamento
e visão do cliente sem custos internos; reaproveitar da `main`
metering, projeção diária e dashboard. **Integrar ao Core existente**
(`QuotaReservations`, `PersistentCircuit`, `AIUsageLedger`,
`FinOpsPreflight`) sem criar segunda fonte de verdade para a mesma
franquia. Para o VendeAtendeIA, manter proteção de teto por tenant,
plano revisionado e dimensões tokens/requests além de orçamento FM.
Não duplicar `ai_cost`/`ai_pricing`, cujos blobs já são idênticos.
Todos os ajustes necessários devem ser feitos nos repositórios do
novo SaaS, não no Kordena.

## Casos de aceitação interna obrigatórios

- Dois planos com **mesmo conjunto de funções**, limite quantitativo
  diferente; ambos conseguem utilizar todas as features enquanto há saldo.
- FM altera/versão preços e limites por autoridade corporativa, com
  auditoria; cliente não modifica limites nem consegue publicar plano.
- Um tenant com duas unidades não ultrapassa o orçamento compartilhado
  com chamadas concorrentes; tentativa bloqueada nunca aciona provedor.
- Saldo insuficiente em qualquer métrica causa rollback atômico;
  requests idempotentes não produzem provider call duplicada.
- Custo/token ausente ou timeout não equivale a zero; manter reserva
  pendente, reconciliar e alertar com processo governado.
- Dashboard mostra capacidade total, usado, reservado, restante,
  renovação e alertas; FM Command também exibe custos, margem e saúde,
  segregando produtos/assinaturas/tenants.
- Alterações de planos e upgrade respeitam data efetiva, proration
  quando previsto, revision, vigência e revogação sem ampliar cota
  em duplicidade; todos os cenários testados com mocks e PG descartável.

## Estado da construção

**CURRENT:** Reader `PlanLimitResolver`, `PlanVersionORM`,
`PlanLimitORM`, `QuotaReservations.reserve_bundle/settle_bundle`,
`usage_snapshot`, ledger, provider token output cap e preflight técnico.

**PENDENTE (software):** API/painel FM de edição de planos, preços e
franquias; publicação/revogação de revisões, entitlement projection
autenticada Command→Assistant→Core, vinculação e mudança de assinatura,
guards obrigatórios em todos os caminhos, limites de input, accounting
final e alertas/UX. Não declarar `BUILD_COMPLETE` até testes verdes.

**PENDENTE (homologação externa somente ao final):** gateways reais,
credenciais/vault, provedores reais, TLS, pagamentos, staging/prod.
Não bloqueiam construção.
