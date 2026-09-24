# -*- coding: utf-8 -*-
"""宋祚 · AI 叙事客户端

设计原则（参照 MingSalvageSim 的 prompts/*.md 范式）：
- 所有提示词从 ai/prompts/*.md 载入，代码只负责「载入 + 填槽 + 调模型 + 验收」。
- 模型输出一律走「JSON 契约」：字段白名单、档位词（无|微|小|中|大），
  数字由程序按 TIER_RANGE 换算并封顶，AI 无法直接压数值。
- 解析失败 / 字段越界 / 复读 → 程序拦截，补调用一次；仍不可用则返回错误标记。
- AI 不可用时不伪造文本，统一返回含 `_error` 标记的结构，由上层提示配置 AI。
"""
import math
import os
import sys
import json
import re
import socket
import threading
import urllib.request
import urllib.error
from difflib import SequenceMatcher



# ============================================================
# 资源目录（兼容打包后 exe 运行：frozen 时用 exe 所在目录）
# ============================================================

from ai.client_narrative import ClientNarrativeMixin
from ai.client_utils import (
    _ai_unavailable, _app_root, _build_offer_context, _clean_text, _extract_json, _fallback_parse, _http_get_json, _http_post_json, _load_prompt, _normalize_decree_effects, _normalize_effects, _org_by_affiliation, _prompt_dir, _safety_filter, _safety_lexicon_path, _sanitize_history, _similar, _tool_dispatch, _TOOL_SCHEMAS, _valid_tier, _wrap_untrusted, effects_to_dict, load_safety_lexicon, safety_filter_operational, tier_to_value,
)
from ai.narrative_guard import (
    _validate_narrative_numbers, _build_numeric_ranges, _build_source_closure,
    build_character_statuses, build_character_blacklist, _validate_characters,
)
from content.data import normalize_tier
from ai.schemas import schema_check as _schema_check  # A1：JSON Schema 结构层（可选，未装库自动跳过）

import logging as _logging
log = _logging.getLogger("ai.client")   # provider 回退/空响应自愈等需要留痕的路径


# ---- 共享辅助（validators）/ 契约 Mixin（contracts_*）----
# 公共 API 再导出：历史调用方 `from ai.client import _summary_text` 等不破。
from ai.validators import (
    _TIERS7, _summary_text, _decide_state_text, _narrative_fallback,
)
from ai.contracts_court import CourtContractMixin
from ai.contracts_decree import DecreeContractMixin
from ai.contracts_settle import SettleContractMixin
from ai.contracts_misc import MiscContractMixin


def normalize_endpoint(base_url: str) -> tuple[str, str, str]:
    """智能解析用户输入的自定义 Base URL，返回 (clean_base, chat_url, models_url)。

    完美兼容各种自定义中转与不同用户输入习惯:
      - 仅输入域名: https://api.deepseek.com -> /v1/chat/completions & /v1/models
      - 带 /v1:     https://api.openai.com/v1 -> /chat/completions & /models
      - 完整端点:   https://my.com/v1/chat/completions -> 自动截取正确 base 并保留
    """
    raw = (base_url or "https://api.deepseek.com").strip().rstrip("/")
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw

    if raw.endswith("/chat/completions"):
        chat_url = raw
        clean_base = raw[:-len("/chat/completions")].rstrip("/")
    else:
        # 如果已经带有 /v1
        if raw.endswith("/v1"):
            clean_base = raw
            chat_url = f"{raw}/chat/completions"
        else:
            # 如果是 deepseek 官方或者只有主域名，尝试挂载 /v1
            clean_base = raw
            chat_url = f"{raw}/chat/completions" if "deepseek.com" in raw else f"{raw}/v1/chat/completions"

    # 计算 models 端点
    models_base = clean_base if clean_base.endswith("/v1") else (clean_base if "deepseek.com" in clean_base else f"{clean_base}/v1")
    models_url = f"{models_base}/models"
    return clean_base, chat_url, models_url


class AIClient(ClientNarrativeMixin, CourtContractMixin, DecreeContractMixin,
               SettleContractMixin, MiscContractMixin):
    """封装在线大模型调用；AI 不可用时返回错误标记（不伪造文本）。"""

    def __init__(self, api_key="", base_url="", model="", enable_tools="auto",
                 settle_api_key="", settle_base_url="", settle_model="",
                 fallback_api_key="", fallback_base_url="", fallback_model=""):
        # P1-4：provider 三要素（key/base_url/model）改为「每线程快照栈」——
        # 请求开始固定不可变快照，切换只入栈/弹栈，绝不原地改共享属性（并发不串 Key）。
        self._pstate = threading.local()
        self._base_provider = {}
        self.api_key = (api_key or "").strip()
        clean_base, chat_url, models_url = normalize_endpoint(base_url)
        self.base_url = clean_base
        self.chat_url = chat_url
        self.models_url = models_url
        self.model = (model or "deepseek-chat").strip()
        # ---- 兜底 provider（用户定稿 2026-09-19：「各种需要 API 的地方先用 Agnes 的，
        #      无法完成再用 a6api」）----
        # 主 provider 失败（HTTP/超时/空正文）或**契约拿不到可解析内容**时，
        # `_call` 自动切到兜底 provider 重发同一请求一次；三者皆空则行为与从前一致。
        self.fallback_api_key = (fallback_api_key or "").strip()
        _fb, _fc, _fm = normalize_endpoint(fallback_base_url or base_url)
        self.fallback_base_url = _fb if fallback_base_url else ""
        self.fallback_chat_url = _fc if fallback_base_url else ""
        self.fallback_models_url = _fm
        self.fallback_model = (fallback_model or "").strip()
        self._in_fallback = False
        self.fallback_hits = 0
        # ---- 回合结算专用 provider（用户定稿 2026-09-19）----
        # 「当宋祚需要过回合结算时，调用 agnes-2.5-flash 来执行」：结算期间
        # （`settle_turn` 的 prelude + 12 步推演 + 月报）整体切到该 provider/模型，
        # 其余契约（召对/拟旨/会签）仍用主配置。三者皆空时行为与从前完全一致。
        self.settle_api_key = (settle_api_key or "").strip()
        _sb, _sc, _sm = normalize_endpoint(settle_base_url or base_url)
        self.settle_base_url = _sb if settle_base_url else ""
        self.settle_chat_url = _sc if settle_base_url else ""
        self.settle_models_url = _sm
        self.settle_model = (settle_model or "").strip()
        self._settle_depth = 0
        self.available = bool(self.api_key)
        self._prev_texts = []   # 复读检测历史
        # 工具开关：'auto'(探测)/'on'(强制开)/'off'(强制关)/'simple'(强制简化)
        # C1 修复：原属性名为 `enable_tools`，与下方同名方法 def enable_tools(mode) 冲突
        # —— 实例属性优先于类方法，方法**不可达**（调用即 TypeError: 'str' object is
        # not callable），使 capability_probe / _call_with_tools 的生产接线永远不可达。
        # 属性改名 enable_tools_mode；方法保留并负责同步两套表示。
        self.enable_tools_mode = (enable_tools if enable_tools in ("auto", "on", "off", "simple")
                                  else "auto")
        self.tools_supported = None  # None=未探测; True/False=已探测
        self.json_mode = None        # response_format=json_object 支持度：None=未探测; True/False=已探测
        # 模型适配层（言枢密设计）：tool_mode 注册表 + 能力探测缓存
        self.tool_mode = "tool_full"   # tool_full / tool_simple / json / error
        self._cap_probe_cache = None   # capability_probe 结果缓存
        self.token_usage = {"prompt": 0, "completion": 0, "calls": 0}
        self._meter = {}   # 按契约方法分桶：method → {"calls": n, "prompt": n, "completion": n}
        self._probe_cache = None  # (ok, msg) 在线自检缓存；None=未做过
        self._cache = {}
        self._cache_hits = 0
        self._cache_misses = 0

    def _ensure_provider_state(self):
        """兼容 __new__/旧对象：确保线程态与主配置字典存在。"""
        bp = getattr(self, "_base_provider", None)
        if not isinstance(bp, dict):
            bp = self._base_provider = {}
        st = getattr(self, "_pstate", None)
        if st is None:
            st = self._pstate = threading.local()
        return bp, st

    def _provider_stack(self):
        _, st = self._ensure_provider_state()
        stack = getattr(st, "stack", None)
        if stack is None:
            stack = []
            st.stack = stack
        return stack

    def _current_provider(self) -> dict:
        stack = self._provider_stack()
        if stack:
            return stack[-1]
        bp, _ = self._ensure_provider_state()
        return bp

    def _push_provider(self, view: dict) -> None:
        self._provider_stack().append(view)

    def _pop_provider(self) -> None:
        stack = self._provider_stack()
        if stack:
            stack.pop()

    _PROVIDER_FIELDS = ("api_key", "base_url", "chat_url", "models_url", "model")

    @property
    def api_key(self):
        return self._current_provider().get("api_key", "")

    @api_key.setter
    def api_key(self, v):
        bp, _ = self._ensure_provider_state()
        bp["api_key"] = (v or "").strip()

    @property
    def base_url(self):
        return self._current_provider().get("base_url", "")

    @base_url.setter
    def base_url(self, v):
        bp, _ = self._ensure_provider_state()
        bp["base_url"] = str(v or "").strip()

    @property
    def chat_url(self):
        return self._current_provider().get("chat_url", "")

    @chat_url.setter
    def chat_url(self, v):
        bp, _ = self._ensure_provider_state()
        bp["chat_url"] = str(v or "").strip()

    @property
    def models_url(self):
        return self._current_provider().get("models_url", "")

    @models_url.setter
    def models_url(self, v):
        bp, _ = self._ensure_provider_state()
        bp["models_url"] = str(v or "").strip()

    @property
    def model(self):
        return self._current_provider().get("model", "")

    @model.setter
    def model(self, v):
        bp, _ = self._ensure_provider_state()
        bp["model"] = str(v or "").strip()

    @property
    def _in_fallback(self):
        _, st = self._ensure_provider_state()
        return bool(getattr(st, "in_fallback", False))

    @_in_fallback.setter
    def _in_fallback(self, v):
        _, st = self._ensure_provider_state()
        st.in_fallback = bool(v)

    # 内部辅助调用链（_meter_key_of 跳过，向上找真实契约方法名）
    _METER_INTERNAL = {"_call", "_call_impl", "_tool_roundtrip", "_cached_call", "_postprocess",
                   # 审查修复：漏登记 _narrative_call，致 9 类部门叙事（yamen/local/
                   # land/finance/exam/science/military_expand/diplomacy/reform）
                   # 的计量全部落进本桶（token_group_of 未命中 → MeterPanel 只显示
                   # 「其它」，无法按月报叙事细分；总数不漏、分组失真）。
                   "_narrative_call"}

    def _meter_key_of(self) -> str:
        """自动检测发起本次 _call 的契约方法名（按方法分桶，零侵入）。

        调用链：契约方法 →（可选 _tool_roundtrip/_cached_call/_postprocess）→ _call
        → _add_usage。从帧 2 起向上跳过内部辅助，取第一个外部方法名。
        """
        import sys
        f = sys._getframe(2)   # _add_usage ← _call ← 调用方
        while f is not None:
            name = f.f_code.co_name
            if name not in self._METER_INTERNAL:
                return name
            f = f.f_back
        return "unknown"

    def _add_usage(self, usage: dict, meter_key: str = "") -> None:
        """累加 token 用量（O(1)，不打印玩家内容）；同时按契约方法分桶计量。

        A2 遥测（可选）：SONGZUO_TELEMETRY=1 时把调用计量写入 SQLite
        （telemetry/store.py，析微澜席位）；任何异常静默——遥测绝不影响游戏。
        """
        try:
            _p = int(usage.get("prompt_tokens", 0) or 0)
            _c = int(usage.get("completion_tokens", 0) or 0)
            # C5 修复（计量丢数）：以下为读-改-写累加，异步/多线程路径并发调用同一
            # client 时会丢数；归属推断 _meter_key_of（走栈帧）亦须在同一临界区内完成。
            _lk = getattr(self, "_meter_lock", None)
            if _lk is None:
                _lk = self._meter_lock = threading.Lock()
            with _lk:
                self.token_usage["prompt"] += _p
                self.token_usage["completion"] += _c
                self.token_usage["calls"] += 1
                key = meter_key or self._meter_key_of()
                b = self._meter.setdefault(key, {"calls": 0, "prompt": 0, "completion": 0})
                b["calls"] += 1
                b["prompt"] += _p
                b["completion"] += _c
            # A2：可选遥测落库（默认关；失败静默）—— 移出临界区，避免持锁做 IO
            if os.environ.get("SONGZUO_TELEMETRY") == "1":
                try:
                    from telemetry.store import get_store
                    st = get_store()
                    if st is not None:
                        st.record_ai_call(method=key, prompt_tokens=_p,
                                          completion_tokens=_c,
                                          estimated=bool(usage.get("estimated")))
                except Exception:
                    pass
        except Exception:
            pass

    def meter_summary(self) -> dict:
        """按方法分桶计量快照（UI Token 计量表用；含总桶）。"""
        return {"total": dict(self.token_usage), "by_method": {
            k: dict(v) for k, v in self._meter.items()}}

    def reset_meter(self) -> None:
        """清零 token 计量（含总桶与分桶；召对统计在 GameState，另清）。"""
        self.token_usage = {"prompt": 0, "completion": 0, "calls": 0}
        self._meter = {}

    def _has_fallback(self) -> bool:
        """是否配置了兜底 provider（三者需 model；key/base 缺省沿用主配置）。"""
        return bool(self.fallback_model) and not self._in_fallback

    def _provider_scope(self, which: str):
        """上下文管理器：把**当前线程**切到兜底 provider 快照（P1-4）。

        实现要点：只向本线程快照栈 push 一层不可变视图，**不再原地改共享
        self.api_key/base_url/model**；并发请求各持自己的 key/base/model，绝不串用。
        退出时严格弹栈还原（嵌套 settlement_mode 亦正确）。
        """
        import contextlib

        @contextlib.contextmanager
        def _cm():
            cur = self._current_provider()
            if which == "fallback":
                view = {
                    "api_key": self.fallback_api_key or cur.get("api_key", ""),
                    "base_url": self.fallback_base_url or cur.get("base_url", ""),
                    "chat_url": self.fallback_chat_url or cur.get("chat_url", ""),
                    "models_url": self.fallback_models_url or cur.get("models_url", ""),
                    "model": self.fallback_model or cur.get("model", ""),
                }
            else:
                view = dict(cur)
            self._push_provider(view)
            try:
                yield
            finally:
                self._pop_provider()
        return _cm()

    @staticmethod
    def _usable_raw(raw, json_mode: bool = False) -> bool:
        """本次调用是否**拿到了可用产出**（空正文 / 非法 JSON 均视为"无法完成"）。"""
        if raw is None:
            return False
        if isinstance(raw, dict):
            return bool(raw.get("tool_calls") or str(raw.get("content") or "").strip())
        s = str(raw).strip()
        if not s:
            return False
        if json_mode:
            return _extract_json(s) is not None
        return True

    def settlement_mode(self):
        """上下文管理器：**回合结算期间**切到结算专用 provider/模型（缺省为空=不切）。

        用法（`core/commands.settle_turn`）：
            with ai_client.settlement_mode():
                _ai_prelude(...); settle_local(...); 月报
        期间 `_call` 读到的 `api_key/chat_url/model` 均为结算配置，退出时严格还原——
        故召对/拟旨等其它契约不受影响。
        """
        import contextlib

        @contextlib.contextmanager
        def _cm():
            if not self.settle_model:
                yield False
                return
            cur = self._current_provider()
            view = {
                "api_key": self.settle_api_key or cur.get("api_key", ""),
                "base_url": self.settle_base_url or cur.get("base_url", ""),
                "chat_url": self.settle_chat_url or cur.get("chat_url", ""),
                "models_url": self.settle_models_url or cur.get("models_url", ""),
                "model": self.settle_model,
            }
            self._push_provider(view)
            self._settle_depth += 1
            try:
                yield True
            finally:
                self._settle_depth = max(0, self._settle_depth - 1)
                self._pop_provider()
        return _cm()

    def _auth_headers(self) -> dict:
        """构造请求认证头（probe/_call 共用，api_key 仅内部使用，绝不外泄）。"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _tools_active(self) -> bool:
        """是否启用工具：依据开关与运行时探测结果。

        P1-12：`simple` 表示「启用但限制工具面」（见 `_tool_schemas`），不是 auto。
        原实现把 simple 落入 auto 分支返回 True，生产 dialogue 仍挂全量 `_TOOL_SCHEMAS`。
        """
        if self.enable_tools_mode == "off":
            return False
        if self.enable_tools_mode in ("on", "simple"):
            return True
        # auto：未探测时先尝试，首次失败后置 False
        if self.tools_supported is False:
            return False
        return True

    def _tool_schemas(self):
        """按 enable_tools_mode 选工具面：simple → 精简 5 工具；其余 → 全量 10 工具。"""
        if self.enable_tools_mode == "simple":
            from ai.client_utils import SIMPLE_TOOL_SCHEMAS
            return SIMPLE_TOOL_SCHEMAS
        return _TOOL_SCHEMAS

    def _tool_roundtrip(self, sys_p, user_p, state, agent, temperature,
                        max_tokens, history=None):
        """真 function calling 单次往返：首轮带工具 → 注入 tool 结果 → 二次生成。

        dialogue / polish_decree / council_review 共用的「工具往返」流程，收敛单处。
        调用方自行决定 raw 返回后如何 _postprocess（draft 走 postprocess、会签取 content）。
        """
        messages = [
            {"role": "system", "content": sys_p},
            {"role": "user", "content": user_p},
        ]
        raw = self._call(sys_p, messages=messages, history=history,
                         temperature=temperature, max_tokens=max_tokens,
                         tools=self._tool_schemas())
        if isinstance(raw, dict) and raw.get("tool_calls"):
            # 首次带工具的调用成功 → 标记端点支持 tools
            self.tools_supported = True
            messages.append({"role": "assistant",
                             "content": raw.get("content") or "",
                             "tool_calls": [
                                 {"id": tc["id"], "type": "function",
                                  "function": {"name": tc["function"]["name"],
                                               "arguments": tc["function"]["arguments"]}}
                                 for tc in raw["tool_calls"]]
                             })
            results = _tool_dispatch(state, raw["tool_calls"], agent)
            for call_id, res in results:
                messages.append({"role": "tool", "tool_call_id": call_id,
                                 "content": res})
            raw2 = self._call(sys_p, messages=messages, history=history,
                              temperature=temperature, max_tokens=max_tokens,
                              tools=_TOOL_SCHEMAS)
            if isinstance(raw2, dict):
                raw2 = raw2.get("content") or ""
            raw = raw2
        elif raw is None:
            self.tools_supported = False
        return raw

    @staticmethod
    def _config_path() -> str:
        return os.path.join(_app_root(), "ai_config.json")

    def save_config(self) -> bool:
        """把当前 API 配置写入根目录 ai_config.json（未配置 AI 则清空）。"""
        path = self._config_path()
        if not self.api_key:
            # 未配置 AI 叙事：删除已保存配置（若存在）
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
            return True
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "api_key": self.api_key,
                    "base_url": self.base_url,
                    "model": self.model,
                    "enable_tools": self.enable_tools_mode,
                    # 结算专用 provider（可选；空则不写，保持配置最小）
                    **({"settle_api_key": self.settle_api_key} if self.settle_api_key else {}),
                    **({"settle_base_url": self.settle_base_url} if self.settle_base_url else {}),
                    **({"settle_model": self.settle_model} if self.settle_model else {}),
                    # 兜底 provider（Agnes 优先，a6api 兜底）
                    **({"fallback_api_key": self.fallback_api_key} if self.fallback_api_key else {}),
                    **({"fallback_base_url": self.fallback_base_url} if self.fallback_base_url else {}),
                    **({"fallback_model": self.fallback_model} if self.fallback_model else {}),
                }, f, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    def probe(self, timeout: float = 15, force: bool = False) -> tuple:
        """轻量在线自检：用当前模型发一个极小请求，验证 key + 模型可用。

        返回 (ok, msg)：ok 为 True 表示可用；msg 为可读说明（成功或失败原因）。
        未配置(api_key 为空)时直接返回 (False, "未配置 API Key")，不发网络请求。

        缓存：首次成功/失败后记住结果，**force=False 时直接复用缓存，不再联网**，
        避免每次点「开始游戏」都阻塞主线程做 15s 超时联网自检导致界面卡死。
        force=True 用于配置面板的「重新自检」按钮，强制真实联网。
        """
        # 配置面板主动重测时清缓存
        if force:
            self._probe_cache = None
        if self._probe_cache is not None:
            return self._probe_cache
        if not self.api_key:
            return False, "未配置 API Key"
        try:
            headers = self._auth_headers()
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "ping"}],
                "temperature": 0,
                "max_tokens": 1,
            }
            status, body, text = _http_post_json(self.chat_url, headers, payload, timeout)
            if status == 200:
                # 能力探测：json_object 支持度（结构调用可用 response_format）
                self.json_mode = self._probe_json_mode(timeout)
                self._probe_cache = (True, f"模型可用（{self.model}）")
                return self._probe_cache
            try:
                err = (body or {}).get("error", {}).get("message", "") or text
            except Exception:
                err = text
            self._probe_cache = (False, f"模型返回 {status}：{str(err)[:120]}")
            return self._probe_cache
        except urllib.error.URLError as e:
            # URLError.reason 可能是 TimeoutError / ConnectionError / socket 错误
            reason = getattr(e, "reason", e)
            if isinstance(reason, TimeoutError):
                self._probe_cache = (False, "连接超时，请检查网络或 base_url")
            else:
                self._probe_cache = (False, "无法连接，请检查 base_url 与网络")
            return self._probe_cache
        except Exception as e:  # noqa: BLE001
            self._probe_cache = (False, f"检测异常：{e}")
            return self._probe_cache

    def fetch_available_models(self, timeout: float = 12) -> list[str]:
        """尝试从远程端点 GET /models 获取该 Key 授权的所有可用模型。"""
        if not self.api_key:
            return ["deepseek-chat", "deepseek-reasoner", "gpt-4o-mini", "gpt-4o", "qwen-plus"]
        try:
            headers = self._auth_headers()
            status, body, _ = _http_get_json(self.models_url, headers, timeout=timeout)
            if status == 200 and isinstance(body, dict):
                data = body.get("data", [])
                models = []
                for item in data:
                    mid = item.get("id") if isinstance(item, dict) else str(item)
                    if mid and isinstance(mid, str):
                        models.append(mid)
                if models:
                    return sorted(models)
            # 若失败或 404，尝试去掉 /v1 再试一次
            alt_url = self.base_url.rstrip("/") + "/models"
            if alt_url != self.models_url:
                status2, body2, _ = _http_get_json(alt_url, headers, timeout=timeout)
                if status2 == 200 and isinstance(body2, dict):
                    data = body2.get("data", [])
                    models = [i.get("id") for i in data if isinstance(i, dict) and i.get("id")]
                    if models: return sorted(models)
        except Exception as e:
            # 审查 P3 修复：改用 logging（GUI 程序 stdout 不宜输出诊断信息）
            import logging as _lg
            _lg.getLogger("ai.client").info("获取模型列表异常：%s", type(e).__name__)
        # 默认推荐清单
        return ["deepseek-chat", "deepseek-reasoner", "gpt-4o", "gpt-4o-mini", "qwen-plus", "qwen-turbo"]

    def _probe_json_mode(self, timeout: float = 15):
        """探测 response_format=json_object 是否被端点支持。

        发一个带 response_format 的极小请求：200 视为支持，其余视为不支持。
        失败时置 False（_call 会据此不再附加 response_format，改走 prompt 约束）。
        """
        try:
            headers = self._auth_headers()
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": 'return {"ok": true}'}],
                "temperature": 0,
                "max_tokens": 16,
                "response_format": {"type": "json_object"},
            }
            status, body, _ = _http_post_json(self.chat_url, headers, payload, timeout)
            return status == 200
        except Exception:
            return False

    def reset_probe(self) -> None:
        """清除在线自检缓存，下次 probe() 会真正联网重测（配置面板用）。"""
        self._probe_cache = None
        self._cap_probe_cache = None

    def capability_probe(self, timeout: float = 15, force: bool = False) -> dict:
        """扩展能力探测四维：连通 / tool_calls / JSON 模式 / 工具参数质量 + 格式变体。

        返回 {ok, tools, json_mode, format, error}——缓存（首次成功/失败后记住；
        force=True 强制重测）。探测失败默认 json 模式（契约兜底不崩）。
        """
        if self._cap_probe_cache is not None and not force:
            return self._cap_probe_cache
        if not self.api_key:
            self._cap_probe_cache = {"ok": False, "tools": "none", "json_mode": False,
                                     "format": "json", "error": "未配置 API Key"}
            return self._cap_probe_cache
        try:
            headers = self._auth_headers()
            payload = {"model": self.model,
                       "messages": [{"role": "user", "content": "ping"}],
                       "temperature": 0, "max_tokens": 1}
            status, body, text = _http_post_json(self.chat_url, headers, payload, timeout)
            if status != 200:
                self._cap_probe_cache = {"ok": False, "tools": "none", "json_mode": False,
                                         "format": "json",
                                         "error": f"模型返回 {status}：{str(text)[:120]}"}
                return self._cap_probe_cache
            # 维度 2/3：tool_calls + json_mode（原生 tools 探测）
            json_ok = bool(self._probe_json_mode(timeout))
            tools_ok = self._probe_tools(timeout)
            if tools_ok:
                fmt = "openai"
                tools = "full"
            elif json_ok:
                fmt = "content_json"   # 无原生 tools → 参数嵌 content + JSON 约束
                tools = "simple"
            else:
                fmt = "json"
                tools = "none"
            self.json_mode = json_ok
            self._cap_probe_cache = {"ok": True, "tools": tools, "json_mode": json_ok,
                                     "format": fmt, "error": ""}
            return self._cap_probe_cache
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", e)
            msg = "连接超时" if isinstance(reason, TimeoutError) else "无法连接"
            self._cap_probe_cache = {"ok": False, "tools": "none", "json_mode": False,
                                     "format": "json", "error": msg}
            return self._cap_probe_cache
        except Exception as e:  # noqa: BLE001
            self._cap_probe_cache = {"ok": False, "tools": "none", "json_mode": False,
                                     "format": "json", "error": f"检测异常：{e}"}
            return self._cap_probe_cache

    def _probe_tools(self, timeout: float = 15) -> bool:
        """探测原生 tools 支持：发带 tools 的极小请求，200 视为支持。"""
        try:
            headers = self._auth_headers()
            payload = {"model": self.model,
                       "messages": [{"role": "user", "content": "调 query_state 查 treasury"}],
                       "temperature": 0, "max_tokens": 32,
                       "tools": [{"type": "function", "function": {
                           "name": "query_state",
                           "parameters": {"type": "object",
                                          "properties": {"target": {"type": "string"}},
                                          "required": ["target"]}}}],
                       "tool_choice": "auto"}
            status, _, _ = _http_post_json(self.chat_url, headers, payload, timeout)
            return status == 200
        except Exception:
            return False

    def enable_tools(self, mode: str) -> None:
        """运行时切换工具模式：auto（自动探测）/ on（强制工具）/ off（强制 JSON）/ simple（强制简化）。

        C1 修复：本方法与同名字符串属性 `enable_tools_mode` 成对使用 ——
        方法负责切换 tool_mode，并**同步字符串开关**，避免两套表示各说各话
        （_tools_active 读字符串，本方法改 tool_mode）。
        """
        mode = str(mode).lower()
        if mode not in ("auto", "on", "off", "simple"):
            mode = "auto"
        self.enable_tools_mode = mode
        if mode == "auto":
            cap = self.capability_probe(force=True)
            if not cap["ok"]:
                self.tool_mode = "error"
            elif cap["tools"] == "full":
                self.tool_mode = "tool_full"
            elif cap["tools"] == "simple":
                self.tool_mode = "tool_simple"
            else:
                self.tool_mode = "json"
        elif mode == "on":
            self.tool_mode = "tool_full"
        elif mode == "off":
            self.tool_mode = "json"
        elif mode == "simple":
            self.tool_mode = "tool_simple"
        else:
            self.tool_mode = "tool_full"

    def _call_with_tools(self, system_prompt: str, user_prompt: str = "",
                         history=None, schemas=None, tool_choice=None,
                         temperature: float = 0.4, max_tokens: int = 500):
        """统一入口（模型适配层）：按 tool_mode 选 schema → _call(tools=) → parse 归一
        → 降级链（工具 → 简化重试 → JSON 契约 → 模板/报错，不伪造）。

        返回 dict 含 tool_calls（结构化，经 parse_tool_calls 归一）或文本/None。

        审查 P1-4 澄清：当前生产中各 *_decide 走 json_mode 纯 JSON 契约，本方法暂无
        生产调用方，作为未来 Function Call 接线预留。实际改状态通道详见各契约 validate
        + 12 步结算/free_effect/_tool_dispatch 消费。
        """
        from ai.client_utils import parse_tool_calls, SIMPLE_TOOL_SCHEMAS, STATE_TOOL_SCHEMAS
        mode = getattr(self, "tool_mode", "tool_full")
        if mode == "error":
            return {"_error": "AI 工具不可用：模型探测失败，请检查配置"}
        # 选 schema（fallback：STATE_TOOL_SCHEMAS 3 通用工具）
        if schemas is None:
            if mode == "tool_simple":
                schemas = SIMPLE_TOOL_SCHEMAS
            elif mode == "tool_full":
                schemas = None   # 用调用方传入或 STATE_TOOL_SCHEMAS
            if not schemas:
                schemas = STATE_TOOL_SCHEMAS
        # 降级链：工具（required）→ 简化重试 → JSON 契约
        for attempt, (sch, choice) in enumerate([
                (schemas, tool_choice or "auto"),
                (SIMPLE_TOOL_SCHEMAS, "auto"),
                (None, None),   # JSON 契约（无 tools）
        ]):
            try:
                if sch is None:
                    raw = self._call(system_prompt, user_prompt, history=history,
                                     temperature=temperature, max_tokens=max_tokens,
                                     json_mode=True)
                else:
                    raw = self._call(system_prompt, user_prompt, history=history,
                                     temperature=temperature, max_tokens=max_tokens,
                                     tools=sch, tool_choice=choice)
                if raw is None:
                    continue
                if isinstance(raw, dict) and raw.get("tool_calls"):
                    calls = parse_tool_calls(raw)
                    if calls:
                        return {"tool_calls": calls, "content": raw.get("content") or ""}
                if sch is None:
                    return raw   # JSON 契约文本
                # 工具调用失败 → 下一级降级
            except Exception:
                continue
        return {"_error": "AI 工具链全部降级失败"}

    @classmethod
    def load_saved(cls):
        """读取已保存配置并返回 AIClient；无配置或读取出错返回 None。"""
        path = cls._config_path()
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            api_key = (cfg.get("api_key") or "").strip()
            if not api_key:
                return None
            return cls(api_key, cfg.get("base_url", ""), cfg.get("model", ""),
                       cfg.get("enable_tools", "auto"),
                       settle_api_key=cfg.get("settle_api_key", ""),
                       settle_base_url=cfg.get("settle_base_url", ""),
                       settle_model=cfg.get("settle_model", ""),
                       fallback_api_key=cfg.get("fallback_api_key", ""),
                       fallback_base_url=cfg.get("fallback_base_url", ""),
                       fallback_model=cfg.get("fallback_model", ""))
        except (OSError, json.JSONDecodeError, ValueError):
            return None

    def __init_cache(self):
        self._cache: dict = {}
        self._cache_hits: int = 0
        self._cache_misses: int = 0

    @staticmethod
    def _state_hash(state_summary) -> str:
        """朝局摘要 hash；朝局变动则失效（同一朝局可命中）。

        审查 P0-1 修复：dict/None 入参先归一为文本再 hash，
        杜绝 'dict' object has no attribute 'encode' 崩溃。
        """
        import hashlib
        if not isinstance(state_summary, str):
            try:
                state_summary = json.dumps(state_summary, ensure_ascii=False, sort_keys=True)
            except Exception:
                state_summary = str(state_summary)
        h = hashlib.md5(state_summary.encode("utf-8", "ignore")).hexdigest()[:16]
        return h

    def _cached_call(self, cache_key: str, state_summary: str,
                     system_prompt: str, user_prompt: str, temperature, max_tokens,
                     json_mode: bool = False, input_key: str = ""):
        """带朝局 hash 的 LRU 缓存包装。命中则直接返回缓存文本。

        input_key：输入差异键（如诏意文本/回合号）——同朝局不同输入不互撞；
        json_mode：透传给 _call（结构调用缓存，同输入同朝局复用）。
        """
        if not hasattr(self, "_cache"):
            self.__init_cache()
        # P2-37：key 含 provider 指纹——切换 provider/模型后旧缓存不得命中
        _prov = f"{self.base_url}|{self.model}"
        key = f"{cache_key}:{input_key}:{_prov}:{self._state_hash(state_summary)}"
        if key in self._cache:
            self._cache_hits += 1
            # 审查 P3 修复（LRU）：命中后重插到队尾（dict 保持插入序）→ 最少使用先淘汰
            val = self._cache.pop(key)
            self._cache[key] = val
            return val
        self._cache_misses += 1
        raw = self._call(system_prompt, user_prompt, temperature=temperature,
                        max_tokens=max_tokens, json_mode=json_mode)
        if raw is not None:
            self._cache[key] = raw
            # 审查 P3 修复（缓存淘汰）：原「超 64 条整体 clear」在朝局抖动时收益不稳；
            # 改为逐条淘汰最久未用（配合上方命中重插 = LRU），保留热点条目。
            while len(self._cache) > 64:
                self._cache.pop(next(iter(self._cache)), None)
        return raw

    def cache_stats(self) -> dict:
        if not hasattr(self, "_cache"):
            self.__init_cache()
        total = self._cache_hits + self._cache_misses
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "rate": (self._cache_hits / total) if total else 0.0,
        }

    # ---------- 底层调用 ----------
    _NET_RETRY = 2        # 瞬时网络错误重试次数（审查 P2-45）
    _NET_BACKOFF = 0.8    # 退避基数（秒）：0.8s / 1.6s

    def _post_with_retry(self, payload, timeout: float = 30):
        """HTTP POST + 瞬时网络错误退避重试（审查 P2-45 修复）。

        仅对网络层异常（超时/连接失败/DNS 抖动）做有限次退避重试；HTTP 4xx/5xx
        仍由 `_call` 按契约降级处理（json_mode / tool_choice 回退），此处不重试。
        """
        import time as _t
        _last = None
        for _i in range(self._NET_RETRY + 1):
            try:
                return _http_post_json(self.chat_url, self._auth_headers(), payload,
                                       timeout=timeout)
            except urllib.error.URLError as e:
                _last = e
                # C4 修复（重复计费）：读取超时意味着请求**可能已被服务端处理并计费**，
                # 重发属非幂等重试。仅对「请求发出前」的连接类失败（DNS/拒绝连接/不可达）
                # 退避重试；超时一律直接上抛，由调用方按契约降级。
                _reason = getattr(e, "reason", None)
                if isinstance(_reason, (socket.timeout, TimeoutError)):
                    raise
                if _i >= self._NET_RETRY:
                    raise
                _t.sleep(self._NET_BACKOFF * (2 ** _i))
        raise _last  # pragma: no cover

    def _call(self, *args, **kwargs):
        """**统一入口**：先主 provider（默认 Agnes），未能完成再回退到兜底 provider（a6api）。

        "未能完成"包括：抛异常（连接失败/超时）、空正文、以及 `json_mode=True` 时
        **拿不到可解析 JSON**（契约注定失败的情形）。回退只做一次，且不在回退内部再回退。
        用户定稿（2026-09-19）：**各种需要 API 的地方先用 Agnes，无法完成再用 a6api**。
        """
        json_mode = bool(kwargs.get("json_mode"))
        err = None
        raw = None
        try:
            raw = self._call_impl(*args, **kwargs)
        except Exception as e:  # noqa: BLE001  主 provider 失败不立即抛出，先试兜底
            err = e
        if self._usable_raw(raw, json_mode):
            return raw
        if not self._has_fallback():
            if err is not None:
                raise err
            return raw
        log.warning("主 provider（%s）未完成，回退兜底（%s）", self.model, self.fallback_model)
        with self._provider_scope("fallback"):
            self._in_fallback = True
            try:
                raw2 = self._call_impl(*args, **kwargs)
            except Exception as e2:  # noqa: BLE001  兜底也失败 → 抛出主因（更贴近玩家配置）
                log.warning("兜底 provider 亦失败：%s", e2)
                raise (err if err is not None else e2)
            finally:
                self._in_fallback = False
        if self._usable_raw(raw2, json_mode):
            self.fallback_hits += 1
            log.warning("已由兜底 provider 完成（累计 %d 次）", self.fallback_hits)
            return raw2
        if err is not None:
            raise err
        return raw2 if raw2 is not None else raw

    def _call_impl(self, system_prompt: str, user_prompt: str = "",
                   history=None, temperature: float = 0.8, max_tokens: int = 800,
                   tools=None, messages=None, json_mode: bool = False,
                   tool_choice=None):
        """底层调用。若传 tools 且端点支持，返回 dict 含 tool_calls；否则返回文本。

        返回：
          - 成功文本：str
          - 成功带工具调用：dict {"content":..., "tool_calls":[...]}
          - 失败：None

        json_mode=True 时尝试附加 response_format=json_object（结构调用用）；
        端点不支持（返回错误含 response_format/json_object）则自动降级为纯
        prompt 约束并重试一次，不伪造成功。

        T1（AI 只通过 Function Call 返回结构化变更）：
        - tool_choice="required" 时 payload 附加 tool_choice="required"——AI 必须调工具；
        - AI 未返回 tool_calls（直接文本）→ 丢弃重请求一次（附消息「请调用工具」），
          仍无工具调用才返回原响应；
        - 端点不支持 tool_choice=required（返回错误）→ 探测降级：记
          self.tools_required_supported=False 并回退 "auto" 重试一次。
        """
        if not self.available:
            return None
        if messages is None:
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                # P2-16：历史/玩家文本经不可信边界定界（防注入改写系统规程）
                messages.extend(_sanitize_history(history, limit=8))
            if user_prompt:
                messages.append({"role": "user", "content": user_prompt})
            else:
                # 兼容性修复（2026-09-19，实测）：部分 OpenAI 兼容网关**要求 messages 必须含
                # user 角色**，只发 system 会被直接拒绝——
                #   Agnes：HTTP 400 `No user query found in messages.`
                #   a6api/gemini：表现为契约失败（模型拿不到"待办"而乱答）
                # 补一条中性占位 user（不改任务语义：任务本身在 system 规程里），
                # 使 AI 可选/可换供应商，不因网关差异整体失败。
                messages.append({"role": "user", "content": "（请依上开规程作答。）"})
        # Agnes 网关防护（实测 2026-09-19）：
        #   ① 上限：其网关对 max_tokens 有硬上限（65536，超出直接 400 invalid_request）；
        #   ② **下限**：`agnes-2.5-flash` 是**思考型**模型，reasoning 先吃掉预算——实测把
        #      max_tokens 设成契约所需的 300 会返回**半截 JSON**（甚至 content=""），
        #      使整个回合以 AI_CONTRACT_FAILED 失败。故结算走 Agnes 时预算至少 8192。
        if "agnes" in (self.chat_url or "").lower():
            max_tokens = max(8192, min(int(max_tokens or 0), 32000))
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        want_required = bool(tools) and tool_choice == "required" \
            and getattr(self, "tools_required_supported", True)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "required" if want_required else "auto"
        # json_mode：仅当端点未被确认不支持时附加；被拒则降级重试一次
        want_json = bool(json_mode) and self.json_mode is not False
        if want_json:
            payload["response_format"] = {"type": "json_object"}
        for attempt in (0, 1):
            try:
                # 审查 P2-45：网络层瞬时错误退避重试（原 URLError 直接抛出，无重试）
                status, data, _ = self._post_with_retry(payload, timeout=30)
            except urllib.error.URLError as e:
                from core.errors import AIRuntimeError as _AIRE
                reason = getattr(e, "reason", e)
                if isinstance(reason, TimeoutError):
                    # 审查 P2-43：超时码具备真实生产者（原 AI_TIMEOUT 仅定义、无产出）
                    raise _AIRE("AI 服务连接超时（限时 30s）：请检查网络或 base_url 后重试。",
                                code="AI_TIMEOUT") from e
                raise _AIRE(f"AI 服务连接失败：{reason}") from e
            except Exception as e:  # noqa: BLE001
                from core.errors import AIRuntimeError as _AIRE
                raise _AIRE(f"AI 调用异常（{type(e).__name__}）：{e}") from e
            if status < 400:
                break
            err = ""
            try:
                err = (data or {}).get("error", {}).get("message", "") or str(data)[:200]
            except Exception:
                err = f"HTTP {status}"
            # json_mode 降级：端点不支持 response_format → 记录并移除后重试一次
            if attempt == 0 and want_json and ("response_format" in err or "json_object" in err):
                self.json_mode = False
                payload.pop("response_format", None)
                continue
            # T1 降级：端点不支持 tool_choice=required → 记录并回退 auto 重试一次
            if attempt == 0 and want_required and "tool_choice" in err:
                self.tools_required_supported = False
                payload["tool_choice"] = "auto"
                continue
            from core.errors import AIRuntimeError as _AIRE
            # 审查 P2-43：鉴权失败给明确错误码（原仅把状态码拼进文本，无法诊断）
            if status in (401, 403):
                raise _AIRE(f"AI 鉴权失败（HTTP {status}）：请检查 api_key 与 base_url。",
                            code="AI_AUTH_FAILED") from None
            raise _AIRE(f"AI 服务返回错误（HTTP {status}）：{err}") from None
        try:
            msg = data["choices"][0]["message"]
        except (KeyError, TypeError, IndexError) as e:
            from core.errors import AIRuntimeError as _AIRE
            raise _AIRE(f"AI 返回格式异常（HTTP {status}）：{e}") from e
        usage = data.get("usage", {})
        if isinstance(usage, dict) and usage:
            self._add_usage(usage)
        else:
            # A3（tiktoken 计量，可选）：端点未回 usage 时按消息估算，
            # 标记 estimated=True 与端点真值区分；估算失败静默（计量缺失不影响游戏）。
            try:
                from ai.token_meter import estimate_messages_tokens
                _ep, _ec = estimate_messages_tokens(
                    messages, out_text=str(msg.get("content") or ""), model=self.model)
                if _ep or _ec:
                    self._add_usage({"prompt_tokens": _ep, "completion_tokens": _ec,
                                     "estimated": True})
            except Exception:
                pass
        if tools and msg.get("tool_calls"):
            tcs = []
            for tc in msg["tool_calls"]:
                tcs.append({
                    "id": tc.get("id", ""),
                    "function": {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("function", {}).get("arguments", "{}"),
                    },
                })
            return {"content": msg.get("content") or "", "tool_calls": tcs}
        # T1：tool_choice=required 时 AI 未返回 tool_calls（直接文本）→ 丢弃重请求一次
        if want_required and attempt == 0:
            messages = messages + [{"role": "assistant", "content": msg.get("content") or ""},
                                   {"role": "user", "content":
                                    "你上次没有调用工具，请调用 update_state 或 query_state 完成结构化变更。"}]
            payload["messages"] = messages
            try:
                headers = self._auth_headers()
                status, data, _ = _http_post_json(self.chat_url, headers, payload, timeout=30)
            except Exception:
                return msg.get("content") or ""
            if status < 400:
                try:
                    # C5 修复（漏计费）：T1 重发（tool_choice=required 未返回工具时的
                    # 补发）此前**未记账**——该响应同样被 provider 计费，导致 Token
                    # 计量表与真实账单偏离。此处按与主路径同一口径补记 usage。
                    _u2 = data.get("usage", {})
                    if isinstance(_u2, dict) and _u2:
                        self._add_usage(_u2)
                    msg2 = data["choices"][0]["message"]
                    if msg2.get("tool_calls"):
                        tcs = [{"id": tc.get("id", ""),
                                "function": {"name": tc.get("function", {}).get("name", ""),
                                             "arguments": tc.get("function", {}).get("arguments", "{}")}}
                               for tc in msg2["tool_calls"]]
                        return {"content": msg2.get("content") or "", "tool_calls": tcs}
                except (KeyError, TypeError, IndexError):
                    pass
        content = msg.get("content") or ""
        if not content and not msg.get("tool_calls") and max_tokens < 4096:
            # 空响应自愈（2026-09-19 实测）：**思考型模型**在 max_tokens 偏小时会把预算
            # 全部用在 reasoning 上，`content` 为空字符串（Agnes `agnes-2.5-flash`：
            # max_tokens=300 → content=""，而 usage 有 completion token）。
            # 结算契约拿到空串即整体失败（AI_CONTRACT_FAILED），故此处加倍预算**重发一次**；
            # 仍为空才按失败返回（不伪造内容）。
            payload["max_tokens"] = max(8192, max_tokens * 8)
            log.warning("AI 返回空正文（max_tokens=%s）→ 以 %s 重发一次",
                        max_tokens, payload["max_tokens"])
            try:
                status, data, _ = self._post_with_retry(payload, timeout=30)
                if status < 400:
                    _u3 = data.get("usage", {})
                    if isinstance(_u3, dict) and _u3:
                        self._add_usage(_u3)          # 重发同样计费，不得漏记
                    _m3 = data["choices"][0]["message"]
                    if _m3.get("content"):
                        return _m3["content"]
            except Exception as e:  # noqa: BLE001  自愈失败仍返回空串，由上层判契约失败
                log.warning("空响应重发失败：%s", e)
        return content

    def _postprocess(self, raw, validator, fallback, retry_prompt=None,
                     retry_user=None, retry_temp: float = 0.3, ranges=None):
        """验收：解析 → validator 校验 → 复读检测；失败回喂修复或兜底。

        三方案：ranges（叙事数值区间）传入时，AI 文本字段过 _validate_narrative_numbers
        （数字须落在注入区间，区间外改写定性词）；无 ranges 跳过（向后兼容）。

        审查 P2-5 修复：解析/校验失败时，按失败阶段区分错误码（AI_EMPTY_RESPONSE/
        AI_INVALID_JSON/AI_CONTRACT_FAILED），覆盖 fallback 默认的 AI_NOT_CONFIGURED，
        使 _error 码具备可诊断性。
        """
        obj = _extract_json(raw) if raw else None
        # 审查 P2-5：按失败阶段定错误码（供 fallback 结果覆盖）
        _fail_code = None
        if not raw:
            _fail_code = "AI_EMPTY_RESPONSE"
        elif obj is None:
            _fail_code = "AI_INVALID_JSON"
        # A1（jsonschema 结构层，可选）：业务 validator 之前先过 JSON Schema 结构校验。
        # schema 未注册 / jsonschema 未安装 → 跳过（业务 validator 仍兜底，行为不变）；
        # 结构不符 → 判契约失败，schema 错误详情回喂修复（见下方 retry_p 增强）。
        _schema_err = ""
        if obj is not None:
            try:
                _caller = sys._getframe(1).f_code.co_name
            except Exception:
                _caller = ""
            _ok, _schema_err = _schema_check(_caller, obj)
            if not _ok:
                obj = None
                if _fail_code is None:
                    _fail_code = "AI_CONTRACT_FAILED"
        obj = validator(obj) if obj is not None else None
        if obj is None and _fail_code is None:
            _fail_code = "AI_CONTRACT_FAILED"
        if obj is None:
            # 回喂修复：把校验失败如实告知模型，补调一次；仍失败才兜底
            if retry_prompt and retry_user:
                try:
                    retry_p = (retry_prompt
                               + "\n【程序校验提示】上一次输出未通过契约校验，"
                                 "请严格按 JSON 契约重新输出，勿附加解释文字。")
                    if _schema_err:
                        # A1：结构层错误详情回喂（字段路径+原因），提高一次修复成功率
                        retry_p += f"\n【结构错误】{_schema_err}"
                    retry_raw = self._call(retry_p, retry_user,
                                           temperature=retry_temp,
                                           max_tokens=900, json_mode=True)
                    obj2 = _extract_json(retry_raw) if retry_raw else None
                    obj2 = validator(obj2) if obj2 is not None else None
                    if obj2 is not None:
                        obj = obj2
                except Exception as _re:  # noqa: BLE001
                    obj = None
                    # 审查 P2-43：保留底层错误码（AI_TIMEOUT / AI_AUTH_FAILED 等）供 fallback 携带
                    _fail_code = getattr(_re, "code", "") or _fail_code
            if obj is None:
                fb = fallback()
                # 审查 P2-5：用阶段失败码覆盖 fallback 默认 AI_NOT_CONFIGURED
                if _fail_code and isinstance(fb, dict) and fb.get("_error"):
                    from content.data import AI_ERROR_CODES
                    if _fail_code in AI_ERROR_CODES:
                        fb["_error"] = _fail_code
                        fb["message"] = AI_ERROR_CODES.get(_fail_code, "")
                return fb
        # 安全过滤：所有 AI 文本统一过敏感词，命中即按不可用返回，不向玩家展示
        # P2-17：词库缺失/损坏时 _safety_filter 亦返回 hit=True（未校验 → 暂停高风险
        # 文本），此处补显式状态标记，避免静默 fail-open。
        for _field in ("reply", "advice", "report", "narrative", "body",
                       "commentary", "court_report", "gazette", "memo",
                       "objections", "executions"):
            _txt = obj.get(_field)
            if isinstance(_txt, str) and _txt:
                _txt, _hit = _safety_filter(_txt)
                if _hit:
                    _fb = fallback()
                    if not safety_filter_operational() and isinstance(_fb, dict):
                        _fb["safety_filter"] = "unavailable"
                        _fb["safety_degraded"] = True
                    return _fb
                # 三方案：叙事-数值一致（数字须落在注入区间，区间外改写定性词）
                if ranges:
                    _txt, _flagged = _validate_narrative_numbers(_txt, ranges)
                obj[_field] = _txt
        # 复读检测（针对有 reply/advice/report 等文本字段）
        # B2 语义升级：语义后端可用时加语义相似度判定（阈值 0.92，抓"换皮复读"——
        # 同义改写字面相似度低但语义相同）；后端不可用（未装 onnxruntime/模型缺失）
        # 自动回落纯字面检测，行为与旧版完全一致。
        txt = obj.get("reply") or obj.get("advice") or obj.get("report") or obj.get("narrative") or ""
        if txt and self._prev_texts:
            _recent = self._prev_texts[-3:]
            if max(_similar(txt, p) for p in _recent) > 0.6:
                return fallback()
            try:
                from ai.semantic import semantic_repetition_hit
                if semantic_repetition_hit(txt, _recent):
                    return fallback()
            except Exception:
                pass
        if txt:
            self._prev_texts.append(txt)
        return obj


# ============================================================
# 统一拟旨解析入口（原 ai/decree.py 内联）
# ============================================================
def parse_decree(text: str, state_summary: str = "", is_secret: bool = False) -> dict:
    """解析一道拟旨，返回结构化结果。

    圣旨 / 密旨 都由玩家自由拟定，交由 AI 推演判定：
    - 类别：fixed_tech / fixed_finance / fixed_army / fixed_construction（走规则程序）
            其余为 free_edict（自由推演）
    - 执行时机：instant（即时）/ longterm（长期，月度推进核销）

    全程依赖 AI，无离线兜底。AI 不可用时返回带 `_error` 标记的结构（T8 分级降级：
    拟旨模板兜底，不代拟效果；与 AIClient.parse_decree 失败路径一致），由 UI 提示配置。
    """
    client = AIClient.load_saved()
    if client is None:
        from ai.narrative_fallback import fallback_decree
        return fallback_decree(text, is_secret)
    return client.parse_decree(text, state_summary, is_secret=is_secret)



# ============================================================
# AI 不可用时的错误标记（不伪造文本）
# ============================================================
