# F4 / WP2a — Revogação de fonte de conhecimento (2026-10-22)

**Estado:** candidata de construção interna do Assistant; não equivale a F4 GREEN.

A função de recuperação F4/WP1 já filtra `active=true`, mas o produto tinha somente a operação de adicionar documentos. Este WP incorpora a primeira operação administrativa segura de ciclo de vida, sem novo banco, provider, credencial real ou integração externa.

## Contrato

- `DELETE /v1/knowledge/{document_id}` somente com credencial autenticada e `knowledge.manage`, utilizando o tenant e a unidade da identidade do servidor. Identificador de outro tenant/unidade é indistinguível de ausente (404).
- Estado `active=false`, `updated_at` e evento `assistant.knowledge.deactivate` com credential/tenant/unit/document são persistidos **na mesma transação**. O PostgreSQL usa row lock para serializar a escrita; sem evento extra em chamada repetida.
- Repetição sobre documento próprio já inativo responde 204 sem criar segunda mutação/evento. Documento inexistente e de outro escopo respondem 404. Não apaga fisicamente o documento nem sua evidência histórica.
- As duas rotas existentes (Context Pack seletivo e contexto legado) deixam de recuperar documento desativado. O serviço cognitivo permanece com `FM_ASSISTANT_KNOWLEDGE_CONTEXT_PACK_ENABLED=false` por padrão, sem novos poderes.

## Gate

Testes SQLAlchemy/SQLite persistentes + HTTP para isolamento entre tenants e unidades, auditabilidade, idempotência, invisibilidade na recuperação e falta de credencial. Exigir suíte SaaS, PostgreSQL-bridge, contrato Core↔Assistant, Ruff/CI no HEAD final, revisão interna e rollback da rota/método. Sem merge se RED.

## Próximas pendências

Ingestão segura de arquivo/URL, versões imutáveis completas, chunking persistente, busca híbrida/rerank, edição governada, UI corporativa, auditoria de leitura e corpus de relevância continuam pendentes. Não ativar conectores externos até `BUILD_COMPLETE_INTERNAL_GREEN`.
