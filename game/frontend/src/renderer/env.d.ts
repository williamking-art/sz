/// <reference types="vite/client" />

// preload 暴露的全局 API
interface Window {
  songzuo?: {
    getBackendUrl: () => Promise<string>;
    minimize: () => Promise<void>;
    maximize: () => Promise<void>;
    close: () => Promise<void>;
  };
}