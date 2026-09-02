[CmdletBinding()]
param()

. "$PSScriptRoot\phase8e-review-boundary-common.ps1"
$state = Get-Phase8EBoundaryState
$pointerPath = Join-Path $script:Phase8EProjectionRoot "current.json"
if (-not (Test-Path -LiteralPath $pointerPath -PathType Leaf)) { throw "Current projection pointer is missing." }
$pointer = Get-Content -Raw -LiteralPath $pointerPath | ConvertFrom-Json
if ($pointer.generation_id -notmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$') {
    throw "Current generation ID is not a canonical lowercase UUID."
}
$generationsRoot = Join-Path $script:Phase8EProjectionRoot "generations"
$generation = Join-Path $generationsRoot $pointer.generation_id
if (-not (Test-Path -LiteralPath $generation -PathType Container) -or
        (Test-Phase8EReparse $generation)) { throw "Current generation is missing or unsafe." }
$resolved = [IO.Path]::GetFullPath($generation)
if ((Split-Path -Parent $resolved) -ne [IO.Path]::GetFullPath($generationsRoot)) {
    throw "Current generation escaped the exact projection root."
}
& "$env:SystemRoot\System32\icacls.exe" $generation /reset /T /C /Q | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Projection ACL inheritance finalization failed." }
[pscustomobject]@{ passed = $true; generation_id = $pointer.generation_id; acl_finalized = $true } |
    ConvertTo-Json -Compress | Write-Output
