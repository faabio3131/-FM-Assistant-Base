# F3.7 — Elegibilidade BYOK no FM Assistant Base

**Data:** 2026-10-18  
**Status:** implementação intermediária de política local — F3 global IN_PROGRESS.

## CURRENT

O arquivo `src/fm_assistant/core_byok_release_policy.py` implementa uma política
interna `CoreBYOKReleasePolicy` com decisão booleana, sem retornar nem decifrar
credenciais. A consulta é somente leitura.

Pré-condições cumulativas:

- tenant ativo;
- unidade ativa **do mesmo tenant**;
- licença em estado active ou trial, ainda dentro do prazo aplicável;
- entitlement `ai.byok` habilitado;
- integração do tenant/unidade em estado ACTIVE;
- provider registrado, habilitado e com integration_type `ai`;
- capability solicitada vinculada à conexão;
- secret `api_key` tenant-managed ativo, ainda não revogado nem expirado;
- ciphertext/referência existente em backend conhecido.

Qualquer condição ausente significa `False`, inclusive no escopo errado.

## Segurança e escopo

- Nenhum endpoint Web/API de liberação de segredo foi adicionado.
- Nenhum valor secreto é lido, desencriptado, enviado ou registrado.
- A política **NÃO** verifica identidade de serviço. Essa autenticação deverá
  ser aplicada por uma fronteira separada antes de qualquer liberação real.
- A política isolada não garante atomicidade entre verificação e entrega:
  integração real deve assegurar versão e estado no momento da leitura,
  incluindo concorrência e revogação.
- Não há integração Core↔Assistant ativa nem BYOK comercial homologado.
- Proibido considerar testes de banco local equivalentes a homologação de
  provider, Vault ou identidade de serviço.

## Evidência

Testes `tests/saas/test_core_byok_release_policy.py` cobrem:

- caso válido sintético;
- tenant/unidade/conexão/capability incorretos;
- tenant, unidade, provider e conexão desabilitados;
- plano/entitlement suspensos;
- trial e assinatura ativa expirados;
- segredo expirado, revogado, FM-managed ou ausente;
- decisão booleana sem retorno de secrets.

## Próximo gate necessário

Implementar e testar o vínculo serviço↔tenant↔unidade↔capability entre Core e
Assistant, com identidade de serviço verificável, consentimento/entitlement,
entrega mínima de segredo, TLS/autenticação, replay, rotação, revogação sob
concorrência, métricas sem valores sensíveis, circuit breaker e testes E2E.

Até então a resolução BYOK deve continuar fail-closed no runtime comercial.
Nenhum merge/deploy enquanto os gates globais da F3 não estiverem verdes.
Kordena continua read-only.
