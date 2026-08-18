# 《宋祚》全量代码审查报告（2026-08-17）

> 审查对象：`G:/sz/game` 当前工作区（含未提交的单位制迁移改动）
> 审查方式：core/AI/UI 三层并行源码走查 + 确定性回放实证（探针脚本，seed 固定）+ pytest（24/24 通过）
> 结论口径：按「当前工作区实际行为」判定，不以文档声明为准

---

## 〇、总体结论

游戏骨架完整、分层清晰、可运行（24 项测试通过、36 个月回放无崩溃），但存在 **1 个 P0 平衡问题、若干 P1 必现逻辑错误**，且相当一部分是「万→石/贯 单位制迁移」进行到一半的遗留产物（工作区有 16 个文件未提交的迁移改动）。修复顺序建议：先修 P0 财政失衡与 P1 单位错位族，再修 AI 工具链与 UI 崩溃点，最后做数据口径归一。

---

## 一、P0：财政系统失衡，国库三档难度全部暴涨

**实证**（seed=2026，36 个月，走真实 `advance_month`+`settle_turn`）：

| 难度 | 开局国库 | 36 月后国库 | 月均净入 |
|---|---|---|---|
| 轻松 | 500 万贯 | 17,640 万贯 | +476 万贯 |
| 史实 | 500 万贯 | 13,658 万贯 | +365 万贯 |
| 艰难 | 500 万贯 | 9,582 万贯 | +252 万贯 |

- 史实难度 12 个月净增 4700 万贯（`_settle_finance` 月入约 656 万 vs 月出约 266 万）。
- 后果：`TREASURY_CRISIS_LINE(-500万)` 与 `TREASURY_COLLAPSE_LINE(-2000万)` 在正常游玩中**永不可达**，「库藏空虚」危机事件、破产兜底、国库维度评分（>1000 万即 90 分）全部失去意义，财政压力从游戏中消失。
- 根因（相互叠加）：
  1. 二税折色月入 307 万贯（12 路 `monthly_tax` 锚合计 548 万贯/月 × 到账率 0.56 × `TAX_COLOR_RATE=1.0`）——折色比例 1.0 是否迁移后失真需裁决；
  2. 工商税月入 269 万贯（3.5 亿基数 × 征率 0.15）；
  3. 支出侧被 `PAY_CASH_BASE=200万/月` 兜底，而实际 `personnel_cash≈136万/月`（见 P1-1 的贪腐归零进一步压低支出）；
  4. 太仓常年满仓（1879 万/2000 万石触顶，月入 430 万石 vs 月耗 ~170 万石），赈济/常平/仓储机制失去空间。

---

## 二、P1：必现 / 高概率触发

### 经济与单位迁移族

1. **`calc_pay_ratio` 未随单位迁移，`pay_ratio` 恒为 1.0 → 吏俸缺口与贪腐扣减机制整体失效**
   - `core/game_state_econ.py:364`：`due = officials*30/10000 + clerks*2/10000`（仍 ÷10000，而同函数 374 行 `qdue` 已去 ÷10000，两者不一致）；`local_finance` 初值取自 `storage`（石），与「贯」口径错位。
   - 实测：所有路 `pay_ratio=1.0`，`calc_clerk_gap()=0`，`calc_corruption_deduction()=(0,0)`。→「厚禄养廉」「肃察吏弊」两项改革空转，`test_corruption_payraise_feedback` 因 gap 恒 0 而"通过"（空转测试）。修好此项后需重跑财政平衡（见 P0）。
2. **一条鞭折银方向错误**（`core/settlement_steps.py:333`）：`silver_tax = land_grain / grain_price`，应为 `land_grain × grain_price`（石 × 贯/石 = 贯）。米价 2 贯/石时折银仅正确值的 1/4，米价越高折银越少，方向反直觉。同文件 `granary_policy` 的「折变」（`commands_policy.py:576`）同源错误；而「和籴」「he_mi」已改为乘法——同一套代码里乘除方向并存。
3. **常平仓单位错位**（`core/settlement_steps.py:550-566`）：平粜卖 8 石入账 `8×price×10000` 贯（实测 1.7 贯/石时入账 13.6 万贯，应 13.6 贯）；平籴 `treasury//10000//price` 花 6 万贯只买 6 石。**卖粮多得 10000 倍钱、买粮只得 1/10000 粮**，且 `st>=5` 阈值（石）恒满足 → 高价月可白嫖巨款。
4. **作坊 grain_feed 被 `recipe.pop()` 销毁**（`core/settlement_steps.py:781`）：`recipe` 是存档中的持久 dict，首月 `pop` 后键消失，次月起酒坊不再耗粮、白嫖产出（实测次月内帑继续 +1200 贯而太仓不再减）。
5. **太仓恒等断言存在潜在崩溃路径**（`core/settlement_steps.py:545-547`）：`out_total = sparrow+given+corr_grain` 未随 `change_granary` 的 0 下限钳制收缩；当前因贪腐=0 不触发，一旦修好 P1-1，太仓枯竭时可能 `AssertionError` 直接崩结算。

### 军事与评价

6. **武功维度恒满分**（`core/evaluation.py:34`）：`avg_def = Σgarrison/4`（真实兵额 ~19 万人）代入 `(avg_def-50)*0.3`，任何防线有兵即 clamp 到 100。实测七维评分武功恒 100。
7. **金军南侵战斗量纲不对等 + 触发条件过苛**（`core/settlement_steps.py:1077-1118`）：我方战力为绝对战力（实测北线 20 万+），金方用 0~100 指数 `power`（30~52）→ `winrate≈99.97%`，必大胜、不破防；且触发需 `invasion_will≥90`，正常局 1122 年累计仅 17~67 → 战斗几乎永不触发。**靖康结局只能靠收束年/驾崩/退位/国库崩坏达成**；`check_game_over` 的「京城陷落」阈值 10 人 vs 东京禁军 ~10 万人，同样形同虚设。
8. **`no_jingkang` 改写位条件过宽**：`_evaluate_timeline_breaks` 中 `army_str = 总战力/1000`，开局北线即 ~200+，配合威望 70 与 will<40（开局 0）即可入候选，无需任何经营。

### AI 叙事管线（子代理深审 + 复核）

9. **召对工具流程：第二轮生成结果被丢弃**（`ai/client.py:456-484`）：模型调用工具后，第二轮若返回纯文本（正常情况），`raw2` 非 dict → 不 return → 落到第三轮**不携带工具结果**的调用，工具办差结果从不进入回奏，且每次多烧一轮 token。
10. **多轮召对失忆**：`dialogue_history` 存 `(说话人, 文本)` 元组（`game_state.py:342`），`_call` 要求 `{role,content}` dict（`client.py:299-301`）→ 全部被跳过，每轮召对都是"初次见面"。
11. **大臣工具建草 effects 契约与全管线冲突 → 会签下发必崩**：工具 schema 声明 `effects` 为 `{dim: 档位}` dict（`client_utils.py:181/222`），而 `effects_to_dict` 要求 `[{dim,tier}]` 列表（`client_utils.py:648`）→ 对 dict 迭代得到字符串键，`e.get("dim")` 抛 AttributeError，穿透到 `issue_edict_from_review`（无异常处理）。
12. **安全过滤双向问题**：`scenes[].text` 不在过滤白名单（可绕过）；敏感词库含「屠城/凌迟/砍头」等**北宋题材正常词汇**，命中即整段替换为固定文案，金兵南侵、靖康叙事会被整体吞掉。
13. **效果契约与执行器不一致**：御笔直发白名单 `_EFFECT_WHITELIST` 仅 6 键，`_apply_decree_effect` 实际支持 ~25 键 → AI 拟诏给的 `relief/granary_reform/single_whip` 等键被 `_normalize_decree_effects` 静默剔除。
14. **事件缓存 × 复读检测互咬**：事件 desc 为静态文本 → 同类事件二次触发命中缓存 → 输出与上次逐字相同 → 相似度>0.6 被复读检测判为 fallback → 第二起同类事件无叙事。缓存亦非 LRU（>64 整体清空）、键不含 model/base_url（换模型后旧结果命中）。

### UI 层（子代理深审 + 复核）

15. **`self.self.messagebox` 33 处误写**（`panels_meta.py` 9 处、`panels_govern.py` 15 处、`panels_economy.py` 9 处）：`SongZuoApp` 无 `.self` 属性，任何点击即 `AttributeError`，由 `report_callback_exception` 弹「运行中出现异常」错误窗顶替预期提示，部分操作后端已生效（如诏令已下发）。
16. **两套浮层系统共享 `_active_overlay` 互相摧毁**（`panels_basic.py:218` vs `panels_core.py:279`）：拟旨面板内点「批改/廷议」→ `_overlay` 先 destroy 拟旨卡片 → 随后 `_refresh_list()` 对已销毁控件操作 → `TclError: bad window path name`，动作已生效、界面错乱。
17. **主菜单读档不重建游戏主界面**（`panels_meta.py:61-68`）：`_build_game_screen`（地图/HUD/dock/回合推演按钮）仅在新开局路径调用 → 「继续游戏/读取存档」后无推进按钮，游戏无法继续。
18. **`_status_canvas` 从未创建 + `theme.shade` 不存在**（`panels_core.py:413/453`）：状态条（国库/内帑/民心/皇威/军备五条）整段死代码。
19. **米价显示取倒数颠倒**（`ui/format_units.py:52-57`）：`humanize_grain_price` 把内部 贯/石 当 石/贯 取倒数 → 0.81 贯/石显示为「1.235 贯/石」，1.18 显示为「0.847」，数值全反。

---

## 三、P2：轻微 / 一致性 / 潜在

### 数据口径（含上轮审计遗留）
- **12 路户数合计 9990 万 vs 全国基准 2000 万**（差 5 倍，上轮审计 P2 未修，仅改了单位注释）；12 路人口 4995 万 vs 全局 8000 万；且 `population = households//2` 使户均 0.5 口倒挂。同一 UI 内「朝堂一览」显示在籍 2000 万户、「州县」逐路合计 9990 万户，自相矛盾。
- **两浙路 `officials:2 / clerks:16` 残留测试值**（`content/data.py:609`），按公式应为 3348/26784，导致该路官俸结算失真 ~1600 倍。
- **旧档兼容兜底失真**：`save_load.py:323-324` 旧档缺 `officials/clerks` 一律 `setdefault(1)/setdefault(8)`（新档派生为 2000~3300 级）；`ArmyUnit(**d)` 无字段过滤，含废弃字段的旧档读档 TypeError。
- **审计回放脚本仍未修**（`analysis/audit_dimension_replay.py:74`）：时间仍冻结在 year=1000（`run_monthly_settlement` 已自推月份，但脚本每轮强制覆盖）、trajectory 仍在循环外重复写 12 遍——上轮 P0 项只改了单位标签，未改实质。

### 游戏机制
- **`_trigger_event` 事件无清除机制** + `resolve_event` 的 `title not in message` 匹配不上（`title` 不在 desc 里）→ `active_events` 无限累积，「当前事件」列表越滚越长。
- **太仓常年满仓**（1879/2000 万石触顶）：赈济、常平、扩建仓储在多数局面无实际作用。
- **`grain_yield = grain×12` 语义矛盾**（`game_state.py:305`）：grain 注释「石」为年产量时 ×12 无意义；若 grain 为月产量则注释错。需作者明确单一口径。
- **国库变 float**：`_settle_finance` 的 `net` 为 float 直接 `+=`，存档写入浮点贯（`8935252.5447`）。
- **长期诏令 `active_decrees` 次月被整体清空**（`settlement_steps.py:77`）：`duration>0` 的 pending 诏令只生效一次即消失，无逐月推进（当前所有 decree duration 恒 1，暂未踩中，属潜伏缺陷）。
- **口谕 `treasury` 效果 +24 万贯/道**：档位换算 × `KOUYU_EFFECT_MULT` 后一道口头言辞凭空入账，量纲偏大。
- **`_settle_mechanisms` 的「运票」写 `land["canal_eff"]` 死字段**，`_settle_granary` 用的是局部变量，机制无效。
- **`_init_local_refugees` 边镇判定字符串不匹配**（`game_state.py:59` 判「边镇路/沿边路」，data 里实际是「缘边重镇」等）→ 边镇流民基准分支永不命中。

### AI / 配置
- `advice.md` 占位符 `{era_name}` 残留（`client.py:815` 未传该参数）；`local_policy` 传原始数值（AI 收到「户数约 8300000 万」的荒谬单位）；`final_eval` 起止年相同；`api_key` 明文落盘 `ai_config.json`；`HttpBackend.conclude` 未实现且 `panels_menu.py:200` 只捕获 AIRuntimeError → HTTP 模式结局界面必崩；`issue_free_decree` 默认类别拼写 `"free_edcree"`；`_fallback_parse._error=True` 与 `_ai_unavailable._error="AI_UNAVAILABLE"` 类型不统一。

### UI / 杂项
- `_panel_map` 调用不存在的 `MapCanvas.refresh()`（死代码潜伏）；`_tech_detail` 读 `state.era` 而非 `state.tech["era"]`（成本预览恒按 era=0，偏贵 20%+）；仓廪面板输入框无单位标注（默认 100 实际 = 100 万石/万亩）；「平盗」预览写「军事开支 -8万贯」但实际不扣钱；立绘分类用旧派系名（`阉党/西军` vs `宦官集团/西军集团`）；`dock_menu.png` 缺失、`theme.remove_white_bg` 不存在、字体注册传参错误（均静默降级）；开局 AI 探测在主线程同步阻塞 8s；`_anim` 动画注册表无清理（长期会话内存增长）；暗角合成首开面板卡顿。

---

## 四、设计澄清（已与作者确认）

- **AI 输入侧提供精确数值是设计**：皇帝（玩家）垂询内帑/国库/太仓/兵力/官员数，大臣可答实数；`check_treasury` 工具即为此设。
- **AI 输出侧只给档位词、程序 `tier_to_value` 换算成数值**：这是**推演结算的波动机制**（同一决策结果浮动），不是"皇帝认知模糊"模拟。
- 因此「AI 看到精确数值」不构成漏洞；但 **`ai/desensitize.py` 是无任何调用者的死代码**，且 `docs/游戏机制说明.md` 第八节「AI 永远看不到精确数值，只看到定性档位」的描述已与实际设计不符——建议：更新文档口径，或删除/标注废弃 desensitize 模块，避免后人误读。`posture`/`get_state_summary` 中 attitude/gunpowder/refugee_count 等精确值按上述设计属正常。

---

## 五、建议修复优先级

| 优先级 | 项 | 说明 |
|---|---|---|
| P0 | 财政平衡重算 | 修 P1-1 后按「年化货币岁入 4000-5000 万、年结余接近 0」目标重调收入（二税折色率/工商税率）或支出（PAY_CASH_BASE 语义）；三档难度都要回归 |
| P1-1 | `calc_pay_ratio` 单位迁移 | 去掉 due 的 ÷10000、明确 local_finance 口径；修后复测贪腐/加俸曲线与太仓断言 |
| P1 | 单位错位族 | 一条鞭折银（乘）、常平仓（去 ×10000）、作坊 grain_feed（改 peek） |
| P1 | 武功评分 / 金军战斗量纲 | avg_def 归一；金 power 与 `_army_power` 对齐或换用比例模型 |
| P1 | AI 工具链 | dialogue_history 格式统一、工具第二轮结果回传、effects dict/list 契约统一、scenes 过滤 |
| P1 | UI 崩溃点 | 33 处 `self.self`、浮层互毁、读档重建主界面 |
| P2 | 数据口径 | 12 路户数归一（或明确双口径为"分路=实管"并修 UI 文案）、两浙 officials、旧档兜底 |
| P2 | 文档 | 更新游戏机制说明.md 脱敏章节；删除/标注 desensitize 死代码 |

---

## 附：验证方法

- `python -m pytest tests` → 24 passed（覆盖诏令执行率/收束年/结束判定/月份推进/口碑权重/恒等断言；未覆盖本报告 P0/P1 各项）。
- 探针脚本（seed=2026/7）：36 个月三档难度国库轨迹、开局快照、常平/折银/作坊/口谕/长期诏令单点验证、金军战斗量纲、七维评分——结果均引用在本报告中。
