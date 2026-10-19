# -*- coding: utf-8 -*-
"""质量放行门 · AI 接线一致性（生产者 ⇔ 消费者）。

背景（2026-10-18 用户批准）：曾出现三类「半边接线」——
`_finance_ai` 有生产者无消费者（白烧 token）、`_reform_ai` 有消费者无生产者（永久兜底）、
`_invest_ai` 两头都没有。另有 `_emperor_ai` 属**直接注入**（不经 Agent 注册表）的正例。

本门把「生产者 ⇔ 消费者」做成静态判据，防止运输 `transport_decide` 接线时重犯。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

GAME = Path(__file__).resolve().parents[3] / "game"
sys.path.insert(0, str(GAME))

from application.agent_router import AGENT_DEFS, PENDING_CONTRACTS  # noqa: E402

_CONSUMER_RE = re.compile(r"""getattr\(\s*[^,]+,\s*["\'](_[A-Za-z0-9_]+_ai)["\']""")
_PRODUCER_RE = re.compile(r"""\.(_[A-Za-z0-9_]+_ai)\s*=""")

#: 不走 Agent 注册表、由 commands/初始化**直接注入**的槽位（必须两端都有，且注明理由）
DIRECT_INJECTED = {
    "_emperor_ai": "commands.py 直接注入 emperor_personal_decide → settlement_imperial 消费",
    "_occupation_ai": "diplomacy/regime_intake.py 本地可注入示例/provider 槽，非独立 LLM Agent",
    "_disaster_ai": "events/disaster_tier.py 本地可注入示例/provider 槽，非独立 LLM Agent",
}


def _scan(pattern):
    found = {}
    for base, dirs, files in os.walk(GAME):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "__pycache__")]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = Path(base) / fn
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = p.relative_to(GAME).as_posix()
            for m in pattern.findall(text):
                found.setdefault(m, set()).add(rel)
    return found


def _consumers():
    return set(_scan(_CONSUMER_RE))


def _producers():
    return set(_scan(_PRODUCER_RE))


def _pending_attrs():
    return {row[0] for row in PENDING_CONTRACTS}


def check_pairing(agents, pending, consumers, producers, direct=None):
    """纯函数：返回不一致清单（便于反例自证）。"""
    direct = direct or {}
    issues = []
    attrs = {a.get("settle_attr") for a in agents.values() if a.get("settle_attr")}
    for aid, adef in agents.items():
        attr = adef.get("settle_attr")
        if not attr:
            continue
        if attr not in consumers:
            issues.append(f"[有产无消] {aid}.{attr} 在 core 里无人读取（白烧 token 风险）")
        if adef.get("wired") is False and attr not in pending:
            issues.append(f"[停用未登记] {aid} wired=False 但 {attr} 不在 PENDING_CONTRACTS")
    for attr in consumers:
        if attr not in attrs and attr not in pending and attr not in direct:
            issues.append(f"[有消无产] {attr} 被读取，但既不在 AGENT_DEFS 也不在 PENDING/DIRECT")
    for attr in producers:
        if attr not in attrs and attr not in pending and attr not in direct:
            issues.append(f"[有产无消] {attr} 有生产者，但未登记为 Agent/PENDING/DIRECT")
    for attr, _why in direct.items():
        if attr not in producers or attr not in consumers:
            issues.append(f"[DIRECT 失效] {attr} 登记为直接注入，但生产者/消费者缺失")
    return issues


def test_no_half_wired_slots():
    issues = check_pairing(AGENT_DEFS, _pending_attrs(), _consumers(), _producers(), DIRECT_INJECTED)
    assert not issues, "AI 接线不一致：\n" + "\n".join(issues)


def test_finance_agent_is_disconnected():
    """`_finance_ai` 已断开：不在 AGENT_DEFS、在 PENDING 说明、且不在 token_meter 推演配额。"""
    attrs = {a.get("settle_attr") for a in AGENT_DEFS.values()}
    assert "_finance_ai" not in attrs, "_finance_ai 不应再出现在 AGENT_DEFS"
    assert "_finance_ai" in _pending_attrs(), "_finance_ai 必须在 PENDING_CONTRACTS 登记"
    from ai.token_meter import TOKEN_GROUPS

    _all = set().union(*TOKEN_GROUPS.values())
    assert "finance_decide" not in _all, "finance_decide 仍占 token 配额 ⇒ 断开不彻底"


def test_pairing_check_detects_injected_violations():
    """反例（注入即红）：三种半接线都必须被检出。"""
    agents = {"x": {"settle_attr": "_x_ai", "wired": True}}
    assert any("有产无消" in i for i in check_pairing(agents, set(), set(), {"_x_ai"}))
    assert any("有消无产" in i for i in check_pairing({}, set(), {"_y_ai"}, set()))
    assert any("停用未登记" in i for i in check_pairing(
        {"z": {"settle_attr": "_z_ai", "wired": False}}, set(), {"_z_ai"}, {"_z_ai"}))
    assert any("DIRECT 失效" in i for i in check_pairing({}, set(), set(), set(), {"_q_ai": "x"}))


def test_transport_agent_not_added_before_consumer():
    """若将来把 transport 加入 AGENT_DEFS，core 侧必须已有消费者。"""
    consumers = _consumers()
    for aid, adef in AGENT_DEFS.items():
        if "transport" in aid:
            assert "_transport_ai" in consumers, \
                "transport_decide 无消费者就被登记为 Agent ⇒ 会白烧 token"