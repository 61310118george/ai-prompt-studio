param([Parameter(Mandatory=$true)][string]$Archive)
$ErrorActionPreference = "Stop"
$TestRoot = Join-Path ([IO.Path]::GetTempPath()) ("prompt-download-" + [guid]::NewGuid())
$PreviousDataDir = $env:AI_PROMPT_STUDIO_DATA_DIR
New-Item -ItemType Directory -Path $TestRoot | Out-Null
try {
    $Downloaded = Join-Path $TestRoot "download.zip"
    Copy-Item $Archive $Downloaded
    Set-Content -Path $Downloaded -Stream Zone.Identifier -Value "[ZoneTransfer]`r`nZoneId=3" -Encoding ASCII
    $Extracted = Join-Path $TestRoot "extracted"
    Expand-Archive $Downloaded -DestinationPath $Extracted
    $Exe = Join-Path $Extracted "AI Prompt Studio Next.exe"
    # Expand-Archive does not always propagate MOTW; explicitly reproduce Explorer's metadata.
    Set-Content -Path $Exe -Stream Zone.Identifier -Value "[ZoneTransfer]`r`nZoneId=3" -Encoding ASCII
    $Report = Join-Path $TestRoot "desktop-result.json"
    $env:AI_PROMPT_STUDIO_DATA_DIR = Join-Path $TestRoot "isolated-data"
    $Process = Start-Process -FilePath $Exe -ArgumentList @("--desktop-self-test", "`"$Report`"", "--test-report", "`"$Report`"") -PassThru
    if (-not $Process.WaitForExit(120000)) {
        # Kill only this test process tree, never a user's application.
        taskkill /PID $Process.Id /T /F | Out-Null
        throw "Downloaded application did not finish native-window validation within 120 seconds."
    }
    if (Test-Path $Report) { Get-Content $Report -Raw | Write-Host }
    $Process.Refresh()
    if ($Process.ExitCode -ne 0 -or -not (Test-Path $Report)) {
        throw "Downloaded application failed to open its native window (exit $($Process.ExitCode))."
    }
    $Result = Get-Content $Report -Raw | ConvertFrom-Json
    if (-not $Result.passed) { throw "Native-window validation failed: $($Result.error)" }
    Write-Host "Downloaded ZIP with ZoneId=3: native window and document tabs passed."
} finally {
    $env:AI_PROMPT_STUDIO_DATA_DIR = $PreviousDataDir
    Remove-Item $TestRoot -Recurse -Force -ErrorAction SilentlyContinue
}
