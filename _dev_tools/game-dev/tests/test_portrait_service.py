# -*- coding: utf-8 -*-
"""立绘服务整改回归（依据 analysis/portrait_system_design.md §一.3/§五/§七）。"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.ministers.data import get_portrait_path  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.minister_profile import _portrait_url, build_minister_profiles  # noqa: E402

_PUBLIC = os.path.join(_GAME_ROOT, "frontend", "public", "portraits", "ministers")


def _public_count():
    try:
        return len([f for f in os.listdir(_PUBLIC) if f.lower().endswith(".png")])
    except OSError:
        return -1


def _s():
    return GameState("史实")


def test_portrait_url_is_controlled_route_not_public_path():
    """URL 必须是后端受控路由，且**不得**是写进 public 的相对路径。"""
    # 用**当前平台的原生绝对路径**（Windows → D:\...；POSIX → /...）构造入参。
    # 原先写死 Windows 路径，在 Linux 下 basename 取不出文件名、被安全校验判为可疑输入
    # 而返回空串，导致该用例只在 Windows 通过（2026-09-23 修）。
    _sample = os.path.join(os.path.abspath(os.sep), "anywhere", "_composed",
                           "韩忠彦_zi_longxiu.png")
    u = _portrait_url(_sample)
    assert u.startswith("/api/portrait/"), u
    assert "frontend" not in u and "public" not in u
    assert _portrait_url("") == ""
    assert _portrait_url(None) == ""
    # 防路径穿越：带分隔符的入参不得通过
    assert _portrait_url("/etc/passwd") == "" or _portrait_url("/etc/passwd").startswith("/api/portrait/passwd")


def test_building_profiles_does_not_write_public_dir():
    """生成大臣档案（含立绘合成）时，**不得**向前端 public 目录写任何文件。"""
    s = _s()
    before = _public_count()
    prof = build_minister_profiles(s)
    after = _public_count()
    assert prof, "应有大臣档案"
    assert after == before, f"运行期写了 public 目录（{before} → {after}）：违反 §一.3"


def test_costume_follows_service_status():
    """服色随在任状态：在任按品级；罢黜/身故 → 士人 shi。"""
    s = _s()
    prof = build_minister_profiles(s)
    # 在任宰执（正一品）→ 紫
    assert prof["韩忠彦"]["tier"] == "zi", prof["韩忠彦"]
    # 在野（rank 为空）→ 士人
    assert prof["蔡京"]["tier"] == "shi", prof["蔡京"]
    # 罢黜后换服（同一实例，状态驱动）
    s.mark_minister_status("韩忠彦", "dismissed")
    prof2 = build_minister_profiles(s)
    assert prof2["韩忠彦"]["tier"] == "shi", "罢黜后应换士人服"
    # 2026-10-16 权威架构（commit 40c4938ea2）：历史名臣专属原画优先，
    # 不因换服做二次合成；换服只改 tier 字段，portrait key 保持专属原画。
    assert prof2["韩忠彦"]["portrait"] == prof["韩忠彦"]["portrait"]


def test_get_portrait_path_is_stable_under_tier():
    """v4 整幅肖像阶段（2026-10-18 用户裁定）：**同一官员的任何 tier 都映射到同一张图**。

    口径变更记录：旧实现按 tier 合成不同官服图（本用例原名
    `test_get_portrait_path_accepts_explicit_tier`，断言"不同 tier 命中不同合成图"）；
    v4 起立绘为整幅肖像、按姓名稳定分配，tier 只作为将来"同脸跨级版"的键；
    索引未登记 tiers 时**不得**因 tier 改变选图（否则同一官员会因升贬换脸）。
    """
    a = get_portrait_path("张知县", tier="shi")
    b = get_portrait_path("张知县", tier="zi")
    assert a and b
    assert a == b, "同一官员不同 tier 必须同一张（同脸）"
    # 已登记官员：同样稳定
    ha = get_portrait_path("韩忠彦", tier="shi")
    hb = get_portrait_path("韩忠彦", tier="zi")
    assert ha and hb
    assert ha == hb, "已登记官员的立绘不得因 tier 改变"


def test_portrait_route_rejects_bad_names():
    """受控路由：拒绝路径穿越与非图片名（直接调处理函数 + 伪造 Request）。"""
    from fastapi import HTTPException
    from backend.server import api_portrait

    class _FakeClient:
        host = "127.0.0.1"

    class _FakeReq:
        headers = {}
        client = _FakeClient()

    for bad in ("../secret.png", "..\\secret.png", "x.txt", ""):
        try:
            api_portrait(bad, _FakeReq())
        except HTTPException as e:
            assert e.status_code in (400, 404), (bad, e.status_code)
        else:
            raise AssertionError(f"非法文件名应被拒：{bad!r}")