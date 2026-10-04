param(
    [string]$Branch = "release/v0.2.2",
    [string]$Tag = "v0.2.2",
    [int]$HostPort = 18001,
    [int]$CiWaitSeconds = 900,
    [switch]$InstallScheduledTask,
    [switch]$AllowGitFallback
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Git = "D:\Git\cmd\git.exe"
$Repo = "scu08265/ai-security-intelligence-workbench"
$ResultPath = Join-Path $Root "outputs\finalize-v0.2.2-result.json"

function Invoke-LocalGit {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $output = & $Git -c "safe.directory=*" -C $Root @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed: $($output -join ' ')"
    }
    return $output
}

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
    $GitCommand = Get-Command git -ErrorAction Stop
    $Git = $GitCommand.Source
}

$gitProxy = (& $Git config --get "http.https://github.com/.proxy" 2>$null | Select-Object -First 1)
if ($gitProxy) {
    if (-not $env:HTTPS_PROXY) {
        $env:HTTPS_PROXY = $gitProxy
    }
    if (-not $env:HTTP_PROXY) {
        $env:HTTP_PROXY = $gitProxy
    }
}

if (-not $env:GITHUB_TOKEN) {
    $credentialToken = Get-GitHubTokenFromCredentialManager
    if ($credentialToken) {
        $env:GITHUB_TOKEN = $credentialToken
    }
}

$localTagCommit = (Invoke-LocalGit rev-list -n 1 $Tag | Select-Object -First 1).Trim()
$branchCommit = (Invoke-LocalGit rev-parse $Branch | Select-Object -First 1).Trim()
if ($localTagCommit -ne $branchCommit) {
    throw "Local $Tag does not point to $Branch. Refusing to publish an inconsistent release."
}

$remoteSha = $null
if ($env:GITHUB_TOKEN) {
    $pushOutput = & $Python (Join-Path $Root "tools\push_release_via_api.py") `
        --repo $Repo `
        --branch $Branch `
        --tag $Tag `
        --sync-tag "v0.2.0" `
        --sync-tag "v0.2.1"
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub API push failed."
    }
    $pushResult = $pushOutput | ConvertFrom-Json
    $remoteSha = $pushResult.commit
} elseif ($AllowGitFallback) {
    Invoke-LocalGit push -u origin $Branch
    Invoke-LocalGit push origin $Tag
    $remoteSha = (Invoke-LocalGit rev-parse $Branch | Select-Object -First 1).Trim()
} else {
    throw (
        "No GitHub API token is available. Set GITHUB_TOKEN or sign in with " +
        "Git Credential Manager before rerunning. Git HTTPS fallback is disabled " +
        "because git-remote-https.exe crashes on this host."
    )
}

$ciOutput = & $Python (Join-Path $Root "tools\record_ci_validation.py") `
    --repo $Repo `
    --branch $Branch `
    --head-sha $remoteSha `
    --wait-seconds $CiWaitSeconds
$ciExitCode = $LASTEXITCODE

$rollbackOutput = & $Python (Join-Path $Root "tools\run_rollback_validation.py") `
    --host-port $HostPort
$rollbackExitCode = $LASTEXITCODE

$schedulerStatus = "not_requested"
if ($InstallScheduledTask) {
    & powershell -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $Root "scripts\install_windows_task.ps1") `
        -IntervalHours 1 `
        -DurationHours 24
    if ($LASTEXITCODE -ne 0) {
        throw "Windows scheduled task installation failed."
    }
    $schedulerStatus = "installed"
}

$result = [ordered]@{
    version = "0.2.2"
    branch = $Branch
    tag = $Tag
    remote_sha = $remoteSha
    ci_exit_code = $ciExitCode
    ci_result = ($ciOutput | ConvertFrom-Json)
    rollback_exit_code = $rollbackExitCode
    scheduler = $schedulerStatus
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ResultPath) | Out-Null
$result | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $ResultPath -Encoding utf8
Write-Host "Release finalization result: $ResultPath"

if ($ciExitCode -ne 0) {
    throw "CI validation failed or was not green."
}
if ($rollbackExitCode -ne 0) {
    throw "Rollback validation failed."
}
Write-Host "v0.2.2 push, CI, and rollback validation completed."
