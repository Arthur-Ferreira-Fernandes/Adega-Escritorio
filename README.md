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

## Backup do banco

O serviço `backup` (`docker-compose.yml`) roda automaticamente, sem precisar de nenhum comando manual:

- Um backup assim que os containers sobem (`docker compose up`), e depois todo dia às 3h da manhã.
- Os arquivos ficam em `./backups/` na raiz do projeto — uma pasta real no computador, fora dos volumes do Docker, então sobrevivem mesmo a um `docker compose down -v`.
- Mantém os últimos 30 dias; backups mais antigos são apagados automaticamente.
- Pra mais segurança, copie a pasta `backups/` de vez em quando pra um lugar fora dessa máquina (iCloud, Dropbox, HD externo) — o backup automático protege contra problema de disco/volume, não contra a máquina inteira sendo perdida.

**Backup manual, a qualquer momento:**

```bash
docker compose exec backup /backup.sh
```

**Restaurar um backup** (cuidado: sobrescreve os dados atuais do banco):

```bash
gunzip -c backups/adega_2026-08-10_03-00-00.sql.gz | docker compose exec -T db psql -U adega -d adega
```

## Estrutura

- `config/` — configuração do projeto Django (settings, urls, wsgi/asgi, celery)
- `apps/estoque` — categorias e produtos
- `apps/clientes` — clientes e fornecedores
- `apps/vendas` — vendas e itens de venda
- `apps/financeiro` — contas a pagar e a receber
- `docker/` — Dockerfile da aplicação, configuração do Nginx e do backup automático do banco
