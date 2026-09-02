[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resident-host-common.ps1')
. (Join-Path $PSScriptRoot 'llama-router-common.ps1')
$taskQueryUnknown = $false
foreach ($name in @($script:ResidentTaskName, $script:RouterTaskName)) {
    try {
        $task = Get-ScheduledTask -TaskPath '\' -TaskName $name -ErrorAction Stop
    } catch {
        if ($_.CategoryInfo.Category -eq 'ObjectNotFound' -or
            $_.FullyQualifiedErrorId -match 'NoMatchingScheduledTask') {
            Write-Output "Scheduled task '\$name': missing"
        } else {
            $taskQueryUnknown = $true
            Write-Output "Scheduled task '\$name': access denied / unknown (category=$($_.CategoryInfo.Category))"
        }
        continue
    }
    Write-Output "Scheduled task '\$name': registered, enabled=$($task.Settings.Enabled), state=$($task.State)"
    try {
        $info = Get-ScheduledTaskInfo -InputObject $task -ErrorAction Stop
        if ($info.LastTaskResult -eq 0 -and $info.LastRunTime -ne [datetime]::MinValue) {
            Write-Output "Scheduled task '\$name': launcher succeeded at $($info.LastRunTime.ToString('o'))"
        } else {
            Write-Output "Scheduled task '\$name': launcher success not established (last_result=$($info.LastTaskResult))"
        }
    } catch {
        $taskQueryUnknown = $true
        Write-Output "Scheduled task '\$name': launcher result access denied / unknown (category=$($_.CategoryInfo.Category))"
    }
}
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'status-graci-resident.ps1')
$residentExit = $LASTEXITCODE
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'status-3090-llama-router.ps1')
$routerExit = $LASTEXITCODE
if ($taskQueryUnknown -or $residentExit -ne 0 -or $routerExit -ne 0) { exit 1 }
