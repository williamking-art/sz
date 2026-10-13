# -*- coding: utf-8 -*-
"""M61 盲区补齐：**后端动作路径**守望（`LocalBackend.action` 分派表）。

背景：M57 的家族哨兵只覆盖 `run_monthly_settlement`，M59 补了**读档往返**，并如实写明
最后一个盲区是**后端动作路径**（`/api/action` → `backend/client.py::LocalBackend.action` 的分派表）。
本用例把该盲区补上：装守卫 + trace 后**逐个派发代表动作**，再跑一月结算，断言
**0 违规、trace 明细为空**。发现新写入者时，失败信息会直接给出 `function @ file:line`。

⚠️ 诚实边界：本用例驱动的是 **LocalBackend（进程内）** 的分派表——`HttpBackend` 只是把同一
`action` 名转成 `/api/action` 请求、由服务端调用**同一套 `core.commands`**，故写点集合相同；
但**并未**真的起 HTTP 服务做端到端验证（那需要 dev server，本机不保证）。
"""

import random

from core import commands
from core.foundation.ledger import pop_bridge as pb

SEED = 20261013

#: 代表动作（**按分派表核过 payload 取值**；空 payload 走各自默认/校验路径）
ACTIONS = (
    "issue_decree",
    "allocate_payraise",
    "do_personal_action",
    "choose_imperial_action",
    "start_tech_research",
    "unlock_focus",
    "start_focus",
    "cancel_focus",
    "issue_military_order",
    "approve_ai_action",
    "reject_ai_action",
    "issue_task_decree",
    "issue_kouyu",
    "merge_drafts",
    "envoy_diplomacy",
)


def _writers(details):
    return sorted({f"{d.get('function')} @ {str(d.get('file')).split(chr(92))[-1]}:{d.get('line')}"
                   for d in details})


def test_backend_action_path_has_zero_mirror_writes():
    import core.settlement as S
    from backend.client import LocalBackend

    random.seed(SEED)
    lb = LocalBackend()
    s = commands.new_game()
    assert pb.install_all_guards(s) == 20, "守卫未装上（应为 20 路）"
    pb.reset_pops_guard()
    pb._GUARD_TRACE = True

    dispatched = 0
    for name in ACTIONS:
        try:
            lb.action(s, name, {}, None)          # 空 payload ⇒ 走默认/校验路径
            dispatched += 1
        except Exception:                          # noqa: BLE001
            # 动作因缺参数而拒绝是**预期**的（本用例只关心"有没有直写"）
            pass
    assert dispatched > 0, "一个动作都没派发成功（分派表/签名变了？）"

    # 动作之后再跑一月结算（动作可能留下待结算状态）
    S.run_monthly_settlement(s)

    details = pb.pops_guard_violation_details()
    assert pb.pops_guard_violations() == [], f"后端动作路径出现直写：{_writers(details)}"
    assert details == [], f"后端动作路径 trace 明细非空：{_writers(details)}"
