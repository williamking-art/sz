# -*- coding: utf-8 -*-
"""阶段 C-7 回归测试：编制参数（§12.3 六杠杆 ＋ §17.4 参数清单 ＋ S-D6 维持费）。

**已拍板决策 3**：不为公务员制做转轨系统 —— 宋代官吏制 ＝ 这组参数的一组取值，
公务员制 ＝ 同一组参数的另一组取值；**改制的本质是"移动参数"**。
因此本文件的验收标准只有一条：**这些参数能被政令改动，并被结算真正消费**。

被断言的缺陷：六个编制杠杆此前**没有任何可改路径**——玩家无法"先定编、再提薪"
（§17.5 的必经路线），公务员化只能靠开发者改代码。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import clerks as ck  # noqa: E402
from core import institution as inst  # noqa: E402
from core import officialdom as od  # noqa: E402
from core.free_effect import _apply_effect_to_state, validate_free_effect  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.settlement_steps import _settle_upkeep  # noqa: E402
from content.data import ASSET_MAINTAIN_RATE, INSTITUTION_PARAM_SPEC  # noqa: E402

_ECO = {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
        "窖银": "小", "城市化": "中", "回乡": "无", "科举": "中"}


def _run(s, months, seed=7):
    from core.settlement import run_monthly_settlement
    for _ in range(months):
        s._economy_ai = _ECO
        run_monthly_settlement(s, seed_offset=seed)
    return s


def _pool_wealth(s, route, keys=("农", "工匠", "商人")):
    p = s.prefectures[route]
    return sum(int(p["pops"][k]["wealth"]) for k in keys)


# ---------------------------------------------------------------- 参数面
def test_defaults_are_identity():
    """默认值必须是**恒等**（不改变既有平衡）：全部等于 SPEC 的 default。"""
    s = GameState("史实")
    cur = inst.all_params(s)
    for k, spec in INSTITUTION_PARAM_SPEC.items():
        assert cur[k] == float(spec["default"]), f"{k} 默认值偏离 SPEC"
    assert inst.changed_count(s) == 0
    # 关键恒等：定员 = 原始口径（乘 1.0 不变）
    od.ensure_quota(s)
    central = sum(len(o.get("posts") or []) for o in s.central_orgs.values()
                  if not o.get("abolished"))
    from content.data import ROUTE_POST_QUOTA
    assert s.posts_quota == central + ROUTE_POST_QUOTA * len(s.prefectures)


def test_params_are_clamped_to_spec_range():
    """值域单点约束：越界值被钳制，未知键被拒绝（不静默落地）。"""
    s = GameState("史实")
    ok, _ = inst.set_param(s, "clerk_pay_mult", 999.0)
    assert ok and inst.get(s, "clerk_pay_mult") == INSTITUTION_PARAM_SPEC["clerk_pay_mult"]["max"]
    ok, _ = inst.set_param(s, "clerk_pay_mult", -5.0)
    assert ok and inst.get(s, "clerk_pay_mult") == INSTITUTION_PARAM_SPEC["clerk_pay_mult"]["min"]
    ok, msg = inst.set_param(s, "not_a_param", 1.0)
    assert not ok and "白名单" in msg


def test_free_effect_accepts_institution_field():
    """`institution` 字段入 free_effect 白名单：合法参数落地，未授权参数**整单拒绝**。"""
    s = GameState("史实")
    err = validate_free_effect({"mode": "once",
                                "effects": {"institution": {"rank_up_mult": "小"}}})
    assert err == "", f"合法编制参数被拒：{err}"
    err = validate_free_effect({"mode": "once",
                                "effects": {"institution": {"teleport": 1}}})
    assert err and "未授权参数" in err, f"未授权参数未被拒：{err!r}"

    # 落地：给个负增量（大幅延长磨勘年限 → 升迁变慢）
    before = inst.get(s, "rank_up_mult")
    _apply_effect_to_state(s, {"institution": {"rank_up_mult": -0.4}})
    assert inst.get(s, "rank_up_mult") < before, "institution 字段未落地"
    # 绝对值写法
    _apply_effect_to_state(s, {"institution": {"clerk_pay_mult": "=2.5"}})
    assert abs(inst.get(s, "clerk_pay_mult") - 2.5) < 1e-9, "绝对值写法未生效"
    # 档位词写法（增量）：往 **下** 调要写负号
    inst.set_param(s, "yinben_mult", 1.0)
    _apply_effect_to_state(s, {"institution": {"yinben_mult": "-中"}})
    assert inst.get(s, "yinben_mult") < 1.0, "档位词增量未生效"
    inst.set_param(s, "yinben_mult", 1.0)
    _apply_effect_to_state(s, {"institution": {"yinben_mult": "小"}})
    assert inst.get(s, "yinben_mult") > 1.0, "正向档位词未生效"


# ---------------------------------------------------------------- 参数被结算真正消费
def test_clerk_pay_mult_reduces_extortion_and_grievance():
    """**§17.5 的必经路线**：提薪（配定编）→ 吏禄充足 → 陋规与吏怨同时下降。"""
    s = GameState("史实")
    ck.ensure_detail(s)
    p = s.prefectures["两浙路"]
    for _ in range(30):
        ck._extort(s, p, [])
    g0 = float(p["clerks_detail"]["grievance"])
    inst.set_param(s, "clerk_pay_mult", 3.0)     # 吏薪 ×3（≈10.5 贯/月，越过 7.2 生计线）
    r = ck._extort(s, p, [])
    assert r["taken"] == 0, f"提薪后仍在取陋规：{r['taken']}"
    for _ in range(80):
        ck._extort(s, p, [])
    assert float(p["clerks_detail"]["grievance"]) < g0, \
        f"提薪后吏怨未回落：{g0:.1f} → {p['clerks_detail']['grievance']:.1f}"


def test_posts_quota_mult_raises_redundancy():
    """**定编是冗官的闸门**：调低定编 → 「在册 − 定编」的差额立刻变大（§12.8）。"""
    s = GameState("史实")
    od.ensure_quota(s)
    r0 = max(0, od.totals(s)["officials"] - s.posts_quota)
    inst.set_param(s, "posts_quota_mult", 0.4)
    od.rescale_quota(s)
    r1 = max(0, od.totals(s)["officials"] - s.posts_quota)
    assert r1 > r0, f"降定编后冗官未上升：{r0} → {r1}"


def test_sinecure_and_retire_params_are_consumed():
    """祠禄比例与考课黜落参数确实被结算消费（不是只存着不用）。"""
    s = GameState("史实")
    # 祠禄：把待阙抬到很高，调大 sinecure_mult 应转出更多祠禄
    for p in s.prefectures.values():
        od.ensure_subpools(p)
        pop = p["pops"]["官僚"]
        pop["waiting"] += 20_000
        pop["officials"] += 20_000
        pop["size"] += 20_000
    od.settle_officialdom(s, [])
    base = od.totals(s)["sinecure"]
    for p in s.prefectures.values():
        pop = p["pops"]["官僚"]
        pop["waiting"] += 20_000
        pop["officials"] += 20_000
        pop["size"] += 20_000
    inst.set_param(s, "sinecure_mult", 3.0)
    od.settle_officialdom(s, [])
    assert od.totals(s)["sinecure"] > base, "祠禄比例参数未被消费"

    # 考课黜落：调大 retire_mult → 年退出人数增加
    s2 = GameState("史实")
    n0 = _retire_count(s2)
    inst.set_param(s2, "retire_mult", 2.5)
    n1 = _retire_count(s2)
    assert n1 > n0, f"考课黜落参数未被消费：{n0} → {n1}"


def _retire_count(s):
    from core.officialdom import _annual_retire
    return _annual_retire(s, [])


def test_asset_maintain_mult_scales_upkeep():
    """**S-D6：玩家主动降维持费**（裁汰冗费）——参数直接乘在维持费率上。"""
    s = GameState("史实")
    s.treasury = 50_000_000
    due_full = _settle_upkeep(s, [])
    assert due_full > 0
    inst.set_param(s, "asset_maintain_mult", 0.5)
    s.treasury = 50_000_000
    due_half = _settle_upkeep(s, [])
    assert abs(due_half - due_full * 0.5) <= 2, f"维持费未按参数缩放：{due_full} → {due_half}"
    inst.set_param(s, "asset_maintain_mult", 0.0)
    s.treasury = 50_000_000
    assert _settle_upkeep(s, []) == 0, "维持费率归零后仍支出"
    assert ASSET_MAINTAIN_RATE > 0, "默认费率常量被改写（应只改参数，不动权威源）"


def test_muster_share_and_hereditary_lower_grip():
    """**禁世袭 ＋ 多用募吏** → 把持度下降（§16.7 的两条政策杠杆）。"""
    s = GameState("史实")
    for _ in range(60):
        _run(s, 1)
    grip0 = ck.totals(s)["grip"]
    inst.set_param(s, "hereditary_mult", 0.0)
    inst.set_param(s, "muster_share", 1.0)
    for _ in range(80):
        _run(s, 1)
    grip1 = ck.totals(s)["grip"]
    assert grip1 < grip0, f"禁世袭/增募吏未降把持度：{grip0:.3f} → {grip1:.3f}"
    # 来源结构被真实写入
    p = next(iter(s.prefectures.values()))
    assert p["clerks_detail"]["source_mix"]["募吏"] == 1.0
    assert p["clerks_detail"]["hereditary"] == 0.0


def test_describe_reports_labels_and_ranges():
    """读数面：每个参数都有中文标签、值域与"是否被改动"标记（面板/AI 直接可用）。"""
    s = GameState("史实")
    inst.set_param(s, "yinben_mult", 0.0)
    d = inst.describe(s)
    assert d["yinben_mult"]["changed"] is True
    assert d["yinben_mult"]["label"] == "荫补之门"
    assert d["posts_quota_mult"]["changed"] is False
    for k, v in d.items():
        assert v["min"] <= v["value"] <= v["max"], f"{k} 读数越界"
    assert inst.changed_count(s) == 1
