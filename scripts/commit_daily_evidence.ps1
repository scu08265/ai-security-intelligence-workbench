param(
    [string]$Branch = "main",
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Git = "D:\Git\cmd\git.exe"
if (-not (Test-Path -LiteralPath $Git)) {
    $Git = "git.exe"
}

$SafeRoot = $Root.Replace("\", "/")
$env:GIT_CONFIG_COUNT = "1"
$env:GIT_CONFIG_KEY_0 = "safe.directory"
$env:GIT_CONFIG_VALUE_0 = $SafeRoot

Push-Location $Root
try {
    & $Git -c http.sslBackend=openssl add -- logs/daily reports docs/screenshots CHANGELOG.md VERSION
    $Pending = & $Git diff --cached --name-only
    if (-not $Pending) {
        if ($NoPush) {
            Write-Host "No daily evidence changes to commit."
            exit 0
        }
        $env:GIT_TERMINAL_PROMPT = "0"
        & $Git -c http.sslBackend=openssl -c http.version=HTTP/1.1 push origin $Branch
        if ($LASTEXITCODE -ne 0) {
            throw "No new evidence, but existing local commits could not be pushed."
        }
        Write-Host "No new evidence; existing local commits are now pushed."
        exit 0
    }
    $Date = Get-Date -Format "yyyy-MM-dd"
    & $Git commit -m "chore(evidence): update daily log $Date"
    if ($LASTEXITCODE -ne 0) {
        throw "Git commit failed"
    }
    if (-not $NoPush) {
        $Python = Join-Path $Root ".venv\Scripts\python.exe"
        $Pusher = Join-Path $Root "tools\push_release_via_api.py"
        if (-not $env:GITHUB_TOKEN) {
            throw "Daily log committed locally, but GITHUB_TOKEN is not set for API push."
        }
        & $Python $Pusher `
            --repo "scu08265/ai-security-intelligence-workbench" `
            --branch $Branch `
            --full-tree
        if ($LASTEXITCODE -ne 0) {
            throw "Daily log committed locally, but GitHub API push failed."
        }
    }
    Write-Host $(if ($NoPush) { "Daily evidence committed locally." } else { "Daily evidence committed and pushed." })
}
finally {
    Pop-Location
}
