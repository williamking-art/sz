# -*- coding: utf-8 -*-
"""2026-09 全面审查 P0 修复回归锁定测试。

覆盖：
  1) 拟旨/润色/解析三链路：get_state_summary() dict 入参不再崩（_summary_text 归一 +
     desensitize_state 区间化），且 prompt 不含精确国库真值；
  2) relief_grant：非法地域拒绝（不落京畿、不动国库），俗名归一（畿内→京畿路/河东→河东路）；
  3) 兵额/路名统一：ARMY_UNIT_INIT 站名全部命中 20 路 → 兵 POP 回填缺口 = 0、军粮全口径一致。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402


def _new_state():
    return GameState("史实")


def test_decree_chain_dict_summary_no_crash_no_leak(monkeypatch):
    """拟旨链 dict 摘要：不崩 + 不把精确国库写进 prompt。"""
    import json as _json
    from ai.client import AIClient, _summary_text

    s = _new_state()
    summary = s.get_state_summary()
    # dict → 区间化文本
    txt = _summary_text(summary)
    assert isinstance(txt, str) and txt
    assert f"{s.treasury:,}" not in txt, "脱敏文本不得含精确国库"

    captured = {}

    class _NoNet(AIClient):
        def _call(self, system_prompt, user_prompt="", **k):
            captured["all"] = system_prompt + "\n" + (user_prompt or "")
            return None

    c = _NoNet(api_key="x", base_url="http://127.0.0.1:9")
    r1 = c.draft_decree("臣请整军", "整饬边防", summary, state=s)
    r2 = c.polish_decree("罢花石纲", summary)
    r3 = c.parse_decree("减税", summary)
    r4 = c.council_review({"title": "t", "body": "b", "effects": []}, summary, state=s)
    assert isinstance(r1, dict) and isinstance(r2, dict)
    assert isinstance(r3, dict) and isinstance(r4, dict)
    if captured.get("all"):
        assert f"{s.treasury:,}" not in captured["all"], "prompt 出现精确国库"
        assert f"{s.imperial_treasury:,}" not in captured["all"], "prompt 出现精确内帑"


def test_relief_region_resolve_and_refuse():
    """relief_grant：俗名归一、非法地域拒绝（国库不动）。"""
    from ai.client_utils import _resolve_region, _tool_dispatch

    s = _new_state()
    assert _resolve_region(s, "畿内") == "京畿路"
    assert _resolve_region(s, "河东") == "河东路"
    assert _resolve_region(s, "两浙路") == "两浙路"
    assert _resolve_region(s, "火星") is None
    t0 = s.treasury
    out = _tool_dispatch(s, [{"id": "1", "function": {
        "name": "relief_grant",
        "arguments": '{"region": "火星", "grain": 3}'}}], minister_name="测试")
    assert out and "未录" in out[0][1]
    assert s.treasury == t0, "非法地域不应动国库"
    # 合法俗名：畿内 → 京畿路，守恒落地（国库 -7万... 按档 cost）
    out2 = _tool_dispatch(s, [{"id": "2", "function": {
        "name": "relief_grant",
        "arguments": '{"region": "畿内", "grain": 1}'}}], minister_name="测试")
    assert "已发 京畿路" in out2[0][1]
    assert s.treasury == t0 - 200000


def test_army_route_names_unified():
    """路名统一：ARMY_UNIT_INIT 站名全命中 20 路，兵 POP 回填缺口 = 0、军粮全口径一致。"""
    from content.data import branch_std
    s = _new_state()
    bad = [u for u in s.army_units if u.station not in s.prefectures]
    assert bad == [], f"仍有旧名驻军：{[u.station for u in bad]}"
    # 兵 POP 缺口（聚合后应为 0）
    gap = sum(u.troops for u in s.army_units) - \
        sum(p["pops"]["兵"]["size"] for p in s.prefectures.values())
    assert gap == 0, f"兵 POP 缺口 {gap}"
    # 军粮全口径一致
    g_now, _ = s.calc_army_grain()
    expect = sum(n * branch_std(u.tier, b)["grain"]
                 for u in s.army_units for b, n in u.branches.items())
    assert abs(g_now - expect) < 1, f"军粮偏离 {g_now} vs {expect}"


def test_external_regime_pop_and_provinces():
    """审查 2026-09：外邦完整六阶 POP + 省份运行态。

    1) 每政权 pop 六阶 Σsize == population×10000（总人口守恒）；
    2) 每政权 provinces 至少 1 省，Σ省人口 == 国人口×10000、Σ省兵力 == 兵 POP；
    3) _simulate_external 演化后 pop/省重算不崩且仍守恒（含交战国损耗）。
    """
    import random as _r
    from core.settlement_steps import _simulate_external

    s = _new_state()
    for key, ex in s.external_regimes.items():
        pop = ex.get("pop")
        assert isinstance(pop, dict) and pop, f"{key} 缺 pop"
        assert abs(sum(v["size"] for v in pop.values()) - ex["population"] * 10000) <= 5, \
            f"{key} 六阶 Σsize ≠ 人口×万"
        provs = ex.get("provinces")
        assert isinstance(provs, list) and provs, f"{key} 缺省份"
        assert abs(sum(p["population"] for p in provs) - ex["population"] * 10000) <= 5, \
            f"{key} Σ省人口 ≠ 国人口"
        assert abs(sum(p["troops"] for p in provs) - pop["兵"]["size"]) <= 5, \
            f"{key} Σ省兵力 ≠ 兵 POP"
    # 演化 + 战争损耗：不崩且仍守恒
    _r.seed(7)
    s._at_war = {"辽": 1}
    s.external_regimes["辽"]["attitude"] = 20
    _simulate_external(s, [])
    ex = s.external_regimes["辽"]
    pop = ex["pop"]
    assert abs(sum(p["population"] for p in ex["provinces"]) - ex["population"] * 10000) <= 5
    assert abs(sum(p["troops"] for p in ex["provinces"]) - pop["兵"]["size"]) <= 5


def test_external_regime_army_entities():
    """审查 2026-09：外邦军队实体化。

    1) 每政权 armies Σtroops == Σ省 troops == 兵 POP（三元严格一致）；
    2) 每支军队含 番号/军籍/兵种 branches/士气/训练，Σbranches==troops；
    3) _simulate_external 演化/战争损耗后仍三元一致。
    """
    import random as _r
    from core.settlement_steps import _simulate_external

    s = _new_state()
    for key, ex in s.external_regimes.items():
        armies = ex.get("armies")
        assert isinstance(armies, list) and armies, f"{key} 缺 armies"
        for a in armies:
            assert a.get("name") and a.get("tier"), f"{key} 军队缺番号/军籍"
            assert a.get("branches") and sum(a["branches"].values()) == a.get("troops", -1), \
                f"{key} 军队 Σbranches≠troops"
        army_sum = sum(a["troops"] for a in armies)
        prov_sum = sum(p["troops"] for p in ex["provinces"])
        bing = ex["pop"]["兵"]["size"]
        assert army_sum == prov_sum == bing, f"{key} 军队/省/兵POP 三元不一致"
    # 演化 + 战争损耗后仍一致
    _r.seed(11)
    s._at_war = {"辽": 1}
    s.external_regimes["辽"]["attitude"] = 20
    for _ in range(3):
        _simulate_external(s, [])
    for key, ex in s.external_regimes.items():
        army_sum = sum(a["troops"] for a in ex["armies"])
        prov_sum = sum(p["troops"] for p in ex["provinces"])
        bing = ex["pop"]["兵"]["size"]
        assert army_sum == prov_sum == bing, f"{key} 演化后三元不一致"
        for a in ex["armies"]:
            assert sum(a["branches"].values()) == a["troops"], f"{key} {a['name']} Σbranches≠troops"


def test_external_provinces_for_web_map():
    """审查 2026-09：外邦省信息供 MapLibre Web 舆图。

    external_provinces_from_state 组装出带经纬/人口/军队/建筑的省列表，
    且仅在 REGIME_GEO 有几何的政权出产经纬（可被 Web 舆图显示）。
    """
    from ui.map_web import external_provinces_from_state

    s = _new_state()
    provs = external_provinces_from_state(s)
    assert provs, "应有外邦省供 Web 舆图显示"
    for p in provs:
        assert "lon" in p and "lat" in p and "buildings" in p and "army" in p
        assert isinstance(p["regime"], str) and p["name"]
    # 空政权集 → 空
    assert external_provinces_from_state(s, regimes={}) == []
    # 有几何的政权应出现（如 辽）
    _with_geo = {p["regime"] for p in provs}
    assert "辽" in _with_geo


def test_external_province_info():
    """审查 2026-09：外邦省信息（人口/军队/建筑/经纬）落运行态。

    1) 每省带 center/buildings/armies；
    2) 省 armies 与政权 armies 为同一对象（演化同步）；
    3) 有 REGIME_GEO 几何的政权其省带 center_lonlat（供 Web 舆图），仅对无几何政权为 None。
    """
    s = _new_state()
    _prov_total = 0
    _with_lonlat = 0
    for key, ex in s.external_regimes.items():
        for p in ex["provinces"]:
            _prov_total += 1
            assert len(p.get("center", []) or []) == 2, f"{key} {p['name']} 缺 center"
            assert isinstance(p.get("buildings"), dict), f"{key} {p['name']} 缺 buildings"
            assert isinstance(p.get("armies"), list), f"{key} {p['name']} 缺省军队"
            _ll = p.get("center_lonlat")
            assert _ll is None or (len(_ll) == 2 and all(isinstance(v, (int, float)) for v in _ll))
            if _ll is not None:
                _with_lonlat += 1
            if p.get("troops", 0) > 0:
                # 省军队与政权 armies 共享同一对象
                _arm = next((a for a in ex["armies"] if a["station"] == p["name"]), None)
                assert _arm is not None and any(a is _arm for a in p["armies"]), \
                    f"{key} {p['name']} 省军队未与政权 armies 共享引用"
    assert _prov_total >= 41
    assert _with_lonlat >= 28, f"应有 ≥28 个可上 Web 舆图的外邦省（有几何政权），实际 {_with_lonlat}"
