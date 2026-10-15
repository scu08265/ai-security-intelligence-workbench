param(
    [string]$TaskId = "daily-disposition-queue",
    [string]$PlannedAt = "",
    [int]$OverdueHours = 24,
    [int]$RecheckDueHours = 24
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PythonCandidates = @(
    (Join-Path $Root ".venv\Scripts\python.exe"),
    (Join-Path (Split-Path -Parent $Root) ".venv\Scripts\python.exe")
)
$Python = $PythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$LogDir = Join-Path $Root "artifacts\logs"
$LogPath = Join-Path $LogDir "disposition-ops.log"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment not found. Checked: $($PythonCandidates -join ', ')."
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
if (-not $PlannedAt) {
    $PlannedAt = [DateTimeOffset]::new(
        [DateTime]::Today.Add([TimeSpan]::Parse("09:00")),
        [TimeZoneInfo]::Local.GetUtcOffset([DateTime]::Today.Add([TimeSpan]::Parse("09:00")))
    ).ToString("o")
}

$Output = & $Python (Join-Path $Root "tools\run_disposition_ops.py") `
    --task-id $TaskId `
    --planned-at $PlannedAt `
    --trigger scheduled `
    --overdue-hours $OverdueHours `
    --recheck-due-hours $RecheckDueHours 2>&1
$ExitCode = $LASTEXITCODE
$Output | Tee-Object -FilePath $LogPath -Append
exit $ExitCode
