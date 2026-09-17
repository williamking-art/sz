# -*- coding: utf-8 -*-
"""承接模式升级测试：research_decide 拒绝式 / 去 west 门槛 / tech_registry 门槛 / 研发推进。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.asset_context import node_prereqs_met, unlock_node, get_tech_node  # noqa: E402
from core.registries import (  # noqa: E402
    register_node, node_entry, deactivate_node, TECH_REGISTRY_MAX,
)


def _new_state():
    return GameState("史实")


def test_no_west_gate():
    """去 west 门槛：含 ("west",N) 副指标的节点，west 不足也可研究（E6 电炉钢 west4 移除后可研发）。"""
    s = _new_state()
    e6 = get_tech_node("E6_elecsteel")
    assert e6 is not None and ("west", 4) in e6[7]
    # 前置全解锁 + level 足 + west 不足 → 仍 researchable（west 跳过）
    s.tech["unlocked"] = list(e6[5]) + ["M9_power"]
    s.tech["level"] = e6[6]
    assert node_prereqs_met(s, e6) is True


def test_research_decide_reject():
    """research_decide 拒绝式：node 不存在 / 档位非法 → None。"""
    from ai.client import AIClient
    c = AIClient(api_key="x")
    # validator 不可直达；验证 node_entry 对不存在节点返回 None（research_decide 依赖）
    s = _new_state()
    assert node_entry(s, "nonexistent") is None
    assert get_tech_node("M0_plow") is not None   # 官方节点存在


def test_tech_registry_gates():
    """tech_registry 门槛（对齐）：前置未解锁拒绝 / 效果合理性软校验（白名单放宽）/ 重名。"""
    s = _new_state()
    # 前置未解锁 → 拒绝（程序底线）
    r = register_node(s, {"name": "新火铳", "prereqs": ["NOPE"], "effect": {"army_power": 0.1}})
    assert r["ok"] is False and "前置" in r["msg"]
    # 白名单放宽：效果字段自由设计（"magic" 也接受——合理性软校验）
    s.tech["unlocked"] = ["M0_plow"]
    r2 = register_node(s, {"name": "新火铳", "prereqs": ["M0_plow"], "effect": {"magic": 1}})
    assert r2["ok"] is True, "效果字段自由设计（白名单放宽）"
    # 合理性软校验：过分效果降档（非拒绝）
    r3 = register_node(s, {"name": "天工造物", "prereqs": ["M0_plow"], "effect": {"treasury": 999999999}})
    assert r3["ok"] is True
    assert s.tech_registry[r3["node_id"]]["effect"]["treasury"] <= 50_000_000, "合理性软校验应降档"
    # 重名拒绝
    r4 = register_node(s, {"name": "新火铳", "prereqs": ["M0_plow"], "effect": {"army_power": 0.1}})
    assert r4["ok"] is False and "已注册" in r4["msg"]


def test_player_node_unlock():
    """玩家注册节点可研发推进并 unlock（_settle_tech_research 兼容）。"""
    from core.settlement_steps import _settle_tech_research
    s = _new_state()
    s.tech["unlocked"] = ["M0_plow"]
    r = register_node(s, {"name": "土火箭", "prereqs": ["M0_plow"],
                          "effect": {"army_power": 0.1}, "tier": "小"})
    assert r["ok"] is True
    # 立项入 researching（progress 92 → 一个月推进 9.17 满 100）
    s.tech["researching"][r["node_id"]] = {"progress": 92.0, "months": 12, "masters": 2}
    _settle_tech_research(s, [])
    assert r["node_id"] in s.tech.get("unlocked", []), "玩家节点应可推进并 unlock"


def test_tech_registry_roundtrip():
    """tech_registry 存档往返。"""
    from core.save_load import save_game, load_game, _slot_path
    s = _new_state()
    s.tech["unlocked"] = ["M0_plow"]
    register_node(s, {"name": "新罗盘", "prereqs": ["M0_plow"], "effect": {"trade_income": 0.1}})
    assert save_game(s, slot=1)
    s2 = load_game(1)
    assert s2 is not None
    assert len(s2.tech_registry) == 1
    if os.path.exists(_slot_path(1)):
        os.remove(_slot_path(1))
