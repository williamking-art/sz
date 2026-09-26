# -*- coding: utf-8 -*-
"""POP 职位子池与丁口维度（B1a，2026-09-27 用户口径）。

用户定稿：
  · "设一个自耕农庄来容纳自耕农跟富农还有贫农，地主的农庄容纳佃农跟地主，
     一个建筑不是只有一个职位的啊" → 农按**职位**分槽；
  · "引入受抚养人口的概念，这样能贴合'户'这个概念" → 人口按**丁/口**二分。

结构（POP 挂载律：**不新增人口账**，只在 `农` POP 内划子池）
--------------------------------------------------------------
  · 职位子池：`自耕农 + 富农 + 贫农 + 佃农 == 农.size`（逐路）
  · 丁口子池：`ding（丁，应役） + kou（口，受抚养） == 农.size`（逐路）
  · 两套划分**正交**——两个边际，**不做交叉表**（否则农要 4×2 = 8 个子池）：
    `Σ职位 == Σ丁口 == size`
  · 隐户 `hidden` 是**加法**子池（不落籍、**不在** `size` 内），**不参与**上述恒等式。

为什么不做交叉表：职位是"经济身份"（种谁的田），丁口是"行政登记口径"（户内应役/受抚养），
两者由**不同机制**改变（职位随土地兼并与就业流动、丁口随年龄结构），交叉表会让
每一次土地兼并都要按丁口比例重算 8 个格子，收益远小于复杂度。
"""
from typing import Dict, List, Tuple

FARM_POSITIONS: Tuple[str, ...] = ("自耕农", "富农", "贫农", "佃农")
# 职位初始比例（🟡初值，可调）：自耕农为主体，佃农次之，富农小、贫农为小自耕/半佃
FARM_POSITION_SHARE: Dict[str, float] = {
    "自耕农": 0.42, "富农": 0.08, "贫农": 0.20, "佃农": 0.30,
}
_DING_KEY = "ding"
_KOU_KEY = "kou"


def _nong_of(p: dict):
    return ((p or {}).get("pops") or {}).get("农")


def _ding_ratio() -> float:
    from content.data_constants import DING_RATIO
    return float(DING_RATIO)


def seed_farm_slices(p: dict) -> int:
    """按比例把 `农.size` 划入四个职位子池，并按 `DING_RATIO` 二分丁/口。

    **只改子池，不改 `size`**（守恒）；尾差归"自耕农"（余数不凭空消失）。
    返回该路农的口数（= 分配总额）。
    """
    nong = _nong_of(p)
    if not isinstance(nong, dict):
        return 0
    size = max(0, int(nong.get("size", 0) or 0))
    alloc = {k: int(size * FARM_POSITION_SHARE[k]) for k in FARM_POSITIONS}
    alloc[FARM_POSITIONS[0]] += size - sum(alloc.values())      # 尾差归自耕农
    for k, v in alloc.items():
        nong[k] = max(0, v)
    ding = int(size * _ding_ratio())
    nong[_DING_KEY] = max(0, ding)
    nong[_KOU_KEY] = max(0, size - ding)
    return size


def adjust_farm_slices(p: dict) -> None:
    """`农.size` 变化后，按**现有比例**同步子池（跨类流动/人口增减调用）。

    - 职位：按现有子池比例缩放到新 `size`（保留结构信息，不重置为初值比例）；
    - 丁口：丁率保持 `DING_RATIO`（迁移是"整体人口"移动，不改变户内年龄结构）；
    - 子池缺失或原和 <= 0 → 退回 `seed_farm_slices` 初值分配。
    """
    nong = _nong_of(p)
    if not isinstance(nong, dict):
        return
    size = max(0, int(nong.get("size", 0) or 0))
    old_sum = sum(max(0, int(nong.get(k, 0) or 0)) for k in FARM_POSITIONS)
    if old_sum <= 0:
        seed_farm_slices(p)
        return
    alloc = {k: int(max(0, int(nong.get(k, 0) or 0)) * size / old_sum) for k in FARM_POSITIONS}
    alloc[FARM_POSITIONS[0]] += size - sum(alloc.values())
    for k, v in alloc.items():
        nong[k] = max(0, v)
    ding = int(size * _ding_ratio())
    nong[_DING_KEY] = max(0, ding)
    nong[_KOU_KEY] = max(0, size - ding)


def ensure_farm_slices(state) -> int:
    """逐路**幂等**补齐职位/丁口子池（开局与读档统一入口）。

    返回被修整的路数（0 = 已一致）。**只改子池，不改 `size`/`hidden`**。
    """
    fixed = 0
    for p in (getattr(state, "prefectures", None) or {}).values():
        nong = _nong_of(p)
        if not isinstance(nong, dict):
            continue
        size = max(0, int(nong.get("size", 0) or 0))
        pos_ok = (all(k in nong for k in FARM_POSITIONS)
                  and sum(int(nong.get(k, 0) or 0) for k in FARM_POSITIONS) == size)
        dk_ok = (_DING_KEY in nong and _KOU_KEY in nong
                 and int(nong.get(_DING_KEY, 0) or 0) + int(nong.get(_KOU_KEY, 0) or 0) == size)
        if pos_ok and dk_ok:
            continue
        seed_farm_slices(p)
        fixed += 1
    return fixed


def check_farm_invariants(state) -> List[str]:
    """逐路校验两条恒等式，返回违规描述（空列表 = 全部通过）。"""
    bad: List[str] = []
    for name, p in (getattr(state, "prefectures", None) or {}).items():
        nong = _nong_of(p)
        if not isinstance(nong, dict):
            bad.append(f"{name}: 缺 `农` POP")
            continue
        size = int(nong.get("size", 0) or 0)
        pos = sum(int(nong.get(k, 0) or 0) for k in FARM_POSITIONS)
        ding = int(nong.get(_DING_KEY, 0) or 0)
        kou = int(nong.get(_KOU_KEY, 0) or 0)
        if pos != size:
            bad.append(f"{name}: Σ职位 {pos} != 农.size {size}")
        if ding + kou != size:
            bad.append(f"{name}: 丁+口 {ding + kou} != 农.size {size}")
        if any(int(nong.get(k, 0) or 0) < 0 for k in FARM_POSITIONS + (_DING_KEY, _KOU_KEY)):
            bad.append(f"{name}: 职位/丁口子池出现负数")
    return bad


def ding_of(p: dict) -> int:
    """该路丁数（应役男口）——赋役税基。"""
    nong = _nong_of(p)
    return max(0, int((nong or {}).get(_DING_KEY, 0) or 0))


def kou_of(p: dict) -> int:
    nong = _nong_of(p)
    return max(0, int((nong or {}).get(_KOU_KEY, 0) or 0))
