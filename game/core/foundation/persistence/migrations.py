# -*- coding: utf-8 -*-
"""宋祚 · 旧档迁移（从 `core/save_load.py` 原文迁来，零行为变更）。

承架构方案 §4.1「存档读写、版本迁移」。⚠️ 这里的"版本迁移"按现状实为
**按字段存在性做幂等迁移**（缺则补、有则不动），**不看 schema 版本号**——
子系统级 `*SCHEMA_VERSION` 目前 13 个常量只被消费 1 次，见
`specs/cross-cutting/存档schema版本消费实况_2026-10-07.md`。

机械改道（本批唯一声明过的漂移）：`_migrate_pops_to_seats` 内两处桥导入
由旧路径 `core.pop_bridge` / `core.grain_bridge` 改指新规范路径
`core.foundation.ledger.*`（甲批规则「新迁入模块不得导入旧转发桩」）。
函数体其余逐字保留，未改任何口径。
"""


def _merge_regions(target: dict, saved) -> None:
    """把存档中的政权数据并入新版默认结构。

    旧存档缺失新增字段（name/population/unrest/... ）时保留默认值，
    从而保证读档后详情面板与舆图标签不会缺字段。
    """
    if not isinstance(saved, dict):
        return
    for key, val in saved.items():
        if not isinstance(val, dict):
            continue
        if key in target and isinstance(target[key], dict):
            target[key].update(val)
        else:
            target[key] = val


# ══ 方案乙旧档迁移（2026-10-04） ══
def _migrate_pops_to_seats(state) -> int:
    """把**旧档**（路级 `pops` 有账、`seats` 缺失）迁移为州府级真账。

    背景：方案乙裁定 POP 实体下沉州府级，真账在 `prefectures[路]["seats"][治所]["pops"][类]`，
    路级 `pops` 降为**只读派生聚合**。新档开箱即带 `seats`；**旧档没有**，
    若不迁移则载入后处于**半迁移状态**（桥接全部回落 legacy ⇒ 行为等价但未下沉）。

    做法：对每个缺 `seats` 的路调 `split_pops_to_seats`（按治所人口权重拆分，
    尾差归权重最大者 ⇒ Σ治所与路级原值**逐字段精确相等**）。

    **保守**：只处理**完全缺失**的 `seats`；已下沉的档**绝不覆盖**（避免二次拆分）。
    无治所或人口全缺 ⇒ `split_pops_to_seats` 返回 0，该路保持原样（不臆造归属）。

    返回实际迁移的路数。

    ⚠️ 已知静默点（本批**不修**，修它属口径变更、需另立批次）：桥接层 import 失败时
    `return 0` —— 与 `pop_bridge.seat_pop_weights` 同类的"断链不报错"形态。
    调用方只有 `_scratch` 级用例与 `test_old_save_seat_migration.py` 等 3 个测试文件
    能间接暴露它；真正兜住的是"迁移后 seats 非空"这类结果断言，不是 import 成功。
    """
    try:
        from core.foundation.ledger.grain_bridge import backfill_grain_to_seats
        from core.foundation.ledger.pop_bridge import split_pops_to_seats, sync_route_pops
    except Exception:               # noqa: BLE001 — 桥接层不可用时不得阻断载入
        return 0
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return 0
    migrated = 0
    for route, pdata in prefs.items():
        if not isinstance(pdata, dict) or not isinstance(pdata.get("pops"), dict):
            continue
        if pdata.get("seats"):
            continue                      # 已下沉：绝不覆盖
        if split_pops_to_seats(pdata, route):
            migrated += 1
            try:
                # 🔴 G-3 片5：下沉后**立即回填粮**到州府（按治所人口权重，Σ治所 == 路级原值），
                # 再刷路级镜像 —— 路级 `grain` 此后是**派生**，不再是载体。
                backfill_grain_to_seats(pdata, route)
                sync_route_pops(pdata)
            except Exception:           # noqa: BLE001 — 镜像刷新失败不影响真账
                pass
    return migrated


def sink_pops_to_seats(state) -> int:
    """把**路级 pops 实体下沉**到州府级 seats（方案乙）。

无条件的下沉入口：**新局**（application/game_init.py）与
**读档**（save_load）共用。两者差别只在调用时机，逻辑完全一致。

本函数幂等（已下沉的路直接跳过），**新局与读档都可安全调用**。
返回实际下沉的路数。
    """
    return _migrate_pops_to_seats(state)


def sink_local_treasury_to_seats(state) -> int:
    """把**地方府库**（`local_treasury`）下沉到州府级 seats（主线 B 第一片）。

    与 `sink_pops_to_seats` 同型：**无条件幂等入口**，新局与读档共用。
    真账落 `prefectures[路]["seats"][治所]["local_treasury"]`，路级降为 Σ 派生镜像。

    🔴 **别与中央国库混淆**：`state.treasury` 是国库（`imperial_treasury` 是内帑），
    本函数只管**地方府库**（账户 id `local:<路>`）。

    ⚠️ 必须在 `sink_pops_to_seats` **之后**调用（分摊权重取自治所人口）。
    返回实际下沉的路数；权重不可得或无 `local_treasury` 数值的路**跳过**（不臆造归属）。

    **Jev 裁定（2026-10-13）**：本批只做「真账下沉 + 聚合 + 对账」，**不改**既有读点
    —— 路级保留为 Σ 镜像，而 Σ 与原值恒等 ⇒ 读路径行为不变（范围 0.93；口径 P=0.995）。
    """
    from core.foundation.ledger import local_treasury_bridge
    return local_treasury_bridge.sink_local_treasury_to_seats(state)


def sink_buildings_to_seats(state) -> int:
    """把**建筑**（`buildings`）下沉到州府级 seats（主线 B 批次 2 · M38b-2）。

    与 `sink_pops_to_seats` / `sink_local_treasury_to_seats` 同型：**无条件幂等入口**，
    新局与读档共用。真账落 `prefectures[路]["seats"][治所]["buildings"]`，路级降为 Σ 派生镜像
    （**保形态**：`{"lv":n,"built_month":m}` 原样搬运）。

    ⚠️ 必须在 `sink_pops_to_seats` **之后**调用——首府（路治）判定取治所人口权重。
    返回实际下沉的路数；无可分配等级或判不出首府的路**跳过**（不臆造归属）。
    """
    from core.foundation.ledger import building_bridge
    return building_bridge.sink_buildings_to_seats(state)


def sink_canal_to_seats(state) -> int:
    """把**漕运淤塞**（`canal_block`）下沉到州府级 seats（交通下沉 M39c-1）。

    与 `sink_pops_to_seats` / `sink_local_treasury_to_seats` / `sink_buildings_to_seats` 同型：
    **无条件幂等入口**，新局与读档共用。原为**全国单标量** ⇒ 按路落到各自**首府**治所
    （无逐治所来源，**不编造差异**）；路级/全国值改为**按水路档位加权平均**的派生镜像。

    ⚠️ 必须在 `sink_pops_to_seats` **之后**调用——首府判定依赖治所存在。
    返回实际下沉的路数。
    """
    from core.domains.economy import canal_bridge
    return canal_bridge.sink_canal_to_seats(state)
