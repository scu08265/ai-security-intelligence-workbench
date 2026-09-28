param(
    [string]$TaskName = "AI-Security-Intelligence-Daily-Collection"
)

$ErrorActionPreference = "Stop"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed scheduled task: $TaskName"
