# -*- coding: utf-8 -*-
"""L0：门面读数供给接入统一 facts 契约（2026-10-21）。

背景（审计实测）：天道层的"上下文"曾有三套并存——`TianDaoFacade.build_state_context`、
`clerk_decision` 自建 ctx、`merchant_decision` 自建 ctx。门面这套与契约
`core.ai.tiandao_facts` 有三处实质不一致，导致裁决**在真实局面上恒定**：

| 读数 | 旧门面实现 | 后果 | 契约口径（本文件守的） |
|---|---|---|---|
| `disaster` | 读 `statistics["disaster_level"]` | **全库无人写入 ⇒ 恒 None** | `state.disaster_severity / 5`（0~5 → 0~1） |
| `integrity` | 无贪腐读数回落 **1.0** | 假装"吏治完美"，违反"缺失≠1.0"硬约束 | 无读数 ⇒ **None** |
| `stock` | `state.granary`（太仓） | 常平仓闸门读的是太仓库存 | Σ 路级 `changping_stock` |

本文件覆盖：
1. `disaster` 由真值给出（severity=0 ⇒ `0.0`，**不是** `None`；`0` 是合法值）；
2. `disaster` 归一化：severity=3 ⇒ `0.6`；
3. `integrity` 无贪腐读数 ⇒ `None`（**不得** 1.0）；
4. 契约校验：context 的 canonical 部分 `validate_facts` 无问题、无未登记键；
5. `stock` = 常平仓合计，≠ 太仓；
6. `block_rate` 可用（实测 10.0）；
7. **判据验收**：三个曾经"恒定单值"的门面裁决在真实 state 变体下不再恒定。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from application.game_init import new_game  # noqa: E402
from core.ai.tiandao_facade import TianDaoFacade  # noqa: E402
from core.ai.tiandao_facts import (  # noqa: E402
    FACT_KEYS, build_facts, validate_facts,
)


def _state():
    return new_game("史实")


def _changping_total(state) -> float:
    """Σ 路级常平仓（与契约同口径：跳过缺失，不把缺失当 0）。"""
    return sum(p.get("changping_stock") or 0 for p in state.prefectures.values()
               if isinstance(p, dict))


# =============================================================================
# 1~2. disaster：真值、归一化（旧实现读一个没人写的字段 ⇒ 恒 None）
# =============================================================================
def test_disaster_is_zero_not_missing_for_calm_new_game():
    s = _state()
    ctx = TianDaoFacade.build_state_context(s)
    assert s.disaster_severity == 0, "新档灾情等级应为 0（史实局初）"
    assert ctx["disaster"] == 0.0, "severity=0 ⇒ disaster 0.0（0 是合法值，不得当缺失）"
    assert ctx["disaster"] is not None, "旧实现读 statistics['disaster_level'] ⇒ 恒 None"


def test_disaster_is_normalized_from_severity():
    s = _state()
    s.disaster_severity = 3
    assert TianDaoFacade.build_state_context(s)["disaster"] == pytest.approx(0.6, abs=1e-9)
    s.disaster_severity = 5
    assert TianDaoFacade.build_state_context(s)["disaster"] == pytest.approx(1.0, abs=1e-9)


# =============================================================================
# 3. integrity：无贪腐读数 ⇒ None（旧实现回落 1.0 = 假装吏治完美）
# =============================================================================
def test_integrity_is_none_without_corruption_reading():
    s = _state()
    s.corruption = {}
    ctx = TianDaoFacade.build_state_context(s)
    assert ctx["integrity"] is None, "无贪腐读数必须是 None（不得回落 1.0）"
    assert ctx["integrity"] != 1.0


def test_integrity_present_when_corruption_exists():
    """反向守卫：有读数时给出 0~1 的真值（避免"永远 None"这种另一种假读数）。"""
    s = _state()
    assert s.corruption, "新档应带贪腐读数（43 名官员）"
    integrity = TianDaoFacade.build_state_context(s)["integrity"]
    assert integrity is not None
    assert 0.0 <= integrity <= 1.0


# =============================================================================
# 4. 契约校验：canonical 部分无问题、除两个过渡别名外无多余键
# =============================================================================
def test_context_canonical_part_passes_contract_validation():
    """`validate_facts` 对 context 的 canonical 投影必须为空问题清单。

    说明：`to_engine_context` 会补 `stock` / `supervision` 两个**过渡别名**（不在
    `FACT_KEYS` 里，`validate_facts` 会判"未登记"）。因此这里校验 canonical 投影，
    并**另行**断言除这两个别名外没有任何多余键——等价于"只返回 canonical 键 + 别名"。
    """
    s = _state()
    ctx = TianDaoFacade.build_state_context(s)
    canonical = {k: v for k, v in ctx.items() if k in FACT_KEYS}
    assert validate_facts(canonical) == []
    assert set(ctx) - set(FACT_KEYS) == {"stock", "supervision"}
    # 契约生产者本身也必须合规（不只是门面视图）
    assert validate_facts(build_facts(s)) == []


# =============================================================================
# 5. stock：常平仓合计，不是太仓
# =============================================================================
def test_stock_is_changping_aggregate_not_imperial_granary():
    s = _state()
    expected = _changping_total(s)
    ctx = TianDaoFacade.build_state_context(s)
    assert expected > 0, "新档各路应带常平仓库存"
    assert ctx["stock"] == pytest.approx(expected), "stock 必须是常平仓合计"
    assert ctx["stock"] != s.granary, "stock 不得是太仓 granary（旧实现的错口径）"
    assert ctx["changping_stock"] == pytest.approx(expected)
    assert ctx["granary"] == s.granary, "太仓仍在 context 里（只改 stock 指向）"


# =============================================================================
# 6. block_rate：漕运淤塞（旧 context 根本没有这个键 ⇒ 改道恒"等疏浚"）
# =============================================================================
def test_block_rate_is_available_from_route_canal_block():
    s = _state()
    blocks = [p["canal_block"] for p in s.prefectures.values()
              if isinstance(p, dict) and p.get("canal_block") is not None]
    assert blocks, "新档各路应带 canal_block 读数"
    ctx = TianDaoFacade.build_state_context(s)
    assert ctx["block_rate"] is not None
    assert ctx["block_rate"] == pytest.approx(sum(blocks) / len(blocks))
    assert ctx["block_rate"] == pytest.approx(10.0), "实测新档均值为 10.0（0~100 量纲）"


# =============================================================================
# 7. 判据验收：三个门面裁决不再恒定单值
# =============================================================================
def _variant(disaster_severity=0, canal_block=10.0, unrest=10.0, refugees=800):
    """构造一组"同结构、不同局面"的 state（只改 audit 点名的四个读数）。"""
    s = _state()
    for p in s.prefectures.values():
        if not isinstance(p, dict):
            continue
        p["canal_block"] = canal_block
        p["unrest"] = unrest
        p["refugees"] = refugees
    s.disaster_severity = disaster_severity
    return s


_NOT_CONSTANT_METHODS = (
    "merchant_trade_or_hoard",     # 旧：无 gap 生产者 + disaster 恒 None ⇒ 恒 ship
    "canal_reroute_choice",        # 旧：context 无 block_rate ⇒ 恒 wait_dredge
    "farmer_destitution_path",     # 旧：debt 恒 None + disaster 恒 None ⇒ 恒 mortgage_land
)


def test_three_methods_are_not_constant_across_real_states():
    """判据验收：现实局面变化必须带来不同裁决。

    通过 `observe_monthly` 走**生产接线**（facts → ctx → 门面），而不是手工构造 ctx，
    这样才验证"读数供给真的接上了"，而不是引擎分支存在与否。
    """
    variants = [
        _variant(disaster_severity=0, canal_block=10.0, unrest=10.0, refugees=800),    # 平年
        _variant(disaster_severity=5, canal_block=100.0, unrest=80.0, refugees=8000),  # 灾重淤塞
        _variant(disaster_severity=2, canal_block=55.0, unrest=45.0, refugees=3000),   # 中间态
    ]
    seen = {m: set() for m in _NOT_CONSTANT_METHODS}
    for s in variants:
        rec = TianDaoFacade.observe_monthly(s)
        decisions = rec["decisions"]
        for m in _NOT_CONSTANT_METHODS:
            assert m in decisions, f"{m} 未进观察记录"
            assert not (isinstance(decisions[m], dict) and decisions[m].get("error")), \
                f"{m} 观测报错：{decisions[m]}"
            seen[m].add(decisions[m])
    for m in _NOT_CONSTANT_METHODS:
        assert len(seen[m]) >= 2, f"{m} 仍恒定单值：{sorted(seen[m])}（判据验收未通过）"
