; Inno Setup 6 script - per-user installer (no admin rights needed)
#ifndef AppVersion
  #define AppVersion "1.5.1"
#endif
[Setup]
AppId={{9D7A3B14-5C2E-4F6A-8E01-A7B2C3D4E5F6}
AppName=91 TV
AppVersion={#AppVersion}
AppPublisher=91 TV
DefaultDirName={autopf}\91 TV
DefaultGroupName=91 TV
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=release
OutputBaseFilename=91TV-Setup-{#AppVersion}
SetupIconFile=assets\aurora.ico
UninstallDisplayIcon={app}\91TV.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0.19041
[Files]
Source: "dist\91TV\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs
[Icons]
Name: "{group}\91 TV"; Filename: "{app}\91TV.exe"
Name: "{autodesktop}\91 TV"; Filename: "{app}\91TV.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\91TV.exe"; Description: "Launch 91 TV"; Flags: nowait postinstall skipifsilent
