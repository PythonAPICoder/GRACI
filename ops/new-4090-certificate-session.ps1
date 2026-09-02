[CmdletBinding()]
param(
    [ValidateSet('VR-Gamer')]
    [string]$ComputerName = 'VR-Gamer',
    [ValidateRange(1, 365)]
    [int]$MinimumValidityDays = 30
)

$ErrorActionPreference = 'Stop'
$subject = 'CN=GRACI-3090-4090-Deployment'
$upn = 'GRACI_Remote@VR-Gamer'
$now = Get-Date
$candidates = @(Get-ChildItem Cert:\CurrentUser\My | Where-Object {
    $_.Subject -eq $subject -and
    $_.HasPrivateKey -and
    $_.NotBefore -le $now -and
    $_.NotAfter -gt $now.AddDays($MinimumValidityDays) -and
    $_.GetNameInfo(
        [Security.Cryptography.X509Certificates.X509NameType]::UpnName,
        $false) -eq $upn
})

if ($candidates.Count -ne 1) {
    throw "Expected exactly one usable GRACI 4090 client certificate; found $($candidates.Count)."
}

New-PSSession -ComputerName $ComputerName -UseSSL `
    -CertificateThumbprint $candidates[0].Thumbprint
