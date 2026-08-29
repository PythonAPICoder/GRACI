$script:RouterOwner = 'GRACI_3090_LLAMA_ROUTER'
$script:RouterTaskName = 'GRACI 3090 llama.cpp Router'
$script:RouterRepositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$script:RouterRuntime = Join-Path $script:RouterRepositoryRoot '.runtime\llama-router'
$script:RouterState = Join-Path $script:RouterRuntime 'pid.json'
$script:RouterApprovedModels = @(
    'qwen3.8-27b-q4_k_m.gguf',
    'GLM-4.7-Flash-64x2.6B-Q4_K_M.gguf'
)

function Read-GraciRouterState {
    if (-not (Test-Path -LiteralPath $script:RouterState -PathType Leaf)) { return $null }
    try { $record = Get-Content -Raw -LiteralPath $script:RouterState | ConvertFrom-Json }
    catch { throw 'GRACI 3090 router state is malformed; refusing process action.' }
    $arguments = @($record.arguments)
    $legacy = $record.schema_version -eq 1 -and $record.owner -eq 'GRACI'
    $current = $record.schema_version -eq 2 -and $record.owner -eq $script:RouterOwner
    $hostIndex = [Array]::IndexOf($arguments, '--host')
    $portIndex = [Array]::IndexOf($arguments, '--port')
    if ($legacy -and $hostIndex -ge 0 -and $portIndex -ge 0) {
        $record | Add-Member -NotePropertyName host -NotePropertyValue $arguments[$hostIndex + 1]
        $record | Add-Member -NotePropertyName port -NotePropertyValue ([int]$arguments[$portIndex + 1])
    }
    if ((-not $legacy -and -not $current) -or $record.pid -notmatch '^\d+$' -or
        [string]::IsNullOrWhiteSpace($record.executable) -or
        [string]::IsNullOrWhiteSpace($record.started_at) -or $record.host -ne '127.0.0.1' -or
        $record.port -notmatch '^\d+$' -or
        $arguments -notcontains '--models-dir' -or $arguments -notcontains '--models-max' -or
        $arguments -notcontains '1' -or $arguments -notcontains '--models-autoload' -or
        $arguments -notcontains '--host' -or $arguments -notcontains '127.0.0.1' -or
        $arguments -notcontains '--port' -or $arguments -notcontains ([string]$record.port) -or
        $arguments -notcontains '--no-webui') {
        throw 'GRACI 3090 router state failed identity validation; refusing process action.'
    }
    return $record
}

function Get-ValidatedGraciRouterProcess {
    param([Parameter(Mandatory)]$Record)
    $process = Get-Process -Id ([int]$Record.pid) -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $null }
    $expected = [IO.Path]::GetFullPath([string]$Record.executable)
    if (-not [string]::IsNullOrWhiteSpace($process.Path)) {
        if ([IO.Path]::GetFullPath([string]$process.Path) -ne $expected) {
            throw 'Recorded router PID belongs to another executable; refusing process action.'
        }
    } else {
        $expectedName = [IO.Path]::GetFileNameWithoutExtension($expected)
        $recordedStart = [datetime]::Parse([string]$Record.started_at).ToUniversalTime()
        $actualStart = $process.StartTime.ToUniversalTime()
        if ($process.ProcessName -ne $expectedName -or
            [math]::Abs(($actualStart - $recordedStart).TotalSeconds) -gt 2) {
            throw 'Recorded router PID identity and start time do not match; refusing process action.'
        }
    }
    return $process
}

function Get-GraciRouterHealth {
    param([Parameter(Mandatory)][int]$Port)
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -TimeoutSec 2
        $models = @($response.data)
        $expected = @($script:RouterApprovedModels | ForEach-Object {
            [IO.Path]::GetFileNameWithoutExtension($_)
        })
        $ids = @($models | ForEach-Object { $_.id })
        $missing = @($expected | Where-Object { $_ -notin $ids })
        $loaded = @($models | Where-Object { $_.status.value -eq 'loaded' } |
            ForEach-Object { $_.id })
        return [pscustomobject]@{
            healthy = ($missing.Count -eq 0)
            missing_models = $missing
            loaded_models = $loaded
        }
    } catch {
        return [pscustomobject]@{ healthy = $false; missing_models = @(); loaded_models = @() }
    }
}

function Write-GraciJsonNoBom {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)]$Value)
    $json = $Value | ConvertTo-Json -Depth 6
    $utf8NoBom = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, $json, $utf8NoBom)
}
