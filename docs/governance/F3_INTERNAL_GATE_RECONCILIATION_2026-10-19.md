# F3 — Reconciliação verificável dos gates internos

Data de registro: 2026-10-19 (São Paulo). Referências: `F3_CURRENT_DISCOVERY_AND_IMPLEMENTATION_PLAN.md`, `F3_F9_PLAN_BINDING_AND_USAGE_INTERNAL_CERTIFICATION.md`, `F3_BUILD_FIRST_EXTERNAL_HOMOLOGATION_LAST_2026-10-18.md` e `EXECUTION_TRACKER_MASTER.md`.

## Provas internas construídas e seus limites

| Gate | Resultado de engenharia | Limite de evidência |
|---|---|---|
| Identidade e assinaturas Command | Assinador Node RS256 com identidade corporativa e step-up; contrato HMAC Command→Assistant | Autorização humana real e confiança de chaves externas não homologadas |
| Evidência de origem independente | `core/ai_provider_source_verifier.py`: Ed25519 com chave pública previamente confiável, checagem de assinatura, freshness, request/tenant/unit; `record_verified_source` gera comprovante FM no ledger imutável somente após validação | Exige fonte com recibos *verdadeiramente assinados*; não prova que provedores comuns forneçam essa assinatura. Para provedores sem assinatura, adaptadores de verificação próprios continuam pendentes |
| Evidência persistente | Core `f3_0005`, digest, scope, custo/token exatos e HMAC interno; PG migration e testes | HMAC demonstra origem do conector FM, não por si só origem do provedor |
| Recovery financeiro | Comando RS256, verificador segregado, Core `reconcile_verified_provider_receipt`, JTI/auditoria e anti-duplicidade | Router opt-in, ainda não montado no app principal; ausência de prova mantém reserva |
| Teste de integração | Command Node assina em processo separado, Assistant ASGI e Core ASGI executam por HTTP loopback; Core com banco PostgreSQL descartável e concorrência previamente certificada; fixture Assistant usa SQLite descartável | Não é três servidores corporativos implantados, nem HTTPS/TLS, nem prova de atomicidade cross-database. Exigir verde exato do Foundation Command antes de declarar PASS |
| Contratos Core↔Assistant | Suítes autenticadas SaaS/F3 PG e Core quotas | Não demonstram sincronização automática de toda assinatura comercial em produção |

## Pendências internas adicionais — impedir falsa declaração BUILD_COMPLETE

1. Integrar concessão canônica do billing Command ao outbox de despacho de assinatura/licença, com replay, compensação, workflow de upgrade/downgrade e auditoria. Signer puro não é despacho de eventos.
2. Propagar manifesto de quotas Assistant→Core com autenticação, TTL, versão monotônica, verificação de licença e revogação imediata; ligar `PlanUsageGuard` ao composition root em **todos** os caminhos de execução e fallback de IA. Não usar policy não sincronizada.
3. Ligar token metering oficial por provider/model/attempt a ledger de reserva e liquidação FM, incluindo falha incerta, deduplicação e limites pré-provider; só expor saldo de cliente, nunca custo/segredo FM.
4. Completar adaptadores de origem de evidência por fornecedor que não assina comprovantes de consumo. Não criar falso recibo como substituto.
5. Ampliar jornada separada de licenciamento → quota → execução → provider usage → estorno apenas comprovado, cross-tenant/cross-unit, concorrência e rollback; aprofundar revogação/consistência cross-db sem alegar transação distribuída atômica.
6. Revisar quaisquer requisitos ainda abertos do cronograma geral (inclusive Command→Assistant QR policy), realizar revisão adversarial de segurança e gates de UI, migrações, build e compatibilidade do HEAD final.

## Separação construção x homologação

Provas com credenciais reais, versões de servidores Evolution/WhatsApp, provedor de IA vivo, TLS/ACL externas, gateway de pagamento real e implantação produtiva são `EXTERNAL_HOMOLOGATION_DEFERRED`. Isso **não** bloqueia construção F3/F4. Segurança, CI interno e isolamento não são homologação externa e continuam obrigatórios.

**Classificação responsável da fase:** `BUILD_IN_PROGRESS` até fechar todos os itens internos enumerados e obter CI verde no HEAD final. Não publicar `BUILD_COMPLETE_INTERNAL_GREEN` com apenas esses dois novos gates. Nenhum merge, deploy, credencial real ou migration produtiva autorizado por este documento.
