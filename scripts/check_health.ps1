param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"
$Deadline = (Get-Date).AddSeconds($TimeoutSeconds)

while ((Get-Date) -lt $Deadline) {
    try {
        $Health = Invoke-RestMethod -Uri "$BaseUrl/api/health" -TimeoutSec 5
        if ($Health.status -eq "ok") {
            Write-Host ("Health OK: version={0}, mode={1}" -f $Health.version, $Health.mode)
            exit 0
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}

throw "Service did not become healthy within $TimeoutSeconds seconds: $BaseUrl"
