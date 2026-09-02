[CmdletBinding()]
param()

. "$PSScriptRoot\phase8e-review-boundary-common.ps1"
Assert-Phase8EAdministrator
$state = Get-Phase8EBoundaryState
$viewer = Get-LocalUser -Name $script:Phase8EViewerName -ErrorAction SilentlyContinue
if ($null -eq $viewer -or $viewer.SID.Value -ne $state.viewer_sid) {
    throw "Viewer identity is missing or does not match the recorded boundary SID."
}
$viewerSid = [Security.Principal.SecurityIdentifier]::new($state.viewer_sid)
$prechange = Join-Path $script:Phase8EEvidenceRoot "prechange"
$policyBackup = Join-Path $prechange "applocker-local.xml"
$serviceBackup = Join-Path $prechange "appidsvc.json"
if (-not (Test-Path -LiteralPath $policyBackup -PathType Leaf) -or
        -not (Test-Path -LiteralPath $serviceBackup -PathType Leaf)) {
    throw "Exact prechange backup is incomplete."
}

Set-AppLockerPolicy -XmlPolicy $policyBackup
foreach ($source in $script:Phase8ESourceRoots) {
    if (-not (Test-Path -LiteralPath $source -PathType Container) -or (Test-Phase8EReparse $source)) {
        throw "Source ACL target is missing or unsafe: $source"
    }
    Remove-Phase8ESourceDeny $source $viewerSid
}
foreach ($path in @($script:Phase8EStagingRoot, $script:Phase8EProjectionRoot,
        $script:Phase8ELauncherRoot)) {
    [void](Assert-Phase8EExactPath $path @($script:Phase8EStagingRoot,
        $script:Phase8EProjectionRoot, $script:Phase8ELauncherRoot))
    if (Test-Path -LiteralPath $path) {
        if (Test-Phase8EReparse $path) { throw "Refused to remove a reparse point." }
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}
$profiles = @(Get-CimInstance Win32_UserProfile | Where-Object SID -eq $state.viewer_sid)
foreach ($profile in $profiles) {
    if ($profile.Loaded) { throw "Viewer profile is loaded; rollback fails closed." }
    $profilePath = [IO.Path]::GetFullPath($profile.LocalPath).TrimEnd('\')
    $usersRoot = [IO.Path]::GetFullPath("C:\Users").TrimEnd('\')
    if ((Split-Path -Parent $profilePath) -ne $usersRoot -or
            (Split-Path -Leaf $profilePath) -notlike "GRACI_Review*") {
        throw "Viewer profile path is outside the exact rollback boundary."
    }
    Remove-CimInstance -InputObject $profile
}
Remove-LocalUser -Name $script:Phase8EViewerName
$serviceState = Get-Content -Raw -LiteralPath $serviceBackup | ConvertFrom-Json
if ($serviceState.Status -eq "Stopped" -and (Get-Service AppIDSvc).Status -eq "Running") {
    Stop-Service AppIDSvc
}
Remove-Item -LiteralPath (Join-Path $script:Phase8EEvidenceRoot "boundary-state.json") -Force
[pscustomobject]@{ rolled_back = $true; preserved_evidence = $script:Phase8EEvidenceRoot } |
    ConvertTo-Json -Compress | Write-Output
