# -*- coding: utf-8 -*-
"""编制参数的单一权威源（阶段 C-7，宋代官制设计 §12.3 / §17.4）。

## 为什么是"参数"而不是"转轨系统"

**已拍板决策 3**：不为公务员制做专门的转轨子系统（不做"归一入口"，不做转轨开关）。
理由：游戏已有完整的政令链路（拟诏 → 会签 → 落地 → 结算），制度变更本就是它的职责；
专门做一套"转轨开关"等于把玩家的制度设计权收回到开发者手里，反而削弱玩点。

> **宋代官吏制 ＝ 这组参数的一组取值；公务员制 ＝ 同一组参数的另一组取值。**
> **改制的本质是"移动参数"，不是"新建系统"。**

因此本模块只做三件事：
1. 单点约束参数**值域**（`content.data.INSTITUTION_PARAM_SPEC`）；
2. 提供 `get()` / `set_param()` 供结算模块**消费**（取代直接读常量）；
3. 供 `free_effect` 的 `institution` 字段与 `/api/readouts` 读取。

`state.institution_params` 只存**被改过的键**（缺键 = 默认值），旧档天然兼容。
"""
from typing import Any, Dict, Tuple

from content.data import INSTITUTION_PARAM_SPEC

_SPEC = INSTITUTION_PARAM_SPEC

# 档位词 → 参数**增量**（倍率）。
#
# 刻意**不走** `ai.client_utils.tier_to_value`：那个函数的维度表（`TIER_VALUE_BASE`）同时被
# `_EFFECT_WHITELIST`/`_ALLOWED_DIMS` 用作"AI 可给出的 effects 键"白名单，把 `institution`
# 加进去会让 AI 可以给出**标量** `"institution": "中"`——而本字段的契约是**字典**。
# 因此这里自带一张小表，只服务 `institution` 字典内部的键。
TIER_STEP = {"无": 0.0, "微": 0.05, "小": 0.12, "中": 0.25, "大": 0.40,
             "极小": 0.02, "极大": 0.60}


def all_params(state) -> Dict[str, float]:
    """当前全部参数的有效值（缺键补默认）。"""
    cur = getattr(state, "institution_params", None)
    if not isinstance(cur, dict):
        cur = {}
        state.institution_params = cur
    return {k: float(cur.get(k, v["default"])) for k, v in _SPEC.items()}


def get(state, key: str, fallback: float = 1.0) -> float:
    """读单个参数（未知键返回 `fallback`，**绝不抛**——结算路径不应因参数缺失而中断）。

    2026-09-18 补测发现并修复：原实现用 `getattr(...) or {}` 兜底，**真值非 dict**
    （如损坏/旧档里 `institution_params` 是字符串）会穿透到 `cur.get(...)` → `AttributeError`。
    而本函数被官制（磨勘/祠禄/恩荫/定编）、吏制（吏薪）、维持费三处**每步结算**调用，
    一旦破档就会让整个月度结算崩掉。现改为显式类型判定。
    """
    spec = _SPEC.get(key)
    if spec is None:
        return float(fallback)
    cur = getattr(state, "institution_params", None)
    if not isinstance(cur, dict):
        return float(spec["default"])
    try:
        return float(cur.get(key, spec["default"]))
    except (TypeError, ValueError):
        return float(spec["default"])


def clamp(key: str, value: float) -> float:
    spec = _SPEC.get(key)
    if spec is None:
        return float(value)
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(spec["default"])
    return max(float(spec["min"]), min(float(spec["max"]), v))


def set_param(state, key: str, value: float) -> Tuple[bool, str]:
    """设置参数（**绝对值**，自动钳到值域）。返回 (是否改动, 说明)。"""
    spec = _SPEC.get(key)
    if spec is None:
        return False, f"未知编制参数「{key}」（不在白名单，拒绝）"
    cur = get(state, key)
    new = clamp(key, value)
    if abs(new - cur) < 1e-9:
        return False, f"{spec['label']} 已是 {cur:g}"
    if not isinstance(getattr(state, "institution_params", None), dict):
        state.institution_params = {}
    state.institution_params[key] = new
    return True, f"{spec['label']} {cur:g} → {new:g}"


def set_by_delta(state, key: str, delta: float) -> Tuple[bool, str]:
    """按**增量**调整（free_effect 的档位词换算结果即为增量）。"""
    return set_param(state, key, get(state, key) + float(delta or 0))


# ---------------------------------------------------------------------------
# 执行侧权限校验（用户口径 2026-09-19：**权限跟部门/官职，人是载体**，换人不换权）
#
# 旋钮不是"定义"而是**权限**：圣旨须**指定执行主体**，由掌该事权者执行。
# 授权表复用既有数据（不新开账本）：
#   · `content/ministers/data.py::AUTHORITY_MATTERS`（事权 → owner 机构）
#   · `CENTRAL_ORG_INFO[机构]["authority"] / ["posts"] / ["holders"]`
# 运行期以 `state.central_orgs`（机构改名/裁撤/换人后的活账）为准，缺省回退内容表。
# ---------------------------------------------------------------------------

_EXECUTOR_KEYS = ("org", "post", "holder", "person", "minister")


def _matter_of(key: str) -> str:
    """参数要求的事权（无 → 不受事权约束，任何主体可改）。"""
    return str((_SPEC.get(key) or {}).get("authority") or "")


def _org_table(state) -> dict:
    """机构活账：`state.central_orgs` 优先（含改名/裁撤/换人），回退内容表。"""
    orgs = getattr(state, "central_orgs", None)
    if isinstance(orgs, dict) and orgs:
        return orgs
    try:
        from content.ministers.data import CENTRAL_ORG_INFO
        return CENTRAL_ORG_INFO
    except Exception:  # noqa: BLE001 - 内容表缺失不应让结算路径崩
        return {}


def _authority_matters_of(state, org_name: str) -> set:
    """某机构掌有的事权集合（机构 authority/matter_keys ＋ 事权表 owner 反查）。"""
    out = set()
    org = _org_table(state).get(org_name) or {}
    if isinstance(org, dict):
        for m in list(org.get("authority") or []) + list(org.get("matter_keys") or []):
            out.add(str(m))
    matters = getattr(state, "authority_matters", None)
    if not isinstance(matters, dict) or not matters:
        try:
            from content.ministers.data import AUTHORITY_MATTERS
            matters = AUTHORITY_MATTERS
        except Exception:  # noqa: BLE001
            matters = {}
    for m, info in (matters or {}).items():
        if isinstance(info, dict) and info.get("owner") == org_name:
            out.add(str(m))
    return out


def _executor_by_org(state, orgs: dict, name: str) -> Tuple[set, str, str]:
    org = orgs.get(name)
    if not isinstance(org, dict):
        return set(), name, f"未知机构「{name}」"
    if org.get("abolished"):
        return set(), name, f"机构「{name}」已裁撤，无权执行"
    return _authority_matters_of(state, name), f"{name}（机构）", ""


def _executor_by_post(state, orgs: dict, title: str) -> Tuple[set, str, str]:
    """官职载体：须该官职**有人任职**（人是载体；换人不换权 → 权在官职上）。"""
    for oname, org in orgs.items():
        if not isinstance(org, dict):
            continue
        for p in (org.get("posts") or []):
            if not isinstance(p, dict) or str(p.get("title") or "") != title:
                continue
            if org.get("abolished"):
                return set(), title, f"机构「{oname}」已裁撤，无权执行"
            holder = str((org.get("holders") or {}).get(title) or "").strip()
            if not holder:
                return set(), title, f"官职「{title}」无人任职（人是载体，须先授职）"
            return (_authority_matters_of(state, oname),
                    f"{title}（{oname} · {holder}）", "")
    return set(), title, f"未知官职「{title}」"


def _executor_by_person(state, orgs: dict, name: str) -> Tuple[set, str, str]:
    """人只是载体：按其**担任的官职**所属机构取权，不按人另立权限。"""
    hits = []
    for oname, org in orgs.items():
        if not isinstance(org, dict) or org.get("abolished"):
            continue
        for post, holder in (org.get("holders") or {}).items():
            if str(holder or "").strip() == name:
                hits.append((oname, str(post)))
    if not hits:
        return set(), name, f"「{name}」未担任任何掌权官职（人是载体）"
    matters = set()
    for oname, _post in hits:
        matters |= _authority_matters_of(state, oname)
    label = name + "（" + "、".join(f"{o}·{p}" for o, p in hits) + "）"
    return matters, label, ""


def resolve_executor(state, executor) -> Tuple[set, str, str]:
    """把"执行主体"解析为 `(掌有的事权集合, 可读标签, 拒绝原因)`。

    载体（三种等价，均落到"机构"上取权）：
      · 机构名（如「户部」）；
      · 官职名（如「抵当所提举」，须有人任职）；
      · 人名（如「王古」，按其担任的官职反查）。
    也可传 `{"org": ...}` / `{"post": ...}` / `{"holder": ...}`（取首个非空字段）。
    解析失败返回原因，由调用方拒绝并留痕（**不静默放行**）。
    """
    if isinstance(executor, dict):
        org = str(executor.get("org") or "").strip()
        post = str(executor.get("post") or "").strip()
        holder = str(executor.get("holder") or executor.get("person")
                     or executor.get("minister") or "").strip()
        text = org or post or holder
        if not text:
            return set(), "", "执行主体须含 org/post/holder 之一"
    else:
        text = str(executor or "").strip()
    if not text:
        return set(), "", "未指定执行主体"
    orgs = _org_table(state)
    if isinstance(executor, dict) and str(executor.get("org") or "").strip():
        return _executor_by_org(state, orgs, text)
    specific = ""
    for finder in (_executor_by_org, _executor_by_post, _executor_by_person):
        matters, label, err = finder(state, orgs, text)
        if not err:
            return matters, label, ""
        if err and "未知" not in err:
            # 已知机构/官职/人但不可执行（已裁撤 / 无人任职 / 未任官职）→ 保留具体原因
            specific = specific or err
    return set(), text, specific or f"未知执行主体「{text}」（既非机构，也非官职或任职人）"


def check_authority(state, key: str, executor) -> Tuple[bool, str]:
    """校验参数 `key` 可否由 `executor` 执行 → `(是否放行, 原因)`。

    无 `authority` 字段的参数（如磨勘/荫补等六杠杆）**不受事权约束**，恒放行；
    受约束参数**未指定主体即拒绝**（圣旨不能绕过执行侧校验）。
    """
    matter = _matter_of(key)
    if not matter:
        return True, ""
    matters, label, err = resolve_executor(state, executor)
    if err:
        return False, f"须由掌「{matter}」事权的部门/官职执行：{err}"
    if matter not in matters:
        return False, f"执行主体「{label}」不掌「{matter}」事权，拒绝"
    return True, ""


def require_matter(state, executor, matter: str) -> Tuple[bool, str]:
    """校验执行主体是否掌某**具体事权** → `(ok, label_or_reason)`。

    与 `check_authority(key)` 不同：这里直接给事权名（如「官吏铨选」），
    供人事/财政等**非参数型**入口复用；未指定事权/解析失败/不掌该权一律拒绝。
    """
    key = str(matter or "").strip()
    if not key:
        return False, "未指定事权"
    matters, label, err = resolve_executor(state, executor)
    if err:
        return False, err
    if key not in matters:
        return False, f"执行主体「{label}」不掌「{key}」事权，拒绝"
    return True, label


def apply_reform(state, reform: Any, executor: Any = None) -> list:
    """落地一份编制改革契约 `{参数名: 绝对值或档位词}`（`free_effect` 的 `institution` 字段）。

    - 值是数字 → **增量**（与 `FREE_EFFECT_CAP["institution"]` 同量纲，档位词换算的结果）；
      「定编」「吏薪」这类用户可能想给倍率绝对值的，也接受带 `=` 前缀的字符串（如 `"=1.4"`）。
    - 值是档位词（无/微/小/中/大）→ 经 `tier_to_value` 换算为增量。
    - 未知键 / 非数值 → 该项拒绝，其余照常（逐项拒绝，不整单回滚）。
    - **受事权约束的参数**（spec 带 `authority` 字段，如 `didang_*` 归「官营放贷」：
      户部 + 抵当所提举）须由 `executor` 掌该事权才落地；**未指定主体或非掌权者逐项拒绝**，
      玩家诏令与 AI 提案走同一校验（不能绕过）。

    `executor` 支持机构名 / 官职名 / 人名 / `{org|post|holder}`（见 `resolve_executor`）。
    """
    log = []
    if not isinstance(reform, dict):
        return ["[编制] 拒绝：institution 须为 {参数名: 值} 对象"]
    for key, raw in reform.items():
        if key not in _SPEC:
            log.append(f"[编制] 「{key}」不在白名单，拒绝")
            continue
        label = _SPEC[key]["label"]
        allowed, why = check_authority(state, key, executor)
        if not allowed:
            log.append(f"[编制] 「{label}」拒绝：{why}")
            continue
        absolute = False
        val = raw
        if isinstance(raw, str):
            text = raw.strip()
            if text.startswith("="):
                absolute, text = True, text[1:]
            if text.replace(".", "", 1).replace("-", "", 1).isdigit():
                val = float(text)
            else:
                # 档位词：用本模块的 TIER_STEP（不碰共享维度表，见上方注释）
                from content.data import normalize_tier
                sign = 1.0
                if text.startswith("+"):
                    text = text[1:]
                elif text.startswith("-"):
                    sign, text = -1.0, text[1:]
                val = sign * TIER_STEP.get(normalize_tier(text), 0.0)
        if not isinstance(val, (int, float)):
            log.append(f"[编制] 「{key}」值须为数字或档位词，拒绝")
            continue
        ok, msg = (set_param(state, key, val) if absolute else set_by_delta(state, key, val))
        log.append(f"[编制] {msg}" + ("" if ok else "（未改动）"))
    return log


def describe(state) -> Dict[str, Any]:
    """面板/AI 读数：每个参数当前值、默认值、值域与是否被改动。"""
    cur = all_params(state)
    out: Dict[str, Any] = {}
    for k, spec in _SPEC.items():
        out[k] = {
            "label": spec["label"],
            "value": round(cur[k], 4),
            "default": float(spec["default"]),
            "min": float(spec["min"]),
            "max": float(spec["max"]),
            "changed": abs(cur[k] - float(spec["default"])) > 1e-9,
        }
    return out


def changed_count(state) -> int:
    return sum(1 for v in describe(state).values() if v["changed"])
