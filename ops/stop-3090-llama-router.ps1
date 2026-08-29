[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'llama-router-common.ps1')
$record = Read-GraciRouterState
if ($null -eq $record) { Write-Output 'GRACI 3090 llama.cpp router is already stopped.'; exit 0 }
$process = Get-ValidatedGraciRouterProcess -Record $record
if ($null -eq $process) {
    Remove-Item -LiteralPath $script:RouterState
    Write-Output 'Recorded GRACI router is no longer running; removed stale ownership record.'
    exit 0
}
Stop-Process -Id $process.Id
if (-not $process.WaitForExit(15000)) {
    throw 'GRACI router did not exit within 15 seconds.'
}
Remove-Item -LiteralPath $script:RouterState
Write-Output "Stopped GRACI-owned llama.cpp router PID $($process.Id)."
