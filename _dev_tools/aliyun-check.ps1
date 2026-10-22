#requires -Version 5.1
<#
aliyun-check.ps1 —— 阿里云侧资产 + 本地工具链自检（默认只读；-Fix 只重建知识库）

用法：
    powershell -NoProfile -ExecutionPolicy Bypass -File _dev_tools\aliyun-check.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File _dev_tools\aliyun-check.ps1 -Fix
    powershell -NoProfile -ExecutionPolicy Bypass -File _dev_tools\aliyun-check.ps1 -Shot

检查什么（口径：**只查可实测的东西**；未开通的服务一律不写配置、不伪造 PASS）：
  1. 本机工具链（node / npm / npx / Python / cargo / dev-env.ps1）
  2. 阿里云 ECS · MCP 健康端点 `http://120.25.223.23:18080/healthz`
     —— 期望 200 且 body 含 `"ok":true` 与 `"tools":8`（2026-10-22 实测口径）
  3. 阿里云 ECS · 直连 IP 端口可达（18080 必检；22 / 8443 可选）
  4. 可选 · 域名 TLS 入口 `https://mcp.songzuo.online:8443/healthz`（**诊断用，不作门禁**：
     该域名入口历史上曾被备案/SNI 拦截，客户端仍以直连 IP 为准）
  5. 可选 · 官网 `https://songzuo.online/` 探活（期望 200）
  6. MCP 服务器配置（`~\.codebuddy\mcp.json` 合法性与入口存在）
  7. 知识库与 `docs/` 一致性（-Fix 自动重建）
  8. 面板目视截图回路（面板有改动或 -Shot 时才跑）

**不检查**（未开通 / 本机无凭据 —— 不登记配置、不假装可用）：
  OSS、RDS/PolarDB、函数计算 FC、CDN、SLB、云监控。
  这些服务的状态登记在《开发服务器与回归测试说明》§8.3「已核实 / 待开通」表。

⚠️ 本文件必须保存为 **UTF-8 with BOM**：PowerShell 5.1 按 GBK 读 .ps1，
   中文注释无 BOM 会解析报错（同 `dev-env.ps1` 的坑）。补 BOM 一行：
   `$p='_dev_tools\aliyun-check.ps1'; [IO.File]::WriteAllText($p,[IO.File]::ReadAllText($p),[Text.UTF8Encoding]::new($true))`
#>
param([switch]$Fix, [switch]$Shot)

$ErrorActionPreference = 'Continue'
$RepoRoot      = Split-Path -Parent $PSScriptRoot          # _dev_tools 的上级 = 仓库根
$WorkspaceRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

# ---- 阿里云侧端点（已核实：2026-10-22 本机直连实测；可用环境变量覆盖）----
$EcsIp        = if ($env:SONGZUO_ECS_IP) { $env:SONGZUO_ECS_IP } else { '120.25.223.23' }
$McpPort      = 18080
$McpHealthUrl = "http://${EcsIp}:${McpPort}/healthz"
$TlsHealthUrl = 'https://mcp.songzuo.online:8443/healthz'
$SiteUrl      = 'https://songzuo.online/'
$ExpectTools  = 8

$NodeDir      = Join-Path $WorkspaceRoot 'tools\nodejs\node-v24.22.1-win-x64'
$PyDir        = Join-Path $WorkspaceRoot '.audit-venv\Scripts'
$CargoDir     = Join-Path $env:USERPROFILE '.cargo\bin'

$script:pass = 0; $script:fail = 0; $script:skip = 0
function Ok  ($m)        { Write-Host "  [ OK ] $m" -ForegroundColor Green;  $script:pass++ }
function Bad ($m, $fix)  { Write-Host "  [FAIL] $m" -ForegroundColor Red; $script:fail++;
                           if ($fix) { Write-Host "         -> $fix" -ForegroundColor Yellow } }
function Skip($m)        { Write-Host "  [SKIP] $m" -ForegroundColor DarkGray; $script:skip++ }
function Head($m)        { Write-Host "`n=== $m ===" -ForegroundColor Cyan }

# 直连探测（--noproxy：本机 mihomo 会拦这些域名，测线上必须绕过代理；2026-10-13 教训）
function Get-Http ($url, $timeoutSec = 12) {
    $raw = & curl.exe -sS --noproxy '*' -m $timeoutSec -w '|http=%{http_code}|t=%{time_total}' $url 2>&1
    $code = $LASTEXITCODE
    $text = ("$raw" -join ' ')
    $http = ''
    if ($text -match '\|http=(\d{3})') { $http = $Matches[1] }
    return [pscustomobject]@{ Exit = $code; Http = $http; Body = $text }
}

function Test-TcpPort ($hostName, $port) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $ar = $c.BeginConnect($hostName, $port, $null, $null)
        if (-not $ar.AsyncWaitHandle.WaitOne(5000)) { $c.Close(); return $false }
        $c.EndConnect($ar); $c.Close(); return $true
    } catch { return $false }
}

# ---------------------------------------------------------------- 面板目视截图回路（函数体；§8 调用）
# 背景：面板的**逻辑**有 pytest/vitest 与 tsc 把关，但**布局/文案渲染/禁用态**只有"真看"才发现。
#       2026-09-27 该回路当场抓到 5 处产品缺陷（Markdown 记号被原样渲染、隐户静默归零、
#       禁用态不可辨、州府级页路级读数未标注、页头再次写 Markdown）+ 截图台自身 4 个坑。
# 触发：面板源码有改动才跑；`-Shot` 强制。缺工具一律 SKIP，不造假失败。
function Invoke-ShotCheck {
    $feRoot  = Join-Path $RepoRoot 'game\frontend'
    $shotJs  = Join-Path $feRoot 'scripts\shot\shoot.mjs'
    $shotPy  = Join-Path $PyDir 'python.exe'
    $edgeExe = if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe' } else { '' }
    $shotOut = Join-Path $env:TEMP 'songzuo-shots'
    $nodeExe = $null
    $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeCmd) { $nodeExe = $nodeCmd.Source }
    elseif ($NodeDir -and (Test-Path (Join-Path $NodeDir 'node.exe'))) { $nodeExe = Join-Path $NodeDir 'node.exe' }
    $panelDirty = @(& git -C $RepoRoot status --porcelain -- game/frontend/src/renderer/panels 2>$null).Count

    if (-not (Test-Path $shotJs))              { Skip "缺少 $shotJs" }
    elseif (-not $Shot -and $panelDirty -eq 0) { Skip '面板未改动（要强制出图加 -Shot）' }
    elseif (-not $nodeExe)                     { Skip 'Node 不在 PATH（§1），略过截图回路' }
    elseif (-not (Test-Path $edgeExe))         { Skip '无 Edge，略过无头截图' }
    elseif (-not (Test-Path $shotPy))          { Skip '无 Python（§1），略过静态服务' }
    else {
        $env:SHOT_PYTHON = $shotPy
        $env:SHOT_OUT    = $shotOut
        Push-Location $feRoot
        & $nodeExe 'scripts\shot\shoot.mjs' 2>&1 | Out-Null
        $shotCode = $LASTEXITCODE
        Pop-Location
        $pngs  = @(Get-ChildItem (Join-Path $shotOut '*.png') -ErrorAction SilentlyContinue)
        $small = @($pngs | Where-Object { $_.Length -lt 10KB }).Count
        if ($shotCode -ne 0)      { Bad "截图回路失败（exit $shotCode）" '手动：cd game\frontend; npm run shot' }
        elseif ($pngs.Count -lt 9) { Bad "只生成 $($pngs.Count) 张（应 ≥9）" '检查 scripts/shot/shoot.mjs 的 PAGES' }
        elseif ($small -gt 0)     { Bad "$small 张 PNG < 10KB（疑似空白：面板崩了或 mock 没喂上）" '看页头探针 store ok 与引导期错误' }
        else                      { Ok "面板截图 $($pngs.Count) 张 → $shotOut（<10KB 视为空白，已排除）" }
    }
}

if ($Shot) {
    Head '面板目视截图回路（-Shot：只跑本节）'
    Invoke-ShotCheck
    Write-Host ("`n  OK={0}  FAIL={1}  SKIP={2}" -f $script:pass, $script:fail, $script:skip) -ForegroundColor Cyan
    return
}

# ---------------------------------------------------------------- 1. 本机工具链
Head '1. 本机工具链'
foreach ($c in 'node', 'npm', 'npx') {
    $g = Get-Command $c -ErrorAction SilentlyContinue
    if ($g) { Ok "$c -> $($g.Source)" }
    else { Bad "$c 不在 PATH" "把 $NodeDir 写入用户 PATH，或先点源 _dev_tools\dev-env.ps1" }
}
if (Test-Path (Join-Path $PyDir 'python.exe')) {
    Ok "Python -> $PyDir（$(& (Join-Path $PyDir 'python.exe') -V 2>&1)）"
} else { Bad "未找到 Python：$PyDir" '检查 .audit-venv 是否仍在' }
if (Test-Path (Join-Path $CargoDir 'cargo.exe')) { Ok "Rust/cargo -> $CargoDir" }
else { Bad "未找到 cargo：$CargoDir" '检查 ~/.cargo/bin' }
$devEnv = Join-Path $PSScriptRoot 'dev-env.ps1'
if (Test-Path $devEnv) { Ok "dev-env.ps1 存在（Python/Rust 靠它注入）" }
else { Bad "缺少 $devEnv" '见文档 §七' }

# ---------------------------------------------------------------- 2. 阿里云 ECS · MCP 健康端点
Head '2. 阿里云 ECS · MCP 健康端点（/healthz，无需 token）'
Write-Host "         目标：$McpHealthUrl" -ForegroundColor DarkGray
$h = Get-Http $McpHealthUrl
if ($h.Http -eq '200' -and $h.Body -match '"ok"\s*:\s*true') {
    $tools = if ($h.Body -match '"tools"\s*:\s*(\d+)') { $Matches[1] } else { '?' }
    if ("$tools" -eq "$ExpectTools") {
        Ok "healthz 200（tools=$tools，期望 $ExpectTools）$($h.Body -replace '\|http=.*$','')"
    } else {
        Bad "healthz 200 但 tools=$tools（期望 $ExpectTools）—— 服务可能降级或版本漂移" '对照 docs 开发服务器说明 §8.1 / mcp-songzuo README'
    }
} elseif ($h.Http) {
    Bad "healthz 返回 HTTP $($h.Http)：$($h.Body)" '查 ECS 容器状态（docker compose ps）与安全组 18080'
} else {
    Bad "healthz 不可达（curl exit=$($h.Exit)）：$($h.Body)" "查网络/安全组；ECS IP 可用环境变量 SONGZUO_ECS_IP 覆盖"
}

# ---------------------------------------------------------------- 3. 阿里云 ECS · 端口可达
Head '3. 阿里云 ECS · 直连 IP 端口可达（只做 TCP 连接，不登录）'
if (Test-TcpPort $EcsIp $McpPort) { Ok "$EcsIp`:$McpPort 可连（MCP 明文入口）" }
else { Bad "$EcsIp`:$McpPort 不可连" '查安全组是否放行 18080、ECS 是否在运行' }
if (Test-TcpPort $EcsIp 22) { Ok "$EcsIp`:22 可连（可选 · SSH；本脚本**不登录**）" }
else { Skip "$EcsIp`:22 不可连（可选，不影响 MCP）" }
if (Test-TcpPort $EcsIp 8443) { Ok "$EcsIp`:8443 可连（可选 · nginx TLS 备用入口，域名未备案时按 IP 访问亦 200）" }
else { Skip "$EcsIp`:8443 不可连（可选；该入口仅在域名可用时有意义）" }

# ---------------------------------------------------------------- 4. 可选 · 域名 TLS 入口（诊断）
Head '4. 可选 · 域名 TLS 入口（诊断，不作门禁）'
$tls = Get-Http $TlsHealthUrl
if ($tls.Http -eq '200') {
    Ok "域名入口 healthz 200（$TlsHealthUrl）—— 2026-10-22 复测证书校验通过；是否切换客户端入口由裁定决定"
} else {
    Skip "域名入口未通（HTTP=$($tls.Http)）：历史上曾被备案/SNI 拦截；客户端仍走直连 IP，不影响使用"
}

# ---------------------------------------------------------------- 5. 可选 · 官网探活
Head '5. 可选 · 官网 songzuo.online 探活'
$site = Get-Http $SiteUrl 15
if ($site.Http -eq '200') { Ok "官网 200（$SiteUrl）" }
else { Bad "官网返回 HTTP=$($site.Http)" '查 songzuo-site 容器与证书；站点仓库见 songzuo-site/（仓库外）' }

# ---------------------------------------------------------------- 6. MCP 服务器（~/.codebuddy/mcp.json）
Head '6. MCP 服务器（~/.codebuddy/mcp.json）'
$mcpJson = Join-Path $env:USERPROFILE '.codebuddy\mcp.json'
if (-not (Test-Path $mcpJson)) { Skip "无 $mcpJson" }
else {
    $m = $null
    try { $m = Get-Content $mcpJson -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { Bad "$mcpJson 不是合法 JSON" '修正该文件，或按文档 §8.6 重建' }
    if ($m -and $m.mcpServers) {
        $names = @($m.mcpServers.PSObject.Properties.Name)
        Ok "mcp.json 合法，共 $($names.Count) 个服务器：$($names -join '、')（生效需重启 IDE）"
        foreach ($n in $names) {
            $s = $m.mcpServers.$n
            if (-not (Test-Path $s.command)) {
                Bad "[$n] command 不存在：$($s.command)" '修正路径（条目均指向 Node 安装目录下的 node.exe）'
                continue
            }
            $miss = @()
            foreach ($a in @($s.args)) {
                if ($a -like '*.js' -and -not (Test-Path $a)) { $miss += $a }
            }
            if ($miss.Count -eq 0) { Ok "[$n] 入口存在" }
            else { Bad "[$n] 入口缺失：$($miss -join ', ')" '修正 args 路径（见 §8.6 清单）' }
        }
    }
}

# ---------------------------------------------------------------- 7. 知识库与文档一致性（本地）
Head '7. 知识库与文档一致性（本地）'
# 背景：知识库是"产物"，改了 docs/ 不重建就会**静默过期**——而且旧版 kb_stats.py 的
#       OK/DRIFT 是库内自洽检查（恒报 OK），实测曾让 7 篇里 5 篇脱节却全绿。现已改为与磁盘源比对。
$kbDir   = Join-Path $RepoRoot '_dev_tools\game-docs\kb'
$kbStats = Join-Path $kbDir 'kb_stats.py'
$kbBuild = Join-Path $kbDir 'build_kb.py'
$kbPy    = Join-Path $PyDir 'python.exe'
if (-not (Test-Path $kbStats)) { Skip "缺少 $kbStats" }
elseif (-not (Test-Path $kbPy)) { Skip '无 Python（§1），略过知识库一致性检查' }
else {
    $kbOut  = & $kbPy $kbStats 2>&1
    $kbCode = $LASTEXITCODE
    if ($kbCode -eq 0) { Ok '两个知识库与磁盘源文档一致' }
    elseif ($Fix) {
        & $kbPy $kbBuild build 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Ok '知识库已重建（-Fix）：build_kb.py build 完成' }
        else { Bad '知识库重建失败' "手动跑：& '$kbPy' '$kbBuild' build" }
    }
    else {
        $stale = @($kbOut | Select-String -Pattern '\[STALE\]' -AllMatches).Count
        Bad "知识库已脱节（$stale 篇）——改了 docs/ 但未重建" '重跑本脚本并加 -Fix（自动重建两库），或手动 python build_kb.py build'
    }
}

# ---------------------------------------------------------------- 8. 面板目视截图回路（本地，dev-only）
Head '8. 面板目视截图回路（本地）'
Invoke-ShotCheck

# ---------------------------------------------------------------- 汇总
Write-Host "`n=== 汇总 ===" -ForegroundColor Cyan
Write-Host ("  OK={0}  FAIL={1}  SKIP={2}" -f $script:pass, $script:fail, $script:skip)
Write-Host "  说明：阿里云侧只校验 /healthz 与端口；OSS/RDS/FC 等未开通服务不在检查范围（见文档 §8.3）。" -ForegroundColor DarkGray
if ($script:fail -eq 0) { Write-Host '  自检通过。' -ForegroundColor Green }
else { Write-Host '  存在失败项，按上面 -> 提示处理。' -ForegroundColor Yellow }
exit ([int]($script:fail -gt 0))
