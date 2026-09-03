[CmdletBinding()]
param([switch]$VerifyOnly)

# HOST-SYSTEM-CHANGE-QUARANTINE: PO-DEC-039
# This launcher depends on the rejected AppLocker boundary. Keep its historical
# verification logic below, but fail before reading or changing host state.
throw "PHASE8E_APPLOCKER_BOUNDARY_QUARANTINED: routine launch is not approved until a replacement boundary is separately accepted and deployed."

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root = "E:\GRACI-Review-Projection"
$statePath = "C:\ProgramData\GRACI\Phase8E\boundary-state.json"
if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) { throw "BOUNDARY_STATE_MISSING" }
$state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
if ($state.projection_root -ne $root) { throw "BOUNDARY_ROOT_MISMATCH" }
$viewerSid = [Security.Principal.SecurityIdentifier]::new($state.viewer_sid)
$acl = Get-Acl -LiteralPath $root
$viewerRules = @($acl.Access | Where-Object {
    $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq $viewerSid.Value -and
    $_.AccessControlType -eq "Allow"
})
$writeMask = [Security.AccessControl.FileSystemRights]::WriteData -bor
    [Security.AccessControl.FileSystemRights]::AppendData -bor
    [Security.AccessControl.FileSystemRights]::Delete -bor
    [Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor
    [Security.AccessControl.FileSystemRights]::ChangePermissions -bor
    [Security.AccessControl.FileSystemRights]::TakeOwnership
if ($viewerRules.Count -ne 1 -or
        -not ($viewerRules[0].FileSystemRights -band [Security.AccessControl.FileSystemRights]::ReadAndExecute) -or
        ($viewerRules[0].FileSystemRights -band $writeMask)) { throw "BOUNDARY_ACL_INVALID" }
$appLocker = (Get-AppLockerPolicy -Effective).ToXml()
$escapedSid = [regex]::Escape($viewerSid.Value)
if (([regex]::Matches($appLocker, "UserOrGroupSid=`"$escapedSid`" Action=`"Deny`"")).Count -ne 8) {
    throw "APPLICATION_CONTROL_INVALID"
}
foreach ($collection in @("Exe", "Msi", "Script", "Dll")) {
    if ($appLocker -notmatch "RuleCollection Type=`"$collection`" EnforcementMode=`"Enabled`"") {
        throw "APPLICATION_CONTROL_INVALID"
    }
}
foreach ($path in @($root, (Join-Path $root "current.json"))) {
    if (-not (Test-Path -LiteralPath $path)) { throw "PROJECTION_MISSING" }
    if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "REPARSE_POINT_REJECTED"
    }
}
$pointer = Get-Content -Raw -LiteralPath (Join-Path $root "current.json") | ConvertFrom-Json
if ($pointer.generation_id -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$') { throw "GENERATION_ID_INVALID" }
$generation = Join-Path (Join-Path $root "generations") $pointer.generation_id
if (-not (Test-Path -LiteralPath $generation -PathType Container) -or
        ((Get-Item -LiteralPath $generation -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw "GENERATION_ROOT_INVALID"
}
$manifestPath = Join-Path $generation "manifest.json"
$hashPath = Join-Path $generation "manifest.sha256"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $hashPath -PathType Leaf)) { throw "MANIFEST_MISSING" }
$manifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $manifestPath).Hash.ToLowerInvariant()
$recordedHash = (Get-Content -Raw -LiteralPath $hashPath).Trim()
if ($manifestHash -ne $recordedHash -or $manifestHash -ne $pointer.manifest_sha256) { throw "MANIFEST_TAMPERED" }
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
if (-not $manifest.complete -or $manifest.generation_id -ne $pointer.generation_id) { throw "MANIFEST_INCOMPLETE" }
$expected = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
[void]$expected.Add("manifest.json"); [void]$expected.Add("manifest.sha256")
foreach ($entry in $manifest.entries) {
    if ($entry.output_path -notmatch '^[A-Za-z0-9][A-Za-z0-9._/-]{0,239}$' -or $entry.output_path -match '(^|/)\.\.(/|$)') {
        throw "OUTPUT_PATH_INVALID"
    }
    $output = Join-Path $generation ($entry.output_path -replace '/', '\')
    if (-not (Test-Path -LiteralPath $output -PathType Leaf)) { throw "OUTPUT_MISSING" }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $output).Hash.ToLowerInvariant() -ne $entry.output_hash) {
        throw "OUTPUT_TAMPERED"
    }
    [void]$expected.Add($entry.output_path)
}
foreach ($file in Get-ChildItem -LiteralPath $generation -File -Recurse) {
    $relative = $file.FullName.Substring($generation.Length + 1).Replace('\', '/')
    if (-not $expected.Contains($relative)) { throw "UNMANIFESTED_OUTPUT" }
}
if ($VerifyOnly) {
    $qualification = "C:\ProgramData\GRACI\Phase8E\qualified-application.json"
    if (-not (Test-Path -LiteralPath $qualification -PathType Leaf)) {
        [pscustomobject]@{
            passed = $true
            generation_id = $pointer.generation_id
            application_qualified = $false
            application_launched = $false
        } | ConvertTo-Json -Compress | Write-Output
        exit 0
    }
}
$qualification = "C:\ProgramData\GRACI\Phase8E\qualified-application.json"
if (-not (Test-Path -LiteralPath $qualification -PathType Leaf)) { throw "APPLICATION_NOT_QUALIFIED" }
$qualified = Get-Content -Raw -LiteralPath $qualification | ConvertFrom-Json
$applicationPath = "C:\Users\GRACI_Review\AppData\Local\Programs\Obsidian\Obsidian.exe"
$applicationRoot = Split-Path -Parent $applicationPath
$viewerConfigRoot = "C:\Users\GRACI_Review\AppData\Roaming\obsidian"
$vaultConfigRoot = Join-Path $root ".obsidian"
$expectedHash = "c01bbd79583037639f5422396cddb457ef48e89e159ca50a8492bbd1f1f10775"
$expectedSigner = "CN=Dynalist Inc, O=Dynalist Inc, L=Oakville, S=Ontario, C=CA"
$expectedThumbprint = "20B5809A5B1C52EB05EC7672673920913E0ED26D"
$firewallRuleName = "GRACI-Phase8E-Stage3-Obsidian-Dedicated-Viewer-Block"
$expectedLocalUser = "D:(A;;CC;;;$($viewerSid.Value))"
if ($qualified.schema_version -ne 1 -or $qualified.authority -ne "PO-DEC-033" -or
        $qualified.viewer_sid -ne $viewerSid.Value -or
        $qualified.application_path -ne $applicationPath -or
        $qualified.application_sha256 -ne $expectedHash -or
        $qualified.application_version -ne "1.13.4" -or
        $qualified.signature_status -ne "Valid" -or
        $qualified.signer_subject -ne $expectedSigner -or
        $qualified.signer_thumbprint -ne $expectedThumbprint -or
        $qualified.firewall_rule_name -ne $firewallRuleName -or
        $qualified.firewall_local_user -ne $expectedLocalUser -or
        $qualified.vault_path -ne $root -or
        $qualified.viewer_config_root -ne $viewerConfigRoot -or
        $qualified.product_owner_accepted -ne $true -or
        $qualified.routine_launch_authorized -ne $true -or
        $qualified.real_data_authorized -ne $false -or
        $qualified.community_plugins_allowed -ne $false) {
    throw "QUALIFICATION_RECORD_INVALID"
}
foreach ($path in @($applicationRoot, $applicationPath, $viewerConfigRoot, $vaultConfigRoot)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "QUALIFIED_PATH_MISSING" }
    if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "QUALIFIED_PATH_REPARSE_REJECTED"
    }
}
if (@(Get-ChildItem -LiteralPath $applicationRoot -Force -Recurse | Where-Object {
        $_.Attributes -band [IO.FileAttributes]::ReparsePoint
    }).Count -ne 0) { throw "QUALIFIED_APPLICATION_REPARSE_REJECTED" }
$application = Get-Item -LiteralPath $applicationPath
$signature = Get-AuthenticodeSignature -LiteralPath $applicationPath
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $applicationPath).Hash.ToLowerInvariant() -ne $expectedHash -or
        $application.VersionInfo.FileVersion -ne "1.13.4" -or
        $signature.Status -ne "Valid" -or
        $signature.SignerCertificate.Subject -ne $expectedSigner -or
        $signature.SignerCertificate.Thumbprint -ne $expectedThumbprint) {
    throw "QUALIFIED_APPLICATION_CHANGED"
}
$firewall = Get-NetFirewallRule -Name $firewallRuleName -ErrorAction Stop
$applicationFilter = $firewall | Get-NetFirewallApplicationFilter
$securityFilter = $firewall | Get-NetFirewallSecurityFilter
if ($firewall.Direction -ne "Outbound" -or $firewall.Action -ne "Block" -or
        $firewall.Enabled -ne "True" -or $applicationFilter.Program -ne $applicationPath -or
        $securityFilter.LocalUser -ne $expectedLocalUser) { throw "QUALIFIED_FIREWALL_INVALID" }
$obsidianConfigPath = Join-Path $viewerConfigRoot "obsidian.json"
if (-not (Test-Path -LiteralPath $obsidianConfigPath -PathType Leaf)) { throw "OBSIDIAN_CONFIGURATION_MISSING" }
$configBytes = [IO.File]::ReadAllBytes($obsidianConfigPath)
if ($configBytes.Length -ge 3 -and $configBytes[0] -eq 0xef -and
        $configBytes[1] -eq 0xbb -and $configBytes[2] -eq 0xbf) {
    throw "OBSIDIAN_CONFIGURATION_ENCODING_INVALID"
}
$obsidianConfig = Get-Content -Raw -LiteralPath $obsidianConfigPath | ConvertFrom-Json
$registeredVaults = @($obsidianConfig.vaults.PSObject.Properties | ForEach-Object Value | Where-Object {
    $_.path -and [IO.Path]::GetFullPath([string]$_.path).TrimEnd('\') -eq $root
})
if ($registeredVaults.Count -ne 1) { throw "OBSIDIAN_VAULT_REGISTRATION_INVALID" }
$corePluginsPath = Join-Path $vaultConfigRoot "core-plugins.json"
if (-not (Test-Path -LiteralPath $corePluginsPath -PathType Leaf)) { throw "CORE_PLUGIN_POLICY_MISSING" }
$corePlugins = Get-Content -Raw -LiteralPath $corePluginsPath | ConvertFrom-Json
foreach ($plugin in @("audio-recorder", "bases", "canvas", "daily-notes", "file-recovery",
        "markdown-importer", "note-composer", "publish", "sync", "templates", "webviewer")) {
    $property = $corePlugins.PSObject.Properties[$plugin]
    if ($null -eq $property -or $property.Value -ne $false) { throw "CORE_PLUGIN_POLICY_INVALID" }
}
$communityPluginsPath = Join-Path $vaultConfigRoot "community-plugins.json"
if (Test-Path -LiteralPath $communityPluginsPath -PathType Leaf) {
    if ([IO.File]::ReadAllText($communityPluginsPath).Trim() -ne "[]") {
        throw "COMMUNITY_PLUGIN_LIST_INVALID"
    }
}
$pluginsRoot = Join-Path $vaultConfigRoot "plugins"
if (Test-Path -LiteralPath $pluginsRoot) {
    if ((Get-Item -LiteralPath $pluginsRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint -or
            @(Get-ChildItem -LiteralPath $pluginsRoot -Force).Count -ne 0) {
        throw "COMMUNITY_PLUGIN_DIRECTORY_INVALID"
    }
}
if ($VerifyOnly) {
    [pscustomobject]@{
        passed = $true
        generation_id = $pointer.generation_id
        application_qualified = $true
        application_launched = $false
    } | ConvertTo-Json -Compress | Write-Output
    exit 0
}
$activeSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
if ($activeSid -ne $viewerSid.Value) { throw "VIEWER_IDENTITY_REQUIRED" }
$viewerProfileRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $viewerConfigRoot))
$env:USERPROFILE = $viewerProfileRoot
$env:APPDATA = Split-Path -Parent $viewerConfigRoot
$env:LOCALAPPDATA = Join-Path $viewerProfileRoot "AppData\Local"
$process = Start-Process -FilePath $applicationPath -ArgumentList @(
    "--disable-gpu",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-default-apps",
    "--user-data-dir=$viewerConfigRoot",
    $root
) -PassThru
[pscustomobject]@{
    passed = $true
    generation_id = $pointer.generation_id
    application_qualified = $true
    application_launched = $true
    process_id = $process.Id
} | ConvertTo-Json -Compress | Write-Output
exit 0
