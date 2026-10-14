// 面板截图台 · 一键脚本（dev-only）：build → 起静态服务 → Edge 无头截图 → 收工。
//   npm run shot                    输出到 <repo>/_scratch/panels/*.png
//   $env:SHOT_OUT / SHOT_BROWSER / SHOT_PYTHON 可覆盖
// 注意：子进程一律 inherit/ignore（本机沙箱下管道 stdio 会被拒）。
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FE = resolve(__dirname, "../..");
// 输出与浏览器 profile 一律放仓库外：先前放在 frontend/ 内，被 git add -A 连带提交过
const OUT = process.env.SHOT_OUT ?? resolve(tmpdir(), "songzuo-shots");
const BROWSER = process.env.SHOT_BROWSER
  ?? "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const PYTHON = process.env.SHOT_PYTHON ?? "python";
const PORT = Number(process.env.SHOT_PORT ?? 8235);

// 要拍的面板：面板名 = src/renderer/panels/<name>.tsx（由 import.meta.glob 动态解析）
//   既有面板可能因 fixture 不全而显"—"或空表——那本身也是有效发现（面板对缺数据的容错），
//   但要区分"fixture 未覆盖"与"产品缺陷"。
// 第 5 项可选：页面文件（缺省 `panel.html`；`hud.html` 用于 HUD 四区占位/裁切核对）。
const PAGES = [
  // P1-1：在办事务面板（支持方/阻力方、当前阻碍、下月预判、圣旨留痕、颁旨入口），
  // 公开 tab 与密令 tab 各一张——两种队列的呈现不同（密令不支持调兵督行）。
  ["todo-public", "panel=TodoPanel", 1000, 1400],
  ["todo-secret", "panel=TodoPanel&tab=secret", 1000, 900],
  ["todo-empty", "panel=TodoPanel&empty=1", 1000, 700],
  // P2-1：主界面 HUD 四区——大窗 / 较小窗（宽 1024×高 640）/ 窄高窗 + 事务空状态
  ["hud-large", "empty=0", 1600, 900, "hud.html"],
  ["hud-small", "empty=0", 1024, 640, "hud.html"],
  ["hud-tiny-empty", "empty=1", 900, 560, "hud.html"],
  ["localarchive-circuit", "panel=LocalArchivePanel&kind=circuit&route=两浙路", 1000, 1520],
  ["localarchive-city", "panel=LocalArchivePanel&kind=city&route=杭州", 1000, 1320],
  ["provincemilitary", "panel=ProvinceMilitaryPanel&route=两浙路", 1000, 1240],
  // M243：**读数索引**（P5 新增的 21 项读数面板）——此前**不在清单内** ⇒ 截图验收不覆盖它，本行补齐
  ["readouthub", "panel=ReadoutHubPanel", 1000, 1200],
  ["PopPanel", "panel=PopPanel", 1000, 1100],
  ["LandPanel", "panel=LandPanel", 1000, 900],
  ["GranaryPanel", "panel=GranaryPanel", 1000, 900],
  ["CourtPanel", "panel=CourtPanel", 1000, 1100],
  ["AccountingPanel", "panel=AccountingPanel", 1000, 1000],
  ["MilitaryPanel", "panel=MilitaryPanel", 1000, 1000]
];

function run(file, args, opts = {}) {
  const r = spawnSync(file, args, { stdio: "inherit", ...opts });
  if (r.status !== 0) {
    console.error(`[shot] 失败：${file} ${args.join(" ")} (exit ${r.status})`);
    process.exit(r.status ?? 1);
  }
}

console.log("[shot] 1/3 构建截图台…");
run(process.execPath, [resolve(FE, "node_modules/vite/bin/vite.js"), "build",
  "--config", "vite.shot.config.mts"], { cwd: FE });

mkdirSync(OUT, { recursive: true });

console.log(`[shot] 2/3 起静态服务 127.0.0.1:${PORT} …`);
const srv = spawn(PYTHON, ["-m", "http.server", String(PORT), "--bind", "127.0.0.1",
  "--directory", resolve(FE, "_shot-dist")], { stdio: "ignore" });
const stop = () => { try { srv.kill(); } catch { /* ignore */ } };
process.on("exit", stop);

await new Promise((r) => setTimeout(r, 2000));
try {
  const probe = await fetch(`http://127.0.0.1:${PORT}/scripts/shot/panel.html`);
  if (!probe.ok) throw new Error(`HTTP ${probe.status}`);
} catch (e) {
  console.error(`[shot] 静态服务不可达：${e}`);
  stop();
  process.exit(1);
}

console.log("[shot] 3/3 截图…");
for (const [name, query, w, h, page = "panel.html"] of PAGES) {
  const url = `http://127.0.0.1:${PORT}/scripts/shot/${page}?${query}`;
  const png = resolve(OUT, `${name}.png`);
  const r = spawnSync(BROWSER, [
    "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
    `--user-data-dir=${resolve(tmpdir(), "songzuo-shot-profile")}`, "--hide-scrollbars",
    "--virtual-time-budget=6000", `--window-size=${w},${h}`, `--screenshot=${png}`, url
  ], { stdio: "ignore" });
  if (r.status !== 0) console.error(`[shot] ${name} 截图失败（exit ${r.status}）`);
  else console.log(`[shot]   ✓ ${name}.png  ${w}×${h}`);
}
stop();
console.log(`[shot] 完成 → ${OUT}`);
// 显式退出码：否则残留的子进程句柄会让 Node 以非零码收场（本项目规矩：非零退出必须查因）
process.exit(0);
