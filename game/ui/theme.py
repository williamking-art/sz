"""宋祚 · 视觉主题工具集

所有绘制函数均为纯函数（除 _cache 缓存外无状态），可被 UI 各面板安全复用。
升级 T-028：新增宋版书页风格浮层装饰（panel_skin / gold_frame / cloud_corner / section_head）。
"""
from __future__ import annotations

import os
import random
import tkinter as tk
from tkinter import font as tkfont
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------------------------------------------------------------------------
# 色彩体系（宋式文人美学）
# ---------------------------------------------------------------------------
PAPER = "#f6ecd6"           # 宣纸米黄
PAPER_DARK = "#efe2c4"      # 宣纸暗部
INK = "#2b1d12"             # 墨色文字
INK_LIGHT = "#5a4a3a"       # 浅墨色
RED = "#8a2b22"             # 朱红
RED_DARK = "#7a1f1f"        # 深朱
GOLD = "#caa24a"            # 描金
GOLD_LIGHT = "#e8d49c"      # 高光金
GOLD_DARK = "#8f6e28"       # 暗金
CREAM = "#fffaf0"           # 象牙白
SHADOW = "#2b1d12"          # 阴影用墨

# 朱批四档色（吉/常/警/急）——供面板统一引用
VERDANT = "#3f6655"         # 吉
COMMON = "#5a5240"          # 常
ALERT = "#8a671e"           # 警
URGENT = "#a24332"          # 急

# T-028 历史别名兼容（部分面板仍引用旧名）
DX_GOOD = VERDANT
DX_NORMAL = COMMON
DX_WARN = ALERT
DX_URGENT = URGENT


def status_color(value, thresholds, default):
    """按阈值表返回状态色。thresholds=[(上限, 颜色), ...]，value 从高到低匹配。"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    for limit, color in sorted(thresholds, key=lambda x: x[0], reverse=True):
        if v >= limit:
            return color
    return default

# ---------------------------------------------------------------------------
# 字体注册
# ---------------------------------------------------------------------------
_fonts_registered = False


def register_fonts():
    """注册自定义字体（如本地打包了 KaiTi 等字体）。"""
    global _fonts_registered
    if _fonts_registered:
        return
    try:
        # 开发/打包统一路径：优先使用 frozen 目录
        base = getattr(__import__("sys"), "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        font_dir = os.path.join(os.path.dirname(base), "assets", "fonts")
        if os.path.isdir(font_dir):
            for fn in os.listdir(font_dir):
                if fn.lower().endswith((".ttf", ".otf", ".ttc")):
                    try:
                        tkfont.Font(file=os.path.join(font_dir, fn), family=fn.rsplit(".", 1)[0])
                    except Exception:
                        pass
    except Exception:
        pass
    _fonts_registered = True


def get_font_family(preferred: Tuple[str, ...] = ("KaiTi", "楷体", "STKaiti", "SimKai")) -> str:
    """按回退链返回可用中文字体族名。"""
    families = set(tkfont.families())
    for name in preferred:
        if name in families:
            return name
    return "Microsoft YaHei"


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------
_cache: dict = {}


def _get(k, factory):
    if k not in _cache:
        _cache[k] = factory()
    return _cache[k]


# ---------------------------------------------------------------------------
# 基础纹理
# ---------------------------------------------------------------------------
def paper_texture(width: int, height: int, seed: int = 7) -> tk.PhotoImage:
    """生成宣纸纹理 PhotoImage，已缓存。"""
    key = ("paper", width, height, seed)

    def _make():
        rng = random.Random(seed)
        img = Image.new("RGB", (width, height), PAPER)
        px = img.load()
        for _ in range(width * height // 12):
            x = rng.randint(0, width - 1)
            y = rng.randint(0, height - 1)
            base = rng.choice((PAPER, PAPER_DARK, CREAM))
            r, g, b = int(base[1:3], 16), int(base[3:5], 16), int(base[5:7], 16)
            v = rng.randint(-10, 10)
            px[x, y] = (
                max(0, min(255, r + v)),
                max(0, min(255, g + v)),
                max(0, min(255, b + v)),
            )
        return ImageTk.PhotoImage(img)

    try:
        from PIL import ImageTk
        return _get(key, _make)
    except Exception:
        # 无 PIL 时退化
        ph = tk.PhotoImage(width=width, height=height)
        ph.put(PAPER, to=(0, 0, width, height))
        return ph


def gradient_image(width: int, height: int, top: str, bottom: str) -> tk.PhotoImage:
    """垂直渐变 PhotoImage，已缓存。"""
    key = ("grad", width, height, top, bottom)

    def _make():
        from PIL import Image, ImageDraw, ImageTk
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)
        t = tuple(int(top[i:i + 2], 16) for i in (1, 3, 5))
        b = tuple(int(bottom[i:i + 2], 16) for i in (1, 3, 5))
        for y in range(height):
            ratio = y / max(1, height - 1)
            color = tuple(int(t[i] + (b[i] - t[i]) * ratio) for i in range(3))
            draw.line([(0, y), (width, y)], fill=color)
        return ImageTk.PhotoImage(img)

    return _get(key, _make)


# ---------------------------------------------------------------------------
# 几何绘制
# ---------------------------------------------------------------------------
def round_rect(canvas: tk.Canvas, x1, y1, x2, y2, radius, **kwargs):
    """在 Canvas 上绘制圆角矩形。"""
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def circle_icon(canvas, cx, cy, r, fill, outline=None, width=1, tag=None):
    return canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline=outline, width=width, tag=tag)


def seal_icon(canvas, cx, cy, r, fill=RED, outline=GOLD, width=2, tag=None):
    """印章式圆钮（朱红底+描金边）。"""
    items = []
    items.append(canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline=outline, width=width, tag=tag))
    # 内细金线
    items.append(canvas.create_oval(cx - r * 0.75, cy - r * 0.75, cx + r * 0.75, cy + r * 0.75, outline=GOLD_LIGHT, width=1, tag=tag))
    return items


def gold_corner(canvas, x, y, size, mirror=False, color=GOLD, width=2, tag=None):
    """右上角/左下角 L 形描金角标。"""
    if mirror:
        canvas.create_line(x + size, y, x, y, x, y + size, fill=color, width=width, tag=tag, smooth=True)
    else:
        canvas.create_line(x, y, x + size, y, x + size, y + size, fill=color, width=width, tag=tag, smooth=True)


# ---------------------------------------------------------------------------
# 宋版书页风格装饰（T-028 新增）
# ---------------------------------------------------------------------------
def panel_skin_image(width: int, height: int, seed: int = 7) -> tk.PhotoImage:
    """
    生成宋版书页风格面板底图：平整宣纸底 + 轻微暗角 + 描金内框。
    返回 PhotoImage 并缓存。
    """
    key = ("panel_skin", width, height, seed)

    def _make():
        from PIL import Image, ImageDraw, ImageFilter, ImageTk
        rng = random.Random(seed)
        img = Image.new("RGB", (width, height), PAPER)
        draw = ImageDraw.Draw(img)

        # 1. 极轻微的宣纸纤维（平整、无褶皱）
        px = img.load()
        for _ in range(max(1, width * height // 80)):
            x = rng.randint(0, width - 1)
            y = rng.randint(0, height - 1)
            base = rng.choice((PAPER, PAPER_DARK, CREAM))
            r, g, b = int(base[1:3], 16), int(base[3:5], 16), int(base[5:7], 16)
            v = rng.randint(-6, 6)
            px[x, y] = (
                max(0, min(255, r + v)),
                max(0, min(255, g + v)),
                max(0, min(255, b + v)),
            )

        # 2. 轻微暗角（四角向内渐晕，模拟古籍翻阅感，而非褶皱）
        pad = min(width, height) // 6
        for i in range(pad):
            alpha = int(255 * (i / pad) ** 2)
            shade = (239, 226, 196, alpha)
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            ov_draw = ImageDraw.Draw(overlay)
            ov_draw.rectangle([i, i, width - 1 - i, height - 1 - i], outline=shade, width=1)
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(img)

        # 3. 描金内框（双线）
        margin = 12
        draw.rectangle([margin, margin, width - margin, height - margin], outline=GOLD, width=2)
        draw.rectangle([margin + 4, margin + 4, width - margin - 4, height - margin - 4], outline=GOLD_LIGHT, width=1)

        return ImageTk.PhotoImage(img)

    return _get(key, _make)


def panel_skin(canvas: tk.Canvas, x: int, y: int, width: int, height: int, seed: int = 7, tag: str | None = None):
    """在 Canvas 上贴宋版书页风格面板底图。"""
    img = panel_skin_image(width, height, seed)
    return canvas.create_image(x, y, image=img, anchor="nw", tag=tag)


def gold_frame(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int,
               radius: int = 16, outer_width: int = 2, inner_width: int = 1,
               outer_color: str = GOLD, inner_color: str = GOLD_LIGHT,
               tag: str | None = None):
    """描金双线圆角边框（外粗内细）。"""
    # 外线
    round_rect(canvas, x1, y1, x2, y2, radius, outline=outer_color, width=outer_width, tag=tag)
    # 内线
    round_rect(canvas, x1 + 3, y1 + 3, x2 - 3, y2 - 3, max(1, radius - 3),
               outline=inner_color, width=inner_width, tag=tag)


def cloud_corner(canvas: tk.Canvas, cx: int, cy: int, size: int = 28,
                 quadrant: str = "tl", color: str = GOLD, tag: str | None = None):
    """
    绘制云纹角标。
    quadrant: tl(左上), tr(右上), bl(左下), br(右下)
    """
    # 用两段圆弧/螺旋近似云纹
    s = size
    arcs = []
    if quadrant == "tl":
        arcs = [(cx, cy, cx + s, cy + s, 180, 90), (cx + s * 0.15, cy + s * 0.15, cx + s * 0.55, cy + s * 0.55, 180, 90)]
    elif quadrant == "tr":
        arcs = [(cx - s, cy, cx, cy + s, 270, 90), (cx - s * 0.55, cy + s * 0.15, cx - s * 0.15, cy + s * 0.55, 270, 90)]
    elif quadrant == "bl":
        arcs = [(cx, cy - s, cx + s, cy, 90, 90), (cx + s * 0.15, cy - s * 0.55, cx + s * 0.55, cy - s * 0.15, 90, 90)]
    elif quadrant == "br":
        arcs = [(cx - s, cy - s, cx, cy, 0, 90), (cx - s * 0.55, cy - s * 0.55, cx - s * 0.15, cy - s * 0.15, 0, 90)]

    items = []
    for (x0, y0, x1, y1, start, extent) in arcs:
        items.append(canvas.create_arc(x0, y0, x1, y1, start=start, extent=extent,
                                       style="arc", outline=color, width=2, tag=tag))
    return items


def section_head(canvas: tk.Canvas, x: int, y: int, width: int, text: str,
                 fill: str = RED, text_color: str = CREAM,
                 font=None, tag: str | None = None):
    """宋式分区抬头：朱红小底 + 描金线 + 文字。"""
    h = 24
    items = []
    items.append(round_rect(canvas, x, y, x + width, y + h, h // 2, fill=fill, outline=GOLD, width=1, tag=tag))
    if font is None:
        font = (get_font_family(), 12)
    items.append(canvas.create_text(x + width // 2, y + h // 2, text=text, fill=text_color,
                                    font=font, tag=tag))
    # 下描金线
    items.append(canvas.create_line(x, y + h + 4, x + width, y + h + 4, fill=GOLD, width=1, tag=tag))
    return items


def section_underline(cv, x, y, width, color=GOLD, thick=2):
    """宋式双线装饰下划线"""
    cv.create_line(x, y, x + width, y, fill=color, width=thick)
    cv.create_line(x, y + 4, x + width, y + 4, fill=color, width=1)


def progress_bar(canvas: tk.Canvas, x: int, y: int, width: int, height: int,
                 value, maxv, radius: int = 6, tag: str | None = None):
    """绘制宋式圆角进度条。value/maxv 自动钳位，maxv<=0 时仅显示空槽。"""
    try:
        v = float(value) if value is not None else 0.0
        m = float(maxv) if maxv is not None else 0.0
    except (TypeError, ValueError):
        v, m = 0.0, 0.0

    ratio = max(0.0, min(1.0, v / m)) if m > 0 else 0.0

    # 背景槽
    round_rect(canvas, x, y, x + width, y + height, radius,
               fill=PAPER_DARK, outline=GOLD_LIGHT, width=1, tag=tag)

    fill_w = int(width * ratio)
    if fill_w <= 0:
        return

    # 填充色按剩余比例分段（吉/常/警/急）
    if ratio >= 0.75:
        fill = VERDANT
    elif ratio >= 0.4:
        fill = COMMON
    elif ratio >= 0.2:
        fill = ALERT
    else:
        fill = URGENT

    r = min(radius, height // 2, fill_w)
    if r > 0:
        # 左侧圆角帽
        canvas.create_oval(x, y, x + 2 * r, y + height,
                           fill=fill, outline="", tag=tag)
        # 主体矩形
        if fill_w > 2 * r:
            canvas.create_rectangle(x + r, y, x + fill_w, y + height,
                                    fill=fill, outline="", tag=tag)
    else:
        canvas.create_rectangle(x, y, x + fill_w, y + height,
                                fill=fill, outline="", tag=tag)
