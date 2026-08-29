[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resident-host-common.ps1')
$record = Read-GraciResidentState
if ($null -eq $record) { Write-Output 'GRACI resident host is already stopped.'; exit 0 }
$process = Get-ValidatedGraciResidentProcess -Record $record
if ($null -eq $process) {
    Remove-Item -LiteralPath $script:ResidentState
    Write-Output 'Removed stale GRACI resident state; no process was signaled.'
    exit 0
}
$request = @{ schema_version = 1; owner = $script:ResidentOwner; instance_id = $record.instance_id } |
    ConvertTo-Json -Compress
$utf8NoBom = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText($script:ResidentStop, $request, $utf8NoBom)
$deadline = (Get-Date).AddSeconds(15)
do {
    Start-Sleep -Milliseconds 100
    $process = Get-Process -Id ([int]$record.pid) -ErrorAction SilentlyContinue
} while ($null -ne $process -and (Get-Date) -lt $deadline)
if ($null -ne $process) { throw 'GRACI resident host did not stop within 15 seconds; no forced termination was attempted.' }
Write-Output "Stopped GRACI resident host PID $($record.pid)."
