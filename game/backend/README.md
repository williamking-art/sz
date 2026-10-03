# `game/backend/` —— 后端抽象与参考实现

> 上级规范：[`game/README.md`](../README.md) ｜ 测试：[`test_readouts_endpoint.py`](../../_dev_tools/game-dev/tests/test_readouts_endpoint.py)、[`test_slot_guard.py`](../../_dev_tools/game-dev/tests/test_slot_guard.py)

## 职责

前端（Electron/React）与内核之间的**接口层**。同一套接口有两个实现方向：
本地直连（进程内）与 HTTP 后端（可选、可外置）。

| 文件 | 职责 |
|---|---|
| `client.py` | **后端客户端抽象层**：`new_game` / `advance` / `action` / `resolve_event` 等模板方法，子类实现传输 |
| `server.py` | **Python 参考后端**（FastAPI + Uvicorn，**可选**）：`new_game`/`advance`/`readouts`/存档槽位/设置面板/AI 配置等 HTTP 端点 |
| `__init__.py` | 包说明（AI 服务抽象层） |

## 关键约定

1. **快照必须脱敏**：`server.py` 下发前会把真值转档位词；新增字段时确认
   「这个数该不该给前端真值」（例如 `estate`/`estate_hoard` 子池已在 `_state_to_dict` 中剥离）。
2. **AI 配置走服务端**：`ai_config.json` 由服务端读取并构建客户端（路径单点在
   `ai/client_utils._ai_config_path()`，即 `~/Documents/宋祚/ai_config.json`，与存档同根；
   `server.py::_ai_config_path()` 必须委托它，不得再 `join(_app_root(), ...)`）；**key 绝不回传前端**，
   也不向客户端指定的任意地址发送（连接前二次校验）。
3. **存档槽位**：槽位合法性由 `test_slot_guard.py` 守着；改槽位规则要同步该测试。
4. FastAPI/Uvicorn 是**可选依赖**（`.audit-venv` 有 fastapi 但无 httpx）→ 端点测试用
   "直接调函数 + 伪造 Request"，不要写 `TestClient`。
5. 前端实际走哪条链路由 `start.bat` / Electron 主进程决定；`server.py` 不是唯一入口（进程内直连同样可用）。
6. **端点只做薄壳**：任何计算在 `core/`；派生失败要**显式记入 `readout_errors`**
   （如 `/api/readouts` 的 `plan` 字段派生失败会追加 `"plan"`），**不得静默返回空**——
   前端无法区分"没有工程"与"读数坏了"。
