# F3.8.3 — Circuit persistente e guarda de quotas no runtime

**Data:** 2026-10-18  
**Fase:** F3 / F3.8 IN_PROGRESS  
**Escopo:** camada técnica interna; não é autorização de deploy.

## Entrega implementada

- `core/ai_circuit_state_store.py`: estado de circuito em tabela
  `core_ai_provider_circuit_state`, com `SELECT FOR UPDATE` por provider,
  versionamento/fencing e identificador aleatório de sondagem half-open.
  OPEN nega admissões antes do cooldown; HALF_OPEN admite uma única sondagem;
  expirou: recuperação explícita reabre com cooldown, sem retry automático.
  Resultados atrasados que não correspondem à versão registrada são rejeitados.
  Falhas transitórias abrem o circuito; sucesso fecha conforme máquina de estados.
- Migration aditiva `f3_0004` e readiness do bootstrap exigindo revisão correta.
  Nenhuma migração foi executada fora de bancos descartáveis de CI.
- `CoreControlPlaneAIRuntime` possui integração **opt-in** para
  `PersistentCircuit`. Apenas credenciais FM-managed são elegíveis ao
  circuito compartilhado por provider; BYOK falha fechado antes mesmo de
  resolver o segredo até existir fencing por credencial/tenant.
- Mesmo sem circuit ativado, o runtime rejeita mistura de rotas
  `tenant_managed` e `fm_managed` no mesmo conjunto de fallback.
- Guarda de quota **opt-in** com reserva prévia antes de toda chamada a
  provider, por request/tenant/unidade/capability. Reserva para execução
  rejeita novo envio do mesmo `request_id` (inclusive após settlement).
  Uma tentativa que conclui com sucesso liquida uma unidade técnica;
  timeout/resultado ambíguo mantém reserva para reconciliação governada.
- Regressões incluem: isolamento BYOK, chave não resolvida em negativa,
  circuito de provider indisponível, transição por timeout, recuperação,
  concorrência PostgreSQL para admissão única half-open, stale fencing,
  quota antes de provider, idempotência e falha de política.

## Limites estritos

Esta entrega **não** injeta automaticamente as políticas em produção:
`build_persistent_core` ainda não fornece guarda de quota/circuit
automaticamente. As políticas precisam ser projetadas da autoridade do
Assistant; habilitação só poderá ocorrer após provisionamento governado,
retrocompatibilidade, auditoria e testes reais.

O ledger de quota mede **uma unidade abstrata por requisição completa**,
não tokens, reais, dólares ou tentativas individuais de fallback. Um mesmo
request com fallback pode disparar múltiplas tentativas de provider,
auditadas no usage ledger, e não comprova limite monetário. Nunca interpretar
a quota de requests como proteção completa de FinOps.

As reservas ambíguas não expiram nem são reembolsadas automaticamente:
é necessária política de retenção, reconciliação com eventos de provider e
ação administrativa auditável para recuperar capacidade. Um resultado
`unknown` não equivale a gasto zero. Políticas ausentes falham fechadas
quando o guard é injetado.

A topologia de circuitos FM-managed por provider não pode ser reaproveitada
para BYOK sem isolamento por credencial; não há fallback BYOK→FM implícito.

## Dependências para concluir F3.8

1. Receber/validar quotas técnicas da autoridade de entitlement do Assistant,
   incluindo assinatura/autorização, revision, ciclo, criação e atualização
   dinâmica, política de nenhum bypass.
2. Projeto e implementação de cost/token preflight com snapshot de preços,
   quotas monetárias, budget e risco desconhecido, contabilização das
   tentativas de fallback e reconciliação FinOps.
3. Política auditável de compensação de reserva abandonada, retenção de
   eventos, alertas e circuit-breaker distribuído para BYOK particionado.
4. Testar integração completa em staging autorizado com Vault/TLS/ACL,
   provedores reais, rate limiting, observabilidade e recuperação após
   interrupção de workers.
5. Revisão independente de segurança, confirmação de gates globais e
   aprovação de produção quando aplicável.

**Classificação:** implementação parcial, testável em CI; não marcar F3.8
completa, não iniciar F4, não mergear PR de F3 com dependências abertas.
