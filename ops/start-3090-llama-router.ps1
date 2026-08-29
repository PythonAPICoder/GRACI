[CmdletBinding()]
param(
    [string]$LlamaRoot = 'E:\llama.cpp',
    [int]$Port = 8080
)

$ErrorActionPreference = 'Stop'
$server = Join-Path $LlamaRoot 'bin\llama-server.exe'
$models = Join-Path $LlamaRoot 'models'
$runtime = Join-Path $PSScriptRoot '..\.runtime\llama-router'
$pidFile = Join-Path $runtime 'pid.json'
$approved = @(
    'qwen3.8-27b-q4_k_m.gguf',
    'GLM-4.7-Flash-64x2.6B-Q4_K_M.gguf'
)

if (-not (Test-Path -LiteralPath $server -PathType Leaf)) {
    throw "llama-server.exe not found at $server"
}
foreach ($name in $approved) {
    $path = Join-Path $models $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Approved model not found at $path"
    }
}
if (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet) {
    throw "Port $Port is already occupied; refusing to stop or replace an unrelated server."
}

New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$stdout = Join-Path $runtime 'stdout.log'
$stderr = Join-Path $runtime 'stderr.log'
$arguments = @(
    '--models-dir', $models,
    '--models-max', '1',
    '--models-autoload',
    '--host', '127.0.0.1',
    '--port', $Port,
    '--ctx-size', '32768',
    '--parallel', '1',
    '--n-gpu-layers', 'all',
    '--flash-attn', 'on',
    '--no-webui'
)
$process = Start-Process -FilePath $server -ArgumentList $arguments -PassThru `
    -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
@{
    schema_version = 1
    owner = 'GRACI'
    pid = $process.Id
    executable = $server
    started_at = (Get-Date).ToUniversalTime().ToString('o')
    arguments = $arguments
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $pidFile -Encoding utf8
$deadline = (Get-Date).AddSeconds(30)
$ready = $false
do {
    if ($process.HasExited) { break }
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -TimeoutSec 2
        $ids = @($response.data | ForEach-Object { $_.id })
        $expected = @($approved | ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_) })
        $ready = @($expected | Where-Object { $_ -notin $ids }).Count -eq 0
    } catch {
        $ready = $false
    }
    if (-not $ready) { Start-Sleep -Milliseconds 250 }
} while ((Get-Date) -lt $deadline)
if (-not $ready) {
    if (-not $process.HasExited) { Stop-Process -Id $process.Id }
    Remove-Item -LiteralPath $pidFile -ErrorAction SilentlyContinue
    throw 'GRACI llama.cpp router did not report both approved models within 30 seconds.'
}
Write-Output "Started GRACI-owned llama.cpp router PID $($process.Id)."
Write-Output "It exposes only approved files from $models and loads at most one model."
