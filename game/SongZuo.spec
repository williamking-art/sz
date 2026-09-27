# -*- mode: python ; coding: utf-8 -*-
# 相对路径：以本 spec 所在目录（game/）为根，避免硬编码盘符
import os
_ROOT = os.path.abspath(SPECPATH)

# ---------------------------------------------------------------
# 随包数据：**白名单**（2026-09-27 审查 §8.2-#1，用户选 A）
#   原为整目录打包（assets + ai + core + engine + backend + content + audio + memory），
#   实测 datas 合计 **302.4 MB**（立绘素材 169 MB、地图 100 MB），而**运行期真正读的只有下列项**：
#     · `ai/prompts/*.md` + `ai/safety_lexicon.json` ← `ai/client_utils.py::_load_prompt` / `load_safety_lexicon`
#     · `assets/kb/game_kb.sqlite`                  ← `ai/kb_query.py:31` `get_resource("kb/game_kb.sqlite")`
#     · `assets/map/empire_bg.png` / `desk_bg.{jpg,png}` ← `content/data.py::empire_bg_path` / `desk_bg_path`
#     · `assets/icon.ico`                           ← EXE 图标（打包期）
#     · `content/ministers/layers/`                 ← **运行期合成输入**：`compose_portrait`，
#       经 `backend/server.py` 的 `/api/portrait/<file>` 与 `core/minister_profile.py` 按需调用
#     · `content/ministers/portraits/*.png`         ← 合成失败时的回退（**必须排除 `_composed/` 缓存**）
#   代码是纯 Python，由 `PYZ(a.pure)` 收走 → `core/engine/backend/memory/audio` **不需要** datas 条目。
#   明确排除：`assets/map/{raw,web,tiles}`（构建期输入，Electron 侧自带副本）、
#   `assets/{events,portraits}`（2026-09-27 已删：与 frontend/public 重复且无读取方）、
#   `content/ministers/portraits/_composed`（按需再生的缓存）。
# ---------------------------------------------------------------
def _files_without_cached(dirpath, exclude_dirs=()):
    """列目录内文件为 datas 条目；`exclude_dirs` 用于剔除 `_composed` 这类缓存子目录。"""
    out = []
    for d, dirs, files in os.walk(dirpath):
        dirs[:] = [x for x in dirs if x not in exclude_dirs]
        for f in files:
            p = os.path.join(d, f)
            out.append((p, os.path.relpath(os.path.dirname(p), _ROOT).replace(os.sep, '/')))
    return out


def _datas():
    items = [
        (os.path.join(_ROOT, 'ai', 'prompts'), 'ai/prompts'),
        (os.path.join(_ROOT, 'ai', 'safety_lexicon.json'), 'ai'),
        (os.path.join(_ROOT, 'assets', 'kb'), 'assets/kb'),
        (os.path.join(_ROOT, 'assets', 'map', 'empire_bg.png'), 'assets/map'),
        (os.path.join(_ROOT, 'assets', 'map', 'desk_bg.jpg'), 'assets/map'),
        (os.path.join(_ROOT, 'assets', 'map', 'desk_bg.png'), 'assets/map'),
        (os.path.join(_ROOT, 'assets', 'icon.ico'), 'assets'),
        (os.path.join(_ROOT, 'content', 'ministers', 'layers'), 'content/ministers/layers'),
    ]
    items += _files_without_cached(
        os.path.join(_ROOT, 'content', 'ministers', 'portraits'),
        exclude_dirs=('_composed',))
    return items


a = Analysis(
    # Tk 废弃（迁移补齐）：入口由 gui_main.py（Tk）改为 backend_server_entry.py
    # （FastAPI 参考后端，供 Electron 前端经 HTTP 调用）
    [os.path.join(_ROOT, 'backend_server_entry.py')],
    pathex=[_ROOT],
    binaries=[],
    datas=_datas(),
    # 2026-09-27：`ai.contract_adapter` / `core.async_ai` 已移出（未接线、不随包）
    hiddenimports=['ai', 'ai.client', 'ai.decree', 'ai.desensitize', 'ai.narrative_guard', 'ai.client_utils', 'ai.client_narrative', 'ai.narrative_fallback', 'ai.token_meter', 'core', 'core.commands', 'core.commands_decree', 'core.game_state', 'core.game_state_econ', 'core.save_load', 'core.events', 'core.evaluation', 'core.asset_context', 'core.settlement', 'core.settlement_steps', 'core.settlement_common', 'core.settlement_decree', 'core.settlement_econ', 'core.settlement_econ_helpers', 'core.settlement_finance', 'core.settlement_granary', 'core.settlement_imperial', 'core.settlement_military', 'core.settlement_officialdom', 'core.settlement_tech', 'core.free_effect', 'core.registries', 'core.era_mechanic', 'core.estate_mechanic', 'core.agent_router', 'core.army_models', 'core.briefing', 'core.flow_summary', 'core.minister_profile', 'core.building_jobs', 'core.clerks', 'core.construction', 'core.decree_effect', 'core.diplomacy_treaty', 'core.dynamic_price', 'core.errors', 'core.external_view', 'core.faction_basis', 'core.faction_metrics', 'core.faction_settle', 'core.faction_split', 'core.faction_voice', 'core.focus_mechanic', 'core.institution', 'core.legacy_mechanic', 'core.literacy', 'core.money', 'core.monthly_gazette', 'core.officialdom', 'core.production_chain', 'core.region_brief', 'core.situations', 'core.situation_metrics', 'core.situation_settle', 'core.tool_registry', 'engine', 'engine.state_applier', 'backend', 'backend.client', 'backend.server', 'content', 'content.data', 'content.codex_data', 'content.data_constants', 'content.data_decree', 'content.data_external', 'content.data_geo_tables', 'content.data_imperial', 'content.data_military', 'content.data_tech', 'content.demography', 'content.geo_admin', 'content.legacy_gazette', 'content.situation_seeds', 'content.ministers.data', 'content.ministers.persona', 'content.codex_text', 'memory', 'memory.memory_graph', 'memory.dialogue_memory', 'audio', 'audio.manifest'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SongZuo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(_ROOT, 'assets', 'icon.ico')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SongZuo',
)
