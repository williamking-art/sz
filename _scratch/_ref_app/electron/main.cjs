app, BrowserWindow, Menu, clipboard, ipcMain, shell } = require("electron");
const { spawn, execFileSync } = require("node:child_process");
const { once } = require("node:events");
const fs = require("node:fs");
const http = require("node:http");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");
const steam = require("./steam.cjs");
const { pickGameDataDir } = require("./dataDir.cjs");

// 双实例锁：两个实例 = 两个后端 = 两个 writer 打同一个 ming_sim.db（无 WAL）→ 丢写/锁超时，
// 退出时后写的那个覆盖云端存档。必须在其它任何初始化之前拿锁，抢不到就立刻退出，
// 交给已在跑的那个实例（由下面的 second-instance 监听器把它的窗口拉到前台）。
if (!app.requestSingleInstanceLock()) {
  app.quit();
  process.exit(0);
}

// 关掉 Chromium 自动播放限制：让主界面背景音乐进游戏即响，无需用户先有手势。
// 命令行开关须在 app ready 前设；与 webPreferences.autoplayPolicy 双保险（不同版本认其一）。
app.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required");

// Steam Overlay 注入（微交易授权框、Shift+Tab、截图都靠它）：
// Electron 默认把渲染放在隔离的 GPU 进程，Steam overlay 钩不到 → overlay 不显示、
// 充值授权框弹不出来。--in-process-gpu 把 GPU 渲染拉回主进程，Steam 才能 hook 到渲染设备；
// --disable-direct-composition 防止渲染全白（Windows DirectComposition 问题，mac 无害）。
// 必须在 app ready 前设。参考：steamworks.js / electron-steam-notes 社区实践。
//
// 曾试过去掉 --disable-direct-composition 来修 Win11 Alt+Tab 幽灵窗口（steamworks.js
// issue #95），但实测导致整个游戏主窗口在 Windows 上直接白屏、完全打不开——这个开关防的是
// 真实渲染 bug 不只是 overlay，比幽灵窗口的 cosmetic 问题严重得多，已加回。
// 幽灵窗口问题暂搁置，玩家侧临时缓解：Alt+Tab 设置里选「仅打开的窗口」。
//
// 但这两个开关合起来也会在部分 Windows 机器上把画面打死：它们把窗口 surface 从
// DirectComposition 打回旧 present 路径，且 GPU 跑在主进程里没有降级余地，遇上特定显卡
// 驱动就是「窗口开了、只剩 backgroundColor、splash 一个字都没有」（已有玩家实测）。
// 故留一个安全模式逃生口——命中即不加这两个开关，代价是 Steam Overlay 与充值授权框失效，
// 换整个窗口能出画面。三个入口任一命中：
//   ① 命令行 --safe-gpu（Steam 库右键→属性→启动选项填这个，黑屏玩家唯一够得着的入口）
//   ② 环境变量 MING_SIM_SAFE_GPU=1
//   ③ window-prefs.json 的 gpuSafeMode（GPU 进程崩过时由 child-process-gone 自动写入）
// --no-safe-gpu 反向清除 ③，免得一次偶发崩溃让玩家永久失去 overlay。
const gpuSafeMode = (() => {
  if (process.argv.includes("--no-safe-gpu")) return false;
  if (process.argv.includes("--safe-gpu")) return true;
  if (process.env.MING_SIM_SAFE_GPU === "1") return true;
  try {
    const raw = fs.readFileSync(path.join(app.getPath("userData"), "window-prefs.json"), "utf8");
    return JSON.parse(raw).gpuSafeMode === true;
  } catch {
    return false;
  }
})();

if (!gpuSafeMode) {
  app.commandLine.appendSwitch("in-process-gpu");
  app.commandLine.appendSwitch("disable-direct-composition");
}

// 无 GPU 环境软件渲染兜底（Valve 自动测试 VM / 无独显 / 远程桌面常无硬件 GPU）：
// Chromium 135+（Electron 42 = Chromium 136+）默认禁用了 SwiftShader，检测不到硬件 GPU 时
// 不再自动回退软件渲染 → 直接黑屏（尤其叠加上面 --in-process-gpu，独立 GPU 进程的降级路径也没了）。
// --enable-unsafe-swiftshader 是「允许」回退而非「强制」软件渲染：有硬件 GPU 的真玩家照常走 GPU
// （overlay/充值/性能都不受影响），只有真无 GPU 时才退回 SwiftShader 把画面画出来，避免黑屏。
app.commandLine.appendSwitch("enable-unsafe-swiftshader");

const repoRoot = path.resolve(__dirname, "..", "..");
const host = "127.0.0.1";
const isPackaged = app.isPackaged;
const appStartedAt = Date.now();

let backend = null;
let mainWindow = null;

// 启动引导状态：splash.html 通过 bootstrap:getStatus 轮询它决定「等待/进游戏/报错」。
// phase: spawning → waiting → steam → ready（带 url）/ error（带 error+logPath）。
const bootstrapState = {
  phase: "spawning",
  port: 0,
  url: "",
  elapsedMs: 0,
  timeoutMs: 120000,
  error: "",
  detail: "",
  logPath: "",
};

// 后端输出的滚动尾巴（最近若干行）。后端启动阶段崩掉时，玩家看到的错误框此前只有一句
// 「后端进程启动阶段退出 code=1」+ 一个日志路径——真正的 Python traceback 躺在
// electron.log 里，得靠玩家自己找文件、发文件，一轮支持来回起步。把尾巴直接印进错误框，
// 玩家截一张图就够定位（实测就是这么卡住过一次）。
const BACKEND_TAIL_LINES = 14;
const backendTail = [];
const pushBackendTail = (chunk) => {
  const text = String(chunk);
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trimEnd();
    if (!line) continue;
    backendTail.push(line);
  }
  while (backendTail.length > BACKEND_TAIL_LINES) backendTail.shift();
};

// 统一日志落盘：主进程 [electron]/[steam]、渲染层 console/全局异常、充值流程
// 关键点都写进同一份 electron.log。stream 在创建窗口前打开，这样 splash/preload
// 乃至后端启动前的错误也不会丢。
let electronLogStream = null;
let electronConsoleCaptured = false;
const appendLog = (line) => {
  try {
    electronLogStream?.write(`${line}\n`);
  } catch {
    /* ignore */
  }
};
const log = (...args) => {
  const line = `[electron] ${args.map(formatLogValue).join(" ")}`;
  console.log(line);
  appendLog(line);
};
const warn = (...args) => {
  const line = `[electron][warn] ${args.map(formatLogValue).join(" ")}`;
  console.warn(line);
  appendLog(line);
};

const formatLogValue = (value) => {
  if (typeof value === "string") return value;
  if (value instanceof Error) return value.stack || value.message;
  try {
    const seen = new WeakSet();
    return JSON.stringify(value, (_key, nested) => {
      if (nested instanceof Error) {
        return { name: nested.name, message: nested.message, stack: nested.stack };
      }
      if (nested && typeof nested === "object") {
        if (seen.has(nested)) return "[Circular]";
        seen.add(nested);
      }
      return nested;
    });
  } catch {
    return String(value);
  }
};

const installElectronLogCapture = () => {
  if (electronLogStream) return;
  const electronLogPath = path.join(app.getPath("userData"), "electron.log");
  const originalLog = console.log.bind(console);
  const originalWarn = console.warn.bind(console);
  const originalError = console.error.bind(console);

  try {
    const stream = fs.createWriteStream(electronLogPath, { flags: "w", encoding: "utf8" });
    electronLogStream = stream;
    stream.on("error", (error) => {
      if (electronLogStream === stream) electronLogStream = null;
      originalError("[electron][error] write electron.log failed:", error);
    });
  } catch (error) {
    originalError("[electron][error] open electron.log failed:", error);
    return;
  }

  // steam.cjs 和其他主进程代码直接用 console，统一接入文件。log()/warn()
  // 自己已经 appendLog，这里跳过 [electron] 前缀防止每行重复两遍。
  if (!electronConsoleCaptured) {
    electronConsoleCaptured = true;
    const capture = (prefix, original, args) => {
      original(...args);
      if (typeof args[0] === "string" && args[0].startsWith("[electron]")) return;
      appendLog(`${prefix}${args.map(formatLogValue).join(" ")}`);
    };
    console.log = (...args) => capture("", originalLog, args);
    console.warn = (...args) => capture("[warn] ", originalWarn, args);
    console.error = (...args) => capture("[error] ", originalError, args);
  }
  log(`electron log capture → ${electronLogPath}`);
};

// 启动失败页的一键诊断：只取「本次启动」的 electron.log 尾部，既能抓 Python import 前的
// stderr，也避免把旧对局的大段运行日志复制出去。复制前遮掉常见密钥、票据和用户主目录；
// 即使后端 exe 根本没拉起来、日志文件尚未创建，也会返回 Electron 自身的环境与错误信息。
const DIAGNOSTIC_LOG_LIMIT = 512 * 1024;

const flushElectronLog = async () => {
  if (!electronLogStream || electronLogStream.destroyed || !electronLogStream.writable) return;
  await Promise.race([
    new Promise((resolve) => electronLogStream.write("", resolve)),
    new Promise((resolve) => setTimeout(resolve, 500)),
  ]);
};

const readCurrentStartupLog = (filePath) => {
  try {
    const stat = fs.statSync(filePath);
    // startBackend 之前就失败时磁盘上可能还留着上次的 electron.log，不能混进本次诊断。
    if (stat.mtimeMs < appStartedAt - 5000) return "";
    const size = Math.min(stat.size, DIAGNOSTIC_LOG_LIMIT);
    const buffer = Buffer.alloc(size);
    const fd = fs.openSync(filePath, "r");
    try {
      fs.readSync(fd, buffer, 0, size, Math.max(0, stat.size - size));
    } finally {
      fs.closeSync(fd);
    }
    return buffer.toString("utf8");
  } catch {
    return "";
  }
};

const redactDiagnostics = (text) => {
  let output = String(text || "");
  const homeDir = app.getPath("home");
  if (homeDir) output = output.split(homeDir).join("<USER_HOME>");
  return output
    .replace(/(authorization\s*["']?\s*[:=]\s*["']?(?:bearer\s+)?)[^"'\s,;}]+/gi, "$1<REDACTED>")
    .replace(
      /((?:api[_-]?key|session[_-]?token|access[_-]?token|auth[_-]?ticket|steam[_-]?ticket|password|client[_-]?secret)\s*["']?\s*[:=]\s*["']?)[^"'\s,}]+/gi,
      "$1<REDACTED>",
    )
    .replace(
      /([?&](?:api[_-]?key|token|ticket|session[_-]?token|access[_-]?token|password)=)[^&#\s]+/gi,
      "$1<REDACTED>",
    );
};

// 渲染层错误有时会在 React、window.error 和 console.error 多条链路上报。
// 同通道短时去重 + 全局每分钟限流，既保留完整错误栈，也防止动画循环中的
// 同一错误把玩家 electron.log 瞬间刷到几百 MB。
const RENDERER_LOG_MAX_LENGTH = 16 * 1024;
const RENDERER_LOGS_PER_MINUTE = 200;
const rendererLogState = {
  windowStartedAt: Date.now(),
  count: 0,
  suppressed: 0,
  recent: new Map(),
};

const appendRendererDiagnostic = (kind, payload) => {
  const now = Date.now();
  if (now - rendererLogState.windowStartedAt >= 60000) {
    if (rendererLogState.suppressed > 0) {
      appendLog(`[renderer] previous minute suppressed ${rendererLogState.suppressed} repeated/noisy messages`);
    }
    rendererLogState.windowStartedAt = now;
    rendererLogState.count = 0;
    rendererLogState.suppressed = 0;
    rendererLogState.recent.clear();
  }

  const safeKind = String(kind || "error").replace(/[^a-z0-9_.-]/gi, "_").slice(0, 48);
  let body = redactDiagnostics(formatLogValue(payload));
  if (body.length > RENDERER_LOG_MAX_LENGTH) {
    body = `${body.slice(0, RENDERER_LOG_MAX_LENGTH)}\n… [renderer message truncated]`;
  }
  const signature = `${safeKind}\0${body}`;
  const previousAt = rendererLogState.recent.get(signature);
  if (previousAt && now - previousAt < 2000) return;
  if (rendererLogState.count >= RENDERER_LOGS_PER_MINUTE) {
    rendererLogState.suppressed += 1;
    if (rendererLogState.suppressed === 1) {
      appendLog(`[renderer] rate limit reached (${RENDERER_LOGS_PER_MINUTE}/minute); suppressing further messages`);
    }
    return;
  }
  rendererLogState.recent.set(signature, now);
  rendererLogState.count += 1;
  appendLog(`[renderer:${safeKind}] ${new Date(now).toISOString()} ${body}`);
};

let processErrorHooksInstalled = false;
const installProcessErrorHooks = () => {
  if (processErrorHooksInstalled) return;
  processErrorHooksInstalled = true;
  process.on("uncaughtExceptionMonitor", (error, origin) => {
    appendLog(`[electron:uncaughtException] origin=${origin} ${redactDiagnostics(formatLogValue(error))}`);
  });
};

const buildStartupDiagnostics = async () => {
  await flushElectronLog();
  const logPath = path.join(app.getPath("userData"), "electron.log");
  const currentLog = readCurrentStartupLog(logPath);
  const lines = [
    "================ MingSalvageSim 启动诊断 ================",
    `time       : ${new Date().toISOString()}`,
    `version    : ${app.getVersion()}`,
    `packaged   : ${isPackaged}`,
    `platform   : ${os.platform()} ${os.release()} ${os.arch()}`,
    `runtime    : Electron ${process.versions.electron} / Chrome ${process.versions.chrome} / Node ${process.versions.node}`,
    `phase      : ${bootstrapState.phase}`,
    `safe gpu   : ${gpuSafeMode}`,
    `safe mods  : ${app.commandLine.hasSwitch("safe-mode")}`,
    `error      : ${bootstrapState.error || "(none)"}`,
    `log path   : ${logPath}`,
    "==========================================================",
    "",
    currentLog || "(本次启动尚未生成 electron.log；上面的错误与运行环境仍可用于排查。)",
  ];
  return redactDiagnostics(lines.join("\n"));
};

// 窗口偏好（目前只有全屏）持久化到 userData/window-prefs.json，启动时按上次状态恢复。
const windowPrefsPath = () => path.join(app.getPath("userData"), "window-prefs.json");

const readWindowPrefs = () => {
  try {
    const raw = fs.readFileSync(windowPrefsPath(), "utf8");
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
};

const writeWindowPrefs = (patch) => {
  try {
    const next = { ...readWindowPrefs(), ...patch };
    fs.writeFileSync(windowPrefsPath(), JSON.stringify(next), "utf8");
  } catch (e) {
    warn("write window-prefs failed:", e instanceof Error ? e.message : String(e));
  }
};

// --no-safe-gpu：把持久化的安全模式标记清掉（开关本身已在上面读过 argv，这里只落盘）。
if (process.argv.includes("--no-safe-gpu")) writeWindowPrefs({ gpuSafeMode: false });

// GPU / 工具进程异常退出：此前一条监听都没有，黑屏时 electron.log 里一点线索都没有
// （玩家发来的日志看着「一切正常」，排查当场断头）。全落盘；GPU 侧非正常退出还要把
// gpuSafeMode 写进 prefs，下次启动自动跳过那两个 Windows 开关，别让玩家一直黑着。
app.on("child-process-gone", (_event, details) => {
  warn(`child process gone: type=${details.type} reason=${details.reason} exitCode=${details.exitCode}`);
  if (details.type === "GPU" && details.reason !== "clean-exit") {
    writeWindowPrefs({ gpuSafeMode: true });
    warn("GPU 进程异常退出 → 已置 gpuSafeMode=true，下次启动走安全模式（无 Steam Overlay）。");
  }
});

// 客户端偏好（BGM/TTS 开关音量音色、流式速度、AI 须知去重、大臣排序…）持久化到
// userData/client-prefs.json。改用文件而非渲染层 localStorage：Electron 窗口 URL 端口每次启动
// 动态分配 → origin 变 → localStorage 读不回上次的值（表现为「每次进来音量/设置全重置」）。
// 文件存 userData，跨启动稳定，不受端口漂移影响。前端 prefs.ts 经 IPC 读写这里。

// 后端存档目录（注入给 Python 的 MING_SIM_USER_DATA_DIR）。
//   Windows：放「文档\MingSalvageSim」——玩家好找、好备份（游戏存档惯例位置）。
//   mac/其它：userData 根（= ~/Library/Application Support/MingSalvageSim）。
// 历史上 mac 曾多套一层 userData/python-data（早期给 Python 后端文件与 Electron 自己的文件
// window-prefs.json/electron.log 分命名空间留下的产物，双方文件名从无冲突，纯属多余的嵌套），
// 已拍平去掉。后端 paths.py 完全尊重这个 override，无需改 Python 侧。老数据（无论是 mac 的
// python-data 还是 Windows 的「Documents 之前」）由后端启动时从 MING_SIM_LEGACY_USER_DATA_DIR
// 复制过来（不删原位，兜底可回退），见 _migrate_save_layout()。
const gameDataDir = () => {
  // 「文档」路径来自注册表（app.getPath 只读账面值，不保证实体可用），故一律先探针再用；
  // 探不通先就地修（悬空重定向 → 把它指向的目标建出来，不动重定向本身），修不了就**抛错**
  // （startBackend 的 catch 把 message 送 splash 展示），绝不静默退回 userData——那会让玩家
  // 眼里存档全消失、本节存档分裂两地且不进 Steam 云。判定与修复在 dataDir.cjs（可脱离 Electron 跑测试）。
  let documents = "";
  try {
    documents = app.getPath("documents");
  } catch (err) {
    warn(`取「文档」目录失败：${err && err.message}`);
  }
  return pickGameDataDir({
    platform: process.platform,
    documentsDir: documents,
    userDataDir: app.getPath("userData"),
    log,
    warn,
  });
};

// MOD 与存档分址：MOD 放在游戏安装目录旁的 mods/，绝不放 userData。
// macOS 的 process.execPath 位于 Foo.app/Contents/MacOS/，因此取 .app 所在目录；
// Linux AppImage 优先使用 APPIMAGE 原始文件位置，避免落进 /tmp/.mount_* 临时挂载点。
const gameLocalDir = () => {
  if (!isPackaged) return repoRoot;
  if (process.platform === "darwin") {
    return path.resolve(path.dirname(process.execPath), "..", "..", "..");
  }
  if (process.platform === "linux" && process.env.APPIMAGE) {
    return path.dirname(path.resolve(process.env.APPIMAGE));
  }
  return path.dirname(process.execPath);
};

const readDotEnv = (filePath) => {
  if (!fs.existsSync(filePath)) return {};
  const env = {};
  for (const line of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const index = trimmed.indexOf("=");
    const key = trimmed.slice(0, index).trim();
    let value = trimmed.slice(index + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (key) env[key] = value;
  }
  return env;
};

const findOpenPort = () =>
  new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, host, () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close(() => resolve(port));
    });
  });

// 超时 120s：干净环境（全新 Windows + Defender 全量扫描 + PyInstaller 首次解压 ~几百MB +
// ONNX 模型加载）冷启动可远超旧的 45s，Valve 自动测试 VM / 玩家慢机器都会在 45s 内没起来被误判死。
// onProgress(elapsedMs, timeoutMs) 每轮回调，喂给 splash 进度条。
const waitForBackend = (port, timeoutMs = 120000, onProgress = null) => {
  const startedAt = Date.now();
  const urlPath = "/api/menu/status";
  return new Promise((resolve, reject) => {
    const tick = () => {
      onProgress?.(Date.now() - startedAt, timeoutMs);
      const request = http.get({ host, port, path: urlPath, timeout: 1500 }, (response) => {
        response.resume();
        if (response.statusCode && response.statusCode < 500) {
          resolve();
          return;
        }
        retry();
      });
      request.on("timeout", () => {
        request.destroy(new Error("timeout"));
      });
      request.on("error", retry);
    };

    const retry = () => {
      if (Date.now() - startedAt > timeoutMs) {
        reject(new Error(`FastAPI did not become ready on ${host}:${port}`));
        return;
      }
      setTimeout(tick, 300);
    };

    tick();
  });
};

const pythonExecutable = () => {
  const venvPython = path.join(repoRoot, ".venv", os.platform() === "win32" ? "Scripts/python.exe" : "bin/python");
  if (fs.existsSync(venvPython)) return venvPython;
  return os.platform() === "win32" ? "python" : "python3";
};

const backendExecutablePath = () => {
  const baseDir = process.resourcesPath;
  const exeName = os.platform() === "win32" ? "MingSalvageBackend.exe" : "MingSalvageBackend";
  return path.join(baseDir, "backend", "MingSalvageBackend", exeName);
};

const backendSpawnSpec = () => {
  if (isPackaged) {
    const executable = backendExecutablePath();
    if (!fs.existsSync(executable)) {
      throw new Error(`Packaged backend executable not found: ${executable}`);
    }
    return {
      command: executable,
      args: [],
      cwd: path.dirname(executable),
    };
  }
  return {
    command: pythonExecutable(),
    args: ["-m", "uvicorn", "web_app:app"],
    cwd: repoRoot,
  };
};

// 发行版类型由 build 时落的 edition.json 决定（与前端 VITE_STEAM_EDITION 同源，CI 按 tag 写）：
//   {"steam": true}  → Steam 版，隐藏 BYOK（前端 tree-shake + 后端 MING_SIM_STEAM_EDITION=1 兜底）
//   {"steam": false} → BYOK 版，保留自定义 API 入口（后端不设该 env）
// 缺文件/读失败 → 默认 true（安全侧：宁可隐藏，绝不意外暴露 BYOK，满足 Steam 规则）。
const isSteamEdition = () => {
  try {
    const raw = fs.readFileSync(path.join(__dirname, "edition.json"), "utf8");
    return JSON.parse(raw).steam !== false;
  } catch {
    return true;
  }
};

// 充值（Steam 微交易）由 edition.json 的 topup 决定（build:steam 时按 VITE_ENABLE_TOPUP 落）：
// 只有正式版 build（VITE_ENABLE_TOPUP=1）为 true → 给后端注 MING_SIM_TOPUP_CLIENT=1 放行充值端点。
// demo/playtest/BYOK 均为 false（默认关）→ 后端拒充值端点、前端也 tree-shake 掉充值 UI。
const isTopupEdition = () => {
  try {
    const raw = fs.readFileSync(path.join(__dirname, "edition.json"), "utf8");
    return JSON.parse(raw).topup === true;
  } catch {
    return false;
  }
};

const startBackend = async () => {
  const port = await findOpenPort();
  const dotenv = isPackaged ? {} : readDotEnv(path.join(repoRoot, ".env"));
  const env = {
    ...process.env,
    ...dotenv,
    // LLM payload dump 是开发调试用（写 scripts/runs/，打包后该相对路径不存在 → 只刷错误日志）。
    // 默认不开；env/.env 仍可强制开（开发）。
    ...(process.env.MING_SIM_DUMP_LLM || dotenv.MING_SIM_DUMP_LLM
      ? { MING_SIM_DUMP_LLM: process.env.MING_SIM_DUMP_LLM || dotenv.MING_SIM_DUMP_LLM }
      : {}),
    // HTTP debug 默认不写死开：由设置页「调试」开关控制（持久化 runtime_llm.json 的 http_debug），
    // 开后把真实 LLM 请求(URL/headers/body)与响应打到 backend.log。env 仍可强制开（开发/CI）。
    ...(process.env.MING_SIM_HTTP_DEBUG || dotenv.MING_SIM_HTTP_DEBUG
      ? { MING_SIM_HTTP_DEBUG: process.env.MING_SIM_HTTP_DEBUG || dotenv.MING_SIM_HTTP_DEBUG }
      : {}),
    MING_SIM_ELECTRON: "1",
    // Steam 发行版＝Electron 包：让后端拒绝「自定义 API / 自定义剧本写入 / 上传立绘」端点
    // （前端编译期硬隐之外的服务端兜底，满足 Steam 不得有 BYOK 入口的规则）。
    // BYOK 版（edition.json steam=false）不设此 env → 后端放行自定义 API。
    ...(isSteamEdition() ? { MING_SIM_STEAM_EDITION: "1" } : {}),
    // 正式版才放行充值端点（其余版本后端拒 /api/steam/topup/*）。见 isTopupEdition。
    ...(isTopupEdition() ? { MING_SIM_TOPUP_CLIENT: "1" } : {}),
    // 发行包固定扫描安装目录/mods；开发模式不注入游戏目录，改由 .env/进程环境中的
    // MING_SIM_MOD_PATH 指定工作根，防止仓库 mods 源码无条件出现在设置页。
    ...(isPackaged ? { MING_SIM_GAME_DIR: gameLocalDir() } : {}),
    MING_SIM_USER_DATA_DIR: gameDataDir(),
    // 老存档迁移用：旧目录（始终是 userData/python-data，Windows/mac 两端字面量相同）。
    // 后端 _migrate_save_layout() 据此把老存档 copy 到新目录（Windows：老目录之前就是这里；
    // mac：§4.0.5 拍平前也是这里）；新旧目录相同时（未改过方案的平台/环境）自动 no-op。
    MING_SIM_LEGACY_USER_DATA_DIR: path.join(app.getPath("userData"), "python-data"),
    // Steam 创意工坊路径推导用（ming_sim/paths.py:steam_workshop_dir()）。Steam 客户端启动游戏
    // 本来就会往进程 env 塞 SteamAppId，会随上面的 ...process.env 继承下去；这里是显式兜底，
    // 也让手工双击打包产物（不经 Steam 客户端）时工坊路径推导仍然能工作。
    ...(steam.getAppId() ? { MING_SIM_STEAM_APP_ID: String(steam.getAppId()) } : {}),
    // Steam 库右键「属性→启动选项」加的第二条「安全模式（不加载创意工坊 MOD）」，对应
    // --safe-mode 参数：订阅了坏 MOD 导致后端起不来时的逃生通道，见 §6.1b。
    ...(app.commandLine.hasSwitch("safe-mode") ? { MING_SIM_SAFE_MODE: "1" } : {}),
    PYTHONUNBUFFERED: "1",
    // Windows 上 Python 子进程 stdout/stderr 默认按 GBK 控制台代码页编码，print 含
    // ⏎/emoji 等非 GBK 字符会抛 UnicodeEncodeError，导致推演 agent 整体崩→只剩简化邸报。
    // 强制 UTF-8（PYTHONUTF8=1 开 UTF-8 模式，PYTHONIOENCODING 兜底）。mac 默认 UTF-8 无影响。
    PYTHONUTF8: "1",
    PYTHONIOENCODING: "utf-8",
  };
  if (isPackaged) {
    delete env.MING_SIM_MOD_PATH;
  } else if (String(env.MING_SIM_MOD_PATH || "").trim()) {
    // .env 中的相对路径一律以仓库根为基准，避免 npm 从 web/ 启动时前后端解析成两个位置。
    env.MING_SIM_MOD_PATH = path.resolve(repoRoot, String(env.MING_SIM_MOD_PATH).trim());
  }
  const spawnSpec = backendSpawnSpec();
  const backendArgs = [...spawnSpec.args, "--host", host, "--port", String(port)];

  backend = spawn(spawnSpec.command, backendArgs, {
    cwd: spawnSpec.cwd,
    env,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  let rejectBackendStartup;
  const backendStartupFailure = new Promise((_, reject) => {
    rejectBackendStartup = reject;
  });

  // 排障：把后端 stdout/stderr 原样落到 userData/electron.log（捕获 Python logging 初始化前的
  // 早期崩溃 + Electron 侧报错）。注意：后端自己另写一份结构化 backend.log 到
  // <MING_SIM_USER_DATA_DIR>/backend.log（web_app._install_backend_log_handler），调试面板读那个。
  // 这里这份是「裸 stdout 捕获」，作早期崩溃兜底，二者不冲突。
  const electronLogPath = path.join(app.getPath("userData"), "electron.log");

  // 启动头：把端口/URL/关键路径明确打到 electron.log 顶部。端口是 findOpenPort() 随机选的空闲端口，
  // 每次启动不同 —— 这一段让玩家/排障时打开 electron.log 第一眼就知道服务在哪个端口、存档在哪。
  const startupBanner = [
    "==================== MingSalvageSim 启动 ====================",
    `  packaged   : ${isPackaged}`,
    `  platform   : ${os.platform()} ${os.arch()}`,
    `  host:port  : ${host}:${port}`,
    `  url        : http://${host}:${port}`,
    `  backend exe: ${spawnSpec.command}`,
    `  userData   : ${app.getPath("userData")}`,
    `  gpu mode   : ${gpuSafeMode ? "SAFE（已跳过 in-process-gpu/disable-direct-composition，Steam Overlay 不可用）" : "normal"}`,
    `  electron.log: ${electronLogPath}`,
    `  python data: ${env.MING_SIM_USER_DATA_DIR}`,
    `  local mods : ${env.MING_SIM_MOD_PATH
      ? path.join(path.resolve(env.MING_SIM_MOD_PATH), "mods")
      : env.MING_SIM_GAME_DIR
        ? path.join(env.MING_SIM_GAME_DIR, "mods")
        : "(not configured)"}`,
    "============================================================",
    "",
  ].join("\n");
  process.stdout.write(startupBanner);
  electronLogStream?.write(startupBanner);
  backend.stdout.on("data", (chunk) => {
    process.stdout.write(`[fastapi] ${chunk}`);
    electronLogStream?.write(chunk);
    pushBackendTail(chunk);
  });
  backend.stderr.on("data", (chunk) => {
    process.stderr.write(`[fastapi] ${chunk}`);
    electronLogStream?.write(chunk);
    pushBackendTail(chunk);
  });
  backend.once("error", (error) => {
    const code = error && error.code ? ` code=${error.code}` : "";
    const message = `后端进程无法启动${code}：${error instanceof Error ? error.message : String(error)}`;
    warn(message);
    if (bootstrapState.phase !== "ready") {
      bootstrapState.error = message;
      bootstrapState.logPath = path.join(app.getPath("userData"), "electron.log");
      bootstrapState.phase = "error";
    }
    rejectBackendStartup(error);
  });
  backend.on("exit", (code, signal) => {
    log(`FastAPI exited code=${code ?? "null"} signal=${signal ?? "null"}`);
    backend = null;
    if (app.isQuitting) return;
    // ready 之前退出 = 启动阶段就崩（import 崩 / GBK / 缺库）：不 app.quit() 秒退，
    // 留住 splash 显示错误 + 日志路径。startBackend 的 await 也会因进程没就绪超时进 catch，
    // 但这里先把 error 写上，splash 立刻反馈，不必干等超时。
    if (bootstrapState.phase !== "ready") {
      if (!bootstrapState.error) {
        bootstrapState.error =
          `后端进程启动阶段退出（code=${code ?? "null"} signal=${signal ?? "null"}）。` +
          "若刚订阅了创意工坊 MOD，请在 Steam 库中右键本游戏 → 属性 → 启动选项，" +
          // 这里必须给能照抄的字面参数。原文写的是「安全模式（不加载创意工坊 MOD）」这句
          // 中文描述，玩家会原样粘进启动选项——而真正被解析的开关是 --safe-mode
          // （main.cjs 下面 hasSwitch("safe-mode") → MING_SIM_SAFE_MODE=1），粘中文毫无作用。
          "填入 --safe-mode 后再启动（该参数不加载创意工坊 MOD）。";
      }
      // Python 的 traceback 就在这段尾巴里（stdout/stderr 都原样落过盘，PYTHONUNBUFFERED=1
      // 保证退出前已吐出来）。经 redactDiagnostics 洗掉 key/token 再上屏。
      if (backendTail.length) {
        bootstrapState.detail = redactDiagnostics(backendTail.join("\n"));
      }
      bootstrapState.logPath = path.join(app.getPath("userData"), "electron.log");
      bootstrapState.phase = "error";
      rejectBackendStartup(
        new Error(`后端进程启动阶段退出（code=${code ?? "null"} signal=${signal ?? "null"}）`),
      );
      return;
    }
    // 游戏运行中后端才意外退出 → 无法继续，退出 app。
    app.quit();
  });

  bootstrapState.phase = "waiting";
  bootstrapState.port = port;
  await Promise.race([
    waitForBackend(port, bootstrapState.timeoutMs, (elapsedMs, timeoutMs) => {
      bootstrapState.elapsedMs = elapsedMs;
      bootstrapState.timeoutMs = timeoutMs;
    }),
    backendStartupFailure,
  ]);
  log(`FastAPI ready at http://${host}:${port}`);
  return port;
};

const stopBackend = () => {
  if (!backend) return;
  const child = backend;
  backend = null;
  if (child.killed) return;
  if (os.platform() === "win32") {
    spawn("taskkill", ["/pid", String(child.pid), "/f", "/t"]);
  } else {
    child.kill("SIGTERM");
    setTimeout(() => {
      if (!child.killed) child.kill("SIGKILL");
    }, 3000).unref();
  }
};

const postShutdown = (port, timeoutMs = 1500) =>
  new Promise((resolve, reject) => {
    const request = http.request(
      { host, port, path: "/api/menu/shutdown", method: "POST", timeout: timeoutMs },
      (response) => {
        response.resume();
        resolve();
      },
    );
    request.on("timeout", () => request.destroy(new Error("timeout")));
    request.on("error", reject);
    request.end();
  });

// 优雅退出：先 POST /api/menu/shutdown（既有端点，session.close()→db.close() 再退出：*nix 自发
// SIGTERM，Windows 直接 os._exit(0)），等子进程真正 exit 再返回；POST 失败（端口还没起来/已经挂了）
// 或超时才升级硬杀。目的是让 Steam 云存档拍快照时后端已经把 db 写完退出，而不是被 Electron 秒杀。
const stopBackendAndWait = async (timeoutMs = 5000) => {
  if (!backend) return;
  const child = backend;
  backend = null;
  if (child.killed) return;

  const exited = once(child, "exit").catch(() => {});

  if (bootstrapState.port) {
    try {
      await postShutdown(bootstrapState.port);
    } catch (e) {
      warn(`graceful shutdown POST failed, falling back to kill: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  const timedOut = await Promise.race([
    exited.then(() => false),
    new Promise((resolve) => setTimeout(() => resolve(true), timeoutMs)),
  ]);

  if (timedOut && !child.killed) {
    if (os.platform() === "win32") {
      spawn("taskkill", ["/pid", String(child.pid), "/f", "/t"]);
    } else {
      child.kill("SIGKILL");
    }
    await exited;
  }
};

// Steam 验票 → auth server 发 session token + 代理 LLM 配置 → 注入本地后端。
// 任何失败只 warn：回落到现状（玩家在设置页手填 key）。
const bootstrapSteamLlm = async (port) => {
  try {
    const result = await steam.authenticateWithServer({});
    if (!result.ok || !result.data || typeof result.data !== "object") {
      warn(`Steam LLM bootstrap skipped: ${result.error || "Steam auth failed"}`);
      return false;
    }
    const data = result.data;
    // 新模式：auth server 返回该 Steam 用户的专属 new-api key（api_key + quota_path）；
    // 旧模式：HMAC session_token 走透传代理。两者注入后端的方式相同。
    const apiKey = data.api_key || data.session_token;
    if (!apiKey || !data.llm || !data.llm.base_url || !data.llm.model) {
      warn("Steam LLM bootstrap skipped: auth server did not return a proxy session.");
      return false;
    }
    let quotaUrl = "";
    if (data.quota_path) {
      try {
        quotaUrl = new URL(data.quota_path, steam.getDefaultAuthUrl()).toString();
      } catch {
        quotaUrl = "";
      }
    }
    const response = await fetch(`http://${host}:${port}/api/steam/llm_session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: apiKey,
        base_url: data.llm.base_url,
        model: data.llm.model,
        advanced_model: data.llm.advanced_model || "",
        models: Array.isArray(data.llm.models) ? data.llm.models : [],
        expires_at: data.session_expires_at || 0,
        quota_url: quotaUrl,
      }),
    });
    if (!response.ok) {
      warn(`Steam LLM bootstrap failed: backend returned HTTP ${response.status}`);
      return false;
    }
    log("Steam LLM session injected into backend.");
    return true;
  } catch (error) {
    warn("Steam LLM bootstrap failed:", error instanceof Error ? error.message : String(error));
    return false;
  }
};

const bootstrapSteamLlmWithTimeout = (port, timeoutMs = 8000) =>
  Promise.race([
    bootstrapSteamLlm(port),
    new Promise((resolve) => setTimeout(() => resolve(false), timeoutMs).unref?.()),
  ]);

const scheduleSteamLlmRenewal = (port) => {
  const sixHours = 6 * 60 * 60 * 1000;
  const timer = setInterval(() => {
    bootstrapSteamLlm(port);
  }, sixHours);
  timer.unref?.();
};

const workshopItemsHash = (items) => items.map((it) => `${it.id}:${it.state}`).sort().join("|");

const postWorkshopReport = async (port, items) => {
  try {
    const response = await fetch(`http://${host}:${port}/api/steam/workshop`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: items.map((it) => ({
          id: it.id,
          state: it.state,
          folder: it.folder,
          size_on_disk: it.sizeOnDisk,
          timestamp: it.timestamp,
        })),
      }),
    });
    if (!response.ok) {
      warn(`workshop report failed: backend returned HTTP ${response.status}`);
    }
  } catch (error) {
    warn("workshop report failed:", error instanceof Error ? error.message : String(error));
  }
};

// 起后端 ready 后上报一次，之后 30s 轮询、仅 id/state 集合哈希变化才再 POST——
// getSubscribedItems() 是本地缓存查询，轮询开销可忽略；steamworks.js 没有 onItemInstalled
// 回调，只能轮询。见 docs/steam-workshop-cloud-plan.md §1.2。
const scheduleWorkshopReporting = (port) => {
  let lastHash = null;
  const tick = async () => {
    const items = steam.listWorkshopItems();
    const hash = workshopItemsHash(items);
    if (hash === lastHash) return;
    lastHash = hash;
    await postWorkshopReport(port, items);
  };
  tick();
  const timer = setInterval(tick, 30000);
  timer.unref?.();
};

const registerWindowIpc = () => {
  // splash.html 轮询启动进度。返回浅拷贝，防渲染层拿到内部引用。
  ipcMain.handle("bootstrap:getStatus", () => ({ ...bootstrapState }));
  ipcMain.handle("bootstrap:copyDiagnostics", async () => {
    try {
      const diagnostics = await buildStartupDiagnostics();
      clipboard.writeText(diagnostics);
      return { ok: true, length: diagnostics.length };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      warn("copy startup diagnostics failed:", message);
      return { ok: false, error: message };
    }
  });
  ipcMain.handle("app:isFullscreen", () => Boolean(mainWindow?.isFullScreen()));
  ipcMain.handle("app:setFullscreen", (_event, value) => {
    const next = Boolean(value);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.setFullScreen(next);
    }
    writeWindowPrefs({ fullscreen: next });
    return next;
  });
  // preload 转发前端的手动日志和全局异常。只接受主窗口发来的 IPC，
  // 避免未来加入的第三方窗口伪造大量日志。
  const fromMainWindow = (event) =>
    Boolean(mainWindow && !mainWindow.isDestroyed() && event.sender === mainWindow.webContents);
  ipcMain.on("client:log", (event, msg) => {
    if (!fromMainWindow(event)) return;
    const kind = msg && typeof msg === "object" && typeof msg.kind === "string" ? msg.kind : "client";
    appendRendererDiagnostic(kind, msg);
  });
  ipcMain.on("client:error", (event, report) => {
    if (!fromMainWindow(event)) return;
    const kind = report && typeof report === "object" ? report.kind : "error";
    appendRendererDiagnostic(kind, report);
  });
};

const registerSteamIpc = () => {
  ipcMain.handle("steam:getStatus", () => steam.getStatus());
  ipcMain.handle("steam:getAuthTicket", (_event, identity) => steam.getAuthTicket(identity));
  ipcMain.handle("steam:cancelAuthTicket", (_event, ticketId) => steam.cancelAuthTicket(ticketId));
  ipcMain.handle("steam:authenticateWithServer", (_event, options) => steam.authenticateWithServer(options));
  ipcMain.handle("steam:addStatInt", (_event, name, delta) => steam.addStatInt(name, delta));
  ipcMain.handle("steam:setStatInt", (_event, name, value) => steam.setStatInt(name, value));
  ipcMain.handle("steam:flushStats", () => steam.flushStats());
  // 充值（web 授权，mac 用）：用系统默认浏览器打开 Steam 授权 steamurl。
  // 选系统浏览器而非内嵌窗：浏览器里 Steam 大概率已登录，授权更顺；Steam 授权页也常拒绝被 iframe/内嵌窗嵌套。
  // 打开后渲染层轮询后端 finalize 确认到账（web 授权不发 microtxn 回调）。Win 用 overlay 不走这条。
  ipcMain.handle("steam:openTopupWindow", async (_event, steamurl) => {
    if (!steamurl || typeof steamurl !== "string") return { ok: false, error: "缺少授权地址" };
    try {
      await shell.openExternal(steamurl);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  });
};

// 充值：注册 Steam 微交易授权回调，玩家在游戏内授权框点确认/取消后，把结果转给渲染层
// （渲染层据 authorized 调后端 /api/steam/topup/finalize）。Steam 不可用时是 noop，不影响其他功能。
const registerMicroTxnForwarding = () => {
  steam.registerMicroTxnCallback((payload) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("steam:microtxnAuthorizationResponse", payload);
    }
  });
};

// Windows 11 辅助功能「文本大小」缩放（设置→辅助功能→文本大小）会被 Chromium 自动当整页
// zoom 套到渲染内容上——玩家调这条系统滑块，游戏内文字（连带整个 100vw/vh 布局）跟着变，
// 与显示器 DPI 缩放（screen.getPrimaryDisplay().scaleFactor）是两码事、Electron 没有开关
// 关掉这条自动缩放。用 webContents.setZoomFactor() 显式设成 100/该值来抵消：宿主设的 zoom
// 就是新的默认值，盖过那次自动缩放，游戏画面永远按系统 100% 走，不随这条系统滑块变化。
// 键不存在（Win10，或 Win11 上从未碰过这条滑块）一律当 100（未缩放）处理。
const windowsTextScaleFactor = () => {
  if (process.platform !== "win32") return 100;
  try {
    const out = execFileSync(
      "reg",
      ["query", "HKCU\\Software\\Microsoft\\Accessibility", "/v", "TextScaleFactor"],
      { encoding: "utf8", windowsHide: true, timeout: 3000 },
    );
    const match = out.match(/TextScaleFactor\s+REG_DWORD\s+0x([0-9a-fA-F]+)/);
    if (match) return parseInt(match[1], 16);
  } catch {
    // 键不存在（reg.exe 退出码非 0）或查询失败，按未缩放处理
  }
  return 100;
};

const createWindow = async () => {
  const startFullscreen = readWindowPrefs().fullscreen === true;
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1100,
    minHeight: 720,
    fullscreen: startFullscreen,
    backgroundColor: "#160f0a",
    icon: path.join(__dirname, "..", "build", os.platform() === "win32" ? "icon.ico" : "icon.png"),
    // 曾是 show:false + ready-to-show 里再 show()。那条路在 Windows 上会把窗口 surface
    // 从「隐藏窗口」重建到「可见窗口」，而 --disable-direct-composition + --in-process-gpu
    // 下这次重建可能 present 不出来 → 窗口开着但只剩 backgroundColor。splash.html 是本地
    // 静态页、毫秒级出画，藏首屏本就省不下什么，故直接可见开窗，绕开这次 surface 重建。
    show: true,
    // Windows/Linux 上隐藏默认应用菜单栏（File/Edit/View…），按 Alt 也不弹出。
    autoHideMenuBar: true,
    menuBarVisible: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      // 允许背景音乐进游戏即自动播放（否则 Chromium 默认要先有用户手势才出声）。
      autoplayPolicy: "no-user-gesture-required",
    },
  });

  // Windows 上 Electron 偶发：窗口显示了但 WebContents 拿不到键盘/输入焦点 → 所有
  // input/textarea 点了不聚焦、打不出字。不止首次 show() 会犯，alt-tab 切回、最小化恢复、
  // 退出全屏后也会复发（所以是「有时候」）。统一在每个「窗口拿到焦点/显示/退出全屏」的
  // 时机把焦点重新打到 WebContents 上，而不是只在启动时打一次。mac WKWebView 本就正常，无副作用。
  //
  // 有一类更顽固的失活：退游戏/切后台再切回时，OS 窗口有焦点（isFocused=true）但渲染层
  // Chromium frame 失焦（document.hasFocus=false）——两者不同步。此时单纯 wc.focus()/
  // window.focus() 打不破这个假死（实测无效），唯一可靠的复位是「模拟用户手动切窗口」：
  // mainWindow.blur() 让 OS 窗口真失焦 → 延迟 → mainWindow.focus() 重新聚焦，触发完整的
  // OS 级 blur→focus 事件链，重置 frame 焦点。但这记重招会自激（focus 事件里再 blur→focus
  // 会循环），所以：① 先试轻量 wc.focus()，② 下一帧确认仍未真聚焦才升级到 blur→focus，
  // ③ 用 forcingRefocus 标志在重招期间短路 focus 监听，防循环。
  let forcingRefocus = false;

  const refocusWebContents = () => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    const wc = mainWindow.webContents;
    if (!wc || wc.isDestroyed()) return;
    if (!wc.isFocused()) wc.focus();
  };

  // 重招：真失焦再聚焦，打破「窗口有焦点但 frame 失焦」的假死。仅在轻量手段无效时升级调用。
  const forceRefocusByBlurFocus = () => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    if (forcingRefocus) return; // 防重入：blur()/focus() 自身会触发 focus 监听
    forcingRefocus = true;
    mainWindow.blur(); // 让 OS 窗口真失焦（等价用户切走）
    setTimeout(() => {
      if (!mainWindow || mainWindow.isDestroyed()) {
        forcingRefocus = false;
        return;
      }
      mainWindow.focus(); // 重新聚焦，触发完整 OS blur→focus 链，复位 frame 焦点
      refocusWebContents();
      forcingRefocus = false;
    }, 60); // 给 OS 一帧多的时间真正 dispatch blur，再 focus 才能形成完整事件链
  };

  // 窗口拿到焦点/显示/恢复后：先轻量补焦，下一帧若渲染层仍没真聚焦，升级到 blur→focus 重招。
  const ensureFocusFixed = () => {
    if (forcingRefocus) return; // 重招进行中，别插队
    refocusWebContents(); // ① 先试轻量
    if (!mainWindow || mainWindow.isDestroyed()) return;
    const wc = mainWindow.webContents;
    if (!wc || wc.isDestroyed()) return;
    setTimeout(() => {
      if (forcingRefocus || !mainWindow || mainWindow.isDestroyed()) return;
      if (wc.isDestroyed()) return;
      // ② 询问渲染层 document 是否真拿到焦点（wc.isFocused 在这种假死下会骗人，问 DOM 更准）
      wc.executeJavaScript("document.hasFocus()", true)
        .then((hasFocus) => {
          if (hasFocus === false) forceRefocusByBlurFocus(); // ③ 升级重招
        })
        .catch(() => {
          /* 页面可能尚未加载，忽略；下次焦点事件再兜 */
        });
    }, 50);
    // 焦点/显示/恢复事件天然带「用户激活」上下文，是 BGM 自动播放补播的黄金时机：
    // 若首屏 kick 因 Win 冷启动慢全打空、或玩家最小化又切回导致音乐断了，这里以 user-gesture
    // 身份再触发一次 __bgmEnsurePlaying（同曲在播则是空操作，重复调安全）。
    if (wc && !wc.isDestroyed()) {
      wc.executeJavaScript("(window.__bgmEnsurePlaying ? !!window.__bgmEnsurePlaying() : undefined)", true)
        .catch(() => { /* 未就绪，下次焦点事件再兜 */ });
    }
  };

  // F5 / Ctrl+R / Cmd+R 强制刷新：Menu.setApplicationMenu(null) 抹掉了 Electron 默认的
  // Reload accelerator，玩家版按 F5 没反应。这里在主进程层拦键盘事件直接 reload BrowserWindow——
  // 走主进程而非渲染层 keydown，是因为「页面卡住」时渲染层 JS 事件循环可能正被阻塞、收不到键，
  // 而 before-input-event 在主进程，照样能把窗口整页重载，是卡死时的最后逃生口。
  mainWindow.webContents.on("before-input-event", (event, input) => {
    if (input.type !== "keyDown") return;
    const key = (input.key || "").toLowerCase();
    const isReload = key === "f5" || ((input.control || input.meta) && key === "r");
    if (!isReload) return;
    event.preventDefault();
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.reload();
  });

  // 强制 present 一帧：Windows 上「帧画好了但没送到窗口」是黑屏的直接形态（渲染进程活着、
  // JS 在跑、BGM 照响，只有画面是死的）。invalidate() 让 Chromium 整页重绘；再把窗口尺寸
  // 抖 1px 又抖回来，强制重建并提交 surface——这类 present 失败的通用兜招。只在 Windows 做，
  // 全屏/最大化态不动尺寸（会掉出全屏），只走 invalidate()。
  const nudgeRepaint = () => {
    if (process.platform !== "win32") return;
    if (!mainWindow || mainWindow.isDestroyed()) return;
    const wc = mainWindow.webContents;
    if (wc && !wc.isDestroyed()) wc.invalidate();
    if (mainWindow.isFullScreen() || mainWindow.isMaximized()) return;
    const [w, h] = mainWindow.getSize();
    mainWindow.setSize(w, h + 1);
    setTimeout(() => {
      if (mainWindow && !mainWindow.isDestroyed()) mainWindow.setSize(w, h);
    }, 32);
  };

  // 渲染进程全链路日志：Chromium console、preload、导航、网络、崩溃与假死。
  // console 只收 warning/error，不把游戏日常 info/debug 刷进玩家日志。
  const webContents = mainWindow.webContents;
  webContents.on("console-message", (details, legacyLevel, legacyMessage, legacyLine, legacySource) => {
    const level = details?.level || ["debug", "info", "warning", "error"][legacyLevel] || "info";
    if (level !== "warning" && level !== "error") return;
    let frameUrl = "";
    try {
      frameUrl = details?.frame?.url || "";
    } catch {
      // console 事件到主进程时 frame 可能已被销毁。
    }
    appendRendererDiagnostic(`console.${level}`, {
      message: details?.message || legacyMessage,
      source: details?.sourceId || legacySource,
      line: details?.lineNumber ?? legacyLine,
      frameUrl,
    });
  });
  webContents.on("preload-error", (_event, preloadPath, error) => {
    appendRendererDiagnostic("preload", {
      preloadPath,
      message: error?.message || String(error),
      stack: error?.stack,
    });
  });
  webContents.on("render-process-gone", (_event, details) => {
    warn("render process gone:", details);
  });
  webContents.on(
    "did-fail-load",
    (_event, code, description, url, isMainFrame, frameProcessId, frameRoutingId) => {
      appendRendererDiagnostic("load", {
        code,
        description,
        url,
        isMainFrame,
        frameProcessId,
        frameRoutingId,
      });
    },
  );
  webContents.on("did-finish-load", () => log(`renderer loaded: ${webContents.getURL()}`));
  webContents.on("unresponsive", () => warn(`webContents unresponsive: ${webContents.getURL()}`));
  webContents.on("responsive", () => log(`webContents responsive again: ${webContents.getURL()}`));

  // fetch/XHR/图片/字体在 Chromium 网络层失败时，未必会触发 JS 异常。记录本地
  // splash 与游戏 origin 的网络错误；ERR_ABORTED 多为正常跳转/取消，不记。
  webContents.session.webRequest.onErrorOccurred((details) => {
    if (details.webContentsId !== webContents.id || details.error === "net::ERR_ABORTED") return;
    let localRequest = false;
    try {
      const requestUrl = new URL(details.url);
      localRequest =
        requestUrl.protocol === "file:" ||
        requestUrl.hostname === "127.0.0.1" ||
        requestUrl.hostname === "localhost";
    } catch {
      // 无法解析的 URL 本身就值得保留。
      localRequest = true;
    }
    if (!localRequest) return;
    appendRendererDiagnostic("network", {
      method: details.method,
      resourceType: details.resourceType,
      url: details.url,
      error: details.error,
      fromCache: details.fromCache,
    });
  });

  mainWindow.once("ready-to-show", () => {
    if (!mainWindow) return;
    mainWindow.show();
    mainWindow.focus();
    refocusWebContents();
    nudgeRepaint();
  });
  // 窗口每次重新获得焦点（alt-tab 切回、点回程序、从最小化恢复）→ 把焦点接力给 WebContents。
  // 走 ensureFocusFixed：轻量补焦 + 渲染层若仍失活则升级 blur→focus 重招（治退后台切回打不了字）。
  mainWindow.on("focus", ensureFocusFixed);
  mainWindow.on("show", ensureFocusFixed);
  mainWindow.on("restore", ensureFocusFixed);
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
  // 用户用 OS 快捷键（F11 / mac 全屏按钮）切全屏时，也把偏好落盘，下次启动保持一致。
  mainWindow.on("enter-full-screen", () => writeWindowPrefs({ fullscreen: true }));
  mainWindow.on("leave-full-screen", () => {
    writeWindowPrefs({ fullscreen: false });
    // 退出全屏后 Windows 也会丢 WebContents 焦点，补一刀。
    refocusWebContents();
  });

  // 先加载本地启动页（不依赖后端，秒出画面）。后端 ready 后由 splash 自身据 bootstrap 状态
  // location.replace 跳到游戏 URL —— 这样双击立刻有画面，冷启动再慢也不黑屏/不秒退。
  await mainWindow.loadFile(path.join(__dirname, "splash.html"));

  // 页面从 splash 跳进真正的游戏 URL 时（http://127.0.0.1:port…）才 kick BGM。
  // 直接在 splash 上 kick 会打空（splash 没有 __bgmEnsurePlaying）。
  mainWindow.webContents.on("did-navigate", (_event, url) => {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      // BGM 进游戏即响：首屏 audio.play() 在无用户手势时会被 Chromium 拒；用 userGesture=true
      // 以「带用户手势」身份调前端 __bgmEnsurePlaying()，让首播合法。轮询重试到就绪，失败只 warn。
      kickBgmAutoplay(mainWindow.webContents);
      // 系统文本缩放隔离：per-origin 生效，须在跳到真正游戏 origin（127.0.0.1:port）后设，
      // 在 splash.html（file://）上设不会带过来。跑在 did-navigate（导航已提交、页面尚未
      // 渲染出内容）里，玩家看不到「先按系统缩放画一下再跳回 100%」的闪烁。
      const factor = windowsTextScaleFactor();
      if (factor && factor !== 100) {
        mainWindow.webContents.setZoomFactor(100 / factor);
        log(`Windows 文本缩放隔离：系统 TextScaleFactor=${factor}%，已设 zoomFactor=${(100 / factor).toFixed(4)} 抵消`);
      }
    }
  });
};

// 反复以 user-gesture 触发前端 __bgmEnsurePlaying()，直到它就绪并返回 true（已起播）或超时。
const kickBgmAutoplay = (webContents) => {
  let tries = 0;
  // Win 冷启动慢（杀毒扫描 + WebView2 初始化 + 后端 PyInstaller 解压），React 挂载可能远超 6s，
  // 太短会让 kick 全打空 → 表现为「进游戏 BGM 不响、要点一下才有」。拉到 ~15s 覆盖慢机器。
  const maxTries = 75; // 75 × 200ms ≈ 15s
  const tick = () => {
    if (!webContents || webContents.isDestroyed()) return;
    webContents
      // 返回值：函数不存在→undefined（未就绪，重试）；起播成功→true；被拦/未开→false。
      .executeJavaScript("(window.__bgmEnsurePlaying ? !!window.__bgmEnsurePlaying() : undefined)", true)
      .then((result) => {
        tries += 1;
        if (result === true) return; // 已起播，停
        if (tries >= maxTries) return; // 超时放弃，交首手势兜底
        setTimeout(tick, 200);
      })
      .catch((e) => {
        tries += 1;
        if (tries < maxTries) {
          setTimeout(tick, 200);
        } else {
          warn("bgm autoplay kick failed:", e instanceof Error ? e.message : String(e));
        }
      });
  };
  tick();
};

app.whenReady().then(async () => {
  // 必须早于 BrowserWindow/preload 和 Steam 初始化，否则启动页自己出错时日志还没打开。
  installElectronLogCapture();
  installProcessErrorHooks();

  // 玩家版不要 File/View/Reload/Toggle DevTools 这些浏览器壳菜单。但**不能**直接
  // Menu.setApplicationMenu(null)——那样会连默认 Edit 菜单一起抹掉，而 Edit 菜单的
  // copy/cut/paste/selectAll role 正是 Win 上 Ctrl+C/X/V/A 加速键的注册处；菜单一 null，
  // Win 选中文字也复制不了（mac 由系统另行接管故不受影响，这就是「mac 能复制 Win 不能」的根因）。
  // 故装一份「只留 Edit 剪贴板 role」的隐藏菜单（autoHideMenuBar 已开，菜单栏平时不显），
  // 让 Ctrl+C/X/V/A 加速键照常生效，又不露出多余壳菜单。
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      {
        label: "Edit",
        submenu: [
          { role: "cut" },
          { role: "copy" },
          { role: "paste" },
          { role: "selectAll" },
        ],
      },
    ]),
  );

  if (isPackaged && steam.restartAppIfNecessary()) {
    log("Steam restart requested, quitting so Steam can relaunch the app.");
    app.quit();
    return;
  }
  registerSteamIpc();
  registerWindowIpc();
  const status = steam.getStatus();
  if (status.available) {
    log(`Steam user ${status.personaName || "(unknown)"} appId=${status.appId}`);
  } else {
    warn(`Steam unavailable: ${status.error || "unknown error"}`);
  }

  // 先开窗显示本地 splash（秒出画面），再异步起后端 —— 双击立刻有画面，冷启动再慢也不黑屏/不秒退。
  // splash 轮询 bootstrapState：waiting 时显示进度条，ready 时自动跳游戏页，error 时显示日志路径。
  await createWindow();
  registerMicroTxnForwarding();

  const logPath = path.join(app.getPath("userData"), "electron.log");
  try {
    bootstrapState.phase = "spawning";
    const port = await startBackend();

    bootstrapState.phase = "steam";
    const injected = await bootstrapSteamLlmWithTimeout(port);
    if (injected) scheduleSteamLlmRenewal(port);
    scheduleWorkshopReporting(port);

    // 就绪：把游戏 URL 交给 splash，由它 location.replace 跳转（同一 BrowserWindow 内导航）。
    const apiBase = `http://${host}:${port}`;
    bootstrapState.url = `${apiBase}?api=${encodeURIComponent(apiBase)}`;
    bootstrapState.port = port;
    bootstrapState.phase = "ready";
  } catch (error) {
    // 不再静默 app.quit()：留住 splash 窗口显示错误 + 日志路径，玩家/Valve 机器人都能看到「有画面在报错」，
    // 而不是「双击秒退」。日志里有真正的失败原因（超时 / exe 缺失 / import 崩）。
    const msg = error instanceof Error ? error.stack || error.message : String(error);
    warn(msg);
    stopBackend();
    bootstrapState.error = bootstrapState.error || (error instanceof Error ? error.message : String(error));
    bootstrapState.logPath = logPath;
    bootstrapState.phase = "error";
  }
});

app.on("second-instance", () => {
  if (!mainWindow) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.focus();
});

let quitting = false;
app.on("before-quit", (event) => {
  if (quitting) return;
  quitting = true;
  app.isQuitting = true;
  event.preventDefault();
  stopBackendAndWait(5000).finally(() => app.quit());
});

app.on("window-all-closed", () => {
  app.quit();
});
const { 