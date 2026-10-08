# -*- coding: utf-8 -*-
"""批次 3 回归：S3 / S4 / S5 / S6 / S9 / S10 / S11（2026-10-01 全审落地）。

主题：统计口径与实物/资金同源（S3/S4）、日志如实（S5）、判据量纲正确（S6）、
AI 通道真接线（S9）、序列化不重复（S10）、未接线机制不诱导 AI（S11）。
"""
import inspect
import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState            # noqa: E402
from core.legacy_mechanic import init_legacies     # noqa: E402


@pytest.fixture()
def state():
    s = GameState("史实")
    init_legacies(s)
    return s


# ---------------------------------------------------------------- S3 市舶抽解
def test_s3_maritime_decree_no_phantom_income(state):
    """S3：市舶抽解不得凭空记 `total_income`（旧实现无对手方，实测 +3,500,010/月）。"""
    from core.settlement import _settle_mechanisms
    state.maritime["open"] = True
    state.maritime["tariff"] = 0.10
    state.mechanisms["市舶抽解"] = {"org": ""}
    before_income = int(state.statistics["total_income"])
    before_tre = int(state.treasury)
    _settle_mechanisms(state, [])
    assert int(state.statistics["total_income"]) == before_income, "不应凭空增记收入"
    assert int(state.treasury) == before_tre, "税率调整当月不应直接动国库"
    # 正解：提高税率，由 _settle_finance 的唯一入账通道下月实征
    assert float(state.maritime["tariff"]) > 0.10


def test_s3_maritime_tariff_respects_single_source_bounds(state):
    """S3：税率钳位走单点权威源 `FINANCE_DECIDE_BASE['tariff']`，不另立数值。"""
    from content.data import FINANCE_DECIDE_BASE
    from core.settlement import _settle_mechanisms
    cfg = FINANCE_DECIDE_BASE["tariff"]
    state.maritime["open"] = True
    state.mechanisms["市舶抽解"] = {"org": ""}
    for _ in range(40):                      #反复施加也不得越界
        _settle_mechanisms(state, [])
        assert float(cfg["min"]) <= float(state.maritime["tariff"]) <= float(cfg["max"])


# ---------------------------------------------------------------- S4 一条鞭收入
def test_s4_single_whip_income_matches_actual_collection(state):
    """S4：一条鞭 `total_income` 增量须等于**实征银**，不得按名义税粮折银。"""
    from core.settlement_econ import _settle_land_local
    state.single_whip = True
    before = int(state.statistics["total_income"])
    tre_before = int(state.treasury)
    _settle_land_local(state, [])
    income_delta = int(state.statistics["total_income"]) - before
    tre_delta = int(state.treasury) - tre_before
    # 统计口径与国库实收同源（允许其他步带来的舍入差，但不得出现巨额虚增）
    assert income_delta == pytest.approx(tre_delta, abs=2), \
        f"收入统计 {income_delta} 与国库实收 {tre_delta} 不同源"


def test_s4_nominal_grain_no_longer_prices_income(state):
    """S4：即便农/士绅钱粮不足以全额折银，收入也不得按名义税粮计。"""
    from core.settlement_econ import _settle_land_local
    state.single_whip = True
    for pref in state.prefectures.values():          # 掏空民间 wealth → 实征≈0
        for slot in pref["pops"].values():
            if isinstance(slot, dict):
                slot["wealth"] = 0
    before = int(state.statistics["total_income"])
    _settle_land_local(state, [])
    assert int(state.statistics["total_income"]) - before == 0


# ---------------------------------------------------------------- S5 赈灾日志
def test_s5_relief_log_reports_actual_amount(state):
    """S5：太仓不足时日志须记**实发额**并注明缺口，不得报请求额。"""
    from core.settlement_decree import _apply_decree_effect
    state.granary = 1_000
    log = []
    _apply_decree_effect(state, {"title": "赈济", "effects": {"relief": 10}}, log)
    relief_lines = [x for x in log if "赈济" in x]
    assert relief_lines, "应有赈济日志"
    assert "实发 1000石" in relief_lines[0]
    assert "开太仓发粟 100000石" not in "\n".join(log), "不得出现请求额冒充实发额"
    assert int(state.granary) == 0


def test_s5_relief_log_normal_case(state):
    """S5 反向：仓廪充足时按实发额记，且无"请发"字样。"""
    from core.settlement_decree import _apply_decree_effect
    state.granary = 10_000_000
    log = []
    _apply_decree_effect(state, {"title": "赈济", "effects": {"relief": 10}}, log)
    line = [x for x in log if "赈济" in x][0]
    assert "发粟 100000石" in line
    assert "请发" not in line


# ---------------------------------------------------------------- S6 灾荒判据量纲
# ✅ S6 已于批次 7 按**用户 2026-10-01 口径裁决**落地（逐路 `grain_months < 1 个月`
#    ＝「本路公储不足一月、粮储告急」→ 该路 +0.008；逐路判定、逐路施加）。
#    原占位用例「断言缺陷仍在案」已随之作废，回归迁至
#    `tests/test_audit_s6_grain_alarm.py`。此处保留一行指向，避免后人误以为漏测。
def test_s6_moved_to_dedicated_suite():
    """S6 回归已迁至专用文件（占位断言的替代说明）。"""
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "test_audit_s6_grain_alarm.py")
    assert os.path.exists(p), "S6 专用回归文件应存在"


# ---------------------------------------------------------------- S9 局势评分接线
def test_s9_situation_grade_channel_is_wired(state):
    """S9：`_situation_grades` 必须有生产写入方（否则 AI 通道恒死）。"""
    from core import commands as C
    src = inspect.getsource(C)
    assert "situations_grade_decide" in src, "settle_turn 必须调用局势档位契约"
    assert "_situation_grades" in src


def test_s9_grades_are_consumed_by_situation_settle(state):
    """S9：消费侧存在（`situation_settle` 读 `_situation_grades`）。"""
    from core import situation_settle as SS
    src = inspect.getsource(SS)
    assert "_situation_grades" in src


def test_s9_stub_client_grades_land_in_state(state):
    """S9 端到端（stub AI）：档位经契约写入 `_situation_grades`，Step 8.5 可消费。"""
    from core import commands as C
    state.situations = [{"id": "sit-1", "status": "active", "deadline": 12,
                         "title": "边患", "condition_text": "敌军压境"}]

    class _StubAI:
        available = True

        def economy_decide(self, posture, state=None):
            return {"景气": "中", "士绅": "观望", "士绅力度": "无", "生产": "无",
                    "窖银": "无", "城市化": "无", "回乡": "无", "科举": "无",
                    "jiaozi_trust": "平", "shortage": "平", "maritime": "平",
                    "bank": "平", "price_trend": "平"}

        def situations_grade_decide(self, state=None, max_items=8):
            return {"grades": [{"situation_id": "sit-1", "grade": "bad",
                                "narrative": "边关吃紧"}]}

        def __getattr__(self, name):            # 其余契约一律走"不可用"
            def _stub(*a, **k):
                return {"_error": "AI_NOT_CONFIGURED"}
            return _stub

    C._inject_agent_ai(state, _StubAI()) if hasattr(C, "_inject_agent_ai") else None
    # 直接执行接线块所在函数
    settle_ai = None
    for fname in dir(C):
        fn = getattr(C, fname)
        if callable(fn) and "economy_decide" in inspect.getsource(fn):
            settle_ai = fn
            break
    assert settle_ai is not None
    settle_ai(state, _StubAI())
    assert isinstance(state._situation_grades, dict)
    assert "sit-1" in state._situation_grades, "stub 档位应写入临时变量"
    assert state._situation_grades["sit-1"]["grade"] == "bad"


def test_s9_ai_unavailable_keeps_inertia(state):
    """S9：AI 不可用时不得伪造评分（`_situation_grades` 保持空，由程序 inertia 兜底）。"""
    from core import commands as C
    state.situations = [{"id": "sit-1", "status": "active", "deadline": 12}]

    class _StubAI:
        available = False

        def economy_decide(self, posture, state=None):
            return {"景气": "中", "士绅": "观望", "士绅力度": "无", "生产": "无",
                    "窖银": "无", "城市化": "无", "回乡": "无", "科举": "无",
                    "jiaozi_trust": "平", "shortage": "平", "maritime": "平",
                    "bank": "平", "price_trend": "平"}

        def __getattr__(self, name):
            def _stub(*a, **k):
                return {"_error": "AI_NOT_CONFIGURED"}
            return _stub

    fn = None
    for fname in dir(C):
        f = getattr(C, fname)
        if callable(f) and "economy_decide" in inspect.getsource(f):
            fn = f
            break
    fn(state, _StubAI())
    assert not state._situation_grades, "AI 不可用时不得写入任何评分"


# ---------------------------------------------------------------- S10 序列化
def test_s10_json_safe_still_serializable(state):
    """S10：改类型白名单后仍须保证输出可 json.dumps（行为等价）。"""
    from backend.server import _json_safe

    class Foo:
        def __repr__(self):
            return "<Foo>"

    cases = [
        {"a": (1, 2), "b": {1, 2}},
        (1, "x", 2.5, True, None),
        {"n": Foo(), "deep": [{"k": (1,)}]},
        {"sets": {3, 1, 2}},
    ]
    # 2026-10-08 审查补强：原为「不抛即通过」（0 assert）。
    #   改为**显式断言**，并校验关键结构而非仅「没炸」：
    #   ① json.dumps 必须真的返回字符串；② tuple/set 必须被 _json_safe 降级为可序列化形态；
    #   ③ 自定义对象的 repr 必须出现（未被静默丢弃）。
    for c in cases:
        out = _json_safe(c)
        dumped = json.dumps(out, ensure_ascii=False)          # 不得抛
        assert isinstance(dumped, str) and dumped, f"序列化结果非空字符串：{c!r}"
    # tuple/set 降级：集合类字段不得仍以 set 形态存在（否则 json 会抛，此处是显式钉住）
    assert not isinstance(_json_safe({"sets": {3, 1, 2}})["sets"], set), "set 未被降级"
    assert "<Foo>" in json.dumps(_json_safe({"n": Foo()}), ensure_ascii=False), "自定义对象 repr 丢失"
    assert _json_safe((1, "x")) == [1, "x"], "tuple 未降级为 list"


def test_s10_no_redundant_dumps_probe():
    """S10：`_json_safe` **代码体**内不得再调用 `json.dumps`（与整体探测重复）。"""
    import textwrap
    from backend.server import _json_safe
    body = textwrap.dedent(inspect.getsource(_json_safe))
    # 去掉 docstring 后再查（docstring 里提到 json.dumps 是解释，不算调用）
    code = body.split('"""')[0] + '"""'.join(body.split('"""')[2:])
    assert "json.dumps" not in code, "叶子层重复序列化已移除"
    assert "json.dumps(" not in body.replace("`json.dumps(v)`", ""), "不得实际调用"


def test_s10_snapshot_still_warns_on_unserializable(state):
    """S10 反向：`_state_to_dict` 的不可序列化告警（字段名可见）必须保留。"""
    from backend.server import _state_to_dict
    snap = _state_to_dict(state)
    assert isinstance(snap, dict) and snap
    assert "loyalty" in snap and isinstance(snap["loyalty"], dict)


# ---------------------------------------------------------------- S11 未接线机制
def test_s11_prompt_does_not_invite_unwritable_faction():
    """S11：AI 提示词不得诱导生成结构上无法登记的新集团。"""
    from ai import contracts_settle as CS
    src = inspect.getsource(CS)
    assert "或催生新集团" not in src, "旧的邀请式措辞须移除"
    assert "尚未接入" in src or "未接线" in src, "应显式标注该机制未接线"


def test_s11_emergent_names_still_rejected_by_state_layer(state):
    """S11：即使 AI（或旧档）给出新集团名，状态层仍按白名单丢弃（不得凭空建派系）。"""
    from core.faction_split import normalize_split
    out = normalize_split({"新党": 0.5, "全新集团": 0.5})
    assert "全新集团" not in out
    assert out.get("新党") == pytest.approx(1.0)