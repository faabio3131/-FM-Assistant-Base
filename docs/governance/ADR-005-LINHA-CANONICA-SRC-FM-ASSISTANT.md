# ADR-005 — Linha canônica do produto: src/fm_assistant

**Data:** 2026-10-17  
**Status:** APPROVED

## Contexto

O repositório contém baseline vertical copiado do Kordena e o novo núcleo universal em `src/fm_assistant`.

## Decisão

`src/fm_assistant` é a única linha comercial canônica do novo produto.

O material copiado do Kordena é:

- proveniência;
- referência comportamental;
- evidência de extração;
- fonte temporária para paridade.

Não deve receber novas funcionalidades comerciais.

## Consequências

- Toda feature nova entra na linha canônica.
- Baseline será progressivamente arquivado/removido da linha comercial depois de certificação de paridade necessária.
- É proibido manter dois domínios concorrentes.
- Kordena original continua read-only.
