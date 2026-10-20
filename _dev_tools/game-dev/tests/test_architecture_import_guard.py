# -*- coding: utf-8 -*-
"""架构分层方向 + 循环依赖的**常驻守卫**（2026-10-20 全审 P0-1 配套低风险落地）。

背景（为什么需要它）
--------------------
`_dev_tools/game-docs/analysis/模块耦合与复用盘点_2026-10-20.md` 实测（AST 全量扫描
`game/**/*.py`：329 个模块、全库 2306 条 import 语句，其中 **1510 条指向 `game/` 内部模块**，
归并为 **996 条模块边**）：

* 分层反向边 **37 对 / 65 条语句**（数据层上引 17 对、业务引 AI/应用 15 对、业务反调编排 5 对）；
* 强连通分量（SCC）**7 个 / 69 个模块**，其中最大的一个 **37 模块**。

这些问题**都是既有事实**，本轮按用户裁定的深度 B（文档 + 低风险落地）**不做大重构**。
所以本文件的定位是**棘轮（ratchet）而不是规约**：

  ① 把现存反向边**逐对冻结**在 `_FROZEN_UPLINK` 里（值 = 冻结时的 import 语句条数）；
  ② 把现存环**逐分量冻结**在 `_FROZEN_CYCLES` 里；
  ③ 之后**只准减、不准增**：新模块不许踩线，老模块不许在同一对上多写一处 import，
     环不许把新模块卷进来（`新 SCC ⊆ 某个冻结 SCC`，因此"拆环/缩小 SCC"不会被误判为回归）。

判据口径（扫描器覆盖哪些导入形态，写清楚免得后人重踩"假 0"）
------------------------------------------------------------
本守卫统计 **AST 里出现的全部 Import / ImportFrom**，覆盖：

* `import a.b` / `import a.b as c` / `from a.b import c` / `from a import b` / `from a import *`；
* **函数内 / `try` 内 / `if` 内的延迟导入**（历史教训：阶段 0 只扫模块级 import ⇒ 得出
  "循环依赖=0" 的错结论，见 `specs/cross-cutting/阶段1_依赖图与循环依赖.md` 开头）；
* 相对导入（`from .x import y`，按文件所在包解析）。

不计：注释/字符串里的 import 文本、`importlib.import_module("...")` 之类的动态导入
（后者由 `_ALLOWED_DYNAMIC_IMPORT_HINT` 单独盯——见 `test_no_obvious_dynamic_import_bypass`）。

层级模型（band 0 最低 → band 5 最高）
-------------------------------------
| band | 成员 | 说明 |
|---|---|---|
| 0 | `content.*`、`core.foundation.*` | 数据表与基础账本（同一带内互相引用合法） |
| 1 | `core.domains.*`、`core.*` 平铺业务、`engine.*`、`memory.*`、`audio.*`、`telemetry.*` | 业务机制 + 同层侧服务（写入边界 / 记忆 / 音频 / 观测） |
| 2 | `core.settlement*.py`、`core.commands*.py` | 结算与命令**编排**（`core.settlement_common` **除外**，见下） |
| 3 | `ai.*`、`application.*` | AI 契约层与应用流程层 |
| 4 | `backend.*` | HTTP/本地接口薄壳 |
| 5 | 仓库脚本（`build_map_basemap` 等） | 不入规则（构建期工具） |

两条落地时定下的口径，别按直觉改：

* **`core.settlement_common` 归 band 1（业务），不归 band 2（编排）**。它是"共享写原语"
  （`distribute_cash` / `transfer_public_funds_to_pops` / `note_settlement_error` …），
  宿主在结算命名空间里纯属历史命名，见
  `specs/cross-cutting/阶段1_依赖图与循环依赖.md` §五之补第 2 条。若把它判成编排层，
  `domains → settlement_common`（19 个消费方）会被误报成 7 条越层，且"改成直认真实家"
  这个正确改法反而无法表达。
* **`core.commands` / `core.agent_router` / `core.save_load → application.*` 的白名单理由**：
  `core/commands.py` 与 `core/agent_router.py` 的目标归属本就是
  `workflows/` + `application/` + 兼容门面（架构方案 §5.2 / §7 归属表），
  `core/save_load.py:1220` 是同一模式（`load_game` 真身在 `application/load_game.py`）。
  所以这三条**不是"下层引上层"**，是"入口层还住在 core 目录里"，登记在案、等搬迁时一并销账。

维护方式
--------
* 新增一条越层边 ⇒ 测试红；**正确做法是改代码**，不是往 `_FROZEN_UPLINK` 里加行。
  只有"确属历史欠账、本轮不动、已进文档"的边才允许登记，且必须写清 `# why:`。
* 修掉一条 ⇒ 测试**仍然绿**（棘轮只挡变坏），但请顺手把该行删掉并同步数字，
  否则冻结表会慢慢变成"现状快照"而不是"欠账清单"。
* 本文件只读源码文本，**不 import 任何 game 模块**（无副作用、无第三方依赖）。
"""
import ast
import io
import os

# ── 路径（与 test_newpath_imports_b9.py 同一算法：从本文件回溯到 game/）──────────
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_GAME_ROOT = os.path.normpath(os.path.join(_TESTS_DIR, "..", "..", "..", "game"))
_FE_RENDERER = os.path.normpath(
    os.path.join(_GAME_ROOT, "frontend", "src", "renderer"))
_SKIP_DIRS = {"__pycache__", "node_modules", ".git", "out", "dist", "release"}

# ── 冻结表：现存**越层边**（键 = (src, dst) 模块点分名；值 = 冻结时的 import 语句条数）──
# 释义：R1 = band0→band1+，R2 = band1/2→band3，R3 = band1→band2。
_FROZEN_UPLINK = {
    # ── R1 数据层上引（17 对 / 27 条语句）────────────────────────────────
    # why: 事件/局势/派系数据表要读规则侧常量与构造器；正确改法是常量下沉 content。
    ("content.codex_data", "core.events"): 1,
    ("content.codex_data", "core.settlement"): 1,
    ("content.data_factions.song", "core.building_jobs"): 1,
    ("content.ministers.persona", "core.domains.administration.estate_mechanic"): 1,
    ("content.ministers.persona", "core.era_mechanic"): 1,
    ("content.situation_seeds", "core.situations"): 2,
    # why: 账本原语要读派生链路（stock_flow / transport），方向是"账本→业务"；
    #      真解是把 stock_flow/transport 的**纯计算**下沉 foundation，成本高、本轮不动。
    ("core.foundation.ledger.material_holding", "core.domains.economy.stock_flow"): 2,
    ("core.foundation.ledger.money_transport", "core.transport"): 5,
    ("core.foundation.ledger.spatial_warehouse_bridge", "core.transport"): 4,
    # why: 计量换算要问 institution 的度支科目表。
    ("core.foundation.metrology", "core.domains.administration.institution"): 2,
    # why: 读档迁移是"开局/迁移装配点"，天然要调各域 init_*；正确改法是迁到
    #      application/（与 game_init.py 同层），属阶段 3 收尾，本轮不动。
    ("core.foundation.persistence.migrations", "core.domains.administration.circuit_officials"): 1,
    ("core.foundation.persistence.migrations", "core.domains.administration.prefect_officials"): 1,
    ("core.foundation.persistence.migrations", "core.domains.economy.building_owner"): 1,
    ("core.foundation.persistence.migrations", "core.domains.economy.canal_bridge"): 1,
    ("core.foundation.persistence.migrations", "core.domains.economy.mineral_deposit"): 1,
    ("core.foundation.persistence.migrations", "core.domains.economy.workshop_opening"): 1,
    ("core.foundation.persistence.migrations", "core.domains.economy.workshop_owner"): 1,

    # ── R2 业务/编排 → AI / 应用流程（15 对 / 31 条语句）──────────────────
    # why: 以下三条的"真家"本来就在 application/，core 侧是兼容门面，见文件头 §维护方式。
    ("core.agent_router", "application.agent_router"): 1,
    ("core.commands", "application.agent_router"): 1,
    ("core.commands", "application.game_init"): 1,
    ("core.commands", "application.turn_lifecycle"): 1,
    ("core.save_load", "application.load_game"): 1,
    # why: 业务侧 import AI 层是为了 **确定性兜底**（AI 不可用时程序出叙事）与
    #      `tier_to_value` 档位换算。方向可疑但功能必需；真解是把
    #      narrative_fallback / tier 换算表下沉 core，属口径单点整改，另立批次。
    ("core.commands", "ai.client_utils"): 1,
    ("core.commands", "ai.narrative_fallback"): 11,
    ("core.commands", "ai.narrative_guard"): 1,
    ("core.commands_decree", "ai.client"): 5,
    ("core.asset_context", "ai.client"): 1,
    ("core.game_state", "ai.desensitize"): 1,
    ("core.events", "ai.client_utils"): 1,
    ("core.free_effect", "ai.client_utils"): 1,
    ("core.settlement_imperial", "ai.client_utils"): 2,
    # 2026-10-20 事件民心冲击档预取：结算期禁止同步 HTTP，玩家动作路径须在结算前
    # 预取档位（application.shock_prefetch 只转发生产者/写槽位）。方向同 R2 既有例外，
    # 真解是把它挪进 application.turn_lifecycle（另立批次，避免动玩法顺序）。
    ("core.commands", "application.shock_prefetch"): 1,

    # ── R3 业务 → 结算/命令编排（5 对 / 7 条语句）────────────────────────
    # why: 业务机制反调编排（"结算步应只发领域事件，不反调编排器"）。
    #      真解是接口倒置（注册表/事件），拆这些边要动玩法顺序，须单独裁定。
    ("core.decree_gates", "core.settlement"): 2,
    ("core.events", "core.commands"): 2,
    ("core.longterm_task", "core.commands_decree"): 1,
    ("core.military_order", "core.commands"): 1,
    ("core.domains.economy.spatial_warehouse_readout", "core.settlement_pipeline"): 1,
}

# ── 冻结表：现存**强连通分量**（每项一个 SCC；大小 1 的不登记）───────────────────
# 判据：计算出的任一 SCC 必须是**某个冻结 SCC 的子集**。
# ⇒ 新模块被卷进环 = 红；拆环/环变小 = 绿（棘轮容许改善）。
_FROZEN_CYCLES = (
    # 39 模块大环（解算链 + AI 契约 + 读档入口）。最小环：
    #   application.load_game → core.save_load → application.load_game
    # 2026-10-20 新增成员：`application.shock_prefetch`（冲击档预取）、
    #   `core.domains.administration.monthly_gazette`（邸报）——由并行会话功能接线带入，
    #   二者都通过既有 AI/读档边进入本环；拆环需先定接口归属，另立批次。
    frozenset({
        "ai.client", "ai.client_narrative", "ai.client_utils", "ai.contracts_court",
        "ai.contracts_decree", "ai.contracts_misc", "ai.contracts_settle", "ai.jev_gate",
        "ai.narrative_fallback", "ai.validators", "application.agent_router",
        "application.decree_prefetch", "application.load_game",
        "application.shock_prefetch",
        "application.turn_lifecycle", "core.asset_context", "core.commands",
        "core.commands_decree", "core.decree_gates",
        "core.domains.administration.monthly_gazette",
        "core.domains.administration.settlement_officialdom",
        "core.domains.construction.settlement_tech",
        "core.domains.economy.readout_hub",
        "core.domains.economy.spatial_warehouse_readout",
        "core.domains.politics.longterm_case", "core.events", "core.free_effect",
        "core.longterm_task", "core.military_order", "core.save_load", "core.settlement",
        "core.settlement_decree", "core.settlement_econ", "core.settlement_granary",
        "core.settlement_imperial", "core.settlement_military", "core.settlement_pipeline",
        "core.settlement_steps",
    }),
    # 20 模块环（基础账本 ↔ 业务计量）。最小环：
    #   imperial_exam → officialdom → imperial_exam
    frozenset({
        "core.audit_case", "core.building_jobs", "core.civil_building",
        "core.construction_cost", "core.construction_shadow",
        "core.domains.administration.imperial_exam",
        "core.domains.administration.officialdom", "core.domains.economy.stock_flow",
        "core.domains.economy.stock_identity", "core.foundation.ledger.building_bridge",
        "core.foundation.ledger.grain_bridge",
        "core.foundation.ledger.local_treasury_bridge",
        "core.foundation.ledger.material_holding", "core.foundation.ledger.pop_bridge",
        "core.foundation.ledger.pop_structure", "core.foundation.ledger.storage_bridge",
        "core.game_state_econ", "core.market_price", "core.settlement_common",
        "core.transport",
    }),
    # content/ministers 内部 4 模块环（数据表 + 画像装配）。
    frozenset({
        "content.ministers.costumes", "content.ministers.data",
        "content.ministers.portrait_assembler", "content.ministers.stats",
    }),
    # 派系两模块环。
    frozenset({"core.faction_basis", "core.faction_metrics"}),
    # 影子对账（shadow）两模块环，各一对。
    frozenset({"core.domains.economy.owner_candidates_shadow",
               "core.domains.economy.workshop_fund_shadow"}),
    frozenset({"core.domains.economy.trade_shadow",
               "core.domains.economy.waterway_seats"}),
    # content.ministers.persona ↔ 家产机制（跨层小环）。
    frozenset({"content.ministers.persona",
               "core.domains.administration.estate_mechanic"}),
)

# ── 扫描器下限断言（"计数为 0 = 扫描失效，不是干净"——项目既定纪律）──────────────
_MIN_MODULES = 300
_MIN_EDGE_PAIRS = 900
_MIN_IMPORT_STATEMENTS = 1300
_MIN_CYCLIC_MODULES = 60


# ══════════════════════════════════════════════════════════════════════════════
# 扫描器
# ══════════════════════════════════════════════════════════════════════════════
def _py_files():
    out = []
    for dirpath, dirnames, filenames in os.walk(_GAME_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def _module_name(path):
    rel = os.path.relpath(path, _GAME_ROOT).replace(os.sep, "/")
    return rel[:-3].replace("/", ".")


def _scan_backend():
    """→ (modules:set, edges:dict[(src,dst)] -> 语句条数, statements:int)"""
    files = _py_files()
    modules = {_module_name(p) for p in files}
    edges = {}
    statements = 0
    for path in files:
        src = _module_name(path)
        tree = ast.parse(io.open(path, encoding="utf-8", errors="replace").read(),
                         filename=path)
        pkg = src.rsplit(".", 1)[0] if "." in src else ""
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                statements += 1
                base = node.module or ""
                if node.level:
                    parts = pkg.split(".") if pkg else []
                    if node.level - 1 > len(parts):
                        continue
                    keep = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
                    base = ".".join(keep + ([base] if base else []))
                target = None
                for alias in node.names:
                    cand = (base + "." + alias.name) if base else alias.name
                    if cand in modules:
                        target = cand
                        break
                if target is None and base in modules:
                    target = base
                if target:
                    edges[(src, target)] = edges.get((src, target), 0) + 1
            elif isinstance(node, ast.Import):
                statements += 1
                for alias in node.names:
                    cand = alias.name
                    target = None
                    while cand:
                        if cand in modules:
                            target = cand
                            break
                        if "." not in cand:
                            break
                        cand = cand.rsplit(".", 1)[0]
                    if target:
                        edges[(src, target)] = edges.get((src, target), 0) + 1
    return modules, edges, statements


def _layer(module):
    """最粗粒度层名（用于报告）。"""
    if module.startswith("core.foundation."):
        return "foundation"
    if module.startswith("core.domains."):
        return "domains"
    if module.startswith("core."):
        return "core"
    top = module.split(".")[0]
    return top if top in ("content", "ai", "engine", "memory", "application",
                          "backend", "audio", "telemetry") else "root"


def _band(module):
    """依赖方向的可比序号（小的在下面）。见文件头 §层级模型。"""
    layer = _layer(module)
    if layer in ("foundation", "content"):
        return 0
    if layer == "domains":
        return 1
    if layer == "core":
        base = module.rsplit(".", 1)[-1]
        # settlement_common 是共享写原语，归业务层（文件头 §层级模型 第 1 条）
        if base == "settlement_common":
            return 1
        if base.startswith("settlement") or base.startswith("commands"):
            return 2
        return 1
    if layer in ("engine", "memory", "audio", "telemetry"):
        return 1
    if layer in ("ai", "application"):
        return 3
    if layer == "backend":
        return 4
    return 5  # 构建脚本，不入规则


def _rule_of(src, dst):
    """一条边触犯哪条规则；不触犯则 None。"""
    s, d = _band(src), _band(dst)
    if s == 0 and d > 0:
        return "R1:数据层上引"
    if s in (1, 2) and d == 3:
        return "R2:业务/编排引AI或应用层"
    if s == 1 and d == 2:
        return "R3:业务反调结算/命令编排"
    if s in (1, 2) and d == 4:
        return "R4:core/domains引backend"
    return None


def _tarjan(modules, edges):
    """→ SCC 列表（仅返回大小 >= 2 的）。"""
    out = {}
    for (src, dst) in edges:
        out.setdefault(src, set()).add(dst)
    index, low, on_stack, stack, sccs = {}, {}, set(), [], []
    counter = [0]

    def strongconnect(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in sorted(out.get(v, ())):
            if w not in index:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                sccs.append(frozenset(comp))

    for v in sorted(modules):
        if v not in index:
            strongconnect(v)
    return sccs


# ══════════════════════════════════════════════════════════════════════════════
# 后端：扫描器自检
# ══════════════════════════════════════════════════════════════════════════════
def test_backend_scan_is_not_degenerate():
    modules, edges, statements = _scan_backend()
    assert len(modules) >= _MIN_MODULES, (
        f"只扫到 {len(modules)} 个模块（下限 {_MIN_MODULES}）——目录算错或跳过规则误伤")
    assert len(edges) >= _MIN_EDGE_PAIRS, (
        f"只扫到 {len(edges)} 条模块边（下限 {_MIN_EDGE_PAIRS}）——导入形态覆盖漏了")
    assert statements >= _MIN_IMPORT_STATEMENTS, (
        f"只扫到 {statements} 条 import 语句（下限 {_MIN_IMPORT_STATEMENTS}）")


# ══════════════════════════════════════════════════════════════════════════════
# 后端：分层方向
# ══════════════════════════════════════════════════════════════════════════════
def _assert_no_unfrozen_uplink(rule_filter):
    _modules, edges, _n = _scan_backend()
    bad, regressed = [], []
    for (src, dst), n in sorted(edges.items()):
        rule = _rule_of(src, dst)
        if rule is None or not rule.startswith(rule_filter):
            continue
        allowed = _FROZEN_UPLINK.get((src, dst))
        if allowed is None:
            bad.append(f"{src} → {dst}  [{rule}] ({n} 处)")
        elif n > allowed:
            regressed.append(f"{src} → {dst}  冻结 {allowed} 处，现有 {n} 处  [{rule}]")
    msg = []
    if bad:
        msg.append("新增越层依赖（现在就该改代码，不要往 _FROZEN_UPLINK 加行）：\n  "
                   + "\n  ".join(bad))
    if regressed:
        msg.append("既有越层依赖的 import 语句变多了（同一对模块只准减、不准增）：\n  "
                   + "\n  ".join(regressed))
    assert not msg, "\n".join(msg)


def test_data_layer_does_not_import_upward():
    """band0（content / core.foundation）不得 import 业务及以上层。"""
    _assert_no_unfrozen_uplink("R1")


def test_business_layer_does_not_import_ai_or_application():
    """band1/2（业务/编排）不得 import band3（ai / application）。"""
    _assert_no_unfrozen_uplink("R2")


def test_business_layer_does_not_import_settlement_orchestration():
    """band1（业务机制）不得反调 band2（结算/命令编排）。"""
    _assert_no_unfrozen_uplink("R3")


def test_core_and_domains_never_import_backend():
    """R4 全绿：core / domains 直连 backend = 0，**不留白名单**。"""
    modules, edges, _n = _scan_backend()
    hits = [f"{s} → {d}" for (s, d) in sorted(edges)
            if _layer(s) in ("core", "domains") and _band(d) == 4]
    assert not hits, "core/domains 不得 import backend：\n  " + "\n  ".join(hits)


def test_frozen_uplink_table_has_no_stale_entries():
    """冻结表里的每一条都**仍然存在**——否则说明已修好却没销账，会掩盖新违规。"""
    _modules, edges, _n = _scan_backend()
    stale = [f"{s} → {d}" for (s, d) in _FROZEN_UPLINK if (s, d) not in edges]
    assert not stale, (
        "以下冻结项已不存在（已修复或改名），请从 _FROZEN_UPLINK 删除并同步文档：\n  "
        + "\n  ".join(sorted(stale)))


# ══════════════════════════════════════════════════════════════════════════════
# 后端：禁止新增循环
# ══════════════════════════════════════════════════════════════════════════════
def test_no_new_cyclic_modules():
    """任何 SCC 都必须落在某个**已冻结**的 SCC 里（可不等于它：拆环/缩小是合法的）。"""
    modules, edges, _n = _scan_backend()
    sccs = _tarjan(modules, edges)
    cyclic = set().union(*sccs) if sccs else set()
    assert len(cyclic) >= _MIN_CYCLIC_MODULES, (
        f"只找到 {len(cyclic)} 个成环模块（下限 {_MIN_CYCLIC_MODULES}）——扫描器失效")

    leaked = []
    for comp in sccs:
        if not any(comp <= frozen for frozen in _FROZEN_CYCLES):
            leaked.append(sorted(comp))
    assert not leaked, (
        "新增循环依赖（这些模块被卷进了环，且不属于任何已冻结 SCC）：\n  "
        + "\n  ".join(" / ".join(c) for c in leaked)
        + "\n\n拆环方向见 analysis/模块耦合与复用盘点_2026-10-20.md §3。")


def test_frozen_cycles_have_no_stale_members():
    """冻结 SCC 里的模块必须仍成环——否则环已被拆开，应销账并同步文档数字。"""
    modules, edges, _n = _scan_backend()
    sccs = _tarjan(modules, edges)
    cyclic = set().union(*sccs) if sccs else set()
    stale = sorted({m for frozen in _FROZEN_CYCLES for m in frozen} - cyclic)
    assert not stale, (
        "以下模块已不再成环（环被拆开或模块改名），请更新 _FROZEN_CYCLES 与文档：\n  "
        + "\n  ".join(stale))


def test_no_obvious_dynamic_import_bypass():
    """动态导入是绕过分层守卫的逃逸口：新增 `importlib.import_module("core...")` 一律拦下。

    现存 3 处均为既有兼容装配（白名单），新增须走评审。
    """
    allowed = {
        ("content.faction_registry", "content.data_factions"),
        ("core.domains.administration.estate_mechanic", "content.ministers.data"),
        ("core.domains.economy.entity_projection", "core.domains.economy.building_owner"),
    }
    hits = []
    for path in _py_files():
        src = _module_name(path)
        tree = ast.parse(io.open(path, encoding="utf-8", errors="replace").read(),
                         filename=path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if name not in ("import_module", "__import__", "module_from_spec"):
                continue
            arg = node.args[0] if node.args else None
            if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                continue
            if any(arg.value.startswith(p) for p in
                   ("core", "ai", "content", "backend", "engine", "memory")):
                hits.append((src, arg.value, node.lineno))
    fresh = [h for h in hits if (h[0], h[1]) not in allowed]
    assert not fresh, (
        "新增动态导入（会绕过分层与环守卫）：\n  "
        + "\n  ".join(f"{s}:{ln} import_module({m!r})" for s, m, ln in fresh))


# ══════════════════════════════════════════════════════════════════════════════
# 前端：renderer 分层方向
# ══════════════════════════════════════════════════════════════════════════════
_IMPORT_RE = None  # 延迟编译，避免 import re 顶到文件头干扰阅读


def _fe_files():
    out = []
    for dirpath, dirnames, filenames in os.walk(_FE_RENDERER):
        dirnames[:] = [d for d in dirnames if d not in ("node_modules", "__tests__")]
        for fn in filenames:
            if fn.endswith((".ts", ".tsx")) and ".selftest." not in fn:
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def _fe_edges():
    import re
    global _IMPORT_RE
    if _IMPORT_RE is None:
        _IMPORT_RE = re.compile(r"""(?:from\s*|import\s*\(\s*|require\s*\(\s*)['"]([^'"]+)['"]""")
    rel = {}
    for path in _fe_files():
        rel[os.path.relpath(path, _FE_RENDERER).replace(os.sep, "/")] = path
    names = set(rel)
    edges = {}
    for relpath, path in rel.items():
        base_dir = os.path.dirname(relpath)
        text = io.open(path, encoding="utf-8", errors="replace").read()
        for m in _IMPORT_RE.finditer(text):
            spec = m.group(1)
            if spec.startswith("@/"):
                cand_base = "renderer/" + spec[2:]
            elif spec.startswith("."):
                cand_base = os.path.normpath(os.path.join(base_dir, spec)).replace(os.sep, "/")
            else:
                continue  # 第三方包/JSON 不在分层规则内
            target = None
            for cand in (cand_base, cand_base + ".ts", cand_base + ".tsx",
                         cand_base + "/index.ts", cand_base + "/index.tsx"):
                if cand in names:
                    target = cand
                    break
            if target:
                edges.setdefault(relpath, set()).add(target)
    return rel, edges


def _fe_slice(relpath):
    """`store/gameStore.tsx` → `store`；根文件（`App.tsx`）→ `root`。"""
    return relpath.split("/")[0] if "/" in relpath else "root"


def test_frontend_scan_is_not_degenerate():
    rel, edges = _fe_edges()
    assert len(rel) >= 60, f"只扫到 {len(rel)} 个 renderer 文件，疑扫错目录"
    assert len(edges) >= 50, f"只扫到 {len(edges)} 个有出边的文件"


def test_frontend_store_api_utils_do_not_import_ui():
    """`store` / `api` / `utils` 是被 UI 依赖的底座：不得反向 import 面板 / HUD / 地图 / 组件。

    当前实测 **0 违规**，因此**不留白名单**——有新边就是设计退步。
    """
    _rel, edges = _fe_edges()
    bad = []
    for src, dsts in sorted(edges.items()):
        s_slice = _fe_slice(src)
        if s_slice not in ("store", "api", "utils"):
            continue
        for dst in sorted(dsts):
            d_slice = _fe_slice(dst)
            if d_slice in ("panels", "hud", "map", "components", "main-menu"):
                bad.append(f"{src} → {dst}  [{s_slice} → {d_slice}]")
    assert not bad, ("store/api/utils 不得反向依赖 UI 层：\n  " + "\n  ".join(bad))


def test_frontend_api_client_is_a_leaf():
    """`api/client.ts` 是唯一后端出口：不得 import store / 面板（否则重演"绕 store 直接取数"）。"""
    _rel, edges = _fe_edges()
    bad = [f"{s} → {d}" for s, dsts in sorted(edges.items())
           if _fe_slice(s) == "api" for d in sorted(dsts)
           if _fe_slice(d) not in ("api", "types", "utils")]
    assert not bad, ("api 层应为叶子（只允许 types/utils）：\n  " + "\n  ".join(bad))
