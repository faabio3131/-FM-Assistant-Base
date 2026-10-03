# Extraction Manifest — FM Assistant Base

## Source of truth

- Source repository: `faabio3131/fm-ai-platform`
- Source branch: `main`
- Source commit: `5a17b0c8a1cb6dad576ce5b089166748b138900c`
- Extraction date: 2026-10-03

## Canonical source chosen

The extraction is based on the modern implementation:

- `core/assistente_atendimento/`
- `application/assistente_atendimento_runtime.py`
- `application/assistente_channel_runtime.py`
- `infra/assistente_atendimento/`

The legacy `core/mica` module was intentionally NOT copied as the foundation. The source documentation itself marks it as transitional compatibility.

## Capabilities preserved in the baseline

- multi-tenant / multi-unit conversation context
- configurable public assistant identity
- text and audio inputs
- AI interpretation with strict structured schema
- customer context/history
- persisted channel state
- WhatsApp/Meta channel runtime
- duplicate-message/idempotency handling
- human handoff
- audited execution
- explicit confirmation/fingerprint gates
- operational status notifications
- focused regression tests

## Known Kordena dependencies to remove during decoupling

The copied baseline still references vertical Kordena contracts in some runtime/adapters, including:

- restaurant catalog/product contracts
- Pedido/checkout
- restaurant payment methods
- delivery/route quotation
- stock reservation
- KDS/production status
- CRM persistence owned by Kordena
- the current Kordena AI composition root
- the current assistant identity repository located under Gerente IA infrastructure

These references are preserved only so the extracted baseline retains the real behavior and provenance. They are not part of the target universal architecture.

## Target dependency direction

`FM Assistant Base -> FM Core Base`

The reverse dependency is forbidden.

## Next refactoring boundary

Restaurant concepts must move behind domain ports/capability adapters. The universal assistant should own conversation, persona, context, channel runtime, state machine, handoff, tool invocation and governance; vertical products should supply business-specific capabilities.
