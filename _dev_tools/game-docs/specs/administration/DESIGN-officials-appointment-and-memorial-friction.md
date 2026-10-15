# 北宋中枢信息中继四司、官员任免博弈与全梯级官僚体系设计文档（权威全案）

> **归属工程**：《宋祚》中枢政务与地方官僚体系  
> **权威决策依据**：
> - `sz/_dev_tools/handover/decisions/JEV-台账-官员任命与上折博弈渗透设计-2026-10-15.json`（Jev A 方案，P=0.828）
> - `sz/_dev_tools/handover/decisions/JEV-台账-银台司进奏院职权与奏报处理机制-2026-10-15.json`（Jev A 方案，P=0.972，信息管道与政治滤镜模式）
> - `sz/_dev_tools/handover/decisions/JEV-台账-州府亲民官深度设计讨论-2026-10-15.json`（Jev A 方案，P=0.687，136 州府知通实体梯级下沉与科举磨勘池）
> - `sz/_dev_tools/handover/decisions/JEV-台账-官僚任免设计完善与连坐保护-2026-10-15.json`（Jev A 方案，P=0.949，举主连坐与工程防膨胀防护）  
> **核心硬约束**：**零独立新 UI**，全量复用既有召对流（`audience_dialogue`）、三省会签流（`council_review`）、动态记忆图谱（`MemoryGraph`）、地方档案（`LocalArchivePanel`）与案头折子（`state.memorials`），实现天子耳目通塞与官僚博弈的自然渗透。

---

## 一、 顶层架构原则：图谱存「史」，GameState 存「态」

为杜绝庞大官僚体系造成存档爆炸与计算卡顿，本体系严格恪守《宋祚》底层架构分工：
1. **GameState（内存与存档 JSON · 存“态”）**：
   - 仅记录当下**在任的官职主官、实时考课与派系状态**（中枢朝臣、21 路四监司、136 州府在任知府与通判）；
   - 不存储历史海量任免流水，保持存档轻盈、读写确定性。
2. **MemoryGraph（SQLite `slot_{slot}.db` · 存“史”）**：
   - 记录官员从**新科及第 -> 初仕知县 -> 举主保任 -> 历任知府/监司 -> 拜相入阁**的终身履历树；
   - 记录举主保任连坐关系网（`Relation: supports/guarantor`）；
   - 依托 SQLite FTS5 与时间半衰期衰减，**平时在磁盘休眠，问到才单点唤醒**，实现零内存浪费与零 Token 浪费。
3. **零新独立 UI**：
   - 所有交互自然渗透进：文华殿召对（提议博弈）、诏草三省会签（封驳博弈）、治道库案头折子（准奏立案）、地方档案抽屉（知通互掣卡片）。

---

## 二、 各核心机制与动态记忆库（Memory Graph）的有机互动

记忆库（`slot_{slot}.db`）在《宋祚》中绝非死板的只读存储仓，而是**所有博弈机制的“因果因陀罗网”**。六大机制与记忆图谱的动态双向交互协议如下：

```mermaid
flowchart TD
  subgraph 机制触发 (写入因)
    E1[科举登第授知县 / 举主开具荐状] -->|写入 Entity & Relation| MG[(MemoryGraph 记忆图谱)]
    E2[皇帝留中不发超过3个月 / 地方决口] -->|写入怠政因果与怨望| MG
    E3[银台司扣压灾折 / 登闻鼓击鼓破茧] -->|写入蔽塞欺君罪证| MG
    E4[皇帝越过三省强下御笔中旨] -->|写入中旨独断历史| MG
    E5[州府知通不合 / 通判拒不连署] -->|写入知通互掣对立边| MG
  end

  subgraph 动态演化 (权重与衰减)
    MG -->|按回合半衰期衰减| M_DEC[日常事务权重平缓衰减]
    MG -->|重大政治事件长半衰期| M_LONG[欺君/中旨/连坐等大事长期保鲜]
  end

  subgraph 游戏回响 (唤醒果)
    M_DEC & M_LONG -->|召对 retrieve_hierarchical| R1[召对大臣主动援引往事: 忆当年/揭旧短/谏中旨]
    M_DEC & M_LONG -->|三省会签 council_review| R2[门下封驳查验前科: 引用旧案封驳新诏]
    M_DEC & M_LONG -->|岁末大考 / 弹劾借案| R3[台谏借案追索举主: 顺藤摸瓜引爆连坐]
    M_DEC & M_LONG -->|前端 MemoryDrawer 抽屉| R4[玩家点击大臣: 历历在目的一生功过]
  end
```

### 2.1 机制与记忆库交互全景矩阵表

| 触发机制 | 写入记忆图谱的结构（Entity / Relation） | 衰减与存活（Half-life） | 读出与唤醒场景（有机反哺游戏） |
|---|---|---|---|
| **1. 知县起步与举主建网** | **Entity**：`official_{name}`（履历属性：首任县名、科举年次）<br>**Relation**：`Relation(朝臣, 知县, "supports", role="举主")` | 长期（$\lambda = 48$ 月）<br>伴随官员整个升迁生涯 | **召对与提拔**：朝臣主动向皇帝进言：“*臣昔年所保鄞县王安石，治水卓异，今磨勘已满，乞赐改官。*” |
| **2. 贪腐激变与连坐索拿** | **Relation**：`Relation(知府/知县, 贪官, "produces", 罪名="科敛扰民")`<br>**Relation**：`Relation(朝臣举主, 案由, "involves", 责任="连坐保任")` | 极长（$\lambda = 72$ 月）<br>成为党争终身政治污点 | **党争借案攻讦**：台谏在三省会签中发难：“*知府蔡某伏诛，查其当年改官举主乃章相公，乞按连坐通籍严办！*” |
| **3. 银台扣压与登闻破茧** | **Entity**：`event_瞒报_{路名}`（记录扣压事实）<br>**Relation**：`Relation(银台主官, 瞒报事实, "produces", 性质="蔽塞言路")` | 永久记录（直到皇帝处置） | **天子问责**：登闻鼓击破后，召对知银台司事时，系统自动注入该欺君边，触发皇帝怒斥与严旨下狱台词。 |
| **4. 案头奏折留中与怠政反噬** | **Entity**：`decision_留中_{折名}`<br>**Relation**：`Relation("朝廷怠政", 地方恶果, "produces", 灾害="运河决口/兵变")` | 中期（$\lambda = 24$ 月） | **月报与召对**：地方官在后来的折子或召对中悲鸣：“*前蒙留中三月，漕渠已决，今费百万金方可修补矣！*” |
| **5. 强推中旨与台谏积怨** | **Relation**：`Relation(皇帝, "御笔直发", "produces", 次数=累加)`<br>**Relation**：`Relation(台谏官, 皇帝, "opposes", 态度="怨望专断")` | 阶梯累加，12个月重置 | **伏阁大危机**：一年内积累 3 条“御笔直发”记录时，记忆库直接触发【宣德门台谏伏阁请退】特大朝政危机。 |
| **6. 州府知通互掣纪实** | **Relation**：`Relation(通判, 知府, "opposes", 事由="拒签加赋文移")` | 中期（$\lambda = 18$ 月） | **皇帝召对知府**：皇帝召对知府时，知府告状：“*通判李某事事掣肘，公文并书百般为难，乞调异路！*” |

---

## 三、 中枢信息四府中继与天子耳目

北宋中枢政务的命脉在于“下情上达与制命下传”。天下各路大员、朝臣、州府亲民官、军旅与民间的公文折子，通过**四大职权中继机构**进行流转与博弈：

| 机构名称 | 挂载主官 | 职掌分工 | 对每回合奏报的影响机制 | 皇帝破局抓手 |
|---|---|---|---|---|
| **都进奏院** | **提辖都进奏院**<br>*(从五品文臣)* | **各路驿传与文书分拣**<br>统辖 21 路驻京进奏官，向地方颁发朝廷邸报 | **时效与通塞**：若驿道通畅、主官尽责，地方急报当月即至；若主官渎职或漕渠受阻，公文延误滞后 1~2 月（标明 `〔都进奏院迟递〕`）。 | 召对撤换提辖官；疏浚运河与驿道 |
| **通进银台司** | **知通进银台司事**<br>*(四品近臣/谏官)* | **常规政务章奏之门神**<br>掌管受纳天下百官章奏、审定呈进御前，核验批红出纳 | **政治滤镜（信息茧房）**：主官派系决定折子偏向。清流在任则天下洞明；权相党羽在任则扣压弹劾与灾荒急折，粉饰太平，呈送祥瑞折。 | 召对罢黜银台官；派御史察访（`inspect_dispatch`） |
| **登闻鼓院** | **知登闻鼓院事**<br>*(正六品御史/台官)* | **民间直诉与非常规申冤通道**<br>专受臣民百姓阙下击鼓鸣冤、士民进献直言 | **破茧机制（反瞒报特急）**：当银台司扣压灾情民变时，民间击登闻鼓直达天听，以特急红折呈御前，揭穿蔽塞言路之罪。 | 准奏即办，顺藤摸瓜严惩银台欺君之罪 |
| **枢密院（机速房）** | **枢密使 / 知枢密院事**<br>*(从一品/正二品执政)* | **军事边防二府专线**<br>与三省并立，专掌天下九边戎务、调兵符契、密奏往还 | **军政密件与战和偏向**：边防军情（辽夏谍报、将领告急）绕过银台司走急递铺直达御前；主官战和倾向决定军务折子主调。 | 召对调整枢密长官；平衡二府文武 |

---

## 四、 官员全梯级流转体系与成长晋阶链

北宋官僚阶梯是一条从**科举殿试 -> 知县磨勘 -> 州府知通 -> 监司大员 -> 中枢宰执**的动态生长网：

### 4.1 第四层：知县级（县令/幕职官）—— 科举起点与磨勘蓄水池
- **科举起步**：每三年春闱放榜，新科进士池（`talent_pool`）绝大部分直接下沉为各路州县的知县、县丞、主簿或签判；
- **初任入库建档（MemoryGraph 记录一生履历）**：
  新科及第授官当月，记忆库自动生成终身履历根节点：
  ```python
  mem.add_entity(f"official_{name}", "minister", name, 
                 attributes={"origin": "科举进士", "year": state.year, "first_post": f"{county}知县"})
  mem.add_relation(name, county, "governs", weight=1.0)
  mem.add_relation(guarantor_minister, name, "supports", weight=1.0, 
                   attributes={"role": "举主", "turn": state.turn})
  ```
- **三年磨勘改官**：
  在县三年考课称职、治水劝农有方、且拥有 3 位举主保荐者，正式“改官”（由选人升入京朝官），进入州府亲民官储备库。
- **待阙冗官困境**：若皇帝滥开恩科导致及第人数远超县缺，触发“待阙冗官”：士人滞留汴京无缺，户部每月支付候缺津贴，士气消沉。

### 4.2 第三层：州府亲民官（全国 136 州府席位）—— 知通互掣
- **实体规模**：全国 136 个州府，每府设 `知府/知州` 1 名、`通判` 1 名（共 272 个实体席位），与 `LocalArchivePanel` 抽屉对齐；
- **公事连署（分权制约）**：知府出台赋税征调、兴修大工、开仓放粮，必须由通判**并书连署**方具效力；
  - 若知府贪敛苛急，清流通判**拒不连署**，该府行政效率骤降至 30%，通判越级密奏朝廷；
  - 若知通同流合污，隐匿赋税田产，动乱度飙升，引爆百姓击登闻鼓；
- **皇帝制衡暗棋**：皇帝若怀疑某地知府不法，可特简一位亲信御史充任该府**通判**，专职监督分权。

### 4.3 第二层：省路主官（21 路四监司 + 路治首府）
- **四大监司分立**：安抚司（帅·兵民戎政）、转运司（漕·赋税漕粮）、提点刑狱司（宪·刑名纠劾）、提举常平司（仓·义仓粮价）；
- 监司考课直接决定该路四维发展（税收、治安、漕运、粮价稳定）。

### 4.4 第一层：中枢朝臣（三省六部、枢密院、台谏 130+ 位历史人物）
- 掌控中枢大政、门下封驳、二府决策。

---

## 五、 召对 Prompt 接入记忆库（极致 Token 保护）

彻底弃用粗糙的手写正则，全面复用已有的 `MemoryGraph`（`memory/memory_graph.py`）：
```python
def get_dialogue_memory_context(state, minister_name: str, player_input: str) -> str:
    """召对前奏：从动态记忆库按需检索相关史料，零冗余注入。"""
    try:
        from memory.memory_graph import get_memory_graph
        mem = get_memory_graph(state.slot)
        # 精准分层检索：先概要，命中了再查关系边
        hits = mem.retrieve_hierarchical(
            minister_name, keywords=player_input, top_k=2, max_chars=350
        )
        if hits:
            return f"\n【前尘往事】\n{hits}"
    except Exception:
        pass
    return ""
```
- **Token 守卫效果**：皇帝不提杭州，全库 136 州府与千余知县数据沉睡在磁盘；皇帝提到杭州，仅提取杭州知通与历史因果；单次 Prompt 补充严格锁定在 **200~400 字以内**。

---

## 六、 案头奏折准奏落地闭环（零新 UI 实现）

### 6.1 治道库案头交互改造（`GovernanceHub.tsx`）
在【奏折 / 疏】原有卡片内补齐轻量出处与准奏动作：
```tsx
<div className="border border-gold/30 bg-card p-2 rounded">
  <div className="flex justify-between items-center">
    <span className="font-kai font-bold text-red">
      〔{memo.source_tag || "通进银台司进呈"}〕{memo.title}
    </span>
    <div className="space-x-1">
      <button onClick={() => acceptMemorial(i)} className="btn-sm bg-red text-paper">准 奏</button>
      <button onClick={() => dismissMemorial(i)} className="btn-sm text-dim">留 中</button>
    </div>
  </div>
  <p className="text-xs text-ink-light mt-1">{memo.body}</p>
  <div className="flex justify-between text-[11px] text-dim mt-0.5 font-kai">
    <span>具奏人：{memo.official?.role} {memo.official?.name}</span>
    {memo.guarantor && <span className="text-dim/80">举主：{memo.guarantor}</span>}
  </div>
</div>
```

### 6.2 准奏转换与三省联动（`core/commands_decree.py`）
```python
def accept_memorial(state: GameState, index: int) -> dict:
    """皇帝在案头点击准奏：将折子转化为待签诏草，直入三省会签推演。"""
    if index < 0 or index >= len(state.memorials):
        return {"ok": False, "msg": "无此奏折"}
    
    m = state.memorials.pop(index)
    
    # 同步记录决策进记忆库
    try:
        from memory.memory_graph import get_memory_graph
        mem = get_memory_graph(state.slot)
        mem.record_decision(f"accept_{m.get('title')}", title=m.get("title"), turn=state.turn)
    except Exception:
        pass

    org_map = {
        "finance": "户部", "military": "枢密院", "governance": "中书省",
        "personnel": "吏部", "invention": "工部"
    }
    org_hint = org_map.get(m.get("kind"), "中书省")
    if m.get("source") == "shumi":
        org_hint = "枢密院"
    
    draft = {
        "title": m["title"].replace("《", "").replace("》", "").replace("请", "准"),
        "body": f"照准所奏：{m['body']}",
        "org_hint": org_hint,
        "effects": _build_memorial_effects(m),
        "source": m.get("source_desc", "臣工奏疏"),
    }
    did = state.add_edict_draft(draft)
    return {"ok": True, "draft_id": did, "msg": f"已批「准奏」，诏草 d{did} 已进三省六部会签。"}
```

---

## 七、 落地代码清单与模块边界

| 模块 / 路径 | 职责定位 | 核心改动点 |
|---|---|---|
| `sz/game/content/ministers/data.py` | 中央机构底册 | 在 `CENTRAL_ORGS` 增设 `yintai_si`（通进银台司）、`jinzou_yuan`（都进奏院）、`dengwengu_yuan`（登闻鼓院）及初始主官。 |
| `sz/game/core/domains/administration/prefect_officials.py` | 州府知通管理 | 维护 136 州府席位（知府 + 通判）数据结构、知通公事连署判定、三年一任常调轮替。 |
| `sz/game/memory/memory_graph.py` | 动态历史记忆库 | 记录新科进士知县起点档案、举主连坐边（`guarantor`）、留中因果记录、提供召对按需层级切片检索。 |
| `sz/game/core/commands.py` | 月度奏折与召对 | 增强 `generate_memorials` 融入四司滤镜、3个月留中归档与怠政反噬；召对接入记忆库层级检索。 |
| `sz/game/core/commands_decree.py` | 诏草与准奏闭环 | 实现 `accept_memorial` 准奏转入 `add_edict_draft` 并同步记入记忆库；实现连续中旨台谏伏阁请退。 |
| `sz/game/frontend/src/renderer/panels/GovernanceHub.tsx` | 案头折子交互 | 在【奏折 / 疏】展示区为折子追加【准奏】/【留中】按钮与具奏人举主信息，零新开面板。 |
| `sz/game/frontend/src/renderer/panels/LocalArchivePanel.tsx` | 地方府级抽屉 | 顺带展示该府当前在任知府与通判姓名卡片，与 136 州府数据无缝呼应。 |
| `sz/game/frontend/src/renderer/panels/MemoryDrawer.tsx` | 大臣记忆抽屉 | 查阅大臣记忆时，展示其仕途起点（知县初仕）、举主关系与所涉地方大案。 |

---

## 八、 测试与验证规划

1. **记忆库双向联动测试（pytest）**：
   - 验证进士及第授知县后，`slot_{slot}.db` 是否生成 `Entity(official_...)` 与 `Relation(..., "governs")`；
   - 验证知府贪墨事发后，知识库能否沿 `supports/guarantor` 反查举主并自动扣减其声望。
2. **信息茧房与登闻破茧集成测试**：
   - 验证银台司主官为新党时，弹劾奏折被拦截、祥瑞折生成；
   - 验证地方动乱度高企时，登闻鼓院特急红折强制插入案头；
   - 验证查办后问责银台官欺君落马。
3. **案头折子防积压与怠政测试**：
   - 模拟 4 个月不批折子，断言过期折子进入历史库，案头不超 5 道，且记忆库生成 `怠政因果边` 并导致地方反噬。
4. **Token 安全压测**：
   - 模拟皇帝召对时输入任意地名，断言召对 Prompt 补充字数严格低于 400 字，无全量州府倾泻。
