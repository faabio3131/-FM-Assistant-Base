# F3.7.3 — Governança Command da identidade Core↔Assistant

**Data:** 2026-10-18  
**Estado:** contrato e persistência implementados em branch de desenvolvimento; testes sintéticos do Assistant aprovados. Homologação real BLOQUEADA.

## Autoridades separadas

- **FM Command corporativo:** `faabio3131/FM-CONTROL-CENTER`, branch `feat/f3-command-core-bridge-governance`, PR #90 Draft.
- **FM Assistant:** fonte de verdade persistente de identidade Core, grants e auditoria; recebe comandos autenticados.
- **FM Core:** consumidor do gateway BYOK; não se autoconcede escopo nem gerencia as chaves.
- `fm-command-v2` é produto comercial separado e não é autoridade para esta integração.

## Lifecycle implementado

`provision → grant(tenant,unit,capability) → revoke_grant → revoke_identity`.

- `provision` permite somente a identidade `key_id` previamente configurada no secret manager da FM. Não gera, distribui ou retorna chaves.
- `grant` só existe se a identidade está ativa e se tenant/unidade existem e estão ativos.
- `revoke_grant` revoga apenas o escopo exato.
- `revoke_identity` revoga a identidade e todos os grants em uma transação.
- Identidade ou grant revogado não pode ser reativado pelo mesmo lifecycle; rotação requer uma nova identidade/chave configurada e promovida via runbook.
- Nonce assinado é consumido numa tabela append-only com índice único; replay é negado.
- Actor do Command, ação, escopo, command request ID, resultado e horário são auditados na mesma transação da alteração.
- A aplicação do Core valida identidade e grant em cada solicitação, com locks no PostgreSQL: revogação bloqueia novas solicitações autorizadas.

## Protocolo interno

`POST /internal/v1/command/core-bridge/manage`

Body obrigatório:

```json
{
  "action": "grant",
  "tenant_id": "tenant-a",
  "unit_id": "unit-a",
  "capability": "ai.text",
  "target_key_id": "core-key-configurado",
  "actor_user_id": "usuario-command-autenticado",
  "organization_id": "organizacao-corporativa-fm",
  "step_up_at": 1792335600,
  "command_request_id": "id-unico-do-command"
}
```

Headers `X-FM-Command-Key-ID`, `X-FM-Command-Timestamp`,
`X-FM-Command-Nonce`, `X-FM-Command-Signature`.

Mensagem HMAC-SHA256 sobre bytes exatos:

```text
POST\n/internal/v1/command/core-bridge/manage\n<key-id>\n<timestamp>\n<nonce>\n<SHA256-hex(corpo)>
```

Proteções: HMAC de serviço separado da chave Core, validade 60s, passo humano
recente de até 5 minutos, organização corporativa exata, identity target fixada
na configuração, nonce único global e ausência de credenciais no payload de gestão.

## Schema e runtime

- `assistant_command_bridge_control_events` é criado por Alembic
  `20261018_0006` (aditiva, sem provisionamento).
- `CommandBridgeControlService` é autoritativo somente depois de validar o
  HMAC da plataforma e a afirmação de step-up assinada pelo Command.
- Segredos FM de gestão exigem configuração conjunta:
  - `FM_ASSISTANT_COMMAND_CONTROL_KEY_ID`;
  - `FM_ASSISTANT_COMMAND_CONTROL_SIGNING_KEY`;
  - `FM_ASSISTANT_TRUSTED_COMMAND_ORGANIZATION_ID`;
  - e identidade Core já configurada, distinta da chave Command.
- As chaves Command, Core e Vault não podem ser reutilizadas entre si.
- Sem configuração, o endpoint nega solicitações (fail closed).

## Command corporativo

A API do Command exige:

1. Sessão Better Auth server-side válida.
2. Organização atual idêntica ao
   `FM_COMMAND_PLATFORM_ORGANIZATION_ID` configurado pela FM.
3. Papel `owner` ou `admin` **dessa organização corporativa**.
4. Step-up por senha do próprio usuário; identidade da prova deve coincidir.
5. Payload validado; actor e target service key não podem ser escolhidos no body.
6. Assinatura HMAC a cada comando com identidade e segredo exclusivos da plataforma.
7. Auditoria no Command e auditoria transacional no Assistant.

O Command não realiza SQL no banco do Assistant. Erros/timeout/resultado
ambíguo falham fechados e **não disparam retry cego**.

## Evidências e limites

- Testes `tests/saas/test_core_bridge_service.py` cobrem provisionamento,
  grant, revogação, identidade revogada irreversivelmente, ataque cross-org,
  HMAC inválido, step-up expirado, target identity falso, nonce replay e auditoria.
- Vetor HMAC estático produzido em Node e validado em Python; cliente Core
  permanece coberto pelo workflow E2E da F3.7.2.
- Alembic `0006` não cria identidades/grants/segredos reais.
- Workflow SaaS CI do Assistant e contrato Core→Assistant em GitHub Actions:
  evidência verde no HEAD funcional de `tests`.
- Workflow do Command na PR #90 encerra sem executar testes (`steps=[]`);
  causa externa não certificada. **CI COMMAND = BLOCKED_EXTERNAL, não GREEN**.

## Pendências antes de merge/produção

- Desbloquear GitHub Actions do Command e passar lint, typecheck, tests e build;
- revisão independente de segurança em ambos os repositórios;
- teste E2E Node Command→Python Assistant no SHA atual (não só vetor HMAC);
- ensaio PostgreSQL real de locks, revogação, concorrência, replay e audit;
- ativação em rede privada HTTPS/mTLS/ACL, rate limit, observabilidade/alertas;
- gestão real de segredos e rotina de rotação/recuperação no Vault/Command;
- aprovação humana específica para migration/deploy/credenciais reais.

**GATE:** Assistant green intermediário; Command CI bloqueado; F3 global IN_PROGRESS. Merge proibido; nenhum deploy/cutover.
