/// <reference types="vite/client" />

// preload 暴露的全局 API
interface Window {
  songzuo?: {
    getBackendUrl: () => Promise<string>;
    // P1-10：getBackendToken 已移除——token 由主进程注入，不进渲染层
    minimize: () => Promise<void>;
    maximize: () => Promise<void>;
    close: () => Promise<void>;
  };
}