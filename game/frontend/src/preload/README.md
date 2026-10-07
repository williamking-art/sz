# preload — 预加载桥

> 极薄的一层（14 行），只暴露必要的 IPC 能力。

## 🔴 纪律

- 🔴 **P1-10：token 不进渲染进程**（主进程 `webRequest` 注入 `Authorization`）。
  `preload` **不得**暴露任何读取凭据的方法。
- `contextIsolation` 保持开启，暴露面按需加，**不要图省事整体透传**。
