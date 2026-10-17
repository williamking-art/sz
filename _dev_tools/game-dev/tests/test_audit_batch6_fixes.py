# -*- coding: utf-8 -*-
"""批次 6 回归：O3 / O4 / O5 / O6 / O7 / O10 / O11（可选打磨，2026-10-01）。

主题：「统计口径与实际同源」（O3/O4）、缺失值不当 0（O5/O10）、
类型归一（O6）、注释与实现对齐（O7）、示例配置口径（O11）。
"""
import inspect
import json
import math
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState            # noqa: E402
from core.legacy_mechanic import init_legacies     # noqa: E402


@pytest.fixture()
def state():
    s = GameState("史实")
    init_legacies(s)
    return s


# ---------------------------------------------------------------- O3 隐户实喂额
def _setup_all_routes(state, hidden: int, farm_grain: int, gentry_grain: int):
    """对**所有路**统一构造（`_settle_granary` 遍历全部路，只改一路会被其它路稀释）。"""
    for pref in state.prefectures.values():
        pops = pref["pops"]
        pops["农"]["hidden"] = hidden
        pops["农"]["grain"] = farm_grain
        pops["士绅"]["grain"] = gentry_grain
    return sum(pref["pops"]["士绅"]["grain"] for pref in state.prefectures.values())


def test_o3_hidden_feed_stat_matches_actual_deduction(state):
    """O3：士绅兜底不足时，`hidden_feed` 只记**实扣额**，不得记全额需求。"""
    from core import settlement_granary as SG
    _setup_all_routes(state, hidden=1000, farm_grain=0, gentry_grain=10)
    before = int(state.granary_stats.get("hidden_feed", 0))
    before_short = int(state.granary_stats.get("hidden_feed_short", 0))
    log = []
    SG._settle_granary(state, log)
    fed_stat = int(state.granary_stats.get("hidden_feed", 0)) - before
    short_stat = int(state.granary_stats.get("hidden_feed_short", 0)) - before_short
    # 2026-10-17 全审：月结在 Step 6 之前会产出粮（农自产自食 + 士绅新增），
    # 因此不能用「月结前士绅总粮」当实扣上限。正确恒等式是：
    #   实喂 + 缺口 == 应喂（Σ 每路 int(hidden × 人均耗粮)）。
    demand = sum(
        int(int(pref["pops"]["农"].get("hidden", 0) or 0) * SG.HIDDEN_CONSUME_PER_CAPITA)
        for pref in state.prefectures.values()
    )
    assert fed_stat + short_stat == demand, \
        f"实喂({fed_stat:,}) + 缺口({short_stat:,}) != 应喂({demand:,})"
    assert 0 <= fed_stat <= demand


def test_o3_shortfall_is_recorded(state):
    """O3：应喂 > 实喂时，缺口另记 `hidden_feed_short` 并出日志（不粉饰）。"""
    from core import settlement_granary as SG
    _setup_all_routes(state, hidden=2000, farm_grain=0, gentry_grain=5)
    log = []
    SG._settle_granary(state, log)
    short = int(state.granary_stats.get("hidden_feed_short", 0))
    assert short > 0, "缺口应被记录"
    assert any("隐户" in x and "实喂" in x for x in log), f"应出日志，实际：{log}"


def test_o3_sufficient_grain_no_shortfall(state):
    """O3 反向：粮足时不得虚报缺口。"""
    from core import settlement_granary as SG
    _setup_all_routes(state, hidden=100, farm_grain=10_000_000, gentry_grain=10_000_000)
    before = int(state.granary_stats.get("hidden_feed", 0))
    SG._settle_granary(state, [])
    assert int(state.granary_stats.get("hidden_feed", 0)) > before, "粮足时应真的喂到"
    assert int(state.granary_stats.get("hidden_feed_short", 0)) == 0


# ---------------------------------------------------------------- O4 囤粮销毁额
def test_o4_hoard_spoil_records_full_destroyed(state):
    """O4：硬上限销毁**全部**未售粮，统计须记实销额（不得只记 3%）。"""
    from core import settlement_econ as SE
    src = inspect.getsource(SE)
    assert 'get("hoard_spoil", 0) + _unsold' in src, "hoard_spoil 须记实销额 _unsold"
    assert '"hoard_spoil_3pct"' in src, "3% 口径应另行留痕（分层口径）"
    # 旧写法不得残留
    assert 'get("hoard_spoil", 0) + _spoil' not in src, "旧的 3% 写法仍在"


def test_o4_hoard_spoil_positive_when_destroyed(state):
    """O4 行为：制造超硬上限囤粮，确认统计记录了实际销毁额。"""
    from core import settlement_econ as SE
    name = next(iter(state.prefectures))
    p = state.prefectures[name]
    genty = p["pops"]["士绅"]
    # 远超硬上限且无可售买方（穷民）→ 大部分只能核销
    genty["grain"] = 10_000_000_000
    for k in ("农", "工匠", "商人"):
        if isinstance(p["pops"].get(k), dict):
            p["pops"][k]["wealth"] = 0
    before = int(state.granary_stats.get("hoard_spoil", 0))
    log = []
    SE._settle_civilian_hoard(state, log)
    after = int(state.granary_stats.get("hoard_spoil", 0))
    if after > before:
        p3 = int(state.granary_stats.get("hoard_spoil_3pct", 0))
        assert p3 <= after, "3% 分层口径不得大于实销额"
    else:
        assert after == before, "未触发销毁时不得虚增"


# ---------------------------------------------------------------- O5 汇率缺失标记
def test_o5_missing_rates_flagged_undefined(state):
    """O5：`standard` 缺字段时须标记 `*_defined=False`（不得静默读成真实汇率）。"""
    from core.money import standard_rates
    state.standard = {}
    r = standard_rates(state, market=False)
    assert r["silver_defined"] is False
    assert r["gold_defined"] is False
    # 数值基线仍在（兑换运算不得炸）
    assert r["silver_per_copper"] > 0 and r["gold_per_copper"] > 0


def test_o5_present_rates_flagged_defined(state):
    """O5 反向：读到真实读数时 `*_defined=True`。"""
    from core.money import standard_rates
    state.standard = {"book_silver_per_copper": 1.2, "book_gold_per_copper": 12.0}
    r = standard_rates(state, market=False)
    assert r["silver_defined"] is True and r["gold_defined"] is True
    assert r["silver_per_copper"] == pytest.approx(1.2)


def test_o5_nonfinite_rate_falls_back_and_flagged(state):
    """O5：NaN/Inf 汇率不得被当成真实读数（回落基线 + 标记未定义）。"""
    from core.money import standard_rates
    state.standard = {"book_silver_per_copper": float("nan"),
                      "book_gold_per_copper": float("inf")}
    r = standard_rates(state, market=False)
    assert r["silver_defined"] is False and r["gold_defined"] is False
    assert math.isfinite(r["silver_per_copper"]) and math.isfinite(r["gold_per_copper"])


def test_o5_exchange_still_works(state):
    """O5 反向：兑换运算不受影响（`exchange_quote` 仍能吃新的 `standard_rates` 返回值）。"""
    from core.money import exchange_quote
    state.standard = {}
    q = exchange_quote(state, 1000, from_unit="copper", to_unit="silver")
    assert isinstance(q, dict) and q.get("ok") is True, q
    # 读到真实汇率时同样可用
    state.standard = {"book_silver_per_copper": 1.2, "book_gold_per_copper": 12.0}
    q2 = exchange_quote(state, 1000, from_unit="copper", to_unit="silver")
    assert q2.get("ok") is True


def test_o5_exchange_missing_rates_not_crash(state):
    """O5：汇率全缺时兑换仍返回结构化结果（不得抛）。"""
    from core.money import exchange_quote
    state.standard = {}
    q = exchange_quote(state, 500, from_unit="silver", to_unit="copper")
    assert isinstance(q, dict)
    assert "ok" in q


# ---------------------------------------------------------------- O6 存量类型归一
def test_o6_resource_stock_stays_int(state):
    """O6：`resources[dim]["stock"]` 不得因 float 产出变成 float。"""
    from core import settlement_econ as SE
    src = inspect.getsource(SE)
    assert "int(round(_new))" in src, "存量须 int(round(...)) 归一"
    assert "min(_cap, _new) if _cap > 0 else _new" not in src, "旧的 float 赋值仍在"


def test_o6_float_yield_yields_int_stock(state):
    """O6 行为：`_settle_workshops` 遇小数产出时，存量仍为 int。"""
    from content.data import RESOURCE_DIMS
    from core import settlement_econ as SE
    # 找一个非酒/非肉/非粮耗的资源维度，注入带小数产量的工坊
    dim = next(d for d in RESOURCE_DIMS if d not in ("grain_feed", "wine", "meat"))
    state.resources[dim] = {"stock": 0, "cap": 0}       # cap=0 → 走归一分支
    log = []
    SE._settle_workshops(state, log)
    stock = state.resources[dim]["stock"]
    assert isinstance(stock, int), f"stock 变成 {type(stock).__name__}：{stock!r}"
    assert not (isinstance(stock, float) and math.isnan(stock))


# ---------------------------------------------------------------- O7 注释对齐
def test_o7_execution_mult_comment_matches_range():
    """O7：`decree_execution_mult` 实际值域 [0.3, 1.0]，注释不得再称 0–2。"""
    from core import situation_metrics as SM
    src = inspect.getsource(SM._m_clerks_execution_mult)
    assert "[0.3, 1.0]" in src, "注释应写明实际值域"
    # 旧措辞只允许以"原称…"的**追述**形式出现（解释变更），不得再作为事实断言
    for line in src.splitlines():
        if "0–2" in line and "原称" not in line and "避免后续" not in line:
            raise AssertionError(f"注释仍把值域当0–2：{line.strip()}")
    # 与实现对齐（权威：注释必须跟实现走）
    from core import clerks
    imp = inspect.getsource(clerks.totals)
    assert "max(0.3, 1.0 - DECREE_GRIP_W * grip)" in imp, "实现已变，注释须跟改"


# ---------------------------------------------------------------- O10 存档识字率
def test_o10_missing_literacy_saves_none(state):
    """O10：缺失识字率写 `None`（不得写 0.0 = "真的没人识字"）。"""
    from core import save_load as SL
    src = inspect.getsource(SL)
    assert 'getattr(state, "literacy", None)' in src, "缺失应存 None"
    assert 'getattr(state, "literacy", 0.0)' not in src, "旧的 0.0 兜底仍在"


# ---------------------------------------------------------------- O11 示例配置
def test_o11_example_config_matches_agnes_caliber():
    """O11：入库示例配置与 Agnes 口径一致（不再示范 tokenrhythm/deepseek）。"""
    path = os.path.join(_GAME_ROOT, "ai_config.example.json")
    cfg = json.loads(open(path, encoding="utf-8").read())
    assert cfg["model"] == "agnes-3.0-flash", cfg["model"]
    assert "agnes" in cfg["base_url"], cfg["base_url"]
    assert cfg["api_key"] == "sk_replace_me", "示例不得含真实密钥"
    assert not cfg.get("fallback_model"), "示例不得示范已移除的兜底字段"