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
; Getting-started page shown after install, before the Finish page
InfoAfterFile=after_install.txt

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
; 1. Argos model download — moved to [Code] CurStepChanged(ssPostInstall)
;    so it runs inside the installer with a visible terminal showing progress.

; 2. Tesseract (only if task is checked) — runs during install phase via [Code]

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
// Run downloads during install phase — visible terminal shows progress.
// Both Argos and Tesseract run synchronously so Finish page only appears
// after downloads complete (no surprise background popups).
// ---------------------------------------------------------------------------
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Argos translation model (Full install only)
    if IsFullInstall then
    begin
      WizardForm.StatusLabel.Caption :=
        'Downloading offline translation model (~50-100 MB)...' + #13#10 +
        'A terminal window shows download progress. Please wait.';
      WizardForm.FilenameLabel.Caption := '';
      WizardForm.Update();
      // SW_SHOWNORMAL: visible terminal so user can watch progress
      // ewWaitUntilTerminated: installer waits here until download is done
      Exec('powershell.exe',
        '-ExecutionPolicy Bypass' +
        ' -File "' + ExpandConstant('{app}\download_packs.ps1') + '"' +
        ' "' + ExpandConstant('{app}') + '"',
        ExpandConstant('{app}'),
        SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode);
      if ResultCode <> 0 then
        MsgBox(
          'Translation model download failed (exit code ' + IntToStr(ResultCode) + ').' + #13#10 +
          'The app still works for dictionary and pinyin lookups.' + #13#10 +
          'To retry later, run download_packs.ps1 from the install folder.',
          mbInformation, MB_OK);
    end;
    // Tesseract OCR (only if task was checked)
    // Script always exits 0; Tesseract is optional so no error dialog shown.
    if WizardIsTaskSelected('tesseract') then
    begin
      WizardForm.StatusLabel.Caption :=
        'Downloading and installing Tesseract OCR (~30 MB)...' + #13#10 +
        'A terminal window shows installation progress. Please wait.';
      WizardForm.Update();
      Exec('powershell.exe',
        '-ExecutionPolicy Bypass' +
        ' -File "' + ExpandConstant('{tmp}\install_tesseract.ps1') + '"',
        '',
        SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode);
      // ResultCode ignored — Tesseract is optional; failures are non-fatal.
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
