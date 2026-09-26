# -*- mode: python ; coding: utf-8 -*-
# 相对路径：以本 spec 所在目录（game/）为根，避免硬编码盘符
import os
_ROOT = os.path.abspath(SPECPATH)

a = Analysis(
    # Tk 废弃（迁移补齐）：入口由 gui_main.py（Tk）改为 backend_server_entry.py
    # （FastAPI 参考后端，供 Electron 前端经 HTTP 调用）
    [os.path.join(_ROOT, 'backend_server_entry.py')],
    pathex=[_ROOT],
    binaries=[],
    datas=[
        (os.path.join(_ROOT, 'assets'), 'assets'),
        (os.path.join(_ROOT, 'ai'), 'ai'),
        (os.path.join(_ROOT, 'core'), 'core'),
        (os.path.join(_ROOT, 'engine'), 'engine'),
        # （R4-6）`ui/` 为 Tk 界面残留的空目录，随界面一并移除，不再打进分发包
        (os.path.join(_ROOT, 'backend'), 'backend'),
        (os.path.join(_ROOT, 'content'), 'content'),
        (os.path.join(_ROOT, 'audio'), 'audio'),
        (os.path.join(_ROOT, 'memory'), 'memory'),
    ],
    hiddenimports=['ai', 'ai.client', 'ai.decree', 'ai.desensitize', 'ai.narrative_guard', 'ai.client_utils', 'ai.client_narrative', 'ai.contract_adapter', 'ai.narrative_fallback', 'ai.token_meter', 'core', 'core.commands', 'core.commands_decree', 'core.game_state', 'core.game_state_econ', 'core.save_load', 'core.events', 'core.evaluation', 'core.asset_context', 'core.settlement', 'core.settlement_steps', 'core.settlement_common', 'core.settlement_decree', 'core.settlement_econ', 'core.settlement_econ_helpers', 'core.settlement_finance', 'core.settlement_granary', 'core.settlement_imperial', 'core.settlement_military', 'core.settlement_officialdom', 'core.settlement_tech', 'core.free_effect', 'core.registries', 'core.era_mechanic', 'core.estate_mechanic', 'core.agent_router', 'core.async_ai', 'core.army_models', 'core.briefing', 'core.flow_summary', 'core.minister_profile', 'core.building_jobs', 'core.clerks', 'core.construction', 'core.decree_effect', 'core.diplomacy_treaty', 'core.dynamic_price', 'core.errors', 'core.external_view', 'core.faction_basis', 'core.faction_metrics', 'core.faction_settle', 'core.faction_split', 'core.faction_voice', 'core.focus_mechanic', 'core.institution', 'core.legacy_mechanic', 'core.literacy', 'core.money', 'core.monthly_gazette', 'core.officialdom', 'core.production_chain', 'core.region_brief', 'core.situations', 'core.situation_metrics', 'core.situation_settle', 'core.tool_registry', 'engine', 'engine.state_applier', 'backend', 'backend.client', 'backend.server', 'content', 'content.data', 'content.codex_data', 'content.data_constants', 'content.data_decree', 'content.data_external', 'content.data_geo_tables', 'content.data_imperial', 'content.data_military', 'content.data_tech', 'content.demography', 'content.geo_admin', 'content.legacy_gazette', 'content.situation_seeds', 'content.ministers.data', 'content.ministers.persona', 'content.codex_text', 'memory', 'memory.memory_graph', 'memory.dialogue_memory', 'audio', 'audio.manifest'],
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
