param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,
    [string]$TargetPath = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$DbPath = if ($TargetPath) {
    [IO.Path]::GetFullPath((Join-Path $Root $TargetPath))
} else {
    Join-Path $Root "data\intel.sqlite"
}
$ResolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path

if (-not (Test-Path -LiteralPath $ResolvedBackup)) {
    throw "Backup not found: $ResolvedBackup"
}

$Parent = Split-Path -Parent $DbPath
New-Item -ItemType Directory -Force -Path $Parent | Out-Null
$Safety = "$DbPath.before-restore-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
if (Test-Path -LiteralPath $DbPath) {
    Copy-Item -LiteralPath $DbPath -Destination $Safety
    Write-Host "Previous database saved at: $Safety"
}
Copy-Item -LiteralPath $ResolvedBackup -Destination $DbPath -Force
Write-Host "Database restored from: $ResolvedBackup"
