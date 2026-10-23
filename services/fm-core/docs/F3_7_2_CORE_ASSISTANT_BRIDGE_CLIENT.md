# F3.7.2 — Authenticated Assistant Credential Gateway

**Data:** 2026-10-18  
**Status:** biblioteca/runtime testados, integração real ainda não ativada.  
**Fonte de autoridade do contrato:** `faabio3131/-FM-Assistant-Base/docs/governance/F3_7_2_CORE_ASSISTANT_SIGNED_BRIDGE.md`.

## Implementação Core

- `core/ai_assistant_credential_gateway.py`: cliente HTTP autenticado, assina
  payload exato com HMAC-SHA256, timestamp UNIX e nonce aleatório;
- `core/ai_tenant_credential_resolver.py`: valida referência de tenant e
  resolve por unidade + capability com `resolve_for_request`;
- `core/ai_control_plane_runtime.py`: rota tenant-managed exige resolução
  com contexto completo e recusa fallback FM após negação BYOK;
- `core/ai_service_settings.py`: três parâmetros opcionais da integração,
  validados como conjunto e proibidos para runtime sem Control Plane persistente;
- `core/ai_service_api.py`: injeção explícita do gateway no bootstrap
  persistente quando a configuração está completa.

## Configuração (valores reais não fazem parte do repositório)

- `FM_CORE_ASSISTANT_BRIDGE_URL` — origin HTTPS do Assistant;
- `FM_CORE_ASSISTANT_BRIDGE_KEY_ID` — identidade da plataforma;
- `FM_CORE_ASSISTANT_BRIDGE_SIGNING_KEY` — chave segregada, proveniente do
  secret manager e diferente da chave de autenticação usual do Core.

Sem os três parâmetros, o gateway não é construído e a resolução de BYOK
continua negada (fail-closed).

## Segurança

- somente HTTPS, sem credencial na URL, sem redirecionamento;
- não usa proxies ambiente por padrão;
- timeout limitado, sem retries cegos;
- status != 200 ou resposta fora do contrato -> negação;
- `SecretValue` mascara `repr`;
- entrada tenant/unidade/capability em cada requisição;
- deny-on-error, sem fallback para credenciais FM;
- nenhuma chave real configurada, credencial de tenant lida ou deploy efetuado.

## Certificação

- Ruff + testes Core;
- teste de HMAC byte-a-byte, timestamp, nonce, URL, timeout e erros HTTP;
- suíte do Assistant incluindo identidade/grants/replay/revogação/auditoria;
- workflow E2E sintético de dois repositórios no Assistant com Core pinado
  em `da05ca3e736197069ac87695e2859671fca142e0`.

Persistem gates adicionais de F3: PostgreSQL concorrente, Vault,
AI provider real, runtime operando com identidade real do Command,
Observability, quotas/circuit breaker, segurança e aprovação de deploy.

**F3 global = IN_PROGRESS; não fazer merge global ou deploy.**
