# AGENTS.md · game/core（模块级 scoped 指令）

> 本文件是**薄路由层**：只放本目录的范围、验证路径与禁区。
> 现行口径唯一权威 = `_dev_tools/game-docs/docs/游戏机制说明.md`（及专题文档）；
> 模块导航与「修改本目录前」清单 = [README.md](README.md)；迁移实测状态 = [foundation/README.md](foundation/README.md)。
> 全局硬约束（POP 挂载律 / 口径单点 / 缺失≠0 等）见仓库根 [AGENTS.md](../../AGENTS.md) §3，
> 对本目录同样生效；**冲突以根文件为准**。
>
> **已抽出的实现（别在本目录里找）**：回合收尾 `commands.py::finish_turn` 现为**薄代理**，
> 真实现在 [`game/application/turn_lifecycle.py`](../../application/turn_lifecycle.py)
> 与 [`game/application/memory_lifecycle.py`](../../application/memory_lifecycle.py)
> （架构方案 §5.2；回归 `test_turn_lifecycle.py`）。改回合生命周期去改应用层，
> 不要往代理里塞实现——那会让"生命周期已抽出"变成假的。

## 验证路径（最直接）

- 改动后先跑**定向回归**：仓库根 `pytest _dev_tools/game-dev/tests -q -p no:cacheprovider`
  只筛涉关文件（环境准备、清 shim、`-q` 汇总行被本机吞掉等坑见根 AGENTS.md §4/§5）。
- 全量必须**串行**跑，并用 `>file 2>&1; echo EXIT=$?` 捕获真实退出码——管道到 tail 的退出码不可信。
- 动核心模拟（经济/人口/税收/随机数/长期结算）：先说明口径 + 加定向回归（根 §3-4）。

## 禁区（高频坑在此留目，细节去 README）

- 🔴 **延迟装配/降级现场的 `except` 不得静默 `pass`**：失败必须 `logging.warning(..., exc_info=True)` 留痕。
  本目录这些边全是函数内 import（§五登记的 12 条 12/12 如此；第十九包补登的第 13 条
  `game_state_econ → core.officialdom`（`:44`）**是顶层**），就近常配 `try/except`，静默就等于
  「照常跑通、账面却少一大块」而零信号——实测 `game_state.py` 10 个处理体里 **6 个纯 `pass`、0 个记日志**，
  `save_load.py` 31 个里 11 静默 / 15 已留痕。已修：`game_state.py:1068` 隐户入 POP（POP 挂载律条 1/4）。
  配套要求：光留痕不够，要有**"结果非空/守恒成立"的哨兵断言**（同一问题在
  `pop_bridge.seat_pop_weights` 的教训：lazy import 包在 try 里返回 `[]` 也不炸，只有断言权重非空才算接通）。
  统计与逐条行号见 `_dev_tools/game-docs/specs/cross-cutting/阶段1_依赖图与循环依赖.md` §五。
- 🔴 POP 与粮的写入必须走桥（`pop_bridge`/`grain_bridge`；调 `grain_bridge` **务必传 `state`**），
  绕过桥接的直写会被路级只读守卫用例当场炸掉（根 §3-1）。
- 裸读写 `goods` 禁止——一律经 `material_holding` 单点访问层；遍历 `goods` 键会把州府桶当商品维参与算术
  （`commodity_dims` 是唯一安全判据，见 README 主链表）。
- 结算步骤顺序是玩法规则：编排唯一归 `settlement.py`，不得在业务域内另开月结算；
  新步骤放语义正确位置并核对读数与存档迁移（README §回合与状态主链）。
- `foundation/` 新迁入模块彼此用新规范路径，**新模块不得导入旧转发桩**（甲批规则 2；
  状态表与 SCC 口径见 foundation/README）。
- 禁 `git checkout -- .` / `git clean`；保留工作区他人未提交改动（根 §3-5）。

## 归属认领（多 agent）

改本目录共享文件前：云端 `state_get("tasks")` 看 `claimedBy`（非空且非己不碰），
`log_append` 一行声明再动手；协议见根 AGENTS.md §1，云端通道读空时的定性纪律见 foundation 交接记录。
