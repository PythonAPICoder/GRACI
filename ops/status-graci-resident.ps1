[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resident-host-common.ps1')
$record = Read-GraciResidentState
if ($null -eq $record) {
    Write-Output 'GRACI resident host is stopped.'
    exit 1
}
$process = Get-ValidatedGraciResidentProcess -Record $record
if ($null -eq $process) {
    Write-Output "GRACI resident host is stopped; stale state exists at $script:ResidentState."
    exit 1
}
Write-Output "GRACI resident host is running (PID $($record.pid), started $($record.started_at))."
Write-Output "Observer-only visualizer: http://127.0.0.1:$($record.visualizer.port)/"
