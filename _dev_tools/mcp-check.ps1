#requires -Version 5
<#
.SYNOPSIS
  MCP health check (Alibaba Cloud ECS self-hosted) -- proxy-illusion-proof.

.DESCRIPTION
  Root cause of a recurring misdiagnosis: local HTTP_PROXY / git http.proxy points
  at 127.0.0.1:7890. When the proxy program is NOT running, a plain direct call
  fails and gets DISGUISED as "server 502 / TLS failure / unreachable".
  This has bitten us three times (local 2026-10-23; recorded in AGENTS.md for
  2026-10-22 and 2026-10-23).

  Counter-measures built into this script:
    1) Introspect and print local proxy config FIRST, so the illusion is traceable;
    2) Every HTTP probe uses `curl --noproxy '*'` to bypass the proxy;
    3) Raw TCP probes to the public IP (18080 required; 22/8443 optional, no login);
    4) Aggregate into an exit code so verify-all.ps1 / CI can chain it.

.PARAMETER Endpoint
  MCP base endpoint (without /mcp). Default matches AGENTS.md sec.7 and
  _dev_tools/mcp-songzuo/README.md.

.PARAMETER TcpPorts
  TCP ports to probe. Default 18080 (service) + 22 (ssh) + 8443 (backup TLS).

.PARAMETER Deep
  Also verify /mcp: initialize + tools/list (requires $env:SONGZUO_MCP_TOKEN).
  The token is read from the environment only -- never written, never echoed.

.NOTES
  Credentials: /healthz is unauthenticated; default mode needs NO credentials.
  Authoritative sources (keep in sync if the endpoint changes):
    - AGENTS.md sec.7
    - _dev_tools/mcp-songzuo/README.md
    - _dev_tools/game-docs/docs/开发服务器与回归测试说明.md sec.8.1
  This script is intentionally ASCII-only: PowerShell 5.1 reads a BOM-less UTF-8
  file as ANSI, which mangles CJK text and can even break string parsing.
#>
param(
    [string]$Endpoint = "http://120.25.223.23:18080",
    [int[]]$TcpPorts = @(18080, 22, 8443),
    [switch]$Deep
)

$ErrorActionPreference = "Stop"
$script:Fail = 0

function Say([string]$m)  { Write-Host $m }
function Ok([string]$m)   { Write-Host "  [OK]   $m" -ForegroundColor Green }
function Bad([string]$m)  { Write-Host "  [FAIL] $m" -ForegroundColor Red; $script:Fail++ }
function Warn([string]$m) { Write-Host "  [WARN] $m" -ForegroundColor Yellow }
function Info([string]$m) { Write-Host "  [....] $m" -ForegroundColor Gray }

function Trunc([string]$s, [int]$n = 200) {
    if ($null -eq $s) { return "" }
    $t = "$s"
    if ($t.Length -le $n) { return $t }
    return $t.Substring(0, $n)
}

# ----------------------------------------------------------- 1) proxy self-check
Say "=== 1) Local proxy introspection (root cause of 502 illusions) ==="
$found = @()
foreach ($v in @("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy")) {
    $val = [Environment]::GetEnvironmentVariable($v)
    if ($val) { $found += "$v = $val" }
}
try {
    $gp = & git config --global --get http.proxy 2>$null
    if ($gp) { $found += "git http.proxy = $gp" }
} catch { }

if ($found.Count -gt 0) {
    Warn "Proxy configuration detected:"
    $found | ForEach-Object { Warn "    $_" }
    Warn "If the proxy program is not running, direct calls fail and look like 502/TLS errors."
    Warn "This script already bypasses it with --noproxy '*'; to clear manually: `$env:HTTP_PROXY=''"
} else {
    Ok "No proxy configuration detected"
}

# ----------------------------------------------------------- 2) TCP ports
Say ""
Say "=== 2) TCP reachability (probe only, no login) ==="
$hostName = ($Endpoint -replace '^https?://', '') -split ':' | Select-Object -First 1
foreach ($p in $TcpPorts) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($hostName, $p, $null, $null)
        $done = $iar.AsyncWaitHandle.WaitOne(4000, $false)
        if ($done -and $client.Connected) {
            Ok "$hostName`:$p reachable"
        } else {
            Bad "$hostName`:$p unreachable (4s timeout)"
        }
    } catch {
        Bad "$hostName`:$p error: $($_.Exception.Message)"
    } finally {
        $client.Close()
    }
}

# ----------------------------------------------------------- 3) /healthz
Say ""
Say "=== 3) /healthz (unauthenticated) ==="
$hz = "$Endpoint/healthz"
try {
    $raw = & curl.exe -sS --noproxy '*' -m 12 $hz 2>&1
    if ($LASTEXITCODE -ne 0) {
        Bad "$hz curl exit code $LASTEXITCODE"
        Info (Trunc "$raw")
    } else {
        try {
            $j = "$raw" | ConvertFrom-Json
            if ($j.ok -eq $true) {
                Ok "$hz -> ok=true, tools=$($j.tools), storage=$($j.storage.driver)"
                if ("$($j.tools)" -ne "8") { Warn "tools=$($j.tools) (AGENTS.md sec.7 records 8)" }
            } else {
                Bad "$hz returned ok!=true"
            }
        } catch {
            Bad "$hz returned non-JSON (likely a proxy interception page)"
            Info (Trunc "$raw")
        }
    }
} catch {
    Bad "$hz probe error: $($_.Exception.Message)"
}

# ----------------------------------------------------------- 4) deep /mcp (optional)
if ($Deep) {
    Say ""
    Say "=== 4) /mcp deep check (needs SONGZUO_MCP_TOKEN) ==="
    if (-not $env:SONGZUO_MCP_TOKEN) {
        Bad "SONGZUO_MCP_TOKEN is not set; skipping /mcp deep check"
    } else {
        $mcp = "$Endpoint/mcp"
        $hdr = @(
            "-H", "Authorization: Bearer $env:SONGZUO_MCP_TOKEN",
            "-H", "Content-Type: application/json",
            "-H", "Accept: application/json, text/event-stream"
        )
        $init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"mcp-check","version":"1.0"}}}'
        try {
            $r1 = & curl.exe -sS --noproxy '*' -m 15 @hdr --data-binary $init $mcp 2>&1
            if ($LASTEXITCODE -ne 0) {
                Bad "initialize curl exit code $LASTEXITCODE"; Info (Trunc "$r1")
            } elseif ("$r1" -match 'serverInfo') {
                Ok "initialize OK"
            } else {
                Bad "initialize: no serverInfo in response"; Info (Trunc "$r1")
            }

            $lst = '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
            $r2 = & curl.exe -sS --noproxy '*' -m 15 @hdr --data-binary $lst $mcp 2>&1
            if ($LASTEXITCODE -eq 0 -and "$r2" -match '"name"') {
                $n = ([regex]::Matches("$r2", '"name"\s*:')).Count
                Ok "tools/list OK (parsed $n tool names)"
            } else {
                Bad "tools/list failed"; Info (Trunc "$r2")
            }
        } catch {
            Bad "/mcp deep check error: $($_.Exception.Message)"
        }
    }
}

# ----------------------------------------------------------- summary
Say ""
if ($script:Fail -eq 0) {
    Ok "MCP health check PASSED"
    exit 0
} else {
    Bad "MCP health check FAILED ($script:Fail item(s))"
    Say ""
    Say "Triage order:"
    Say "  1) Read section 1 first: is the proxy running? If not, stop it or clear the env var and re-run."
    Say "  2) 502 / TLS failure but section 2 TCP OK  -> almost certainly the local proxy illusion."
    Say "  3) TCP also fails -> it IS server/security-group; check ECS and port 18080 ingress."
    exit 1
}
