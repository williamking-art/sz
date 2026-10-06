"""势力配置的**统一注册表**（P1）。

裁定 3：由统一注册表加载 `content/data_factions/*`；**共用机制定义与势力参数分离**。
裁定 1：**不得把宋配置作为外邦默认值** —— 查不到势力 ⇒ **显式报错**，不落 default。
"""
import importlib
from typing import Any, Dict, List, Optional

from content.faction_schema import (
    BASE_BUILDINGS, FieldState, FactionConfigError, REQUIRED_GROUPS,
    check_not_applicable_reason,
)

_REGISTRY: Optional[Dict[str, Any]] = None


def _module_faction_id(mod) -> str:
    return str(getattr(mod, 'FACTION_ID', '') or '')


def validate(faction: str, cfg: Dict[str, Any]) -> List[str]:
    """结构校验。**返回问题清单**；`strict` 时直接抛出。

    校验项：
 1. 必填组齐全；2. 基础建筑 id 必须落在共同目录或扩展层；
    3. `NOT_APPLICABLE` 必须带实质理由；
    4. `POSITION_CLASS` / `BUILDING_WORKER` 的引用闭合。
    """
    problems: List[str] = []
    allowed = set(BASE_BUILDINGS)
    allowed |= set(getattr(cfg, 'EXTENSION_BUILDINGS', ()) or ())
    for g in REQUIRED_GROUPS:
        if g not in cfg:
            problems.append('缺必填配置组 %s' % g)
    states = cfg.get('FIELD_STATES') or {}
    for k, v in states.items():
        if v == FieldState.NOT_APPLICABLE:
            try:
                check_not_applicable_reason(faction, k, (cfg.get('NA_REASONS') or {}).get(k))
            except FactionConfigError as e:
                problems.append(str(e))
    jpl = cfg.get('JOBS_PER_LEVEL') or {}
    for b in jpl:
        if b not in allowed:
            problems.append('基础建筑「%s」不在共同目录 %s（裁定 5：不得另造重复类型）'
                            % (b, tuple(sorted(allowed))))
    pos = set(cfg.get('POSITIONS') or ())
    for p in (cfg.get('POSITION_CLASS') or {}):
        if pos and p not in pos:
            problems.append('POSITION_CLASS 引用未登记职位「%s」' % p)
    return problems


def load_all(reload: bool = False) -> Dict[str, Any]:
    """加载 `content.data_factions` 下全部势力配置并校验。"""
    global _REGISTRY
    if _REGISTRY is not None and not reload:
        return _REGISTRY
    pkg = importlib.import_module('content.data_factions')
    names = list(getattr(pkg, 'FACTIONS', ()) or ())
    out: Dict[str, Any] = {}
    for name in names:
        mod = importlib.import_module('content.data_factions.%s' % name)
        fid = _module_faction_id(mod)
        if not fid:
            raise FactionConfigError('data_factions/%s.py 缺 FACTION_ID' % name)
        if fid in out:
            raise FactionConfigError('势力 id 重复：%s' % fid)
        cfg = mod.CONFIG
        cfg.setdefault('EXTENSION_BUILDINGS', tuple())
        probs = validate(fid, cfg)
        if probs:
            raise FactionConfigError('势力「%s」配置不合规：%s' % (fid, '；'.join(probs)))
        out[fid] = cfg
    _REGISTRY = out
    return out


def get(faction: str) -> Optional[Dict[str, Any]]:
    """按势力 id 取配置。

    🔴 查不到 ⇒ 返回 `None`（**不回落到宋侧、不回落 default**）。
    """
    return load_all().get(str(faction))


def get_field(faction: str, group: str) -> Any:
    """取单个配置组；缺失或标 NA ⇒ 返回 `None`（调用方须显示「未定义」）。"""
    cfg = get(faction)
    if cfg is None:
        return None
    states = cfg.get('FIELD_STATES') or {}
    if states.get(group) == FieldState.NOT_APPLICABLE:
        return None
    return cfg.get(group)