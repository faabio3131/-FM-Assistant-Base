# WhatsApp Channel Adapter V1

## Objetivo

Conectar o WhatsApp Cloud API da Meta ao núcleo universal `src/fm_assistant` sem
dependências de Kordena, Pedido, KDS, Delivery ou qualquer domínio vertical.

## Fronteira

```text
Meta WhatsApp Cloud API
        |
        v
/webhooks/meta/whatsapp/{channel_id}
        |
        +--> assinatura HMAC SHA-256
        +--> idempotência por message_id
        +--> tenant/unidade derivados do channel_id
        +--> sender convertido em referência HMAC opaca
        |
        v
WhatsAppRuntime
        |
        v
AssistantService
        |
        +--> persona
        +--> conhecimento
        +--> conversation engine
        +--> handoff humano
        +--> ModelGateway
```

## Segurança

- O webhook público usa `channel_id` opaco. Tenant e unidade não são aceitos na URL.
- `X-Hub-Signature-256` é validada com o App Secret da configuração do canal.
- Access Token, App Secret e Verify Token são criptografados em repouso com Fernet.
- A chave mestra nunca é salva no banco e deve vir de secret manager/variável de ambiente.
- O número do cliente não é persistido em `external_ref`; é convertido em HMAC.
- Mensagens duplicadas são descartadas pelo par `channel_id + message_id`.
- POST de envio para Meta não possui retry cego.
- Timeout/5xx/429 após envio entram em `reconcile_required` para evitar duplicação.

## Configuração da chave mestra

Gere uma chave Fernet:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Salve o resultado em:

```text
FM_ASSISTANT_CHANNEL_ENCRYPTION_KEY=<chave>
```

A chave de desenvolvimento presente no exemplo é proibida em staging/production.

## Configuração do tenant

Com uma API key válida do tenant:

```http
PUT /v1/channels/whatsapp
Authorization: Bearer <tenant-api-key>
Content-Type: application/json

{
  "phone_number_id": "...",
  "business_account_id": "...",
  "access_token": "...",
  "app_secret": "...",
  "verify_token": "...",
  "graph_api_version": "v23.0"
}
```

A resposta não devolve segredos. Ela informa o `channel_id` e o `webhook_path`.

## Webhook Meta

Use a URL pública:

```text
https://<host>/webhooks/meta/whatsapp/<channel_id>
```

A mesma URL atende:

- GET: challenge de verificação da Meta.
- POST: eventos assinados do WhatsApp.

## Texto

Mensagens de texto entram no Conversation Engine, recuperam/criam a conversa pelo
sender opaco, passam por persona/conhecimento/modelo e retornam pela Cloud API.

## Áudio

O adapter já:

1. reconhece eventos de áudio;
2. obtém metadados da mídia;
3. baixa apenas conteúdo `audio/*` dentro do limite;
4. expõe a porta `AudioTranscriber`.

O `CoreAudioTranscriber` já está conectado ao FM Core Base quando
`FM_ASSISTANT_MODEL_BACKEND=core`. Nesse modo, tenant, unidade, correlation ID,
bytes de áudio e MIME seguem para a capability governada de transcrição do Core.

Quando não existe transcriber configurado (por exemplo em desenvolvimento sem Core),
o comportamento permanece fail-safe: a conversa entra em handoff humano e o cliente
recebe uma mensagem determinística informando que o áudio será encaminhado.

## Estados de idempotência

- `processing`: evento reivindicado e em processamento.
- `processed`: concluído; duplicatas não reexecutam.
- `failed`: falha definitiva/retryable do processamento interno.
- `reconcile_required`: entrega externa incerta; não reenviar cegamente.

## CURRENT certificado após F2

O WhatsApp agora opera sobre o **Integration & Credential Control Plane universal**.

A fonte canônica de configuração e segredos passa a ser o Integration Fabric:

- provider `whatsapp_meta`;
- connection tenant/unit-scoped;
- configuração não secreta separada de credenciais;
- Credential Vault com ciphertext no banco e master key externa;
- versionamento de segredos;
- lifecycle de conexão;
- catálogo e capabilities;
- validação remota;
- eventos/auditoria;
- ledger inbound universal.

Os endpoints `/v1/channels/whatsapp` permanecem como **facade de compatibilidade** e
não criam uma segunda autoridade.

A migration `20261018_0004` preserva as tabelas legadas para rollback/evidência e
faz backfill do estado existente sem descriptografar ou recriptografar os ciphertexts.

Continuam fora do CURRENT:

- templates outbound iniciados pela empresa;
- gestão de opt-in/opt-out de campanhas;
- mídia de imagem/documento/vídeo;
- status de leitura/entrega;
- billing por mensagem;
- painel visual do canal.

Os controles previamente certificados permanecem obrigatórios: HMAC, idempotência,
sender opaco, áudio, handoff, no-blind-retry e `reconcile_required`.
