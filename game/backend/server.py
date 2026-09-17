# -*- coding: utf-8 -*-
"""宋祚 · Python 参考后端（B3：FastAPI + Uvicorn，可选）

定位：**开发/测试用参考实现**——把 LocalBackend 原样包成 HTTP 服务，
实现与 Rust songzuo_server 相同的 /api/* 端点，供 HttpBackend 联调、
自动化回归（严归正席位）与无 Rust 环境的远程后端体验。

设计纪律：
- 薄壳：业务逻辑 100% 复用 LocalBackend（core.commands），**零复制**——
  这正是"远程后端常量漂移"质量债（ANNUAL_TAX_BASE 曾差 8 倍）的根治方式：
  参考后端与本地后端共享同一份权威常量，漂移无处发生；
- 单会话：全局一把锁（单机游戏语义），并发请求串行化；
- AI 可选：服务端按 ai_config.json 构建 AIClient；无 key 时用禁用客户端，
  叙事自动走本地降级模板（绝不伪造在线结果）；
- 状态快照：vars(state) 逐字段 JSON 安全过滤（不可序列化字段跳过，
  重建端以 GameState 构造默认值兜底——与 HttpBackend._to_state 对称）。

运行：python -m backend.server   （端口/地址见环境变量，默认 127.0.0.1:8080）
依赖：fastapi + uvicorn（见 requirements-extras.txt；未安装则本模块不可导入）
"""
from __future__ import annotations

import json
import os
import sys
import threading

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from ai.client import AIClient
from backend.client import LocalBackend, _app_root

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Songzuo Reference Backend", version="1.0")

# 配置：默认仅本机；跨源需显式白名单（审查 P2：禁止裸 * + credentials）
_DEFAULT_ORIGINS = [
    "http://127.0.0.1:8080", "http://localhost:8080",
    "http://127.0.0.1:5173", "http://localhost:5173",
]
_allowed = os.environ.get("SONGZUO_CORS_ORIGINS", "")
_origins = [o.strip() for o in _allowed.split(",") if o.strip()] or _DEFAULT_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_lock = threading.Lock()
_backend = LocalBackend()
_state = None          # 当前 GameState（服务端持有）
_ai = None             # 服务端 AIClient（可禁用）

#: 可选鉴权 token（环境变量）；仅本机回环且未设 token 时放行（兼容单机联调）
_AUTH_TOKEN = (os.environ.get("SONGZUO_SERVER_TOKEN") or "").strip()


def _require_auth(request) -> None:
    """非本机或已配置 token 时强制校验 Authorization: Bearer。"""
    if not _AUTH_TOKEN:
        return
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if auth == f"Bearer {_AUTH_TOKEN}":
        return
    raise HTTPException(status_code=401, detail="令符不合，未获授权。")


def _build_ai() -> AIClient:
    """按 ai_config.json 构建服务端 AI 客户端；无配置/无 key → 禁用客户端。"""
    try:
        path = os.path.join(_app_root(), "ai_config.json")
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return AIClient(
            api_key=str(cfg.get("api_key", "") or ""),
            base_url=str(cfg.get("base_url", "") or ""),
            model=str(cfg.get("model", "") or ""),
            # 迁移补齐：办差工具三档（缺省 auto=按端点探测）
            enable_tools=str(cfg.get("enable_tools", "") or "auto"),
        )
    except Exception:
        return AIClient()  # available=False → 叙事走本地降级


def _get_ai() -> AIClient:
    global _ai
    if _ai is None:
        _ai = _build_ai()
    return _ai


def _json_safe(v):
    """递归转 JSON 安全值：set/tuple→list，其余不可序列化→str 兜底。"""
    if isinstance(v, dict):
        return {str(k): _json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (set, frozenset)):
        return sorted(str(x) for x in v)
    try:
        json.dumps(v, ensure_ascii=False)
        return v
    except Exception:
        return str(v)


def _loyalty_band_word(v) -> str:
    if v >= 85: return "死忠"
    if v >= 70: return "忠顺"
    if v >= 55: return "恭谨"
    if v >= 40: return "敷衍"
    if v >= 25: return "离心"
    return "怨望"


def _corruption_band_word(v) -> str:
    if v >= 0.85: return "巨贪"
    if v >= 0.65: return "贪墨"
    if v >= 0.45: return "平庸"
    if v >= 0.25: return "尚廉"
    if v >= 0.10: return "清廉"
    return "廉洁"


def _estate_band_word(e) -> str:
    """大臣家产 → 档位词（铁律 6：真值不外泄，只见档位）。"""
    try:
        from core.estate_mechanic import estate_tier
        return estate_tier(int((e or {}).get("wealth", 0)) if isinstance(e, dict) else 0)
    except Exception:
        return "清贫"


def _state_to_dict(s) -> dict:
    """GameState → JSON 快照（与 HttpBackend._to_state 对称）。

    审查 P1：忠诚/贪腐是隐藏维度（铁律 6——只给姿态词，数值绝不外泄），
    快照下发前转为档位词，防真值直送客户端面板。
    审查 P2：minister_estate（家产精确财富/田亩）与 pending_secret_decrees
    （密令秘密忠诚）同属隐藏数值，一并档位化/剔除。
    """
    out = {}
    for k, v in vars(s).items():
        if k.startswith("_"):
            continue  # 私有/缓存字段不外发
        if k in ("loyalty", "corruption") and isinstance(v, dict):
            out[k] = {str(n): (_loyalty_band_word(x) if k == "loyalty" else _corruption_band_word(x))
                      for n, x in v.items()}
            continue
        if k == "minister_estate" and isinstance(v, dict):
            # 家产真值不外泄：只给档位词
            out[k] = {str(n): _estate_band_word(e) for n, e in v.items()}
            continue
        if k == "pending_secret_decrees" and isinstance(v, list):
            # 密令中的 secret_loyalty 为隐藏数值，剔除后下发
            out[k] = [{kk: vv for kk, vv in (d or {}).items() if kk != "secret_loyalty"}
                      for d in v]
            continue
        try:
            json.dumps(v, ensure_ascii=False)
            out[k] = _json_safe(v)
        except Exception:
            continue
    return out


def _require_state():
    if _state is None:
        raise HTTPException(status_code=409, detail="尚未开局，请先行开新局。")


def _find_frontend_event(s, title: str):
    """按 title 反查完整事件对象（含 choices）。

    审查 P1-12 修复：前端 resolveEvent 只发送 {title, choice}，而 core.resolve_event 需要
    完整事件对象（读取 choices）。原服务端把 title 字符串直接转给 core → AttributeError
    （远程模式事件抉择 100% 失败）。现按 title 从本回合缓存（/api/advance 写入）反查，
    再兜底扫描在场事件；都取不到则返回 None（由端点给出明确 404，而非崩溃）。
    """
    if not title:
        return None
    cache = getattr(s, "_frontend_events", None) or {}
    ev = cache.get(title)
    if isinstance(ev, dict) and ev.get("choices"):
        return ev
    for e in (getattr(s, "active_events", None) or []):
        if isinstance(e, dict) and e.get("title") == title and e.get("choices"):
            return e
    return ev if isinstance(ev, dict) else None


class NewGameReq(BaseModel):
    difficulty: str = "史实"


class ActionReq(BaseModel):
    action: str
    params: dict = {}


class ResolveReq(BaseModel):
    # 前端（Electron）契约：{title, choice}；同时兼容直接传完整事件对象 {event, choice}
    title: str = ""
    event: dict = {}
    choice: int = 0


class SlotReq(BaseModel):
    slot: int = 1


class DecreePolishReq(BaseModel):
    """圣旨润色 / 批改诏草（迁移补齐：原 Tk `_panel_decree_entry`）。"""
    raw_intent: str = ""
    draft_id: str = ""          # 非空 = 批改已有诏草（回写正文/题名/效果）
    org_hint: str = "政府"
    source_minister: str = ""


class DecreeDraftReq(BaseModel):
    """润色稿入待签队列（供三省会签）。"""
    draft: dict = {}


class DecreeDiscardReq(BaseModel):
    draft_id: str = ""


class CouncilReviewReq(BaseModel):
    draft_id: str


class AiConfigReq(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    # 迁移补齐：大臣办差工具（function calling）三档（auto/on/off），对齐 Tk 设置面板
    enable_tools: str = ""

class FetchModelsReq(BaseModel):
    api_key: str = ""
    base_url: str = ""


@app.get("/health")
def health():
    return {"ok": True, "backend": "python-reference", "has_state": _state is not None}


@app.post("/api/new_game")
def api_new_game(req: NewGameReq, request: Request):
    global _state
    _require_auth(request)
    with _lock:
        _state = _backend.new_game(req.difficulty, _get_ai())
        return {"state": _state_to_dict(_state)}


@app.post("/api/advance")
def api_advance(request: Request):
    global _state
    _require_auth(request)
    _require_state()
    with _lock:
        events, log, report, _state = _backend.advance(_state, _get_ai())
        # 审查 P1-12：缓存本回合完整事件对象（含 choices），供 /api/resolve_event 按 title
        # 反查（前端契约只传 title）。下划线前缀字段由 _state_to_dict 过滤，不下发。
        try:
            _state._frontend_events = {
                str(e.get("title", "")): e for e in (events or []) if isinstance(e, dict)}
        except Exception:
            pass
        return {"events": _json_safe(events), "log": _json_safe(log),
                "report": report, "state": _state_to_dict(_state)}


@app.post("/api/action")
def api_action(req: ActionReq, request: Request):
    global _state
    _require_auth(request)
    _require_state()
    with _lock:
        try:
            message, _state = _backend.action(_state, req.action, req.params, _get_ai())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"message": message, "state": _state_to_dict(_state)}


@app.post("/api/resolve_event")
def api_resolve_event(req: ResolveReq, request: Request):
    global _state
    _require_auth(request)
    _require_state()
    with _lock:
        ev = req.event or _find_frontend_event(_state, req.title)
        if not isinstance(ev, dict) or not ev:
            raise HTTPException(
                status_code=404,
                detail=f"事件「{req.title}」不在场或已处置（无法取得选项）")
        message, _state = _backend.resolve_event(
            _state, ev, req.choice, _get_ai())
        return {"message": message, "state": _state_to_dict(_state)}


@app.post("/api/save")
def api_save(req: SlotReq, request: Request):
    _require_auth(request)
    _require_state()
    with _lock:
        _backend.save(_state, req.slot)
        return {"ok": True, "slot": req.slot}


@app.post("/api/load")
def api_load(req: SlotReq, request: Request):
    global _state
    _require_auth(request)
    with _lock:
        _state = _backend.load(req.slot)
        return {"state": _state_to_dict(_state)}


@app.get("/api/save_slots")
def api_save_slots(request: Request):
    # 审查 P3：补鉴权（原缺 _require_auth，配置 token 后仍可未授权读盘面）
    _require_auth(request)
    with _lock:
        return {"slots": _json_safe(_backend.save_slots())}


@app.get("/api/readouts")
def api_readouts(request: Request):
    """只读派生读数（军政/会计/仓廪面板用）。

    薄壳纪律：仅调用 GameState 现有方法并序列化，零业务逻辑复制。
    army_units / central_arsenal 为对象，_state_to_dict 无法序列化，故在此展开。
    """
    # 审查补齐：本端点原漏鉴权，在设 SONGZUO_SERVER_TOKEN（或非本机部署由
    # main() 强制要求）时仍匿名可读军政/会计/群臣档案。此处与其他端点同规。
    _require_auth(request)
    _require_state()
    with _lock:
        s = _state
        try:
            s._derive_defense_lines()
        except Exception:
            pass
        army = []
        for u in getattr(s, "army_units", []) or []:
            try:
                army.append({
                    "unit_id": u.unit_id, "name": u.name, "tier": u.tier,
                    "branches": dict(u.branches), "troops": u.troops,
                    "station": u.station, "defense_line": u.defense_line,
                    "morale": u.morale, "training": u.training,
                    "equip_rate": round(u.equip_rate(), 3),
                    "army_name": u.army_name, "org_arm": u.org_arm,
                    "scale": u.scale, "serial": u.serial,
                })
            except Exception:
                continue
        arsenal = {}
        ca = getattr(s, "central_arsenal", None)
        if ca is not None:
            arsenal = dict(getattr(ca, "stock", {}) or {})
        try:
            finance = _json_safe(s.finance_readout())
        except Exception:
            finance = {}
        try:
            from core.flow_summary import build_flow_summary
            flow = _json_safe(build_flow_summary(s))
        except Exception:
            flow = {}
        try:
            granary = {
                "monthly": s.calc_monthly_grain()[0],
                "army": s.calc_army_grain()[0],
                "official": s.calc_official_grain()[0],
                "clerk": s.calc_clerk_grain()[0],
                "capacity_used": s.granary_capacity_used(),
            }
        except Exception:
            granary = {}
        # 迁移补齐（原 Tk panels_govern `_render_briefing`）：朝局简报可行动项
        # （纯程序派生、零 AI、只读；Web 端据此渲染「前往」跳转）
        try:
            from core.briefing import build_briefing_actions
            briefing = _json_safe(build_briefing_actions(s))
        except Exception:
            briefing = []
        # 迁移补齐（原 Tk 大臣卡片信息密度）：群臣档案（年龄/职衔/派系/性格一句话/生平）
        # —— 单一权威源 core/minister_profile.py（Tk 废弃后由面板与后端内联下沉而来）
        try:
            from core.minister_profile import build_minister_profiles
            ministers = build_minister_profiles(s)
        except Exception:
            ministers = {}
        return {
            "army": army,
            "arsenal": arsenal,
            "finance": finance,
            "flow": flow,
            "granary": granary,
            "briefing": briefing,
            "ministers": ministers,
            "defense_lines": _json_safe(s.defense_lines),
        }


@app.get("/api/meter")
def api_meter(request: Request):
    """Token 计量表（迁移补齐：原 Tk panels_meta `_panel_token_meter`）。

    数据源：服务端 AIClient.meter_summary()（按契约方法分桶）+ state._dialogue_stats
    （召对预过滤/缓存命中与 AI 调用次数）+ state.ai_token_log（历史回合用量）。
    分组映射由 ai/token_meter.grouped_meter_rows 提供（单一权威源，Tk/Web 共用）。
    """
    _require_auth(request)
    _require_state()
    with _lock:
        from ai.token_meter import grouped_meter_rows
        ai = _get_ai()
        rows = grouped_meter_rows(ai, getattr(_state, "_dialogue_stats", None))
        total = {}
        try:
            total = (ai.meter_summary() or {}).get("total", {}) if ai is not None else {}
        except Exception:
            total = {}
        return {
            "rows": _json_safe(rows),
            "total": _json_safe(total),
            "token_log": _json_safe(getattr(_state, "ai_token_log", []) or []),
        }


@app.post("/api/meter/reset")
def api_meter_reset(request: Request):
    """清零 Token 计量（客户端分桶 + 召对命中统计）。"""
    _require_auth(request)
    _require_state()
    with _lock:
        ai = _get_ai()
        try:
            if ai is not None and hasattr(ai, "reset_meter"):
                ai.reset_meter()
        except Exception:
            pass
        st = getattr(_state, "_dialogue_stats", None)
        if isinstance(st, dict):
            st.update({"prefilter_hits": 0, "cache_hits": 0, "ai_calls": 0})
        return {"ok": True}


@app.post("/api/conclude")
def api_conclude(request: Request):
    _require_auth(request)
    _require_state()
    with _lock:
        eval_result, ai_eval = _backend.conclude(_state, _get_ai())
        return {"eval": _json_safe(eval_result), "ai_eval": ai_eval}


@app.post("/api/council_review")
def api_council_review(req: CouncilReviewReq, request: Request):
    """三省会签推演（票拟批红用）。

    薄壳纪律：只调 AIClient.council_review 并序列化，零业务逻辑复制。
    先查 council_reviews 缓存（随存档持久化），命中即复用，避免重复推演耗 token。
    AI 不可用 → 返回规则兜底（明确标注，不伪造 AI 文本），与旧版 Tk 行为一致。
    """
    _require_auth(request)
    _require_state()
    with _lock:
        draft = _state.get_edict_draft(req.draft_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="诏草已不存在。")
        cached = getattr(_state, "council_reviews", {}).get(req.draft_id)
        if cached:
            return {"review": _json_safe(cached), "cached": True}
        ai = _get_ai()
        rev = None
        if ai and getattr(ai, "available", False):
            try:
                rev = ai.council_review(draft, _state.get_state_summary(), state=_state)
            except Exception:
                rev = None
        if not rev:
            rev = {"memo": "（会签不可用）", "objections": "（门下省未见条目）",
                   "executions": "（六部俟旨）", "verdict": "可准", "revised_effects": []}
        _state.store_council_review(req.draft_id, rev)
        return {"review": _json_safe(rev), "cached": False}


@app.post("/api/decree/polish")
def api_decree_polish(req: DecreePolishReq, request: Request):
    """圣旨润色 / 批改诏草（迁移补齐：原 Tk `_panel_decree_entry` 的润色与诏草批改）。

    薄壳：AI 润色走 AIClient.polish_decree（严格契约 + 兜底），零业务逻辑复制；
    draft_id 非空时把结果回写该诏草并清会签缓存（重入待签）。AI 未接入 → 明确 409。
    """
    _require_auth(request)
    _require_state()
    with _lock:
        ai = _get_ai()
        if ai is None or not getattr(ai, "available", False):
            raise HTTPException(status_code=409, detail="AI 未接入：请先在设置中配置 OpenAI 兼容 API")
        text = (req.raw_intent or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="诏意不可为空")
        summary = _state.get_state_summary()
        try:
            out = ai.polish_decree(text, summary)
        except Exception as e:  # noqa: BLE001
            # 异常类名/原文只入服务端日志，不下发界面（界面一律中文）
            print(f"[server] 诏书润色中断: {e!r}", flush=True)
            raise HTTPException(status_code=502, detail="AI 词臣一时未有回音，请稍后再试。")
        if not isinstance(out, dict) or out.get("_error"):
            raise HTTPException(status_code=502, detail="润色未通过契约校验（可重试）")
        out["org_hint"] = req.org_hint or out.get("org_hint") or "政府"
        if req.source_minister:
            out["source_minister"] = req.source_minister
        if req.draft_id:
            d = _state.get_edict_draft(req.draft_id)
            if d is None:
                raise HTTPException(status_code=404, detail="诏草已不存在")
            for k in ("title", "effects", "org_hint", "source_minister"):
                if out.get(k) is not None:
                    d[k] = out[k]
            if out.get("body"):
                d["body"] = out["body"]
            try:
                _state.store_council_review(req.draft_id, {})   # 清缓存：批改后重入待签
            except Exception:
                pass
            return {"draft": _json_safe(d), "state": _state_to_dict(_state)}
        return {"draft": _json_safe(out)}


@app.post("/api/decree/draft")
def api_decree_draft(req: DecreeDraftReq, request: Request):
    """润色稿入待签队列（迁移补齐：Tk「入待签」→ GameState.add_edict_draft）。"""
    _require_auth(request)
    _require_state()
    with _lock:
        if not isinstance(req.draft, dict) or not req.draft:
            raise HTTPException(status_code=400, detail="诏草不可为空")
        did = _state.add_edict_draft(dict(req.draft))
        return {"draft_id": did, "draft": _json_safe(_state.get_edict_draft(did) or {}),
                "state": _state_to_dict(_state)}


@app.post("/api/decree/discard")
def api_decree_discard(req: DecreeDiscardReq, request: Request):
    """弃删诏草（迁移补齐：Tk「弃删」→ GameState.remove_edict_draft）。"""
    _require_auth(request)
    _require_state()
    with _lock:
        d = _state.get_edict_draft(req.draft_id)
        if d is None:
            raise HTTPException(status_code=404, detail="诏草已不存在")
        _state.remove_edict_draft(req.draft_id)
        return {"ok": True, "title": str(d.get("title", "")),
                "state": _state_to_dict(_state)}


@app.post("/api/monthly_report")
def api_monthly_report(request: Request):
    """月折（奏报摘要，迁移补齐：Tk「奏报摘要」tab）。

    AI 失败/未接入 → 本地模板 + 结构化真值兜底（与 /api/advance 的 report 同源，不伪造）。
    """
    _require_auth(request)
    _require_state()
    with _lock:
        from core.commands import _monthly_report_text
        try:
            text = _monthly_report_text(_state, _get_ai())
        except Exception as e:  # noqa: BLE001
            print(f"[server] 月折生成失败: {e!r}", flush=True)
            raise HTTPException(status_code=502, detail="月折未能草就，请稍后再试。")
        return {"report": text}


def _ai_config_path() -> str:
    return os.path.join(_app_root(), "ai_config.json")


@app.get("/api/ai_config")
def api_ai_config_get(request: Request):
    """读 AI 配置（设置面板预填；不回传完整 key，只回是否已配）。

    审查 P3：补鉴权（原缺 _require_auth，配置 token 后仍可未授权读取 base_url/model）。
    """
    _require_auth(request)
    try:
        with open(_ai_config_path(), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        key = str(cfg.get("api_key", "") or "")
        return {
            "configured": bool(key),
            "api_key_masked": (key[:4] + "…" + key[-4:]) if len(key) > 8 else "",
            "base_url": str(cfg.get("base_url", "") or ""),
            "model": str(cfg.get("model", "") or ""),
            "enable_tools": str(cfg.get("enable_tools", "") or "auto"),
        }
    except Exception:
        return {"configured": False, "api_key_masked": "", "base_url": "",
                "model": "", "enable_tools": "auto"}


@app.post("/api/fetch_models")
def api_fetch_models(req: FetchModelsReq, request: Request):
    """根据输入的 Key 与 Base URL，智能探测并拉取远程支持的模型列表。"""
    _require_auth(request)
    try:
        from ai.client import AIClient
        key = req.api_key.strip()
        # 若未填 key，尝试读已有配置
        if not key:
            try:
                with open(_ai_config_path(), "r", encoding="utf-8") as f:
                    key = str(json.load(f).get("api_key", "") or "").strip()
            except Exception: pass
        client = AIClient(api_key=key, base_url=req.base_url)
        models = client.fetch_available_models()
        return {"ok": True, "models": models}
    except Exception as e:  # noqa: BLE001
        # 不回传完整异常栈/URL 细节给客户端
        return {"ok": False, "models": [], "error": type(e).__name__}


@app.post("/api/ai_config")
def api_ai_config_set(req: AiConfigReq, request: Request):
    """写 AI 配置并重建服务端 AI 客户端（设置面板保存）。"""
    global _ai
    _require_auth(request)
    with _lock:
        old_cfg = {}
        try:
            with open(_ai_config_path(), "r", encoding="utf-8") as f:
                old_cfg = json.load(f)
        except Exception: pass
        
        # 若传入 key 为空但已有 key，保持已有 key 不被洗掉
        key_to_save = req.api_key.strip() or str(old_cfg.get("api_key", "") or "")
        cfg = {"api_key": key_to_save, "base_url": req.base_url.strip(), "model": req.model.strip(),
               # 迁移补齐：办差工具三档（未传则沿用旧值/auto）
               "enable_tools": (req.enable_tools.strip()
                                or str(old_cfg.get("enable_tools", "") or "auto"))}
        with open(_ai_config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        _ai = None  # 重建客户端
        client = _get_ai()
        # 强制做一次在线真实探测
        ok, msg = False, "未配置"
        if client:
            ok, msg = client.probe(force=True)
        return {
            "ok": True,
            "available": ok,
            "message": msg,
            "has_key": bool(key_to_save),
            "base_url": cfg["base_url"],
            "model": cfg["model"]
        }


def main() -> None:
    host = os.environ.get("SONGZUO_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("SONGZUO_SERVER_PORT", "8080"))
    # 审查 P0：禁止无 token 时绑非本机地址（防局域网/公网裸奔）
    if host not in ("127.0.0.1", "localhost", "::1") and not _AUTH_TOKEN:
        raise SystemExit(
            f"拒绝启动：host={host} 非本机回环，必须设置环境变量 SONGZUO_SERVER_TOKEN"
        )
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    sys.exit(main() or 0)
