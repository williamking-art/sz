# renderer/audio — 音频

> 前端音频引擎与偏好设置。

## 文件（3 个）

| 文件 | 行 | 职责 |
|---|---:|---|
| `engine.ts` | 186 | 音频引擎（**singleton**） |
| `settings.ts` | 47 | 音频偏好持久化 |
| `useGameBgm.ts` | 18 | 根据是否处于游戏内**自动切换 BGM** |

## 纪律

- `engine.ts` 是 singleton，**不要在组件里 new**；统一走导出的单例。
- BGM 跟随游戏内状态切换，判定只写在 `useGameBgm.ts` 一处。
- `__tests__/` 有 2 个用例（engine / useGameBgm），改这两个文件必须跑。
