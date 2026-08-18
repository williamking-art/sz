# -*- coding: utf-8 -*-
"""宋祚 · 士绅囤粮/窖银（POP 经济子模块）

从 settlement_steps.py 拆分而出（P2-5 巨文件拆分第一步），逻辑与调用签名完全不变：
  _settle_civilian_hoard(state, log)

边界：自包含，仅依赖 state 与 content.data 的 HOARD_SUPPLY_SQUEEZE / TIER_RANGE。
settlement_steps.py 仍从本模块 re-export，所有既有 import 无需改动。
"""
from content.data import HOARD_SUPPLY_SQUEEZE, TIER_RANGE


def _settle_civilian_hoard(state, log):
    """士绅囤粮操作（钱粮守恒）：AI 推演档位优先，无 AI 时按粮价方向兜底。

    囤 = 士绅用 wealth 买粮（wealth↓ grain↑，受资金约束）；抛 = 卖粮得钱（grain↓ wealth↑）。
    士绅囤粮挤压市场流通（见 calc_region_grain_price 的 HOARD_SUPPLY_SQUEEZE）。
    """
    # AI 经济动态推演（settle_turn 已注入 state._economy_ai：{景气,士绅,士绅力度,生产}）或无
    _eco = getattr(state, "_economy_ai", None) or {}
    _ai_act = _eco.get("士绅", "") if _eco.get("士绅") in ("囤", "抛") else None
    _ai_tier = _eco.get("士绅力度", "中")
    for name, p in state.prefectures.items():
        genty = p["pops"]["士绅"]
        price = p.get("grain_price", state.grain_price)
        if _ai_act:
            act, tier = _ai_act, _ai_tier   # AI 推演（全国统一景气下的士绅行为）
        else:
            # 兜底：丰收贱买囤积、高价惜售/抛售获利（不再高价囤，与常平粜粮方向一致）
            if price < 0.6:
                act, tier = "囤", "小"
            elif price > 2.2:
                act, tier = "抛", "中"
            elif price > 1.6:
                act, tier = "抛", "微"       # 高价惜售（小幅抛售获利）
            else:
                # 粮价平稳：士绅卖囤粮换钱（买商品/维持现金流），卖 5%/月使囤粮存量稳定
                act, tier = "抛", "中"
        mult = TIER_RANGE.get(tier, 0.5) * 0.05   # 囤/抛比例：微0.0125/小0.025/中0.05/大0.09（不 round）
        # 士绅囤粮上限 = 士绅田产年产的 20%（史实囤积约占产粮 10-20%，避免永动机式囤积）
        _land = max(float(p.get("land", 1)), 1.0)
        _gentry_land_total = float(p.get("gentry_land", 0)) + float(p.get("hidden_land", 0))
        _hoard_cap = int(p.get("grain", 0) * _gentry_land_total / _land * 0.2)
        if act == "囤":
            buy = int(p.get("grain", 0) / 12.0 * mult)      # 月产 × 档位
            afford = genty["wealth"] // max(int(price * 1000), 1)  # 资金能买多少石（文级精度）
            room = max(0, _hoard_cap - genty["grain"])       # 囤粮余量（上限约束）
            buy = min(buy, afford, room)
            if buy > 0:
                genty["wealth"] -= int(buy * price * 1000) / 1000.0
                genty["grain"] += buy
        elif act == "抛":
            sell = int(genty["grain"] * mult)
            if sell > 0:
                genty["grain"] -= sell
                genty["wealth"] += int(sell * price * 0.3)            # 30% 进流通
                genty["窖银"] = genty.get("窖银", 0) + int(sell * price * 0.7)  # 70% 窖藏
        # 超上限强制卖粮（士绅粮仓装不下，超出部分必卖回市场，体现囤积有上限）
        if genty["grain"] > _hoard_cap:
            _excess = genty["grain"] - _hoard_cap
            genty["grain"] = _hoard_cap
            genty["wealth"] += int(_excess * price * 0.3)
            genty["窖银"] = genty.get("窖银", 0) + int(_excess * price * 0.7)
        # 窖银年化回流（挥霍/购地/市舶投资，每月 2% 窖银流出，流向服务提供者=消费，不积累 wealth）
        _draw = int(genty.get("窖银", 0) * 0.01)
        genty["窖银"] = genty.get("窖银", 0) - _draw
        p["pops"]["工匠"]["wealth"] += int(_draw * 0.5)
        p["pops"]["商人"]["wealth"] += int(_draw * 0.5)
