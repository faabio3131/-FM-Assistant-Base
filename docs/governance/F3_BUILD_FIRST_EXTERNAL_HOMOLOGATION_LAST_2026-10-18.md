# Decisão executiva — concluir a construção antes da homologação externa

**Data:** 18/10/2026  
**Autoridade:** determinação explícita do proprietário do produto.  
**Aplica-se a:** FM Assistant Base, FM Core Base e FM Command, inclusive às próximas fases do Cronograma Mestre.

## Separação obrigatória de duas trilhas

**Trilha A — construção 100% do software (AGORA):** codificar todos os requisitos aprovados; finalizar módulos e integrações; criar contratos e adapters de terceiros com mocks/fakes e fixtures realistas; migrations aditivas exercitadas em bancos descartáveis; testes unitários, integração, concorrência PostgreSQL 16, adversariais, E2E simulado, segurança, lint/typecheck/build/CI; corrigir regressões; atualizar AGENTS.md, tracker e documentação. Prosseguir autonomamente pelas tarefas internas do Cronograma Mestre sem depender de contas externas, credenciais, DNS, provedores vivos ou homologação de produção.

**Trilha B — configuração e provas reais (DEPOIS do Build 100%):** fornecimento/rotação de segredos verdadeiros; provedores de IA, Vault, redes, TLS/ACL, gateways e outros serviços externos; integração contra ambientes reais; deployment/staging/produção quando dependentes de serviços externos; homologações junto a terceiros; revisão final independente externa, testes end-to-end reais e cutover. **Não bloquear o desenvolvimento de F3, F4 e fases subsequentes pela Trilha B.**

## Classificação de progresso sem falsos verdes

- `BUILD_IN_PROGRESS`: implementação interna ainda incompleta.
- `BUILD_COMPLETE_INTERNAL_GREEN`: código completo quanto ao escopo aprovado e **todos os gates executáveis internamente** verdes; mocks/fixtures não equivalem a homologação de terceiro.
- `EXTERNAL_HOMOLOGATION_DEFERRED`: itens da Trilha B documentados, **não testados**, aguardam fase final; esta marcação não impede programação nem certificação de conclusão interna.
- `REAL_HOMOLOGATION_APPROVED`: concedido somente quando provas reais forem executadas, auditadas e aprovadas.

Cada tarefa deve registrar evidência, HEAD/PR, testes, estado de implementação e classificação por trilha. Não elevar provas sintéticas a provas reais.

## Sequenciamento e autonomia

1. Atacar primeiro toda pendência de software, construir interfaces e contratos isolados para dependências externas e provar internamente seus comportamentos.
2. Se encontrar credencial, conexão, assinatura externa ou permissão de conta indisponível, criar fixture/driver adaptável e registrar `EXTERNAL_HOMOLOGATION_DEFERRED`; **seguir para a próxima tarefa de software**. Nunca criar chave falsa em produção.
3. Uma fase pode avançar para a próxima **quando seu escopo de construção e CI interno estiverem completos**, mesmo que a homologação externa tenha sido deferida. O status de operação real continua pendente.
4. Merges em branches de desenvolvimento podem usar autorização prévia apenas após gates internos, checagens de segurança, compatibilidade, migrations e consequências de CI/CD conferidos; **nenhum merge que cause deploy/cutover ou mutação de produção é autorizado implicitamente**.
5. Não alterar autoridade constitucional/segurança, não contornar RBAC/tenant, não enfraquecer testes e não marcar `PRODUCTION_APPROVED` sem prova. Deploy produtivo, segredos reais, migrations não descartáveis e gastos precisam de autorização humana específica.
6. Evitar paradas por relatos intermediários. Executor trabalha em lotes substanciais, corrige falhas internamente e apresenta conclusões verificadas.

**Precedência:** esta decisão mais recente substitui exclusivamente as interpretações de checkpoints antigos que bloqueavam *construção ou avanço da programação* pela ausência de homologação externa. As regras de segurança, auditoria, limites de autoridade e autorização para produção permanecem obrigatórias.
