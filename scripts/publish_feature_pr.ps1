param(
    [string]$Branch = "feat/a-scheduled-evidence-20261002",
    [string]$Base = "main",
    [string]$Title = "feat: add real scheduled-run evidence and latency denominator",
    [string]$BodyFile = "docs\PR_A_SCHEDULED_EVIDENCE.md"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Git = "D:\Git\cmd\git.exe"
$Repo = "scu08265/ai-security-intelligence-workbench"
$ResultPath = Join-Path $Root "outputs\publish-feature-pr-result.json"

function Get-GitHubTokenFromCredentialManager {
    $credentialInput = "protocol=https`nhost=github.com`n`n"
    $lines = $credentialInput | & $Git credential fill 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    $passwordLine = $lines |
        Where-Object { $_ -match "^password=" } |
        Select-Object -Last 1
    if (-not $passwordLine) {
        return $null
    }
    return $passwordLine.Substring("password=".Length)
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment not found: $Python"
}
if (-not (Test-Path -LiteralPath $Git)) {
    $Git = (Get-Command git -ErrorAction Stop).Source
}

$gitProxy = (& $Git config --get "http.https://github.com/.proxy" 2>$null | Select-Object -First 1)
if ($gitProxy) {
    if (-not $env:HTTPS_PROXY) { $env:HTTPS_PROXY = $gitProxy }
    if (-not $env:HTTP_PROXY) { $env:HTTP_PROXY = $gitProxy }
}
if (-not $env:GITHUB_TOKEN) {
    $env:GITHUB_TOKEN = Get-GitHubTokenFromCredentialManager
}
if (-not $env:GITHUB_TOKEN) {
    throw "No GitHub API token is available. Set GITHUB_TOKEN or sign in with Git Credential Manager."
}

$baseSha = (& $Git -c "safe.directory=*" -C $Root rev-parse "origin/$Base").Trim()
$pushOutput = & $Python (Join-Path $Root "tools\push_release_via_api.py") `
    --repo $Repo `
    --branch $Branch `
    --full-tree `
    --base-commit $baseSha
if ($LASTEXITCODE -ne 0) {
    throw "GitHub API branch push failed."
}
$pushResult = $pushOutput | ConvertFrom-Json
$remoteSha = $pushResult.commit

$prOutput = & $Python (Join-Path $Root "tools\create_pull_request.py") `
    --repo $Repo `
    --head $Branch `
    --base $Base `
    --title $Title `
    --body-file (Join-Path $Root $BodyFile)
if ($LASTEXITCODE -ne 0) {
    throw "GitHub pull request creation failed."
}
$prResult = $prOutput | ConvertFrom-Json

$ciOutput = & $Python (Join-Path $Root "tools\record_ci_validation.py") `
    --repo $Repo `
    --branch $Branch `
    --head-sha $remoteSha `
    --wait-seconds 900
$ciExitCode = $LASTEXITCODE

$result = [ordered]@{
    branch = $Branch
    base = $Base
    remote_sha = $remoteSha
    pull_request = $prResult
    ci_exit_code = $ciExitCode
    ci_result = ($ciOutput | ConvertFrom-Json)
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ResultPath) | Out-Null
$result | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $ResultPath -Encoding utf8
Write-Host "PR result: $ResultPath"
if ($ciExitCode -ne 0) {
    throw "CI validation failed or was not green."
}
Write-Host "Feature branch and PR published with green CI."
