# F3 — Fonte das evidências de uso de IA e FinOps (revisão interna 20/10/2026)

Estado: **BUILD_IN_PROGRESS / NOT_PRODUCTION_HOMOLOGATED**. Este documento separa transporte HTTP autenticado, telemetria relatada pelo provider, evidência independente assinada, assinatura interna FM e custo estimado. Uma assinatura HMAC do gateway FM **não comprova** que a origem original foi assinada por OpenAI, Gemini ou qualquer outro fornecedor.

| Caminho técnico já presente | Métricas observadas | Prova de origem | Estado de construção |
|---|---|---|---|
| OpenAI-compatible `/chat/completions` | `usage.prompt_tokens`, `completion_tokens`, cache quando informado | Resposta HTTP via conexão TLS; não equivale a comprovante financeiro assinado pelo provider | Adaptador implementado, contagem inteira estrita; verificação independente de faturamento ainda pendente |
| OpenAI-compatible `/audio/transcriptions` | `usage.input_tokens`, `output_tokens` quando retornados | Idem; modalidades em que não há tokens ficam desconhecidas | Controle de limite de upload e tentativa, fail-closed em quota, metering parcial ainda não contabiliza tempo/duração verificável |
| Google Gemini `generateContent` texto/áudio | `usageMetadata.promptTokenCount`, `candidatesTokenCount`, `cachedContentTokenCount` quando informado | Resposta HTTP via conexão TLS, sem assinatura nativa atestada por este código | Adaptador implementado e parse estrito; autenticação de fatura/usage export ainda não homologada |
| Provider que emite declaração Ed25519 conforme contrato FM | Campos `input_tokens`, `output_tokens`, `cost_usd`, `no_charge`, `observed_at` | `verified_signed_usage_source` exige chave pública previamente ancorada e assinatura verificável | Verificador e armazenamento imutável internos implementados; nenhum provedor real certificado como emissor dessa declaração |
| Gateway interno FM HMAC | Envelope verificado contra recibo estruturado | Prova apenas do gateway FM e de escopo, não da fatura do provedor | `TrustedProviderEvidenceStore` e `GovernedRecoveryCommand` existentes; nunca usar para fabricar fato externo |

## Invariantes de operação
- Cada tentativa efetiva de roteamento, inclusive fallback, precisa ser medida ou marcada como de custo/uso desconhecido, com dados de proveniência. Não somar custos desconhecidos como zero.
- Tokens em cache integram tokens de entrada. Se a métrica independente de cache NÃO estiver no plano, entrada/saída conhecidas podem liquidar suas quotas mesmo sem breakdown de cache; se estiver, a falta de breakdown retém a reserva.
- Nenhuma resposta de erro HTTP, timeout ou ausência de token count comprova `no_charge`. Sem prova independente e com gasto incerto, manter reserva e `needs_attention`.
- Novo endpoint somente leitura `GET /v1/admin/ai/usage/request` requer `X-Core-Admin-Key` separado da chave consumidora, escopo exato tenant/unit/request, e informa `unknown_attempts`, `known_cost_subtotal`, `all_costs_known` e motivos de alerta. Não faz reconciliação contábil nem envia alertas.
- O limite de alerta por requisição é opcional e informado por operador; **não representa preço comercial nem cota do plano**. Interface persistida para configurar limiares pela FM e notificações automáticas permanece como construção futura.
- Pré-requisitos internos para certificação F3 integral: adaptadores de verificação de origem reais específicos dos provedores escolhidos, reconciliador de tentativas com fonte de faturamento confiável, rollups de custos por cliente/produto/modelo, política de limiares/alertas administrada pela FM, revisão independente de segurança, contrato Command e ensaios adversariais de concorrência e recuperação. Credenciais e homologação externas vêm **após** conclusão de construção, não substituem os adaptadores de software.
