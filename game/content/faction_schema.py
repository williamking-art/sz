"""势力配置的**中立结构定义**（P1）。

用户裁定（2026-10-06）：
- **中立的是结构、校验规则与查询接口**，不是数据；宋与外邦**都是各自提供配置的势力**；
- **不得把宋配置作为外邦默认值**；
- **官制因势力而异**：职位、职位到阶层映射、机构与官制参数**全部按势力提供**；
- **经济基础建筑目录跨势力共用**：同一套基础建筑标识 + 字段结构 + 机制接口，
  **不为外邦另造「粮田/桑麻田」等重复类型**；特色内容作为扩展/变体；
- 每个配置须**明确记录已提供 / 缺失 / 有意不适用**。

缺失不等于 0 也不等于 1.0（AGENTS.md 3-3）：本模块**只定义结构与校验**，
**绝不提供任何默认数值**，尤其**不得**把宋侧数值当作兜底。
"""
from typing import Any, Tuple


class FieldState:
    """配置项三态（裁定 3：须明确记录）。"""

    PROVIDED = 'provided'
    MISSING = 'missing'
    NOT_APPLICABLE = 'not_applicable'


class FactionConfigError(ValueError):
    """势力配置不合法 —— **加载期即抛出**，不静默回落。"""


#: 共同基础建筑目录（跨势力共用；P1 只登记宋侧已有的 6 项）。
#: 外邦的「粮田/桑麻田/林果蔗田/牧场/矿场」**不得**直接进入本目录，
#: 须映射到本目录 id，或登记进扩展层 EXTENSION_BUILDINGS。
BASE_BUILDINGS: Tuple[str, ...] = (
    '农田', '自耕农庄', '地主农庄', '工坊', '商铺', '庄园',
)

#: 扩展/变体建筑（建立在共同目录之上的特色内容）。
EXTENSION_BUILDINGS: Tuple[str, ...] = ()

#: 官制相关配置组（**全部按势力提供**；外邦不得照抄宋制）。
OFFICIAL_GROUPS: Tuple[str, ...] = (
    'POSITIONS',
    'POSITION_CLASS',
    'INSTITUTIONS',
    'OFFICIAL_PARAMS',
)

#: 经济/岗位相关配置组。
ECON_GROUPS: Tuple[str, ...] = (
    'JOBS_PER_LEVEL',
    'BUILDING_WORKER',
    'JOB_CLASSES',
    'JOB_QUEUE',
    'JOB_SHARE',
    'JOB_FLOW_RATE',
    'JOB_PUSH_UNEMPLOYED',
)

#: 全部必填配置组（缺任一组 => 加载失败）。
REQUIRED_GROUPS: Tuple[str, ...] = OFFICIAL_GROUPS + ECON_GROUPS


_BANNED_NA_REASON = ('暂无数据', '未实现', '待定', '待补', 'todo', 'tbd', 'none', 'n/a')


def check_not_applicable_reason(faction: str, field: str, reason: Any) -> None:
    """校验 `NOT_APPLICABLE` 必须带**实质理由**。

    裁定：不能因为**目前缺数据**就标 NA。
    """
    s = str(reason or '').strip()
    if not s:
        raise FactionConfigError(
            '[%s] %s: 标为 not_applicable 必须写明理由' % (faction, field))
    low = s.lower()
    for b in _BANNED_NA_REASON:
        if b in low:
            raise FactionConfigError(
                '[%s] %s: 理由「%s」属「缺数据」，不能据此标 not_applicable'
                % (faction, field, s))