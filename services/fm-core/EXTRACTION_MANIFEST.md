# Extraction Manifest — FM Core Base

## Source of truth

- Source repository: `faabio3131/fm-ai-platform`
- Source branch: `main`
- Source commit: `5a17b0c8a1cb6dad576ce5b089166748b138900c`
- Extraction date: 2026-10-03

## Included foundation

The initial isolated baseline contains:

- AI Model Router: `core/ai_router.py`
- AI pricing/cost/FinOps contracts
- Domain primitives required by the foundation: IDs, money, serialization, clock and domain errors
- Security foundation: execution context, RBAC, deny-by-default authorization, policies, secrets references and audit contracts
- Event foundation: canonical envelopes, inbox/DLQ contracts, retry, idempotent processing and metrics
- Hardening/privacy guards
- Runtime configuration, database foundation and module readiness registry
- Focused unit tests copied from the audited source

## Explicitly excluded from this base

Restaurant-specific modules were intentionally not copied:

- orders/pedidos
- PDV
- KDS
- salão/garçom
- delivery/entrega
- restaurant stock/estoque
- restaurant marketplaces
- restaurant-specific Gerente IA tools

## Multimodel status at extraction

The canonical router is provider-neutral and already supports capability routing, priority and fallback. The Kordena commercial composition root at the source commit has an effective production adapter only for Gemini. Multi-provider adapters are therefore an evolution task of this isolated repository, not a redesign of the router.

## Extraction rule

Do not introduce a dependency from FM Core Base to Kordena, FM Assistant Base, Command, NF, CampaIA or any other vertical product.
