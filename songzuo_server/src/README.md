# songzuo_server/src · Rust 后端源码

> 层归属：**开发侧并行实现**（不随发行）。

## 模块
| 文件 | 职责 |
|---|---|
| `main.rs` | 入口：读配置、起服务、把请求分派到各模块（对应 Python 侧 `/api/*`） |
| `server.rs` | HTTP 服务与路由 |
| `commands.rs` | 诏令/玩家行动的处理（对应 `game/core/commands.py`） |
| `settle.rs` | 月度结算（对应 `game/core/settlement*.py` 的主干） |
| `state.rs` | 游戏状态结构与派生量（对应 `GameState`） |
| `constants.rs` | 数值常量（**独立口径**，不要求与 Python 一致） |
| `save.rs` | 存档读写（**格式不与 Python 互通**） |

## 纪律
- 两套实现若出现**差异**，先判断"谁更符合史实/设计文档"，再统一口径；
  禁止为了"看起来一致"而在两侧复制粘贴同一份常量（那会掩盖真正的分歧）。
---
最后更新：2026-09-27（补目录文档）
