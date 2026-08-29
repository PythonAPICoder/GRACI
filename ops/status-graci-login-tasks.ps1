[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resident-host-common.ps1')
. (Join-Path $PSScriptRoot 'llama-router-common.ps1')
foreach ($name in @($script:ResidentTaskName, $script:RouterTaskName)) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($null -eq $task) { Write-Output "Scheduled task '$name': not installed" }
    else { Write-Output "Scheduled task '$name': installed, enabled=$($task.Settings.Enabled), state=$($task.State)" }
}
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'status-graci-resident.ps1')
$residentExit = $LASTEXITCODE
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'status-3090-llama-router.ps1')
$routerExit = $LASTEXITCODE
if ($residentExit -ne 0 -or $routerExit -ne 0) { exit 1 }
