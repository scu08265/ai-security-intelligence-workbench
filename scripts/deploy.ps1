param(
    [string]$Version = "0.2.0",
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or not on PATH."
}

Push-Location $Root
try {
    $env:APP_VERSION = $Version
    docker compose build
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose build failed."
    }
    docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose startup failed."
    }
    & (Join-Path $PSScriptRoot "check_health.ps1") -BaseUrl $BaseUrl
}
finally {
    Pop-Location
}
