# F4/WP1 — Knowledge Context Packs com recuperação seletiva por tenant

**Data:** 2026-10-22. **Estado:** WP interno candidato para CI. F4 global permanece IN_PROGRESS.

## Base reutilizada e objetivo

A fundação já possui KnowledgeDocumentORM, KnowledgeRepository, endpoints existentes de conhecimento e isolamento SQL. Esta entrega **não** recria schema, conversa, auth nem outro repositório. Introduz `BoundedKnowledgeRetrieval` e a seleção opt-in de contexto por pergunta na mesma `KnowledgeCapabilityProvider` que alimenta o AssistantService.

## Semântica de recuperação

- Leitura SQL restrita por `tenant_id`, `unit_id`, `active=true`, ordenação determinística; no máximo 501 linhas consultadas e 500 consideradas.
- Pergunta normalizada com Unicode e stopwords PT-BR; coincidência lexical ponderada por título e corpo. Nenhum vetor/provider/modelo externo, nenhuma busca global.
- Context Pack limitado: cinco fontes, 4.400 caracteres de snippets+proveniência, trechos de até 1.000 caracteres com `document_id` e `updated_at` da fonte; fonte não é autoridade para instruções do modelo.
- Falta de correspondência => contexto vazio, **nunca** despejo do catálogo inteiro no modo novo, informação inventada ou prova de preço/certificação.
- Documento inativo ou fora da unidade/tenant não é recuperado. Fonte muito extensa é pulada até a futura ingestão versionada por chunks.
- `current_source_verified=false` porque o sistema conhece a versão local existente, **não** autentica URLs, preços, estoque ou informação externa.

## Ativação e compatibilidade

`FM_ASSISTANT_KNOWLEDGE_CONTEXT_PACK_ENABLED=false` por padrão. Quando `true` na composição da API, o mesmo `AssistantService` usa Context Pack mínimo e question-aware. Sem o flag, o contrato legado continua intacto para compatibilidade; nenhuma credencial ou configuração externa real é exigida. O próximo WP deve migrar para política por tenant e remover o fallback de contexto global legado após certificar relevância.

## Testes e pendências

`tests/saas/test_f4_knowledge_context_pack.py` prova isolamento de tenant+unidade, exclusão de inativos, ranking determinístico, orçamento de contexto, vazamento cruzado negativo, fonte com texto hostil rotulada como dados, pergunta sem termos e seleção runtime opt-in. Banco SQLite isolado (SQLAlchemy real); a suite completa e os gates PostgreSQL/bridge já existentes devem permanecer verdes.

F4 **NÃO** está concluída: ainda faltam documento/URL/arquivo, ingestão com validação, versões imutáveis de fonte, chunking persistente, busca híbrida/reranking, UI/admin, auditoria por operação e testes de relevância com corpus de referência. Não declarar homologação externa, produção, F4 GREEN ou BUILD_COMPLETE_INTERNAL_GREEN por este WP.