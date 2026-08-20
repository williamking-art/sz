# 会话进度快照（2026-08-17 · POP 经济重构）

> 用途：上下文恢复用。本会话从「审一遍游戏」开始，完成了一次 POP 经济重构。此文件记录当前状态与遗留，后续会话读此可快速续接。

## 一、本次会话做了什么

从一次代码审查出发，最终完成了**维多利亚式 POP 经济重构**，全部落地、pytest 24/24、36 月回放稳定（民心 49、国库 ~800万、米价 1.4）。

### 主要里程碑（按顺序）
1. **代码审查**：产出 `analysis/code_review_report_2026-08-17.md`（P0/P1/P2 清单）
2. **单位统一**：后台去万（贯/石/户/口/亩真实单位），UI 展示层可换算"万"（`ui/format_units.py`）
3. **人口统一**：12 路户数归一 2000 万户、人口 8000 万口、户均 4 口；隐户 500 万（UI 不显示）
4. **粮产/田亩**：亩产分路（北1.0/南2.5）、经济作物占田（北10%/南20%细分产物）、三运期产粮、废弃 grain_yield×12
5. **POP 模型**：6 类（农/士绅/工匠/商人/官僚/兵）× 每路 {人数,钱,粮,商品}，粮市/商品市/财政/金融/政策六阶段
6. **田亩归属**：自耕田40%/地主田50%/官田8%/皇庄2%/隐田25%，产粮按归属分配
7. **士绅经济**：囤粮（AI 推演+上限）、卖粮（AI 推演）、窖藏（50%退出流通）、交地主田赋
8. **税基 POP 化**：工商税=产值流量、役钱=农丁口、二税折色=税粮×折色率
9. **AI 推演**：economy_decide（景气/士绅/生产）、survey_settle（方田均税）、register_raw_material/finished_good（新作物新商品）
10. **清理**：删废弃代码（TENANT_RATE、hoard_decide、_local_policy_signing、LOCAL_ACTS）+ 29 个 tmpdir

## 二、关键设计决策（用户确认的口径）

- **后台去万、UI 可换算万**；文（0.001贯）只存在于物价体系，国库整数贯
- **AI 输入精确值、输出档位、程序换算**（推演波动，非"皇帝模糊认知"）
- **粮是田产的**（按田亩归属分配），不是人产的
- **士绅纳税**：田赋按田归属（地主田赋由士绅交）；隐田逃税；诡名寄产；官户免役
- **坊郭户不服乡村差役**（役钱只从农征），科配并入工商税
- **士绅囤粮有上限**（=士绅田产年产）、卖粮 AI 推演、窖藏藏富
- **政策效果 AI 推演**（方田均税清隐田/退田力度）
- **新作物/新矿/新商品预留接口**（玩家后期经 AI 开发）

## 三、当前数值锚

| 项 | 值 |
|---|---|
| 人口 | 在籍 8000万 + 兵75万；隐户 2000万 |
| 田亩 | 在册 4.68亿（自耕40/地主50/官田8/皇庄2）+ 隐田 1.17亿 |
| 粮产 | 7.2亿石/年（亩产北1.0/南2.5，扣经济作物） |
| 人均口粮 | 0.3石/月 |
| 俸饷(月) | 军粮2石/饷0.5贯、官禄15石/俸30贯、吏禄1.5石/俸2贯 |
| 税率 | 工商5%、役钱10%、折色40%、盐榷利0.045贯/斤、地租=佃户50%×50% |
| 收支 | 月入~207万 ≈ 月出~207万（平衡） |

## 四、遗留问题 / 待办

1. ~~长期通胀~~ **已解决**：士绅卖粮当场窖藏 80%（钱退出货币体系）+ 奢侈消费 5%/月，物价稳定 0.5~0.96、米价 0.5~1.67 正常波动（60 月验证）。
2. **存档兼容**：POP 重构后旧档未做兼容（用户明确"存档不用管"）。
3. **UI 展示 POP**：POP 的 size/wealth/grain/goods 还没在 UI 面板展示。
4. **灾荒/流民接入 POP**：现有 disaster/refugee 机制未接 POP（农 POP 缺粮→流民）。
5. **交子超发→贬值**：交子 issued×信任度入货币，但超发贬值逻辑未做。
6. **市舶白银**：商人 POP 外贸未完全接入。
7. **旧 policy 函数**（local_policy/reform_policy 等）：面板移出后是死代码，但为 AI 叙事方法宿主，暂留（后续 AI 拟诏落地政策可能复用）。

## 五、改动文件清单（git status 未提交）

- **修改**：core/settlement_steps.py、game_state.py、game_state_econ.py、commands.py、commands_decree.py、commands_policy.py、save_load.py、settlement_extensions.py、events.py、asset_context.py；ai/client.py、client_utils.py、decree.py；content/data.py；ui/panels_*.py、gui.py、gui_common.py、format_units.py；backend/client.py
- **新增**：ai/prompts/economy.md、survey_settle.md；analysis/pop_economy_system.md、code_review_report_2026-08-17.md、progress_snapshot.md(本文件)；ui/format_units.py
- **删除**：ai/prompts/hoard.md；29 个 .tmpdir 空目录

## 六、核心文档

- `analysis/pop_economy_system.md`：POP 经济体系完整整理（十节）
- `analysis/code_review_report_2026-08-17.md`：审查报告（P0/P1/P2）
- 本文件：进度快照

## 七、测试状态

pytest 24/24 通过；36 月多种子回放稳定（seed 2026/7/42 结果一致）。

---

## 八、第二轮：专家团审查 + P0/P1 全修（2026-08-17 晚）

4 名专家（蔡权衡/谷承构/言枢密+沈舶司/严归正）并行审查，共 10 P0/28 P1/27 P2，详见 `analysis/expert_review_report.md`。已修复：

**P0（10 全修）**：会计录 ImportError、流民 6 亿爆炸（spill 符号）、田赋 140% 双征、月报 raise 双月推进、imperial_granary/mechanisms 丢档、旧档 pops 崩、粮食 3.1×年耗膨胀（口粮 0.5+存粮入供给）、士绅窖银永动机（囤粮上限 ×0.2+窖银回流+士绅折色税）、posture 泄精确值（四档脱敏）、economy_decide 滞后。

**P1（11 修）**：灾荒减产、交子信用悬崖（divisor 100 万）、一体发钞双发、兵 POP 漂移（重聚合）、TIER_RANGE 迁 data.py、core 顶层 import ui 潜伏环、开局饥荒（农存粮 ×2）、折色税士绅分摊、囤抛方向（高价不囤）、物价石贯混加（粮×粮价）、士绅奢侈 10%→5%。

**后续新增**：商品消耗机制（5%/月折旧）、全 POP 有钱就消费（wealth 弹性消费率）、POP 职业流动（农⇄工匠商人 城市化/回乡）。

**60 月回放现状**：民心 37、国库 516 万、物价 2.30（温和通胀）、米价 2.30、流民 72 万、士绅囤粮 1.08 亿（上限生效）、农存粮 5.8 亿。

**尚存**：长期温和通胀（货币总量慢增长：税短收印钞、士绅卖粮造钱）；POP 逻辑零测试覆盖（24 条全绿但都不碰 POP，建议补钱粮守恒/Σpops/囤粮上限/灾荒流民断言）。

---

## 九、第三轮：CodeBuddy plan 执行（拆文件/补测试/扩内容/AI 打磨）

依据 CodeBuddy CN 的 plan（`C:\Users\ma_li\AppData\Roaming\CodeBuddy CN\...\plan.md`）执行，按"先补测试→再拆文件→再扩内容"顺序。**镜像同步（SongZuo/_internal）跳过**（当前环境无该镜像目录）。

### 1. 拆巨文件（re-export 保持调用兼容，-681 行）
- `core/settlement_finance.py`（_settle_finance/_recalc_region_price/_avg_corruption）
- `core/settlement_disaster.py`（_settle_disaster/_normalize_disaster_region）
- `ai/client_narrative.py`（ClientNarrativeMixin：9 类部门叙事 + _narrative_call）
- `content/data_desensitize.py`（11 个 desensitize_* 函数族）
- 效果：settlement_steps 1410→1061、ai/client 893→755、data 1222→1028

### 2. 补测试（24 → 49）
- `tests/test_desensitize.py`（10 条）：区间脱敏/机构精度/噪声/滞后/米价趋势
- `tests/test_ai_contract.py`（10 条）：档位换算/封顶/效果字典/白名单 17 键
- `tests/test_identity.py` +5 条：存档往返/回放确定性/士绅囤粮上限/抛粮守恒/税不抽干

### 3. 扩内容
- 随机事件 +5（黄河秋汛/太学三舍法/市舶贡使/常平籴粜/西军乏饷）
- 科举入仕（士绅 → 官僚 0.01%/月微量流动）

### 4. AI 打磨
- 自动存档（每年正月 + 游戏结束写槽 0）

### 验证
pytest 49 passed；check_docs_constants OK（常量零漂移）。

### 未做（plan 剩余，收益低/风险高）
1. UI panel 拆分（panels_govern 883 行/panels_economy 794 行，Tkinter 风险高）
2. 大臣特质/离任影响、外部政权科技节点（需史实素材）
3. posture 全区间化、认知层多级滞后、查账代价动态化（AI 体验，发散）

---

## 十、当前全局状态速查

- **测试**：pytest 49/49 通过
- **大臣**：43 人（新党12/清流9/西军7/东南5/旧党4/宦官4/皇子2，12 人在野未生）
- **提交**：`5ca8128`（本轮）+ 之前 `a4310eb`/`72f962f` 等
- **工作区**：干净
- **权威文档**：本快照 + `pop_economy_system.md` + `expert_review_report.md`

**下一步候选**（任选）：继续 plan 剩余（大臣特质/UI 拆分/posture 区间化）；或处理长期温和通胀（税短收记欠税科目）；或扩事件/大臣史实素材。

---

## 十一、第四轮：专家团执行 POP 经济收尾（2026-08-18）

依据 `_dev_tools/songzuo-game-studio` 专家团（12 席 subagent 加载）执行，主理人邹运筹路由，收敛快照遗留待办。

### 完成项
1. **A1 长期温和通胀修复**（量化定案：F1 士绅卖粮凭空造币 = 货币增量 104%，唯一造币源；印钞实为 0；税短收=记账缺口非造币）：
   - B1 抛粮买方化 + 买方得粮（钱粮双向守恒）
   - A 欠税科目（ARREARS_COLLECT_RATE=0.2 追缴）
   - C 发钞单发化（jiaozi.issued += personnel_cash）
   - 开局校准 START_MONEY_BOOST=170M（蔡权衡定案，注入民间 wealth）
   - 支出回流（常费→工匠40%+商人60%、贪腐→官僚、岁币保留销币）
   - 超上限软约束（HOARD_CAP_MULT=0.3，软/硬双 cap：超软未售保留、超硬 3% 核销）
   - 奢侈品支出率 5%→1%（防 B1 后士绅破产）
   - 窖银机制（用户 4 条史实指示）：30%流通+70%窖藏、**只藏铜钱不藏纸币**、**AI 档位决定动用**（HOARD_DRAW_RATE，无 AI 冻结）
2. **A2 POP 测试**：`tests/test_pop_identity.py` 20 用例（Σpops/钱粮守恒/灾荒流民/交子市舶四类断言）
3. **灾荒流民守恒双修复**：赈济安置回流农 POP（BUG#1）、灾荒新发从农扣减（BUG#2）
4. **A3 大臣特质/离任**：TRAITS 13 键 + DEPARTURE_RULES + apply_minister_departure（36/43 trait_ids）
5. **A6 内容扩展**：5 张史实事件卡（三标签+篇/卷出处）+ 大臣特质素材；事件落地（档位词换算层）
6. **AI 窖银档位**：economy_decide 新增「窖银」字段（言枢密）

### 关键史实决策（用户确认）
- 士绅窖银 = 藏富·死钱，**不到最后不用**，**AI 决定用不用**
- **纸币（交子）不能窖藏**（有界贬值），窖银只藏铜钱
- 粮钱循环：**粮卖钱 → 钱买粮 → 粮被消耗**（太仓发本色俸禄是「转移」非「消耗」，兵/官/吏吃掉才是消耗）

### 最终状态
- pytest **81/81 全绿**（49 → 81）
- 60 月回放（seed_offset=2026）：开局物价 1.069、60月末物价/米价 1.032、货币漂移 -2.9%、窖银 1473万、国库 +1158万

### 排除 / 待办
- 排除：存档兼容（用户不用管）、外部政权科技节点（用户不做）、UI 拆分 / AI 体验（用户跳过）
- 待确认：奢侈品 5%→1%（用户问过理由，未定是否改回 5% 或走替代方案）
- 未落地：特质×事件联动（素材 2.4）、7 人 trait_ids 考据补齐

---

## 十二、第五轮：AI/agent 化重构 + 工具配置（2026-08-20）

### 游戏机制（pytest 145 全绿）
- **全游戏强制 AI**：free_effect 契约（once/ongoing + 白名单 + CAP + 拒绝式）+ 18 模板 validator 拒绝式 + AI_ERROR_CODES 6 码 + UI 提示（AI 缺失 → 不执行 + 明确报错，不伪造）
- **记忆知识库**（memory/memory_graph.py）：实体/关系图谱 + 衰减 λ + 检索 + 槽位写盘 + 损坏重建 + 9 写入入口 + 召对/拟旨/月报注入；两层记忆（短期日志 append-only 不注入 + 长期图谱选择性注入）
- **persona 0-100**（content/ministers/persona.py）：六维人格 + baseline_stance（史翰青史实复核）+ 程序化立场演化 + 阳奉阴违危险度 + 忠诚隐藏；大臣家产（钱+田 1101 基线 + 膨胀机制 + 靖康籍没锚点验证）
- **省 token**：query_state 按需查询（召对注入 -98%）+ 本地计算优先（AI 保混沌）+ 档位词 7 档（无/微/小/中/大/巨/极 + 丰富表达归一）
- **融入 Ming 菁**：叙事-数值校验（narrative_guard）+ 来源闭集 + 人物校验表 + 工具落档铁律 + 大臣自设工具（tool_registry）
- **12 步 agent 化**：推演官（经济+金融 5 字段）/按察使（清丈+灾荒）/使节（外交）/枢密（军事）/史官（事件+长期政务），守恒步本地
- **经济金融 AI**：交子/钱荒/市舶/银行/物价趋势 AI 方向档 + 程序记账
- **建筑**（政府 projects + POP 路级 buildings Lv1-5 乘数）+ **投资**（invest_decide 四账闭合）
- 军队模型重构：每路禁/厢/乡 35 支 + BRANCH_STD 按率粮饷 + 装备按人头 + 宋制番号 + 内帑口谕调拨

### 工具配置（会话内）
- **CloudBase**（帮助开发，不接游戏）：Skills + tcb CLI 3.7.3 + 环境 william-d6gbq46nl4bd4e950
- **codebase-memory-mcp** v0.10.8：CodeBuddy 完整配置（mcp.json/CODEBUDDY.md/agents/skill）+ 索引 G-sz-game（4009 节点）；DSH 内用 CLI 查询
- **专家团 12 席** subagent 已加载

### 文档更新
- `docs/游戏机制说明.md`（融合式更新：AI 架构总览 + 各章融合新机制）
- `README.md`（定位/架构/目录/模块职责/运行匹配）
- `analysis/pop_economy_system.md`（融合金融 AI/家产/建筑/投资）
- `analysis/refactor_plan_ai_harness.md`（harness 化重构计划 + 执行进展）

### 待办
- 12 步 agent 化 P2+（其余步位）/ 徽宗朝新番号 / 特质×事件联动 / P0 混沌运算（派系+党争、外邦态度）
