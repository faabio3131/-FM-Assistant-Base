# Auditoria de Conformidade — FM Assistant Base + FM Core Base × Fundação Nova FM

**Data:** 2026-10-17  
**Status:** CANÔNICO PARA PLANEJAMENTO  
**Escopo:** FM Assistant Base + FM Core Base  
**Normas superiores:**  
- `C:\Nova-FM-Tecnologia\01-Governanca\00-DOCUMENTO-MESTRE-NOVA-FM-TECNOLOGIA.md`
- `C:\Nova-FM-Tecnologia\01-Governanca\02-PADROES-DE-CONSTRUCAO-NOVA-FM.md`

## Baseline técnico auditado

- FM Assistant Base: `f9df4e415c8317ed61ffc46e3007fe3d56d9e0fc`
- FM Core Base: `72498c8853dfc84198d0de98cc9b5e7378b4c260`
- Ambas as PRs permanecem Draft.
- Nenhum merge ou deploy de produção foi autorizado por este documento.
- Kordena permanece fonte de referência/read-only; alterações são proibidas salvo decisão explícita futura.

## Conclusão executiva

A base técnica atual é aproveitável e não deve ser reconstruída. Ela está forte em multi-tenancy, boundaries, WhatsApp, idempotência, secrets, migrations, CI, separação Assistant/Core e roteamento multimodelo. O principal desvio foi de sequência institucional: implementação estrutural relevante começou antes da formalização integral de System Design, ADRs, Definition of Done comercial, Control Plane, frontend, observabilidade e readiness.

## Verde — preservar

- `src/fm_assistant` como núcleo universal.
- FM Core Base separado do produto vertical.
- CoreModelGateway e CoreAudioTranscriber.
- AIModelRouter provider-neutral.
- Tenant/unidade derivados da autoridade autenticada.
- WhatsApp Meta em adapter dedicado.
- Verificação HMAC de webhook.
- Idempotência `channel_id + message_id`.
- Estado `reconcile_required` para entrega incerta.
- Segredos do WhatsApp criptografados em repouso.
- API keys de tenant armazenadas por hash.
- Alembic/migrations rastreáveis.
- APIs `/v1`.
- Correlation IDs.
- Auditoria persistida.
- CI, lint e testes atuais.
- PRs Draft sem merge automático.

## Amarelo — evolução obrigatória

- autenticação humana e sessões;
- RBAC/ABAC;
- Control Plane de tenant/unidade/licença;
- Integration & Credential Control Plane universal;
- Core obrigatório em staging/produção;
- observabilidade;
- health de dependências;
- rate limiting e quotas;
- FinOps persistente;
- Knowledge/RAG real;
- handoff humano operacional;
- CI de segurança/migration/E2E/smoke;
- documentação reconciliada;
- homologação real de providers;
- staging/cloud;
- backup/restore.

## Vermelho/ausente

- frontend comercial;
- onboarding web;
- CRM/Sales Pack;
- billing/plans/entitlements;
- painel de atendimento humano;
- Product & Market formal do produto;
- Gate Final de Segurança;
- readiness comercial;
- registro organizacional completo do novo produto.

## Seis decisões aprovadas em 2026-10-17

1. **Produto V1:** Atendente + Vendedor IA, arquitetado para evoluir a plataforma de agentes.
2. **FM Core obrigatório:** staging/produção usam FM Core Base como caminho cognitivo normal.
3. **Integration & Credential Control Plane universal:** novo cliente/configuração não exige alteração de código nem deploy.
4. **BYOK suportado:** IA da FM e chave/provider do assinante podem coexistir, governados por plano/política.
5. **Linha canônica:** `src/fm_assistant` é a linha comercial oficial; baseline Kordena é somente proveniência controlada.
6. **Frontend comercial definitivo:** construir a UI final sobre a mesma linha de produto; proibido painel provisório descartável.

Essas decisões estão formalizadas nos ADRs desta pasta.

## Estado de prontidão correto

- **IMPLEMENTADO:** sim, para parte relevante da fundação.
- **INTEGRADO:** sim, para Assistant ↔ Core e WhatsApp no escopo testado.
- **TESTADO:** sim, no escopo dos testes atuais.
- **HOMOLOGADO:** não.
- **PRONTO PARA PRODUÇÃO:** não.
- **COMERCIALMENTE DISPONÍVEL:** não.

## Gate

Nenhum executor deve declarar o produto pronto, homologado ou comercialmente disponível até que o Prompt Mestre de Execução Integral seja concluído e seus gates obrigatórios estejam verdes.
