# F4/WP2 — versionamento e chunking persistentes de conhecimento

**Data:** 2026-10-22 · Status: construção interna candidata; nenhuma homologação externa ou migration real.

## Evolução sem reconstruir o legado

Reutilizamos `assistant_knowledge_documents`, `KnowledgeRepository`, `Permission.KNOWLEDGE_MANAGE` e a API FastAPI existente. A migration **aditiva** `20261022_0020` cria dois registros vinculados ao documento canônico: versões imutáveis de conteúdo com SHA-256 e autoria (`credential_id`), e chunks indexados por tenant/unidade/documento/revisão/ordinal com SHA-256 e offsets. Não apaga nem modifica documentação antiga durante a migration.

O comando interno autenticado `PUT /v1/knowledge/{document_id}/version` é OFF por padrão via `FM_ASSISTANT_KNOWLEDGE_VERSIONING_ENABLED=false`. Ele exige escopo da sessão, `expected_revision` estrito, documento ativo e limites de tamanho; compara revisões sob lock, insere versão/chunks na **mesma transação** e atualiza o documento legado apenas após persistir o snapshot. Se já houver a mesma versão retorna `indexed=false` sem duplicar registros.

### Regra crítica de preservação

Documento antigo sem versão **precisa primeiro ser indexado sem alterar título/conteúdo** como revisão 1. Isso evita perder a versão original por uma substituição silenciosa. Nova versão somente com `expected_revision=1`; revisões antigas e IDs de outros tenants/unidades são negados. Não existe importação de URL, fornecedor ou arquivo neste WP, nem aprovação de autenticidade externa (`external_source_verified=false`).

### Chunking

Janela determinística de 800 caracteres com sobreposição de 100, offsets de origem e limite superior, no máximo 64 chunks/documento. Sem vetorizador, chamada a LLM, cópia entre clientes, normalização destrutiva ou carga descontrolada.

### Gates

Testes SQLAlchemy/SQLite para snapshots e chunks originais, idempotência, CAS, auth API, isolamento de tenant/unidade, validação de input, limites, `active=false` e migration Alembic de dados preexistentes sem reescrita. Suite SaaS/Bridge/PG completa no SHA exato; auditoria interna FM e merge apenas na branch candidata F4 após gates; PR monolítica Assistant #1 permanece Draft.

**Limites:** ainda faltam URL/arquivo seguros, ingestão externa controlada, retriever indexado por chunks (WP1 consulta documentação legada), relevância/rerank híbrido e UI administrativa. Não declarar F4 concluída nem software pronto. Produção, migração real, segredos e homologação só após `BUILD_COMPLETE_INTERNAL_GREEN` e autorização adicional.