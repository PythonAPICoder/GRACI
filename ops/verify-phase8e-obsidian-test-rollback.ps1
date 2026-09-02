[CmdletBinding()]
param()

. "$PSScriptRoot\phase8e-review-boundary-common.ps1"
Assert-Phase8EAdministrator

$prechangePath = Join-Path $script:Phase8EEvidenceRoot "stage3-obsidian-prechange.json"
if (-not (Test-Path -LiteralPath $prechangePath -PathType Leaf)) {
    throw "Stage 3 Obsidian prechange evidence is missing."
}
$prechange = Get-Content -Raw -LiteralPath $prechangePath | ConvertFrom-Json
$failures = [Collections.Generic.List[string]]::new()
if ($prechange.viewer_sid -ne (Get-Phase8EBoundaryState).viewer_sid) {
    $failures.Add("viewer SID mismatch")
}
if ((Get-Acl -LiteralPath $prechange.obsidian_root).Sddl -ne $prechange.obsidian_root_sddl) {
    $failures.Add("Obsidian folder ACL was not restored")
}
if (Get-NetFirewallRule -Name $prechange.firewall_rule_name -ErrorAction SilentlyContinue) {
    $failures.Add("Stage 3 firewall rule remains")
}
if (-not $prechange.viewer_config_preexisted -and
        (Test-Path -LiteralPath $prechange.viewer_config_root)) {
    $failures.Add("test-created viewer Obsidian configuration remains")
}
$viewerResultRoot = Split-Path -Parent $prechange.viewer_result_path
$testArtifacts = @(
    $prechange.viewer_result_path,
    (Join-Path $viewerResultRoot "stage3-obsidian.stdout.txt"),
    (Join-Path $viewerResultRoot "stage3-obsidian.stderr.txt"),
    (Join-Path $script:Phase8ELauncherRoot "Test-ObsidianCandidate.ps1"),
    (Join-Path $script:Phase8ELauncherRoot "stage3-obsidian-test-state.json")
)
foreach ($path in $testArtifacts) {
    if (Test-Path -LiteralPath $path) { $failures.Add("test artifact remains: $path") }
}
if (@(Get-Process -Name Obsidian -ErrorAction SilentlyContinue).Count -ne 0) {
    $failures.Add("Obsidian process remains")
}
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $prechange.obsidian_path).Hash.ToLowerInvariant()
$signature = Get-AuthenticodeSignature -LiteralPath $prechange.obsidian_path
if ($hash -ne "c01bbd79583037639f5422396cddb457ef48e89e159ca50a8492bbd1f1f10775") {
    $failures.Add("Obsidian executable hash changed")
}
if ($signature.Status -ne "Valid") { $failures.Add("Obsidian signature is no longer valid") }

$result = [ordered]@{
    schema_version = 1
    observed_at = [DateTimeOffset]::Now.ToString("o")
    obsidian_acl_restored = (Get-Acl -LiteralPath $prechange.obsidian_root).Sddl -eq $prechange.obsidian_root_sddl
    firewall_rule_present = [bool](Get-NetFirewallRule -Name $prechange.firewall_rule_name -ErrorAction SilentlyContinue)
    test_profile_artifacts_present = @($testArtifacts | Where-Object { Test-Path -LiteralPath $_ }).Count
    obsidian_process_count = @(Get-Process -Name Obsidian -ErrorAction SilentlyContinue).Count
    obsidian_hash = $hash
    obsidian_signature = $signature.Status.ToString()
    failures = @($failures)
    passed = $failures.Count -eq 0
}
$result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath `
    (Join-Path $script:Phase8EEvidenceRoot "stage3-obsidian-rollback-verification.json") -Encoding utf8
$result | ConvertTo-Json -Depth 4 -Compress | Write-Output
if ($failures.Count -ne 0) { exit 1 }
