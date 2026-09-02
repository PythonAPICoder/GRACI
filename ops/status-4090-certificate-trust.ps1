[CmdletBinding()]
param(
    [switch]$SkipRemoteProbe,
    [ValidateRange(1, 365)]
    [int]$MinimumValidityDays = 30
)

$ErrorActionPreference = 'Stop'
$subject = 'CN=GRACI-3090-4090-Deployment'
$upn = 'GRACI_Remote@VR-Gamer'
$rootSubject = 'CN=GRACI WinRM Root 2026'
$now = Get-Date
$allClients = @(Get-ChildItem Cert:\CurrentUser\My | Where-Object {
    $_.Subject -eq $subject -and $_.HasPrivateKey
})
$usableClients = @($allClients | Where-Object {
    $_.NotBefore -le $now -and
    $_.NotAfter -gt $now.AddDays($MinimumValidityDays) -and
    $_.GetNameInfo(
        [Security.Cryptography.X509Certificates.X509NameType]::UpnName,
        $false) -eq $upn
})
$roots = @(Get-ChildItem Cert:\CurrentUser\Root | Where-Object {
    $_.Subject -eq $rootSubject -and $_.NotAfter -gt $now.AddDays($MinimumValidityDays)
})

$remote = $null
$remoteError = $null
if (-not $SkipRemoteProbe -and $usableClients.Count -eq 1 -and $roots.Count -eq 1) {
    $session = $null
    try {
        $session = & (Join-Path $PSScriptRoot 'new-4090-certificate-session.ps1') `
            -MinimumValidityDays $MinimumValidityDays
        $remote = Invoke-Command -Session $session -ScriptBlock {
            $httpsListener = @(Get-ChildItem WSMan:\localhost\Listener | Where-Object {
                (Get-Item "$($_.PSPath)\Transport").Value -eq 'HTTPS'
            })
            $mapping = @(Get-ChildItem WSMan:\localhost\ClientCertificate | Where-Object {
                (Get-Item "$($_.PSPath)\Subject").Value -eq 'GRACI_Remote@VR-Gamer'
            })
            $firewall = @(Get-NetFirewallRule -DisplayName 'GRACI WinRM HTTPS from 3090' |
                ForEach-Object {
                    $address = Get-NetFirewallAddressFilter -AssociatedNetFirewallRule $_
                    [pscustomobject]@{
                        Enabled = $_.Enabled.ToString()
                        Action = $_.Action.ToString()
                        RemoteAddress = @($address.RemoteAddress)
                    }
                })
            [pscustomobject]@{
                ComputerName = $env:COMPUTERNAME
                Identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
                Elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
                    [Security.Principal.WindowsBuiltInRole]::Administrator)
                CertificateAuth = (Get-Item WSMan:\localhost\Service\Auth\Certificate).Value
                HttpsListenerCount = $httpsListener.Count
                MappingCount = $mapping.Count
                Firewall = $firewall
            }
        }
    }
    catch {
        $remoteError = $_.Exception.Message
    }
    finally {
        if ($null -ne $session) {
            Remove-PSSession $session -ErrorAction SilentlyContinue
        }
    }
}

$ready = (
    $usableClients.Count -eq 1 -and
    $roots.Count -eq 1 -and
    ($SkipRemoteProbe -or (
        $null -ne $remote -and
        $remote.ComputerName -eq 'VR-GAMER' -and
        $remote.Identity -eq 'VR-Gamer\GRACI_Remote' -and
        $remote.Elevated -and
        $remote.CertificateAuth -eq 'true' -and
        $remote.HttpsListenerCount -eq 1 -and
        $remote.MappingCount -eq 1 -and
        @($remote.Firewall).Count -eq 1 -and
        @($remote.Firewall[0].RemoteAddress).Count -eq 1 -and
        $remote.Firewall[0].RemoteAddress[0] -eq '192.168.0.100'
    ))
)

[pscustomobject]@{
    Status = if ($ready) { 'ready' } else { 'unavailable' }
    ObservedAt = $now.ToString('o')
    MinimumValidityDays = $MinimumValidityDays
    ClientCertificateCount = $allClients.Count
    UsableClientCertificateCount = $usableClients.Count
    ClientThumbprint = if ($usableClients.Count -eq 1) { $usableClients[0].Thumbprint } else { $null }
    ClientNotAfter = if ($usableClients.Count -eq 1) { $usableClients[0].NotAfter.ToString('o') } else { $null }
    TrustedRootCount = $roots.Count
    Remote = $remote
    RemoteError = $remoteError
} | ConvertTo-Json -Depth 8

if (-not $ready) {
    exit 1
}
