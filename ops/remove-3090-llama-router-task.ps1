[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'llama-router-common.ps1')
$task = Get-ScheduledTask -TaskName $script:RouterTaskName -ErrorAction SilentlyContinue
if ($null -eq $task) { Write-Output "Scheduled task '$script:RouterTaskName' is not installed."; exit 0 }
Unregister-ScheduledTask -TaskName $script:RouterTaskName -Confirm:$false
Write-Output "Removed scheduled task '$script:RouterTaskName'. The router process was not stopped."
