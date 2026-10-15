# Empacotamento do Adega.exe com PyInstaller. Rodar a partir da raiz do
# projeto, depois do collectstatic (ver desktop/build.ps1):
#     pyinstaller desktop/adega.spec
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

RAIZ = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, RAIZ)  # pros collect_submodules abaixo acharem apps/ e config/
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.desktop"

# O Django carrega apps, middlewares e backends por nome (string), então o
# PyInstaller não os enxerga sozinho: tudo precisa entrar explicitamente.
hiddenimports = (
    collect_submodules("apps")
    + collect_submodules("config")
    + collect_submodules("django", filter=lambda nome: not nome.startswith("django.contrib.postgres"))
    + collect_submodules("whitenoise")
    + collect_submodules("waitress")
)

datas = (
    collect_data_files("django")
    + collect_data_files("apps")
    + [
        (os.path.join(RAIZ, "templates"), "templates"),
        (os.path.join(RAIZ, "staticfiles"), "staticfiles"),
    ]
)

a = Analysis(
    [os.path.join(SPECPATH, "iniciar.py")],
    pathex=[RAIZ],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["celery", "redis", "django_redis", "psycopg2", "tkinter"],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Adega",
    console=False,  # sem janela preta: o app abre a própria janela (pywebview)
    icon=os.path.join(SPECPATH, "adega.ico"),
)

coll = COLLECT(exe, a.binaries, a.datas, name="Adega")
