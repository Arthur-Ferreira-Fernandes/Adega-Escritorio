; Instalador do Adega para Windows (Inno Setup 6). Gera AdegaSetup-<versão>.exe
; a partir da pasta dist\Adega criada pelo PyInstaller. Ver desktop/build.ps1.
;
; Instala só para o usuário atual (sem pedir administrador). Os dados ficam
; em %LOCALAPPDATA%\Adega e NÃO são apagados ao desinstalar nem ao atualizar.

#ifndef Versao
  #define Versao "1.0.0"
#endif

[Setup]
AppId={{6F1C2A4E-8B3D-4E7A-9C51-2D8E0F4B7A13}
AppName=Adega Escritório
AppVersion={#Versao}
AppPublisher=Arthur Ferreira Fernandes
DefaultDirName={autopf}\Adega
DefaultGroupName=Adega
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=AdegaSetup-{#Versao}
SetupIconFile=adega.ico
UninstallDisplayIcon={app}\Adega.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
; Quem reabre é o [Run] abaixo; reabrir também por aqui abriria duas vezes.
RestartApplications=no

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "areadetrabalho"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"
Name: "iniciarcomwindows"; Description: "Abrir o Adega automaticamente ao ligar o computador"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "..\dist\Adega\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; AppUserModelID igual ao ID_APP_WINDOWS de iniciar.py: é o que faz a janela
; aberta e o atalho fixado na barra de tarefas serem o mesmo ícone.
Name: "{group}\Adega Escritório"; Filename: "{app}\Adega.exe"; AppUserModelID: "ArthurFerreira.AdegaEscritorio"
Name: "{group}\Dados e backups do Adega"; Filename: "{localappdata}\Adega"
Name: "{autodesktop}\Adega Escritório"; Filename: "{app}\Adega.exe"; AppUserModelID: "ArthurFerreira.AdegaEscritorio"; Tasks: areadetrabalho
Name: "{userstartup}\Adega Escritório"; Filename: "{app}\Adega.exe"; AppUserModelID: "ArthurFerreira.AdegaEscritorio"; Tasks: iniciarcomwindows

[Run]
Filename: "{app}\Adega.exe"; Description: "Abrir o Adega Escritório agora"; Flags: nowait postinstall skipifsilent
; Atualização pelo próprio programa (instalação silenciosa): reabre sozinho no fim.
Filename: "{app}\Adega.exe"; Flags: nowait skipifnotsilent
