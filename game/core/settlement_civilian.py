# -*- coding: utf-8 -*-
"""宋祚 · 士绅囤粮/窖银（POP 经济子模块）

从 settlement_steps.py 拆分而出（P2-5 巨文件拆分第一步），逻辑与调用签名完全不变：
  _settle_civilian_hoard(state, log)

边界：自包含，仅依赖 state 与 content.data 的 HOARD_SUPPLY_SQUEEZE / TIER_RANGE。
settlement_steps.py 仍从本模块 re-export，所有既有 import 无需改动。
"""
from content.data import HOARD_SUPPLY_SQUEEZE, TIER_RANGE, HOARD_SPOIL_RATE, HOARD_DRAW_RATE, HOARD_CAP_MULT, HOARD_COPPER_RATIO_BASE


def _buyer_pool(p, price):
    """该路缺粮 POP 的可支付财富池（A1/B1 抛粮买方化）。

    买方 = 工匠/商人/官僚/兵 中当月缺粮者；可支付财富 = wealth - 保底线
    （保底线 = 1 个月口粮钱，与税征段 _min_wealth 同口径）。
    返回 ([ (pop_name, 缺口石, 可支付贯) ...], 池总额贯)；无合格买方返回 ([], 0)。
    """
    from content.data import PER_CAPITA_MONTH_GRAIN
    buyers = []
    pool = 0
    for pop_name in ("工匠", "商人", "官僚", "兵"):
        pop = p["pops"][pop_name]
        need = int(pop["size"] * PER_CAPITA_MONTH_GRAIN)
        short = max(0, need - pop.get("grain", 0))
        if short <= 0:
            continue
        floor = int(pop["size"] * PER_CAPITA_MONTH_GRAIN * price)   # 保底线（贯）
        afford = max(0, pop["wealth"] - floor)
        if afford <= 0:
            continue
        buyers.append((pop_name, short, afford))
        pool += afford
    return buyers, pool


def _sell_to_buyers(p, seller, qty, price, copper_share=1.0):
    """把 qty 石粮卖给该路缺粮 POP 买方池，返回实售石数（A1/B1）。

    实售 = min(qty, 池可购石数)；买方按缺口比例扣 wealth、得粮（钱粮双向守恒）：
      买方 wealth -= share（钱出）、grain += 份额粮（缺口被填补，粮进）；
      卖方士绅 grain -= sold（粮出，调用处扣减）、wealth+窖银 += sold×price（钱进）。
    尾差归末位：买方扣款合计 == cost、买方得粮合计 == sold（无凭空生钱/灭粮）。
    窖银只藏铜钱（用户史实指示 b）：交子有界贬值、不能窖藏——交子部分全额进 wealth，
    仅铜钱部分按 30/70 拆分（copper_share = 铜钱占流通货币比例）。
    池为 0 → 实售 0（囤积维持，不造币）。
    """
    buyers, pool = _buyer_pool(p, price)
    if not buyers:
        return 0
    price_wen = max(int(price * 1000), 1)
    can_buy = (pool * 1000) // price_wen   # pool（贯）按文级单价折算石（×1000 对齐 price_wen，防贯/文量级 bug）
    sold = min(qty, can_buy)
    if sold <= 0:
        return 0
    cost = int(sold * price)
    short_total = sum(b[1] for b in buyers)
    paid = 0
    grain_given = 0
    for i, (pop_name, short, _aff) in enumerate(buyers):
        share = int(cost * short / short_total)
        grain_share = int(sold * short / short_total)
        if i == len(buyers) - 1:            # 尾差归末位：扣款合计 == cost、得粮合计 == sold
            share = cost - paid
            grain_share = sold - grain_given
        pop = p["pops"][pop_name]
        pop["wealth"] -= share              # 钱出
        pop["grain"] = pop.get("grain", 0) + grain_share   # 粮进（缺口被填补）
        paid += share
        grain_given += grain_share
    copper = int(cost * max(0.0, min(1.0, copper_share)))   # 铜钱部分
    jiaozi_part = cost - copper                              # 交子部分（不窖藏，全进流通）
    _hoard_ratio = HOARD_COPPER_RATIO_BASE                   # 铜钱入窖比例（复核定案 0.5）
    seller["wealth"] += int(copper * (1 - _hoard_ratio)) + jiaozi_part  # (1−ratio) 铜钱 + 全部交子进 wealth
    seller["窖银"] = seller.get("窖银", 0) + int(copper * _hoard_ratio)  # ratio 铜钱进窖银（只藏铜钱）
    return sold


def _settle_civilian_hoard(state, log):
    """士绅囤粮操作（钱粮守恒）：AI 推演档位优先，无 AI 时按粮价方向兜底。

    囤 = 士绅用 wealth 买粮（wealth↓ grain↑，受资金约束）；抛 = 卖粮得钱（grain↓ wealth↑）。
    士绅囤粮挤压市场流通（见 calc_region_grain_price 的 HOARD_SUPPLY_SQUEEZE）。
    """
    # AI 经济动态推演（settle_turn 已注入 state._economy_ai：{景气,士绅,士绅力度,生产,窖银}）或无
    _eco = getattr(state, "_economy_ai", None) or {}
    _ai_act = _eco.get("士绅", "") if _eco.get("士绅") in ("囤", "抛") else None
    _ai_tier = _eco.get("士绅力度", "中")
    # 窖银只藏铜钱（用户史实指示 b）：铜钱占流通货币比例 = 1 - 交子有效额 / 货币总量
    # （交子有界贬值、不能窖藏；issued=0 时 100% 铜钱，藏富不受影响）
    _jiaozi_eff = state.jiaozi.get("issued", 0) * state._jiaozi_acceptance()
    _pop_money = sum(pop.get("wealth", 0)
                     for _p in state.prefectures.values() for pop in _p.get("pops", {}).values())
    _money_total = _jiaozi_eff + _pop_money + max(0, state.treasury) + max(0, state.imperial_treasury)
    _copper_share = max(0.0, min(1.0, 1.0 - _jiaozi_eff / max(_money_total, 1.0)))
    # 窖银动用档位（A1 定稿·用户史实指示 c）：AI 推演决定每月动用比例，程序换算；
    # 无 AI（本地降级/_economy_ai 缺该键）默认「无」= 冻结不动用（藏富不到最后关头不用）。
    _draw_tier = _eco.get("窖银") if _eco.get("窖银") in HOARD_DRAW_RATE else "小"   # no-AI 被动缓释 0.5%/月（防永久抽水；有 AI 由档位决定）
    _draw_rate = HOARD_DRAW_RATE.get(_draw_tier, 0.0)
    for name, p in state.prefectures.items():
        genty = p["pops"]["士绅"]
        price = p.get("grain_price", state.grain_price)
        if _ai_act:
            act, tier = _ai_act, _ai_tier   # AI 推演（全国统一景气下的士绅行为）
        elif not _eco:
            # 全游戏级强制 AI（拒绝式）：无经济推演 → 不伪造囤/抛决策，士绅按兵不动
            act, tier = "观望", "无"
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
        # 囤粮上限（A1 定案·软约束）：软上限 = 士绅田产年产 × HOARD_CAP_MULT（0.3），
        # 硬上限 = 软上限 × 1.5。超软上限先售买方池、未售保留（囤积居奇机制保留）；
        # 仅超硬上限强制出清，未售按 3% 损耗核销（防无限囤积）。
        _land = max(float(p.get("land", 1)), 1.0)
        _gentry_land_total = float(p.get("gentry_land", 0)) + float(p.get("hidden_land", 0))
        _soft_cap = int(p.get("grain", 0) * _gentry_land_total / _land * HOARD_CAP_MULT)
        _hard_cap = int(_soft_cap * 1.5)
        if act == "囤":
            buy = int(p.get("grain", 0) / 12.0 * mult)      # 月产 × 档位
            afford = genty["wealth"] // max(int(price * 1000), 1)  # 资金能买多少石（文级精度）
            room = max(0, _soft_cap - genty["grain"])       # 囤粮余量（软上限约束）
            buy = min(buy, afford, room)
            if buy > 0:
                genty["wealth"] -= int(buy * price * 1000) / 1000.0
                genty["grain"] += buy
        elif act == "抛":
            sell = int(genty["grain"] * mult)
            if sell > 0:
                # B1：抛粮买方化——卖给该路缺粮 POP 可支付财富池，不卖给虚空；
                # 未售部分继续囤（囤积维持，不造币）。窖银只藏铜钱（copper_share）。
                sold = _sell_to_buyers(p, genty, sell, price, _copper_share)
                if sold > 0:
                    genty["grain"] -= sold
        # 超软上限：先售买方池，未售保留（不压回、不核销）——囤积居奇机制保留
        if genty["grain"] > _soft_cap:
            sold = _sell_to_buyers(p, genty, genty["grain"] - _soft_cap, price, _copper_share)
            if sold > 0:
                genty["grain"] -= sold
        # 仅超硬上限：强制出清，未售按损耗核销（不凭空变钱；粮压回硬上限，防无限囤积）
        if genty["grain"] > _hard_cap:
            _excess = genty["grain"] - _hard_cap
            sold = _sell_to_buyers(p, genty, _excess, price, _copper_share)
            genty["grain"] = _hard_cap
            _unsold = _excess - sold
            if _unsold > 0:
                # 未售部分按 HOARD_SPOIL_RATE 损耗核销（雀鼠耗/霉变）：粮凭空消失但钱不凭空生；
                # 3% 记入损耗统计，余量一并出清（grain 压回硬上限）
                _spoil = int(_unsold * HOARD_SPOIL_RATE)
                state.granary_stats["hoard_spoil"] = state.granary_stats.get("hoard_spoil", 0) + _spoil
        # 窖银动用（A1 定稿·用户史实指示 c）：按 AI 档位换算的每月动用比例取窖银出窖，
        # 流向工匠/商人（挥霍/购地/市舶投资等服务消费），死钱转活钱、不积累 wealth；
        # 无 AI 时 _draw_rate = 0（冻结，不到最后关头不用）。
        _draw = int(genty.get("窖银", 0) * _draw_rate)
        if _draw > 0:
            genty["窖银"] = genty.get("窖银", 0) - _draw
            p["pops"]["工匠"]["wealth"] += int(_draw * 0.5)
            p["pops"]["商人"]["wealth"] += int(_draw * 0.5)
