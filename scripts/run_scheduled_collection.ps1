param(
    [string]$TaskId = "daily-recommended-sources",
    [string]$PlannedAt = "",
    [string]$ScheduledTime = "02:30"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$LogDir = Join-Path $Root "artifacts\logs"
$LogPath = Join-Path $LogDir "scheduled-collection.log"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment not found: $Python. Run the installation steps in docs/DOCKER_CI_GUIDE.md."
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
if (-not $PlannedAt) {
    $TimeOfDay = [TimeSpan]::Parse($ScheduledTime)
    $PlannedAt = [DateTimeOffset]::new(
        [DateTime]::Today.Add($TimeOfDay),
        [TimeZoneInfo]::Local.GetUtcOffset([DateTime]::Today.Add($TimeOfDay))
    ).ToString("o")
}

$Output = & $Python (Join-Path $Root "tools\run_scheduled_collection.py") `
    --task-id $TaskId `
    --planned-at $PlannedAt 2>&1
$ExitCode = $LASTEXITCODE
$Output | Tee-Object -FilePath $LogPath -Append
exit $ExitCode
