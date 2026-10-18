# Integração FM Assistant Base → FM Core Base V1

## Decisão arquitetural

O FM Assistant Base não importa o código do FM Core Base e não conhece SDKs de providers.

A integração usa uma API interna autenticada:

```text
WhatsApp / API / Webchat
          |
          v
FM Assistant Base
          |
          +--> CoreModelGateway
          +--> CoreAudioTranscriber
                    |
                    v
             FM Core Base
                    |
                    v
             AIModelRouter
                    |
              provider/model
```

Isso permite versionar e implantar os dois repositórios separadamente.

## Texto

Quando `FM_ASSISTANT_MODEL_BACKEND=core`, o Conversation Engine envia ao Core:

- tenant/unidade autenticados;
- system prompt derivado da persona;
- contexto autorizado;
- histórico mínimo;
- mensagem do cliente;
- correlation ID.

O Core retorna apenas o resultado selecionado. A Assistente não escolhe provider/model.

## Áudio

O WhatsApp passa para `CoreAudioTranscriber`:

- tenant_id;
- unit_id;
- WhatsApp message ID como correlation ID;
- bytes do áudio;
- MIME type.

O Core executa a capability `atendimento_transcricao` e pode aplicar fallback entre rotas.

## Configuração

```text
FM_ASSISTANT_MODEL_BACKEND=core
FM_ASSISTANT_CORE_BASE_URL=https://<core-internal-host>
FM_ASSISTANT_CORE_SERVICE_KEY=<internal-secret>
```

Em staging/production a service key precisa ter pelo menos 32 caracteres.

## Compatibilidade

O backend direto `openai_compatible` permanece temporariamente para compatibilidade e desenvolvimento, mas a arquitetura alvo de produção é `core`.

## Falhas

Se o Core ficar temporariamente indisponível:

- a chamada da Assistente falha fechada;
- no WhatsApp, o inbound fica como falha retryable do processamento;
- o webhook retorna falha para permitir nova entrega;
- a Assistente não tenta escolher um provider por conta própria.

Se a entrega de saída para a Meta ficar incerta depois de uma resposta do Core, permanece a proteção `reconcile_required`, sem retry cego.

## Resultado

Provider routing, fallback e evolução multimodelo passam a ser responsabilidade exclusiva do FM Core Base. A Assistente permanece focada em conversa, contexto, canais, handoff e capabilities de negócio.


## Governança comercial aprovada em 2026-10-17

Conforme ADR-002, staging/produção devem usar `FM_ASSISTANT_MODEL_BACKEND=core`
como caminho cognitivo normal. Provider direto no Assistant permanece apenas para
development/test, diagnóstico controlado ou exceção formal.

Conforme ADR-003 e ADR-004, configuração de providers/credenciais por cliente evoluirá
para Control Plane data-driven e BYOK governado. Novo cliente não pode exigir alteração
de código nem deploy.
