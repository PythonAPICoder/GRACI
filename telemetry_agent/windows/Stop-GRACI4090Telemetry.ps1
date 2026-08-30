[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference = 'Stop'
$taskName = 'GRACI 4090 Read-Only Telemetry'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -eq $task) { throw 'The fixed GRACI telemetry task is not installed.' }
if ($task.State -ne 'Ready' -and $PSCmdlet.ShouldProcess($taskName, 'Stop fixed telemetry task')) {
    Stop-ScheduledTask -TaskName $taskName
}
