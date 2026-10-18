# EXECUTION TRACKER MASTER — FM Assistant + Sales AI V1

**Data de criação:** 2026-10-17  
**Autoridade operacional:** AGENTS.md + Prompt Mestre  
**Regra:** somente uma fase pode ser considerada fechada quando seu gate estiver GREEN 100%.

## Estados

- NOT_STARTED
- IN_PROGRESS
- RED
- BLOCKED_EXTERNAL
- GREEN

---

## Baseline

- Assistant PR: #1 Draft
- Assistant branch: `feat/saas-foundation-v1`
- Assistant HEAD documental na criação deste tracker: `823ad9e385ae5edf156df07c3561a335b12a0bd4`
- Core PR: #1 Draft
- Core branch: `feat/ai-service-v1`
- Core HEAD documental na criação deste tracker: `41617b70e2126c8a2d76e7325e68541c7d045a07`
- Kordena: read-only

---

## F0 — Reconciliação institucional

**Status:** BLOCKED_EXTERNAL

### Concluído

- [x] Auditoria de conformidade criada.
- [x] System Design Mestre criado.
- [x] ADR-001 a ADR-006 criados.
- [x] Prompt Mestre criado.
- [x] SAAS_ARCHITECTURE reconciliado com CURRENT.
- [x] WHATSAPP_CHANNEL reconciliado com CURRENT.
- [x] CORE_INTEGRATION reconciliado.
- [x] AI_SERVICE do Core reconciliado.
- [x] README Assistant atualizado.
- [x] README Core atualizado.
- [x] Projetos registrados em `C:\Nova-FM-Tecnologia\04-Projetos`.
- [x] seis decisões registradas no ledger institucional.
- [x] diff comprovou alterações documentais, sem código funcional desde os últimos SHAs certificados.

### Gate pendente

- [ ] GitHub Actions remoto verde no HEAD atual.

### Blocker

GitHub Actions não iniciou os jobs por bloqueio externo de Billing/Plans da conta.  
Classificação: `BLOCKED_EXTERNAL`.

### Regra de avanço

F1 não pode ser declarada fase ativa/fechável enquanto o gate obrigatório de F0 permanecer indisponível. Tarefas preparatórias não destrutivas podem ser estudadas, mas nenhuma promoção de fase ocorre sem GREEN.

---

## F1 — Identity / RBAC / Tenant / License Control Plane

**Status:** NOT_STARTED

## F2 — Integration & Credential Control Plane

**Status:** NOT_STARTED

## F3 — FM Core Production Control Plane

**Status:** NOT_STARTED

## F4 — Knowledge & Retrieval

**Status:** NOT_STARTED

## F5 — Human Inbox

**Status:** NOT_STARTED

## F6 — Sales / CRM Pack

**Status:** NOT_STARTED

## F7 — Follow-up / Cadences / Agenda

**Status:** NOT_STARTED

## F8 — Frontend Web Comercial

**Status:** NOT_STARTED

## F9 — Billing / Plans / Quotas / Usage

**Status:** NOT_STARTED

## F10 — Observability / SRE

**Status:** NOT_STARTED

## F11 — Security Hardening

**Status:** NOT_STARTED

## F12 — Backup / Restore / Incidents

**Status:** NOT_STARTED

## F13 — Staging / Homologação

**Status:** NOT_STARTED

## F14 — Final Commercial Readiness

**Status:** NOT_STARTED

## F15 — Merge / Production

**Status:** NOT_STARTED

### Regra atualizada de autorização

- Merge: pré-autorizado quando todos os gates aplicáveis estiverem GREEN 100%.
- Deploy/produção: bloqueado até autorização humana explícita.

---

## Registro de execução

Adicionar entradas sem apagar histórico.

Formato:

```text
YYYY-MM-DD HH:MM
FASE:
HEAD:
AÇÃO:
EVIDÊNCIA:
RESULTADO:
GATE:
PRÓXIMO PASSO:
```
