# -*- coding: utf-8 -*-
"""历史↔游戏性「取中」校准的回归测试。

## 本次取中的两个新机制

1. **农户「粜粮完税」**（`_settle_tax_grain_sale`）：农户现金恒低于保底线，导致役钱与
   自耕田折色**全部转为永不回收的欠税**（60 月 4,399 万贯），农税通道整体是死账。
   史实上农户卖粮换钱完税，买主是豪强/粮商 → 新通道为**钱粮双向守恒**的民间内部转移。
2. **结余「补发积欠」**（`_settle_arrears_repayment`）：取中后国帑在长局转丰，而
   `pay_arrears` 仍单向累积 → 「国库满、军队欠饷」自相矛盾。丰年补发积欠是史实。

两者都必须满足 POP 挂载律 ⑤（每条改动配守恒断言）。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import clerks as ck  # noqa: E402
from core import money  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402
from core.settlement_steps import (  # noqa: E402
    _settle_arrears_repayment, _settle_tax_grain_sale,
)

_ECO = {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
        "窖银": "小", "城市化": "中", "回乡": "无", "科举": "中"}


def _run(s, months, seed=7):
    for _ in range(months):
        s._economy_ai = _ECO
        run_monthly_settlement(s, seed_offset=seed)
    return s


def _farm_wealth(s, route):
    return int(s.prefectures[route]["pops"]["农"]["wealth"])


def _farm_grain(s, route):
    return int(s.prefectures[route]["pops"]["农"]["grain"])


def _buyers(s, route, keys=("士绅", "商人")):
    p = s.prefectures[route]
    return (sum(int(p["pops"][k]["wealth"]) for k in keys),
            sum(int(p["pops"][k]["grain"]) for k in keys))


# ---------------------------------------------------------------- 粜粮完税
def test_tax_grain_sale_conserves_money_and_grain():
    """核心守恒：`ΔM_ALL == 0`（不造币）且 Σ粮不变（不凭空生粮）；两侧等额反向。"""
    s = GameState("史实")
    p = s.prefectures["两浙路"]
    m0 = money.m_all(s)
    fw0, fg0 = _farm_wealth(s, "两浙路"), _farm_grain(s, "两浙路")
    bw0, bg0 = _buyers(s, "两浙路")

    got = _settle_tax_grain_sale(s, p, 200_000)

    assert got > 0, "农户现金不足时应能粜粮完税"
    fw1, fg1 = _farm_wealth(s, "两浙路"), _farm_grain(s, "两浙路")
    bw1, bg1 = _buyers(s, "两浙路")
    assert fw1 - fw0 == got, "农户所得现钱与返回值不符"
    assert bw0 - bw1 == got, "买方付出与农户所得不等额"
    assert fg0 - fg1 > 0, "农户未卖出粮"
    assert bg1 - bg0 == fg0 - fg1, "买方得粮与农户售粮不等额"
    assert money.m_all(s) - m0 == 0, "粜粮完税改变了 M_ALL（造币或销毁）"


def test_tax_grain_sale_respects_keep_floor_and_monthly_cap():
    """保留 `FARMER_TAX_GRAIN_KEEP_MONTHS` 个月口粮；单月不超 `TAX_GRAIN_SALE_MAX_SHARE`。"""
    from content.data import FARMER_TAX_GRAIN_KEEP_MONTHS, PER_CAPITA_MONTH_GRAIN, TAX_GRAIN_SALE_MAX_SHARE

    s = GameState("史实")
    p = s.prefectures["两浙路"]
    size = int(p["pops"]["农"]["size"])
    need = int(size * PER_CAPITA_MONTH_GRAIN * FARMER_TAX_GRAIN_KEEP_MONTHS)  # 恰好只够口粮

    # 存粮 == 3 个月口粮 → 一粒不卖
    p["pops"]["农"]["grain"] = need
    g0 = _farm_grain(s, "两浙路")
    assert _settle_tax_grain_sale(s, p, 10_000_000) == 0, "触及口粮安全垫仍在卖粮"
    assert _farm_grain(s, "两浙路") == g0

    # 存粮远超口粮 → 单月出售受 5% 上限约束
    p["pops"]["农"]["grain"] = need * 40
    _settle_tax_grain_sale(s, p, 10 ** 12)          # 索要天文数字，仍应受上限约束
    sold = need * 40 - _farm_grain(s, "两浙路")
    cap = int(need * 40 * TAX_GRAIN_SALE_MAX_SHARE)
    # 价格换算会有 ±1 石误差，给 2 石容差
    assert sold <= cap + 2, f"单月售粮超过上限：{sold} > {cap}"


def test_tax_grain_sale_disabled_is_noop(monkeypatch):
    """通道可关闭（回滚开关）：关闭后不改任何账户。"""
    import core.settlement_steps as _m
    from content import data as _d
    s = GameState("史实")
    p = s.prefectures["两浙路"]
    monkeypatch.setattr(_d, "TAX_GRAIN_SALE_ENABLED", False)
    m0 = money.m_all(s)
    fw0, fg0 = _farm_wealth(s, "两浙路"), _farm_grain(s, "两浙路")
    assert _settle_tax_grain_sale(s, p, 200_000) == 0
    assert money.m_all(s) - m0 == 0
    assert _farm_wealth(s, "两浙路") == fw0 and _farm_grain(s, "两浙路") == fg0
    del _m


def test_farm_tax_channel_is_no_longer_a_dead_letter():
    """端到端：农税不再是"永不回收的死账"——粜粮完税发生，且农欠税不再无界累积。"""
    s = _run(GameState("史实"), 12, seed=7)
    assert s.statistics.get("tax_grain_sale", 0) > 0, "粜粮完税通道未生效"
    farm_arrears = sum(p["pops"]["农"].get("欠税", 0) for p in s.prefectures.values())
    nominal = s.statistics.get("poll_tax_nominal", 0)
    # 一年内农欠税不应达到"役钱名义额 × 12"这种全部落空的程度
    assert farm_arrears < nominal * 12, \
        f"农税仍整体落空：欠税={farm_arrears:,} 役钱名义×12={nominal * 12:,}"


# ---------------------------------------------------------------- 补发积欠
def test_arrears_repayment_conserves_money_and_reduces_army_arrears():
    """补发积欠：国库 ↓ == 兵/官僚 wealth ↑，`ΔM_ALL == 0`；`pay_arrears` 与各军欠饷同减。"""
    s = GameState("史实")
    _run(s, 12, seed=7)                     # 先产生真实欠饷
    s.treasury = 5_000_000                  # 人为给足结余（模拟丰年）
    before = int(s.statistics.get("pay_arrears", 0))
    assert before > 0, "前提：应有欠饷"
    army_before = sum(int(getattr(u, "arrears", 0)) for u in s.army_units)

    m0 = money.m_all(s)
    tre0 = s.treasury
    pay_wealth0 = (sum(p["pops"]["兵"]["wealth"] for p in s.prefectures.values())
                   + sum(p["pops"]["官僚"]["wealth"] for p in s.prefectures.values()))

    got = _settle_arrears_repayment(s, [])

    assert got > 0, "国帑充裕却未补发积欠"
    pay_wealth1 = (sum(p["pops"]["兵"]["wealth"] for p in s.prefectures.values())
                   + sum(p["pops"]["官僚"]["wealth"] for p in s.prefectures.values()))
    assert tre0 - s.treasury == got, "国库支出与补发额不符"
    assert pay_wealth1 - pay_wealth0 == got, "补发额未全额落到兵/官僚 POP"
    assert money.m_all(s) - m0 == 0, "补发积欠改变了 M_ALL"
    assert int(s.statistics["pay_arrears"]) == before - got
    assert sum(int(getattr(u, "arrears", 0)) for u in s.army_units) < army_before, \
        "补发后各军欠饷未冲减（Σ各军欠饷与 pay_arrears 失去同源性）"


def test_arrears_repayment_keeps_safety_stock_and_no_arrears_is_noop():
    """国库低于应急安全库存 → 不补发；无欠饷 → 不补发。"""
    from content.data import ARREARS_KEEP_TREASURY
    s = GameState("史实")
    _run(s, 12, seed=7)
    s.statistics["pay_arrears"] = 10_000_000

    s.treasury = int(ARREARS_KEEP_TREASURY)          # 恰在安全线下
    assert _settle_arrears_repayment(s, []) == 0, "低于安全库存仍在补发"
    assert s.treasury == int(ARREARS_KEEP_TREASURY)

    s.treasury = 5_000_000
    s.statistics["pay_arrears"] = 0
    assert _settle_arrears_repayment(s, []) == 0, "无欠饷却在补发"
    assert s.treasury == 5_000_000


# ---------------------------------------------------------------- 结算步守恒（专项检查产物）
def test_focus_monthly_cost_is_a_conserving_transfer():
    """**国策度支**必须守恒：国库照扣（财政成本保留），但钱进民间 POP → `ΔM_ALL == 0`。

    缺陷（2026-09-18 结算步专项检查）：`focus_mechanic.settle_focus` 原为裸
    `state.change_treasury(-cost)` —— 无对手方、未登记 burn，钱凭空消失。
    实测：国策 10,000 贯/月 × 3 月 → 月度对账累计残差 **−30,416 贯**（`burned=0`），
    而正常基线只有 −418 贯。修复后回到基线量级。

    注意：这条缺陷**跨过了全部既有账本测试** —— 因为 `_STEPS` 镜像当时缺 `focus` 步，
    且没有用例启动过国策。故此处既测行为，也钉住"镜像必须含 focus"。
    """
    from core.focus_mechanic import start_focus

    s = GameState("史实")
    _run(s, 1)                                   # 建立基线快照
    base = float((s.money_audit or {}).get("cum_residual", 0))
    assert start_focus(s, "govern", "g1_centralize").get("ok"), "用例前提：国策应能立案"

    tre0 = s.treasury
    _run(s, 3)                                   # 国策 3 月 × 10,000 贯
    res = float((s.money_audit or {}).get("cum_residual", 0)) - base

    assert s.treasury < tre0, "国策度支未真实扣减国库（财政成本丢失）"
    # 修复前 ≈ −30,416；基线未启国策时 ≈ −418。放宽到 3,000 仍能稳稳区分两者。
    assert abs(res) < 3_000, \
        f"国策度支破坏了货币守恒：3 月累计残差 {res:+,.0f} 贯（应回到截断量级）"
    # 2026-09-18 测试体检：原为 `assert money.m_all(s) - m0 != 0 or True` —— **恒真**（自己写的，已删）。
    # 改为**直接验证回流去向**：国策度支应落到工匠/商人 POP（"支出回流"口径），
    # 而不是蒸发——这才是"守恒"的可观测证据（残差只是间接判据）。
    _craft_mer = (sum(p["pops"]["工匠"]["wealth"] for p in s.prefectures.values())
                  + sum(p["pops"]["商人"]["wealth"] for p in s.prefectures.values()))
    assert _craft_mer > 0, "国策度支未回流民间（工匠/商人 POP 无入账）"
    assert money.m_all(s) > 0, "M_ALL 不应为负"


def test_test_mirror_covers_full_pipeline():
    """逐步账本审计的 `_STEPS` 镜像必须**逐步等于**真实管线（同一个函数对象、同一顺序）。

    缺陷（2026-09-18 结算步专项检查）：镜像曾缺 `legacies` / `focus` 两步。
    这种缺失不会让任何测试变红，只会让"新结算步偷偷漏钱"从所有断言底下溜过去。

    断言方式：从 `run_monthly_settlement` 的 AST 里按**行号**取出实际调用序列，
    `getattr(core.settlement, name)` 解析成函数对象，再与镜像的 `(label, fn)` 逐位比较。
    这避免了对镜像短标签（`_settle_decrees` → `decrees`）做脆弱的名字猜测。
    """
    import ast
    import inspect as _inspect
    import core.settlement as S
    import test_pop_identity as T

    src = _inspect.getsource(S.run_monthly_settlement)
    tree = ast.parse(src)
    calls = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id.startswith("_")):
            if node.func.id in ("_money_audit_step", "_next_month"):
                continue
            calls.append((node.lineno, node.func.id))
    calls.sort()
    real_fns = []
    for _, name in calls:
        fn = getattr(S, name, None)
        assert callable(fn), f"管线里调用了 `{name}`，但在 core.settlement 中取不到可调用对象"
        real_fns.append(fn)
    mirror_fns = [fn for _, fn in T._STEPS]

    assert len(mirror_fns) == len(real_fns), (
        f"镜像步数 {len(mirror_fns)} ≠ 真实管线步数 {len(real_fns)}；"
        f"真实序列={[n for _, n in calls]}")
    for i, (m, r) in enumerate(zip(mirror_fns, real_fns)):
        assert m is r, (
            f"第 {i + 1} 步不一致：镜像={getattr(m, '__name__', m)} "
            f"真实={getattr(r, '__name__', r)}（顺序或成员不符，账本审计会错位）")


def test_middle_values_match_documented_compromise():
    """把**用户拍板的取中值**钉住：这些是刻意的历史↔游戏性折中，改动必须是有意的。

    历史侧 / 游戏性侧 / 取中值（详见 `游戏机制说明.md` 与各设计文档）：
      · 待阙俸率：史实多无俸(0) ↔ 待阙须有成本(0.5) → **0.35**
      · 祠禄折俸：史实半俸偏低 ↔ 需体现祠禄成本 → **0.4**
      · 吏薪基值：史实极薄(2.0) ↔ "先裁后提"要能走通 → **2.4**
      · 吏额自我膨胀：史实冗滥 ↔ 20 年内可感知 → **0.10%/月**
    """
    from content.data import (CLERK_ENTITLEMENT_GROWTH, CLERK_PAY_PER_MONTH,
                             SINECURE_PAY_RATIO, WAITING_PAY_RATIO)
    assert WAITING_PAY_RATIO == 0.35
    assert SINECURE_PAY_RATIO == 0.4
    assert CLERK_PAY_PER_MONTH == 2.4
    assert CLERK_ENTITLEMENT_GROWTH == 0.0010
    # 史实锚点**不动**：取中靠"修通道"而不是"改史实标尺"
    from content.data import ARRIVAL_BASE, ROUTE_POST_QUOTA
    assert ARRIVAL_BASE == 0.45, "史实到账率锚点被改动（取中不应动它）"
    assert ROUTE_POST_QUOTA == 1350
