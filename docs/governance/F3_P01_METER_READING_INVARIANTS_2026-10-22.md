# F3/P01 — MeterReading: proteção na fronteira do painel de consumo

O `CoreQuotaUsageHTTPReader` já rejeita JSON com versões/limites adulterados; o contrato `MeterReading` também pode receber objetos de leitores intercambiáveis. Este WP fecha esse segundo ponto de entrada exigindo inteiros exatos positivos para revisão, limite e duração de janela, bem como contadores exatos, não negativos, cuja soma fecha com a franquia. `bool`, `float`, tempo ingênuo e timestamps em formato inválido não podem virar saldo verificado.

A verificação ocorre na construção do snapshot, antes que `PlanConsumptionView` ou o dashboard possa classificar crédito como disponível. Não altera franquias, preço ou política de limiares, não cria custódia/cobrança e não usa dados reais. Testes adversariais parametrizados protegem a invariância também para leitores futuros.

Candidato para a branch `feat/saas-foundation-v1`; validar Test SaaS, PostgreSQL bridge e signed E2E no HEAD exato, revisar e, se verde, integrar como WP isolado. A PR monolítica #1 para main permanece Draft; Prompt 01/04 não é promovido por este WP. F13/homologações reais continuam posteriores à construção.
