; HaramaIn by Sheraz - Windows installer script (Inno Setup)
;
; Produces a single Setup.exe that installs the app with a Start Menu
; entry, optional desktop shortcut, and a proper uninstaller.
;
; Prerequisites:
;   1. You must have already run PyInstaller so that
;      dist\HaramaIn\HaramaIn.exe exists (see deployment\windows\harmain.spec).
;   2. Install Inno Setup (free): https://jrsoftware.org/isdl.php
;
; To build the installer:
;   - Open this file in Inno Setup and click Compile, OR
;   - From the command line:  ISCC deployment\windows\installer.iss
;
; Output: deployment\windows\installer_output\HaramaIn_Setup.exe

#define MyAppName "HaramaIn by Sheraz"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "HaramaIn by Sheraz"
#define MyAppExeName "HaramaIn.exe"

[Setup]
AppId={{4F1E9B7A-6C2D-4E3F-9A1B-HARAMAINBYSHZ}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=HaramaIn_Setup
SetupIconFile=..\..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
; Lowest privileges = installs to the current user without needing admin
; rights, and keeps app data under the same user's %APPDATA% it already
; uses today (see core/config.py -> get_app_data_dir).

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\..\dist\HaramaIn\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

; NOTE: this installer only places the program files under Program Files /
; AppData\Local\Programs. It deliberately does NOT touch
; %APPDATA%\HaramaIn (your database, documents, photos) on install OR
; uninstall, so re-running this installer to upgrade the app is always
; safe and never touches your existing data.
