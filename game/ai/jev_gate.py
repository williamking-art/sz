# -*- coding: utf-8 -*-
"""Jev 决策闸门（可选层）—— 给 AI 提议加一层**独立**语义复核。

为什么需要它
------------
`decree_action_plan`（诏令 → 行动链）由 LLM 拆解，契约明文「**AI 只有提议权**」：
它自报 `unresolved`（哪里歧义/缺信息）。但**自报是自我评估**，没有第二双眼睛：
模型完全可能把「原文没写、自己推出来的」动作当成原文有据。

本模块用 Jev（TypeSafe System One，决策模型）做这件事：对每个动作问一个
**noul**（是/否概率）问题 ——「圣旨原文是否明确支持这个动作，而不是推演/猜测？」，
低于阈值就把该动作追加进 `unresolved`。该出口已被 `core/plan_commit.py` 与 UI 消费，
所以这是**可观察**的接线，而不是加个没人读的字段。

契约纪律（逐条对齐 game/ai/README.md）
--------------------------------------
1. **可选层，静默降级**：无配置 / 超时 / 报错 → 一律返回 `None`，调用方**行为完全不变**。
   绝不抛异常进主流程（"AI 不可用时不得让主流程崩"）。
2. **只出判断，不出数值**：Jev 返回概率，**由本模块**按阈值折算成档位词；玩家可见文案
   里不出现原始概率（脱敏优先，见 README 关键约定 1）。
3. **不引第三方依赖**：纯标准库 HTTP。
4. **失败要留痕**：不静默 `pass`，`logging.warning(..., exc_info=True)`。
5. **省钱**：N 个动作打包成**一次**调用（Jev 的 state 只摄入一次、多问题并行评估）。

配置（住在 `~/Documents/宋祚/ai_config.json`，与存档同根、`.gitignore` 已忽略）
------------------------------------------------------------------------------
    {
      "provider": "...", "api_key": "...",          # 原有 LLM 配置，不动
      "jev": {                                       # 新增可选段，缺失即整层禁用
        "enabled": true,
        "model": "jev-latest",
        "api_key": "apikey_...",                     # 或 key_file（每行一把，轮询）
        "endpoint": "https://api.typesafe.ai/v1/systemone",
        "threshold": 0.5,
        "timeout": 20
      }
    }

环境变量可覆盖（便于服务器/CI）：`SONGZUO_JEV_ENABLED=1`、`TYPESAFE_API_KEY`、
`SONGZUO_JEV_MODEL`、`SONGZUO_JEV_THRESHOLD`。
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
_DEFAULT_MODEL = "jev-latest"
_DEFAULT_THRESHOLD = 0.5
_DEFAULT_TIMEOUT = 20.0

#: 玩家可见的低支撑档位词（**不含数字**，脱敏优先）
_REASON_LOW = "独立复核：圣旨原文对该动作的支持不足，疑为推演，请核"

_ENV_ENABLED = "SONGZUO_JEV_ENABLED"


# --------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------
def load_config() -> dict | None:
    """读取 `jev` 配置段。返回 None 表示**未启用**（可选层关闭）。

    只用 `client_utils` 的单点配置路径；任何异常 → None（不抛）。
    """
    env_flag = os.environ.get(_ENV_ENABLED, "").strip().lower()
    if env_flag in ("0", "false", "no", "off"):
        return None

    cfg = None
    try:
        from ai.client_utils import resolve_ai_config_path
        path = resolve_ai_config_path()
        if path and os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
            if isinstance(raw, dict):
                cfg = raw.get("jev") if isinstance(raw.get("jev"), dict) else None
    except Exception:
        log.warning("jev_gate: 读取 ai_config.json 失败", exc_info=True)
        cfg = None

    cfg = dict(cfg or {})

    # 环境变量覆盖（服务器上没有 ai_config.json 时也能开）
    if os.environ.get("TYPESAFE_API_KEY"):
        cfg.setdefault("api_key", os.environ["TYPESAFE_API_KEY"])
    if os.environ.get("SONGZUO_JEV_MODEL"):
        cfg["model"] = os.environ["SONGZUO_JEV_MODEL"]
    if os.environ.get("SONGZUO_JEV_THRESHOLD"):
        cfg["threshold"] = os.environ["SONGZUO_JEV_THRESHOLD"]
    if env_flag in ("1", "true", "yes", "on"):
        cfg["enabled"] = True

    if not cfg.get("enabled"):
        return None
    # provider 解析（配置 > 环境变量 > 默认 **tokenrhythm**，免代理；typesafe 作兜底）
    name = str(cfg.get("provider") or os.environ.get("SONGZUO_JEV_PROVIDER") or "tokenrhythm")
    base = _PROVIDERS.get(name) or {}
    cfg["provider"] = name
    if base and "threshold" not in cfg:
        # 阈值按供应商各自校准（实测两种概率标度不同，不可互用）
        cfg["threshold"] = base["threshold"]
    if not (cfg.get("api_key") or cfg.get("key_file") or _keys_for(base)):
        log.warning("jev_gate: enabled 但 provider=%s 无可用 key → 视为禁用", name)
        return None
    return cfg


def enabled() -> bool:
    return load_config() is not None


#: 供应商登记表。**阈值必须按供应商各自校准**（见 tools\jev\jev_calibrate.py）：
#: tokenrhythm 的响应自带
#: `confidence_source=local_delivery_formula_not_verified_as_typesafe_equivalent`，
#: 即它自己声明概率并非 TypeSafe 等价物。实测（8 条中文样例）：
#:   typesafe    正例 0.65–0.95 / 负例 0.04–0.09 → 100% 区间 0.15–0.65 → 取 0.40
#:   tokenrhythm 正例 0.95–0.97 / 负例 0.00–0.09 → 100% 区间 0.15–0.90 → 取 0.50
_PROVIDERS = {
    "typesafe": {
        "endpoint": "https://api.typesafe.ai/v1/systemone",
        "model": "jev-latest",
        "key_env": "TYPESAFE_API_KEY",
        "keys_file": r"D:\codebuddy\_credentials\typesafe_jev_keys.txt",
        "threshold": 0.40,
    },
    "tokenrhythm": {
        # 服务器侧首选：**不需要代理**、更快（实测 0.36–0.54s vs TypeSafe 0.58s）
        "endpoint": "https://tokenrhythm.studio/v1/decision",
        "model": "NeoHorse-Jev-4B",
        "key_env": "TOKENRHYTHM_API_KEY",
        "keys_file": None,
        "threshold": 0.50,
    },
}


def _keys_for(spec: dict) -> list[str]:
    """按 provider 登记表取 key（env 优先，其次本地密钥文件）。"""
    keys: list[str] = []
    env = spec.get("key_env")
    if env and os.environ.get(env):
        keys += [k.strip() for k in os.environ[env].split(",") if k.strip()]
    kf = spec.get("keys_file")
    if not keys and kf and os.path.isfile(kf):
        try:
            with open(kf, encoding="utf-8") as fh:
                keys += [ln.strip() for ln in fh
                         if ln.strip() and not ln.startswith("#")]
        except Exception:
            log.warning("jev_gate: 读 keys_file 失败: %s", kf, exc_info=True)
    return keys


def _keys(cfg: dict) -> list[str]:
    keys = [k.strip() for k in str(cfg.get("api_key") or "").split(",") if k.strip()]
    kf = cfg.get("key_file")
    if kf and os.path.isfile(kf):
        try:
            with open(kf, encoding="utf-8") as fh:
                keys += [ln.strip() for ln in fh
                         if ln.strip() and not ln.startswith("#")]
        except Exception:
            log.warning("jev_gate: 读 key_file 失败: %s", kf, exc_info=True)
    return keys


# --------------------------------------------------------------------------
# HTTP（纯标准库；任何失败都不抛）
# --------------------------------------------------------------------------
def _decide(cfg: dict, state, questions: dict) -> dict | None:
    """调一次 Jev：**主通道失败自动降级到备用通道**。全失败返回 None（不抛）。

    主通道由 `provider` 决定（配置或环境变量 `SONGZUO_JEV_PROVIDER`，默认 typesafe）；
    备用通道用 `fallback_provider`（或 `SONGZUO_JEV_FALLBACK_PROVIDER`）指定。
    典型部署：服务器 `provider=tokenrhythm`（免代理）+ `fallback_provider=typesafe`。
    """
    primary = str(cfg.get("provider") or os.environ.get("SONGZUO_JEV_PROVIDER") or "tokenrhythm")
    order = [primary]
    fb = (cfg.get("fallback_provider") or os.environ.get("SONGZUO_JEV_FALLBACK_PROVIDER")
          or "typesafe")            # 默认：主 tokenrhythm（免代理）→ 备 typesafe
    if fb and str(fb) != primary:
        order.append(str(fb))
    try:
        timeout = float(cfg.get("timeout") or _DEFAULT_TIMEOUT)
    except Exception:
        timeout = _DEFAULT_TIMEOUT

    for name in order:
        base = _PROVIDERS.get(name)
        if not base:
            log.warning("jev_gate: 未知 provider=%s，跳过", name)
            continue
        is_primary = (name == primary)
        endpoint = str(cfg.get("endpoint") or base["endpoint"]) if is_primary else base["endpoint"]
        model = str(cfg.get("model") or base["model"]) if is_primary else base["model"]
        # 该 provider **自己的** key 优先；配置里的 api_key 只作最后兜底
        # （否则会出现「拿 typesafe 的 key 去打 tokenrhythm」的错配）
        keys = _keys_for(base) or (_keys(cfg) if is_primary else [])
        if not keys:
            log.warning("jev_gate: provider=%s 无可用 key，跳过", name)
            continue

        body = {"model": model, "state": state, "questions": questions}
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        for key in keys:                  # 多把 key 轮询（够用即可，不做退避重试）
            req = urllib.request.Request(
                endpoint, data=payload, method="POST",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json",
                         "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    out = json.loads(resp.read().decode("utf-8"))
                    if not is_primary:
                        log.warning("jev_gate: 主通道(%s)失败，已由备用通道(%s)应答", primary, name)
                    return out
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:200]
                log.warning("jev_gate: %s HTTP %s %s", name, exc.code, detail)
            except Exception:
                log.warning("jev_gate: %s 调用失败 endpoint=%s", name, endpoint, exc_info=True)
    return None


# --------------------------------------------------------------------------
# 决策点 1：动作是否有原文依据（noul）—— 接线到 unresolved
# --------------------------------------------------------------------------
def review_actions(edict_text, actions, *, threshold: float | None = None) -> list | None:
    """独立复核每个动作的原文依据。

    返回：追加的 `unresolved` 条目列表；**未启用/失败/无动作 → None**（调用方不改动）。
    多个动作打包成一次 Jev 调用。
    """
    cfg = load_config()
    if not cfg:
        return None
    if not isinstance(actions, list) or not actions:
        return None
    if not isinstance(edict_text, str) or not edict_text.strip():
        return None

    thr = _DEFAULT_THRESHOLD
    try:
        thr = float(threshold if threshold is not None else
                    cfg.get("threshold", _DEFAULT_THRESHOLD))
    except Exception:
        thr = _DEFAULT_THRESHOLD

    questions, index = {}, []
    for i, act in enumerate(actions):
        if not isinstance(act, dict):
            continue
        frag = str(act.get("source_fragment") or "").strip()
        title = str(act.get("title") or "").strip()
        if not (frag or title):
            continue
        key = f"a{i}"
        index.append((key, frag, title))
        questions[key] = {
            "type": "noul",
            "instructions": (
                "圣旨原文是否**明确支持**下面这个动作（而不是靠推演/猜测补出来的）？"
                f"\n动作题名：{title}\n动作依据片段：{frag}"),
        }
    if not questions:
        return None

    out = _decide(cfg, edict_text, questions)
    if not isinstance(out, dict):
        return None
    answers = out.get("answers")
    if not isinstance(answers, dict):
        log.warning("jev_gate: 响应缺 answers")
        return None

    extra = []
    for key, frag, _title in index:
        ans = answers.get(key)
        if not isinstance(ans, dict):
            continue
        p = ans.get("noul")
        try:
            p = float(p)
        except Exception:
            continue
        if p < thr:
            # 只写档位词，不把概率带进玩家可见文案（脱敏优先）
            extra.append({"source_fragment": frag, "reason": _REASON_LOW})
            log.info("jev_gate: 动作依据不足 p=%.3f < %.2f frag=%s", p, thr, frag[:40])
    return extra or None


# --------------------------------------------------------------------------
# 决策点 2：清单是否含不可逆后果（noul）—— 供后续「提交前确认」用
# --------------------------------------------------------------------------
def assess_irreversibility(edict_text, plan) -> dict | None:
    """判定行动清单是否含**不可逆/破坏性**后果。

    返回 `{"p": float, "tier": "高"|"低"}`（供程序决策）；未启用/失败 → None。
    `tier` 是档位词，可直接给前端；`p` 只供程序内部与日志。
    """
    cfg = load_config()
    if not cfg:
        return None
    if not isinstance(edict_text, str) or not edict_text.strip():
        return None
    acts = plan.get("actions") if isinstance(plan, dict) else None
    if not isinstance(acts, list) or not acts:
        return None
    summary = "；".join(str(a.get("title") or "") for a in acts if isinstance(a, dict))[:400]

    out = _decide(cfg, edict_text, {"q": {
        "type": "noul",
        "instructions": ("这批行动是否包含**不可逆或破坏性**的后果"
                         f"（拆毁、罢黜、处斩、开战、徵调等难以挽回者）？\n行动清单：{summary}")}})
    if not isinstance(out, dict):
        return None
    ans = (out.get("answers") or {}).get("q")
    if not isinstance(ans, dict):
        return None
    try:
        p = float(ans.get("noul"))
    except Exception:
        return None
    try:
        thr = float(cfg.get("threshold", _DEFAULT_THRESHOLD))
    except Exception:
        thr = _DEFAULT_THRESHOLD
    return {"p": p, "tier": "高" if p >= thr else "低"}
