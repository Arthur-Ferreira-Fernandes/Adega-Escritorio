# Adega Escritório

Sistema de gestão para adega/tabacaria: estoque, PDV (vendas rápidas e comandas), caixa, clientes/fornecedores, financeiro, relatórios, auditoria e usuários — tudo em português, pensado para uso local no computador do estabelecimento.

## Stack

- Django (templates server-side + HTMX)
- PostgreSQL
- Redis (cache; fila com Celery provisionada para uso futuro)
- Nginx (proxy reverso) + Gunicorn
- Docker Compose

## Como rodar (desenvolvimento)

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
```

Acesse `http://localhost/` e faça login — a navegação principal é pela barra lateral (Vendas, Estoque, Caixa, área Administrativa).

Pra popular o banco com dados fictícios de uma adega de porte médio (só para ambiente de teste — **nunca rode isso numa instalação real de cliente**):

```bash
docker compose exec web python manage.py seed_demo
```

## Versão desktop para Windows (instalador `.exe`, sem Docker)

Para computadores Windows 10/11 comuns, o sistema também é distribuído como um instalador (`AdegaSetup-<versão>.exe`) que não precisa de Docker, Python nem internet. Nessa versão, o SQLite substitui o Postgres, o cache em memória substitui o Redis e o Waitress + WhiteNoise substituem o Gunicorn + Nginx. O sistema abre numa janela própria, sem barra de endereço, pelo pywebview, que no Windows usa o WebView2 do Edge. O código é o mesmo, e a configuração fica em `config/settings/desktop.py`.

### Gerar o instalador

- **Pelo GitHub (recomendado):** crie e envie uma tag de versão (`git tag v1.0.0 && git push --tags`). O workflow `.github/workflows/instalador-windows.yml` roda os testes, gera o instalador e o anexa a uma Release. Também dá para disparar pela aba **Actions → Instalador Windows → Run workflow** e baixar o artefato.
- **Num Windows local** (Python 3.12 e Inno Setup 6 instalados): `powershell -ExecutionPolicy Bypass -File desktop\build.ps1 -Versao 1.0.0`. O resultado sai em `dist\`.

### Instalar na adega

1. Copie o `AdegaSetup-<versão>.exe` para o computador e execute. Não pede senha de administrador.
   - O instalador não é assinado digitalmente, então o Windows pode mostrar "O Windows protegeu o computador". Clique em **Mais informações → Executar assim mesmo**.
2. No primeiro uso, a janela do Adega abre na tela **Bem-vindo!**, onde se cria o usuário administrador. Essa tela só existe enquanto não há nenhum administrador e só funciona no próprio computador.

Fechar a janela **desliga o sistema**, inclusive para celulares conectados, por isso o Adega pede confirmação antes. Comprovantes e relatórios de caixa abrem numa segunda janela, com o botão de imprimir. Se o Windows não tiver o WebView2 (só em versões muito desatualizadas), o sistema abre no navegador e mostra um aviso cujo OK desliga o sistema. Erros ao abrir aparecem numa caixa de mensagem e ficam registrados em `logs\app.log`. No instalador, é possível marcar "Abrir o Adega automaticamente ao ligar o computador".

### Dados, backups e atualização

Tudo fica em `%LOCALAPPDATA%\Adega`. O menu Iniciar tem o atalho **Dados e backups do Adega**:

- `adega.sqlite3`: o banco de dados.
- `backups\`: cópia automática a cada abertura do sistema e a cada 24h com ele aberto. Guarda os últimos 30 dias. Copie essa pasta de vez em quando para um pendrive ou para a nuvem.
- `navegador\`: dados da janela do app, como o login salvo.
- `adega.env`: configuração desta instalação, incluindo a `SECRET_KEY`, que é gerada automaticamente.
- `logs\`: registros do sistema.

**Atualizar:** basta rodar o instalador da versão nova. Os dados não são tocados, e as migrations rodam sozinhas ao abrir o sistema (com backup feito logo antes).

**Restaurar um backup:** feche o Adega, apague `adega.sqlite3`, `adega.sqlite3-wal` e `adega.sqlite3-shm`, copie o backup desejado de `backups\` para o lugar e renomeie para `adega.sqlite3`.

### Acesso pelo celular/tablet (rede local)

1. Em `%LOCALAPPDATA%\Adega\adega.env`, troque `ACESSO_REDE=False` por `ACESSO_REDE=True` e reabra o Adega.
2. Na primeira vez, o Windows pergunta se libera o acesso na rede. Marque **Redes privadas** e permita. Isso exige a senha de administrador do Windows.
3. O título da janela do Adega mostra o endereço para usar no celular (ex.: `http://192.168.0.10:8000/`). O celular precisa estar no mesmo Wi-Fi.

Para o endereço não mudar, reserve um IP fixo para o computador no roteador. O acesso é só por HTTP, sem criptografia, então use apenas numa rede Wi-Fi de confiança (não na rede aberta para clientes).

## Instalar no computador do cliente (Docker)

### 1. Pré-requisitos

Instalar o [Docker Desktop](https://www.docker.com/products/docker-desktop/) na máquina onde o sistema vai rodar.

- **Windows**: habilitar o WSL2 antes (PowerShell como administrador: `wsl --install`, reiniciar o computador), depois instalar o Docker Desktop normalmente.
- **Mac**: instalação direta, sem passo extra.

Depois de instalado, em **Settings → General**, habilitar "Start Docker Desktop when you sign in" — os serviços já têm `restart: unless-stopped`, mas isso só funciona com o Docker Desktop rodando.

### 2. Levar o código até lá

```bash
git clone https://github.com/Arthur-Ferreira-Fernandes/Adega-Escritorio.git
cd Adega-Escritorio
```

(Alternativa sem git: copiar a pasta do projeto inteira, sem `.env` nem nada gerado pelo Docker — bancos e arquivos estáticos ficam em volumes do Docker, fora da pasta.)

### 3. Configurar o ambiente — não reaproveite o `.env` de outra instalação

```bash
cp .env.example .env
```

Ajuste **pelo menos** estes dois valores no `.env` antes de subir:

- `SECRET_KEY`: gere um valor novo e único para esta instalação:
  ```bash
  docker compose run --rm web python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
  ```
- `POSTGRES_PASSWORD`: troque o valor padrão por uma senha de verdade.

O resto (`DEBUG=False`, `DJANGO_SETTINGS_MODULE=config.settings.prod`, as flags de HTTPS desligadas) já vem correto do `.env.example` — só ligue as flags de HTTPS (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`) se um dia houver certificado TLS de verdade na frente do Nginx; sem isso, ligá-las quebra o login.

Se o sistema for acessado de outro dispositivo na rede local (tablet, outro computador), além de `localhost,127.0.0.1` adicione o IP da máquina em `ALLOWED_HOSTS`.

### 4. Subir e criar o primeiro acesso

```bash
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

Acesse `http://localhost/` no navegador do computador do cliente. O banco nasce vazio — o cliente cadastra categoria/produto/cliente/fornecedor reais pela própria tela.

## Backup do banco

O serviço `backup` (`docker-compose.yml`) roda automaticamente, sem precisar de nenhum comando manual:

- Um backup assim que os containers sobem (`docker compose up`), e depois todo dia às 3h da manhã.
- Os arquivos ficam em `./backups/` na raiz do projeto — uma pasta real no computador, fora dos volumes do Docker, então sobrevivem mesmo a um `docker compose down -v`.
- Mantém os últimos 30 dias; backups mais antigos são apagados automaticamente.
- Pra mais segurança, copie a pasta `backups/` de vez em quando pra um lugar fora dessa máquina (nuvem, HD externo) — o backup automático protege contra problema de disco/volume, não contra a máquina inteira sendo perdida ou roubada.

**Backup manual, a qualquer momento:**

```bash
docker compose exec backup /backup.sh
```

**Restaurar um backup** (cuidado: sobrescreve os dados atuais do banco):

```bash
gunzip -c backups/adega_2026-08-10_03-00-00.sql.gz | docker compose exec -T db psql -U adega -d adega
```

## Testes automatizados

```bash
docker compose exec web python manage.py test
```

## Estrutura

- `config/` — configuração do projeto Django (settings, urls, wsgi/asgi, celery, logging)
- `apps/estoque` — categorias, produtos e entrada de estoque
- `apps/clientes` — clientes e fornecedores
- `apps/vendas` — vendas rápidas, comandas e histórico
- `apps/caixa` — abertura, sangria, reforço, fechamento e relatório de caixa
- `apps/financeiro` — contas a pagar e a receber
- `apps/relatorios` — dashboard de faturamento, lucro/margem e estoque baixo
- `apps/notificacoes` — sino de alertas (estoque baixo, limite de caixa, sugestão de sangria)
- `apps/usuarios` — contas de usuário, "Minha conta"
- `apps/configuracoes` — dados do administrador e parâmetros do caixa
- `apps/auditoria` — registro de alterações sensíveis feitas por usuários
- `docker/` — Dockerfile da aplicação, configuração do Nginx e do backup automático do banco
- `desktop/` — versão Windows: lançador (`iniciar.py`), empacotamento PyInstaller (`adega.spec`), instalador Inno Setup (`instalador.iss`) e script de build
