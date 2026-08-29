[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$pidFile = Join-Path $PSScriptRoot '..\.runtime\llama-router\pid.json'
if (-not (Test-Path -LiteralPath $pidFile -PathType Leaf)) {
    throw 'No GRACI llama.cpp router ownership record exists.'
}
$record = Get-Content -Raw -LiteralPath $pidFile | ConvertFrom-Json
if ($record.owner -ne 'GRACI' -or $record.executable -ne 'E:\llama.cpp\bin\llama-server.exe') {
    throw 'Ownership record is invalid; refusing to stop any process.'
}
$process = Get-Process -Id ([int]$record.pid) -ErrorAction SilentlyContinue
if ($null -eq $process) {
    Remove-Item -LiteralPath $pidFile
    Write-Output 'Recorded GRACI router is no longer running; removed stale ownership record.'
    exit 0
}
if ($process.Path -ne $record.executable) {
    throw 'Recorded PID belongs to another executable; refusing to stop it.'
}
Stop-Process -Id $process.Id
if (-not $process.WaitForExit(15000)) {
    throw 'GRACI router did not exit within 15 seconds.'
}
Remove-Item -LiteralPath $pidFile
Write-Output "Stopped GRACI-owned llama.cpp router PID $($process.Id)."
