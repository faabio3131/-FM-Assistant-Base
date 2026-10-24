# Matriz de construção integral — VendeAtendeIA

**Autoridade:** Prompt Mestre V1 + decisão executiva de 18/10/2026  
**Objetivo:** visão resumida da auditoria. O plano executável e os critérios vinculantes estão em
`CRONOGRAMA_MESTRE_CONSTRUCAO_100_INTERNA.md`.

| Fase | Construção de software | Configuração/teste externo |
|---|---|---|
| F0 — arquitetura e reconciliação | GREEN no tracker | Não aplicável à construção |
| F1 — Identity/RBAC/Tenant/License | GREEN no tracker | Verificações reais finais diferidas |
| F2 — integrações e credenciais (contratos) | GREEN no tracker | Credenciais e conectores vivos diferidos |
| F3 — FM Core Production Control Plane | IN_PROGRESS: base avançada; integração/reconciliação final pendente | Provedores, Vault, TLS e rede diferidos |
| F4 — Knowledge & Retrieval | NOT_BUILT na linha SaaS canônica | Serviços externos diferidos |
| F5 — Human Inbox | NOT_BUILT; fila Evolution não substitui inbox humana | Canal Meta/WhatsApp real diferido |
| F6 — Sales/CRM Pack | PARCIAL_REUTILIZÁVEL no legado; domínio comercial incompleto | Integrações CRM reais diferidas |
| F7 — Follow-up/Cadences/Agenda | NOT_BUILT | Integrações de agenda/mensageria reais diferidas |
| F8 — Frontend web comercial | PARCIAL_REUTILIZÁVEL; páginas pontuais, sem app definitivo | Domínio/publicação real diferidos |
| F9 — Billing/Plans/Quotas/Usage | IN_PROGRESS nos três repositórios; lifecycle ainda aberto | Gateway financeiro e cobrança reais diferidos |
| F10 — Observability/SRE | PARCIAL_REUTILIZÁVEL | Endpoints externos e contas reais diferidos |
| F11 — Security hardening | IN_PROGRESS por blocos; auditoria final ausente | Auditoria externa opcional diferida |
| F12 — Backup/Restore/Incidents | NOT_BUILT como gate comprovado | Infraestrutura real diferida; restore descartável é interno |
| F14 — Commercial Readiness, parte de software | PARCIAL_REUTILIZÁVEL | Verificação real de lançamento diferida |
| F13 — Staging/homologação real | `EXTERNAL_HOMOLOGATION_DEFERRED` | Executar apenas depois de Build 100% |
| F15 — Release/produção | NOT_STARTED | Separado e sujeito à aprovação |

**REGRA:** avanço da próxima fase de **construção** exige encerramento de código e gates internos da fase anterior, não credenciais reais. Criar desde já adapters e mocks de integração, inclusive testes negativos de timeout, falha, replay e isolamento. Não forjar aprovação externa.

## Critérios internos para BUILD_COMPLETE_INTERNAL_GREEN

- Implementação dos requisitos F0–F12 e parte de software de F14 sem TODOs críticos.
- Contratos externos definidos, versionados, com mocks e cobertura E2E determinística.
- CI obrigatório do HEAD certificado, lint/typecheck, testes, build, concorrência PostgreSQL descartável, migrações seguras e documentação.
- Segurança canônica: sem bypass de tenant/RBAC, vazamento de segredos ou privilégios; sem STOP crítico.
- Migrations, rede, Vault e demais recursos externos **não são** exigidos vivos para esta classificação, mas permanecem `EXTERNAL_HOMOLOGATION_DEFERRED`.

## Marco de conclusão real

Após `BUILD_COMPLETE_INTERNAL_GREEN`: configurar contas e segredos, executar staging/homologação externa F13, revisar evidências, finalizar aspectos reais de F14 e obter consentimento específico para F15. Somente essa fase pode confirmar `REAL_HOMOLOGATION_APPROVED`.

**Checkpoint corrente:** executar B0 e B1 do cronograma mestre; F3/F9 permanecem IN_PROGRESS.
