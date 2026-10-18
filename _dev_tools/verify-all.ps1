param(
    [switch]$Fast,        # 后端只跑快路径（-m "not slow"）
    [switch]$SkipShot,    # 跳过截图矩阵
    [switch]$Bench,       # 追加地图首帧基准（信息性）
    [switch]$LongRun      # 追加 240 月长局哨兵（约 10 分钟）
)
# =============================================================================
# 《宋祚》一条命令全量验证（2026-10-18 重建）
#
# 层次：
#   0. 仓库完整性（tracked 删除 / 未跟踪测试 / 关键文件）+ Markdown 断链
#   1. 后端 pytest
#   1b. 质量放行门 · POP 守卫（SONGZUO_POPS_GUARD=1）
#   2. 前端 vitest
#   3. TypeScript 双配置类型检查
#   4. 面板截图矩阵（可 -SkipShot）
#   6. HEAD 干净导出 import 冒烟
#   7. 240 月长局哨兵（-LongRun）
# =============================================================================
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
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

Write-Host "宋祚 · 全量验证（Fast=$Fast SkipShot=$SkipShot Bench=$Bench LongRun=$LongRun）" -ForegroundColor White
Write-Host "  repo=$RepoRoot"

# ---------------------------------------------------------------- 0. 仓库完整性
Head '0. 仓库完整性（tracked 删除 / 未跟踪测试 / 关键文件）与文档断链'
if (-not (Test-Path $py)) { Skip "无 Python：$py" }
else {
    & $py (Join-Path $PSScriptRoot 'check_repo_integrity.py') 2>&1 | ForEach-Object { Write-Host "  $_" }
    if ($LASTEXITCODE -eq 0) { Ok '仓库完整性通过（未跟踪测试仅告警；发版请加 --strict）' }
    else { Bad '仓库完整性失败' 'python _dev_tools/check_repo_integrity.py' }
    & $py (Join-Path $PSScriptRoot 'check_doc_links.py') 2>&1 | ForEach-Object { Write-Host "  $_" }
    if ($LASTEXITCODE -eq 0) { Ok '文档断链检查通过' }
    else { Bad '存在 Markdown 断链' 'python _dev_tools/check_doc_links.py' }
}

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
    else {
        $out | Select-String -Pattern '^FAILED|^ERROR' | Select-Object -First 20 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        Bad "pytest 失败（exit $code）：$sum" 'cd game; python -m pytest -q --tb=short'
    }
}

# ---------------------------------------------------------------- 1b. POP 守卫门
Head '1b. 质量放行门 · POP 守卫（SONGZUO_POPS_GUARD=1）'
if (-not (Test-Path $py)) { Skip "无 Python：$py" }
else {
    $prevGuard = $env:SONGZUO_POPS_GUARD
    $prevMonths = $env:SONGZUO_GATE_MONTHS
    $env:SONGZUO_POPS_GUARD = '1'
    $env:SONGZUO_GATE_MONTHS = '15'
    try {
        Push-Location $RepoRoot
        $gout = & $py -m pytest -p no:cacheprovider -o addopts= -q --tb=line `
            _dev_tools/game-dev/tests/test_quality_gate_pops_guard.py 2>&1
        $gcode = $LASTEXITCODE
        Pop-Location
    } finally {
        $env:SONGZUO_POPS_GUARD = $prevGuard
        $env:SONGZUO_GATE_MONTHS = $prevMonths
    }
    $gsum = ($gout | Select-String -Pattern 'passed|failed|error' | Select-Object -Last 1)
    if ($gcode -eq 0) { Ok "POP 守卫门通过：$gsum" }
    else { Bad "POP 守卫门失败（exit $gcode）：$gsum" 'cd <repo>; $env:SONGZUO_POPS_GUARD=1; python -m pytest _dev_tools/game-dev/tests/test_quality_gate_pops_guard.py -q' }
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

# ---------------------------------------------------------------- 3. 类型检查
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

# ---------------------------------------------------------------- 4. 截图矩阵
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
    elseif ($small -gt 0) { Bad "$small 张 <10KB（疑似空白：崩了或 mock 没喂上）" '看页头探针 store ok / 引导期错误' }
    else { Ok "截图 $($pngs.Count) 张 → $shotOut" }
}

# ---------------------------------------------------------------- 5. 基准（可选）
if ($Bench) {
    Head '5. 地图首帧基准（信息性，不计失败）'
    if (-not ($nodeExe -and $npmCmd)) { Skip '无 node/npm' }
    else {
        Push-Location $fe
        & $nodeExe 'scripts\shot\bench-map.mjs' 2>&1 | Select-String -Pattern 'JSON.parse|feature|合计|文件' | ForEach-Object { Write-Host "  $_" }
        Pop-Location
        Ok '基准已输出（不作失败判据）'
    }
}

# ---------------------------------------------------------------- 6. HEAD 导出冒烟
Head '6. 干净导出 import 冒烟（git archive HEAD）'
if (-not (Test-Path $py)) { Skip '无 Python' }
else {
    $zip = Join-Path $env:TEMP 'songzuo-head.zip'
    $exp = Join-Path $env:TEMP 'songzuo-head-export'
    Push-Location $RepoRoot
    git archive --format=zip -o $zip HEAD 2>&1 | Out-Null
    Pop-Location
    if (Test-Path $exp) { Remove-Item -Recurse -Force $exp }
    Expand-Archive -Path $zip -DestinationPath $exp -Force
    $oldPyPath = $env:PYTHONPATH
    $env:PYTHONPATH = Join-Path $exp 'game'
    $mods = @('core.commands','core.settlement_pipeline','application.game_init',
              'core.domains.economy.market','core.foundation.ledger.pop_bridge')
    $bad = 0
    foreach ($m in $mods) {
        & $py -c "import $m" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { $bad++ }
    }
    $env:PYTHONPATH = $oldPyPath
    if ($bad -eq 0) { Ok "HEAD 导出 $($mods.Count) 个关键模块 import 通过" }
    else { Bad "$bad 个关键模块在干净导出中 import 失败" '检查是否有未入库模块/资源' }
}

# ---------------------------------------------------------------- 7. 240 月长局（可选）
if ($LongRun) {
    Head '7. 240 月长局哨兵（SONGZUO_LONG_RUN=240）'
    $oldLr = $env:SONGZUO_LONG_RUN
    $env:SONGZUO_LONG_RUN = '240'
    Push-Location $RepoRoot
    $out = & $py -m pytest '_dev_tools/game-dev/tests/test_m162_long_run_sentinel.py' -q -p no:cacheprovider -o addopts= --tb=line 2>&1
    $code = $LASTEXITCODE
    Pop-Location
    $env:SONGZUO_LONG_RUN = $oldLr
    $sum = ($out | Select-String -Pattern 'passed|failed|error' | Select-Object -Last 1)
    if ($code -eq 0) { Ok "240 月长局通过：$sum" } else { Bad "240 月长局失败（exit $code）：$sum" }
}

# ---------------------------------------------------------------- 汇总
Write-Host "`n=== 汇总 ===" -ForegroundColor Cyan
Write-Host ("  OK={0}  FAIL={1}  SKIP={2}" -f $script:pass, $script:fail, $script:skip)
if ($script:fail -eq 0) { Write-Host '  全量验证通过。' -ForegroundColor Green }
else { Write-Host '  存在失败项，按上面 -> 提示处理。' -ForegroundColor Yellow }
exit $script:fail