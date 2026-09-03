[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet(
    "projection-read", "source-denied", "worktree-denied", "staging-denied",
    "create-denied", "edit-denied", "append-denied", "delete-denied", "rename-denied",
    "acl-denied", "ownership-denied"
)][string]$Case)

# HOST-SYSTEM-CHANGE-QUARANTINE: PO-DEC-039
# This worker is reachable only from the rejected Stage 2 host test path. Retain
# its source for evidence, but fail before reading or changing host state.
throw "PHASE8E_APPLOCKER_BOUNDARY_QUARANTINED: the Stage 2 viewer worker is historical evidence only."

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$projection = "E:\GRACI-Review-Projection"
$homeNote = Get-ChildItem -LiteralPath (Join-Path $projection "generations") -Filter Home.md -File -Recurse |
    Select-Object -First 1

function Test-Denied([scriptblock]$Action) {
    try { & $Action; return $false } catch [UnauthorizedAccessException] { return $true }
    catch [Management.Automation.ItemNotFoundException] { return $true }
    catch { return ($_.Exception.Message -match "denied|permission|access") }
}

$passed = switch ($Case) {
    "projection-read" { $null -ne $homeNote -and (Get-Content -Raw -LiteralPath $homeNote.FullName).Length -gt 0 }
    "source-denied" { Test-Denied { Get-ChildItem -LiteralPath "E:\GRACI" -ErrorAction Stop | Out-Null } }
    "worktree-denied" { Test-Denied { Get-ChildItem -LiteralPath "C:\Users\Steve\.codex\worktrees\2c0c\GRACI" -ErrorAction Stop | Out-Null } }
    "staging-denied" { Test-Denied { Get-ChildItem -LiteralPath "E:\GRACI-Review-Staging" -ErrorAction Stop | Out-Null } }
    "create-denied" { Test-Denied { Set-Content -LiteralPath (Join-Path $projection "viewer-create.txt") -Value test -ErrorAction Stop } }
    "edit-denied" { Test-Denied { Set-Content -LiteralPath $homeNote.FullName -Value test -ErrorAction Stop } }
    "append-denied" { Test-Denied { Add-Content -LiteralPath $homeNote.FullName -Value test -ErrorAction Stop } }
    "delete-denied" { Test-Denied { Remove-Item -LiteralPath $homeNote.FullName -Force -ErrorAction Stop } }
    "rename-denied" { Test-Denied { Rename-Item -LiteralPath $homeNote.FullName -NewName "viewer-renamed.md" -ErrorAction Stop } }
    "acl-denied" { Test-Denied { Set-Acl -LiteralPath $homeNote.FullName -AclObject (Get-Acl -LiteralPath $homeNote.FullName) -ErrorAction Stop } }
    "ownership-denied" {
        [void](Start-Process "$env:SystemRoot\System32\takeown.exe" `
            -ArgumentList @("/f", $homeNote.FullName) -Wait -PassThru -WindowStyle Hidden)
        $true
    }
}
if ($passed) { exit 0 } else { exit 1 }
