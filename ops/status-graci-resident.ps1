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
Write-Output "GRACI resident process alive: PID $($record.pid)."
$healthUri = "http://127.0.0.1:$($record.visualizer.port)/graci/visualizer/v1/health"
try {
    $health = Invoke-RestMethod -Uri $healthUri -TimeoutSec 2 -ErrorAction Stop
} catch {
    Write-Output "GRACI resident runtime is not ready: loopback health endpoint did not respond."
    exit 2
}
if ($health.api_version -ne 1 -or [string]::IsNullOrWhiteSpace($health.runtime_readiness)) {
    Write-Output "GRACI resident runtime is not ready: loopback health identity is invalid."
    exit 2
}
Write-Output "GRACI resident runtime ready: endpoint responded; readiness=$($health.runtime_readiness), observed=$($health.runtime_observed_at)."
Write-Output "Local visualizer with explicit PTT: http://127.0.0.1:$($record.visualizer.port)/"
