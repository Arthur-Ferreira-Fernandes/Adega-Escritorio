"""Exporta os dados da versão web (Docker + Postgres) para a versão desktop.

Gera um adega.sqlite3 com a MESMA estrutura e o mesmo histórico de migrations
da versão que está rodando. Ao abrir esse arquivo, a versão desktop faz backup
e atualiza o banco sozinha, como em qualquer atualização. Os números das
vendas, os usuários e as senhas são preservados. O Postgres só é lido: nada
nele é alterado.

Uso, na pasta do projeto do computador que roda o Docker (o docker-compose
monta essa pasta dentro do container em /app):

    docker compose exec web python exportar_para_desktop.py

O arquivo sai como adega-exportado.sqlite3 na mesma pasta. Depois, no
computador com a versão desktop: feche o Adega, coloque o arquivo em
%LOCALAPPDATA%\\Adega com o nome adega.sqlite3 (veja o README) e abra.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

DESTINO = PASTA / "adega-exportado.sqlite3"
# Gerados de novo pelo migrate no arquivo novo, ou descartáveis (sessões de login).
FORA_DA_COPIA = ["contenttypes", "auth.permission", "sessions", "admin.logentry"]


def main():
    from django.conf import settings

    settings.DATABASES["destino"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": str(DESTINO)}

    import django

    django.setup()

    from django.apps import apps
    from django.core.management import call_command
    from django.db import connections
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connections["default"])
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        sys.exit(
            "O banco atual tem migrations pendentes. Reinicie o sistema "
            "(docker compose restart web) e rode este script de novo."
        )

    print("1/3 Criando o banco novo com a estrutura desta versão...")
    if DESTINO.exists():
        DESTINO.unlink()
    # Em outro processo, com o arquivo novo como banco principal: as migrations
    # de dados (RunPython) sempre usam o banco principal, e aqui o principal é
    # o Postgres, que não pode ser tocado.
    subprocess.run(
        [sys.executable, "manage.py", "migrate", "--noinput", "-v", "0"],
        cwd=PASTA,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{DESTINO}"},
        check=True,
    )

    print("2/3 Copiando os dados...")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as arquivo:
        caminho_json = arquivo.name
    try:
        call_command(
            "dumpdata",
            database="default",
            natural_foreign=True,
            exclude=FORA_DA_COPIA,
            indent=None,
            output=caminho_json,
            verbosity=0,
        )
        call_command("loaddata", caminho_json, database="destino", verbosity=0)
    finally:
        os.unlink(caminho_json)

    print("3/3 Conferindo...")
    problemas = []
    total = 0
    for modelo in apps.get_models():
        rotulo = modelo._meta.label_lower
        if any(rotulo == item or rotulo.startswith(item + ".") for item in FORA_DA_COPIA):
            continue
        origem = modelo._default_manager.using("default").count()
        copiado = modelo._default_manager.using("destino").count()
        total += copiado
        if origem != copiado:
            problemas.append(f"  {rotulo}: {origem} no sistema, {copiado} no arquivo")
    connections["destino"].close()

    if problemas:
        DESTINO.unlink()
        sys.exit("A cópia não bateu e o arquivo foi descartado:\n" + "\n".join(problemas))

    print(f"Pronto: {total} registros exportados para {DESTINO.name} ({DESTINO.stat().st_size // 1024} KB).")


if __name__ == "__main__":
    main()
