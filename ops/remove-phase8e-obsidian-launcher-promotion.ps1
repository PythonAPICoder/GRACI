[CmdletBinding()]
param()

. "$PSScriptRoot\phase8e-review-boundary-common.ps1"
Assert-Phase8EAdministrator

$authority = "PO-DEC-033"
$qualificationPath = Join-Path $script:Phase8ELauncherRoot "qualified-application.json"
$launcherPath = Join-Path $script:Phase8ELauncherRoot "Open-GRACIReview.ps1"
$launcherStatePath = Join-Path $script:Phase8ELauncherRoot "boundary-state.json"
$evidenceStatePath = Join-Path $script:Phase8EEvidenceRoot "boundary-state.json"
$prechangeRoot = Join-Path $script:Phase8EEvidenceRoot "stage3-routine-launch-prechange"
$prechangeStatePath = Join-Path $prechangeRoot "state.json"
$resultPath = Join-Path $script:Phase8EEvidenceRoot "stage3-routine-launch-rollback.json"
$applicationPath = "C:\Users\GRACI_Review\AppData\Local\Programs\Obsidian\Obsidian.exe"
$vaultConfigRoot = Join-Path $script:Phase8EProjectionRoot ".obsidian"
$corePluginsPath = Join-Path $vaultConfigRoot "core-plugins.json"
$communityPluginsPath = Join-Path $vaultConfigRoot "community-plugins.json"

foreach ($path in @($qualificationPath, $launcherPath, $launcherStatePath, $evidenceStatePath,
        $prechangeRoot, $prechangeStatePath, $applicationPath, $vaultConfigRoot)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Required routine-launch rollback state is missing: $path" }
    if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Routine-launch rollback refused a reparse point: $path"
    }
}
$backups = @{
    Launcher = Join-Path $prechangeRoot "Open-GRACIReview.ps1"
    LauncherState = Join-Path $prechangeRoot "launcher-boundary-state.json"
    EvidenceState = Join-Path $prechangeRoot "evidence-boundary-state.json"
    CorePlugins = Join-Path $prechangeRoot "core-plugins.json"
    CommunityPlugins = Join-Path $prechangeRoot "community-plugins.json"
}
foreach ($name in @("Launcher", "LauncherState", "EvidenceState", "CorePlugins")) {
    if (-not (Test-Path -LiteralPath $backups[$name] -PathType Leaf)) {
        throw "Routine-launch rollback backup is missing: $name"
    }
}

$boundary = Get-Phase8EBoundaryState
$prechange = Get-Content -Raw -LiteralPath $prechangeStatePath | ConvertFrom-Json
$qualification = Get-Content -Raw -LiteralPath $qualificationPath | ConvertFrom-Json
$expectedHash = "c01bbd79583037639f5422396cddb457ef48e89e159ca50a8492bbd1f1f10775"
if ($prechange.schema_version -ne 1 -or $prechange.authority -ne $authority -or
        $prechange.launcher_path -ne $launcherPath -or
        $prechange.qualification_path -ne $qualificationPath -or
        $prechange.qualification_preexisted -ne $false -or
        $prechange.launcher_sha256 -ne
            (Get-FileHash -LiteralPath $backups.Launcher -Algorithm SHA256).Hash.ToLowerInvariant()) {
    throw "Routine-launch prechange evidence is invalid."
}
if ($qualification.schema_version -ne 1 -or $qualification.authority -ne $authority -or
        $qualification.viewer_sid -ne $boundary.viewer_sid -or
        $qualification.application_path -ne $applicationPath -or
        $qualification.application_sha256 -ne $expectedHash -or
        $qualification.product_owner_accepted -ne $true -or
        $qualification.routine_launch_authorized -ne $true -or
        $qualification.real_data_authorized -ne $false -or
        $qualification.community_plugins_allowed -ne $false) {
    throw "The live qualification record is outside the exact rollback boundary."
}
foreach ($statePath in @($launcherStatePath, $evidenceStatePath)) {
    $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
    if ($state.qualified_application.path -ne $applicationPath -or
            $state.qualified_application.sha256 -ne $expectedHash -or
            $state.qualified_application.authority -ne $authority) {
        throw "A live boundary state is outside the exact rollback boundary."
    }
}

foreach ($process in @(Get-Process -Name Obsidian -ErrorAction SilentlyContinue | Where-Object {
    try { $_.Path -eq $applicationPath } catch { $false }
})) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }

if (Test-Path -LiteralPath $communityPluginsPath -PathType Leaf) {
    if (-not (Test-Path -LiteralPath $backups.CommunityPlugins -PathType Leaf) -and
            [IO.File]::ReadAllText($communityPluginsPath).Trim() -ne "[]") {
        throw "Unexpected community-plugin state blocks rollback."
    }
}

Copy-Item -LiteralPath $backups.Launcher -Destination $launcherPath -Force
Copy-Item -LiteralPath $backups.LauncherState -Destination $launcherStatePath -Force
Copy-Item -LiteralPath $backups.EvidenceState -Destination $evidenceStatePath -Force
Copy-Item -LiteralPath $backups.CorePlugins -Destination $corePluginsPath -Force
if (Test-Path -LiteralPath $backups.CommunityPlugins -PathType Leaf) {
    Copy-Item -LiteralPath $backups.CommunityPlugins -Destination $communityPluginsPath -Force
} else {
    Remove-Item -LiteralPath $communityPluginsPath -Force -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath $qualificationPath -Force

[ordered]@{
    schema_version = 1
    rolled_back_at = [DateTimeOffset]::Now.ToString("o")
    authority = $authority
    routine_launcher_removed = $true
    dedicated_application_removed = $false
    product_owner_obsidian_changed = $false
    preserved_evidence = $script:Phase8EEvidenceRoot
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $resultPath -Encoding utf8
Get-Content -Raw -LiteralPath $resultPath | Write-Output
