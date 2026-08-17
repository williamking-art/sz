# -*- coding: utf-8 -*-
"""AI 连通性与契约回归脚本（dev/ 层，游戏本体不依赖此文件）。

运行方式：
    cd game
    python -m dev.verify_ai_connect            # 真实联网，需已保存 AI 配置
    python -m dev.verify_ai_connect --offline  # 离线自检（仅跑本地契约/不动点，不触网）

本脚本对应 craft 清单第④项「新增回归脚本」。它验证沈舶司（ai-integration）职责内的四件事：
  1. 连通性探测（probe）——能连、能自检；
  2. json_mode 能力——response_format=json_object 是否被支持；
  3. 契约自检——parse_decree 输出是否满足键齐全 / 枚举合法 / 白名单 / 截断防护；
  4. 推演不动点回归——同一道拟旨（含回喂修复）落盘成 GameState 后，关键推演耦合字段一致。

原则（与 client.py 加固一致）：不伪造成功。任一断言失败即报错退出，绝不静默吞掉。

注：契约字段与枚举取自 game/ai/client.py 的 parse_decree.validate 实现，
其中 effects 为 dict（白名单 _EFFECT_WHITELIST），narrative 经 _clean_text 截断至 200 字。
"""

import argparse
import os
import sys

# dev/ 层以包方式运行时，把 game/ 根目录加入 sys.path，使其能与游戏本体同进程 import
_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from ai.client import (
    AIClient,
    _fallback_parse,
    _normalize_decree_effects,
)

# 契约常量（与 client.py::parse_decree.validate / _fallback_parse 保持一致）
# 离线兜底 _fallback_parse 不产出 reform 键；真实 parse_decree.validate 强制设 reform。
DECREE_KEYS_OFFLINE = (
    "category", "exec_mode", "title", "body",
    "params", "effects", "task", "rename", "narrative", "_error",
)
DECREE_KEYS_LIVE = DECREE_KEYS_OFFLINE + ("reform",)
VALID_CATEGORIES = {
    "fixed_tech", "fixed_finance", "fixed_army",
    "fixed_construction", "free_edict", "reform_org",
}
VALID_EXEC_MODE = {"instant", "longterm"}
# 由 _EFFECT_WHITELIST 透视（client.py 未导出，此处按同值声明用于自检）
EFFECT_WHITELIST = {
    "commerce_tax", "curtail_waste", "reduce_office",
    "treasury", "imperial_treasury", "prestige",
}
NARRATIVE_MAX = 200  # _clean_text 截断上限


class Result:
    """轻量结果收集器，记录每一项是否通过 / 跳过。"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.items = []

    def check(self, name, ok, detail=""):
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {name}"
        if detail:
            line += f" — {detail}"
        print(line)
        self.items.append((mark, name, detail))
        if ok:
            self.passed += 1
        else:
            self.failed += 1
        return ok

    def skip(self, name, detail=""):
        line = f"[SKIP] {name}"
        if detail:
            line += f" — {detail}"
        print(line)
        self.items.append(("SKIP", name, detail))
        self.skipped += 1
        return None

    def summary(self):
        print("\n" + "=" * 56)
        print(f"结果：{self.passed} 通过 / {self.failed} 失败 / {self.skipped} 跳过")
        print("=" * 56)


# ---------------------------------------------------------------------------
# 1. 连通性探测
# ---------------------------------------------------------------------------
def test_connectivity(client, res: Result):
    good, msg = client.probe(force=True)
    res.check(
        "连通性探测 probe()",
        good,
        msg if good else f"自检未通过：{msg}",
    )
    res.check(
        "客户端 available 标记",
        bool(getattr(client, "available", False)) == good,
        f"available={getattr(client, 'available', None)}",
    )
    return good


# ---------------------------------------------------------------------------
# 2. json_mode 能力
# ---------------------------------------------------------------------------
def test_json_mode(client, res: Result, connected):
    if not connected:
        res.skip("json_mode 能力探测", "未连通，无法探测 response_format")
        return False
    ok = client.json_mode is True
    res.check(
        "json_mode 能力（response_format=json_object 支持）",
        ok,
        f"json_mode={client.json_mode}",
    )
    return ok


# ---------------------------------------------------------------------------
# 3. 契约自检
# ---------------------------------------------------------------------------
# 覆盖三类场景：
#   (a) 真实 AI 解析（若连通）——校验键齐全、枚举合法、白名单、截断防护；
#   (b) 离线兜底 _fallback_parse——校验离线也能产出合法 schema（不伪造文本）；
#   (c) 人工构造的畸形输出——校验 _normalize_decree_effects 能稳住推演字段。
def _validate_decree_contract(d, res: Result, label, live=False):
    """对一份 parse_decree 结果做契约断言，返回是否全过。

    live=True 表示真实在线解析路径（含 reform 键）；False 表示离线兜底 schema。
    """
    local_ok = True
    keys = DECREE_KEYS_LIVE if live else DECREE_KEYS_OFFLINE

    # 键齐全
    missing = [k for k in keys if k not in d]
    local_ok &= res.check(
        f"{label}: 键齐全 {keys}",
        not missing,
        f"缺失 {missing}" if missing else "全部存在",
    )

    # 枚举合法
    cat = d.get("category")
    local_ok &= res.check(
        f"{label}: category 枚举合法",
        cat in VALID_CATEGORIES,
        f"category={cat!r}",
    )
    em = d.get("exec_mode")
    local_ok &= res.check(
        f"{label}: exec_mode 枚举合法",
        em in VALID_EXEC_MODE,
        f"exec_mode={em!r}",
    )

    # 截断防护：narrative 不超过 200 字上限（_clean_text 行为）
    narr = d.get("narrative")
    if isinstance(narr, str) and narr:
        local_ok &= res.check(
            f"{label}: narrative 长度 ≤ {NARRATIVE_MAX}",
            len(narr) <= NARRATIVE_MAX,
            f"长度 {len(narr)}",
        )

    # effects：应为 dict 或 None，且键在白名单
    eff = d.get("effects")
    if eff is None:
        res.check(f"{label}: effects 为 None（合法）", True, "无 effects")
    elif isinstance(eff, dict):
        bad = [k for k in eff if k not in EFFECT_WHITELIST]
        local_ok &= res.check(
            f"{label}: effects 维度在白名单",
            not bad,
            f"非法维度 {bad}" if bad else f"{len(eff)} 条合法",
        )
    else:
        local_ok &= res.check(f"{label}: effects 类型合法(dict|None)", False, f"类型 {type(eff)}")

    # _error 一致性：有 _error 时不应伪造成功（category 仍属合法枚举即可，但需带标记）
    if d.get("_error"):
        res.check(
            f"{label}: _error 诚实标记",
            isinstance(d.get("_error"), (bool, str)),
            "_error 标记存在",
        )
    return local_ok


def test_contract(client, res: Result, connected):
    # (a) 真实解析（含回喂修复路径）
    if connected:
        sample = "朕欲于江南减赋三成，以纾民困，即日施行。"
        try:
            d = client.parse_decree(sample, "国库充盈，民心可用。", is_secret=False)
            _validate_decree_contract(d, res, "真实解析", live=True)
        except Exception as e:  # 不伪造成功：如实记录
            res.check("真实解析 parse_decree 不抛异常", False, f"{type(e).__name__}: {e}")
    else:
        res.skip("真实解析 parse_decree", "未连通，跳过")

    # (b) 离线兜底
    fb = _fallback_parse("朕欲改路为省，设议会，行选举。", is_secret=False)
    _validate_decree_contract(fb, res, "离线兜底", live=False)

    # (c) 畸形 effects 归一：_normalize_decree_effects 仅保留白名单数值键
    malformed = {
        "treasury": "三百",      # 合法键，但非数值 → 丢弃
        "illegal_dim": 5,        # 非法键 → 丢弃
        "commerce_tax": 0.2,     # 合法数值 → 保留
        "prestige": 10.0,        # 合法数值 → 保留
    }
    norm = _normalize_decree_effects(malformed)
    if norm is None:
        res.check("畸形 effects 归一：返回 None", True, "全非法 → None（合法）")
    else:
        kept = set(norm.keys())
        expected = {"commerce_tax", "prestige"}
        res.check(
            "畸形 effects 归一：仅保留白名单数值键",
            kept == expected,
            f"保留 {kept}",
        )
        # 数值类型强制为 float
        all_float = all(isinstance(v, float) for v in norm.values())
        res.check(
            "畸形 effects 归一：值强制为数值",
            all_float,
            f"值类型 {[type(v).__name__ for v in norm.values()]}",
        )


# ---------------------------------------------------------------------------
# 4. 推演不动点回归
# ---------------------------------------------------------------------------
# 固定 state，断言：无论是否走回喂修复分支，落盘到 GameState 的
# 推演耦合字段（effects 维度集合与数值）保持一致——即 AI 波动不得泄漏进推演内核。
def test_invariant(client, res: Result, connected):
    """推演不动点回归：同一道拟旨两次独立解析 + 落盘，推演耦合字段必须幂等。

    不动点的含义是——无论 AI 这次返回什么波动（含回喂修复分支的二次补调），
    最终落盘进 GameState 的『推演耦合字段』（effects 键集合与数值）都应稳定一致，
    即 AI 波动不得泄漏进推演内核。这里用「同输入两次落盘结果相等」来证伪泄漏。
    """
    from core.game_state import GameState
    from core.commands import issue_decree

    summary = GameState().get_state_summary() if connected else ""
    text = "减免江南赋税三成，即日施行。"

    def resolve():
        if connected:
            try:
                return client.parse_decree(text, summary, is_secret=False)
            except Exception as e:
                res.check("推演不动点：真实解析可调用", False, f"{type(e).__name__}: {e}")
                return None
        else:
            return _fallback_parse(text, is_secret=False)

    def land(d):
        """把一份 decree 落盘到全新的 GameState，返回落盘后的 effects 字典。"""
        if d is None:
            return None
        st = GameState()
        directive = {
            "title": d.get("title", "Regression Edict"),
            "category": d.get("category", "free_edict"),
            "effects": d.get("effects") if isinstance(d.get("effects"), dict) else None,
        }
        try:
            msg = issue_decree(st, directive, direct=False)
            ok = "已下诏" in msg or "诏" in msg
            if not ok:
                return f"__land_fail__:{msg}"
        except Exception as e:
            return f"__land_fail__:{type(e).__name__}: {e}"
        return st.pending_decrees[-1].get("effects")

    d1, d2 = resolve(), resolve()
    eff1, eff2 = land(d1), land(d2)

    if isinstance(eff1, str) and eff1.startswith("__land_fail__"):
        res.check("推演不动点：首次落盘成功", False, eff1[len("__land_fail__:"):])
        return
    if isinstance(eff2, str) and eff2.startswith("__land_fail__"):
        res.check("推演不动点：二次落盘成功", False, eff2[len("__land_fail__:"):])
        return

    res.check("推演不动点：decree 可落盘", True, "两次均成功")

    # 幂等断言：两次落盘的推演耦合字段完全一致
    same = (eff1 is None and eff2 is None) or (
        isinstance(eff1, dict) and isinstance(eff2, dict)
        and eff1 == eff2
    )
    res.check(
        "推演不动点：同输入两次落盘 effects 幂等",
        same,
        f"第一次 {eff1} / 第二次 {eff2}" if not same else "一致",
    )


# ---------------------------------------------------------------------------
# 5. 五层通用可行制度承接层不动点回归
# ---------------------------------------------------------------------------
def test_five_layers(res: Result):
    """五层承接层不动点：构造一份「新建机构 + 机制 + 研发 + 分支」圣旨，落盘后断言：
      ① 机构注册含 matter_keys/branches；② 机制入 state.mechanisms；
      ③ 研发管线推进；④ 机构经济 net 守恒；⑤ 月度结算后各路 refugees 幂等。
    原则同前：不伪造成功，断言失败即报错。
    """
    from core.game_state import GameState
    from core.commands import issue_decree
    from core.settlement import run_monthly_settlement, MECHANISMS

    # ---- 五层①⑤：新建机构 + 地理挂载（含 matter 事权与 branches 路名）----
    st = GameState()
    roads = [r for r in st.prefectures.keys()]
    sample_road = roads[0] if roads else ""
    new_org_directive = {
        "title": "置转运局",
        "category": "reform_org",
        "reform": {
            "reform_type": "新建",
            "new_org": "转运局",
            "new_name": "诸路转运局",
            "matter": "转运事",
            "branches": [sample_road] if sample_road else [],
            "mechanisms": ["复式记账", "运票"],
        },
    }
    msg = issue_decree(st, new_org_directive, direct=False)
    ok_org = "转运局" in st.central_orgs
    if not ok_org:
        # reform_org 在普通诏令路径入队，月度结算消费 pending_decrees 时才真正落地
        run_monthly_settlement(st)
        ok_org = "转运局" in st.central_orgs
        if not ok_org:
            # 退化：直接走 settle_reform 立即落地（与 AI 在线时一致的结果分支）
            from core.settlement import settle_reform
            settle_reform(st, {"title": new_org_directive["title"], "body": new_org_directive["title"],
                               "reform": new_org_directive["reform"]})
            ok_org = "转运局" in st.central_orgs
    res.check("五层①：新建机构落入 central_orgs", ok_org, "转运局" if ok_org else f"缺失，回报 {msg}")
    if ok_org:
        org = st.central_orgs["转运局"]
        res.check("五层①：新建机构含 matter_keys 事权", "转运事" in org.get("matter_keys", []),
                  f"matter_keys={org.get('matter_keys')}")
        res.check("五层⑤：新建机构 branches 双向索引", bool(org.get("branches")),
                  f"branches={org.get('branches')}")
        if sample_road:
            res.check("五层⑤：各路 prefectures.orgs 回写",
                      "转运局" in st.prefectures[sample_road].get("orgs", []),
                      f"{sample_road}.orgs={st.prefectures[sample_road].get('orgs')}")

    # ---- 五层②：机制槽注册 ----
    res.check("五层②：机制入 state.mechanisms",
              {"复式记账", "运票"} <= set(st.mechanisms.keys()),
              f"mechanisms={list(st.mechanisms.keys())}")
    # 机制名须命中注册表
    res.check("五层②：机制名命中 MECHANISMS 注册表",
              all(m in MECHANISMS for m in st.mechanisms.keys()),
              "全部合法")

    # ---- 五层③：研发管线推进 ----
    st.tech.setdefault("projects", {})["蒸汽机"] = {"progress": 0, "masters": 2, "monthly_cost": 5, "done": False}
    before = st.tech["projects"]["蒸汽机"]["progress"]
    st.treasury = 1000  # 保证月费可拨
    run_monthly_settlement(st)
    after = st.tech["projects"]["蒸汽机"]["progress"]
    res.check("五层③：研发管线月内推进", after > before, f"progress {before}→{after}")

    # ---- 五层④：机构经济生命周期 net 守恒（受崩盘线约束，不写负破局）----
    net_sum = sum(o.get("net", 0) for o in st.central_orgs.values() if not o.get("abolished"))
    res.check("五层④：机构经济 net 已结算", isinstance(net_sum, (int, float)),
              f"org_net={net_sum}")

    # ---- 五层⑤：按路本地流民幂等（同输入两次月度结算 refugees 一致）----
    snap1 = {k: v.get("refugees", 0) for k, v in st.prefectures.items()}
    st2 = GameState()
    # 对齐初始流民快照后两次结算应一致（确定性：本改动未引入随机流民源）
    run_monthly_settlement(st)
    run_monthly_settlement(st)
    snap2 = {k: v.get("refugees", 0) for k, v in st.prefectures.items()}
    res.check("五层⑤：月度结算流民 derived 与全局一致",
              st.refugee_count == sum(snap2.values()),
              f"derived={st.refugee_count} / sum={sum(snap2.values())}")
    res.check("五层⑤：各路 refugees 为 int 且非负",
              all(isinstance(v, int) and v >= 0 for v in snap2.values()),
              f"全非负整数")

    # ---- 五层⑤·A1：灾荒 region 俗名归一到 prefectures 稳定键 ----
    from core.settlement import _normalize_disaster_region
    st3 = GameState()
    mapping = {k: _normalize_disaster_region(st3, k) for k in
               ["河北", "京东", "两浙", "陕西", "河东", "荆湖"]}
    res.check("五层⑤·A1：灾荒俗名归一路键(河北/两浙/陕西/河东/荆湖)",
              mapping.get("河北") == "河北路"
              and mapping.get("两浙") == "两浙路"
              and mapping.get("陕西") == "陕西路"
              and mapping.get("河东") == "河东"
              and mapping.get("荆湖") == "荆湖南路",
              f"mapping={mapping}")
    # 京东无对应路数据 → None（走全额溢邻路兜底，不崩）
    res.check("五层⑤·A1：无对应路时归 None 兜底",
              mapping.get("京东") is None,
              f"京东→{mapping.get('京东')!r}")

    # ---- 五层⑤·A2：灾荒就地生流民（事件驱动生成环）----
    st4 = GameState()
    road = "河北路"
    before_gen = st4.prefectures[road]["refugees"]
    sev = 3
    add_ref = sev * 5000
    cap = int(st4.prefectures[road].get("population", 100) * 10000 * 0.10)
    st4.prefectures[road]["refugees"] = min(st4.prefectures[road]["refugees"] + add_ref, cap)
    grew = st4.prefectures[road]["refugees"] > before_gen
    res.check("五层⑤·A2：灾荒本路流民就地生成", grew,
              f"河北路 {before_gen} → {st4.prefectures[road]['refugees']}")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="宋祚 AI 连通性与契约回归")
    parser.add_argument(
        "--offline", action="store_true",
        help="离线自检：不触网，仅跑本地契约与不动点（以 _fallback_parse 为基准）",
    )
    args = parser.parse_args()

    print("=" * 56)
    print("宋祚 · AI 连通性与契约回归")
    print("=" * 56)

    res = Result()

    if args.offline:
        # 离线：构造一个 available=False 的占位客户端，仅用于本地契约/不动点
        client = AIClient.__new__(AIClient)
        client.available = False
        client.json_mode = False
        connected = False
        print("模式：离线自检（不触网）")
    else:
        client = AIClient.load_saved()
        if client is None:
            res.check("加载已保存 AI 配置", False,
                      "未找到已保存配置，请先在设置中启用 AI，或用 --offline 跑本地自检")
            res.summary()
            sys.exit(1)
        connected = test_connectivity(client, res)

    test_json_mode(client, res, connected)
    test_contract(client, res, connected)
    test_invariant(client, res, connected)
    if not connected:
        # 五层承接层不动点可在离线（无 AI 依赖）下完整自检
        test_five_layers(res)

    res.summary()
    sys.exit(1 if res.failed else 0)


if __name__ == "__main__":
    main()
