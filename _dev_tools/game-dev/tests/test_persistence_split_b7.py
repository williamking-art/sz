# -*- coding: utf-8 -*-
"""第七包回归：save_load 槽位/迁移机械迁入 foundation/persistence/ 后的不变量。

四条各管一种"看起来成功实则已断"的失败：
 ① 旧路径公开面与同一性（转发桩是否真的没换实现）；
 ② `_slot_path` 移动后**仍能被重定向**（否则测试会写进玩家真实存档目录）；
 ③ `_migrate_pops_to_seats` 的桥导入改道后**真的执行到拆分**——它把 import 失败
    吞成 `return 0`，所以"没报错"完全不能证明接通，必须断言迁移条数 > 0；
 ④ `save_game` **建的目录**与**写入的目录**同源（实测本批全量跑红 3 例后补的守卫）。
"""
import json
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

import core.save_load as SL  # noqa: E402
import core.foundation.persistence.migrations as MG  # noqa: E402
import core.foundation.persistence.slots as SP  # noqa: E402
from core.game_state import GameState  # noqa: E402

MOVED = ["SLOT_MIN", "_slot_ok", "_slot_path", "get_save_slots",
         "_merge_regions", "_migrate_pops_to_seats"]


# ── ① 旧路径公开面 + 同一性 ──────────────────────────────────────
def test_moved_symbols_still_visible_on_old_path():
    missing = [n for n in MOVED if not hasattr(SL, n)]
    assert not missing, f"旧路径 core.save_load 丢了符号：{missing}"


def test_old_path_forwards_are_same_objects():
    """必须 `is` 同一对象：复制实现会让两份代码各自漂移，本批就白拆了。"""
    pairs = {"SLOT_MIN": SP, "_slot_ok": SP, "_slot_path": SP, "get_save_slots": SP,
             "_merge_regions": MG, "_migrate_pops_to_seats": MG}
    bad = [n for n, mod in pairs.items() if getattr(SL, n) is not getattr(mod, n)]
    assert not bad, f"以下名字旧路径与新实现不是同一对象：{bad}"


def test_unmoved_reexports_intact():
    """`save_load` 顶部的 util re-export 面不能因本次切片受损。"""
    for n in ("_safe_int", "_safe_float", "_strip_unknown_faction_keys", "FACTION_NAME_SET"):
        assert hasattr(SL, n), f"re-export 面缺 {n}"
    assert callable(SL.save_game) and callable(SL.load_game)


# ── ② 移动后 SAVE_DIR 重定向仍有效（防污染真实玩家存档）──────────────
def test_slot_path_honors_module_save_dir(tmp_path, monkeypatch):
    """把 slots 模块的 SAVE_DIR 指到 tmp，`_slot_path`/`get_save_slots` 必须跟着走。

    这是 `_slot_path` 原文 docstring 里那句"抽走会让 patch 失效"的反证：
    只要 conftest 的 blanket 补丁或显式 patch 命中的是**本模块**，重定向就成立。
    """
    monkeypatch.setattr(SP, "SAVE_DIR", str(tmp_path), raising=False)
    p = SP._slot_path(2)
    assert p.startswith(str(tmp_path)), f"仍指向别处：{p}"
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"save_time_str": "某年", "year": 1060, "month": 1,
                   "era_name": "嘉祐", "turn": 7}, f)
    got = {d["slot"]: d for d in SP.get_save_slots()}
    assert got[2]["turn"] == 7, f"读不到刚写入的槽 2：{got[2]}"
    assert got[1]["empty"] is True, f"未写入的槽应标 empty：{got[1]}"


def test_conftest_redirects_persistence_module(tmp_path):
    """迁移后的模块必须仍被 conftest 重定向，否则测试会写进玩家真实存档目录。

    ⚠️ 判据不能写成「与 `content.data.SAVE_DIR` 不同」——conftest 是**按用例**把
    所有带 SAVE_DIR 的已加载模块统一指到本用例 tmp 下，两边都被改了当然相等
    （我第一版就是这么写错的）。真正的判据是：它落在本用例的 tmp 目录里，
    且 `core.save_load` 看到的也是同一个目录（旧路径未留下第二份真相）。
    """
    assert str(tmp_path) in SP.SAVE_DIR.replace('/', os.sep), (
        f"persistence.slots 的 SAVE_DIR 不在用例 tmp 下，可能写真档：{SP.SAVE_DIR}")
    assert SL.SAVE_DIR == SP.SAVE_DIR, (
        f"core.save_load 与 persistence.slots 的 SAVE_DIR 分叉："
        f"{SL.SAVE_DIR!r} vs {SP.SAVE_DIR!r}")


# ── ③ 桥导入改道的非空哨兵 ──────────────────────────────────────
def test_migrate_pops_to_seats_actually_migrates():
    """清掉 seats 后应真的拆分出州府级真账。

    该函数把 import 失败吞成 `return 0`，所以必须断言**结果 > 0**，
    只看"没抛异常"完全证明不了桥接层接通。

    附带实测事实（纠正本批一开始的假设）：**新局 `GameState` 的各路也没有 `seats`**
    （20 路全为空），所以该迁移对新开局势同样会执行一次；docstring 里"新档开箱即带
    `seats`"指的是**经过首月结算/落盘之后**的档，不是内存里的初始对象。
    """
    s = GameState("史实")
    routes_with_pops = [r for r, p in s.prefectures.items() if isinstance(p.get("pops"), dict)
                        and p.get("pops")]
    assert routes_with_pops, "前置不成立：新局没有路级 pops 可迁"
    for r in routes_with_pops:
        s.prefectures[r]["seats"] = None            # 模拟旧档：完全缺 seats
    n = MG._migrate_pops_to_seats(s)
    assert n == len(routes_with_pops), (
        f"迁移路数 {n} != 应迁 {len(routes_with_pops)} —— "
        f"桥导入很可能被 except 吞掉（返回 0）或拆分失败")
    for r in routes_with_pops:
        assert s.prefectures[r].get("seats"), f"路 {r} 迁移后仍无 seats"


# ── ④ 建目录与写入路径必须同源（第七包引入的真实风险）──────────────
def test_save_game_creates_the_dir_it_writes_into(tmp_path, monkeypatch):
    """`save_game` 建的目录必须就是 `_slot_path` 属主模块的 `SAVE_DIR`。

    搬走 `_slot_path` 后，`core.save_load` 里保留的 `SAVE_DIR` 只为维持 `dir()` 公开面，
    **不再驱动写入**。若建目录那行仍读它，就会出现"建了 A 目录、写进 B 目录"：
    B 不存在 → 写盘 FileNotFoundError。

    两个目录都取**不存在**的嵌套路径，所以这条会被证明会红：
    把 `os.makedirs` 改回读 `save_load.SAVE_DIR` 时，属主目录没人建，存档直接失败。
    """
    real = str(tmp_path / "owner_dir")
    decoy = str(tmp_path / "decoy_dir")
    monkeypatch.setattr(SP, "SAVE_DIR", real, raising=False)
    monkeypatch.setattr(SL, "SAVE_DIR", decoy, raising=False)
    s = GameState("史实")
    assert SL.save_game(s, 4), "save_game 返回 False：很可能建了 A 目录、写进 B 目录"
    assert os.path.isfile(os.path.join(real, "slot_4.json")), "存档未落到属主目录"
    assert not os.path.exists(decoy), (
        f"属主模块之外还建了目录 {decoy} —— 说明建目录仍读的是 core.save_load.SAVE_DIR")


# ── ⑤ 幂等 ────────────────────────────────────────────────────
def test_migrate_is_idempotent_on_already_sunk_save():
    """幂等：已下沉的档绝不二次拆分（再拆会制造双份真账）。

    判据是"连跑两次，第二次 0 且 seats 逐字节不变"，而不是"新局不该被迁"——
    后者前提本身不成立（见上一条的实测说明）。
    """
    s = GameState("史实")
    assert MG._migrate_pops_to_seats(s) > 0, "前置：第一次应真的迁移"
    snapshot = json.dumps({r: p.get("seats") for r, p in s.prefectures.items()},
                          sort_keys=True, ensure_ascii=False)
    second = MG._migrate_pops_to_seats(s)
    after = json.dumps({r: p.get("seats") for r, p in s.prefectures.items()},
                       sort_keys=True, ensure_ascii=False)
    assert second == 0, f"第二次不应再迁任何路，实际 {second}"
    assert after == snapshot, "seats 在第二次调用中被改动 —— 幂等性破裂"
