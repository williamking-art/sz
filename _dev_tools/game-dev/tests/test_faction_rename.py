# -*- coding: utf-8 -*-
"""利益集团**改名**的验收测试（2026-09-19 用户定稿）。

改名（改用 `FACTION_POP_BASIS.aliases` 里已备好的名称）：
    东南士人 → **中立派**     （党争之外的第三方/不结党的士商，不绑定东南）
    西军集团 → **军功集团**   （兵/官僚 POP 中持军功立场者）
    宦官集团 → **皇党集团**   （依附皇权的那一部分，不绑定京畿）

用户口径：**旧档不迁移**（按新开局重建 factions）。本文件锁定三件事：
  ① 新名生效且是唯一主键；
  ② **旧名仍可反查**（留在 aliases 里 → `resolve_faction_key` 归一，AI/事件文本不炸）；
  ③ 旧档载入**不崩且不迁移** —— 旧名不作为幽灵派系混入，`faction_split` /
     各诏令 `faction_stances` 里的旧名键被清理（否则 `calc_decree_execution_rate`
     会 `self.factions[旧名]` KeyError → 读档即崩）。
"""
import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import FACTION_NAMES, FACTION_POP_BASIS  # noqa: E402
from core.faction_basis import resolve_faction_key  # noqa: E402
from core.game_state import GameState  # noqa: E402

NEW_TO_OLD = {"中立派": "东南士人", "军功集团": "西军集团", "皇党集团": "宦官集团"}


def test_new_names_are_the_only_primary_keys():
    assert set(FACTION_NAMES) == {"新党", "旧党", "皇党集团", "军功集团", "中立派"}
    for old in NEW_TO_OLD.values():
        assert old not in FACTION_NAMES, f"旧名 {old} 不应再是主键"


def test_old_names_still_resolve_via_aliases():
    """旧名留在 aliases 里 → AI/旧文本出现旧名时仍能归一（改名不破坏在玩内容）。"""
    for new, old in NEW_TO_OLD.items():
        assert resolve_faction_key(old) == new, f"{old} 应归一为 {new}"
        assert old in (FACTION_POP_BASIS[new].get("aliases") or []), \
            f"{new} 的 aliases 应保留旧名 {old}"


def test_legacy_named_save_loads_without_crash_and_without_migration(tmp_path, monkeypatch):
    """旧档（含旧名）载入：不崩；factions 按新开局重建；旧名键被清理。"""
    import core.save_load as sl

    monkeypatch.setattr(sl, "SAVE_DIR", str(tmp_path), raising=False)
    s = GameState("史实")
    assert sl.save_game(s, 7) is True
    path = sl._slot_path(7)
    raw = json.loads(open(path, encoding="utf-8").read())

    # 注入"旧档"特征：旧名派系 + 旧名立场占比 + 旧名诏令立场
    raw["factions"] = {
        "东南士人": {"influence": 88, "satisfaction": 90, "cohesion": 50, "leader": "曾布"},
        "新党": {"influence": 11, "satisfaction": 12, "cohesion": 13, "leader": "蔡京"},
    }
    raw["faction_split"] = {"东南士人": 0.5, "西军集团": 0.3, "新党": 0.2}
    raw["pending_decrees"] = [{"title": "旧诏", "faction_stances": {"宦官集团": 1, "新党": -1}}]
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(raw, ensure_ascii=False))

    st = sl.load_game(7)
    assert st is not None, "含旧名的旧档不得读档失败"
    # ① 同名派系**照常合并**（进度不丢），旧名不迁移、不混入
    assert set(st.factions) == set(FACTION_NAMES)
    assert st.factions["新党"]["influence"] == 11, "同名派系（新党）的进度不应被丢弃"
    assert "东南士人" not in st.factions, "旧名不得作为幽灵派系混入"
    # ② 旧名键被清理（否则 calc_decree_execution_rate 会 KeyError）
    assert "东南士人" not in (st.faction_split or {})
    assert "西军集团" not in (st.faction_split or {})
    assert set(st.faction_split or {}) <= set(FACTION_NAMES)
    for dec in st.pending_decrees or []:
        if isinstance(dec, dict):
            assert set(dec.get("faction_stances") or {}) <= set(FACTION_NAMES)
    # ③ 能正常结算（真踩过 KeyError 的路径）
    from core.settlement import run_monthly_settlement
    run_monthly_settlement(st, 0)
