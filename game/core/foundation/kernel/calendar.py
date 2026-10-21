# -*- coding: utf-8 -*-
"""日历/年号服务 —— P0 零行为。

把"相对 1101 的隐式假设"收进一个可测试对象；当前只做只读计算与状态镜像，
不改结算公式。后续由 `new_game(pack_id=...)` 用 pack 的 start_year/年号初始化。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

__all__ = ["Calendar", "sync_state"]

def sync_state(state: Any) -> Optional[Calendar]:
    """把 `state.year/month/era_name` 镜像到 `state.calendar`（若存在）；不反向写 state。"""
    cal = getattr(state, "calendar", None)
    if not isinstance(cal, Calendar):
        return None
    cal.year = int(getattr(state, "year", cal.year))
    cal.month = int(getattr(state, "month", cal.month))
    cal.era_name = str(getattr(state, "era_name", cal.era_name) or "")
    return cal


@dataclass
class Calendar:
    start_year: int = 1101
    year: int = 1101
    month: int = 1
    era_name: str = ""

    @classmethod
    def from_manifest(cls, manifest: Any, year: Optional[int] = None,
                      month: Optional[int] = None) -> "Calendar":
        start = int(getattr(manifest, "start_year", 1101))
        return cls(
            start_year=start,
            year=int(year if year is not None else getattr(manifest, "start_year", start)),
            month=int(month if month is not None else getattr(manifest, "start_month", 1)),
            era_name=str(getattr(manifest, "era_name", "") or ""),
        )

    @classmethod
    def from_state(cls, state: Any) -> "Calendar":
        cal = getattr(state, "calendar", None)
        if isinstance(cal, Calendar):
            return cal
        return cls(start_year=int(getattr(cal, "start_year", 1101)) if cal else 1101,
                   year=int(getattr(state, "year", 1101)),
                   month=int(getattr(state, "month", 1)),
                   era_name=str(getattr(state, "era_name", "") or ""))

    def year_index(self, year: Optional[int] = None) -> int:
        """相对开局年的序号（0 起）；开局前为负。"""
        return int(year if year is not None else self.year) - int(self.start_year)

    def exam_cycle(self, interval: int = 3, year: Optional[int] = None) -> bool:
        """科次/郊祀等周期：相对开局年取模。interval<=0 ⇒ False。"""
        if interval <= 0:
            return False
        return self.year_index(year) % int(interval) == 0

    def advance(self) -> Tuple[int, int, str]:
        """推进一月并同步自身；返回 (year, month, era_name)。"""
        m = int(self.month) + 1
        if m > 12:
            m = 1
            self.year = int(self.year) + 1
        self.month = m
        return self.year, self.month, self.era_name

    def snapshot(self) -> Dict[str, Any]:
        return {"start_year": self.start_year, "year": self.year,
                "month": self.month, "era_name": self.era_name}

    def apply_era_names(self, era_names_history: Mapping[int, str]) -> str:
        """按年号表更新当前年号（与旧 `update_era_name` 同口径：取 <= 当前年的最大键）。"""
        name = str(self.era_name or "")
        for y, n in sorted((era_names_history or {}).items(), reverse=True):
            if int(self.year) >= int(y):
                name = str(n)
                break
        self.era_name = name
        return name
