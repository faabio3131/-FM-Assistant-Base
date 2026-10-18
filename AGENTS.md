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
