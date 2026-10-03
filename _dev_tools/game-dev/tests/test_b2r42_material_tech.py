# -*- coding: utf-8 -*-
"""B4-2 · 建材科技解锁的定向回归（规格 `market-civilian-economy` **B4-2**）。

锁定六件事（与 B4-2「执行要求」一一对应）：

1. **未解锁不可用**——水泥/钢筋在开局**不是价格为 0**（返回 `None`）、**不是缺货伪装**，
   而是 `defined=False` + 可诊断 `reason`；
2. **三种来源各能解锁**——科技节点 / 工艺改进 / 贸易引入都能解锁，且**记录来源**；
3. **前置条件拒绝式**——前置科技/等级/时间/作坊/贸易渠道任一不满足即**拒绝并给 reason**；
4. **非法条目拒绝**——注册表非法条目 raise，**不静默写入半个条目**；
5. **缺失 ≠ 0 ≠ False**——未记录状态给 `None`/`unrecorded`，**不得**回落成"未解锁"或 0 价；
6. **读数不改 state**——所有读数函数零写入（含不创建 `tech["materials"]` 容器），
   且 POP 挂载律不被破坏（解锁只写既有容器，绝不动 POP wealth/grain/size 与国库）。

⚠️ 新材声明：**北宋没有水泥、没有钢筋**。二者是**架空后世材料**
（注册表内 `fictional: True` + 史实声明 `note`），只能经解锁进入本作，
不得以"开局即有"的方式出现。本模块**尚未接线**到 `settlement.py`（由 Lead 统一接线）。
"""
import copy
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import material_tech as M                            # noqa: E402
from core.game_state import GameState                         # noqa: E402
from core.legacy_mechanic import init_legacies                 # noqa: E402


# =============================================================================
# 夹具
# =============================================================================

@pytest.fixture(autouse=True)
def _registry_guard():
    """注册表是模块级可变常量：**深拷贝**快照/还原，避免用例就地改动泄漏到后续用例。"""
    snapshot = copy.deepcopy(M.MATERIAL_TECH_UNLOCKS)
    yield
    M.MATERIAL_TECH_UNLOCKS.clear()
    M.MATERIAL_TECH_UNLOCKS.update(snapshot)
    M.invalidate_material_tech_cache()


def _state(**kw):
    """全新开局（确定性：不跑结算，字段即开局值）。"""
    s = GameState("史实")
    init_legacies(s)
    s.year = kw.get("year", 1121)
    s.month = kw.get("month", 3)
    tech = s.tech
    tech["level"] = kw.get("level", 75)
    tech["west"] = kw.get("west", 1.0)
    tech["unlocked"] = list(kw.get("unlocked", ["M4_furnace", "C2_acid", "E2_coke"]))
    s.maritime["open"] = kw.get("maritime", True)
    for r in kw.get("workshop_routes", ("京畿路", "两浙路", "成都府路", "河北路", "利州路")):
        s.prefectures[r].setdefault("buildings", {})["官营作坊"] = kw.get("lv", 1)
    return s


def _state_snapshot(s):
    """用于「读数不改 state」的深快照（三块既有容器 + POP 口径）。"""
    return copy.deepcopy({
        "tech": s.tech,
        "resources": s.resources,
        "prefectures": s.prefectures,
        "treasury": s.treasury,
        "imperial_treasury": s.imperial_treasury,
        "statistics": s.statistics,
    })


def _pop_money_grain(s):
    """ΣPOP wealth / ΣPOP grain / ΣPOP size（挂载律：本模块不得改变任何一项）。"""
    w = g = 0.0
    n = 0
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            if isinstance(pop, dict):
                w += float(pop.get("wealth", 0) or 0)
                g += float(pop.get("grain", 0) or 0)
                n += int(pop.get("size", 0) or 0)
    return w, g, n


# =============================================================================
# 0 · 前置：新材声明本身（架空后世材料，非北宋现实）
# =============================================================================

def test_new_materials_declared_fictional_with_note():
    """水泥/钢筋必须显式标注为架空后世材料，并写明史实依据/架空声明。"""
    assert M.MATERIAL_TECH_UNLOCKS, "注册表不得为空"
    for key in ("水泥", "钢筋"):
        e = M.MATERIAL_TECH_UNLOCKS[key]
        assert e["fictional"] is True, f"{key} 必须标注 fictional=True（北宋无此物）"
        assert e["note"] and isinstance(e["note"], str) and e["note"].strip()
        assert e["dim"] == key


def test_three_unlock_sources_all_expressible():
    """三种解锁来源都能表达，且每种都有其语义齐备的前置。"""
    for key, e in M.MATERIAL_TECH_UNLOCKS.items():
        assert set(e["unlock"]) == {"tech", "craft", "trade"}, key
        assert e["unlock"]["tech"].get("tech_node")
        assert e["unlock"]["craft"].get("workshops")
        trade = e["unlock"]["trade"]
        assert ("min_west" in trade) or trade.get("maritime")


def test_registered_materials_absent_from_resource_dims_at_start():
    """开局不存在水泥/钢筋资源槽（材料必须靠解锁进入，不得开局即有）。"""
    s = _state()
    for dim in ("水泥", "钢筋"):
        assert dim not in s.resources
        assert dim not in s.tech.get("materials", {})


# =============================================================================
# 1 · 未解锁 ⇒ 不可用（不是价格 0，不是缺货伪装）
# =============================================================================

def test_locked_material_is_unavailable_not_free_and_not_stockout():
    """已登记但未解锁：不可交易、**价格 None（不是 0）**、产地不可用且带 reason。"""
    s = _state(unlocked=[])                        # 前置科技确实未点亮 ⇒ 确凿「未解锁」
    s.tech["materials"] = {}                       # 容器在、记录无
    st = M.material_unlock_status(s, "水泥")
    assert st["status"] == M.STATUS_LOCKED
    assert st["defined"] is True                   # 「未解锁」是实测结论，不是缺失
    assert M.is_material_unlocked(s, "水泥") is False

    avail = M.material_availability(s, "水泥")
    assert avail["available"] is False
    assert avail["reason"] == "not_unlocked"

    assert M.effective_material_price(s, "水泥", 800) is None   # 绝不 0（0 价 = 白给）
    assert M.effective_material_price(s, "水泥", 0) is None
    assert M.material_tradable(s, "钢筋") is False

    sites = M.material_sites(s, "水泥")
    assert sites["defined"] is False
    assert sites["sites"] is None                  # 不是空列表：不可用 ≠ 没有产地


def test_unlocked_material_is_usable_after_unlock():
    """解锁后才有配方/产地/价格：读数如实翻正。"""
    s = _state()
    assert M.effective_material_price(s, "水泥", 800) is None
    M.unlock_material(s, "水泥", "tech")
    assert M.is_material_unlocked(s, "水泥") is True
    assert M.effective_material_price(s, "水泥", 800) == 800.0
    assert M.material_tradable(s, "水泥") is True
    sites = M.material_sites(s, "水泥")
    assert sites["defined"] is True
    assert set(sites["candidate_sites"]) == {"京畿路", "两浙路", "成都府路"}
    assert set(sites["sites"]) == {"京畿路", "两浙路", "成都府路"}    # 官营作坊已建


def test_no_available_site_when_workshop_absent():
    """承载作坊未建成 ⇒ 有候选产地但**无可用产地**（不冒充"没有该路"）。"""
    s = _state()
    M.unlock_material(s, "水泥", "tech")
    s.prefectures["京畿路"]["buildings"] = {}
    s.prefectures["两浙路"]["buildings"] = {}
    s.prefectures["成都府路"]["buildings"] = {}
    sites = M.material_sites(s, "水泥")
    assert len(sites["candidate_sites"]) == 3
    assert sites["sites"] == []
    assert M.material_availability(s, "水泥")["available"] is False
    assert M.material_availability(s, "水泥")["reason"] == "no_workshop_site"


def test_unknown_route_and_missing_buildings_are_missing_not_zero():
    """产地读数缺失要如实留痕：未知路 + `buildings` 键缺失都进 `missing`。"""
    s = _state()
    M.unlock_material(s, "水泥", "tech")
    del s.prefectures["京畿路"]["buildings"]       # 路在、buildings 键缺失 ⇒ 读数缺失
    s.prefectures.pop("两浙路")                     # 未知路
    sites = M.material_sites(s, "水泥")
    assert sites["candidate_sites"] == ["京畿路", "成都府路"]
    assert "route_buildings_missing:京畿路" in sites["missing"]
    assert "unknown_route:两浙路" in sites["missing"]
    assert sites["sites"] == ["成都府路"]            # 缺失的那路**不计入**，也不当 0 产能


# =============================================================================
# 2 · 三种来源各能解锁，且记录来源
# =============================================================================

def test_unlock_via_tech_node():
    """来源 1：科技节点解锁。"""
    s = _state(year=1121, level=70, unlocked=["M4_furnace", "C2_acid"])
    rec = M.unlock_material(s, "水泥", "tech")
    assert rec["source"] == "tech"
    assert rec["via"] == "C2_acid"                 # 主解锁节点被记录
    assert rec["year"] == 1121 and rec["month"] == 3
    by = M.material_unlocked_by(s, "水泥")
    assert by["source"] == "tech" and by["via"] == "C2_acid"
    assert M.material_unlock_status(s, "水泥")["source"] == "tech"


def test_unlock_via_craft_improvement():
    """来源 2：工艺改进（本土匠人在**既有官营作坊**内改良），不涉外来。"""
    s = _state(year=1101, level=66, unlocked=["M4_furnace"],
               workshop_routes=("京畿路",))
    rec = M.unlock_material(s, "水泥", "craft")
    assert rec["source"] == "craft"
    assert rec["via"] == "官营作坊"
    assert M.material_unlocked_by(s, "水泥")["source"] == "craft"


def test_unlock_via_trade_import():
    """来源 3：贸易引入（市舶广开 + 西学东渐 ≥ 1）。"""
    s = _state(year=1112, level=80, unlocked=["E2_coke"], west=1.0, maritime=True)
    rec = M.unlock_material(s, "钢筋", "trade")
    assert rec["source"] == "trade"
    assert rec["via"] == "市舶"
    assert M.material_unlocked_by(s, "钢筋")["source"] == "trade"
    # 钢筋解锁后才有产地/价格
    assert set(M.material_sites(s, "钢筋")["sites"]) == {"京畿路", "河北路", "利州路"}
    assert M.effective_material_price(s, "钢筋", 2500) == 2500.0


def test_unlock_source_recorded_in_existing_save_container():
    """落档策略：记录写进**既有** `state.tech` 的子键 + 资源空槽，无 schema 迁移。"""
    s = _state()
    M.unlock_material(s, "水泥", "tech")
    assert s.tech["materials"]["水泥"]["source"] == "tech"
    assert s.resources["水泥"] == {"stock": 0, "cap": 0}
    # 只新增子键，不新增顶层容器
    assert "materials" in s.tech and isinstance(s.tech["materials"], dict)


def test_double_unlock_rejected():
    """重复解锁拒绝（否则来源记录分叉）。"""
    s = _state()
    M.unlock_material(s, "水泥", "tech")
    with pytest.raises(M.MaterialTechError, match="已解锁"):
        M.unlock_material(s, "水泥", "trade")
    assert M.material_unlocked_by(s, "水泥")["source"] == "tech"      # 来源未被改写


# =============================================================================
# 3 · 前置条件：拒绝式 + reason
# =============================================================================

@pytest.mark.parametrize("kw, reason", [
    (dict(unlocked=["C2_acid"]), "tech_node_missing:M4_furnace"),          # 前置科技未备
    (dict(level=69, unlocked=["M4_furnace", "C2_acid"]), "tech_level_below:69<70"),  # 等级不足
    (dict(year=1104, level=70, unlocked=["M4_furnace", "C2_acid"]), "year_before:1104<1105"),  # 时机未到
])
def test_tech_unlock_prereq_rejected_with_reason(kw, reason):
    """科技解锁：前置科技 / 等级 / 时间任一不满足即拒绝并给可诊断 reason。"""
    s = _state(**kw)
    chk = M.check_material_prereq(s, "水泥", "tech")
    assert chk["ok"] is False
    assert chk["reason"] == reason
    assert reason in chk["missing"]
    with pytest.raises(M.MaterialTechError, match=reason):
        M.unlock_material(s, "水泥", "tech")
    assert M.material_unlocked_by(s, "水泥") is None        # 拒绝 ⇒ 没写半个记录
    assert "水泥" not in s.tech.get("materials", {})


def test_craft_unlock_requires_workshop_sites():
    """工艺改进：承载作坊未建成（或数量不足）即拒绝。"""
    s = _state(year=1111, level=80, unlocked=["E2_coke"],
               workshop_routes=("京畿路",))
    chk = M.check_material_prereq(s, "钢筋", "craft")
    assert chk["ok"] is False
    assert chk["reason"] == "sites_below:1<2"                # 钢筋要求两处以上作坊
    with pytest.raises(M.MaterialTechError, match="sites_below"):
        M.unlock_material(s, "钢筋", "craft")
    # 作坊凑齐即可
    s.prefectures["河北路"].setdefault("buildings", {})["官营作坊"] = 1
    assert M.check_material_prereq(s, "钢筋", "craft")["ok"] is True


def test_trade_unlock_requires_maritime_or_west():
    """贸易引入：市舶未广开、西学东渐不足即拒绝。"""
    s = _state(year=1112, level=80, unlocked=["E2_coke"], west=1.0, maritime=False)
    chk = M.check_material_prereq(s, "钢筋", "trade")
    assert chk["ok"] is False and chk["reason"] == "maritime_closed"
    with pytest.raises(M.MaterialTechError, match="maritime_closed"):
        M.unlock_material(s, "钢筋", "trade")

    s2 = _state(year=1112, level=80, unlocked=["E2_coke"], west=0.0, maritime=True)
    chk2 = M.check_material_prereq(s2, "钢筋", "trade")
    assert chk2["ok"] is False and chk2["reason"] == "west_below:0<1"


def test_source_not_allowed_is_reason_not_exception():
    """未声明的来源：查询给 reason（不抛），写入才抛。"""
    s = _state()
    reg = M.MATERIAL_TECH_UNLOCKS["水泥"]
    all_unlock = dict(reg["unlock"])
    reg["unlock"] = {"tech": all_unlock["tech"]}
    try:
        chk = M.check_material_prereq(s, "水泥", "trade")
        assert chk["ok"] is False and chk["reason"] == "source_not_allowed"
        assert chk["allowed_sources"] == ("tech",)
        with pytest.raises(M.MaterialTechError, match="source_not_allowed"):
            M.unlock_material(s, "水泥", "trade")
        assert "水泥" not in s.tech.get("materials", {})
    finally:
        reg["unlock"] = all_unlock


def test_illegal_source_and_unknown_material_raise():
    """非法入参拒绝式：未知来源 / 未注册材料 / None state。"""
    s = _state()
    with pytest.raises(M.MaterialTechError, match="解锁来源非法"):
        M.unlock_material(s, "水泥", "warp")
    with pytest.raises(M.MaterialTechError, match="未注册的材料"):
        M.unlock_material(s, "琉璃", "tech")
    with pytest.raises(M.MaterialTechError, match="未注册的材料"):
        M.check_material_prereq(s, "琉璃", "tech")
    with pytest.raises(TypeError):
        M.material_unlock_status(None, "水泥")


def test_base_price_illegal_is_rejected_not_zero():
    """基准价非法（非有限/负/非数值）⇒ raise，**不静默当 0**。"""
    s = _state()
    M.unlock_material(s, "水泥", "tech")
    with pytest.raises(ValueError):
        M.effective_material_price(s, "水泥", float("nan"))
    with pytest.raises(ValueError):
        M.effective_material_price(s, "水泥", -1)
    with pytest.raises(ValueError):
        M.effective_material_price(s, "水泥", "八百")
    assert M.effective_material_price(s, "水泥", None) is None  # 缺失 ⇒ None


def test_fictional_material_price_zero_is_rejected():
    """架空后世材料**不得**以 0 价入市（0 价＝白送，正犯 B4-2）。"""
    s = _state()
    M.unlock_material(s, "水泥", "tech")
    with pytest.raises(ValueError, match="不得为 0"):
        M.effective_material_price(s, "水泥", 0)
    assert M.effective_material_price(s, "水泥", 800) == 800.0
    # 有宋实物依据的材料（fictional=False）不受此限：0 就是 0，不被改写
    M.register_material_tech("熟铁", _good_entry())
    s2 = _state(unlocked=[])                  # 熟铁走工艺改进，不依赖科技节点
    M.unlock_material(s2, "熟铁", "craft")
    assert M.effective_material_price(s2, "熟铁", 0) == 0.0


# =============================================================================
# 4 · 注册表非法条目拒绝（不静默写入半个条目）
# =============================================================================

def _good_entry():
    return {
        "label": "熟铁", "dim": "熟铁", "unit": "斤",
        "fictional": False,
        "note": "宋代已有锻铁熟铁（铁料加工），非架空材料。",
        "aliases": ("wrought_iron",),
        "workshop": "官营作坊",
        "sites": ("京畿路",),
        "recipe": {"name": "锻铁坊", "recipe": {"iron": 10},
                   "output_dim": "熟铁", "yield": 8},
        "unlock": {
            "tech": {"tech_node": "E2_coke", "tech_nodes": ("E2_coke",),
                     "min_tech_level": 60},
            "craft": {"workshops": ("官营作坊",), "min_sites": 1},
            "trade": {"min_west": 1},
        },
    }


@pytest.mark.parametrize("mutate, pattern", [
    (lambda e: e.pop("label"), "缺 label"),
    (lambda e: e.pop("fictional"), "fictional"),
    (lambda e: e.pop("note"), "缺 note"),
    (lambda e: e.__setitem__("fictional", "yes"), "fictional 必须是 bool"),
    (lambda e: e.__setitem__("note", "  "), "缺 note"),
    (lambda e: e["unlock"].__setitem__("warp", {}), "未知来源"),
    (lambda e: e["unlock"]["tech"].__setitem__("min_levle", 60), "未知前置字段"),
    (lambda e: e["unlock"]["tech"].__setitem__("min_tech_level", float("inf")), "非有限值"),
    (lambda e: e["unlock"]["tech"].__setitem__("min_tech_level", -1), "为负"),
    (lambda e: e["unlock"]["tech"].pop("tech_nodes"), "缺 tech_nodes"),
    (lambda e: e["unlock"]["tech"].__setitem__("tech_node", "M9_power"), "不在 tech_nodes"),
    (lambda e: e["unlock"]["craft"].pop("workshops"), "缺 workshops"),
    (lambda e: e["unlock"]["trade"].clear(), "等于白给"),
    (lambda e: e.__setitem__("sites", ("不存在路",)), "PREFECTURE_LIST"),
    (lambda e: (e["unlock"]["tech"].__setitem__("tech_nodes", ("不存在的节点",)),
                e["unlock"]["tech"].__setitem__("tech_node", "不存在的节点")), "TECH_NODES"),
    (lambda e: e.__setitem__("workshop", "不存在的作坊"), "BUILDING_STD"),
    (lambda e: e["recipe"].__setitem__("output_dim", "别的东西"), "不一致"),
    (lambda e: e["recipe"].__setitem__("yield", 0), "必须为正"),
    (lambda e: e.__setitem__("sites", ()), "sites 为空"),
])
def test_register_material_tech_rejects_illegal_entry(mutate, pattern):
    """非法条目 ⇒ `MaterialTechError`，**且注册表里不得留下半个条目**。"""
    entry = _good_entry()
    mutate(entry)
    before = set(M.MATERIAL_TECH_UNLOCKS)
    with pytest.raises(M.MaterialTechError, match=pattern):
        M.register_material_tech("熟铁", entry)
    assert set(M.MATERIAL_TECH_UNLOCKS) == before
    assert M.resolve_material_tech("熟铁") is None


def test_register_rejects_duplicate_key_and_bad_key():
    with pytest.raises(M.MaterialTechError, match="已存在"):
        M.register_material_tech("水泥", _good_entry())
    with pytest.raises(M.MaterialTechError, match="注册键非法"):
        M.register_material_tech("  ", _good_entry())
    with pytest.raises(M.MaterialTechError, match="必须是 dict"):
        M.register_material_tech("熟铁", ["不是 dict"])


def test_register_accepts_legal_entry_and_invalidates_alias_cache():
    """合法动态注册：新材可解析（**别名缓存随注册失效**）。"""
    assert M.resolve_material_tech("熟铁") is None
    before = M.resolve_material_tech("水泥")
    got = M.register_material_tech("熟铁", _good_entry())
    assert got["dim"] == "熟铁"
    assert M.resolve_material_tech("熟铁") is not None
    assert M.resolve_material_tech("wrought_iron") is not None      # 别名随注册生效
    assert M.resolve_material_tech("水泥") is before                 # 旧条目未被扰动


def test_alias_collision_rejected():
    """别名撞车 ⇒ 拒绝（否则一条材被两条登记，来源记录会分叉）。"""
    M.register_material_tech("熟铁", _good_entry())
    clash = _good_entry()
    clash["aliases"] = ("portland_cement",)                        # 撞水泥的别名
    clash["dim"] = "熟铁"
    with pytest.raises(M.MaterialTechError, match="别名"):
        M.register_material_tech("熟铁2", clash)


# =============================================================================
# 5 · 缺失 ≠ 0 ≠ False：未记录状态必须是 unrecorded / None
# =============================================================================

def test_missing_record_container_is_unrecorded_not_false():
    """存档缺 `tech["materials"]` 容器 ⇒ **缺失**（None/unrecorded），不是"未解锁"。"""
    s = _state()
    assert M.MATERIALS_RECORD_KEY not in s.tech
    st = M.material_unlock_status(s, "水泥")
    assert st["status"] == M.STATUS_UNRECORDED
    assert st["defined"] is False
    assert st["reason"] == "record_container_missing"
    assert st["source"] is None and st["via"] is None
    assert M.is_material_unlocked(s, "水泥") is None                 # 不是 False
    assert M.material_unlocked_by(s, "水泥") is None
    assert M.material_tradable(s, "水泥") is None                     # 不是 False
    assert M.effective_material_price(s, "水泥", 800) is None         # 不是 0
    avail = M.material_availability(s, "水泥")
    assert avail["available"] is None and avail["defined"] is False


def test_malformed_record_is_unrecorded():
    """记录畸形 / 来源字段非法 ⇒ 不可判定（**不猜一个来源填上**）。"""
    s = _state()
    s.tech["materials"] = {"水泥": "不是 dict"}
    assert M.material_unlock_status(s, "水泥")["reason"].startswith("record_malformed")

    s.tech["materials"] = {"水泥": {"material": "水泥", "source": "warp"}}
    st = M.material_unlock_status(s, "水泥")
    assert st["status"] == M.STATUS_UNRECORDED
    assert st["reason"] == "record_source_invalid:'warp'"


def test_unlocked_tech_node_without_record_is_unrecorded_and_blocks_write():
    """「节点已点亮却无记录」⇒ unrecorded，且**拒绝写入**（须人工裁决，不臆断）。"""
    s = _state(level=80, year=1121, unlocked=["M4_furnace", "C2_acid"])
    s.tech["materials"] = {}
    st = M.material_unlock_status(s, "水泥")
    assert st["status"] == M.STATUS_UNRECORDED
    assert st["reason"].startswith("record_missing_but_tech_node_unlocked")
    assert M.is_material_unlocked(s, "水泥") is None
    with pytest.raises(M.MaterialTechError, match="不得臆断"):
        M.unlock_material(s, "水泥", "tech")
    assert s.tech["materials"] == {}                                # 没写进去


def test_missing_tech_readings_are_undefined_not_zero():
    """科技读数缺失 ⇒ 前置校验 `defined=False` 且 `ok=False`（不回落 0/1.0 放行）。"""
    s = _state(level=70, unlocked=["M4_furnace", "C2_acid"])
    del s.tech["level"]
    chk = M.check_material_prereq(s, "水泥", "tech")
    assert chk["ok"] is False and chk["defined"] is False
    assert chk["reason"] == "tech_level_missing"
    assert chk["detail"]["tech_level"] is None                      # 不是 0

    s2 = _state(level=70, unlocked=["M4_furnace", "C2_acid"])
    del s2.tech["unlocked"]
    chk2 = M.check_material_prereq(s2, "水泥", "tech")
    assert chk2["ok"] is False and chk2["reason"] == "tech_unlocked_list_missing"


def test_unregistered_material_status_unknown():
    """未在注册表登记的材料 ⇒ `unknown`，调用方须记 unregistered，不得兜底中性值。"""
    s = _state()
    s.tech["materials"] = {}
    st = M.material_unlock_status(s, "琉璃")
    assert st["status"] == M.STATUS_UNKNOWN
    assert st["defined"] is False and st["reason"] == "unregistered_material"
    assert M.is_material_unlocked(s, "琉璃") is None
    assert M.material_sites(s, "琉璃")["sites"] is None
    assert M.effective_material_price(s, "琉璃", 999) is None


# =============================================================================
# 6 · 读数不改 state（含 POP 挂载律）
# =============================================================================

def test_readouts_do_not_mutate_state():
    """所有读数函数零写入：连 `tech["materials"]` 容器都不许被读数创建。"""
    s = _state(year=1104, level=69, unlocked=["C2_acid"])   # 前端不满足，便于走拒绝分支
    before = _state_snapshot(s)

    M.material_unlock_status(s, "水泥")
    M.is_material_unlocked(s, "水泥")
    M.material_unlocked_by(s, "水泥")
    M.material_sites(s, "水泥")
    M.material_sites(s, "水泥", require_unlock=False)
    M.check_material_prereq(s, "水泥", "tech")
    M.check_material_prereq(s, "钢筋", "trade")
    M.material_availability(s, "水泥")
    M.effective_material_price(s, "水泥", 800)
    M.material_tradable(s, "水泥")

    assert _state_snapshot(s) == before
    assert M.MATERIALS_RECORD_KEY not in s.tech          # 读数不建容器
    assert "水泥" not in s.resources                       # 读数不建物资槽


def test_readouts_after_unlock_do_not_mutate_either():
    s = _state()
    M.unlock_material(s, "水泥", "tech")
    before = _state_snapshot(s)
    for _ in range(3):
        M.material_unlock_status(s, "水泥")
        M.material_sites(s, "水泥")
        M.check_material_prereq(s, "水泥", "craft")
        M.effective_material_price(s, "水泥", 800)
        M.material_tradable(s, "水泥")
    assert _state_snapshot(s) == before


def test_unlock_respects_pop_mount_rule_and_save_containers():
    """解锁只写既有容器（tech 子键 + 资源空槽），**不动 POP / 国库 / 内帑**。"""
    s = _state()
    w0, g0, n0 = _pop_money_grain(s)
    t0 = (float(s.treasury), float(s.imperial_treasury))
    stats0 = copy.deepcopy(s.statistics)

    M.unlock_material(s, "水泥", "tech")

    assert _pop_money_grain(s) == (w0, g0, n0)             # POP 挂载律
    assert (float(s.treasury), float(s.imperial_treasury)) == t0
    assert s.statistics == stats0                           # 不建平行统计账本
    assert set(s.tech) >= {"level", "west", "unlocked", "materials"}   # 既有容器
    assert s.resources["水泥"] == {"stock": 0, "cap": 0}    # 新材零库存，不得凭空有料


def test_unlock_logs_are_optional_and_go_to_caller_list():
    """日志走调用方列表（不写 state、不自建全局 log）。"""
    s = _state()
    log = []
    M.unlock_material(s, "水泥", "tech", log=log)
    assert len(log) == 1 and "水泥" in log[0] and "架空后世材料" in log[0]
    assert "log" not in s.tech and "log" not in s.statistics


def test_via_override_is_recorded_and_validated():
    s = _state()
    rec = M.unlock_material(s, "水泥", "trade", via="于阗商队")
    assert rec["via"] == "于阗商队"
    with pytest.raises(M.MaterialTechError, match="via 非法"):
        M.unlock_material(_state(year=1112, level=80, unlocked=["E2_coke"],
                                 west=1.0, maritime=True), "钢筋", "trade", via=7)


def test_registry_is_static_not_a_ledger():
    """注册表是纯模块常量：不随回合/状态漂移，不含任何存量型字段。"""
    s = _state()
    M.unlock_material(s, "水泥", "tech")
    for key, e in M.MATERIAL_TECH_UNLOCKS.items():
        forbidden = {"stock", "qty", "amount", "balance", "wealth", "grain",
                     "produced", "count"}
        assert not (forbidden & set(e)), f"{key} 注册表含存量型字段"


# =============================================================================
# 7 · 科技线单行接入点（Lead 接线用；本模块自身不改 settlement_tech.py）
# =============================================================================

def test_unlock_materials_for_node_unlocks_only_matching_tech_source():
    """节点点亮 ⇒ 只解锁以它为前置、且前置全备的新材；其余逐条给 reason。"""
    # 模拟 Lead 的调用点：`unlock_node()` 之后（节点已在 unlocked 里）
    s = _state(level=80, year=1121, unlocked=["M4_furnace", "C2_acid"])
    out = M.unlock_materials_for_node(s, "C2_acid")
    assert [r["material"] for r in out["unlocked"]] == ["水泥"]
    assert out["unlocked"][0]["source"] == "tech" and out["unlocked"][0]["via"] == "C2_acid"

    # 钢筋的 tech 前置含 E2_coke/E3_steel（均未点亮）⇒ 不解锁，只记 reason
    got = M.unlock_materials_for_node(s, "E2_coke")
    assert got["unlocked"] == []
    assert [x["material"] for x in got["skipped"]] == ["钢筋"]
    assert "tech_node_missing:E2_coke" in got["skipped"][0]["reason"]

    # 幂等：已解锁的不重复解锁、不重复记
    again = M.unlock_materials_for_node(s, "C2_acid")
    assert again["unlocked"] == [] and again["skipped"] == []

    # 节点本身还没点亮（调用点放错）⇒ 拒绝解锁并留 reason，不硬写记录
    s2 = _state(level=80, year=1121, unlocked=["M4_furnace"])
    bad = M.unlock_materials_for_node(s2, "C2_acid")
    assert bad["unlocked"] == []
    assert [x["material"] for x in bad["skipped"]] == ["水泥"]
    assert "tech_node_missing:C2_acid" in bad["skipped"][0]["reason"]
    assert M.MATERIALS_RECORD_KEY not in s2.tech


def test_unlock_materials_for_node_rejects_bad_node_id():
    s = _state()
    with pytest.raises(TypeError):
        M.unlock_materials_for_node(s, None)
    with pytest.raises(TypeError):
        M.unlock_materials_for_node(s, "")
    before = _state_snapshot(s)
    with pytest.raises(TypeError):
        M.unlock_materials_for_node(s, 123)
    assert _state_snapshot(s) == before
