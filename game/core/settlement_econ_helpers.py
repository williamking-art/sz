# -*- coding: utf-8 -*-
"""宋祚 · 结算金钱/粮分发助手（从 settlement_steps.py 拆出，零行为变更）。

- `_distribute_pop_wealth`：lump 按 POP size 分摊，**尾差归最大府**（守恒）
- `_settle_mint`：铸钱受控（铜料约束 + 熔耗 + 对账台账）
"""
from __future__ import annotations


def _distribute_pop_wealth(state, lump, cls, total):
    """把 lump 贯按各府 cls POP 的 size 比例分摊入 wealth，**尾差归最大府**。

    守恒修正：逐府 `int(lump * size / total)` 截断使 Σcredit < lump，差额成为
    无对手方的货币销毁（对账残差漂移源，实测 ~50 贯/月）。分摊后 Σcredit == lump。
    """
    if lump <= 0 or total <= 0:
        return 0
    shares = {}
    big_key, big_sz = None, -1
    for rk, p in state.prefectures.items():
        sz = p["pops"][cls]["size"]
        if sz > 0:
            shares[rk] = int(lump * sz / total)
            if sz > big_sz:
                big_key, big_sz = rk, sz
    if big_key is None:
        return 0
    shares[big_key] += lump - sum(shares.values())
    for rk, c in shares.items():
        state.prefectures[rk]["pops"][cls]["wealth"] += c
    return lump


def _settle_mint(state, log, amount: int = 0):
    """铸钱受控（T9 定稿）：铜资源约束 + 熔耗 20% 净增 80% + 物价>2.0 禁止。

    供诏令/工具调用（铸钱请求 amount 贯）：校验物价上限与金属资源存量，
    熔耗 20%（MINT_MELT_LOSS）→ 净增 80%（MINT_NET_RATIO）入民间流通（工匠/商人 wealth）。
    返回 (ok, message)。
    """
    from content.data import (MINT_MELT_LOSS, MINT_NET_RATIO, MINT_PRICE_BAN,
                              COPPER_RESOURCE_DIM)
    if state.price_level > MINT_PRICE_BAN:
        return False, f"物价 {state.price_level:.2f} 高于 {MINT_PRICE_BAN}，禁铸钱（防助涨通胀）"
    if amount <= 0:
        return False, "铸钱量须为正"
    # 金属料：优先熔铜池（熔化回收的铜料，闭环），不足回退 resources 存量
    _pool = int(state.coin.get("melted_pool", 0) or 0)
    _res = state.resources.get(COPPER_RESOURCE_DIM, {})
    _metal = _pool + int(_res.get("stock", 0) or 0)
    # 金属需求 = 铸钱额 / 净增率（含熔耗；熔耗 20% 时需金属 = 额 / 0.8）
    _need_metal = int(amount / MINT_NET_RATIO)
    if _metal < _need_metal:
        return False, f"铜料不足：需 {_need_metal} 单位（熔铜池+存 {_metal}），铸钱受阻"
    # 先耗熔铜池，再耗 resources（守恒：wealth→池→铸钱→wealth 闭环）
    _from_pool = min(_pool, _need_metal)
    state.coin["melted_pool"] = _pool - _from_pool
    if _need_metal > _from_pool:
        _res["stock"] = max(0, int(_res.get("stock", 0) or 0) - (_need_metal - _from_pool))
    _net = int(amount * MINT_NET_RATIO)          # 净增 80%（20% 熔耗蒸发，退出流通）
    _art_total = sum(p["pops"]["工匠"]["size"] for p in state.prefectures.values()) or 1
    _mer_total = sum(p["pops"]["商人"]["size"] for p in state.prefectures.values()) or 1
    # 尾差归最大府（同 _distribute_pop_wealth）：逐府 int() 截断会使 Σcredit < _net，
    # 差额成为无对手方销毁（audit 残差恒正的来源之一）。
    # 工匠/商人各半；仅一侧有人时整笔给该侧（避免半数凭空消失）。
    _both = _art_total > 0 and _mer_total > 0
    for _cls, _cls_total in (("工匠", _art_total), ("商人", _mer_total)):
        if _both:
            _half = _net // 2 if _cls == "工匠" else _net - _net // 2
        else:
            _half = _net if _cls_total > 0 else 0
        if _half <= 0 or _cls_total <= 0:
            continue
        _shares = {}
        _big, _big_sz = None, -1
        for _rk, _p in state.prefectures.items():
            _sz = _p["pops"][_cls]["size"]
            if _sz > 0:
                _shares[_rk] = int(_half * _sz / _cls_total)
                if _sz > _big_sz:
                    _big, _big_sz = _rk, _sz
        if _big is None:
            continue
        _shares[_big] += _half - sum(_shares.values())
        for _rk, _c in _shares.items():
            state.prefectures[_rk]["pops"][_cls]["wealth"] += _c
    state.statistics["minted"] = state.statistics.get("minted", 0) + _net
    # 对账：矿料（resources，不在 M_ALL）→ 货币 = external_in；熔铜池出资 = 池侧离账，
    # 其中未变成钱的部分（熔耗）记 burn，使 residual 归零。
    try:
        from core.money import register_flow as _reg_flow
        if _net > 0:
            _reg_flow(state, "external", _net, "铸钱净增")
        if _from_pool > 0:
            _reg_flow(state, "burn", _from_pool, "熔铜池出资离账")
    except Exception:  # noqa: BLE001 — 台账登记失败不影响结算
        pass
    log.append(f"[铸钱] 熔铜铸钱 {amount}贯（熔耗 {amount - _net}贯，净增 {_net}贯入市）")
    return True, f"铸钱 {_net}贯入市（熔耗 {amount - _net}贯）"
