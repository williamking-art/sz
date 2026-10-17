param(
    [switch]$Fast,        # 后端只跑快路径（-m "not slow"，约省 30s）
    [switch]$SkipShot,    # 跳过截图矩阵（约 30s）
    [switch]$Bench        # 追加地图首帧基准（信息性，不计失败）
)
# =============================================================================
# 《宋祚》一条命令全量验证（2026-09-27）
#
# 为什么需要它：验证层已从 1 层长到 5 层（后端 pytest / 前端 vitest / tsc / 截图矩阵 / 基准），
# 散落在 README 与 cloudbase-check.ps1 的 §8 里 → **可复现的验证入口本身就是地基**，
# 否则"我跑过了"永远无法被复述。
#
# 分工：
#   · 本脚本 = **代码验证**（写代码后跑这个）；
#   · `_dev_tools/cloudbase-check.ps1` = **环境/云端/知识库**自检（含其 §8 会调截图回路）。
#
# 约定（都是踩过的坑）：
#   · 本文件必须存为 **UTF-8 with BOM**（PS 5.1 按 GBK 读无 BOM 的 .ps1 → 中文乱码）；
#   · `pytest.ini` 的 addopts=-q 与命令行 -q 叠加成 -qq 会**抑制摘要行** → 这里用 `-o addopts=` 覆盖；
#   · Node 可能不在 PATH → 先 Get-Command，再回落到固定目录；缺工具一律 SKIP，不造假失败。
# =============================================================================
$ErrorActionPreference = 'Continue'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$WorkspaceRoot = Split-Path -Parent $RepoRoot
$PyDir    = Join-Path $WorkspaceRoot '.audit-venv\Scripts'
$NodeDir  = Join-Path $WorkspaceRoot 'tools\nodejs\node-v20.19.5-win-x64'
$script:pass = 0; $script:fail = 0; $script:skip = 0

function Ok  ($m)       { Write-Host "  [ OK ] $m" -ForegroundColor Green;  $script:pass++ }
function Bad ($m, $fix) { Write-Host "  [FAIL] $m" -ForegroundColor Red;    $script:fail++
                          if ($fix) { Write-Host "         -> $fix" -ForegroundColor Yellow } }
function Skip($m)       { Write-Host "  [SKIP] $m" -ForegroundColor DarkGray; $script:skip++ }
function Head($m)       { Write-Host "`n=== $m ===" -ForegroundColor Cyan }

$py = Join-Path $PyDir 'python.exe'
$nodeExe = $null
$c = Get-Command node -ErrorAction SilentlyContinue
if ($c) { $nodeExe = $c.Source } elseif (Test-Path (Join-Path $NodeDir 'node.exe')) { $nodeExe = Join-Path $NodeDir 'node.exe' }
$npmCmd = $null
$c = Get-Command npm -ErrorAction SilentlyContinue
if ($c) { $npmCmd = $c.Source } elseif (Test-Path (Join-Path $NodeDir 'npm.cmd')) { $npmCmd = Join-Path $NodeDir 'npm.cmd' }
$fe = Join-Path $RepoRoot 'game\frontend'
$game = Join-Path $RepoRoot 'game'
$tsb = Join-Path $env:TEMP 'songzuo-verify'

Write-Host "宋祚 · 全量验证（Fast=$Fast SkipShot=$SkipShot Bench=$Bench）" -ForegroundColor White
Write-Host "  repo=$RepoRoot"

# ---------------------------------------------------------------- 1. 后端 pytest
Head '1. 后端 pytest（core/settlement/州县…）'
if (-not (Test-Path $py)) { Skip "无 Python：$py" }
else {
    Push-Location $game
    $args = @('-m','pytest','-p','no:cacheprovider','-o','addopts=','-q','--tb=line')
    if ($Fast) { $args += @('-m','not slow') }
    $out = & $py @args 2>&1
    $code = $LASTEXITCODE
    Pop-Location
    $sum = ($out | Select-String -Pattern 'passed|failed|error' | Select-Object -Last 1)
    if ($code -eq 0) { Ok "pytest 通过：$sum" }
    else { Bad "pytest 失败（exit $code）：$sum" 'cd game; python -m pytest -q --tb=short' }
}

# ---------------------------------------------------------------- 2. 前端 vitest
Head '2. 前端 vitest（组件/工具/面板）'
if (-not $npmCmd) { Skip '无 npm' }
else {
    Push-Location $fe
    $out = & $npmCmd test 2>&1
    $code = $LASTEXITCODE
    Pop-Location
    $sum = ($out | Select-String -Pattern 'Test Files|Tests ' | Select-Object -Last 2) -join ' / '
    if ($code -eq 0) { Ok "vitest 通过：$sum" } else { Bad "vitest 失败（exit $code）：$sum" 'cd game\frontend; npm test' }
}

# ---------------------------------------------------------------- 3. 类型检查（双配置）
Head '3. TypeScript 类型检查（web + node 两套 tsconfig）'
if (-not $nodeExe) { Skip '无 node' }
else {
    foreach ($cfg in @('tsconfig.web.json','tsconfig.node.json')) {
        Push-Location $fe
        $out = & $nodeExe 'node_modules\typescript\bin\tsc' --noEmit -p $cfg --tsBuildInfoFile "$tsb-$cfg" 2>&1
        $code = $LASTEXITCODE
        Pop-Location
        if ($code -eq 0) { Ok "$cfg 通过" }
        else { Bad "$cfg 报错（exit $code）" (($out | Select-Object -First 2) -join ' | ') }
    }
}

# ---------------------------------------------------------------- 4. 截图矩阵（目视层）
Head '4. 面板截图矩阵（9 张；空白页会被体积识别）'
if ($SkipShot) { Skip '按 -SkipShot 跳过' }
elseif (-not ($nodeExe -and $npmCmd)) { Skip '无 node/npm' }
else {
    $shotOut = Join-Path $env:TEMP 'songzuo-shots'
    $env:SHOT_PYTHON = $py
    $env:SHOT_OUT = $shotOut
    Push-Location $fe
    & $nodeExe 'scripts\shot\shoot.mjs' 2>&1 | Out-Null
    $code = $LASTEXITCODE
    Pop-Location
    $pngs = @(Get-ChildItem (Join-Path $shotOut '*.png') -ErrorAction SilentlyContinue)
    $small = @($pngs | Where-Object { $_.Length -lt 10KB }).Count
    if ($code -ne 0) { Bad "截图回路失败（exit $code）" 'cd game\frontend; npm run shot' }
    elseif ($pngs.Count -lt 9) { Bad "只生成 $($pngs.Count) 张（应 ≥9）" '检查 scripts/shot/shoot.mjs 的 PAGES' }
    elseif ($small -gt 0) { Bad "$small 张 <10KB（疑似空白：崩了或 mock 没喂上）" '看页头探针 store ok / 引导期错误；方案 §8.2' }
    else { Ok "截图 $($pngs.Count) 张 → $shotOut" }
}

# ---------------------------------------------------------------- 5. 基准（信息性）
if ($Bench) {
    Head '5. 地图首帧基准（信息性，不计失败）'
    if (-not ($nodeExe -and $npmCmd)) { Skip '无 node/npm' }
    else {
        Push-Location $fe
        & $nodeExe 'scripts\shot\bench-map.mjs' 2>&1 | Select-String -Pattern 'JSON.parse|feature|合计|文件' | ForEach-Object { Write-Host "  $_" }
        Pop-Location
        Ok '基准已输出（对照报告 §11 的区间，不作失败判据）'
    }
}

# ---------------------------------------------------------------- 汇总
Write-Host "`n=== 汇总 ===" -ForegroundColor Cyan
Write-Host ("  OK={0}  FAIL={1}  SKIP={2}" -f $script:pass, $script:fail, $script:skip)
if ($script:fail -eq 0) { Write-Host '  全量验证通过。' -ForegroundColor Green }
else { Write-Host '  存在失败项，按上面 -> 提示处理。' -ForegroundColor Yellow }
exit $script:fail
