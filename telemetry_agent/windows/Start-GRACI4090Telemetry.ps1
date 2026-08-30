[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference = 'Stop'
$taskName = 'GRACI 4090 Read-Only Telemetry'
if (-not (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)) {
    throw 'The fixed GRACI telemetry task is not installed.'
}
if ($PSCmdlet.ShouldProcess($taskName, 'Start fixed telemetry task')) {
    Start-ScheduledTask -TaskName $taskName
}
