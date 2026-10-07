# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.domains.administration.officialdom
# 阶段 3 主体：官制×POP 的单一权威源归 administration 域。
from core.domains.administration.officialdom import (
    Any, CLAN_GROWTH_ANNUAL, CLAN_OFFICE_RATIO,
    CLERK_PER_OFFICIAL, Dict, EXAM_EXAMINER_ORG,
    EXAM_INTERVAL_YEARS, FACTION_SINECURE_EXIT_TILT, GENTRY_CLASS,
    OFFICIAL_RETIRE_RATE_YEAR, OFFICIAL_SUB_KEYS, Optional,
    POP_CLASS, RANK_INDEX_CAP, RANK_UP_PER_YEAR,
    ROUTE_POST_QUOTA, SINECURE_PAY_RATIO, Tuple,
    WAITING_PAY_RATIO, WAITING_SINECURE_MULT, YINBEN_PER_JIAOSI,
    YINBEN_PRESTIGE_REF, _PREF_STATE, _annual_clan,
    _annual_rank_up, _annual_retire, _apply_sinecure_faction_exit,
    _blend_faction_inflow, _examiner_faction, _fill_vacancies,
    _gentry_total, _inst, _minister_faction,
    _officials_total, _overflow_to_sinecure, _pop_obj_add,
    _state_of, _triennial_exam, _triennial_yinben,
    add_officials, blend_entrants, check_invariants,
    clan_total, ensure_all, ensure_clan,
    ensure_quota, ensure_subpools, exit_faction_members,
    minister_faction, move_pop_people, post_officials,
    recruit_by_recommendation, register_pref_state, remove_officials,
    rescale_quota, route_clerks, route_officials,
    route_pay_units, settle_officialdom, split_of,
    subpool, sync_legacy_mirror, to_sinecure,
    totals,
)

__all__ = ['Any', 'CLAN_GROWTH_ANNUAL', 'CLAN_OFFICE_RATIO', 'CLERK_PER_OFFICIAL', 'Dict', 'EXAM_EXAMINER_ORG', 'EXAM_INTERVAL_YEARS', 'FACTION_SINECURE_EXIT_TILT', 'GENTRY_CLASS', 'OFFICIAL_RETIRE_RATE_YEAR', 'OFFICIAL_SUB_KEYS', 'Optional', 'POP_CLASS', 'RANK_INDEX_CAP', 'RANK_UP_PER_YEAR', 'ROUTE_POST_QUOTA', 'SINECURE_PAY_RATIO', 'Tuple', 'WAITING_PAY_RATIO', 'WAITING_SINECURE_MULT', 'YINBEN_PER_JIAOSI', 'YINBEN_PRESTIGE_REF', '_PREF_STATE', '_annual_clan', '_annual_rank_up', '_annual_retire', '_apply_sinecure_faction_exit', '_blend_faction_inflow', '_examiner_faction', '_fill_vacancies', '_gentry_total', '_inst', '_minister_faction', '_officials_total', '_overflow_to_sinecure', '_pop_obj_add', '_state_of', '_triennial_exam', '_triennial_yinben', 'add_officials', 'blend_entrants', 'check_invariants', 'clan_total', 'ensure_all', 'ensure_clan', 'ensure_quota', 'ensure_subpools', 'exit_faction_members', 'minister_faction', 'move_pop_people', 'post_officials', 'recruit_by_recommendation', 'register_pref_state', 'remove_officials', 'rescale_quota', 'route_clerks', 'route_officials', 'route_pay_units', 'settle_officialdom', 'split_of', 'subpool', 'sync_legacy_mirror', 'to_sinecure', 'totals']
