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
| `bench-map.mjs` | 47 | 地图首帧成本基准：`JSON.parse`(13MB topojson) + 4 次 topojson 解析 |
| `hud.html` / `panel.html` | 33 / 34 | 两个截图台入口 HTML |
| `types.ts` | 2 | |

## 运行

```powershell
$env:SHOT_PYTHON = "D:\codebuddy\.audit-venv\Scripts\python.exe"
$env:SHOT_OUT    = "D:\codebuddy\sz\_dev_tools\analysis-shots\panels"
& "D:\codebuddy\tools\nodejs\node-v20.19.5-win-x64\node.exe" scripts/shot/shoot.mjs
```

## 纪律

- **dev-only**：`mock` 与 `fixtures` 只服务截图台，不得被产品代码 import。
- **地图为何不拍舆图**：`maplibre` 需 WebGL，无头浏览器不保证 ⇒ 地图改用**数据级回归**
  （`tests/test_map_prefecture_geometry.py`），像素级验收仍须真机。
