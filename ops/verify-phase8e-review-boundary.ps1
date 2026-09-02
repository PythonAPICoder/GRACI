[CmdletBinding()]
param([switch]$RequireProjection)

. "$PSScriptRoot\phase8e-review-boundary-common.ps1"
$state = Get-Phase8EBoundaryState
$failures = [Collections.Generic.List[string]]::new()
$viewer = Get-LocalUser -Name $script:Phase8EViewerName -ErrorAction SilentlyContinue
if ($null -eq $viewer -or $viewer.SID.Value -ne $state.viewer_sid) { $failures.Add("viewer identity mismatch") }
if ($null -ne $viewer -and (Get-LocalGroupMember -Group Administrators | Where-Object SID -eq $viewer.SID)) {
    $failures.Add("viewer is an administrator")
}
foreach ($path in @($script:Phase8EStagingRoot, $script:Phase8EProjectionRoot,
        $script:Phase8ELauncherRoot, $script:Phase8EEvidenceRoot)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) { $failures.Add("missing root: $path"); continue }
    if (Test-Phase8EReparse $path) { $failures.Add("reparse root: $path") }
}
if ((Split-Path -Qualifier $script:Phase8EStagingRoot) -ne
        (Split-Path -Qualifier $script:Phase8EProjectionRoot)) { $failures.Add("roots are not same-volume siblings") }

if ($null -ne $viewer) {
    $sid = $viewer.SID.Value
    foreach ($source in $script:Phase8ESourceRoots) {
        $deny = @(Get-Acl -LiteralPath $source | Select-Object -ExpandProperty Access | Where-Object {
            $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq $sid -and
            $_.AccessControlType -eq "Deny" -and ($_.FileSystemRights -band "FullControl")
        })
        if ($deny.Count -eq 0) { $failures.Add("source deny missing: $source") }
    }
    $projectionRules = @(Get-Acl -LiteralPath $script:Phase8EProjectionRoot |
        Select-Object -ExpandProperty Access | Where-Object {
            $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq $sid -and
            $_.AccessControlType -eq "Allow"
        })
    $writeMask = [Security.AccessControl.FileSystemRights]::WriteData -bor
        [Security.AccessControl.FileSystemRights]::AppendData -bor
        [Security.AccessControl.FileSystemRights]::WriteAttributes -bor
        [Security.AccessControl.FileSystemRights]::WriteExtendedAttributes -bor
        [Security.AccessControl.FileSystemRights]::Delete -bor
        [Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor
        [Security.AccessControl.FileSystemRights]::ChangePermissions -bor
        [Security.AccessControl.FileSystemRights]::TakeOwnership
    if ($projectionRules.Count -ne 1 -or
            ($projectionRules[0].FileSystemRights -band $writeMask)) {
        $failures.Add("projection viewer ACL is not exact read-only")
    }
    $stagingRules = @(Get-Acl -LiteralPath $script:Phase8EStagingRoot |
        Select-Object -ExpandProperty Access | Where-Object {
            $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq $sid
        })
    if ($stagingRules.Count -ne 0) { $failures.Add("viewer has a staging ACE") }
}
$appLocker = (Get-AppLockerPolicy -Effective).ToXml()
foreach ($collection in @("Exe", "Msi", "Script", "Dll")) {
    if ($appLocker -notmatch "RuleCollection Type=`"$collection`" EnforcementMode=`"Enabled`"") {
        $failures.Add("AppLocker $collection collection not enforced")
    }
}
if ($null -ne $viewer) {
    $escapedSid = [regex]::Escape($viewer.SID.Value)
    if (([regex]::Matches($appLocker, "UserOrGroupSid=`"$escapedSid`" Action=`"Deny`"")).Count -ne 8) {
        $failures.Add("AppLocker viewer deny rule count is not eight")
    }
}
if ((Get-Service AppIDSvc).Status -ne "Running") { $failures.Add("Application Identity service is not running") }
if ($RequireProjection) {
    $pointer = Get-Content -Raw -LiteralPath (Join-Path $script:Phase8EProjectionRoot "current.json") | ConvertFrom-Json
    $generationAcl = Get-Acl -LiteralPath (Join-Path (Join-Path $script:Phase8EProjectionRoot "generations") $pointer.generation_id)
    $generationViewer = @($generationAcl.Access | Where-Object {
        $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq $state.viewer_sid -and
        $_.AccessControlType -eq "Allow" -and
        ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::ReadAndExecute)
    })
    if ($generationViewer.Count -eq 0) { $failures.Add("current generation lacks viewer read inheritance") }
    & (Join-Path $script:Phase8ELauncherRoot "Open-GRACIReview.ps1") -VerifyOnly
    if ($LASTEXITCODE -ne 0) { $failures.Add("launcher projection verification failed") }
}
$result = [ordered]@{
    schema_version = 1
    observed_at = [DateTimeOffset]::Now.ToString("o")
    viewer_sid = if ($null -eq $viewer) { $null } else { $viewer.SID.Value }
    wdac_mutation_attempted = $false
    appidsvc_running = (Get-Service AppIDSvc).Status -eq "Running"
    projection_required = [bool]$RequireProjection
    failures = @($failures)
    passed = $failures.Count -eq 0
}
$result | ConvertTo-Json -Depth 4 | Write-Output
if ($failures.Count -ne 0) { exit 1 }
