param(
    [string]$TaskName = "AI-Security-Intelligence-Hourly-Collection",
    [int]$IntervalHours = 1,
    [string]$UserId = "$env:USERDOMAIN\$env:USERNAME"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $Root "scripts\run_scheduled_collection.ps1"
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path -LiteralPath $Runner)) {
    throw "Runner script not found: $Runner"
}

$Action = New-ScheduledTaskAction `
    -Execute $PowerShell `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`" -TaskId `"$TaskName`" -Hourly" `
    -WorkingDirectory $Root
$StartAt = (Get-Date).AddMinutes(1)
$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At $StartAt `
    -RepetitionInterval (New-TimeSpan -Hours $IntervalHours) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$Principal = New-ScheduledTaskPrincipal `
    -UserId $UserId `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Run recommended AI security intelligence sources every $IntervalHours hour(s)." `
    -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "Schedule: every $IntervalHours hour(s), starting $StartAt"
Write-Host "Manual test: Start-ScheduledTask -TaskName '$TaskName'"
