# songzuo_server · Rust 并行后端（MVP）

> 层归属：**开发侧并行实现**（不随发行）。用于与 Python 本体做**独立第二实现**的对照与平价校验。

## 定位（务必看清）
- 这是**简化版 MVP**：数值口径与 Python 本体（`game/`）**不必一致**，**存档字段亦不互通**；
- 它的价值是"用另一套语言/结构复算关键链路"，发现 Python 侧的隐性假设；
- 完整实现与唯一权威仍是 `game/backend/server.py` + `game/core/`。

## 关键内容
| 文件 | 说明 |
|---|---|
| `Cargo.toml` / `Cargo.lock` | crate 定义与锁定 |
| `src/` | 源码（见 `src/README.md`） |
| `Dockerfile` / `.dockerignore` / `cloudbaserc.json` | 云端构建（CloudBase）相关 |
| `target/` | Rust 构建缓存（**≈1.1 GB**，已 gitignore；可 `cargo build` 重建） |

## 常用命令
```powershell
cd D:\codebuddy\sz\songzuo_server
& "$env:USERPROFILE\.cargo\bin\cargo.exe" test --offline     # 当前 8 个用例通过
```
---
最后更新：2026-09-27（补目录文档）
