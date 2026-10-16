"""Configuração da versão desktop (Windows, sem Docker).

Tudo que é da instalação — banco, chave secreta, logs, backups — fica numa
pasta de dados fora do programa (%LOCALAPPDATA%\\Adega no Windows), então
reinstalar ou atualizar o programa nunca mexe nos dados. A pasta pode ser
trocada pela variável ADEGA_DATA_DIR (útil em teste).

Ajustes da instalação ficam em <pasta de dados>/adega.env, criado no
primeiro uso. Pra liberar acesso pelo celular/tablet na rede local, trocar
ACESSO_REDE=False por ACESSO_REDE=True nesse arquivo e reiniciar o programa.
"""

import os
import socket
import sys
from pathlib import Path

import environ
from django.core.management.utils import get_random_secret_key

DATA_DIR = Path(
    os.environ.get("ADEGA_DATA_DIR")
    or Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Adega"
)
BACKUP_DIR = DATA_DIR / "backups"
for pasta in (DATA_DIR, BACKUP_DIR, DATA_DIR / "logs"):
    pasta.mkdir(parents=True, exist_ok=True)

ARQUIVO_CONFIG = DATA_DIR / "adega.env"
if not ARQUIVO_CONFIG.exists():
    ARQUIVO_CONFIG.write_text(
        "# Configuração desta instalação do Adega — não copie para outro computador.\n"
        f"SECRET_KEY={get_random_secret_key()}\n"
        "PORTA=8000\n"
        "# True libera o acesso por outros aparelhos da rede local (celular, tablet).\n"
        "ACESSO_REDE=False\n",
        encoding="utf-8",
    )
environ.Env.read_env(ARQUIVO_CONFIG, overwrite=True)

# base.py exige estas variáveis na importação; aqui elas são sobrescritas logo
# abaixo, mas precisam existir (e não podem vir de um .env de desenvolvimento).
os.environ["DATABASE_URL"] = "sqlite:///" + str(DATA_DIR / "adega.sqlite3")
os.environ["REDIS_URL"] = "locmem://"

from .base import *  # noqa: E402,F401,F403
from .base import BASE_DIR, LOGGING, MIDDLEWARE, env  # noqa: E402

DEBUG = False
SECURE_PROXY_SSL_HEADER = None  # sem proxy reverso na frente
PRIMEIRO_ACESSO_PELA_TELA = True

PORTA = env.int("PORTA", default=8000)
ACESSO_REDE = env.bool("ACESSO_REDE", default=False)


def _ips_da_maquina():
    ips = set()
    try:
        ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    try:
        # Não envia nada: só descobre qual IP o sistema usaria pra sair pra rede.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


IPS_REDE = _ips_da_maquina() if ACESSO_REDE else []
ALLOWED_HOSTS = ["localhost", "127.0.0.1", *IPS_REDE]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "adega.sqlite3",
        "OPTIONS": {
            # IMMEDIATE trava o banco já no início da transação: é o que faz o
            # select_for_update() de caixa/vendas continuar protegendo contra
            # duas vendas simultâneas (o SQLite ignora o FOR UPDATE).
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
            # cache_size/mmap: mais do banco fica em memória, menos leitura no
            # disco (notebook com HD lento); temp_store: ordenações em memória.
            "init_command": (
                "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; "
                "PRAGMA cache_size=-16000; PRAGMA temp_store=MEMORY; PRAGMA mmap_size=134217728;"
            ),
        },
        # Reaproveita a conexão entre os cliques em vez de abrir uma por página.
        "CONN_MAX_AGE": None,
        "CONN_HEALTH_CHECKS": True,
    }
}

# Sessão de login lida da memória (o banco fica de reserva): uma consulta a
# menos em cada clique.
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
if sys.argv[1:2] == ["test"]:
    # O cache em memória sobreviveria de um teste para outro (o banco não):
    # nos testes nada fica guardado. Os testes do cache ligam o LocMem por conta.
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

# Sem Nginx: o WhiteNoise serve os arquivos estáticos direto do Django.
MIDDLEWARE = [
    MIDDLEWARE[0],
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [p for p in [BASE_DIR / "static"] if p.exists()]
MEDIA_ROOT = DATA_DIR / "media"

# No programa instalado os arquivos estáticos ganham um código no nome
# (site.3f2a1b….css): o navegador guarda em cache para sempre, em vez de
# baixar tudo de novo a cada minuto. O build liga isso para o collectstatic
# gerar os nomes; em testes e no desenvolvimento fica desligado.
if getattr(sys, "frozen", False) or env.bool("ADEGA_ESTATICOS_VERSIONADOS", default=False):
    from django.conf import global_settings

    STORAGES = {
        **global_settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
    }

# desktop/versao.txt é gravado pelo build (desktop/build.ps1) e vai dentro do
# executável; rodando pelo código-fonte ele não existe e o atualizador fica
# desligado. CANAL_ATUALIZACAO=testes no adega.env também oferece as versões
# de teste (tags com hífen, ex.: v1.3.0-teste), para validar antes da adega.
ARQUIVO_VERSAO = BASE_DIR / "desktop" / "versao.txt"
VERSAO = ARQUIVO_VERSAO.read_text(encoding="utf-8").strip() if ARQUIVO_VERSAO.exists() else None
ATUALIZACAO_ATIVA = bool(VERSAO) and sys.platform == "win32"
ATUALIZACAO_CANAL = env("CANAL_ATUALIZACAO", default="estavel")
GAVETA_DISPONIVEL = True

LOG_DIR = DATA_DIR / "logs"
LOGGING["handlers"]["arquivo"]["filename"] = str(LOG_DIR / "app.log")
