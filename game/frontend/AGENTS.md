# AGENTS.md · game/frontend（模块级 scoped 指令）

> 薄路由层。当前目录结构、命令与界面约定唯一在 [README.md](README.md)
> （§常用命令 / §地图资源 / §界面改动约定）；打包现状与环境坑见仓库根
> [AGENTS.md](../../AGENTS.md) §5。**冲突以根文件为准**。

## 验证路径

- 类型检查（**双配置**都要过）+ 单测：命令块见根 AGENTS.md §4
  （本机用便携 node：`tsc --noEmit -p tsconfig.web.json` / `-p tsconfig.node.json`、`vitest run`）。
- 舆图改动走**数据级回归**：`test_map_prefecture_geometry.py`；
  像素级验收需真机（无头浏览器不保证 maplibre 的 WebGL）。
- ⚠️ `electron-vite build` 成功 ≠ Windows 安装包构建成功（`electron/dist` 缺失，见 README §常用命令与根 §5）。

## 禁区

- React 层**不复制结算算法**——算法单点在 `core/`、后端只做薄壳，界面只渲染读数（根 §3-2）。
- 不得仅在界面端造默认值：改接口字段须对照后端序列化/API、TS 类型与组件测试（README §界面改动约定）；
  缺失值一律显式呈现「未定义」，**不得回落 0/1.0**（根 §3-3）。
- 舆图产物（`assets/map/web/*`、`public/map/*.topojson`）**不入库**；改生成器后按根 AGENTS.md §4 顺序重建，
  否则新克隆舆图空白。
- 面板/共享组件索引与主题变量约定见 README 所指各子目录 README，勿在界面代码里另建第二套状态展示口径。
