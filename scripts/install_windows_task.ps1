param(
    [string]$TaskName = "AI-Security-Intelligence-Daily-Collection",
    [string]$DailyAt = "02:30",
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
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`" -TaskId `"$TaskName`" -ScheduledTime `"$DailyAt`"" `
    -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At $DailyAt
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
    -Description "Run the recommended AI security intelligence sources once per day." `
    -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "Schedule: daily at $DailyAt"
Write-Host "Manual test: Start-ScheduledTask -TaskName '$TaskName'"
