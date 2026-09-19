# -*- coding: utf-8 -*-
"""整改①（经济与物价）+ 联动（第五节）专项测试。

覆盖：
 1. 固定回合顺序（生产→工程投入→POP收入消费→粮食商品市场→税收转移→
    货币信用→物价→集团读数）——AST 取真实管线调用序列断言相位单调。
 2. 失败整月回滚——`core/commands.settle_local` 异常即回滚、回合不推进。
 3. 粮价月度上限（纯函数 + 物价相位）。
 4. 路线物价由 供给/需求/库存/运输/货币有效供给 派生；全国 PRICE_LEVEL 只作加权读数。
 5. 生产/工程声明契约 + 材料不足逐步降效（不得静默）。
 6. 税/俸先落 POP wealth，财政步不得直写利益集团。
 7. 联动：过度发行→物价↑；工程须持续维护（国库→民间守恒转移）。
所有断言均为可失败的实质断言（无恒真/自比式）。
"""
import ast
import copy
import inspect
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.game_state_econ import (  # noqa: E402
    cap_monthly_price, project_declaration_gaps, project_supply_ratio,
    PROJECT_DECLARATION_FIELDS,
)
from core.settlement_steps import (  # noqa: E402
    _settle_econ_prices, _settle_projects, _settle_upkeep, _settle_finance,
)
from content.data import (  # noqa: E402
    GRAIN_PRICE_MONTHLY_CAP, PRICE_LEVEL_MONTHLY_CAP,
    GRAIN_PRICE_MIN, GRAIN_PRICE_MAX, PRICE_FLOOR_HARD, PRICE_CEIL_HARD,
)


def _new_state():
    return GameState("史实")


def _pop_wealth(s):
    return sum(int(pp.get("wealth", 0) or 0)
               for p in s.prefectures.values() for pp in p["pops"].values())


def _pipeline_settle_calls():
    """从 run_monthly_settlement 的 AST 取**真实**调用序列（行号排序，去掉票据步）。"""
    import core.settlement as S
    tree = ast.parse(inspect.getsource(S.run_monthly_settlement))
    calls = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id.startswith("_settle")):
            calls.append((node.lineno, node.func.id))
    calls.sort()
    return [name for _, name in calls]


# ---------------------------------------------------------------
# 1. 固定回合顺序
# ---------------------------------------------------------------
def test_econ_phase_order_is_fixed_and_monotonic():
    """经济相位必须按文档顺序出现：生产→工程→市场→税收→货币信用→物价→集团读数。"""
    seq = _pipeline_settle_calls()
    _phases = [
        ("\u751f\u4ea7", ("_settle_economy", "_settle_land_local",
                          "_settle_region_deepen", "_settle_literacy")),
        ("\u5de5\u7a0b\u6295\u5165/\u7ef4\u62a4", ("_settle_projects", "_settle_workshops",
                                                    "_settle_upkeep")),
        ("\u7cae\u98df\u5546\u54c1\u5e02\u573a", ("_settle_granary",)),
        ("\u7a0e\u6536\u8f6c\u79fb", ("_settle_finance",)),
        ("\u8d27\u5e01\u4fe1\u7528", ("_settle_extensions",)),
        ("\u7269\u4ef7", ("_settle_econ_prices",)),
        ("\u96c6\u56e2\u8bfb\u6570", ("_settle_faction_metrics",)),
    ]
    idx = {n: i for i, n in enumerate(seq)}
    last = -1
    for pname, names in _phases:
        assert all(n in idx for n in names), f"管线缺相位 {pname} 的步：{[n for n in names if n not in idx]}"
        pos = min(idx[n] for n in names)
        assert pos > last, f"经济相位顺序错误：{pname} 出现在上一相位之前（{names}）"
        last = max(idx[n] for n in names)
    # 文档点名的三条硬顺序
    assert idx["_settle_projects"] < idx["_settle_granary"], "工程投入必须在粮食市场之前"
    assert idx["_settle_granary"] < idx["_settle_finance"], "粮食市场必须在税收之前"
    assert idx["_settle_finance"] < idx["_settle_extensions"], "税收必须在货币信用之前"
    assert idx["_settle_extensions"] < idx["_settle_econ_prices"], "货币信用必须在物价之前"
    assert idx["_settle_econ_prices"] < idx["_settle_faction_metrics"], "物价必须在集团读数之前"


# ---------------------------------------------------------------
# 2. 失败整月回滚
# ---------------------------------------------------------------
def test_failed_settlement_rolls_back_whole_month(monkeypatch):
    """任一结算步抛异常：整月状态回滚、回合不推进（可安全重试）。"""
    import core.settlement as _S
    from core.commands import settle_local

    s = _new_state()
    t0 = s.turn
    pop0 = s.population
    sizes0 = {n: {k: pp["size"] for k, pp in p["pops"].items()}
              for n, p in s.prefectures.items()}
    _before = copy.deepcopy(s.statistics)

    def _boom(state, log):
        raise RuntimeError("模拟结算步失败（整改①-1 回滚用例）")

    monkeypatch.setattr(_S, "_settle_finance", _boom)
    with pytest.raises(RuntimeError):
        settle_local(s)

    assert s.turn == t0, "失败后回合被推进（应整月回滚）"
    assert s.population == pop0, "失败后 population 未回滚（说明半结算脏状态）"
    assert {n: {k: pp["size"] for k, pp in p["pops"].items()}
            for n, p in s.prefectures.items()} == sizes0, "失败后 POP size 未回滚"
    assert s.statistics == _before, "失败后 statistics 未回滚"


# ---------------------------------------------------------------
# 3. 粮价月度上限
# ---------------------------------------------------------------
def test_cap_monthly_price_pure_function():
    assert cap_monthly_price(1.0, 3.0, 0.15) == pytest.approx(1.15)
    assert cap_monthly_price(1.0, 0.1, 0.15) == pytest.approx(0.85)
    assert cap_monthly_price(1.0, 1.10, 0.15) == pytest.approx(1.10), "未超限不得改动"
    assert cap_monthly_price(0.0, 9.9, 0.15) == 9.9, "prev<=0 不设限（兼容旧档）"
    assert cap_monthly_price(1.0, 9.9, -1) == 9.9, "非法 cap 不得放大"
    with pytest.raises(ValueError):
        cap_monthly_price(None, 1.0, 0.1)


def test_settle_econ_prices_enforces_monthly_cap_and_weighted_readout():
    """物价相位：全国指数/粮价/路线价均受月度上限；全国值是路线价的人口加权读数。"""
    s = _new_state()
    s._price_month_open = {"level": 1.0, "grain": 1.0,
                           "route": {n: 1.0 for n in s.prefectures}}
    for p in s.prefectures.values():
        for pop in p["pops"].values():
            pop["wealth"] = 10_000_000_000          # 天量货币 → 目标价触顶
    log = []
    _settle_econ_prices(s, log)

    assert abs(s.price_level - 1.0) <= PRICE_LEVEL_MONTHLY_CAP + 1e-9, \
        f"全国物价指数单月涨幅越限：{s.price_level}"
    assert abs(s.grain_price - 1.0) <= GRAIN_PRICE_MONTHLY_CAP + 1e-9, \
        f"全国粮价单月涨幅越限：{s.grain_price}"
    for n, p in s.prefectures.items():
        assert abs(p["grain_price"] - 1.0) <= GRAIN_PRICE_MONTHLY_CAP + 1e-9, \
            f"{n} 路线粮价单月涨幅越限：{p['grain_price']}"
        assert GRAIN_PRICE_MIN - 1e-9 <= p["grain_price"] <= GRAIN_PRICE_MAX + 1e-9
    assert PRICE_FLOOR_HARD - 1e-9 <= s.price_level <= PRICE_CEIL_HARD + 1e-9

    _tot = sum(p["population"] for p in s.prefectures.values())
    _exp = sum(p["grain_price"] * p["population"] for p in s.prefectures.values()) / _tot
    assert abs(s.grain_price_readout - _exp) < 1e-3, "全国粮价读数不是路线价的人口加权"
    assert abs(s.national_grain_price_weighted() - _exp) < 1e-3


# ---------------------------------------------------------------
# 4. 路线物价派生因子
# ---------------------------------------------------------------
def test_route_grain_price_derives_from_transport_stock_money():
    s = _new_state()
    s.price_level = s.calc_price_level()
    s.grain_price = s.calc_grain_price()
    base = s.calc_region_grain_price("京畿路")
    assert GRAIN_PRICE_MIN <= base <= GRAIN_PRICE_MAX

    # 运输：漕运阻塞 → 外粮难入 → 加价
    s.canal_block = 100
    _blocked = s.calc_region_grain_price("京畿路")
    assert _blocked > base * 1.05, f"漕运阻塞未抬升路线粮价：{base} -> {_blocked}"
    s.canal_block = 0

    # 库存：本地仓廪充足 → 抑价
    _p = s.prefectures["京畿路"]
    _keep_stock = _p.get("changping_stock", 0)
    _p["changping_stock"] = int(_p.get("population", 1_000_000))
    _stocky = s.calc_region_grain_price("京畿路")
    assert _stocky < base, f"库存充足未抑价：{base} -> {_stocky}"
    _p["changping_stock"] = _keep_stock

    # 货币有效供给：M1 翻倍 → 加价
    _mid = s.calc_region_grain_price("京畿路")
    s.money_supply = float(s.money_supply) * 2.0
    _money_up = s.calc_region_grain_price("京畿路")
    assert _money_up > _mid, f"货币有效供给增加未抬升路线粮价：{_mid} -> {_money_up}"


def test_over_issuance_raises_price_level():
    """联动⑤：过度发行（交子超发）→ 货币有效供给↑ → 物价↑。"""
    s = _new_state()
    _base = s.calc_price_level()
    s.jiaozi["issued"] = int(s.jiaozi.get("issued", 0)) + 50_000_000
    _after = s.calc_price_level()
    assert _after > _base, f"过度发行未抬升物价：{_base} -> {_after}"


# ---------------------------------------------------------------
# 5. 生产/工程声明 + 材料不足逐步降效
# ---------------------------------------------------------------
def test_project_declaration_contract():
    assert len(PROJECT_DECLARATION_FIELDS) == 9, "生产/工程必须声明九项"
    full = {
        "cost_material": {"铁": 10}, "cost_coin": 100, "craft_hours": 5,
        "output": {"granary_cap_add": 1}, "duration": 3, "upkeep": 2,
        "depreciation": 0.01, "route": "京畿路", "beneficiaries": ["\u519c"],
    }
    assert project_declaration_gaps(full) == [], f"完整声明被判缺：{project_declaration_gaps(full)}"
    _gaps = project_declaration_gaps({})
    assert len(_gaps) == 9, f"空声明的缺口数应为 9，实际 {len(_gaps)}"
    assert set(_gaps) == {label for _, _, label in PROJECT_DECLARATION_FIELDS}


def test_project_material_shortage_degrades_not_silently_stalls():
    """材料不足 → 按最短板同比例消耗与推进（逐步降效），且缺声明可诊断。"""
    s = _new_state()
    s.treasury = 1_000_000
    s.resources.setdefault("铁", {"stock": 50, "cap": 100_000})
    s.resources["铁"]["stock"] = 50
    s.projects["p1"] = {
        "name": "测试工程", "progress": 0, "speed": 20, "done": False,
        "cost_material": {"铁": 100}, "cost_coin": 0, "output": {},
    }
    log = []
    _settle_projects(s, log)
    p1 = s.projects["p1"]
    assert p1["progress"] == 10, f"应按供给率 0.5 降效推进，实际 {p1['progress']}"
    assert not p1["done"], "降效不得静默完工"
    assert s.resources["铁"]["stock"] == 0, "材料应按供给率同比例消耗"
    assert any("声明不全" in m for m in log), "缺声明必须可诊断（不得静默成功）"

    # 完全无料 → 停滞，且必须留痕
    s.projects["p2"] = {
        "name": "测试工程2", "progress": 5, "speed": 20, "done": False,
        "cost_material": {"铁": 100}, "cost_coin": 0, "output": {},
    }
    s.resources["铁"]["stock"] = 0
    log2 = []
    _settle_projects(s, log2)
    assert s.projects["p2"]["progress"] == 5, "完全无料应停滞"
    assert any("缺料停滞" in m for m in log2), "停滞必须留痕（不得静默成功）"


def test_project_supply_ratio_is_binding_shortest():
    proj = {"cost_material": {"铁": 100, "铜": 50}, "cost_coin": 1000}
    # 铁 50%（短板）、铜充足、钱充足 → 0.5
    assert project_supply_ratio(proj, {"铁": {"stock": 50}, "铜": {"stock": 999}},
                                treasury=999_999) == pytest.approx(0.5)
    # 钱成短板
    assert project_supply_ratio({"cost_coin": 1000, "cost_material": {}},
                                {}, treasury=250) == pytest.approx(0.25)
    # 无成本 → 1.0
    assert project_supply_ratio({}, {}, 0) == 1.0


# ---------------------------------------------------------------
# 6. 税/俸先落 POP，财政步不得直写集团
# ---------------------------------------------------------------
def test_finance_flows_through_pop_not_factions():
    """税收/俸禄先改 POP wealth，再由派生步读 POP；财政步不得直接给集团写数。"""
    s = _new_state()
    fac0 = copy.deepcopy(s.factions)
    w0 = _pop_wealth(s)
    inc0 = s.statistics.get("total_income", 0)

    _settle_finance(s, [])

    assert s.factions == fac0, "财政步直接改写了利益集团（违反①-4：禁止直接给集团发钱/写数）"
    assert _pop_wealth(s) != w0, "财政步必须经 POP wealth 收税/发俸"
    assert s.statistics.get("total_income", 0) > inc0, "税收未入国库/statistics"
    src = inspect.getsource(_settle_finance)
    assert "factions" not in src, "财政步源码出现 factions 直写入口"

    # 至少一笔 POP 财富减少（纳税）、一笔增加（俸禄/常费回流）
    s2 = _new_state()
    _w_before = [[int(pp.get("wealth", 0) or 0) for pp in p["pops"].values()]
                 for p in s2.prefectures.values()]
    _settle_finance(s2, [])
    _deltas = [int(pp.get("wealth", 0) or 0) - _w_before[i][j]
               for i, p in enumerate(s2.prefectures.values())
               for j, pp in enumerate(p["pops"].values())]
    assert any(d < 0 for d in _deltas), "没有 POP 实际纳税（钱未从 POP 财富出）"
    assert any(d > 0 for d in _deltas), "俸禄/常费未回流到 POP（钱未落 POP）"


# ---------------------------------------------------------------
# 7. 联动：工程须持续维护（国库→民间，货币守恒）
# ---------------------------------------------------------------
def test_upkeep_is_conserving_treasury_to_pop_transfer():
    """工程提产能但需维护：维持费是国库→民间的守恒转移（ΔM_ALL == 0）。"""
    from content.data import WORKSHOP_VALUE
    from core import money as _money

    s = _new_state()
    s.treasury = 50_000_000
    s.workshops["w1"] = {"name": "酒坊", "active": True, "recipe": {},
                         "output_dim": None, "yield": 0}
    assert WORKSHOP_VALUE > 0, "用例前提：作坊有名义造价"
    w0, m0, t0 = _pop_wealth(s), _money.m_all(s), s.treasury
    log = []
    paid = _settle_upkeep(s, log)
    assert paid > 0, "有资产必须产生维持费"
    assert t0 - s.treasury == paid, "维持费未从国库实扣"
    assert _pop_wealth(s) - w0 == paid, "维持费未全额回流民间（无对手方转移）"
    assert _money.m_all(s) - m0 == 0, "维持费破坏了货币守恒（ΔM_ALL != 0）"
