# G · 内容数据与文档一致性审查

> 审查对象：《宋祚 Songzuo》内容数据层（`game/content/`）单一权威源 + 文档↔代码一致性
> 审查方式：**只读**。真读源码按行定位；自撰 3 个对拍脚本自动抽取代码常量与文档数字做 diff；跑现有 `check_docs_constants.py` 与 `validate_geo()`。
> 工具环境：`D:\codebuddy\.audit-venv\Scripts\python.exe`（Py3.13），`PYTHONPATH=''`，cwd=`D:\codebuddy\sz\game`。
> 审查日期：2026 年（本报告内数字均以审查当时 HEAD 为准；工作区**非 git 仓库**，无法给出 commit）。
> 说明：任务书给的行数与实测不符（`data.py` 实为 **2149** 行而非 1637；`ministers/data.py` 实为 **685** 行而非 619；`geo_admin.py` 1284 行）。全部定位以实测行号为准。

---

## 结论速览

| 编号 | 严重度 | 一句话 | 文件:行 | 证据类型 |
|---|---|---|---|---|
| G-1 | P0 | Rust 平行后端 7 项财政常量已与 Python 权威源漂移，其中酒课 6×、折色率 2.5× | `songzuo_server/src/constants.rs:30,41,43,45,48,35,36,216` | [确认] 实跑对拍 |
| G-2 | P0 | `check_docs_constants.py` 无法按自身文档方式运行（sys.path 指错目录），且只覆盖 12 个常量、当前退出码 1 | `analysis/check_docs_constants.py:15,22-41,115-119` | [确认] 实跑复现 |
| G-3 | P1 | 常支文档写 55 万贯/月，代码 `MONTHLY_EXP_CIVIL_BASE=880000`（已知遗留，**仍未修**） | `docs/游戏机制说明.md:184,467` ↔ `content/data.py:165` | [确认] 脚本对拍 |
| G-4 | P1 | 盐榷利单价文档 0.045，代码 0.055 | `游戏机制说明.md:178,472` ↔ `data.py:197` | [确认] |
| G-5 | P1 | 酒课保底文档 10 万贯/月，代码 60 万贯/月（6×） | `游戏机制说明.md:179` ↔ `data.py:204` | [确认] |
| G-6 | P1 | 破产两档线文档仍写「国库 < −500万 / −2000万」，代码为**正的累计亏空深度**，且文档所述分支已不可达 | `游戏机制说明.md:61,440,476` ↔ `data.py:369-370`,`core/evaluation.py:51-61` | [确认] |
| G-7 | P1 | 史实事件文档 9 个 / 随机事件 5 个，实际 14 个 / 10 个 | `游戏机制说明.md:302,317` ↔ `core/events.py:9-278,283-375` | [确认] 脚本计数 |
| G-8 | P1 | 外部政权文档「31 个」，`EXTERNAL_REGIMES` 实为 41 个（非辽/夏/金者 38） | `游戏机制说明.md:224` ↔ `data.py:1249-1296` | [确认] |
| G-9 | P1 | §八 档位换算文档仍写 5 档 `大=1.8`，代码已是 7 档 `大=1.5/巨=2.0/极=2.5` | `游戏机制说明.md:359` ↔ `data.py:1361-1369` | [确认] |
| G-10 | P1 | §八 效果键白名单文档写 17 键，`TIER_VALUE_BASE` 实为 18 键 | `游戏机制说明.md:360` ↔ `data.py:1417-1436` | [确认] |
| G-11 | P1 | §九 财政分档与 `evaluate_game` 判据不一致（代码用亏空深度，且无「>0」独立档） | `游戏机制说明.md:430` ↔ `core/evaluation.py:48-61` | [确认] |
| G-12 | P1 | 工商征率文档「可调 0.05~0.30 / 默认 5%」，代码上限 0.40、默认 0.06 | `游戏机制说明.md:148,175` ↔ `data.py:340-341,337` | [确认] |
| G-13 | P1 | 商品月折旧文档 3%，代码 ×0.95 = 5%/月 | `游戏机制说明.md:163` ↔ `core/settlement_steps.py:1693-1696` | [确认] |
| G-14 | P1 | 铜钱私熔文档 20%，代码 `private_melt=0.10` | `游戏机制说明.md:246` ↔ `data.py:1509` | [确认] |
| G-15 | P1 | 同一权威文件内两个全局田亩锚不一致：`LAND_INFO.cultivated` 4.6 亿 ↔ Σ20 路 `land` 4.68 亿 | `data.py:1474` ↔ `data.py:992-1093` | [确认] 脚本求和 |
| G-16 | P1 | `TECH_EFFECT_LABELS` 缺 4 个真实效果键；且 `trade_income` 在字典字面量中**重复定义**被静默覆盖 | `data.py:847,860`,`data.py:831-871` | [确认] |
| G-17 | P1 | 46 个 `data.py` 模块级常量全库零引用（含 `PAY_GRANARY_BASE`/`MILITARY_GRAIN_MONTHLY`/`CASH_CROP_LAND` 等），其中 14 个「本应是权威源」 | `data.py` 多处 | [确认] 脚本扫描 |
| G-18 | P1 | ACTS 事务清单常量族（科举/科技/金融/改革/外交/军事）在 data.py 全死，真实清单硬编码在 `ai/prompts/*.md` 文本里（双源） | `data.py:1853,1881,1883,2051,2057,2063,1550` ↔ `ai/prompts/{exam,military_expand,finance}.md` | [确认] |
| G-19 | P1 | `EXTERNAL_FORCES`/`EXTERNAL_PROVINCES` 有「金」，`EXTERNAL_REGIMES` **没有**「金」→ `external_view` 对金返回 `{}`；且该模块无生产调用方 | `data.py:396-400,1122,1249` ↔ `core/external_view.py:18-20,41-43` | [确认] |
| G-20 | P2 | 常平仓托市线文档 0.6，代码 0.9 | `游戏机制说明.md:199` ↔ `data.py:1788` | [确认] |
| G-21 | P2 | 文档仍描述已取消的「狼来了」机制；`wolf_count` 只减不增、`WOLF_THRESHOLD`/`S_DIRECT_PENALTY` 死常量 | `游戏机制说明.md:91,101` ↔ `data.py:109,138`,`core/commands_decree.py:170` | [确认] |
| G-22 | P2 | 圣旨执行率 9 常量 + 到账率 5 常量（共 14）全死，`core` 侧硬编码同值影子副本（当前值同、改一处即漂移） | `data.py:132-150` ↔ `core/game_state.py:872-888`,`core/game_state_econ.py:312-318` | [确认] |
| G-23 | P2 | `SECRET_DECREE_MAX=3`/`DIRECT_DECREE_MAX=2` 死常量，消费侧硬编码 `>= 3` / `>= 2` | `data.py:106-108` ↔ `core/commands_decree.py:151,308,366` | [确认] |
| G-24 | P2 | `FIREARM_TIERS` 死常量，`army_models` 另行硬编码同一组 20/40/65/85 门槛 | `data.py:528-533` ↔ `core/army_models.py:290-299` | [确认] |
| G-25 | P2 | `FINANCE_DESC` 死常量，`desensitize_trust/shortage` 在**同一文件内**硬编码同样文案（文件内双写） | `data.py:1838-1841` ↔ `data.py:2100-2110` | [确认] |
| G-26 | P2 | 官数系数 `0.00135` 在 3 处重复；`CLERK_PER_OFFICIAL=8` 未复用而硬编码 `* 8` | `core/game_state.py:71,491,492` ↔ `data.py:187` | [确认] |
| G-27 | P2 | 存档读档硬编码影子默认值 0.45 / 85 / 25 / 30（权威源为 `ARRIVAL_BASE`/`EMPEROR_*_START`） | `core/save_load.py:274-276,280` ↔ `data.py:145,95-99` | [确认] |
| G-28 | P2 | 私熔兜底 `coin.get("private_melt", 0.2)` 已与权威值 0.10 漂移（一旦缺键即回退错值） | `core/game_state_econ.py:116` ↔ `data.py:1509` | [确认] |
| G-29 | P2 | 七档词表缺档：`DOWRY_BASE`/`TRADE_INCOME`/`_DIPLO_ATT` 缺「无/巨」（战争还缺微/极）→ 消费侧 `.get` 静默降级 | `data.py:1818-1829` ↔ `core/diplomacy_treaty.py:46,79` | [确认] |
| G-30 | P2 | `EVAL_OUTCOMES` 末档「身死国灭」在 `_get_outcome_desc` 无对应键 → 结局描述返回空串 | `data.py:617-623` ↔ `core/evaluation.py:105-113` | [确认] |
| G-31 | P2 | §九「武功」算法文档写 `(防线 garrison 均值−50)×0.3`，代码先按 20 万归一化再计分 | `游戏机制说明.md:428` ↔ `core/evaluation.py:37-42` | [确认] |
| G-32 | P2 | 5 个 A6 史实事件类别「制度/西线军事/财政」不在 `EVENT_CATEGORIES`，成为孤立标签 | `core/events.py:170,195,229,256` ↔ `data.py:552-556` | [确认] |
| G-33 | P2 | 同一史实（宋江起义）两处年份不一致：压力闸 `year>=1111` vs 事件窗口 `(1119,1121)` | `core/settlement_steps.py:2439` ↔ `core/events.py:41` | [确认] |
| G-34 | P2 | 治所「颍昌府」同时挂在京畿路与京西路 | `content/geo_admin.py:44,54` | [确认] |
| G-35 | P2 | `SONG_SEAT_WEIGHTS["台湾府"]` 悬空（不在任何路 members），与「已划归福建路」的注释矛盾 | `demography.py:52` ↔ `geo_admin.py:349,581` | [确认] |
| G-36 | P2 | `AUTHORITY_MATTERS` ↔ `CENTRAL_ORG_INFO.matter_keys` 双向不匹配：12 个 matter_key 无 owner 登记、`赋税` 无任何机构引用 | `ministers/data.py:269-403` | [确认] |
| G-37 | P2 | 现成自检 `validate_geo()` 返回 0 问题，却漏检重复治所与悬空权重键（自检覆盖不足） | `geo_admin.py:1096` | [确认] 实跑 |
| G-38 | P2 | §八 文档「角色 prompt 35+ 个」，实际 23 个（README 亦写 23，两文档互斥） | `游戏机制说明.md:339` ↔ `game/README.md:76` | [确认] |
| G-39 | P2 | `data.py:176` 注释称「太仓月入 = Σ grain_yield/12 × 本色率」，实际代码用 `/3.0`（三运期） | `data.py:176` ↔ `core/game_state_econ.py:346-357` | [确认] |
| G-40 | P2 | `codex_text` 注释仍写「A14 九人简介」而实为 8 条；`CODEX_TECH_OVERVIEW` 写「循三时代递进」而 `TECH_ERAS` 有 7 个 | `codex_text.py:52,108` ↔ `codex_data.py:86` | [确认] |
| G-41 | P2 | 同一商品「布/绸」两套价表口径冲突：`MATERIAL_PRICE_BASE` 120/800 钱 vs `GOODS_PRICE` 1/3 贯 | `data.py:219-225` ↔ `data.py:1768` | [疑似] |
| G-42 | P3 | 文档 §四「投资…六领域基准」，`INVEST_BASE` 实为 7 领域 | `游戏机制说明.md:168` ↔ `data.py:1633-1641` | [确认] |
| G-43 | P3 | §一 称「11 步流水线」，`settlement.py` 实有 23 个 Step（3.5.5/6.9/6.10/10.5 未列） | `游戏机制说明.md:38` ↔ `core/settlement.py:339-438` | [确认] |
| G-44 | P3 | `population_satisfaction` 初值 55 未进权威源（硬编码在 state）；`POP_TYPES`/`PRESTIGE_MAX` 等 46 常量同属死数据 | `core/game_state.py:403` ↔ `data.py` | [确认] |
| G-45 | P3 | 历史遗留「7 人 trait_ids 考据补齐」**仍未做**（36/43 有 trait_ids） | `ministers/data.py` 赵挺之/童贯/赵桓/唐恪/聂昌/何执中/岳飞 | [确认] |
| G-46 | P3 | 岁币口径遗留：`SUI_GONG_ANNUAL=30万贯/年` 全折贯，未按史实拆「银 10 万两 + 绢 20 万匹」 | `data.py:1813`,`core/settlement_steps.py:2918` | [确认] |
| G-47 | P3 | `asset_context` 第五套档位表 `{无:0,微:0.08,小:0.15,中:0.25,大:0.40}`，与 `TIER_RANGE` 并存 | `core/asset_context.py:247-248` | [确认] |

**统计：P0 × 2，P1 × 17，P2 × 22，P3 × 6，合计 47 条。**
**漂移表条数**：A 区（主文档↔代码）31 行 = **19 项不一致** + 12 项核验一致；B 区（历史分析文档↔代码）11 行 = 5 项不一致 + 1 项半一致 + 1 项已修复 + 4 项其它；C 区（Python↔Rust）12 行 = **8 项不一致** + 4 项其它。合计**确认漂移 24 项**（含 8 项 Rust 侧）。
**重复定义表条数**：18 项（D-1 ~ D-18），其中**已实际漂移** 6 项（D-8 私熔兜底、D-11 商品价、D-12 田亩锚、D-15 事件类别、D-17 宋江年份、D-18 金政权），其余 12 项为「值暂同但双源」的潜在漂移。

---

## 文档-代码常量漂移表

> 「文档值」取自 `_dev_tools/game-docs/docs/游戏机制说明.md`（主文档）与 `_dev_tools/game-docs/analysis/*.md`（历史分析）；「代码值」取自 `game/content/data.py` 等现行源。

### A. 主文档《游戏机制说明.md》↔ 代码

| 项 | 文档值(位置) | 代码值(文件:行) | 是否一致 | 影响 |
|---|---|---|---|---|
| 朝廷常支 | 55 万贯/月（:184 正文、:467 速查表） | `MONTHLY_EXP_CIVIL_BASE = 880_000`（`data.py:165`） | ❌ 1.6× | 玩家按文档估收支会全面低估支出 |
| 盐榷利单价 | 0.045 贯/斤（:178、:472） | `SALT_PROFIT_PER_JIN = 0.055`（`data.py:197`） | ❌ 1.22× | 盐课预算 4.4 万贯/月误差 |
| 酒课保底 | 10 万贯/月（:179） | `WINE_COIN_BASE = 600_000`（`data.py:204`） | ❌ 6× | 内帑收入量级完全失真 |
| 破产危机线 / 崩坏线 | −500 万 / −2000 万贯（:61、:440、:476） | `TREASURY_CRISIS_LINE = 5_000_000` / `TREASURY_COLLAPSE_LINE = 20_000_000`（正数＝累计亏空深度，`data.py:369-370`） | ❌ 符号+判据双重过时 | 文档描述的分支自 R2-7 起已不可达 |
| 工商征率可调范围 | 0.05 ~ 0.30（:148） | `MIN=0.05` / `MAX=0.40`（`data.py:340-341`） | ❌ 上限差 0.10 | 上限档政策无法按文档预期评估 |
| 工商征率默认 | 5%（:175） | `COMMERCE_TAX_RATE_DEFAULT = 0.06`（`data.py:337`） | ❌ | 开局岁入估算偏差 ~20% |
| 常平仓籴粮托市线 | < 0.6（:199） | `CHANGPING_LOW = 0.9`（`data.py:1788`） | ❌ | 托市触发点描述错误 |
| 铜钱私熔扣减 | 20%（:246） | `COIN_INFO["private_melt"] = 0.10`（`data.py:1509`） | ❌ 2× | 货币供给口径失真 |
| AI 档位换算 | 5 档 `0 / 0.25 / 0.5 / 1.0 / 1.8`（:359） | 7 档 `TIER_RANGE`（大 1.5 / 巨 2.0 / 极 2.5，`data.py:1361-1369`） | ❌ | 文档失去对 AI 量级的约束力 |
| 效果键白名单 | 「17 键」（:360） | `TIER_VALUE_BASE` 18 键（`data.py:1417-1436`） | ❌ | 少列 `art_mastery` |
| 财政评价分档 | 「>1000万=90、>500万=70、>0=50、>-200万=30、否则10」（:430） | `deficit>TREASURY_COLLAPSE→10 / deficit>CRISIS→30 / treasury>1000万→90 / >500万→70 / else→50`（`core/evaluation.py:48-61`） | ❌ | 30/10 档判据完全不同，文档未提 `deficit_depth()` |
| 武功评分·防线项 | `(garrison 均值 − 50) × 0.3`（:428） | 先 `100×avg_def/200_000` 归一再 `(pct−50)×0.3`（`core/evaluation.py:37-42`） | ❌ | 量纲说明错误 |
| 史实事件数 | 9 个（:302）+ 表列 9 行 | `HISTORICAL_EVENTS` 14 个（`core/events.py:9-278`） | ❌ | 漏 5 个 A6 事件 |
| 随机事件数 | 5 个（:317） | `RANDOM_EVENTS` 10 个（`core/events.py:283-375`） | ❌ | 漏 5 个 |
| 花石纲年份窗口 | 1102–1120（:305） | `(1105, 1120)`（`core/events.py:13`） | ❌ | 文档未同步 A15 时代门槛 |
| 外部政权数 | 「金/辽/西夏 + 31 个」（:224） | `EXTERNAL_REGIMES` 41 个（非辽/夏者 38，且**不含金**）（`data.py:1249-1296`） | ❌ | 名册规模错 7 个 |
| 商品月折旧 | 3%（:163） | ×0.95 = 5%/月（`core/settlement_steps.py:1696`） | ❌ | 商品周转/物价推演失真 |
| 角色 prompt 数 | 「35+ 个」（:339） | `ai/prompts/*.md` 23 个 | ❌ | 与 README:76「23 个」自相矛盾 |
| 投资领域数 | 「六领域基准」（:168） | `INVEST_BASE` 7 领域（`data.py:1633-1641`） | ❌ | 漏「科技」 |
| 事件阈值 | 80（:477） | `threshold_base = 80`（`core/settlement_steps.py:2454`） | ✅ | — |
| 密旨泄露率 | 20%（:93） | `random.random() < 0.2`（`core/settlement_steps.py:123`） | ✅ | — |
| 施恩 | +7 满意度 / +2 权势 / −20 万贯（:108） | `commands.py:104-121` 逐值一致 | ✅ | — |
| 省浮费 | 12~18 月 / 月省 5~15 万 / 减威望 2（:149） | `settlement_steps.py:431-436` 一致 | ✅ | — |
| 常平仓粜粮线 | > 1.6（:199） | `CHANGPING_HIGH = 1.6`（`data.py:1787`） | ✅ | — |
| 交子界制/工墨费 | 一界 36 回合 / 5%（未在正文，代码 `JIAOZI_TERM=36`/`JIAOZI_REDEEM_FEE=0.05`） | `data.py:1497-1498` | ✅ | — |
| 缓存 LRU | ≤64（:366） | `while len(self._cache) > 64`（`ai/client.py:657`） | ✅ | — |
| 区间脱敏噪声 | 半宽 ±8%~±25%、中心 ±5% 偏移（:349） | `width_pct` 默认 0.20、`_ORG_PRECISION` 0.06~0.15、`jitter_pct=0.05`（`ai/desensitize.py:40-41,70-79`） | ✅ | — |
| 大臣家产 | 蔡京 3万/800、陈瓘 0.5万/80、封顶 5000 万（:166,276） | `ESTATE_INIT` / `ESTATE_WEALTH_CAP=50_000_000`（`data.py:1580,1586,1605`） | ✅ | — |
| 岁币 | 辽 ≥60 出 60%、夏 ≥60 出 40%，年 30 万贯（:188） | `settlement_steps.py:2918` `SUI_GONG_ANNUAL*0.6/12` | ✅ 值一致（口径问题见 G-46） | — |
| 事件压力倍率 | 1.0（史实）（:478） | `DIFFICULTY_PRESETS["史实"]["event_pressure_mult"]=1.0`（`data.py:573`） | ✅ | — |

### B. 历史分析文档 `analysis/*.md` ↔ 代码

| 项 | 文档值(位置) | 代码值(文件:行) | 是否一致 | 影响 |
|---|---|---|---|---|
| 田亩 | 「在册 4.68 亿亩」（`progress_snapshot.md:37`、`pop_economy_system.md:144`、`economy_audit_report.md:50`） | Σ20 路 `land = 468,000,000` ✅ **但** `LAND_INFO["cultivated"] = 460,000,000`（`data.py:1474`） | ⚠️ 半一致 | 两全局锚相差 800 万亩（1.7%） |
| 粮产 | 「7.2 亿石/年」（`pop_economy_system.md:45,145`、`progress_snapshot.md:38`） | Σ20 路 `grain = 707,301,250`（7.07 亿） | ❌ 1.8% | 量级说明基本对，精确值错 |
| 人口 | 「在籍 8000 万 + 兵 75 万」（`pop_economy_system.md:20,143`） | Σ`population = 80,000,000`；`ARMY_UNIT_INIT` 合计 750,000 | ✅ | — |
| 隐户 | 「隐户 2000 万」（`pop_economy_system.md:20`）vs「隐户 500 万」（`progress_snapshot.md:12`） | `LAND_INFO["hidden_households"] = 5_000_000`（`data.py:1476`） | ❌（前者错） | 两份分析文档互相矛盾 |
| 人均口粮 | 「0.3 石/月」（`pop_economy_system.md:53`、`progress_snapshot.md:39`） | `PER_CAPITA_MONTH_GRAIN = 0.5`（`data.py:1755`）+ `GRAIN_CONSUME_PER_CAPITA` 分阶 0.4~1.8（`data.py:1758`） | ❌ | 分析文档口径彻底过时 |
| 盐课 | 「1.85 亿斤 × 0.045 ≈ 40 万贯/月」（`pop_economy_system.md:151`） | 0.055 贯/斤（`data.py:197`） | ❌ | 同 G-4 |
| 酒课 | 「`WINE_COIN_BASE = 100_000`，✅ 与注释一致」（`economy_audit_report.md:38`） | 600_000（`data.py:204`） | ❌ | 分析结论已被后续改动推翻 |
| 岁币口径 | 「全折贯，史实为银 10 万两 + 绢 20 万匹」（`audit_dimension_report.md:55`） | 仍为 `SUI_GONG_ANNUAL` 全贯（`data.py:1813`） | ❌ 遗留未修 | 见 G-46 |
| 州层 Σpopulation 与全局锚差 7% | 「Σ=4995 万 vs 5355 万，差 7%」（`audit_dimension_report.md:56`） | 现 Σ=80,000,000 == `SALT_POP_BASE` == 文档 8000 万 | ✅ **已修复** | 历史遗留已消解 |
| 12 路户数 9990 万 vs 全国 2000 万 | `code_review_report_2026-08-17.md:75` | Python 已改 20 路 Σhouseholds=20,000,000 ✅；**Rust 仍是 12 路 Σ=9990 万**（`constants.rs:79-209`） | ⚠️ Python 已修 / Rust 未修 | 见 G-1 |

### C. 三处常量一致性（Python 权威源 ｜ 文档 ｜ Rust 平行后端）

> 依任务要求「顺带记录」，Rust 逻辑深审归另一位审计员。

| 常量 | Python `content/data.py` | Rust `constants.rs` | 一致 | Rust 行 |
|---|---|---|---|---|
| `MONTHLY_EXP_CIVIL_BASE` | 880_000 | **1_300_000** | ❌ 1.48× | :30 |
| `WINE_COIN_BASE` | 600_000 | **100_000** | ❌ 6× | :41 |
| `TAX_COLOR_RATE` | 0.40 | **1.0** | ❌ 2.5× | :43 |
| `CHANGPING_LOW` | 0.9 | **0.6** | ❌ | :48 |
| `SPARROW_RAT` | 0.012 | **0.01** | ❌ | :45 |
| `CANAL_LOSS_BASE` | 0.06 | **0.04** | ❌ | :216 |
| `SALT_CAPACITY_BASE` | 185_000_000（斤/年） | 231.0（单位不同） | ❌ 口径异 | :35 |
| `SALT_POP_BASE` | 80_000_000（口） | 5065.0（万） | ❌ | :36 |
| `SALT_PROFIT_PER_JIN` | 0.055 | 无（改用 `SALT_COIN_UNIT=3090.0`） | ❌ 结构异 | :34 |
| `TREASURY_START`/`INNER_TREASURY_START`/`PRESTIGE_START`/`ARRIVAL_BASE`/`ANNUAL_TAX_BASE`/`TAX_POLL_RATIO`/`COMMERCE_TAX_RATE_MIN`/`MAX`/`PAY_CASH_BASE`/`PAY_GRANARY_BASE`/`SUI_GONG_ANNUAL`/`LAND_TAX_RATE_BENEFIT`/`IMPERIAL_SHARE`/`CHANGPING_HIGH`/`CORRUPTION_MULT`/`BRIBE_FLOOR`/`MARITIME_TRADE_BASE`/`CANAL_MONTHLY_RATE`/`CANAL_LOSS_CORRUPT_WEIGHT`/`CLERK_PER_OFFICIAL`/`SOLDIER_*`/`OFFICIAL_*`/`CLERK_*` | 同 | 同 | ✅ | — |
| Rust 独有 | — | `COMMERCE_BASE=350_000_000`、`SALT_COIN_UNIT=3090.0`、`GRANARY_START(_CAP)`（万石口径） | ⚠️ | :66,34,18-19 |

---

## 重复定义（单一权威源被违反）表

| # | 常量/表 | 岗位上的权威源 | 影子副本位置 | 当前是否已漂移 |
|---|---|---|---|---|
| D-1 | 圣旨执行率 9 常量 | `content/data.py:132-140`（`S_BASE`/`S_SUPPORT_WEIGHT`/`S_CONFLICT_WEIGHT`/`S_SECRET_BASE`/`S_SECRET_LOYALTY_WEIGHT`/`S_DIRECT_BONUS`/`S_DIRECT_PENALTY`/`E_MIN`/`E_MAX`） | `core/game_state.py:872,876,878,881,886,888` 硬编码 `0.30/0.7/0.85/0.04/0.45/0.08/0.10/0.15/0.05/0.95` | 值暂同；**权威源 9 个全为死常量**（改权威源无任何效果） |
| D-2 | 到账率 5 常量 | `content/data.py:145-150` | `core/game_state_econ.py:312-318` 硬编码 `0.30/0.15/0.25/0.05/0.95`（仅 `arrival_rate_base` 从 state 取） | 值暂同；**5 个权威常量全死** |
| D-3 | 密旨/御笔上限 | `data.py:106-108` `SECRET_DECREE_MIN/MAX`、`DIRECT_DECREE_MAX` | `core/commands_decree.py:151,366`（`>= 3`）、`:308`（`>= 2`） | 值暂同；权威常量全死 |
| D-4 | 火器代际门槛 | `data.py:528-533` `FIREARM_TIERS` | `core/army_models.py:290-299` 硬编码 `85/65/40` 与倍率 `1.30/1.18/1.08/1.0` | 值暂同；权威常量死 |
| D-5 | trust/shortage 脱敏文案 | `data.py:1838-1841` `FINANCE_DESC` | **同文件** `data.py:2100-2110` `desensitize_trust/shortage` 硬编码同 4+4 条文案 | 值暂同；`FINANCE_DESC` 死 |
| D-6 | 官数/吏数派生 | `data.py:187` `CLERK_PER_OFFICIAL=8` | `core/game_state.py:71` 与 `:491-492` 三处 `* 0.00135`，其中 `:492` 硬编码 `* 8` | 值暂同；系数 0.00135 无权威常量 |
| D-7 | 存档读档默认值 | `data.py:95-99,145` `EMPEROR_*_START`/`ARRIVAL_BASE` | `core/save_load.py:274-276,280` 硬编码 `85/25/30/0.45` | 值暂同（潜在） |
| D-8 | 私熔兜底默认 | `data.py:1509` `0.10` | `core/game_state_econ.py:116` `coin.get("private_melt", 0.2)` | **已漂移**（0.2 ≠ 0.10） |
| D-9 | 事务清单（科举/科技/金融/改革/外交/军事） | 无（data.py 的 `EXAM_ACTS`/`TECH_ACTS`/`TECH_ACTS_EX`/`FINANCE_ACTS`/`REFORM_ACTS`/`DIPLOMACY_ACTS`/`ARMY_EXPAND_ACTS` 全死） | `ai/prompts/exam.md:8`、`military_expand.md:8`、`finance.md:10` 等以**自然语言文本**重复同一清单 | 结构上双源、且文档指向已死的那一份 |
| D-10 | 档位→数值映射 | `data.py:1361-1369` `TIER_RANGE` | `core/asset_context.py:247-248` `{无:0, 微:0.08, 小:0.15, 中:0.25, 大:0.40}` | **两套并存、语义不同**（生成节点效果 vs 通用档位倍率） |
| D-11 | 商品价 | `data.py:219-225` `MATERIAL_PRICE_BASE`（钱/单位） | `data.py:1768` `GOODS_PRICE`（贯/单位）——布 120 钱 vs 1 贯、绸 800 钱 vs 3 贯 | **已冲突**（见 G-41 [疑似]） |
| D-12 | 田亩全局锚 | Σ20 路 `land = 468,000,000` | `LAND_INFO["cultivated"] = 460,000,000`（`data.py:1474`）、`LAND_INFO["wasteland"]=80,000,000` | **已漂移 800 万亩** |
| D-13 | 田赋本色月入口径 | 代码 `game_state_econ.py:357` `/3.0`（三运期） | `data.py:176` 注释写 `/12`；主文档 `:173` 写 `/3` | 注释与代码矛盾 |
| D-14 | 粮/钱俸禄月度总盘子 | `data.py:1744-1745` `PAY_GRANARY_BASE=800_000` / `PAY_CASH_BASE=2_000_000` | `MILITARY_GRAIN_MONTHLY=600_000` + `OFFICIAL_GRAIN_MONTHLY=200_000`（`data.py:1644-1645`）表述同一量 | 三者皆与 `PAY_GRANARY_BASE` 同值，但**三者全为死常量** |
| D-15 | 事件类别登记 | `data.py:552-556` `EVENT_CATEGORIES` | `core/events.py` 内 5 个新事件用「制度/西线军事/财政」标签 | **集合不等** |
| D-16 | 事权归属 | `ministers/data.py:376-403` `AUTHORITY_MATTERS` | 同文件 `CENTRAL_ORG_INFO[*].matter_keys`（269-371） | **双向 12+1 不匹配** |
| D-17 | 宋江/方腊起义年份闸 | `core/events.py:27,41`（1118 / 1119） | `core/settlement_steps.py:2434,2439`（1118 / **1111**） | **已漂移** |
| D-18 | 「金」政权登记 | `data.py:396-400` `EXTERNAL_FORCES` + `:1122` `EXTERNAL_PROVINCES` | `data.py:1249` `EXTERNAL_REGIMES` **无「金」** | **已漂移**（`external_view` 对金返回 `{}`） |

---

## 详细条目

### G-1 [P0] Rust 平行后端常量已与 Python 权威源实质漂移（7 项）
- 位置：`songzuo_server/src/constants.rs:30,41,43,45,48,35,36,216` ↔ `game/content/data.py`
- 证据：[确认] 实跑 `g_audit_exports.py` 逐项对拍：
  ```
  MONTHLY_EXP_CIVIL_BASE   Python 880000    Rust 1_300_000   **漂移**
  WINE_COIN_BASE           Python 600000    Rust 100_000     **漂移**
  TAX_COLOR_RATE           Python 0.4       Rust 1.0         **漂移**
  CHANGPING_LOW            Python 0.9       Rust 0.6         **漂移**
  SPARROW_RAT              Python 0.012     Rust 0.01        **漂移**
  CANAL_LOSS_BASE          Python 0.06      Rust 0.04        **漂移**
  SALT_CAPACITY_BASE       Python 1.85e8    Rust 231.0       **口径异**
  SALT_POP_BASE            Python 8.0e7     Rust 5065.0      **口径异**
  ```
  另：`constants.rs:70` 注释「对齐 Python content/data.py PREFECTURE_INFO **432-571**」行号已过期（现为 992-1093）；`default_prefectures()` 仅 12 路、Σhouseholds=9,990 万、Σpopulation=4,995 万，与 Python 20 路 2000 万户/8000 万口完全不同源。
- 影响：`game/README.md:197` 与主文档 `:381` 宣称的「根治远程后端常量漂移」只覆盖了**Python 版 FastAPI 薄壳**（`backend/server.py` 复用 `LocalBackend`）；玩家一旦接云端 `songzuo_server`，折色率、酒课、常支、常平仓、漕运损耗全部走另一套数——同一存档两种经济。
- 验证方式：`python g_audit_exports.py`（输出见 `g_audit_exports.out.txt`）
- 建议修复：为 Rust 端加**同源生成**（由 `content/data.py` 导出 JSON/`build.rs` 生成常量表）或删去 Rust 副本改由环境注入；至少在 CI 增加 Python↔Rust 常量对拍门禁（Rust 逻辑深审归另一审计员）。

### G-2 [P0] 唯一的文档-常量防线 `check_docs_constants.py` 不可运行且覆盖极窄
- 位置：`_dev_tools/game-docs/analysis/check_docs_constants.py:15,19,22-41,115-119`
- 证据：[确认] 实跑复现
  ```
  A: cwd=game, python <abs>/check_docs_constants.py
     → ModuleNotFoundError: No module named 'content'   （exit 1）
  B: 加 PYTHONPATH=D:\codebuddy\sz\game 后才跑出：
     ===== 文档-常量漂移检出 =====
      - [漂移] TREASURY_CRISIS: 文档=-500万 | data.py=5000000
      - [漂移] TREASURY_COLLAPSE: 文档=-2000万贯 | data.py=20000000
      - [漂移] MONTHLY_EXP_CIVIL_BASE: 文档=55万贯 | data.py=880000
      - [漂移] SALT_PROFIT_PER_JIN: 文档=0.045 贯 | data.py=0.055
     共 4 处不一致   （exit 1）
  ```
  根因：`:15` `sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))` 解析为 `game-docs/`，而 `content` 在 `game/`；docstring 写的 `python analysis/check_docs_constants.py` 从 game 根目录也**不可能成功**（脚本目录才是 `sys.path[0]`）。
  覆盖面缺陷：`DOC_TO_ATTR`（`:22-41`）只映射 **12 个常量**，且 `TREASURY_CRISIS`/`TREASURY_COLLAPSE` 在字典字面量里各写两遍（`:28-29` 与 `:39-40`），重复键被静默覆盖；`_UNIT_MULT` 在 `_parse_doc_table` 中先用后定义（`:61`/`:72`，靠调用时序侥幸不报错）。它**完全没覆盖**本报告 G-3~G-14 的 11 项新漂移（酒课、常平仓、私熔、征率上限/默认、事件数、外部政权数、档位档数、TIER 键数、财政分档、商品折旧、prompt 数）。
- 影响：这条「防漂移」防线从未生效——脚本自带 4 个红灯长期无人处理；且它若真接入 CI 会直接红。文档与代码的漂移因此持续累积（本轮新增 11 项）。
- 验证方式：`pwsh -Command "$env:PYTHONPATH=''; python D:\codebuddy\sz\_dev_tools\game-docs\analysis\check_docs_constants.py"`（必然失败）；加 `PYTHONPATH` 后见上方输出。
- 建议修复：① `sys.path.insert` 改为指向 `game/`（`"..", "..", "game"`）；② 改为**从文档全文正则抽取**而非维护 12 行手写映射（可复用本报告 `g_audit_core.py` §19 的写法）；③ 把 `check_docs_constants.py` + `check_docs_constants` 之外的断言纳入 CI 门禁，红灯即阻断。

### G-3 [P1] 常支 55 万贯/月 vs `MONTHLY_EXP_CIVIL_BASE = 880_000`（历史遗留，**仍未修**）
- 位置：`游戏机制说明.md:184`（正文支出侧）、`:467`（速查表） ↔ `content/data.py:165`
- 证据：[确认] 脚本对拍：文档 `常支 | 55 万贯/月`，代码 `MONTHLY_EXP_CIVIL_BASE = 880_000`。`review_2026-08-31.md:130` 已将此项列为「未修项（P2）」，本轮复核确认**一字未改**。
- 影响：财务规划类文档完全失真；1.6 倍差足以让玩家对「开源节流」难度做出错误判断。
- 验证方式：`g_audit_core.py` §19 第 1、2 行
- 建议修复：文档改写为 88 万贯/月；并把该常量接入 `check_docs_constants.py` 的强制项。（另注意 `:165` 注释「税基 POP 化后按收入规模校准」未给出与 `PAY_CASH_BASE=200 万` 的平衡关系。）

### G-4 [P1] 盐榷利单价 0.045 vs 0.055
- 位置：`游戏机制说明.md:178`（收入侧公式）、`:472`（速查表） ↔ `content/data.py:197`
- 证据：[确认] `SALT_PROFIT_PER_JIN = 0.055  # 平衡修复 0.045→0.055`（代码注释自述已改，文档未跟）。
- 影响：盐课月入 ≈ Σ盐产 1.85 亿斤 × 0.01 贯/斤 ÷ 12 = 15.4 万贯/月的估算误差。
- 验证方式：`g_audit_core.py` §19

### G-5 [P1] 酒课保底 10 万 vs 60 万贯/月
- 位置：`游戏机制说明.md:179` ↔ `content/data.py:204`
- 证据：[确认] `WINE_COIN_BASE = 600_000  # 加消耗定案扩容 10万→60万贯/月`。另 `analysis/audit_dimension_report.md:12,30` 曾裁决「WINE_COIN_BASE=10 万贯/月」，二次扩容后该分析文档亦失效。
- 影响：内帑收入量级差 6 倍——玩家对内帑「皇帝私库」规模的判断全错。
- 验证方式：`g_audit_core.py` §19

### G-6 [P1] 破产两档线文档符号与判据双重过时
- 位置：`游戏机制说明.md:61`（Step 0）、`:440`（结局 1）、`:476`（速查表） ↔ `content/data.py:369-370`、`core/evaluation.py:48-61,174-179`
- 证据：[确认] 文档「国库 < -2000 万贯 / < -500 万贯」；代码 `TREASURY_CRISIS_LINE = 5_000_000`、`TREASURY_COLLAPSE_LINE = 20_000_000` 为**正数**，判据是 `state.deficit_depth() > LINE`（`game_state.py:744`）。README `R2-7`（`:139`）明示「原 −500万/−2000万 与国库 `max(0,…)` 纪律矛盾 → 永不可达；改为累计亏空深度」。README 已改、机制文档未改。
- 影响：文档所述三条不可达分支（破产结局/库藏空虚危机/财政评价 30·10 档）在读者看来仍存在，实际已是另一套语义；`check_docs_constants.py` 也正是靠这条报出唯一的「真」符号漂移。
- 验证方式：`g_audit_core.py` §19「危机线」行；`check_docs_constants.py` 输出第 1、2 行

### G-7 [P1] 事件数量文档 9/5，实际 14/10
- 位置：`游戏机制说明.md:302`（史实事件表）、`:317`（随机事件） ↔ `core/events.py:9-278`、`:283-375`
- 证据：[确认] 脚本枚举 `HISTORICAL_EVENTS` = 14（多出 `chongning_party_proscription`(1102-1104)、`school_three_halls`(1102-1108)、`recover_hehuang`(1103-1104)、`chongning_coinage`(1103-1105)、`fangtian_taxation`(1104-1115)）；`RANDOM_EVENTS` = 10（多出 黄河秋汛告急 / 太学三舍法争议 / 市舶贡使献方物 / 常平仓奏请籴粜 / 西军乏饷）。
  另：文档 `:305` 写花石纲 1102-1120，代码 `events.py:13` 为 `(1105, 1120)`（A15 时代门槛，注释自述「此前不可触发」）。
- 影响：机制文档对事件系统的覆盖面少 36%；花石纲年份错误会导致「1102 年就该有花石纲」的错误预期。
- 验证方式：`g_audit_extra.py` §D

### G-8 [P1] 外部政权数 31 vs 41/38，且「金」登记在三张表中不齐
- 位置：`游戏机制说明.md:224` ↔ `content/data.py:1249-1296`
- 证据：[确认] `EXTERNAL_REGIMES` = 41 键；扣去 辽、西夏 后 39 个，其中也**不含「金」**，故「金/辽/西夏 + 31 个」的 31 应对应 38（若把金单列则 40）。同见 G-19。
- 影响：外交/舆图名册规模认知错误；「金」的登记不齐导致静态视图缺项。
- 验证方式：`g_audit_core.py` §13

### G-9 [P1] §八 档位换算仍写 5 档 `大=1.8`，代码已 7 档
- 位置：`游戏机制说明.md:359` ↔ `content/data.py:1361-1369`
- 证据：[确认] 文档「无|微|小|中|大 → `tier_to_value()` 换算（0 / 0.25 / 0.5 / 1.0 / 1.8）」；代码 `TIER_RANGE = {无:0.0, 微:0.25, 小:0.5, 中:1.0, 大:1.5, 巨:2.0, 极:2.5}`，`TIER_ORDER` 7 档。文档 `:359` 整段漏「巨/极」，且 `大` 的倍率从 1.8 改为 1.5（`data.py:1360` 注释「大 1.8→1.5 归一」）。
- 影响：§八 是 AI 契约使用者查阅量级的唯一入口；按 1.8 估算会高估「大」档效果 20%，并完全看不到「巨/极」两档的存在。§八 `:360` 的「17 键」同源过时（实为 18 键，`data.py:1417-1436`）。
- 验证方式：`g_audit_core.py` §19 手动断言区

### G-10 [P1] 效果键白名单 17 键 vs 18 键
- 位置：`游戏机制说明.md:360` ↔ `content/data.py:1417-1436`
- 证据：[确认] `TIER_VALUE_BASE` 键 = prestige, treasury, population_satisfaction, external_jin, external_liao, external_xixia, defense_bonus, commerce_tax, curtail_waste, reduce_office, land_survey, hoard, finance, talent, tech, army, reform, art_mastery = **18**；文档正文列了 17 个（漏 `art_mastery`，而 `data.py:1435` 注释恰称「原 _TIER_BASE 缺此项致换算恒0」曾修过）。
- 影响：修完代码忘改文档，同一处遗漏在文档侧复现。
- 验证方式：`g_audit_core.py` §19 手动断言区

### G-11 [P1] §九 财政分档判据与代码不符
- 位置：`游戏机制说明.md:430` ↔ `core/evaluation.py:48-61`
- 证据：[确认] 文档「>1000 万=90、>500 万=70、>0=50、>-200 万=30、否则 10」；代码：
  ```python
  if _deficit > TREASURY_COLLAPSE_LINE: caizheng = 10      # 累计亏空 >2000万
  elif _deficit > TREASURY_CRISIS_LINE: caizheng = 30      # 累计亏空 >500万
  elif state.treasury > 10_000_000:     caizheng = 90
  elif state.treasury > 5_000_000:      caizheng = 70
  else:                                 caizheng = 50
  ```
  文档的「>0=50」与「否则 10」之间的「−200 万」档在代码中**不存在**；30/10 档按亏空深度而非国库余额。
- 影响：结局评分预期错误；`EVAL_WEIGHTS["财政"]=0.10`，影响总分 ~±4 分，可能跨结局档（85/70/55/40）。
- 验证方式：`g_audit_core.py` §19 手动断言区

### G-12 [P1] 工商征率上限 0.30 vs 0.40、默认 5% vs 6%
- 位置：`游戏机制说明.md:148,175` ↔ `content/data.py:337,340-341`
- 证据：[确认] 文档「可调 0.05~0.30」；代码 `COMMERCE_TAX_RATE_MAX = 0.40  # 最高 4 成`。文档「征率（默认5%）」；代码 `COMMERCE_TAX_RATE_DEFAULT = 0.06`（注释自述「0.055→0.05」但值写 0.06，注释本身也失同步）。
- 影响：`core/settlement_steps.py:421` 的 clamp 上限为 0.40，玩家可把征率推到「苛征（三成以上）」（`game_state_econ.py:88`），文档却说上限 0.30——策略空间描述错误。默认值差 1 个百分点直接影响开局岁入。
- 验证方式：`g_audit_core.py` §19

### G-13 [P1] 商品月折旧 3% vs 5%
- 位置：`游戏机制说明.md:163` ↔ `core/settlement_steps.py:1693-1696`
- 证据：[确认] 文档「商品月折旧 3%」；代码注释与实现均为 5%：
  ```python
  # 3) 商品折旧（各 POP 持有商品每月 5% 消耗 ...）
  _pop["goods"][_gdim] = int(_pop["goods"][_gdim] * 0.95)
  ```
- 影响：商品存量平衡点差 1.67 倍，影响工匠/商人 wealth 与物价推演；也是「加消耗方案」的一部分，直接影响长期财政。
- 验证方式：`g_audit_extra.py` §20（原 `g_audit_core.py` §20「商品折旧率」命中行）

### G-14 [P1] 铜钱私熔 20% vs 10%
- 位置：`游戏机制说明.md:246` ↔ `content/data.py:1509`
- 证据：[确认] 文档「private_melt（私熔 20% 扣减货币供给）」；代码 `COIN_INFO = {"shortage":0.30, "private_melt": 0.10}  # T9 定稿 0.2→0.1`。
- 影响：物价公式 `money *= (1 - private_melt)`（`game_state_econ.py:116`）据此扣减货币供给，文档口径把货币供给低估 10%。
- 验证方式：`g_audit_core.py` §19

### G-15 [P1] 同一权威文件内两个田亩全局锚不一致（4.6 亿 vs 4.68 亿）
- 位置：`content/data.py:1474` ↔ `content/data.py:992-1093`
- 证据：[确认] 实测
  ```
  Σ PREFECTURE_INFO.land = 468,000,000
  LAND_INFO['cultivated'] = 460,000,000    diff = 8,000,000
  ```
  `LAND_INFO["cultivated"]` 被 `game_state.py:637`（`self.land = dict(LAND_INFO)`）载入运行态，并被 `settlement_steps.py:784`（自然开垦）、`SEED_GRAIN_PER_MU=0.065`（种粮预留）消费；`PREFECTURE_INFO.land` 则被 `split_circuit_demog` 与舆图州府层消费。两份文档（`progress_snapshot.md:37`、`pop_economy_system.md:144`）都主张 4.68 亿。
- 影响：全局耕地锚与路级锚分叉，种粮预留量差 1.7%，且「田亩总览」与「州府合计数」在 UI 上会对不上。
- 验证方式：`g_audit_core.py` §2
- 建议修复：`LAND_INFO["cultivated"]` 改由 `sum(PREFECTURE_INFO[r]["land"])` 派生（或建表时断言两者相等），并同步 `wasteland`（现 8000 万亩无对应路级字段，属独立锚）。

### G-16 [P1] `TECH_EFFECT_LABELS` 缺 4 键 + 同字典内 `trade_income` 重复定义被静默覆盖
- 位置：`content/data.py:831-871`（字典）、`:847` 与 `:860`（`trade_income` 两次）
- 证据：[确认] 脚本抽取「代码中实际出现的全部效果键」与标签表对比：
  ```
  有键无中文标签 = ['calendar_bonus', 'defense_bonus', 'flood_risk', 'maritime_income']
  标签表多余键   = ['art_gain','bandwidth_bonus',...,'training','treasury','unrest']  （25 个）
  ```
  重复键：
  ```python
  "trade_income": "贸易收入",     # data.py:847  ← 被下面覆盖，死条目
  ...
  "trade_income": "市舶收入",     # data.py:860  ← 实际生效
  ```
  `content/codex_data.py:121-128` 的 `_codex_effect_label` 对未知键回退 `str(k)`，于是图鉴上直接显示英文键名。
- 影响：图鉴（唯一前端）对 `CAPABILITY_EFFECTS`（`data.py:1911-1933`）里的 `maritime_income`/`calendar_bonus`/`flood_risk`，以及 `CAPABILITY_EFFECTS[("筑城","城防")]` 的 `defense_bonus` 全部渲染成英文；`trade_income` 第一次定义的文案永久失效（内容死数据）。
- 验证方式：`g_audit_core.py` §8
- 建议修复：补 4 个标签；删掉 `:847` 的重复项；把「标签表键 ⊇ 实际效果键」做成断言（放 `check_docs_constants.py` 同级的自检）。

### G-17 [P1] 46 个 `data.py` 模块级常量全库零引用（含「本应是权威源」的 14 个）
- 位置：`game/content/data.py` 多处（清单见下）
- 证据：[确认] 脚本全库逐行扫描（排除定义行自身、排除 `frontend/node_modules` 等），真死常量 46 个：
  ```
  ARMY_EXPAND_ACTS(2051) ARRIVAL_AUDIT_WEIGHT(146) ARRIVAL_AUTHORITY_WEIGHT(147)
  ARRIVAL_DIVERSION_WEIGHT(148) ARRIVAL_MAX(150) ARRIVAL_MIN(149) CASH_CROP_LAND(969)
  DECREE_MAX_BANDWIDTH(105) DIPLOMACY_ACTS(2057) DIRECT_DECREE_MAX(108) EMPEROR_HEALTH_MAX(96)
  EXAM_ACTS(1853) E_MAX(140) E_MIN(139) FINANCE_ACTS(1550) FINANCE_DESC(1838) FIREARM_TIERS(528)
  FIXED_PROCEDURES(597) INDUSTRY_OLD_DECAY(1728) INLAND_MORALE_BONUS(471) INLAND_TRAIN_BONUS(470)
  MILITARY_GRAIN_MONTHLY(1644) OFFICIAL_GRAIN_MONTHLY(1645) ORG_AFFILIATION(113) PAY_GRANARY_BASE(1744)
  POP_TYPES(257) PRESTIGE_MAJOR_EVENT_CAP(72) PRESTIGE_MAX(69) PRESTIGE_MIN(70) PRESTIGE_MONTHLY_CAP(71)
  REFORM_ACTS(2063) ROUTE_MULT_DEFAULT(172) SECRET_DECREE_MAX(107) SECRET_DECREE_MIN(106)
  S_BASE(132) S_CONFLICT_WEIGHT(134) S_DIRECT_BONUS(137) S_DIRECT_PENALTY(138) S_SECRET_BASE(135)
  S_SECRET_LOYALTY_WEIGHT(136) S_SUPPORT_WEIGHT(133) TAX_COMMERCE_RATIO(327) TAX_LAND_RATIO(326)
  TECH_ACTS(1881) TECH_ACTS_EX(1883) WOLF_THRESHOLD(109)
  ```
  其中 14 个属「应为权威源 → 消费侧硬编码影子」：`S_BASE/S_SUPPORT_WEIGHT/S_CONFLICT_WEIGHT/S_SECRET_BASE/S_SECRET_LOYALTY_WEIGHT/S_DIRECT_BONUS/E_MIN/E_MAX`（`core/game_state.py`）、`ARRIVAL_AUDIT_WEIGHT/ARRIVAL_AUTHORITY_WEIGHT/ARRIVAL_DIVERSION_WEIGHT/ARRIVAL_MIN/ARRIVAL_MAX`（`core/game_state_econ.py`）、`PAY_GRANARY_BASE`（与 `MILITARY_GRAIN_MONTHLY`+`OFFICIAL_GRAIN_MONTHLY` 三方同义）。
- 影响：`README.md:81` 把 `content/data.py` 描述为「数据（**单一权威源**）」，但近 1/6 的模块级常量无人读取。改动权威源**完全无效果**（改 `S_BASE` 不会改变任何执行率），这是最危险的「假权威源」形态。`PAY_GRANARY_BASE`（粮）/`PAY_CASH_BASE`（钱）本是一对，钱侧是活常量、粮侧是死常量，进一步说明这对盘子已被别的公式取代。
- 验证方式：`g_audit_extra.py` §A、§B
- 建议修复：① 删或标注 `# DEAD (审查 2026-…)`；② 对「应为权威源」的 14 个，改消费侧 `from content.data import …`；③ 加一条「data.py 常量必须被至少一处非 data.py 引用，或显式列入 `_DEAD_ALLOWLIST`」的自检。

### G-18 [P1] 事务清单（ACTS 族）在权威源全死，真实清单硬编码在 prompt 文本
- 位置：`content/data.py:1853`（`EXAM_ACTS`）、`:1881,1883`（`TECH_ACTS(+EX)`）、`:1550`（`FINANCE_ACTS`）、`:2063`（`REFORM_ACTS`）、`:2057`（`DIPLOMACY_ACTS`）、`:2051`（`ARMY_EXPAND_ACTS`） ↔ `ai/prompts/exam.md:8`、`military_expand.md:8`、`finance.md:10`
- 证据：[确认] 上述 7 个常量在全库零引用；同一清单以自然语言形式存在于 prompt：
  ```
  ai/prompts/military_expand.md:8  所行举措：{act}（可选范围：募兵益军 / 整练新军 / 缮修兵甲 / 置将练兵 / 修城备边）
  ai/prompts/exam.md:8             ...（可选范围：开科取士 / 改革科举（经义或词学） / 兴州县学 / 制科荐才 / 武举）
  ai/prompts/finance.md:10         ...（可选范围：行交子 / 榷货市舶 / 设银行 / 定金银铜三品本位 / 平抑物价 / 铸铁钱）
  ```
  与 `data.py` 中同名列表逐项一致（当前未漂移）。
- 影响：文档 `游戏机制说明.md:113` 明确写「事务清单定义在 `content/data.py` 的 ACTS 常量族」——**与事实相反**。任何人按文档去改 `data.py` 都会以为生效，实际 AI 看到的是 prompt 文本。这是「权威源文档化错误」的典型。
- 验证方式：`g_audit_extra.py` §A（ACTS 全部落入真死列表）
- 建议修复：prompt 改为运行时由 `data.py` 列表插槽渲染；或反之删掉 `data.py` 副本并把文档指向 prompt。

### G-19 [P1] 「金」政权登记不齐：`EXTERNAL_REGIMES` 缺失
- 位置：`content/data.py:396-400`（`EXTERNAL_FORCES` 有金）、`:1122`（`EXTERNAL_PROVINCES` 有金）、`:1249-1296`（`EXTERNAL_REGIMES` **无金**） ↔ `core/external_view.py:18-20,41-43`
- 证据：[确认] 脚本对拍：
  ```
  EXTERNAL_FORCES 键 = ['西夏','辽','金']   ⊄ EXTERNAL_REGIMES? ['金']
  EXTERNAL_PROVINCES 键 = ['大理','日本','西夏','辽','金','高丽']  ⊄ EXTERNAL_REGIMES = ['金']
  ```
  `external_view.external_pop_view(state, "金")` / `external_provinces(state, "金")` 首行 `EXTERNAL_REGIMES.get(name)` → `None` → 返回 `{}` / `[]`。
  `core/game_state.py:563` 的 `external_regimes` 也只迭代 `EXTERNAL_REGIMES` → 快照 `external_regimes` 里没有「金」（而前端舆图取的就是它，见 `README.md:220`、`游戏机制说明.md:176`）。
  `content/geo_admin.py:291` 的 `REGIME_GEO["金"]` 带 `"active": False`（未兴灰米），设计上是「金激活后追加」——但 `EXTERNAL_FORCES["金"]` 与 `EXTERNAL_PROVINCES["金"]` 的金是**已注册的活数据**，二者语义冲突。
  另：`core/external_view.py` 的 `external_pop_view`/`external_provinces` 全库无生产调用方（同为死代码）。
- 影响：外交面板/静态视图对「金」无人口·税·地·粮，而国主 persona（`data.py:1834`）、岁币倍率（`game_state.py:671`）、外交协议（`diplomacy_treaty.py:33`）都把金当一级对象。`EXTERNAL_PROVINCES["金"]=[("上京会宁",0.55),("黄龙府",0.45)]` 成为死键。
- 验证方式：`g_audit_core.py` §13；`g_audit_extra.py` §A
- 建议修复：二选一——① 把「金」补进 `EXTERNAL_REGIMES`（active 字段控制舆图显隐）；② 删掉 `EXTERNAL_FORCES`/`EXTERNAL_PROVINCES` 中的金，把金完全交给 `timeline` 激活链。当前两套并存必生歧义。

### G-20 [P2] 常平仓托市线 0.6 vs 0.9
- 位置：`游戏机制说明.md:199` ↔ `content/data.py:1788`
- 证据：[确认] `CHANGPING_LOW = 0.9  # 加消耗定案 0.6→0.9，收储托价扩容`。文档未跟。
- 影响：常平仓籴粮触发点描述错误，区域粮价稳定器行为预期偏差。
- 验证方式：`g_audit_core.py` §19

### G-21 [P2] 文档仍描述已取消的「狼来了」机制
- 位置：`游戏机制说明.md:91`（御笔直发 +0.10，「狼来了」≥3 次转 −0.15）、`:101`（触发 `wolf_count` 公信力下降） ↔ `data.py:109,138`、`core/game_state.py:880`、`core/commands_decree.py:170`
- 证据：[确认] `WOLF_THRESHOLD = 3  # 已停用`；`S_DIRECT_PENALTY = 0.0  # 已停用`；`game_state.py:880` 注释「狼来了机制已取消（审查 2026-09）：御笔直发恒有 +0.10 加成」；`commands_decree.py:170`「不再累计 wolf_count」。而 `state.wolf_count` 仍在 `settlement_steps.py:47-49` 被**只减不增**地衰减，并随存档持久化（`save_load.py:105,383`）。
- 影响：文档的御笔惩罚描述错误；`wolf_count` 成为永为 0 的僵尸字段（占存档、误导读者）。
- 验证方式：`grep WOLF_THRESHOLD|wolf_count`

### G-22 [P2] 圣旨执行率/到账率「权威源」全死，core 侧硬编码同值影子
- 位置：`content/data.py:132-150` ↔ `core/game_state.py:872-888`、`core/game_state_econ.py:312-318`
- 证据：[确认] 逐值对拍（当前全一致，但仍属影子副本）：
  | 权威常量 | 值 | 硬编码位置 | 硬编码值 |
  |---|---|---|---|
  | `S_BASE` | 0.45 | `game_state.py:878` | `0.45` |
  | `S_SUPPORT_WEIGHT` | 0.08 | `game_state.py:878` | `0.08` |
  | `S_CONFLICT_WEIGHT` | 0.15 | `game_state.py:886` | `0.15` |
  | `S_SECRET_BASE` | 0.30 | `game_state.py:872` | `0.30` |
  | `S_SECRET_LOYALTY_WEIGHT` | 0.7 | `game_state.py:872` | `0.7` |
  | `S_DIRECT_BONUS` | 0.10 | `game_state.py:881` | `0.10` |
  | `E_MIN` / `E_MAX` | 0.05 / 0.95 | `game_state.py:888` | `0.05 / 0.95` |
  | `ARRIVAL_AUDIT_WEIGHT` | 0.30 | `game_state_econ.py:314` | `0.30` |
  | `ARRIVAL_AUTHORITY_WEIGHT` | 0.15 | `game_state_econ.py:315` | `0.15` |
  | `ARRIVAL_DIVERSION_WEIGHT` | 0.25 | `game_state_econ.py:316` | `0.25` |
  | `ARRIVAL_MIN` / `ARRIVAL_MAX` | 0.05 / 0.95 | `game_state_econ.py:318` | `0.05 / 0.95` |
  唯一被真正 import 的是 `ZHONGZHI_AFFILIATION_RATE`（`game_state.py:856`），说明「应 import」的写法本就存在、只是漏了这 14 个。
  另 `game_state.py:876` 的中旨净支持权重 `0.04` 在任何表中都没有对应常量。
- 影响：文档 §三（`:87-89`）把 `基础率 = 0.45 + 净支持×0.08 …` 呈现为「公式常量」；读者会去改 `data.py` 的 `S_BASE`，改了无效。单边调参（例如只改 `data.py` 的 `ARRIVAL_BASE`）不会同步到公式权重。
- 验证方式：`g_audit_extra.py` §B、§E
- 建议修复：core 侧改 `from content.data import S_BASE, S_SUPPORT_WEIGHT, …`；中旨 `0.04` 补一个 `S_ZHONGZHI_SUPPORT_WEIGHT` 常量。

### G-23 [P2] 密旨上限 3 / 御笔上限 2 常量死，消费侧硬编码
- 位置：`content/data.py:106-108` ↔ `core/commands_decree.py:151,308,366`
- 证据：[确认] `SECRET_DECREE_MAX = 3`、`DIRECT_DECREE_MAX = 2` 全库零引用；实际判定：
  ```python
  commands_decree.py:151  if len(state.pending_secret_decrees) >= 3:
  commands_decree.py:366  if len(state.pending_secret_decrees) >= 3:
  commands_decree.py:308  if state.direct_decree_used >= 2:
  ```
  文档 §三 `:99,101` 也直写「上限 3 条」「≤2」。
- 影响：与 G-22 同类；上调上限需同时改 3 处且极易漏。
- 验证方式：`grep DIRECT_DECREE_MAX`

### G-24 [P2] 火器代际 `FIREARM_TIERS` 死，`army_models` 硬编码同门槛
- 位置：`content/data.py:528-533` ↔ `core/army_models.py:290-299`
- 证据：[确认] `FIREARM_TIERS = [(20,"突火枪"),(40,"火铳"),(65,"火枪"),(85,"燧发枪")]` 全库零引用；`army_models.py:292-299` 注释与分支自写：
  ```python
  # 突火枪(20)→1.0；火铳(40)→1.08；火枪(65)→1.18；燧发枪(85)→1.30
  if gunpowder >= 85: ... 1.30
  if gunpowder >= 65: ... 1.18
  if gunpowder >= 40: ... 1.08
  ```
  文档 §五 `:217` 的两组门槛（`20/40/65/85`）与之值同。
- 影响：门槛双写；`FIREARM_TIERS` 的形态名（突火枪等）实际无任何消费方，图鉴/叙事拿不到。
- 验证方式：`grep FIREARM_TIERS`

### G-25 [P2] `FINANCE_DESC` 死，同文件内 `desensitize_trust/shortage` 硬编码同样文案
- 位置：`content/data.py:1838-1841` ↔ `content/data.py:2100-2110`
- 证据：[确认]
  ```python
  # data.py:1838（死常量）
  FINANCE_DESC = {"trust": {20:"交子几不可信",40:"商民疑之",60:"信用尚稳",80:"远近信行"},
                  "shortage": {0.1:"泉货流转",0.3:"钱荒渐显",0.6:"钱荒严重",0.9:"几乎无钱可用"}}
  # data.py:2100-2110（真正生效，逐字重复）
  def desensitize_trust(value): if value<=20: return "交子几不可信" ...
  def desensitize_shortage(rate): if rate<=0.1: return "泉货流转" ...
  ```
  对照 `desensitize_prestige/arrival/satisfaction/treasury` 已改成查 `DESENSITIZE_MAP`（`:2069-2098`，注释自述「审查 P2-61 修复：原四个函数各自硬编码…现统一查表」）——同一文件里的一半已修、另一半未修。
- 影响：改文案需改两处；`FINANCE_DESC` 是纯死数据。
- 验证方式：`g_audit_core.py` §9
- 建议修复：把 trust/shortage 并入 `DESENSITIZE_MAP`，`desensitize_trust/shortage` 改走 `_desensitize_from_map`。

### G-26 [P2] 官数系数 `0.00135` 三处重复 + `CLERK_PER_OFFICIAL` 未复用
- 位置：`core/game_state.py:71,491,492` ↔ `content/data.py:187`
- 证据：[确认]
  ```python
  game_state.py:71   _off = round(info.get("households", 0) * 0.00135)   # 官数（与 officials 派生同口径）
  game_state.py:491  "officials": info.get("officials", round(info["households"] * 0.00135)),
  game_state.py:492  "clerks": info.get("clerks", round(info["households"] * 0.00135) * 8),   # 硬编码 8
  ```
  `data.py:187 CLERK_PER_OFFICIAL = 8` 存在且**被引用**（未落入死常量），但这一行没用它。
- 影响：0.00135（官/户比）无任何权威常量，改「官数口径」要改 3 处；`clerks` 的 `* 8` 与 `CLERK_PER_OFFICIAL` 一旦分叉即产生「吏数 ≠ 官数×8」。
- 验证方式：`g_audit_extra.py` §F

### G-27 [P2] 存档读档硬编码影子默认值
- 位置：`core/save_load.py:274-276,280` ↔ `content/data.py:95-99,145`
- 证据：[确认]
  ```python
  save_load.py:274  state.art_mastery      = data.get("art_mastery", 85)      # ↔ EMPEROR_ART_START=85
  save_load.py:275  state.taoism_leaning   = data.get("taoism_leaning", 25)   # ↔ EMPEROR_TAOISM_START=25
  save_load.py:276  state.pleasure_leaning = data.get("pleasure_leaning", 30) # ↔ EMPEROR_PLEASURE_START=30
  save_load.py:280  state.arrival_rate_base= data.get("arrival_rate_base", 0.45) # ↔ ARRIVAL_BASE=0.45
  ```
- 影响：当前值一致（潜在漂移）；旧档缺字段时回退到影子默认值而非权威源。
- 验证方式：`grep "data.get(\"art_mastery\""`

### G-28 [P2] 私熔兜底默认值已漂移（0.2 vs 0.10）
- 位置：`core/game_state_econ.py:116` ↔ `content/data.py:1509`
- 证据：[确认] `money *= (1 - self.coin.get("private_melt", 0.2))`；权威值 `COIN_INFO["private_melt"] = 0.10`。这是**已经发生的漂移**（不是潜在），只因 `state.coin` 总由 `COIN_INFO` 初始化而暂不触发。
- 影响：任何绕过 `COIN_INFO` 初始化 `state.coin` 的路径（旧档/测试夹具）会以 0.2 扣减货币供给，物价翻倍偏低。
- 验证方式：`grep private_melt`

### G-29 [P2] 七档词表缺档导致消费侧静默降级
- 位置：`content/data.py:1818-1829` ↔ `core/diplomacy_treaty.py:46,79`
- 证据：[确认]
  ```
  _DIPLO_ATT["和亲"] 缺 ['无','巨']       _DIPLO_ATT["战争"] 缺 ['无','微','巨','极']
  DOWRY_BASE        缺 ['无','巨']        TRADE_INCOME      缺 ['无','巨']
  ```
  消费侧：
  ```python
  diplomacy_treaty.py:22  delta  = table.get(tier, 0)                      # ← 缺档即 attitude 变化恒 0
  diplomacy_treaty.py:46  dowry  = DOWRY_BASE.get(tier, DOWRY_BASE["中"])  # ← 缺档静默降到「中」20 万贯
  diplomacy_treaty.py:79  income = TRADE_INCOME.get({"开":"小","扩":"中"}.get(tier,"小"), TRADE_INCOME["小"])
  ```
  AI 契约输出 7 档（`client.py:2377` 注释自述「其余协议 微~极」），出「巨」时 → 静默落到「中」档嫁妆（20 万贯）。
- 影响：与 `BOOM_MULT`/`EXAM_HARD_POOR_SHARE`/`HOARD_DRAW_RATE` 已补 7 档的修复（`data.py:1771-1779,247`）形成不一致：同一批修复漏掉了外交这三张表。和亲/榷场是「高代价协议」，静默降级属于给少不给多（安全方向），但会让 AI 的强度表达失效。
- 验证方式：`g_audit_extra.py` §C

### G-30 [P2] 「身死国灭」结局无描述文案
- 位置：`content/data.py:617-623`（`EVAL_OUTCOMES` 末档 `(0, "身死国灭")`） ↔ `core/evaluation.py:105-113`（`_get_outcome_desc`）
- 证据：[确认] `EVAL_OUTCOMES` 五档为 中兴/守成/治平/昏聩/身死国灭；`_get_outcome_desc` 的 `descs` 键为 中兴/守成/治平/昏聩/**社稷倾覆**。`社稷倾覆` 是 `evaluate_game` 里 `outcome` 的初始值（`:91`），但只要 `total >= 0` 就必然被 `(0,"身死国灭")` 覆盖 → `社稷倾覆` 不可达、`身死国灭` 无描述 → `description` 返回 `""`。最坏的结局（默认档、也是低分玩家最常看到的一档）没有结局面评。
- 影响：结局面板在最坏结局时文案为空。
- 验证方式：`python -c "from core.evaluation import _get_outcome_desc; print(repr(_get_outcome_desc('身死国灭')))"` → `''`
- 建议修复：`descs` 键改 `身死国灭`（或同时保留两者）。

### G-31 [P2] §九 武功·防线项量纲说明与代码不符
- 位置：`游戏机制说明.md:428` ↔ `core/evaluation.py:5-8,37-42`
- 证据：[确认] 文档「+（防线 garrison 均值-50）×0.3」；代码先归一：
  ```python
  _DEF_GARRISON_SCORE_BASE = 200_000
  avg_def_pct = max(0.0, min(100.0, 100.0 * avg_def / _DEF_GARRISON_SCORE_BASE))
  wu += (avg_def_pct - 50) * 0.3
  ```
  （注释自述「审查 P1-7 修复：garrison 为真实兵额（数万级），原实现直接 `(avg_def - 50)*0.3` 使武功恒被 clamp 到 100」——文档正是照抄了被修掉的旧实现。）
- 影响：§九 是对玩家公开的评分规则；此处照抄了已修 bug 的描述。
- 验证方式：`g_audit_core.py` §19 手动断言区

### G-32 [P2] 5 个 A6 史实事件类别不在 `EVENT_CATEGORIES`
- 位置：`core/events.py:146,170,195,229,256` ↔ `content/data.py:552-556`
- 证据：[确认]
  ```
  HISTORICAL_EVENTS 类别 = {... '制度':1, '西线军事':1, '财政':2 ...}
  EVENT_CATEGORIES 中无任何史实事件脚本 = ['宋夏战争', '灾荒', '科举']
  !! 事件类别不在 EVENT_CATEGORIES = ['制度', '西线军事', '财政']
  ```
  `_settle_events` 只对 `EVENT_CATEGORIES` 累积压力（`settlement_steps.py:2398-2402`），压力达阈值才 `_trigger_event(cat)`（`:2454-2459`）——因此这 3 个类别永远不会进入压力体系，图鉴上显示的 `category` 字段（`codex_data.py:222`）也没有任何消费方。文档 §七 `:315` 只承认「宋夏战争 无史实脚本」，未提这 3 个「有脚本但无类别登记」的反向缺口。
- 影响：图鉴事件条目的分类不可靠；`statistics["total_wars"]` / `total_disasters`（`settlement_steps.py:2471`）的归类口径与史实事件表脱节。
- 验证方式：`g_audit_extra.py` §D

### G-33 [P2] 同一史实两处年份不一致（宋江起义 1111 vs 1119）
- 位置：`core/settlement_steps.py:2439` ↔ `core/events.py:41`
- 证据：[确认]
  ```python
  # settlement_steps.py:2405 注释
  # P0-③ 起义类事件压力仅在史实窗口（1118 年方腊/1111 年宋江起）...
  settlement_steps.py:2439   if state.year >= 1111:
  # events.py:41
  "id": "songjiang", "year_range": (1119, 1121),
  ```
  史实宋江起义为宣和元年（1119）。压力闸用 1111（政和元年）比事件窗口早 8 年。
- 影响：1111–1118 年间「宋江起义」压力会持续累积（阈值 80），一旦 `get_historical_event` 在 1119 前不返回该事件，压力仍会通过 `_trigger_event` 直接触发——绕开 `year_range` 闸。这实际上把史实窗口 1119 提前到了 1111（与 `review_2026-08-31.md` P0 的「史实时间闸」修复目标部分抵消）。
- 验证方式：`g_audit_extra.py` §D（末行）
- 建议修复：两处统一为 1119（或把压力闸也纳入 `HISTORICAL_EVENTS` 的 `year_range` 单一源）。

### G-34 [P2] 治所「颍昌府」重复挂在两个路
- 位置：`content/geo_admin.py:44`（京畿路 members）与 `:54`（京西路 members）
- 证据：[确认] 脚本统计 136 个治所，唯一重复项：
  ```
  颍昌府 in 京畿路 ('颍昌府','府',113.85,34.04)
  颍昌府 in 京西路 ('颍昌府','府',113.85,34.04)
  ```
  `demography.split_circuit_demog` 以治所名做字典键（`demography.py:107` `out[n] = {...}`），两路拆分时**后者覆盖前者**——京畿路拆出的颍昌府人口/田亩/粮产会被京西路覆盖，且两路的口径都不再守恒（尾差落点仍是各路自己的最大块，导致 Σ子分量 ≠ 父级分量）。
- 影响：州府级人口经济（`prefecture_demog()` 的公开 API）静默丢失一路数据；舆图州府层总面积/总人口与路级合计不符。`content/build_map_geo.py:663` 的生成器断言只在**构建期**跑，运行时无保护。
- 验证方式：`g_audit_core.py` §17
- 建议修复：删除其一（颍昌府宋属京西北路/京畿路有争议，择一并补注释），并把「治所名全局唯一」纳入 `validate_geo()`。

### G-35 [P2] `SONG_SEAT_WEIGHTS["台湾府"]` 悬空，与注释矛盾
- 位置：`content/demography.py:52` ↔ `content/geo_admin.py:349,581`
- 证据：[确认] 脚本：`SONG_SEAT_WEIGHTS 悬空键(不在任何路 members) = ['台湾府']`；`台湾 members: []`。
  而注释链条声称已落地：
  ```
  demography.py:52    "台湾府": 0.05,  # 宋代台湾不入版籍（土著，人口仅数万），整体直挂福建路
  geo_admin.py:349    # 琉球＝琉球群岛…；台湾岛已划归宋福建路(台湾府)。
  geo_admin.py:581    # "琉球" 不再 use_parts：版图为琉球群岛…，台湾省已归宋福建路台湾府。
  ```
  `demography.py:24` 自述「悬空键（不在任何路 members 中）静默忽略，不报错不阻塞」——即该权重**永远不会生效**。
- 影响：台湾府在舆图上无人口经济（`split_circuit_demog` 遍历 `area_map` 时不会出现该键），但三条注释都称已划归福建路。属「文档/注释声称已实现、代码未实现」。
- 验证方式：`g_audit_core.py` §17
- 建议修复：在 `CIRCUIT_INFO["福建路"]["members"]` 补 `("台湾府", ...)` 条目，或在三处注释标注「暂未落地」。

### G-36 [P2] `AUTHORITY_MATTERS` ↔ `CENTRAL_ORG_INFO.matter_keys` 双向不匹配
- 位置：`content/ministers/data.py:269-371`（`CENTRAL_ORG_INFO`）、`:376-403`（`AUTHORITY_MATTERS`）
- 证据：[确认]
  ```
  CENTRAL_ORG_INFO.matter_keys 未被 AUTHORITY_MATTERS 登记 (12) =
    ['京城防务','内制','内地屯驻','军务机要','军需后勤','北边防务','弹劾',
     '政令奉行','政令审议','朝政决策','禁中庶务','谏诤']
  AUTHORITY_MATTERS 未被任何机构 matter_keys 引用 (1) = ['赋税']
  ```
  而 `data.py:255` 的契约注释明写 `matter_keys 关联事权 key（见 AUTHORITY_MATTERS）`；`AUTHORITY_MATTERS` 自身注释写「事权归属表（开局，用于『改权限/越权授权』推演）」。另 `户部.authority` 含「赋税」，但 `户部.matter_keys` 不含「赋税」（`data.py:295-297`）。
- 影响：改制推演（`REFORM_TYPES` 含「改权限」「越权授权」）读取的是 `AUTHORITY_MATTERS`；机构声明了 12 件事权却不在 owner 表中 → 这 12 件事永远无法被「改权限」操作命中，属**引用了但不存在**的反向悬空（虽不抛 KeyError，但功能静默缺失）。
- 验证方式：`g_audit_core.py` §12

### G-37 [P2] 现成自检 `validate_geo()` 绿灯但漏检 G-34/G-35
- 位置：`content/geo_admin.py:1096`（`validate_geo`）
- 证据：[确认] 实跑
  ```
  validate_geo() 返回问题数: 0
  ```
  而同期脚本已证实存在「颍昌府跨路重复」与「SONG_SEAT_WEIGHTS 悬空键」两项真实数据缺陷。`validate_geo` 只校验 `REGIME_GEO` 多边形闭合、owner 注册、分路母政权注册（`:1132-1161`），不校验 CIRCUIT members 唯一性与跨模块权重键覆盖率。
- 影响：生成器（`build_map_geo.py:663,703`）依赖该断言放行坏数据。
- 验证方式：`python -c "from content.geo_admin import validate_geo; print(validate_geo())"`

### G-38 [P2] §八「角色 prompt 35+ 个」vs 实际 23（与 README 互斥）
- 位置：`游戏机制说明.md:339` ↔ `game/README.md:76`
- 证据：[确认] `Get-ChildItem ai/prompts/*.md | Measure-Object` → **23**。README `:76` 明写「`ai/prompts/`（23 个 .md：角色 prompt + decree_style_ref 拟旨文风）」。
- 影响：两份并列文档对同一事实给出互斥数字（35+ vs 23）。
- 验证方式：`(Get-ChildItem game/ai/prompts/*.md).Count`

### G-39 [P2] `data.py:176` 注释「/12」与实际代码「/3」矛盾
- 位置：`content/data.py:176` ↔ `core/game_state_econ.py:346-357`
- 证据：[确认]
  ```python
  # data.py:176（权威源内注释，错）
  LAND_TAX_RATE_BENEFIT = 0.10    # 本色率：太仓月入 = Σ各路 grain_yield_i/12 × 本色率 × 到账 × 丰歉 × 隐漏 × 水利
  # game_state_econ.py:344-357（实际）
  # 产粮集中在三运期（春3/夏6/秋9月…）：每期征收 1/3 年产，非运期不征本色。
  if getattr(self, "month", 1) not in (3, 6, 9): return 0.0, {...}
  grain_in = gy / 3.0 * LAND_TAX_RATE_BENEFIT * ...
  ```
  主文档 `:173` 写的是正确的 `/3` + 三运期。
- 影响：权威源自身的注释比外部文档还旧；读者据此推算太仓月入会差 4 倍（`/12` 是「年均摊」，`/3` 是「运期集中」）。
- 验证方式：`grep "grain_yield_i/12"`

### G-40 [P2] 图鉴文案计数/时代数过时
- 位置：`content/codex_text.py:52`（「A14 九人简介」）、`:108`（「循三时代递进」） ↔ `content/codex_data.py:86`
- 证据：[确认] `CODEX_MINISTER_BIO` 实为 **8** 条（`codex_text.py:56-65`）；同文件 `:54-55` 注释自述「原含『章惇』一条…已删」，但标题行「九人」未同步。`CODEX_TECH_OVERVIEW` 写「循三时代递进」，而 `TECH_ERAS` 有 **7** 个时代（`data.py:1893-1901`），`TECH_NODES` 覆盖 era 0~6。
- 影响：图鉴「科技总览」条目向玩家输出错误时代数；注释计数误导后续维护者。
- 验证方式：`g_audit_extra.py` §G

### G-41 [P2] 同一商品「布/绸」两套价表口径冲突
- 位置：`content/data.py:219-225`（`MATERIAL_PRICE_BASE`，注释「钱/单位」） ↔ `content/data.py:1768`（`GOODS_PRICE`，注释「贯/单位」）
- 证据：[疑似]（两表数值明确不同，是否属同一口径需设计确认）
  ```
  MATERIAL_PRICE_BASE["布"] = 120（钱/匹）   GOODS_PRICE["布"] = 1（贯/单位）     → 1.0 vs 0.12 贯，8.3×
  MATERIAL_PRICE_BASE["绸"] = 800（钱/匹）   GOODS_PRICE["绸"] = 3（贯/单位）     → 3.0 vs 0.8 贯，3.75×
  ```
  同样代指作坊产出的成品（`FINISHED_DIMS = ["绸","布","wine"]`）。`MATERIAL_PRICE_BASE` 被 `_settle_workshops`（`settlement_steps.py:2152` 等）用作产出入账折价，`GOODS_PRICE` 被 `settlement_steps.py:1702-1711` 用作库存外销变现价。1 贯 = 1000 文（`settlement_steps.py:2772` 注释）。
- 影响：同一匹布在「作坊产出折钱」与「超库存外销」两条通道定价差 8 倍，玩家可通过建作坊→外销套利（或反之完全不划算），是守恒/经济平衡的隐患。
- 验证方式：`grep GOODS_PRICE|MATERIAL_PRICE_BASE`
- 建议修复：统一到一张价表（或明确「生料/成品」「内销/外销」两套并写明换算关系）。

### G-42 [P3] §四「投资…六领域基准」vs `INVEST_BASE` 7 领域
- 位置：`游戏机制说明.md:168` ↔ `content/data.py:1633-1641`
- 证据：[确认] `INVEST_BASE` = 农业/水利/工坊/商铺/漕运/军器/**科技**（`:1640` `{"return":0.0,"risk":0.0,"rnd":True}`），共 7。
- 影响：文档漏列「科技」领域（该领域回报为 0，属特殊通道，更需说明）。
- 验证方式：`g_audit_extra.py` §D

### G-43 [P3] §一「11 步流水线」vs 实际 23 个 Step
- 位置：`游戏机制说明.md:38` ↔ `core/settlement.py:339-438`
- 证据：[确认] `settlement.py` 的 Step 序列（行号）：
  `0:339, 1:365, 2:368, 3:371, 3.5:374, 3.5.5:377, 3.6:380, 3.7:383, 3.8:387, 4:390, 4.5:393, 5:397, 6:400, 6.5:403, 6.8:406, 6.9:411, 6.10:414, 7:417, 8:420, 9:423, 10:426, 10.5:429, 11:438` = **23 个**。文档 §二 只列 19 条，漏 `3.5.5 地区模型深化`、`6.9 帝国修正`、`6.10 国策树`、`10.5 人口总账校正`。
- 影响：文档是「机制说明」的唯一完整来源，四个结算步完全无说明（其中 `10.5` 正是 `review_2026-08-31.md` P1-3 的关键修复点）。
- 验证方式：`grep -n "Step " core/settlement.py`

### G-44 [P3] 全局初值 55 未入权威源；`POP_TYPES` 等常量同属死数据
- 位置：`core/game_state.py:403` ↔ `content/data.py`
- 证据：[确认] `self.population_satisfaction: int = 55` 硬编码；`data.py` 无 `POPULATION_SATISFACTION_START`（对比 `PRESTIGE_START`/`EMPEROR_HEALTH_START` 都进了权威源）。文档 §一 `:49`、§四 `:158` 都把 55 当权威口径。
  同类：`POP_TYPES`（`data.py:257`）被文档 §四 `:158` 引为「六类人口 `POP_TYPES`」，但代码零引用（实际分层来自 `POP_SHARE`/`GOODS_DEMAND`/`GRAIN_CONSUME_PER_CAPITA` 的键）。
- 影响：中优先级初值散落在 state 层；文档指向的常量是死数据（同 D-9 模式）。
- 验证方式：`g_audit_extra.py` §A

### G-45 [P3] 历史遗留「7 人 `trait_ids` 考据补齐」仍未做
- 位置：`content/ministers/data.py`（赵挺之 :57-59、童贯 :76-78、赵桓 :109-111、唐恪 :144-146、聂昌 :147-149、何执中 :156-158、岳飞 :191-193）
- 证据：[确认] 脚本：`有 trait_ids 者 = 36；无 = 7`。`data.py:196-199` 的注释「未在素材 2.2 标注特质的大臣，trait_ids 统一补空列表（不臆造，待考据单补齐）」仍在。`persona.py:7` 头注释亦写「兼容既有 **43** 名现役」——人数已对，但 7 人缺口未动。
  **好消息**：`TRAITS` 键集合与 `trait_ids` 实际引用集合**完全相等**（双向零差集），`TRAITS[*].note` 的「代表」名单与 `MINISTERS[*].trait_ids` 逐条吻合（13/13 全对），历史上「图鉴死键/特质悬空」类问题已修好。`DEPARTURE_RULES` 6 条（贬黜/致仕/病故/战殁/处死/乞休）齐备，`FATE_MARKS`「战殁」正确地未被任何 `trait_ids` 引用。
- 影响：7 人与全部特质机制无关（`traits_of()` 返回 `[]`），其中含童贯（皇党集团领袖）、赵桓（皇长子）等主要角色。
- 验证方式：`g_audit_core.py` §11
- 建议修复：按 2026-08-18 第五轮待办补齐考据，或明确降级为「无机制特质」。

### G-46 [P3] 岁币口径遗留未修（全折贯）
- 位置：`content/data.py:1813`、`core/settlement_steps.py:2918-2919`
- 证据：[确认] `SUI_GONG_ANNUAL = 300_000  # 岁币岁赐年支出基准（贯）`；结算 `sui_gong += int(SUI_GONG_ANNUAL * 0.6 / 12 * _mult.get("辽", 1.0))`（西夏 0.4）。`audit_dimension_report.md:55` 记录裁决遗留：「史实澶渊之盟为银 10 万两 + 绢 20 万匹。若七维物资含绢匹，岁币应拆两/匹两维（audit-core 已标，未在此轮裁决）」。现 `RAW_UNITS` 已有「绸」「布」= 匹（`data.py:265`），技术条件已具备，仍未拆。
- 影响：岁币以「贯」口径外流，与「银/绢两维」的货币-实物守恒链不自洽；主文档 `:188` 也只写「（年 30 万贯）」。
- 验证方式：`grep SUI_GONG_ANNUAL`

### G-47 [P3] 第五套档位表 `asset_context` tier_map
- 位置：`core/asset_context.py:247-248`
- 证据：[确认]
  ```python
  tier_map = {"无": 0.0, "微": 0.08, "小": 0.15, "中": 0.25, "大": 0.40}
  val = tier_map.get(inv.get("effect_tier", "微"), 0.08)
  ```
  与 `content/data.py:1361-1369` 的 `TIER_RANGE`（0.25/0.5/1.0/1.5/2.0/2.5）语义不同（比例 vs 倍率），但**同为 5 档词→数值**映射，且只覆盖 5 档（AI 出「巨/极」落 `0.08`）。
- 影响：AI 献策生成节点时，档位强度与其余系统不在同一刻度；「巨/极」被静默降为「微」。这是 `BOOM_MULT`/`EXAM_HARD_POOR_SHARE` 之外第三处未补 7 档的地方。
- 验证方式：`grep tier_map core/asset_context.py`

---

## 附：修复良好、本轮确认无缺陷的项（避免重复上报）

| 历史项 | 复核结论 | 证据 |
|---|---|---|
| R2-18 文档/契约校正 | 部分已做（`codex_data.py:184` 的「12 路→20 路」、`codex_text.py:98-102` 死键改挂真实节点）；但 G-7/G-8 等数字未跟 | `g_audit_core.py` §10 |
| TIER_RANGE 迁入 `data.py` | ✅ 已迁，且 `TIER_ORDER == list(TIER_RANGE) == list(TIER_ALIAS)` | `g_audit_core.py` §5 |
| `EXAM_HARD_POOR_SHARE` 补 7 档 | ✅ 7 档齐全（含巨/极） | 同上 |
| `FINANCE_DECIDE_BASE` 单一权威源 | ✅ `settlement_steps.py:974 _fdb = FINANCE_DECIDE_BASE`，无第二份 | `grep FINANCE_DECIDE_BASE` |
| 外邦 `type` 注册 | ✅ `EXTERNAL_REGIMES` 的 31 个 type 全部在 `_EXTERNAL_POP_SHARE_BY_TYPE` 内；占比 Σ=1.0 全部成立 | `g_audit_core.py` §13 |
| 图鉴死键对齐 | ✅ `CODEX_TECH_NOTE` 5 键全为真实 `TECH_NODES` id；`CODEX_ORG_DESC` ↔ `CENTRAL_ORG_INFO` 全覆盖；`CODEX_REGION_NOTE` 20/20；`CODEX_BRANCH_DESC` ↔ `BRANCH_BASE` 7/7；图鉴 8 类键与 `_BUILDERS` 完全一致 | `g_audit_core.py` §10 |
| 州层 Σpopulation 与全局锚差 7%（量纲报告遗留） | ✅ 已修：Σ=80,000,000 == `SALT_POP_BASE` == 文档 8000 万；Σhouseholds=20,000,000 == `LAND_INFO.households`；户均 4.00 口 | `g_audit_core.py` §2 |
| Σmonthly_tax 注释锚 | ✅ 实测 Σ=5,480,000，与 `data.py:169` 注释「≈5_480_000」精确相符 | 同上 |
| `SALT_CAPACITY_BASE` 锚 | ✅ 实测 Σsalt=185,000,000，与 `SALT_CAPACITY_BASE` 精确相符 | 同上 |
| `ARMY_UNIT_INIT` 站名/合计 | ✅ 12 路全为 `PREFECTURE_LIST` 成员，Σ=750,000（= 注释「75 万」），非零军籍 35 支（= 文档「12 路 35 支」） | `g_audit_core.py` §1、§3 |
| 派系领袖 | ✅ 6 派 leader（蔡京/韩忠彦/童贯/种师道/曾布/陈瓘）全部在 `MINISTERS` 且 `faction` 字段自洽 | `g_audit_core.py` §11 |
| `MINISTERS` 人数 | ✅ 43 == 文档 §六「约 43 人」 | 同上 |
| `TRAITS`(13) ↔ `trait_ids` 覆盖 | ✅ 双向零差集，note 代表名单 13/13 吻合 | 同上 |
| `ARMY_UNIT_SPLIT` / `GOODS_DEMAND` / `EVAL_WEIGHTS` / `_EXTERNAL_POP_SHARE_BY_TYPE` / `_EXT_POP_DEFAULT` / `_EXTERNAL_ARM_*` | ✅ 全部比例和 = 1.0（脚本逐表断言） | `g_audit_core.py` §4、§13 |
| `ERA_BUILDING_LINK` 死键（P2-55） | ✅ 10 键全部对应真实建筑闭集，值全在 `ERA_DIMENSIONS` | `g_audit_core.py` §14 |
| `BUILDING_BLUEPRINTS` / `TECH_BUILDING_MAP` | ✅ 键全为真实 `TECH_NODES` id（`TECH_BUILDING_MAP` 的 semantic 键由 `codex_data._semantic` 正确转译）；`need_node == key` 全部成立 | 同上 |
| 科技树 | ✅ 45 节点、id 无重复、line 全在 `TECH_LINES`、era 0~6、前置 id 全存在、**拓扑无环**、`DEFAULT_UNLOCKED` 9 项全覆盖 | `g_audit_core.py` §15 |
| `EXTERNAL_FORCES` / `EXTERNAL_PROVINCES` 权重 | ✅ 各省份权重和 = 1.0；`external_provinces_of()` 归一化后和 = 1.0 | `g_audit_core.py` §13 |
| 前端导出物新鲜度 | ✅ **全部新鲜**：`constants.json`/`codex.json`/`focus_tree.json`/`ministers_dict.json` 在内存重算后与磁盘**逐字节等价**（无过期产物）；图鉴 8 类齐全（含 mechanism 5、event 24） | `g_audit_exports.py` |
| 事件压力阈值 80 / 密旨泄露 20% / 施恩 +7−20万 / 省浮费 12~18月·5~15万 −2威望 / 常平仓 1.6 / LRU 64 / 区间脱敏参数 | ✅ 文档与代码逐值一致 | 见漂移表 A 区 |

---

## 附：本轮实际执行的验证命令与脚本

三个脚本均落在 `D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\`，**不写 game/ 下任何文件**：

| 脚本 | 作用 | 输出 |
|---|---|---|
| `g_audit_core.py` | 20 组核心对拍：路级键集合、算术恒等式、兵额、比例求和、7 档闭合、RESOURCE_DIMS/POP/codex 键集合、大臣自洽、家产机构、外部政权、建筑/科技、geo_admin、死常量扫描、文档数值断言 | `g_audit_core.out.txt`（492 行） |
| `g_audit_extra.py` | 真·死常量精确扫描（定义行除外）、影子副本定位、档位缺档、事件类别对齐、军事/投资参数、codex 计数 | `g_audit_extra.out.txt`（142 行） |
| `g_audit_exports.py` | 前端 4 个导出物新鲜度对拍 + Python↔Rust 36 项常量三处对拍 | `g_audit_exports.out.txt` |

复现命令（PowerShell，注意 cwd 与环境变量）：

```powershell
$env:PYTHONPATH=''; $env:PYTHONIOENCODING='utf-8'
Remove-Item Env:CODEBUDDY_TOOL_CALL_ID -ErrorAction SilentlyContinue
Remove-Item Env:CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR -ErrorAction SilentlyContinue
cd D:\codebuddy\sz\_dev_tools\_scratch\audit-2026
& D:\codebuddy\.audit-venv\Scripts\python.exe g_audit_core.py
& D:\codebuddy\.audit-venv\Scripts\python.exe g_audit_extra.py
& D:\codebuddy\.audit-venv\Scripts\python.exe g_audit_exports.py

# 现有防线（实跑均非常态）
& D:\codebuddy\.audit-venv\Scripts\python.exe "D:\codebuddy\sz\_dev_tools\game-docs\analysis\check_docs_constants.py"     # → ModuleNotFoundError (exit 1)
$env:PYTHONPATH='D:\codebuddy\sz\game'
& D:\codebuddy\.audit-venv\Scripts\python.exe "D:\codebuddy\sz\_dev_tools\game-docs\analysis\check_docs_constants.py"     # → 4 处漂移 (exit 1)
Remove-Item Env:PYTHONPATH

# 自检与单点验证
cd D:\codebuddy\sz\game
& D:\codebuddy\.audit-venv\Scripts\python.exe -c "from content.geo_admin import validate_geo; print('problems:', len(validate_geo()))"
& D:\codebuddy\.audit-venv\Scripts\python.exe -c "from core.evaluation import _get_outcome_desc; print(repr(_get_outcome_desc('身死国灭')))"
(Get-ChildItem "ai\prompts\*.md").Count
```

**未执行/受限于权限或环境、仅靠静态阅读判定的项**：Rust 逻辑深审（归另一审计员）；`import` 级 pytest 全量回归（不在本任务范围，且 `_dev_tools/game-dev/tests/` 未跑）。
