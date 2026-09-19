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


def apply_reform(state, reform: Any) -> list:
    """落地一份编制改革契约 `{参数名: 绝对值或档位词}`（`free_effect` 的 `institution` 字段）。

    - 值是数字 → **增量**（与 `FREE_EFFECT_CAP["institution"]` 同量纲，档位词换算的结果）；
      「定编」「吏薪」这类用户可能想给倍率绝对值的，也接受带 `=` 前缀的字符串（如 `"=1.4"`）。
    - 值是档位词（无/微/小/中/大）→ 经 `tier_to_value` 换算为增量。
    - 未知键 / 非数值 → 该项拒绝，其余照常（逐项拒绝，不整单回滚）。
    """
    log = []
    if not isinstance(reform, dict):
        return ["[编制] 拒绝：institution 须为 {参数名: 值} 对象"]
    for key, raw in reform.items():
        if key not in _SPEC:
            log.append(f"[编制] 「{key}」不在白名单，拒绝")
            continue
        label = _SPEC[key]["label"]
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
