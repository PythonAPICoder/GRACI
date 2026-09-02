[CmdletBinding()]
param()

. "$PSScriptRoot\phase8e-review-boundary-common.ps1"
Assert-Phase8EAdministrator

$allManagedRoots = @($script:Phase8EStagingRoot, $script:Phase8EProjectionRoot,
    $script:Phase8ELauncherRoot, $script:Phase8EEvidenceRoot)
foreach ($path in $allManagedRoots) {
    [void](Assert-Phase8EExactPath $path $allManagedRoots)
    if (Test-Phase8EReparse $path) { throw "A managed root is a reparse point." }
}
foreach ($source in $script:Phase8ESourceRoots) {
    if (-not (Test-Path -LiteralPath $source -PathType Container)) {
        throw "An exact source root is missing: $source"
    }
    if (Test-Phase8EReparse $source) { throw "An exact source root is a reparse point: $source" }
}
if ((Get-Volume -DriveLetter E).FileSystem -ne "NTFS") {
    throw "Stage 2 requires NTFS on E:."
}
$ciResult = & "$env:SystemRoot\System32\CiTool.exe" --list-policies --json | ConvertFrom-Json
$wdac = @($ciResult.Policies | Where-Object {
    $_.PolicyID -eq "0283ac0f-fff1-49ae-ada1-8a933130cad6" -and
    $_.FriendlyName -eq "VerifiedAndReputableDesktop" -and $_.IsEnforced -and $_.IsAuthorized
})
if ($ciResult.OperationResult -ne 0 -or $wdac.Count -ne 1) {
    throw "The enforced VerifiedAndReputableDesktop policy was not confirmed."
}
if ((Get-AppLockerPolicy -Effective).ToXml() -notin @("<AppLockerPolicy Version=`"1`" />",
        "<AppLockerPolicy Version=`"1`"/>")) {
    $existingState = Test-Path -LiteralPath (Join-Path $script:Phase8EEvidenceRoot "boundary-state.json")
    if (-not $existingState) { throw "An unexpected AppLocker policy exists; refusing replacement." }
}

if (-not (Test-Path -LiteralPath $script:Phase8EEvidenceRoot)) {
    New-Item -ItemType Directory -Path $script:Phase8EEvidenceRoot | Out-Null
}
$prechange = Join-Path $script:Phase8EEvidenceRoot "prechange"
if (-not (Test-Path -LiteralPath $prechange)) {
    New-Item -ItemType Directory -Path $prechange | Out-Null
    (Get-AppLockerPolicy -Local).ToXml() | Set-Content -LiteralPath (Join-Path $prechange "applocker-local.xml") -Encoding utf8
    $service = Get-Service AppIDSvc
    [pscustomobject]@{ Status = $service.Status.ToString(); StartType = $service.StartType.ToString() } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $prechange "appidsvc.json") -Encoding utf8
    $sourceAcls = foreach ($source in $script:Phase8ESourceRoots) {
        [pscustomobject]@{ Path = $source; Sddl = (Get-Acl -LiteralPath $source).Sddl }
    }
    $sourceAcls | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $prechange "source-acls.json") -Encoding utf8
}

$viewer = Get-LocalUser -Name $script:Phase8EViewerName -ErrorAction SilentlyContinue
if ($null -eq $viewer) {
    $bytes = [byte[]]::new(48)
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    $random.GetBytes($bytes)
    $random.Dispose()
    $secret = [Convert]::ToBase64String($bytes)
    $secure = ConvertTo-SecureString $secret -AsPlainText -Force
    $newUser = @{
        Name = $script:Phase8EViewerName
        Password = $secure
        AccountNeverExpires = $true
        PasswordNeverExpires = $true
        UserMayNotChangePassword = $true
        Description = "GRACI Phase 8E restricted review identity"
    }
    $viewer = New-LocalUser @newUser
    $secret = $null
    $secure.Dispose()
}
$viewerSid = [Security.Principal.SecurityIdentifier]::new($viewer.SID.Value)
if (Get-LocalGroupMember -Group Administrators | Where-Object SID -eq $viewer.SID) {
    throw "The Phase 8E viewer unexpectedly belongs to Administrators."
}

foreach ($path in @($script:Phase8EStagingRoot, $script:Phase8EProjectionRoot,
        $script:Phase8ELauncherRoot)) {
    if (-not (Test-Path -LiteralPath $path)) { New-Item -ItemType Directory -Path $path | Out-Null }
}
Set-Phase8EProtectedAcl $script:Phase8EStagingRoot $viewerSid $false $false
Set-Phase8EProtectedAcl $script:Phase8EProjectionRoot $viewerSid $true $false
Set-Phase8EProtectedAcl $script:Phase8ELauncherRoot $viewerSid $true $true
Set-Phase8EProtectedAcl $script:Phase8EEvidenceRoot $viewerSid $true $true
foreach ($source in $script:Phase8ESourceRoots) { Add-Phase8ESourceDeny $source $viewerSid }

$launcherSource = Join-Path $PSScriptRoot "open-phase8e-review.ps1"
Copy-Item -LiteralPath $launcherSource -Destination (Join-Path $script:Phase8ELauncherRoot "Open-GRACIReview.ps1") -Force
$workerSource = Join-Path $PSScriptRoot "test-phase8e-viewer-worker.ps1"
Copy-Item -LiteralPath $workerSource -Destination (Join-Path $script:Phase8ELauncherRoot "Test-ViewerBoundary.ps1") -Force
$policyPath = Join-Path $script:Phase8EEvidenceRoot "phase8e-applocker.xml"
New-Phase8EAppLockerXml $viewerSid.Value | Set-Content -LiteralPath $policyPath -Encoding utf8
Set-AppLockerPolicy -XmlPolicy $policyPath
if ((Get-Service AppIDSvc).Status -ne "Running") { Start-Service AppIDSvc }

$state = [ordered]@{
    schema_version = 1
    applied_at = [DateTimeOffset]::Now.ToString("o")
    computer = $env:COMPUTERNAME
    viewer_name = "$env:COMPUTERNAME\$script:Phase8EViewerName"
    viewer_sid = $viewerSid.Value
    exporter_sid = $script:Phase8EExporterSid
    staging_root = $script:Phase8EStagingRoot
    projection_root = $script:Phase8EProjectionRoot
    launcher_root = $script:Phase8ELauncherRoot
    evidence_root = $script:Phase8EEvidenceRoot
    source_roots = $script:Phase8ESourceRoots
    application_control = "AppLocker user-scoped path deny layered with unchanged WDAC"
    wdac_policy_id = "0283ac0f-fff1-49ae-ada1-8a933130cad6"
    qualified_application = $null
}
$state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $script:Phase8EEvidenceRoot "boundary-state.json") -Encoding utf8
$state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $script:Phase8ELauncherRoot "boundary-state.json") -Encoding utf8
Write-Output ($state | ConvertTo-Json -Depth 4 -Compress)
