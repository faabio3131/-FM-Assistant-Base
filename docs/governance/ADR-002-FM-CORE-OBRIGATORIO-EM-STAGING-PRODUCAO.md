# ADR-002 — FM Core obrigatório em staging/produção

**Data:** 2026-10-17  
**Status:** APPROVED

## Contexto

O Assistant possui gateways diretos e integração oficial com FM Core Base. A Fundação Nova FM determina o Core como módulo cognitivo central.

## Decisão

Em **staging e production**, toda capacidade cognitiva normal do FM Assistant deve passar pelo **FM Core Base**.

Adapters diretos de provider no Assistant ficam restritos a:

- development;
- test;
- diagnóstico controlado;
- exceção formal aprovada.

## Consequências

- `FM_ASSISTANT_MODEL_BACKEND=core` torna-se requisito de runtime comercial.
- Provider/model/fallback/custo são responsabilidade do Core.
- Assistant não contém política de seleção de modelos.
- Bypass comercial do Core deve falhar na validação de configuração.
