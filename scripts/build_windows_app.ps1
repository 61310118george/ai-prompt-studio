$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RootDir = Split-Path -Parent $PSScriptRoot
$ReleaseVersion = "V1.0"
$AppName = "AI Prompt Studio Next"
$VenvDir = Join-Path $RootDir ".venv-windows"
$Python = Join-Path $VenvDir "Scripts\python.exe"
$PyInstaller = Join-Path $VenvDir "Scripts\pyinstaller.exe"

if ($env:OS -ne "Windows_NT") {
    throw "Windows build must run on Windows. PyInstaller does not cross-compile."
}

function Assert-AppClosed {
    if (Get-Process -Name $AppName -ErrorAction SilentlyContinue) {
        throw "Save your work and exit AI Prompt Studio Next before building. Never replace a running app."
    }
}
Assert-AppClosed

Set-Location $RootDir
if (-not (Test-Path $Python)) {
    py -3.12 -m venv $VenvDir
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt
& $Python -m pip install pyinstaller

if (-not (Test-Path "resources\tokenizers\o200k_base.json") -or -not (Test-Path "resources\tokenizers\cl100k_base.json")) {
    & $Python scripts\prepare_tokenizers.py
}

$env:PYTHONPATH = "src"
$SslPolicy = & $Python -c 'import ssl; from pathlib import Path; print(Path(ssl.__file__).with_name("codex-rejected-cas.pem"))'
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect Python TLS runtime." }
$SslData = @()
if (Test-Path $SslPolicy) {
    $SslData = @("--add-data", "${SslPolicy};.")
}
Assert-AppClosed
& $PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name $AppName `
    --collect-all tiktoken `
    --collect-all keyring `
    --paths src `
    --add-data "web-ui;web-ui" `
    --add-data "resources;resources" `
    @SslData `
    run_app.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$Executable = Join-Path $RootDir "dist\$AppName.exe"
$CheckProcess = Start-Process -FilePath $Executable -ArgumentList "--self-test" -Wait -PassThru
if ($CheckProcess.ExitCode -ne 0) { throw "Packaged app self-test failed; archive not created." }

$ReleaseDir = Join-Path $RootDir "release"
$Archive = Join-Path $ReleaseDir "$AppName $ReleaseVersion Windows x64.zip"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
if (Test-Path $Archive) {
    Remove-Item $Archive -Force
}
Compress-Archive -Path $Executable -DestinationPath $Archive

# Test the delivered ZIP, including the internet-zone metadata Explorer propagates.
& (Join-Path $PSScriptRoot "test_windows_download.ps1") -Archive $Archive

Write-Host "Built: $Executable"
Write-Host "Packaged: $Archive"
