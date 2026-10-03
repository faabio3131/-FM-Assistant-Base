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
              +--> desenvolvimento
              +--> OpenAI-compatible temporário
              +--> FM Core Base (destino arquitetural)
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

O adapter `OpenAICompatibleGateway` permite operação temporária com endpoints
compatíveis. A arquitetura alvo é um adapter para o FM Core Base, que será responsável
por roteamento multimodelo, fallback, FinOps e políticas de modelo.

## Segurança

- credenciais de tenant armazenadas somente como HMAC-SHA256
- API key retornada uma única vez no provisionamento
- contexto de tenant derivado da credencial
- auditoria persistida
- SQLite proibido em staging/production
- gateway de desenvolvimento proibido em staging/production
- handoff explícito para humano

## Próximas capacidades

1. adapter oficial para FM Core Base
2. WhatsApp como channel adapter desacoplado
3. webchat/Instagram
4. CRM/lead plugin
5. pipeline comercial e lead scoring
6. scheduling/follow-up
7. RAG híbrido e embeddings
8. billing/metering por tenant
9. painel administrativo
10. webhooks e SDK público
