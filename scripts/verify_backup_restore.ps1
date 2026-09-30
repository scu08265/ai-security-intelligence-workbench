param(
    [string]$OutputPath = "reports\backup-restore-validation.json"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$BackupScript = Join-Path $PSScriptRoot "backup_database.ps1"
$RestoreScript = Join-Path $PSScriptRoot "restore_database.ps1"
$BackupDir = Join-Path $Root "artifacts\backups"
$TestRelative = "artifacts\restore-test\intel-restored-$(Get-Date -Format 'yyyyMMdd-HHmmss').sqlite"
$TestDb = Join-Path $Root $TestRelative
$Output = Join-Path $Root $OutputPath

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment not found: $Python"
}

& $BackupScript -KeepDays 14
$Backup = Get-ChildItem -LiteralPath $BackupDir -Filter "intel-*.sqlite" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $Backup) {
    throw "No backup file was created."
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $TestDb) | Out-Null
& $RestoreScript -BackupPath $Backup.FullName -TargetPath $TestRelative

$Evidence = & $Python -c @"
import json, sqlite3, sys
source = sqlite3.connect(sys.argv[1])
restored = sqlite3.connect(sys.argv[2])
integrity = restored.execute('PRAGMA integrity_check').fetchone()[0]
source_events = source.execute('SELECT COUNT(*) FROM events').fetchone()[0]
restored_events = restored.execute('SELECT COUNT(*) FROM events').fetchone()[0]
source_assets = source.execute('SELECT COUNT(*) FROM assets').fetchone()[0]
restored_assets = restored.execute('SELECT COUNT(*) FROM assets').fetchone()[0]
print(json.dumps({
    'integrity_check': integrity,
    'source_events': source_events,
    'restored_events': restored_events,
    'source_assets': source_assets,
    'restored_assets': restored_assets,
    'counts_match': source_events == restored_events and source_assets == restored_assets,
}))
"@ (Join-Path $Root "data\intel.sqlite") $TestDb

$Payload = $Evidence | ConvertFrom-Json
$Payload | Add-Member -NotePropertyName version -NotePropertyValue (Get-Content -Raw (Join-Path $Root "VERSION")).Trim()
$Payload | Add-Member -NotePropertyName backup_path -NotePropertyValue $Backup.FullName
$Payload | Add-Member -NotePropertyName restored_path -NotePropertyValue $TestDb
$Payload | Add-Member -NotePropertyName generated_at -NotePropertyValue ([DateTime]::UtcNow.ToString("o"))
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Output) | Out-Null
$Payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Output -Encoding utf8
$Payload | ConvertTo-Json -Depth 5
