# -*- coding: utf-8 -*-
"""v4 立绘解析（整幅肖像 + 稳定分配）。

设计口径（2026-10-18 用户裁定）：
- 立绘是**整幅肖像**（非分件拼装）；同一官员永远同一张（按姓名稳定）；
- 现有 91 名官员各有专属立绘；未登记官员（科举新人等）按姓名哈希**稳定**分配到池内一张；
- 资产与索引都在仓库内：`game/assets/portraits/v4/*.webp` + `content/ministers/portrait_index_v4.json`；
- 只读：不写任何目录、不生成图片。缺失时返回 None，由调用方回退到旧路径（缺失 ≠ 0）。

改口径只改本文件与索引，不动调用方。
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_INDEX_PATH = os.path.join(_HERE, "portrait_index_v4.json")
_REPO_GAME = os.path.dirname(os.path.dirname(_HERE))          # game/
_ASSET_DIR = os.path.join(_REPO_GAME, "assets", "portraits", "v4")

_index_cache: Optional[Dict[str, dict]] = None
_pool_cache: Optional[Dict[str, dict]] = None


def _index() -> Dict[str, dict]:
    global _index_cache
    if _index_cache is None:
        try:
            with open(_INDEX_PATH, encoding="utf-8") as fh:
                _index_cache = dict((json.load(fh) or {}).get("officials") or {})
        except Exception:  # noqa: BLE001
            _index_cache = {}
    return _index_cache


def asset_dir() -> str:
    return _ASSET_DIR


def available() -> int:
    """已登记官员数（用于自检/读数，不做业务判断）。"""
    return len(_index())


def _safe_name(name: str) -> str:
    base = os.path.basename(str(name or "").strip())
    if not base or base != str(name or "").strip():
        return ""
    if ".." in base or "/" in base or "\\" in base:
        return ""
    return base


def _pool() -> Dict[str, dict]:
    """新官池（未登记官员用）。索引里有 pool 段就优先，没有则退回 officials。"""
    global _pool_cache
    if _pool_cache is None:
        try:
            with open(_INDEX_PATH, encoding="utf-8") as fh:
                _pool_cache = dict((json.load(fh) or {}).get("pool") or {})
        except Exception:  # noqa: BLE001
            _pool_cache = {}
    return _pool_cache


def _stable_pick(name: str) -> Optional[str]:
    """未登记官员：按姓名哈希稳定落到池内某一张（同名必同图）。

    池子（pool）存在时只从池内取；池内为空才退回已登记官员集合。
    """
    pool = _pool()
    source = pool if pool else _index()
    keys: List[str] = sorted(source)
    if not keys:
        return None
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
    return dict(source[keys[h % len(keys)]]).get("file")


def portrait_path(name: str, tier: Optional[str] = None) -> Optional[str]:
    """→ 立绘绝对路径；未登记则按哈希落池；池为空时 None（调用方回退旧逻辑）。

    `tier` 目前只用于将来"同脸跨级"版本（索引里若登记 tiers 则优先取用）。
    """
    safe = _safe_name(name)
    if not safe:
        return None
    entry = _index().get(safe)
    if entry:
        tiers = entry.get("tiers") or {}
        if tier and isinstance(tiers, dict) and tiers.get(tier):
            cand = os.path.join(_ASSET_DIR, str(tiers[tier]))
            if os.path.isfile(cand):
                return cand
        fn = entry.get("file")
        if fn:
            cand = os.path.join(_ASSET_DIR, str(fn))
            if os.path.isfile(cand):
                return cand
    fn = _stable_pick(safe)
    if fn:
        cand = os.path.join(_ASSET_DIR, str(fn))
        if os.path.isfile(cand):
            return cand
    return None


def has_exact(name: str) -> bool:
    """该官员是否有专属（非哈希池）立绘。"""
    return _safe_name(name) in _index()