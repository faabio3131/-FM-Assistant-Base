# F3/F9 — Construção interna: contrato de planos, licença e consumo

**Data:** 2026-10-18
**Classificação:** implementação incremental de software e testes sintéticos;
não é homologação externa nem lançamento.
**Autoridade:** ADR-009: todas as funcionalidades em todos os planos;
a FM define preços e franquias, e o Core mede/limita consumo.

## Construção implementada

### FM Command (corporativo)

- Editor de planos versionados por produto, preço BRL em centavos e
  franquias positivas por métrica/período, sem feature gating.
- Publicação exige autoridade FM e step-up de senha, audit intent e
  gravação do outbox na mesma transação.
- `assistant-plan-outbox-dispatcher.ts` dispõe de envelope assinado
  com HMAC e path específico para publicar revisão no Assistant.
- `signAssistantPlanLicenseBind` constrói envelope diferente, também
  assinado e com domínio criptográfico separado, para vincular
  **uma licença existente** à revisão aprovada. Não dispara chamadas
  externas nem cria assinaturas de pagamento por si só.

### FM Assistant (fonte de verdade da licença)

- `CommandPlanProjectionService` recebe revisão comercial governada;
  valida assinatura, organização FM, produto, timestamps, nonce,
  integridade do JSON e imutabilidade da revisão.
- `GovernedPlanLicenseBinding` vincula revisão já publicada a tenant
  ativo e assinatura/trial vigente, sem alterar/estender período ou
  status de pagamento. O mesmo grant é idempotente com nova nonce;
  replay literal é negado. Mudança de revisão já vinculada exige
  workflow distinto de upgrade/downgrade com regras de período.
- Endpoints internos ocultos `/internal/v1/command/assistant-plans/project`
  e `/bind` não admitem autoridade do cliente. Auditoria de concessão
  em `assistant_plan_binding_audit`; migration aditiva `0011`.
- `PlanConsumptionView` resolve sempre tenant/unidade da sessão humana
  com `billing.read`, plano e revisão fixados, janela e validade.
  Responde via `GET /v1/plan/consumption`.
- `GET /v1/plan/consumption/dashboard` traz painel responsivo com
  franquias, saldo quando confirmado, estado desconhecido conservador
  quando telemetria não chegou, sem expor custo de provider/FM e sem
  barra de progresso falsa em caso de ausência de medição.
- `CoreQuotaUsageHTTPReader` consulta Core via serviço autenticado
  usando HTTPS e request scope de sessão; somente considera saldo
  observado quando tenant/unidade/métrica/escopo, revisão, limite,
  janela, atualidade e inteiros do ledger são consistentes.
  Falha de rede, redirecionamento, preço interno e resposta divergente
  nunca são convertidos em zero ou cota renovada.

### FM Core (execução e medição)

- `GET /v1/plan/usage` exige serviço autenticado e retorna quota de
  um escopo exato no ledger PostgreSQL, com revision, janela,
  consumido, reservado, restante e horário de medição.
- Sem policy carregada, sem engine persistente ou sem serviço autenticado
  a API falha fechada.
- Motor de reservas transacionais, guard por plano e metering por
  tentativa continuam em desenvolvimento e disponíveis como módulos
  internos. A composição comercial não recebeu ativação automática.

## Provas internas

- Testes de OAuth/sessão e RBAC existentes mantidos.
- Testes sintéticos para HMAC, tampering, replay, vinculação inicial,
  período de trial imutável, upgrade recusado sem governança e auditoria.
- Dashboard protegido por sessão: outro tenant não pode ser consultado
  por querystring; custo privado não é renderizado; sem telemetria,
  `remaining_units` é `null`, nunca zero.
- Leituras reais de saldo em PostgreSQL descartável e transporte HTTP
  simulado; timestamps, escopo e revisão divergentes são rejeitados.
- Nenhuma migration executada em banco não descartável.

## Pendências de CONSTRUÇÃO — não esperar ambiente real

1. Conectar a concessão de assinatura do billing ao signer/dispatcher
   corporativo, com outbox idempotente, auditoria e workflow de upgrade;
   não permitir concessão por tenant e não resetar saldo no meio do ciclo.
2. Projetar sincronização autenticada/expirável de políticas do Assistant
   para o Core e ligar `PlanUsageGuard` ao composition root, sem
   execução de IA sem reserva válida; incluir revogação imediata.
3. Exigir contadores oficiais por attempt, guarda de input tokens e
   fallback, política de consumo desconhecido/compensação, custo FM e
   dashboard consolidado/alertas de plano.
4. Executar contratos E2E inteiramente sintéticos Command→Assistant→Core,
   testes de concorrência, abuso, rollback e revisão independente interna.

**Pendências externas adiadas:** provedores vivos, Vault, gateways de
pagamento, domínio, rede TLS, deploy e homologação de produção;
não impedem a construção.

**Classificação final:** F3/F9 `BUILD_IN_PROGRESS`; F4 ainda
`NOT_STARTED` até conclusão de código F3. Não declarar funcionalidade
comercial completa nem operação real.

## Avanço interno adicional — alertas e projeção canônica de franquias

- `PlanConsumptionView` calcula `committed_units` somando consumo
  confirmado e reservas pendentes, com `utilization_percent` e níveis
  `normal`, `warning` (>=70%), `critical` (>=90%) e `blocked` (>=100%).
  Leitura indisponível gera `unknown`, sem fabricar saldo.
- Painel do cliente apresenta consumo + reservas, alerta graduado e
  mantém confidenciais preços de providers e custos internos da FM.
  HTML trata dados como texto escapado, sem executar marcações do cliente.
- `LicensedQuotaManifestService` fornece uma projeção **somente leitura**
  de todos os recursos/regras de uma revisão de plano efetivamente fixada
  à licença ativa, validando tenant/unidade, revisão, prazo e presença
  obrigatória dos limites de requests e tokens. Mudança de status da
  assinatura para suspensa interrompe a emissão de manifestos.
- O manifesto **não deve ser consumido diretamente da entrada do
  navegador**: seu transporte Assistant→Core ainda necessita assinatura,
  autorização, TTL, versão monotônica e revogação que falhe fechada.
- Testes sintéticos: tenant isolado, revisão imutável, assinatura
  suspensa, mensagens de alerta e desconhecidos conservadores.

**Status:** funcionalidades adicionais implementadas; gates obrigatórios
precisam estar verdes no HEAD atualizado antes de declaração de
certificação. Não ativou provedores, migração produtiva ou deploy.
