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

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ai.client import AIClient
from backend.client import LocalBackend, _app_root

app = FastAPI(title="Songzuo Reference Backend", version="1.0")

_lock = threading.Lock()
_backend = LocalBackend()
_state = None          # 当前 GameState（服务端持有）
_ai = None             # 服务端 AIClient（可禁用）


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


def _state_to_dict(s) -> dict:
    """GameState → JSON 快照（与 HttpBackend._to_state 对称）。"""
    out = {}
    for k, v in vars(s).items():
        if k.startswith("_"):
            continue  # 私有/缓存字段不外发
        try:
            json.dumps(v, ensure_ascii=False)
            out[k] = _json_safe(v)
        except Exception:
            continue
    return out


def _require_state():
    if _state is None:
        raise HTTPException(status_code=409, detail="尚未开局：请先 POST /api/new_game")


class NewGameReq(BaseModel):
    difficulty: str = "史实"


class ActionReq(BaseModel):
    action: str
    params: dict = {}


class ResolveReq(BaseModel):
    title: str
    choice: int


class SlotReq(BaseModel):
    slot: int = 1


class AiConfigReq(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""


@app.get("/health")
def health():
    return {"ok": True, "backend": "python-reference", "has_state": _state is not None}


@app.post("/api/new_game")
def api_new_game(req: NewGameReq):
    global _state
    with _lock:
        _state = _backend.new_game(req.difficulty, _get_ai())
        return {"state": _state_to_dict(_state)}


@app.post("/api/advance")
def api_advance():
    global _state
    _require_state()
    with _lock:
        events, log, report, _state = _backend.advance(_state, _get_ai())
        return {"events": _json_safe(events), "log": _json_safe(log),
                "report": report, "state": _state_to_dict(_state)}


@app.post("/api/action")
def api_action(req: ActionReq):
    global _state
    _require_state()
    with _lock:
        try:
            message, _state = _backend.action(_state, req.action, req.params, _get_ai())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"message": message, "state": _state_to_dict(_state)}


@app.post("/api/resolve_event")
def api_resolve_event(req: ResolveReq):
    global _state
    _require_state()
    with _lock:
        message, _state = _backend.resolve_event(
            _state, req.title, req.choice, _get_ai())
        return {"message": message, "state": _state_to_dict(_state)}


@app.post("/api/save")
def api_save(req: SlotReq):
    _require_state()
    with _lock:
        _backend.save(_state, req.slot)
        return {"ok": True, "slot": req.slot}


@app.post("/api/load")
def api_load(req: SlotReq):
    global _state
    with _lock:
        _state = _backend.load(req.slot)
        return {"state": _state_to_dict(_state)}


@app.get("/api/save_slots")
def api_save_slots():
    with _lock:
        return {"slots": _json_safe(_backend.save_slots())}


@app.get("/api/readouts")
def api_readouts():
    """只读派生读数（军政/会计/仓廪面板用）。

    薄壳纪律：仅调用 GameState 现有方法并序列化，零业务逻辑复制。
    army_units / central_arsenal 为对象，_state_to_dict 无法序列化，故在此展开。
    """
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
            granary = {
                "monthly": s.calc_monthly_grain()[0],
                "army": s.calc_army_grain()[0],
                "official": s.calc_official_grain()[0],
                "clerk": s.calc_clerk_grain()[0],
                "capacity_used": s.granary_capacity_used(),
            }
        except Exception:
            granary = {}
        return {
            "army": army,
            "arsenal": arsenal,
            "finance": finance,
            "granary": granary,
            "defense_lines": _json_safe(s.defense_lines),
        }


@app.post("/api/conclude")
def api_conclude():
    _require_state()
    with _lock:
        eval_result, ai_eval = _backend.conclude(_state, _get_ai())
        return {"eval": _json_safe(eval_result), "ai_eval": ai_eval}


def _ai_config_path() -> str:
    return os.path.join(_app_root(), "ai_config.json")


@app.get("/api/ai_config")
def api_ai_config_get():
    """读 AI 配置（设置面板预填；不回传完整 key，只回是否已配）。"""
    try:
        with open(_ai_config_path(), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        key = str(cfg.get("api_key", "") or "")
        return {
            "configured": bool(key),
            "api_key_masked": (key[:4] + "…" + key[-4:]) if len(key) > 8 else "",
            "base_url": str(cfg.get("base_url", "") or ""),
            "model": str(cfg.get("model", "") or ""),
        }
    except Exception:
        return {"configured": False, "api_key_masked": "", "base_url": "", "model": ""}


@app.post("/api/ai_config")
def api_ai_config_set(req: AiConfigReq):
    """写 AI 配置并重建服务端 AI 客户端（设置面板保存）。"""
    global _ai
    with _lock:
        cfg = {"api_key": req.api_key, "base_url": req.base_url, "model": req.model}
        with open(_ai_config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        _ai = None  # 下次 _get_ai() 重建
        client = _get_ai()
        return {"ok": True, "available": bool(getattr(client, "available", False))}


def main() -> None:
    host = os.environ.get("SONGZUO_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("SONGZUO_SERVER_PORT", "8080"))
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    sys.exit(main() or 0)
