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
; Optional: Tesseract OCR fallback — auto-checked if Windows OCR unavailable (see [Code])
Name: "tesseract"; Description: "Download && install Tesseract OCR as Chinese OCR fallback (~30 MB)"; \
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
; 1. Download Argos zh->en translation model (Full install only — Check: IsFullInstall)
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\download_packs.ps1"" ""{app}"""; \
  Description: "Download offline sentence translation model (~50-100 MB)"; \
  Check: IsFullInstall; \
  Flags: postinstall runhidden nowait; \
  StatusMsg: "Launching translation model download..."

; 2. Download & install Tesseract OCR (only if tesseract task is checked)
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -File ""{tmp}\install_tesseract.ps1"""; \
  Description: "Download and install Tesseract OCR (~30 MB)"; \
  Tasks: tesseract; \
  Flags: postinstall nowait; \
  StatusMsg: "Downloading and installing Tesseract OCR..."

; 3. Launch the app after install (optional, user choice)
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
  Flags: postinstall nowait skipifsilent

[UninstallRun]
; Remove startup registry entry on uninstall
Filename: "reg.exe"; \
  Parameters: "delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Run"" /v ""{#MyAppName}"" /f"; \
  Flags: runhidden; RunOnceId: "RemoveStartupEntry"

[Code]
// ---------------------------------------------------------------------------
// Install type radio-button page + Windows OCR check
// ---------------------------------------------------------------------------

var
  InstallTypePage: TInputOptionWizardPage;
  WinOcrAvailable: Boolean;
  TesseractAutoChecked: Boolean;

// ---------------------------------------------------------------------------
// Check whether Windows.Media.Ocr has a Chinese recogniser installed.
// Shells out to PowerShell; returns True if zh* language found.
// ---------------------------------------------------------------------------
function CheckWindowsOcrAvailable: Boolean;
var
  TempFile: String;
  Script: String;
  ResultCode: Integer;
begin
  TempFile := ExpandConstant('{tmp}\check_ocr.ps1');
  Script :=
    '[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null; ' +
    '$langs = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages; ' +
    '$zh = $langs | Where-Object { $_.LanguageTag -like "zh*" }; ' +
    'if ($zh) { exit 0 } else { exit 1 }';
  SaveStringToFile(TempFile, Script, False);
  Result := Exec(
    'powershell.exe',
    '-ExecutionPolicy Bypass -NonInteractive -File "' + TempFile + '"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode
  ) and (ResultCode = 0);
end;

// ---------------------------------------------------------------------------
// Called by [Run] Check: parameter — determines whether to download Argos
// ---------------------------------------------------------------------------
function IsFullInstall: Boolean;
begin
  Result := InstallTypePage.Values[0];
end;

// ---------------------------------------------------------------------------
// Set up custom pages during wizard initialisation
// ---------------------------------------------------------------------------
procedure InitializeWizard;
begin
  TesseractAutoChecked := False;

  // Check Windows OCR availability early (before wizard pages are shown)
  WinOcrAvailable := CheckWindowsOcrAvailable();

  // Create radio-button install-type page, inserted after the directory page
  InstallTypePage := CreateInputOptionPage(
    wpSelectDir,
    'Installation Type',
    'Choose the type of installation',
    'Select the installation that best suits your needs:',
    True,   // Exclusive = True renders as radio buttons
    False   // ListBox = False (standard radio group, not list box)
  );

  InstallTypePage.Add(
    'Full install (recommended)' + #13#10 +
    '    Includes offline sentence translation. After install, the Argos ' +
    'zh' + #226#134#146 + 'en model (~50-100 MB) is downloaded automatically.'
  );
  InstallTypePage.Add(
    'Lite install' + #13#10 +
    '    Dictionary lookup and pinyin only — no sentence translation. ' +
    'No additional downloads required after install.'
  );

  // Default: Full install
  InstallTypePage.Values[0] := True;
end;

// ---------------------------------------------------------------------------
// When the Tasks page appears, auto-check Tesseract if Windows OCR is absent
// ---------------------------------------------------------------------------
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectTasks then
  begin
    if (not WinOcrAvailable) and (not TesseractAutoChecked) then
    begin
      // Pre-select Tesseract since Windows OCR won't handle Chinese
      WizardSelectTasks('tesseract');
      TesseractAutoChecked := True;
    end;
  end;
end;

// ---------------------------------------------------------------------------
// Customise the "Ready to Install" summary memo
// ---------------------------------------------------------------------------
function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo,
  MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
var
  InstallType: String;
  OcrNote: String;
begin
  if IsFullInstall then
    InstallType := 'Full install — dictionary, pinyin + offline sentence translation'
  else
    InstallType := 'Lite install — dictionary and pinyin only';

  if not WinOcrAvailable then
    OcrNote := NewLine +
      'Note: Windows OCR for Chinese not detected. ' +
      'Tesseract is recommended for OCR support.'
  else
    OcrNote := '';

  Result :=
    MemoDirInfo + NewLine + NewLine +
    'Install type:' + NewLine +
    Space + InstallType + NewLine + NewLine +
    MemoTasksInfo +
    OcrNote;
end;
