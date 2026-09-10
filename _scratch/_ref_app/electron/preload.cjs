contextBridge, ipcRenderer } = require("electron");

// 前端全局异常兜底。不在这里劫持 console：Chromium 的 console-message 由主进程
// 直接捕获，可以保留源文件和行号；这里补齐 console 看不到的 Promise、资源和 CSP 错误。
const sendRendererDiagnostic = (kind, details) => {
  try {
    ipcRenderer.send("client:error", {
      kind,
      pageUrl: window.location.href,
      readyState: document.readyState,
      ...details,
    });
  } catch {
    // 主进程已退出或 structured clone 失败时不再抛第二个错误。
  }
};

const errorDetails = (value) => {
  if (value instanceof Error) {
    return {
      name: value.name,
      message: value.message,
      stack: value.stack,
      cause:
        value.cause === undefined
          ? undefined
          : value.cause instanceof Error
            ? value.cause.stack || value.cause.message
            : String(value.cause),
    };
  }
  if (typeof value === "string") return { message: value };
  try {
    return { message: JSON.stringify(value) ?? String(value) };
  } catch {
    return { message: String(value) };
  }
};

window.addEventListener(
  "error",
  (event) => {
    if (event instanceof ErrorEvent || event.error || event.message) {
      const serialized = errorDetails(event.error || event.message);
      sendRendererDiagnostic("window.error", {
        ...serialized,
        message: event.message || serialized.message || "Unknown renderer error",
        filename: event.filename,
        line: event.lineno,
        column: event.colno,
      });
      return;
    }

    // <script>/<link>/<img>/<audio>/<video> 等资源加载失败不会冒泡成 ErrorEvent。
    const target = event.target;
    if (!target || target === window) return;
    let url = "";
    try {
      url =
        target.currentSrc ||
        target.src ||
        target.href ||
        target.getAttribute?.("src") ||
        target.getAttribute?.("href") ||
        "";
    } catch {
      // 元素可能已卸载。
    }
    sendRendererDiagnostic("resource", {
      tagName: target.tagName || target.nodeName || "unknown",
      id: target.id || "",
      url,
      documentUrl: window.location.href,
    });
  },
  true,
);

window.addEventListener("unhandledrejection", (event) => {
  sendRendererDiagnostic("unhandledrejection", errorDetails(event.reason));
});

window.addEventListener("securitypolicyviolation", (event) => {
  sendRendererDiagnostic("csp", {
    effectiveDirective: event.effectiveDirective,
    violatedDirective: event.violatedDirective,
    blockedURI: event.blockedURI,
    sourceFile: event.sourceFile,
    line: event.lineNumber,
    column: event.columnNumber,
  });
});

window.addEventListener("messageerror", (event) => {
  sendRendererDiagnostic("messageerror", {
    origin: event.origin,
    message: "Renderer could not deserialize a posted message",
  });
});

// 窗口控制（全屏等）。纯 web/浏览器跑时不存在 → 前端据 window.app 是否存在隐藏相关开关。
contextBridge.exposeInMainWorld("app", {
  isFullscreen: () => ipcRenderer.invoke("app:isFullscreen"),
  setFullscreen: (value) => ipcRenderer.invoke("app:setFullscreen", value),
  // 平台标识：darwin/win32/linux。前端据此分流充值授权方式（mac=web、win=overlay），
  // 比 navigator.userAgent 判断可靠（主进程 process.platform 权威）。
  platform: process.platform,
  // 渲染层手动日志 / React 错误转发到 electron.log。
  clientLog: (msg) => ipcRenderer.send("client:log", msg),
});

// Windows 上 Electron 偶发：窗口看着是激活的，但 WebContents/document 没真正拿到焦点 →
// 点 input/textarea 不聚焦、打不出字，要 alt-tab 切一下才好。主进程的 focus 事件在「直接点
// input」这条路径上常不触发（焦点本就没离开过窗口外）。所以在渲染层兜底：每次鼠标按下那一刻，
// 若 document 未聚焦，主动 window.focus() 并把焦点打到被点中的可输入元素上——每次点都重新获取。
window.addEventListener(
  "mousedown",
  (event) => {
    if (document.hasFocus()) return;
    window.focus();
    const target = event.target;
    if (
      target &&
      typeof target.focus === "function" &&
      (target.matches?.("input, textarea, select, [contenteditable], [tabindex]") ||
        target.isContentEditable)
    ) {
      // 放到下一帧，等 window.focus() 生效后再聚焦元素，避免被浏览器默认行为覆盖。
      requestAnimationFrame(() => {
        try {
          target.focus();
        } catch {
          /* 元素可能已卸载，忽略 */
        }
      });
    }
  },
  true, // capture：在 React 等框架的事件处理前先把焦点补上
);

// 启动引导：splash.html 轮询后端启动进度。返回
// {phase, port, url, elapsedMs, timeoutMs, error, logPath}。phase: spawning/waiting/steam/ready/error。
contextBridge.exposeInMainWorld("bootstrap", {
  getStatus: () => ipcRenderer.invoke("bootstrap:getStatus"),
  copyDiagnostics: () => ipcRenderer.invoke("bootstrap:copyDiagnostics"),
});

contextBridge.exposeInMainWorld("steam", {
  getStatus: () => ipcRenderer.invoke("steam:getStatus"),
  getAuthTicket: (identity) => ipcRenderer.invoke("steam:getAuthTicket", identity),
  cancelAuthTicket: (ticketId) => ipcRenderer.invoke("steam:cancelAuthTicket", ticketId),
  authenticateWithServer: (options) => ipcRenderer.invoke("steam:authenticateWithServer", options),
  addStatInt: (name, delta) => ipcRenderer.invoke("steam:addStatInt", name, delta),
  setStatInt: (name, value) => ipcRenderer.invoke("steam:setStatInt", name, value),
  flushStats: () => ipcRenderer.invoke("steam:flushStats"),
  // 充值：订阅 Steam 微交易授权回调。回调 payload = {appId, orderId, authorized}。
  // 返回退订函数。Steam 未初始化时回调永不触发（充值入口自然不可用）。
  onMicroTxnAuthorizationResponse: (handler) => {
    const listener = (_event, payload) => handler(payload);
    ipcRenderer.on("steam:microtxnAuthorizationResponse", listener);
    return () => ipcRenderer.removeListener("steam:microtxnAuthorizationResponse", listener);
  },
  // 充值（web 授权，mac 用）：开内嵌子窗加载 steamurl，玩家授权完关窗后 resolve。
  openTopupWindow: (steamurl) => ipcRenderer.invoke("steam:openTopupWindow", steamurl),
});
<!DOCTYP