Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# HOST-SYSTEM-CHANGE-QUARANTINE: PO-DEC-039
# The source below is retained only as incident evidence. Dot-sourcing this file
# must fail before it reads or changes host state.
throw "PHASE8E_APPLOCKER_BOUNDARY_QUARANTINED: the rejected Stage 2 and dependent Stage 3 host workflow is historical evidence only."

$script:Phase8EViewerName = "GRACI_Review"
$script:Phase8EStagingRoot = "E:\GRACI-Review-Staging"
$script:Phase8EProjectionRoot = "E:\GRACI-Review-Projection"
$script:Phase8ELauncherRoot = "C:\ProgramData\GRACI\Phase8E"
$script:Phase8EEvidenceRoot = "E:\GRACI-Review-Evidence"
$script:Phase8ESourceRoots = @(
    "E:\GRACI",
    "C:\Users\Steve\.codex\worktrees\2c0c\GRACI"
)
$script:Phase8EExporterSid = "S-1-5-21-80404339-2367555055-2558411261-1001"
$script:Phase8ERuleNamespace = "GRACI Phase 8E Stage 2"

function Assert-Phase8EAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Phase 8E boundary mutation requires an elevated administrator token."
    }
}

function Assert-Phase8EExactPath([string]$Path, [string[]]$Allowed) {
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $matches = @($Allowed | Where-Object {
        [IO.Path]::GetFullPath($_).TrimEnd('\') -eq $full
    })
    if ($matches.Count -ne 1) {
        throw "Refused a path outside the exact Phase 8E boundary."
    }
    return $full
}

function Test-Phase8EReparse([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    return [bool]((Get-Item -LiteralPath $Path -Force).Attributes -band
        [IO.FileAttributes]::ReparsePoint)
}

function New-Phase8EAccessRule(
    [Security.Principal.IdentityReference]$Identity,
    [Security.AccessControl.FileSystemRights]$Rights,
    [Security.AccessControl.AccessControlType]$Type
) {
    return [Security.AccessControl.FileSystemAccessRule]::new(
        $Identity,
        $Rights,
        [Security.AccessControl.InheritanceFlags]"ContainerInherit, ObjectInherit",
        [Security.AccessControl.PropagationFlags]::None,
        $Type
    )
}

function Set-Phase8EProtectedAcl(
    [string]$Path,
    [Security.Principal.SecurityIdentifier]$ViewerSid,
    [bool]$ViewerRead,
    [bool]$ExporterFull
) {
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $system = [Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $admins = [Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $exporter = [Security.Principal.SecurityIdentifier]::new($script:Phase8EExporterSid)
    [void]$acl.AddAccessRule((New-Phase8EAccessRule $system FullControl Allow))
    [void]$acl.AddAccessRule((New-Phase8EAccessRule $admins FullControl Allow))
    $exporterRights = if ($ExporterFull) { "FullControl" } else { "Modify, Synchronize" }
    [void]$acl.AddAccessRule((New-Phase8EAccessRule $exporter $exporterRights Allow))
    if ($ViewerRead) {
        [void]$acl.AddAccessRule((New-Phase8EAccessRule $ViewerSid "ReadAndExecute, Synchronize" Allow))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Add-Phase8ESourceDeny([string]$Path, [Security.Principal.SecurityIdentifier]$ViewerSid) {
    $acl = Get-Acl -LiteralPath $Path
    $rule = New-Phase8EAccessRule $ViewerSid FullControl Deny
    [void]$acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Remove-Phase8ESourceDeny([string]$Path, [Security.Principal.SecurityIdentifier]$ViewerSid) {
    $acl = Get-Acl -LiteralPath $Path
    $matches = @($acl.Access | Where-Object {
        $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq $ViewerSid.Value -and
        $_.AccessControlType -eq [Security.AccessControl.AccessControlType]::Deny
    })
    foreach ($rule in $matches) { [void]$acl.RemoveAccessRuleSpecific($rule) }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function New-Phase8EAppLockerXml([string]$ViewerSid) {
    $collections = @(
        @{ Type = "Exe"; Allow = "03c5ba1b-9a71-47a8-9b0f-4fca19b3ad01"; Stage = "03c5ba1b-9a71-47a8-9b0f-4fca19b3ad11"; Projection = "03c5ba1b-9a71-47a8-9b0f-4fca19b3ad21" },
        @{ Type = "Msi"; Allow = "1c835fde-3814-42d4-a3fe-f6636cf59f02"; Stage = "1c835fde-3814-42d4-a3fe-f6636cf59f12"; Projection = "1c835fde-3814-42d4-a3fe-f6636cf59f22" },
        @{ Type = "Script"; Allow = "99a8fe2c-24e4-4fa6-9338-02f80c0e1a03"; Stage = "99a8fe2c-24e4-4fa6-9338-02f80c0e1a13"; Projection = "99a8fe2c-24e4-4fa6-9338-02f80c0e1a23" },
        @{ Type = "Dll"; Allow = "cba25771-5d89-4c02-ad73-71c71c66bb04"; Stage = "cba25771-5d89-4c02-ad73-71c71c66bb14"; Projection = "cba25771-5d89-4c02-ad73-71c71c66bb24" }
    )
    $rules = foreach ($collection in $collections) {
        "<RuleCollection Type=`"$($collection.Type)`" EnforcementMode=`"Enabled`">" +
        "<FilePathRule Id=`"$($collection.Allow)`" Name=`"$script:Phase8ERuleNamespace compatibility allow`" Description=`"Preserves prior empty AppLocker behavior; viewer-specific denies take precedence.`" UserOrGroupSid=`"S-1-1-0`" Action=`"Allow`"><Conditions><FilePathCondition Path=`"*`" /></Conditions></FilePathRule>" +
        "<FilePathRule Id=`"$($collection.Stage)`" Name=`"$script:Phase8ERuleNamespace staging deny`" Description=`"Dedicated viewer cannot execute from staging.`" UserOrGroupSid=`"$ViewerSid`" Action=`"Deny`"><Conditions><FilePathCondition Path=`"$script:Phase8EStagingRoot\*`" /></Conditions></FilePathRule>" +
        "<FilePathRule Id=`"$($collection.Projection)`" Name=`"$script:Phase8ERuleNamespace projection deny`" Description=`"Dedicated viewer cannot execute from projection.`" UserOrGroupSid=`"$ViewerSid`" Action=`"Deny`"><Conditions><FilePathCondition Path=`"$script:Phase8EProjectionRoot\*`" /></Conditions></FilePathRule>" +
        "</RuleCollection>"
    }
    return "<AppLockerPolicy Version=`"1`">$($rules -join '')</AppLockerPolicy>"
}

function Get-Phase8EBoundaryState {
    $path = Join-Path $script:Phase8EEvidenceRoot "boundary-state.json"
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 8E boundary state is missing."
    }
    return Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
}
