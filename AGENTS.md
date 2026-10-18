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
- Reusar seletivamente Kordena FinOps (pricing/cost idênticos ao Core, metering/aggregates e dashboard) mas nunca usar read-model diário para autorizar operações; impedir tokens desconhecidos=0 e dedup equivocado entre tentativas de fallback.
- Fonte canônica aprovada: `docs/governance/ADR-009-ALL-FEATURES-PLAN-CONSUMPTION-AND-KORDENA-FINOPS.md`. Devem ser corrigidos os anteriores conceitos que associavam feature gating/recursos habilitados ao plano. Todos os tiers têm mesmo conjunto de funções.
- Construção pendente: painel FM e publisher de preços/franquias, projeção assinada Command→Assistant→Core, hard stop pré-provider, dashboards e alertas. Homologações externas só depois da conclusão integral do software.
