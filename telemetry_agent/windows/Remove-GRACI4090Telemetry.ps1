[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference = 'Stop'
$taskName = 'GRACI 4090 Read-Only Telemetry'
$firewallName = 'GRACI 4090 Telemetry from 3090'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -ne $task -and $task.State -ne 'Ready') { Stop-ScheduledTask -TaskName $taskName }
if ($null -ne $task -and $PSCmdlet.ShouldProcess($taskName, 'Unregister telemetry task')) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}
if ($PSCmdlet.ShouldProcess($firewallName, 'Remove telemetry firewall allow rule')) {
    Get-NetFirewallRule -DisplayName $firewallName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
}
Write-Host 'Task and firewall rule removed. Package files were retained for inspection or rollback.'
