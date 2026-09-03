# 前端面板迁移 · 数据契约与规范（React 版）

> 本文档是 Tkinter → React 面板迁移的**唯一权威数据契约**。所有面板组件以此为准。

## 1. 架构原则

- **后端零业务逻辑复制**：React 面板只消费 HTTP。数据源有三：
  1. `state` 快照（`/api/load`、`/api/advance`、`/api/action` 返回的 `state` 字段，存于 `useGameStore((s) => s.state)`）
  2. `/api/readouts`（只读派生读数：军队/武库/财政/仓廪计算，`client.readouts()`）
  3. `constants.json`（静态常量：`import ... from "../data/constants.json"`）
- **写操作**一律走 `getApiClient().action(actionName, params)`，成功后 `setState(res.state)` 刷新。
- 可用 action 名见 `api/client.ts::ActionName`（issue_decree / do_personal_action / choose_imperial_action / start_tech_research / approve_invention / reject_invention 等）。**参数契约以 Tk 面板源码调用为准**。

## 2. 前端约定（必读文件）

迁移前先读：
- `frontend/src/renderer/store/gameStore.tsx` — store、`pick()`、HUD 派生
- `frontend/src/renderer/panels/DecreePanel.tsx` — **风格范本**（卡片/按钮/表单/提交模式）
- `frontend/src/renderer/panels/OverlayStack.tsx` — 面板挂载方式
- `frontend/src/renderer/utils/format.ts` — 格式化工具（humanizeCoin 等）

样式用 Tailwind 语义类：`bg-card`、`bg-paper/60`、`border-gold/40`、`text-ink`、`text-ink-light`、`text-dim`、`text-red`、`font-kai`。卡片：`rounded-lg border border-gold/40 bg-paper/60 p-3`。主按钮：`rounded-lg bg-red px-6 py-2 font-kai tracking-widest text-paper hover:bg-red-dark`。次按钮：`bg-paper/60 text-ink hover:bg-gold-light`。图标用 `lucide-react`。

**禁止**：子代理不得修改 `OverlayStack.tsx`、`gameStore.tsx`、`client.ts`、HUD 文件——只新建自己的面板文件。挂载由主代理统一完成。

## 3. state 快照字段（实测，1101 年开局）

顶层键（节选，`pick(state, key, fallback)` 取值）：

```
year, month, turn, era_name, emperor_name, emperor_health, emperor_alive,
prestige, population, population_satisfaction, treasury, imperial_treasury,
granary, granary_cap, grain_price, canal_block, coin, price_level,
pay_system, single_whip, commerce_tax_rate, waste_reform, money_supply,
wine_tax, statistics, tax_breakdown, granary_stats, economy_history,
jiaozi, maritime, exam, bank, standard, land, era_state, legacies,
factions, yamen, prefectures, external_regimes, external, central_orgs,
defense_lines, tech, projects, workshops, resources,
longterm_public, longterm_secret, short_term_log, settlement_log,
event_history, active_events, dialogue_history, opening_gazette,
imperial_action, pending_imperial_trip, imperial_micro_count,
personal_action, major_policy, major_policy_target,
edict_drafts, pending_decrees, active_decrees, council_reviews,
spy_network, loyalty, corruption, minister_estate,
game_over, game_result, victory, focus_tree, timeline
```

关键字段形状：

```jsonc
// factions["新党"]
{ "influence": 90, "satisfaction": 85, "cohesion": 70, "leader": "蔡京", "net_support": 0, "decree_stance": 0, "last_decree_comment": "" }
// 派系名列表：新党/旧党/宦官集团/西军集团/东南士人/清流言官/宫禁（constants.json::faction_names）

// yamen["吏部"]  （六部：吏户礼兵刑工）
{ "duty": "铨选官吏、考核黜陟", "faction": "旧党", "efficiency": 60, "backlog": 0, "acts": ["整饬吏治","裁汰冗员","兴办科举"] }

// prefectures["两浙路"]
{ "name": "两浙", "households": 2482482, "land": 52000000, "self_farm_land": …, "gentry_land": …,
  "official_land": …, "imperial_land": …, "grain": …, "mood": 66, "govern": 68, "population": …,
  "unrest": 8, "monthly_tax": 780000, "hidden_land": …, "storage": …, "changping_stock": …,
  "grain_yield": …, "yields": { "salt": …, "tea": …, "silk": …, … },
  "officials": 3351, "clerks": 26808, "route_mult": 1, "local_finance": …, "local_treasury": …,
  "pops": { "农": { "size": …, "wealth": …, "grain": …, "goods": {…}, "欠税": 0, "窖银": 0 },
            "士绅": {…}, "工匠": {…}, "商人": {…}, "官僚": {…}, "兵": {…} },
  "buildings": {}, "pay_ratio": …, "gap": …, "grain_price": …, "type": …, "is_capital": …,
  "refugees": …, "orgs": …, "controlled_by": …, "public_support": …, "gentry_resistance": …,
  "city_defense": …, "fiscal": … }

// tech
{ "level": 50, "gunpowder": 20, "hydraulics": 40, "calendar": 60, "iron": 20, "masters": 3,
  "era": 0, "west": 0, "unlocked": ["M0_plow", …], "researching": {}, "assets": {},
  "pending_inventions": [], "dynamic_capabilities": {}, "milestones": {}, "generated_nodes": {},
  "projects": {}, "signoffs": {} }

// central_orgs["尚书省"]（键：中书省/门下省/尚书省/六部/枢密院/三衙/御史台/谏院/翰林学士院/内侍省/开封府）
{ "lead": "韩忠彦", "belong": "皇帝", "scope": "总领六部/奉行", "authority": [...], "matter_keys": [...],
  "posts": [{ "title": "尚书左仆射" }, …], "holders": { "尚书左仆射": "韩忠彦", … },
  "comissions": [], "abolished": false, "efficiency": 1, "backlog": 0, "branches": {}, "budget_in": 0, "budget_out": 0, "net": 0 }

// external_regimes["辽"]（31 政权） / external（辽/金/西夏 三国精简）
{ "name": "辽", "type": "游牧帝国", "power": 75, "attitude": 50, "internal_pressure": 20, … }
// external["金"] 额外有 invasion_will

// defense_lines
{ "北线_太原真定": { "fortification": 60, "garrison": 130000 }, … }

// workshops（键如 "酒坊_东京开封府_0"）
{ "name": "酒坊", "recipe": { "grain_feed": 50000 }, "output_dim": "wine", "yield": 30, "active": true }

// loyalty / corruption / minister_estate（键为人名）
loyalty: { "蔡京": 0.85, … }   corruption: { "蔡京": 0.78, … }
minister_estate: { "蔡京": { "wealth": 30000, "land": 800 }, … }

// spy_network（键为派系名）
{ "新党": 0, …, "宫禁": 0.5 }

// legacies（键：new_party_dominance/redundant_officials/hidden_land/liao_xia_border/huashigang_grievance）
{ "key": …, "name": "新党专权", "desc": …, "clear_desc": …, "active": true, "progress": 0, "cleared": false }

// opening_gazette
{ "header": "大宋邸报", "era": "建中靖国元年", "body": "…", "tasks": [ { "key": …, "title": "户部亏空", "desc": …, "goto": "decree", "urgent": true }, … ] }

// economy 杂项
wine_tax: 600000（数）
coin: { "shortage": 0.3, "private_melt": 0.1 }
jiaozi: { "issued": 0, "trust": 60, "reserve": 2000000, "term": 36, "cycle": 0, "age": 0, "redeemed_total": 0 }
maritime: { "open": false, "tariff": 0.1, "silver_in": 30 }
exam: { "open": true, "mode": "词学", "talent_pool": 50, "schools": 30 }
bank: { "established": false, "capital": 0 }
statistics: { "total_income": 0, "total_expenditure": 0, "total_decrees": 0, "total_wars": 0, "total_disasters": 0 }
granary_stats: { "canal_in": 0, "military": 0, "converted": 0, "relief": 0, "tax": 0, "sparrow": 0, "canal_loss": 0, "official": 0 }
tax_breakdown: { "commerce": 0, "poll": 0 }
land: { "cultivated": 460000000, "households": 20000000, "hidden_households": 5000000, "hidden_rate": 0.35, "wasteland": 80000000, "yield": 1 }
era_state: { "economy_center": 50, "culture": 50, "commerce": 50, "military": 50, "urban": 50 }
```

## 4. /api/readouts（`client.readouts()`，GET）

```jsonc
{
  "army": [ { "unit_id": …, "name": …, "tier": …, "branches": {…}, "troops": …, "station": …,
             "defense_line": …, "morale": …, "training": …, "equip_rate": 0.55,
             "army_name": …, "org_arm": …, "scale": …, "serial": … } ],   // 35 支
  "arsenal": { … },                    // 中央武库库存（键为兵器名）
  "finance": { …25 字段… },            // finance_readout() 全量
  "granary": { "monthly": …, "army": …, "official": …, "clerk": …, "capacity_used": … },
  "defense_lines": { "北线_太原真定": { "fortification": 60, "garrison": 130000 }, … }
}
```

## 5. constants.json（`frontend/src/renderer/data/constants.json`）

```jsonc
{
  "faction_names": ["新党", …],
  "faction_init": { "新党": { "influence": 90, … } },
  "yamen_list": ["吏部", …],
  "yamen_info": { "吏部": { "duty": …, "faction": …, "acts": [...] } },
  "prefecture_list": ["两浙路", …],
  "tech_lines": ["机械动力", "能源与材料", "化学化工", "信息通讯", "生命医学", "观念与制度"],
  "tech_nodes": [ { "id": "M0_plow", "line": "机械动力", "era": 0, "name": "牛耕挽犁",
                    "desc": "铁犁牛耕，九州之基", "prereq": [], "cost": { "silver": 0, "months": 0, "masters": 0 },
                    "effect": { "yield_bonus": 0.05 } }, … ],
  "building_std": { "水利": …, "常平仓": …, "官营作坊": …, "官署": …, "军营": …, "学校": … },
  "building_blueprints": { "M2_spindle": …, … },   // 10 张蓝图
  "imperial_locations": ["宫里", "京城", "出京"],
  "imperial_modes": ["公开", "微服"],
  "imperial_matrix": {
    "宫里": { "公开": { "临朝": { "label": …, "desc": …, "base_cost": …, "fund": "treasury", "risk": "低",
                            "era_gate": null, "prep": 0, "distance": false, "micro_once": false,
                            "base_effects": {…} }, "书画翰墨": …, "崇道修醮": …, "宴游享乐": … },
              "微服": {} },
    "京城": { "公开": { "幸艮岳": …, "延福宫宴游": …, "上清宝箓宫": … },
              "微服": { "微行市井": …, "微行大臣府第": … } },
    "出京": { "公开": { "巡幸东南": …, "东幸镇江": … }, "微服": { "微服他地": … } }
  }
}
```

## 6. 面板 → Tk 源码映射

| PanelKind | Tk 源码 | 说明 |
|---|---|---|
| court 朝堂 | `game/ui/panels_core.py::_panel_overview` (L743) | 总览 |
| ministers 群臣 | `game/ui/panels_govern.py::_panel_yamen` (L1498) | 六部衙门 |
| gazette 朝报 | `game/ui/panels_govern.py::_panel_daily_log` (L1629) | 日志 |
| personal 行止 | `game/ui/panels_economy.py::_panel_personal` (L195) | 帝王行动矩阵 |
| prefecture 州县 | `panels_economy.py::_panel_prefectures` (L90) + `_panel_prefecture` (L121) | 列表+详情 |
| granary 仓廪 | `panels_economy.py::_panel_granary` (L1304) | |
| accounting 会计 | `panels_economy.py::_panel_accounting` (L1214) | |
| military 军政 | `panels_economy.py::_panel_military_affairs` (L644) + `_panel_detail` (L727) | |
| tech 科技 | `panels_economy.py::_panel_tech` (L771) | |
| engineering 工程 | `panels_economy.py::_panel_engineering` (L1146) | |
| settings 设置 | `game/ui/panels_meta.py::_panel_settings` (L82) | |
| save 存档 | `panels_meta.py::_panel_save_load` (L22) | |
| conclude 终局 | `game/ui/panels_menu.py::_panel_game_over` (L223) | |
| todo 在办 | `panels_govern.py::_panel_todo` (L1583) | |

## 7. 迁移守则

1. **视觉对齐 Tk 版**：布局结构、字段、文案尽量 1:1；Tk 的 Canvas 绘制（仪表条等）用 CSS/Tailwind 等价实现。
2. **数据取自快照/readouts/constants**，不得硬编码游戏数值（开局数值会随难度变）。
3. **交互动作**：找到 Tk 面板里调用的后端方法名（`self.app.do_xxx` / `self.state.xxx` / `commands.xxx`），映射为 `client.action(...)` 的 action 名与参数。若 action 不在 `ActionName` 列表中，说明后端 `/api/action` 未暴露——此时面板做成**只读展示**，并在组件顶部注释标注「待后端暴露 action」。
4. 组件导出 `export default function XxxPanel()`，无 props 或 `{ props }`。
5. 中文文案保持古意风格，与 Tk 版一致。
