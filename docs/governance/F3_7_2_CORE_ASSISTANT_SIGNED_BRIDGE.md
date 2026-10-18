# F3.7.2 — Core ↔ Assistant: identidade de serviço autenticada

**Data:** 2026-10-18  
**Estado:** Implementação de contrato + E2E sintético testados. Homologação operacional real ainda pendente.  
**Fase mestre:** F3 IN_PROGRESS — não promover F4 nem liberar deploy.

## Contexto e princípios

O Core não pode ler diretamente o banco do Assistant. A origem canônica do
tenant, unidade, plano, entitlement, status da integração e segredos permanece
no Assistant. A resolução de BYOK deve ocorrer por conexão explícita,
autenticada e auditada, sem acesso cross-tenant.

## Contrato

`POST /internal/v1/core/credentials/resolve`

Payload JSON estrito:

```json
{
  "tenant_id": "tenant-id",
  "unit_id": "unit-id",
  "capability": "atendimento_interpretacao",
  "connection_id": "id-opaco-da-conexao"
}
```

Cabeçalhos:

- `X-FM-Core-Key-ID` — identidade de serviço configurada no plano FM;
- `X-FM-Core-Timestamp` — UNIX timestamp em segundos;
- `X-FM-Core-Nonce` — valor criptograficamente aleatório e exclusivo;
- `X-FM-Core-Signature` — HMAC-SHA256 hexadecimal.

String assinada:

```text
POST\n/internal/v1/core/credentials/resolve\n<key-id>\n<timestamp>\n<nonce>\n<SHA256_hex(raw_body)>
```

A API calcula o HMAC sobre **bytes exatos** do corpo da requisição, sem
recanonizar JSON. Timestamp fora da janela de 60 s é negado. Nonce repetido
para a identidade de serviço é negado pela chave primária de banco.

Em sucesso, a resposta contém somente o segredo autorizado,
`Cache-Control: no-store`, sob HTTPS obrigatório no cliente Core.
Nenhum segredo é escrito no ledger, em logs ou exposto pelo frontend.

## Persistência governada

Migration aditiva `20261018_0005` cria:

- `assistant_core_bridge_identities` — identidades com `active` e `revoked_at`;
- `assistant_core_bridge_grants` — grants exatos por identidade, tenant,
  unidade e capability, também revogáveis;
- `assistant_core_bridge_access` — consumo de nonce, escopo solicitado, hora
  e decisão `released`/`denied`.

A migration **não provisiona, ativa nem cria chave de serviço real**.

A consulta de autorização e a auditoria do nonce usam uma transação SQL
conjunta; grant, identidade, conexão e versão do segredo são consultados com
`FOR UPDATE` quando suportado pelo backend (PostgreSQL de staging/produção).

O Assistant verifica:

- identidade de serviço existente/ativa/não revogada;
- grant por tenant/unidade/capability exatos;
- tenant e unidade ativos;
- assinatura/trial válida;
- entitlement `ai.byok`;
- provider AI habilitado e capability vinculada;
- conexão ACTIVE;
- versão `api_key` tenant-managed ativa, não revogada/não expirada;
- backend de segredo suportado.

Sem qualquer desses critérios: negar. O serviço só entrega ciphertext
descriptografado do backend atual `db_encrypted`; referência externa
continua fail-closed até existir adapter Vault homologado.

## Configuração opcional

Assistant (separada das chaves do Core e do cliente):

```text
FM_ASSISTANT_CORE_BRIDGE_KEY_ID
FM_ASSISTANT_CORE_BRIDGE_SIGNING_KEY
```

Core:

```text
FM_CORE_ASSISTANT_BRIDGE_URL
FM_CORE_ASSISTANT_BRIDGE_KEY_ID
FM_CORE_ASSISTANT_BRIDGE_SIGNING_KEY
```

- Em ausência dos parâmetros, BYOK permanece desabilitado.
- A chave é plataforma FM, segregada de `FM_CORE_SERVICE_KEY`.
- O Core exige HTTPS, host válido, sem query/fragment/userinfo.
- O Core não faz retry cego de resposta ambígua.
- Negação BYOK nunca permite fallback implícito para chave da FM.
- Revogar a identidade ou seu grant no banco interrompe solicitações futuras.
- Rotação da chave de serviço requer control plane/runbook e gestão de secret
  externo, não alterações de código por tenant.

## Gates certificados em ambiente sintético

- validação de assinatura, nonce, timeout e replay;
- acesso cross-tenant e cross-unit negados;
- conexão/capability inválidas negadas;
- revogação de identidade/grant/entitlement/credencial;
- rotação de versão de segredo;
- auditoria persistente sem valor sensível;
- Alembic `0005` aditiva e sem provisionamento automático;
- suíte SaaS e Ruff;
- testes do Core, Ruff;
- teste E2E que instala o código real de ambos os repositórios e liga
  `AssistantSignedCredentialGateway` ao ASGI real do Assistant;
- workflow E2E com SHA **fixo** do Core:
  `da05ca3e736197069ac87695e2859671fca142e0`.

## Pendências para homologação real

1. Provisionamento/revogação/rotação governados da identidade e grants pelo
   Command/Control Plane aprovado, sem SQL manual ad hoc.
2. Configuração de TLS, ACL de rede privada/ingress e rate limit do endpoint.
3. Backend Vault externo com autorização efetiva de leitura.
4. AI provider adapter/catalog tenant-scoped, com homologação real.
5. Testes de concorrência/revogação/nonce e locks em PostgreSQL real.
6. Estratégia de retenção e limpeza governada dos nonces/auditoria.
7. Observabilidade, alertas, threat model, pentest e certificação de
   produção do fluxo inteiro.
8. Deploy e credenciais reais somente após autorização humana específica.

**Conclusão:** contrato assinado implementado e E2E sintético verde não equivale
a BYOK comercial homologado. F3 global permanece IN_PROGRESS.
