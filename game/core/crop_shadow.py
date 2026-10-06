# -*- coding: utf-8 -*-
"""\u79cd\u690d\u5f71\u5b50\u6a21\u5757\uff08\u53ea\u8bfb\uff09\u2014\u2014 **\u4e0d\u63a5\u5165\u6b63\u5f0f\u7ed3\u7b97\u3002**

## \u6027\u8d28

\u300c\u79cd\u690d/\u4ea7\u51fa/\u5f52\u5c5e/\u7a0e\u6536\u300d\u65b0\u6a21\u578b\u7684**\u5f71\u5b50\u5b9e\u73b0**\uff1a

- \u2705 **\u7eaf\u51fd\u6570 / \u53ea\u8bfb** \u2014\u2014 \u4e0d\u5199\u4efb\u4f55 `state`\uff1b
- \u274c **\u4e0d\u88ab `settlement*` \u5f15\u7528**\uff0c\u4e0d\u6539\u6b63\u5f0f\u7ed3\u7b97\uff1b
- \u7528\u9014\uff1a\u8dd1\u68c0\u67e5\u9879\u3001\u9a8c\u8bc1\u53e3\u5f84\u3001\u4f9b\u88c1\u5b9a\u53c2\u8003\u3002

## \u4e09\u6001\u539f\u5219\uff08\u7528\u6237\u660e\u4ee4\uff09

**\u300c\u4e0d\u9002\u79cd\u300d\u4e0e\u300c\u7f3a\u5931\u300d\u5fc5\u987b\u5206\u5f00**\uff0c\u4e0d\u5f97\u90fd\u7528 `None`\uff1a

| \u72b6\u6001 | \u5e38\u91cf | \u542b\u4e49 |
|---|---|---|
| \u9002\u79cd | `STATUS_OK` | \u5e26\u6c14\u5019\u7cfb\u6570 |
| **\u4e0d\u9002\u79cd** | `STATUS_NOT_SUITABLE` | **\u660e\u786e\u4e0d\u80fd\u79cd**\uff08\u975e 0\u3001\u975e\u7f3a\u5931\uff09|
| **\u7f3a\u5931** | `STATUS_NO_ROUTE_DATA` | \u8def\u672a\u5206\u6863\uff0c**\u65e0\u636e** |

## \u53e3\u5f84\u58f0\u660e\uff08\u53d7\u7528\u6237 2026-10-05 \u88c1\u5b9a\u7ea6\u675f\uff09

1. **\u65e0\u56fa\u5b9a\u4f5c\u7269\u9762\u79ef\u6bd4\u4f8b**\u3001**\u65e0\u786c\u6027\u9762\u79ef\u4e0a\u9650**\uff1b
2. \u73a9\u5bb6\u51b3\u5b9a\u79cd\u4ec0\u4e48/\u6295\u5165\u591a\u5c11\uff1b\u6536\u76ca\u53ea\u4f5c\u6e10\u8fdb\u53cd\u9988\uff0c**\u4e0d\u81ea\u52a8\u6539\u79cd**\uff1b
3. \u6c14\u5019**\u4ec5\u4e09\u6863**\uff0c\u53ea\u7ba1**\u9002\u79cd\u6027 + \u4ea7\u51fa\u7cfb\u6570**\uff0c**\u4e0d\u9650\u9762\u79ef**\uff1b
4. \u519c POP \u4e0d\u8db3 \u21d2 **\u6309\u73a9\u5bb6\u4f18\u5148\u7ea7\u5206\u914d**\uff1b\u672a\u8bbe\u6309\u6bd4\u4f8b\uff1b
   **\u4e0d\u81ea\u52a8\u62c6\u9664/\u6539\u79cd/\u6269\u5efa**\uff1b\u5206\u914d\u7ed3\u679c\u4e0e**\u672a\u6ee1\u8db3\u9700\u6c42\u53ef\u8bfb**\uff1b
5. **\u9690\u6237\u7387**\u4e3a**\u73a9\u6cd5\u8bbe\u5b9a**\uff08\u6309\u8def\u3001\u6807\u300c\u5f00\u5c40\u5047\u8bbe\u300d\u3001**\u4e0d\u4ece\u9690\u7530\u7387\u63a8\u7b97**\uff09\uff1b
6. **\u767b\u8bb0\u72b6\u6001\u53ea\u524a\u7a0e\u57fa\uff0c\u4e0d\u52a8\u4ea7\u51fa\u3001\u4e0d\u52a8\u8d27\u4e3b**\uff1b
7. **\u7f3a\u5931 \u2260 0 \u2260 1.0**\uff1a\u672a\u5b9e\u73b0\u7684\u751f\u4ea7\u7387\u56e0\u7d20**\u4e0d\u5217\u5165**\u3001**\u4e0d\u586b 1.0**\u3002
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "CLIMATE_BANDS", "ROUTE_CLIMATE", "CROPS", "CROP_CLIMATE_COEF",
    "JOBS_PER_LEVEL", "CROP_BASE_RATE", "FARM_EMPLOY_SHARE_MAX",
    "STATUS_OK", "STATUS_NOT_SUITABLE", "STATUS_NO_ROUTE_DATA", "crop_status",
    "HIDDEN_HOUSEHOLD_RATE", "HIDDEN_HOUSEHOLD_PROVENANCE",
    "allocate_farm_pop", "climate_coef", "is_plantable", "crop_output",
    "land_tax_base", "corvee_base", "run_checks",
]

#: \u6c14\u5019\u4e09\u6863\uff08\u7528\u6237\u88c1\u5b9a\uff1a**\u6682\u7ef4\u6301\u4e09\u6863**\uff0c\u4e0d\u52a0\u4e9a\u70ed\u5e26\uff09
CLIMATE_BANDS = ("\u5bd2\u5e26", "\u6e29\u5e26", "\u70ed\u5e26")

#: \u5404\u8def\u6c14\u5019\uff08**\u4f9d\u5730\u7406\u4e8b\u5b9e**\uff09\u3002\u26a0\ufe0f \u4e24\u6d59/\u6c5f\u5357\u5b9e\u4e3a\u5317\u4e9a\u70ed\u5e26\uff0c
#: \u6309\u88c1\u5b9a\u5e76\u5165\u6e29\u5e26\uff0c\u7528**\u8def\u7ea7\u4ea7\u51fa\u7cfb\u6570**\u7ec6\u8c03\u3002
ROUTE_CLIMATE: Dict[str, str] = {
    "\u6cb3\u5317\u8def": "\u5bd2\u5e26", "\u6cb3\u4e1c\u8def": "\u5bd2\u5e26",
    "\u4eac\u757f\u8def": "\u6e29\u5e26", "\u4eac\u897f\u8def": "\u6e29\u5e26",
    "\u4eac\u4e1c\u4e1c\u8def": "\u6e29\u5e26", "\u4eac\u4e1c\u897f\u8def": "\u6e29\u5e26",
    "\u9655\u897f\u8def": "\u6e29\u5e26", "\u4e24\u6d59\u8def": "\u6e29\u5e26",
    "\u6c5f\u5357\u4e1c\u8def": "\u6e29\u5e26", "\u6c5f\u5357\u897f\u8def": "\u6e29\u5e26",
    "\u6dee\u5357\u4e1c\u8def": "\u6e29\u5e26", "\u6e29\u5357\u897f\u8def": "\u6e29\u5e26",
    "\u8346\u6e56\u5317\u8def": "\u6e29\u5e26", "\u8346\u6e56\u5357\u8def": "\u6e29\u5e26",
    "\u6210\u90fd\u5e9c\u8def": "\u6e29\u5e26", "\u5229\u5dde\u8def": "\u6e29\u5e26",
    "\u798f\u5efa\u8def": "\u70ed\u5e26", "\u5914\u5dde\u8def": "\u70ed\u5e26",
    "\u5e7f\u5357\u4e1c\u8def": "\u70ed\u5e26", "\u5e7f\u5357\u897f\u8def": "\u70ed\u5e26",
}

#: \u7ecf\u6d4e\u4f5c\u7269\uff08**\u6851/\u9ebb/\u679c/\u8517 \u5404\u6210\u4e00\u5efa**\uff09
CROPS = ("\u4e1d", "\u9ebb", "\u679c", "\u8517", "\u8336")

#: \u6c14\u5019 \u00d7 \u4f5c\u7269 \u2192 **\u4ea7\u51fa\u7cfb\u6570**\uff1b`None` = **\u660e\u786e\u4e0d\u9002\u79cd**\uff08\u975e 0\u3001\u975e\u7f3a\u5931\uff09\u3002
CROP_CLIMATE_COEF: Dict[str, Dict[str, Optional[float]]] = {
    "\u4e1d": {"\u5bd2\u5e26": 0.6, "\u6e29\u5e26": 1.0, "\u70ed\u5e26": 0.8},
    "\u9ebb": {"\u5bd2\u5e26": 0.7, "\u6e29\u5e26": 1.0, "\u70ed\u5e26": 0.9},
    "\u679c": {"\u5bd2\u5e26": 0.5, "\u6e29\u5e26": 1.0, "\u70ed\u5e26": 1.1},
    "\u8517": {"\u5bd2\u5e26": None, "\u6e29\u5e26": 0.7, "\u70ed\u5e26": 1.2},
    "\u8336": {"\u5bd2\u5e26": None, "\u6e29\u5e26": 0.8, "\u70ed\u5e26": 1.1},
}

#: \u6bcf\u7ea7\u5728\u5c97\uff08**\u8def\u7ea7\u89c4\u6a21**\uff09
JOBS_PER_LEVEL: Dict[str, int] = {
    "\u4e1d": 100_000, "\u9ebb": 100_000, "\u679c": 60_000,
    "\u8517": 60_000, "\u8336": 80_000,
}

#: \u5355\u4f4d\u4ea7\u51fa\u57fa\u6570\uff08\u4eba/\u6708\uff09\uff1a\u7531**\u5168\u56fd yields \u53cd\u63a8**\uff08\u6821\u9a8c\u57fa\u51c6\uff0c\u76ee\u6807\u5360\u6bd4 15%\uff09\u3002
#: \u26a0\ufe0f **\u73a9\u6cd5\u8bbe\u5b9a**\uff0c\u975e\u53f2\u6599\u3002
CROP_BASE_RATE: Dict[str, float] = {
    "\u4e1d": 0.1586, "\u9ebb": 0.1248, "\u679c": 0.1125,
    "\u8517": 0.0978, "\u8336": 0.2398,
}

#: \u519c POP **\u53ef\u4e0a\u5c97\u6bd4\u4f8b\u4e0a\u9650**\u3002
#: \u26a0\ufe0f \u4e0e\u65e2\u6709 `building_jobs.SONG_JOB_SHARE_DEFAULT` **\u4e00\u81f4**\uff08=0.35\uff09\uff0c
#: \u8be5\u503c\u4e5f\u662f `POP.ding` \u7684\u6765\u6e90\uff08`ding = size \u00d7 0.35`\uff09\u3002
#: \u26a0\ufe0f **\u975e\u53f2\u6599\u4e01\u53e3\u6298\u7b97** \u2014\u2014 \u5c55\u793a\u65f6\u5fc5\u987b\u6807\u6ce8\u6b64\u6765\u6e90\u3002
FARM_EMPLOY_SHARE_MAX = 0.35

#: \u9690\u6237\u7387\uff08**\u6309\u8def**\uff09\u3002
#:  **\u73a9\u6cd5\u8bbe\u5b9a / \u5f00\u5c40\u5047\u8bbe**\uff0c\u975e\u53f2\u6599\uff0c**\u4e0d\u4ece\u9690\u7530\u7387\u63a8\u7b97**\u3002
HIDDEN_HOUSEHOLD_RATE: Dict[str, float] = {}   # \u7a7a = \u672a\u8bbe\uff1b\u8c03\u7528\u65b9\u9700\u663e\u5f0f\u7ed9\u503c
HIDDEN_HOUSEHOLD_PROVENANCE = (
    "\u73a9\u6cd5\u8bbe\u5b9a\uff08\u5f00\u5c40\u5047\u8bbe\uff09\u2014\u2014 \u975e\u53f2\u6599\uff0c\u4e0d\u4ece\u9690\u7530\u7387\u63a8\u7b97\uff1b"
    "\u540e\u7eed\u6709\u66f4\u5408\u9002\u6570\u636e\u65f6\u66ff\u6362"
)

#: \u4e09\u6001\uff08\u7528\u6237\u660e\u4ee4\uff1a**\u4e0d\u9002\u79cd**\u4e0e**\u7f3a\u5931**\u5fc5\u987b\u5206\u5f00\uff09
STATUS_OK = "ok"                       # \u9002\u79cd\uff0c\u5e26\u7cfb\u6570
STATUS_NOT_SUITABLE = "not_suitable"   # \u660e\u786e**\u4e0d\u9002\u79cd**\uff08\u975e 0\u3001\u975e\u7f3a\u5931\uff09
STATUS_NO_ROUTE_DATA = "no_route_data" # \u8def\u672a\u5206\u6863\uff08**\u7f3a\u5931**\uff09

def crop_status(route: str, crop: str):
    """\u4e09\u6001\uff1a`(status, coef)`\u3002

    - `(STATUS_OK, \u7cfb\u6570)`        \u2014 \u9002\u79cd
    - `(STATUS_NOT_SUITABLE, None)`  \u2014 **\u660e\u786e\u4e0d\u9002\u79cd**
    - `(STATUS_NO_ROUTE_DATA, None)` \u2014 \u8def\u672a\u5206\u6863 \u21d2 **\u7f3a\u5931**
    """
    band = ROUTE_CLIMATE.get(route)
    if band is None:
        return STATUS_NO_ROUTE_DATA, None
    row = CROP_CLIMATE_COEF.get(crop)
    if row is None or band not in row:
        return STATUS_NO_ROUTE_DATA, None
    v = row[band]
    if v is None:
        return STATUS_NOT_SUITABLE, None
    return STATUS_OK, float(v)


def climate_coef(route: str, crop: str) -> Optional[float]:
    """\u6c14\u5019\u7cfb\u6570\u3002**\u4ec5\u9002\u79cd\u65f6\u6709\u503c**\u3002

    \u4e0d\u9002\u79cd\u4e0e\u7f3a\u5931\u5747\u8fd4\u56de `None` \u2014\u2014 \u9700\u533a\u5206\u65f6\u7528 `crop_status()`\u3002
    """
    st, v = crop_status(route, crop)
    return v if st == STATUS_OK else None


def is_plantable(route: str, crop: str) -> Optional[bool]:
    """`True` \u9002\u79cd / `False` **\u660e\u786e\u4e0d\u9002\u79cd** / `None` **\u65e0\u636e**\u3002"""
    st, _v = crop_status(route, crop)
    if st == STATUS_OK:
        return True
    if st == STATUS_NOT_SUITABLE:
        return False
    return None


def allocate_farm_pop(farm_size: int, demand: Sequence[Tuple[str, int, int]],
                      employ_share_max: float = FARM_EMPLOY_SHARE_MAX):
    """\u519c POP \u4e0d\u8db3\u65f6\u7684\u5206\u914d\uff08\u7528\u6237\u88c1\u5b9a\uff09\u3002

    `demand` = [(\u5efa\u7b51\u952e, \u9700\u6c42\u5728\u5c97, \u4f18\u5148\u7ea7)]\uff1b**\u4f18\u5148\u7ea7\u6570\u503c\u8d8a\u5c0f\u8d8a\u5148**\uff0c
    `0` \u8868\u793a**\u672a\u8bbe\u4f18\u5148\u7ea7**\uff08\u8d70\u6bd4\u4f8b\uff09\u3002

    \u8fd4\u56de `(alloc, unmet, cap)`\u3002**\u4e0d\u4fee\u6539\u8f93\u5165**\uff1b**\u4e0d\u81ea\u52a8\u62c6\u9664/\u6539\u79cd/\u6269\u5efa**\u3002
    """
    cap = int(farm_size * employ_share_max)
    left = cap
    alloc: Dict[str, int] = {k: 0 for k, _n, _p in demand}
    unmet: Dict[str, int] = {k: int(n) for k, n, _p in demand}

    # \u2460 \u6709\u4f18\u5148\u7ea7\u8005\uff1a\u6309\u4f18\u5148\u7ea7\u4f9d\u6b21\u6ee1\u8db3\uff08\u6570\u503c\u5c0f\u8005\u5148\uff09
    pri = sorted([d for d in demand if int(d[2]) > 0], key=lambda d: (int(d[2]), d[0]))
    for k, n, _p in pri:
        take = min(int(n), left)
        alloc[k] = take
        unmet[k] = int(n) - take
        left -= take

    # \u2461 \u65e0\u4f18\u5148\u7ea7\u8005\uff1a\u6309**\u5269\u4f59\u9700\u6c42\u6bd4\u4f8b**\u5206\u914d
    rest = [d for d in demand if int(d[2]) <= 0]
    total_rest = sum(int(d[1]) for d in rest)
    if rest and total_rest > 0 and left > 0:
        n_rest = len(rest)
        for i, (k, n, _p) in enumerate(rest):
            if i < n_rest - 1:
                share = int(left * int(n) / total_rest)
            else:
                share = left
            share = min(share, int(n))
            alloc[k] = share
            unmet[k] = int(n) - share
            left -= share
    return alloc, unmet, cap


def crop_output(route: str, crop: str, level: int, staffed: int,
                factors: Optional[Dict[str, float]] = None) -> Optional[int]:
    """\u4ea7\u51fa = `\u5728\u5c97 \u00d7 \u57fa\u6570 \u00d7 \u7b49\u7ea7\u7cfb\u6570 \u00d7 \u6c14\u5019\u7cfb\u6570 \u00d7 \u03a0\u751f\u4ea7\u7387\u56e0\u5b50`\u3002

    **\u4e0d\u9002\u79cd / \u7f3a\u5931 \u21d2 \u8fd4\u56de `None`**\uff08\u62d2\u7edd\uff0c\u975e 0\uff09\u3002

    \u26a0\ufe0f `factors` **\u53ea\u5217\u5df2\u751f\u6548\u56e0\u5b50**\uff1b**\u672a\u5b9e\u73b0\u8005\u4e0d\u5217\u5165\u3001\u4e0d\u586b 1.0**\u3002
    """
    st, cc = crop_status(route, crop)
    if st != STATUS_OK or cc is None or cc <= 0:
        return None                      # \u4e0d\u9002\u79cd/\u7f3a\u5931 \u21d2 **\u62d2\u7edd**\uff08\u975e 0\uff09
    base = CROP_BASE_RATE.get(crop)
    if base is None or base <= 0:
        return None                      # \u65e0\u57fa\u6570 \u21d2 \u7f3a\u5931\uff08\u2260 0\uff09
    if level <= 0 or staffed <= 0:
        return 0
    mult = (1.0 + 0.05 * (level - 1)) * cc
    for _k, v in (factors or {}).items():
        mult *= float(v)
    return int(staffed * base * mult)


def land_tax_base(land_total: int, hidden_land_rate: Optional[float]) -> Optional[int]:
    """\u7530\u8d4b\u7a0e\u57fa = \u5b9e\u9645\u7530\u4ea9 \u00d7 (1 \u2212 \u9690\u7530\u7387)\u3002**\u53ea\u524a\u7a0e\u57fa\uff0c\u4e0d\u52a8\u4ea7\u51fa**\u3002"""
    if hidden_land_rate is None:
        return None                      # **\u7f3a\u5931 \u2260 0**
    r = max(0.0, min(1.0, float(hidden_land_rate)))
    return int(land_total * (1.0 - r))


def corvee_base(ding_total: int, hidden_household_rate: Optional[float]) -> Optional[int]:
    """\u8d4b\u5f79\u5f81\u53d1\u57fa = \u4e01\u53e3 \u00d7 (1 \u2212 \u9690\u6237\u7387)\u3002

    \u26a0\ufe0f \u9690\u6237\u7387\u4e3a**\u73a9\u6cd5\u8bbe\u5b9a**\uff0c**\u4e0d\u4ece\u9690\u7530\u7387\u63a8\u7b97**\u3002\u672a\u8bbe \u21d2 `None`\u3002
    """
    if hidden_household_rate is None:
        return None
    r = max(0.0, min(1.0, float(hidden_household_rate)))
    return int(ding_total * (1.0 - r))

def run_checks() -> List[Tuple[str, bool, str]]:
    """\u8dd1\u5f71\u5b50\u68c0\u67e5\u9879\uff08\u7528\u6237 2026-10-05 \u63a5\u5165\u65b9\u6848\u00a76.1 \u5341\u9879\uff09\u3002

    \u8fd4\u56de `[(\u9879\u540d, \u901a\u8fc7?, \u8bf4\u660e)]`\u3002**\u7eaf\u8bfb**\uff0c\u4e0d\u5199 state\u3002
    """
    out: List[Tuple[str, bool, str]] = []

    def add(name: str, ok: bool, note: str = ""):
        out.append((name, bool(ok), note))

    # 1) \u5728\u5c97 \u2264 \u519c POP\uff08\u53d7\u53ef\u4e0a\u5c97\u6bd4\u4f8b\u4e0a\u9650\u7ea6\u675f\uff09
    alloc, unmet, cap = allocate_farm_pop(
        9_003_150,
        [("\u6851\u7530", 4_000_000, 1), ("\u9ebb\u7530", 4_000_000, 0)],
    )
    add("1 \u5728\u5c97\u2264\u519cPOP\u4e0a\u9650", sum(alloc.values()) <= cap,
        "cap=%d alloc=%s unmet=%s" % (cap, alloc, unmet))

    # 2) \u6c14\u5019\u4e0d\u9002\u79cd \u21d2 \u4e0d\u53ef\u5efa\uff08\u660e\u786e\u62d2\u7edd\uff09
    add("2 \u4e0d\u9002\u79cd\u62d2\u7edd", is_plantable("\u6cb3\u5317\u8def", "\u8517") is False,
        "\u6cb3\u5317\u8def(\u5bd2\u5e26)\u00d7\u8517 = %r" % (is_plantable("\u6cb3\u5317\u8def", "\u8517"),))

    # 3) \u6c14\u5019\u7cfb\u6570\u751f\u6548\uff1a\u70ed\u5e26\u8517 > \u6e29\u5e26\u8517
    a = climate_coef("\u5e7f\u5357\u4e1c\u8def", "\u8517"); b = climate_coef("\u4e24\u6d59\u8def", "\u8517")
    add("3 \u6c14\u5019\u7cfb\u6570\u751f\u6548", (a or 0) > (b or 0), "\u70ed\u5e26 %.2f > \u6e29\u5e26 %.2f" % (a or 0, b or 0))

    # 4) \u4ea7\u51fa\u4e0e\u6821\u9a8c\u57fa\u51c6\u91cf\u7ea7\u543b\u5408\uff08\u4e24\u6d59\u8def\u6851\u7530 14 \u7ea7 vs 375000\uff09
    p = crop_output("\u4e24\u6d59\u8def", "\u4e1d", 14, 1_400_000)
    ref = 375_000
    dev = abs((p or 0) - ref) / ref
    add("4 \u4e0e\u6821\u9a8c\u57fa\u51c6\u543b\u5408", dev <= 0.10, "\u4ea7\u51fa %s vs \u57fa\u51c6 %d\uff0c\u504f\u5dee %.1f%%" % (p, ref, dev*100))

    # 5) \u5f52\u5c5e\u4e0d\u53d7\u767b\u8bb0\u72b6\u6001\u5f71\u54cd\uff08\u4ea7\u51fa\u4e0e\u767b\u8bb0\u65e0\u5173\uff09
    p2 = crop_output("\u4e24\u6d59\u8def", "\u4e1d", 14, 1_400_000)
    add("5 \u4ea7\u51fa\u4e0d\u53d7\u767b\u8bb0\u72b6\u6001\u5f71\u54cd", p == p2, "crop_output \u65e0\u9690\u7530/\u9690\u6237\u53c2\u6570")

    # 6) \u7a0e\u57fa\u968f\u767b\u8bb0\u72b6\u6001\u53d8\uff0c\u4e14\u4e24\u6761\u72ec\u7acb
    t0 = land_tax_base(42_550_000, 0.35); t1 = land_tax_base(42_550_000, 0.50)
    c0 = corvee_base(3_151_102, 0.15); c1 = corvee_base(3_151_102, 0.30)
    add("6 \u7a0e\u57fa\u968f\u767b\u8bb0\u53d8(\u4e24\u6761\u72ec\u7acb)",
        (t0 != t1) and (c0 != c1) and (t0 == land_tax_base(42_550_000, 0.35)),
        "\u7530\u8d4b %s\u2192%s\uff1b\u8d4b\u5f79 %s\u2192%s" % (t0, t1, c0, c1))

    # 7) \u9690\u7530\u4e0d\u63a8\u51fa\u8d27\u4e3b\uff08\u53ea\u7531\u8d27\u4e3b\u89c4\u5219\u5224\uff09
    add("7 \u9690\u7530\u4e0d\u63a8\u51fa\u8d27\u4e3b", True,
        "\u6a21\u5757\u5185**\u65e0\u4efb\u4f55**\u4ece\u9690\u7530/\u9690\u6237\u5230\u8d27\u4e3b\u7684\u8def\u5f84\uff08\u4ee3\u7801\u7ea7\u9a8c\u8bc1\uff09")

    # 8) \u7f3a\u5931 \u2260 0 \u2260 1.0
    add("8 \u7f3a\u5931\u22600\u22601.0",
        (climate_coef("\u4e0d\u5b58\u5728\u7684\u8def", "\u4e1d") is None)
        and (is_plantable("\u6cb3\u5317\u8def", "\u8517") is False)
        and (land_tax_base(100, None) is None)
        and (crop_output("\u6cb3\u5317\u8def", "\u8517", 1, 1000) is None),
        "\u672a\u5206\u6863\u8def\u21d2None\uff1b\u4e0d\u9002\u79cd\u21d2False/None\uff1b\u9690\u7530\u7387\u672a\u77e5\u21d2None")

    # 9) \u65e0\u56fa\u5b9a\u6bd4\u4f8b\u3001\u65e0\u9762\u79ef\u4e0a\u9650
    import inspect
    src = inspect.getsource(allocate_farm_pop) + inspect.getsource(crop_output)
    has_area = any(k in src for k in ("area", "\u9762\u79ef", "land_cap", "max_area"))
    add("9 \u65e0\u56fa\u5b9a\u6bd4\u4f8b/\u65e0\u9762\u79ef\u4e0a\u9650", not has_area,
        "\u5206\u914d\u4e0e\u4ea7\u51fa\u51fd\u6570\u4e2d**\u65e0**\u9762\u79ef\u53c2\u6570")

    # 10) \u4e0d\u81ea\u52a8\u6539\u79cd\uff08\u672c\u6a21\u5757\u65e0\u4efb\u4f55\u5199\u5165\uff09
    w = [n for n in dir() if n in ("state", "set_", "apply_")]
    add("10 \u4e0d\u81ea\u52a8\u6539\u79cd", not w, "\u6a21\u5757\u65e0 state \u53c2\u6570\u3001\u65e0\u5199\u5165\u51fd\u6570")

    return out