# -*- coding: utf-8 -*-
"""宋祚 · 读档编排（应用层）。

> **为什么在这里**：2026-10-07 用户裁定（M25）要求动态蓝图恢复
> 从基础持久化层 `core/save_load.py` **迁到应用层**，使其不再引用业务域（§6-1）。
>
> 分工：基础层 `_load_with_data` 只做**反序列化**（字段回填）；蓝图的
> **校验与登记**属于业务域，由本模块编排。
"""
from __future__ import annotations


class RestoreServiceError(RuntimeError):
    """**恢复服务自身失败**（整档级）⇒ 读档必须失败，不返回部分恢复的 state。

    覆盖：读档编排本身出错、蓝图域服务不可用、版本表不可得等
    「继续下去会得到一个残缺档案」的情形。
    """

    def __init__(self, slot, stage, cause):
        self.slot = slot
        self.stage = stage
        self.cause = cause
        super().__init__(
            f"存档 slot={slot} 恢复失败 @ {stage}：{type(cause).__name__}: {cause}"
        )


def restore_dynamic_blueprints(state, data, slot):
    """恢复动态蓝图注册表并逐条重过校验器。

    **失败分级**（2026-10-07 用户裁定）：

    | 层级 | 处理 |
    |---|---|
    | 整档结构 / 必需状态损坏、恢复服务自身失败 | **fail-fast**，读档失败，不返回部分恢复的 state |
    | **单条**动态蓝图校验失败（内容非法） | **只丢弃该条**并留痕，其余合法蓝图继续恢复 |
    | 子段 schema 高于支持版本 | **只拒绝该子段**并留痕，整档继续 |

    🔴 **内容校验失败 ≠ 恢复服务故障** —— 前者是数据问题（可能只错一条），
    整档丢弃会连带废掉玩家所有合法蓝图；后者是服务问题，继续只会得到残缺档案。
    """
    import logging
    from core.blueprint_dynamic import register_dynamic_blueprint
    from core.save_load import _plan_schema_versions

    _dlog = logging.getLogger("save_load")
    state.dynamic_blueprints = {}
    _dyn_saved = data.get("dynamic_blueprints")

    # ---- 子 schema 版本门：超版本只拒绝该子段（留痕），整档继续 ----
    try:
        _supported = _plan_schema_versions()
    except Exception as e:  # noqa: BLE001 — 版本表取不到 = 服务故障，非内容问题
        raise RestoreServiceError(slot, "plan_schema_versions", e) from e
    _saved_ver = data.get("plan_schemas")
    if isinstance(_saved_ver, dict):
        for _k, _v in _saved_ver.items():
            _sup = _supported.get(_k)
            if _sup is None:
                continue
            try:
                _vn = int(_v)
            except (TypeError, ValueError):
                _dlog.warning("[读档] plan_schemas.%s 非法（%r），按当前版本 %s 处理",
                              _k, _v, _sup)
                continue
            if _vn > int(_sup):
                _dlog.warning("[读档] 存档 %s schema v%s 高于本程序支持的 v%s，该段拒绝载入",
                              _k, _vn, _sup)
                if _k == "dynamic_blueprint":
                    _dyn_saved = None

    if not isinstance(_dyn_saved, dict):
        return 0

    _n = 0
    _dropped = 0
    for _dk, _dv in _dyn_saved.items():
        try:
            _r = register_dynamic_blueprint(state, _dv)
        except Exception as e:  # noqa: BLE001 — 服务自身故障 ⇒ 整档 fail-fast
            raise RestoreServiceError(slot, "register_dynamic_blueprint", e) from e
        if not _r.get("ok"):
            _dropped += 1
            _dlog.warning("[读档] 动态蓝图 %s 未通过校验，已丢弃：%s",
                          _dk, _r.get("errors"))
            continue
        _n += 1
    if _dropped:
        _dlog.warning("[读档] 共丢弃 %d 条非法动态蓝图", _dropped)
    return _n


def load_game(slot: int = 1):
    """读档入口：基础反序列化 → 业务域恢复。

    整档级失败（结构损坏 / 恢复服务故障）⇒ 直接抛出，**不返回半恢复的 state**。
    """
    from core.save_load import _load_with_data

    state, data = _load_with_data(slot)
    if state is None:
        return None
    restore_dynamic_blueprints(state, data, slot)
    # 主线 B 第一片：**地方府库**（local_treasury）州府级下沉。
    # 新档已在 new_game 下沉过 ⇒ 本调用幂等跳过；旧档（无 seats[治所]["local_treasury"]）在此补齐。
    # 失败**不得拒档**：桥接层在未下沉时会返回 None，调用方回落旧载体，行为不变。
    try:
        from core.foundation.persistence.migrations import sink_local_treasury_to_seats
        sink_local_treasury_to_seats(state)
    except Exception:  # noqa: BLE001 — 迁移失败不拒档（见上）
        _dlog.warning("[读档] 地方府库州府级下沉失败（不拒档，桥接将回落旧载体）",
                      exc_info=True)
    # 主线 B 批次 2：**建筑**（buildings）州府级下沉。新档已在 new_game 下沉过 ⇒ 幂等跳过；
    # 旧档在此补齐。同样**失败不拒档**（桥接未下沉时返回 None，调用方回落原写法）。
    try:
        from core.foundation.persistence.migrations import sink_buildings_to_seats
        sink_buildings_to_seats(state)
    except Exception:  # noqa: BLE001 — 同上
        _dlog.warning("[读档] 建筑州府级下沉失败（不拒档，桥接将回落旧载体）", exc_info=True)
    # M91：建筑**归属**（P2 第一片）——旧档补齐；**失败不拒档**（只登记元数据、不动数值）。
    try:
        from core.foundation.persistence.migrations import assign_building_owners
        assign_building_owners(state)
    except Exception:  # noqa: BLE001 — 同上
        _dlog.warning("[读档] 建筑归属登记失败（不拒档；P2 就绪度将偏低）", exc_info=True)
    # M196：**丝坊补座**（产能批）——存量档补齐到绝对目标 28 座；**必须在登记作坊货主之前**
    # （`assign_workshop_owners` 紧随其后）⇒ 新座才有货主；**失败不拒档**、不动钱货、不改 yield。
    try:
        from core.foundation.persistence.migrations import open_workshop_expansion
        open_workshop_expansion(state)
    except Exception:  # noqa: BLE001 — 同上
        _dlog.warning("[读档] 丝坊补座失败（不拒档；产能仍按旧座数，缺失≠0）", exc_info=True)
    # M66：作坊**货主**（产权落点）——旧档补齐；**失败不拒档**（只登记字段、不动钱）。
    try:
        from core.foundation.persistence.migrations import assign_workshop_owners
        assign_workshop_owners(state)
    except Exception:  # noqa: BLE001 — 同上
        _dlog.warning("[读档] 作坊货主登记失败（不拒档；影子读数将报 undefined）", exc_info=True)
    # 交通下沉 M39c-1：**漕运淤塞**（canal_block）州府级下沉（旧档补齐；新档已幂等跳过）。
    # 失败同样**不拒档**：桥接未下沉时返回 None，调用方回落原写法（state.canal_block 直写）。
    try:
        from core.foundation.persistence.migrations import sink_canal_to_seats
        sink_canal_to_seats(state)
    except Exception:  # noqa: BLE001 — 同上
        _dlog.warning("[读档] 漕运淤塞州府级下沉失败（不拒档，桥接将回落旧写法）", exc_info=True)
    # 行政区划 P3（2026-10-19）：旧档无 `regions` ⇒ 幂等重建（不拒档）。
    try:
        from core.foundation.ledger.region_registry import migrate_regions
        migrate_regions(state)
    except Exception:  # noqa: BLE001 — 迁移失败不拒档（overlay 将为空）
        _dlog.warning("[读档] 行政区划骨架迁移失败（不拒档）", exc_info=True)
    # 批次 4 仓储片：**常平仓**（changping_stock）州府级下沉（旧档补齐；新档已幂等跳过）。
    try:
        from core.foundation.persistence.migrations import sink_changping_to_seats
        sink_changping_to_seats(state)
    except Exception:  # noqa: BLE001 — 同上
        _dlog.warning("[读档] 常平仓州府级下沉失败（不拒档，桥接将回落旧写法）", exc_info=True)
    # 批次 4 仓储片：**州仓**（storage）州府级下沉（M40b，旧档补齐；新档已幂等跳过）。
    try:
        from core.foundation.persistence.migrations import sink_prefectural_storage_to_seats
        sink_prefectural_storage_to_seats(state)
    except Exception:  # noqa: BLE001 — 同上
        _dlog.warning("[读档] 州仓州府级下沉失败（不拒档，桥接将回落旧写法）", exc_info=True)
    # 空间确权底座（Bundle 1）：**物理四仓位**（warehouses）州府级下沉（旧档补齐；新档已幂等跳过）。
    try:
        from core.foundation.persistence.migrations import sink_spatial_warehouses_to_seats
        sink_spatial_warehouses_to_seats(state)
    except Exception:  # noqa: BLE001 — 同上
        _dlog.warning("[读档] 物理仓位州府级下沉失败（不拒档，桥接将回落旧写法）", exc_info=True)
    # C-14（2026-10-20 可选层）：旧档长期事务缺 id ⇒ 首轮结算前授权/案卷页命中不到。
    # 读档时确定性补齐（幂等；同内容同 id），后续结算/读数同键。
    try:
        from core.domains.politics.longterm_case import ensure_task_ids_in_state
        _n_fixed = ensure_task_ids_in_state(state)
        if _n_fixed:
            _dlog.info("[读档] 为 %d 条旧长期事务补齐 id", _n_fixed)
    except Exception:  # noqa: BLE001 — 旧档迁移失败不拒档
        _dlog.warning("[读档] 旧长期事务补 id 失败（不拒档；结算前会再补）", exc_info=True)
    return state

