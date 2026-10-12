# -*- coding: utf-8 -*-
"""M57 「直写路级 pops/镜像」家族**收口哨兵**（长局守卫 + trace）。

背景：本会话共定位并修好 **6 处**同族缺陷（商品折旧 / 产出入 POP / 成品池分派 / 成交钱货 /
外销变现 / 和买取货），全部是「直写路级派生镜像 ⇒ 被 `sync_route_pops` 覆盖」。
本用例把排查固化成**常驻哨兵**：跑长局时开守卫 trace，**任何**直写都会红，并直接报出
`function @ file:line`（不必再手工二分）。

⚠️ 与 `test_route_pops_readonly_guard.py` 的关系：那个文件用 guard 抓"直写"；
本用例**额外**要求 **trace 明细为空**（即"连合法镜像刷新之外的写入都没有"），
并在失败时打印**唯一写入者清单**，把"找写入者"从手工变成自动。
"""

import random

from core import commands
from core.foundation.ledger import pop_bridge as pb

MONTHS_PLAIN = 12
MONTHS_COMBO = 8
SEED = 20261013


def _run(months, mutate=None):
    import core.settlement as S

    random.seed(SEED)
    s = commands.new_game()
    if mutate:
        mutate(s)
    installed = pb.install_all_guards(s)
    assert installed == 20, f"守卫只装上 {installed} 路（应为 20，说明下沉/安装没生效）"
    pb.reset_pops_guard()
    pb._GUARD_TRACE = True                       # 打开写入者定位（默认关）
    for _ in range(months):
        S.run_monthly_settlement(s)
    return pb.pops_guard_violations(), pb.pops_guard_violation_details()


def _writers(details):
    seen = {}
    for d in details:
        key = f"{d.get('function')} @ {str(d.get('file')).split(chr(92))[-1]}:{d.get('line')}"
        seen[key] = seen.get(key, 0) + 1
    return seen


def test_plain_long_run_has_zero_mirror_writes():
    v, details = _run(MONTHS_PLAIN)
    assert v == [], f"朴素长局出现直写：{_writers(details)}"
    assert details == [], f"trace 明细非空：{_writers(details)}"


def test_combo_long_run_has_zero_mirror_writes():
    def _combo(s):
        s.single_whip = True
        s._economy_ai = {"景气": "大", "城市化": "大", "回乡": "无", "科举": "无",
                         "窖银": "大", "士绅": "囤", "士绅力度": "大"}
        for pdata in s.prefectures.values():
            pdata["buildings"] = {"工坊": {"lv": 2}, "商铺": {"lv": 1}}
        _, first = next(iter(s.prefectures.items()))
        for cls, size in (("农", 250_000), ("工匠", 100), ("商人", 100)):
            pb.pop_set(first, cls, "size", size)
        if not isinstance(getattr(s, "maritime", None), dict):
            s.maritime = {}
        s.maritime["open"] = True
        s.maritime["silver_in"] = max(int(s.maritime.get("silver_in", 0) or 0), 10_000_000)

    v, details = _run(MONTHS_COMBO, _combo)
    assert v == [], f"组合长局出现直写：{_writers(details)}"
    assert details == [], f"trace 明细非空：{_writers(details)}"
