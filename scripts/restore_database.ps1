param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$DbPath = Join-Path $Root "data\intel.sqlite"
$ResolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path

if (-not (Test-Path -LiteralPath $ResolvedBackup)) {
    throw "Backup not found: $ResolvedBackup"
}

$Safety = "$DbPath.before-restore-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
if (Test-Path -LiteralPath $DbPath) {
    Copy-Item -LiteralPath $DbPath -Destination $Safety
}
Copy-Item -LiteralPath $ResolvedBackup -Destination $DbPath -Force
Write-Host "Database restored from: $ResolvedBackup"
Write-Host "Previous database saved at: $Safety"
