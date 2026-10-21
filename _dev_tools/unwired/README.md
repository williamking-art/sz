# `_dev_tools/unwired/` —— 未接线的参考实现（**不随游戏分发**）

2026-09-27 按用户口径「② 移出」从 `game/` 移到这里：这些模块**有测试、但无生产调用方**，
留在 `game/` 会让它们随 PyInstaller 进分发物、并造成"有测试＝有保护"的错觉。

| 文件 | 原位置 | 状态与原因 |
|---|---|---|
| `contract_adapter.py` | `game/ai/contract_adapter.py` | 34 契约 → `{changes, narrative}` 统一视图；**待接线**（审计 C-10 AST 核实 0 调用） |
| `async_ai.py` | `game/core/async_ai.py` | AI 异步化；**未接线**——其线程纪律以**已移除的 Tkinter `ui.after`** 为前提；现非阻塞由 FastAPI 线程池 + 前端 HTTP 异步承担 |
| `disaster_tier.py` | —（本目录新增） | 灾害档位参考实现；**未进 games 生产路径**，由测试直接 import。⚠️ 先前 README 漏登记，2026-10-21 补 |

**保留在 `game/ai/client_utils.py` 的 `STATE_TOOL_SCHEMAS`**（未一并移出）：实测
`_tool_dispatch` / `_TOOL_SCHEMAS`（八工具）**是生产路径**（`ai/contracts_court.py:93`、`ai/client.py:440`），
只有那份"3 通用工具"的预留 schema 未接线，且与生产函数同处一文件 —— 移出会改动生产代码，得不偿失；
现以注释标注"预留、未接生产"。

**测试**：`_dev_tools/game-dev/tests/test_contract_adapter.py`、`test_async_ai.py`
（含"未接线哨兵"）、`test_improvements.py`、`test_parallel_settlement.py`、`test_review_p0_conservation.py`
已改为从本目录导入（各自插入 `_UNWIRED` sys.path）。

**若要接线**：把文件移回 `game/` 对应目录 → 从 `agent_router`/`settlement` 侧接线 →
修 `parse_tool_calls → _tool_dispatch` 形状不兼容（审计 C-10）→ 重新加回 `SongZuo.spec` 的 hiddenimports。
