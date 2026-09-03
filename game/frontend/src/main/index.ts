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
}

const DEFAULT_BACKEND = "http://127.0.0.1:8080";

function resolveBackendConfig(): BackendConfig {
  const envUrl = process.env.SONGZUO_BACKEND;
  if (envUrl) {
    return { url: envUrl, spawn: false };
  }
  // 尝试读取 backend_config.json（位于 frontend/ 或 game/ 根）
  const candidates = [
    join(__dirname, "../../backend_config.json"),
    join(__dirname, "../../../game/backend_config.json")
  ];
  for (const p of candidates) {
    if (existsSync(p)) {
      try {
        const cfg = JSON.parse(readFileSync(p, "utf-8")) as Partial<BackendConfig>;
        if (cfg.url) {
          return { url: cfg.url, spawn: cfg.spawn ?? false, cwd: cfg.cwd, command: cfg.command };
        }
      } catch (e) {
        console.error("[backend] 解析 backend_config.json 失败:", e);
      }
    }
  }
  return { url: DEFAULT_BACKEND, spawn: true };
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

function spawnBackend(cfg: BackendConfig): void {
  const cwd = cfg.cwd ?? join(__dirname, "../../../game");
  const command = cfg.command ?? "python";
  const args = ["-m", "backend.server"];
  console.log(`[backend] spawn ${command} ${args.join(" ")} (cwd=${cwd})`);
  backendProc = spawn(command, args, {
    cwd,
    shell: false,
    env: { ...process.env, PYTHONIOENCODING: "utf-8" }
  });
  backendProc.stdout?.on("data", (d) => console.log(`[backend] ${String(d).trimEnd()}`));
  backendProc.stderr?.on("data", (d) => console.error(`[backend] ${String(d).trimEnd()}`));
  backendProc.on("exit", (code) => {
    console.log(`[backend] 退出 code=${code}`);
    backendProc = null;
  });
}

async function ensureBackend(): Promise<string> {
  const cfg = resolveBackendConfig();
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
      sandbox: false
    }
  });

  mainWindow.on("ready-to-show", () => mainWindow?.show());

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
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