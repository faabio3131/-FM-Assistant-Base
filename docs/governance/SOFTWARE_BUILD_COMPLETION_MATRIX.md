# Matriz de construção integral — FM Assistant + Sales AI V1

**Autoridade:** Prompt Mestre V1 + decisão executiva de 18/10/2026  
**Objetivo:** finalizar a implementação de todo o produto antes da homologação real.

| Fase | Construção de software | Configuração/teste externo |
|---|---|---|
| F0 — arquitetura e reconciliação | GREEN no tracker | Não aplicável à construção |
| F1 — Identity/RBAC/Tenant/License | GREEN no tracker | Verificações reais finais diferidas |
| F2 — integrações e credenciais (contratos) | GREEN no tracker | Credenciais e conectores vivos diferidos |
| F3 — FM Core Production Control Plane | IN_PROGRESS: F3.8 FinOps/entitlement em desenvolvimento | Provedores, Vault, TLS e rede diferidos |
| F4 — Knowledge & Retrieval | NOT_STARTED | Serviços externos diferidos |
| F5 — Human Inbox | NOT_STARTED | Canal Meta/WhatsApp real diferido |
| F6 — Sales/CRM Pack | NOT_STARTED | Integrações CRM reais diferidas |
| F7 — Follow-up/Cadences/Agenda | NOT_STARTED | Integrações de agenda/mensageria reais diferidas |
| F8 — Frontend web comercial | NOT_STARTED | Domínio/publicação real diferidos |
| F9 — Billing/Plans/Quotas/Usage | NOT_STARTED | Gateway financeiro e cobrança reais diferidos |
| F10 — Observability/SRE | NOT_STARTED | Endpoints externos e contas reais diferidos |
| F11 — Security hardening | NOT_STARTED | Auditoria final externa diferida |
| F12 — Backup/Restore/Incidents | NOT_STARTED | Restore real de infraestrutura diferido |
| F14 — Commercial Readiness, parte de software | NOT_STARTED | Verificação real de lançamento diferida |
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

**Checkpoint corrente:** F3 IN_PROGRESS. Não antecipar certificação interna de F4–F12/F14 que ainda não foram construídas.
