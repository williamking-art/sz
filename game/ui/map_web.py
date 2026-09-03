# -*- coding: utf-8 -*-
"""宋祚 · MapLibre Web 舆图 × pywebview 集成层。

职责（框架席位）：
- 本地 HTTP 服务：以 127.0.0.1 随机端口伺服 assets/map/web/（禁 file:// 直开，
  规避 WebView2 对 file:// 下 fetch 的 CORS 限制），MIME 含 .geojson。
- 桥接枢纽：JS→Python（pywebview js_api / POST /bridge 双通道）统一入
  _BridgeHub；附带 Tk root 时经 root.after(0, ...) 回主线程，禁止跨线程直改控件。
- Python→JS：push_state 合并状态并经 window.evaluate_js 下发
  （window.SongZuoMap.applyState）；浏览器降级模式由页面轮询 GET /state。
- 生命周期：WebMapController.open() 在守护线程拉起 pywebview（Tk 共存），
  无 pywebview 时自动降级 webbrowser 打开，全功能保留。

用法（面板层示例）：
    from ui.map_web import WebMapController
    self.webmap = WebMapController(root, on_feature=self._on_map_feature)
    self.webmap.open()                      # 'pywebview' 或 'browser'
    self.webmap.set_active_regimes(["金"])  # 金崛起后激活
    self.webmap.select("city", "开封府")
    self.webmap.close()

依赖：pywebview 为可选依赖（pip install pywebview）；缺失时降级浏览器，
不阻断游戏主流程。
"""
from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:  # 可选依赖：缺失时降级系统浏览器
    import webview as _webview
except Exception:  # pragma: no cover - 环境相关
    _webview = None

__all__ = ["WebMapController", "MapBridgeApi", "web_dir", "webview_available"]


def webview_available() -> bool:
    return _webview is not None


# ---------------------------------------------------------------------------
# 资源路径（与 content/data.py 的 frozen 逻辑一致）
# ---------------------------------------------------------------------------
def _base_dir() -> str:
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # game/


def web_dir() -> str:
    return os.path.join(_base_dir(), "assets", "map", "web")


_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".geojson": "application/geo+json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


# ---------------------------------------------------------------------------
# 桥接枢纽：JS → Python（统一入口，Tk 安全回主线程）
# ---------------------------------------------------------------------------
class _BridgeHub:
    """收集 JS 侧事件并分发到 Python 回调。

    - 附带 Tk root：回调经 root.after(0, ...) 投递到主线程执行；
    - 无 root（独立启动器/测试）：当前线程直接调用。
    所有回调异常被捕获记入日志，绝不反冲 webview/Tk 线程。
    """

    def __init__(self, root=None):
        self._root = root
        self._lock = threading.Lock()
        self._handlers = {}
        self._logs = []

    def register(self, method: str, fn) -> None:
        with self._lock:
            self._handlers[method] = fn

    def dispatch(self, method: str, payload) -> dict:
        with self._lock:
            fn = self._handlers.get(method)
        if fn is None:
            self.log(f"[warn] 未注册的桥接方法：{method}")
            return {"ok": False, "error": "unknown method"}
        if self._root is not None:
            try:
                self._root.after(0, self._safe_call, fn, method, payload)
            except Exception:  # root 已销毁等场景：退化为直接调用
                self._safe_call(fn, method, payload)
        else:
            self._safe_call(fn, method, payload)
        return {"ok": True}

    def _safe_call(self, fn, method, payload):
        try:
            fn(payload)
        except Exception as e:  # 面板回调异常不反冲桥线程
            self.log(f"[error] {method} 回调异常：{e!r}")

    def log(self, msg: str) -> None:
        with self._lock:
            self._logs.append(msg)
            if len(self._logs) > 200:
                del self._logs[:100]

    def recent_logs(self, n: int = 30):
        with self._lock:
            return list(self._logs[-n:])


# ---------------------------------------------------------------------------
# Python → JS 状态盒（seq 单调递增；浏览器模式轮询拉取）
# ---------------------------------------------------------------------------
class _StateBox:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = {}
        self._seq = 0

    def update(self, patch: dict) -> int:
        with self._lock:
            self._state.update(patch or {})
            self._seq += 1
            return self._seq

    def snapshot(self, since: int = 0):
        with self._lock:
            return self._seq, dict(self._state) if self._seq > since else None


# ---------------------------------------------------------------------------
# pywebview js_api 对象（JS: window.pywebview.api.xxx(payload)）
# ---------------------------------------------------------------------------
class MapBridgeApi:
    def __init__(self, hub: _BridgeHub):
        self._hub = hub

    def map_ready(self, payload=None):  # noqa: N802 - js_api 命名保持小驼峰语义
        return self._hub.dispatch("map_ready", payload or {})

    def feature_click(self, payload=None):
        return self._hub.dispatch("feature_click", payload or {})

    def map_event(self, payload=None):
        return self._hub.dispatch("map_event", payload or {})


# ---------------------------------------------------------------------------
# 本地 HTTP 服务
# ---------------------------------------------------------------------------
class _MapHandler(BaseHTTPRequestHandler):
    server_version = "SongZuoMap/1.0"
    web_root = ""       # 由工厂注入
    hub: _BridgeHub = None
    box: _StateBox = None

    # ---- 工具 ----
    def _send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, full: str):
        ext = os.path.splitext(full)[1].lower()
        ctype = _MIME.get(ext, "application/octet-stream")
        try:
            with open(full, "rb") as f:
                body = f.read()
        except OSError:
            self._send_json({"error": "read failed"}, 500)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _resolve(self, path: str):
        rel = path.lstrip("/") or "index.html"
        if rel.endswith("/"):
            rel += "index.html"
        root = os.path.realpath(self.web_root)
        full = os.path.realpath(os.path.join(root, rel))
        # 防目录穿越：必须落在 web_root 内
        if full != root and not full.startswith(root + os.sep):
            return None
        if not os.path.isfile(full):
            return None
        return full

    # ---- GET ----
    def do_GET(self):  # noqa: N802 - http.server 约定
        path, _, query = self.path.partition("?")
        if path == "/healthz":
            return self._send_json({"ok": True})
        if path == "/state":
            since = 0
            try:
                since = int(dict(pair.split("=", 1) for pair in query.split("&") if "=" in pair)
                            .get("since", "0"))
            except Exception:
                since = 0
            seq, state = self.box.snapshot(since)
            return self._send_json({"seq": seq, "state": state})
        full = self._resolve(path)
        if full is None:
            return self._send_json({"error": "not found", "path": path}, 404)
        self._send_file(full)

    # ---- POST /bridge（浏览器降级通道） ----
    def do_POST(self):  # noqa: N802
        path, _, _ = self.path.partition("?")
        if path != "/bridge":
            return self._send_json({"error": "not found"}, 404)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n) if n > 0 else b"{}"
            msg = json.loads(raw.decode("utf-8"))
            method = str(msg.get("method", ""))
            payload = msg.get("payload") or {}
        except Exception as e:
            return self._send_json({"ok": False, "error": f"bad request: {e!r}"}, 400)
        result = self.hub.dispatch(method, payload)
        self._send_json(result)

    def log_message(self, fmt, *args):  # 静默：路由进 hub 日志
        if self.hub is not None:
            try:
                self.hub.log("[http] " + (fmt % args))
            except Exception:
                pass


def _make_server(hub: _BridgeHub, box: _StateBox, root_dir: str,
                 port: int = 0) -> ThreadingHTTPServer:
    handler = type("_BoundMapHandler", (_MapHandler,), {
        "web_root": root_dir, "hub": hub, "box": box,
    })

    class _Server(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    return _Server(("127.0.0.1", port), handler)


# ---------------------------------------------------------------------------
# 控制器：面板层唯一入口
# ---------------------------------------------------------------------------
class WebMapController:
    """Web 舆图生命周期与桥接控制。

    线程模型：
    - Tk 共存模式（root 不为 None）：webview.start() 跑在守护线程，
      JS 事件经 _BridgeHub → root.after 回主线程；push_state 可在任意线程调用。
    - 独立模式（root 为 None）：open(run_in_thread=False) 时阻塞当前线程，
      回调直接在 webview 线程执行（调用方自行保证线程安全）。
    """

    def __init__(self, root=None, on_feature=None, on_ready=None, on_closed=None,
                 title: str = "宋祚 · 舆图", width: int = 1180, height: int = 780,
                 port: int = 0):
        self.root = root
        self.title = title
        self._width, self._height = width, height
        self._port = port                  # 0 = 自动分配；指定则固定端口
        self._on_feature = on_feature      # (kind, name, props, lnglat)
        self._on_ready = on_ready          # (info: dict)
        self._on_closed = on_closed        # ()
        self._hub = _BridgeHub(root)
        self._box = _StateBox()
        self._server = None
        self._server_thread = None
        self._window = None
        self._wv_thread = None
        self._mode = None                  # 'pywebview' | 'browser'
        self._loaded = threading.Event()
        self._closed = threading.Event()
        self._lock = threading.Lock()
        self._register_handlers()

    # ---- 内部 ----
    def _register_handlers(self):
        self._hub.register("map_ready", self._h_map_ready)
        self._hub.register("feature_click", self._h_feature_click)
        self._hub.register("map_event", self._h_map_event)

    def _h_map_ready(self, payload):
        self._loaded.set()
        self._flush_state()
        if self._on_ready:
            self._on_ready(payload or {})

    def _h_feature_click(self, payload):
        if not self._on_feature:
            return
        props = payload.get("props") or {}
        lnglat = payload.get("lnglat") or [None, None]
        self._on_feature(
            str(payload.get("kind", "")),
            str(payload.get("name", "")),
            props,
            (lnglat[0], lnglat[1]),
        )

    def _h_map_event(self, payload):
        # 预留：selection_cleared / zoom 等页面事件；当前仅记日志
        self._hub.log(f"[map_event] {payload}")

    def _on_window_loaded(self, *_args):
        self._loaded.set()
        self._flush_state()

    def _on_window_closed(self, *_args):
        if self._closed.is_set():
            return
        self._closed.set()
        if self._on_closed:
            try:
                if self.root is not None:
                    self.root.after(0, self._on_closed)
                else:
                    self._on_closed()
            except Exception:
                pass

    def _flush_state(self):
        """把最新状态推给页面（pywebview 通道）。evaluate_js 线程安全。"""
        win = self._window
        if win is None or not self._loaded.is_set():
            return
        seq, state = self._box.snapshot(0)
        if state is None:
            return
        js = ("window.SongZuoMap && window.SongZuoMap.applyState(" +
              json.dumps(state, ensure_ascii=False) + ");")
        try:
            win.evaluate_js(js)
        except Exception as e:
            self._hub.log(f"[warn] evaluate_js 失败：{e!r}")

    def _start_server(self):
        root_dir = web_dir()
        if not os.path.isfile(os.path.join(root_dir, "index.html")):
            raise RuntimeError(f"舆图资源缺失：{root_dir}")
        self._server = _make_server(self._hub, self._box, root_dir, self._port)
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.2},
            daemon=True, name="songzuo-map-http")
        self._server_thread.start()

    def _run_webview_blocking(self):
        """在当前线程阻塞运行 webview 循环（独立模式）。"""
        ended = False
        try:
            try:
                _webview.start(private_mode=False)
                ended = True
            except TypeError:  # 旧版 pywebview 无 private_mode
                _webview.start()
                ended = True
        except Exception as e:
            self._hub.log(f"[error] webview 循环异常：{e!r}")
            if not self._loaded.is_set():
                # 循环启动即失败（如缺 WebView2 运行时）→ 降级浏览器，不误报关闭
                self._mode = "browser"
                try:
                    webbrowser.open(self.url)
                except Exception:
                    pass
                return
        finally:
            # 仅当窗口仍存活（close() 尚未复位）时上报关闭，避免 join 超时后二次触发
            if (ended or self._loaded.is_set()) and self._window is not None:
                self._on_window_closed()

    def _run_webview_threaded(self):
        """Tk 共存模式：守护线程运行 webview 循环。"""
        self._wv_thread = threading.Thread(
            target=self._run_webview_blocking,
            daemon=True, name="songzuo-map-webview")
        self._wv_thread.start()

    # ---- 公开 API ----
    @property
    def url(self) -> str:
        if self._server is None:
            return ""
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/index.html"

    @property
    def mode(self):
        return self._mode

    def is_open(self) -> bool:
        return (self._mode == "pywebview" and not self._closed.is_set()) \
            or (self._mode == "browser" and self._server is not None)

    def wait_ready(self, timeout: float = 8.0) -> bool:
        """等待页面 map_ready。注意：Tk 共存模式下勿在主线程调用
        （回调经 root.after 投递，主线程阻塞会互等）；仅供独立启动器/测试用。"""
        return self._loaded.wait(timeout)

    def open(self, run_in_thread: bool | None = None,
             mode: str = "auto") -> str:
        """启动舆图窗口。返回实际模式：'pywebview' | 'browser'。

        mode: 'auto'（优先 pywebview，缺失降级浏览器）/ 'browser'（强制浏览器）。
        run_in_thread: None 时自动——有 Tk root 则线程化，否则阻塞当前线程。
        """
        if self._window is not None or self._mode is not None:
            return self._mode  # 重入防护：已打开过则直接返回当前模式
        with self._lock:
            if self._server is None:
                self._start_server()
        if mode == "browser" or _webview is None:
            self._mode = "browser"
            webbrowser.open(self.url)
            self._hub.log("[info] pywebview 不可用，已降级系统浏览器：" + self.url)
            return self._mode

        if run_in_thread is None:
            run_in_thread = self.root is not None
        try:
            self._window = _webview.create_window(
                self.title, self.url,
                js_api=MapBridgeApi(self._hub),
                width=self._width, height=self._height,
                min_size=(640, 460),
                background_color="#f1e5c8")
            self._window.events.loaded += self._on_window_loaded
            self._window.events.closed += self._on_window_closed
        except Exception as e:
            self._hub.log(f"[warn] pywebview 窗口创建失败，降级浏览器：{e!r}")
            self._window = None
            self._mode = "browser"
            webbrowser.open(self.url)
            return self._mode

        self._mode = "pywebview"
        if run_in_thread:
            self._run_webview_threaded()
        else:
            self._run_webview_blocking()
        return self._mode

    # ---- 状态下发（任意线程可调） ----
    def push_state(self, state: dict) -> bool:
        """合并下发状态。键见 index.html applyState：
        hud / active_regimes / hidden_regimes / sub_owners / regime_owners /
        focus / select / markers。"""
        if not isinstance(state, dict) or not state:
            return False
        self._box.update(state)
        if self._mode == "pywebview":
            self._flush_state()
        return True

    def set_hud(self, era=None, year=None, month=None, season=None) -> bool:
        hud = {}
        if era is not None:
            hud["era"] = era
        if year is not None:
            hud["year"] = year
        if month is not None:
            hud["month"] = month
        if season is not None:
            hud["season"] = season
        return self.push_state({"hud": hud}) if hud else False

    def set_active_regimes(self, names) -> bool:
        """强制显示的境外政权（如 金崛起 → ['金']）；配合 hidden_regimes 用。"""
        return self.push_state({"active_regimes": list(names or [])})

    def set_hidden_regimes(self, names) -> bool:
        """强制隐藏的境外政权（如 辽收缩 → ['辽']）。"""
        return self.push_state({"hidden_regimes": list(names or [])})

    def set_sub_owners(self, mapping: dict) -> bool:
        """分路单独易主（如宋北伐取燕云：{'南京道': '宋', '西京道': '宋'}）。
        数据侧权威在 geo_admin.set_subdivision_owner，本方法只同步舆图显示。"""
        if not mapping:
            return False
        return self.push_state({"sub_owners": dict(mapping)})

    def set_regime_owners(self, mapping: dict) -> bool:
        """政权整体易主（金崛起代辽：{'辽': '金'}）。数据侧级联改写分路
        用 geo_admin.set_regime_owner(cascade=True)，本方法只同步舆图显示。"""
        if not mapping:
            return False
        return self.push_state({"regime_owners": dict(mapping)})

    def focus(self, lng=None, lat=None, zoom=None, bounds=None,
              padding=None, max_zoom=None) -> bool:
        f = {}
        if bounds is not None:
            f["bounds"] = list(bounds)
            if padding is not None:
                f["padding"] = padding
            if max_zoom is not None:
                f["maxZoom"] = max_zoom
        elif lng is not None and lat is not None:
            f["lng"], f["lat"] = lng, lat
            if zoom is not None:
                f["zoom"] = zoom
        return self.push_state({"focus": f}) if f else False

    def select(self, kind: str, name: str) -> bool:
        return self.push_state({"select": {"kind": kind, "name": name}})

    def clear_select(self) -> bool:
        return self.push_state({"select": None})

    def set_markers(self, markers) -> bool:
        """自定义朱印标注：[{lng, lat, label, kind}]，kind='warn' 用暗金。"""
        return self.push_state({"markers": list(markers or [])})

    # ---- 关闭 ----
    def close(self, wait_timeout: float = 3.0) -> None:
        win = self._window
        if win is not None and not self._closed.is_set():
            try:
                win.destroy()
            except Exception:
                pass
        if self._wv_thread is not None:
            self._wv_thread.join(timeout=wait_timeout)
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
        # 复位生命周期状态，允许再次 open()
        self._window = None
        self._wv_thread = None
        self._mode = None
        self._loaded.clear()
        self._closed.clear()

    def recent_logs(self, n: int = 30):
        return self._hub.recent_logs(n)


def open_map(root=None, **kw) -> WebMapController:
    """便捷入口：创建并打开舆图，返回控制器。"""
    ctl = WebMapController(root=root, **kw)
    ctl.open()
    return ctl
