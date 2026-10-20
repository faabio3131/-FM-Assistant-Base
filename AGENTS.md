# AGENTS.md — FM Core Base

**Status:** NORMA OPERACIONAL OBRIGATÓRIA DO REPOSITÓRIO  
**Escopo:** todo agente, executor, modelo, automação ou ferramenta que altere este repositório

---

## 1. PAPEL DO REPOSITÓRIO

FM Core Base é a fundação cognitiva compartilhada da Nova FM Tecnologia.

Responsabilidades:

- capability routing;
- provider/model routing;
- fallback;
- metering;
- FinOps;
- provider health;
- políticas cognitivas;
- contratos horizontais reutilizáveis.

Não é autoridade para:

- tenant/licença do produto;
- CRM;
- billing comercial do cliente;
- autenticação humana do produto;
- mutações críticas sem serviço determinístico autorizado.

---

## 2. HIERARQUIA DE AUTORIDADE

1. Documento Mestre Nova FM Tecnologia v2.0.
2. Padrões de Construção Nova FM.
3. Este `AGENTS.md`.
4. `docs/AI_SERVICE_V1.md`.
5. ADRs/System Design aprovados do produto consumidor.
6. Prompt Mestre do produto consumidor.
7. CURRENT comprovado por código/testes/CI.

Para o trabalho atual com FM Assistant + Sales AI, a orquestração de fases é definida por:

`faabio3131/-FM-Assistant-Base/docs/governance/PROMPT_MESTRE_EXECUCAO_INTEGRAL_V1.md`

e pelo tracker canônico daquele produto.

---

## 3. REGRA ANTI-DELÍRIO

Nunca presumir:

- provider homologado;
- capability disponível;
- custo conhecido;
- fallback funcional;
- credencial válida;
- CI verde;
- produção pronta.

Distinguir sempre:

- CURRENT;
- TARGET;
- DECISÃO;
- PENDÊNCIA;
- BLOCKED_EXTERNAL.

Evidência vence memória ou suposição.

---

## 4. AUTONOMIA

O agente está autorizado a:

- implementar dentro do System Design aprovado;
- corrigir falhas;
- criar/ajustar testes;
- corrigir lint/typecheck;
- corrigir CI;
- criar migrations não destrutivas quando o Core possuir persistência correspondente;
- atualizar documentação;
- commit/push;
- atualizar PR;
- repetir gates;
- avançar conforme a fase governante ficar GREEN 100%.

Falha deve iniciar automaticamente:

```text
diagnosticar → corrigir → testar → auditar → repetir
```

Não pedir autorização para correções ordinárias cobertas pela arquitetura aprovada.

---

## 5. MERGE PRÉ-AUTORIZADO

Merge está autorizado somente quando:

- todos os gates obrigatórios aplicáveis estão GREEN 100%;
- CI obrigatório está verde;
- testes estão verdes;
- nenhuma STOP condition está aberta;
- diff foi revisado;
- documentação foi atualizada;
- PR está mergeable;
- nenhuma evidência contraditória existe.

Se qualquer gate estiver RED, BLOCKED_EXTERNAL ou não executado, merge é proibido.

Após merge, verificar CI pós-merge e registrar SHA/evidência.

---

## 6. DEPLOY / PRODUÇÃO

Deploy/cutover de produção exige autorização humana explícita.

Isso inclui:

- deploy produtivo;
- migration de produção como parte do release;
- cutover/tráfego;
- ativação de credenciais reais que coloque produção em funcionamento;
- operação irreversível equivalente.

Merge autorizado não significa deploy autorizado.

---

## 7. CONFIGURAÇÃO E PROVIDERS

A configuração atual por ambiente/JSON é bootstrap CURRENT.

O Target é Control Plane data-driven + Credential Vault + BYOK.

Novo cliente ou nova credencial não pode exigir:

- branch;
- commit;
- alteração de código;
- deploy específico.

Novo adapter é aceitável apenas para nova capability/provider da plataforma, não para cadastrar cliente.

Segredos:

- nunca no código;
- nunca no repositório;
- nunca em logs;
- nunca em respostas de API;
- nunca no frontend.

---

## 8. BOUNDARY OBRIGATÓRIO

Consumidores comerciais Nova FM usam o Core como caminho cognitivo normal em staging/produção.

O Core:

- interpreta;
- seleciona modelo;
- aplica fallback;
- mede uso/custo;
- retorna resultado cognitivo.

Serviços determinísticos do produto:

- autorizam;
- validam;
- mutam estado;
- executam ação crítica;
- auditam.

IA não equivale a autorização.

---

## 9. STOP CONDITIONS

Parar promoção/merge se houver:

- secret exposure;
- auth bypass;
- tenant contamination;
- capability incorreta;
- custo/medição corrompido;
- fallback inseguro;
- provider não homologado sendo tratado como homologado;
- migration destrutiva não planejada;
- regressão crítica;
- evidência contraditória.

Corrigir autonomamente quando dentro do escopo aprovado.

---

## 10. CI E BLOCKED_EXTERNAL

CI obrigatório precisa ser executado de fato.

Se GitHub Actions não iniciar por problema externo de Billing/Plans:

- registrar `BLOCKED_EXTERNAL`;
- não classificar como falha de código;
- não classificar como GREEN;
- não fazer merge dependente desse gate;
- repetir quando o serviço voltar.

Teste local é evidência auxiliar, não substituto silencioso do CI obrigatório.

---

## 11. PROIBIÇÕES

- depender de Kordena ou produto vertical;
- adicionar regra vertical;
- hardcode por tenant;
- provider direto no domínio;
- segredo no repositório;
- falsificar resultado de CI;
- remover teste para passar gate;
- contornar FM Core governance;
- alterar arquitetura material sem ADR;
- merge com gate incompleto;
- deploy sem autorização humana.

---

## 12. CONCLUSÃO

O agente deve continuar automaticamente enquanto os gates forem verificáveis e corrigíveis.

Só pode promover estado quando 100% dos critérios obrigatórios estiverem verdes.

A única barreira humana operacional permanente após gates verdes é deploy/produção.

---

## 13. CHECKPOINT F3.7.3 — CORE↔ASSISTANT↔COMMAND (2026-10-18)

- F3 do cronograma mestre Assistant é a fase ativa. F4 não pode iniciar antes de F3 100% GREEN.
- O Core **consome** credenciais BYOK do Assistant via S2S autenticado, sem ler seu banco. Toda chamada exige tenant/unidade/capability. Negação, expiração, revogação e falha de política BYOK são **definitivas**, sem troca silenciosa para FM-managed.
- O Assistant mantém identidade Core, grants e auditoria transacional de provisionamento/revogação (migration `20261018_0006`).
- O **Command corporativo** `faabio3131/FM-CONTROL-CENTER` (PR #90 Draft) gerencia o lifecycle humano; `fm-command-v2` é produto diferente e NÃO é essa autoridade.
- **Evidências inter-repositórios**: CI do Core deve estar verde no HEAD pertinente, Assistant CI e integração HMAC sintética no HEAD pertinente, e Command CI lint/typecheck/test/build e revisão de segurança também. Um participante verde não torna os demais verdes.
- CI Command encerrado antes de executar steps é `BLOCKED_EXTERNAL / NOT_TESTED`, não GREEN. Não mergear PRs F3 enquanto faltar gate. Não iniciar F4 antecipadamente.
- Próximos gates F3: PostgreSQL concorrente (nonce/revoke/locks), contratos Command↔Assistant, Vault/TLS/ACL/rate limits/secret lifecycle, quotas/circuit/FinOps/provider real/observabilidade, revisão independente de segurança.
- Testes sintéticos não equivalem a homologação; segredos reais, migrations de produção, deploy e cutover requerem autorização humana específica.
- Autonomia: corrigir, testar, documentar, atualizar tracker/PR e avançar tarefas **dentro de F3** enquanto houver gates parciais. Merge autorizado somente após 100% GREEN. Não usar computador remoto quando GitHub ou ambiente próprio bastar.


## 14. EVIDÊNCIA ASSISTANT F3.7.4 (2026-10-18)

O consumidor Core↔Assistant tem novo gate PostgreSQL 16, validando nonce concorrente e revogação em banco real descartável. **Assistant SHA funcional** `6dd2d9f7ebf84fa140ae7380f6f0386387500ca9`; Actions Postgres push `39139495756` e PR `39139500097`: SUCCESS; SaaS/contrato Core verdes. Isto é GREEN INTERMEDIÁRIO do contrato, não homologação de credencial real.

O Core não deverá considerar F3 global aprovada enquanto o Command corporativo `FM-CONTROL-CENTER` PR #90 não executar CI efetivo lint/typecheck/test/build, revisão independente e E2E completo. Jobs com zero steps são `BLOCKED_EXTERNAL`, jamais GREEN. Próxima sequência: segurança Command, Vault/rede, provider catalog, circuit/quotas/FinOps, homologação real. Sem merge prematuro nem deploy/segredos/migration produtivos.


## F3.7.5 — Cross-runtime Command/Assistant e segurança (2026-10-18)

- O estado autoritativo das identities/grants continua no Assistant. Core não pode provisionar, autoautorizar escopo, contornar revogação nem assumir o papel do Command corporativo.
- Command corporativo correto = `faabio3131/FM-CONTROL-CENTER`, PR #90 Draft; `fm-command-v2` é produto separado.
- Command recebeu auditoria de negativas e teste cross-runtime real do cliente Node assinador contra o ASGI FastAPI do Assistant. **Não confundir teste definido com teste executado**: Foundation/F21/Cognitive do Command falharam sem steps, portanto novo teste é NOT_TESTED/BLOCKED_EXTERNAL.
- Risco restante: consistência/reconciliação da auditoria interserviços, Vault, TLS/ACL, quotas/circuit/FinOps, provider homologation e revisão independente.
- F3 GLOBAL permanece IN_PROGRESS; sem merge enquanto todos os gates obrigatórios não forem GREEN. Nenhum deploy/credencial real/migration produtiva sem autorização específica. Kordena read-only.


## F3.7.7 — Governança da reconciliação de identidade (2026-10-18)

- Assistant implementou `command_request_id` único e consulta read-only HMAC de outcome do Command, sem modificar identidades/grants. Assistant gate 6/6 verde no SHA funcional `c65f05f73546380f1641611d96d6a3bd74c3a0b3`.
- A consulta tem resultados `applied`, `denied` e `unknown`; só a auditoria transacional exata no Assistant comprova execução. `unknown` jamais autoriza retry de grant/revoke/provision.
- FM Core é **somente consumidor governado**, não consulta Command para promover a si próprio nem pode substituir auditoria/grants/ACL por resposta de UI. Respeitar revogação em cada request.
- Command corporativo real `FM-CONTROL-CENTER` PR #90 Draft já tem código e testes de lookup, mas CI privado não inicia steps. Continuar `NOT_TESTED / BLOCKED_EXTERNAL` até teste efetivo.
- F3 global IN_PROGRESS, F4 NOT_STARTED, sem merge/deploy/segredos reais/migrations produtivas sem gates e autoridade humana.

## F3.7.9 — Status HMAC: replay protection no Assistant (2026-10-18)

- Assistant introduziu ledger de nonce `assistant_command_bridge_status_nonce` + migration aditiva `20261018_0008`, com teste PostgreSQL 16 de consultas concorrentes/replay, HEAD funcional `303747d8efe33536af796d75c698bf01864409a5` 6/6 SUCCESS.
- Não altera a autoridade do FM Core: Core continua consumindo credenciais somente após verificação de identidade, tenant/unidade/capability e grants pelo Assistant, e nunca consulta o Command para autoautorizar acesso.
- Não há deployment, credenciais reais nem homologação de rede/Vault: F3 IN_PROGRESS e F4 NOT_STARTED; PRs continuam Draft e merge condicionado aos gates da fase.

## F3.8 — Quotas, Circuit & FinOps: design candidate (2026-10-18)

- O arquivo `docs/F3_8_QUOTAS_CIRCUIT_FINOPS_DESIGN_CANDIDATE.md` é **proposta técnica**, não implementação, homologação nem arquitetura aprovada.
- CURRENT: route resolver exige provider healthy/circuit closed; transição automatizada e breaker distribuído/half-open não foram certificados. Usage/FinOps persistente não equivale a reserva/limite preventivo.
- Implementação futura deve exigir token/custo/quota determinísticos pré-provider, idempotência e settlement reconciliável, circuit state distribuído, half-open probe com lease/fencing, limites por tenant/unidade/capability e sem bypass BYOK→FM-managed.
- Antes de criar migrations ou alterar runtime, revisar a proposta contra ADRs, impor testes concorrentes PostgreSQL e não assumir defaults econômicos sem decisão explícita.
- F3 IN_PROGRESS; F3.8 DESIGN_CANDIDATE, não GREEN; sem merge/deploy/providers reais.

## F3.8.1–2 — Gate intermediário (2026-10-18)

- A F3.8 possui agora circuit breaker **determinístico puro**, sem estado distribuído e sem conexão ao AIModelRouter; não afirmar que o circuito protege providers reais.
- Novo ledger transacional de quotas por tenant/unidade/capability e request_id com policy row locking em PostgreSQL, reserve, settle, idempotência e limitação; migration aditiva `f3_0003`. É projeção técnica das decisões do Assistant, jamais autoridade de plano/licença do produto.
- CI do Core (funcional `3dbab732d8fa9c2425d6ebaa8d560cd6b1fbcf21`): AI Service push/PR SUCCESS e novo gate PostgreSQL16 push/PR SUCCESS. Ver `docs/F3_8_1_2_EXECUTION_CERTIFICATION.md`.
- Não ativar quotas nem breaker no runtime antes de fonte de policy autenticada, locks/leasing/fencing do breaker, testes de gasto/token/custo, monitoramento e controle de fallback.
- F3.8.1/2 = GREEN INTERMEDIÁRIO sintético; F3.8 GLOBAL IN_PROGRESS, F3 GLOBAL IN_PROGRESS, F4 NOT_STARTED. Sem merge, deploy, credenciais reais ou migration em banco não descartável.

## F3.8.3 — Circuito persistente e guards opt-in (2026-10-18)

- Código implementado: `core/ai_circuit_state_store.py`, migration aditiva `f3_0004`, row locking PostgreSQL, epoch fencing, single probe half-open, reabertura governada pós-expiração e rejeição de resultados obsoletos.
- `CoreControlPlaneAIRuntime` admite guards **injetáveis** de circuito e quota. Quando injetada, quota rejeita ausência de política antes de provider e proíbe novo envio do mesmo `request_id`, mesmo com reserva contábil idempotente.
- Circuito provider-wide é SOMENTE FM-managed nesta etapa. BYOK com circuito injetado é negado ANTES de resolver segredo; configuração com fallback misto BYOK→FM é negada para impedir troca de autoridade silenciosa.
- Uma quota representa **request técnico**, não custo nem tokens. Timeout mantém reserva pendente para reconciliação; não reembolsar automaticamente.
- Não habilitar guards por padrão no composition root comercial antes de projeção de entitlement, política aprovada, retrocompatibilidade, segurança de BYOK, FinOps real e staging.
- Documento canônico da entrega: `docs/F3_8_3_PERSISTENT_CIRCUIT_QUOTA_RUNTIME.md`. Exigir Ruff, suites, PostgreSQL16 concorrente e review antes de promover o subgate.
- F3.8 global e F3 global permanecem IN_PROGRESS; F4 NOT_STARTED. Sem deploy, migração em banco persistente, segredos reais ou merge antecipado.

## F3.8.4 — Consulta de pendencias sem acao automatica (2026-10-18)

- A quota permite consulta scoped de reservas ainda nao conciliadas, usando tenant/unidade/capability e cutoff obrigatorios. Nunca retornar reservas de outro tenant.
- A consulta nao reembolsa, nao contabiliza gasto ficticio, nao repete provider call e nao muda o estado do registro.
- O produtor do request continua impedido de executar novamente o mesmo request_id em caso de resultado ambiguo.
- Este gate nao equivale a conciliacao monetaria, provider usage settlement, cobranca ou verificacao de saldo real.
- CI verde no HEAD atual e revisao independente sao condicoes de certificacao. Nao ativar em producao.

## F3.8 — DECISÃO SUPERIOR: SOFTWARE 100% ANTES DE HOMOLOGAÇÃO EXTERNA (2026-10-18)

- Ordem expressa do proprietário: concluir **todo o código, migrations, contratos e testes internos de software**, avançando autonomamente pelas próximas tarefas e fases. Nenhuma pendência de provider real, Vault, DNS, TLS, rede, credencial externa ou homologação impede a construção.
- Depêndencias de terceiros devem ter adapters completos, mock/fake e testes determinísticos de falha/sucesso; as provas reais ficam registradas exclusivamente como `EXTERNAL_HOMOLOGATION_DEFERRED`, para após `BUILD_COMPLETE_INTERNAL_GREEN`.
- Não confundir testes PostgreSQL descartáveis/contract CI com homologação real. Manter isolamento de tenant, fail-closed, quota/circuit/FinOps, segurança, migrations aditivas, lint e CI como gates obrigatórios **internos**.
- A progressão para F4 e subsequentes depende da conclusão de implementação e CI interno da fase anterior, não de testes contra provedores reais.
- Não ativar providers, segredos reais, deploy, migration produtiva ou custos sem autorização específica; merge condicionado à certificação interna integral e à verificação de que não provoca deploy automático.
- Registrar conclusão comprovada em `docs/governance/EXECUTION_TRACKER_MASTER.md` do Assistant. Autoridade: `docs/governance/F3_BUILD_FIRST_EXTERNAL_HOMOLOGATION_LAST_2026-10-18.md` naquele repositório. Esta decisão substitui a restrição antiga somente quanto ao bloqueio de **construção** por dependências externas.

## F3.8 — MULTI-METRIC PLAN ENFORCEMENT / FM AI FINOPS (2026-10-18)

- FM Assistant é autoridade exclusiva de planos, trial, assinatura e limites comerciais. FM Core apenas aplica políticas projetadas e registra uso real; não cria um segundo sistema de billing.
- `QuotaReservations.reserve_bundle/settle_bundle` permite reservar num único commit múltiplas métricas, com policy row locking ordenado, idempotência, limitação por tenant e por unidade, proteção contra replay de request e rollback de todas as métricas diante de qualquer insuficiência.
- Tenant agregado é representado por chave técnica `__tenant__` nos testes. Não aceitar essa chave de input do cliente; só um projetor governado escolhe tenant/unidade e origem da policy.
- Custo da IA é despesa interna FM; tokens, requests, áudio e eventuais orçamentos de micro-unidades de moeda são métricas para guard técnico, não cobrança ao cliente. Nunca contabilizar tokens/custo desconhecidos como zero.
- O runtime só poderá habilitar a guarda obrigatória depois de receber plan policies assinadas do Assistant, teto de tokens efetivamente aplicado nos adapters, expiração/revogação de licença, settlement por tentativa/fallback e CI interno completo. Não confundir engine transacional de quota com funcionalidade comercial inteiramente conectada.
- Catálogo comercial é configurável e versionado, sem valores comerciais fixados no código. Referência de autoridade: Assistant `docs/governance/F3_F9_PLAN_QUOTAS_AND_AI_USAGE_ARCHITECTURE.md`.
- Homologação externa ao final; testes unitários e PostgreSQL efêmero obrigatórios durante construção, sem deploy ou credenciais reais.

## ADR-009 ASSISTANT — LIMITAR CONSUMO, NUNCA FUNÇÕES (18/10/2026)

- Planos comerciais VendeAtendeIA terão 100% das funcionalidades disponíveis a todos os tiers. O Core NÃO deve usar `plan_code` para negar acesso a módulo ou feature. Aplicar apenas teto quantitativo do consumo autorizado, RBAC/segurança/licença igualmente para todos.
- Limites e preços são cadastrados exclusivamente pela FM no Command, revisionados e publicados por autoridade corporativa; o Assistant mantém entitlement de consumo do tenant e envia projeção assinada; Core impõe limite transacional e mede gasto próprio da FM.
- Kordena `main` possui metering/projector/dashboard; **PR #230 Draft** traz também ledger de budget monetário com `UPDATE` condicionado, `AIFranchiseBudgetGuard` pré-provider, pendência conservadora no timeout, ciclo/entitlement e alertas ao cliente. Reaproveitar padrões no Core atual (quota store, FinOps preflight, ledger de attempts), sem duplicar fonte canônica de saldo. Não interpretar read-model assíncrono como reserva atômica; preservar tokens desconhecidos e identidade de attempts. Custo/pricing já possuem conteúdo idêntico em ambos projetos.
- Referência principal: `faabio3131/-FM-Assistant-Base/docs/governance/ADR-009-ALL-FEATURES-PLAN-CONSUMPTION-AND-KORDENA-FINOPS.md`.
- Construção antes de provas externas; nenhuma chamada provider real, merge com deploy indireto, segredo real ou migração não descartável sem aprovação específica.

## F3/F9 — LEITURA EXATA DE SALDO POR CLIENTE (2026-10-18)

- `GET /v1/plan/usage` usa a chave de serviço já existente do Core, com tenant/unit/resource/scope explícitos. Responde somente se o ledger persistente estiver configurado e a política existir. Não inferir `remaining=0` quando Core/policy está indisponível.
- Resposta inclui policy_revision, limit_units, window_seconds, consumed_units, reserved_units, remaining_units, period_ends_at e observed_at. Scope tenant usa chave técnica `__tenant__`; scope unidade usa unit_id específico. Não confiar em `__tenant__` fornecido pelo browser; somente Assistant autenticado envia o escopo real.
- Testes de API exigem serviço autenticado, saldo real derivado de reservas/settlements e negativa para tenant não configurado. Core CI + PostgreSQL16 obrigatórios.
- Assistant valida revisão, franquia, janela, freshness e escopo antes de exibir saldo ao cliente. Custos de modelo são dados internos FM, não entram no painel do assinante.
- A leitura é incremental, NÃO completa o control-plane de políticas ou ativação obrigatória da quota no runtime. Construir projeção assinada Assistant→Core, hard-stop e billing/eventos; não esperar homologação externa.

## F3/F9 — PONTO DE COMPOSIÇÃO DE LIMITES POR PLANO (2026-10-18)
- `build_persistent_core(..., plan_authority=...)` agora permite injetar explicitamente autoridade governada de quotas do Assistant. A inicialização nunca deve provisionar quotas, consultar provedores nem gastar tokens; o integrador confiável fornece a autoridade.
- Com `plan_authority` ausente, a compatibilidade anterior permanece, mas **isto não constitui lançamento comercial**. Antes de disponibilizar o VendeAtendeIA ao público, a composição deve exigir de modo irremovível policy assinada/atualizada, revogação, reserva atômica pré-provider, parâmetros de tokens e testes E2E.
- Consulta de consumo do Assistant já deriva avisos de uso (confirmado + reservado) e manifesto de licença ativo; não usar snapshot de dashboard como fonte de verdade de autorização.
- Estado: etapa interna incremental, F3 GLOBAL BUILD_IN_PROGRESS, homologação externa adiada. Gates no SHA final continuam necessários; sem merge/deploy/credenciais reais.


## F3/F9 — POLICY REVISION FENCING / INTERNAL GREEN (2026-10-18)

- Functional Core SHA `ca378e54226bb2925cd57e5f367f7bb27585d149`: `QuotaRequirement.policy_revision` opt-in validates the licensed plan revision against locked PostgreSQL quota policy rows during atomic reserve and settle.
- `PlanUsageGuard` always binds its requirements to the authorized policy revision, rejecting stale grants before provider execution and retaining reservations on mismatched settlement; legacy non-plan quota calls remain compatible with `policy_revision=None`.
- Negative per-attempt token counts, cached-token inconsistencies and boolean plan revision are rejected; unknown usage is not silently converted into zero.
- AI Service CI run `39189526526`: SUCCESS; F3 Quota PostgreSQL Security Gate run `39189526538`: SUCCESS on the functional SHA, including Ruff and disposable PostgreSQL concurrency/migration gate.
- Scope: **internal security subgate only**. Authenticated Assistant→Core policy projection, immediate revocation, mandatory runtime composition, full provider accounting and cross-service E2E remain BUILD_IN_PROGRESS. EXTERNAL_HOMOLOGATION_DEFERRED. No merge, production migration, provider credentials or deploy.


## F3/F9 — CORE↔ASSISTANT SIGNED PLAN GRANT TRANSPORT (2026-10-18)

- A signed, short-lived, challenge-bound grant now has a dedicated Core verifier `core/ai_signed_plan_authority.py`. Fresh challenge on each request, path-separated HMAC, strict tenant/unit/capability/revision/TTL/metrics verification; failed/unknown requests do not create unlimited quotas or retry provider work.
- `AssistantPlanHTTPSFetch` implements an explicitly injected HTTPS-only transport. It signs requests with the separately configured plan key, rejects redirects and error responses, and passes the exact signed bytes to the verifier; synthetic `httpx.MockTransport` tests cover valid, redirect, outage, replay and invalid token bounds.
- Functional SHA `cf1fd77fd7271b7eae8aa589f58a79bc78f61882`. AI Service CI `39190989920` SUCCESS; F3 Quota PostgreSQL Security Gate `39190990006` SUCCESS.
- **Not yet composed as mandatory commercial guard:** `build_persistent_core` still requires trusted `plan_authority` injection. Authenticated outbound transport is built/tested, but automatic bootstrap, live entitlement-to-policy projection/revocation state, provider input caps and comprehensive attempt/cost accounting are pending. F3 `BUILD_IN_PROGRESS`, external homologation deferred. No merge/deploy/production secrets.


## F3/F9 — Commercial runtime plan-authority gate (2026-10-19)

- Functional HEAD `0569a451d3d6d27448a0e25d10f9856f10acdd59` certifies the first commercial composition step: `core/ai_service_settings.py` now requires dedicated `FM_CORE_ASSISTANT_PLAN_URL` (HTTPS) and `FM_CORE_ASSISTANT_PLAN_SIGNING_KEY` (distinct from service, admin and BYOK secrets) for staging/production. Incomplete/insecure configuration fails startup.
- `core/ai_service_api.py` constructs `SignedAssistantPlanAuthority(AssistantPlanHTTPSFetch)` and injects it into `build_persistent_core(plan_authority=...)` for both text and audio; quota denials fail closed with sanitized dependency errors before provider invocation. Test/development can run isolated synthetic setups without signing keys.
- AI Service CI run `39193067739` SUCCESS, F3 Quota PostgreSQL Security Gate `39193067850` SUCCESS. Synthetic validation only; no real provider/network secret/deploy/merge.
- Remaining mandatory internal work: signed full allowance projection into Core quota policy tables, monotonic revision and revocation fencing under concurrent updates, provider-enforced output token bounds and safe unknown-attempt accounting, configurable per-capability bounds managed by FM, strong Core↔Assistant E2E and deployment assurance. Gate remains `BUILD_IN_PROGRESS`, PR remains Draft. External credential homologation is deferred until software construction is complete.


## F3/F9 — Signed full quota projection + provider output cap (2026-10-19)

- Assistant signs the complete grant tuple `(metric, scope, limit_units, window_seconds)` in its short-lived, challenge-bound license assertion; Core checks exact grant shape/limits/windows and revision before treating the assertion as quota authority.
- `QuotaReservations.project_signed_grants` persists each metric policy in an all-or-nothing transaction; the PostgreSQL path acquires a per-tenant/unit advisory lock, revision is monotonic, same-revision conflicts fail closed, and existing reserved/consumed amounts are retained. `PlanUsageGuard.admit` projects verified grants before atomic multi-metric admission.
- `CoreControlPlaneAIRuntime` now builds provider executors only after admission, injecting the licensed output token cap to supported OpenAI-compatible / Gemini adapters. A simulated provider test verifies the cap and token reconciliation. Unknown provider usage continues to leave reservations held, not silently refunded.
- Functional SHA Core `4bacb3fbac84997de6dbe02744d2c2e805f1c7a7`, CI `39194025504` SUCCESS, PostgreSQL gate `39194025523` SUCCESS. Companion Assistant SHA `63a1be2e99a32d40503e38b009533a3964663b3e`, 3/3 workflows SUCCESS.
- Remains `BUILD_IN_PROGRESS`: audit and close input token hard-bound handling, multiple-provider-attempt budget and failure reconciliation, window changes under active reservations, strict transport/identity authorization and commercial per-capability bounds, version transitions and full cross-runtime E2E on PostgreSQL; do not claim 100% completion. No merge/deploy/external credential or homologation work.


## F3 — 2026-10-19 GOVERNED ROTATION / FALLBACK BUDGET / FM TOKEN CEILINGS

- Atomic signed-quota projector now denies changing the accounting window for any policy with historical reservation records, preventing orphaned usage and double-counting. Version changes roll back atomically if one metric cannot migrate. Test commit `6b648c67` AI Service CI `39269317960` SUCCESS, PostgreSQL gate `39269318155` SUCCESS.
- Plan quota admission now reserves *worst-case across every routed fallback attempt* (max eight, enforced by the router); reconciliation uses aggregate measured attempts. Unknown metering remains held and is not reported as zero. The router is fenced to the admitted count; scoped credentials are not touched before admission. Functional fallback CI `39270229533` SUCCESS, PostgreSQL `39270229274` SUCCESS.
- FM-controlled `FM_CORE_ASSISTANT_PLAN_BOUNDS_JSON` can configure independent text/audio input/output token budgets; startup rejects missing, boolean, negative or oversized caps. Uses secure bounded defaults if unset. Settings/provider adapter and strict tests certified on `a284e0e0`, CI `39270629034` SUCCESS, PostgreSQL `39270628943` SUCCESS.
- Real router synthetic E2E confirms that a transient failed first provider attempt followed by fallback keeps the entire reservation pending, because cost and token usage of the first attempt are uncertain. Commit `3b6dced7` AI Service CI `39270774348` SUCCESS, PostgreSQL `39270774530` SUCCESS.
- F3 GLOBAL remains BUILD_IN_PROGRESS; not yet certifiable as complete. Remaining internal work: provider-specific reliable input-token preflight (especially audio), safe governed reconciliation/recovery for ambiguous provider attempts, quota period evolution/migration and true multi-process PostgreSQL E2E; Command/Assistant/Core contract and service identity integration; independent security review. Do not conflate with external homologation deferred until full software construction. No merge/deploy/real secrets.


## F3 — 2026-10-19 PostgreSQL historical quota rotation certification
- Implemented additional disposable PostgreSQL integration regression for signed revision changes over existing consumption in `tests/service/test_ai_quota_postgres.py`, functional SHA `3b638e4800aa0925a27d340321a8036022198f68`. Core AI Service CI `39271248172` SUCCESS and F3 Quota PostgreSQL Security Gate `39271248045` SUCCESS.
- Corporate Command `FM-CONTROL-CENTER` PR #90 remains Draft and has four passing workflows on SHA `626be1432cbd753edf3bf547dbe288dde3199b25`, but a green CI does not prove full cross-system end-to-end service identity/secret rotation.
- F3 remains BUILD_IN_PROGRESS. No promotion, merge or deploy until reliable provider-specific input/audio admission, governed reconciliation and transactional window migration, plus full Command–Assistant–Core isolated integration and security review are complete. External real-provider homologation remains deferred, not a construction blocker.


## F3 — 2026-10-19 TEXT PRE-ADMISSION ENVELOPE (INTERNAL SUBGATE)

- Added conservative UTF-8 prompt envelope preflight in `core/ai_plan_usage_guard.py`, before any quota reservation, secret resolution, or external model execution. Includes system prompt, message bodies, roles and multibyte input. Oversized requests now deny with `core_plan.input_envelope_exceeded`; they do not consume a reservation.
- Synthetic regression `tests/service/test_ai_plan_usage_guard.py::test_oversized_utf8_prompt_denied_before_any_quota_reservation` verifies no quota records are reserved for denied Unicode input.
- Functional SHA `d63621cf916ad47a1de8b70385196d9bb1359f0e` — AI Service CI `39273574128` SUCCESS, F3 Quota PostgreSQL Gate `39273575267` SUCCESS.
- This is a conservative byte envelope, NOT a provider-specific token counter. F3 remains BUILD_IN_PROGRESS until model-aware counting, particularly multimodal/audio, governed reconciliation of ambiguous paid provider attempts, signed cross-system E2E and independent security review. User requires external provider homologation only after software construction completes; do not treat it as an internal coding gate. PR draft; no merge or deploy.


## F3 — 2026-10-19 audio upload envelope gate

- Core now enforces an FM-configurable `FM_CORE_ASSISTANT_MAX_AUDIO_BYTES` audio payload ceiling (default 10 MiB, absolute max 64 MiB), validated at startup, injected from commercial CoreSettings through `build_persistent_core` into `PlanUsageGuard`. An oversize audio payload is denied before quota reservation, credential resolution and provider call. It is a *byte transport limit*, not audio token metering or model-aware token estimation.
- Functional SHA `a343b3af2374cc5ceae08b65ffe72f12841a12ac`; Core AI Service CI `39274933331` SUCCESS, F3 Quota PostgreSQL Security Gate `39274933453` SUCCESS. Regression tests cover oversize uploads, untouched quota reservations and malformed FM configuration.
- F3 BUILD_IN_PROGRESS. Pending provider-aware text/audio token accounting, uncertain-charge governed reconciliation, cross-service identity and PostgreSQL E2E, independent audit. No merge, deploy or external homologation.


## F3 — 2026-10-19 ambiguous provider consumption recovery candidate

- Internal `QuotaReservations.reconcile_ambiguous_bundle` implemented in `core/ai_quota_store.py` and regression tests added in `tests/service/test_ai_quota_store.py` and `tests/service/test_ai_quota_postgres.py`. Requires `VerifiedCommandAdmin`, fresh step-up, 64-hex SHA-256 evidence reference, explicit provider-confirmed positive usage or actual provider-confirmed no-charge, complete same-request metric bundle, matched revision, and atomic quota settlement + append-only Command admin audit with one-use token JTI.
- Concurrent PostgreSQL recovery test enforces one settlement/one audit even with two contending authorized recovery calls. No external provider call, no automatic retry, no silent refund. Internal only; no public endpoint.
- `docs/F3_8_AMBIGUOUS_USAGE_RECOVERY.md` documents limits: the evidence hash references reviewed material and is NOT itself proof that provider billed zero; independent provider evidence ingestion/verification and signed Command-facing API remain separate engineering work.
- First functional Core quota reconciliation CI `39277663167` SUCCESS, PostgreSQL `39277662911` SUCCESS. Additional concurrent PostgreSQL and latest documentation runs were queued at this checkpoint; **do not mark final subgate GREEN** until their run results are verified.
- F3 BUILD_IN_PROGRESS. No merge/deploy/production credentials or external homologation. Keep Command/Assistant/Kordena unchanged.


## F3 — 2026-10-19 GOVERNED PROVIDER RECEIPT TO CORE QUOTA SETTLEMENT

- Implemented `core/ai_verified_usage_receipt.py` for strict provider/model/request/tenant/unit identity, nonnegative integer input/output tokens, finite nonnegative Decimal FM-private provider cost and a SHA-256 evidence reference. A provider no-charge attestation must be explicitly verified; timeout/unknown status never becomes zero-cost.
- `QuotaReservations.reconcile_verified_provider_receipt` delegates to existing canonical `reconcile_ambiguous_bundle`; human `VerifiedCommandAdmin`, fresh step-up, unique Command token JTI, complete reservation bundle, policy revision, single settlement and append-only audit remain mandatory. No second Assistant ledger or self-service recovery path created.
- Added `tests/service/test_ai_verified_usage_receipt.py` plus canonical ledger settlement/integrity test in `tests/service/test_ai_quota_store.py`. All tests synthetic. Functional SHA `0f4d6b5df71cb4f606dd40bdc1e68334827dfbe8`. CI status MUST be verified independently before certification.
- These typed receipts are not themselves proof of the provider's signature: independent evidence ingestion/verification and signed Command HTTP authority remain pending internal construction. No public recovery endpoint is opened.
- Cross-service Command→Assistant→Core multi-process E2E with PostgreSQL still open; passing local contracts do NOT imply it is certified. FM Core is the financial/usage source of truth; prices/costs remain FM-private. All external provider credential/version/production homologation remains after full software construction. No merge/deploy, real secrets or production database changes. F3 BUILD_IN_PROGRESS.


- F3 synthetic end-to-end canonical quota test expanded on functional SHA `c7b336bac11931f73d20c387e5f7e40c1b1b83ae`: signed-grant-shaped plan projection → Core atomic request/token reserve → provider evidence typed receipt → Command-authorized Core recovery → exact remaining quota and duplicate settlement rejection, all in one test database. Exact-SHA Core AI Service CI `39349243629` SUCCESS and PostgreSQL quota security gate `39349243605` SUCCESS. This confirms deterministic flow logic only; the plan tuple is supplied as a trusted test input and Command principal is a synthetic verified instance, not an actual signed HTTP identity exchange between processes.
