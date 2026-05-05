; Inno Setup 6 script for zh-en-translator
;
; Build:  iscc installer\zh-en-translator.iss
; Prerequisite: run PyInstaller first (see installer\build.ps1)
;
; Output: installer\Output\zh-en-translator-setup.exe
;         (single self-contained installer, ~240-290 MB)

#define MyAppName      "zh-en-translator"
#define MyAppVersion   "2026.05.05.3"
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
; User-level install -- always installs to current user, no admin required
PrivilegesRequired=lowest
; Output
OutputDir=Output
OutputBaseFilename=zh-en-translator-v{#MyAppVersion}-setup
; License shown during installation
LicenseFile=..\LICENSE
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
; Desktop shortcut -- opt-in (default unchecked)
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; Launch at Windows startup -- default checked
Name: "startup"; Description: "Launch {#MyAppName} when Windows starts"; GroupDescription: "Windows startup:"; Flags: checkedonce

[Files]
; PyInstaller onedir output -- entire dist\zh-en-translator\ folder
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Post-install helper scripts
Source: "download_packs.ps1"; DestDir: "{app}"; Flags: ignoreversion
; Elevated OCR setup -- Windows OCR capability only (one UAC prompt for this step)
Source: "setup_ocr_elevated.ps1"; DestDir: "{app}"; Flags: ignoreversion
; Full elevated setup for Preferences OCR page (Windows OCR + Tesseract system-wide)
Source: "setup_elevated.ps1"; DestDir: "{app}"; Flags: ignoreversion
; User-level Tesseract install (no admin required -- installs to LocalAppData via winget/direct)
Source: "install_tesseract.ps1"; DestDir: "{app}"; Flags: ignoreversion
; Bundled Tesseract OCR -- only installed if user keeps the Tesseract checkbox checked
Source: "tesseract-bundle\*"; DestDir: "{app}\tesseract"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: ShouldInstallTesseract
; Bundled CC-CEDICT (pre-populated so no network required on first run)
Source: "cedict-bundle\cedict_ts.u8"; DestDir: "{userappdata}\zh-en-translator"; Flags: ignoreversion; Check: BundleExists('cedict-bundle\cedict_ts.u8')
; Bundled Argos zh->en model (pre-populated packages dir)
Source: "argos-bundle\*"; DestDir: "{userappdata}\argos-translate\packages"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: BundleDirExists('argos-bundle')
; Bundled Argos en->zh model (back-translation quality check)
Source: "argos-en-zh-bundle\*"; DestDir: "{userappdata}\argos-translate\packages"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: BundleDirExists('argos-en-zh-bundle')

[Icons]
; Start Menu shortcut
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
; Desktop shortcut (optional task)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; HKCU Run entry -- written only when user ticked "startup" task
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#MyAppName}"; \
  ValueData: """{app}\{#MyAppExeName}"""; \
  Tasks: startup; Flags: uninsdeletevalue

[Run]
; Launch the app after install (optional, user choice)
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
// State variables
// ---------------------------------------------------------------------------
var
  InstallTypePage: TInputOptionWizardPage;
  OcrPage:         TInputOptionWizardPage;
  WinOcrAvailable:    Boolean;   // True if Windows OCR Chinese is already enabled
  PreviousInstallType: String;   // 'full', 'lite', or '' for new install
  InstallTesseract:    Boolean;  // mirrors OcrPage.Values[1]; gates [Files] Check:
  ArgosInstalled:      Boolean;  // post-install outcome for install_state.toml
  WinOcrInstalled:     Boolean;  // post-install outcome for install_state.toml

// ---------------------------------------------------------------------------
// Bundle presence checks -- used as Check: guards in [Files]
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
// Tesseract install gate -- evaluated during file-copy phase
// ---------------------------------------------------------------------------
function ShouldInstallTesseract: Boolean;
begin
  Result := InstallTesseract and BundleExists('tesseract-bundle\tesseract.exe');
end;

// ---------------------------------------------------------------------------
// Install type and OCR option helpers
// ---------------------------------------------------------------------------
function IsFullInstall: Boolean;
begin
  Result := InstallTypePage.Values[0];
end;

function WantsWindowsOcr: Boolean;
begin
  Result := OcrPage.Values[0];
end;

// ---------------------------------------------------------------------------
// Check whether Windows.Media.Ocr has a Chinese recogniser installed.
// Shells out to PowerShell; returns True if a zh* language is found.
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
// Read previous install metadata from registry
// ---------------------------------------------------------------------------
function GetPreviousInstallType: String;
var
  Value: String;
begin
  Result := '';
  if RegQueryStringValue(HKCU, 'Software\zh-en-translator', 'InstallType', Value) then
    Result := LowerCase(Value);
end;

function GetPreviousRegBool(const ValueName: String): Boolean;
var
  Value: String;
begin
  Result := True;  // default to checked if no previous record
  if RegQueryStringValue(HKCU, 'Software\zh-en-translator', ValueName, Value) then
    Result := (LowerCase(Value) = 'true');
end;

// ---------------------------------------------------------------------------
// Write install state to HKCU registry and %APPDATA%\install_state.toml
// Called at the end of ssPostInstall so it reflects actual outcomes.
// ---------------------------------------------------------------------------
procedure WriteInstallState(InstType: String; ArgosOk: Boolean;
  WinOcrOk: Boolean; TessOk: Boolean);
var
  StateDir:  String;
  FilePath:  String;
  Content:   String;
  SArgos:    String;
  SWinOcr:   String;
  STess:     String;
begin
  if ArgosOk  then SArgos  := 'true' else SArgos  := 'false';
  if WinOcrOk then SWinOcr := 'true' else SWinOcr := 'false';
  if TessOk   then STess   := 'true' else STess   := 'false';

  // -- Registry --
  RegWriteStringValue(HKCU, 'Software\zh-en-translator', 'InstallType',         InstType);
  RegWriteStringValue(HKCU, 'Software\zh-en-translator', 'InstallVersion',      '{#MyAppVersion}');
  RegWriteStringValue(HKCU, 'Software\zh-en-translator', 'InstallDir',          ExpandConstant('{app}'));
  RegWriteStringValue(HKCU, 'Software\zh-en-translator', 'ArgosInstalled',      SArgos);
  RegWriteStringValue(HKCU, 'Software\zh-en-translator', 'WinOcrInstalled',     SWinOcr);
  RegWriteStringValue(HKCU, 'Software\zh-en-translator', 'TesseractInstalled',  STess);

  // -- TOML file --
  StateDir := ExpandConstant('{userappdata}\zh-en-translator');
  ForceDirectories(StateDir);
  FilePath := StateDir + '\install_state.toml';

  Content :=
    '# zh-en-translator installation state' + #13#10 +
    '# Written by installer -- reflects outcomes of the last install/upgrade.' + #13#10 +
    '# The app may update [components] at runtime (e.g. after downloading Argos).' + #13#10 + #13#10 +
    '[install]' + #13#10 +
    'version = "' + '{#MyAppVersion}' + '"' + #13#10 +
    'type    = "' + InstType + '"' + #13#10 +
    'date    = "' + GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':') + '"' + #13#10 +
    'dir     = "' + ExpandConstant('{app}') + '"' + #13#10 + #13#10 +
    '[components]' + #13#10 +
    'argos        = ' + SArgos  + #13#10 +
    'windows_ocr  = ' + SWinOcr + #13#10 +
    'tesseract    = ' + STess   + #13#10;

  SaveStringToFile(FilePath, Content, False);
end;

// ---------------------------------------------------------------------------
// Detect whether the app is already running before the wizard starts.
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
// InitializeWizard -- build custom pages and apply previous-install defaults
// ---------------------------------------------------------------------------
procedure InitializeWizard;
var
  PrevNote:    String;
  OcrWinNote:  String;
  PrevWinOcr:  Boolean;
  PrevTess:    Boolean;
begin
  // Detect environment and prior state
  WinOcrAvailable     := CheckWindowsOcrAvailable();
  PreviousInstallType := GetPreviousInstallType();

  // Initialise outcome trackers
  InstallTesseract := True;
  ArgosInstalled   := False;
  WinOcrInstalled  := WinOcrAvailable;

  // Previous-install note shown as the sub-caption on the Install Type page
  if PreviousInstallType = 'full' then
    PrevNote :=
      'Previous Full installation detected -- options pre-selected to match.' + #13#10 +
      'Change any option below to upgrade or switch install type.'
  else if PreviousInstallType = 'lite' then
    PrevNote :=
      'Previous Lite installation detected -- options pre-selected to match.' + #13#10 +
      'Change any option below to upgrade or switch install type.'
  else
    PrevNote := 'Select the installation that best suits your needs:';

  // ---- Install Type page (radio buttons, after the directory page) ----
  InstallTypePage := CreateInputOptionPage(
    wpSelectDir,
    'Installation Type',
    'Choose the type of installation',
    PrevNote,
    True,    // Exclusive = True -> radio buttons
    False
  );
  InstallTypePage.Add(
    'Full install (recommended)' + #13#10 +
    '    Includes offline sentence translation. The Argos zh' + #226#134#146 + 'en model' + #13#10 +
    '    (~50-100 MB) is bundled or downloaded automatically after install.'
  );
  InstallTypePage.Add(
    'Lite install' + #13#10 +
    '    Dictionary lookup and pinyin only -- no sentence translation.' + #13#10 +
    '    No additional downloads required after install.'
  );

  // Pre-select based on previous install; default to Full for new installs
  if PreviousInstallType = 'lite' then
    InstallTypePage.Values[1] := True
  else
    InstallTypePage.Values[0] := True;

  // ---- OCR Options page (checkboxes, after the Install Type page) ----
  if WinOcrAvailable then
    OcrWinNote :=
      'Windows OCR  [Recommended -- Chinese already enabled]' + #13#10 +
      '    Built-in Windows recognition. Chinese language pack is already installed.' + #13#10 +
      '    Setup will verify and refresh the configuration (no admin prompt needed).'
  else
    OcrWinNote :=
      'Windows OCR  [Recommended]' + #13#10 +
      '    Built-in Windows recognition for Chinese text.' + #13#10 +
      '    Requires one administrator (UAC) prompt to enable the language pack.' + #13#10 +
      '    Language data downloads via Windows Update -- this can take 30 minutes' + #13#10 +
      '    or more on slow connections, or longer if other updates are queued.';

  OcrPage := CreateInputOptionPage(
    InstallTypePage.ID,
    'OCR Options',
    'Configure text recognition (OCR) features',
    'Select which OCR engines to install:',
    False,   // Exclusive = False -> checkboxes
    False
  );
  OcrPage.Add(OcrWinNote);
  OcrPage.Add(
    'Tesseract OCR  [Bundled -- ~150 MB, no download required]' + #13#10 +
    '    Portable backup OCR engine included in this installer.' + #13#10 +
    '    Used automatically when Windows OCR is unavailable.' + #13#10 +
    '    Uncheck to skip installation and save ~150 MB of disk space.' + #13#10 +
    '    Note: other applications on this system may also depend on Tesseract.'
  );

  // Pre-select from previous install record (default both checked for new installs)
  if PreviousInstallType <> '' then
  begin
    PrevWinOcr := GetPreviousRegBool('WinOcrInstalled');
    PrevTess   := GetPreviousRegBool('TesseractInstalled');
    OcrPage.Values[0] := PrevWinOcr;
    OcrPage.Values[1] := PrevTess;
    InstallTesseract   := PrevTess;
  end
  else
  begin
    OcrPage.Values[0] := True;
    OcrPage.Values[1] := True;
  end;
end;

// ---------------------------------------------------------------------------
// NextButtonClick -- validate OCR choices before advancing
// ---------------------------------------------------------------------------
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if CurPageID = OcrPage.ID then
  begin
    InstallTesseract := OcrPage.Values[1];

    if not InstallTesseract then
    begin
      if MsgBox(
          'You have unchecked Tesseract OCR.' + #13#10#13#10 +
          'Tesseract is used as a backup when Windows OCR is unavailable.' + #13#10 +
          'Other applications on this system may also depend on Tesseract.' + #13#10#13#10 +
          'If a bundled copy was installed previously, it will be removed.' + #13#10#13#10 +
          'Are you sure you want to skip Tesseract installation?',
          mbConfirmation, MB_YESNO) = IDNO then
      begin
        OcrPage.Values[1] := True;
        InstallTesseract   := True;
      end;
    end;
  end;
end;

// ---------------------------------------------------------------------------
// CurPageChanged -- nothing needed at this time
// ---------------------------------------------------------------------------
procedure CurPageChanged(CurPageID: Integer);
begin
  // Tesseract is bundled; no dynamic page changes required.
end;

// ---------------------------------------------------------------------------
// CurStepChanged -- pre-install cleanup + post-install downloads/OCR setup
// ---------------------------------------------------------------------------
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode:  Integer;
  StepTotal:   Integer;
  StepCurrent: Integer;
  InstTypeStr: String;
begin
  // ssInstall fires before file extraction -- remove old bundled Tesseract
  // if the user opted out on an upgrade so the directory does not linger.
  if CurStep = ssInstall then
  begin
    if not InstallTesseract then
    begin
      if DirExists(ExpandConstant('{app}\tesseract')) then
        DelTree(ExpandConstant('{app}\tesseract'), True, True, True);
    end;
  end;

  if CurStep = ssPostInstall then
  begin
    // Count the steps that will actually run (for "Step X of Y" labels)
    StepTotal := 0;
    if IsFullInstall and not BundleDirExists('argos-bundle') then
      StepTotal := StepTotal + 1;
    if WantsWindowsOcr and not WinOcrAvailable then
      StepTotal := StepTotal + 1;
    if StepTotal = 0 then
      StepTotal := 1;  // avoid divide-by-zero; no visible steps needed
    StepCurrent := 0;

    // ----------------------------------------------------------------
    // Step: Argos translation model (Full install only, not pre-bundled)
    // ----------------------------------------------------------------
    if IsFullInstall and not BundleDirExists('argos-bundle') then
    begin
      StepCurrent := StepCurrent + 1;
      WizardForm.StatusLabel.Caption :=
        'Step ' + IntToStr(StepCurrent) + ' of ' + IntToStr(StepTotal) +
        ': Downloading offline translation model (~50-100 MB)...';
      WizardForm.FilenameLabel.Caption :=
        'A console window shows download progress. Please wait.';
      WizardForm.Update();

      Exec('powershell.exe',
        '-ExecutionPolicy Bypass' +
        ' -File "' + ExpandConstant('{app}\download_packs.ps1') + '"' +
        ' "' + ExpandConstant('{app}') + '"',
        ExpandConstant('{app}'),
        SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode);

      if ResultCode = 0 then
      begin
        ArgosInstalled := True;
        WizardForm.StatusLabel.Caption :=
          'Step ' + IntToStr(StepCurrent) + ' of ' + IntToStr(StepTotal) +
          ': Translation model installed successfully.';
      end
      else
      begin
        WizardForm.StatusLabel.Caption :=
          'Step ' + IntToStr(StepCurrent) + ' of ' + IntToStr(StepTotal) +
          ': Translation model download failed (code ' + IntToStr(ResultCode) + ').';
        MsgBox(
          'Translation model download failed (exit code ' + IntToStr(ResultCode) + ').' + #13#10 +
          'The app still works for dictionary and pinyin lookups.' + #13#10 +
          'To retry, run download_packs.ps1 from the install folder.',
          mbInformation, MB_OK);
      end;
      WizardForm.FilenameLabel.Caption := '';
      WizardForm.Update();
    end
    else if IsFullInstall then
      ArgosInstalled := True;  // already bundled -- counts as installed

    // ----------------------------------------------------------------
    // Step: Windows OCR
    // ----------------------------------------------------------------
    if WantsWindowsOcr then
    begin
      if WinOcrAvailable then
      begin
        // Chinese language pack already installed -- nothing to do
        WinOcrInstalled := True;
        WizardForm.StatusLabel.Caption :=
          'Windows OCR: Chinese already enabled -- no action needed.';
        WizardForm.Update();
      end
      else
      begin
        StepCurrent := StepCurrent + 1;
        WizardForm.StatusLabel.Caption :=
          'Step ' + IntToStr(StepCurrent) + ' of ' + IntToStr(StepTotal) +
          ': Configuring Windows OCR (administrator required)...';
        WizardForm.FilenameLabel.Caption :=
          'Language packs download via Windows Update -- can take 30+ minutes on slow connections.';
        WizardForm.Update();

        if MsgBox(
            'Windows OCR Chinese language support requires administrator rights.' + #13#10#13#10 +
            'After the UAC prompt, Windows will download and install the language' + #13#10 +
            'pack in the background. This can take 30 minutes or more on slower' + #13#10 +
            'connections, or longer if other Windows updates are also queued.' + #13#10#13#10 +
            'Click OK to proceed (one UAC prompt), or Cancel to configure later' + #13#10 +
            'via the app Preferences.',
            mbConfirmation, MB_OKCANCEL) = IDOK then
        begin
          ShellExec('runas', 'powershell.exe',
            '-ExecutionPolicy Bypass -WindowStyle Normal' +
            ' -File "' + ExpandConstant('{app}\setup_ocr_elevated.ps1') + '"',
            ExpandConstant('{app}'),
            SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode);
          WinOcrInstalled := (ResultCode = 0);
          WizardForm.StatusLabel.Caption :=
            'Step ' + IntToStr(StepCurrent) + ' of ' + IntToStr(StepTotal) +
            ': Windows OCR setup complete.';
        end
        else
        begin
          WizardForm.StatusLabel.Caption :=
            'Step ' + IntToStr(StepCurrent) + ' of ' + IntToStr(StepTotal) +
            ': Windows OCR skipped -- configure later via Preferences.';
        end;

        WizardForm.FilenameLabel.Caption := '';
        WizardForm.Update();
      end;
    end;

    // ----------------------------------------------------------------
    // Persist install state
    // ----------------------------------------------------------------
    if IsFullInstall then
      InstTypeStr := 'full'
    else
      InstTypeStr := 'lite';

    WriteInstallState(InstTypeStr, ArgosInstalled, WinOcrInstalled, InstallTesseract);

    WizardForm.StatusLabel.Caption := 'Installation complete.';
    WizardForm.FilenameLabel.Caption := '';
    WizardForm.Update();
  end;
end;

// ---------------------------------------------------------------------------
// UpdateReadyMemo -- "Ready to Install" summary page
// ---------------------------------------------------------------------------
function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo,
  MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
var
  InstallType: String;
  OcrSummary:  String;
begin
  if IsFullInstall then
    InstallType := 'Full install -- dictionary, pinyin + offline sentence translation'
  else
    InstallType := 'Lite install -- dictionary and pinyin only';

  OcrSummary := '';
  if OcrPage.Values[0] then
  begin
    if WinOcrAvailable then
      OcrSummary := OcrSummary + Space + 'Windows OCR (Chinese already enabled)' + NewLine
    else
      OcrSummary := OcrSummary + Space + 'Windows OCR (will install -- requires admin prompt)' + NewLine;
  end;
  if OcrPage.Values[1] then
    OcrSummary := OcrSummary + Space + 'Tesseract OCR (bundled, ~150 MB)' + NewLine;
  if OcrSummary = '' then
    OcrSummary := Space + '(no OCR engines selected)' + NewLine;

  Result :=
    MemoDirInfo + NewLine + NewLine +
    'Install type:' + NewLine +
    Space + InstallType + NewLine + NewLine +
    'OCR features:' + NewLine +
    OcrSummary + NewLine +
    MemoTasksInfo;
end;
