# components · 共享 UI 组件

> **层归属**：`game/frontend/src/renderer/` 的**可复用装饰组件层**。
> 面板（`../panels/`）**优先复用这里**，不要各自写裸卡片。

## 文件

| 文件 | 内容 |
|---|---|
| [`PanelKit.tsx`](PanelKit.tsx) | 宋式装饰组件库（UI 升级 2026-09-29）：把 `theme.css` 的 `sz-panel` / `sz-card` / 描金 / 朱印系统封装成组件，消除「裸 `rounded-lg border`」卡片的简陋感 |

## PanelKit 导出（7 个）

| 组件 | 用途 |
|---|---|
| `PanelShell` | 面板外壳：宣纸底 ＋ 双线描金 ＋ 题头饰带（`title` / `subtitle` / `actions` / `children`） |
| `SectionHead` | 章节标题：描金分隔线 ＋ 楷体小标（`text` / `hint` / `tone`） |
| `StatCard` | 数值卡：单指标展示 |
| `GoldDivider` | 描金分隔线 |
| `SceneCard` | 场景/事件卡 |
| `Badge` | 徽标（小标签） |
| `Seal` | 朱印 |

## 约定

- **Tailwind 类名走 `theme.css` 的 `sz-*` 语义类**，不在组件里写死颜色；
- 新增组件先问"能不能用 `PanelKit` 已有导出表达"，避免同义组件重复出现；
- 组件**只管呈现**，不含业务计算——数值一律取后端 `readouts`（口径单点，前端不重算）。