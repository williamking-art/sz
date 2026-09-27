#requires -Version 5.1
<#
cloudbase-check.ps1 —— 开发辅助工具链自检（默认只读；-Fix 修复可自动修复项）

用法：
    powershell -NoProfile -ExecutionPolicy Bypass -File _dev_tools\cloudbase-check.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File _dev_tools\cloudbase-check.ps1 -Fix

它检查什么（对应文档《开发服务器与回归测试说明》§七 / §八）：
  1. 本机三套工具链是否可直接调用（Node 已入用户 PATH；Python/Rust 走 dev-env.ps1）
  2. CloudBase MCP 的「地域」配置是否到位 —— 这是 MCP 的 PG 工具能否工作的关键（§8.0）
  3. CloudBase MCP 进程状态与日志里是否仍有 PG/地域 报错
  4. PG 直连备用通路是否可用（需提供 API Key，可选）
  5. 可选：CVM / CI 是否可达（需提供主机名，可选）

⚠️ 本文件必须保存为 **UTF-8 with BOM**：PowerShell 5.1 按 GBK 读 .ps1，
   中文注释无 BOM 会解析报错（见文档 §七 的踩坑记录）。
#>
param([switch]$Fix, [switch]$Shot)

$ErrorActionPreference = 'Continue'
$RepoRoot     = Split-Path -Parent $PSScriptRoot          # _dev_tools 的上级 = 仓库根
$McpCwd       = 'D:\codebuddy'                            # MCP 进程 cwd（§8.0 实测）
$EnvId        = 'william-1-d5grtya3z0b5e143d'
$Region       = 'ap-singapore'
$Site         = 'domestic'
$NodeDir      = 'D:\codebuddy\tools\nodejs\node-v20.19.5-win-x64'
$PyDir        = 'D:\codebuddy\.audit-venv\Scripts'
$CargoDir     = Join-Path $env:USERPROFILE '.cargo\bin'
$McpLogDir    = Join-Path $env:USERPROFILE '.cloudbase-mcp\logs'
$CfgPaths     = @((Join-Path $McpCwd '.cloudbase\project.json'),
                  (Join-Path $RepoRoot '.cloudbase\project.json'))

$script:pass = 0; $script:fail = 0; $script:skip = 0
function Ok  ($m)        { Write-Host "  [ OK ] $m" -ForegroundColor Green;  $script:pass++ }
function Bad ($m, $fix)  { Write-Host "  [FAIL] $m" -ForegroundColor Red; $script:fail++;
                           if ($fix) { Write-Host "         -> $fix" -ForegroundColor Yellow } }
function Skip($m)        { Write-Host "  [SKIP] $m" -ForegroundColor DarkGray; $script:skip++ }
function Head($m)        { Write-Host "`n=== $m ===" -ForegroundColor Cyan }

# ---------------------------------------------------------------- 面板目视截图回路（函数体；§8 调用）
# 背景：面板的**逻辑**有 pytest/vitest 与 tsc 把关，但**布局/文案渲染/禁用态**只有"真看"才发现。
#       2026-09-27 该回路当场抓到 5 处产品缺陷（Markdown 记号被原样渲染、隐户静默归零、
#       禁用态不可辨、州府级页路级读数未标注、页头再次写 Markdown）+ 截图台自身 4 个坑（方案 §8.2）。
# 触发：面板源码有改动才跑；`-Shot` 强制。缺工具一律 SKIP，不造假失败。
function Invoke-ShotCheck {
    $feRoot  = Join-Path $RepoRoot 'game\frontend'
    $shotJs  = Join-Path $feRoot 'scripts\shot\shoot.mjs'
    $shotPy  = Join-Path $PyDir 'python.exe'
    $edgeExe = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
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
        elseif ($small -gt 0)     { Bad "$small 张 PNG < 10KB（疑似空白：面板崩了或 mock 没喂上）" '看页头探针 store ok 与引导期错误；方案 §8.2' }
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
    else { Bad "$c 不在 PATH" "把 $NodeDir 写入用户 PATH，或先点源 _dev_tools\dev-env.ps1（可加 -Fix 由本脚本只补 PATH 提示）" }
}
if (Test-Path (Join-Path $PyDir 'python.exe')) {
    Ok "Python -> $PyDir（$(& (Join-Path $PyDir 'python.exe') -V 2>&1)）"
} else { Bad "未找到 Python：$PyDir" '检查 .audit-venv 是否仍在' }
if (Test-Path (Join-Path $CargoDir 'cargo.exe')) { Ok "Rust/cargo -> $CargoDir" }
else { Bad "未找到 cargo：$CargoDir" '检查 ~/.cargo/bin' }
$devEnv = Join-Path $PSScriptRoot 'dev-env.ps1'
if (Test-Path $devEnv) { Ok "dev-env.ps1 存在（Python/Rust 靠它注入）" }
else { Bad "缺少 $devEnv" '见文档 §七' }

# ---------------------------------------------------------------- 2. CloudBase 地域配置
Head '2. CloudBase 地域配置（MCP 的 PG 工具能否工作的关键，§8.0）'
$userRegion = [Environment]::GetEnvironmentVariable('TCB_REGION', 'User')
if ($userRegion -eq $Region) { Ok "用户级 TCB_REGION = $userRegion（IDE 重启后对 MCP 子进程生效）" }
else {
    if ($Fix) {
        [Environment]::SetEnvironmentVariable('TCB_REGION', $Region, 'User')
        Ok "已写入用户级 TCB_REGION = $Region（需重启 IDE 才生效）"
    } else { Bad "用户级 TCB_REGION = '$userRegion'（期望 $Region）" '重跑本脚本并加 -Fix，然后重启 IDE' }
}
foreach ($p in $CfgPaths) {
    if (-not (Test-Path $p)) {
        if ($Fix) {
            $dir = Split-Path -Parent $p
            if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
            $json = "{`n  `"envId`": `"$EnvId`",`n  `"region`": `"$Region`",`n  `"site`": `"$Site`"`n}`n"
            [IO.File]::WriteAllText($p, $json, [Text.UTF8Encoding]::new($false))
            Ok "已创建 $p"
        } else { Bad "缺少 $p" '重跑本脚本并加 -Fix' }
        continue
    }
    try { $cfg = Get-Content $p -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { Bad "$p 不是合法 JSON" '删除后重跑 -Fix'; continue }
    $rOk = ($cfg.region -eq $Region); $eOk = ($cfg.envId -eq $EnvId); $sOk = ($cfg.site -eq $Site)
    if ($rOk -and $eOk -and $sOk) { Ok "$p（envId/region/site 均正确）" }
    else {
        if ($Fix) {
            $json = "{`n  `"envId`": `"$EnvId`",`n  `"region`": `"$Region`",`n  `"site`": `"$Site`"`n}`n"
            [IO.File]::WriteAllText($p, $json, [Text.UTF8Encoding]::new($false))
            Ok "$p 已按期望值重写"
        } else {
            Bad "$p 内容不符（region='$($cfg.region)', envId='$($cfg.envId)', site='$($cfg.site)'）" '重跑本脚本并加 -Fix'
        }
    }
}

# ---------------------------------------------------------------- 3. MCP 进程与日志
Head '3. CloudBase MCP 进程与日志'
$proc = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'cloudbase-mcp' }
if ($proc) {
    foreach ($p in $proc) { Ok ("MCP 进程 PID=" + $p.ProcessId + "，启动于 " + $p.CreationDate) }
    Write-Host "         提示：改完第 2 节的配置后**不必重启**，但进程内缓存了 manager/地域，" -ForegroundColor DarkGray
    Write-Host "               需等其刷新（实测约 15 分钟）——期间复验会看到假阴性（§8.0）。" -ForegroundColor DarkGray
} else { Skip '未发现运行中的 cloudbase-mcp 进程（IDE 未开或集成未加载）' }
if (Test-Path $McpLogDir) {
    $latest = Get-ChildItem $McpLogDir -Filter '*.log' -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime | Select-Object -Last 1
    if ($latest) {
        $tail = Get-Content $latest.FullName -Tail 400 -ErrorAction SilentlyContinue
        $pgErr = $tail | Select-String -Pattern 'PG_NOT_READY' -Quiet
        $rgErr = $tail | Select-String -Pattern 'not in config support region' -Quiet
        if ($pgErr) { Bad "最近日志仍有 PG_NOT_READY（$($latest.Name)）" '确认第 2 节配置正确后等缓存刷新，再复验' }
        else { Ok "最近日志无 PG_NOT_READY（$($latest.Name)）" }
        if ($rgErr) { Skip '日志含云托管的地域报错（该地域本就不支持云托管，与 PG 无关）' }
    }
} else { Skip "无 MCP 日志目录：$McpLogDir" }
Write-Host '         注：MCP 工具本身无法从本脚本调用（stdio）。用 queryPgDatabase action=sql 复验：' -ForegroundColor DarkGray
Write-Host '             SELECT 1                                        -> 应成功' -ForegroundColor DarkGray
Write-Host '             SELECT count(*) FROM dev_econ_monthly / dev_ci_runs -> 240 / 34' -ForegroundColor DarkGray

# ---------------------------------------------------------------- 4. PG 直连备用通路（可选）
Head '4. PG 直连备用通路（可选，§8.7）'
$key = $env:TCB_PG_API_KEY
$keyFile = Join-Path $McpCwd '.cloudbase\pg_api_key.txt'
if (-not $key -and (Test-Path $keyFile)) { $key = (Get-Content $keyFile -Raw).Trim() }
if ($key) {
    $u = "https://$EnvId.api.tcloudbasegateway.com/v1/rdb/exec-pgsql"
    $b = Join-Path $env:TEMP 'cbcheck.json'
    [IO.File]::WriteAllText($b, '{"sql":"SELECT 1 AS ok"}', [Text.UTF8Encoding]::new($false))
    $r = curl.exe -sS -m 30 -w '|http=%{http_code}' -X POST -H "Authorization: Bearer $key" `
         -H 'Content-Type: application/json' --data-binary "@$b" $u 2>&1
    Remove-Item $b -Force -ErrorAction SilentlyContinue
    if ("$r" -match '\|http=200') { Ok "PG 直连可用：$r" }
    else { Bad "PG 直连失败：$r" 'API Key 可能已过期/被删（sz-dev-pg-http，2026-10-23 到期）；用 manageAppAuth 重签' }
} else {
    Skip "未提供 API Key。启用方式：设环境变量 TCB_PG_API_KEY，或写 $keyFile"
}

# ---------------------------------------------------------------- 5. CVM / CI（可选）
Head '5. CVM / CI（可选）'
$host_ = $env:SONGZUO_CVM_HOST
$sk = Join-Path $env:USERPROFILE '.ssh\sz_cvm_ed25519'
if (-not (Test-Path $sk)) { Skip "缺少 SSH 私钥：$sk" }
elseif (-not $host_) { Skip '未设 SONGZUO_CVM_HOST（仓库为公开库，主机名不入库），略过连通性检查' }
else {
    $out = & ssh -i $sk -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 `
           "root@$host_" 'tail -1 /var/log/sz-ci.log' 2>&1
    if ("$out" -match 'PASS|FAIL') { Ok "CVM 可达，CI 末行：$out" }
    else { Bad "CVM/CI 检查失败：$out" '检查网络、安全组与密钥' }
}

# ---------------------------------------------------------------- 6. MCP 服务器（~/.codebuddy/mcp.json）
Head '6. MCP 服务器（~/.codebuddy/mcp.json，§8.13）'
$mcpJson = Join-Path $env:USERPROFILE '.codebuddy\mcp.json'
if (-not (Test-Path $mcpJson)) { Skip "无 $mcpJson" }
else {
    $m = $null
    try { $m = Get-Content $mcpJson -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { Bad "$mcpJson 不是合法 JSON" '修正该文件，或按文档 §8.13 重建' }
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
            else { Bad "[$n] 入口缺失：$($miss -join ', ')" '修正 args 路径（见 §8.13 清单）' }
        }
    }
}

# ---------------------------------------------------------------- 7. 知识库与文档一致性（本地）
Head '7. 知识库与文档一致性（本地开发，2026-09-27 新增）'
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
    if ($kbCode -eq 0) { Ok '两个知识库与磁盘源文档一致（游戏库 7 篇 / 开发库 21 篇）' }
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
if ($script:fail -eq 0) { Write-Host '  工具链自检通过。' -ForegroundColor Green }
else { Write-Host '  存在失败项，按上面 -> 提示处理（多数可加 -Fix 自动修）。' -ForegroundColor Yellow }
exit ([int]($script:fail -gt 0))
