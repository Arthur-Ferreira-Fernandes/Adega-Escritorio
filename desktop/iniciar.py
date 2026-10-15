"""Ponto de entrada da versão desktop (vira o Adega.exe).

Prepara o banco, faz backup, garante que existe um administrador, sobe o
servidor e abre o navegador. A janela preta que fica aberta É o sistema:
fechá-la desliga o Adega.
"""

import os
import socket
import sqlite3
import sys
import threading
import time
import webbrowser
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(RAIZ))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.desktop"

DIAS_DE_BACKUP = 30
INTERVALO_BACKUP = 24 * 60 * 60


def porta_em_uso(porta):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def fazer_backup(settings):
    origem = Path(settings.DATABASES["default"]["NAME"])
    if not origem.exists():
        return
    destino = settings.BACKUP_DIR / f"adega_{datetime.now():%Y-%m-%d_%H-%M-%S}.sqlite3"
    # A API de backup do SQLite gera uma cópia consistente mesmo com o
    # sistema em uso — copiar o arquivo direto poderia pegar uma venda pela metade.
    with closing(sqlite3.connect(origem)) as banco, closing(sqlite3.connect(destino)) as copia:
        banco.backup(copia)
    limite = time.time() - timedelta(days=DIAS_DE_BACKUP).total_seconds()
    for antigo in settings.BACKUP_DIR.glob("adega_*.sqlite3"):
        if antigo.stat().st_mtime < limite:
            antigo.unlink()
    print(f"Backup criado: {destino}")


def backup_periodico(settings):
    while True:
        time.sleep(INTERVALO_BACKUP)
        try:
            fazer_backup(settings)
        except Exception as erro:  # um backup que falha não pode derrubar o sistema
            print(f"Falha no backup automático: {erro}")


def garantir_administrador():
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    if get_user_model().objects.filter(is_superuser=True).exists():
        return
    print()
    print("=" * 60)
    print(" PRIMEIRO USO: crie o usuário administrador do sistema.")
    print(" (a senha não aparece enquanto você digita — é normal)")
    print("=" * 60)
    call_command("createsuperuser")


def main():
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.kernel32.SetConsoleTitleW("Adega — NÃO FECHE esta janela")

    import django

    django.setup()
    from django.conf import settings
    from django.core.management import call_command

    url = f"http://localhost:{settings.PORTA}/"
    if porta_em_uso(settings.PORTA):
        # Já tem um Adega rodando (clicaram duas vezes no ícone): só abre o navegador.
        webbrowser.open(url)
        return

    print("Iniciando o Adega...")
    fazer_backup(settings)
    call_command("migrate", interactive=False, verbosity=0)
    if not getattr(sys, "frozen", False):
        call_command("collectstatic", interactive=False, verbosity=0)
    garantir_administrador()

    from waitress import serve
    from django.core.wsgi import get_wsgi_application

    threading.Thread(target=backup_periodico, args=(settings,), daemon=True).start()
    threading.Timer(1.5, webbrowser.open, args=(url,)).start()

    host = "0.0.0.0" if settings.ACESSO_REDE else "127.0.0.1"
    print()
    print(f"Adega rodando em {url}")
    for ip in settings.IPS_REDE:
        print(f"Na rede local (celular/tablet): http://{ip}:{settings.PORTA}/")
    print(f"Dados e backups em: {settings.DATA_DIR}")
    print("Mantenha esta janela aberta (pode minimizar). Fechar = desligar o sistema.")
    serve(get_wsgi_application(), host=host, port=settings.PORTA, threads=8)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        input("\nO Adega encontrou um erro e vai fechar. Tire uma foto desta tela e pressione Enter.")
        sys.exit(1)
