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


def _sync_public(src_path: str) -> str:
    """合成立绘同步到前端静态目录，返回前端相对 URL（portraits/ministers/x.png）。

    同步失败（无前端目录）返回 ''，不影响档案取数。
    """
    import os
    import shutil
    try:
        repo = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))            # game/core/.. → 仓库根
        dst_dir = os.path.join(repo, "_dev_tools", "frontend", "public",
                               "portraits", "ministers")
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, os.path.basename(src_path))
        if (not os.path.exists(dst)
                or os.path.getmtime(dst) < os.path.getmtime(src_path)):
            shutil.copy2(src_path, dst)
        return "ministers/" + os.path.basename(src_path)
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
            p = get_portrait_path(name)
            if p:
                portrait = _sync_public(p)
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
