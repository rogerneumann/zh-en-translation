; Inno Setup 6 script for zh-en-translator
;
; Build:  iscc installer\zh-en-translator.iss
; Prerequisite: run PyInstaller first (see installer\build.ps1)
;
; Output: installer\Output\zh-en-translator-setup.exe
;         (single self-contained installer, ~240-290 MB)

#define MyAppName      "zh-en-translator"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "rogerneumann"
#define MyAppExeName   "zh-en-translator.exe"
#define MyDistDir      "..\dist\zh-en-translator"

[Setup]
AppId={{A7C3E2D1-4F8B-4A2E-9C1D-3B6F5E8A0D2C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/{#MyAppPublisher}/zh-en-translator
AppSupportURL=https://github.com/{#MyAppPublisher}/zh-en-translator/issues
AppUpdatesURL=https://github.com/{#MyAppPublisher}/zh-en-translator/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Show installation directory page explicitly
DisableDirPage=no
; User-level install — no admin required
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Output
OutputDir=Output
OutputBaseFilename=zh-en-translator-setup
; Compression
Compression=lzma2/ultra64
SolidCompression=yes
; Architecture
ArchitecturesInstallIn64BitMode=x64compatible
; Minimum Windows 10
MinVersion=10.0.17763
; Visual
WizardStyle=modern
SetupIconFile=
; No icon file yet — omit to use default Inno Setup icon

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Desktop shortcut — opt-in (default unchecked)
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; Launch at Windows startup — default checked
Name: "startup"; Description: "Launch {#MyAppName} when Windows starts"; GroupDescription: "Windows startup:"; Flags: checkedonce
; Optional: Download and install Tesseract OCR as a fallback
Name: "tesseract"; Description: "Download & install Tesseract OCR (Chinese Simplified)"; \
  GroupDescription: "Optional components:"; Flags: unchecked

[Files]
; PyInstaller onedir output — entire dist\zh-en-translator\ folder
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Post-install helper scripts
Source: "download_packs.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "install_tesseract.ps1"; DestDir: "{tmp}"; Flags: ignoreversion

[Icons]
; Start Menu shortcut
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
; Desktop shortcut (optional task)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; HKCU Run entry — written only when user ticked "startup" task
; Cleared on uninstall automatically (Flags: uninsdeletevalue)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#MyAppName}"; \
  ValueData: """{app}\{#MyAppExeName}"""; \
  Tasks: startup; Flags: uninsdeletevalue

[Run]
; 1. Download Argos zh→en translation model pack post-install (background)
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\download_packs.ps1"" ""{app}"""; \
  Description: "Download translation model pack (required for offline translation)"; \
  Flags: postinstall runhidden nowait; \
  StatusMsg: "Downloading translation model pack..."

; 2. Download & install Tesseract (only if tesseract task is checked)
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -File ""{tmp}\install_tesseract.ps1"""; \
  Description: "Installing Tesseract OCR..."; \
  Tasks: tesseract; \
  Flags: postinstall nowait; \
  StatusMsg: "Downloading and installing Tesseract OCR (~30 MB)..."

; 3. Launch the app after install (optional, user choice)
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
  Flags: postinstall nowait skipifsilent

[UninstallRun]
; Remove startup registry entry on uninstall (belt-and-suspenders alongside [Registry] Flags)
Filename: "reg.exe"; \
  Parameters: "delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Run"" /v ""{#MyAppName}"" /f"; \
  Flags: runhidden; RunOnceId: "RemoveStartupEntry"

[Code]
// Provide a summary note on the Ready to Install page
function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo,
  MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := MemoDirInfo + NewLine + NewLine +
    MemoGroupInfo + NewLine + NewLine +
    MemoTasksInfo + NewLine + NewLine +
    'Next steps:' + NewLine +
    Space + '• Argos translation model (~50-100 MB) downloads after install' + NewLine +
    Space + '• If Tesseract is checked, it will install as an OCR fallback' + NewLine +
    Space + '• Internet connection required for initial downloads' + NewLine +
    Space + '• Windows OCR will be used if available; Tesseract is optional.';
end;
