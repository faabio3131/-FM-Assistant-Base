# FM Assistant Base — SaaS Architecture V1

## Objetivo

Transformar a cópia isolada do Assistente de Atendimento em um produto SaaS horizontal,
sem alterar o Kordena e sem carregar regras de restaurante no novo núcleo.

## Fronteira canônica

```text
Cliente / Canal
      |
      v
FM Assistant API
      |
      +--> Auth -> TenantContext
      |
      +--> Persona por tenant/unidade
      |
      +--> Conversation Engine
      |       |
      |       +--> persisted state/history
      |       +--> human handoff
      |
      +--> CapabilityProvider
      |       |
      |       +--> knowledge base
      |       +--> futuros plugins de domínio
      |
      +--> ModelGateway
              |
              +--> desenvolvimento (somente dev/test)
              +--> OpenAI-compatible direto (compatibilidade controlada)
              +--> FM Core Base (CURRENT integrado; obrigatório em staging/produção)
```

## Regra de isolamento

Tenant e unidade são derivados da credencial autenticada. O cliente não escolhe
`tenant_id` ou `unit_id` no payload das operações normais.

Todas as consultas persistentes de persona, conversa, mensagem e conhecimento incluem
o escopo autenticado.

## O que saiu do núcleo universal

Pedido, cardápio, KDS, delivery, estoque, forma de pagamento de restaurante e checkout
não fazem parte de `src/fm_assistant`.

O baseline extraído continua no repositório apenas como evidência histórica e fonte de
comportamento para a migração. Novas funcionalidades SaaS devem entrar pelo pacote
`src/fm_assistant`.

## Identidade configurável

Cada tenant/unidade pode definir:

- nome público
- idioma
- tom
- instruções adicionais
- status habilitado/desabilitado

Nenhum nome como “Mica” é identidade fixa do produto.

## Conhecimento

A V1 inclui uma base de conhecimento textual isolada por tenant. É deliberadamente
simples e determinística. A evolução deverá substituir/estender essa capability por
retrieval híbrido/RAG governado sem alterar o contrato do Conversation Engine.

## IA

O domínio depende de `ModelGateway`, não de SDK de provider.

O `CoreModelGateway` e o `CoreAudioTranscriber` já integram oficialmente o
FM Assistant Base ao FM Core Base. O Core é responsável por roteamento multimodelo,
fallback e evolução das políticas de modelo.

O `OpenAICompatibleGateway` direto permanece apenas como compatibilidade controlada.
Conforme ADR-002, staging/produção devem utilizar o backend `core`, salvo exceção
formal aprovada.

## Segurança

- credenciais de tenant armazenadas somente como HMAC-SHA256
- API key retornada uma única vez no provisionamento
- contexto de tenant derivado da credencial
- auditoria persistida
- SQLite proibido em staging/production
- gateway de desenvolvimento proibido em staging/production
- handoff explícito para humano

## CURRENT certificado

Já fazem parte da linha canônica:

1. integração oficial com FM Core Base;
2. WhatsApp/Meta como channel adapter desacoplado;
3. texto e áudio;
4. persona tenant-scoped;
5. knowledge textual tenant-scoped;
6. conversation engine;
7. handoff state;
8. auditoria;
9. migrations;
10. CI/testes da fundação.

## TARGET aprovado

A sequência futura é regida por:

- `docs/governance/SYSTEM_DESIGN_MASTER_V1.md`;
- ADR-001 a ADR-006;
- `docs/governance/PROMPT_MESTRE_EXECUCAO_INTEGRAL_V1.md`.

Inclui Identity/RBAC, Control Plane, Integration Fabric, BYOK, CRM/Sales Pack,
follow-up, RAG governado, human inbox, frontend comercial, billing, observabilidade
e readiness de produção.
