[CmdletBinding()]
param()

. "$PSScriptRoot\phase8e-review-boundary-common.ps1"
Assert-Phase8EAdministrator

$prechangePath = Join-Path $script:Phase8EEvidenceRoot "stage3-dedicated-obsidian-prechange.json"
$statePath = Join-Path $script:Phase8ELauncherRoot "stage3-dedicated-obsidian-state.json"
$evidenceStatePath = Join-Path $script:Phase8EEvidenceRoot "stage3-dedicated-obsidian-state.json"
$evidenceResultPath = Join-Path $script:Phase8EEvidenceRoot "stage3-dedicated-obsidian-test-result.json"
$expectedHash = "c01bbd79583037639f5422396cddb457ef48e89e159ca50a8492bbd1f1f10775"
$ruleName = "GRACI-Phase8E-Stage3-Obsidian-Dedicated-Viewer-Block"
if (-not (Test-Path -LiteralPath $prechangePath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $statePath -PathType Leaf)) { throw "Dedicated Obsidian state is missing." }
$prechange = Get-Content -Raw -LiteralPath $prechangePath | ConvertFrom-Json
$installedState = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
$boundary = Get-Phase8EBoundaryState
if ($prechange.viewer_sid -ne $boundary.viewer_sid -or $installedState.viewer_sid -ne $boundary.viewer_sid -or
        $prechange.destination_path -ne $installedState.destination_path -or
        $prechange.firewall_rule_name -ne $ruleName) { throw "Dedicated Obsidian state does not match the exact boundary." }
$destinationPath = [IO.Path]::GetFullPath([string]$prechange.destination_path)
$profileRoot = [IO.Path]::GetFullPath([string]$prechange.viewer_profile_root).TrimEnd('\')
$viewerConfigRoot = [IO.Path]::GetFullPath([string]$prechange.viewer_config_root).TrimEnd('\')
$viewerResultRoot = [IO.Path]::GetFullPath([string]$prechange.viewer_result_root).TrimEnd('\')
$viewerResultPath = Join-Path $viewerResultRoot "stage3-dedicated-obsidian-result.json"
$vaultConfigRoot = [IO.Path]::GetFullPath([string]$prechange.vault_config_root).TrimEnd('\')
$vaultConfigPath = Join-Path $vaultConfigRoot "app.json"
$workerTarget = Join-Path $script:Phase8ELauncherRoot "Test-DedicatedObsidian.ps1"
foreach ($path in @($destinationPath, $profileRoot, $viewerConfigRoot, $viewerResultRoot, $vaultConfigRoot)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "A dedicated Obsidian path is missing." }
    if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "A dedicated Obsidian path is a reparse point."
    }
}
if (@(Get-Process -Name Obsidian -ErrorAction SilentlyContinue).Count -ne 0) { throw "Obsidian is already running." }
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $destinationPath).Hash.ToLowerInvariant() -ne $expectedHash -or
        (Get-AuthenticodeSignature -LiteralPath $destinationPath).Status -ne "Valid") {
    throw "The dedicated Obsidian executable no longer matches."
}
$firewall = Get-NetFirewallRule -Name $ruleName -ErrorAction Stop
$application = $firewall | Get-NetFirewallApplicationFilter
$security = $firewall | Get-NetFirewallSecurityFilter
$localUserSddl = "D:(A;;CC;;;$($boundary.viewer_sid))"
if ($firewall.Direction -ne "Outbound" -or $firewall.Action -ne "Block" -or
        $firewall.Enabled -ne "True" -or $application.Program -ne $destinationPath -or
        $security.LocalUser -ne $localUserSddl) { throw "The exact viewer-only firewall rule is not active." }

try {
    $encoding = [Text.UTF8Encoding]::new($false)
    $obsidianConfig = @{ vaults = @{ "graci-review" = @{ path = $script:Phase8EProjectionRoot; ts = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds(); open = $true } } } |
        ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText((Join-Path $viewerConfigRoot "obsidian.json"), $obsidianConfig, $encoding)
    $vaultConfig = @{ showUnsupportedFiles = $false; alwaysUpdateLinks = $false } | ConvertTo-Json
    [IO.File]::WriteAllText($vaultConfigPath, $vaultConfig, $encoding)
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
            "-ExpectedHash", $expectedHash, "-ExpectedViewerSid", $boundary.viewer_sid,
            "-ResultPath", $viewerResultPath) -Wait -PassThru -WindowStyle Hidden
    $secure.Dispose()
    if (Test-Path -LiteralPath $viewerResultPath -PathType Leaf) {
        Copy-Item -LiteralPath $viewerResultPath -Destination $evidenceResultPath -Force
    }
    if ($testProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $viewerResultPath -PathType Leaf)) {
        throw "The corrected dedicated Obsidian test failed."
    }
    $testResult = Get-Content -Raw -LiteralPath $viewerResultPath | ConvertFrom-Json
    if (-not $testResult.passed -or $testResult.configuration_parse_error) {
        throw "The corrected dedicated Obsidian test did not pass cleanly."
    }
    $installedState | Add-Member -NotePropertyName retested_at -NotePropertyValue ([DateTimeOffset]::Now.ToString("o")) -Force
    $installedState | Add-Member -NotePropertyName configuration_encoding -NotePropertyValue "UTF-8 without BOM" -Force
    $installedState | Add-Member -NotePropertyName clean_configuration_parse -NotePropertyValue $true -Force
    $installedState | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statePath -Encoding utf8
    $installedState | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $evidenceStatePath -Encoding utf8
    $installedState | ConvertTo-Json -Depth 5 -Compress | Write-Output
} catch {
    $failure = $_
    $rollbackFailure = $null
    try { & (Join-Path $PSScriptRoot "remove-phase8e-dedicated-obsidian.ps1") } catch { $rollbackFailure = $_.Exception.Message }
    [ordered]@{
        schema_version = 1
        observed_at = [DateTimeOffset]::Now.ToString("o")
        failure = $failure.Exception.Message
        rollback_failure = $rollbackFailure
    } | ConvertTo-Json -Depth 4 | Set-Content `
        -LiteralPath (Join-Path $script:Phase8EEvidenceRoot "stage3-dedicated-obsidian-retest-failure.json") -Encoding utf8
    if ($null -ne $rollbackFailure) { throw "Dedicated Obsidian retest and rollback both failed; inspect evidence immediately." }
    throw $failure
}
