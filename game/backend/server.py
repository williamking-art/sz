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
- AI 可选（**2026-09-18 勘误**）：服务端按 ai_config.json 构建 AIClient。**但回合推演
  是全游戏级强制 AI**——未配置时 `core.commands` 按「拒绝式」抛 `AIRuntimeError`
  （见 `core/commands.py:251-259`），本服务据此回 **503 ＋ 结构化错误码**
  （`AI_ERROR_CODES` 6 码之一），**绝不伪造在线结果**；"本地降级模板"只适用于
  **叙事文本**（`ai/narrative_fallback.py`），不适用于数值推演。
- 状态快照：vars(state) 逐字段 JSON 安全过滤（不可序列化字段跳过，
  重建端以 GameState 构造默认值兜底——与 HttpBackend._to_state 对称）。

运行：python -m backend.server   （端口/地址见环境变量，默认 127.0.0.1:8080）
依赖：fastapi + uvicorn（见 requirements-extras.txt；未安装则本模块不可导入）
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import sys
import tempfile
import threading
import urllib.parse

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from ai.client import AIClient
from ai.client_utils import validate_outbound_url
from backend.client import LocalBackend, _app_root
from core.errors import AIRuntimeError

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Songzuo Reference Backend", version="1.0")

log = logging.getLogger("backend.server")

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
# 审查 P1-3：ai_config.json 的读-改-写单独串行化（与游戏主锁分离，避免长联网持锁）
_config_lock = threading.Lock()
_backend = LocalBackend()
_state = None          # 当前 GameState（服务端持有）
_ai = None             # 服务端 AIClient（可禁用）

#: 可选鉴权 token（环境变量）；仅本机回环且未设 token 时放行（兼容单机联调）
_AUTH_TOKEN = (os.environ.get("SONGZUO_SERVER_TOKEN") or "").strip()


def _client_is_loopback(request) -> bool:
    """请求来源是否为本机回环（用于「未配 token 时的兜底放行」判定）。"""
    client = getattr(request, "client", None)
    host = str(getattr(client, "host", "") or "")
    if not host:
        return False
    if host in ("localhost",):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _require_auth(request) -> None:
    """鉴权（安全审查 A4）。

    规则与 Rust 端 auth_mw 同构：
      - 已配置 SONGZUO_SERVER_TOKEN：必须携带匹配的 `Authorization: Bearer <token>`
        （比较用 hmac.compare_digest，避免时序侧信道）；
      - 未配置：**仅放行本机回环来源**。

    修复前：未配 token 即 `return` 全放行，而「非回环必须设 token」的校验只写在
    `main()` 里 —— 用 `uvicorn backend.server:app --host 0.0.0.0`（或任意 ASGI
    服务器挂载 `app`）即可绕过，非回环部署下所有 /api/* 匿名可用。
    """
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if _AUTH_TOKEN:
        if hmac.compare_digest(auth, f"Bearer {_AUTH_TOKEN}"):
            return
        raise HTTPException(status_code=401, detail="令符不合，未获授权。")
    if _client_is_loopback(request):
        return
    raise HTTPException(
        status_code=401,
        detail="服务端未配置 SONGZUO_SERVER_TOKEN，且来源非本机，拒绝访问。",
    )


def _validate_base_url(url: str) -> str:
    """校验 AI base_url（审查 P1-2 SSRF 加固）。

    规则（详见 ai.client_utils.validate_outbound_url）：
      - 仅 http/https，必须含主机名；
      - 拒绝 userinfo（`user:pass@host`）；
      - 拒绝回环 127/8、::1；RFC1918 私网；link-local 169.254/16、fe80::/10；
        云 metadata 169.254.169.254；multicast；unspecified 0.0.0.0/::；
      - 域名先 DNS 解析，任一解析地址落入上述禁用段即拒（DNS rebinding）；
      - 可选 provider 白名单（SONGZUO_AI_HOST_ALLOWLIST）优先约束。
    不合法抛 400；合法返回原 URL。
    """
    try:
        return validate_outbound_url(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


#: ai_config.json 受本端点管理的字段（其余键——fallback/settle/未来扩展——PATCH 保留）
_AI_CONFIG_MANAGED_FIELDS = ("api_key", "base_url", "model", "enable_tools")
#: 兼容既有配置的选填 provider 字段（统一 schema，round-trip 不丢）
_AI_CONFIG_OPTIONAL_FIELDS = (
    "settle_api_key", "settle_base_url", "settle_model",
    "fallback_api_key", "fallback_base_url", "fallback_model",
)


def _load_ai_config() -> dict:
    """读取 ai_config.json；缺失/损坏返回 {}（不抛，避免端点 500）。"""
    try:
        with open(_ai_config_path(), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def _client_from_config(cfg: dict) -> AIClient:
    """按配置字典构造 AIClient（主 + fallback + settle 全字段，统一 schema）。"""
    cfg = cfg if isinstance(cfg, dict) else {}
    return AIClient(
        api_key=str(cfg.get("api_key", "") or ""),
        base_url=str(cfg.get("base_url", "") or ""),
        model=str(cfg.get("model", "") or ""),
        enable_tools=str(cfg.get("enable_tools", "") or "auto"),
        settle_api_key=str(cfg.get("settle_api_key", "") or ""),
        settle_base_url=str(cfg.get("settle_base_url", "") or ""),
        settle_model=str(cfg.get("settle_model", "") or ""),
        fallback_api_key=str(cfg.get("fallback_api_key", "") or ""),
        fallback_base_url=str(cfg.get("fallback_base_url", "") or ""),
        fallback_model=str(cfg.get("fallback_model", "") or ""),
    )


def _atomic_write_json(path: str, data: dict) -> None:
    """临时文件 + fsync + os.replace 原子落盘；失败清理临时文件、保留旧文件。"""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".ai_config.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        tmp = None
        try:
            _dfd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(_dfd)
            finally:
                os.close(_dfd)
        except OSError:
            pass
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _key_id(key: str) -> str:
    """服务端生成的稳定 key 指纹（sha256 前 8 位）；不回传任何 key 片段。"""
    k = str(key or "")
    if not k:
        return ""
    return hashlib.sha256(k.encode("utf-8")).hexdigest()[:8]


def _merge_ai_config(req, old_cfg: dict) -> dict:
    """PATCH/merge 语义：以旧配置为底，只覆盖本次显式提交的字段。

    - api_key 为空视为「保持旧 key」（设置面板不回显 key，空提交不得洗掉密钥）；
    - base_url 非空才覆盖，且先过 SSRF 校验；
    - model/enable_tools 仅在显式提交且非空时覆盖；
    - fallback/settle/未知字段一律原样保留（P2-14）。
    """
    merged = dict(old_cfg) if isinstance(old_cfg, dict) else {}
    try:
        fields = set(getattr(req, "model_fields_set", None) or ())
    except Exception:
        fields = set()
    # 兼容用 __new__/dict 构造的请求替身：字段集合为空时按「全部显式」处理
    _explicit = (lambda name: (not fields) or (name in fields))
    key_in = str(getattr(req, "api_key", "") or "").strip()
    if _explicit("api_key") and key_in:
        merged["api_key"] = key_in
    base_in = str(getattr(req, "base_url", "") or "").strip()
    if base_in:
        merged["base_url"] = _validate_base_url(base_in)
    model_in = str(getattr(req, "model", "") or "").strip()
    if _explicit("model") and model_in:
        merged["model"] = model_in
    tools_in = str(getattr(req, "enable_tools", "") or "").strip()
    if _explicit("enable_tools") and tools_in in ("auto", "on", "off", "simple"):
        merged["enable_tools"] = tools_in
    merged.setdefault("enable_tools", "auto")
    return merged


def _build_ai() -> AIClient:
    """按 ai_config.json 构建服务端 AI 客户端；无配置/无 key → 禁用客户端。"""
    try:
        return _client_from_config(_load_ai_config())
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
        if k == "_ai_failures" and isinstance(v, list):
            # 审查修复（AI 失败对玩家全静默）：各 Agent 契约失败只写 state._ai_failures，
            # 而该字段以 `_` 前缀被快照过滤、且全库无读取方 → 除 economy（拒绝式）外，
            # 「本月哪几项推演未成、已走本地兜底」玩家完全无从得知。
            # 此处按公开名 ai_failures 下发**仅 agent 名**（异常原文属技术细节，只留服务端日志，
            # 故不随快照外发），由前端以中文提示呈现。
            _names = [str((d or {}).get("agent", "")).strip() for d in v[-8:]]
            out["ai_failures"] = [n for n in _names if n]
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
    # D 修复（并发一致性）：状态判空必须与后续读写同在锁内。原实现在 `with _lock`
    # **之前**调用 _require_state()，而 `_state` 在锁内被 advance/load 重新赋值 →
    # 并发请求可能读到刚被替换/尚未替换的旧对象（「刚 load 完却判未开局 409」或
    # 对旧 state 执行动作）。
    with _lock:
        _require_state()
        try:
            events, log, report, _state = _backend.advance(_state, _get_ai())
        except AIRuntimeError as e:
            # 审查 I-2 / E-2 修复（2026-09-18）：回合推演是「全游戏级强制 AI → 拒绝式」，
            # 原先此处无人接管 → FastAPI 回 500 裸 "Internal Server Error"。
            # 现映射为 503 ＋ 结构化错误码（AI_ERROR_CODES 6 码之一）。
            # 异常来源（2026-09-21 重审 M-1 更正）：三段式下 `advance_two_phase` **首段
            # AI 预检**（AI 缺失/未配置 → code=AI_NOT_CONFIGURED，不 spawn daemon），
            # 以及旧同步路径 `settle_turn` / `advance_and_settle` 的拒绝式。
            raise HTTPException(
                status_code=503,
                detail={
                    "error_code": getattr(e, "code", "") or "AI_RUNTIME_ERROR",
                    "message": str(e) or "AI 推演失败：请检查 AI 配置或网络后重试。",
                },
            ) from e
        # 审查 P1-12：缓存本回合完整事件对象（含 choices），供 /api/resolve_event 按 title
        # 反查（前端契约只传 title）。下划线前缀字段由 _state_to_dict 过滤，不下发。
        try:
            _state._frontend_events = {
                str(e.get("title", "")): e for e in (events or []) if isinstance(e, dict)}
            # P1-29：同时按 id 索引——同名事件/标题改写时仍可精确定位
            for e in (events or []):
                if isinstance(e, dict) and e.get("id"):
                    _state._frontend_events[str(e["id"])] = e
        except Exception:
            pass
        return {"events": _json_safe(events), "log": _json_safe(log),
                "report": report, "state": _state_to_dict(_state)}


@app.get("/api/advance/round2")
def api_advance_round2(request: Request):
    """**两段式回合推进 round2 轮询**（2026-09-21「民间情况先行」）。

    首段 `/api/advance` 已同步返回程序真值月报（民间情况立即可读）；round2 daemon
    线程在后台跑 AI 月报/奏章富化，完成后置 `state.rich_ready`。前端每 4s 轮询本端点，
    `ready=true` 且 `rich_report` 非空 → 就地替换月报富文本段（阅读不中断）。
    """
    _require_auth(request)
    with _lock:
        s = _require_state()
        return {"ready": bool(getattr(s, "rich_ready", False)),
                "rich_report": str(getattr(s, "rich_report", "") or ""),
                "rich_report_scenes": _json_safe(list(getattr(s, "rich_report_scenes", None) or [])),
                "rich_civilian": str(getattr(s, "rich_civilian", "") or ""),
                "rich_civilian_scenes": _json_safe(list(getattr(s, "rich_civilian_scenes", None) or [])),
                "settle_error": str(getattr(s, "settle_error", "") or ""),
                "log": _json_safe(list(getattr(s, "_last_settle_log", None) or [])),
                # 后台结算完成的最新快照（供回合报告弹窗用 before/after 差值）
                "state": _state_to_dict(s)}


class ProposeProjectReq(BaseModel):
    route: str
    name: str = ""
    key: str = ""
    levels: int = 1


@app.post("/api/project/propose")
def api_project_propose(req: ProposeProjectReq, request: Request):
    """营建立项（工程系统）：蓝图/政府建筑 → `state.projects`（status=proposed）。

    校验（蓝图登记 / 科技前置 / **地利前置** / 国库）失败 → 400 + 可读原因（拒绝式，不立项）。
    立项后由 `_settle_projects` 五态状态机逐月推进，完工时落成 `prefectures[route]["buildings"]`。
    """
    global _state
    _require_auth(request)
    with _lock:
        s0 = _require_state()
        from core.construction import propose_project
        res = propose_project(s0, req.route, req.name, req.key or None, req.levels)
        if not res.get("ok"):
            raise HTTPException(status_code=400,
                                detail="；".join(res.get("errors") or ["立项被拒"]))
        return {
            "message": f"{res.get('name') or req.name} 已立项（工期 {res.get('months')} 月，"
                       f"需 {int(res.get('cost') or 0):,} 贯）",
            "project_id": res.get("pid"),
            "state": _state_to_dict(s0),
        }


@app.post("/api/action")
def api_action(req: ActionReq, request: Request):
    global _state
    _require_auth(request)
    # D 修复（并发一致性）：状态判空必须与后续读写同在锁内。原实现在 `with _lock`
    # **之前**调用 _require_state()，而 `_state` 在锁内被 advance/load 重新赋值 →
    # 并发请求可能读到刚被替换/尚未替换的旧对象（「刚 load 完却判未开局 409」或
    # 对旧 state 执行动作）。
    with _lock:
        _require_state()
        try:
            message, _state = _backend.action(_state, req.action, req.params, _get_ai())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except AIRuntimeError as e:
            # 同上（I-2 / E-2）：动作路径同样可能触发 AI 拒绝式失败（拟诏解析等）。
            raise HTTPException(
                status_code=503,
                detail={
                    "error_code": getattr(e, "code", "") or "AI_RUNTIME_ERROR",
                    "message": str(e) or "AI 推演失败：请检查 AI 配置或网络后重试。",
                },
            ) from e
        return {"message": message, "state": _state_to_dict(_state)}


@app.post("/api/resolve_event")
def api_resolve_event(req: ResolveReq, request: Request):
    global _state
    _require_auth(request)
    # D 修复（并发一致性）：状态判空必须与后续读写同在锁内。原实现在 `with _lock`
    # **之前**调用 _require_state()，而 `_state` 在锁内被 advance/load 重新赋值 →
    # 并发请求可能读到刚被替换/尚未替换的旧对象（「刚 load 完却判未开局 409」或
    # 对旧 state 执行动作）。
    with _lock:
        _require_state()
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
    # D 修复（并发一致性）：状态判空必须与后续读写同在锁内。原实现在 `with _lock`
    # **之前**调用 _require_state()，而 `_state` 在锁内被 advance/load 重新赋值 →
    # 并发请求可能读到刚被替换/尚未替换的旧对象（「刚 load 完却判未开局 409」或
    # 对旧 state 执行动作）。
    with _lock:
        _require_state()
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
    # D 修复（并发一致性）：状态判空必须与后续读写同在锁内。原实现在 `with _lock`
    # **之前**调用 _require_state()，而 `_state` 在锁内被 advance/load 重新赋值 →
    # 并发请求可能读到刚被替换/尚未替换的旧对象（「刚 load 完却判未开局 409」或
    # 对旧 state 执行动作）。
    with _lock:
        _require_state()
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
                    # 阶段 B-3：装备**实物明细**（7 项）＋ 该军累计**欠饷**（贯），
                    # 供前端"点开某军 → 明细窗"显示人员/兵种/装备/士气/欠饷。
                    "equip": dict(getattr(u, "equip", {}) or {}),
                    "arrears": int(getattr(u, "arrears", 0) or 0),
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
        # 税基 / 免役口径（阶段 C-4，§13.6）：让"冗官 → 免役 → 税基萎缩"这条链可见。
        # 薄壳纪律：只调 GameState 的只读派生视图。
        try:
            tax_base = _json_safe(s.tax_base_summary())
        except Exception:
            tax_base = {}
        # 吏制派生视图（阶段 C-5，§16）：吏额/冗吏率/吏禄充足/把持度/吏怨/有效吏力/定性四档。
        # 吏不具名（§16.9）；面板据此渲染「吏治」一行与「该路吏胥把持」的诊断。
        try:
            from core.clerks import totals as _clerk_totals
            clerks = _json_safe(_clerk_totals(s))
        except Exception:
            clerks = {}
        # 编制参数（阶段 C-7，§12.3/§17.4）：面板据此渲染"改革完成度"读数；
        # AI 经 free_effect 的 `institution` 字段提议改动（值域由 core/institution 单点约束）。
        try:
            from core.institution import describe as _inst_describe
            institution = _json_safe(_inst_describe(s))
        except Exception:
            institution = {}
        # 州路简报（只读派生，core/region_brief.py 为单一权威源）：民生/粮储/到账月税/
        # 驻军月饷/风险分一体下发，供前端「州县」面板排序与"为何危险"的可解释展示。
        # 薄壳纪律：只调 core 的只读派生函数，算法不在此复制。
        try:
            from core.region_brief import build_region_brief
            regions = _json_safe(build_region_brief(s))
        except Exception:
            regions = {}
        # 局势投影（只读，core/situations.py 单一权威源）：把既有长期项
        # （帝修/国策/长期诏/活跃事件）聚合成统一局势视图；缺失维度下发 None（前端示"未定义"）。
        # 薄壳纪律：只调 core 只读投影，不在此复制映射规则。
        try:
            from core.situations import build_situation_readout
            situations = _json_safe(build_situation_readout(s))
        except Exception:
            situations = {"items": [], "by_status": {}, "readout_status": "partial",
                          "readout_errors": ["situations: 投影失败"]}
        return {
            "army": army,
            "arsenal": arsenal,
            "finance": finance,
            "flow": flow,
            "granary": granary,
            "briefing": briefing,
            "ministers": ministers,
            "tax_base": tax_base,
            "clerks": clerks,
            "institution": institution,
            "regions": regions,
            "situations": situations,
            "defense_lines": _json_safe(s.defense_lines),
        }


@app.get("/api/memory")
def api_memory(request: Request, minister: str = "", limit: int = 60):
    """记忆库只读视图 —— 玩家可见「AI 到底记住了什么」。

    数据源：GameState.memory（MemoryGraph，SQLite 一轮一库）+ 对话记忆库
    （DialogueMemory，slot_{slot}_dialogue.db）。
    薄壳纪律：只调两库既有**只读**接口（query_summaries/query_sql/query_change_log/
    list_summaries/list_sessions/list_dialogues），零写操作、零业务逻辑复制。
    脱敏与截断：记忆库只存语义实体（人/事/机构/关系），不含经济真值；此处再对
    note/概要/日志做长度截断，防超长文本灌入前端。

    `minister` 非空时为**会话视图**（召对面板内嵌记忆库侧栏用）：额外返回该大臣的
    完整会话流（`dialogues`，含 `speaker="朕"` 的陛下之言）与其按期纪要
    （`dialogue_summaries` 收窄到该人）、涉该人的近关系（`minister_relations`）；
    不给 `minister` 即全局视图（独立记忆库面板用），契约不变。
    """
    _require_auth(request)
    minister = (minister or "").strip()
    limit = max(1, min(200, int(limit or 60)))
    with _lock:
        _require_state()
        s = _state
        mg = getattr(s, "memory", None)
        if mg is None:
            return {"turn": 0, "state_turn": int(getattr(s, "turn", 0) or 0),
                    "entity_counts": {}, "relation_total": 0, "relation_archived": 0,
                    "summaries": [], "recent": [], "dialogue_summaries": [],
                    "change_log": [], "minister": minister, "sessions": [],
                    "dialogues": [], "minister_relations": []}
        slot = getattr(mg, "_slot", None)
        if slot is None:
            slot = getattr(s, "memory_slot", None)
        counts: dict = {}
        for e in (mg.entities or {}).values():
            if not isinstance(e, dict):
                continue
            key = str(e.get("type", "?"))
            counts[key] = counts.get(key, 0) + 1
        # 概要层（compress/summarize_period 产物）
        summaries = []
        try:
            for row in mg.query_summaries(top_k=8, slot=slot) or []:
                attrs = row.get("attrs") or {}
                top = attrs.get("top_relations") or []
                summaries.append({
                    "eid": str(row.get("eid", "")),
                    "kind": str(row.get("stype", "")),
                    "period": row.get("period"),
                    "name": str(row.get("name", "")),
                    "turn": int(row.get("created_turn", 0) or 0),
                    "relation_count": int(attrs.get("relation_count", 0) or 0),
                    "decision_count": int(attrs.get("decision_count", 0) or 0),
                    "event_count": int(attrs.get("event_count", 0) or 0),
                    "highlights": [str(x)[:60] for x in top[:5]],
                })
        except Exception:
            summaries = []
        # 细节层：近 24 回合关系（query_sql 自身跳过 archived）
        names = {eid: str(e.get("name", eid))
                 for eid, e in (mg.entities or {}).items() if isinstance(e, dict)}
        recent = []
        try:
            for src, dst, rtype, w, note in (mg.query_sql(time_window=24, top_k=12,
                                                           slot=slot) or []):
                recent.append({
                    "src": names.get(src, src), "dst": names.get(dst, dst),
                    "rtype": str(rtype), "weight": round(float(w), 3),
                    "note": str(note or "")[:60],
                })
        except Exception:
            recent = []
        # 对话记忆库概要（召对：人 + 立场/主题）；minister 非空时收窄到该大臣
        dialogue = []
        sessions = []
        dialogues: list = []
        try:
            from memory.dialogue_memory import get_dialogue_memory
            dm = get_dialogue_memory(s)
            sessions = _json_safe(dm.list_sessions())
            if minister:
                dialogue = _json_safe(dm.list_summaries(minister=minister, limit=12))
                dialogues = _json_safe(dm.list_dialogues(minister=minister, limit=limit))
            else:
                dialogue = _json_safe(dm.list_summaries(limit=12))
        except Exception:
            dialogue, sessions, dialogues = [], [], []
        # 变更日志（审计/回放）
        try:
            change_log = mg.query_change_log(limit=20, slot=slot) or []
        except Exception:
            change_log = []
        # 涉该大臣的近关系（会话视图：侧栏「相关关系」；按实体名精确匹配，非模糊）
        minister_relations = []
        if minister:
            for r in recent:
                if r["src"] == minister or r["dst"] == minister or minister in r["note"]:
                    minister_relations.append(r)
        return {
            "turn": int(getattr(mg, "turn", 0) or 0),
            "state_turn": int(getattr(s, "turn", 0) or 0),
            "entity_counts": counts,
            "relation_total": len(mg.relations or []),
            "relation_archived": sum(1 for r in (mg.relations or [])
                                     if isinstance(r, dict) and r.get("archived")),
            "summaries": summaries,
            "recent": recent,
            "dialogue_summaries": dialogue,
            "change_log": [{"turn": r.get("turn"), "action": r.get("action"),
                            "detail": str(r.get("detail", ""))[:80],
                            "ts": r.get("ts")} for r in change_log],
            "minister": minister,
            "sessions": sessions,
            "dialogues": dialogues,
            "minister_relations": minister_relations,
        }


@app.get("/api/meter")
def api_meter(request: Request):
    """Token 计量表（迁移补齐：原 Tk panels_meta `_panel_token_meter`）。

    数据源：服务端 AIClient.meter_summary()（按契约方法分桶）+ state._dialogue_stats
    （召对预过滤/缓存命中与 AI 调用次数）+ state.ai_token_log（历史回合用量）。
    分组映射由 ai/token_meter.grouped_meter_rows 提供（单一权威源，Tk/Web 共用）。
    """
    _require_auth(request)
    # D 修复（并发一致性）：状态判空必须与后续读写同在锁内。原实现在 `with _lock`
    # **之前**调用 _require_state()，而 `_state` 在锁内被 advance/load 重新赋值 →
    # 并发请求可能读到刚被替换/尚未替换的旧对象（「刚 load 完却判未开局 409」或
    # 对旧 state 执行动作）。
    with _lock:
        _require_state()
        from ai.token_meter import grouped_meter_rows
        ai = _get_ai()
        rows = grouped_meter_rows(ai, getattr(_state, "_dialogue_stats", None),
                                  getattr(_state, "_kb_stats", None))
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
    # D 修复（并发一致性）：状态判空必须与后续读写同在锁内。原实现在 `with _lock`
    # **之前**调用 _require_state()，而 `_state` 在锁内被 advance/load 重新赋值 →
    # 并发请求可能读到刚被替换/尚未替换的旧对象（「刚 load 完却判未开局 409」或
    # 对旧 state 执行动作）。
    with _lock:
        _require_state()
        ai = _get_ai()
        try:
            if ai is not None and hasattr(ai, "reset_meter"):
                ai.reset_meter()
        except Exception:
            pass
        st = getattr(_state, "_dialogue_stats", None)
        if isinstance(st, dict):
            st.update({"prefilter_hits": 0, "cache_hits": 0, "ai_calls": 0})
        kst = getattr(_state, "_kb_stats", None)
        if isinstance(kst, dict):
            kst.update({"calls": 0, "hits": 0})
        return {"ok": True}


@app.post("/api/conclude")
def api_conclude(request: Request):
    _require_auth(request)
    # D 修复（并发一致性）：状态判空必须与后续读写同在锁内。原实现在 `with _lock`
    # **之前**调用 _require_state()，而 `_state` 在锁内被 advance/load 重新赋值 →
    # 并发请求可能读到刚被替换/尚未替换的旧对象（「刚 load 完却判未开局 409」或
    # 对旧 state 执行动作）。
    with _lock:
        _require_state()
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
    # D 修复（并发一致性）：状态判空必须与后续读写同在锁内。原实现在 `with _lock`
    # **之前**调用 _require_state()，而 `_state` 在锁内被 advance/load 重新赋值 →
    # 并发请求可能读到刚被替换/尚未替换的旧对象（「刚 load 完却判未开局 409」或
    # 对旧 state 执行动作）。
    with _lock:
        _require_state()
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
            except Exception as e:  # noqa: BLE001
                log.warning("[server] 会签推演失败: %s", e)
                rev = None
        # 审查修复（伪结论 + 失败入档）：契约失败时 council_review 返回带 _error 的
        # **非空** dict，原 `if not rev` 判空对其无效 → 错误对象被当作合法会签意见；
        # 且无论成败都 store_council_review 落库，随存档长期复用（玩家会看到 AI
        # 从未产出的"可准"，并因缓存命中而每次都是它）。
        # 现改为：仅真正的会签结果才落库；失败明确回报「待议」且不缓存。
        _ok = bool(isinstance(rev, dict) and rev and not rev.get("_error"))
        if not _ok:
            return {"review": {"memo": "（会签未成，未落档）", "objections": "",
                               "executions": "", "verdict": "待议",
                               "revised_effects": []},
                    "cached": False, "unavailable": True}
        _state.store_council_review(req.draft_id, rev)
        return {"review": _json_safe(rev), "cached": False}


@app.post("/api/decree/polish")
def api_decree_polish(req: DecreePolishReq, request: Request):
    """圣旨润色 / 批改诏草（迁移补齐：原 Tk `_panel_decree_entry` 的润色与诏草批改）。

    薄壳：AI 润色走 AIClient.polish_decree（严格契约 + 兜底），零业务逻辑复制；
    draft_id 非空时把结果回写该诏草并清会签缓存（重入待签）。AI 未接入 → 明确 409。
    """
    _require_auth(request)
    # D 修复（并发一致性）：状态判空必须与后续读写同在锁内。原实现在 `with _lock`
    # **之前**调用 _require_state()，而 `_state` 在锁内被 advance/load 重新赋值 →
    # 并发请求可能读到刚被替换/尚未替换的旧对象（「刚 load 完却判未开局 409」或
    # 对旧 state 执行动作）。
    with _lock:
        _require_state()
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
            log.warning("[server] 诏书润色中断: %s", e)
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
    # D 修复（并发一致性）：状态判空必须与后续读写同在锁内。原实现在 `with _lock`
    # **之前**调用 _require_state()，而 `_state` 在锁内被 advance/load 重新赋值 →
    # 并发请求可能读到刚被替换/尚未替换的旧对象（「刚 load 完却判未开局 409」或
    # 对旧 state 执行动作）。
    with _lock:
        _require_state()
        if not isinstance(req.draft, dict) or not req.draft:
            raise HTTPException(status_code=400, detail="诏草不可为空")
        did = _state.add_edict_draft(dict(req.draft))
        return {"draft_id": did, "draft": _json_safe(_state.get_edict_draft(did) or {}),
                "state": _state_to_dict(_state)}


@app.post("/api/decree/discard")
def api_decree_discard(req: DecreeDiscardReq, request: Request):
    """弃删诏草（迁移补齐：Tk「弃删」→ GameState.remove_edict_draft）。"""
    _require_auth(request)
    # D 修复（并发一致性）：状态判空必须与后续读写同在锁内。原实现在 `with _lock`
    # **之前**调用 _require_state()，而 `_state` 在锁内被 advance/load 重新赋值 →
    # 并发请求可能读到刚被替换/尚未替换的旧对象（「刚 load 完却判未开局 409」或
    # 对旧 state 执行动作）。
    with _lock:
        _require_state()
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
    # D 修复（并发一致性）：状态判空必须与后续读写同在锁内。原实现在 `with _lock`
    # **之前**调用 _require_state()，而 `_state` 在锁内被 advance/load 重新赋值 →
    # 并发请求可能读到刚被替换/尚未替换的旧对象（「刚 load 完却判未开局 409」或
    # 对旧 state 执行动作）。
    with _lock:
        _require_state()
        from core.commands import _monthly_report_text
        try:
            text = _monthly_report_text(_state, _get_ai())
        except Exception as e:  # noqa: BLE001
            log.warning("[server] 月折生成失败: %s", e)
            raise HTTPException(status_code=502, detail="月折未能草就，请稍后再试。")
        return {"report": text}


def _ai_config_path() -> str:
    return os.path.join(_app_root(), "ai_config.json")


@app.get("/api/portrait/{fname}")
def api_portrait(fname: str, request: Request):
    """立绘受控路由：从后端缓存目录取合成图（**不写源码/安装目录**）。

    2026-09-19 整改（`analysis/portrait_system_design.md` §七）：
    运行期不得写 `frontend/public` 或安装目录；合成图留在 `_composed/`（按需再生、不入库），
    由本路由提供。仅允许**纯文件名**（防路径穿越），且必须是已合成产物。
    """
    _require_auth(request)
    import os as _os
    from fastapi.responses import FileResponse
    name = _os.path.basename(str(fname or ""))
    if not name or name != str(fname) or ".." in name:
        raise HTTPException(status_code=400, detail="立绘文件名不合法")
    if not name.lower().endswith((".png", ".webp")):
        raise HTTPException(status_code=400, detail="立绘格式不支持")
    try:
        from content.ministers.data import COMPOSE_DIR
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="立绘缓存目录不可用")
    path = _os.path.join(COMPOSE_DIR, name)
    if not _os.path.isfile(path):
        # 兼容：按 `名_档_姿.png` 反解并即时合成（可用则返回，否则 404）
        try:
            from content.ministers.data import compose_portrait
            stem = name.rsplit(".", 1)[0]
            parts = stem.split("_")
            if len(parts) >= 3:
                p = compose_portrait("_".join(parts[:-2]), parts[-2], parts[-1])
                if p and _os.path.isfile(p):
                    path = p
        except Exception:  # noqa: BLE001
            pass
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail="立绘未生成")
    return FileResponse(path, media_type="image/png")


@app.get("/api/ai_config")
def api_ai_config_get(request: Request):
    """读 AI 配置（设置面板预填；不回传完整 key 或片段）。

    审查 P3：补鉴权（原缺 _require_auth）。
    审查 P2-15：只回 configured + 服务端稳定 key 指纹（sha256 前 8 位），
    绝不回传 key 的任何片段（原 `key[:4]+…+key[-4:]`）。
    """
    _require_auth(request)
    try:
        cfg = _load_ai_config()
        key = str(cfg.get("api_key", "") or "")
        return {
            "configured": bool(key),
            "key_id": _key_id(key),
            "base_url": str(cfg.get("base_url", "") or ""),
            "model": str(cfg.get("model", "") or ""),
            "enable_tools": str(cfg.get("enable_tools", "") or "auto"),
        }
    except Exception:
        return {"configured": False, "key_id": "", "base_url": "",
                "model": "", "enable_tools": "auto"}


@app.post("/api/fetch_models")
def api_fetch_models(req: FetchModelsReq, request: Request):
    """根据输入的 Key 与 Base URL，探测并拉取远程支持的模型列表。

    安全审查 A2（凭据外泄）+ P1-2（SSRF）：
      - base_url 先过 SSRF 校验（协议 / userinfo / 内网/回环/metadata / DNS rebinding）；
      - key 为空时可复用服务端已配置 Key，**仅当目标与已配置端点同规范**，
        绝不把生产 Key 发往客户端指定的任意地址；连接前由 _http_* 再解析校验一次。
    """
    _require_auth(request)
    base_url = _validate_base_url(req.base_url)
    key = (req.api_key or "").strip()
    if not key:
        _cfg = _load_ai_config()
        _cfg_url = str(_cfg.get("base_url", "") or "").strip()
        _cfg_key = str(_cfg.get("api_key", "") or "").strip()
        try:
            from ai.client import normalize_endpoint as _ne
            _cfg_clean = _ne(_cfg_url)[0].rstrip("/")
            _req_clean = _ne(base_url)[0].rstrip("/")
        except Exception:
            _cfg_clean, _req_clean = _cfg_url.rstrip("/"), base_url.rstrip("/")
        if _cfg_key and _cfg_clean and _cfg_clean == _req_clean:
            key = _cfg_key
    if not key:
        raise HTTPException(status_code=400, detail="请先填写 API Key 再探测模型")
    try:
        from ai.client import AIClient
        client = AIClient(api_key=key, base_url=base_url)
        models = client.fetch_available_models()
        return {"ok": True, "models": models}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        # 不回传完整异常栈/URL 细节给客户端
        return {"ok": False, "models": [], "error": type(e).__name__}


@app.post("/api/ai_config")
def api_ai_config_set(req: AiConfigReq, request: Request):
    """写 AI 配置并重建服务端 AI 客户端（设置面板保存）——**事务化**（审查 P1-3）。

    顺序：读旧配置 + PATCH 合并（SSRF 校验）→ 构造候选 client → 在线 probe
    （锁外，避免阻塞其它请求）→ 成功后才临时文件 + fsync + 原子 os.replace →
    锁内原子替换全局 client。任一步失败：不写盘、不换 client，旧配置/旧 client 原样保留。
    """
    global _ai
    _require_auth(request)
    # 1) PATCH 合并：未提交字段（含 fallback/settle）不得删除；base_url 先 SSRF 校验
    with _config_lock:
        merged = _merge_ai_config(req, _load_ai_config())
    candidate = _client_from_config(merged)

    # 2) 候选 client 在线探测（锁外执行）
    ok, msg = False, "未配置 API Key"
    if candidate.available:
        try:
            ok, msg = candidate.probe(force=True)
        except Exception as e:  # noqa: BLE001
            ok, msg = False, f"探测失败：{type(e).__name__}"
        if not ok:
            # 事务回滚语义：probe 失败 → 不落盘、不替换，旧配置/旧 client 保留
            _old = _ai if _ai is not None else None
            return {
                "ok": False, "available": False, "message": msg,
                "has_key": bool(merged.get("api_key")),
                "base_url": str(_old.base_url if _old is not None else ""),
                "model": str(_old.model if _old is not None else ""),
            }

    # 3) 提交：重读最新配置再合并（并发更新不覆盖彼此无关字段）→ 原子落盘 + 原子换 client
    with _config_lock:
        final_cfg = _merge_ai_config(req, _load_ai_config())
        new_client = _client_from_config(final_cfg)
        with _lock:
            _atomic_write_json(_ai_config_path(), final_cfg)
            _ai = new_client
    return {
        "ok": True,
        "available": bool(ok),
        "message": msg,
        "has_key": bool(final_cfg.get("api_key")),
        "base_url": new_client.base_url,
        "model": new_client.model,
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
