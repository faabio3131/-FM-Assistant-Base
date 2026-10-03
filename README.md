# FM Assistant Base

Fundação universal de atendimento e agentes conversacionais da FM Tecnologia.

## Proveniência
- Origem: `faabio3131/fm-ai-platform`
- Branch auditada: `main`
- SHA de origem: `5a17b0c8a1cb6dad576ce5b089166748b138900c`
- Extração: 2026-10-03
- Estratégia: cópia isolada primeiro; desacoplamento do domínio restaurante depois.

## Objetivo
Preservar como base reutilizável: conversation state, identidade/persona configurável, contexto de cliente, texto/áudio, runtime de canais, WhatsApp/Meta, handoff humano, idempotência, auditoria e integração governada com IA.

## Regra arquitetural
O FM Assistant Base pode depender do FM Core Base. O FM Core Base não pode depender deste repositório.

Regras de restaurante como pedido, cardápio, delivery, pagamento, estoque e KDS não pertencem ao núcleo universal; serão convertidas em adapters/capabilities de domínio durante o desacoplamento.
