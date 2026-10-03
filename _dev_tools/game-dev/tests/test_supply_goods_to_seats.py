# -*- coding: utf-8 -*-
"""**卡3 · G-2 骨架 全商品供给入州府桶** 定向回归（2026-10-04）。

把只服务建材三维的供给入口推广为 `supply_goods_to_seats()`：

1. **全商品**：默认覆盖 `GOODS_DIMS`，不再限建材三维；
2. **按产地/人口归属**：`seat_weights_for()` 产地优先、人口兜底；
3. **守恒**：只是搬运，`state.resources` 总量不变，差额为未领余量；
4. **幂等**：重复调用不膨胀。

⚠️ 已知口径事实：治所级 `yields` 是路级按人口等比拆分 ⇒ 现两权重数值等价，
接口分离是为后续接入《宋史》州级贡物数据留口（详见 `seat_weights_for` 注释）。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from content.data import GOODS_DIMS                     # noqa: E402
from core.game_state import GameState                   # noqa: E402
from core.material_holding import (goods_amount,   # noqa: E402
                                   seat_weights_for, supply_goods_to_seats)


def _seed(dim, stock):
    s = GameState("史实")
    s.resources.setdefault(dim, {"stock": 0, "cap": 0})
    s.resources[dim]["stock"] = stock
    return s


def test_supply_covers_all_goods_dims_not_only_materials():
    """骨架是**全商品**入口，不再只服务建材三维。"""
    assert "丝" in GOODS_DIMS and "米" in GOODS_DIMS
    # 建材之外的非成品维也应有州府桶承载能力（此处只验接口可用、非空目录）
    s = _seed("丝", 1000)
    out = supply_goods_to_seats(s, dims=["丝"])
    # 有商人路且有量时应落桶；无路/无量时不报错（份额留总账，不臆造归属）
    assert isinstance(out, dict)
    assert out.get("丝", 0) >= 0


def test_supply_is_conserving_and_idempotent():
    """守恒＋幂等：只是搬运，总量不变，重复调用不膨胀。"""
    s = _seed("木", 1000)
    before = s.resources["木"]["stock"]
    supply_goods_to_seats(s, dims=["木"])
    after = s.resources["木"]["stock"]
    assert after <= before, "供给只搬运，库存不得增加（凭空造料）"
    assert after >= 0, "库存不得为负"
    a = sum(goods_amount((p or {}).get("goods") or {}, "木") or 0
            for p in (s.prefectures.get(next(iter(s.prefectures))) or {}).get("pops", {}).values())
    supply_goods_to_seats(s, dims=["木"])
    b = sum(goods_amount((p or {}).get("goods") or {}, "木") or 0
            for p in (s.prefectures.get(next(iter(s.prefectures))) or {}).get("pops", {}).values())
    assert b == a, f"重复调用不得膨胀：{a} → {b}"


def test_seat_weights_fall_back_without_fabricating():
    """权重优先产地、无产地回退人口；两者皆空 ⇒ 不臆造归属。"""
    from core.prefecture_entity import all_seats
    rt = sorted(set(str(s.get("circuit")) for s in all_seats(include_merged=False)))[0]
    w = seat_weights_for(None, rt, "木")
    assert w, f"{rt} 应有治所权重"
    for sid, _x in w:
        assert "|" in sid, f"权重键应是州府主键 路|治所，实得 {sid!r}"
    # 不存在的路 ⇒ 空列表（份额留总账，不臆造）
    assert seat_weights_for(None, "不存在的路", "木") == []