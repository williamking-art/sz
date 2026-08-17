# -*- coding: utf-8 -*-
"""MapCanvas：北宋水墨大舆图（纯地形底图版）。

- 底图：assets/map/empire_bg.png（纯水墨地形，无行政区色块/描边/标签）。
- 桌板：assets/map/desk_bg.png（cover 铺满画布作为底层背景）。
- 交互：滚轮以光标为中心缩放、左键拖拽平移、点击空白处不触发选区。
- 注：分区着色、点击命中、hover 高亮等归一化坐标功能已移除，舆图仅作氛围底图。
"""
import os
import tkinter as tk

try:
    from PIL import Image, ImageTk
    _HAVE_PIL = True
except Exception:
    _HAVE_PIL = False

from content.data import empire_bg_path, desk_bg_path

# 底图源尺寸（与 empire_bg.png 一致）
_BASE_W, _BASE_H = 1000, 800
_MIN_SCALE, _MAX_SCALE = 0.35, 1.6
_SNAP = 4  # 拖拽阈值（像素），超过才视为拖拽而非点击


class MapCanvas(tk.Canvas):
    def __init__(self, master, state, on_select=None, **kw):
        super().__init__(master, **kw)
        self.state = state
        self.scale = 1.0
        self.off_x = 0
        self.off_y = 0
        self._desk_cache = {}
        self._bg_cache = {}
        self._desk_tk = None
        self._bg_tk = None
        self._drag = None  # 拖拽状态 (sx, sy, ox, oy, moved)

        self.bind("<Configure>", self._resize_redraw)
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set_state(self, state):
        self.state = state
        self._draw()

    # ---------------- 坐标换算（仅用于视图定位，无归一化数据依赖） ----------------
    def _to_canvas(self, nx, ny):
        bw, bh = _BASE_W * self.scale, _BASE_H * self.scale
        return self.off_x + nx * bw, self.off_y + ny * bh

    def _to_norm(self, x, y):
        bw, bh = _BASE_W * self.scale, _BASE_H * self.scale
        return (x - self.off_x) / bw, (y - self.off_y) / bh

    # ---------------- 绘制 ----------------
    def _resize_redraw(self, event=None):
        if event is not None:
            w, h = event.width, event.height
        else:
            w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2:
            return
        fit = min(w / _BASE_W, h / _BASE_H, 1.0)
        self.scale = fit
        self.off_x = (w - _BASE_W * self.scale) / 2
        self.off_y = (h - _BASE_H * self.scale) / 2
        self._draw()

    def _load_desk(self, w, h):
        """加载桌板底图（cover 铺满画布）。"""
        if not _HAVE_PIL:
            return None
        w = max(2, int(w))
        h = max(2, int(h))
        key = f"{w}x{h}"
        if key in self._desk_cache:
            return self._desk_cache[key]
        try:
            path = desk_bg_path()
            if not os.path.exists(path):
                return None
            img = Image.open(path)
            cw, ch = img.size
            scale = max(w / cw, h / ch)
            nw, nh = max(1, int(cw * scale)), max(1, int(ch * scale))
            img = img.resize((nw, nh), Image.LANCZOS)
            left = (nw - w) // 2
            top = (nh - h) // 2
            img = img.crop((left, top, left + w, top + h))
            tk_img = ImageTk.PhotoImage(img)
            self._desk_cache[key] = tk_img
            if len(self._desk_cache) > 6:
                self._desk_cache.pop(next(iter(self._desk_cache)))
            return tk_img
        except Exception:
            return None

    def _load_bg(self):
        """按当前 scale 量化档位取缓存的缩放舆图。"""
        if not _HAVE_PIL:
            return None
        w = max(2, int(_BASE_W * self.scale))
        h = max(2, int(_BASE_H * self.scale))
        key = int(w // 40)
        if key in self._bg_cache:
            return self._bg_cache[key]
        try:
            path = empire_bg_path()
            if not os.path.exists(path):
                return None
            img = Image.open(path)
            img = img.resize((w, h), Image.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
            self._bg_cache[key] = tk_img
            if len(self._bg_cache) > 12:
                self._bg_cache.pop(next(iter(self._bg_cache)))
            return tk_img
        except Exception:
            return None

    def _draw(self):
        self.delete("all")
        # 最底层：深色木纹桌板
        cw, ch = self.winfo_width(), self.winfo_height()
        self._desk_tk = self._load_desk(cw, ch)
        if self._desk_tk is not None:
            self.create_image(0, 0, anchor="nw", image=self._desk_tk, tag="desk")
        else:
            self.create_rectangle(0, 0, cw, ch, fill="#4a3225", tag="desk")
        # 上层：纯地形底图（empire_bg.png，不含任何行政区色块/描边/标签）
        self._bg_tk = self._load_bg()
        if self._bg_tk is not None:
            self.create_image(self.off_x, self.off_y, anchor="nw",
                              image=self._bg_tk, tag="bg")
        else:
            self.create_rectangle(self.off_x, self.off_y,
                                  self.off_x + _BASE_W * self.scale,
                                  self.off_y + _BASE_H * self.scale,
                                  fill="#efe3c8", tag="bg")

        # 年号水印已移除（HUD 状态条已显示年号季节）

    # ---------------- 交互 ----------------
    def _on_wheel(self, event):
        if not _HAVE_PIL:
            return
        mx, my = event.x, event.y
        old = self.scale
        factor = 1.12 if event.delta > 0 else 1 / 1.12
        new = min(_MAX_SCALE, max(_MIN_SCALE, old * factor))
        if new == old:
            return
        new = min(new, 1.0)
        self.off_x = mx - (mx - self.off_x) * (new / old)
        self.off_y = my - (my - self.off_y) * (new / old)
        self.scale = new
        self._draw()

    def _on_press(self, event):
        self._drag = (event.x, event.y, self.off_x, self.off_y, False)

    def _on_drag(self, event):
        if self._drag is None:
            return
        sx, sy, ox, oy, _ = self._drag
        dx, dy = event.x - sx, event.y - sy
        if abs(dx) > _SNAP or abs(dy) > _SNAP:
            self._drag = (sx, sy, ox, oy, True)
        self.off_x = ox + dx
        self.off_y = oy + dy
        self._draw()

    def _on_release(self, event):
        # 纯地形底图：点击不触发选区/详情，仅做拖拽/平移
        self._drag = None
