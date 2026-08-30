[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory=$true)][ValidateScript({Test-Path -LiteralPath $_ -PathType Leaf})]
    [string]$PythonExecutable
)
$ErrorActionPreference = 'Stop'
$taskName = 'GRACI 4090 Read-Only Telemetry'
$firewallName = 'GRACI 4090 Telemetry from 3090'
$installRoot = 'C:\ProgramData\GRACI\telemetry_agent'
$sourceRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = (Resolve-Path -LiteralPath $PythonExecutable).Path
if ([IO.Path]::GetFileName($python) -notin @('python.exe','pythonw.exe')) {
    throw 'PythonExecutable must identify python.exe or pythonw.exe.'
}
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Administrator rights are required to register the fixed task and firewall rule.'
}
if ($PSCmdlet.ShouldProcess($installRoot, 'Install bounded telemetry package')) {
    New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $sourceRoot '__init__.py') -Destination $installRoot -Force
    Copy-Item -LiteralPath (Join-Path $sourceRoot '__main__.py') -Destination $installRoot -Force
    Copy-Item -LiteralPath (Join-Path $sourceRoot 'agent.py') -Destination $installRoot -Force
    Copy-Item -LiteralPath (Join-Path $sourceRoot 'config.defaults.json') -Destination $installRoot -Force
}
if ($PSCmdlet.ShouldProcess($taskName, 'Register startup telemetry task')) {
    $action = New-ScheduledTaskAction -Execute $python -Argument '-m telemetry_agent' -WorkingDirectory 'C:\ProgramData\GRACI'
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Description 'Fixed read-only GRACI 4090 telemetry endpoint.' -Force | Out-Null
}
if ($PSCmdlet.ShouldProcess($firewallName, 'Restrict inbound telemetry to the 3090')) {
    Get-NetFirewallRule -DisplayName $firewallName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule -DisplayName $firewallName -Direction Inbound -Action Allow -Protocol TCP `
        -LocalAddress '192.168.0.101' -LocalPort 8767 -RemoteAddress '192.168.0.100' `
        -Profile Private -Program $python | Out-Null
}
Write-Host 'Installed but not started. Review README.md, then use Start-GRACI4090Telemetry.ps1.'
