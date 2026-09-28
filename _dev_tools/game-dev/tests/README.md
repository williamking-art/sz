# tests · 测试套件（回归主入口）

> 层归属：**开发工具**。**唯一**的 Python 测试目录（`pytest.ini` 的 `testpaths` 指向此处）。
> 规模：126 个 `test_*.py`，≈1170 个用例；另有前端 57 个 vitest 用例在 `game/frontend`。

## 怎么跑
```powershell
# ① 全量（约 57–72 s）
cd D:\codebuddy\sz\game
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' -m pytest -p no:cacheprovider -q

# ② 快路径（跳过 8 个长时推演用例，约 27–33 s）
... -m "not slow"

# ③ 只跑长时用例
... -m slow
```
> ⚠️ 工作目录必须是 `sz\game`（在仓库根跑会误收集 `_scratch/*.py`）。
> ⚠️ `pytest.ini` 的 `addopts = -q` 与命令行 `-q` 叠加成 `-qq` 会**吞掉摘要行**，取摘要加 `-o addopts=`。

## 关键文件
| 文件 | 说明 |
|---|---|
| `conftest.py` | 公共夹具 + `SRC_PACKAGES` / `iter_src_files()` / `src_roots()`（静态守卫统一按**源码包**扫描） |
| `fake_ai_backend.py` | 假 AI 后端：离线跑通需要 AI 的链路（不联网） |

## 测试类型（不止"跑通"）
- **守恒/恒等式**：ΣPOP、钱粮双向守恒、单位口径；
- **静态守卫**：单一真值源（`test_pop_class_single_source`）、唯一写者（`test_faction_flows`）、
  文档目录与实际符号一致（`test_doc_index_parity`）、未接线模块不得复活（`test_uncovered_modules`）；
- **回归**：`test_regression_2026_08.py`（36 月回放）、`test_review_*.py`（历次审查修复固化）；
- **分层标记**：长时推演用例标 `@pytest.mark.slow`。
---
最后更新：2026-09-27（补目录文档）
