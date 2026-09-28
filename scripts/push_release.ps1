param(
    [string]$Branch = "main",
    [string]$Tag = "v0.2.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Pusher = Join-Path $Root "tools\push_release_via_api.py"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment not found: $Python"
}
if (-not $env:GITHUB_TOKEN) {
    throw "GITHUB_TOKEN is not set. Create a fine-grained token with Contents: Read and write, set it for this PowerShell session, and rerun."
}

Push-Location $Root
try {
    & $Python $Pusher `
        --repo "scu08265/ai-security-intelligence-workbench" `
        --branch $Branch `
        --tag $Tag
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub API release push failed."
    }
    Write-Host "Release pushed successfully through the GitHub API."
}
finally {
    Pop-Location
}
