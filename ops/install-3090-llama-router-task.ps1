[CmdletBinding()]
param([string]$LlamaRoot = 'E:\llama.cpp', [int]$Port = 8080)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'llama-router-common.ps1')
if ($null -ne (Get-ScheduledTask -TaskName $script:RouterTaskName -ErrorAction SilentlyContinue)) {
    throw "Scheduled task '$script:RouterTaskName' already exists; remove it explicitly before reinstalling."
}
$startScript = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'start-3090-llama-router.ps1'))
$root = [IO.Path]::GetFullPath($LlamaRoot)
$server = Join-Path $root 'bin\llama-server.exe'
if (-not (Test-Path -LiteralPath $server -PathType Leaf)) { throw "llama-server.exe not found at $server" }
$arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$startScript`" -LlamaRoot `"$root`" -Port $Port"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $script:RouterRepositoryRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $script:RouterTaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Description 'Starts the GRACI-owned loopback 3090 llama.cpp model router.' | Out-Null
Write-Output "Installed scheduled task '$script:RouterTaskName' for the current user at logon."
