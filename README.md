# Adega Escritório

Sistema de gestão para adega/escritório: estoque, vendas, clientes/fornecedores e financeiro.

## Stack

- Django (templates server-side)
- PostgreSQL
- Redis (cache; fila com Celery provisionada para uso futuro)
- Nginx (proxy reverso) + Gunicorn
- Docker Compose

## Como rodar

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
```

Acesse:

- http://localhost/admin/ — administração (CRUD dos 4 domínios)
- http://localhost/estoque/
- http://localhost/vendas/
- http://localhost/clientes/
- http://localhost/financeiro/

## Estrutura

- `config/` — configuração do projeto Django (settings, urls, wsgi/asgi, celery)
- `apps/estoque` — categorias e produtos
- `apps/clientes` — clientes e fornecedores
- `apps/vendas` — vendas e itens de venda
- `apps/financeiro` — contas a pagar e a receber
- `docker/` — Dockerfile da aplicação e configuração do Nginx
