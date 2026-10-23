# F3.6.2 — Autoridade humana delegada e auditoria administrativa

**Data:** 2026-10-18  
**Estado:** implementação parcial certificada; F3 GLOBAL = IN_PROGRESS.  
**Core SHA funcional certificado:** `ec95f02b38decffdaf06f6ebc7a8e7a77af5aa5f`  
**GitHub Actions:** push `39128801541` SUCCESS; PR `39128805551` SUCCESS.

## Implementado e validado

- Verificador independente de identidade humana delegada pelo FM Command.
- JWT assinado em RS256, chave pública fixada por política; algoritmo explícito, sem aceitar chave de serviço/admin como identidade.
- `iss`, `aud`, `sub`, `jti`, `iat`, `nbf`, `exp` e `session_id` obrigatórios.
- `actor_type=human`, `role=platform_admin`, `scope=fm_core_platform`, permissão `core.ai.admin.mutate`.
- Tempo máximo de token de 5 minutos, step-up recente de até 5 minutos, tolerância de relógio limitada.
- Falha fechada, sem detalhes sobre assinatura/identidade na mensagem de erro.
- `core_ai_admin_mutation_audit` em migration aditiva Alembic `f3_0002`.
- `token_jti` único na camada SQL para prevenção de reutilização de uma mesma autorização.
- Ledger armazena identidade/sessão/ação/recurso/hash da requisição e timestamp; nunca requisição bruta, prompt ou segredos.
- `stage_admin_mutation_audit` utiliza a **mesma transação SQL** da alteração. Falha de uniqueness provoca rollback completo.
- Readiness comercial exige revision `f3_0002`; nenhuma migration automática no boot.
- Testes de identidade falsa, issuer/audience incorretos, assinatura errada, algoritmo inadequado, step-up expirado, falta de permissão, replay de jti, atomicidade e rollback.

## Restrições essenciais

**Nenhuma mutação administrativa foi habilitada.**

As APIs `/v1/admin/ai` existentes continuam apenas leitura, protegidas por chave técnica separada. A chave `X-Core-Admin-Key` **não é** uma identidade humana e não autoriza alteração.

O verificador já existe como biblioteca testada, mas **ainda não está integrado a um emissor real e governado do FM Command**.

## Pendente antes de permitir escrita

1. Definir e homologar o contrato de emissão/rotação/revogação das credenciais de assinatura do Command.
2. Verificação real de sessão e autoridade `platform_admin`, com política de revogação.
3. Integrar dois controles independentes: operador técnico + identidade humana delegada válida.
4. Implementar autorização granular por operação, no serviço determinístico.
5. Mutação de provider/route/price apenas na mesma transação do ledger auditado.
6. Proteção de concorrência, race, replay e idempotência em PostgreSQL.
7. Testes completos PostgreSQL, contrato Command↔Core, segurança e gates comerciais.
8. Revisão do modelo de confiança e aprovação do ADR correspondente.

## Gate

- Biblioteca RS256 e ledger transacional: **GREEN INTERMEDIÁRIO**.
- F3.6.2 completa: **IN_PROGRESS**.
- F3 global: **IN_PROGRESS**.
- F4: **NOT_STARTED**.
- Merge de F3: **NÃO AUTORIZADO** enquanto critérios globais não estiverem todos verdes.
- Deploy/cutover/credenciais reais/migration produtiva: **exigem autorização humana específica**.
- Kordena: **READ-ONLY**.
