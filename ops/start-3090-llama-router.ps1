[CmdletBinding()]
param(
    [string]$LlamaRoot = 'E:\llama.cpp',
    [int]$Port = 8080
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'llama-router-common.ps1')
if ($Port -lt 1 -or $Port -gt 65535) { throw 'Router port must be between 1 and 65535.' }
$server = [IO.Path]::GetFullPath((Join-Path $LlamaRoot 'bin\llama-server.exe'))
$models = [IO.Path]::GetFullPath((Join-Path $LlamaRoot 'models'))
if (-not (Test-Path -LiteralPath $server -PathType Leaf)) {
    throw "llama-server.exe not found at $server"
}
foreach ($name in $script:RouterApprovedModels) {
    $path = Join-Path $models $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Approved model not found at $path"
    }
}

$mutex = New-Object Threading.Mutex($false, 'Local\GRACI-3090-Llama-Router-Start')
$acquired = $false
try {
    $acquired = $mutex.WaitOne(0)
    if (-not $acquired) { throw 'Another GRACI 3090 router start is already in progress.' }
    $existing = Read-GraciRouterState
    if ($null -ne $existing) {
        $owned = Get-ValidatedGraciRouterProcess -Record $existing
        if ($null -ne $owned) {
            $health = Get-GraciRouterHealth -Port ([int]$existing.port)
            if (-not $health.healthy) {
                throw 'The owned GRACI 3090 router is running but unhealthy; refusing replacement.'
            }
            if ($existing.schema_version -eq 1) {
                Write-GraciJsonNoBom -Path $script:RouterState -Value @{
                    schema_version = 2
                    owner = $script:RouterOwner
                    pid = [int]$existing.pid
                    executable = [string]$existing.executable
                    host = '127.0.0.1'
                    port = [int]$existing.port
                    started_at = [string]$existing.started_at
                    arguments = @($existing.arguments)
                }
            }
            Write-Output "GRACI-owned llama.cpp router is already running (PID $($existing.pid))."
            exit 0
        }
        Remove-Item -LiteralPath $script:RouterState
    }
    if (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet) {
        throw "Port $Port is already occupied; refusing to stop or replace an unrelated server."
    }

    New-Item -ItemType Directory -Force -Path $script:RouterRuntime | Out-Null
    $stdout = Join-Path $script:RouterRuntime 'stdout.log'
    $stderr = Join-Path $script:RouterRuntime 'stderr.log'
    $arguments = @(
        '--models-dir', $models,
        '--models-max', '1',
        '--models-autoload',
        '--host', '127.0.0.1',
        '--port', [string]$Port,
        '--ctx-size', '32768',
        '--parallel', '1',
        '--n-gpu-layers', 'all',
        '--flash-attn', 'on',
        '--no-webui'
    )
    $process = Start-Process -FilePath $server -ArgumentList $arguments -PassThru `
        -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    Write-GraciJsonNoBom -Path $script:RouterState -Value @{
        schema_version = 2
        owner = $script:RouterOwner
        pid = $process.Id
        executable = $server
        host = '127.0.0.1'
        port = $Port
        started_at = (Get-Date).ToUniversalTime().ToString('o')
        arguments = $arguments
    }
    $deadline = (Get-Date).AddSeconds(30)
    $health = Get-GraciRouterHealth -Port $Port
    do {
        if ($process.HasExited) { break }
        if (-not $health.healthy) { Start-Sleep -Milliseconds 250 }
        $health = Get-GraciRouterHealth -Port $Port
    } while (-not $health.healthy -and (Get-Date) -lt $deadline)
    if (-not $health.healthy) {
        if (-not $process.HasExited) { Stop-Process -Id $process.Id }
        Remove-Item -LiteralPath $script:RouterState -ErrorAction SilentlyContinue
        throw "GRACI llama.cpp router did not report both approved models within 30 seconds. See $stderr"
    }
    Write-Output "Started GRACI-owned llama.cpp router PID $($process.Id)."
    Write-Output "It exposes only approved files from $models and loads at most one model."
} finally {
    if ($acquired) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
