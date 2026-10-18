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


## Governança Nova FM

Este produto é subordinado à Fundação Nova FM Tecnologia.

Documentação canônica de execução:

1. `docs/governance/AUDITORIA_CONFORMIDADE_FUNDACAO_NOVA_FM_2026-10-17.md`
2. `docs/governance/SYSTEM_DESIGN_MASTER_V1.md`
3. `docs/governance/ADR-001` a `ADR-006`
4. `docs/governance/PROMPT_MESTRE_EXECUCAO_INTEGRAL_V1.md`

Decisões vigentes:

- V1 = Atendente + Vendedor IA;
- FM Core obrigatório em staging/produção;
- Integration & Credential Control Plane universal;
- BYOK suportado;
- `src/fm_assistant` é a linha comercial canônica;
- frontend Web será a linha comercial definitiva.

Regra obrigatória: configuração específica de cliente, unidade, chave, token,
credencial, provider ou integração deve ser data-driven e não pode exigir alteração
de código ou deploy.

### Estado de prontidão

- IMPLEMENTADO: parcial/fundação
- INTEGRADO: parcial/fundação
- TESTADO: parcial/fundação
- HOMOLOGADO: não
- PRONTO PARA PRODUÇÃO: não
- COMERCIALMENTE DISPONÍVEL: não
