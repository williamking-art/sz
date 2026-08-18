# -*- coding: utf-8 -*-
"""宋祚 · tkinter GUI 界面层（宣纸朱红仿古风）

视觉：
- 宣纸底（#f6ecd6）+ 朱红（#8a2b22）+ 深褐字（#2b1d12）+ 描金（#caa24a）
- 楷体标题（KaiTi/STKaiti），微软雅黑正文

布局（全屏舆图 + 悬浮控件）：
- 地图（MapCanvas）铺满整个窗口（relwidth=1, relheight=1）作为底图，不内缩；
- 所有交互控件浮于舆图之上：
  · 顶部状态条（朱红徽章 + 年号季节 + 数值胶囊）
  · 左侧常驻「在办」栏
  · 右侧竖排悬浮钮（州县 / 军政 / 科技 / 工程）
  · 底部 dock（朝堂 / 群臣 / 朝报 / 个人行止 / 拟旨）+ 右下角回合推演朱印
- 功能面板以浮层呈现（半透明遮罩 + 居中宣纸卡片），用于拟诏 / 事件 / 结局。
- 全程单 tk.Tk() 主窗口。

逻辑层命令（core.commands）与 AI（ai.client）保持不变，本文件仅负责呈现。

拆分说明：原单类 SongZuoApp 按职责域拆分为多个 Mixin，
本文件保留类定义、生命周期方法与 __init__，面板构建方法见：
  ui/panels_basic.py   ui/panels_menu.py   ui/panels_core.py
  ui/panels_govern.py  ui/panels_economy.py  ui/panels_meta.py
共享常量/工具见 ui/gui_common.py。外部接口 __all__ = ["SongZuoApp"] 不变。
"""
import os
import sys
import random
import tkinter as tk

from content.data import (
    PERSONAL_ACTIONS, FACTION_NAMES,
    YAMEN_LIST, YAMEN_INFO, PREFECTURE_LIST,
    FIXED_PROCEDURES,
)
from ai.client import AIClient, _org_by_affiliation
import ai.decree as ai_decree
import ui.theme as theme
from core.commands import AIRuntimeError as _AIRuntimeError

from ui.gui_common import (
    PAPER, PAPER2, CARD, INK, DIM, RED, RED_D, GOLD, GREEN,
    BORDER, SEAL_BG, KAI, SANS, DECREE_CATEGORIES,
    _bar, _format_effects, _judge_effects,
)
from ui.panels_basic import PanelsBasicMixin
from ui.panels_menu import PanelsMenuMixin
from ui.panels_core import PanelsCoreMixin
from ui.panels_govern import PanelsGovernMixin
from ui.panels_economy import PanelsEconomyMixin
from ui.panels_meta import PanelsMetaMixin


class SongZuoApp(PanelsBasicMixin, PanelsMenuMixin, PanelsCoreMixin,
                 PanelsGovernMixin, PanelsEconomyMixin, PanelsMetaMixin):
    def __init__(self, root):
        self.root = root
        self.state = None
        self.ai_client = AIClient.load_saved()  # 自动恢复上次保存的 AI 配置（无则离线）
        # 前后端分离：所有游戏逻辑经 backend 调用（本地直跑 / 远程 Rust 服务可切换）
        from backend.client import BackendClient
        self.backend = BackendClient.create()
        self._pending_logs = []
        self._inited = False
        self._current_panel = None
        self._active_overlay = None
        self._current_minister = None
        self._anim = []            # 动画对象注册表（呼吸/hover/波纹/加载环）
        self._setup_window_icon()
        self._tick_seq = 0
        self._overlay_mask = None  # 浮层暗化遮罩
        self._register_fonts()
        self._load_font_scale()
        self._configure_root()
        self.container = tk.Frame(root, bg=PAPER)
        self.container.pack(fill="both", expand=True)
        # 窗口尺寸变化时让地图/状态条等跟随重绘（响应式布局）
        self.root.bind("<Configure>", self._on_root_resize)
        self._last_root_size = (0, 0)
        self._build_main_menu()
        # 启动常驻动画 tick（呼吸/波纹/加载环由注册对象自行绘制）
        self._start_tick()

    def _setup_window_icon(self):
        """设置窗口图标：优先 .ico，失败时回退到 assets/seal.png 用 PhotoImage。"""
        errs = []
        try:
            self.root.iconbitmap(self._resource("icon.ico"))
            return
        except Exception as e:
            errs.append(f"iconbitmap: {e}")
        try:
            from assets import load
            icon = load("", "seal.png", size=(64, 64))
            if icon:
                self.root.iconphoto(True, icon)
                return
        except Exception as e:
            errs.append(f"iconphoto: {e}")
        # 兜底：静默记录，不阻断启动
        self._pending_logs.append(f"[warn] 窗口图标加载失败：{'; '.join(errs)}")

    def _register_fonts(self):
        """注册打包字体（若有），并确定运行期楷体名与字号档位。"""
        global KAI
        try:
            name = theme.register_fonts(self.root)
            if name:
                KAI = name                       # 保留 gui.py 命名空间的既有行为
                self._kai_actual = name
            else:
                self._kai_actual = KAI           # 回退 KaiTi
        except Exception:
            self._kai_actual = "KaiTi"

    def _start_tick(self):
        self._tick_seq = 0
        self._tick()

    def _tick(self):
        """常驻动画帧循环：驱动所有注册动画对象的 step()。"""
        self._tick_seq += 1
        for a in self._anim:
            try:
                if getattr(a, "alive", True):
                    a.step(self._tick_seq)
            except Exception:
                pass
        self._anim = [a for a in self._anim if getattr(a, "alive", True)]
        self.root.after(50, self._tick)

    def register_anim(self, obj):
        if obj not in self._anim:
            self._anim.append(obj)

    def _configure_root(self):
        self.root.title("宋祚")
        self.root.geometry("1040x680")
        self.root.minsize(760, 520)
        # 默认窗口化全屏（最大化但保留系统窗口栏与任务栏）
        try:
            self.root.state("zoomed")
        except Exception:
            pass
        self._setup_window_icon()
        self.root.configure(bg=PAPER)
        self.root.option_add("*Background", PAPER)
        self.root.option_add("*Foreground", INK)

    def _on_root_resize(self, event):
        """窗口尺寸变化时重绘地图与状态条，使界面跟随窗口缩放。"""
        if event.widget is not self.root:
            return
        w, h = self.root.winfo_width(), self.root.winfo_height()
        if (w, h) == self._last_root_size or w < 2 or h < 2:
            return
        # 节流：尺寸变化超过阈值才重绘
        lw, lh = self._last_root_size
        if abs(w - lw) < 4 and abs(h - lh) < 4:
            return
        self._last_root_size = (w, h)
        # 地图随窗口尺寸重绘（不重建，仅刷新缩放）
        if getattr(self, "_map_cv", None) is not None:
            # 延迟一帧，等 MapCanvas 自身 Configure 事件尺寸稳定
            self.root.after(30, self._map_cv._resize_redraw)
        # 左侧在办卡片响应式宽度，避免与右侧竖排按钮重叠
        try:
            self._adjust_left_card_width()
        except Exception:
            pass
        # 状态条刷新
        try:
            self._refresh_status()
        except Exception:
            pass
        # 同步浮层卡片尺寸，避免窗口缩放后浮层超出或挡住 dock 区域。
        try:
            self._update_overlay_geometry()
        except Exception:
            pass

    def _adjust_left_card_width(self):
        """根据窗口宽度调整左侧在办卡片宽度，确保不与右侧竖排按钮栏重叠，
        并按顶部状态条实际底边下移，避免被横条遮挡。"""
        left = getattr(self, "_hud_left", None)
        if left is None:
            return
        w = self.root.winfo_width()
        # 右侧条宽 60、右外边距 12；左侧 x=12；中间至少留 12 间隙
        available = max(180, w - 12 - 12 - 12 - 60)
        new_w = min(260, available)
        left.configure(width=int(new_w))
        # 顶部状态条底边（y=12 + height=50 + 边框 2）后留 24 间隙，避免贴得太近
        top_bottom = 12 + 50 + 2
        left.place_configure(y=top_bottom + 24)

    # ---------- 日志 ----------
    def _log(self, msg):
        if not hasattr(self, "_log_lines"):
            self._log_lines = []
        self._log_lines.append(msg)
        self._log_lines = self._log_lines[-200:]


__all__ = ["SongZuoApp"]
