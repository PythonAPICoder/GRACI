[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$taskName = 'GRACI 4090 Read-Only Telemetry'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -eq $task) { Write-Output 'NOT INSTALLED'; exit 2 }
$task | Select-Object TaskName, State
try {
    Invoke-RestMethod -Method Get -Uri 'http://192.168.0.101:8767/health' -TimeoutSec 2
} catch {
    Write-Warning 'Task exists but the fixed health route did not answer.'
    exit 1
}
