# Code Signing Integration Plan

This plan outlines the steps to integrate code signing into the `zh-en-translator` build process to prevent Windows SmartScreen and other security warnings.

## Objective
Enable automated code signing for:
1. The main application executable and its dependencies (DLLs).
2. The final Windows installer (`.exe`).
3. The portable ZIP archive (by signing the contents before zipping).

## Proposed Changes

### 1. Update `installer\build.ps1`
*   Add parameters for signing:
    *   `$SignThumbprint`: SHA1 thumbprint of the certificate in the Windows Certificate Store.
    *   `$CertFile`: Path to a `.pfx` or `.p12` certificate file.
    *   `$CertPassword`: Password for the certificate file.
    *   `$TimestampUrl`: URL of the timestamp server (defaults to DigiCert).
*   Add a `Find-SignTool` helper function to locate `signtool.exe` in the Windows SDK.
*   Add a `Sign-Files` helper function to sign a list of files with retries (timestamping can sometimes fail).
*   Integrate signing into the build flow:
    *   Sign the PyInstaller bundle in `dist\zh-en-translator\` after it's created.
    *   Pass signing instructions to the Inno Setup compiler (`iscc.exe`).

### 2. Update `installer\zh-en-translator.iss`
*   Configure the `SignTool` setting in the `[Setup]` section to allow `iscc.exe` to sign the generated installer.

### 3. Documentation
*   Provide a guide on how to:
    *   Obtain a Code Signing Certificate (Standard vs. EV).
    *   Install the certificate or use a PFX file.
    *   Run the build script with signing enabled.

## Implementation Details

### Build Script Logic (PowerShell)
```powershell
function Sign-Files {
    param([string[]]$Files)
    if (-not $SignTool) { $SignTool = Find-SignTool }
    
    $BaseArgs = @("sign", "/v")
    if ($SignThumbprint) {
        $BaseArgs += "/sha1", $SignThumbprint
    } elseif ($CertFile) {
        $BaseArgs += "/f", $CertFile, "/p", $CertPassword
    } else {
        return
    }
    
    $BaseArgs += "/tr", $TimestampUrl, "/td", "sha256"

    foreach ($f in $Files) {
        Write-Host "    Signing: $f" -ForegroundColor Gray
        & $SignTool @BaseArgs $f
    }
}
```

### Inno Setup Logic
Add to `[Setup]`:
```pascal
SignTool=signtool $f
```
And call `iscc` with:
```powershell
& $Iscc /S"signtool=$SignTool sign /sha1 $SignThumbprint /tr $TimestampUrl /td sha256 /v `$f" $IssFile
```

## Verification Plan
1.  **Dry Run**: Ensure the build still works without signing parameters.
2.  **Mock Signing**: Test the signing logic with a self-signed certificate (for development/test purposes).
3.  **Final Verification**: Check digital signatures of the produced `.exe` and `.dll` files using `File -> Properties -> Digital Signatures`.
