[CmdletBinding()]
param()

. "$PSScriptRoot\phase8e-review-boundary-common.ps1"
Assert-Phase8EAdministrator

trap {
    try {
        [ordered]@{
            schema_version = 1
            observed_at = [DateTimeOffset]::Now.ToString("o")
            failure = $_.Exception.Message
        } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath `
            (Join-Path $script:Phase8EEvidenceRoot "stage3-dedicated-obsidian-bootstrap-failure.json") -Encoding utf8
    } catch {}
    exit 1
}

$sourceRoot = "C:\Users\Steve\AppData\Local\Programs\Obsidian"
$sourcePath = Join-Path $sourceRoot "Obsidian.exe"
$expectedHash = "c01bbd79583037639f5422396cddb457ef48e89e159ca50a8492bbd1f1f10775"
$expectedSigner = "CN=Dynalist Inc, O=Dynalist Inc, L=Oakville, S=Ontario, C=CA"
$expectedVersion = "1.13.4"
$ruleName = "GRACI-Phase8E-Stage3-Obsidian-Dedicated-Viewer-Block"
$ruleDisplayName = "GRACI Phase 8E dedicated Obsidian viewer outbound block"
$prechangePath = Join-Path $script:Phase8EEvidenceRoot "stage3-dedicated-obsidian-prechange.json"
$workerTarget = Join-Path $script:Phase8ELauncherRoot "Test-DedicatedObsidian.ps1"
$statePath = Join-Path $script:Phase8ELauncherRoot "stage3-dedicated-obsidian-state.json"
$evidenceResultPath = Join-Path $script:Phase8EEvidenceRoot "stage3-dedicated-obsidian-test-result.json"

$state = Get-Phase8EBoundaryState
$viewer = Get-LocalUser -Name $script:Phase8EViewerName -ErrorAction Stop
if ($viewer.SID.Value -ne $state.viewer_sid) { throw "Viewer SID mismatch." }
$viewerSid = [Security.Principal.SecurityIdentifier]::new($viewer.SID.Value)
$profiles = @(Get-CimInstance Win32_UserProfile | Where-Object SID -eq $viewerSid.Value)
if ($profiles.Count -ne 1 -or $profiles[0].Loaded) { throw "The exact unloaded viewer profile was not found." }
$profileRoot = [IO.Path]::GetFullPath($profiles[0].LocalPath).TrimEnd('\')
if ((Split-Path -Parent $profileRoot) -ne "C:\Users" -or (Split-Path -Leaf $profileRoot) -notlike "GRACI_Review*") {
    throw "The viewer profile is outside the exact boundary."
}
$destinationRoot = Join-Path $profileRoot "AppData\Local\Programs\Obsidian"
$destinationPath = Join-Path $destinationRoot "Obsidian.exe"
$viewerConfigRoot = Join-Path $profileRoot "AppData\Roaming\obsidian"
$viewerResultRoot = Join-Path $profileRoot "AppData\Local\GRACI\Stage3Dedicated"
$viewerResultPath = Join-Path $viewerResultRoot "stage3-dedicated-obsidian-result.json"
$vaultConfigRoot = Join-Path $script:Phase8EProjectionRoot ".obsidian"
$vaultConfigPath = Join-Path $vaultConfigRoot "app.json"

if (@(Get-Process -Name Obsidian -ErrorAction SilentlyContinue).Count -ne 0) { throw "Obsidian is already running." }
foreach ($path in @($sourceRoot, $sourcePath, $script:Phase8EProjectionRoot, $profileRoot)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "A required exact path is missing: $path" }
    if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "A required exact path is a reparse point: $path"
    }
}
if (@(Get-ChildItem -LiteralPath $sourceRoot -Force -Recurse | Where-Object {
        $_.Attributes -band [IO.FileAttributes]::ReparsePoint
    }).Count -ne 0) { throw "The verified source tree contains a reparse point." }
$sourceFile = Get-Item -LiteralPath $sourcePath
$sourceSignature = Get-AuthenticodeSignature -LiteralPath $sourcePath
$sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourcePath).Hash.ToLowerInvariant()
if ($sourceHash -ne $expectedHash -or $sourceFile.VersionInfo.FileVersion -ne $expectedVersion -or
        $sourceSignature.Status -ne "Valid" -or $sourceSignature.SignerCertificate.Subject -ne $expectedSigner) {
    throw "The local source no longer matches the verified Obsidian application."
}
foreach ($path in @($destinationRoot, $viewerConfigRoot, $vaultConfigRoot, $viewerResultRoot)) {
    if (Test-Path -LiteralPath $path) { throw "A dedicated-test destination already exists: $path" }
}
if (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue) { throw "The exact firewall rule already exists." }

$prechange = [ordered]@{
    schema_version = 1
    recorded_at = [DateTimeOffset]::Now.ToString("o")
    viewer_sid = $viewerSid.Value
    source_root = $sourceRoot
    source_path = $sourcePath
    destination_root = $destinationRoot
    destination_path = $destinationPath
    viewer_profile_root = $profileRoot
    viewer_config_root = $viewerConfigRoot
    viewer_result_root = $viewerResultRoot
    vault_config_root = $vaultConfigRoot
    firewall_rule_name = $ruleName
    created_paths_preexisted = $false
}
$prechange | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $prechangePath -Encoding utf8

function New-ExactAcl([string]$ViewerRights) {
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($entry in @(
        @("S-1-5-18", "FullControl"),
        @("S-1-5-32-544", "FullControl"),
        @($script:Phase8EExporterSid, "FullControl"),
        @($viewerSid.Value, $ViewerRights)
    )) {
        $sid = [Security.Principal.SecurityIdentifier]::new($entry[0])
        $rule = [Security.AccessControl.FileSystemAccessRule]::new(
            $sid, [Security.AccessControl.FileSystemRights]$entry[1],
            [Security.AccessControl.InheritanceFlags]"ContainerInherit, ObjectInherit",
            [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow)
        [void]$acl.AddAccessRule($rule)
    }
    return $acl
}

function Assert-ExactRemovablePath([string]$Path, [string]$Expected) {
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    if ($full -ne [IO.Path]::GetFullPath($Expected).TrimEnd('\')) { throw "Rollback path mismatch." }
    if (Test-Path -LiteralPath $full) {
        if ((Get-Item -LiteralPath $full -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Rollback refused a reparse point."
        }
    }
    return $full
}

function Remove-DedicatedChanges {
    Remove-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
    foreach ($pair in @(
        @($destinationRoot, (Join-Path $profileRoot "AppData\Local\Programs\Obsidian")),
        @($viewerConfigRoot, (Join-Path $profileRoot "AppData\Roaming\obsidian")),
        @($viewerResultRoot, (Join-Path $profileRoot "AppData\Local\GRACI")),
        @($vaultConfigRoot, (Join-Path $script:Phase8EProjectionRoot ".obsidian"))
    )) {
        $exact = Assert-ExactRemovablePath $pair[0] $pair[1]
        if (Test-Path -LiteralPath $exact) { Remove-Item -LiteralPath $exact -Recurse -Force }
    }
    Remove-Item -LiteralPath $workerTarget, $statePath -Force -ErrorAction SilentlyContinue
}

function Get-TreeDigest([string]$Root) {
    return @(
        Get-ChildItem -LiteralPath $Root -File -Recurse | Sort-Object FullName | ForEach-Object {
            [pscustomobject]@{
                Path = $_.FullName.Substring($Root.Length + 1)
                Length = $_.Length
                Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
            }
        }
    ) | ConvertTo-Json -Compress
}

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    [IO.File]::WriteAllText($Path, $Content, [Text.UTF8Encoding]::new($false))
}

try {
    $destinationParent = Split-Path -Parent $destinationRoot
    New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
    Copy-Item -LiteralPath $sourceRoot -Destination $destinationParent -Recurse -Force
    if (Get-ChildItem -LiteralPath $destinationRoot -Force -Recurse | Where-Object {
            $_.Attributes -band [IO.FileAttributes]::ReparsePoint
        }) { throw "The copied application contains a reparse point." }
    if ((Get-TreeDigest $sourceRoot) -ne (Get-TreeDigest $destinationRoot)) { throw "The dedicated copy differs from the verified source tree." }
    Set-Acl -LiteralPath $destinationRoot -AclObject (New-ExactAcl "ReadAndExecute, Synchronize")

    New-Item -ItemType Directory -Path $viewerConfigRoot, $viewerResultRoot, $vaultConfigRoot -Force | Out-Null
    Set-Acl -LiteralPath $viewerConfigRoot -AclObject (New-ExactAcl "Modify, Synchronize")
    Set-Acl -LiteralPath $viewerResultRoot -AclObject (New-ExactAcl "Modify, Synchronize")
    Set-Acl -LiteralPath $vaultConfigRoot -AclObject (New-ExactAcl "Modify, Synchronize")
    $obsidianConfig = @{ vaults = @{ "graci-review" = @{ path = $script:Phase8EProjectionRoot; ts = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds(); open = $true } } } |
        ConvertTo-Json -Depth 5
    Write-Utf8NoBom (Join-Path $viewerConfigRoot "obsidian.json") $obsidianConfig
    $vaultConfig = @{ showUnsupportedFiles = $false; alwaysUpdateLinks = $false } | ConvertTo-Json
    Write-Utf8NoBom $vaultConfigPath $vaultConfig

    $localUserSddl = "D:(A;;CC;;;$($viewerSid.Value))"
    New-NetFirewallRule -Name $ruleName -DisplayName $ruleDisplayName `
        -Group "GRACI Phase 8E Stage 3" -Direction Outbound -Action Block `
        -Program $destinationPath -Profile Any -Enabled True -LocalUser $localUserSddl | Out-Null
    $firewall = Get-NetFirewallRule -Name $ruleName -ErrorAction Stop
    $application = $firewall | Get-NetFirewallApplicationFilter
    $security = $firewall | Get-NetFirewallSecurityFilter
    if ($firewall.Direction -ne "Outbound" -or $firewall.Action -ne "Block" -or
            $firewall.Enabled -ne "True" -or $application.Program -ne $destinationPath -or
            $security.LocalUser -ne $localUserSddl) { throw "The viewer-only firewall rule was not established exactly." }

    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "test-phase8e-dedicated-obsidian-worker.ps1") -Destination $workerTarget -Force
    $bytes = [byte[]]::new(48)
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    $random.GetBytes($bytes); $random.Dispose()
    $secret = [Convert]::ToBase64String($bytes)
    $secure = ConvertTo-SecureString $secret -AsPlainText -Force
    Set-LocalUser -Name $script:Phase8EViewerName -Password $secure
    $credential = [Management.Automation.PSCredential]::new("$env:COMPUTERNAME\$script:Phase8EViewerName", $secure)
    $secret = $null
    $testProcess = Start-Process -FilePath "powershell.exe" -Credential $credential -WorkingDirectory "$env:SystemRoot\System32" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $workerTarget,
            "-ObsidianPath", $destinationPath, "-ProjectionRoot", $script:Phase8EProjectionRoot,
            "-ViewerProfileRoot", $profileRoot, "-ViewerConfigRoot", $viewerConfigRoot,
            "-ExpectedHash", $expectedHash, "-ExpectedViewerSid", $viewerSid.Value,
            "-ResultPath", $viewerResultPath) -Wait -PassThru -WindowStyle Hidden
    $secure.Dispose()
    if (Test-Path -LiteralPath $viewerResultPath -PathType Leaf) {
        Copy-Item -LiteralPath $viewerResultPath -Destination $evidenceResultPath -Force
    }
    if ($testProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $viewerResultPath -PathType Leaf)) {
        throw "The dedicated Obsidian synthetic test did not complete successfully."
    }
    $testResult = Get-Content -Raw -LiteralPath $viewerResultPath | ConvertFrom-Json
    if (-not $testResult.passed) { throw "The dedicated Obsidian synthetic test failed." }

    $ownerMarkdownReadable = $true
    $pointer = Get-Content -Raw -LiteralPath (Join-Path $script:Phase8EProjectionRoot "current.json") | ConvertFrom-Json
    $currentRoot = Join-Path (Join-Path $script:Phase8EProjectionRoot "generations") $pointer.generation_id
    foreach ($note in @(Get-ChildItem -LiteralPath $currentRoot -Filter "*.md" -File -Recurse)) {
        try { [void](Get-Content -Raw -LiteralPath $note.FullName) } catch { $ownerMarkdownReadable = $false }
    }
    if (-not $ownerMarkdownReadable -or -not (Test-Path -LiteralPath $vaultConfigPath -PathType Leaf)) {
        throw "The Product Owner read-access check failed."
    }
    $destinationSignature = Get-AuthenticodeSignature -LiteralPath $destinationPath
    $installedState = [ordered]@{
        schema_version = 1
        configured_at = [DateTimeOffset]::Now.ToString("o")
        viewer_sid = $viewerSid.Value
        destination_path = $destinationPath
        executable_hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $destinationPath).Hash.ToLowerInvariant()
        executable_version = (Get-Item -LiteralPath $destinationPath).VersionInfo.FileVersion
        signature = $destinationSignature.Status.ToString()
        signer = $destinationSignature.SignerCertificate.Subject
        vault_path = $script:Phase8EProjectionRoot
        firewall_rule_name = $ruleName
        firewall_local_user = $localUserSddl
        synthetic_test_passed = $true
        owner_can_read_synthetic_notes = $ownerMarkdownReadable
        product_owner_obsidian_changed = $false
        qualified_for_real_data = $false
    }
    $installedState | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statePath -Encoding utf8
    $installedState | ConvertTo-Json -Depth 5 | Set-Content `
        -LiteralPath (Join-Path $script:Phase8EEvidenceRoot "stage3-dedicated-obsidian-state.json") -Encoding utf8
    $installedState | ConvertTo-Json -Depth 5 -Compress | Write-Output
} catch {
    $failure = $_
    $rollbackSucceeded = $false
    $rollbackFailure = $null
    try { Remove-DedicatedChanges; $rollbackSucceeded = $true } catch { $rollbackFailure = $_.Exception.Message }
    [ordered]@{
        schema_version = 1
        observed_at = [DateTimeOffset]::Now.ToString("o")
        failure = $failure.Exception.Message
        rollback_succeeded = $rollbackSucceeded
        rollback_failure = $rollbackFailure
    } | ConvertTo-Json -Depth 4 | Set-Content `
        -LiteralPath (Join-Path $script:Phase8EEvidenceRoot "stage3-dedicated-obsidian-failure.json") -Encoding utf8
    if (-not $rollbackSucceeded) { throw "Dedicated Obsidian setup and rollback both failed; inspect evidence immediately." }
    throw $failure
}
