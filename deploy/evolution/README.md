# VendeAtendeIA — preparação da VPS / Evolution v2.3.7

**Status: BUILD-ONLY REFERENCE / NOT DEPLOYED / EXTERNAL_HOMOLOGATION_DEFERRED.**
Este diretório é um modelo de configuração, não uma ordem para subir produção.
F3 ainda está em construção. Não copiar a sugestão genérica `atendavende/evolution-api:latest`.

## Compatibilidade canônica

- Imagem upstream de referência: `evoapicloud/evolution-api:v2.3.7`.
- Assistant: `FM_ASSISTANT_EVOLUTION_ORIGIN` exige **HTTPS, porta 443**, com URL sem caminho; `FM_ASSISTANT_EVOLUTION_GLOBAL_KEY` corresponde ao segredo dedicado `EVOLUTION_MASTER_API_KEY`, **somente no gerenciador de segredos**, jamais enviado ao navegador.
- `FM_ASSISTANT_EVOLUTION_NATIVE_WEBHOOK_BASE_URL` exige `https://<host>/webhooks/evolution-native`; cada instância recebe **token exclusivo de callback**, armazenado cifrado e enviado no header `X-FM-Evolution-Token` pela configuração FM do webhook. Não configurar webhook global exposto sem autenticação.
- Banco Redis e PostgreSQL são privados à rede Compose; nada de `5432:5432` ou `6379:6379`; Evolution fica somente em `127.0.0.1:8080`, atrás de proxy HTTPS e ACL que permita o **Assistant** acessar os endpoints necessários.
- O canal Meta oficial permanece alternativa separada. Evolution/Baileys não garante ausência de restrições WhatsApp. Política de QR no painel: **45s padrão de exibição**, não TTL garantido do provedor.
- `evolution_instances`, `postgres_data` e `redis_data` são persistentes. Ainda exigem política de backups, restore testado, TLS, firewall, IP allowlist, logs sem `apikey`, supervisão, DNS e hardening operacional.
- O segredo PostgreSQL interpolado na URI deve ser **URL-safe**; não inserir senhas literais em arquivos versionados. Na VPS aplicar permissões estritas `chmod 600 .env`. Os envs ainda são inspecionáveis por administradores Docker; usar serviço de segredos/isolamento do host conforme política da FM.

## Pré-checagem **sem subir containers**

1. Separar VPS/ambiente, subdomínio HTTPS e reverse proxy, mas deixar credenciais reais e conexão de WhatsApp para homologação final.
2. Copiar o arquivo de exemplo para um `.env` **fora do Git** e preencher os placeholders apenas no ambiente autorizado. Nunca compartilhar o arquivo preenchido em chat, PR ou logs.
3. Executar `docker compose --env-file .env -f docker-compose.yml config --quiet` **somente** quando houver configuração autorizada; isso valida YAML e expansão, não garante integração, disponibilidade ou segurança do host.
4. Executar `python -m pytest tests/saas/test_evolution_deployment_template.py` na raiz do repositório como inspeção estática; este teste não inicia containers.
5. **Não executar `docker compose up`** nesta etapa. Na homologação final, confirmar a versão/digest real do servidor, os contratos e `POST /instance/create`, `GET /instance/connect/{instance}`, `POST /webhook/set/{instance}`, `GET /instance/connectionState/{instance}`, webhook autenticado, mensagens, logout, reconexão, concorrência, backup/restore e risco operacional.

## Guardrails de publicação

- O único caminho de entrada para a API Evolution será o proxy TLS (443) com bloqueio de acesso público administrativo indevido; não publicar a porta 8080 na interface pública.
- Nunca expor tokens de instância, chave global ou credenciais PostgreSQL na UI, logs, URL, CORS aberto, callback ou repositório.
- Antes de qualquer deploy real: congelar digest de imagem, revisar variáveis contra o container **efetivamente escolhido**, observar consumo de CPU/RAM/disco, definir limites e autorização humana de publicação.
- Este Compose é somente para **Evolution e sua infraestrutura**. O FM Assistant/FastAPI, FM Core e Command mantêm deployments e bancos próprios, sem fusão de bancos ou mudança de fonte de verdade.

### Fontes para comparação futura
- [Upstream compose](https://github.com/evolution-foundation/evolution-api/blob/main/docker-compose.yaml)
- [Upstream Swarm v2.3.7](https://github.com/evolution-foundation/evolution-api/blob/main/Docker/swarm/evolution_api_v2.yaml)
- [Contrato local](../../docs/integrations/EVOLUTION_V2_3_7_RELEASE_CONTRACT.md)
