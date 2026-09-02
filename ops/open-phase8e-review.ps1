[CmdletBinding()]
param([switch]$VerifyOnly)

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
    [pscustomobject]@{ passed = $true; generation_id = $pointer.generation_id; application_launched = $false } |
        ConvertTo-Json -Compress | Write-Output
    exit 0
}
$activeSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
if ($activeSid -ne $viewerSid.Value) { throw "VIEWER_IDENTITY_REQUIRED" }
$qualification = "C:\ProgramData\GRACI\Phase8E\qualified-application.json"
if (-not (Test-Path -LiteralPath $qualification -PathType Leaf)) { throw "APPLICATION_NOT_QUALIFIED" }
throw "APPLICATION_NOT_QUALIFIED"
