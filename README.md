# FM Core Base

Fundação cognitiva reutilizável da FM Tecnologia.

## Proveniência
- Origem: `faabio3131/fm-ai-platform`
- Branch auditada: `main`
- SHA de origem: `5a17b0c8a1cb6dad576ce5b089166748b138900c`
- Extração: 2026-10-03
- Estratégia: cópia isolada primeiro; desacoplamento e evolução depois.

## Objetivo
Concentrar capacidades horizontais reutilizáveis por qualquer SaaS da FM: roteamento de IA, custos/FinOps, contexto multi-tenant, segurança, eventos, idempotência, auditoria, hardening e runtime.

## Regra arquitetural
O FM Core Base não deve depender de nenhum produto vertical. Kordena, Command, NF, CampaIA, FM Assistant Base e futuros SaaS devem depender desta fundação — nunca o contrário.

## Multimodelo
A arquitetura extraída já é provider-neutral e suporta rotas, prioridades e fallback por capability. No baseline de origem, o runtime comercial possui adapter efetivo somente para Gemini. Este repositório deverá completar adapters multimodelo preservando o contrato canônico do Router.
