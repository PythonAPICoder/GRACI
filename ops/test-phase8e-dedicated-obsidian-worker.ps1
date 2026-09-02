[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ObsidianPath,
    [Parameter(Mandatory)][string]$ProjectionRoot,
    [Parameter(Mandatory)][string]$ViewerProfileRoot,
    [Parameter(Mandatory)][string]$ViewerConfigRoot,
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
        } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ResultPath -Encoding utf8
    } catch {}
    exit 1
}

function Get-Phase8EProtectedTree([string]$Root) {
    return @(
        Get-ChildItem -LiteralPath $Root -File -Recurse | Sort-Object FullName | ForEach-Object {
            $relative = $_.FullName.Substring($Root.Length + 1)
            if (-not $relative.StartsWith(".obsidian\", [StringComparison]::OrdinalIgnoreCase)) {
                [pscustomobject]@{
                    Path = $relative
                    Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
                }
            }
        }
    )
}

$currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
if ($currentSid -ne $ExpectedViewerSid) { throw "VIEWER_IDENTITY_REQUIRED" }
foreach ($path in @($ObsidianPath, $ProjectionRoot, $ViewerProfileRoot, $ViewerConfigRoot)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "REQUIRED_PATH_MISSING" }
    if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "REPARSE_PATH_REJECTED"
    }
}
$binaryHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ObsidianPath).Hash.ToLowerInvariant()
if ($binaryHash -ne $ExpectedHash) { throw "OBSIDIAN_HASH_MISMATCH" }

$pointerPath = Join-Path $ProjectionRoot "current.json"
$pointer = Get-Content -Raw -LiteralPath $pointerPath | ConvertFrom-Json
if ($pointer.generation_id -notmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$') {
    throw "GENERATION_ID_INVALID"
}
$generationRoot = Join-Path (Join-Path $ProjectionRoot "generations") $pointer.generation_id
$homeNote = Join-Path $generationRoot "Home.md"
$markdownFiles = @(Get-ChildItem -LiteralPath $generationRoot -Filter "*.md" -File -Recurse)
$projectionReadable = $markdownFiles.Count -gt 0 -and (Get-Content -Raw -LiteralPath $homeNote).Length -gt 0
$before = Get-Phase8EProtectedTree $ProjectionRoot | ConvertTo-Json -Compress
$writeDenied = $false
try {
    Set-Content -LiteralPath (Join-Path $generationRoot "viewer-stage3-write-test.tmp") -Value "test" -ErrorAction Stop
} catch [UnauthorizedAccessException] {
    $writeDenied = $true
} catch {
    $writeDenied = $_.Exception.Message -match "denied|permission|access"
}

$env:USERPROFILE = $ViewerProfileRoot
$env:APPDATA = Split-Path -Parent $ViewerConfigRoot
$env:LOCALAPPDATA = Join-Path $ViewerProfileRoot "AppData\Local"
$testTemp = Join-Path $env:LOCALAPPDATA "Temp\GRACI-Obsidian"
if (-not (Test-Path -LiteralPath $testTemp)) { New-Item -ItemType Directory -Path $testTemp -Force | Out-Null }
$env:TEMP = $testTemp
$env:TMP = $testTemp

$processObserved = $false
$nonLoopbackConnections = 0
$ownedProcesses = @()
$started = $null
$startedProcessId = $null
$startedHasExited = $null
$startedExitCode = $null
$resultParent = Split-Path -Parent $ResultPath
if (-not (Test-Path -LiteralPath $resultParent)) { New-Item -ItemType Directory -Path $resultParent -Force | Out-Null }
$standardOutputPath = Join-Path $resultParent "stage3-dedicated-obsidian.stdout.txt"
$standardErrorPath = Join-Path $resultParent "stage3-dedicated-obsidian.stderr.txt"
Remove-Item -LiteralPath $standardOutputPath, $standardErrorPath -Force -ErrorAction SilentlyContinue
try {
    $arguments = @(
        "--disable-gpu",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--user-data-dir=$ViewerConfigRoot",
        $ProjectionRoot
    )
    $started = Start-Process -FilePath $ObsidianPath -ArgumentList $arguments `
        -RedirectStandardOutput $standardOutputPath -RedirectStandardError $standardErrorPath -PassThru
    $startedProcessId = $started.Id
    Start-Sleep -Seconds 15
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
    foreach ($process in $ownedProcesses) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    if ($null -ne $started -and -not $started.HasExited) { Stop-Process -Id $started.Id -Force -ErrorAction SilentlyContinue }
}

$configPath = Join-Path $ViewerConfigRoot "obsidian.json"
$syntheticVaultRegistered = $false
if (Test-Path -LiteralPath $configPath -PathType Leaf) {
    $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
    $vaults = @($config.vaults.PSObject.Properties | ForEach-Object Value)
    $expectedVault = [IO.Path]::GetFullPath($ProjectionRoot).TrimEnd('\')
    $syntheticVaultRegistered = @($vaults | Where-Object {
        $_.path -and [IO.Path]::GetFullPath([string]$_.path).TrimEnd('\') -eq $expectedVault
    }).Count -eq 1
}
$after = Get-Phase8EProtectedTree $ProjectionRoot | ConvertTo-Json -Compress
$projectionUnchanged = $before -eq $after
$standardOutput = if (Test-Path -LiteralPath $standardOutputPath) { [IO.File]::ReadAllText($standardOutputPath) } else { $null }
$standardError = if (Test-Path -LiteralPath $standardErrorPath) { [IO.File]::ReadAllText($standardErrorPath) } else { $null }
$configurationParseError = (($standardOutput + "`n" + $standardError) -match "not valid JSON|SyntaxError.*JSON")
$passed = $projectionReadable -and $writeDenied -and $processObserved -and
    $syntheticVaultRegistered -and $projectionUnchanged -and $nonLoopbackConnections -eq 0 -and
    -not $configurationParseError

[ordered]@{
    schema_version = 1
    observed_at = [DateTimeOffset]::Now.ToString("o")
    viewer_sid = $currentSid
    executable_hash = $binaryHash
    generation_id = $pointer.generation_id
    markdown_file_count = $markdownFiles.Count
    projection_readable = $projectionReadable
    projection_write_denied = $writeDenied
    process_observed = $processObserved
    synthetic_vault_registered = $syntheticVaultRegistered
    protected_projection_unchanged = $projectionUnchanged
    non_loopback_established_connections = $nonLoopbackConnections
    configuration_parse_error = $configurationParseError
    started_process_id = $startedProcessId
    started_process_has_exited = $startedHasExited
    started_process_exit_code = $startedExitCode
    standard_output = $standardOutput
    standard_error = $standardError
    passed = $passed
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ResultPath -Encoding utf8
if (-not $passed) { exit 1 }
