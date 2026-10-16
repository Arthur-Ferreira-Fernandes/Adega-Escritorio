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
    # Certificados HTTPS pelo Windows (atualização). Importado dentro de uma
    # função; declarado aqui para não depender da análise do PyInstaller.
    + collect_submodules("truststore")
)

datas = (
    collect_data_files("django")
    + collect_data_files("apps")
    + [
        (os.path.join(RAIZ, "templates"), "templates"),
        (os.path.join(RAIZ, "staticfiles"), "staticfiles"),
        (os.path.join(SPECPATH, "adega.ico"), "desktop"),
        (os.path.join(SPECPATH, "adega.png"), "desktop"),
    ]
    # Gravado pelo build.ps1: sem ele o programa não sabe a versão e não se atualiza.
    + ([(os.path.join(SPECPATH, "versao.txt"), "desktop")] if os.path.exists(os.path.join(SPECPATH, "versao.txt")) else [])
)

a = Analysis(
    [os.path.join(SPECPATH, "iniciar.py")],
    pathex=[RAIZ],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["celery", "redis", "django_redis", "psycopg2", "tkinter"],
)
pyz = PYZ(a.pure)

# Nome que o Windows mostra no Gerenciador de Tarefas e nas propriedades do .exe.
versao = None
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
    )

    versao = VSVersionInfo(
        ffi=FixedFileInfo(),
        kids=[
            StringFileInfo([StringTable("041604B0", [
                StringStruct("CompanyName", "Adega & Tabacaria Escritório"),
                StringStruct("FileDescription", "Adega Escritório"),
                StringStruct("ProductName", "Adega Escritório"),
                StringStruct("OriginalFilename", "Adega.exe"),
                StringStruct("ProductVersion", open(os.path.join(SPECPATH, "versao.txt"), encoding="utf-8").read().strip()
                             if os.path.exists(os.path.join(SPECPATH, "versao.txt")) else "dev"),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0416, 1200])]),
        ],
    )

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Adega",
    console=False,  # sem janela preta: o app abre a própria janela (pywebview)
    icon=os.path.join(SPECPATH, "adega.ico"),
    version=versao,
)

coll = COLLECT(exe, a.binaries, a.datas, name="Adega")
