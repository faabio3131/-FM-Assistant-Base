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
      +--> Identity / Session / RBAC
      |       |
      |       +--> humano -> sessão tenant/unit-scoped
      |       +--> máquina -> API credential tenant/unit-scoped
      |
      +--> Tenant / Unit / License / Entitlements
      |
      +--> Integration & Credential Control Plane
      |       |
      |       +--> provider catalog
      |       +--> connection lifecycle
      |       +--> Credential Vault / secret versions
      |       +--> WhatsApp Meta
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

Tenant e unidade são derivados da autoridade autenticada.

Para usuários humanos, o contexto vem da sessão + membership + unidade ativa autorizada.
Para integrações de máquina, o contexto vem da API credential tenant/unit-scoped.
O cliente não obtém privilégio enviando `tenant_id` ou `unit_id` arbitrários.

Todas as consultas persistentes sensíveis devem aplicar o escopo autenticado.

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

- identidade humana separada de API credential;
- senhas com Argon2;
- sessão por token opaco armazenado somente como hash;
- cookies HttpOnly/SameSite Strict;
- RBAC por permissions explícitas e deny-by-default;
- tenant/unidade derivados da autoridade autenticada;
- API key de máquina armazenada somente como HMAC-SHA256;
- Integration Vault sem retorno de segredo/ciphertext em APIs;
- versionamento/rotação/revogação de credenciais de integração;
- auditoria persistida;
- SQLite proibido em staging/production;
- FM Core obrigatório em staging/production;
- handoff explícito para humano.

## CURRENT certificado

Já fazem parte da linha canônica:

1. integração oficial com FM Core Base;
2. Identity, sessão e RBAC humanos;
3. Tenant/Unit authority;
4. License/Entitlements foundation;
5. API credentials separadas de identidade humana;
6. Integration & Credential Control Plane universal;
7. provider catalog inicial (`whatsapp_meta`);
8. Credential Vault + secret versioning/rotation/revocation;
9. WhatsApp/Meta como facade/canal sobre o Integration Fabric;
10. texto e áudio;
11. persona tenant-scoped;
12. knowledge textual tenant-scoped;
13. conversation engine;
14. handoff state;
15. auditoria;
16. migrations versionadas;
17. CI/testes da fundação.

## TARGET aprovado

A sequência futura é regida por:

- `docs/governance/SYSTEM_DESIGN_MASTER_V1.md`;
- ADRs aprovados;
- `docs/governance/PROMPT_MESTRE_EXECUCAO_INTEGRAL_V1.md`;
- `docs/governance/EXECUTION_TRACKER_MASTER.md`.

A próxima fase é F3 — FM Core Production Control Plane. Permanecem posteriores:
Knowledge/Retrieval avançado, Human Inbox, CRM/Sales Pack, follow-up/agenda,
frontend comercial, billing/quotas, observabilidade, hardening, backup/restore,
staging/homologação e readiness comercial.
