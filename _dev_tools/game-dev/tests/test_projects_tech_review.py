# -*- coding: utf-8 -*-
"""整改③（工程）+ 整改④（科技）专项测试（工程与科技整改工程师交付）。

覆盖：
  工程：项目状态机（proposed→funded→building→operating→degraded/abandoned）、
        材料/钱不足按供给率逐步降效（不静默完成）、工匠工时约束与工役审计读数、
        营造款守恒转移、完工转运行、维持欠费降效/恢复。
  科技：能力域索引（火药/冶金/水利/历法/航海/财政/医学农学）、节点声明完整性、
        level 只作综合读数（非硬门槛）、researching 消耗预算与人才时间、
        中断保留进度（机会成本）、解锁≠全国生效（adoption 部署覆盖率）、
        west 来源制（非万能加速器）、立项经费守恒转移。

纪律：所有改动配守恒断言（ΔM_ALL==0 / 不新增 POP / 无平行账本）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core import money  # noqa: E402
from core.settlement_steps import _settle_projects, _settle_tech_research  # noqa: E402
from core.asset_context import (  # noqa: E402
    unlock_node, settle_adoption, accrue_west, start_research,
    node_prereqs_met, get_tech_node, node_adoption_coverage,
)
from content.data import (  # noqa: E402
    PROJECT_STATUS_FLOW, PROJECT_STATUS_LABELS, PROJECT_PROPOSED_TIMEOUT,
    TECH_DOMAIN_NODES, TECH_NODES, TECH_NODE_DEPLOY, TECH_NODE_MAINTENANCE,
    TECH_ADOPTION_MAX, TECH_WEST_ACCEL_CAP,
)


def _new_state():
    return GameState("史实")


def _pop_wealth(s):
    return sum(int(pp.get("wealth", 0) or 0)
               for p in s.prefectures.values() for pp in p["pops"].values())


def _pop_size_total(s):
    return sum(int(pp.get("size", 0) or 0)
               for p in s.prefectures.values() for pp in p["pops"].values())


def _full_project(**kw):
    """满足九项声明的工程模板（可按需覆盖）。"""
    proj = {
        "name": "测试工程", "status": "building", "progress": 0, "speed": 20,
        "done": False, "cost_material": {}, "cost_coin": 0, "craft_hours": 1,
        "output": {}, "duration": 3, "upkeep": 1, "depreciation": 0.01,
        "route": "京畿路", "beneficiaries": ["农"],
    }
    proj.update(kw)
    return proj


# ================================================================
# 一、工程：状态机
# ================================================================
def test_project_status_machine_declared_in_order():
    assert tuple(PROJECT_STATUS_FLOW) == (
        "proposed", "funded", "building", "operating", "degraded", "abandoned")
    for st in PROJECT_STATUS_FLOW:
        assert st in PROJECT_STATUS_LABELS, f"状态 {st} 缺中文标签"


def test_proposed_project_waits_for_funding_then_abandons_on_timeout():
    """拟议项目无款不得静默开工；超期作罢并留痕（可诊断）。"""
    s = _new_state()
    s.treasury = 0
    s.projects["p1"] = _full_project(name="待款水利", status="proposed",
                                     fund_cost=100000, cost_coin=100000)
    log = []
    _settle_projects(s, log)
    p1 = s.projects["p1"]
    assert p1["status"] == "proposed" and p1.get("done") is not True
    assert any("拟议待款" in m for m in log), "待款必须留痕（不得静默）"

    for _ in range(PROJECT_PROPOSED_TIMEOUT):
        _settle_projects(s, [])
    assert s.projects["p1"]["status"] == "abandoned", "超期未拨款应作罢"
    assert s.projects["p1"].get("done") is not True

def test_project_material_shortage_degrades_by_supply_ratio():
    """九项声明齐全时，材料不足按供给率同比例消耗与推进（不静默完成）。"""
    s = _new_state()
    s.treasury = 1_000_000
    s.resources.setdefault("铁", {"stock": 50, "cap": 100_000})
    s.resources["铁"]["stock"] = 50
    s.projects["p1"] = _full_project(
        cost_material={"铁": 100}, cost_coin=0, speed=20)
    log = []
    _settle_projects(s, log)
    p1 = s.projects["p1"]
    assert p1["progress"] == 10, f"供给率 0.5 应降效推进 10，实际 {p1['progress']}"
    assert not p1.get("done"), "降效不得静默完工"
    assert s.resources["铁"]["stock"] == 0, "材料应按供给率同比例消耗"
    assert any("降效" in m for m in log), "降效必须留痕"


def test_project_labor_hours_limit_progress_and_record_corvee():
    """工匠工时（craft_hours）不足 → 降效；工役只记审计读数，不新增人口。"""
    s = _new_state()
    s.treasury = 1_000_000
    route = "京畿路"
    art_size = int(s.prefectures[route]["pops"]["工匠"]["size"])
    avail = art_size * 0.25                      # 与 PROJECT_LABOR_RATIO 同源口径
    s.projects["p1"] = _full_project(
        route=route, craft_hours=avail * 2,      # 到位率 0.5
        cost_material={}, cost_coin=0, speed=20)
    size0 = _pop_size_total(s)
    pops0 = {c for p in s.prefectures.values() for c in p["pops"]}
    log = []
    _settle_projects(s, log)

    p1 = s.projects["p1"]
    assert p1["progress"] == 10, f"工匠到位 50% 应降效推进 10，实际 {p1['progress']}"
    assert s.statistics.get("project_corvee_time_loss", 0) > 0, "工役时间损失未留审计读数"
    assert _pop_size_total(s) == size0, "工程不得新增人口"
    assert {c for p in s.prefectures.values() for c in p["pops"]} == pops0, \
        "工程不得新增工程人口池（平行账本）"


def test_project_coin_is_conserving_transfer_and_enters_operating():
    """营造款：国库照扣、全额入民间 POP wealth、ΔM_ALL==0；完工转 operating。"""
    s = _new_state()
    s.treasury = 5_000_000
    s.resources.setdefault("铁", {"stock": 10_000, "cap": 100_000})
    s.projects["p1"] = _full_project(
        progress=90, speed=20, cost_material={"铁": 100}, cost_coin=500_000)
    w0, m0, t0 = _pop_wealth(s), money.m_all(s), s.treasury
    _settle_projects(s, [])

    p1 = s.projects["p1"]
    assert p1.get("done") is True
    assert p1["status"] == "operating", "完工应转入 operating 状态"
    assert t0 - s.treasury == 500_000, "财政成本丢失（国库未扣）"
    assert _pop_wealth(s) - w0 == 500_000, "工程款未回流民间（无对手方销毁）"
    assert money.m_all(s) - m0 == 0, "工程款破坏货币守恒"
    assert s.resources["铁"]["stock"] == 9_900, "材料未扣"


def test_operating_project_degrades_on_maintenance_arrears_then_recovers():
    """运行资产：维持欠费 → 产能折旧降级；维持到位 → 恢复（折旧可逆）。"""
    s = _new_state()
    s.projects["p1"] = _full_project(status="operating", done=True, capacity=1.0,
                                     depreciation=0.03)
    s.statistics["upkeep_arrears"] = s.statistics.get("upkeep_arrears", 0)
    log = []
    for _ in range(25):
        s.statistics["upkeep_arrears"] = s.statistics.get("upkeep_arrears", 0) + 1000
        _settle_projects(s, log)
    p1 = s.projects["p1"]
    assert p1["status"] == "degraded", f"欠费应降级，实际 {p1['status']}"
    assert p1["capacity"] < 0.6
    assert any("降效" in m for m in log)

    for _ in range(25):                          # 停止欠费 → 维护到位 → 回升
        _settle_projects(s, [])
    assert s.projects["p1"]["status"] == "operating", "维持到位应恢复运行"
    assert s.projects["p1"]["capacity"] >= 0.6

# ================================================================
# 二、科技：能力域 / 节点声明 / level 读数
# ================================================================
def test_tech_domain_index_covers_required_capabilities():
    """TECH_INFO.level 之外，火药/冶金/水利/历法/航海/财政/医学农学 均有可研节点。"""
    required = ["火药", "冶金", "水利", "历法", "航海", "财政", "医学农学"]
    for dom in required:
        assert dom in TECH_DOMAIN_NODES, f"缺能力域 {dom}"
        ids = TECH_DOMAIN_NODES[dom]
        assert ids, f"能力域 {dom} 无节点"
        for nid in ids:
            assert get_tech_node(nid) is not None, f"{dom} 指向不存在的节点 {nid}"


def test_tech_node_declarations_complete():
    """节点须声明前置/成本（含工匠学者投入）/效果；有部署路径者须声明建筑与维护。"""
    for node in TECH_NODES:
        assert len(node) == 10, f"节点元组长度异常：{node[0]}"
        nid, prereq, cost, effect = node[0], node[5], node[8], node[9]
        assert isinstance(prereq, list), f"{nid} 前置未声明"
        assert isinstance(cost, dict), f"{nid} 成本未声明"
        for k in ("silver", "months", "masters"):
            assert k in cost, f"{nid} 成本缺 {k}"
        assert isinstance(effect, dict) and effect, f"{nid} 效果未声明"
        if nid in TECH_NODE_DEPLOY:
            assert TECH_NODE_DEPLOY[nid], f"{nid} 部署建筑为空"
            assert TECH_NODE_MAINTENANCE.get(nid, 0) > 0, f"{nid} 有部署但无维护声明"


def test_tech_level_is_readout_not_hard_gate():
    """总体 level 只作综合读数：能力由前置节点 + 副指标判定。"""
    s = _new_state()
    e3 = get_tech_node("E3_steel")
    # 前置齐 + west 副指标跳过 → level=0 仍可研（level 不再是关卡）
    s.tech["unlocked"] = ["E2_coke"]
    s.tech["level"] = 0
    s.tech["west"] = 0
    assert node_prereqs_met(s, e3) is True, "level 仍在充当硬门槛"

    # 副指标（calendar）不足 → 即便 level=100 也不可研（真正的能力门槛是域节点/副指标）
    a0 = get_tech_node("A0_calendar")
    s.tech["unlocked"] = ["I0_block"]
    s.tech["level"] = 100
    s.tech["calendar"] = 10
    assert node_prereqs_met(s, a0) is False, "副指标未满足却放行"


# ================================================================
# 三、科技：researching 消耗预算/人才时间，中断保留进度
# ================================================================
def test_research_consumes_budget_and_stalls_keeping_progress():
    """经费不继 → 中断保留进度并记机会成本；有款 → 预算守恒转移入 POP。"""
    s = _new_state()
    s.tech["unlocked"] = list(s.tech.get("unlocked", []))
    s.tech["researching"]["M2_spindle"] = {
        "progress": 10.0, "months": 9, "masters": 3,
        "monthly_cost": 20000, "idle_months": 0,
    }
    s.treasury = 0
    m0 = money.m_all(s)
    log = []
    _settle_tech_research(s, log)
    r = s.tech["researching"]["M2_spindle"]
    assert r["progress"] == 10.0, "经费不继仍推进（不得静默）"
    assert r["idle_months"] >= 1, "中断未记机会成本"
    assert s.statistics.get("research_idle_months", 0) >= 1
    assert any("经费不继" in m for m in log), "中断必须可诊断"
    assert money.m_all(s) == m0, "停滞期不应有货币变化"

    s.treasury = 1_000_000
    m0b = money.m_all(s)
    w0, t0 = _pop_wealth(s), s.treasury
    _settle_tech_research(s, [])
    assert s.tech["researching"]["M2_spindle"]["progress"] > 10.0, "有款应推进"
    assert t0 - s.treasury == 20000, "月预算未实扣"
    assert _pop_wealth(s) - w0 == 20000, "研发经费未入 POP（无对手方销毁）"
    assert money.m_all(s) - m0b == 0, "研发经费破坏货币守恒"


def test_research_rate_improves_with_schools_and_literacy():
    def _one_month(state):
        state.tech["researching"]["M2_spindle"] = {
            "progress": 0.0, "months": 12, "masters": 2,
            "monthly_cost": 0, "idle_months": 0,
        }
        _settle_tech_research(state, [])
        return state.tech["researching"]["M2_spindle"]["progress"]

    low = _one_month(_new_state())
    s = _new_state()
    s.literacy = 90.0
    s.projects["sch"] = {"type": "学校", "level": 2, "name": "州学"}
    high = _one_month(s)
    assert high > low, f"学校/识字率未提升研发速率：{low} -> {high}"


def test_start_research_funding_is_conserving_transfer():
    """立项首月经费：国库 → 学者/工匠 POP 的守恒转移（非无对手方销毁）。"""
    s = _new_state()
    w0, m0, t0 = _pop_wealth(s), money.m_all(s), s.treasury
    msg = start_research(s, "I2_metaltype")
    assert "I2_metaltype" in s.tech.get("researching", {}), msg
    assert s.treasury < t0, "立项未扣经费"
    assert _pop_wealth(s) - w0 == t0 - s.treasury, "经费未全额入 POP"
    assert money.m_all(s) - m0 == 0, "立项经费破坏货币守恒"
    assert s.tech["researching"]["I2_metaltype"].get("monthly_cost", 0) >= 1


# ================================================================
# 四、科技：解锁≠全国生效（adoption 部署覆盖率）
# ================================================================
def test_unlock_is_not_national_effect_until_deployed():
    """解锁只入资产（coverage 0）；建成部署建筑后按覆盖率产生效果。"""
    s = _new_state()
    y0 = float(s.land.get("yield", 1.0) or 1.0)
    unlock_node(s, "C4_fertilizer")
    assert s.tech["assets"]["C4_fertilizer"]["adoption"] == 0.0
    assert abs(float(s.land.get("yield", 1.0)) - y0) < 1e-9, "未部署却已全国生效"

    deploy = TECH_NODE_DEPLOY["C4_fertilizer"]
    s.projects["d1"] = {"name": deploy, "status": "operating", "done": True,
                        "level": 4}
    settle_adoption(s, [])
    assert s.tech["assets"]["C4_fertilizer"]["adoption"] == TECH_ADOPTION_MAX
    assert abs(float(s.land["yield"]) - (y0 + 0.20)) < 1e-9, "部署后效果未生效"

    settle_adoption(s, [])                       # 幂等：不得重复全额计账
    assert abs(float(s.land["yield"]) - (y0 + 0.20)) < 1e-9, "覆盖率增量被重复施加"


def test_adoption_decays_when_maintenance_unpaid():
    """维护欠费 → 部署覆盖率折旧（维护 → 折旧）。"""
    s = _new_state()
    unlock_node(s, "C4_fertilizer")
    deploy = TECH_NODE_DEPLOY["C4_fertilizer"]
    s.projects["d1"] = {"name": deploy, "status": "operating", "done": True,
                        "level": 4}
    settle_adoption(s, [])
    assert s.tech["assets"]["C4_fertilizer"]["adoption"] == TECH_ADOPTION_MAX

    s.statistics["upkeep_arrears"] = s.statistics.get("upkeep_arrears", 0) + 5000
    settle_adoption(s, [])
    assert s.tech["assets"]["C4_fertilizer"]["adoption"] < TECH_ADOPTION_MAX, \
        "维持欠费未触发覆盖率折旧"


# ================================================================
# 五、科技：west 来源制（非万能加速器）
# ================================================================
def test_west_requires_concrete_sources_and_is_not_universal():
    s = _new_state()
    w0 = float(s.tech.get("west", 0) or 0)
    assert accrue_west(s) == 0.0, "无来源却增长 west"
    assert float(s.tech.get("west", 0) or 0) == w0

    s.maritime["open"] = True
    gain = accrue_west(s)
    assert gain > 0, "海路通商（贸易来源）应累积 west"
    assert s.tech["west_sources"].get("trade") == 1, "west 来源未留痕"

    s.maritime["open"] = False                   # 来源消失 → 不再增长
    w1 = float(s.tech["west"])
    assert accrue_west(s) == 0.0
    assert float(s.tech["west"]) == w1

    # 对研发的加速有封顶，不作万能加速器
    assert TECH_WEST_ACCEL_CAP <= 1.25
