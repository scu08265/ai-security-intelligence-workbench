param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BackupScript = Join-Path $PSScriptRoot "backup_database.ps1"
$HealthScript = Join-Path $PSScriptRoot "check_health.ps1"
$Image = "ai-security-intelligence-workbench:$Version"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or not on PATH."
}

Push-Location $Root
try {
    Write-Host "Creating a safety backup before rollback..."
    & $BackupScript

    & docker image inspect $Image *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Rollback image not found: $Image. Build or restore that image version first."
    }

    docker compose down
    $env:APP_VERSION = $Version
    docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        throw "Rollback startup failed for image $Image."
    }
    & $HealthScript -BaseUrl $BaseUrl
    Write-Host "Rollback completed. Active image: $Image"
}
finally {
    Pop-Location
}
