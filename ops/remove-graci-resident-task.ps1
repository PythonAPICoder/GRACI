[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resident-host-common.ps1')
$task = Get-ScheduledTask -TaskName $script:ResidentTaskName -ErrorAction SilentlyContinue
if ($null -eq $task) { Write-Output "Scheduled task '$script:ResidentTaskName' is not installed."; exit 0 }
Unregister-ScheduledTask -TaskName $script:ResidentTaskName -Confirm:$false
Write-Output "Removed scheduled task '$script:ResidentTaskName'. The resident process was not stopped."
