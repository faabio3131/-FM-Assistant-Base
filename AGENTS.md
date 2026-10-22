# AGENTS.md — FM Assistant + Sales AI

**Status:** NORMA OPERACIONAL OBRIGATÓRIA DO REPOSITÓRIO  
**Escopo:** todo agente, executor, modelo, automação ou ferramenta que altere este repositório  
**Produto:** FM Assistant + Sales AI V1

---

## 1. MISSÃO

Executar o Prompt Mestre até a conclusão comercial com máxima autonomia operacional, sem perder sequência, governança, evidência ou segurança.

Para a execução iniciada em 20/10/2026, o cronograma canônico de construção é
`docs/governance/CRONOGRAMA_MESTRE_CONSTRUCAO_100_INTERNA.md`. Ele substitui classificações
genéricas do tracker quando a auditoria de código comprovar trabalho parcial já existente, sem
apagar o histórico. O tracker continua sendo o diário de evidências.

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

Homologação externa também é posterior a `BUILD_COMPLETE_INTERNAL_GREEN`. Até esse marco, o
executor deve concluir adapters, configuração, contratos, fakes, migrations e testes internos, mas
não usar credenciais, contas, infraestrutura ou usuários reais. Ausência de terceiro não bloqueia
construção interna independente.

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


2026-10-19 — F3 WHATSAPP LIFECYCLE VISIBILITY / RECONCILIATION SAFETY — INTERNALLY GREEN
- Functional SHA `13add8dc9193a6169ecd5f51b45658a73ee88b01`. GitHub Actions: SaaS Foundation CI `39343758194` SUCCESS; F3 PostgreSQL Core Bridge Security Gate `39343757959` SUCCESS; Core Assistant Authenticated Bridge Contract `39343757968` SUCCESS. 3/3 functional gates GREEN.
- Extended existing tenant-scoped operation snapshot with bounded, no-payload lifecycle data: received/claimed/send-start/last-transition timestamps, processing state, attempted operation id, acknowledgement reference, and manual review requirement. `provider_delivery_confirmed` is deliberately always false; a provider send receipt does not prove final WhatsApp delivery.
- Enforced fail-closed terminal completion: a `sending` row cannot be marked `complete` without previously stored provider acknowledgement. Operations with uncertain send remain quarantined for operator review and cannot be automatically replayed.
- Worker now revalidates connection ACTIVE status and revision after durable intent transaction, immediately before outbound HTTP; if pause/revoke occurred, it refuses the send and leaves the attempt for reconciliation. Race between this check and non-transactional third-party HTTP is NOT fully eliminated.
- Added synthetic regression for lifecycle privacy, tenant/connection isolation, erroneous success transition on unknown send, scoped operations API and concurrent manual review one-winner. No full independent security audit or production-scale chaos certification is claimed.
- F3 remains BUILD_IN_PROGRESS, PR #1 Draft. NEXT: formal provider delivery status correlation and evidence-qualified reconciliation, broader race/chaos coverage for pause/revocation versus outbound, and remaining internal F3 tasks. External TLS/VPS/real WhatsApp/Evolution certification deferred to POST-CONSTRUCTION HOMOLOGATION and must not block internal development. No merge/deploy, production migration, real secrets, Kordena or Command governance changes.


2026-10-19 — F3 EVOLUTION DELIVERY CORRELATION / EVIDENCE-GATED REVIEW / PAUSE-REVOKE RACES — INTERNALLY CERTIFIED
- Certified functional HEAD `1955ce88609a2f16ac62b046392b778200f8f49b`: SaaS Foundation CI `39345728463` SUCCESS, PostgreSQL F3 Security Gate `39345728494` SUCCESS, Core↔Assistant Contract `39345728413` SUCCESS; 3/3 exact functional SHA gates GREEN.
- Evolution v2 per-instance webhook subscription now includes MESSAGES_UPDATE. Only an already authenticated FM-signed event (native edge also checks distinct per-instance bearer credential) can correlate a provider-generated outbound message reference with one and only one existing scoped queue attempt. It stores normalized monotonic sent/delivered/read states and SHA-256 digest of authenticated event bytes, no raw webhook body, no phone or message contents. Missing/ambiguous/foreign references and forged signatures cannot change delivery state. Migration `20261019_0015` adds nullable delivery status/digest/timestamp fields.
- Governed review now denies resolving a `reconcile_required` job that had a durable provider-send intent until it also has correlated authenticated provider delivery-status evidence; operator acknowledgement never retries or claims false delivery. Intent without provider ID/evidence intentionally REMAINS quarantined, requires a later separately authenticated evidence-acquisition pathway, not an invented delivery result.
- A locally DISABLED channel may ingest *status-only* callbacks for already attempted messages after credential authentication; all inbound and connection-open events remain denied, and REVOKED connections deny all callbacks. Added synthetic tests of signed/forged/regressive delivery events; cross-connection isolation; evidence-gated review; pause and revocation races injected between committed send intent and outbound HTTP. These are bounded internal regressions, not a proof of all possible race interleavings.
- Not resolved / separate internal security engineering: atomic pause/revoke vs external HTTP final micro-race remains (the final state check cannot transact with a third-party network call); no exactly-once provider guarantee. No independent adversarial review or production-scale chaos certification claimed. A provider-acknowledged callback establishes evidence accepted by the FM trust boundary, NOT a vendor-native cryptographic signature nor third-party verified delivery. Offline v2.3.7 contract is a candidate, not confirmed against installed server.
- F3 global remains BUILD_IN_PROGRESS; PR #1 DRAFT. No merge, deploy, real VPS keys, migrations outside disposable CI, production WhatsApp or Command universal policy changes. All external provider version/certificate/proxy/network/real WhatsApp homologations remain POST-100%-BUILD gates and must NOT block further software construction.


2026-10-19 — F3 UNCERTAIN PROVIDER EVIDENCE INVESTIGATION + POSTGRESQL SEND SERIALIZATION
- Functional implementation on Assistant Draft PR #1 follows certified `e1a4e11e509631059260cb713e498d7eb28e16fd`. Added read-only `POST /chat/findMessages/{instance}` adapter lookup with per-instance credential and strict exact outbound `key.id/fromMe` match. New tenant/unit-authorized `POST /v1/channels/whatsapp/qr/{connection_id}/operations/{message_id}/investigate` requires matching persisted operation ID; rejects foreign tenant/unknown or already investigated attempt. Bounded response and no-stored-plaintext hash from actual provider record. Migration `20261019_0016` stores ONLY candidate provider reference/hash/timestamp. Candidate evidence is explicitly INSUFFICIENT to prove that a previously ambiguous send created that message; it never changes reconcile_required, never retries, refunds, activates a channel or promotes delivery. No automatic approval if reference is missing. Live provider response compatibility remains an external homologation gate AFTER software build.
- Added PostgreSQL transaction-scoped `FOR UPDATE` of the integration connection row during actual bounded provider HTTP send in worker. The mutating `IntegrationRepository.update_connection` now takes the same row lock before pause/revoke/revision updates. This serializes send window against state transitions on PostgreSQL, so a pause/revoke must wait for an already-started provider send; it cannot cancel a network request already begun. SQLite's FOR UPDATE is a no-op; synthetic SQLite tests must not be advertised as proof of distributed locking. Transaction lock is deliberately released on both success and failure. All other integrations using this update path continue to use existing scope and protections.
- Internal regression coverage added for foreign operation, missing provider, no automatic replay, strict read-only provider query and connection revision/pause guard. Mocked provider evidence is only a candidate; no provider-side cryptographic signature or definitive link to the unknown send is invented.
- Last 3/3 internally GREEN functional checkpoint `9a7f683e1a1427c5fa9ea01a1002affe96c6af24`: SaaS Foundation `39346805176`, PostgreSQL security `39346805213`, Core bridge `39346805316` SUCCESS. Later test-only commit `ceaedb31ea6a941479f9f2337d32093745b1d433` needs own current-HEAD certification; do NOT label the documentation HEAD certified without verified workflows.
- F3 still BUILD_IN_PROGRESS, PR #1 Draft; no merge/deploy, external credentials, production migrations, Command universal policy changes. Further internal requirements: independent distributed PostgreSQL chaos/lock contention certification with actual overlapping HTTP send and pause/revoke, Command/Assistant/Core multi-process end-to-end, reviewed charge reconciliation and provider-specific token accounting. External Evolution real VPS/TLS/WhatsApp compatibility/homologation ONLY AFTER complete software construction.


2026-10-19 — F3 DISTRIBUTED POSTGRESQL SEND LOCK + FINOPS RECEIPT CLASSIFICATION / CROSS-COMPONENT CONTRACT TESTS
- Functional SHA `c4d0d1cac9ef417aa41734c76116886bd26b1aca`, exact-SHA GitHub Actions: SaaS Foundation CI #39347964117 SUCCESS, PostgreSQL F3 Core Bridge Security Gate #39347964105 SUCCESS, Core↔Assistant authenticated contract #39347964171 SUCCESS; 3/3 green. Testing was on isolated synthetic databases only.
- NEW actual PostgreSQL concurrent lock-contention test in `tests/saas/test_core_bridge_postgres.py`: two independent sessions/threads exercise `EvolutionInboundQueue.outbound_connection_guard` versus `IntegrationRepository.update_connection` for both DISABLED and REVOKED states. While send holds the DB row lock, terminal state mutation does not commit; after release it does, and stale revision cannot obtain send guard. This tests database ordering, NOT remote HTTP behavior or guaranteed WhatsApp cancellation.
- NEW `provider_usage_reconciliation.py` models FM-private provider/model/request usage receipts with exact nonnegative integer input/output token units and nonnegative finite Decimal USD cost; preserves unknown tokens/cost on uncertain execution, rejects conflicting confirmations and mismatched request/provider/model. No estimated token usage or monetary conversion is invented. This is a **pure internal classification/reconciliation primitive**, NOT an integrated durable accounting ledger or finished provider-specific billing. Core retains authoritative quota/charges. Tests cover uncertain/confirmed/duplicate/malformed receipts.
- NEW `tests/saas/test_f3_command_assistant_core_usage_contract.py` validates with mocked Core HTTP endpoints that requests carry authenticated service identity and fixed tenant/unit, and the trusted metering read rejects foreign-tenant response. This is a synthetic adapter contract test, **NOT** real end-to-end three-running-service Command↔Assistant↔Core certification.
- STILL OPEN INTERNAL F3 construction (does not depend on external homologation): integrate canonical provider usage receipts with Core's persistent economic ledger and provisionally reserved/uncertain usage recovery; versioned provider token usage rules with Core routing/fallback and platform-only cost visibility; perform real multi-process Command↔Assistant↔Core workflow with all three repositories, including corrupted/missing meter readings, tenant boundaries, revoked grants and payment/license attribution. Do NOT certify these from current contract tests.
- F3 BUILD_IN_PROGRESS; Assistant PR #1 DRAFT; no merge, deploy, production migrations, real secrets or real provider homologation. External Evolution/WhatsApp/proxy version tests deferred until 100%-built software.


2026-10-19 — F3 CORE CANONICAL USAGE RECONCILIATION INTEGRATION CHECKPOINT
- Companion FM Core Base branch `feat/ai-service-v1` functional SHA `0f4d6b5df71cb4f606dd40bdc1e68334827dfbe8`: `VerifiedProviderUsageReceipt` normalization and `QuotaReservations.reconcile_verified_provider_receipt` route verified token usage to the EXISTING canonical reserved/settled ledger, not another Assistant ledger. Exact-SHA Core AI Service CI run `39348829313` SUCCESS and Core PostgreSQL F3 gate `39348829333` SUCCESS.
- Only independently verified provider evidence and authorized fresh Command `VerifiedCommandAdmin` can settle a complete request bundle once, with persistent audit/JTI; timeout never implies free usage. Provider cost remains FM-private. Assistant-side provider reconciliation remains a validation primitive, never an independent accounting authority.
- Previously certified Assistant tests validate Core generation and quota read with synthetically mocked HTTP; NO actual three-process Command↔Assistant↔Core PostgreSQL E2E completed in this checkpoint. Provider evidence verification and Command recovery HTTP interface remain OPEN internal construction. External providers and credentials after 100% software construction.
- Assistant PR #1 Draft; no merge/deploy/real secrets; F3 BUILD_IN_PROGRESS.


2026-10-19 — F3 GOVERNED COMMAND RECOVERY BOUNDARY CONTINUATION
- Companion Core branch `feat/ai-service-v1` introduced signed human Command RS256 recovery orchestration, independently injected provider evidence verification and an opt-in internal recovery router. It is NOT mounted in the default Core app, because durable trusted provider evidence verification is still an INTERNAL CONSTRUCTION prerequisite. An opaque candidate reference or untrusted SHA-256 cannot autonomously settle a quota reservation.
- Functional Core SHA `9e8d01f4fc4b68e053825493597e810582d98c2e`, AI Service CI `39350176109` SUCCESS and PostgreSQL gate `39350176117` SUCCESS. New Core documentation HEAD is under its own gate; verify independently. Existing Assistant/SaaS quotas and plan pricing authority unchanged.
- Cross-process Command↔Assistant↔Core execution and independent durable evidence verifier still OPEN; synthetic Command JWT and Core recovery router unit tests are NOT a three-service E2E certification. Next internal work: protected evidence ingestion/verification and isolated multi-process test harness with tenant, plan revocation, reserve, settle, uncertain failure and retry/replay controls. External credentials/HTTPS/VPS/WhatsApp homologation deferred until software 100% built. Assistant PR #1 stays Draft; no merge/deploy.


2026-10-20 — F3 COMMAND ASSISTANT CORE RECOVERY CROSS-CODEBASE CERTIFICATION
- Companion FM Command corporate branch `feat/f3-command-core-bridge-governance` implements actual RS256 corporate human recovery signer and no-retry HTTPS internal client. Companion Core `feat/ai-service-v1` uses canonical quota ledger + optional RS256 Command recovery route backed by immutable HMAC-authenticated FM gateway evidence table `f3_0005`.
- Command Foundation Gate now pins Assistant source `ab30a89bfe4d15937b15ab0cc7ebb033030af803` and certified Core functional `3733c25e39d2c9df1203b4c9834604c7c96dbcb8`, exercising real Command Node signing, Assistant FastAPI ASGI identity revocation, Core deterministic quota reserve/reconciliation, persisted scoped evidence and duplicate-settlement rejection with synthetic secrets. CI completion must be checked against exact Command HEAD before claiming GREEN.
- These are **three codebases** connected through a test harness, NOT 3 independently running service processes over network with PostgreSQL shared across end-to-end calls. Command signer alone is NOT a deployment; provider-source verification beyond authenticated FM evidence gateway and opt-in recovery API activation remain internal construction gates. The authenticated FM gateway key only proves the internal attestation source, not the external provider invoice.
- No merge/deploy/production schema updates. Command plan/licensing and FM-only AI cost model unchanged. F3 BUILD_IN_PROGRESS. External provider homologation postponed until complete software construction.


2026-10-19 — F3 SOURCE-VERIFIED EVIDENCE + ISOLATED NETWORK GATE / MASTER RECONCILIATION
- Added a precise work-item matrix at `docs/governance/F3_INTERNAL_GATE_RECONCILIATION_2026-10-19.md`; read it before marking any F3/F9 phase complete. Companion Core `feat/ai-service-v1` now has `verified_signed_usage_source` with independently pinned Ed25519 signer, payload freshness, exact request/tenant/unit and upstream digest, plus `TrustedProviderEvidenceStore.record_verified_source`; a plain unsigned provider response is NEVER independently verified. Functional Core SHA `78885dc4383255678b7639163c9c33975dfb793a`, AI Service CI `39353714999` and PostgreSQL Security Gate `39353715201` SUCCESS.
- Companion Command Foundation Gate now launches separate Assistant and Core uvicorn instances and a Node Command signer subprocess on loopback, uses a disposable PostgreSQL database for Core, verifies signed scoped upstream fixture, then tests Command↔Assistant revocation, Core reservation, signed recovery and duplicate settlement. Exact Command functional commit and CI must be verified separately. This does not certify HTTPS, deployment, a permanently running Command HTTP server nor atomicity of two databases. External integration remains AFTER software completion.
- Master Schedule still lists internal build blockers: billing subscription outbox integration; signed/monotonic Assistant→Core quota projection/revocation connected to runtime; provider metering and fallback/cost reconciliation at every attempt; non-signing provider verification adapters and full license/payment attribution under failure; wider adversarial tests and final code reviews. F3 remains `BUILD_IN_PROGRESS` even if source and loopback network tests pass. Do not declare `BUILD_COMPLETE_INTERNAL_GREEN` early. No merge/deploy/real keys or production DB changes.


2026-10-19 — F3/F9 COMMERCIAL BILLING TO LICENSE TO CORE QUOTA INTERNAL GATE
- Companion FM Command branch `feat/f3-command-core-bridge-governance` added Drizzle `0014_vende_paid_license_outbox`, unique scoped paid-invoice outbox and canonical billing transaction that checks persisted payment, Vende product, FM-published quota plan and actual SaaS customer mapping, atomically enqueues delivery intent/audit. A single-shot signed /bind dispatch plus bounded worker drain denies duplicates and does not re-send after uncertain timeout/reversed invoice. No automatic customer-initiated quota elevation.
- The signing implementation was refactored into pure Node `assistant-plan-license-signer.ts`, using the exact existing HMAC contract. Cross-repository test `tests/f3_command_license_quota_journey.py` checks real Command signer -> existing Assistant `GovernedPlanLicenseBinding` -> live `LicensedQuotaManifestService` -> Core existing `SignedAssistantPlanAuthority`/`PlanUsageGuard`: atomic 180-token reserve, replay denial and next request fail-closed after license suspension. It is **synthetic SQLite for license/quota test**; Command's isolated PostgreSQL billing gate separately validates real paid invoice/outbox/claim.
- Command functional SHA `13621d4b6c103e857e98fd1e32fb42460cf8142a`: Foundation `39358095382` SUCCESS; Billing PG `39358095405` SUCCESS; F21 `39358095433` SUCCESS; Cognitive `39358095442` SUCCESS (4/4). This is not a provider-certified paid checkout nor distributed atomicity across Command/Assistant/Core. Core's preexisting signed authority/guard was preserved; a redundant parallel quota implementation was deleted after architectural inspection.
- Still `BUILD_IN_PROGRESS`: authorized worker/scheduler delivery, reconciliation of blocked intents, subscription grant/trial linkage, upgrade/downgrade/renewal effective periods, signed/revocable policy sync for each runtime path, official attempt-level provider metering/cost and remaining F3 gates. No merge/deploy, live credentials or production migrations; external homologations must not block further internal construction.


2026-10-20 — F3 COMMERCIAL LICENSING OUTBOX GOVERNED RECOVERY — INTERNAL CHECKPOINT
- Added Command-only signed read-only `POST /internal/v1/command/assistant-plans/binding-status` with replay-resistant HMAC and dedicated path domain, trusted corporate issuer and exact tenant/plan/revision plus persisted **operation nonce**. Only a matching `PlanBindingAuditORM` entry permits `bound_confirmed`; a pre-existing plan with no audit matching the original attempt is NOT delivery proof. No plan mutation, resend, extension or quota elevation occurs during the query. Synthetic tests cover exact nonce, foreign/forged signature and replay.
- Exact Assistant code HEAD `c41e640c5be8a7d5f6db3d9c505226f10de95ffd`: SaaS Foundation `39425361539`, PostgreSQL security `39425361484`, Core/Assistant contract `39425361529` all SUCCESS (3/3).
- FM Command companion PR #90 adds stable claimToken as signed original bind nonce, signed read-only status inquiry and CAS blocked-to-delivered only on exact scoped audit proof; also quarantines crashed `processing` claims without replay. Cross-runtime Command Node→Assistant status and PostgreSQL outbox tests added. Latest Command HEAD still has NO matching new workflow runs; DO NOT claim GREEN or merge on prior SHA. PR #90 remains Draft and GitHub reports mergeable=false.
- Still incomplete internal F3 commercial lifecycle: scheduled worker activation, human reconciliation when proof absent, renewal/upgrade/downgrade/expiration governance, authoritative cross-service revocation/fresh quotas in all runtime paths, provider/model/attempt financial reconciliation including audio and unknowns, WhatsApp recovery edge cases, independent security review and final whole-product regression. Existing Core guarded execution/pricing and QR queue controls must be reused, not recreated.
- F3 BUILD_IN_PROGRESS, F4 as scheduled only after its formal gates. No actual provider credentials, migrations in permanent DB, production deployment or external homologation. Do not promote BUILD_COMPLETE_INTERNAL_GREEN or merge until all gates green on exact HEAD.


## F3 — suspensão operacional assinada e independente de billing (20/10/2026)
O receptor `SignedLicenseSecurityHold` processa APENAS `security_hold` de FM Command, com assinatura HMAC estrita, chave corporativa já governada, scope VendeAtendeIA, ator FM, `step_up_at` e `approved_at` recentes (300 s), nonce único, command_request_id único, revisão do plano e corte `expected_valid_until` verificado sob lock. Suspende `TenantLicenseORM.status` atomicamente e cria evidência imutável em `assistant_license_security_hold_audit` (migration aditiva 0018). A política comercial (estorno, reembolso, inadimplência, renovação, prorrata, mudança de plano) continua NÃO definida: proibido usar o endpoint para mudanças comerciais ou invocação automática por webhook. Segurança e revogação de quota local devem permanecer fail-closed e passíveis de investigação. Endpoint real não ativado nem migrado, Command sender público ainda não construído. CI e revisão independente obrigatórios.

---

## 2026-10-20 — DIRETRIZ VINCULANTE DE AGILIDADE POR BLOCO (AUTORIZAÇÃO DO PROPRIETÁRIO)

Autoridade: decisão humana mais recente, formalizada no Prompt Mestre, seção 26. Esta é a interpretação executável das regras de autonomia, sequência e merge deste AGENTS.md, **sem afrouxar** quaisquer gates de segurança, CI ou revisão.

- **Ciclo sem pedir permissão a cada bloco:** ler CURRENT GitHub+tracker; implementar ou corrigir próximo WP desbloqueado; revisar diffs, executar testes/CI do SHA real; consertar automaticamente qualquer gate RED e repetir; certificar `WP=GREEN`; fazer merge da **PR daquele WP** quando 100% dos critérios aplicáveis forem comprovados e a PR for mergeable; verificar CI de `main`, documentar SHA e prosseguir imediatamente ao próximo WP.
- **Critério de merge é por WP autocontido, não por toda a fase:** WP `GREEN/MERGED` pode coexistir com fase `BUILD_IN_PROGRESS`. A fase só vira `BUILD_COMPLETE_INTERNAL_GREEN` após **todos** os seus WPs/gates internos. Nunca fundir PR com alterações ainda incompletas só porque alguns testes passaram; em PR monolítica, avaliar o conjunto inteiro.
- **Evitar pilha de PRs:** preferir `main` atual e uma única PR por WP. Reconciliar PRs legadas acumuladas antes de promover commits; identificar overlap, independência e ordenação. Não reaplicar mudanças incorporadas, inclusive correções comerciais do Command.
- **STOP sem merge:** gates falhos/não executados ou `BLOCKED_EXTERNAL` que afete o próprio WP; review obrigatória ausente; CI em SHA velho; incompatibilidade entre repositórios; erro RBAC/tenant/PII/segredo; perda de idempotência ou rollback; PR conflitante; ou merge que cause deploy/migration/uso de credencial real não autorizado. Corrigir o que for interno. Se bloqueio for realmente externo, registrar evidência e trabalhar só em WP **independente**, sem falsificar GREEN.
- **Provas externas depois:** versões/rede reais Evolution/Meta/IA/Asaas, credenciais, Contabo/Render, TLS/PSP são `EXTERNAL_HOMOLOGATION_DEFERRED` e não impedem terminar código, testes internos e merge seguro. Não usar este rótulo para esconder defeito de código ou teste obrigatório interno.
- **Reserva humana:** deploy/cutover, migrations permanentes de produção, segredos/credenciais verdadeiros com efeito real, mudanças materiais de arquitetura/política comercial, gastos e ações irreversíveis continuam dependendo da aprovação específica do proprietário. `merge != deploy`.
- **Registro obrigatório:** tracker por WP com HEAD exato, gates, revisão (não rotular autoauditoria de independente), merge SHA, CI pós-merge, regressões e próximo bloco. Não refazer fases encerradas. Preservar Kordena como read-only.

**Aplicação:** seção 26 do `docs/governance/PROMPT_MESTRE_EXECUCAO_INTEGRAL_V1.md` e checkpoint mais recente do `EXECUTION_TRACKER_MASTER.md`. Esta regra não autoriza execução assíncrona sem sessão/execução ativa.

## 2026-10-20 — CONSTRUÇÃO 100% ANTES DA HOMOLOGAÇÃO EXTERNA

- A avaliação e a sequência oficial passam a ser `docs/governance/CRONOGRAMA_MESTRE_CONSTRUCAO_100_INTERNA.md`.
- Executar B0→B11 até `BUILD_COMPLETE_INTERNAL_GREEN`. B12/F13 é homologação externa e só pode começar depois desse marco.
- Todo ponto externo deve possuir configuração governada, validação fail-closed, secret reference, adapter/port, fake determinístico e testes de sucesso/falha durante a construção.
- Não cadastrar tenant, unidade, preço, limite, plano, credencial ou instância de provider por código.
- O executor tem autonomia contínua para corrigir, commit/push, abrir/atualizar PR, reconciliar branches, executar auditoria interna em passe separado, fazer merge de WP 100% verde, validar a main e seguir ao próximo bloco sem novo pedido.
- Uma pergunta de status não suspende o trabalho. Parar apenas em STOP real, decisão material ainda não aprovada ou ação externa/real que exija autorização.
- Permanecem proibidos sem autorização específica: deploy/cutover, migration em banco real, credencial real, cobrança/envio real, gasto, homologação externa antecipada e operação destrutiva.

## 22/10/2026 — Continuidade do único SaaS Core + Assistant e provas P01/F3

- **Decisão do proprietário:** FM Core + FM Assistant constituem **um único SaaS**, VendeAtendeIA é nome provisório. FM Command fica separado, gerencia todos SaaS FM e possui comercialização própria. Não reorganizar agora os repositórios atuais nem reconstruir as bases: preservar trabalho, PRs e compromissos vigentes.
- O CURRENT verificado e gates constam ao fim de `docs/governance/EXECUTION_TRACKER_MASTER.md`; sempre reconciliar esse checkpoint com GitHub antes de codificar. Command até PR #159 merge `0aefac3c587a896366d9a635c31a10ba08d04249`; Core PR #4 integrada na branch F3 candidata `c03ec3162d0fc55f061ce71cd5df2591c37ad919` (porta HMAC efetivamente montada, OFF por padrão). Command Foundation usa pins explícitos Assistant `8279f3c10993ace277f713c01688a3412fc3e92a` e Core `c03ec3162d0fc55f061ce71cd5df2591c37ad919`.
- Core PR #1 e Assistant PR #1 seguem Draft, **F3/B1 não GREEN**. Módulo Core HMAC e tela Command passam testes internos, mas flags/segredos/rede reais não estão habilitados; não atribuir licença/quotas atuais a uma evidência histórica.
- Certificação do WP exige CI no SHA após cada mudança; revalidar 3/3 Assistant e 2/2 Core e Foundation Command. Sem F3 GREEN não marcar B2/F4 concluído. Provedores, Evolution/WhatsApp, Asaas, DNS e infraestrutura reais somente após BUILD_COMPLETE_INTERNAL_GREEN. Usuário mantém autorização de correção/PR/merge de WP elegível, nunca deploy/cutover/secret real por implicação.


### F4 — WP1 recuperação seletiva de conhecimento (22/10/2026)

Reutilizar KnowledgeDocumentORM e KnowledgeRepository; não criar segundo repositório para knowledge. Novo BoundedKnowledgeRetrieval lê apenas tenant/unidade/active, devolve contexto seletivo limitado com document_id/updated_at e marcadores de fonte não confiável. A opção `FM_ASSISTANT_KNOWLEDGE_CONTEXT_PACK_ENABLED` inicia OFF; sem prova de relevância, jamais despejar todos os documentos quando ligada. Ver docs/governance/F4_WP1_SCOPED_KNOWLEDGE_CONTEXT_PACK_2026-10-22.md. Não confundir este WP com F4 GREEN: versões imutáveis, ingestão por URL/arquivo, chunking persistente, busca híbrida e UI permanecem pendentes. CI Assistant SaaS+Postgres+Core bridge no SHA e nenhuma operação externa antes da construção 100%.
