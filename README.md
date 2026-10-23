# VendeAtendeIA — um único SaaS (Core + Assistant)

**Um só produto para o cliente.** O Assistant é a aplicação comercial; o Core em `services/fm-core` é seu motor interno de IA. O FM Command é um control center corporativo externo e não integra este repositório.

**Execução local unificada:** instale `pip install -e ".[dev]"` e `pip install -e ./services/fm-core`, configure o `.env` a partir de `.env.example` com chave interna forte e rotas ou banco do Core e execute `python scripts/vendeatendeia_dev.py`. O launcher inicia o Core somente em `127.0.0.1` e o Assistant como aplicação de entrada. Não é procedimento de produção.

Fundação universal de atendimento e agentes conversacionais da FM Tecnologia.

## Proveniência
- Origem: `faabio3131/fm-ai-platform`
- Branch auditada: `main`
- SHA de origem: `5a17b0c8a1cb6dad576ce5b089166748b138900c`
- Extração: 2026-10-03
- Estratégia: cópia isolada primeiro; desacoplamento do domínio restaurante depois.

## Objetivo
Preservar como base reutilizável: conversation state, identidade/persona configurável, contexto de cliente, texto/áudio, runtime de canais, WhatsApp/Meta, handoff humano, idempotência, auditoria e integração governada com IA.

## Regra arquitetural
O VendeAtendeIA é **um único produto comercial**: Assistant (atendimento e vendas) + Core (motor interno de IA). Ambos são versionados neste repositório; o Core reside em `services/fm-core`. O FM Command permanece um control center corporativo externo, conectado apenas por contratos de integração.

Regras de restaurante como pedido, cardápio, delivery, pagamento, estoque e KDS não pertencem ao núcleo universal; serão convertidas em adapters/capabilities de domínio durante o desacoplamento.


## Governança Nova FM

Este produto é subordinado à Fundação Nova FM Tecnologia.

Documentação canônica de execução:

1. `docs/governance/AUDITORIA_CONFORMIDADE_FUNDACAO_NOVA_FM_2026-10-17.md`
2. `docs/governance/SYSTEM_DESIGN_MASTER_V1.md`
3. `docs/governance/ADR-001` a `ADR-006`
4. `docs/governance/PROMPT_MESTRE_EXECUCAO_INTEGRAL_V1.md`

Decisões vigentes:

- V1 = Atendente + Vendedor IA;
- FM Core obrigatório em staging/produção;
- Integration & Credential Control Plane universal;
- BYOK suportado;
- `src/fm_assistant` é a linha comercial canônica;
- frontend Web será a linha comercial definitiva.

Regra obrigatória: configuração específica de cliente, unidade, chave, token,
credencial, provider ou integração deve ser data-driven e não pode exigir alteração
de código ou deploy.

### Estado de prontidão

- IMPLEMENTADO: parcial/fundação
- INTEGRADO: parcial/fundação
- TESTADO: parcial/fundação
- HOMOLOGADO: não
- PRONTO PARA PRODUÇÃO: não
- COMERCIALMENTE DISPONÍVEL: não
