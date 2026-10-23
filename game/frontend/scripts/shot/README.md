# scripts/shot — 面板/HUD 截图台（dev-only）

> 独立于产品构建的截图台：`hud.html` + `panel.html` 各挂一个 React 入口，
> 用 fixture 数据渲染真实组件，由 Edge 无头截图产出 PNG。**不进产品构建。**

## 文件

| 文件 | 行 | 职责 |
|---|---:|---|
| `fixtures.ts` | 225 | 截图台 fixture（**仅 dev 用**）：一份确定的 state 与 readouts，喂给组件 |
| `shoot.mjs` | 91 | 一键脚本：build → 起静态服务 → Edge 无头截图 |
| `panel.tsx` | 112 | 面板截图台入口（**dev-only**） |
| `hud.tsx` | 61 | HUD 截图台入口（**dev-only**） |
| `storeMock.ts` | 61 | store mock：面板需要有数据的 state |
| `apiMock.ts` | 30 | api/client mock（**仅 dev 用**） |
| `hubFixture.ts` | 452 | **hub fixture（仅 dev 用）**：`GET /api/readouts::hub` 的**真实 payload**（由 `readout_hub.collect` 导出，非手写；seed=20261013 且先跑 6 个月结算）⇒ 供 `apiMock` 让 `ReadoutHubPanel` 渲染 **21 项**读数 |
| `situationsFixture.ts` | 44KB | **situations fixture（仅 dev 用）**：`/api/readouts` 的 `situations` 键**真实 payload**（来源＝`core.situations.build_situation_readout`，与 `backend/server.py:888` 同源调用；seed=20261013 且先跑 6 个月结算） |
| `planFixture.ts` | 见文件头 | **plan fixture（仅 dev 用）**：`/api/readouts` 的 `plan` 键**真实 payload**（来源＝`core.plan_readout.build_plan_readout`，与 `backend/server.py:817` 同源调用） |
| `financeFixture.ts` | 见文件头 | **finance fixture（仅 dev 用）**：`/api/readouts` 的 `finance` 键**真实 payload**（来源＝`state.finance_readout()`，`core/game_state_econ.py:362`） |
| `bench-map.mjs` | 47 | 地图首帧成本基准：`JSON.parse`(13MB topojson) + 4 次 topojson 解析 |
| `hud.html` / `panel.html` | 33 / 34 | 两个截图台入口 HTML |
| `types.ts` | 2 | |

## 运行

```powershell
$env:SHOT_PYTHON = "D:\codebuddy\.audit-venv\Scripts\python.exe"
$env:SHOT_OUT    = "D:\codebuddy\sz\_dev_tools\analysis-shots\panels"
& "D:\codebuddy\tools\nodejs\node-v24.22.1-win-x64\node.exe" scripts/shot/shoot.mjs
```

## 纪律

- **dev-only**：`mock` 与 `fixtures` 只服务截图台，不得被产品代码 import。
- **地图为何不拍舆图**：`maplibre` 需 WebGL，无头浏览器不保证 ⇒ 地图改用**数据级回归**
  （`tests/test_map_prefecture_geometry.py`），像素级验收仍须真机。


## 🔴 已知限制：**`state` 通道未接通**（M287/M291 定论，dev-only）

**决定性证据（可观测探针，M291）**：在页头探针里追加渲染 `state.statistics.total_income` 后，
截图显示：

```
store ok（state 7 键｜statistics.total_income=undefined）
```

而 `fixtures.ts` 的 `STATE` **顶层确有** `statistics`（值 `total_income = 16329544`，由真实
`state.statistics` 导出）。⇒ **面板通过 `useGameStore((s) => s.state)` 拿到的 `state`
不是 `fixtures.STATE`**（**7 键 vs 34 键**；该 7 键对象没有 `statistics`）。

**⇒ 结论（通道级）**：

| 通道 | 状态 | 说明 |
|---|---|---|
| **`readouts`**（`useGameStore(s => s.readouts)` / `getApiClient().readouts()`） | ✅ **可用** | 本会话所有**成功**的数据内容验收（`hub` 21 项 · `situations` · `plan` · `finance`）**全部走此通道** |
| **`state`**（`useGameStore(s => s.state)`） | ❌ **未接通** | 面板看到的是 7 键的空/桩对象 ⇒ **凡读 `s.state` 的块在截图里恒为空/0**（如 `GovernanceHub` 的「累计统计」「仓廪统计」、其它面板的 state 派生块） |

**影响范围**：**仅截图台（dev-only）**；**生产不受影响**（真实后端下发完整 state）。
**⇒ 使用纪律**：截图台**只应据 `readouts` 派生数据做内容验收**；凡结论涉及 `s.state` 的块，
**不得**以截图为准（须用契约用例或**在生产环境**核对）。

**可选修法（须单独一批）**：在截图台 bootstrap 里显式 `setState(STATE)`（或修 alias 使
`storeMock` 真正生效），随后**逐张复核**并把本限制条删除。
**页头探针**：`panel.tsx` 的探针已保留 `statistics.total_income` 一栏（诊断用；值为 `undefined` 即表示未接通）。


---

## 🔴 更正（M293）：上文「`state` 通道未接通」**结论有误，已撤回**

**真相**：`state` 通道**本来就是通的**；此前的「未接通」是**我自己的 fixture 注入插错层级**造成的假象 ——
`scripts/shot/fixtures.ts` 的缩进**不一致**（嵌套块的键也是 2 空格），我据此误判「已置于 `STATE` 顶层」，
实则插进了**嵌套块** ⇒ `fixtures.STATE.statistics === undefined`。

**决定性对照（同一条探针先后两次读数）**：

| 轮次 | 页头读数 | 面板「累计统计」 |
|---|---|---|
| M292（注入在嵌套块） | `store.state 7 键｜statistics=undefined｜fixtures.STATE 7 键｜statistics=undefined` | 入 **0** 贯（行） |
| **M293（移到真顶层后）** | `store.state **8 键**｜statistics=**16329544**｜fixtures.STATE **8 键**｜statistics=**16329544**` | 入 **1633 万贯（行）**· 出 **1741 万贯** |

⇒ **`readouts` 与 `state` 两条通道均可用**；「`state` 通道盲点」一条**作废**，**不得**再据此写限制。
**保留的资产**：页头探针（`fixtures.STATE` 键数与 `statistics` 值）——**下次注入 fixture 时先看它**，
可立刻发现「注入没进顶层」这类问题（**这正是本次的诊断工具**）。

**教训（新增，第 5 条自查纪律）**：**下结论前先验证「探针自身的输入」**——
本次我据「探针读不到值」断言通道死，却没先验证 `fixtures.STATE.statistics` **是否真的在顶层**。
⇒ 探针结论必须连同**其输入的前置核验**一起给出，否则会把「自己的错误」误判成「系统的缺陷」。
