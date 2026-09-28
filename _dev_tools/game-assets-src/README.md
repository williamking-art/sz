# game-assets-src · 资产管线源目录

> 层归属：**开发工具**（一次性资产管线的源脚本 + 源图；2026-09-26 从 `game/content/` 迁出，
> 依据分层纪律「开发脚本不驻运行时目录」，同时避免随 PyInstaller 进分发版）。

## 子目录
| 目录 | 说明 |
|---|---|
| `ministers-layers/` | 大臣立绘**分层合成**管线的源脚本与源图（见其自带 `PORTRAIT_PIPELINE.md`） |

## 关联
- 运行期消费方：`game/core/minister_profile.py::compose_portrait`（经后端 `/api/portrait/<file>` 提供）；
- 打包必须带的是 `game/content/ministers/layers/`（合成输入），**不是**本目录。
---
最后更新：2026-09-27（补目录文档）
