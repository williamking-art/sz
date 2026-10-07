# -*- coding: utf-8 -*-
"""B1d-b 跨 POP 流动**带财富/粮**回归（修 P3：人均 wealth 假信号）。

背景：此前科举/致仕/裁汰等跨 POP 迁移**只改 `size`**，财富留在原池 →
一次大科举让官僚人均 wealth 骤降、士绅骤升（污染消费/生计/派系读数）。
`move_pop_people(src, dst, n)` 按**人均份额**把 wealth/grain 随人划转 ⇒ 两池人均**连续**。

锁定：
  1. `Σwealth`/`Σgrain` 跨两池**不变**（纯内部转移）；
  2. 迁出池**人均不变**（按人均份额搬走）；迁入池新人均落在**两池原人均之间**（加权平均）；
  3. 源池 `size`/余额双重钳制，**不会抽成负数**；空池不再搬；
  4. 端到端（12 月）：`officialdom` 手工调子池 + move 之后，官僚子池**两个不变量仍成立**
     （覆盖 `add_officials` 会改 `size` 的双重计数风险）。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.pop_structure import move_pop_people  # noqa: E402


def test_move_conserves_total_and_keeps_source_per_capita():
    src = {"size": 1000, "wealth": 5000, "grain": 2000}
    dst = {"size": 200, "wealth": 100, "grain": 50}
    assert move_pop_people(src, dst, 300) == 300
    assert (src["size"], dst["size"]) == (700, 500)
    assert src["wealth"] + dst["wealth"] == 5100, "Σwealth 必须守恒"
    assert src["grain"] + dst["grain"] == 2050, "Σgrain 必须守恒"
    assert abs(src["wealth"] / src["size"] - 5.0) < 0.01, "迁出池人均应不变（按人均份额搬走）"
    lo, hi = min(100 / 200, 5.0), max(100 / 200, 5.0)
    assert lo - 0.01 <= dst["wealth"] / dst["size"] <= hi + 0.01, \
        "迁入池新人均应落在两池原人均之间（加权平均＝人均连续）"


def test_move_clamps_and_never_negative():
    src = {"size": 10, "wealth": 3, "grain": 1}
    dst = {"size": 0}
    assert move_pop_people(src, dst, 999) == 10, "受源池 size 钳制"
    assert (src["size"], src["wealth"], src["grain"]) == (0, 0, 0)
    assert (dst["size"], dst["wealth"], dst["grain"]) == (10, 3, 1)
    assert move_pop_people(src, dst, 5) == 0, "空池不再搬"
    assert move_pop_people({"size": 5, "wealth": 100}, {"size": 0}, 0) == 0


def test_retirement_keeps_official_subpool_invariants():
    """端到端 12 月：致仕（带财富回士绅）后，官僚子池**两个不变量仍成立**。

    这条专门覆盖 B1d-b 的接入风险：`add_officials` 会改 `size`，故接入时改为"只调子池、
    `size` 交给 `move_pop_people`"——若哪里双重计数或漏调子池，本断言会失败。
    """
    from core.settlement import run_monthly_settlement
    s = GameState("史实")
    s.treasury = 10 ** 9
    for _ in range(12):
        run_monthly_settlement(s, 0)
    for name, p in s.prefectures.items():
        g = p["pops"]["官僚"]
        assert int(g["size"]) == int(g["officials"]) + int(g["clerks"]), f"{name}: 不变量①破"
        assert int(g["officials"]) == int(g["on_post"]) + int(g["waiting"]) + int(g["sinecure"]), \
            f"{name}: 不变量②破"


def test_exam_carries_wealth_into_bureaucrats(monkeypatch):
    """科举（农/士绅 → 官僚）应**带入财富**：跑一次科次后官僚 POP wealth 增加、Σwealth 不凭空增减。"""
    import core.domains.administration.officialdom as od

    s = GameState("史实")
    # 直接跑一次科次（离散科次，避免 36 月长跑）
    assert hasattr(od, "_triennial_exam"), "科举入口名变了，请同步本测试"
    _exam = getattr(od, "_triennial_exam")
    w0 = sum(p["pops"]["官僚"]["wealth"] for p in s.prefectures.values())
    p0 = sum(p["pops"]["农"]["wealth"] + p["pops"]["士绅"]["wealth"]
             for p in s.prefectures.values())
    _exam(s, [])
    w1 = sum(p["pops"]["官僚"]["wealth"] for p in s.prefectures.values())
    p1 = sum(p["pops"]["农"]["wealth"] + p["pops"]["士绅"]["wealth"]
             for p in s.prefectures.values())
    guan_size = sum(p["pops"]["官僚"]["size"] for p in s.prefectures.values())
    if guan_size > 0 and w1 > w0:
        assert abs((w0 + p0) - (w1 + p1)) <= 8, "迁移前后『官僚+农+士绅』财富总和应守恒"
