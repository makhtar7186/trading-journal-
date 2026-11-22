; Installateur Trading Journal (Inno Setup 6). Compilé par build.py avec /DAppVersion /DSourceDir /DOutputDir.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "dist\TradingJournal"
#endif
#ifndef OutputDir
  #define OutputDir "dist"
#endif

[Setup]
AppId={{6E1B7F0A-3C52-4E84-9B6D-7A4C2F1D9E10}
AppName=Trading Journal
AppVersion={#AppVersion}
AppVerName=Trading Journal {#AppVersion}
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\TradingJournal
DefaultGroupName=Trading Journal
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=TradingJournal-Setup-{#AppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\TradingJournal.exe
Compression=lzma2/max
SolidCompression=yes
; Installation pour l'utilisateur courant, SANS droits administrateur (PostgreSQL demandera les siens séparément).
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Trading Journal"; Filename: "{app}\TradingJournal.exe"
Name: "{autodesktop}\Trading Journal"; Filename: "{app}\TradingJournal.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[Run]
Filename: "{app}\TradingJournal.exe"; Description: "Lancer Trading Journal"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Seuls les fichiers de l'installation sont supprimés. Les données (%LOCALAPPDATA%\TradingJournal) et PostgreSQL
; sont CONSERVÉS : désinstaller puis réinstaller ne fait jamais perdre un seul trade.
Type: filesandordirs; Name: "{app}"
