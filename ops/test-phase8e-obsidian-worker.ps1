[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ObsidianPath,
    [Parameter(Mandatory)][string]$ProjectionRoot,
    [Parameter(Mandatory)][string]$ExpectedHash,
    [Parameter(Mandatory)][string]$ExpectedViewerSid,
    [Parameter(Mandatory)][string]$ResultPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

trap {
    try {
        $failureParent = Split-Path -Parent $ResultPath
        if (-not (Test-Path -LiteralPath $failureParent)) {
            New-Item -ItemType Directory -Path $failureParent | Out-Null
        }
        [ordered]@{
            schema_version = 1
            observed_at = [DateTimeOffset]::Now.ToString("o")
            failure = $_.Exception.Message
            passed = $false
        } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ResultPath -Encoding utf8
    } catch {}
    exit 1
}

function Get-Phase8EFileTree([string]$Root) {
    return @(
        Get-ChildItem -LiteralPath $Root -File -Recurse | Sort-Object FullName | ForEach-Object {
            [pscustomobject]@{
                Path = $_.FullName.Substring($Root.Length + 1)
                Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
            }
        }
    )
}

$currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
if ($currentSid -ne $ExpectedViewerSid) { throw "VIEWER_IDENTITY_REQUIRED" }
if (-not (Test-Path -LiteralPath $ObsidianPath -PathType Leaf)) { throw "OBSIDIAN_MISSING" }
if ((Get-Item -LiteralPath $ObsidianPath -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw "OBSIDIAN_REPARSE_REJECTED"
}
$binaryHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ObsidianPath).Hash.ToLowerInvariant()
if ($binaryHash -ne $ExpectedHash) { throw "OBSIDIAN_HASH_MISMATCH" }

$pointerPath = Join-Path $ProjectionRoot "current.json"
$pointer = Get-Content -Raw -LiteralPath $pointerPath | ConvertFrom-Json
if ($pointer.generation_id -notmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$') {
    throw "GENERATION_ID_INVALID"
}
$generationRoot = Join-Path (Join-Path $ProjectionRoot "generations") $pointer.generation_id
if (-not (Test-Path -LiteralPath $generationRoot -PathType Container) -or
        ((Get-Item -LiteralPath $generationRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw "GENERATION_ROOT_INVALID"
}
$homeNote = Join-Path $generationRoot "Home.md"
$projectionReadable = (Get-Content -Raw -LiteralPath $homeNote).Length -gt 0
$before = Get-Phase8EFileTree $generationRoot | ConvertTo-Json -Compress
$writeDenied = $false
try {
    Set-Content -LiteralPath (Join-Path $generationRoot "viewer-stage3-write-test.tmp") -Value "test" -ErrorAction Stop
} catch [UnauthorizedAccessException] {
    $writeDenied = $true
} catch {
    $writeDenied = $_.Exception.Message -match "denied|permission|access"
}

$processObserved = $false
$nonLoopbackConnections = 0
$ownedProcesses = @()
$started = $null
$startedExitCode = $null
$startedProcessId = $null
$startedHasExited = $null
$resultParent = Split-Path -Parent $ResultPath
if (-not (Test-Path -LiteralPath $resultParent)) {
    New-Item -ItemType Directory -Path $resultParent | Out-Null
}
$standardOutputPath = Join-Path $resultParent "stage3-obsidian.stdout.txt"
$standardErrorPath = Join-Path $resultParent "stage3-obsidian.stderr.txt"
Remove-Item -LiteralPath $standardOutputPath, $standardErrorPath -Force -ErrorAction SilentlyContinue
try {
    $started = Start-Process -FilePath $ObsidianPath -ArgumentList @(
        "--disable-gpu", "--disable-background-networking", $generationRoot
    ) -RedirectStandardOutput $standardOutputPath -RedirectStandardError $standardErrorPath -PassThru
    $startedProcessId = $started.Id
    Start-Sleep -Seconds 12
    $started.Refresh()
    $startedHasExited = $started.HasExited
    if ($startedHasExited) { $startedExitCode = $started.ExitCode }
    $ownedProcesses = @(Get-Process -Name Obsidian -ErrorAction SilentlyContinue)
    $processObserved = $ownedProcesses.Count -gt 0 -or -not $startedHasExited
    foreach ($process in $ownedProcesses) {
        $connections = @(Get-NetTCPConnection -OwningProcess $process.Id -State Established -ErrorAction SilentlyContinue |
            Where-Object { $_.RemoteAddress -notin @("127.0.0.1", "::1") })
        $nonLoopbackConnections += $connections.Count
    }
} finally {
    foreach ($process in $ownedProcesses) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    if ($null -ne $started -and -not $started.HasExited) {
        Stop-Process -Id $started.Id -Force -ErrorAction SilentlyContinue
    }
}

$configPath = Join-Path (Join-Path $env:APPDATA "obsidian") "obsidian.json"
$syntheticVaultRegistered = $false
if (Test-Path -LiteralPath $configPath -PathType Leaf) {
    $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
    $vaults = @($config.vaults.PSObject.Properties | ForEach-Object Value)
    $expectedVault = [IO.Path]::GetFullPath($generationRoot).TrimEnd('\')
    $syntheticVaultRegistered = @($vaults | Where-Object {
        $_.path -and [IO.Path]::GetFullPath([string]$_.path).TrimEnd('\') -eq $expectedVault
    }).Count -eq 1
}
$after = Get-Phase8EFileTree $generationRoot | ConvertTo-Json -Compress
$projectionUnchanged = $before -eq $after
$passed = $projectionReadable -and $writeDenied -and $processObserved -and
    $syntheticVaultRegistered -and $projectionUnchanged -and $nonLoopbackConnections -eq 0

$result = [ordered]@{
    schema_version = 1
    observed_at = [DateTimeOffset]::Now.ToString("o")
    viewer_sid = $currentSid
    executable_hash = $binaryHash
    generation_id = $pointer.generation_id
    projection_readable = $projectionReadable
    projection_write_denied = $writeDenied
    process_observed = $processObserved
    synthetic_vault_registered = $syntheticVaultRegistered
    projection_unchanged = $projectionUnchanged
    non_loopback_established_connections = $nonLoopbackConnections
    started_process_id = $startedProcessId
    started_process_has_exited = $startedHasExited
    started_process_exit_code = $startedExitCode
    standard_output = if (Test-Path -LiteralPath $standardOutputPath) {
        [IO.File]::ReadAllText($standardOutputPath)
    } else { $null }
    standard_error = if (Test-Path -LiteralPath $standardErrorPath) {
        [IO.File]::ReadAllText($standardErrorPath)
    } else { $null }
    passed = $passed
}
$result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ResultPath -Encoding utf8
$result | ConvertTo-Json -Depth 4 -Compress | Write-Output
if (-not $passed) { exit 1 }
