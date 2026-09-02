[CmdletBinding()]
param()

. "$PSScriptRoot\phase8e-review-boundary-common.ps1"
Assert-Phase8EAdministrator

$authority = "PO-DEC-033"
$applicationPath = "C:\Users\GRACI_Review\AppData\Local\Programs\Obsidian\Obsidian.exe"
$expectedHash = "c01bbd79583037639f5422396cddb457ef48e89e159ca50a8492bbd1f1f10775"
$expectedVersion = "1.13.4"
$expectedSigner = "CN=Dynalist Inc, O=Dynalist Inc, L=Oakville, S=Ontario, C=CA"
$expectedThumbprint = "20B5809A5B1C52EB05EC7672673920913E0ED26D"
$firewallRuleName = "GRACI-Phase8E-Stage3-Obsidian-Dedicated-Viewer-Block"
$launcherPath = Join-Path $script:Phase8ELauncherRoot "Open-GRACIReview.ps1"
$qualificationPath = Join-Path $script:Phase8ELauncherRoot "qualified-application.json"
$launcherStatePath = Join-Path $script:Phase8ELauncherRoot "boundary-state.json"
$evidenceStatePath = Join-Path $script:Phase8EEvidenceRoot "boundary-state.json"
$dedicatedStatePath = Join-Path $script:Phase8EEvidenceRoot "stage3-dedicated-obsidian-state.json"
$prechangeRoot = Join-Path $script:Phase8EEvidenceRoot "stage3-routine-launch-prechange"
$resultPath = Join-Path $script:Phase8EEvidenceRoot "stage3-routine-launch-result.json"
$vaultConfigRoot = Join-Path $script:Phase8EProjectionRoot ".obsidian"
$corePluginsPath = Join-Path $vaultConfigRoot "core-plugins.json"
$communityPluginsPath = Join-Path $vaultConfigRoot "community-plugins.json"

$state = Get-Phase8EBoundaryState
$viewer = Get-LocalUser -Name $script:Phase8EViewerName -ErrorAction Stop
if ($viewer.SID.Value -ne $state.viewer_sid) { throw "Viewer SID mismatch." }
$viewerSid = [Security.Principal.SecurityIdentifier]::new($viewer.SID.Value)
$profiles = @(Get-CimInstance Win32_UserProfile | Where-Object SID -eq $viewerSid.Value)
if ($profiles.Count -ne 1 -or $profiles[0].Loaded) { throw "The exact unloaded viewer profile was not found." }
$profileRoot = [IO.Path]::GetFullPath($profiles[0].LocalPath).TrimEnd('\')
$viewerConfigRoot = Join-Path $profileRoot "AppData\Roaming\obsidian"
$viewerResultRoot = Join-Path $profileRoot "AppData\Local\GRACI\Stage3Dedicated"
$launcherOutputPath = Join-Path $viewerResultRoot "routine-launch.stdout.txt"
$launcherErrorPath = Join-Path $viewerResultRoot "routine-launch.stderr.txt"
if ($profileRoot -ne "C:\Users\GRACI_Review" -or
        $applicationPath -ne (Join-Path $profileRoot "AppData\Local\Programs\Obsidian\Obsidian.exe")) {
    throw "The dedicated profile paths are not exact."
}
foreach ($path in @($script:Phase8EProjectionRoot, $script:Phase8ELauncherRoot,
        $script:Phase8EEvidenceRoot, $applicationPath, $viewerConfigRoot, $viewerResultRoot, $vaultConfigRoot,
        $launcherPath, $launcherStatePath, $evidenceStatePath, $dedicatedStatePath)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "A required exact path is missing: $path" }
    if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "A required exact path is a reparse point: $path"
    }
}
if (Test-Path -LiteralPath $qualificationPath) { throw "A qualification record already exists." }
$application = Get-Item -LiteralPath $applicationPath
$signature = Get-AuthenticodeSignature -LiteralPath $applicationPath
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $applicationPath).Hash.ToLowerInvariant() -ne $expectedHash -or
        $application.VersionInfo.FileVersion -ne $expectedVersion -or $signature.Status -ne "Valid" -or
        $signature.SignerCertificate.Subject -ne $expectedSigner -or
        $signature.SignerCertificate.Thumbprint -ne $expectedThumbprint) {
    throw "The dedicated application no longer matches the accepted candidate."
}
$dedicatedState = Get-Content -Raw -LiteralPath $dedicatedStatePath | ConvertFrom-Json
if ($dedicatedState.viewer_sid -ne $viewerSid.Value -or
        $dedicatedState.destination_path -ne $applicationPath -or
        $dedicatedState.executable_hash -ne $expectedHash -or
        -not $dedicatedState.synthetic_test_passed -or
        -not $dedicatedState.clean_configuration_parse -or
        $dedicatedState.qualified_for_real_data) {
    throw "The dedicated candidate evidence does not match the accepted synthetic result."
}
$localUserSddl = "D:(A;;CC;;;$($viewerSid.Value))"
$firewall = Get-NetFirewallRule -Name $firewallRuleName -ErrorAction Stop
$applicationFilter = $firewall | Get-NetFirewallApplicationFilter
$securityFilter = $firewall | Get-NetFirewallSecurityFilter
if ($firewall.Direction -ne "Outbound" -or $firewall.Action -ne "Block" -or
        $firewall.Enabled -ne "True" -or $applicationFilter.Program -ne $applicationPath -or
        $securityFilter.LocalUser -ne $localUserSddl) { throw "The exact viewer-only firewall rule is not active." }
$dedicatedProcesses = @(Get-Process -Name Obsidian -ErrorAction SilentlyContinue | Where-Object {
    try { $_.Path -eq $applicationPath } catch { $false }
})
if ($dedicatedProcesses.Count -ne 0) { throw "The dedicated Obsidian copy is already running." }

if (Test-Path -LiteralPath $prechangeRoot) {
    $prechangeStatePath = Join-Path $prechangeRoot "state.json"
    if (-not (Test-Path -LiteralPath $prechangeStatePath -PathType Leaf)) {
        throw "Routine-launch prechange evidence is incomplete."
    }
    $prechangeState = Get-Content -Raw -LiteralPath $prechangeStatePath | ConvertFrom-Json
    if ($prechangeState.authority -ne $authority -or $prechangeState.launcher_path -ne $launcherPath -or
            $prechangeState.qualification_path -ne $qualificationPath -or
            $prechangeState.qualification_preexisted -or
            $prechangeState.launcher_sha256 -ne
                (Get-FileHash -Algorithm SHA256 -LiteralPath $launcherPath).Hash.ToLowerInvariant()) {
        throw "Existing routine-launch prechange evidence does not match the restored baseline."
    }
    foreach ($backup in @("Open-GRACIReview.ps1", "launcher-boundary-state.json",
            "evidence-boundary-state.json", "core-plugins.json")) {
        if (-not (Test-Path -LiteralPath (Join-Path $prechangeRoot $backup) -PathType Leaf)) {
            throw "Routine-launch prechange evidence is incomplete."
        }
    }
    if (Test-Path -LiteralPath $communityPluginsPath -PathType Leaf) {
        if ([IO.File]::ReadAllText($communityPluginsPath).Trim() -ne "[]" -or
                (Get-Item -LiteralPath $communityPluginsPath).LastWriteTime -lt
                    [DateTimeOffset]::Parse($prechangeState.recorded_at).LocalDateTime) {
            throw "Unexpected community-plugin state exists after the failed promotion."
        }
        Remove-Item -LiteralPath $communityPluginsPath -Force
    }
} else {
    New-Item -ItemType Directory -Path $prechangeRoot | Out-Null
    Copy-Item -LiteralPath $launcherPath -Destination (Join-Path $prechangeRoot "Open-GRACIReview.ps1")
    Copy-Item -LiteralPath $launcherStatePath -Destination (Join-Path $prechangeRoot "launcher-boundary-state.json")
    Copy-Item -LiteralPath $evidenceStatePath -Destination (Join-Path $prechangeRoot "evidence-boundary-state.json")
    if (Test-Path -LiteralPath $corePluginsPath -PathType Leaf) {
        Copy-Item -LiteralPath $corePluginsPath -Destination (Join-Path $prechangeRoot "core-plugins.json")
    }
    if (Test-Path -LiteralPath $communityPluginsPath -PathType Leaf) {
        Copy-Item -LiteralPath $communityPluginsPath -Destination (Join-Path $prechangeRoot "community-plugins.json")
    }
    [ordered]@{
        schema_version = 1
        recorded_at = [DateTimeOffset]::Now.ToString("o")
        authority = $authority
        launcher_path = $launcherPath
        launcher_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $launcherPath).Hash.ToLowerInvariant()
        qualification_path = $qualificationPath
        qualification_preexisted = $false
        core_plugins_preexisted = Test-Path -LiteralPath $corePluginsPath -PathType Leaf
        community_plugins_preexisted = Test-Path -LiteralPath $communityPluginsPath -PathType Leaf
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $prechangeRoot "state.json") -Encoding utf8
}

function Restore-RoutineLaunch {
    foreach ($process in @(Get-Process -Name Obsidian -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Path -eq $applicationPath } catch { $false }
    })) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    Copy-Item -LiteralPath (Join-Path $prechangeRoot "Open-GRACIReview.ps1") -Destination $launcherPath -Force
    Copy-Item -LiteralPath (Join-Path $prechangeRoot "launcher-boundary-state.json") -Destination $launcherStatePath -Force
    Copy-Item -LiteralPath (Join-Path $prechangeRoot "evidence-boundary-state.json") -Destination $evidenceStatePath -Force
    Remove-Item -LiteralPath $qualificationPath -Force -ErrorAction SilentlyContinue
    $savedCorePlugins = Join-Path $prechangeRoot "core-plugins.json"
    if (Test-Path -LiteralPath $savedCorePlugins -PathType Leaf) {
        Copy-Item -LiteralPath $savedCorePlugins -Destination $corePluginsPath -Force
    } elseif (Test-Path -LiteralPath $corePluginsPath -PathType Leaf) {
        Remove-Item -LiteralPath $corePluginsPath -Force
    }
    $savedCommunityPlugins = Join-Path $prechangeRoot "community-plugins.json"
    if (Test-Path -LiteralPath $savedCommunityPlugins -PathType Leaf) {
        Copy-Item -LiteralPath $savedCommunityPlugins -Destination $communityPluginsPath -Force
    } else {
        Remove-Item -LiteralPath $communityPluginsPath -Force -ErrorAction SilentlyContinue
    }
}

try {
    $corePluginPolicy = [ordered]@{
        "file-explorer" = $true
        "global-search" = $true
        "switcher" = $true
        "graph" = $true
        "backlink" = $true
        "canvas" = $false
        "outgoing-link" = $true
        "tag-pane" = $true
        "footnotes" = $false
        "properties" = $true
        "page-preview" = $true
        "daily-notes" = $false
        "templates" = $false
        "note-composer" = $false
        "command-palette" = $true
        "slash-command" = $false
        "editor-status" = $true
        "bookmarks" = $true
        "markdown-importer" = $false
        "zk-prefixer" = $false
        "random-note" = $false
        "outline" = $true
        "word-count" = $true
        "slides" = $false
        "audio-recorder" = $false
        "workspaces" = $false
        "file-recovery" = $false
        "publish" = $false
        "sync" = $false
        "bases" = $false
        "webviewer" = $false
    } | ConvertTo-Json -Depth 3
    [IO.File]::WriteAllText($corePluginsPath, $corePluginPolicy, [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($communityPluginsPath, "[]", [Text.UTF8Encoding]::new($false))
    $pluginsRoot = Join-Path $vaultConfigRoot "plugins"
    if ((Test-Path -LiteralPath $pluginsRoot) -and
            @(Get-ChildItem -LiteralPath $pluginsRoot -Force).Count -ne 0) {
        throw "Community plugin content exists."
    }

    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "open-phase8e-review.ps1") -Destination $launcherPath -Force
    $qualification = [ordered]@{
        schema_version = 1
        accepted_at = [DateTimeOffset]::Now.ToString("o")
        authority = $authority
        viewer_sid = $viewerSid.Value
        application_path = $applicationPath
        application_sha256 = $expectedHash
        application_version = $expectedVersion
        signature_status = "Valid"
        signer_subject = $expectedSigner
        signer_thumbprint = $expectedThumbprint
        firewall_rule_name = $firewallRuleName
        firewall_local_user = $localUserSddl
        vault_path = $script:Phase8EProjectionRoot
        viewer_config_root = $viewerConfigRoot
        product_owner_accepted = $true
        routine_launch_authorized = $true
        real_data_authorized = $false
        community_plugins_allowed = $false
    }
    $qualificationJson = $qualification | ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText($qualificationPath, $qualificationJson, [Text.UTF8Encoding]::new($false))

    foreach ($stateFile in @($launcherStatePath, $evidenceStatePath)) {
        $boundaryState = Get-Content -Raw -LiteralPath $stateFile | ConvertFrom-Json
        $boundaryState.qualified_application = [pscustomobject]@{
            path = $applicationPath
            sha256 = $expectedHash
            authority = $authority
        }
        $boundaryState | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $stateFile -Encoding utf8
    }

    & $launcherPath -VerifyOnly | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "The promoted launcher verification failed." }
    $bytes = [byte[]]::new(48)
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    $random.GetBytes($bytes); $random.Dispose()
    $secret = [Convert]::ToBase64String($bytes)
    $secure = ConvertTo-SecureString $secret -AsPlainText -Force
    Set-LocalUser -Name $script:Phase8EViewerName -Password $secure
    $credential = [Management.Automation.PSCredential]::new("$env:COMPUTERNAME\$script:Phase8EViewerName", $secure)
    $secret = $null
    Remove-Item -LiteralPath $launcherOutputPath, $launcherErrorPath -Force -ErrorAction SilentlyContinue
    $launcherProcess = Start-Process -FilePath "powershell.exe" -Credential $credential `
        -WorkingDirectory "$env:SystemRoot\System32" -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launcherPath
        ) -RedirectStandardOutput $launcherOutputPath -RedirectStandardError $launcherErrorPath `
        -PassThru -WindowStyle Hidden
    $secure.Dispose()
    $deadline = [DateTimeOffset]::Now.AddSeconds(20)
    $launched = @()
    $launcherResult = $null
    do {
        Start-Sleep -Milliseconds 500
        $launcherProcess.Refresh()
        if (Test-Path -LiteralPath $launcherOutputPath -PathType Leaf) {
            try { $launcherResult = Get-Content -Raw -LiteralPath $launcherOutputPath | ConvertFrom-Json } catch {}
        }
        $launched = @(Get-Process -Name Obsidian -ErrorAction SilentlyContinue | Where-Object {
            try { $_.Path -eq $applicationPath } catch { $false }
        })
    } while (($null -eq $launcherResult -or $launched.Count -eq 0) -and
        [DateTimeOffset]::Now -lt $deadline)
    if ($null -eq $launcherResult -or -not $launcherResult.passed -or
            -not $launcherResult.application_qualified -or -not $launcherResult.application_launched) {
        $launcherError = if (Test-Path -LiteralPath $launcherErrorPath -PathType Leaf) {
            [IO.File]::ReadAllText($launcherErrorPath).Trim()
        } else { "No error text was captured." }
        throw "The actual viewer-token routine launcher failed: $launcherError"
    }
    if ($launched.Count -eq 0) { throw "The routine launcher did not leave the dedicated application running." }
    Start-Sleep -Seconds 10
    $launched = @(Get-Process -Name Obsidian -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Path -eq $applicationPath } catch { $false }
    })
    if ($launched.Count -eq 0) { throw "The dedicated application did not remain running for the test interval." }
    $nonLoopbackConnections = 0
    foreach ($process in $launched) {
        $nonLoopbackConnections += @(Get-NetTCPConnection -OwningProcess $process.Id -State Established -ErrorAction SilentlyContinue |
            Where-Object { $_.RemoteAddress -notin @("127.0.0.1", "::1") }).Count
    }
    if ($nonLoopbackConnections -ne 0) { throw "The dedicated application established a non-loopback connection." }
    foreach ($process in $launched) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    if (-not $launcherProcess.WaitForExit(10000)) {
        Stop-Process -Id $launcherProcess.Id -Force -ErrorAction SilentlyContinue
        throw "The viewer launcher process did not exit after its application closed."
    }
    # Start-Process -Credential can report a nonzero wrapper exit code after an
    # Electron child closes even though the launcher emitted its validated success
    # record.  The exact JSON result and observed dedicated process above are the
    # authoritative launch checks.
    & $launcherPath -VerifyOnly | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Post-launch verification failed." }
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:8766/" -TimeoutSec 10 -UseBasicParsing
    if ($health.StatusCode -ne 200) { throw "The resident page was not healthy after launcher promotion." }
    [ordered]@{
        schema_version = 1
        promoted_at = [DateTimeOffset]::Now.ToString("o")
        authority = $authority
        viewer_sid = $viewerSid.Value
        application_path = $applicationPath
        application_sha256 = $expectedHash
        qualification_path = $qualificationPath
        routine_viewer_launch_passed = $true
        core_plugin_policy_applied = $true
        community_plugins_absent = $true
        non_loopback_established_connections = $nonLoopbackConnections
        owner_obsidian_processes_stopped = $false
        real_data_used = $false
        resident_http_status = $health.StatusCode
        passed = $true
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $resultPath -Encoding utf8
    Get-Content -Raw -LiteralPath $resultPath | Write-Output
} catch {
    $failure = $_
    $rollbackFailure = $null
    try { Restore-RoutineLaunch } catch { $rollbackFailure = $_.Exception.Message }
    [ordered]@{
        schema_version = 1
        observed_at = [DateTimeOffset]::Now.ToString("o")
        failure = $failure.Exception.Message
        rollback_failure = $rollbackFailure
    } | ConvertTo-Json -Depth 4 | Set-Content `
        -LiteralPath (Join-Path $script:Phase8EEvidenceRoot "stage3-routine-launch-failure.json") -Encoding utf8
    if ($null -ne $rollbackFailure) { throw "Routine-launch promotion and rollback both failed; inspect evidence immediately." }
    throw $failure
}
