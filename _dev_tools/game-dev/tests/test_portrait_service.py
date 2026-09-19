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
    u = _portrait_url(r"D:\anywhere\_composed\韩忠彦_zi_longxiu.png")
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
    assert prof2["韩忠彦"]["portrait"] != prof["韩忠彦"]["portrait"], "换服应换立绘 key"


def test_get_portrait_path_accepts_explicit_tier():
    """`tier` 显式指定时优先（供在任状态驱动的服色）。"""
    a = get_portrait_path("韩忠彦", tier="shi")
    b = get_portrait_path("韩忠彦", tier="zi")
    assert a and b
    assert a != b, "不同 tier 应命中不同合成图"
    assert "shi" in os.path.basename(a)
    assert "zi" in os.path.basename(b)


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