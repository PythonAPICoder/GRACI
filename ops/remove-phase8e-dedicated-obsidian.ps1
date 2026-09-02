[CmdletBinding()]
param()

. "$PSScriptRoot\phase8e-review-boundary-common.ps1"
Assert-Phase8EAdministrator

$qualificationPath = Join-Path $script:Phase8ELauncherRoot "qualified-application.json"
if (Test-Path -LiteralPath $qualificationPath -PathType Leaf) {
    & "$PSScriptRoot\remove-phase8e-obsidian-launcher-promotion.ps1" | Out-Null
}

$prechangePath = Join-Path $script:Phase8EEvidenceRoot "stage3-dedicated-obsidian-prechange.json"
if (-not (Test-Path -LiteralPath $prechangePath -PathType Leaf)) { throw "Dedicated Obsidian prechange evidence is missing." }
$prechange = Get-Content -Raw -LiteralPath $prechangePath | ConvertFrom-Json
$state = Get-Phase8EBoundaryState
$expectedDestination = Join-Path $prechange.viewer_profile_root "AppData\Local\Programs\Obsidian"
$expectedConfig = Join-Path $prechange.viewer_profile_root "AppData\Roaming\obsidian"
$expectedResult = Join-Path $prechange.viewer_profile_root "AppData\Local\GRACI\Stage3Dedicated"
$expectedVaultConfig = Join-Path $script:Phase8EProjectionRoot ".obsidian"
if ($prechange.viewer_sid -ne $state.viewer_sid -or
        $prechange.destination_root -ne $expectedDestination -or
        $prechange.viewer_config_root -ne $expectedConfig -or
        $prechange.viewer_result_root -ne $expectedResult -or
        $prechange.vault_config_root -ne $expectedVaultConfig -or
        $prechange.firewall_rule_name -ne "GRACI-Phase8E-Stage3-Obsidian-Dedicated-Viewer-Block" -or
        $prechange.created_paths_preexisted) { throw "Dedicated Obsidian rollback evidence is outside the exact boundary." }

$rule = Get-NetFirewallRule -Name $prechange.firewall_rule_name -ErrorAction SilentlyContinue
if ($null -ne $rule) {
    $application = $rule | Get-NetFirewallApplicationFilter
    $security = $rule | Get-NetFirewallSecurityFilter
    $expectedLocalUser = "D:(A;;CC;;;$($state.viewer_sid))"
    if ($rule.Direction -ne "Outbound" -or $rule.Action -ne "Block" -or
            $application.Program -ne $prechange.destination_path -or $security.LocalUser -ne $expectedLocalUser) {
        throw "The firewall rule no longer matches the exact rollback boundary."
    }
    Remove-NetFirewallRule -Name $prechange.firewall_rule_name
}
foreach ($pair in @(
    @($prechange.destination_root, $expectedDestination),
    @($prechange.viewer_config_root, $expectedConfig),
    @($prechange.viewer_result_root, $expectedResult),
    @($prechange.vault_config_root, $expectedVaultConfig)
)) {
    $actual = [IO.Path]::GetFullPath([string]$pair[0]).TrimEnd('\')
    $expected = [IO.Path]::GetFullPath([string]$pair[1]).TrimEnd('\')
    if ($actual -ne $expected) { throw "A rollback path did not match its exact expected target." }
    if (Test-Path -LiteralPath $actual) {
        if ((Get-Item -LiteralPath $actual -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Rollback refused a reparse point."
        }
        Remove-Item -LiteralPath $actual -Recurse -Force
    }
}
Remove-Item -LiteralPath (Join-Path $script:Phase8ELauncherRoot "Test-DedicatedObsidian.ps1") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $script:Phase8ELauncherRoot "stage3-dedicated-obsidian-state.json") -Force -ErrorAction SilentlyContinue
[pscustomobject]@{ rolled_back = $true; preserved_evidence = $script:Phase8EEvidenceRoot; owner_obsidian_changed = $false } |
    ConvertTo-Json -Compress | Write-Output
