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
