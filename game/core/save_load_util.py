# -*- coding: utf-8 -*-
"""宋祚 · 存档工具（从 save_load.py 拆出，零行为变更）。

供 save_load.py re-export，既有 `from core.save_load import _safe_int` 等调用不破坏。
"""
from __future__ import annotations

import math
import os

from content.data import SAVE_DIR, FACTION_NAMES

#: 当前合法集团名（改名后：新党/旧党/皇党集团/军功集团/中立派）
FACTION_NAME_SET = frozenset(FACTION_NAMES)


def _strip_unknown_faction_keys(state) -> list:
    """清理旧存档里**已废弃的集团名键**（2026-09-19 集团改名，用户定稿"不迁移"）。

    不迁移 ≠ 什么都不做：`faction_split`（立场占比）与各诏令的 `faction_stances`
    都以集团名为键，而 `GameState.calc_decree_execution_rate` 会 `self.factions[名]`
    直接取值 → 旧名残留会让**读档即崩**。故此处按当前 `FACTION_NAMES` 白名单删键，
    只删已废弃的键、不动其余值；返回被删名单（供日志诊断）。
    """
    known = FACTION_NAME_SET
    dropped: set = set()

    def _clean(d) -> None:
        if not isinstance(d, dict):
            return
        for k in [k for k in list(d.keys()) if str(k) not in known]:
            d.pop(k, None)
            dropped.add(str(k))

    _clean(getattr(state, "faction_split", None))
    for attr in ("pending_decrees", "active_decrees", "longterm_public", "longterm_secret",
                 "pending_secret_decrees", "pending_public_decrees"):
        for dec in (getattr(state, attr, None) or []):
            if isinstance(dec, dict):
                _clean(dec.get("faction_stances"))
    return sorted(dropped)


def _safe_int(value, default=None):
    """宽松取整：空值 / 布尔 / 数字串可转则转；非法字符串、容器、NaN/inf → `default`。

    审查 P2-10：存档字段被写坏成对象/列表/乱码字符串时，`int()` 会抛未处理异常
    （经 UI/后端 → 500）。统一走此入口，把「档损坏」交给既有损坏档路径，
    而不是让异常冒泡。
    """
    if isinstance(value, bool):
        return int(value)
    if value is None or isinstance(value, (dict, list, tuple, set, bytes, bytearray)):
        return default
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return default
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_float(value, default=None):
    """宽松取浮点：语义同 `_safe_int`，并剔除 NaN / ±inf。"""
    if isinstance(value, bool):
        return float(value)
    if value is None or isinstance(value, (dict, list, tuple, set, bytes, bytearray)):
        return default
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return default
    try:
        f = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return f if math.isfinite(f) else default


# 注意：`_slot_path` 刻意留在 save_load.py——它读模块级 SAVE_DIR，
# 测试通过 monkeypatch.setattr(save_load, "SAVE_DIR", ...) 重定向路径；
# 抽到本模块会让 patch 失效（读到 save_load_util.SAVE_DIR）。


def migrate_army_units(data: dict):
    """旧档军队模型迁移（从 load_game 拆出，零行为变更）。

    用户定稿·每路禁/厢/乡各一支：
      ① 旧版单兵种（branch/troops）→ branches {"军籍:兵种": 人数}；
      ② 混合版（branches 键「军籍:兵种」复合键）→ 按军籍拆分（每支单一军籍），兵额守恒。
    返回 (army_units: list[ArmyUnit], central_arsenal: CentralArsenal)。
    """
    from core.army_models import build_army_units, ArmyUnit, CentralArsenal
    if "army_units" not in data:
        # 旧档兼容：无 army_units 字段，由调用方从 state 重建
        return None, CentralArsenal()
    _units = []
    for d in data.get("army_units", []):
        if not isinstance(d, dict):
            continue
        d = dict(d)
        if "branches" not in d and "branch" in d:
            d["branches"] = {f"{d.get('tier', '禁军')}:{d.pop('branch', '轻步兵')}":
                             _safe_int(d.pop("troops", 0), 0)}
        brs = d.get("branches") or {}
        if any(":" in k for k in brs):
            by_tier = {}
            for k, n in brs.items():
                t, b = k.split(":", 1) if ":" in k else (d.get("tier", "禁军"), k)
                bucket = by_tier.setdefault(t, {})
                bucket[b] = bucket.get(b, 0) + n
            for t, brs2 in by_tier.items():
                nd = dict(d)
                nd["tier"] = t
                nd["branches"] = brs2
                _units.append(ArmyUnit(**nd))
        else:
            _units.append(ArmyUnit(**d))
    # 审查 P0-3：旧档站名迁移（20 路重构前 ARMY_UNIT_INIT 用旧经济单位名）
    _STATION_RENAME = {
        "东京开封府": "京畿路",
        "河东": "河东路",
    }
    for _u in _units:
        _old = getattr(_u, "station", "")
        if _old in _STATION_RENAME:
            _u.station = _STATION_RENAME[_old]
    _stock = data.get("central_arsenal", {}).get("stock", {})
    arsenal = CentralArsenal(stock=_stock) if _stock else CentralArsenal()
    return _units, arsenal
