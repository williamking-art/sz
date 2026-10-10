# `_dev_tools/game-dev/tests/` · Python 回归

这是 `game/pytest.ini` 配置的 Python 测试目录。测试文件覆盖核心规则、账本守恒、API、存档、地图和 AI 契约；用例数量会持续变化，本 README 不固定数量或最近一次运行结果。

## 运行

从仓库根目录：

```powershell
$py = "..\.audit-venv\Scripts\python.exe"
$env:PYTHONPATH = ""
$env:CODEBUDDY_SAFE_DELETE_ENABLED = "0"
& $py -m pytest _dev_tools/game-dev/tests -p no:cacheprovider
```

跳过标记为长时推演的用例：

```powershell
& $py -m pytest _dev_tools/game-dev/tests -p no:cacheprovider -m "not slow"
```

仅运行长时用例：

```powershell
& $py -m pytest _dev_tools/game-dev/tests -p no:cacheprovider -m slow
```

解释器路径是此工作区配置示例；换机后替换为可用 Python。仓库根和 `game/` 各有 pytest 配置，若从其他目录启动，先确认实际选中的配置及标记注册。完整环境和复跑要求见 [`../../game-docs/docs/开发服务器与回归测试说明.md`](../../game-docs/docs/开发服务器与回归测试说明.md)。

## 目录约定

- `conftest.py`：共享夹具、源码包扫描入口和测试辅助。
- `fake_ai_backend.py`：离线测试使用的假 AI 后端。
- `test_*.py`：Python 测试。前端 Vitest 用例位于 `game/frontend/`，不在本目录统计。
- 新增测试时覆盖真实调用链或状态转换；只测试未被生产调用的纯函数，不能证明功能已接线。
- `test_route_pops_readonly_guard.py` 覆盖精选结算子步、真实 15 月月结、玩家扩编命令、一条鞭折银欠税、家产循环、士绅囤粮/市舶窖银（含出窖）、AI 城市化/就业流及组合压力结算；守卫应零直写、逐字段镜像一致，另核对 POP 财富/粮食与 `M_ALL` 守恒。
- `test_econ_price_review.py` 覆盖路线价本地性（别路隐户不传染、本地隐户能影响本地价）及同一初局、仅改 AI 城市化档位的 12 月对照，用于证明经济选择能产生可测的 POP 结构差异。
- 经济与人口回归应分别检查账本守恒、需求/供给和长局民生指标；残差为零不能代替平衡验收。
- test_military_summary.py 覆盖省级军政派生：兵额守恒、只读、逐路筛选，以及**单军月饷/月粮**（region_brief.unit_cost_readout）与 calc_army_cash / calc_army_grain 的逐分不分叉。

按专题查找审查整改、圣旨闭环或市场用例时，以当前文件名和相应 `specs/*/tasks.md` 为准；批次文件会增删，不在此重复维护静态清单。
