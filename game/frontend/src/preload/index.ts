import { contextBridge, ipcRenderer } from "electron";

const api = {
  getBackendUrl: (): Promise<string> => ipcRenderer.invoke("backend:get-url"),
  // P1-10：token 不进渲染进程（主进程 webRequest 注入 Authorization）。
  // 此处刻意不暴露 getBackendToken。
  minimize: (): Promise<void> => ipcRenderer.invoke("window:minimize"),
  maximize: (): Promise<void> => ipcRenderer.invoke("window:maximize"),
  close: (): Promise<void> => ipcRenderer.invoke("window:close")
};

contextBridge.exposeInMainWorld("songzuo", api);

export type SongzuoApi = typeof api;