[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'llama-router-common.ps1')
$record = Read-GraciRouterState
if ($null -eq $record) { Write-Output 'GRACI 3090 llama.cpp router is stopped.'; exit 1 }
$process = Get-ValidatedGraciRouterProcess -Record $record
if ($null -eq $process) {
    Write-Output "GRACI router is stopped; stale state exists at $script:RouterState."
    exit 1
}
$health = Get-GraciRouterHealth -Port ([int]$record.port)
if (-not $health.healthy) {
    Write-Output "GRACI-owned router PID $($record.pid) is running but unhealthy."
    exit 2
}
$loaded = if (@($health.loaded_models).Count) { @($health.loaded_models) -join ', ' } else { 'none' }
Write-Output "GRACI-owned router is healthy (PID $($record.pid), http://127.0.0.1:$($record.port))."
Write-Output "Loaded models: $loaded"
