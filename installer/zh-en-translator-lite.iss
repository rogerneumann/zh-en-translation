; Inno Setup 6 script for zh-en-translator -- LITE installer
;
; The Lite installer ships without the bundled Argos translation model (~100 MB)
; and without a bundled Tesseract binary. All heavy components can be downloaded
; post-install via the wizard options below -- same user experience, smaller download.
;
; Estimated Lite installer size: ~100 MB (vs ~175 MB for the full installer).
;
; Build: iscc installer\zh-en-translator-lite.iss
; (build.ps1 compiles this automatically alongside the full installer)

#define MyAppName      "zh-en-translator"
#define MyAppVersion   "2026.05.04.2"
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
DisableDirPage=no
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=zh-en-translator-v{#MyAppVersion}-lite-setup
LicenseFile=..\LICENSE
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
WizardStyle=modern
SetupIconFile=icon.ico
WizardImageFile=wizard_large.bmp
WizardSmallImageFile=wizard_small.bmp
InfoAfterFile=after_install.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "Launch {#MyAppName} when Windows starts"; GroupDescription: "Windows startup:"; Flags: checkedonce

[Files]
; PyInstaller onedir output -- entire dist\zh-en-translator\ folder
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Post-install helper scripts (download_packs.ps1 used when Full install is selected)
Source: "download_packs.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "setup_elevated.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "install_tesseract.ps1"; DestDir: "{app}"; Flags: ignoreversion
; CC-CEDICT bundled (only 6 MB -- always included even in Lite)
Source: "cedict-bundle\cedict_ts.u8"; DestDir: "{userappdata}\zh-en-translator"; Flags: ignoreversion; Check: BundleExists('cedict-bundle\cedict_ts.u8')
; NOTE: argos-bundle and tesseract-bundle intentionally omitted from Lite installer.
; When user selects Full install, download_packs.ps1 fetches the Argos model (~100 MB).
; When user enables Tesseract on the OCR page, setup_elevated.ps1 downloads it.

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#MyAppName}"; \
  ValueData: """{app}\{#MyAppExeName}"""; \
  Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
  Flags: postinstall nowait skipifsilent

[UninstallRun]
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
  WinOcrAvailable:    Boolean;
  PreviousInstallType: String;
  InstallTesseract:    Boolean;
  ArgosInstalled:      Boolean;
  WinOcrInstalled:     Boolean;

// ---------------------------------------------------------------------------
// Bundle presence checks
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
// Tesseract install gate -- no bundle in Lite, so this always returns False.
// Tesseract is downloaded via setup_elevated.ps1 when user enables it on OCR page.
// ---------------------------------------------------------------------------
function ShouldInstallTesseract: Boolean;
begin
  Result := InstallTesseract and BundleExists('tesseract-bundle\tesseract.exe');
end;

// ---------------------------------------------------------------------------
// Install type helpers
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
// Check whether Windows OCR has a Chinese recogniser installed.
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
  Result := True;
  if RegQueryStringValue(HKCU, 'Software\zh-en-translator', ValueName, Value) then
    Result := (LowerCase(Value) = 'true');
end;

// ---------------------------------------------------------------------------
// Write install state to registry and %APPDATA%\install_state.toml
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

  RegWriteStringValue(HKCU, 'Software\zh-en-translator', 'InstallType',         InstType);
  RegWriteStringValue(HKCU, 'Software\zh-en-translator', 'InstallVersion',      '{#MyAppVersion}');
  RegWriteStringValue(HKCU, 'Software\zh-en-translator', 'InstallDir',          ExpandConstant('{app}'));
  RegWriteStringValue(HKCU, 'Software\zh-en-translator', 'ArgosInstalled',      SArgos);
  RegWriteStringValue(HKCU, 'Software\zh-en-translator', 'WinOcrInstalled',     SWinOcr);
  RegWriteStringValue(HKCU, 'Software\zh-en-translator', 'TesseractInstalled',  STess);

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
// Detect whether app is already running
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
// InitializeWizard -- build custom pages
// ---------------------------------------------------------------------------
procedure InitializeWizard;
var
  PrevNote:    String;
  OcrWinNote:  String;
  PrevWinOcr:  Boolean;
  PrevTess:    Boolean;
begin
  WinOcrAvailable     := CheckWindowsOcrAvailable();
  PreviousInstallType := GetPreviousInstallType();

  InstallTesseract := False;
  ArgosInstalled   := False;
  WinOcrInstalled  := WinOcrAvailable;

  if PreviousInstallType = 'full' then
    PrevNote :=
      'Previous Full installation detected -- options pre-selected to match.' + #13#10 +
      'Change any option below to upgrade or switch install type.'
  else if PreviousInstallType = 'lite' then
    PrevNote :=
      'Previous Lite installation detected -- options pre-selected to match.' + #13#10 +
      'Change any option below to upgrade or switch install type.'
  else
    PrevNote := 'Select how much to install now. You can add more components later.';

  // ---- Install Type page ----
  InstallTypePage := CreateInputOptionPage(
    wpSelectDir,
    'Installation Type',
    'Choose what to install',
    PrevNote,
    True,
    False
  );
  InstallTypePage.Add(
    'Full install -- dictionary, pinyin + offline sentence translation' + #13#10 +
    '    The Argos zh' + #226#134#146 + 'en model (~100 MB) will download automatically' + #13#10 +
    '    after installation. An internet connection is required for this step.'
  );
  InstallTypePage.Add(
    'Lite install  [recommended -- no downloads required]' + #13#10 +
    '    Dictionary lookup and pinyin only. Starts instantly with no extra downloads.' + #13#10 +
    '    Add offline sentence translation any time: re-run this installer and select Full,' + #13#10 +
    '    or enable cloud translation (Azure / DeepL) in Preferences ' + #226#128#186 + ' Cloud.'
  );

  // Pre-select based on previous install; default to Lite for new installs
  if PreviousInstallType = 'full' then
    InstallTypePage.Values[0] := True
  else
    InstallTypePage.Values[1] := True;

  // ---- OCR Options page ----
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
    'Select which OCR engines to install. All options require a download or admin action:',
    False,
    False
  );
  OcrPage.Add(OcrWinNote);
  OcrPage.Add(
    'Tesseract OCR  [will download ~150 MB + admin prompt]' + #13#10 +
    '    Backup OCR engine used when Windows OCR is unavailable.' + #13#10 +
    '    Downloads and installs Tesseract via an administrator (UAC) prompt.' + #13#10 +
    '    Skip this if you plan to use Windows OCR (above) or cloud translation only.'
  );

  // Pre-select from previous install; default to Windows OCR only for new Lite installs
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
    OcrPage.Values[0] := True;   // Windows OCR default on
    OcrPage.Values[1] := False;  // Tesseract default off in Lite (avoids surprise 150 MB download)
  end;
end;

// ---------------------------------------------------------------------------
// NextButtonClick -- capture Tesseract choice
// ---------------------------------------------------------------------------
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if CurPageID = OcrPage.ID then
  begin
    InstallTesseract := OcrPage.Values[1];

    if InstallTesseract then
    begin
      if MsgBox(
          'Tesseract OCR will be downloaded (~150 MB) and installed.' + #13#10#13#10 +
          'An administrator (UAC) prompt will appear after installation completes.' + #13#10#13#10 +
          'Continue?',
          mbConfirmation, MB_YESNO) = IDNO then
      begin
        OcrPage.Values[1] := False;
        InstallTesseract   := False;
      end;
    end;
  end;
end;

// ---------------------------------------------------------------------------
// CurPageChanged -- nothing needed
// ---------------------------------------------------------------------------
procedure CurPageChanged(CurPageID: Integer);
begin
end;

// ---------------------------------------------------------------------------
// CurStepChanged -- post-install downloads and OCR setup
// ---------------------------------------------------------------------------
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode:  Integer;
  StepTotal:   Integer;
  StepCurrent: Integer;
  InstTypeStr: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Count steps: Argos download (if Full) + Windows OCR (if not already ready)
    StepTotal := 0;
    if IsFullInstall and not BundleDirExists('argos-bundle') then
      StepTotal := StepTotal + 1;
    if WantsWindowsOcr and not WinOcrAvailable then
      StepTotal := StepTotal + 1;
    if InstallTesseract then
      StepTotal := StepTotal + 1;
    if StepTotal = 0 then
      StepTotal := 1;
    StepCurrent := 0;

    // ----------------------------------------------------------------
    // Step: Argos translation model (Full install, not pre-bundled)
    // ----------------------------------------------------------------
    if IsFullInstall and not BundleDirExists('argos-bundle') then
    begin
      StepCurrent := StepCurrent + 1;
      WizardForm.StatusLabel.Caption :=
        'Step ' + IntToStr(StepCurrent) + ' of ' + IntToStr(StepTotal) +
        ': Downloading offline translation model (~100 MB)...';
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
          'To retry: re-run this installer and select Full install,' + #13#10 +
          'or enable cloud translation in Preferences ' + #226#128#186 + ' Cloud.',
          mbInformation, MB_OK);
      end;
      WizardForm.FilenameLabel.Caption := '';
      WizardForm.Update();
    end;

    // ----------------------------------------------------------------
    // Step: Windows OCR
    // ----------------------------------------------------------------
    if WantsWindowsOcr then
    begin
      if WinOcrAvailable then
      begin
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
            ' -File "' + ExpandConstant('{app}\setup_elevated.ps1') + '"',
            ExpandConstant('{app}'),
            SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode);
          WinOcrInstalled := (ResultCode = 0);
          WizardForm.StatusLabel.Caption :=
            'Step ' + IntToStr(StepCurrent) + ' of ' + IntToStr(StepTotal) +
            ': Windows OCR setup complete.';
        end
        else
          WizardForm.StatusLabel.Caption :=
            'Step ' + IntToStr(StepCurrent) + ' of ' + IntToStr(StepTotal) +
            ': Windows OCR skipped -- configure later via Preferences.';

        WizardForm.FilenameLabel.Caption := '';
        WizardForm.Update();
      end;
    end;

    // ----------------------------------------------------------------
    // Step: Tesseract (download via setup_elevated.ps1)
    // ----------------------------------------------------------------
    if InstallTesseract then
    begin
      StepCurrent := StepCurrent + 1;
      WizardForm.StatusLabel.Caption :=
        'Step ' + IntToStr(StepCurrent) + ' of ' + IntToStr(StepTotal) +
        ': Installing Tesseract OCR (administrator required)...';
      WizardForm.FilenameLabel.Caption :=
        'Downloading Tesseract (~150 MB). An admin (UAC) prompt will appear.';
      WizardForm.Update();

      ShellExec('runas', 'powershell.exe',
        '-ExecutionPolicy Bypass -WindowStyle Normal' +
        ' -File "' + ExpandConstant('{app}\setup_elevated.ps1') + '"',
        ExpandConstant('{app}'),
        SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode);

      WizardForm.StatusLabel.Caption :=
        'Step ' + IntToStr(StepCurrent) + ' of ' + IntToStr(StepTotal) +
        ': Tesseract setup complete.';
      WizardForm.FilenameLabel.Caption := '';
      WizardForm.Update();
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
    InstallType := 'Full install -- dictionary, pinyin + offline translation (downloads ~100 MB)'
  else
    InstallType := 'Lite install -- dictionary and pinyin only, no downloads';

  OcrSummary := '';
  if OcrPage.Values[0] then
  begin
    if WinOcrAvailable then
      OcrSummary := OcrSummary + Space + 'Windows OCR (Chinese already enabled)' + NewLine
    else
      OcrSummary := OcrSummary + Space + 'Windows OCR (will install -- requires admin prompt)' + NewLine;
  end;
  if OcrPage.Values[1] then
    OcrSummary := OcrSummary + Space + 'Tesseract OCR (will download ~150 MB -- requires admin prompt)' + NewLine;
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
