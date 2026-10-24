# ADR-003 — Integration & Credential Control Plane universal

**Data:** 2026-10-17  
**Status:** APPROVED

## Contexto

WhatsApp já possui configuração tenant-scoped, porém cada integração futura não pode gerar novo fluxo ad hoc nem exigir alteração de código por cliente.

## Decisão

Construir um **Integration & Credential Control Plane universal**, data-driven, com adapters por provider.

Novo assinante deve configurar integrações via UI/API sem commit, branch ou deploy.

Lifecycle mínimo:

```text
DRAFT → VALIDATING → ACTIVE → DEGRADED → DISABLED → REVOKED
```

Operações:

- connect;
- validate;
- activate;
- update;
- rotate;
- revoke;
- disconnect;
- health check.

## Consequências

- WhatsApp será migrado para o fabric.
- Configurações não-secretas ficam em storage tenant-scoped.
- Secrets ficam em vault/ciphertext/referência aprovada.
- Get/list nunca retornam segredo em claro.
- Integrações futuras reutilizam o mesmo control plane.
