# -*- coding: utf-8 -*-
"""宋祚 · 美术资源加载（缓存，纯 tkinter 实现，无第三方依赖）

素材位于 assets/events|ui|portraits/，按事件 id / 用途命名。
风格参考 MingSalvageSim（仿古工笔宣纸 + 朱批），但为 songzuo 专属北宋题材生成。

注：Python 3.14 的 tkinter.PhotoImage 原生支持 PNG，故无需 Pillow。
缩放用 subsample（整数倍）近似。
"""
import os
import sys
from tkinter import PhotoImage

def _asset_root():
    # 打包后用 sys._MEIPASS；开发时用项目根目录
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_BASE = os.path.join(_asset_root(), "assets")
_CACHE = {}


def _path(sub, name):
    return os.path.join(_BASE, sub, name)


def load(sub, name, size=None):
    """加载 PNG 为 PhotoImage。size=(w,h) 时尽量用 subsample 缩小到接近目标。
    返回 PhotoImage 或 None。结果按 (path,size) 缓存，避免重复 IO / 被 GC。"""
    p = _path(sub, name)
    if not os.path.exists(p):
        return None
    key = (p, size)
    if key in _CACHE:
        return _CACHE[key]
    try:
        ph = PhotoImage(file=p)
    except Exception:
        return None
    if size:
        iw, ih = ph.width(), ph.height()
        tw, th = size
        # 取使图片不超过目标尺寸的最大整数倍
        sx = max(1, iw // tw)
        sy = max(1, ih // th)
        s = max(sx, sy)
        if s > 1:
            ph = ph.subsample(s, s)
    _CACHE[key] = ph
    return ph


def event_image(event_id, size=(260, 340)):
    return load("events", f"{event_id}.png", size)


def edict_skin(size=(680, 540)):
    return load("ui", "edict_skin.png", size)


def memo_skin(size=None):
    return load("ui", "memo_skin.png", size)


def court_bg(size=(760, 300)):
    return load("ui", "court_bg.png", size)


def audience_bg(size=(880, 600)):
    """官员奏对弹层背景（卷轴边框 + 标题匾 + 左肖像预留 + 右行文区）。"""
    return load("ui", "audience_bg.png", size)


def portrait(kind, size=(180, 240)):
    return load("portraits", f"{kind}.png", size)


def seal_image(size=(96, 96)):
    """朱印国玺图标（用于主菜单徽标、玉玺角标）。用 PNG 因 tkinter 不支持 ico。"""
    return load("", "seal.png", size)


def minister_portrait(kind="civil", size=(180, 240)):
    """文臣/武将立绘。kind: civil / military"""
    name = "minister" if kind == "civil" else "general"
    return load("portraits", f"{name}.png", size)


def emperor_portrait(state, size=(180, 240)):
    """按游戏年份/月份返回对应年龄段与季节的皇帝常服立绘。"""
    year = getattr(state, "year", 1101)
    month = getattr(state, "month", 1)
    if year <= 1115:
        age = "young"
    elif year <= 1125:
        age = "middle"
    else:
        age = "old"
    season = "winter" if month in (11, 12, 1, 2, 3) else "summer"
    ph = load("portraits", f"emperor_{age}_{season}.png", size)
    if ph is None:
        # 兜底：任一皇帝图
        for a in ("young", "middle", "old"):
            for s in ("summer", "winter"):
                ph = load("portraits", f"emperor_{a}_{s}.png", size)
                if ph:
                    break
            if ph:
                break
    return ph
