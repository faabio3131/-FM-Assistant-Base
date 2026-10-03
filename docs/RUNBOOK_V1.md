# FM Assistant Base — Runbook V1

## Desenvolvimento local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn fm_assistant.main:app --reload
```

A API ficará disponível em `http://127.0.0.1:8000`.

## Fluxo mínimo de provisionamento

1. Defina `FM_ASSISTANT_ADMIN_KEY` e `FM_ASSISTANT_CREDENTIAL_PEPPER`.
2. Provisione um tenant via `POST /v1/admin/credentials` usando `X-Admin-Key`.
3. Guarde a `api_key` retornada; ela não é persistida em texto puro.
4. Use `Authorization: Bearer <api_key>` nas operações do tenant.
5. Configure a persona em `PUT /v1/persona`.
6. Adicione conhecimento em `POST /v1/knowledge`.
7. Crie uma conversa e envie mensagens.

## Produção

Antes de subir staging/production:

- PostgreSQL obrigatório.
- `FM_ASSISTANT_AUTO_CREATE_SCHEMA=0`.
- Execute `alembic upgrade head` como etapa controlada de release.
- Use chaves fortes e exclusivas.
- `FM_ASSISTANT_MODEL_BACKEND=development` é recusado em produção.
- Configure um gateway de modelo real.
- Não coloque tokens/segredos em logs ou no repositório.

## Health check

`GET /health`

## Rollback

O primeiro release deve ser promovido apenas depois dos testes da branch e da migration
em ambiente descartável. Em caso de rollback de aplicação, mantenha o schema compatível;
não execute `alembic downgrade` em produção sem plano explícito de dados.
