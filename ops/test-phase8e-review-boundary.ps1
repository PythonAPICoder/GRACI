[CmdletBinding()]
param([Parameter(Mandatory)][string]$GenerationId)

. "$PSScriptRoot\phase8e-review-boundary-common.ps1"
Assert-Phase8EAdministrator
$state = Get-Phase8EBoundaryState
$viewer = Get-LocalUser -Name $script:Phase8EViewerName
if ($viewer.SID.Value -ne $state.viewer_sid) { throw "Viewer SID mismatch." }

$bytes = [byte[]]::new(48)
$random = [Security.Cryptography.RandomNumberGenerator]::Create()
$random.GetBytes($bytes); $random.Dispose()
$secret = [Convert]::ToBase64String($bytes)
$secure = ConvertTo-SecureString $secret -AsPlainText -Force
Set-LocalUser -Name $script:Phase8EViewerName -Password $secure
$credential = [Management.Automation.PSCredential]::new("$env:COMPUTERNAME\$script:Phase8EViewerName", $secure)
$secret = $null

$worker = Join-Path $script:Phase8ELauncherRoot "Test-ViewerBoundary.ps1"
$cases = @("projection-read", "source-denied", "worktree-denied", "staging-denied",
    "create-denied", "edit-denied", "append-denied", "delete-denied", "rename-denied", "acl-denied",
    "ownership-denied")
$results = [ordered]@{}
foreach ($case in $cases) {
    $ownerBefore = if ($case -eq "ownership-denied") {
        (Get-Acl -LiteralPath (Get-ChildItem -LiteralPath (Join-Path $script:Phase8EProjectionRoot "generations") -Filter Home.md -File -Recurse | Select-Object -First 1).FullName).Owner
    } else { $null }
    $start = @{
        FilePath = "powershell.exe"
        Credential = $credential
        WorkingDirectory = "$env:SystemRoot\System32"
        ArgumentList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $worker, "-Case", $case)
        Wait = $true
        PassThru = $true
    }
    $process = Start-Process @start
    if ($case -eq "ownership-denied") {
        $ownerAfter = (Get-Acl -LiteralPath (Get-ChildItem -LiteralPath (Join-Path $script:Phase8EProjectionRoot "generations") -Filter Home.md -File -Recurse | Select-Object -First 1).FullName).Owner
        $results[$case] = $process.ExitCode -eq 0 -and $ownerBefore -eq $ownerAfter -and $ownerAfter -notmatch "GRACI_Review"
        $results["ownership-debug"] = "exit=$($process.ExitCode);before=$ownerBefore;after=$ownerAfter"
    } else {
        $results[$case] = $process.ExitCode -eq 0
    }
}

$current = Get-Content -Raw -LiteralPath (Join-Path $script:Phase8EProjectionRoot "current.json") | ConvertFrom-Json
$generation = Join-Path (Join-Path $script:Phase8EProjectionRoot "generations") $current.generation_id
$exeProbe = Join-Path $script:Phase8EProjectionRoot "synthetic-probe.exe"
$scriptProbe = Join-Path $script:Phase8EProjectionRoot "synthetic-probe.ps1"
Copy-Item -LiteralPath "$env:SystemRoot\System32\whoami.exe" -Destination $exeProbe
Set-Content -LiteralPath $scriptProbe -Value "exit 0" -Encoding ascii
try {
    try {
        $probe = Start-Process $exeProbe -Credential $credential -WorkingDirectory "$env:SystemRoot\System32" -Wait -PassThru
        $results["executable-denied"] = $probe.ExitCode -ne 0
    } catch { $results["executable-denied"] = $_.Exception.Message -match "policy|blocked|access|denied" }
    $probe = Start-Process powershell.exe -Credential $credential -WorkingDirectory "$env:SystemRoot\System32" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $scriptProbe) -Wait -PassThru
    $results["script-denied"] = $probe.ExitCode -ne 0
} finally {
    Remove-Item -LiteralPath $exeProbe, $scriptProbe -Force -ErrorAction SilentlyContinue
}

$homeNote = Join-Path $generation "Home.md"
$original = [IO.File]::ReadAllBytes($homeNote)
[IO.File]::WriteAllBytes($homeNote, $original + [Text.Encoding]::UTF8.GetBytes("tamper"))
try {
    & (Join-Path $script:Phase8ELauncherRoot "Open-GRACIReview.ps1") -VerifyOnly *> $null
    $results["tamper-detected"] = $LASTEXITCODE -ne 0
} catch { $results["tamper-detected"] = $_.Exception.Message -match "TAMPERED" }
[IO.File]::WriteAllBytes($homeNote, $original)

$pointer = Join-Path $script:Phase8EProjectionRoot "current.json"
$withheld = Join-Path $script:Phase8EProjectionRoot "current.json.withheld"
Move-Item -LiteralPath $pointer -Destination $withheld
try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:8766/" -TimeoutSec 5 -UseBasicParsing
    $results["projection-optional"] = $health.StatusCode -eq 200 -and $health.Content -match "GRACI"
} catch { $results["projection-optional"] = $false }
Move-Item -LiteralPath $withheld -Destination $pointer

try {
    $launcher = Start-Process powershell.exe -Credential $credential -WorkingDirectory "$env:SystemRoot\System32" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            (Join-Path $script:Phase8ELauncherRoot "Open-GRACIReview.ps1")) -Wait -PassThru
    $results["unqualified-launch-denied"] = $launcher.ExitCode -ne 0
} catch { $results["unqualified-launch-denied"] = $true }

$secure.Dispose()
$passed = @($results.GetEnumerator() | Where-Object {
    $_.Key -ne "ownership-debug" -and -not $_.Value
}).Count -eq 0
[pscustomobject]@{
    schema_version = 1
    observed_at = [DateTimeOffset]::Now.ToString("o")
    generation_id = $GenerationId
    viewer_sid = $viewer.SID.Value
    cases = $results
    passed = $passed
} | ConvertTo-Json -Depth 5 | Write-Output
if (-not $passed) { exit 1 }
