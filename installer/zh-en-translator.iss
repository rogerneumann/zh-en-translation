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
SetupIconFile=icon.ico
WizardImageFile=wizard_large.bmp
WizardSmallImageFile=wizard_small.bmp
; Getting-started page shown after install, before the Finish page
InfoAfterFile=after_install.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Desktop shortcut — opt-in (default unchecked)
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; Launch at Windows startup — default checked
Name: "startup"; Description: "Launch {#MyAppName} when Windows starts"; GroupDescription: "Windows startup:"; Flags: checkedonce

[Files]
; PyInstaller onedir output — entire dist\zh-en-translator\ folder
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Post-install helper scripts
Source: "download_packs.ps1"; DestDir: "{app}"; Flags: ignoreversion
; Elevated OCR setup (Windows OCR capability + Tesseract Program Files) -- triggered once post-install
Source: "setup_elevated.ps1"; DestDir: "{app}"; Flags: ignoreversion
; User-level Tesseract install fallback (used by Preferences if elevated script unavailable)
Source: "install_tesseract.ps1"; DestDir: "{app}"; Flags: ignoreversion
; Bundled Tesseract OCR (portable — always included, no UAC required)
Source: "tesseract-bundle\*"; DestDir: "{app}\tesseract"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: BundleExists('tesseract-bundle\tesseract.exe')
; Bundled CC-CEDICT (pre-populated so no network required on first run)
Source: "cedict-bundle\cedict_ts.u8"; DestDir: "{userappdata}\zh-en-translator"; Flags: ignoreversion; Check: BundleExists('cedict-bundle\cedict_ts.u8')
; Bundled Argos zh->en model (pre-populated packages dir)
Source: "argos-bundle\*"; DestDir: "{userappdata}\argos-translate\packages"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: BundleDirExists('argos-bundle')

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
// Bundle presence checks — used as Check: guards in [Files] so missing
// bundles (e.g. CI builds) don't cause compiler or installer errors.
// ---------------------------------------------------------------------------
function BundleExists(RelPath: String): Boolean;
begin
  Result := FileExists(ExpandConstant('{src}\' + RelPath));
end;

function BundleDirExists(RelDir: String): Boolean;
begin
  Result := DirExists(ExpandConstant('{src}\' + RelDir));
end;

// ---------------------------------------------------------------------------
// Detect if the app is already running before the wizard starts.
// Offers to kill it automatically so files can be overwritten cleanly.
// ---------------------------------------------------------------------------
function InitializeSetup: Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  Exec('powershell.exe',
    '-NoProfile -NonInteractive -Command ' +
    '"if (Get-Process -Name ''zh-en-translator'' -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if ResultCode = 1 then
  begin
    if MsgBox(
        'zh-en-translator is currently running.' + #13#10 +
        'Click OK to close it automatically and continue,' + #13#10 +
        'or Cancel to exit the installer.',
        mbConfirmation, MB_OKCANCEL) = IDOK then
    begin
      Exec('powershell.exe',
        '-NoProfile -NonInteractive -Command ' +
        '"Stop-Process -Name ''zh-en-translator'' -Force -ErrorAction SilentlyContinue"',
        '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Sleep(1500);
    end
    else
      Result := False;
  end;
end;

// ---------------------------------------------------------------------------
// Install type radio-button page + Windows OCR check
// ---------------------------------------------------------------------------

var
  InstallTypePage: TInputOptionWizardPage;
  WinOcrAvailable: Boolean;

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
// CurPageChanged — no Tesseract task to auto-check (Tesseract is now bundled)
// ---------------------------------------------------------------------------
procedure CurPageChanged(CurPageID: Integer);
begin
  // Tesseract is now always bundled in the installer — no task auto-selection needed.
end;


// ---------------------------------------------------------------------------
// Run downloads during install phase — visible terminal shows progress.
// Both Argos and OCR setup run synchronously so Finish page only appears
// after they complete (no surprise background popups).
// ---------------------------------------------------------------------------
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Step 1: Argos translation model (Full install only)
    // Skip if the Argos bundle was pre-populated in the installer.
    if IsFullInstall and not BundleDirExists('argos-bundle') then
    begin
      WizardForm.StatusLabel.Caption :=
        'Downloading offline translation model (~50-100 MB)...' + #13#10 +
        'A terminal window shows download progress. Please wait.';
      WizardForm.FilenameLabel.Caption := '';
      WizardForm.Update();
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

    // Step 2: Single-elevation OCR setup
    // Covers both Windows OCR Chinese capability and Tesseract Program Files install.
    // Skip if Windows OCR Chinese is already available AND Tesseract is bundled.
    if not (WinOcrAvailable and BundleExists('tesseract-bundle\tesseract.exe')) then
    begin
      if MsgBox(
          'OCR features need a one-time administrator prompt to complete setup.' + #13#10#13#10 +
          'This will:' + #13#10 +
          '  - Install Windows OCR Chinese language support' + #13#10 +
          '  - Install Tesseract as an OCR backup (if not already present)' + #13#10#13#10 +
          'Click OK to allow (one UAC prompt), or Cancel to configure later via Preferences.',
          mbConfirmation, MB_OKCANCEL) = IDOK then
      begin
        WizardForm.StatusLabel.Caption := 'Configuring OCR features (administrator required)...';
        WizardForm.FilenameLabel.Caption := '';
        WizardForm.Update();
        // ShellExec with runas verb triggers a single UAC elevation.
        // ewWaitUntilTerminated ensures the installer waits before showing Finish.
        ShellExec('runas', 'powershell.exe',
          '-ExecutionPolicy Bypass -WindowStyle Normal' +
          ' -File "' + ExpandConstant('{app}\setup_elevated.ps1') + '"',
          ExpandConstant('{app}'),
          SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode);
      end;
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
begin
  if IsFullInstall then
    InstallType := 'Full install — dictionary, pinyin + offline sentence translation'
  else
    InstallType := 'Lite install — dictionary and pinyin only';

  Result :=
    MemoDirInfo + NewLine + NewLine +
    'Install type:' + NewLine +
    Space + InstallType + NewLine + NewLine +
    MemoTasksInfo;
end;
