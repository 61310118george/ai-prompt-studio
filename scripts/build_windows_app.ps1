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
& $PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $AppName `
    --collect-all tiktoken `
    --paths src `
    --add-data "web-ui;web-ui" `
    --add-data "resources;resources" `
    run_app.py

$Executable = Join-Path $RootDir "dist\$AppName\$AppName.exe"
& $Executable --self-test

$ReleaseDir = Join-Path $RootDir "release"
$Archive = Join-Path $ReleaseDir "$AppName $ReleaseVersion Windows x64.zip"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
if (Test-Path $Archive) {
    Remove-Item $Archive -Force
}
Compress-Archive -Path (Join-Path $RootDir "dist\$AppName") -DestinationPath $Archive

Write-Host "Built: $Executable"
Write-Host "Packaged: $Archive"
