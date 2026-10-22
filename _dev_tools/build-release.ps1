param(
    [switch]$SkipPyInstaller,
    [switch]$SkipFrontend
)
# =============================================================================
# 《宋祚》发布打包（2026-10-18）
# 顺序：PyInstaller 后端 one-dir → electron-vite build → electron-builder NSIS → 校验产物
# 前置：frontend/node_modules/electron/dist 必须存在
#   （可从 %LOCALAPPDATA%\electron\Cache\electron-v33.0.0-win32-x64.zip 解压恢复，
#    并写 node_modules/electron/path.txt = electron.exe）
# =============================================================================
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$py = Join-Path (Split-Path -Parent $RepoRoot) '.audit-venv\Scripts\python.exe'
$node = Join-Path (Split-Path -Parent $RepoRoot) 'tools\nodejs\node-v24.22.1-win-x64\node.exe'
$game = Join-Path $RepoRoot 'game'
$fe = Join-Path $game 'frontend'

function Step($m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }

if (-not (Test-Path $py)) { throw "缺少 Python：$py" }
if (-not (Test-Path $node)) { throw "缺少 Node：$node" }
if (-not (Test-Path (Join-Path $fe 'node_modules\electron\dist\electron.exe'))) {
    throw "electron/dist 缺失：请先解压 electron 缓存并写 path.txt（见脚本头注释）"
}

if (-not $SkipPyInstaller) {
    Step '1. PyInstaller 后端 one-dir（game/dist/SongZuo）'
    Push-Location $game
    & $py -m PyInstaller SongZuo.spec --noconfirm
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "PyInstaller 失败（exit $LASTEXITCODE）" }
    Pop-Location
    if (-not (Test-Path (Join-Path $game 'dist\SongZuo\SongZuo.exe'))) {
        throw "PyInstaller 产物缺失：game/dist/SongZuo/SongZuo.exe"
    }
    Write-Host '  PyInstaller OK'
}

if (-not $SkipFrontend) {
    Step '2. electron-vite build（out/renderer）'
    Push-Location $fe
    & $node 'node_modules\electron-vite\bin\electron-vite.js' build
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "electron-vite build 失败（exit $LASTEXITCODE）" }
    Pop-Location
    if (-not (Test-Path (Join-Path $fe 'out\renderer\index.html'))) {
        throw "前端产物缺失：out/renderer/index.html"
    }
    Write-Host '  electron-vite OK'
}

Step '3. electron-builder NSIS'
Push-Location $fe
& $node 'node_modules\electron-builder\out\cli\cli.js' --win nsis --publish never
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "electron-builder 失败（exit $LASTEXITCODE）" }
Pop-Location

Step '4. 产物校验'
$outDir = Join-Path $RepoRoot 'songzuo'
$installer = Get-ChildItem $outDir -File -Filter '*.exe' -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like '*Setup*' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $installer) { throw "未找到安装包：$outDir\*Setup*.exe" }
$unpacked = Join-Path $outDir 'win-unpacked\SongZuo.exe'
$backend = Join-Path $outDir 'win-unpacked\resources\backend\SongZuo.exe'
$asar = Join-Path $outDir 'win-unpacked\resources\app.asar'
foreach ($p in @($unpacked, $backend, $asar)) {
    if (-not (Test-Path $p)) { throw "产物缺失：$p" }
}
$mb = [math]::Round($installer.Length / 1MB, 1)
if ($mb -lt 100) { throw "安装包过小（$mb MB），疑似不完整" }
$ageH = [math]::Round(((Get-Date) - $installer.LastWriteTime).TotalHours, 2)
if ($ageH -gt 2) { throw "安装包不是本次构建（$ageH 小时前）" }
Write-Host ("  安装包：{0}（{1} MB，{2}）" -f $installer.FullName, $mb, $installer.LastWriteTime)
Write-Host ("  unpacked：{0} / backend：{1} / app.asar：{2}" -f $unpacked, $backend, $asar)
Write-Host '打包完成。' -ForegroundColor Green