[CmdletBinding()]
param()

. "$PSScriptRoot\phase8e-review-boundary-common.ps1"
Assert-Phase8EAdministrator

$prechangePath = Join-Path $script:Phase8EEvidenceRoot "stage3-obsidian-prechange.json"
if (-not (Test-Path -LiteralPath $prechangePath -PathType Leaf)) {
    throw "Stage 3 Obsidian prechange evidence is missing."
}
$prechange = Get-Content -Raw -LiteralPath $prechangePath | ConvertFrom-Json
$state = Get-Phase8EBoundaryState
if ($prechange.viewer_sid -ne $state.viewer_sid -or
        $prechange.obsidian_root -ne "C:\Users\Steve\AppData\Local\Programs\Obsidian" -or
        $prechange.obsidian_path -ne "C:\Users\Steve\AppData\Local\Programs\Obsidian\Obsidian.exe" -or
        $prechange.firewall_rule_name -ne "GRACI-Phase8E-Stage3-Obsidian-Viewer-Block") {
    throw "Stage 3 Obsidian rollback evidence is outside the exact boundary."
}
if ((Get-Item -LiteralPath $prechange.obsidian_root -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw "Refused to restore permissions on a reparse point."
}
$rule = Get-NetFirewallRule -Name $prechange.firewall_rule_name -ErrorAction SilentlyContinue
if ($null -ne $rule) {
    $application = $rule | Get-NetFirewallApplicationFilter
    $security = $rule | Get-NetFirewallSecurityFilter
    $expectedLocalUser = "D:(A;;CC;;;$($state.viewer_sid))"
    if ($rule.Direction -ne "Outbound" -or $rule.Action -ne "Block" -or
            $application.Program -ne $prechange.obsidian_path -or
            $security.LocalUser -ne $expectedLocalUser) {
        throw "The Stage 3 firewall rule no longer matches the exact rollback boundary."
    }
    Remove-NetFirewallRule -Name $prechange.firewall_rule_name
}
$restore = [Security.AccessControl.DirectorySecurity]::new()
$restore.SetSecurityDescriptorSddlForm($prechange.obsidian_root_sddl)
Set-Acl -LiteralPath $prechange.obsidian_root -AclObject $restore
if (-not $prechange.viewer_config_preexisted -and (Test-Path -LiteralPath $prechange.viewer_config_root)) {
    $configRoot = [IO.Path]::GetFullPath([string]$prechange.viewer_config_root).TrimEnd('\')
    $profileRoot = [IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $configRoot)))).TrimEnd('\')
    if ((Split-Path -Parent $profileRoot) -ne "C:\Users" -or
            (Split-Path -Leaf $profileRoot) -notlike "GRACI_Review*" -or
            ((Get-Item -LiteralPath $configRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "The Stage 3 viewer configuration is outside the exact rollback boundary."
    }
    Remove-Item -LiteralPath $configRoot -Recurse -Force
}
Remove-Item -LiteralPath $prechange.viewer_result_path -Force -ErrorAction SilentlyContinue
$viewerResultRoot = Split-Path -Parent $prechange.viewer_result_path
$viewerOutputFiles = @(
    (Join-Path $viewerResultRoot "stage3-obsidian.stdout.txt"),
    (Join-Path $viewerResultRoot "stage3-obsidian.stderr.txt")
)
Remove-Item -LiteralPath $viewerOutputFiles -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $script:Phase8ELauncherRoot "Test-ObsidianCandidate.ps1") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $script:Phase8ELauncherRoot "stage3-obsidian-test-state.json") -Force -ErrorAction SilentlyContinue
[pscustomobject]@{
    rolled_back = $true
    preserved_evidence = $script:Phase8EEvidenceRoot
    obsidian_owner_access_changed = $false
} | ConvertTo-Json -Compress | Write-Output
