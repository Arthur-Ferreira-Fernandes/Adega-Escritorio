# Gera o instalador do Adega num Windows com Python 3.12 e Inno Setup 6.
# Uso (na raiz do projeto):  powershell -ExecutionPolicy Bypass -File desktop\build.ps1 -Versao 1.0.0
param([string]$Versao = "1.0.0")
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true  # pip/pyinstaller falhando também param o build

python -m venv .venv-desktop
.\.venv-desktop\Scripts\python -m pip install --upgrade pip
.\.venv-desktop\Scripts\pip install -r requirements\desktop.txt pyinstaller

# Pasta de dados descartável: o build importa as configurações, que criam
# a pasta de dados — não pode ser a pasta real desta máquina.
$env:ADEGA_DATA_DIR = Join-Path $env:TEMP "adega-build"
# Vai dentro do executável: é como o programa sabe a própria versão e liga o
# atualizador (apps/atualizacao). Sem BOM, para o Python ler limpo.
[System.IO.File]::WriteAllText((Join-Path $PWD "desktop\versao.txt"), $Versao)
.\.venv-desktop\Scripts\python manage.py collectstatic --noinput --clear --settings=config.settings.desktop
.\.venv-desktop\Scripts\pyinstaller --noconfirm desktop\adega.spec

$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
& $iscc "/DVersao=$Versao" desktop\instalador.iss
Write-Host "Pronto: dist\AdegaSetup-$Versao.exe"
