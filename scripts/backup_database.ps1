param(
    [string]$BackupDir = "artifacts\backups",
    [int]$KeepDays = 14
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$DataDir = Join-Path $Root "data"
$DbPath = Join-Path $DataDir "intel.sqlite"
$BackupRoot = Join-Path $Root $BackupDir

if (-not (Test-Path -LiteralPath $DbPath)) {
    throw "Database not found: $DbPath"
}

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Target = Join-Path $BackupRoot "intel-$Stamp.sqlite"

# SQLite's online backup API creates a consistent copy while the service is running.
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment not found: $Python"
}

& $Python -c "import sqlite3,sys; src=sqlite3.connect(sys.argv[1]); dst=sqlite3.connect(sys.argv[2]); src.backup(dst); dst.close(); src.close()" $DbPath $Target
if ($LASTEXITCODE -ne 0) {
    throw "Database backup failed"
}

$Cutoff = (Get-Date).AddDays(-$KeepDays)
Get-ChildItem -LiteralPath $BackupRoot -Filter "intel-*.sqlite" |
    Where-Object { $_.LastWriteTime -lt $Cutoff } |
    Remove-Item -Force

Write-Host "Backup created: $Target"
