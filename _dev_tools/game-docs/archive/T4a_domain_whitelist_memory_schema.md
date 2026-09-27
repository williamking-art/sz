# T4a 领域路由字段白名单 + 记忆数据库 schema 设计

> 作者：析微澜（data-analytics）｜状态：设计稿（供 T7/T4b 落地，先不动代码）｜日期：2026-08-20
> 上游：`analysis/refactor_ai_upgrade_plan.md`（§G 领域融合、§I 一轮一库 SQLite）
> 全部字段名以 `core/game_state.py`、`core/game_state_econ.py` **实际实勘**为准（P0 可运行代码 > P1 文档）；未经验证的提示词兜底名不进入白名单。
> 权威常量：`content/data.py`（TIER_RANGE 已为 7 档且迁入 data.py，`ai/client_utils.py` 从此导入——TEAM.md 记载的"TIER_RANGE 定义于 ai/client_utils.py 属漂移"已修复，本设计以 data.py 为准）。

---

## 〇、术语与坐标系

- **路径（path）**：沿用 `engine/state_applier.py` 的点分路径语法（`treasury` / `prefectures.两浙路.mood` / `*` 通配），作为 AI changes 的唯一寻址方式。
- **领域 Agent（10）**：推演官 / 财计 / 军务 / 使节 / 按察使 / 史官 / 知制诰 / 铨选 / 起居注 / 大臣。本文给每个领域定义**稳定 ASCII id**（供 AGENT_DEFS 扩展键与 SQLite domain 列取值）与中文花名。
- **三类权限**：W=可写（该领域主责路径）/ R=只读可查（query_state 可达）/ X=全局硬禁写（任何 Agent 不可写，含 engine 派生/真值/隐藏态）。
- **单一主责原则**：每个可写路径只归一个领域主责；跨领域同路径写入由 `state_applier` 多 Agent 冲突合并 + 守恒校验兜底（已有），但设计上避免。
- **AI 只有提议权**：档位词→数值换算（`TIER_RANGE`/`tier_to_value`）与 CAP 封顶由程序执行（`_tool_dispatch`/结算），AI 不得直写数值量级；本白名单只约束 **changes 可落地的路径集合**。

---

## 一、领域字段白名单表（AGENT_DEFS 扩展）

### 1.1 领域注册表（10 领域 → AGENT_DEFS 扩展键）

| 领域 Agent | ASCII id（新增） | 聚合契约（现有 method） | 对应现有 AGENT_DEFS 键 | 记忆子图 |
|---|---|---|---|---|
| 推演官 | `economist` | economy_decide | economy | 经济史 |
| 财计 | `finance_minister` | finance_decide / treasury_decide / granary_decide | finance | 财计史 |
| 军务 | `military_minister` | military_decide / military_expand / decree_execute | military | 军务史 |
| 使节 | `envoy` | diplomacy_decide / diplomacy | diplomacy | 外交史 |
| 按察使 | `inspector` | land_local_decide / relief_decide / local_policy / land_manage / survey_settle | relief | 民政史 |
| 史官 | `historian` | era_decide / event_narrative | （新增） | 时代史 |
| 知制诰 | `drafter` | parse_decree / draft / polish / free_effect_decide / invest_decide | （新增） | 政令史 |
| 铨选 | `selector` | faction_decide / exam / emperor_personal_decide / hidden_state_decide | （新增） | 人事史 |
| 起居注 | `court_diarist` | monthly_report / advice / council_review / final_eval | narrative | 朝局史 |
| 大臣 | `minister` | dialogue（含 _tool_dispatch 8 工具通道） | （新增） | 召对史 |

> T4b 落地建议：AGENT_DEFS 每项扩展 `writable_paths` / `readonly_paths` / `memory_subgraph` 三键；旧 6 键（diplomacy/finance/military/relief/economy/narrative）按上表映射到新 id，`wake_*` 逻辑保留不动。

### 1.2 全局硬禁写清单（X · 所有领域一律不可写）

**A. 派生/只读字段**（引擎 calc_* 计算或聚合产出，AI 直写即破坏守恒/口径）：

| path | 派生来源（P0 实勘） |
|---|---|
| `money_supply` | `GameStateEconMixin.calc_price_level()` 写副作用（货币有效供给） |
| `price_level` | `calc_price_level()` 计算值 |
| `grain_price` / `prefectures.*.grain_price` | `calc_grain_price()` / `calc_region_grain_price()` 计算值 |
| `defense_lines.*.garrison` | `_derive_defense_lines()` 由 army_units 聚合派生 |
| `refugee_count` | `GameState.refugee_count` **property**（各路 refugees 求和；含 setter 摊回） |
| `army_units.*.unit_id / .name / .tier / .defense_line / .branches` | 军籍结构字段，`build_army_units` 构造，AI 只可改 troops/training/morale/station |
| `prefectures.*.name / .is_capital / .type / .households / .population / .officials / .clerks / .pops.*.size` | 户籍/结构/派生（人口分层由引擎演化） |
| `arrival_rate_base` / `difficulty*` | 难度参数（DIFFICULTY_PRESETS） |

**B. 真实层/认知层真值**（真假分层铁律）：

| path | 说明 |
|---|---|
| `economy_history` | 真实层快照环形缓冲（近 12 月），结算追加 |
| `economy_knowledge` | 认知层滞后奏报，结算从真值写入；AI 只读不写 |

**C. 隐藏态/引擎专属**：

| path | 说明 |
|---|---|
| `loyalty` / `corruption` | 后台隐藏真值（0~1），事件/制度联动，AI 只给定性（`authority_brief_for_ai`），**数值永不落 AI** |
| `statistics` / `settlement_log` / `event_history` / `dialogue_history` / `diplomacy_log` / `short_term_log` / `_prestige_history` / `era_building_log` | append-only 日志，引擎写入 |
| `game_over` / `game_result` / `victory` / `is_abdicated` / `abdication_reason` | `evaluation.check_game_over()` / 命令判定 |
| `timeline` / `pending_breaks` | 历史改写位，**玩家朱批确认**（commands.confirm_timeline_break）后落，AI 不可直改历史 |

### 1.3 分领域白名单（W / R）

> 符号：W=可写（主责）｜R=只读可查｜（注）为数据视角要点；`*` 通配沿用 state_applier 语法。`external.金` 等为真实 dict 键（`EXTERNAL_FORCES`），**不是**提示词里的 `external_jin`（getattr 兜底名，GameState 无此字段）。

#### ① 推演官 `economist`（经济史）
- **W**：`jiaozi.trust`、`coin.shortage`、`maritime.open`、`bank.established`（金融 5 字段的 4 个布尔/三态落点）、`prefectures.*.pops.士绅.窖银`
- **R**：treasury / granary / grain_price / price_level / money_supply（只读）/ population_satisfaction / factions / exam / tech / external / economy_knowledge / finance_readout() 读数
- **注**：景气/士绅/生产经结算（settlement_civilian/estate/era_mechanic）间接作用于 POP 与 era_state，**不**给推演官直写 `era_state`（归史官）；科举输出归铨选落地，推演官只读 exam。

#### ② 财计 `finance_minister`（财计史）
- **W**：`treasury`、`imperial_treasury`、`granary`（均需过 `state_applier` 守恒校验：钱组/粮组 ΣΔ==0，来源=去向）
- **R**：commerce_tax_rate / tax_breakdown / pay_system / waste_reform / payraise_budget / single_whip / standard / coin / jiaozi / maritime / bank / granary_cap
- **注**：`granary_cap` 只读（新建仓储是工程/知制诰通道）；征率/俸制/一条鞭为玩家改制权限，AI 只读。

#### ③ 军务 `military_minister`（军务史）
- **W**：`army_units.*.troops`、`army_units.*.training`、`army_units.*.morale`、`army_units.*.station`、`defense_lines.*.fortification`
- **R**：army_units 其余只读、defense_lines（garrison 只读）、external.金/辽/西夏.attitude / invasion_will、treasury（军费）、granary（军粮）、tech.gunpowder / level
- **注**：`army_units` 是列表，state_applier 的 `*` 通配需支持**列表下标**（T4b 扩展 `_path_ok`/`_resolve_path_value`）；兵额增减走 changes 时须守恒（兵 POP size 同步）。

#### ④ 使节 `envoy`（外交史）
- **W**：`external.金.attitude`、`external.辽.attitude`、`external.西夏.attitude`、`alliance_jin_liao`
- **R**：external 全键、external_regimes、treasury（岁币成本）、prestige
- **注**：岁币（sui_gong）金额由结算按 `SUI_GONG_ANNUAL` 核算，使节只给"订/毁"意图（契约布尔），无直接路径；`invasion_will` 为引擎推演，只读。

#### ⑤ 按察使 `inspector`（民政史）
- **W**：`prefectures.*.mood`、`prefectures.*.govern`、`prefectures.*.unrest`、`prefectures.*.refugees`（各路本地流民）、`prefectures.*.storage`、`prefectures.*.changping_stock`、`prefectures.*.hidden_land`、`prefectures.*.pops.农.wealth`、`prefectures.*.pops.农.grain`、`prefectures.*.pops.农.欠税`、`prefectures.*.pops.士绅.wealth`、`prefectures.*.pops.士绅.grain`、`disaster_severity`、`disaster_region`、`population_satisfaction`
- **R**：population、prefectures 其余只读、granary（发仓）、treasury（赈银）、economy_knowledge
- **注**：`refugee_count` 是派生 property，**禁直写**（见 §1.2-A）；灾级 `disaster_severity` 落地自 `relief_decide.disaster_level`（1~5，经结算放大粮价）。

#### ⑥ 史官 `historian`（时代史）
- **W**：`era_state.*`（五维 economy_center/culture/commerce/military/urban，`era_decide.era_change` 经程序定幅 ±10 迁移）
- **R**：posture 全量脱敏态势、event_history、timeline（只读）、pending_breaks（只读）
- **注**：事件触发（trigger_event/active_events/event_pressure）归 `core/events.py` 引擎，史官只叙事不触发。

#### ⑦ 知制诰 `drafter`（政令史）
- **W**：`edict_drafts`、`pending_decrees`、`pending_secret_decrees`、`longterm_public`、`longterm_secret`、`active_decrees`、`council_reviews`、`longterm_effects`（free_effect 长期制度队列）、`investments`（invest_decide 记账）、`tech.pending_inventions`（offer_blueprint 献策队列）
- **R**：treasury / granary / prestige / factions（会签参考）/ central_orgs（机构归属）
- **注**：free_effect 的 effects 白名单 `FREE_EFFECT_FIELD_WHITELIST`（content/data.py，拒绝式校验）是**程序换算通道**，知制诰只写 `longterm_effects` 队列（提议），数值落地由引擎每月结算执行——不与财计的 treasury 主责冲突。

#### ⑧ 铨选 `selector`（人事史）
- **W**：`factions.*.satisfaction`、`factions.*.influence`、`exam.open`、`exam.mode`、`exam.talent_pool`、`emperor_health`
- **R**：factions（cohesion 只读）、exam、spy_network、emperor_*（art/taoism/pleasure）、minister_estate、player_minister_status、loyalty 定性档位
- **注（数据视角风险）**：`art_mastery` 直接进七维"艺术造诣"评分（`evaluation.evaluate_game`），**放开 AI 直写 = 刷分漏洞**——现 `state_applier.VALID_PATHS` 已含 `art_mastery`，建议**降级为只读**，仅经诏令/事件通道；`emperor_health` 影响结局判定，写前 clamp 且禁止 set 大值（只能 add 小值）。

#### ⑨ 起居注 `court_diarist`（朝局史）
- **W**：无（纯叙事/记录；仅写记忆库"朝局史"子图）
- **R**：posture 全量 + economy_knowledge + event_history + statistics + dialogue_history（月报/建议/会签/终评素材）
- **注**：`monthly_report`/`final_eval` 等契约不产生 changes（若产 changes 一律拒绝）。

#### ⑩ 大臣 `minister`（召对史）
- **W**：无直接 GameState 写（召对经 `_tool_dispatch` 8 工具通道，程序执行）
- **R**：minister_memory（本人）、loyalty 定性档位、persona
- **注（数据视角质量债）**：`_tool_dispatch.relief_grant`（`ai/client_utils.py`）**直写派生 property** `state.refugee_count = max(0, ... - grain*5000)`（setter 摊回各路）——违反 §1.2 派生保护，应改为对各路 `prefectures.*.refugees` 按比例减，或走按察使 changes 通道。

### 1.4 与既有白名单的关系（对齐表）

| 现有来源 | 内容 | 本设计关系 |
|---|---|---|
| `engine/state_applier.VALID_PATHS`（16 条） | treasury/imperial_treasury/granary/prestige/population_satisfaction/art_mastery/era_state./prefectures.*.{mood,govern,unrest,grain,storage}/pops.*.wealth/grain/factions.*.{satisfaction,influence} | 保留为**全局可写超集**，本文按领域收窄为子集；`art_mastery` 建议从超集移除（刷分风险）；`prefectures.*.grain` 建议移入引擎专属（田亩产出由结算写） |
| `content.data.FREE_EFFECT_FIELD_WHITELIST` | prestige/treasury/population_satisfaction/faction_change/external_jin.../defense_bonus/tech/art_mastery/army/finance/talent | effect-key 风格 → 经 `_apply_free_effect` 换算落路径；**key 名 ≠ GameState 字段**，T4b 需建"effect-key → 真实路径"映射表 |
| `core/agent_router.AGENT_DEFS[*].domain_fields` | 现有 6 键的 domain_fields（external_jin/sui_gong/defense_bonus 等） | 同上是 effect-key 风格，非真实路径；本文给出真实路径版，落地时替换 |

---

## 二、记忆数据库 schema（SQLite · 一轮一库 `saves/slot_{slot}.db`）

> 范围：entities / relations / summaries / change_log 四表（T4a 交付）；`state` 表（世界状态快照）归 T7 沈舶司定稿，本设计仅给 linkage 约定。
> 衔接：`memory/memory_graph.py` 改 SQLite 后端，**接口保留**（add_entity/add_relation/upsert_relation/query/keyword_search/summarize/record_decision/record_event/save/load/archive + 新增 compress/summarize_period）；旧 JSON 记忆文件 `saves/slot_{slot}_memory*.json` 迁移或重建。
> 权威常量：`MEMORY_RELATION_DECAY` / `MEMORY_ARCHIVE_WEIGHT`（content/data.py）**以查询参数注入，不落库复制**（防双源漂移）。

### 2.1 通用约定

- **schema_version**：`meta` 表存（当前 JSON 版 `_SCHEMA_VERSION=1` → SQLite 版 `2`），损坏时从主存档重放重建（不阻断游戏，保留现有 load 语义）。
- **id 命名**：延续现有 eid 前缀（`minister_蔡京` / `faction_新党` / `org_枢密院` / `external_金` / `decision_{turn}_{title}` / `event_{eid}` / `tool_{name}_{tname}` / `summary_{domain}_{end_turn}`）。
- **去重（INSERT OR REPLACE）**：entities 唯一键 `(type, name)`；relations 唯一键 `(src, dst, rtype)`——同向关系叠加权重（cap 10.0），stance/promises 覆盖更新。
- **衰减（不落库）**：`w_eff = weight × exp(-λ × Δturn)`，λ = `MEMORY_RELATION_DECAY[rtype]`（缺省 0.02）；SQLite 内置 `exp()`，查询时 λ 以参数注入。
- **归档（不物理删除）**：`relations.archived` 标志位（0 活跃 / 1 归档），`w_eff < MEMORY_ARCHIVE_WEIGHT` 时置 1；查询默认 `archived=0`。
- **压缩/周期总结（不动旧数据）**：每 6 回合 SQL 聚合近 6 回合 → `summaries`（etype=`summary`）；每 12 回合 → `summaries`（etype=`period_summary`，含七维评分快照）；**不删改 relations**。
- **层级检索**：先命中 `summaries`（概要）→ 按 `ref_entities` 细节查 `relations`。
- **领域索引**：`domain` 列取值 = §1.1 的 10 个 ASCII id + `global`（开局基线/跨领域史实）+ `system`（引擎/玩家记录）。

### 2.2 DDL（建议稿）

```sql
-- meta：schema 版本 / 当前回合 / 槽位 / 游戏标识
CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,          -- schema_version / turn / slot / game_id
  value TEXT NOT NULL
);

-- entities：记忆实体（7 类）
CREATE TABLE IF NOT EXISTS entities (
  id         TEXT PRIMARY KEY,             -- eid：minister_蔡京 / decision_12_崇宁新法 ...
  type       TEXT NOT NULL,                -- minister|event|decision|task|org|institution|external_power
  name       TEXT NOT NULL,
  attrs      TEXT NOT NULL DEFAULT '{}',   -- JSON（{faction: ...} / {effects: ...}）
  turn       INTEGER NOT NULL DEFAULT 0,   -- 创建回合（时间窗锚点）
  weight     REAL  NOT NULL DEFAULT 1.0,   -- 基础权重（同 eid 重建可覆盖）
  domain     TEXT  NOT NULL DEFAULT 'global',  -- 领域索引（10 领域 / global / system）
  created_at TEXT  NOT NULL DEFAULT '',    -- _now_str() 兼容字段
  UNIQUE (type, name)                      -- 去重：INSERT OR REPLACE
);
CREATE INDEX IF NOT EXISTS idx_entities_type   ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_domain ON entities(domain, turn);   -- 领域×时间窗
CREATE INDEX IF NOT EXISTS idx_entities_turn   ON entities(turn);           -- 时间窗

-- relations：记忆关系（8 类）
CREATE TABLE IF NOT EXISTS relations (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  src        TEXT NOT NULL REFERENCES entities(id),
  dst        TEXT NOT NULL REFERENCES entities(id),
  rtype      TEXT NOT NULL,                -- supports|opposes|involves|produces|progresses|promises|stance|governs
  weight     REAL  NOT NULL DEFAULT 1.0,   -- 基础权重（同向叠加 cap 10.0）
  turn       INTEGER NOT NULL DEFAULT 0,   -- 最近更新回合（时间窗锚点）
  note       TEXT  NOT NULL DEFAULT '',
  domain     TEXT  NOT NULL DEFAULT 'global',  -- 领域索引
  archived   INTEGER NOT NULL DEFAULT 0,   -- 0 活跃 / 1 已归档（不物理删除）
  created_at TEXT  NOT NULL DEFAULT '',
  UNIQUE (src, dst, rtype)                 -- 去重：INSERT OR REPLACE
);
CREATE INDEX IF NOT EXISTS idx_relations_src          ON relations(src);
CREATE INDEX IF NOT EXISTS idx_relations_dst          ON relations(dst);
CREATE INDEX IF NOT EXISTS idx_relations_rtype        ON relations(rtype);
CREATE INDEX IF NOT EXISTS idx_relations_domain_turn  ON relations(domain, turn); -- 领域×时间窗
CREATE INDEX IF NOT EXISTS idx_relations_turn         ON relations(turn);
CREATE INDEX IF NOT EXISTS idx_relations_archived     ON relations(archived);

-- summaries：压缩概要 + 周期总结
CREATE TABLE IF NOT EXISTS summaries (
  id          TEXT PRIMARY KEY,           -- summary_{domain}_{end_turn}
  etype       TEXT NOT NULL,              -- summary（6 回合压缩）| period_summary（12 回合周期总结）
  domain      TEXT NOT NULL,              -- 领域索引
  start_turn  INTEGER NOT NULL,
  end_turn    INTEGER NOT NULL,
  content     TEXT  NOT NULL,             -- 紧凑中文概要（脱敏：只含实体名/档位词/事件，复用 summarize()）
  weight      REAL  NOT NULL DEFAULT 1.0,
  ref_entities TEXT NOT NULL DEFAULT '[]',-- JSON：覆盖实体 id 列表（层级检索：概要→细节）
  created_at  TEXT  NOT NULL DEFAULT '',
  UNIQUE (etype, domain, end_turn)
);
CREATE INDEX IF NOT EXISTS idx_summaries_domain ON summaries(domain, start_turn, end_turn); -- 领域×时间窗
CREATE INDEX IF NOT EXISTS idx_summaries_etype   ON summaries(etype, end_turn);

-- change_log：变更日志（append-only，守恒审计锚点）
CREATE TABLE IF NOT EXISTS change_log (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  turn         INTEGER NOT NULL,          -- 回合（时间窗索引）
  source_agent TEXT NOT NULL,             -- 10 领域 id / engine / player / system / merge / cascade
  domain       TEXT NOT NULL,             -- 领域索引（=source_agent 的领域，便于按领域检索）
  path         TEXT NOT NULL,             -- GameState 路径（与 state_applier 同语法）
  op           TEXT NOT NULL,             -- set|add|mul|remove|push
  old_value    TEXT NOT NULL DEFAULT 'null', -- JSON（old/new 供守恒审计与回放）
  new_value    TEXT NOT NULL DEFAULT 'null',
  reason       TEXT NOT NULL DEFAULT '',  -- 因果说明（强制，与 validate_changes 对齐）
  created_at   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_changelog_turn        ON change_log(turn);
CREATE INDEX IF NOT EXISTS idx_changelog_agent       ON change_log(source_agent);
CREATE INDEX IF NOT EXISTS idx_changelog_domain_turn ON change_log(domain, turn); -- 领域×时间窗
```

### 2.3 关键查询（供 T7 落地参考）

```sql
-- 领域子图检索（BFS 1-2 跳 → 先取领域内活跃关系，w_eff 排序；λ 参数注入）
SELECT r.src, r.dst, r.rtype,
       r.weight * exp(-:lambda * MAX(0, :cur_turn - r.turn)) AS w_eff, r.note
FROM relations r
WHERE r.archived = 0
  AND (r.domain = :domain OR r.domain = 'global')
  AND (:time_window = 0 OR :cur_turn - r.turn <= :time_window)
  AND (r.src IN (SELECT id FROM entities WHERE type IN (:seed_types))
       OR r.dst IN (SELECT id FROM entities WHERE type IN (:seed_types)))
ORDER BY w_eff DESC LIMIT :top_k;

-- 6 回合压缩 → summary（不动旧数据）
INSERT OR REPLACE INTO summaries (id, etype, domain, start_turn, end_turn, content, ref_entities)
SELECT 'summary_' || :domain || '_' || MAX(turn), 'summary', :domain,
       MIN(turn), MAX(turn),
       summarize(domain 内 turn > :cur_turn - 6 的关系),
       json_group_array(DISTINCT src || dst)   -- 聚合覆盖的实体（示意）
FROM relations WHERE domain = :domain AND turn > :cur_turn - 6 AND archived = 0;

-- 12 回合周期总结 → period_summary（可附七维评分：evaluate_game(state) 快照入 attrs/content）
```

---

## 三、领域记忆子图映射（每领域 Agent → 检索条件）

> 检索语义对齐现有 `memory_graph.query(seed, rtypes, time_window, top_k)`；**seed 用实体类型前缀（type ∈ ENTITY_TYPES）而非单实体**，即"领域锚点类"，配合 domain 列过滤出该领域时间线。`_agent_inject`（ai/client.py）注入用 `max_chars` 预算截断（现有 100 字）。

| 领域 Agent（id） | 记忆子图 | seed 锚点（type 前缀） | rtypes（优先） | 时间窗（回合） | top_k | 注入用途 |
|---|---|---|---|---|---|---|
| 推演官 `economist` | 经济史 | `decision`（effects 含 treasury/grain 键）、`institution`（户部/三司） | produces, progresses, involves | 12 | 6 | economy_decide 推演参考（景气/粮价/士绅动向） |
| 财计 `finance_minister` | 财计史 | `org`（户部/三司）、`decision`（effects.treasury） | produces, governs, promises | 12 | 6 | finance/treasury/granary_decide 度支参考 |
| 军务 `military_minister` | 军务史 | `org`（枢密院/兵部）、`external_power`（金/辽/西夏）、`event`（战事） | involves, produces, opposes | 12 | 6 | military_decide 军情参考 |
| 使节 `envoy` | 外交史 | `external_power`（全部 31 政权） | stance, promises, produces | 24 | 6 | diplomacy_decide 邦交参考 |
| 按察使 `inspector` | 民政史 | `event`（灾/赈/流民）、`decision`（赈济） | involves, produces | 12 | 6 | relief/land_local_decide 民情参考 |
| 史官 `historian` | 时代史 | `event`（史实/战略事件）、`decision` | involves, produces, governs | 24 | 8 | era_decide 时代注记（六合窗口放宽） |
| 知制诰 `drafter` | 政令史 | `decision`（全部诏令）、`tool_*`、`task` | produces, promises, supports, opposes | 12 | 6 | parse_decree/draft 拟旨参考 |
| 铨选 `selector` | 人事史 | `minister`（在朝大臣）、`org` | supports, opposes, stance, governs | 12 | 8 | faction_decide / 任免参考 |
| 起居注 `court_diarist` | 朝局史 | `decision`、`minister`、`event` | involves, stance, supports, opposes | 12 | 8 | monthly_report / advice / final_eval 素材 |
| 大臣 `minister` | 召对史 | `minister_{当前召对大臣}`（**单实体 seed**） | promises, stance, supports, opposes, involves | 24 | 6 | dialogue 召对注入（个性/前史，persona 独立保障） |

**跨领域最小关联**：领域子图 = `domain ∈ {本领域, global}` 的活跃关系；`global` 承载开局基线（minister/faction/org/external 实体 + 邦交 stance）与史实硬锚事件，任何领域都可见；跨领域细节按需（相关 diff 摘要）二级查询，不进首屏预算。

---

## 四、数据视角发现的质量债（供 T7/T4b 及主理人裁决）

1. **`_tool_dispatch.relief_grant` 直写派生 property**（`ai/client_utils.py:509`）：`state.refugee_count = max(0, ...)` 触发 setter 摊回各路——违反 §1.2 派生保护。建议改为对各路 `prefectures.*.refugees` 按比例扣减（守恒），或改走按察使 changes 通道。
2. **`art_mastery` 刷分风险**：直接进七维"艺术造诣"（`evaluation.py:53`），现 `state_applier.VALID_PATHS` 已放开。建议移出全局可写超集，仅经诏令/事件/工程通道。
3. **effect-key ≠ 真实路径**：现有 `AGENT_DEFS.domain_fields` 与 `FREE_EFFECT_FIELD_WHITELIST` 用 `external_jin` / `sui_gong` / `defense_bonus` / `army` 等键，GameState 无对应存储字段（`transport` / `cultivated_land` / `wasteland` 亦为提示词 getattr 兜底名）。T4b 需建"effect-key → 真实路径"单一映射表，并同步 `VALID_PATHS`。
4. **`army_units` 列表通配缺口**：`state_applier._path_ok`/`_resolve_path_value` 仅支持 dict 命名键；军务 W 清单依赖列表下标 `*`，T4b 须扩展。
5. **金融 5 字段缺白名单**：`jiaozi.trust` / `coin.shortage` / `maritime.open` / `bank.established` 现不在 `VALID_PATHS`，推演官 changes 落地前须补入。
6. **记忆 JSON → SQLite 迁移**：`saves/slot_{slot}_memory.json`（+ `_archive`）需一次性迁移或重建；schema_version 升 2；衰减/归档 λ 与阈值仍以 `content/data.py` 为单一权威源。

---

## 五、来源标注

- P0 代码实勘：`core/game_state.py`、`core/game_state_econ.py`、`core/agent_router.py`、`engine/state_applier.py`、`memory/memory_graph.py`、`ai/client.py`、`ai/client_utils.py`、`content/data.py`、`core/evaluation.py`、`core/commands.py`、`tests/test_memory_graph.py`、`analysis/refactor_ai_upgrade_plan.md`
- P1 团队权威：`TEAM.md`（三层边界 / 单一权威源 / 真假分层 / 12 步结算）
- 未验证项：`state` 表最终 DDL（归 T7）、effect-key→路径映射表逐条取值（T4b 建表时以 `_apply_free_effect`/`_generate_decree_effects` 实际换算核对）
