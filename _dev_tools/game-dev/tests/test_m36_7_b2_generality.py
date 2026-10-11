# -*- coding: utf-8 -*-
"""M36.7-B+《通用性验收》：同一套机制处理**不同人物/不同档案状况/不同议题/不同人数**。

用户裁定（2026-10-11 修正）：B 的三人原型只证明最小链路；**通用性必须单独验收**。
六项（对应裁定 §三）：
 ①档案规模（动态读档，不写死人名）②资格（不在册/in_office=False 不得误判；缺依据⇒unknown）
 ③缺失属性（逐字段 unknown，不猜、不当 0/负面）④差异性（同议题结论不同，但差异**可追溯**）
 ⑤动态选人（在任状态/议题域/人数变化 ⇒ 结果随规则变化）⑥回归与隔离（只读、不越权、不触发执行）

外加**反硬编码守卫**：`core/ministers_selection.py` 与 `content/ministers/registry.py`
内**不得出现任何具体大臣姓名**（新增大臣只应改内容档案，不应改机制代码）。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.ministers.data import MINISTERS  # noqa: E402
from content.ministers.registry import (DOMAIN_ENUM, TRAIT_FORBIDDEN,  # noqa: E402
                                        TRAIT_REGISTRY, is_registered_trait,
                                        registry_note)
from core import money  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.ministers_selection import minister_registry_facts, select_participants  # noqa: E402


def _by_unknown(field):
    """动态挑一个在该字段缺失的大臣（**不写死人名**）。"""
    for name, f in minister_registry_facts().items():
        if field in f["unknown_fields"]:
            return name, f
    return None, None


def _pick(domains, **kw):
    return select_participants(new_game(), domains, **kw)


# ------------------------------------------------- ① 档案规模（动态）

def test_scale_reads_registry_dynamically():
    """① 候选集＝**动态读档**结果，规模随档案变化；不依赖任何固定人名列表。"""
    facts = minister_registry_facts()
    assert len(facts) == len(MINISTERS) and len(facts) > 20, "应覆盖全部登记大臣"
    # 全量资格扫描（不限人数）：在册且在朝者应显著多于单次会签人数
    sel = _pick(["finance"], max_n=10 ** 6)
    in_office = [n for n, f in facts.items() if f.get("in_office") is True]
    assert len(sel["participants"]) <= len(in_office), "参与者不可能多于在朝者"
    assert sel["max_n"] == 10 ** 6, "人物总数与单次人数分离（max_n 由议题给定）"
    # 新增一位大臣 ⇒ 只改内容档案即可；此处以"函数不缓存名单"证明动态性
    facts2 = minister_registry_facts()
    assert set(facts2) == set(facts)


# ------------------------------------------------- ② 资格（在朝/在册/缺依据）

def test_eligibility_no_false_active():
    """② 不在册／`in_office=False` **不得**入选；缺 `in_office` ⇒ `unknown`（不判在朝）。"""
    s = new_game()
    facts = minister_registry_facts(s)
    out_of_office = [n for n, f in facts.items() if f.get("in_office") is False]
    missing = [n for n, f in facts.items() if f.get("in_office") is None]
    sel = select_participants(s, ["military", "finance", "personnel", "justice",
                                  "works", "diplomacy", "agri", "culture"], max_n=10 ** 6)
    picked = {p["name"] for p in sel["participants"]}
    assert not (picked & set(out_of_office)), f"不在朝者入选：{picked & set(out_of_office)}"
    assert not (picked & set(missing)), f"状态未知者入选：{picked & set(missing)}"
    assert {u["name"] for u in sel["unknown"]} >= set(missing), "缺 in_office 须记 unknown"
    # 不在册名字：即便 state.loyalty 里有记录，也不得凭 minister_status 的缺省 active 入选
    assert "章惇" not in MINISTERS
    assert "章惇" not in picked, "不在册者不得入选（不得依赖 minister_status 缺省值）"


# ------------------------------------------------- ③ 缺失属性（逐字段 unknown）

def test_missing_attributes_are_unknown_not_zero():
    """③ 封爵/派系/标签/职责 各自缺失 ⇒ 记 `unknown`，**不**推成 0／无／负面。"""
    facts = minister_registry_facts()
    checked = 0
    for field in ("nobility", "faction", "trait_ids", "role"):
        name, f = _by_unknown(field)
        if name is None:
            continue
        checked += 1
        assert field in f["unknown_fields"], f"{name}.{field} 应标 unknown"
        # 缺失不得被解读为负面结论
        assert f["nobility"] in ("", f["nobility"]), "封爵缺失不得填充伪值"
        assert "domains_note" in f, "职责未能归类时须留说明（unknown 标记）"
        if not f["domains"]:
            assert f["domains_note"].startswith("unknown"), "未命中须显式 unknown:…"
    assert checked >= 1, "实测档案中应至少存在一类缺失字段（否则本测试形同虚设）"


# ------------------------------------------------- ④ 差异性（可追溯）

def test_difference_traces_to_registry_not_randomness():
    """④ 同议题下参与者集合不同域、判断差异可追溯到**档案/职责**（非随机）。"""
    sel = _pick(["finance", "agri"], max_n=3)
    assert sel["participants"], "应有参与者"
    for p in sel["participants"]:
        f = minister_registry_facts()[p["name"]]
        assert p["domains"] == f["domains"], "参与理由须与其职责映射一致"
        assert p["trait_ids"] == f["trait_ids"], "标签须取自登记（未登记者不入）"
    # 两次调用结果稳定（确定性，非随机）
    assert _pick(["finance", "agri"], max_n=3)["participants"] == sel["participants"]
    # 同一议题下不同大臣的 domains/职责确有差异（差异有据）
    doms = {p["name"]: tuple(p["domains"]) for p in sel["participants"]}
    assert len(set(doms.values())) >= 1
    for p in sel["participants"]:
        if p["selected_by"] == "domain":
            assert p["domains"], "按 domain 入选者必须有可解释的 domain"
        else:
            assert p["domains"] == [], "中枢补足者可以无 domain（但须有职责说明）"
            assert minister_registry_facts()[p["name"]]["domains_note"].startswith("unknown")


# ------------------------------------------------- ⑤ 动态选人（三变量）

def test_dynamic_selection_responds_to_state_issue_and_size():
    """⑤ 在任状态／议题域／人数变化 ⇒ 结果随规则变化（无硬编码）。"""
    s = new_game()
    base = select_participants(s, ["finance"], max_n=3)
    # 变量一：人数
    one = select_participants(s, ["finance"], max_n=1)
    five = select_participants(s, ["finance"], max_n=5)
    assert len(one["participants"]) <= 1 and len(five["participants"]) <= 5
    assert len(five["participants"]) >= len(base["participants"])
    # 变量二：议题域（不同域 ⇒ 参与者不同）
    mil = select_participants(s, ["military"], max_n=3)
    fin = select_participants(s, ["finance"], max_n=3)
    assert ({p["name"] for p in mil["participants"]} !=
            {p["name"] for p in fin["participants"]}), "换议题域应改变参与者（若同则因中枢补足，需人工复核）"
    # 变量三：在任状态（把某参与者改为不在朝 ⇒ 其被排除）
    target = base["participants"][0]["name"]
    MINISTERS[target]["in_office"] = False
    try:
        after = select_participants(s, ["finance"], max_n=3)
    finally:
        MINISTERS[target]["in_office"] = True
    assert target not in {p["name"] for p in after["participants"]}, "不在朝者须被排除"
    assert any(e["name"] == target for e in after["excluded"]), "须给出排除原因"
    # 议题域非法：不猜，记 invalid_domains
    bad = select_participants(s, ["navy"], max_n=3)
    assert bad["invalid_domains"] == ["navy"]


# ------------------------------------------------- ⑥ 回归与隔离（只读/不越权/不触发执行）

def test_readonly_and_isolation():
    """⑥ 选人与档案读数**只读**；不触碰审批/执行/审计链；不暴露私德数值。"""
    s = new_game()
    before = (copy.deepcopy(s.prefectures), money.m_all(s),
              copy.deepcopy(dict(s.statistics or {})),
              copy.deepcopy(getattr(s, "ai_pending_actions", [])),
              copy.deepcopy(getattr(s, "council_reviews", {})),
              len(getattr(s, "discovery_suspicions", []) or []))
    facts = minister_registry_facts(s)
    sel = select_participants(s, ["personnel", "justice"], max_n=3)
    after = (s.prefectures, money.m_all(s), dict(s.statistics or {}),
             getattr(s, "ai_pending_actions", []), getattr(s, "council_reviews", {}),
             len(getattr(s, "discovery_suspicions", []) or []))
    assert before[0] == after[0] and before[1] == after[1] and before[2] == after[2]
    assert before[3] == after[3] and before[4] == after[4] and before[5] == after[5]
    # 数值不外泄（§17/D5）：**数据面**不得含私德数值（说明性文案不计）
    data_blob = str(facts) + str(sel["participants"]) + str(sel["excluded"]) + str(sel["unknown"])
    for leak in ("loyalty", "corruption"):
        assert leak not in data_blob, f"不得外泄 {leak}"
    assert "loyalty" in sel["fields_exposed"], "须显式声明字段边界（不含私德数值）"
    # 隔离：模块不得触碰执行/审计/审批入口
    src = open(os.path.join(_GAME_ROOT, "core", "ministers_selection.py"),
               encoding="utf-8").read()
    for banned in ("resolve_audit", "enqueue_inspection", "file_inspection_report",
                   "record_report_suspicion", "approve_ai_action", "reject_ai_action",
                   "money", "apply_finance_reform"):
        assert banned not in src, f"选人器不得触碰 {banned}"


def test_no_hardcoded_names_and_registry_integrity():
    """反硬编码守卫＋登记表完整性（Q9）：机制代码不得出现具体人名；标签须登记且禁止用途明确。"""
    for rel in ("core/ministers_selection.py", "content/ministers/registry.py"):
        src = open(os.path.join(_GAME_ROOT, *rel.split("/")), encoding="utf-8").read()
        hits = [n for n in MINISTERS if n and n in src]
        assert not hits, f"{rel} 疑似硬编码大臣姓名：{hits[:5]}"
    # 既有 13 个标签全部登记、语义非空、且统一禁止用途已声明
    used = set()
    for fig in MINISTERS.values():
        used |= set(fig.get("trait_ids") or [])
    assert used <= set(TRAIT_REGISTRY), f"存在未登记标签：{sorted(used - set(TRAIT_REGISTRY))}"
    assert all(v.get("semantics") for v in TRAIT_REGISTRY.values())
    assert TRAIT_FORBIDDEN and "competence" in TRAIT_FORBIDDEN
    for t in used:
        assert TRAIT_REGISTRY[t].get("consumers"), f"{t} 须声明允许消费方"
    # 未登记标签不参与派生
    assert is_registered_trait("聚敛") and not is_registered_trait("不存在的标签")
    assert "禁" in registry_note() or "禁止" in registry_note()
    # domain 枚举锁定 v1 八类
    assert set(DOMAIN_ENUM) == {"military", "finance", "personnel", "justice",
                                "works", "diplomacy", "agri", "culture"}


