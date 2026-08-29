$script:ResidentOwner = 'GRACI_RESIDENT_HOST'
$script:ResidentModule = 'graci.resident_host'
$script:RepositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$script:ResidentRuntime = Join-Path $script:RepositoryRoot '.runtime\resident-host'
$script:ResidentState = Join-Path $script:ResidentRuntime 'state.json'
$script:ResidentStop = Join-Path $script:ResidentRuntime 'stop-request.json'
$script:ResidentTaskName = 'GRACI Resident Host'

function Resolve-GraciPythonPath {
    param([AllowNull()][object]$Python)
    if ($null -ne $Python) {
        if ($Python -isnot [string] -or [string]::IsNullOrWhiteSpace($Python)) {
            throw 'Python must be one concrete absolute executable path.'
        }
        if (-not [IO.Path]::IsPathRooted($Python)) {
            throw 'Python must be supplied as an absolute executable path.'
        }
        $candidate = [IO.Path]::GetFullPath($Python)
        if ([IO.Path]::GetExtension($candidate) -ne '.exe' -or
            -not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            throw "Python executable does not exist or is not an .exe: $candidate"
        }
        return $candidate
    }

    $candidates = @()
    $roots = @(
        'HKCU:\Software\Python\PythonCore',
        'HKLM:\Software\Python\PythonCore',
        'HKLM:\Software\WOW6432Node\Python\PythonCore'
    )
    foreach ($root in $roots) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        foreach ($versionKey in Get-ChildItem -LiteralPath $root -ErrorAction Stop) {
            $version = $null
            if (-not [version]::TryParse($versionKey.PSChildName, [ref]$version) -or
                $version -lt [version]'3.14') { continue }
            $install = Get-ItemProperty -LiteralPath (Join-Path $versionKey.PSPath 'InstallPath') `
                -ErrorAction SilentlyContinue
            $path = $install.ExecutablePath
            if ([string]::IsNullOrWhiteSpace($path) -and $null -ne $install.'(default)') {
                $path = Join-Path $install.'(default)' 'python.exe'
            }
            if (-not [string]::IsNullOrWhiteSpace($path)) {
                $full = [IO.Path]::GetFullPath([string]$path)
                if ([IO.Path]::GetExtension($full) -eq '.exe' -and
                    (Test-Path -LiteralPath $full -PathType Leaf)) { $candidates += $full }
            }
        }
    }
    $candidates = @($candidates | Sort-Object -Unique)
    if ($candidates.Count -ne 1) {
        throw "Expected exactly one registered Python 3.14+ executable; found $($candidates.Count). Supply -Python with one absolute path."
    }
    return [string]$candidates[0]
}

function Read-GraciResidentState {
    if (-not (Test-Path -LiteralPath $script:ResidentState -PathType Leaf)) { return $null }
    try { $record = Get-Content -Raw -LiteralPath $script:ResidentState | ConvertFrom-Json }
    catch { throw 'GRACI resident state is malformed; refusing process action.' }
    if ($record.schema_version -ne 1 -or $record.owner -ne $script:ResidentOwner -or
        $record.module -ne $script:ResidentModule -or $record.pid -notmatch '^\d+$' -or
        [string]::IsNullOrWhiteSpace($record.instance_id) -or
        $record.visualizer.host -ne '127.0.0.1') {
        throw 'GRACI resident state failed identity validation; refusing process action.'
    }
    return $record
}

function Get-ValidatedGraciResidentProcess {
    param([Parameter(Mandatory)]$Record)
    $process = Get-Process -Id ([int]$Record.pid) -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $null }
    $expectedExecutable = [IO.Path]::GetFullPath([string]$Record.executable)
    if ([IO.Path]::GetFullPath([string]$process.Path) -ne $expectedExecutable) {
        throw 'Recorded resident PID belongs to another executable; refusing process action.'
    }
    return $process
}
