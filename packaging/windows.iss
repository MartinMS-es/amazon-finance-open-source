#define AppName "AMAZON FINANCE OPEN SOURCE"
#define AppVersion "1.0.0"
[Setup]
AppId={{5A47334A-BF38-4B26-9AD0-7C895A422D2C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=MartinMS-es
AppPublisherURL=https://github.com/MartinMS-es
AppSupportURL=https://github.com/MartinMS-es
DefaultDirName={localappdata}\Programs\AmazonFinanceOpenSource
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\Instalador
OutputBaseFilename=AMAZON-FINANCE-OPEN-SOURCE-Setup-1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
SetupLogging=yes
UninstallDisplayIcon={app}\AmazonFinanceOpenSource.exe
LicenseFile=..\LICENSE
[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio / Create desktop shortcut"; Flags: checkedonce
[Files]
Source: "..\dist\AmazonFinanceOpenSource\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\GUIA-INSTALACION.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\INSTALLATION-GUIDE-EN.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\AmazonFinanceOpenSource.exe"
Name: "{group}\Desinstalar / Uninstall"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\AmazonFinanceOpenSource.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\AmazonFinanceOpenSource.exe"; Description: "Abrir / Open {#AppName}"; Flags: nowait postinstall skipifsilent
; User data and personal certificates are deliberately never shipped or deleted by uninstall.
