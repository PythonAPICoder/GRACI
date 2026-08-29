[CmdletBinding()]
param([string]$Python)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resident-host-common.ps1')
if ($null -ne (Get-ScheduledTask -TaskName $script:ResidentTaskName -ErrorAction SilentlyContinue)) {
    throw "Scheduled task '$script:ResidentTaskName' already exists; remove it explicitly before reinstalling."
}
$startScript = Join-Path $PSScriptRoot 'start-graci-resident.ps1'
$pythonPath = if ($PSBoundParameters.ContainsKey('Python')) {
    Resolve-GraciPythonPath -Python $Python
} else {
    Resolve-GraciPythonPath
}
$arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$startScript`" -Python `"$pythonPath`""
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $script:RepositoryRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $script:ResidentTaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Description 'Starts the idle, observer-only GRACI resident host.' | Out-Null
Write-Output "Installed scheduled task '$script:ResidentTaskName' for the current user at logon."
