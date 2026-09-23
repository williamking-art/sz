import { app, BrowserWindow, ipcMain, Menu, net, shell } from "electron";
import { join } from "path";
import { spawn, ChildProcess } from "child_process";
import { existsSync, readFileSync } from "fs";

// ---------------- 后端配置解析 ----------------
// 优先级：环境变量 SONGZUO_BACKEND > backend_config.json > 本地默认
interface BackendConfig {
  url: string;
  spawn: boolean;
  cwd?: string;
  command?: string;
  /** 服务端启用 SONGZUO_SERVER_TOKEN 时的 Bearer token；未配置为 undefined。 */
  token?: string;
}

const DEFAULT_BACKEND = "http://127.0.0.1:8080";

/** 规范化 token：去首尾空白，空串视为未配置（与 backend/client.py 的 strip 语义一致）。 */
function normalizeToken(raw: unknown): string | undefined {
  const s = typeof raw === "string" ? raw.trim() : "";
  return s.length > 0 ? s : undefined;
}

function resolveBackendConfig(): BackendConfig {
  // 鉴权 token 与环境变量 SONGZUO_SERVER_TOKEN 同名、同优先级，与 Python 端
  // backend/client.py 完全对齐 —— 两端可共用同一份 backend_config.json
  // （{"backend":"remote","url":...,"token":...}）。
  const envToken = normalizeToken(process.env.SONGZUO_SERVER_TOKEN);
  const envUrl = process.env.SONGZUO_BACKEND;
  if (envUrl) {
    return { url: envUrl, spawn: false, token: envToken };
  }
  // 配置查找：前端工程根 + 游戏本体根（前端在 game/frontend/）
  // dev: __dirname ≈ <repo>/game/frontend/out/main
  //   上二级 = 前端工程根；上四级 = 仓库根 → 再进 game/（前端与 game/ 同为二级目录）
  const candidates = [
    join(__dirname, "../../backend_config.json"),
    join(__dirname, "../../../../game/backend_config.json"),
  ];
  for (const p of candidates) {
    if (existsSync(p)) {
      try {
        const cfg = JSON.parse(readFileSync(p, "utf-8")) as Partial<BackendConfig>;
        if (cfg.url) {
          return {
            url: cfg.url,
            spawn: cfg.spawn ?? false,
            cwd: cfg.cwd,
            command: cfg.command,
            // 环境变量优先于配置文件（与 client.py 的 `env or config` 同序）
            token: envToken ?? normalizeToken(cfg.token)
          };
        }
      } catch (e) {
        console.error("[backend] 解析 backend_config.json 失败:", e);
      }
    }
  }
  return { url: DEFAULT_BACKEND, spawn: true, token: envToken };
}

// 缓存一次解析结果：保证「后端地址」与「token」出自同一次解析 —— 若两处各自解析，
// 会出现「url 命中配置文件、token 命中环境变量」这类不一致的组合。
let resolvedBackendConfig: BackendConfig | null = null;
function getBackendConfig(): BackendConfig {
  if (!resolvedBackendConfig) resolvedBackendConfig = resolveBackendConfig();
  return resolvedBackendConfig;
}

// ---------------- 后端健康检查与拉起 ----------------
let backendProc: ChildProcess | null = null;

async function checkHealth(url: string, timeoutMs = 1500): Promise<boolean> {
  return new Promise((resolve) => {
    const req = net.request(`${url}/health`);
    const timer = setTimeout(() => {
      req.abort();
      resolve(false);
    }, timeoutMs);
    req.on("response", (res) => {
      clearTimeout(timer);
      resolve(res.statusCode === 200);
    });
    req.on("error", () => {
      clearTimeout(timer);
      resolve(false);
    });
    req.end();
  });
}

async function waitForBackend(url: string, attempts = 40, intervalMs = 500): Promise<boolean> {
  for (let i = 0; i < attempts; i++) {
    if (await checkHealth(url)) return true;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return false;
}

function resolveBackendCommand(cwd: string): { command: string; args: string[] } {
  // 打包环境：优先使用内置的 server.exe（resources/backend/server.exe），零 Python 依赖
  if (app.isPackaged) {
    // 必须用 process.resourcesPath（Electron 官方 resources 根绝对路径），
    // 不能用 __dirname 推导：asar 虚拟路径下 path.join("..") 会产生错误盘符路径
    const resourcesRoot = process.resourcesPath;
    // 随包后端为 PyInstaller one-dir（game/SongZuo.spec → name='SongZuo'），
    // 可执行体名为 SongZuo.exe；旧代码只探 server.exe，与实际产物不符。
    // 两者皆探，兼容既有分发习惯。
    for (const exe of ["SongZuo.exe", "server.exe"]) {
      const bundledServer = join(resourcesRoot, "backend", exe);
      console.log(`[backend] probing bundled server: ${bundledServer}`);
      if (existsSync(bundledServer)) {
        return { command: bundledServer, args: [] };
      }
    }
    console.warn(`[backend] bundled backend not found under ${join(resourcesRoot, "backend")}`);
  }
  // 开发环境：优先工程 venv，其次 PATH 上的 python
  const venvPython = join(cwd, ".venv", "Scripts", "python.exe");
  if (existsSync(venvPython)) return { command: venvPython, args: ["-m", "backend.server"] };
  return { command: "python", args: ["-m", "backend.server"] };
}

function spawnBackend(cfg: BackendConfig): void {
  const isPackaged = app.isPackaged;
  // 打包后：server.exe 自含数据，cwd = resources 根；
  // 开发：前端在 <repo>/game/frontend，Python 本体在 <repo>/game
  //   __dirname ≈ <repo>/game/frontend/out/main → 上四级到仓库根，再进 game/
  const cwd =
    cfg.cwd ??
    (isPackaged ? process.resourcesPath : join(__dirname, "../../../../game"));
  const { command, args } = cfg.command
    ? { command: cfg.command, args: ["-m", "backend.server"] }
    : resolveBackendCommand(cwd);
  console.log(`[backend] spawn ${command} ${args.join(" ")} (cwd=${cwd})`);
  backendProc = spawn(command, args, {
    cwd,
    shell: false,
    env: { ...process.env, PYTHONIOENCODING: "utf-8" }
  });
  backendProc.stdout?.on("data", (d) => console.log(`[backend] ${String(d).trimEnd()}`));
  backendProc.stderr?.on("data", (d) => console.error(`[backend] ${String(d).trimEnd()}`));
  backendProc.on("error", (e) => {
    // spawn 失败（ENOENT 等）只降级为“后端未连接”，不允许击穿主进程
    console.error(`[backend] 启动失败: ${String(e)}`);
    backendProc = null;
  });
  backendProc.on("exit", (code) => {
    console.log(`[backend] 退出 code=${code}`);
    backendProc = null;
  });
}

async function ensureBackend(): Promise<string> {
  // 走缓存配置：后端地址与 token 必须出自同一次解析
  const cfg = getBackendConfig();
  if (await checkHealth(cfg.url)) {
    console.log(`[backend] 已就绪: ${cfg.url}`);
    return cfg.url;
  }
  if (cfg.spawn) {
    spawnBackend(cfg);
    if (await waitForBackend(cfg.url)) {
      console.log(`[backend] 拉起成功: ${cfg.url}`);
      return cfg.url;
    }
    console.warn(`[backend] 拉起超时，前端将显示连接错误: ${cfg.url}`);
  }
  return cfg.url;
}

// ---------------- 窗口 ----------------
let mainWindow: BrowserWindow | null = null;

/**
 * 安全审查 A6：外链白名单。
 * 原实现把任意 URL 直接交给 shell.openExternal，`file:` / `smb:` / 自定义协议
 * 可触达 OS 处理器（本地命令执行面）。此处仅放行 http/https。
 */
function isSafeExternalUrl(raw: string): boolean {
  try {
    const protocol = new URL(raw).protocol;
    return protocol === "http:" || protocol === "https:";
  } catch {
    return false;
  }
}

function openExternalIfSafe(raw: string): void {
  if (isSafeExternalUrl(raw)) {
    void shell.openExternal(raw);
  } else {
    console.warn(`[window] 已拦截非 http(s) 外链: ${raw}`);
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    show: false,
    backgroundColor: "#f6ecd6",
    title: "宋祚",
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false,
      // 安全审查 A6：preload 仅用 contextBridge/ipcRenderer，完全兼容沙箱，
      // 原显式关闭沙箱使 preload 持有完整 Node 权限，无必要。
      sandbox: true
    }
  });

  mainWindow.on("ready-to-show", () => mainWindow?.show());

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    openExternalIfSafe(url);
    return { action: "deny" };
  });

  // 安全审查 A6：拦截页面内跳转（否则渲染层可导航到任意来源/协议）。
  mainWindow.webContents.on("will-navigate", (event, url) => {
    const devUrl = process.env.ELECTRON_RENDERER_URL;
    if (devUrl && url.startsWith(devUrl)) return;      // 开发模式热更新
    if (url.startsWith("file://")) return;             // 本地打包页面
    event.preventDefault();
    openExternalIfSafe(url);
  });

  if (process.env.ELECTRON_RENDERER_URL) {
    mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else {
    mainWindow.loadFile(join(__dirname, "../renderer/index.html"));
  }
}

// ---------------- IPC ----------------
// 缓存后端 URL 解析结果，避免多次触发 spawn
let backendUrlPromise: Promise<string> | null = null;
function ensureBackendUrl(): Promise<string> {
  if (!backendUrlPromise) backendUrlPromise = ensureBackend();
  return backendUrlPromise;
}

ipcMain.handle("backend:get-url", async () => {
  return ensureBackendUrl();
});

// token 与 url 分开取：url 会触发后端拉起（可能耗时），token 是纯配置读取、立即返回。
ipcMain.handle("backend:get-token", () => getBackendConfig().token ?? "");

ipcMain.handle("window:minimize", () => mainWindow?.minimize());
ipcMain.handle("window:maximize", () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.handle("window:close", () => mainWindow?.close());

// ---------------- 生命周期 ----------------
app.whenReady().then(() => {
  // 去掉系统默认菜单栏（File/Edit/View…），游戏窗口只保留自绘 HUD
  Menu.setApplicationMenu(null);
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProc) {
    console.log("[backend] 关闭后端子进程");
    backendProc.kill();
    backendProc = null;
  }
});