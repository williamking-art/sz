# -*- coding: utf-8 -*-
"""经济金融推演接入测试（蔡权衡定稿）：FINANCE_DECIDE_BASE / 5 金融字段 / 消费调制守恒。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import FINANCE_DECIDE_BASE, FINANCE_STATES  # noqa: E402
from core.game_state import GameState  # noqa: E402


def _new_state():
    return GameState("史实")


def test_finance_base_and_states():
    """FINANCE_DECIDE_BASE 五维 CAP + 三态词白名单。"""
    assert FINANCE_DECIDE_BASE["jiaozi_trust"]["cap"] == 5
    assert FINANCE_DECIDE_BASE["jiaozi_issued"]["cap"] == 1_000_000
    assert FINANCE_DECIDE_BASE["shortage"]["cap"] == 0.05
    assert FINANCE_DECIDE_BASE["tariff"]["cap"] == 0.02
    assert FINANCE_DECIDE_BASE["silver_in"]["cap"] == 10
    assert FINANCE_DECIDE_BASE["bank_capital"]["cap"] == 0.20
    assert FINANCE_DECIDE_BASE["price_mult"]["cap"] == 0.05
    assert FINANCE_STATES["jiaozi_trust"] == ("增", "稳", "跌")
    assert FINANCE_STATES["shortage"] == ("缓", "平", "加剧")
    assert FINANCE_STATES["maritime"] == ("兴", "平", "衰")
    assert FINANCE_STATES["bank"] == ("扩", "稳", "损")
    assert FINANCE_STATES["price_trend"] == ("通胀", "平", "通缩")


def test_settle_extensions_finance_modulation():
    """金融消费调制：交子 trust/issued、钱荒、市舶、价格系数（CAP/clamp）。"""
    from core.settlement_steps import _settle_extensions
    s = _new_state()
    s._economy_ai = {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
                     "窖银": "无", "城市化": "无", "回乡": "无", "科举": "无",
                     "jiaozi_trust": "增", "shortage": "缓", "maritime": "平",
                     "bank": "稳", "price_trend": "通胀"}
    t0, sh0 = s.jiaozi["trust"], s.coin["shortage"]
    s.maritime["open"] = True
    s.jiaozi["issued"] = 1_000_000  # ≤ ceiling
    _settle_extensions(s, [])
    assert s.jiaozi["trust"] == min(100, t0 + 5 + 1)   # 增+5 与自然恢复 +1
    # 适量发钞-0.005 + 缓-0.05 + 市舶-0.01 + 家产聚敛窖藏（蔡京/童贯 聚敛≥70 → shortage 增，量级 <0.02）
    base = max(0.05, sh0 - 0.005 - 0.05 - 0.01)
    assert base <= s.coin["shortage"] <= base + 0.02
    assert abs(s._price_mult - 1.05) < 1e-9
    # 通胀持续 → clamp 上限 3.0
    for _ in range(30):
        _settle_extensions(s, [])
    assert s._price_mult <= 3.0 + 1e-9


def test_finance_conservation_no_magic():
    """守恒断言：金融组合下无凭空造灭——交子增发 ≤ 可发额度（超发触发既有崩溃路径）。"""
    from core.settlement_steps import _settle_extensions
    s = _new_state()
    s.jiaozi["issued"] = 10_000_000  # 超发
    s.jiaozi["reserve"] = 2_000_000
    s.jiaozi["trust"] = 60
    ceiling = s._jiaozi_ceiling()
    assert s.jiaozi["issued"] > ceiling
    _fin = {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
            "窖银": "无", "城市化": "无", "回乡": "无", "科举": "无",
            "jiaozi_trust": "增", "jiaozi_issued": "增", "shortage": "平",
            "maritime": "平", "bank": "稳", "price_trend": "平"}
    s._economy_ai = _fin
    issued0 = s.jiaozi["issued"]
    trust0 = s.jiaozi["trust"]
    _settle_extensions(s, [])
    # 已超发：增发被拒（≤ ceiling 才加），超发路径触发既有 trust 崩（无凭空造币）
    assert s.jiaozi["issued"] == issued0   # 超发状态不再增发（加 0）
    assert s.jiaozi["trust"] <= trust0 + 1  # 超发崩路径（+1 自然恢复被崩抵消或更低）


def test_finance_reject_bad_states(monkeypatch):
    """economy_decide 金融字段**拒绝式**：缺失/非法 → 整单返回 None（不默认填充、不伪造）。

    2026-09-18 测试体检：原用例名写着"拒绝式：缺失/非法 → None"，但**一行都没测拒绝路径**
    （唯一断言是 `"非法" not in states` 与"值都是字符串"这类常量形状检查 —— 恒真且无用）。
    现改为**真驱动** `economy_decide`：伪造 `_call` 返回非法/缺失金融字段的 JSON，
    断言其返回 None（拒绝），并用合法载荷做**正向对照**（证明拒绝不是"永远返回 None"）。
    """
    import json
    from ai.client import AIClient
    from content.data import FINANCE_STATES

    _VALID = {k: v[0] for k, v in FINANCE_STATES.items()}
    _core = {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
             "窖银": "小", "城市化": "中", "回乡": "无", "科举": "中"}

    def _client(payload: dict):
        c = AIClient.__new__(AIClient)
        c.available = True
        monkeypatch.setattr(c, "_call", lambda *a, **k: json.dumps(payload, ensure_ascii=False))
        return c

    # ① 正向对照：全部合法 → 返回 dict，且 5 个金融字段原样带回
    ok = _client({**_core, **_VALID}).economy_decide("中")
    assert isinstance(ok, dict), "合法载荷应通过（否则下面的「拒绝」断言没有意义）"
    for fk in FINANCE_STATES:
        assert ok.get(fk) == _VALID[fk], f"合法金融字段 {fk} 未被带回"

    # ② 非法词 → 拒绝（返回 None，不落默认值）
    for fk in FINANCE_STATES:
        bad = {**_core, **_VALID, fk: "非法档位词"}
        assert _client(bad).economy_decide("中") is None, f"{fk} 非法词未被拒绝"

    # ③ 缺失 → 拒绝
    for fk in FINANCE_STATES:
        miss = {**_core, **_VALID}
        miss.pop(fk)
        assert _client(miss).economy_decide("中") is None, f"{fk} 缺失未被拒绝"

    # ④ 非字符串（数字）→ 拒绝
    for fk in FINANCE_STATES:
        assert _client({**_core, **_VALID, fk: 1}).economy_decide("中") is None, \
            f"{fk} 非字符串未被拒绝"
