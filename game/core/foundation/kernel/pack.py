# -*- coding: utf-8 -*-
"""内容包（pack）加载骨架 —— P0 零行为。

只负责读取/校验 manifest，不改变任何游戏行为；后续阶段再由 `new_game` 选择 pack。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

__all__ = ["PackError", "PackManifest", "load_pack", "packs_root", "REQUIRED_FIELDS"]

REQUIRED_FIELDS = ("pack_id", "dynasty", "start_year", "schema_version")


class PackError(ValueError):
    """pack 缺失/非法。"""


@dataclass(frozen=True)
class PackManifest:
    pack_id: str
    dynasty: str
    start_year: int
    schema_version: int
    start_month: int = 1
    era_name: str = ""
    end_year: Optional[int] = None
    name: str = ""
    calendar: Mapping[str, Any] = field(default_factory=dict)
    data: Mapping[str, Any] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PackManifest":
        if not isinstance(data, Mapping):
            raise PackError("manifest 必须是 JSON object")
        missing = [k for k in REQUIRED_FIELDS if k not in data]
        if missing:
            raise PackError("manifest 缺字段：%s" % ",".join(missing))
        if not isinstance(data["pack_id"], str) or not data["pack_id"].strip():
            raise PackError("pack_id 必须是非空字符串")
        if not isinstance(data["dynasty"], str) or not data["dynasty"].strip():
            raise PackError("dynasty 必须是非空字符串")
        for key in ("start_year", "schema_version"):
            v = data[key]
            if isinstance(v, bool) or not isinstance(v, int):
                raise PackError("%s 必须是整数" % key)
        sm = data.get("start_month", 1)
        if isinstance(sm, bool) or not isinstance(sm, int) or not 1 <= sm <= 12:
            raise PackError("start_month 必须是 1..12 的整数")
        ey = data.get("end_year")
        if ey is not None and (isinstance(ey, bool) or not isinstance(ey, int)):
            raise PackError("end_year 必须是整数或缺失")
        for key in ("calendar", "data"):
            if key in data and not isinstance(data[key], Mapping):
                raise PackError("%s 必须是 object" % key)
        return cls(
            pack_id=data["pack_id"],
            dynasty=data["dynasty"],
            start_year=data["start_year"],
            schema_version=data["schema_version"],
            start_month=sm,
            era_name=str(data.get("era_name") or ""),
            end_year=ey,
            name=str(data.get("name") or ""),
            calendar=dict(data.get("calendar") or {}),
            data=dict(data.get("data") or {}),
            raw=dict(data),
        )


def packs_root(root: Optional[Path] = None) -> Path:
    """默认 `game/content/packs`；测试可传临时根。"""
    if root is not None:
        return Path(root)
    # .../game/core/foundation/kernel/pack.py -> .../game/content/packs
    return Path(__file__).resolve().parents[3] / "content" / "packs"


def load_pack(pack_id: str = "song_1101", root: Optional[Path] = None) -> PackManifest:
    """读取 `<root>/<pack_id>/manifest.json` 并校验；**不触碰 GameState**。"""
    pid = str(pack_id or "").strip()
    if not pid or "/" in pid or "\\" in pid or pid in (".", ".."):
        raise PackError("非法 pack_id：%r" % (pack_id,))
    path = packs_root(root) / pid / "manifest.json"
    if not path.is_file():
        raise PackError("pack 不存在或缺 manifest：%s" % path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PackError("manifest 读取/解析失败：%s（%r）" % (path, exc)) from exc
    manifest = PackManifest.from_dict(data)
    if manifest.pack_id != pid:
        raise PackError("manifest.pack_id=%r 与目录 %r 不一致" % (manifest.pack_id, pid))
    return manifest
