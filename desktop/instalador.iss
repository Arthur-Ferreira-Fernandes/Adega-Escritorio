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
AppName=Adega
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

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "areadetrabalho"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"
Name: "iniciarcomwindows"; Description: "Abrir o Adega automaticamente ao ligar o computador"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "..\dist\Adega\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Adega"; Filename: "{app}\Adega.exe"
Name: "{group}\Dados e backups do Adega"; Filename: "{localappdata}\Adega"
Name: "{autodesktop}\Adega"; Filename: "{app}\Adega.exe"; Tasks: areadetrabalho
Name: "{userstartup}\Adega"; Filename: "{app}\Adega.exe"; WindowState: minimized; Tasks: iniciarcomwindows

[Run]
Filename: "{app}\Adega.exe"; Description: "Abrir o Adega agora"; Flags: nowait postinstall skipifsilent
