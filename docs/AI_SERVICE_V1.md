# FM Core Base — AI Service V1

## Objetivo

Expor o AIModelRouter do FM Core Base como serviço interno independente para produtos da FM, começando pelo FM Assistant Base.

A Assistente não seleciona Gemini, OpenAI, NVIDIA ou outro modelo. Ela solicita uma capability ao Core. O Core seleciona rota, aplica prioridade, fallback, metering e preserva o provider utilizado.

## Fluxo

```text
FM Assistant Base
      |
      | X-Core-Service-Key
      v
FM Core Base AI Service
      |
      +--> AIModelRouter
              |
              +--> rota primária
              |
              +--> fallback governado
                    |
                    +--> Gemini REST
                    +--> OpenAI-compatible
```

## Endpoints

- `GET /health`
- `POST /v1/ai/text`
- `POST /v1/ai/transcribe`

Os endpoints de IA exigem `X-Core-Service-Key`.

## Capabilities

A V1 atende diretamente:

- `atendimento_interpretacao`
- `atendimento_transcricao`

O contrato original do Router continua suportando novas capabilities sem alterar os consumidores.

## Providers concretos

### Gemini REST

Suporta texto e conteúdo de áudio via `generateContent`, com áudio enviado como `inlineData`.

### OpenAI-compatible

Suporta texto via `/chat/completions`.

Para uma rota de transcrição, o endpoint configurado deve suportar `/audio/transcriptions`. Isso permite OpenAI e outros providers compatíveis que ofereçam a mesma rota.

NVIDIA pode usar o adapter OpenAI-compatible para capabilities suportadas pelo endpoint configurado. Não se deve declarar transcrição em um provider que não ofereça essa capability.

## Configuração de rotas

`FM_CORE_AI_ROUTES_JSON` é uma lista JSON. Segredos não entram no JSON; cada rota aponta para o nome de uma variável de ambiente.

Exemplo conceitual:

```json
[
  {
    "configuration_id": "assistant-text-gemini",
    "provider": "gemini",
    "model": "gemini-model",
    "capability": "atendimento_interpretacao",
    "priority": 100,
    "price_snapshot_id": "price-gemini-text-v1",
    "adapter": "gemini",
    "base_url": "https://generativelanguage.googleapis.com/v1beta",
    "api_key_env": "GEMINI_API_KEY"
  },
  {
    "configuration_id": "assistant-text-openai-fallback",
    "provider": "openai",
    "model": "model-name",
    "capability": "atendimento_interpretacao",
    "priority": 90,
    "price_snapshot_id": "price-openai-text-v1",
    "adapter": "openai_compatible",
    "base_url": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY"
  }
]
```

Cada capability deve ter prioridades únicas. O Router falha fechado em políticas ambíguas.

## Fallback

Falhas transitórias de rede, HTTP 408, 429 e 5xx permitem que o AIModelRouter tente a próxima rota configurada.

Falhas definitivas não são silenciosamente transformadas em fallback.

## Isolamento

Toda requisição carrega:

- tenant_id
- unit_id
- request_id
- correlation_id
- capability

Esses campos seguem até o metering do Router.

## Segurança

- chave interna obrigatória;
- comparação constante da service key;
- segredos de provider obtidos de variáveis/secret manager;
- nenhum segredo retorna na API;
- nenhuma dependência do Kordena;
- nenhuma lógica vertical de restaurante.

## Estado desta versão

Os adapters Gemini e OpenAI-compatible possuem testes com transporte simulado. Credenciais reais de produção não foram usadas nesta certificação. Homologação real de cada provider será um gate separado.
