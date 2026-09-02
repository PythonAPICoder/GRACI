[CmdletBinding()]
param()

. "$PSScriptRoot\phase8e-review-boundary-common.ps1"
Assert-Phase8EAdministrator

$obsidianRoot = "C:\Users\Steve\AppData\Local\Programs\Obsidian"
$obsidianPath = Join-Path $obsidianRoot "Obsidian.exe"
$expectedHash = "c01bbd79583037639f5422396cddb457ef48e89e159ca50a8492bbd1f1f10775"
$expectedSigner = "CN=Dynalist Inc, O=Dynalist Inc, L=Oakville, S=Ontario, C=CA"
$expectedVersion = "1.13.4"
$ruleName = "GRACI-Phase8E-Stage3-Obsidian-Viewer-Block"
$ruleDisplayName = "GRACI Phase 8E Stage 3 Obsidian viewer outbound block"
$prechangePath = Join-Path $script:Phase8EEvidenceRoot "stage3-obsidian-prechange.json"
$evidenceResultPath = Join-Path $script:Phase8EEvidenceRoot "stage3-obsidian-test-result.json"
$launcherStatePath = Join-Path $script:Phase8ELauncherRoot "stage3-obsidian-test-state.json"
$workerTarget = Join-Path $script:Phase8ELauncherRoot "Test-ObsidianCandidate.ps1"

$state = Get-Phase8EBoundaryState
$viewer = Get-LocalUser -Name $script:Phase8EViewerName -ErrorAction Stop
if ($viewer.SID.Value -ne $state.viewer_sid) { throw "Viewer SID mismatch." }
$viewerSid = [Security.Principal.SecurityIdentifier]::new($viewer.SID.Value)
if (@(Get-Process -Name Obsidian -ErrorAction SilentlyContinue).Count -ne 0) {
    throw "Obsidian is already running; the bounded test refuses to continue."
}
if (-not (Test-Path -LiteralPath $obsidianPath -PathType Leaf)) { throw "Exact Obsidian executable is missing." }
foreach ($path in @($obsidianRoot, $obsidianPath)) {
    if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "An Obsidian candidate path is a reparse point."
    }
}
if (@(Get-ChildItem -LiteralPath $obsidianRoot -Force -Recurse | Where-Object {
        $_.Attributes -band [IO.FileAttributes]::ReparsePoint
    }).Count -ne 0) { throw "The Obsidian installation contains a reparse point." }
$file = Get-Item -LiteralPath $obsidianPath
$signature = Get-AuthenticodeSignature -LiteralPath $obsidianPath
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $obsidianPath).Hash.ToLowerInvariant()
if ($hash -ne $expectedHash -or $file.VersionInfo.FileVersion -ne $expectedVersion -or
        $signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -ne $expectedSigner) {
    throw "The Obsidian candidate no longer matches the inspected file."
}
if (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue) {
    throw "The exact Stage 3 firewall rule already exists."
}
$profile = @(Get-CimInstance Win32_UserProfile | Where-Object SID -eq $viewerSid.Value)
if ($profile.Count -ne 1 -or $profile[0].Loaded) { throw "The exact unloaded viewer profile was not found." }
$profileRoot = [IO.Path]::GetFullPath($profile[0].LocalPath).TrimEnd('\')
if ((Split-Path -Parent $profileRoot) -ne "C:\Users" -or
        (Split-Path -Leaf $profileRoot) -notlike "GRACI_Review*") {
    throw "The viewer profile is outside the exact Stage 3 boundary."
}
$viewerConfigRoot = Join-Path $profileRoot "AppData\Roaming\obsidian"
$viewerResultPath = Join-Path $profileRoot "AppData\Local\GRACI\stage3-obsidian-result.json"
if (Test-Path -LiteralPath $prechangePath -PathType Leaf) {
    $prechange = Get-Content -Raw -LiteralPath $prechangePath | ConvertFrom-Json
    if ($prechange.viewer_sid -ne $viewerSid.Value -or
            $prechange.obsidian_root -ne $obsidianRoot -or
            $prechange.obsidian_path -ne $obsidianPath -or
            $prechange.firewall_rule_name -ne $ruleName -or
            $prechange.firewall_rule_preexisted -or
            $prechange.obsidian_root_sddl -ne (Get-Acl -LiteralPath $obsidianRoot).Sddl -or
            $prechange.viewer_config_root -ne $viewerConfigRoot -or
            $prechange.viewer_result_path -ne $viewerResultPath -or
            (-not $prechange.viewer_config_preexisted -and (Test-Path -LiteralPath $viewerConfigRoot))) {
        throw "Existing Stage 3 prechange evidence does not match the restored baseline."
    }
} else {
    $prechange = [ordered]@{
        schema_version = 1
        recorded_at = [DateTimeOffset]::Now.ToString("o")
        viewer_sid = $viewerSid.Value
        obsidian_root = $obsidianRoot
        obsidian_path = $obsidianPath
        obsidian_root_sddl = (Get-Acl -LiteralPath $obsidianRoot).Sddl
        firewall_rule_name = $ruleName
        firewall_rule_preexisted = $false
        viewer_config_root = $viewerConfigRoot
        viewer_config_preexisted = Test-Path -LiteralPath $viewerConfigRoot
        viewer_result_path = $viewerResultPath
    }
    $prechange | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $prechangePath -Encoding utf8
}

function Restore-Phase8EObsidianTest {
    Remove-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
    $restore = [Security.AccessControl.DirectorySecurity]::new()
    $restore.SetSecurityDescriptorSddlForm($prechange.obsidian_root_sddl)
    Set-Acl -LiteralPath $obsidianRoot -AclObject $restore
    if (-not $prechange.viewer_config_preexisted -and (Test-Path -LiteralPath $viewerConfigRoot)) {
        if ((Get-Item -LiteralPath $viewerConfigRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refused to remove a reparse-point viewer configuration root."
        }
        Remove-Item -LiteralPath $viewerConfigRoot -Recurse -Force
    }
    Remove-Item -LiteralPath $viewerResultPath -Force -ErrorAction SilentlyContinue
    $viewerResultRoot = Split-Path -Parent $viewerResultPath
    $viewerOutputFiles = @(
        (Join-Path $viewerResultRoot "stage3-obsidian.stdout.txt"),
        (Join-Path $viewerResultRoot "stage3-obsidian.stderr.txt")
    )
    Remove-Item -LiteralPath $viewerOutputFiles -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $workerTarget, $launcherStatePath -Force -ErrorAction SilentlyContinue
}

try {
    $acl = Get-Acl -LiteralPath $obsidianRoot
    $accessRule = [Security.AccessControl.FileSystemAccessRule]::new(
        $viewerSid,
        [Security.AccessControl.FileSystemRights]"ReadAndExecute, Synchronize",
        [Security.AccessControl.InheritanceFlags]"ContainerInherit, ObjectInherit",
        [Security.AccessControl.PropagationFlags]::None,
        [Security.AccessControl.AccessControlType]::Allow
    )
    [void]$acl.AddAccessRule($accessRule)
    Set-Acl -LiteralPath $obsidianRoot -AclObject $acl

    $localUserSddl = "D:(A;;CC;;;$($viewerSid.Value))"
    New-NetFirewallRule -Name $ruleName -DisplayName $ruleDisplayName `
        -Group "GRACI Phase 8E Stage 3" -Direction Outbound -Action Block `
        -Program $obsidianPath -Profile Any -Enabled True -LocalUser $localUserSddl | Out-Null

    $rootRules = @((Get-Acl -LiteralPath $obsidianRoot).Access | Where-Object {
        $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq $viewerSid.Value -and
        $_.AccessControlType -eq "Allow"
    })
    $fileRules = @((Get-Acl -LiteralPath $obsidianPath).Access | Where-Object {
        $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq $viewerSid.Value -and
        $_.AccessControlType -eq "Allow"
    })
    $writeMask = [Security.AccessControl.FileSystemRights]::WriteData -bor
        [Security.AccessControl.FileSystemRights]::AppendData -bor
        [Security.AccessControl.FileSystemRights]::Delete -bor
        [Security.AccessControl.FileSystemRights]::ChangePermissions -bor
        [Security.AccessControl.FileSystemRights]::TakeOwnership
    if ($rootRules.Count -ne 1 -or $fileRules.Count -ne 1 -or
            -not ($fileRules[0].FileSystemRights -band [Security.AccessControl.FileSystemRights]::ReadAndExecute) -or
            ($rootRules[0].FileSystemRights -band $writeMask) -or ($fileRules[0].FileSystemRights -band $writeMask)) {
        throw "The exact Obsidian read-and-execute ACL was not established."
    }
    $firewall = Get-NetFirewallRule -Name $ruleName -ErrorAction Stop
    $application = $firewall | Get-NetFirewallApplicationFilter
    $security = $firewall | Get-NetFirewallSecurityFilter
    if ($firewall.Direction -ne "Outbound" -or $firewall.Action -ne "Block" -or
            $firewall.Enabled -ne "True" -or $application.Program -ne $obsidianPath -or
            $security.LocalUser -ne $localUserSddl) {
        throw "The exact viewer-only Obsidian firewall rule was not established."
    }

    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "test-phase8e-obsidian-worker.ps1") `
        -Destination $workerTarget -Force
    Remove-Item -LiteralPath $viewerResultPath -Force -ErrorAction SilentlyContinue
    $bytes = [byte[]]::new(48)
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    $random.GetBytes($bytes); $random.Dispose()
    $secret = [Convert]::ToBase64String($bytes)
    $secure = ConvertTo-SecureString $secret -AsPlainText -Force
    Set-LocalUser -Name $script:Phase8EViewerName -Password $secure
    $credential = [Management.Automation.PSCredential]::new("$env:COMPUTERNAME\$script:Phase8EViewerName", $secure)
    $secret = $null
    $start = @{
        FilePath = "powershell.exe"
        Credential = $credential
        WorkingDirectory = "$env:SystemRoot\System32"
        ArgumentList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $workerTarget,
            "-ObsidianPath", $obsidianPath, "-ProjectionRoot", $script:Phase8EProjectionRoot,
            "-ExpectedHash", $expectedHash, "-ExpectedViewerSid", $viewerSid.Value,
            "-ResultPath", $viewerResultPath)
        Wait = $true
        PassThru = $true
        WindowStyle = "Hidden"
    }
    $testProcess = Start-Process @start
    $secure.Dispose()
    if (Test-Path -LiteralPath $viewerResultPath -PathType Leaf) {
        Copy-Item -LiteralPath $viewerResultPath -Destination `
            (Join-Path $script:Phase8EEvidenceRoot "stage3-obsidian-test-last-worker-result.json") -Force
    }
    $viewerLog = Join-Path $viewerConfigRoot "obsidian.log"
    if (Test-Path -LiteralPath $viewerLog -PathType Leaf) {
        Copy-Item -LiteralPath $viewerLog -Destination `
            (Join-Path $script:Phase8EEvidenceRoot "stage3-obsidian-test-last.log") -Force
    }
    if ($testProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $viewerResultPath -PathType Leaf)) {
        throw "The actual viewer-token Obsidian test did not complete successfully."
    }
    $testResult = Get-Content -Raw -LiteralPath $viewerResultPath | ConvertFrom-Json
    if (-not $testResult.passed) { throw "The actual viewer-token Obsidian test failed." }
    Copy-Item -LiteralPath $viewerResultPath -Destination $evidenceResultPath -Force
    $testState = [ordered]@{
        schema_version = 1
        configured_at = [DateTimeOffset]::Now.ToString("o")
        viewer_sid = $viewerSid.Value
        obsidian_path = $obsidianPath
        obsidian_hash = $hash
        obsidian_version = $file.VersionInfo.FileVersion
        signer = $signature.SignerCertificate.Subject
        firewall_rule_name = $ruleName
        firewall_local_user = $localUserSddl
        synthetic_test_passed = $true
        qualified_for_routine_launch = $false
    }
    $testState | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $launcherStatePath -Encoding utf8
    $testState | ConvertTo-Json -Depth 4 | Set-Content `
        -LiteralPath (Join-Path $script:Phase8EEvidenceRoot "stage3-obsidian-test-state.json") -Encoding utf8
    $testState | ConvertTo-Json -Depth 4 -Compress | Write-Output
} catch {
    $failure = $_
    $rollbackSucceeded = $false
    $rollbackFailure = $null
    try {
        Restore-Phase8EObsidianTest
        $rollbackSucceeded = $true
    } catch {
        $rollbackFailure = $_.Exception.Message
    }
    [ordered]@{
        schema_version = 1
        observed_at = [DateTimeOffset]::Now.ToString("o")
        failure = $failure.Exception.Message
        rollback_succeeded = $rollbackSucceeded
        rollback_failure = $rollbackFailure
    } | ConvertTo-Json -Depth 4 | Set-Content `
        -LiteralPath (Join-Path $script:Phase8EEvidenceRoot "stage3-obsidian-test-failure.json") -Encoding utf8
    if (-not $rollbackSucceeded) { throw "Stage 3 test and rollback both failed; inspect evidence immediately." }
    throw $failure
}
