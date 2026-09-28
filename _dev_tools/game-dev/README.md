# game-dev · 开发工具根

> 层归属：**开发工具**（不参与打包；路径引用以**仓库根** `sz/` 为基准）。

## 子目录
| 目录 | 说明 |
|---|---|
| `tests/` | **测试套件**（126 文件 / ≈1170 用例）——日常回归主入口 |
| `analytics/` | 平衡分析工具（`balance.py`） |
| `replay/` | 回放工具（目前为占位包） |
| `scripts/` | 运维脚本（云库清理、kb 检索观察） |
| `skill/` | 本地大目录（≈1.7 GB，**已 gitignore**） |

## 关键文件
- `requirements-dev.txt` —— 测试/开发依赖清单（`tests/` 与之被放行入库）；
- `verify_ai_connect.py` / `verify_refactor.py` —— 一次性校验脚本；
- `build_exe.py`、`_split_*.py`、`SongZuo.spec` —— **历史/过时**脚本（打包已迁到 `game/SongZuo.spec`），仅作参考。

## 常用命令
```powershell
# 快路径回归（跳过 8 个长时推演用例）
cd D:\codebuddy\sz\game
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' -m pytest -p no:cacheprovider -q -m "not slow"
```
---
最后更新：2026-09-27（补目录文档）
