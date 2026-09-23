import { contextBridge, ipcRenderer } from "electron";

const api = {
  getBackendUrl: (): Promise<string> => ipcRenderer.invoke("backend:get-url"),
  // 服务端启用 SONGZUO_SERVER_TOKEN 时的 Bearer token；未配置返回空串
  getBackendToken: (): Promise<string> => ipcRenderer.invoke("backend:get-token"),
  minimize: (): Promise<void> => ipcRenderer.invoke("window:minimize"),
  maximize: (): Promise<void> => ipcRenderer.invoke("window:maximize"),
  close: (): Promise<void> => ipcRenderer.invoke("window:close")
};

contextBridge.exposeInMainWorld("songzuo", api);

export type SongzuoApi = typeof api;