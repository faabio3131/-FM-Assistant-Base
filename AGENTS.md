# AGENTS.md — FM Assistant + Sales AI

**Status:** NORMA OPERACIONAL OBRIGATÓRIA DO REPOSITÓRIO  
**Escopo:** todo agente, executor, modelo, automação ou ferramenta que altere este repositório  
**Produto:** FM Assistant + Sales AI V1

---

## 1. MISSÃO

Executar o Prompt Mestre até a conclusão comercial com máxima autonomia operacional, sem perder sequência, governança, evidência ou segurança.

O agente deve trabalhar como executor disciplinado, não como improvisador.

Objetivos deste arquivo:

- impedir delírio/alucinação de estado;
- impedir salto de fases;
- impedir declaração falsa de conclusão;
- impedir irregularidades de execução;
- permitir correção autônoma;
- permitir avanço automático quando o gate estiver 100% verde;
- permitir merge automático quando todos os critérios de merge estiverem 100% verdes;
- manter deploy/produção sob autorização humana explícita.

---

## 2. HIERARQUIA DE AUTORIDADE

Ler e obedecer nesta ordem:

1. Documento Mestre Nova FM Tecnologia v2.0.
2. Padrões de Construção Nova FM.
3. Este `AGENTS.md`.
4. `docs/governance/SYSTEM_DESIGN_MASTER_V1.md`.
5. ADR-001 a ADR-006.
6. `docs/governance/PROMPT_MESTRE_EXECUCAO_INTEGRAL_V1.md`.
7. `docs/governance/EXECUTION_TRACKER_MASTER.md`.
8. contratos e documentação técnica vigente.
9. CURRENT comprovado por código, banco, CI, logs e testes.

Em conflito, a autoridade superior prevalece.

Memória de chat, comentário antigo, suposição do modelo ou documentação obsoleta nunca prevalecem sobre CURRENT comprovado.

---

## 3. REGRA ANTI-DELÍRIO

O agente é proibido de preencher lacunas com suposição.

Antes de afirmar qualquer estado, classificar como:

- **FATO CONFIRMADO**
- **CURRENT**
- **TARGET**
- **DECISÃO**
- **PENDÊNCIA**
- **HIPÓTESE**
- **BLOCKED_EXTERNAL**

Regras:

- TARGET nunca é CURRENT.
- Arquivo existente não prova funcionalidade completa.
- Código existente não prova teste.
- Teste unitário não prova homologação.
- Deploy não prova saúde.
- PR aberta não prova readiness.
- Resultado antigo não prova HEAD atual quando código relevante mudou.
- Ausência de erro visível não equivale a sucesso.
- Nunca inventar CI verde, credencial válida, provider homologado, migration aplicada ou integração funcional.

Toda afirmação importante precisa de evidência verificável.

---

## 4. REGRA DE SEQUÊNCIA

A execução deve seguir estritamente F0 → F1 → F2 → ... → F15 conforme o Prompt Mestre.

É proibido:

- pular fase;
- executar fase posterior porque "parece independente";
- marcar fase concluída parcialmente;
- avançar com gate vermelho;
- avançar com gate não executado;
- converter BLOCKED_EXTERNAL em GREEN por interpretação;
- iniciar redesign paralelo fora do escopo.

Exceção: tarefas preparatórias que não alterem CURRENT nem violem dependências podem ser feitas antecipadamente, mas não podem fechar nem promover fase futura.

---

## 5. EXECUTION TRACKER OBRIGATÓRIO

A autoridade de progresso é:

`docs/governance/EXECUTION_TRACKER_MASTER.md`

Antes de começar qualquer tarefa:

1. ler o tracker;
2. identificar a fase ativa;
3. confirmar o último gate;
4. confirmar HEAD/branch/PR;
5. verificar blockers;
6. continuar exatamente do próximo item não concluído.

Após cada unidade relevante:

- registrar alteração;
- registrar evidência;
- registrar testes;
- registrar CI;
- registrar risco;
- atualizar status da tarefa;
- nunca apagar histórico de falha; marcar superseded/resolved.

O tracker impede reinício acidental, repetição e salto de cronograma.

---

## 6. ESTADOS DE GATE

Cada fase e subgate deve possuir um destes estados:

- `NOT_STARTED`
- `IN_PROGRESS`
- `RED`
- `BLOCKED_EXTERNAL`
- `GREEN`

### GREEN

Só usar quando **100% dos critérios obrigatórios aplicáveis** estiverem aprovados com evidência.

### RED

Existe falha técnica, funcional, segurança, teste, migration, contrato ou regressão.

### BLOCKED_EXTERNAL

A validação não pode ser concluída por causa externa verificável, por exemplo:

- billing do GitHub;
- provider fora do ar;
- credencial externa ainda indisponível;
- ambiente oficial indisponível.

BLOCKED_EXTERNAL não é GREEN e não permite declarar a fase concluída.

---

## 7. AUTONOMIA DE EXECUÇÃO

O agente está autorizado a trabalhar autonomamente dentro do Prompt Mestre.

Não pedir autorização para:

- analisar CURRENT;
- criar/editar código dentro da arquitetura aprovada;
- criar migrations não destrutivas;
- criar/editar testes;
- corrigir bugs;
- corrigir lint/typecheck/build;
- corrigir CI;
- corrigir regressões;
- refatorar somente o necessário para atender requisito aprovado;
- atualizar documentação;
- atualizar tracker;
- criar commits;
- fazer push;
- atualizar PR;
- repetir testes;
- repetir gates;
- executar auditorias internas;
- corrigir falha detectada e retestar;
- avançar para a próxima tarefa/fase quando o gate anterior estiver GREEN 100%.

O padrão é:

```text
executar
→ testar
→ falhou?
   ├─ sim → diagnosticar → corrigir → retestar
   └─ não → auditar evidência → marcar GREEN → avançar
```

Não interromper o usuário para pedir autorização de correção ordinária já coberta por este documento.

---

## 8. AUTORIZAÇÃO DE MERGE

**MERGE ESTÁ PRÉ-AUTORIZADO** quando, e somente quando, todas as condições abaixo forem verdadeiras:

1. fase/entrega correspondente = `GREEN`;
2. todos os testes obrigatórios aplicáveis = verdes;
3. lint/typecheck/build aplicáveis = verdes;
4. migrations aplicáveis = validadas;
5. tenant isolation aplicável = verde;
6. security gate aplicável = verde;
7. CI obrigatório = verde;
8. nenhuma STOP condition aberta;
9. documentação/tracker atualizados;
10. diff revisado;
11. PR mergeable;
12. nenhuma evidência contraditória.

Se qualquer condição não estiver 100% verde, **merge é proibido**.

O agente não precisa pedir nova autorização ao usuário quando essas condições forem satisfeitas.

Após merge:

- verificar CI pós-merge;
- verificar regressões;
- registrar SHA;
- atualizar tracker;
- só então considerar integração concluída.

---

## 9. BLOQUEIO HUMANO: DEPLOY / PRODUÇÃO

A execução autônoma termina antes de qualquer ação de deploy/cutover de produção.

Exigem autorização humana explícita:

- deploy em produção;
- cutover de domínio/tráfego;
- promoção final para produção;
- migration em banco de produção como parte do release;
- ativação de credenciais reais que efetivamente coloquem tráfego/operação de produção em funcionamento;
- ação irreversível equivalente de produção.

Preparação, código, testes, staging, documentação e merge podem avançar conforme gates.

Nunca interpretar "merge autorizado" como "deploy autorizado".

---

## 10. CORREÇÃO AUTÔNOMA OBRIGATÓRIA

Se um gate falhar, o agente deve:

1. preservar evidência da falha;
2. identificar causa raiz;
3. verificar se a correção respeita System Design/ADR;
4. aplicar a menor mudança coerente;
5. adicionar/ajustar teste de regressão quando aplicável;
6. executar novamente o gate;
7. repetir até GREEN ou BLOCKED_EXTERNAL real.

É proibido:

- remover teste para fazer CI passar;
- afrouxar regra sem decisão;
- ocultar erro;
- marcar warning crítico como aceitável sem análise;
- trocar provider/framework para escapar de bug;
- bypassar segurança;
- criar exceção silenciosa;
- desabilitar gate obrigatório.

---

## 11. PROIBIÇÕES ABSOLUTAS

### Kordena

`faabio3131/fm-ai-platform` é **READ-ONLY** para este projeto.

Proibido:

- commit;
- branch;
- PR;
- migration;
- configuração;
- banco;
- deploy;
- qualquer escrita.

### Produto

Proibido:

- hardcode por cliente;
- alterar código para cadastrar tenant;
- alterar código para trocar chave/token de cliente;
- secrets no repositório;
- secrets no frontend;
- secrets em logs;
- segundo motor conversacional;
- segunda autoridade de tenant;
- segunda autoridade de licença;
- segundo domínio CRM concorrente;
- bypass comercial do FM Core;
- regra crítica apenas no frontend;
- UI temporária conhecida como descartável;
- arquitetura paralela;
- migration destrutiva improvisada;
- cross-tenant access;
- autorização por ocultação de botão;
- provider direto no domínio;
- merge com gate incompleto;
- deploy sem autorização humana.

---

## 12. REGRA DE CONFIGURAÇÃO POR CLIENTE

Novo:

- cliente;
- unidade;
- usuário;
- chave;
- token;
- credencial;
- provider;
- canal;
- integração;
- plano;
- quota;
- capability;
- política tenant-specific;

deve ser configurável por dados/control plane/vault/entitlement.

Não pode exigir:

- branch;
- commit;
- alteração de código;
- build especial;
- deploy específico por cliente.

Novo código é aceitável apenas para criar **nova capability/tipo de integração da plataforma**, nunca para cadastrar uma instância de cliente.

---

## 13. MONITORAMENTO DA EXECUÇÃO

Durante execução longa, o agente deve monitorar:

- branch correta;
- HEAD;
- PR;
- diff;
- testes;
- CI;
- migrations;
- dependências;
- segurança;
- tenant isolation;
- documentação;
- blockers externos;
- regressões.

Antes de avançar de fase, revalidar que não houve alteração concorrente que invalide a evidência.

Se HEAD mudar inesperadamente:

1. parar promoção;
2. descobrir a origem;
3. reavaliar diff;
4. rerodar gates afetados.

---

## 14. CI E BLOQUEIOS EXTERNOS

CI obrigatório não pode ser presumido.

Se CI não iniciar por causa externa, registrar `BLOCKED_EXTERNAL` com evidência.

Exemplo atual conhecido em 2026-10-17/18:

GitHub Actions recusou iniciar jobs por problema de Billing/Plans da conta.

Isso:

- não é falha de código;
- não é GREEN;
- não autoriza merge que dependa daquele gate;
- deve ser reexecutado quando o serviço for restabelecido.

Testes locais podem produzir evidência auxiliar, mas não falsificam CI remoto obrigatório.

---

## 15. SEGURANÇA E STOP CONDITIONS

Parar promoção/merge imediatamente se houver:

- cross-tenant access;
- auth bypass;
- authorization bypass;
- privilege escalation;
- secret exposure;
- vazamento relevante;
- risco crítico de fraude;
- corrupção/perda de dados;
- ação destrutiva não autorizada;
- migration destrutiva não planejada;
- conflito grave de autoridade;
- vulnerabilidade crítica;
- evidência contraditória.

Corrigir autonomamente quando estiver dentro do escopo aprovado.

Se exigir mudança material de decisão arquitetural, registrar e escalar.

---

## 16. EVIDÊNCIA MÍNIMA

Cada fase deve deixar:

- commit(s);
- diff identificável;
- testes;
- resultados;
- CI;
- migration evidence quando houver;
- security evidence;
- PR;
- tracker atualizado;
- riscos/pendências;
- SHA final.

A frase "feito" sem essas evidências não possui valor de gate.

---

## 17. REGRA DE FINALIZAÇÃO

Nenhum agente pode declarar:

- HOMOLOGADO;
- PRONTO PARA PRODUÇÃO;
- COMERCIALMENTE DISPONÍVEL;

apenas porque o código está implementado.

Esses estados só podem ser usados segundo o Definition of Done do System Design e o Prompt Mestre.

---

## 18. LOOP OPERACIONAL RESUMIDO

```text
LER GOVERNANÇA
      ↓
LER TRACKER
      ↓
CONFIRMAR CURRENT/HEAD/PR
      ↓
EXECUTAR PRÓXIMA TAREFA
      ↓
TESTAR
      ↓
RED? ──SIM──> CORRIGIR AUTOMATICAMENTE ──> TESTAR NOVAMENTE
      │
      NÃO
      ↓
AUDITAR EVIDÊNCIA
      ↓
100% GREEN?
  │          │
 NÃO        SIM
  │          ↓
CORRIGIR   ATUALIZAR TRACKER
  │          ↓
  └──────  AVANÇAR FASE
             ↓
      CONDIÇÕES DE MERGE 100%?
             │
       NÃO   │   SIM
        │    │    ↓
        │    └─> MERGE AUTORIZADO
        │          ↓
        │     PÓS-MERGE GREEN
        │          ↓
        └──── CONTINUAR CRONOGRAMA
                   ↓
            DEPLOY/PRODUÇÃO?
                   ↓
            PARAR E PEDIR AUTORIZAÇÃO
```

Este fluxo é obrigatório.

---

## 19. CHECKPOINT F3.7.3 — ORQUESTRAÇÃO INTER-REPOSITÓRIOS (2026-10-18)

Este checkpoint é parte do cronograma F3, não aprovação de F4 nem homologação comercial.

- **Assistant**: autoridade canônica do estado de identidade Core, grants tenant/unidade/capability, revogação e ledger de auditoria. Migration aditiva `20261018_0006`; sem provisionar chaves reais.
- **Core**: consumidor S2S; não pode criar grants, ignorar escopo, trocar BYOK negado por chave FM ou acessar o banco do Assistant.
- **Command corporativo**: `faabio3131/FM-CONTROL-CENTER`, PR #90 Draft; autenticação Better Auth, organização corporativa FM, step-up humano e HMAC Command→Assistant. **Não confundir com `fm-command-v2`, produto comercial separado.**
- **Vetor HMAC entre Node/Python e testes sintéticos** são evidências de contrato; não provam transporte real ou credenciais reais.
- **Gate do Command**: workflow com falha e zero passos de execução é `BLOCKED_EXTERNAL / NOT_TESTED`, jamais PASS ou falha funcional comprovada. Investigar causa e executar gates completos; até isso, PR #90 permanece Draft, sem merge.
- **Assistant e Core**: os gates que estão verdes não substituem CI, segurança, PostgreSQL concorrente ou homologação dos demais participantes.
- **Sequência F3 restante**: (a) testes PostgreSQL de race/revoke/nonces e migrations; (b) integração Command→Assistant real e review independente de segurança; (c) provisionamento/rotação no Vault, TLS/ACL/rate limit; (d) provider catalog real, quota/circuit, homologação e observabilidade; (e) gate F3 100% GREEN e então F4.
- Executar autonomamente correções e testes não destrutivos; se bloqueio externo, registrar evidência sem avançar fase. 
- **Merge das PRs relacionadas a F3** somente após todos os gates aplicáveis 100% GREEN e autorização de merge pré-estabelecida; **deploy/migration de produção, ativação de credenciais reais e cutover exigem autorização humana específica**.
- Nunca utilizar ferramenta de computador remoto para trabalho reproduzível via GitHub ou ambiente de execução próprio; usar somente se indispensável, preservando créditos.

## 20. GATE F3.7.4 POSTGRESQL REAL — GREEN INTERMEDIÁRIO

- Exigir para o gateway Core↔Assistant: migration real de teste PostgreSQL, replay/nonce concorrente, revogação de grant/identidade e trilha de auditoria.
- Novo workflow obrigatório: `.github/workflows/f3-postgres-core-bridge.yml`, CI PostgreSQL 16 efêmero.
- Evidência no SHA de código `6dd2d9f7ebf84fa140ae7380f6f0386387500ca9`: PG push `39139495756` e PR `39139500097` **SUCCESS**; SaaS CI e contrato Core também verdes.
- Foi corrigido o fixture sem afrouxar FK, autenticação ou testes. Histórico RED permanece no tracker.
- **Isso certifica apenas F3.7.4**; NÃO certifica F3 inteira, Command PR #90, provider/Vault real nem produção. Gate do Command continua bloqueado por jobs encerrados sem executar etapas.
- Próxima tarefa permitida dentro de F3: desbloquear CI Command, revisão independente e E2E Node Command→Python Assistant; depois Vault/rede/provider/quotas/circuit gates. Sem avanço a F4 enquanto F3 não estiver 100% GREEN.


## 21. F3.7.5 — GATE COMMAND NODE/PYTHON (2026-10-18)

- **Fonte de autoridade:** o FM Command interno `faabio3131/FM-CONTROL-CENTER` PR #90 Draft; nunca `fm-command-v2`.
- Branch Command contém auditoria de tentativas 403/400, testes negativos e um novo contrato cruzado que usa o **cliente assinador Node real** e o **FastAPI ASGI real** do Assistant.
- Suite `tests/f3_command_assistant_cross_runtime.py` vive no Command; Foundation Gate faz checkout pinado do Assistant público em `45b35a6900c59825a987d9db47e98ad18073dec2`. Rede/TLS de produção não são cobertos por essa simulação de transporte.
- **CI Command permanece NOT_TESTED/BLOCKED_EXTERNAL:** os jobs encerraram sem steps, inclusive Foundation `39141786529`, F21 `39141786535` e Cognitive `39141786543`; não declarar teste Node/Python executado.
- **Risco em aberto:** reconciliar mutação commitada no Assistant com eventual falha da auditoria do Command por `command_request_id`; sem repetir operação automaticamente.
- Exigir 100% GREEN real, revisão independente e infra/Vault/provider/quotas antes de merge. F3 global `IN_PROGRESS`, F4 `NOT_STARTED`. Sem deploy, credenciais reais ou migrations produtivas.


## 22. F3.7.6 — PRÉ-AUDITORIA OBRIGATÓRIA DE MUTATION (2026-10-18)

- No Command corporativo, registrar intent persistente antes de mutation S2S, com UUID `commandRequestId` produzido server-side; usar mesmo UUID no corpo HMAC e nas evidências de outcome. Falha da pré-auditoria impede envio.
- Assistant é autoridade transacional de grants e mantém `command_request_id` em seu ledger; resultados HTTP ambíguos **não autorizam** retry cego.
- Exigir reconciliação read-only governada por esse ID antes de certificar ciclo completo; pré-auditoria isolada não é atomicidade interserviços.
- Código e testes permanecem na Command PR #90 Draft e **NÃO CERTIFICADOS** por CI sem steps. F3 GLOBAL IN_PROGRESS; F4 NOT_STARTED; sem merge/deploy/segredos reais/migration produtiva.


## 23. F3.7.7 — SIGNED RECONCILIATION (2026-10-18)

- A mutation no Assistant grava evidência transacional com `command_request_id` único, via índice de unicidade criado pela migration aditiva `20261018_0007`. Reuso do mesmo ID em nova mutation deve falhar integralmente e sem contornar grants/revogação.
- Endpoint interno `/internal/v1/command/core-bridge/status` usa HMAC com caminho canônico próprio, mesmo actor/organização/tenant/unidade/capability e identity configurada para retornar exclusivamente `applied`, `denied` ou `unknown`; não revela segredos, não muta identities/grants.
- `unknown`, indisponibilidade e timeout NÃO autorizam replay da mutation. Monitorar e reconciliar sempre contra auditoria transacional.
- Assistant CI para esta entrega: `c65f05f73546380f1641611d96d6a3bd74c3a0b3`, 6/6 SUCCESS em SaaS, PG16 e contrato Core↔Assistant.
- Command PR #90 introduziu consulta corporativa read-only com Better Auth e step-up, mas CI de seu repositório privado ainda termina sem steps; considerá-lo NOT_TESTED/BLOCKED_EXTERNAL. F3 GLOBAL IN_PROGRESS, F4 NOT_STARTED.
- O ambiente de produção depende de segurança em rede, Vault, rate limit, observabilidade e teste real autorizado pelo proprietário. Sem merge/deploy/segredo real/migration de produção enquanto gates obrigatórios faltarem.

## 24. F3.7.9 — STATUS HMAC NONCE REPLAY GUARD (2026-10-18)

- Assistant passa a persistir nonces válidos de consultas read-only de `/internal/v1/command/core-bridge/status` em `assistant_command_bridge_status_nonce`, com PRIMARY KEY `nonce`, migração aditiva `20261018_0008`.
- A validação de MAC, trusted organization, actor/escopo, key ID, timestamp e step-up ocorre antes de consumir nonce. Nonce é persistido em transação no lookup (inclusive outcome `unknown`); replay idêntico ou concorrente retorna 401. Um lookup não modifica grants/identities nem gera evento de mutação.
- Testes SQLite e PostgreSQL 16 (incluindo concorrência) e migration foram certificados no HEAD funcional `303747d8efe33536af796d75c698bf01864409a5`: **6/6 SUCCESS** em push e PR. Os testes intermediários RED por import sorting e asserção de ledger pré-existente foram corrigidos sem desabilitar regras.
- Nonces de status exigem política de retenção/expurgo auditável e observabilidade antes de escala produtiva; replay nunca deve ser permitido dentro da janela, mesmo após futura limpeza.
- A homologação de ambiente real (rede TLS/ACL, secret manager, política de quotas, circuit breakers, credenciais e revisão independente) não foi feita. **F3 IN_PROGRESS, F4 NOT_STARTED, sem merge/deploy/segredos reais/migrations não descartáveis.**

## 25. DECISÃO SUPERIOR — BUILD FIRST, HOMOLOGAÇÃO EXTERNA AO FINAL (2026-10-18)

- Autoridade: determinação direta do proprietário; ver `docs/governance/F3_BUILD_FIRST_EXTERNAL_HOMOLOGATION_LAST_2026-10-18.md`.
- CONSTRUIR E CERTIFICAR INTERNAMENTE todas as funcionalidades de F3, F4 e fases seguintes de forma autônoma. Não bloquear programação pela falta de chaves, gateway, Vault real, domínio, TLS, provider real ou testes externos. Simular dependências com contratos, stubs e fixtures validados e registrar a prova interna específica.
- GATES DE CONSTRUÇÃO obrigatórios: código, segurança, autorização, isolamento de tenant, lint, testes, migrations descartáveis, concorrência, build e CI real. Fase internamente completa pode iniciar a próxima fase com pendências externas classificadas separadamente.
- HOMOLOGAÇÃO EXTERNA somente DEPOIS de concluir 100% do build: integrações e segredos verdadeiros, rede, infraestrutura real, ensaios com terceiros, cutover. Classificar como `EXTERNAL_HOMOLOGATION_DEFERRED`, nunca como GREEN ou como impedimento à construção.
- Status distintos: `BUILD_IN_PROGRESS`, `BUILD_COMPLETE_INTERNAL_GREEN`, `EXTERNAL_HOMOLOGATION_DEFERRED`, `REAL_HOMOLOGATION_APPROVED`. Não confundir código completo com software homologado em produção.
- Manter autorização especial para ações irreversíveis, deploy, credenciais reais, gastos e migrations não descartáveis. Merge interno pré-autorizado apenas se gates de software verdes, proteção de branches e ausência de deploy implícito forem comprovados.
- Esta decisão substitui apenas a leitura antiga que exigia provas externas para avançar a construção; o restante dos controles de segurança e auditoria continua em vigor.

## F3/F9 — PLANOS E CONTROLE DE CONSUMO POR ASSINATURA (2026-10-18)

- A autoridade canônica de plano, assinatura, trial, estado comercial e entitlements é o FM Assistant. Core não cria, promove ou altera plano comercial por conta própria.
- Catálogo de planos e métricas versionados: `assistant_plan_versions`, `assistant_plan_limits`; `TenantLicenseORM.plan_revision` fixa a versão comercial por tenant. PlanLimitResolver só retorna quotas após validar tenant, unidade, licença, vigência, revisão e escopo; ausência falha fechada.
- Métricas propostas: requests IA, input/output/cached/total tokens, custo técnico interno da FM, áudio, mensagens, usuários, unidades, armazenamento, CRM e automações. Valores e preços dos planos são configuráveis e ainda NÃO definidos comercialmente.
- Um plano deve poder limitar por tenant e/ou unidade; global tenant deve incluir consumo de todas as unidades e não criar quota separada que amplie artificialmente limite.
- Consumo técnico dos modelos é custo da FM Tecnologia; a assinatura comercial é cobrada do cliente e fica no billing do produto, não confundida com o custo interno da IA.
- Nenhum endpoint para tenant autoatribuir quotas, criar versões de planos ou aumentar limite. Projeção Command/Assistant→Core deve ser autenticada, revisionada, anti-replay, expirável, revogável e auditada; construir e certificar internamente antes de produção.
- Core implementou pré-reserva atômica multi-métrica e um ledger por request (tokens/requests/custo) com PostgreSQL 16 concorrente, porém **os guards ainda devem ser integrados ao fluxo comercial completo** antes de declarar funcionalidade concluída. Garantir rollback total se qualquer limite falhar.
- Documento: `docs/governance/F3_F9_PLAN_QUOTAS_AND_AI_USAGE_ARCHITECTURE.md`. Trilha externa permanece adiada conforme diretriz Build First; não bloquear programação por configuração real.

## COMPLEMENTO F3/F9 — REGRAS DE LIMITE TÉCNICO (2026-10-18)

- O Core expõe `QuotaRequirement`, `reserve_bundle` e `settle_bundle` para atomicidade de múltiplas dimensões de um mesmo request, incluindo consumo agregado do tenant contra unidades concorrentes. Testar sempre atomic rollback e idempotência em PostgreSQL 16.
- `ProviderRouteSettings.max_output_tokens` é limite opcional explicitamente encaminhado aos adapters OpenAI-compatible e Gemini; ainda não configura o teto de input nem garante cobrança exata sem uso oficial e validação. Criar pré-reserva de pior caso e conciliação.
- Catálogo de planos tem revisão pinada por licença, não altera clientes anteriores silenciosamente. Tenant desativado/expirado/suspenso ou sem revisão/limite deve falhar fechado ao resolver quota.
- A sincronização autenticada de plano Assistant→Core e todas as interfaces reais de gestão/monitoramento são tarefas de software pendentes, a construir sem dependência de credenciais externas. Fonte: `docs/governance/F3_F9_PLAN_QUOTAS_AND_AI_USAGE_ARCHITECTURE.md`.

## ADR-009 — TODOS OS PLANOS COM TODAS AS FUNÇÕES (18/10/2026)

- Decisão explícita do proprietário: **nenhuma funcionalidade será bloqueada por tier/plano**. RBAC, segurança e licença válida continuam obrigatórios; diferenças de plano apenas em limites quantitativos/volume de uso, período e preço.
- **Somente a FM Tecnologia** poderá configurar, publicar e revisar preços comerciais e franquias, mediante autoridade corporativa Command, versionamento, auditoria e step-up. Tenant não pode elevar quota nem editar preço/limites.
- Reusar seletivamente Kordena: `main` traz pricing/cost idênticos ao Core, metering/agregados/dashboard; **PR #230 Draft** também traz `AIFranchiseBudgetGuard` + ledger transacional Decimal, provisionamento por ciclo e customer view, ainda sem certificação integral. Não usar read-model diário para autorizar operações, nem tratar custo/token desconhecido como zero. Adaptar ao Core atual sem criar ledgers duplicados.
- Fonte canônica aprovada: `docs/governance/ADR-009-ALL-FEATURES-PLAN-CONSUMPTION-AND-KORDENA-FINOPS.md`. Devem ser corrigidos os anteriores conceitos que associavam feature gating/recursos habilitados ao plano. Todos os tiers têm mesmo conjunto de funções.
- Construção pendente: painel FM e publisher de preços/franquias, projeção assinada Command→Assistant→Core, hard stop pré-provider, dashboards e alertas. Homologações externas só depois da conclusão integral do software.

## F3/F9 — PUBLICAÇÃO, VÍNCULO DE LICENÇA E PAINEL DE CONSUMO (2026-10-18)

- `GovernedPlanLicenseBinding` vincula uma licença existente a uma revisão do plano **já publicada pela FM**, por HMAC domain-separated/nonce/corporate organization, com trilha de auditoria (migration `0011`). Não cria assinaturas, não estende trial nem period_ends_at e recusa upgrade implícito sem workflow governado.
- `PlanConsumptionView` e endpoints `/v1/plan/consumption` e `/dashboard` exigem sessão humana e `billing.read`, tenant/unidade provenientes da sessão. Uma querystring nunca determina escopo. Esconder orçamento interno de provider/FM do cliente.
- `CoreQuotaUsageHTTPReader` consulta o Core somente via HTTPS autenticado; exige assinatura implícita pela chave de serviço, tenant, unidade, métrica, revisão de política, franquia, janela e medição recente. Qualquer divergência resulta em `metering_unavailable`, **não zero**.
- A visualização premium exibe franquia e saldo comprovado quando disponível; se não há telemetria confiável, mostra claramente saldo não verificado, jamais barra zero fictícia.
- Contratos de assinatura/billing e upgrade continuam pendentes de código. Sincronização de policy/quotas para Core e ativação do PlanUsageGuard no composition root também pendentes. Sem bypass por falta de ambiente real: continuar com mocks, testes e PG descartável.
- Referência e evidências: `docs/governance/F3_F9_PLAN_BINDING_AND_USAGE_INTERNAL_CERTIFICATION.md`. F3/F9 BUILD_IN_PROGRESS, homologação externa deferida; F4 ainda não iniciada.

## F3/F9 — CUSTOMER USAGE ALERTS + LICENSE QUOTA MANIFEST (18/10/2026)
- Plano: todas as funções disponíveis em todos os tiers, diferenciados só por franquia e preço FM. O `PlanConsumptionView` agora informa usado, reservado, comprometido, restante e faixa de alerta (70/90/100%). Nunca presumir telemetria ausente como 0.
- `LicensedQuotaManifestService` prepara política de quotas a partir de tenant/unidade e licença canônica com plan_code+revision fixados. Negar assinatura suspensa, expirada, mudança de revisão ou recursos essenciais ausentes. Manifesto não é permissão de cliente para editar limite, nem deve ser encaminhado sem canal interno assinado/revogável ao Core.
- Alertas são cálculos de leitura e não substituem `QuotaReservations` transacional do Core. Cobrar do cliente só assinatura/serviços aprovados; custo de IA FM-managed é da FM.
- Trilha externa permanece diferida até build completo. Não promover F3 global antes da sincronização autorizada em runtime, FinOps e demais gates internos. Sem deploy nem alteração de Kordena.


## F3/F9 — CORE SIGNED PLAN GRANT READ-THROUGH (2026-10-18)

- Route `POST /internal/v1/assistant/core-plan-grant` is a private service-only issuer, disabled without `FM_ASSISTANT_CORE_PLAN_SIGNING_KEY`; key requires minimum length and cannot reuse Command/Core/Vault/session signing values.
- Request HMAC is domain-bound to the method/path and exact body; a fresh challenge is copied into the separately signed short-lived response (max 30s), preventing reuse by a different Core request. Canonical license, tenant/unit and pinned published plan revision are read on every request; expired/suspended/invalid licenses deny. Response is no-store and signed on the exact returned JSON bytes.
- Functional SHA `9b971d64ed8224641c58a3be5def886f7fb6d16d`. SaaS Foundation CI `39190924170` SUCCESS; Core Assistant Authenticated Bridge Contract `39190924237` SUCCESS; F3 PostgreSQL Core Bridge Security Gate `39190924161` SUCCESS.
- Transport and issuer are internally tested but **not** proof of mutual TLS/private network, production key, mandatory Core runtime quotas or immediate revocation of every already issued grant. Remaining integration/guard gates are BUILD_IN_PROGRESS. No actual provider/production secrets/deploy/merge; Kordena and FM Command V2 untouched.


## WhatsApp FM-managed QR onboarding — INCREMENTAL BUILD (2026-10-19)

- User approved the new onboarding requirement from a third-party proposal, **not** adoption of its example code. Implemented in existing `Integration & Credential Control Plane` with provider `whatsapp_evolution`, FM-only HTTPS origin and master key, tenant/unit scoped draft connections, opaque instance ID, encrypted individual token and no-store QR response.
- Backend entry points: `POST /v1/channels/whatsapp/qr/provision` (`integration.manage`), `GET /v1/channels/whatsapp/qr/{connection_id}` (`integration.read`); no customer exposure of FM secret, instance token or arbitrary VPS URL.
- Fail closed on missing FM configuration, insecure URL, invalid QR, remote create ambiguity, cross-tenant lookup, repeated provision, and generic customer lifecycle changes. PostgreSQL advisory locking serializes first instance creation per tenant/unit.
- Code: `src/fm_assistant/channels/whatsapp_evolution.py`, `src/fm_assistant/evolution_onboarding.py`, `integration.py`, `integration_repository.py`, `integration_service.py`, `settings.py`, `api.py`. Synthetic tests: `tests/saas/test_evolution_onboarding.py`.
- This **does not yet deliver a complete live WhatsApp channel**. Keep event-webhook authenticity, deduplication/inbox queue and outbound routing, QR status lifecycle/reconnect/remote revocation, real provider-edition contract, React onboarding UI, multiworker PG gate and independent review as pending engineering gates. See `docs/governance/WHATSAPP_QR_FM_MANAGED_ONBOARDING.md`.
- GitHub Actions were still QUEUED on latest functional commits at this checkpoint; do not label new feature certified until workflow PASS on exact HEAD. Existing F3 Core reconciliation checkpoint is preserved; do not repeat F3 or promote F4. No production secret, deploy, merge or external homologation; Kordena and FM Command V2 untouched.


## WhatsApp QR FM-managed — 2026-10-19 customer panel + synthetic message E2E

- New customer-facing secured HTML dashboard `/v1/channels/whatsapp/qr/panel`: owner/authorized human session, mobile-friendly standalone UX, signed nonce CSP, no-store, QR refresh, automatic 8-second polling, no external JS or asset dependencies. `GET /v1/channels/whatsapp/qr/current` is tenant/unit-scoped and read-only. No leaked FM global key or individual instance token.
- `EvolutionRuntime` consumes only signed normalized events from the FM ingress trust boundary; verifies connection_id, stored opaque instance, timestamp and HMAC; rejects unknown/revoked/inactive connections. Signed `connection.update` events transition connecting->active or active->degraded. Message events reuse the existing Assistant Conversation Engine and `WhatsAppInboundRepository` dedup ledger with HMAC sender reference; individual encrypted connection token is used for a single outbound reply attempt. Network/unknown outcomes quarantine the inbound message in `reconcile_required`, not blind retry.
- New `EvolutionClient.send_text` uses per-instance token in BOTH HTTP transport code paths; earlier CI tests exposed a mistaken global key in injected client mode and that was corrected. Tests `tests/saas/test_evolution_runtime.py`, `tests/saas/test_evolution_onboarding.py`, plus existing bridge and PostgreSQL suites.
- Functional SHA `85d49c4f0ce95a26a79c78f5c63ee07234a37c55`; SaaS Foundation CI run `39291893839` SUCCESS (131+ cases), F3 PostgreSQL Core Bridge Security Gate `39291893849` SUCCESS, Core Assistant Authenticated Bridge Contract `39291895488` SUCCESS. No merge or deploy.
- **Not production-ready yet:** signed ingress verifier requires a genuine authenticated FM-native Evolution webhook broker (native VPS callbacks must NOT directly set trusted HMAC headers); binding the chosen provider release/version; durable queued inbox/outbox and crash recovery; remotely verified disconnect/delete/reprovision and account ownership; full tenant UX accessibility and browser security review; PostgreSQL concurrency and independent security audit. Do not claim live WhatsApp account integration or external homologation. F3 prior checkpoint remains separately paused, not promoted.


## Corporate WhatsApp QR display cap (2026-10-19)
- Approved by FM: default 45 seconds. Implemented customer UI fail-safe: hide unchanged QR after 45s from first display (not reset by 8s polling); show a changed QR as new. Verified against synthetic CI on functional commit `bd38b0f5ba8c7dd7a495273bd3327c1d0082fbb3` (Assistant gates all 3 SUCCESS).
- Central policy authoring in actual FM Command `faabio3131/FM-CONTROL-CENTER` PR #90: protected setting, revision, audit, migration, UI. **Signed dynamic publication/consumption across Command→Assistant not implemented/certified yet; current Assistant default remains 45s.** Provider expiration must override if shorter. No merge/deploy/real VPS.


## WhatsApp QR — stranded inbound recovery (2026-10-19)
- Implemented internal-only `WhatsAppInboundRepository.quarantine_stale_processing`: bounded 1..500 batch, older_than timestamp required, PostgreSQL `SKIP LOCKED`, conditional processing-state update, one transaction. It changes stale `processing` to `reconcile_required` and never retries provider, AI, charge, or message delivery. Existing duplicate webhook remains denied by inbox ledger.
- `EvolutionOnboarding.quarantine_stale` enforces exact tenant+unit+connection provider scoping and approved cutoff window (60..86400 seconds). No public recovery endpoint, no external secrets or DB migration.
- New tests `tests/saas/test_evolution_recovery.py` cover tenant isolation, quarantine once, replay avoidance and invalid recovery windows.
- Functionally certified SHA `2f7700bdb2bc7cdfb835d02baa2fd172c4dac86b`: SaaS Foundation CI run `39297829882` SUCCESS; F3 PostgreSQL Core Bridge Security Gate `39297829871` SUCCESS; Core Assistant Authenticated Bridge Contract `39297829914` SUCCESS.
- Command architecture review is pending by user. Do not expand/edit Command universal SaaS configuration ingestion until reviewed; keep VendeAtendeIA integration adapter separate. Still pending: authenticated native webhook broker, durable queued inbox/outbox and worker, managed reconnection/revoke, pinned provider API release, stronger lifecycle/order guard and independent security audit. No merge/deploy or external homologation.


## QR WhatsApp Local Pause (2026-10-19)
- Implemented tenant/unit-scoped `EvolutionOnboarding.pause` and authenticated `POST /v1/channels/whatsapp/qr/{connection_id}/pause` with `integration.manage`, no exposure of secrets, revision bump and audit; repeated pause idempotent. UI now shows explicit "Pausar atendimento", detects disabled status, hides QR and stops polling. Pause is **local**, not logout or remote session deletion: never claim provider device was unpaired.
- Existing runtime fail-closes disabled and revoked channel before parsing signed events; added signed-open replay regression test to forbid reactivation after pause. Tests include foreign tenant 404, unauthenticated 401, no provider disconnect request, repeated pause and post-pause QR 409.
- Separate provider contract certification and remote disconnect/revoke/reconnect remain not implemented. In-flight races/async durable queue still require independent review. No Command universal architecture changes, merge, deploy, or live credentials.


## Signed Evolution connection-event replay ledger (2026-10-19)
- Added `assistant_evolution_webhook_receipts` table (Alembic `20261019_0012`) with composite PK `(connection_id,event_digest)`, FK cascade, date index. The `EvolutionRuntime` now claims each **authenticated** signed `connection.update` event once before changing state. Duplicated delivery (same signed timestamp+body) returns no-op and cannot re-apply a stale `open` after a later degradation.
- This protects already authenticated FM broker notifications only. It is not proof that raw upstream Evolution callbacks are authentic and not a substitute for durable queues/outbox or event sequencing. The committed receipt before side effects is deliberately fail-closed: a crash can require operator reconciliation rather than blind replay. No auto production migration/deploy/merge.
- Added synthetic lifecycle replay regression and updated Alembic-head test to require receipt table. F3 original checkpoint remains separate. Command architecture held for corporate review.


## F3 WhatsApp Evolution encrypted queue + autonomous worker batch (2026-10-19)
- Signed broker inbound messages are now enqueued instead of performing inline AI/provider delivery when composed via `create_app`. The additive Alembic migration `20261019_0013` introduces `assistant_evolution_inbound_jobs`, unique (connection_id,message_id), encrypted sender+text, state and claim timestamps. Dequeue uses bounded, transactionally claimed work with PostgreSQL `FOR UPDATE SKIP LOCKED` and compare-and-swap state. No plaintext phone, message, or provider master key in queue columns. Successful/uncertain work clears encrypted text and retains auditable terminal status.
- `EvolutionRuntime.process_pending(limit)` uses existing Assistant/tenant isolation and per-instance encrypted credential; HTTP webhook only acknowledges persisted work. `python -m fm_assistant.evolution_worker --once` is a standalone controlled worker entrypoint with bounded batches. Loop mode periodically quarantines stale processing claims, **never retries** ambiguous AI/provider side effects.
- Core/Assistant authenticated bridge, local pause and 45-second QR display remain untouched. Original synthetic synchronous `EvolutionRuntime` constructor without queue remains for backward-compatible tests; production app composition explicitly injects persistent queue. No deployment, production migrations, real upstream homology or Command changes.
- **Remaining**: actual FM-authenticated Evolution-native ingress edge (upstream provenance independent of broker MAC), pinned provider version, remote revoke/reconnect lifecycle, strict per-tenant backpressure, outbox reconciliation with provider reference, crash/chaos/PostgreSQL concurrency certification and staff recovery UI. Do not mark channel production-ready.


## Evolution encrypted durable queue + guarded remote logout (2026-10-19)
- Add-only migration `20261019_0013`, encrypted `assistant_evolution_inbound_jobs` queue (unique connection_id + message_id), safe worker claim via PostgreSQL SKIP LOCKED / conditional CAS, async standalone worker `python -m fm_assistant.evolution_worker`, stale processing quarantine and strict no-blind-retry policy. Signed FM broker webhook now only enqueues in app composition; AI/outbound executes in dedicated worker. Worker rechecks tenant channel status/revision after model inference immediately before outbound attempt to reduce pause/revoke races. Full transactionally fenced network send requires later independent race/chaos certification.
- New adapter methods `connection_state` and `logout` follow documented Evolution-v2-style endpoints, synthetic tests only. `POST /v1/channels/whatsapp/qr/{connection_id}/logout` requires tenant/unit `integration.manage`, local disable first, single remote logout attempt, revokes encrypted token and marks local REVOKED only after explicit provider success. Ambiguous logout leaves local DISABLED with token retained for governed reconciliation. The UI requires human confirmation and clearly distinguishes pause vs remote logout.
- **External contract not certified:** provider family/release must be pinned before homologation; Evolution Go and Evolution v2 are distinct transports. Native Evolution webhook callbacks are NOT cryptographically authenticated by the FM-broker HMAC alone. Provider-facing ingress security (trusted FM edge, network source identity, independent signing), remote reconnection and deletion, and effective distributed send fencing remain required before production.
- All work remains on Assistant PR #1 Draft. FM Command cross-SaaS architecture is held pending explicit owner review. No deployment, real accounts, migrations in non-test environments, merges or real provider credentials.


## WhatsApp QR locally paused session resume (2026-10-19)
- Added `EvolutionOnboarding.resume` and `POST /v1/channels/whatsapp/qr/{connection_id}/resume`; requires tenant/unit `integration.manage` and **fresh remote `connectionState=open`**. Revoked sessions never resume. Paused remote-closed sessions remain DISABLED, no optimistic reactivation; owner must use governed re-link process. UI offers "Retomar atendimento" only for disabled session. Synthetic tests cover foreign scope, closed denial and open confirmation. Requires selected Evolution v2 provider release compatibility certification before production.
- IMPORTANT: Native webhook provenance remains unverified; the signed FM relay is a trust-boundary contract, not an upstream Evolution authentication claim. Remote logout/reconnect and queue tests are synthetic. No live work, production promotion or Command changes.


## 2026-10-19 — native Evolution v2 ingress auth, relink and worker race batch
- FM native edge is now explicitly **gated/opt-in** via `FM_ASSISTANT_EVOLUTION_NATIVE_WEBHOOK_BASE_URL` and the separate existing `FM_ASSISTANT_EVOLUTION_WEBHOOK_SIGNING_KEY`; provider profile fixed to `evolution_v2_whatsapp_baileys`, not Evolution Go. Provisioning mints a distinct random per-instance source credential, stores ciphertext in the CredentialVault, and configures the per-instance HTTPS webhook with a custom `X-FM-Evolution-Token` header and minimal events. Remote configuration requires explicit enabled+URL echo; timeout/ambiguity leaves DRAFT for operator review with NO blind replay.
- `POST /webhooks/evolution-native/{connection_id}` requires the matching cryptographically strong bearer header from stored per-instance credentials; rejects absent/wrong secret, cross-instance payload, locally disabled/revoked state, oversized request, and internal HMAC/header spoofing. Only after this independent header verification does the edge synthesize a fresh canonical FM HMAC and invoke existing authenticated ingress/queue. **This is per-instance possession authentication, not a vendor-native message signature**; use TLS plus edge/network restrictions in deployment. Never accept unauthenticated global webhooks. Exact third-party Evolution release/server API behavior is not externally homologated.
- Confirmed remote logout revokes prior instance secrets and status. A new QR provision is permitted **only after** the most recent provider connection is REVOKED, with a new instance identifier and new unique source credential. Existing non-revoked/ambiguous creations remain blocked, with history preserved. No automatic replay of uncertain logout.
- SQLite threaded regression uses two workers claiming one pending job; SQL CAS provides single owner, a competing SQLite database-busy is treated as a non-claim. Additional tests cover wrong source headers, missing source secret, spoofed internal signing headers, same-body duplicate, foreign tenant, confirmed relink, and unconfirmed webhook registration. CI SHA `c39ade7ac607cdb120332001721710a4d4cf00f2`: SaaS Foundation CI `39330977685` SUCCESS, PostgreSQL F3 security `39330977553` SUCCESS, Core Assistant contract `39330977550` SUCCESS.
- Not yet proved: chosen specific Evolution v2 server RELEASE with live API, cryptographic provider signature (not available by contract), network-origin enforcement in actual ingress proxy, DB load/chaos at scale and coordinated transactions for pause/send. These are strictly release gates, not permission to claim externally homologated software. F3/Command architecture unaffected; Draft only, no live credentials/deploy/merge.


## 2026-10-19 — Evolution operational resilience and capacity gates (internal)
- Durable `EvolutionInboundQueue`: per-connection cap defaults to **250 pending+processing**; FM operator can set `FM_ASSISTANT_EVOLUTION_MAX_PENDING_PER_CONNECTION` (1..10000) in the Assistant environment, independently of Command architecture. PostgreSQL advisory transaction lock serializes cap checks across replicas; per-connection message PK preserves idempotency, including terminal states. Full queue raises `EvolutionQueueCapacityExceeded`; both native and signed broker ingress return 429 with Retry-After 5, not a fake 204 nor an AI retry.
- `GET /v1/channels/whatsapp/qr/{connection_id}/operations` requires `integration.read` and tenant/unit resolution; only aggregate queue counters, cap and sanitized reconciliation entries are returned, never plaintext message/sender. `POST /.../operations/{message_id}/review` requires `integration.manage`, validates tenant/unit and records audit; changes `reconcile_required` to terminal `reviewed` **without invoking AI or resending**. QR onboarding page includes safe DOM-only operation panel and review buttons, never interpolates event text as HTML.
- Infrastructure reference `deploy/nginx/evolution-ingress.reference.conf` enforces public TLS, native ingress rate/size/method limits, and forbids publicly reaching the trusted internal `/webhooks/fm-evolution` endpoint. It is a **reference template only**, not installed or externally verified. Proxy deployment/security evidence will be an external release gate.
- Target adapter contract explicitly set to `evolution_v2_whatsapp_baileys` / `v2.3.7` with strict fail-closed settings. Handles nested `webhook` response, rejects unsafe/redirect webhook URLs, preserves per-instance source-header identity. This is an offline contract baseline, NOT certification against an actual Evolution v2.3.7 server. `docs/integrations/EVOLUTION_V2_3_7_RELEASE_CONTRACT.md` defines future evidence.
- Added **real disposable PostgreSQL** multiworker tests: two ingress producers race for one capacity slot; eight workers race for a single queued job, with only one claim permitted. Synthetic provider failures quarantine as reconcile_required without replay; 429 Retry-After, per-tenant operator read/review, immutable message dedup, provider nested webhook responses and rejection of URL mismatch are covered.
- Functional SHA `8abbb90824cc7cc59a040ee9a718d498a6c13d83` passed SaaS Foundation CI `39334496416` SUCCESS, F3 PostgreSQL `39334496577` SUCCESS, Core/Assistant `39334496427` SUCCESS. After this governance update revalidate latest HEAD before marking final certification.
- Still cannot claim production homologation, actual Evolution provider release compatibility, installed TLS/network edge, field-scale chaos, real provider delivery or external WhatsApp account testing. Those remain deliberately separate from software construction. Keep PR #1 Draft, no merge, deploy, production migration, credentials, changes to Command cross-SaaS architecture or bypass of quotas.


## 2026-10-19 — F3 WhatsApp queue claim-freshness guard + backlog aging
- Implemented `EvolutionInboundQueue.assert_claim_current` to check that the per-connection message still owns a non-expired `processing` claim (300s default, min 60s/max 86400s). The AI worker checks the lease **immediately before attempting provider send**, in addition to existing tenant/connection status and revision check. Missing, stale or already quarantined claim fails closed. The worker's exception path treats a concurrent existing `reconcile_required` as terminal and does not try to reopen/replay it.
- Operational dashboard now shows oldest pending message age. `operational_snapshot` returns aggregate oldest ages in seconds for pending/processing records, using timezone-safe normalization on SQLite, never sender/phone/message text.
- Tests include old claim rejection before quarantine, terminal claim rejection after quarantine and anonymized queue-age output. Synthetic functional SHA `4bf8e0fdfece45c7436d3a364630a4941f9647b8` passed SaaS Foundation CI `39337851841`, PostgreSQL security `39337851787`, Core/Assistant bridge `39337851775` (3/3 SUCCESS).
- **Remaining architecture gate:** stronger coordinated/renewed leases and durable outbound fencing for provider network request and long-running AI calls (state verification followed by network send is not atomic). Do not claim mathematically exactly-once end-to-end or field chaos certification. No production deployment, real secrets, migrations or merge. Preserve Command architectural review hold.


## 2026-10-19 — F3 generation-fenced worker lease primitive (UNVERIFIED / BUILD)
- Following certified SHA `0675ff1413c2ec2726e8b3397f7b8b9514a18bdf`, added claim-generation tokens using the existing monotonically incrementing `attempt_count` column, and atomic `renew_claim` CAS that refuses expired, quarantined, superseded, and completed jobs. Worker checks its own claim generation before send and uses generation fencing for queue completion/reconciliation. Existing 3/3 green checkpoint remains the baseline; these changes are NOT yet CI-certified.
- Added synthetic regression tests for foreign generation renewal/completion and non-renewability of expired jobs. Changes stay in Assistant PR #1 Draft; do not deploy, merge, or treat as production-ready before current exact-HEAD gates pass.
- Explicit follow-up internal build gates: ongoing periodic lease heartbeats during long-running AI execution, durable provider outbound attempt fencing/reconciliation and lifecycle trace, race/chaos validation. A renewable lease primitive alone does NOT provide atomic provider delivery, provider-side exactly-once guarantee, or prevent a send race after the DB check.
- External Evolution server compatibility, real proxy/TLS and WhatsApp homologation remain separate release gates AFTER 100% software construction. They must not block implementing remaining internal milestones.


2026-10-19 — WHATSAPP F3 HEARTBEAT + DURABLE OUTBOUND INTENT — INTERNAL IMPLEMENTATION, CI PENDING
- F3 next increment built on previously green generation-fenced lease: background 30s heartbeat renews the current worker claim during long model/provider calls, strictly CAS-guarded by claim generation and expiry; lease loss fails closed. Prevents normal long AI latency from expiring the worker lease, without claiming atomic third-party delivery.
- Add-only Alembic 20261019_0014: provider operation identifier, outbound status, provider receipt reference, send-start timestamp and 'sending' state; a single transaction commits one send-intent BEFORE invoking HTTP. Durable intent denies second outbound attempt, and crash/timeout during 'sending' is reconciled instead of automatically resent. PostgreSQL/SQLite compatible batch migration; no non-test migration applied.
- Queue reconciliation snapshot includes non-payload attempt metadata; existing tenant/user authorization remains mandatory. Added regressions for single-winner concurrent send intent, replay exclusion, stale send quarantine and bounded provider receipt. No actual provider receipt verification or cryptographic proof of WhatsApp delivery implied.
- Functional implementation commits: 5e7f45ac, 3840660b, 42d5af30, 8f6b7397, c3b6e22b, 2548acf7. CI remains unverified until all 3 exact-HEAD gates report GREEN. NEXT: fix any CI regression, formalize provider reconciliation evidence and lifecycle visibility, broaden failure/chaos and ownership tests.
- F3 remains BUILD_IN_PROGRESS, PR #1 DRAFT. External Evolution live version, real proxy/VPS/phone credentials, WhatsApp delivery and field load remain POST-CONSTRUCTION HOMOLOGATION; these do not block next internal build phases. No production deploy, merge, live secrets, Kordena or Command architecture modifications.


2026-10-19 — WHATSAPP F3 HEARTBEAT / OUTBOUND INTENT / RECONCILIATION — INTERNALLY CERTIFIED
- Functional HEAD `623e2b0b2af26375b23ee088a194081e16d7ece8`. GitHub Actions on this exact SHA: SaaS Foundation CI run `39342275837` SUCCESS; PostgreSQL F3 Security Gate `39342275941` SUCCESS; Core↔Assistant Contract `39342276035` SUCCESS. Functional internal subgate **3/3 GREEN**.
- Implemented worker claim renewal every 30 seconds with generation check and fail-closed loss signaling. Persistent outbound intent is transactionally written before Evolution HTTP call; only one state transition processing→sending per job, and stored provider result is matched to its unique operation ID. A sending worker that expires/vanishes is quarantined to reconcile_required, never requeued blindly. Operator snapshot surfaces non-message provider reference and uncertain intent for governed follow-up. Added migration 20261019_0014 and regression scenarios for concurrent intent, expired sending and immutable dedup.
- Failures corrected during gates: Ruff broad-exception annotations, and legacy Alembic-head assertion updated from 0013 to 0014. Green suite includes 160+ SaaS tests; external network not used.
- Important limits: no proof of true provider-side exactly-once delivery or signed provider delivery receipt; inbound pause/send atomicity and independent chaos at production scale remain separate engineering/security review issues. No external Evolution 2.3.7 instance, real WhatsApp delivery, TLS gateway, VPS credentials or production migration was tested. External configuration/homologation waits until COMPLETE SOFTWARE BUILD and DOES NOT block unrelated internal construction.
- Status F3 BUILD_IN_PROGRESS. PR #1 remains Draft, no merge/deploy; Command universal policy architecture held for separate owner review. Next phase as ordered in Master Schedule: strengthen lifecycle observability and independently audit provider reconciliation, race between pause/revoke and send, then remaining F3 cross-system gates.
