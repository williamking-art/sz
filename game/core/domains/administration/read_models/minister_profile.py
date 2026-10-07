# -*- coding: utf-8 -*-
"""宋祚 · 群臣档案（大臣卡片数据，供 HTTP readouts 与测试共用）。

迁移补齐：该数据原在 Tk 面板（`ui/panels_govern._minister_card_data`）与后端
`/api/readouts` 内联各一份；Tk 废弃后统一下沉本模块（单一权威源）。

- 数据源：`content.ministers.data.MINISTERS`（born/role/faction）+ persona.style（性格一句话）
  + `content.codex_text.CODEX_MINISTER_BIO`（A14 简介，缺失时按职司程序生成）。
- 脱敏：只出可见档案（年龄/职衔/派系/性情/生平），loyalty / corruption 等隐藏数值绝不出现。
- 只读：不写状态、不依赖 Tk。
"""
from __future__ import annotations


def _portrait_url(src_path: str) -> str:
    """合成立绘 → 前端可用 URL（**不写任何源码/public 目录**）。

    2026-09-19 整改（依据 `analysis/portrait_system_design.md` §一.3）：
    原 `_sync_public` 把合成图**复制进 `game/frontend/public/`** —— 运行期写安装目录，
    打包后只读会失败，并发生成还会争用；且产物落到入库目录需靠 .gitignore 兜底。
    现改为：合成图留在后端缓存目录（`content/ministers/portraits/_composed/`，
    按需再生、不入库），前端走受控路由 `GET /api/portrait/<file>` 取图。

    返回以 `/` 开头的**绝对路径 URL**（前端不得再拼 `./portraits/` 前缀）。
    无前端需求/参数异常时返回 ""。"""
    try:
        import os
        fname = os.path.basename(str(src_path or ""))
        if not fname or "/" in fname or "\\" in fname:
            return ""
        return "/api/portrait/" + fname
    except Exception:
        return ""


def build_minister_profiles(state) -> dict:
    """→ {大臣名: {age, role, faction, style, bio}}（只读，不写状态）。"""
    from content.ministers.data import MINISTERS
    from content.codex_text import CODEX_MINISTER_BIO
    from content.ministers.persona import get_persona
    try:
        year = int(getattr(state, "year", 0) or 0)
    except Exception:
        year = 0
    out = {}
    for name, fig in MINISTERS.items():
        fig = fig or {}
        born = fig.get("born")
        age = max(0, year - int(born)) if isinstance(born, int) and year else None
        role = str(fig.get("role", "") or "")
        style = ""
        try:
            style = str((get_persona(name) or {}).get("style", "") or "")
        except Exception:
            style = ""
        bio = str(CODEX_MINISTER_BIO.get(name, "") or "")
        if not bio:
            # 无 A14 简介 → 按职司程序生成（以句号收束，与 Tk 版一致）
            bio = f"{name}，{role}。" if role else f"{name}，在朝任事。"
        # 分层立绘：头部层 + 按品级官服层合成（官级变化即换官服，头部不变）
        portrait = ""
        tier = ""
        try:
            from content.ministers.data import get_portrait_path, minister_tier
            tier = minister_tier(name)
            # 立绘服色随**运行态身份**（文档 §五：服饰优先级含"是否在任"）：
            # 已罢黜/已身故 → 士人襕衫（shi）；在任 → 按档案品级（宗室→亲王服）。
            try:
                _st = state.minister_status(name)
            except Exception:  # noqa: BLE001
                _st = "active"
            if _st in ("dismissed", "dead"):
                tier = "shi"
            p = get_portrait_path(name, tier=tier)
            if p:
                portrait = _portrait_url(p)
        except Exception:
            portrait = ""
        out[name] = {
            "age": age,
            "role": role,
            "faction": str(fig.get("faction", "") or ""),
            "style": style,
            "bio": bio,
            "portrait": portrait,      # 前端相对 URL（portraits/ministers/x.png）
            "tier": tier,              # 服色档：zi/fei/lv/qing/shi/qinwang
        }
    return out
