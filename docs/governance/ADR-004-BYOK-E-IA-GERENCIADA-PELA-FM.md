# ADR-004 — BYOK + IA gerenciada pela FM

**Data:** 2026-10-17  
**Status:** APPROVED

## Contexto

A FM pode fornecer IA como parte do serviço, mas clientes corporativos podem exigir provider/chave próprios.

## Decisão

A arquitetura suportará simultaneamente:

1. **FM-managed AI:** credenciais/providers pertencentes à FM.
2. **BYOK:** credenciais/providers pertencentes ao tenant.

A disponibilidade comercial de BYOK será governada por plano/entitlement.

## Consequências

- A escolha é configuração/política, não código.
- Segredo BYOK nunca transita para frontend após gravação.
- Core resolve a rota autorizada.
- Billing/FinOps devem distinguir custo FM de custo assumido pelo tenant.
- Provider inválido ou capability não homologada deve falhar fechado.
