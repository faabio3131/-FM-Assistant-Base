# ADR-001 — Produto V1: Atendente + Vendedor IA

**Data:** 2026-10-17  
**Status:** APPROVED

## Contexto

A fundação atual já atende conversação, conhecimento, WhatsApp, áudio, handoff e Core. Era necessário definir se a V1 seria apenas atendente, vendedor ou plataforma ampla de agentes.

## Decisão

A V1 será **Atendente + Vendedor IA**.

Deve atender dúvidas e executar jornada comercial governada:

- identificar lead;
- qualificar;
- registrar oportunidade;
- operar pipeline;
- responder objeções;
- agendar;
- realizar follow-up;
- gerar proposta/CTA;
- registrar conversão;
- escalar para humano.

A arquitetura deve permitir futura evolução para plataforma de agentes sem exigir reconstrução.

## Consequências

- CRM/Sales Pack entra no escopo da V1.
- Billing, painel e human inbox deixam de ser opcionais para disponibilidade comercial.
- Não serão criados agentes independentes com domínios paralelos nesta fase.
