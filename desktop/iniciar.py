"""Ponto de entrada da versão desktop (vira o Adega.exe).

Prepara o banco, faz backup, sobe o servidor e abre o sistema numa janela
própria (pywebview — no Windows usa o WebView2, o motor do Edge). Fechar a
janela desliga o sistema, inclusive para celulares conectados pela rede.
"""

import logging
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

# O .exe roda sem console: sem isso, qualquer print/log no terminal quebra.
for nome in ("stdout", "stderr"):
    if getattr(sys, nome) is None:
        setattr(sys, nome, open(os.devnull, "w", encoding="utf-8"))

NOME_APP = "Adega Escritório"
# Identifica o app pro sistema (barra de tarefas): no Windows é o
# AppUserModelID — igual ao dos atalhos em instalador.iss; no Linux é o
# app_id do Wayland, que tem que bater com o nome do arquivo .desktop.
ID_APP_WINDOWS = "ArthurFerreira.AdegaEscritorio"
ID_APP_LINUX = "adega-escritorio"

DIAS_DE_BACKUP = 30
INTERVALO_BACKUP = 24 * 60 * 60

log = logging.getLogger("apps.desktop")

# Os links com target="_blank" (comprovante de venda, relatório de caixa) iriam
# para o navegador externo, que não tem o login: abre numa janela do app.
# No Linux (Qt) abre na mesma janela: o pywebview cria um QWebEngineProfile
# novo, na mesma pasta, para cada janela, e o Chromium entra em loop
# consumindo memória até travar o computador. As páginas têm "Voltar".
if sys.platform.startswith("linux"):
    JS_ABRIR_LINK = "location.href = link.href;"
else:
    JS_ABRIR_LINK = "window.pywebview.api.abrir_janela(link.href);"
JS_JANELAS_NOVAS = """
document.addEventListener("click", function (evento) {
    var link = evento.target.closest("a[target=_blank]");
    if (!link || !window.pywebview) return;
    evento.preventDefault();
    %s
}, true);
""" % JS_ABRIR_LINK


def avisar(texto):
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, texto, NOME_APP, 0x40)
    else:
        print(texto)
        # Aberto pelo menu de aplicativos não há terminal: mostra como notificação.
        try:
            import subprocess

            subprocess.run(["notify-send", "--app-name", NOME_APP, NOME_APP, texto], timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass


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
    log.info("Backup criado", extra={"arquivo": str(destino)})


def backup_periodico(settings):
    while True:
        time.sleep(INTERVALO_BACKUP)
        try:
            fazer_backup(settings)
        except Exception:  # um backup que falha não pode derrubar o sistema
            log.exception("Falha no backup automático")


def ativar_impressao(window):
    """No Linux (Qt) o window.print() não faz nada sozinho: abre o diálogo de impressão."""
    from qtpy.QtPrintSupport import QPrintDialog, QPrinter

    navegador = window.native

    def imprimir():
        impressora = QPrinter(QPrinter.PrinterMode.HighResolution)
        # O Qt rasteriza cada página na resolução da impressora: na máxima,
        # são centenas de MB por página. 300 dpi basta para um comprovante.
        impressora.setResolution(300)
        if QPrintDialog(impressora, navegador).exec() != QPrintDialog.DialogCode.Accepted:
            return
        navegador._impressora = impressora  # a impressão é assíncrona
        navegador.webview.print(impressora)

    navegador.webview.printRequested.connect(imprimir)


def ativar_downloads(window):
    """No Linux (Qt) salva as planilhas exportadas com o nome que o sistema sugere.

    O tratamento do pywebview usaria o caminho da URL como nome, sem extensão.
    """
    from qtpy.QtCore import QStandardPaths
    from qtpy.QtWidgets import QFileDialog

    navegador = window.native

    def baixar(download):
        pasta = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        caminho, _ = QFileDialog.getSaveFileName(
            navegador, "Salvar arquivo", os.path.join(pasta, download.downloadFileName())
        )
        if not caminho:
            download.cancel()
            return
        download.setDownloadDirectory(os.path.dirname(caminho))
        download.setDownloadFileName(os.path.basename(caminho))
        download.accept()

    navegador.webview.page().profile().downloadRequested.connect(baixar)


def criar_janela(*args, **kwargs):
    import webview

    janela = webview.create_window(*args, **kwargs)
    if sys.platform.startswith("linux"):
        janela.events.before_show += ativar_impressao
        janela.events.before_show += ativar_downloads
    return janela


class Api:
    """Funções que o JavaScript das páginas pode chamar (window.pywebview.api)."""

    def abrir_janela(self, url):
        criar_janela(NOME_APP, url, width=900, height=800)


def instalar_atalho_linux(icone):
    """Cria o .desktop que dá nome e ícone ao app na barra do GNOME/KDE.

    No Wayland a janela não carrega ícone próprio: o sistema procura o
    .desktop com o mesmo app_id e, sem ele, mostra uma engrenagem e "python3".
    """
    if getattr(sys, "frozen", False):
        comando = f'"{sys.executable}"'
    else:
        comando = f'"{sys.executable}" "{Path(__file__).resolve()}"'
    if os.environ.get("ADEGA_DATA_DIR"):
        comando = f'env ADEGA_DATA_DIR="{os.environ["ADEGA_DATA_DIR"]}" {comando}'
    conteudo = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={NOME_APP}\n"
        "Comment=Sistema de gestão da Adega & Tabacaria Escritório\n"
        f"Exec={comando}\n"
        f"Icon={icone}\n"
        f"StartupWMClass={ID_APP_LINUX}\n"
        "Categories=Office;\n"
    )
    arquivo = Path.home() / ".local/share/applications" / f"{ID_APP_LINUX}.desktop"
    try:
        if not arquivo.exists() or arquivo.read_text(encoding="utf-8") != conteudo:
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            arquivo.write_text(conteudo, encoding="utf-8")
    except OSError:
        log.exception("Não foi possível criar o atalho do Linux")


def identificar_app():
    """Faz a barra de tarefas mostrar o logo e o nome do app. Devolve o ícone e a GUI."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ID_APP_WINDOWS)
        # O WinForms só aceita .ico.
        return str(RAIZ / "desktop" / "adega.ico"), None
    icone = str(RAIZ / "desktop" / "adega.png")
    if sys.platform.startswith("linux"):
        instalar_atalho_linux(icone)
        from qtpy.QtCore import QLocale
        from qtpy.QtGui import QGuiApplication

        # O navegador do Qt herda o idioma daqui: sem isso as datas saem em
        # inglês (07/18/2026) mesmo com o sistema em português.
        QLocale.setDefault(QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil))
        # Precisa vir antes do pywebview criar a QApplication.
        QGuiApplication.setApplicationName(ID_APP_LINUX)
        QGuiApplication.setDesktopFileName(ID_APP_LINUX)
        return icone, "qt"
    return icone, None


# Aparece na hora, enquanto o sistema carrega em segundo plano: num computador
# lento são alguns segundos, e sem nada na tela a pessoa clica de novo.
TELA_ABRINDO = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><style>
body{margin:0;height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;
background:#0c0a08;color:#e6c76a;font-family:Georgia,serif;gap:1.25rem}
.roda{width:38px;height:38px;border:3px solid #3a2f1c;border-top-color:#c9a227;border-radius:50%;
animation:g 0.9s linear infinite}@keyframes g{to{transform:rotate(360deg)}}
p{margin:0;font-size:1.25rem}small{color:#b3a68a;font-family:sans-serif}
</style></head><body><div class="roda"></div><p>Abrindo o Adega…</p><small>Só um instante</small></body></html>"""

TELA_ERRO = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><style>
body{margin:0;padding:3rem;background:#0c0a08;color:#f2ead9;font-family:sans-serif}
h1{color:#e6c76a;font-family:Georgia,serif}pre{white-space:pre-wrap;color:#b3a68a;font-size:.85rem}
</style></head><body><h1>O Adega encontrou um erro e não pôde abrir</h1>
<p>Tire uma foto desta tela e envie para o suporte. Os dados não foram alterados.</p><pre>{detalhes}</pre></body></html>"""


def _migracoes_pendentes():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    return bool(executor.migration_plan(executor.loader.graph.leaf_nodes()))


def _backup_inicial(settings):
    try:
        fazer_backup(settings)
    except Exception:  # um backup que falha não pode derrubar o sistema
        log.exception("Falha no backup ao abrir")


def preparar_sistema():
    """Carrega o Django, confere o banco e sobe o servidor. Devolve a URL inicial."""
    import django

    django.setup()
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    if _migracoes_pendentes():
        # Versão nova que muda o banco: backup antes, sempre, e só então migra.
        fazer_backup(settings)
        call_command("migrate", interactive=False, verbosity=0)
    else:
        # Nada a mudar: o backup de cada abertura vai em segundo plano.
        threading.Thread(target=_backup_inicial, args=(settings,), daemon=True).start()
    if not getattr(sys, "frozen", False):
        call_command("collectstatic", interactive=False, verbosity=0)

    from django.core.wsgi import get_wsgi_application
    from waitress import create_server

    host = "0.0.0.0" if settings.ACESSO_REDE else "127.0.0.1"
    servidor = create_server(get_wsgi_application(), host=host, port=settings.PORTA, threads=8)
    threading.Thread(target=servidor.run, daemon=True).start()
    threading.Thread(target=backup_periodico, args=(settings,), daemon=True).start()
    if settings.ATUALIZACAO_ATIVA:
        from apps.atualizacao import servicos as atualizacao

        atualizacao.registrar_versao_iniciada()
        atualizacao.iniciar_verificacao_periodica()

    url = f"http://localhost:{settings.PORTA}/"
    if not get_user_model().objects.filter(is_superuser=True).exists():
        url += "usuarios/primeiro-acesso/"
    log.info("Adega iniciado", extra={"url": url, "rede": settings.IPS_REDE})
    return url


def abrir_janela(titulo, pasta_dados, preparar):
    import html
    import traceback

    import webview

    icone, gui = identificar_app()
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    # Exportar para planilha. No Linux quem trata é ativar_downloads.
    webview.settings["ALLOW_DOWNLOADS"] = not sys.platform.startswith("linux")
    janela = criar_janela(
        titulo, html=TELA_ABRINDO, js_api=Api(), width=1280, height=800, min_size=(900, 600),
        confirm_close=True, maximized=True,
    )
    janela.events.loaded += lambda: janela.evaluate_js(JS_JANELAS_NOVAS)

    def carregar():
        try:
            janela.load_url(preparar())
        except Exception:
            log.exception("Erro ao iniciar o Adega")
            janela.load_html(TELA_ERRO.replace("{detalhes}", html.escape(traceback.format_exc(limit=3))))

    webview.start(
        carregar,
        gui=gui,
        icon=icone,
        private_mode=False,  # janelas compartilham o login
        storage_path=str(pasta_dados / "navegador"),
        localization={
            "global.quitConfirmation": "Fechar o Adega? O sistema será desligado.",
            "global.ok": "OK",
            "global.cancel": "Cancelar",
            "global.quit": "Fechar",
        },
    )


def main():
    # Só lê a configuração (rápido); o Django inteiro carrega com a janela já aberta.
    from django.conf import settings

    if porta_em_uso(settings.PORTA):
        avisar("O Adega já está aberto. Procure a janela dele na barra de tarefas.")
        return

    titulo = "Adega & Tabacaria Escritório"
    if settings.IPS_REDE:
        titulo += f"  —  no celular: http://{settings.IPS_REDE[0]}:{settings.PORTA}/"

    url = []

    def preparar():
        url.append(preparar_sistema())
        return url[0]

    try:
        abrir_janela(titulo, settings.DATA_DIR, preparar)
    except Exception:
        # Sem WebView2 (Windows muito desatualizado): cai pro navegador.
        log.exception("Não foi possível abrir a janela do app; usando o navegador")
        webbrowser.open(url[0] if url else preparar())
        avisar("O Adega foi aberto no navegador.\n\nClique em OK somente quando quiser DESLIGAR o sistema.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("Erro ao iniciar o Adega")
        import traceback

        avisar(
            "O Adega encontrou um erro e não pôde abrir.\n\n"
            + traceback.format_exc(limit=3)
            + "\nTire uma foto desta mensagem e envie para o suporte."
        )
        sys.exit(1)
