param(
    [string]$TaskName = "AI-Security-Intelligence-Hourly-Collection",
    [int]$IntervalHours = 1,
    # 0 = repeat indefinitely.  A finite window expires silently: once the
    # repetition duration runs out the task still exists but NextRunTime goes
    # blank, so the schedule stops without any error.  The task on this machine
    # sat at LastRunTime 2026-10-02 17:48 with LastTaskResult 0 (success) and an
    # empty NextRunTime, which is why "re-hung" looked fine but never fired.
    [int]$DurationHours = 0,
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
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`" -TaskId `"hourly-recommended-sources`" -Hourly" `
    -WorkingDirectory $Root
$StartAt = (Get-Date).AddMinutes(1)
$TriggerArgs = @{
    Once               = $true
    At                 = $StartAt
    RepetitionInterval = (New-TimeSpan -Hours $IntervalHours)
}
if ($DurationHours -gt 0) {
    $TriggerArgs["RepetitionDuration"] = (New-TimeSpan -Hours $DurationHours)
}
$Trigger = New-ScheduledTaskTrigger @TriggerArgs
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -DontStopOnIdleEnd `
    -StartWhenAvailable `
    -WakeToRun `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$Principal = New-ScheduledTaskPrincipal `
    -UserId $UserId `
    -LogonType Interactive `
    -RunLevel Limited

# Keep the machine awake while the screen is allowed to turn off.
powercfg /change standby-timeout-ac 0 | Out-Null
powercfg /change standby-timeout-dc 0 | Out-Null
powercfg /change hibernate-timeout-ac 0 | Out-Null
powercfg /change hibernate-timeout-dc 0 | Out-Null

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Run recommended AI security intelligence sources every $IntervalHours hour(s)." `
    -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
$Window = if ($DurationHours -gt 0) { "for $DurationHours hour(s)" } else { "indefinitely (no expiry)" }
Write-Host "Schedule: every $IntervalHours hour(s) $Window, starting $StartAt"
Write-Host "Sleep and hibernation are disabled; display timeout is unchanged."
Write-Host "Manual test: Start-ScheduledTask -TaskName '$TaskName'"

# A2: the disposition queue is swept once a day.  It is a separate task on
# purpose: collection is hourly and must not be coupled to a daily reminder.
$DispositionTask = "AI-Security-Intelligence-Daily-Disposition"
$DispositionRunner = Join-Path $Root "scripts\run_disposition_ops.ps1"
if (Test-Path -LiteralPath $DispositionRunner) {
    $DispositionAction = New-ScheduledTaskAction `
        -Execute $PowerShell `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$DispositionRunner`" -TaskId `"daily-disposition-queue`"" `
        -WorkingDirectory $Root
    $DispositionTrigger = New-ScheduledTaskTrigger -Daily -At "09:00"
    Register-ScheduledTask `
        -TaskName $DispositionTask `
        -Action $DispositionAction `
        -Trigger $DispositionTrigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "Sweep the disposition queue once a day: overdue reminder and re-check due scan." `
        -Force | Out-Null
    Write-Host "Installed scheduled task: $DispositionTask (daily at 09:00)"
    Write-Host "Manual test: Start-ScheduledTask -TaskName '$DispositionTask'"
}
