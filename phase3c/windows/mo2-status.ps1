$ErrorActionPreference = 'Stop'

$allowedRemoteAddress = '192.168.0.100'
$listenerPrefix = 'http://+:8765/'
$allowedPath = '/graci/v1/mo2'
$exactProcessName = 'ModOrganizer.exe'

$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add($listenerPrefix)
$listener.IgnoreWriteExceptions = $true

function Send-Response {
    param(
        [Parameter(Mandatory)]
        [System.Net.HttpListenerContext] $Context,
        [Parameter(Mandatory)]
        [int] $StatusCode,
        [Parameter(Mandatory)]
        [hashtable] $Payload
    )
    $json = $Payload | ConvertTo-Json -Compress
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    $Context.Response.StatusCode = $StatusCode
    $Context.Response.ContentType = 'application/json; charset=utf-8'
    $Context.Response.ContentLength64 = $bytes.Length
    $Context.Response.KeepAlive = $false
    $Context.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    $Context.Response.Close()
}

try {
    $listener.Start()
    while ($listener.IsListening) {
        $context = $listener.GetContext()
        try {
            $remoteAddress = $context.Request.RemoteEndPoint.Address
            if ($remoteAddress.IsIPv4MappedToIPv6) {
                $remoteAddress = $remoteAddress.MapToIPv4()
            }
            $remoteText = $remoteAddress.ToString()
            $isAllowedCaller =
                $remoteText -eq $allowedRemoteAddress -or
                [System.Net.IPAddress]::IsLoopback($remoteAddress)
            if (-not $isAllowedCaller) {
                Send-Response -Context $context -StatusCode 403 -Payload @{
                    schema_version = 1
                    process_name = $exactProcessName
                    state = 'ERROR'
                    reason_code = 'caller_not_allowed'
                }
                continue
            }
            if (
                $context.Request.HttpMethod -cne 'GET' -or
                $context.Request.Url.AbsolutePath -cne $allowedPath -or
                $context.Request.ContentLength64 -gt 0
            ) {
                Send-Response -Context $context -StatusCode 404 -Payload @{
                    schema_version = 1
                    process_name = $exactProcessName
                    state = 'ERROR'
                    reason_code = 'unsupported_request'
                }
                continue
            }
            try {
                $matches = @(
                    Get-CimInstance -ClassName Win32_Process `
                        -Filter "Name = 'ModOrganizer.exe'" -Property Name `
                        -ErrorAction Stop
                )
                $exactMatch = $false
                foreach ($match in $matches) {
                    if ([System.StringComparer]::OrdinalIgnoreCase.Equals(
                            [string]$match.Name, $exactProcessName)) {
                        $exactMatch = $true
                        break
                    }
                }
                if ($exactMatch) {
                    Send-Response -Context $context -StatusCode 200 -Payload @{
                        schema_version = 1
                        process_name = $exactProcessName
                        state = 'RUNNING'
                        reason_code = 'exact_process_found'
                    }
                }
                else {
                    Send-Response -Context $context -StatusCode 200 -Payload @{
                        schema_version = 1
                        process_name = $exactProcessName
                        state = 'NOT_RUNNING'
                        reason_code = 'exact_process_absent'
                    }
                }
            }
            catch {
                Send-Response -Context $context -StatusCode 503 -Payload @{
                    schema_version = 1
                    process_name = $exactProcessName
                    state = 'ERROR'
                    reason_code = 'process_query_error'
                }
            }
        }
        catch {
            try {
                Send-Response -Context $context -StatusCode 500 -Payload @{
                    schema_version = 1
                    process_name = $exactProcessName
                    state = 'ERROR'
                    reason_code = 'request_handling_error'
                }
            }
            catch {
                try { $context.Response.Abort() } catch {}
            }
        }
    }
}
finally {
    if ($listener.IsListening) {
        $listener.Stop()
    }
    $listener.Close()
}
