[CmdletBinding()]
param([string]$Python)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resident-host-common.ps1')

$existing = Read-GraciResidentState
if ($null -ne $existing) {
    $process = Get-ValidatedGraciResidentProcess -Record $existing
    if ($null -ne $process) {
        Write-Output "GRACI resident host is already running (PID $($existing.pid))."
        exit 0
    }
    Remove-Item -LiteralPath $script:ResidentState
}

$pythonPath = if ($PSBoundParameters.ContainsKey('Python')) {
    Resolve-GraciPythonPath -Python $Python
} else {
    Resolve-GraciPythonPath
}
$instanceId = [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Force -Path $script:ResidentRuntime | Out-Null
$stdout = Join-Path $script:ResidentRuntime 'stdout.log'
$stderr = Join-Path $script:ResidentRuntime 'stderr.log'
$arguments = @('-m', $script:ResidentModule, '--instance-id', $instanceId)
$process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $script:RepositoryRoot `
    -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr

$deadline = (Get-Date).AddSeconds(15)
do {
    if ($process.HasExited) { break }
    Start-Sleep -Milliseconds 100
    $record = Read-GraciResidentState
} while ($null -eq $record -and (Get-Date) -lt $deadline)

if ($null -eq $record -or $record.instance_id -ne $instanceId -or [int]$record.pid -ne $process.Id) {
    throw "GRACI resident host did not publish matching state within 15 seconds. See $stderr"
}
$validated = Get-ValidatedGraciResidentProcess -Record $record
if ($null -eq $validated) { throw "GRACI resident host exited during startup. See $stderr" }
Write-Output "Started GRACI resident host PID $($record.pid)."
Write-Output "Local visualizer with explicit PTT: http://127.0.0.1:$($record.visualizer.port)/"
