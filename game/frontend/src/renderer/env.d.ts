/// <reference types="vite/client" />

// preload 暴露的全局 API
interface Window {
  songzuo?: {
    getBackendUrl: () => Promise<string>;
    /** 服务端启用 SONGZUO_SERVER_TOKEN 时的 Bearer token；未配置返回空串。 */
    getBackendToken: () => Promise<string>;
    minimize: () => Promise<void>;
    maximize: () => Promise<void>;
    close: () => Promise<void>;
  };
}