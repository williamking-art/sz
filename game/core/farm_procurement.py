# -*- coding: utf-8 -*-
"""\u548c\u4e70\uff1a\u5b98\u5e9c\u5411\u519c\u6237\u91c7\u8d2d\u519c\u5bb6\u4ea7\u7269\uff08\u7528\u6237 2026-10-05 \u88c1\u5b9a\uff09\u3002

## \u4e3a\u4ec0\u4e48\u6709\u8fd9\u4e2a\u6a21\u5757

Y \u8f68\u88c1\u5b9a\uff1a**\u4ea7\u51fa\u5148\u5f52\u519c\u6237\u751f\u4ea7\u4e3b\u4f53**\uff08\u4e0d\u4f2a\u9020\u6237\u7ea7\u7530\u5951\uff09\uff0c
\u5b98\u5e9c/\u5de5\u574a\u8981\u7528\u65f6**\u518d\u6309\u73a9\u6cd5\u5b9a\u4ef7\u91c7\u8d2d**\u3002

\u274c **\u4e0d\u53ef**\u76f4\u63a5\u628a\u519c\u6237\u4ea7\u7269\u6539\u6210\u56fd\u5e93\u6240\u6709\u2014\u2014\u90a3\u4e0d\u7b97\u8d27\u6743\u95ed\u73af\uff08\u7528\u6237\u660e\u786e\u5426\u5b9a\uff09\u3002
\u5de5\u574a\u8bfb\u4e0d\u5230\u519c\u6237\u5e93\u5b58\u662f**\u63a5\u7ebf\u95ee\u9898**\uff0c\u4e0d\u662f\u628a\u519c\u6237\u8d27\u7269\u6539\u6210\u56fd\u5e93\u6240\u6709\u7684\u4f9d\u636e\u3002

## \u53e3\u5f84

- **\u4e70\u65b9**\uff1a\u56fd\u5e93 `state.treasury`\uff1b**\u5356\u65b9**\uff1a\u672c\u8def `\u519c` POP\uff1b
- **\u4ef7\u683c**\uff1a`MATERIAL_PRICE_BASE[dim] \u00d7 FARM_PRICE_RATIO`\uff08**\u73a9\u6cd5\u8bbe\u5b9a**\uff0c\u975e\u53f2\u6599\uff09\uff1b
- **\u94b1\u8d27\u540c\u65f6**\uff1a`transfer_money(treasury \u2192 pop:\u8def:\u519c)`\uff0c\u8d27\u4ece\u519c\u6237 `goods` \u8f6c\u5165 `state.resources`\uff1b
- **\u4e09\u91cd\u7ea6\u675f**\uff1a\u2460\u56fd\u5e93\u8d44\u91d1 \u2461\u5b98\u4ed3\u4f59\u91cf \u2462\u5f53\u6708\u9700\u6c42\uff08\u5de5\u574a\u6295\u6599\uff09\uff1b
- **\u672a\u4e70\u8d70\u7684\u4ecd\u5f52\u519c\u6237**\uff1a**\u4e0d\u4e22\u5931\u3001\u4e0d\u65e0\u507f\u5165\u5e93**\uff1b
- **\u5b9e\u4e70\u5fc5\u987b\u53ef\u5bf9\u8d26**\uff1a`\u4ed8\u94b1\u989d == \u5b9e\u4e70\u91cf \u00d7 \u5355\u4ef7`\uff0c\u4e14 `money \u2192
` \u4e0e `goods \u51cf\u91cf` \u540c\u6b65\u3002

## \u73a9\u6cd5\u53c2\u6570\uff08\u53ef\u8c03\uff0c\u975e\u53f2\u6599\uff09
"""
from __future__ import annotations

from typing import Dict, List, Optional

__all__ = ["FARM_PROCURE_DIMS", "FARM_PRICE_RATIO", "PROCURE_TARGET_MONTHS",
           "MERCHANT_BUY_RATIO", "MERCHANT_SPEND_SHARE",
           "procure_from_farmers", "sell_surplus_to_merchants"]

#: \u53c2\u4e0e\u548c\u4e70\u7684\u519c\u5bb6\u4ea7\u7269\uff08\u5bf9\u5e94 HOLDER_MAP \u4e2d household_self \u7684\u90a3\u4e9b\uff09
FARM_PROCURE_DIMS = ("\u4e1d", "\u9ebb", "\u8517", "\u679c")

#: \ud83d\udd34 **\u73a9\u6cd5\u8bbe\u5b9a**\uff08\u975e\u53f2\u6599\uff09\uff1a\u548c\u4e70\u4ef7 = \u57fa\u51c6\u4ef7 \u00d7 \u6b64\u7cfb\u6570\u3002
#: \u53d6 0.9\uff08\u7565\u4f4e\u4e8e\u5e02\u4ef7\uff09\u2014\u2014 \u5b8b\u4ee3\u548c\u4e70\u5e38\u538b\u4ef7\uff0c\u4f46\u672c\u503c\u4e3a**\u53ef\u8c03\u7684\u6e38\u620f\u53c2\u6570**\uff0c\u975e\u53f2\u6599\u8003\u8bc1\u3002
FARM_PRICE_RATIO = 0.9

#: \ud83d\udd34 **\u73a9\u6cd5\u8bbe\u5b9a**\uff1a\u76ee\u6807\u5e93\u5b58 = \u5de5\u574a\u6708\u9700\u6c42 \u00d7 \u6b64\u6708\u6570\u3002
PROCURE_TARGET_MONTHS = 1.0

#: 🔴 **玩法设定**：和买单月最多动用国库的比例。
#: ⚠⚠ 首轮实测：无此上限时和买一轮花掉 **39.6M / 50M**（国库），
#: 直接导致政府付不出经费（`upkeep_arrears` 124398）。
#: 故加保留：**和买不得把国库压到 50% 以下**。
PROCURE_MAX_TREASURY_SHARE = 0.5


def _take_goods(goods: dict, dim: str, qty: int) -> int:
    """\u4ece `goods`\uff08\u6241\u5e73 + \u5dde\u5e9c\u6876\u53cc\u5f62\u6001\uff09\u53d6\u51fa `qty`\uff0c\u8fd4\u56de**\u5b9e\u9645\u53d6\u51fa\u91cf**\u3002"""
    from core.foundation.ledger.material_holding import goods_amount, goods_set
    have = int(goods_amount(goods, dim) or 0)
    take = min(int(qty), have)
    if take <= 0:
        return 0
    left = take
    for k in [x for x in goods if isinstance(goods.get(x), dict)]:
        b = goods.get(k) or {}
        cur = int(b.get(dim, 0) or 0)
        if cur <= 0:
            continue
        d = min(cur, left)
        goods_set(goods, dim, cur - d, k)
        left -= d
        if left <= 0:
            break
    if left > 0:
        flat = int(goods.get(dim, 0) or 0)
        goods_set(goods, dim, max(0, flat - left))
    return take


def _workshop_demand(state) -> Dict[str, int]:
    """\u5f53\u6708\u5de5\u574a\u5bf9\u5404\u539f\u6599\u7ef4\u7684\u9700\u6c42\u5408\u8ba1\uff08\u4ec5\u7528\u4f5c**\u91c7\u8d2d\u76ee\u6807**\uff0c\u4e0d\u53c2\u4e0e\u7ed3\u7b97\uff09\u3002"""
    out: Dict[str, int] = {}
    for ws in (getattr(state, "workshops", None) or {}).values():
        if not isinstance(ws, dict) or not ws.get("active"):
            continue
        for dim, need in (ws.get("recipe") or {}).items():
            if dim in ("grain_feed", "ration_weight"):
                continue
            n = int(need or 0)
            if n > 0:
                out[dim] = out.get(dim, 0) + n
    return out


def procure_from_farmers(state, log: Optional[List[str]] = None):
    """\u5b98\u5e9c\u5411\u5404\u8def\u519c\u6237**\u548c\u4e70**\u519c\u5bb6\u4ea7\u7269\u3002

    \u94b1\u8d27\u540c\u65f6\u8f6c\u79fb\uff1b\u53d7\u56fd\u5e93\u8d44\u91d1 / \u5b98\u4ed3\u4f59\u91cf / \u5f53\u6708\u9700\u6c42\u4e09\u91cd\u7ea6\u675f\uff1b
    **\u672a\u4e70\u8d70\u7684\u4ecd\u5f52\u519c\u6237**\u3002\u8fd4\u56de `{dim: {qty, paid}}`\u3002
    """
    from content.data import MATERIAL_PRICE_BASE
    logs = log if isinstance(log, list) else []
    demand = _workshop_demand(state)
    prefs = getattr(state, "prefectures", None) or {}
    res = getattr(state, "resources", None)
    out: Dict[str, Dict[str, int]] = {}
    if not isinstance(res, dict):
        return out
    _tre0 = int(getattr(state, "treasury", 0) or 0)
    _budget = int(_tre0 * PROCURE_MAX_TREASURY_SHARE)   # 单月和买总预算
    _spent = 0
    for dim in FARM_PROCURE_DIMS:
        base = float(MATERIAL_PRICE_BASE.get(dim, 0) or 0)
        if base <= 0:
            continue                      # \u65e0\u57fa\u51c6\u4ef7 \u21d2 **\u4e0d\u5b9a\u4ef7**\uff08\u7f3a\u5931\u22600\uff09
        unit = base * FARM_PRICE_RATIO
        slot = res.setdefault(dim, {"stock": 0, "cap": 50_000})
        cap = int(slot.get("cap", 50_000) or 50_000)
        target = int(demand.get(dim, 0) * PROCURE_TARGET_MONTHS)
        qty = 0; paid = 0
        for route, pf in prefs.items():
            if not isinstance(pf, dict):
                continue
            room = max(0, cap - int(slot.get("stock", 0) or 0))
            gap = max(0, target - int(slot.get("stock", 0) or 0))
            if room <= 0 or gap <= 0:
                break
            nong = (pf.get("pops") or {}).get("\u519c")
            if not isinstance(nong, dict):
                continue
            goods = nong.get("goods")
            if not isinstance(goods, dict):
                continue
            from core.foundation.ledger.material_holding import goods_amount
            have = int(goods_amount(goods, dim) or 0)
            if have <= 0:
                continue
            _left_budget = max(0, _budget - _spent)
            _cash = min(int(getattr(state, "treasury", 0) or 0), _left_budget)
            afford = int(_cash / unit) if unit > 0 else 0
            want = min(have, gap, room, afford)
            if want <= 0:
                continue
            pay = int(round(want * unit))
            got = state.transfer_money("treasury", "pop:%s:\u519c" % route, pay)
            if got <= 0:
                continue                  # \u94b1\u4e0d\u5230\u4f4d \u21d2 **\u4e0d\u53d6\u8d27**\uff08\u4e0d\u65e0\u507f\u5165\u5e93\uff09
            take = _take_goods(goods, dim, want)
            if take <= 0:
                state.transfer_money("pop:%s:\u519c" % route, "treasury", got)   # \u56de\u9000
                continue
            slot["stock"] = int(slot.get("stock", 0) or 0) + take
            qty += take; paid += got; _spent += got
        if qty > 0:
            out[dim] = {"qty": qty, "paid": paid}
            logs.append("[\u548c\u4e70] %s +%d\uff08\u4ed8 %d \u8d2f\uff09" % (dim, qty, paid))
    return out


#: \ud83d\udd34 **\u73a9\u6cd5\u8bbe\u5b9a**\uff1a\u519c\u6237\u5411\u5546\u4eba\u552e\u6599\u7684**\u6536\u8d2d\u4ef7** = \u57fa\u51c6\u4ef7 \u00d7 \u6b64\u7cfb\u6570\u3002
#: \u4f4e\u4e8e\u5b98\u5e9c\u548c\u4e70\u4ef7\uff080.9\uff09\u2014\u2014 \u7b26\u5408\u300c\u6c11\u95f4\u6536\u8d2d\u4ef7\u4f4e\u4e8e\u5b98\u5e9c\u300d\u7684\u5e38\u8bc6\uff0c\u4f46**\u4ecd\u4e3a\u73a9\u6cd5\u53c2\u6570**\u3002
MERCHANT_BUY_RATIO = 0.7

#: \ud83d\udd34 **\u73a9\u6cd5\u8bbe\u5b9a**\uff1a\u5546\u4eba\u5355\u6708\u6700\u591a\u52a8\u7528\u5176 wealth \u7684\u6bd4\u4f8b\u7528\u4e8e\u6536\u8d2d\u3002
#: \u26a0\u26a0 \u672c\u4fa7\u9650\u5236\u4f7f\u6210\u4ea4**\u5929\u7136\u81ea\u9650**\uff08\u5546\u4eba\u94b1\u6709\u9650\uff09\uff0c
#: \u907f\u514d\u53ea\u662f\u628a\u519c\u6237\u7684\u6ce1\u6cab\u539f\u6837\u8f6c\u7ed9\u5546\u4eba\u3002
MERCHANT_SPEND_SHARE = 0.3


# 本函数尚未接线，且已知有守恒 bug（2026-10-05 实测）。
# 实测：接线后「农户 + 商人」的丝麻合计比基线多 408 万（第 3 月）
#       ⇒ 货物被凭空创造，守恒破裂。
# 怀疑点：_take_goods 在本场景下未真正移除（桶键/_seat_of 口径），
#         而商人侧又已入账 ⇒ 双重计数。
# 接线前必须先修守恒并建定向回归。（用户 2026-10-05 裁定「丙」，实现待修）
#
# 玩法参数（已定）：收购价 = 基准价 × 0.7；商人单月最多动用 wealth 的 30%。
def sell_surplus_to_merchants(state, log: Optional[List[str]] = None):
    """\u519c\u6237\u5411\u672c\u8def**\u5546\u4eba**\u552e\u51fa\u4f59\u6599\uff08\u73a9\u6cd5\u8bbe\u5b9a\uff0c\u66f4\u8d34\u53f2\u5b9e\uff1a\u519c\u5bb6\u4ea7\u7269\u5165\u5e02\uff09\u3002

    \u94b1\u8d27\u540c\u65f6\uff1a`\u5546\u4eba wealth \u2192 \u519c POP wealth`\uff0c`\u519c goods \u2192 \u5546\u4eba goods`\uff0c\u540c\u8def\u3002
    **\u6210\u4ea4\u53d7\u5546\u4eba\u8d44\u91d1\u7ea6\u675f** \u21d2 \u81ea\u9650\uff08\u4e0d\u4f1a\u65e0\u9650\u627f\u63a5\u519c\u6237\u4f59\u6599\uff09\u3002
    """
    from content.data import MATERIAL_PRICE_BASE
    from core.foundation.ledger.material_holding import goods_amount, goods_bucket
    logs = log if isinstance(log, list) else []
    prefs = getattr(state, "prefectures", None) or {}
    out: Dict[str, Dict[str, int]] = {}
    for route, pf in prefs.items():
        if not isinstance(pf, dict):
            continue
        pops = pf.get("pops") or {}
        nong = pops.get("\u519c"); shang = pops.get("\u5546\u4eba")
        if not isinstance(nong, dict) or not isinstance(shang, dict):
            continue
        ng = nong.get("goods"); sg = shang.get("goods")
        if not isinstance(ng, dict) or not isinstance(sg, dict):
            continue
        wealth = int(shang.get("wealth", 0) or 0)
        if wealth <= 0:
            continue
        budget = int(wealth * MERCHANT_SPEND_SHARE)
        # 🔴 预算需在各维间**均分**：若用单一递减预算，
        # 排在 `FARM_PROCURE_DIMS` 前面的维（丝）会把预算吃光，
        # 后面的（麻/蔗/果）**被饿死**（实测麻仅 138）。
        _dims_here = [d for d in FARM_PROCURE_DIMS
                      if goods_amount(ng, d) and float(MATERIAL_PRICE_BASE.get(d, 0) or 0) > 0]
        _per_dim = int(budget / len(_dims_here)) if _dims_here else 0
        for dim in FARM_PROCURE_DIMS:
            base = float(MATERIAL_PRICE_BASE.get(dim, 0) or 0)
            if base <= 0 or _per_dim <= 0:
                continue
            unit = base * MERCHANT_BUY_RATIO
            if unit <= 0:
                continue
            have = int(goods_amount(ng, dim) or 0)
            if have <= 0:
                continue
            want = min(have, int(_per_dim / unit))
            if want <= 0:
                continue
            pay = int(round(want * unit))
            # \u94b1\u8d77\uff1a\u5546\u4eba -> \u519c\uff08\u540c\u8def\uff09
            got = state.transfer_money("pop:%s:\u5546\u4eba" % route,
                                       "pop:%s:\u519c" % route, pay)
            if got <= 0:
                continue
            # 按**实付金额**折算取货量，保证「付钱 == 取货×价」严格成立
            want2 = int(got / unit) if unit > 0 else 0
            take = _take_goods(ng, dim, min(want, want2))

            if take <= 0:
                state.transfer_money("pop:%s:\u519c" % route,
                                     "pop:%s:\u5546\u4eba" % route, got)  # \u56de\u9000
                continue
            # \u8d27\u843d\uff1a\u8fdb\u5546\u4eba goods\uff08\u6309\u672c\u8def\u6700\u5927\u6cbb\u6240\u6876\uff0c\u540c\u519c\u6237\u53e3\u5f84\uff09
            _sid = _seat_of(pf)
            b = goods_bucket(sg, "%s|%s" % (route, _sid), create=True) if _sid else None
            if isinstance(b, dict):
                b[dim] = int(b.get(dim, 0) or 0) + take
            else:
                # 无治所名（新建局未下沉）⇒ 落**扁平**存储，不造假桶
                sg[dim] = int(sg.get(dim, 0) or 0) + take

            d = out.setdefault(dim, {"qty": 0, "paid": 0})
            d["qty"] += take; d["paid"] += got
    for dim, v in out.items():
        logs.append("[\u6c11\u95f4\u552e\u6599] %s %d\uff08\u6536 %d \u8d2f\uff09" % (dim, v["qty"], v["paid"]))
    return out


def _seat_of(pf: dict) -> str:
    """\u53d6\u8be5\u8def\u4e00\u4e2a\u6cbb\u6240\u540d\uff08\u4f9b\u5546\u4eba goods \u6876\u7528\uff09\uff1b\u65e0\u5219\u56de\u7a7a\u4e32\u3002"""
    seats = (pf or {}).get("seats") or {}
    if isinstance(seats, dict) and seats:
        return str(sorted(seats)[0]).split("|")[-1]
    return ""