import { contextBridge, ipcRenderer } from "electron";

const api = {
  getBackendUrl: (): Promise<string> => ipcRenderer.invoke("backend:get-url"),
  minimize: (): Promise<void> => ipcRenderer.invoke("window:minimize"),
  maximize: (): Promise<void> => ipcRenderer.invoke("window:maximize"),
  close: (): Promise<void> => ipcRenderer.invoke("window:close")
};

contextBridge.exposeInMainWorld("songzuo", api);

export type SongzuoApi = typeof api;