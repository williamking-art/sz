# -*- coding: utf-8 -*-
"""AI 配置路径：**写用户数据目录、读兼容旧位置**（2026-10-03 收口全审 A-6）。

背景（2026-10-02 全审 A-6）：`ai_config.json` 原落 `_app_root()/ai_config.json`，
frozen 态即 **安装目录**（exe 同级）；装到 `C:\\Program Files` 一类只读位置时
`/api/ai-config` 的读-改-写会失败，AI 配置无处安放 —— 而存档一直在
`~/Documents/宋祚/saves`。现配置文件与存档同根，且**读取兼容旧位置**。

本测试同时守「口径单点」：`backend/server.py::_ai_config_path()` 与
`ai/client.py::_config_path()` 必须同源，不得各写一份 `join(_app_root(), ...)`
（2026-10-03 前正是两份重复定义）。
"""
import json
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from ai import client as aiclient  # noqa: E402
from ai import client_utils as cu  # noqa: E402
from backend import server as srv  # noqa: E402


# ---------------------------------------------------------------- 真实落点（不打桩）
def test_config_path_is_under_user_data_dir():
    """权威路径必须在用户数据目录，**不得**在安装目录/仓库根之下。"""
    p = cu._ai_config_path()
    assert p == os.path.join(os.path.expanduser("~/Documents"), "宋祚", "ai_config.json")
    root = os.path.abspath(cu._app_root()) + os.sep
    assert not os.path.abspath(p).startswith(root), \
        "AI 配置又落回安装目录了 —— 只读安装位置会写不进去（全审 A-6）"


def test_config_root_matches_documents_convention():
    """配置根与存档根用**同一条推导式**（`~/Documents/宋祚`），不是各写一份。

    注意：不能拿 `content.data.SAVE_DIR` 当基准 —— `tests/conftest.py` 会把它
    全局重定向到 `tmp_path`（防止污染真实玩家存档），故此处用它的来源常量
    `content.data._DOCUMENTS`。
    """
    from content import data as cd
    assert os.path.dirname(cu._ai_config_path()) == os.path.join(cd._DOCUMENTS, "宋祚")


def test_backend_and_ai_share_one_path():
    """口径单点：后端与 AI 客户端必须返回同一条路径。"""
    assert srv._ai_config_path() == cu._ai_config_path()
    assert aiclient.AIClient._config_path() == cu._ai_config_path()


def test_legacy_path_is_the_old_location():
    """旧的安装目录路径仍可解析（供读取回退）。"""
    assert cu._legacy_ai_config_path() == os.path.join(cu._app_root(), "ai_config.json")


# ---------------------------------------------------------------- 打桩辅助
def _install(monkeypatch, tmp_path):
    """把新/旧两个位置都指向 tmp 下的目录，返回 (new_path, legacy_path)。

    用 monkeypatch 而非直接赋值 —— 直接赋值会跨用例泄漏（第一次写本文件时踩过）。
    """
    new = tmp_path / "userdata" / "ai_config.json"
    legacy = tmp_path / "install" / "ai_config.json"
    new.parent.mkdir(parents=True, exist_ok=True)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cu, "_ai_config_path", lambda: str(new))
    monkeypatch.setattr(cu, "_legacy_ai_config_path", lambda: str(legacy))
    monkeypatch.setattr(aiclient, "_ai_config_path", lambda: str(new))
    monkeypatch.setattr(aiclient, "_legacy_ai_config_path", lambda: str(legacy))
    return new, legacy


# ---------------------------------------------------------------- 读回退
def test_read_prefers_new_location(monkeypatch, tmp_path):
    new, legacy = _install(monkeypatch, tmp_path)
    new.write_text("{}", encoding="utf-8")
    legacy.write_text("{}", encoding="utf-8")
    assert cu.resolve_ai_config_path() == str(new)


def test_read_falls_back_to_legacy_when_new_absent(monkeypatch, tmp_path):
    """已装机用户的旧配置还能读到（一次性回退）。"""
    new, legacy = _install(monkeypatch, tmp_path)
    legacy.write_text("{}", encoding="utf-8")
    assert cu.resolve_ai_config_path() == str(legacy)


def test_read_returns_new_when_neither_exists(monkeypatch, tmp_path):
    new, legacy = _install(monkeypatch, tmp_path)
    assert cu.resolve_ai_config_path() == str(new)


# ---------------------------------------------------------------- 写行为
def test_save_config_writes_to_user_data_path(monkeypatch, tmp_path):
    new, legacy = _install(monkeypatch, tmp_path)
    c = aiclient.AIClient("sk-test", "https://example.invalid/v1", "m")
    assert c.save_config() is True
    assert new.exists(), "配置没写到用户数据目录"
    assert not legacy.exists(), "不该再往旧位置（安装目录）写"
    assert json.loads(new.read_text(encoding="utf-8"))["api_key"] == "sk-test"


def test_save_config_migrates_and_removes_legacy(monkeypatch, tmp_path):
    """写入新位置成功后，旧位置的残留副本必须删掉（否则留两份、且旧那份含真 key）。"""
    new, legacy = _install(monkeypatch, tmp_path)
    legacy.write_text(json.dumps({"api_key": "sk-old"}), encoding="utf-8")
    c = aiclient.AIClient("sk-new", "https://example.invalid/v1", "m")
    assert c.save_config() is True
    assert new.exists()
    assert not legacy.exists(), "旧位置残留未清 → 会变成两份配置"


def test_clear_config_removes_both_locations(monkeypatch, tmp_path):
    """清空配置必须两处都删 —— 否则旧位置的残留会被回退读回来。"""
    new, legacy = _install(monkeypatch, tmp_path)
    new.write_text("{}", encoding="utf-8")
    legacy.write_text("{}", encoding="utf-8")
    c = aiclient.AIClient("", "https://example.invalid/v1", "m")
    assert c.save_config() is True
    assert not new.exists() and not legacy.exists(), \
        "清空后仍残留配置 → load_saved 会把旧配置读回来"


def test_load_saved_reads_legacy_once(monkeypatch, tmp_path):
    new, legacy = _install(monkeypatch, tmp_path)
    legacy.write_text(json.dumps({"api_key": "sk-legacy",
                                 "base_url": "https://example.invalid/v1",
                                 "model": "m"}), encoding="utf-8")
    # 注意签名：load_saved 会把自己的 `_config_path()` 传进来（保留可打桩接缝）
    monkeypatch.setattr(aiclient, "resolve_ai_config_path", lambda _new: str(legacy))
    c = aiclient.AIClient.load_saved()
    assert c is not None and c.api_key == "sk-legacy"