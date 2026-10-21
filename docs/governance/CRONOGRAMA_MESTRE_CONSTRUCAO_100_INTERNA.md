# CRONOGRAMA MESTRE — VENDEATENDEIA 100% CONSTRUÍDO E VALIDADO INTERNAMENTE

**Versão:** 1.0  
**Data-base da auditoria:** 20/10/2026 (America/Sao_Paulo)  
**Status:** APROVADO PARA EXECUÇÃO AUTÔNOMA  
**Autoridade:** decisão do proprietário da FM Tecnologia de 20/10/2026  
**Escopo:** FM Assistant/VendeAtendeIA + FM Core Base + integrações comerciais no FM Command

## 1. Objetivo e regra executiva

Concluir todo o software do VendeAtendeIA, com código, migrations, contratos, interfaces,
testes e validações internas, antes de iniciar homologações reais com terceiros.

Regra obrigatória da FM Tecnologia:

1. tudo que depende de configuração externa deve ser configurável por dados, Control Plane,
   secret reference, feature flag ou variável de ambiente validada;
2. cadastrar cliente, unidade, plano, preço, limite, credencial ou instância de provider não
   pode exigir alteração de código, branch ou deploy;
3. adapters, contratos, simuladores, fakes e testes de falha/sucesso devem ser construídos agora;
4. credenciais reais, VPS, DNS, TLS público, telefone, WhatsApp, Evolution vivo, gateway de
   pagamento, modelo de IA real e demais homologações externas só serão usados depois de
   `BUILD_COMPLETE_INTERNAL_GREEN`;
5. ausência de ambiente externo não bloqueia construção independente e não pode ser usada para
   declarar funcionalidade interna concluída sem código e testes;
6. `BUILD_COMPLETE_INTERNAL_GREEN` não significa homologado, publicado ou em produção.

## 2. Evidência auditada

| Componente | Linha auditada | HEAD | Gate no HEAD |
|---|---|---|---|
| FM Assistant / VendeAtendeIA | `feat/saas-foundation-v1`, PR #1 Draft | `503a92743e042f17af389a021e169b82c3e52c12` | 3/3 GitHub Actions SUCCESS |
| FM Core Base | `feat/ai-service-v1`, PR #1 Draft | `aea8523ce34c9011a1fc11802c94e8c43ece45f7` | 2/2 GitHub Actions SUCCESS |
| FM Command — candidato C06/F3 | PR #124 | `98650de9bd547ab592e4ce5baab438e4213b8349` | 4/4 GitHub Actions SUCCESS |

Os gates provam os respectivos HEADs. Não provam automaticamente que a fase inteira, outra PR,
um provider real ou o produto completo esteja aprovado.

## 3. Avaliação real da construção

Estados deste documento:

- `GREEN_INTERNO`: código e gates internos da fase concluídos;
- `IN_PROGRESS`: implementação ativa, com requisitos internos abertos;
- `PARCIAL_REUTILIZÁVEL`: existe base aproveitável, mas o gate da fase não foi fechado;
- `NOT_BUILT`: requisito substancial ainda ausente da linha canônica;
- `EXTERNAL_DEFERRED`: somente configuração/homologação real posterior ao build;
- `RELEASE_BLOCKED`: depende de autorização humana de produção.

| Fase | Estado auditado | O que já existe | O que falta para fechar internamente |
|---|---|---|---|
| F0 Arquitetura/reconciliação | `GREEN_INTERNO` | System Design, ADRs, Prompt Mestre, tracker e regras de autoridade | manter documentação reconciliada durante a execução |
| F1 Identity/RBAC/Tenant/License | `GREEN_INTERNO` | identidade, sessões, convites, recuperação, RBAC, tenant/unidade, licença e testes negativos | regressão final no candidato integrado |
| F2 Integration/Credential Control Plane | `GREEN_INTERNO` | catálogo, conexões, vault port, rotação/revogação, Meta/Evolution e isolamento | regressão final e adapters externos configuráveis |
| F3 FM Core Production Control Plane | `IN_PROGRESS` | catálogo/rotas persistentes, BYOK/FM-managed, quota, circuit, FinOps, plan guard, áudio, evidence store, recovery e bridges Command/Assistant | consolidar PRs; projeção/revogação obrigatória em todos os paths; metering/custo por tentativa/fallback; reconciliadores por provider sem recibo assinado; lifecycle comercial S2S; E2E adversarial e auditoria final |
| F4 Knowledge & Retrieval | `NOT_BUILT` | existem estruturas legadas de contexto, sem subsistema SaaS governado completo | documentos/URLs/arquivos, ingestão, chunk/version, provenance, busca/rerank, Context Pack, isolamento e audit |
| F5 Human Inbox | `NOT_BUILT` | fila técnica Evolution não equivale a inbox humana | assignment, takeover, transfer, notas, SLA, presence, locks, return-to-AI, UI e audit |
| F6 Sales/CRM Pack | `PARCIAL_REUTILIZÁVEL` | atendimento, persona e contexto de cliente legados | Contact/Lead, Opportunity, Pipeline/Stage, qualification/score, activity, proposal, conversion/loss, state machines, mutações determinísticas e APIs/UI |
| F7 Follow-up/Cadences/Agenda | `NOT_BUILT` | não há módulo comercial completo na linha canônica | regras/cadências, scheduler, retry/DLQ, opt-out, quiet hours, slots, reminders, audit e UI |
| F8 Frontend Web Comercial | `PARCIAL_REUTILIZÁVEL` | APIs e páginas pontuais de onboarding/QR/consumo | aplicação definitiva com auth, dashboard, knowledge, integrations, inbox, CRM, pipeline, agenda, analytics, equipe, billing, settings, acessibilidade, responsividade e E2E |
| F9 Billing/Plans/Quotas/Usage | `IN_PROGRESS` | planos/limites, quotas Core, consumo, licenças, outbox e C06 no Command | reconciliar PRs 114/118–124; concluir renovação, upgrade, downgrade, cancelamento, reativação, suspensão comercial, ACK/reconcile e visão do cliente sem expor custo FM |
| F10 Observability/SRE | `PARCIAL_REUTILIZÁVEL` | health/readiness e telemetria localizada | logging/redaction uniforme, métricas, tracing/correlation, health de dependências, alertas, incident events, SLO e dashboards internos |
| F11 Security Hardening | `IN_PROGRESS` | muitos controles e testes negativos por bloco | auditoria integral auth/RBAC/tenant/API/PII/secrets/webhooks/replay/rate limit/supply-chain/prompt-tool/billing, threat model e zero STOP aberto |
| F12 Backup/Restore/Incidents | `NOT_BUILT` | runbooks parciais | política de backup/retention configurável, restore em banco descartável, smoke, rollback e runbooks de incidente/segredo/provider |
| F13 Staging/Homologação externa | `EXTERNAL_DEFERRED` | templates e contratos internos | executar somente após marco interno: infraestrutura, chaves, providers, WhatsApp/Evolution, Asaas, TLS/DNS e E2E reais |
| F14 Commercial Readiness | `PARCIAL_REUTILIZÁVEL` | arquitetura comercial, políticas e documentação fragmentada | onboarding/support, termos/LGPD na interface, runbooks completos, ownership, QA/SRE/security final e pacote de release |
| F15 Merge/Produção | `RELEASE_BLOCKED` | merge interno pré-autorizado pelos gates | produção, cutover e migrations reais exigem autorização humana específica |

### Conclusão da avaliação

O produto possui uma fundação técnica relevante, mas ainda não atende ao marco de software 100%
construído. O gargalo não é apenas configuração externa: há módulos comerciais internos inteiros a
construir. Também existe dívida de integração por PRs monolíticas e sobrepostas. O próximo ganho de
velocidade vem de consolidar F3/F9, integrar o que já está verde e então executar F4–F12 sem voltar
a refazer fundações já certificadas.

## 4. Cronograma mestre por blocos integráveis

Cada bloco gera uma PR pequena sempre que possível. Dependências não impedem preparar testes e
contratos, mas nenhum bloco é promovido como concluído sem seu gate.

### B0 — Reconciliação e saneamento de branches/PRs

**Objetivo:** formar uma baseline integrável e eliminar trabalho concorrente redundante.

- inventariar diffs únicos e dependências das PRs Command #114, #118–#124 e PRs históricas relacionadas;
- escolher um único candidato canônico por unidade de trabalho;
- incorporar somente conteúdo ausente, resolver conflitos e marcar candidatos substituídos;
- confirmar se PR #124 contém integralmente políticas/termos/transições pretendidas;
- atualizar Assistant/Core para os HEADs certificados e impedir pin em SHA antigo;
- revisar se merge dispara deploy/migration real; desligar qualquer gatilho antes de integrar;
- executar todos os gates dos três repositórios e E2E cross-repo em bancos descartáveis;
- integrar WPs autocontidos verdes e verificar CI pós-merge.

**Gate:** inventário sem lacunas, nenhuma duplicidade de autoridade, branches atualizadas, CI completo,
rollback definido e main pós-merge verde.

### B1 — Fechamento interno de F3 e núcleo comercial F9

- tornar plan/license projection assinada e monotônica obrigatória em texto e áudio;
- assegurar revogação/expiração imediata e denial antes de acessar segredo/provider;
- medir cada tentativa e fallback com identidade própria; desconhecido permanece desconhecido;
- configurar limites e alertas administrados pela FM sem hardcode por cliente;
- implementar reconciliadores internos para providers sem recibo criptográfico nativo, com ports,
  evidência verificável simulada e estado `needs_attention` quando a prova for insuficiente;
- concluir Command→Assistant lifecycle: bind, renew, upgrade, downgrade, suspend, reactivate, cancel,
  new-customer-on-return, ACK, status read-back e reconciliação de outcome incerto;
- concluir worker/scheduler internos OFF por padrão, idempotência, leases, fencing, DLQ/quarantine;
- criar jornada cross-repo completa em processos isolados e PostgreSQL descartável;
- executar concorrência, replay, timeout, crash, cross-tenant/unit e rollback.

**Gate:** F3 `GREEN_INTERNO`, subset F9 correspondente verde, Assistant/Core/Command integrados e CI
pós-merge verde. Providers reais continuam `EXTERNAL_DEFERRED`.

### B2 — F4 Knowledge & Retrieval

- modelo persistente de fontes, documentos, versões, chunks e provenance;
- ingestão configurável de texto/arquivo/URL por ports;
- ativar/desativar/excluir com auditoria e isolamento;
- recuperação lexical/híbrida, rerank e Context Pack mínimo;
- comportamento explícito de contexto insuficiente e proteção PII/segredos;
- API, painel web e testes de relevância/regressão.

**Gate:** relevância determinística, cross-tenant negativo, provenance, falha segura e CI verde.

### B3 — F5 Human Inbox

- caixa de entrada multi-tenant, filas, assignment e presença;
- takeover/transfer/notes/SLA/return-to-AI;
- lock/fencing para impedir resposta simultânea humano+IA;
- APIs e frontend com auditoria completa.

**Gate:** concorrência, takeover, transfer, unauthorized/cross-tenant e E2E verde.

### B4 — F6 Sales/CRM Pack

- Contact/Lead e deduplicação;
- Opportunity/Pipeline/Stage state machine;
- qualification/score/activity/proposal/conversion/loss reason;
- IA limitada a interpretar/sugerir; serviços determinísticos fazem mutações;
- APIs, UI, idempotência e audit.

**Gate:** state machines, auth negativa, duplicidade, tenancy, contratos e E2E verdes.

### B5 — F7 Follow-up, Cadências e Agenda

- regras versionadas e cadências;
- scheduler/leases/retries/idempotência/DLQ/recovery;
- opt-out e quiet hours por timezone;
- slots, compromissos e lembretes;
- telas operacionais e auditoria.

**Gate:** relógio simulado, duplicidade, retry/crash, opt-out, tenancy e E2E verdes.

### B6 — F8 Frontend Web Comercial definitivo

- integrar todos os módulos em navegação única;
- estados loading/empty/success/partial/error/unavailable/unauthorized/forbidden;
- design system premium, PT-BR, acessibilidade e responsividade;
- segurança server-side; frontend nunca é fonte de autoridade;
- testes de componentes e E2E das jornadas críticas.

**Gate:** lint, typecheck, build, component, accessibility, responsive e E2E verdes.

### B7 — Fechamento integral de F9

- consolidar catálogo/planos/preços/limites configuráveis no Command;
- finalizar trial, subscription e lifecycle completo;
- fechar quotas de mensagem, áudio, tokens, storage, usuários e integrações;
- separar billing do cliente, custo IA, custo provider e margem FM;
- dashboard do cliente mostra franquia/uso/status, sem custo interno;
- testes de webhook simulado, reconciliação, concorrência, idempotência e tenancy.

**Gate:** F9 `GREEN_INTERNO` nos três repositórios e CI pós-merge verde.

### B8 — F10 Observability/SRE

- padronizar logs estruturados/redaction/correlation;
- métricas, readiness/liveness e dependency health;
- alertas configuráveis, tracing útil, incident events e SLO candidates;
- dashboards operacionais do Command com fonte/proveniência.

**Gate:** falhas sintéticas de dependência detectadas e alertadas sem vazar dados.

### B9 — F11 Security Hardening

- threat model final e matriz de fronteiras;
- testes auth/RBAC/tenant/session/API/PII/secrets/webhook/replay/abuse/rate limit;
- supply-chain, logs, migrations, destructive actions, billing e prompt/tool injection;
- secret scan, dependency audit e testes adversariais cross-repo;
- corrigir autonomamente até zero STOP.

**Gate:** zero STOP, evidência por controle e regressão integral verde.

### B10 — F12 Backup/Restore/Incidents

- contratos configuráveis de backup e retenção por ambiente;
- scripts/runbooks reprodutíveis sem segredo no repositório;
- backup e restore em PostgreSQL descartável com smoke de integridade;
- rollback de app/schema, compromise e provider outage runbooks;
- simulação interna de incidente e recuperação.

**Gate:** restore realmente executado em ambiente descartável, RPO/RTO candidatos documentados.

### B11 — F14 interno e certificação `BUILD_COMPLETE_INTERNAL_GREEN`

- fechar onboarding, ajuda, suporte e ownership;
- interfaces de termos, privacidade e LGPD conforme decisão jurídica aplicável;
- documentação, runbooks e matriz de configuração externa;
- auditoria final QA/Security/SRE e jornada mestre sem terceiros reais;
- garantir que todos os adapters externos tenham configuração, validação, fake e falha segura;
- congelar Release Candidate interno e registrar SHAs/CI/rollback.

**Gate:** F0–F12 e software de F14 verdes; nenhum TODO crítico; todos os repositórios integrados;
`BUILD_COMPLETE_INTERNAL_GREEN` formalmente registrado.

### B12 — F13 homologação externa, somente após B11

Esta etapa não pertence à construção interna. Executar depois, com autorização para ações reais:

- provisionar staging, PostgreSQL, HTTPS, DNS, Vault e observabilidade;
- configurar Evolution/WhatsApp e número real;
- configurar Gemini/OpenAI-compatible e validar uso/custo/fallback;
- configurar Asaas/gateway e executar sandbox/real controlado;
- executar E2E reais, carga, failover, backup/restore de infraestrutura e aceite;
- corrigir qualquer defeito encontrado no código e repetir certificação interna afetada.

**Gate:** `REAL_HOMOLOGATION_APPROVED`. Produção continua bloqueada até autorização F15.

## 5. Definition of Done de cada WP

Um WP só pode ser integrado quando possuir, conforme aplicável:

- requisito e autoridade canônica identificados;
- implementação completa, configuração data-driven e rollback;
- migration aditiva/reversível validada em banco descartável;
- unit, integration, contract, tenancy, security e concorrência;
- lint, format, typecheck e build;
- CI efetivamente executado no HEAD exato;
- diff e secret scan revisados;
- documentação/tracker atualizados;
- PR mergeable e sem STOP.

Falha inicia automaticamente:

```text
preservar evidência → diagnosticar causa raiz → corrigir → testar → auditar → repetir
```

## 6. Autonomia operacional permanente

O executor está autorizado, sem nova consulta, a:

- auditar, implementar e refatorar dentro da arquitetura aprovada;
- criar migrations não destrutivas e testá-las em bancos descartáveis;
- corrigir código, testes, lint, typecheck, build e CI;
- criar/atualizar branches, commits e PRs;
- reconciliar conflitos e PRs sobrepostas sem apagar evidência;
- executar revisão adversarial interna em passe separado;
- marcar PRs comprovadamente substituídas depois de registrar a relação de supersessão;
- integrar/mergear cada WP com 100% dos gates verdes;
- verificar CI pós-merge e continuar imediatamente para o próximo WP;
- atualizar este cronograma, `AGENTS.md` e o tracker conforme o CURRENT evoluir.

Não pedir autorização para correção ordinária, merge elegível ou avanço de bloco.

Continuam exigindo autorização humana específica:

- deploy/cutover/produção;
- migration em banco persistente real;
- inserir/ativar credencial real;
- realizar cobrança, pagamento, envio ou contato externo real;
- contratar recurso pago ou gerar despesa;
- executar homologação externa antes do marco B11;
- alterar política comercial ou arquitetura material já aprovada;
- operação destrutiva/irreversível sobre dados reais.

## 7. Medição e continuidade

Progresso será medido por capacidades e gates, nunca por horas gastas, número de commits ou arquivo
existente. O tracker deve registrar, por WP: estado, repositório, branch, SHA, PR, testes, CI, revisão,
merge, CI pós-merge, rollback, risco e próximo passo.

O executor não deve parar para emitir relatório intermediário. Deve avançar até conclusão, STOP real,
dependência humana material ou ação externa que exija autorização. Pergunta de status não cancela a
execução em andamento.
