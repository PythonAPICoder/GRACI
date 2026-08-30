[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$taskName = 'GRACI 4090 Read-Only Telemetry'
try {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
} catch {
    if ($_.FullyQualifiedErrorId -like 'CmdletizationQuery_NotFound_TaskName*' -or
            $_.CategoryInfo.Category -eq [System.Management.Automation.ErrorCategory]::ObjectNotFound) {
        Write-Output 'NOT INSTALLED'
        exit 2
    }
    Write-Warning 'TASK ENUMERATION UNAVAILABLE - INSUFFICIENT PRIVILEGE OR TASK SCHEDULER ACCESS FAILURE.'
    exit 3
}
$task | Select-Object TaskName, State
try {
    Invoke-RestMethod -Method Get -Uri 'http://192.168.0.101:8767/health' -TimeoutSec 2
} catch {
    Write-Warning 'Task exists but the fixed health route did not answer.'
    exit 1
}
