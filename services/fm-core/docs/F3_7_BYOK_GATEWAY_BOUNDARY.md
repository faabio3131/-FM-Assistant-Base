# F3.7 — Fronteira BYOK governada entre Core e Integration Fabric

**Data:** 2026-10-18  
**Estado:** GREEN intermediário de biblioteca, contratos e bootstrap; F3 global IN_PROGRESS.  
**Baseline funcional CI:** `5ee93dbe3d43baf7503ccc211ecf6b8989e4f176`  
**Gates remotos:** pull_request `39132973708` SUCCESS; push `39132968727` SUCCESS.

## CURRENT implementado

1. `TenantCredentialGateway` é uma porta de integração, sem dependência do domínio do Assistant.
2. `GovernedCredentialResolver` resolve credenciais FM-managed ou tenant-managed segundo origem explícita, sem alterar silenciosamente a origem.
3. BYOK exige referência de formato `integration:<tenant_id>:<opaque_id>`. Tenant deve corresponder exatamente ao tenant da solicitação.
4. IDs opacos são validados e não aparecem em `repr`.
5. Gateway é consultado apenas após validação de referência; não recebe secret/ciphertext via logs/inputs de frontend.
6. Erro de autorização, indisponibilidade ou retorno inesperado de gateway é fail-closed com código genérico.
7. Falha de autorização BYOK no executor cognitivo é definitiva. **O roteador não tenta uma rota FM-managed como fallback dessa falha.**
8. `build_persistent_core` permite injetar gateway explicitamente; sem gateway o bootstrap continua recusando BYOK.
9. É proibido configurar `credential_resolver` e `tenant_gateway` simultaneamente (origem de confiança ambígua).

## Testes obrigatórios já implementados

- FM-managed não chama gateway tenant.
- Tenant-managed não acessa chave FM.
- Tenant exato/ID opaco válido.
- Cross-tenant, referências malformadas e tentativas de path/query injection são rejeitadas antes do gateway.
- Fonte desconhecida falha fechada.
- Credencial revogada/não autorizada não causa fallback FM.
- Stub de gateway sem `SecretValue` é rejeitado.
- Bootstrap sem gateway não libera BYOK.
- Bootstrap com gateway explícito resolve o escopo correto.
- Bootstrap recusa dupla configuração de resolvers.
- Fluxo `AIModelRouter` com duas rotas comprova que BYOK negado não tenta rota FM de menor prioridade.

## TARGET ainda pendente, obrigatório antes de fechar F3.7

- Integrador de credenciais real que conecte Core à autoridade do Integration Fabric/Assistant com identidade de serviço de escopo estrito; sem usar banco do Assistant diretamente.
- Política real de autorização tenant + unit, capability, plano/BYOK entitlement, connection ACTIVE, versão atual, revogação e expiração.
- Token transportado apenas em canal criptografado e autenticado, com limites, timeouts, redaction, auditoria e controle de tráfego.
- Regras de consentimento/custos: falha de BYOK não deve cobrar FM sem política explícita.
- Testes negativos ponta a ponta de identidade de serviço, replay, tenant-unit binding, rotação e revogação sob concorrência.
- Homologação de Vault externo/rotacionável e provider real após autorizações necessárias.
- Security review, PostgreSQL e CI integration gates.

## Restrições

Nenhuma chave real foi criada, lida ou ativada nesta entrega.
Nenhum endpoint de exposição de secrets foi criado.
Nenhuma rota BYOK foi ativada na instância comercial.
Nenhum deploy ou migration real.
Nenhum merge antes de F3/gates globais 100% verdes.
Kordena read-only.

**Esta etapa é um contrato de segurança funcionalmente testado, não homologação final do BYOK.**
