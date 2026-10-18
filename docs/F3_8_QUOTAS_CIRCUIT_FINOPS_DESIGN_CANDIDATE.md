# F3.8 — Quotas, circuit breaker e governança FinOps (candidata de design)

**Estado:** DESIGN CANDIDATE / NOT_IMPLEMENTED, 2026-10-18.
**Autoridade:** Prompt Mestre F3, AGENTS.md, tracker mestre Assistant.
Não promover para GREEN, não criar recursos nem ativar providers por este documento.

## CURRENT comprovado

- `AIControlPlaneStore.resolve` seleciona rota na ordem de scope
  unit→tenant→platform, filtrando provider com `health=healthy` e
  `circuit=closed`. O estado health/circuit é atualmente configurado por
  `set_provider_health`, não por transições automáticas com cooldown.
- `AIModelRouter` faz fallback para falha transitória, sem circuit state
  global distribuído. Construir um router por request **não** permite usar
  contadores locais como autoridade do breaker entre workers.
- O ledger persistente de usage/FinOps registra tentativas por scope e
  price_snapshot imutável. Custo desconhecido é identificado, não vira
  implicitamente R$ 0. Controle preventivo de quotas ainda não é provado.
- BYOK tenant-scoped é resolvido apenas no caminho escolhido; negativa BYOK
  não pode cair silenciosamente em rota FM-managed.
- A ponte Command→Assistant é distinta deste governor. Não alterar seu
  estado de identities/grants ou chave HMAC para contornar falhas do provider.

## Arquitetura alvo a validar

1. **PolicyStore governado:** limites (request, token, custo máximo estimado,
   concurrency) por tenant/unidade/capability/periodo, origem dos limites e
   revisão. Não aceitar override por cabeçalho cliente.
2. **Preflight Reserve** determinístico, persistente e transacional:
   (tenant, unit, capability, request_id) idempotente, com quota e período
   definidos. Contadores globais não podem depender de memória local.
3. **Settlement:** contabilizar consumo real de provider, refund de reserva
   não usada, retries/fallback sem dupla cobrança, unknown cost auditável e
   política explícita de risco financeiro quando preço não for conhecido.
4. **Circuit State Store** compartilhado entre workers, chave por provider
   ou pool seguro de credenciais conforme modelo de falha; estado CLOSED,
   OPEN e HALF_OPEN governado por janela de falhas e cooldown. Jamais
   compartilhar chaves BYOK ou conceder acesso entre tenants.
5. **Single half-open probe:** lease/compare-and-swap persistente com TTL e
   fencing; concorrência de múltiplos workers não autoriza múltiplos probes
   involuntários. Erro/timing desconhecido deve falhar fechado conforme
   política de disponibilidade e segurança.
6. **Integration point:** avaliar interface no `AIModelRouter` que faça
   reservar→admitir rota→executar→registrar outcome→settlement, sem segundo
   motor de decisão. Controle de quotas precede toda chamada externa.
7. **Circuit no fallback:** se rota A estiver aberta, selecionar somente
   alternativa compatível com a política de escopo e custo, respeitando
   preferência tenant/BYOK e lista de capabilities. Nenhum fallback de
   credenciais de cliente para credencial FM é implícito.
8. **Timeout / replay / race:** retry só para erro transiente idempotente;
   requests longas, backpressure, cancelamento, nonce e correlação não
   devem gerar duplicidade de gasto.
9. **Observabilidade:** métricas por org/tenant/unidade/modelo, abertura de
   breaker, half-open probe, custos conhecidos/desconhecidos, reservados/
   liquidados e saturação. Não exportar payloads, segredos ou PII.

## Gates de engenharia

- Unitários de transição CLOSED→OPEN→HALF_OPEN→CLOSED e falha de probe.
- PostgreSQL 16 real com múltiplos workers concorrentes: quota no limite,
  idempotência, lease half-open e rollback/falha de banco.
- Negative tests: cross-tenant, spoofing, permissão insuficiente,
  BYOK→FM-managed proibido, resposta ambígua e preço desconhecido.
- Fallback e FinOps ledger conciliados por request_id mesmo em provider
  timeout, rate limit, erro permanente, parcial e concorrência.
- CI de Core e Assistant 100% GREEN no HEAD após qualquer implementação.
- Revisão independente de segurança e homologação de providers reais antes
  de F3 global GREEN.

## Decisões ainda não congeladas

- Política exata de preço desconhecido: negar por padrão operação de custo
  financeiro não limitado, exceto sandbox autorizado com quota própria.
- Granularidade de circuit por provider vs rota vs credencial.
- Janela de contagem, limiar, tempo de cooldown, fencing/leases e limites
  per-tenant devem partir de configuração versionada e testes, nunca valores
  ocultos hardcoded.
- Persistência das reservas: tabela própria e migration aditiva, com regras
  de expiração e compensação revisadas no System Design da F3.

**Próximo passo:** aprovar tecnicamente esta candidata contra as ADRs
existentes, dividir em subtarefas incrementais (state machine/testes →
persistência/concurrency → runtime hook → audit/FinOps → gates) e implementar
sem ligar providers ou credenciais reais antecipadamente.
