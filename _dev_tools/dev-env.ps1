# dev-env.ps1 —— 一键注入本机工具链到 PATH（宋祚项目，2026-09-23）
#
# 背景：本机 Node / Python / Rust 三套工具链都已安装，但**都不在 PATH**，
#       直接敲 node / python / cargo 会提示"找不到命令"（用 where 也查不到）。
#       本脚本把它们的绝对路径前置到 PATH，**只在当前 PowerShell 会话生效**。
#
# 用法（在项目根目录执行，注意开头那个点 = 点源，才会作用于当前会话）：
#     . .\_dev_tools\dev-env.ps1
#     python -m pytest          # 之后即可直接用
#     node -v ; cargo -V
#
# 想每次打开 PowerShell 自动生效？把下面这行加到 $PROFILE：
#     . D:\codebuddy\sz\_dev_tools\dev-env.ps1

$ErrorActionPreference = 'Stop'

# —— 定位各工具链（对版本号变化做容错，不写死具体版本目录）——
$nodeRoot = 'D:\codebuddy\tools\nodejs'
$nodeDir = $null
if (Test-Path $nodeRoot) {
    $nodeDir = (Get-ChildItem $nodeRoot -Directory -Filter 'node-v*-win-x64' -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending | Select-Object -First 1).FullName
}

$targets = @(
    @{ Name = 'Node';   Path = $nodeDir },
    @{ Name = 'Python'; Path = 'D:\codebuddy\.audit-venv\Scripts' },
    @{ Name = 'Rust';   Path = (Join-Path $env:USERPROFILE '.cargo\bin') }
)

$injected = @()
foreach ($t in $targets) {
    if (-not $t.Path) { Write-Warning "$($t.Name)：未找到安装目录（可检查脚本里的路径）"; continue }
    if (-not (Test-Path $t.Path)) { Write-Warning "$($t.Name)：路径不存在 -> $($t.Path)"; continue }
    if ($env:PATH -notlike "*$($t.Path)*") {
        $env:PATH = "$($t.Path);$env:PATH"
        $injected += "$($t.Name) -> $($t.Path)"
    } else {
        $injected += "$($t.Name) 已在 PATH 中"
    }
}

Write-Host '[dev-env] PATH 注入：' -ForegroundColor Green
$injected | ForEach-Object { Write-Host "  $_" }

# —— 自检（顺带把版本打出来，便于确认注入成功）——
Write-Host '[dev-env] 版本自检：' -ForegroundColor Green
foreach ($cmd in @('node', 'npm', 'python', 'cargo')) {
    $ver = try { (& $cmd --version 2>&1 | Select-Object -First 1) } catch { 'FAILED' }
    Write-Host ("  {0,-7} {1}" -f $cmd, $ver)
}

Write-Host ''
Write-Host '提示：想跑全量回归 → cd game ; python -m pytest' -ForegroundColor DarkGray
Write-Host '      （服务器侧 CI 见 _dev_tools/game-docs/docs/开发服务器与回归测试说明.md）' -ForegroundColor DarkGray
