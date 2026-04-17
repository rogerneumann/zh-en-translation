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

[Files]
; PyInstaller onedir output — entire dist\zh-en-translator\ folder
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Post-install helper scripts
Source: "download_packs.ps1"; DestDir: "{app}"; Flags: ignoreversion

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

; 2. Launch the app after install (optional, user choice)
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
  Flags: postinstall nowait skipifsilent

[UninstallRun]
; Remove startup registry entry on uninstall (belt-and-suspenders alongside [Registry] Flags)
Filename: "reg.exe"; \
  Parameters: "delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Run"" /v ""{#MyAppName}"" /f"; \
  Flags: runhidden; RunOnceId: "RemoveStartupEntry"

[Code]
// ---------------------------------------------------------------------------
// Windows OCR availability check + Tesseract download offer
// ---------------------------------------------------------------------------

var
  OcrCheckPage: TOutputMsgWizardPage;
  TesseractPage: TOutputMsgWizardPage;
  OfferTesseract: Boolean;

// Check whether Windows.Media.Ocr is available for Chinese (Simplified)
// by shelling out to PowerShell and checking the return code.
function CheckWindowsOCRAvailable(): Boolean;
var
  TempFile: String;
  ResultCode: Integer;
  Script: String;
begin
  TempFile := ExpandConstant('{tmp}\check_ocr.ps1');
  Script := '[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null; ' +
            '$langs = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages; ' +
            '$zh = $langs | Where-Object { $_.LanguageTag -like "zh*" }; ' +
            'if ($zh) { exit 0 } else { exit 1 }';
  SaveStringToFile(TempFile, Script, False);
  Result := Exec(
    'powershell.exe',
    '-ExecutionPolicy Bypass -NonInteractive -File "' + TempFile + '"',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  ) and (ResultCode = 0);
end;

// Download and silently install Tesseract with Chinese Simplified support
procedure DownloadAndInstallTesseract();
var
  TempDir: String;
  InstallerPath: String;
  ResultCode: Integer;
  DownloadScript: String;
  ScriptPath: String;
begin
  TempDir := ExpandConstant('{tmp}');
  InstallerPath := TempDir + '\tesseract-setup.exe';
  ScriptPath := TempDir + '\download_tesseract.ps1';

  // PowerShell download script for Tesseract UB-Mannheim installer
  // Using Tesseract 5.x with chi_sim language pack
  DownloadScript :=
    '$url = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.3.3.20231005/tesseract-ocr-w64-setup-5.3.3.20231005.exe"' + #13#10 +
    '$out = "' + InstallerPath + '"' + #13#10 +
    'try {' + #13#10 +
    '  $wc = New-Object System.Net.WebClient' + #13#10 +
    '  $wc.DownloadFile($url, $out)' + #13#10 +
    '  Write-Host "Download complete"' + #13#10 +
    '  exit 0' + #13#10 +
    '} catch {' + #13#10 +
    '  Write-Host "Download failed: $_"' + #13#10 +
    '  exit 1' + #13#10 +
    '}';

  SaveStringToFile(ScriptPath, DownloadScript, False);

  WizardForm.StatusLabel.Caption := 'Downloading Tesseract OCR...';

  if Exec(
    'powershell.exe',
    '-ExecutionPolicy Bypass -NonInteractive -File "' + ScriptPath + '"',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  ) and (ResultCode = 0) then
  begin
    // Install silently: /VERYSILENT /NORESTART + select chi_sim language
    if not Exec(
      InstallerPath,
      '/VERYSILENT /NORESTART /COMPONENTS="tesseract,langdata_fast\chi_sim"',
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    ) then
    begin
      MsgBox(
        'Tesseract installer could not be launched. ' +
        'Please install Tesseract manually from:' + #13#10 +
        'https://github.com/UB-Mannheim/tesseract/wiki' + #13#10 +
        'and install the "chi_sim" language pack.',
        mbInformation, MB_OK
      );
    end;
  end
  else
  begin
    MsgBox(
      'Could not download Tesseract. Please install it manually from:' + #13#10 +
      'https://github.com/UB-Mannheim/tesseract/wiki' + #13#10 +
      #13#10 +
      'Install the "chi_sim" (Chinese Simplified) language pack during setup.',
      mbInformation, MB_OK
    );
  end;
end;

// Called after installation finishes — check OCR and optionally download Tesseract
procedure CurStepChanged(CurStep: TSetupStep);
var
  WinOCRAvailable: Boolean;
  Answer: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Check Windows OCR availability for Chinese
    WinOCRAvailable := CheckWindowsOCRAvailable();

    if not WinOCRAvailable then
    begin
      // Ask whether to download Tesseract as a fallback
      Answer := MsgBox(
        'Windows OCR does not have a Chinese language pack installed.' + #13#10 +
        #13#10 +
        'For best OCR results, install the Chinese (Simplified) language pack via:' + #13#10 +
        '  Settings > Time & Language > Language & Region > Add a language' + #13#10 +
        '  (choose "Chinese Simplified, China" or "Chinese Simplified, Singapore")' + #13#10 +
        #13#10 +
        'Alternatively, would you like to download and install Tesseract OCR (~30 MB)' + #13#10 +
        'as a fallback OCR engine?' + #13#10 +
        #13#10 +
        'Click Yes to download Tesseract, No to skip (you can install it later).',
        mbConfirmation, MB_YESNO
      );

      if Answer = IDYES then
        DownloadAndInstallTesseract();
    end;
    // If Windows OCR is available, nothing extra to do — the app will use it automatically
  end;
end;

// Provide a note on the finish page about the translation model download
function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo,
  MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := MemoDirInfo + NewLine + NewLine +
    MemoGroupInfo + NewLine + NewLine +
    MemoTasksInfo + NewLine + NewLine +
    'Note: The Argos translation model pack (~50-100 MB) will be downloaded' + NewLine +
    Space + 'automatically after installation.' + NewLine +
    Space + 'An internet connection is required on first run.';
end;
