; The Windows installer of sci2audio (#215, D-797), built by scripts/build_installer.py:
;   ISCC /DAppVersion=1.4.0 /DSourceDir=<PyInstaller folder> /DRepoDir=<checkout>
;        /DOutputDir=<folder> /DOutputName=<file name without .exe> sci2audio.iss
; For one person, no administrator rights: the program goes to
; %LOCALAPPDATA%\Programs\sci2audio. Uninstalling removes that folder only; the
; audiobooks, the voice files, the settings and the library stay where they are.

#ifndef AppVersion
  #error AppVersion is not set
#endif

[Setup]
; never change: Windows finds an earlier installation of sci2audio by it
AppId={{6A0B7D62-5B7C-4C55-9E1B-2E3A54C1D0F7}
AppName=sci2audio
AppVersion={#AppVersion}
AppVerName=sci2audio {#AppVersion}
AppPublisher=sci2audio contributors
AppPublisherURL=https://github.com/dubidu22/sci2audio
AppSupportURL=https://github.com/dubidu22/sci2audio/issues
DefaultDirName={autopf}\sci2audio
DefaultGroupName=sci2audio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
LicenseFile={#RepoDir}\LICENSE
SetupIconFile={#RepoDir}\packaging\icons\sci2audio.ico
UninstallDisplayIcon={app}\sci2audio-app.exe
UninstallDisplayName=sci2audio
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
Compression=lzma2/normal
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\sci2audio"; Filename: "{app}\sci2audio-app.exe"
Name: "{autodesktop}\sci2audio"; Filename: "{app}\sci2audio-app.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\sci2audio-app.exe"; Description: "{cm:LaunchProgram,sci2audio}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; the program folder only (a log or cache PyInstaller might leave there); never the
; user's files, which live in Documents\sci2audio and the user's AppData folders
Type: filesandordirs; Name: "{app}"
