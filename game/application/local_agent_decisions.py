# -*- coding: utf-8 -*-
"""本地 Agent 决策（第一片：仓廪/漕运）—— 用程序+天道替代一次 LLM 往返。

只降低推演 token，不改变数值口径：
- 输入仍是 state（与 `granary_decide` 同源读数）；
- 输出仍是契约要求的三态/四态档位 + 短叙事；
- 默认关闭（`SONGZUO_LOCAL_AGENTS=1` 才启用），失败/缺读数 ⇒ 返回 None，调用方回落 LLM。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

__all__ = ["local_agents_enabled", "local_granary_decide", "local_relief_decide",
           "local_economy_decide", "local_diplomacy_decide", "local_military_decide",
           "local_unrest_decide", "local_sentiment_decide",
           "local_decree_duration_decide", "local_agent_savings", "local_decide"]

TIERS4 = ("微", "小", "中", "大")
LOSS_TIERS = ("无", "轻", "中", "重")


def local_agents_enabled() -> bool:
    return str(os.environ.get("SONGZUO_LOCAL_AGENTS", "")).strip().lower() in ("1", "true", "yes", "on")


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _tier_by_cut(v: Optional[float], cuts) -> str:
    if v is None:
        return "小"
    for limit, tier in cuts:
        if v <= limit:
            return tier
    return "大"


def local_granary_decide(state: Any) -> Optional[Dict[str, Any]]:
    """确定性仓廪档位；读数严重缺失时返回 None（交给 LLM/旧路径）。"""
    if state is None:
        return None
    granary = _num(getattr(state, "granary", None))
    cap = _num(getattr(state, "granary_cap", None))
    block = _num(getattr(state, "canal_block", None)) or 0.0
    disaster = _num(getattr(state, "disaster_severity", None)) or 0.0
    month = int(getattr(state, "month", 1) or 1)
    prefs = getattr(state, "prefectures", None) or {}
    unrest = 0.0
    prices = []
    for p in prefs.values() if isinstance(prefs, dict) else ():
        if not isinstance(p, dict):
            continue
        u = _num(p.get("unrest"))
        if u is not None:
            unrest = max(unrest, u)
        gp = _num(p.get("grain_price"))
        if gp is not None:
            prices.append(gp)

    # 漕运运期（3/6/9 月）且淤积低 ⇒ 入仓大；否则按淤积降档
    if month in (3, 6, 9) and block < 30:
        inflow = "大"
    else:
        inflow = _tier_by_cut(block, ((20, "中"), (50, "小"), (80, "微")))
    # 发仓：灾情/民怨/仓存低 ⇒ 出仓大
    pressure = max(disaster, min(100.0, unrest) / 20.0)
    if granary is not None and cap and cap > 0:
        ratio = granary / cap
        pressure = max(pressure, 1.0 - max(0.0, min(1.0, ratio)))
    outflow = "大" if pressure >= 3 else ("中" if pressure >= 1.5 else "小")
    # 平粜：粮价高于基准或灾情明显时加大
    base_price = _num(getattr(state, "grain_price", None))
    avg_price = (sum(prices) / len(prices)) if prices else None
    price_ratio = (avg_price / base_price) if (avg_price and base_price and base_price > 0) else None
    if price_ratio is None:
        price_stabilize = "中" if disaster > 0 else "小"
    elif price_ratio >= 1.5:
        price_stabilize = "大"
    elif price_ratio >= 1.2:
        price_stabilize = "中"
    else:
        price_stabilize = "小"
    # 军粮：驻军多/边事紧 ⇒ 大（用军费/兵力近似；缺失不臆造）
    troops = 0
    for u in (getattr(state, "army_units", None) or []):
        try:
            troops += int(getattr(u, "troops", 0) or 0)
        except Exception:  # noqa: BLE001
            continue
    army_supply = "大" if troops >= 200_000 else ("中" if troops >= 80_000 else "小")
    # 仓储损耗：天道/程序档位（灾/贪腐重 ⇒ 重；监察强 ⇒ 轻；默认中）
    corruption = getattr(state, "corruption", None)
    avg_corr = 0.0
    if isinstance(corruption, dict) and corruption:
        vals = [float(v) for v in corruption.values() if isinstance(v, (int, float))]
        avg_corr = sum(vals) / len(vals) if vals else 0.0
    if disaster >= 3 or avg_corr >= 0.6:
        storage_loss = "重"
    elif disaster <= 0 and avg_corr <= 0.2:
        storage_loss = "轻"
    else:
        storage_loss = "中"

    return {
        "granary": {"inflow": inflow, "outflow": outflow,
                    "price_stabilize": price_stabilize,
                    "army_supply": army_supply, "storage_loss": storage_loss},
        "narrative": "本地仓漕推演：%s入仓、%s发仓、平粜%s、军粮%s、仓储%s。" % (
            inflow, outflow, price_stabilize, army_supply, storage_loss),
        "_source": "local_tiandao",
    }


def local_relief_decide(state: Any) -> Optional[Dict[str, Any]]:
    """确定性赈济档位；无灾/无流民 ⇒ None（交给 LLM/旧路径）。"""
    if state is None:
        return None
    severity = int(_num(getattr(state, "disaster_severity", None)) or 0)
    prefs = getattr(state, "prefectures", None) or {}
    refugees = 0
    for p in prefs.values() if isinstance(prefs, dict) else ():
        if isinstance(p, dict):
            try:
                refugees += int(p.get("refugees", 0) or 0)
            except (TypeError, ValueError):
                pass
    if severity <= 0 and refugees <= 0:
        return None
    level = max(1, min(5, severity or 1))
    granary = _num(getattr(state, "granary", None))
    # 赈济力度：灾级越重/流民越多/太仓越薄 ⇒ 越大
    if level >= 4 or refugees >= 200_000 or (granary is not None and granary < 200_000):
        relief = "大"
    elif level >= 3 or refugees >= 100_000:
        relief = "中"
    elif level >= 2 or refugees >= 30_000:
        relief = "小"
    else:
        relief = "微"
    # 流民档位（契约允许 微/小/中/大）：按存量分档
    if refugees >= 200_000:
        refugee = "大"
    elif refugees >= 100_000:
        refugee = "中"
    elif refugees >= 30_000:
        refugee = "小"
    else:
        refugee = "微"
    return {
        "disaster_level": level,
        "relief": relief,
        "refugee": refugee,
        "narrative": "本地赈济推演：灾级%d，赈济%s，流民%s档。" % (level, relief, refugee),
        "_source": "local_tiandao",
    }


def local_economy_decide(state: Any) -> Optional[Dict[str, Any]]:
    """确定性全国经济档位（替代强制 LLM economy_decide 的第一片）。

    只给档位，不给数值；读数缺失按中性档位处理，不伪造精确值。
    """
    if state is None:
        return None
    prefs = getattr(state, "prefectures", None) or {}
    unrest = 0.0
    prices = []
    for p in prefs.values() if isinstance(prefs, dict) else ():
        if not isinstance(p, dict):
            continue
        u = _num(p.get("unrest"))
        if u is not None:
            unrest = max(unrest, u)
        gp = _num(p.get("grain_price"))
        if gp is not None:
            prices.append(gp)
    base = _num(getattr(state, "grain_price", None))
    avg = (sum(prices) / len(prices)) if prices else None
    ratio = (avg / base) if (avg and base and base > 0) else None
    treasury = _num(getattr(state, "treasury", None))
    granary = _num(getattr(state, "granary", None))
    disaster = _num(getattr(state, "disaster_severity", None)) or 0.0
    if ratio is None:
        price_trend = "平"
    elif ratio >= 1.2:
        price_trend = "通胀"
    elif ratio <= 0.8:
        price_trend = "通缩"
    else:
        price_trend = "平"
    # 景气：钱粮/灾情/民怨的综合档位
    score = 0
    if treasury is not None and treasury < 1_000_000:
        score -= 1
    if granary is not None and granary < 200_000:
        score -= 1
    if disaster >= 3 or unrest >= 60:
        score -= 1
    if price_trend == "通胀":
        score -= 1
    boom = "大" if score >= 1 else ("中" if score >= -1 else ("小" if score >= -3 else "微"))
    # 士绅：粮价高/灾荒 ⇒ 囤；价低/太平 ⇒ 抛；其余观望
    if disaster >= 2 or (ratio is not None and ratio >= 1.15):
        gentry, gentry_power = "囤", ("大" if disaster >= 3 else "中")
    elif price_trend == "通缩" or (unrest < 30 and disaster <= 0):
        gentry, gentry_power = "抛", "小"
    else:
        gentry, gentry_power = "观望", "中"
    production = "小" if disaster >= 2 else ("大" if disaster <= 0 and boom in ("大", "中") else "中")
    hoard = "无" if boom in ("大", "中") else ("小" if boom == "小" else "中")
    urban = "小" if boom in ("大", "中") else "无"
    return_home = "中" if disaster >= 2 else "小"
    exam = "小"
    # 金融 5 字段（与 FINANCE_STATES 白名单一致）
    jiaozi = "跌" if (unrest >= 60 or price_trend == "通胀") else "稳"
    shortage = "加剧" if (treasury is not None and treasury < 1_000_000) else "平"
    maritime = "平"
    bank = "损" if boom in ("微",) else "稳"
    return {
        "景气": boom, "士绅": gentry, "士绅力度": gentry_power, "生产": production,
        "窖银": hoard, "城市化": urban, "回乡": return_home, "科举": exam,
        "jiaozi_trust": jiaozi, "shortage": shortage, "maritime": maritime,
        "bank": bank, "price_trend": price_trend,
        "_source": "local_tiandao",
    }


def local_diplomacy_decide(state: Any) -> Optional[Dict[str, Any]]:
    """确定性外交档位：态度/岁币/盟约；只读 external + 国库。"""
    if state is None:
        return None
    ext = getattr(state, "external", None) or {}
    threat = 0.0
    for name in ("金", "辽", "西夏"):
        row = ext.get(name) if isinstance(ext, dict) else None
        if isinstance(row, dict):
            v = _num(row.get("invasion_will"))
            if v is not None:
                threat = max(threat, v)
    treasury = _num(getattr(state, "treasury", None))
    if threat >= 70:
        attitude, sui, alliance = "大", "订", "结"
    elif threat >= 40:
        attitude, sui, alliance = "中", "不变", "结"
    elif threat >= 15:
        attitude, sui, alliance = "小", "不变", "不变"
    else:
        attitude, sui, alliance = "微", ("毁" if (treasury or 0) > 2_000_000 else "不变"), "不变"
    return {"attitude": attitude, "sui_gong": sui, "alliance": alliance,
            "_source": "local_tiandao"}


def local_military_decide(state: Any) -> Optional[Dict[str, Any]]:
    """确定性军事档位：战力/兵额/训练/士气/征发；只读 army + 国库。"""
    if state is None:
        return None
    units = getattr(state, "army_units", None) or []
    troops = 0
    morale_vals, training_vals = [], []
    for u in units:
        try:
            troops += int(getattr(u, "troops", 0) or 0)
            m = _num(getattr(u, "morale", None))
            t = _num(getattr(u, "training", None))
            if m is not None:
                morale_vals.append(m)
            if t is not None:
                training_vals.append(t)
        except (TypeError, ValueError):
            continue
    morale = sum(morale_vals) / len(morale_vals) if morale_vals else None
    training = sum(training_vals) / len(training_vals) if training_vals else None
    treasury = _num(getattr(state, "treasury", None))
    ext = getattr(state, "external", None) or {}
    threat = 0.0
    for name in ("金", "辽", "西夏"):
        row = ext.get(name) if isinstance(ext, dict) else None
        if isinstance(row, dict):
            v = _num(row.get("invasion_will"))
            if v is not None:
                threat = max(threat, v)
    power = "大" if (troops >= 150_000 and (morale is None or morale >= 55)) else (
        "中" if troops >= 60_000 else ("小" if troops > 0 else "微"))
    army = "大" if (treasury or 0) >= 3_000_000 and threat >= 40 else (
        "中" if (treasury or 0) >= 1_000_000 else "小")
    train = "大" if (training or 0) >= 60 else ("中" if (training or 0) >= 40 else "小")
    mor = "大" if (morale or 0) >= 60 else ("中" if (morale or 0) >= 40 else "小")
    levy = "大" if threat >= 70 else ("中" if threat >= 40 else "小")
    return {"power": power, "army": army, "training": train,
            "morale": mor, "levy": levy, "_source": "local_tiandao"}


def local_unrest_decide(state: Any) -> Optional[Dict[str, Any]]:
    """确定性民变档位：无/小乱/骚乱/大乱（替代外部 Jev 生产者）。"""
    if state is None:
        return None
    sat = _num(getattr(state, "population_satisfaction", None))
    prefs = getattr(state, "prefectures", None) or {}
    unrest = 0.0
    refugees = 0
    for p in prefs.values() if isinstance(prefs, dict) else ():
        if not isinstance(p, dict):
            continue
        u = _num(p.get("unrest"))
        if u is not None:
            unrest = max(unrest, u)
        try:
            refugees += int(p.get("refugees", 0) or 0)
        except (TypeError, ValueError):
            pass
    if (sat is not None and sat < 15) or unrest >= 85 or refugees >= 500_000:
        tier = "大乱"
    elif (sat is not None and sat < 30) or unrest >= 65 or refugees >= 250_000:
        tier = "骚乱"
    elif (sat is not None and sat < 45) or unrest >= 45 or refugees >= 100_000:
        tier = "小乱"
    else:
        tier = "无"
    return {"tier": tier, "note": "本地天道裁民变", "_source": "local_tiandao"}


def local_sentiment_decide(state: Any) -> Optional[Dict[str, Any]]:
    """确定性民情档位：大坏/转坏/持平/转好/大好（替代外部 Jev 生产者）。"""
    if state is None:
        return None
    sat = _num(getattr(state, "population_satisfaction", None))
    prestige = _num(getattr(state, "prestige", None))
    treasury = _num(getattr(state, "treasury", None))
    if sat is None:
        return None
    if sat < 20:
        tier = "大坏"
    elif sat < 40:
        tier = "转坏"
    elif sat < 60:
        tier = "持平"
    elif sat < 80:
        tier = "转好"
    else:
        tier = "大好"
    # 皇威/国库极弱时压低一档；极强时抬高半档（只用既有档位）
    if (prestige is not None and prestige < 20) or (treasury is not None and treasury < 500_000):
        tier = {"大好": "转好", "转好": "持平", "持平": "转坏",
                "转坏": "大坏", "大坏": "大坏"}[tier]
    elif (prestige is not None and prestige >= 80) and (treasury or 0) >= 3_000_000:
        tier = {"转好": "大好", "持平": "转好", "转坏": "持平",
                "大坏": "转坏", "大好": "大好"}[tier]
    return {"tier": tier, "note": "本地天道裁民情", "_source": "local_tiandao"}


def local_decree_duration_decide(state: Any) -> Optional[Dict[str, Any]]:
    """确定性诏令时效/态度/落地档（替代 `jev_gate` 外部调用的本地版）。"""
    if state is None:
        return None
    decrees = [d for d in (getattr(state, "pending_decrees", None) or [])
               if isinstance(d, dict)]
    if not decrees:
        return None
    effects = set()
    ids, titles = [], []
    for d in decrees[:5]:
        eff = d.get("effects") if isinstance(d.get("effects"), dict) else {}
        effects.update(str(k) for k in eff)
        did = str(d.get("decree_id") or "").strip()
        if did:
            ids.append(did)
        title = str(d.get("title") or "").strip()
        if title:
            titles.append(title)
    long_keys = {"reduce_office", "curtail_waste", "land_survey", "anti_corruption",
                 "granary_reform", "military_supply"}
    immediate_keys = {"pay_reform", "commerce_tax", "single_whip", "prestige",
                      "treasury", "imperial_treasury", "population_satisfaction",
                      "faction_change", "defense_bonus", "he_mi", "grain_stabilize"}
    if effects & long_keys:
        timing, pace = "长期", "缓"
    elif effects & immediate_keys:
        timing, pace = "即时", "速"
    else:
        timing, pace = "短期", "常"
    prestige = _num(getattr(state, "prestige", None))
    satisfaction = _num(getattr(state, "population_satisfaction", None))
    corruption = getattr(state, "corruption", None)
    avg_corr = 0.0
    if isinstance(corruption, dict) and corruption:
        vals = [float(v) for v in corruption.values() if isinstance(v, (int, float))]
        avg_corr = sum(vals) / len(vals) if vals else 0.0
    loss_to_officials = bool(effects & {"reduce_office", "curtail_waste", "anti_corruption"})
    gain_to_officials = bool(effects & {"pay_reform"})
    if prestige is not None and prestige >= 70 and avg_corr <= 0.3:
        attitude = "奉行" if not loss_to_officials else "依违"
    elif prestige is not None and prestige < 35 or avg_corr >= 0.6:
        attitude = "拖延" if loss_to_officials else "阳奉阴违"
    elif gain_to_officials:
        attitude = "奉行"
    else:
        attitude = "依违"
    landing = {"奉行": "全办", "依违": "大部", "阳奉阴违": "半数", "拖延": "少半"}[attitude]
    out = {"pace": pace, "execution_timing": timing,
           "execution_attitude": attitude, "landing_level": landing,
           "_decree_ids": ids, "_decree_titles": titles,
           "_source": "local_tiandao"}
    try:
        turn = getattr(state, "turn", None)
        if turn is not None:
            out["_turn"] = int(turn)
    except (TypeError, ValueError):
        pass
    return out


_LOCAL = {"granary": local_granary_decide, "relief": local_relief_decide,
          "economy": local_economy_decide, "diplomacy": local_diplomacy_decide,
          "military": local_military_decide, "unrest": local_unrest_decide,
          "sentiment": local_sentiment_decide,
          "decree_duration": local_decree_duration_decide}


def local_agent_savings(state: Any) -> Dict[str, Any]:
    """本地替代读数（供 token 面板）：按 Agent 计数 + 省下的 LLM 调用数。"""
    stats = getattr(state, "local_agent_stats", None) if state is not None else None
    if not isinstance(stats, dict):
        return {"by_agent": {}, "saved_llm_calls": 0}
    by_agent = {k: int(v) for k, v in stats.items()
                if k != "saved_llm_calls" and isinstance(v, (int, float))}
    return {"by_agent": by_agent,
            "saved_llm_calls": int(stats.get("saved_llm_calls", 0) or 0)}


def local_decide(agent_id: str, state: Any) -> Optional[Dict[str, Any]]:
    fn = _LOCAL.get(str(agent_id))
    if fn is None or not local_agents_enabled():
        return None
    try:
        return fn(state)
    except Exception:  # noqa: BLE001 —— 本地失败必须回落 LLM/旧路径
        import logging
        logging.getLogger("local_agent").warning("本地 %s 决策失败", agent_id, exc_info=True)
        return None
