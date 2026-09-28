// electron-builder `afterPack` 钩子：把**图标与版本信息**写进打包后的 exe。
//
// 背景（2026-09-27）：本机无管理员权限，electron-builder 解压 winCodeSign 时因 macOS
// 符号链接（darwin/*.dylib）失败 → 只能设 `win.signAndEditExecutable = false`，
// 于是 electron-builder 自己**不写**图标/版本。此前是打包后手工跑 rcedit 补目录版，
// 但 **NSIS 安装包内的 exe 仍会是 Electron 默认图标**（安装包在 afterPack 之后压缩）。
//
// 本钩子在"打包完成、安装包压缩之前"执行，用 electron-builder 自带缓存里的 rcedit
// 写入图标与版本 → 目录版与安装包版**同时**正确。
//
// rcedit 来自缓存（无需下载、无需管理员）：%LOCALAPPDATA%\electron-builder\Cache\winCodeSign\*\rcedit-x64.exe
const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

function findRcedit() {
  const roots = [
    path.join(os.homedir(), "AppData", "Local", "electron-builder", "Cache", "winCodeSign"),
    path.join(os.homedir(), "AppData", "Local", "electron-builder", "Cache"),
  ];
  for (const root of roots) {
    if (!fs.existsSync(root)) continue;
    for (const entry of fs.readdirSync(root)) {
      const cand = path.join(root, entry, "rcedit-x64.exe");
      if (fs.existsSync(cand)) return cand;
    }
  }
  return null;
}

exports.default = async function afterPack(context) {
  const appOutDir = context.appOutDir;
  const exe = path.join(appOutDir, "SongZuo.exe");
  const rcedit = findRcedit();
  if (!rcedit) {
    console.warn("[afterPack] 未找到 rcedit，跳过图标写入（exe 将保留 Electron 默认图标）");
    return;
  }
  if (!fs.existsSync(exe)) {
    console.warn("[afterPack] 未找到 " + exe + "，跳过");
    return;
  }
  // game/frontend/scripts → ../../assets/icon.ico = game/assets/icon.ico
  const ico = path.resolve(__dirname, "..", "..", "assets", "icon.ico");
  execFileSync(
    rcedit,
    [
      exe,
      "--set-icon", ico,
      "--set-version-string", "ProductName", "SongZuo",
      "--set-version-string", "FileDescription", "SongZuo",
      "--set-version-string", "CompanyName", "SongZuo",
      "--set-version-string", "LegalCopyright", "SongZuo",
      "--set-version-string", "OriginalFilename", "SongZuo.exe",
      "--set-file-version", "0.1.0.0",
      "--set-product-version", "0.1.0.0",
    ],
    { stdio: "inherit" },
  );
  console.log("[afterPack] 已写入图标与版本信息: " + exe);
};
