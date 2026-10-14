// 截图台 finance fixture（**仅 dev 用**）——由**真实后端口径单点**产出，非手写：
//   `state.finance_readout()`（`core/game_state_econ.py:362`；docstring：供会计录只读奏报台，
//   GUI 与终端共用，避免两处口径漂移）。state = new_game()，seed=20261013，先跑 6 个月结算。
//   ⚠️ 重新生成见本目录 README；**不要手改数字**（口径单点）。生成日期：2026-10-14（M283）

export const FINANCE = {
  "nominal_annual": 28580060,
  "nominal_annual_full": 57628924.0,
  "monthly_in_taxed": 1499367,
  "arrival_ratio_taxed": 0.6295439547712637,
  "arrival_ratio_full": 0.7434475177777048,
  "arrival_ratio_cross_scope": 1.4990899424283923,
  "mechanism_arrival_rate": 0.5874999999999999,
  "arrival_ratio_scope": "三税（工商·役钱·市舶）——不含二税折色与盐课（诊断口径·勿当到账率）｜五科目（工商·役钱·市舶·二税折色[按应征]·盐课）（诊断口径·勿当到账率）",
  "arrival_ratio_scope_taxed": "三税（工商·役钱·市舶）——不含二税折色与盐课（诊断口径·勿当到账率）",
  "arrival_ratio_scope_full": "五科目（工商·役钱·市舶·二税折色[按应征]·盐课）（诊断口径·勿当到账率）",
  "commerce": 1108322,
  "poll": 391045,
  "maritime": 0,
  "tax_color": 1572822,
  "tax_color_legacy": 1478848,
  "salt_coin": 498151.04166666657,
  "assessed_total": 1572822,
  "collection_rate_avg": 0.6239,
  "transfer_rate_avg": 0.94,
  "land_tax_last": {
    "turn": 5,
    "assessed": 1582760,
    "collected": 1298013,
    "central": 1003710,
    "local": 269228,
    "diverted": 25075,
    "required": 216443
  },
  "land_tax_cum": {
    "assessed": 8986404,
    "collected": 6591187,
    "central": 4874028,
    "local": 1588974,
    "diverted": 128185
  },
  "legacy_arrival_rate": 0.5874999999999999,
  "local_expenditure": {
    "cap_share": 0.5,
    "active_kinds": [
      "official_salary",
      "clerk_pay",
      "runner_pay",
      "public_supply"
    ],
    "expense_mult": 1.0,
    "disaster": {
      "severity": 0,
      "region": ""
    },
    "by_kind": {
      "official_salary": 46580,
      "clerk_pay": 155604,
      "runner_pay": 23323,
      "public_supply": 22400,
      "granary": 27688,
      "relief": 0
    },
    "total_due": 275595,
    "total_plan": 275595,
    "total_shortfall": 0,
    "total_due_active": 247907,
    "total_plan_active": 247907,
    "total_shortfall_active": 0,
    "total_due_eff": 216341,
    "total_plan_eff": 216341,
    "total_shortfall_eff": 0,
    "by_route": {
      "京畿路": {
        "coffer": 2331278,
        "official_salary": 2917,
        "clerk_pay": 10666,
        "runner_pay": 2723,
        "public_supply": 1800,
        "granary": 395,
        "relief": 0,
        "due": 18501,
        "cap": 1165639,
        "plan": 18501,
        "shortfall": 0,
        "due_active": 18106,
        "plan_active": 18106,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 1.0,
        "efficacy": 0.8979,
        "due_eff": 16257,
        "plan_eff": 16257,
        "shortfall_eff": 0
      },
      "京西路": {
        "coffer": 1087721,
        "official_salary": 1972,
        "clerk_pay": 6847,
        "runner_pay": 785,
        "public_supply": 1000,
        "granary": 504,
        "relief": 0,
        "due": 11108,
        "cap": 543860,
        "plan": 11108,
        "shortfall": 0,
        "due_active": 10604,
        "plan_active": 10604,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.8865,
        "efficacy": 0.8618,
        "due_eff": 9138,
        "plan_eff": 9138,
        "shortfall_eff": 0
      },
      "京东东路": {
        "coffer": 1207433,
        "official_salary": 2064,
        "clerk_pay": 7227,
        "runner_pay": 0,
        "public_supply": 1000,
        "granary": 408,
        "relief": 0,
        "due": 10699,
        "cap": 603716,
        "plan": 10699,
        "shortfall": 0,
        "due_active": 10291,
        "plan_active": 10291,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.8827,
        "efficacy": 0.8587,
        "due_eff": 8836,
        "plan_eff": 8836,
        "shortfall_eff": 0
      },
      "京东西路": {
        "coffer": 1017329,
        "official_salary": 1779,
        "clerk_pay": 6086,
        "runner_pay": 0,
        "public_supply": 1000,
        "granary": 375,
        "relief": 0,
        "due": 9240,
        "cap": 508664,
        "plan": 9240,
        "shortfall": 0,
        "due_active": 8865,
        "plan_active": 8865,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.8981,
        "efficacy": 0.8613,
        "due_eff": 7635,
        "plan_eff": 7635,
        "shortfall_eff": 0
      },
      "河北路": {
        "coffer": 2029849,
        "official_salary": 3121,
        "clerk_pay": 11409,
        "runner_pay": 2246,
        "public_supply": 1000,
        "granary": 537,
        "relief": 0,
        "due": 18313,
        "cap": 1014924,
        "plan": 18313,
        "shortfall": 0,
        "due_active": 17776,
        "plan_active": 17776,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.8242,
        "efficacy": 0.8412,
        "due_eff": 14953,
        "plan_eff": 14953,
        "shortfall_eff": 0
      },
      "河东路": {
        "coffer": 1405032,
        "official_salary": 2081,
        "clerk_pay": 7607,
        "runner_pay": 1564,
        "public_supply": 1000,
        "granary": 298,
        "relief": 0,
        "due": 12550,
        "cap": 702516,
        "plan": 12550,
        "shortfall": 0,
        "due_active": 12252,
        "plan_active": 12252,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.8241,
        "efficacy": 0.8401,
        "due_eff": 10292,
        "plan_eff": 10292,
        "shortfall_eff": 0
      },
      "陕西路": {
        "coffer": 1578761,
        "official_salary": 2706,
        "clerk_pay": 9888,
        "runner_pay": 9755,
        "public_supply": 1000,
        "granary": 590,
        "relief": 0,
        "due": 23939,
        "cap": 789380,
        "plan": 23939,
        "shortfall": 0,
        "due_active": 23349,
        "plan_active": 23349,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.7491,
        "efficacy": 0.8196,
        "due_eff": 19136,
        "plan_eff": 19136,
        "shortfall_eff": 0
      },
      "两浙路": {
        "coffer": 2103037,
        "official_salary": 5216,
        "clerk_pay": 15598,
        "runner_pay": 1427,
        "public_supply": 1000,
        "granary": 3545,
        "relief": 0,
        "due": 26786,
        "cap": 1051518,
        "plan": 26786,
        "shortfall": 0,
        "due_active": 23241,
        "plan_active": 23241,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 1.0,
        "efficacy": 0.9059,
        "due_eff": 21054,
        "plan_eff": 21054,
        "shortfall_eff": 0
      },
      "江南东路": {
        "coffer": 1457558,
        "official_salary": 3687,
        "clerk_pay": 11028,
        "runner_pay": 735,
        "public_supply": 1000,
        "granary": 2638,
        "relief": 0,
        "due": 19088,
        "cap": 728779,
        "plan": 19088,
        "shortfall": 0,
        "due_active": 16450,
        "plan_active": 16450,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 1.0,
        "efficacy": 0.9039,
        "due_eff": 14869,
        "plan_eff": 14869,
        "shortfall_eff": 0
      },
      "江南西路": {
        "coffer": 1555472,
        "official_salary": 3944,
        "clerk_pay": 11795,
        "runner_pay": 735,
        "public_supply": 1000,
        "granary": 2803,
        "relief": 0,
        "due": 20277,
        "cap": 777736,
        "plan": 20277,
        "shortfall": 0,
        "due_active": 17474,
        "plan_active": 17474,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 1.0,
        "efficacy": 0.9029,
        "due_eff": 15777,
        "plan_eff": 15777,
        "shortfall_eff": 0
      },
      "淮南东路": {
        "coffer": 394283,
        "official_salary": 1762,
        "clerk_pay": 6086,
        "runner_pay": 0,
        "public_supply": 1000,
        "granary": 2344,
        "relief": 0,
        "due": 11192,
        "cap": 197141,
        "plan": 11192,
        "shortfall": 0,
        "due_active": 8848,
        "plan_active": 8848,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 1.0,
        "efficacy": 0.8899,
        "due_eff": 7873,
        "plan_eff": 7873,
        "shortfall_eff": 0
      },
      "淮南西路": {
        "coffer": 643703,
        "official_salary": 1630,
        "clerk_pay": 5706,
        "runner_pay": 0,
        "public_supply": 1000,
        "granary": 1261,
        "relief": 0,
        "due": 9597,
        "cap": 321851,
        "plan": 9597,
        "shortfall": 0,
        "due_active": 8336,
        "plan_active": 8336,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.9721,
        "efficacy": 0.8805,
        "due_eff": 7339,
        "plan_eff": 7339,
        "shortfall_eff": 0
      },
      "荆湖北路": {
        "coffer": 211534,
        "official_salary": 1768,
        "clerk_pay": 6467,
        "runner_pay": 0,
        "public_supply": 1000,
        "granary": 2967,
        "relief": 0,
        "due": 12202,
        "cap": 105767,
        "plan": 12202,
        "shortfall": 0,
        "due_active": 9235,
        "plan_active": 9235,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.9698,
        "efficacy": 0.8838,
        "due_eff": 8161,
        "plan_eff": 8161,
        "shortfall_eff": 0
      },
      "荆湖南路": {
        "coffer": 419239,
        "official_salary": 1976,
        "clerk_pay": 7227,
        "runner_pay": 785,
        "public_supply": 1000,
        "granary": 2628,
        "relief": 0,
        "due": 13616,
        "cap": 209619,
        "plan": 13616,
        "shortfall": 0,
        "due_active": 10988,
        "plan_active": 10988,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.9466,
        "efficacy": 0.8799,
        "due_eff": 9668,
        "plan_eff": 9668,
        "shortfall_eff": 0
      },
      "福建路": {
        "coffer": 1097364,
        "official_salary": 3054,
        "clerk_pay": 9133,
        "runner_pay": 785,
        "public_supply": 1800,
        "granary": 1814,
        "relief": 0,
        "due": 16586,
        "cap": 548682,
        "plan": 16586,
        "shortfall": 0,
        "due_active": 14772,
        "plan_active": 14772,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.9324,
        "efficacy": 0.8726,
        "due_eff": 12890,
        "plan_eff": 12890,
        "shortfall_eff": 0
      },
      "成都府路": {
        "coffer": 905165,
        "official_salary": 2542,
        "clerk_pay": 7607,
        "runner_pay": 998,
        "public_supply": 1000,
        "granary": 1774,
        "relief": 0,
        "due": 13921,
        "cap": 452582,
        "plan": 13921,
        "shortfall": 0,
        "due_active": 12147,
        "plan_active": 12147,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.9222,
        "efficacy": 0.8665,
        "due_eff": 10525,
        "plan_eff": 10525,
        "shortfall_eff": 0
      },
      "利州路": {
        "coffer": 349781,
        "official_salary": 874,
        "clerk_pay": 3201,
        "runner_pay": 0,
        "public_supply": 1000,
        "granary": 501,
        "relief": 0,
        "due": 5576,
        "cap": 174890,
        "plan": 5576,
        "shortfall": 0,
        "due_active": 5075,
        "plan_active": 5075,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.8912,
        "efficacy": 0.8622,
        "due_eff": 4375,
        "plan_eff": 4375,
        "shortfall_eff": 0
      },
      "夔州路": {
        "coffer": 321465,
        "official_salary": 770,
        "clerk_pay": 2820,
        "runner_pay": 0,
        "public_supply": 1000,
        "granary": 429,
        "relief": 0,
        "due": 5019,
        "cap": 160732,
        "plan": 5019,
        "shortfall": 0,
        "due_active": 4590,
        "plan_active": 4590,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.9098,
        "efficacy": 0.8628,
        "due_eff": 3960,
        "plan_eff": 3960,
        "shortfall_eff": 0
      },
      "广南东路": {
        "coffer": 679399,
        "official_salary": 1781,
        "clerk_pay": 5781,
        "runner_pay": 785,
        "public_supply": 1800,
        "granary": 1168,
        "relief": 0,
        "due": 11315,
        "cap": 339699,
        "plan": 11315,
        "shortfall": 0,
        "due_active": 10147,
        "plan_active": 10147,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.96,
        "efficacy": 0.8839,
        "due_eff": 8968,
        "plan_eff": 8968,
        "shortfall_eff": 0
      },
      "广南西路": {
        "coffer": 356063,
        "official_salary": 936,
        "clerk_pay": 3425,
        "runner_pay": 0,
        "public_supply": 1000,
        "granary": 709,
        "relief": 0,
        "due": 6070,
        "cap": 178031,
        "plan": 6070,
        "shortfall": 0,
        "due_active": 5361,
        "plan_active": 5361,
        "shortfall_active": 0,
        "grip": 0.1662,
        "pay_ratio": 0.9156,
        "efficacy": 0.8646,
        "due_eff": 4635,
        "plan_eff": 4635,
        "shortfall_eff": 0
      }
    }
  },
  "local_arrears": 0,
  "local_expense_paid": 1323155,
  "land_tax_required": 1321809,
  "local_arrears_by_kind": {},
  "local_arrears_pop": 0,
  "local_extra_income": 981675,
  "local_extra_by_kind": {
    "坊场钱": 539531,
    "经制钱": 269536,
    "杂税": 172608
  },
  "local_arrears_pressure": {},
  "local_arrears_by_identity": {},
  "identity_economics": {
    "total": {
      "officials": 32290,
      "clerks": 216130,
      "officials_wealth": 248345,
      "clerks_wealth": 828472,
      "pool_wealth": 13986067,
      "officials_salary_arrears": 0,
      "clerks_pay_arrears": 0,
      "runner_count": 0,
      "officials_wealth_share": 0.2306,
      "clerks_wealth_share": 0.7694,
      "occupation_income": {
        "runner": 127310
      }
    },
    "by_route": {
      "京畿路": {
        "officials": 2117,
        "clerks": 14814,
        "officials_wealth": 15934,
        "clerks_wealth": 58266,
        "attributed_total": 74200,
        "pool_wealth": 1018282,
        "coverage": 0.0729,
        "officials_wealth_share": 0.2147,
        "clerks_wealth_share": 0.7853,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 15647
        }
      },
      "京西路": {
        "officials": 1358,
        "clerks": 9510,
        "officials_wealth": 10320,
        "clerks_wealth": 35840,
        "attributed_total": 46160,
        "pool_wealth": 582662,
        "coverage": 0.0792,
        "officials_wealth_share": 0.2236,
        "clerks_wealth_share": 0.7764,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 4210
        }
      },
      "京东东路": {
        "officials": 1434,
        "clerks": 10038,
        "officials_wealth": 10793,
        "clerks_wealth": 37799,
        "attributed_total": 48592,
        "pool_wealth": 656372,
        "coverage": 0.074,
        "officials_wealth_share": 0.2221,
        "clerks_wealth_share": 0.7779,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 0
        }
      },
      "京东西路": {
        "officials": 1208,
        "clerks": 8454,
        "officials_wealth": 9340,
        "clerks_wealth": 31958,
        "attributed_total": 41298,
        "pool_wealth": 515084,
        "coverage": 0.0802,
        "officials_wealth_share": 0.2262,
        "clerks_wealth_share": 0.7738,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 0
        }
      },
      "河北路": {
        "officials": 2265,
        "clerks": 15846,
        "officials_wealth": 15996,
        "clerks_wealth": 58478,
        "attributed_total": 74474,
        "pool_wealth": 942961,
        "coverage": 0.079,
        "officials_wealth_share": 0.2148,
        "clerks_wealth_share": 0.7852,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 12255
        }
      },
      "河东路": {
        "officials": 1510,
        "clerks": 10566,
        "officials_wealth": 10636,
        "clerks_wealth": 38890,
        "attributed_total": 49526,
        "pool_wealth": 627082,
        "coverage": 0.079,
        "officials_wealth_share": 0.2148,
        "clerks_wealth_share": 0.7852,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 8342
        }
      },
      "陕西路": {
        "officials": 1964,
        "clerks": 13734,
        "officials_wealth": 13500,
        "clerks_wealth": 49331,
        "attributed_total": 62831,
        "pool_wealth": 844659,
        "coverage": 0.0744,
        "officials_wealth_share": 0.2149,
        "clerks_wealth_share": 0.7851,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 52041
        }
      },
      "两浙路": {
        "officials": 3457,
        "clerks": 21664,
        "officials_wealth": 28738,
        "clerks_wealth": 85938,
        "attributed_total": 114676,
        "pool_wealth": 1464535,
        "coverage": 0.0783,
        "officials_wealth_share": 0.2506,
        "clerks_wealth_share": 0.7494,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 8190
        }
      },
      "江南东路": {
        "officials": 2444,
        "clerks": 15318,
        "officials_wealth": 20264,
        "clerks_wealth": 60625,
        "attributed_total": 80889,
        "pool_wealth": 1030129,
        "coverage": 0.0785,
        "officials_wealth_share": 0.2505,
        "clerks_wealth_share": 0.7495,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 4146
        }
      },
      "江南西路": {
        "officials": 2614,
        "clerks": 16382,
        "officials_wealth": 21693,
        "clerks_wealth": 64884,
        "attributed_total": 86577,
        "pool_wealth": 1100762,
        "coverage": 0.0787,
        "officials_wealth_share": 0.2506,
        "clerks_wealth_share": 0.7494,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 4149
        }
      },
      "淮南东路": {
        "officials": 1208,
        "clerks": 8454,
        "officials_wealth": 9548,
        "clerks_wealth": 32991,
        "attributed_total": 42539,
        "pool_wealth": 550269,
        "coverage": 0.0773,
        "officials_wealth_share": 0.2245,
        "clerks_wealth_share": 0.7755,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 0
        }
      },
      "淮南西路": {
        "officials": 1133,
        "clerks": 7926,
        "officials_wealth": 8760,
        "clerks_wealth": 30672,
        "attributed_total": 39432,
        "pool_wealth": 505888,
        "coverage": 0.0779,
        "officials_wealth_share": 0.2222,
        "clerks_wealth_share": 0.7778,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 0
        }
      },
      "荆湖北路": {
        "officials": 1283,
        "clerks": 8982,
        "officials_wealth": 9505,
        "clerks_wealth": 34774,
        "attributed_total": 44279,
        "pool_wealth": 570120,
        "coverage": 0.0777,
        "officials_wealth_share": 0.2147,
        "clerks_wealth_share": 0.7853,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 0
        }
      },
      "荆湖南路": {
        "officials": 1434,
        "clerks": 10038,
        "officials_wealth": 10570,
        "clerks_wealth": 38671,
        "attributed_total": 49241,
        "pool_wealth": 635483,
        "coverage": 0.0775,
        "officials_wealth_share": 0.2147,
        "clerks_wealth_share": 0.7853,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 4303
        }
      },
      "福建路": {
        "officials": 2024,
        "clerks": 12686,
        "officials_wealth": 16205,
        "clerks_wealth": 48475,
        "attributed_total": 64680,
        "pool_wealth": 843641,
        "coverage": 0.0767,
        "officials_wealth_share": 0.2505,
        "clerks_wealth_share": 0.7495,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 4269
        }
      },
      "成都府路": {
        "officials": 1685,
        "clerks": 10566,
        "officials_wealth": 13414,
        "clerks_wealth": 40148,
        "attributed_total": 53562,
        "pool_wealth": 703261,
        "coverage": 0.0762,
        "officials_wealth_share": 0.2504,
        "clerks_wealth_share": 0.7496,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 5436
        }
      },
      "利州路": {
        "officials": 634,
        "clerks": 4446,
        "officials_wealth": 4582,
        "clerks_wealth": 16783,
        "attributed_total": 21365,
        "pool_wealth": 276586,
        "coverage": 0.0772,
        "officials_wealth_share": 0.2145,
        "clerks_wealth_share": 0.7855,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 0
        }
      },
      "夔州路": {
        "officials": 559,
        "clerks": 3918,
        "officials_wealth": 4049,
        "clerks_wealth": 14836,
        "attributed_total": 18885,
        "pool_wealth": 264559,
        "coverage": 0.0714,
        "officials_wealth_share": 0.2144,
        "clerks_wealth_share": 0.7856,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 0
        }
      },
      "广南东路": {
        "officials": 1280,
        "clerks": 8030,
        "officials_wealth": 9563,
        "clerks_wealth": 31048,
        "attributed_total": 40611,
        "pool_wealth": 529375,
        "coverage": 0.0767,
        "officials_wealth_share": 0.2355,
        "clerks_wealth_share": 0.7645,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 4322
        }
      },
      "广南西路": {
        "officials": 679,
        "clerks": 4758,
        "officials_wealth": 4935,
        "clerks_wealth": 18065,
        "attributed_total": 23000,
        "pool_wealth": 324357,
        "coverage": 0.0709,
        "officials_wealth_share": 0.2146,
        "clerks_wealth_share": 0.7854,
        "officials_salary_arrears": 0,
        "clerks_pay_arrears": 0,
        "runner_count": 0,
        "occupation_income": {
          "runner": 0
        }
      }
    }
  },
  "local_identities": {
    "total": {
      "official": 32290,
      "clerk": 216130,
      "soldier": 600000,
      "militia": 150000,
      "runner": 0,
      "runner_income": 127310,
      "soldiers_arrears": 0,
      "runners_pay_arrears": 0,
      "militia_pay_arrears": 0
    },
    "by_route": {
      "京畿路": {
        "official": 2117,
        "clerk": 14814,
        "soldier": 80000,
        "militia": 0,
        "runner": 0,
        "runner_income": 15647,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "京西路": {
        "official": 1358,
        "clerk": 9510,
        "soldier": 20000,
        "militia": 10000,
        "runner": 0,
        "runner_income": 4210,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "京东东路": {
        "official": 1434,
        "clerk": 10038,
        "soldier": 0,
        "militia": 0,
        "runner": 0,
        "runner_income": 0,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "京东西路": {
        "official": 1208,
        "clerk": 8454,
        "soldier": 0,
        "militia": 0,
        "runner": 0,
        "runner_income": 0,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "河北路": {
        "official": 2265,
        "clerk": 15846,
        "soldier": 50000,
        "militia": 30000,
        "runner": 0,
        "runner_income": 12255,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "河东路": {
        "official": 1510,
        "clerk": 10566,
        "soldier": 40000,
        "militia": 10000,
        "runner": 0,
        "runner_income": 8342,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "陕西路": {
        "official": 1964,
        "clerk": 13734,
        "soldier": 240000,
        "militia": 20000,
        "runner": 0,
        "runner_income": 52041,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "两浙路": {
        "official": 3457,
        "clerk": 21664,
        "soldier": 40000,
        "militia": 20000,
        "runner": 0,
        "runner_income": 8190,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "江南东路": {
        "official": 2444,
        "clerk": 15318,
        "soldier": 20000,
        "militia": 10000,
        "runner": 0,
        "runner_income": 4146,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "江南西路": {
        "official": 2614,
        "clerk": 16382,
        "soldier": 20000,
        "militia": 10000,
        "runner": 0,
        "runner_income": 4149,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "淮南东路": {
        "official": 1208,
        "clerk": 8454,
        "soldier": 0,
        "militia": 0,
        "runner": 0,
        "runner_income": 0,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "淮南西路": {
        "official": 1133,
        "clerk": 7926,
        "soldier": 0,
        "militia": 0,
        "runner": 0,
        "runner_income": 0,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "荆湖北路": {
        "official": 1283,
        "clerk": 8982,
        "soldier": 0,
        "militia": 0,
        "runner": 0,
        "runner_income": 0,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "荆湖南路": {
        "official": 1434,
        "clerk": 10038,
        "soldier": 20000,
        "militia": 10000,
        "runner": 0,
        "runner_income": 4303,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "福建路": {
        "official": 2024,
        "clerk": 12686,
        "soldier": 20000,
        "militia": 10000,
        "runner": 0,
        "runner_income": 4269,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "成都府路": {
        "official": 1685,
        "clerk": 10566,
        "soldier": 30000,
        "militia": 10000,
        "runner": 0,
        "runner_income": 5436,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "利州路": {
        "official": 634,
        "clerk": 4446,
        "soldier": 0,
        "militia": 0,
        "runner": 0,
        "runner_income": 0,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "夔州路": {
        "official": 559,
        "clerk": 3918,
        "soldier": 0,
        "militia": 0,
        "runner": 0,
        "runner_income": 0,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "广南东路": {
        "official": 1280,
        "clerk": 8030,
        "soldier": 20000,
        "militia": 10000,
        "runner": 0,
        "runner_income": 4322,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      },
      "广南西路": {
        "official": 679,
        "clerk": 4758,
        "soldier": 0,
        "militia": 0,
        "runner": 0,
        "runner_income": 0,
        "soldiers_arrears": 0,
        "runners_pay_arrears": 0,
        "militia_pay_arrears": 0
      }
    }
  },
  "identity_pressures": {
    "total": {
      "clerk_pressure_max": 3.6,
      "official_pressure_max": 3.98,
      "runner_pressure_max": 3.6,
      "routes_with_clerk_arrears": 0,
      "routes_with_official_arrears": 0,
      "max_arrears_months": 0.0
    },
    "by_route": {
      "京畿路": {
        "clerk_pressure": 3.51,
        "official_pressure": 0.19,
        "runner_pressure": 3.51,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 1.0,
          "div": 0.019
        }
      },
      "京西路": {
        "clerk_pressure": 3.53,
        "official_pressure": 1.91,
        "runner_pressure": 3.53,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.8865,
          "div": 0.021
        }
      },
      "京东东路": {
        "clerk_pressure": 3.55,
        "official_pressure": 1.99,
        "runner_pressure": 3.55,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.8827,
          "div": 0.023
        }
      },
      "京东西路": {
        "clerk_pressure": 3.57,
        "official_pressure": 1.78,
        "runner_pressure": 3.57,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.8981,
          "div": 0.025
        }
      },
      "河北路": {
        "clerk_pressure": 3.55,
        "official_pressure": 2.87,
        "runner_pressure": 3.55,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.8242,
          "div": 0.023
        }
      },
      "河东路": {
        "clerk_pressure": 3.56,
        "official_pressure": 2.88,
        "runner_pressure": 3.56,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.8241,
          "div": 0.024
        }
      },
      "陕西路": {
        "clerk_pressure": 3.54,
        "official_pressure": 3.98,
        "runner_pressure": 3.54,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.7491,
          "div": 0.022
        }
      },
      "两浙路": {
        "clerk_pressure": 3.43,
        "official_pressure": 0.11,
        "runner_pressure": 3.43,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 1.0,
          "div": 0.011
        }
      },
      "江南东路": {
        "clerk_pressure": 3.45,
        "official_pressure": 0.13,
        "runner_pressure": 3.45,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 1.0,
          "div": 0.013
        }
      },
      "江南西路": {
        "clerk_pressure": 3.46,
        "official_pressure": 0.14,
        "runner_pressure": 3.46,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 1.0,
          "div": 0.014
        }
      },
      "淮南东路": {
        "clerk_pressure": 3.59,
        "official_pressure": 0.27,
        "runner_pressure": 3.59,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 1.0,
          "div": 0.027
        }
      },
      "淮南西路": {
        "clerk_pressure": 3.6,
        "official_pressure": 0.7,
        "runner_pressure": 3.6,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.9721,
          "div": 0.028
        }
      },
      "荆湖北路": {
        "clerk_pressure": 3.56,
        "official_pressure": 0.69,
        "runner_pressure": 3.56,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.9698,
          "div": 0.024
        }
      },
      "荆湖南路": {
        "clerk_pressure": 3.53,
        "official_pressure": 1.01,
        "runner_pressure": 3.53,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.9466,
          "div": 0.021
        }
      },
      "福建路": {
        "clerk_pressure": 3.56,
        "official_pressure": 1.25,
        "runner_pressure": 3.56,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.9324,
          "div": 0.024
        }
      },
      "成都府路": {
        "clerk_pressure": 3.59,
        "official_pressure": 1.44,
        "runner_pressure": 3.59,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.9222,
          "div": 0.027
        }
      },
      "利州路": {
        "clerk_pressure": 3.54,
        "official_pressure": 1.85,
        "runner_pressure": 3.54,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.8912,
          "div": 0.022
        }
      },
      "夔州路": {
        "clerk_pressure": 3.59,
        "official_pressure": 1.62,
        "runner_pressure": 3.59,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.9098,
          "div": 0.027
        }
      },
      "广南东路": {
        "clerk_pressure": 3.53,
        "official_pressure": 0.81,
        "runner_pressure": 3.53,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.96,
          "div": 0.021
        }
      },
      "广南西路": {
        "clerk_pressure": 3.59,
        "official_pressure": 1.54,
        "runner_pressure": 3.59,
        "inputs": {
          "clerk_arrears": 0,
          "official_arrears": 0,
          "runner_arrears": 0,
          "clerk_months": 0.0,
          "official_months": 0.0,
          "runner_months": 0.0,
          "grip": 0.1662,
          "pay_ratio": 0.9156,
          "div": 0.027
        }
      }
    }
  },
  "fiscal_visibility": {
    "official": {
      "land_central": 4874028,
      "loss_report": {
        "运输损耗": 32044,
        "地方耗费": 12816,
        "火耗": 76919,
        "杂费": 6406,
        "total": 128185
      },
      "loss_status": "正常"
    },
    "rumor": {
      "tier": 1,
      "label": "钱粮迟滞",
      "signals": {
        "routes_tier_ge1": 8,
        "routes_tier_ge2": 0,
        "routes_tier_ge3": 0,
        "routes_tier_ge4": 0
      },
      "by_route": {
        "京畿路": {
          "tier": 1,
          "label": "钱粮迟滞",
          "signals": {
            "months": 0.0,
            "pressure": 3.51,
            "grip": 0.1662,
            "grain_price": 2.1375,
            "unrest": 0.0
          }
        },
        "京西路": {
          "tier": 1,
          "label": "钱粮迟滞",
          "signals": {
            "months": 0.0,
            "pressure": 3.53,
            "grip": 0.1662,
            "grain_price": 2.0649,
            "unrest": 10.81
          }
        },
        "京东东路": {
          "tier": 1,
          "label": "钱粮迟滞",
          "signals": {
            "months": 0.0,
            "pressure": 3.55,
            "grip": 0.1662,
            "grain_price": 2.3131,
            "unrest": 15.0
          }
        },
        "京东西路": {
          "tier": 1,
          "label": "钱粮迟滞",
          "signals": {
            "months": 0.0,
            "pressure": 3.57,
            "grip": 0.1662,
            "grain_price": 2.2358,
            "unrest": 15.0
          }
        },
        "河北路": {
          "tier": 1,
          "label": "钱粮迟滞",
          "signals": {
            "months": 0.0,
            "pressure": 3.55,
            "grip": 0.1662,
            "grain_price": 2.0655,
            "unrest": 11.74
          }
        },
        "河东路": {
          "tier": 1,
          "label": "钱粮迟滞",
          "signals": {
            "months": 0.0,
            "pressure": 3.56,
            "grip": 0.1662,
            "grain_price": 2.1324,
            "unrest": 15.66
          }
        },
        "陕西路": {
          "tier": 1,
          "label": "钱粮迟滞",
          "signals": {
            "months": 0.0,
            "pressure": 3.98,
            "grip": 0.1662,
            "grain_price": 1.9875,
            "unrest": 0.0
          }
        },
        "两浙路": {
          "tier": 0,
          "label": "无异常",
          "signals": {
            "months": 0.0,
            "pressure": 3.43,
            "grip": 0.1662,
            "grain_price": 1.1226,
            "unrest": 0.0
          }
        },
        "江南东路": {
          "tier": 0,
          "label": "无异常",
          "signals": {
            "months": 0.0,
            "pressure": 3.45,
            "grip": 0.1662,
            "grain_price": 1.0628,
            "unrest": 3.86
          }
        },
        "江南西路": {
          "tier": 0,
          "label": "无异常",
          "signals": {
            "months": 0.0,
            "pressure": 3.46,
            "grip": 0.1662,
            "grain_price": 1.0695,
            "unrest": 3.85
          }
        },
        "淮南东路": {
          "tier": 0,
          "label": "无异常",
          "signals": {
            "months": 0.0,
            "pressure": 3.59,
            "grip": 0.1662,
            "grain_price": 0.9861,
            "unrest": 15.0
          }
        },
        "淮南西路": {
          "tier": 0,
          "label": "无异常",
          "signals": {
            "months": 0.0,
            "pressure": 3.6,
            "grip": 0.1662,
            "grain_price": 1.1505,
            "unrest": 15.0
          }
        },
        "荆湖北路": {
          "tier": 0,
          "label": "无异常",
          "signals": {
            "months": 0.0,
            "pressure": 3.56,
            "grip": 0.1662,
            "grain_price": 0.9079,
            "unrest": 15.0
          }
        },
        "荆湖南路": {
          "tier": 0,
          "label": "无异常",
          "signals": {
            "months": 0.0,
            "pressure": 3.53,
            "grip": 0.1662,
            "grain_price": 1.0041,
            "unrest": 10.69
          }
        },
        "福建路": {
          "tier": 0,
          "label": "无异常",
          "signals": {
            "months": 0.0,
            "pressure": 3.56,
            "grip": 0.1662,
            "grain_price": 1.3047,
            "unrest": 10.74
          }
        },
        "成都府路": {
          "tier": 0,
          "label": "无异常",
          "signals": {
            "months": 0.0,
            "pressure": 3.59,
            "grip": 0.1662,
            "grain_price": 1.0926,
            "unrest": 9.57
          }
        },
        "利州路": {
          "tier": 0,
          "label": "无异常",
          "signals": {
            "months": 0.0,
            "pressure": 3.54,
            "grip": 0.1662,
            "grain_price": 1.5892,
            "unrest": 24.0
          }
        },
        "夔州路": {
          "tier": 1,
          "label": "钱粮迟滞",
          "signals": {
            "months": 0.0,
            "pressure": 3.59,
            "grip": 0.1662,
            "grain_price": 1.6073,
            "unrest": 15.0
          }
        },
        "广南东路": {
          "tier": 0,
          "label": "无异常",
          "signals": {
            "months": 0.0,
            "pressure": 3.53,
            "grip": 0.1662,
            "grain_price": 1.2768,
            "unrest": 10.69
          }
        },
        "广南西路": {
          "tier": 0,
          "label": "无异常",
          "signals": {
            "months": 0.0,
            "pressure": 3.59,
            "grip": 0.1662,
            "grain_price": 1.2376,
            "unrest": 24.0
          }
        }
      },
      "discovery": {
        "level": 0,
        "anomalies": [],
        "suspicions": [],
        "evidence": [],
        "truths": []
      }
    },
    "viewer": "player",
    "layers": [
      "official",
      "rumor"
    ],
    "granularity": "route"
  },
  "local_arrears_months": {
    "official_salary": {
      "max": 0.0,
      "mean": 0.0,
      "routes_over_3": 0,
      "longest_route": null
    },
    "clerk_pay": {
      "max": 0.0,
      "mean": 0.0,
      "routes_over_3": 0,
      "longest_route": null
    },
    "runner_pay": {
      "max": 0.0,
      "mean": 0.0,
      "routes_over_3": 0,
      "longest_route": null
    },
    "public_supply": {
      "max": 0.0,
      "mean": 0.0,
      "routes_over_3": 0,
      "longest_route": null
    }
  },
  "arrears_recovery_capacity": {
    "total": {
      "treasury_available": 0,
      "coffer_surplus_total": 20935125,
      "arrears_total": 0,
      "recoverable_total": 20935125,
      "routes_with_arrears": 0,
      "routes_over_3_months": 0,
      "priority": [
        "clerk_pay",
        "runner_pay",
        "public_supply",
        "official_salary"
      ]
    },
    "by_route": {
      "京畿路": {
        "coffer": 2331278,
        "coffer_surplus": 2315021,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.51,
          "official_pressure": 0.19,
          "runner_pressure": 3.51
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "京西路": {
        "coffer": 1087721,
        "coffer_surplus": 1078583,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.53,
          "official_pressure": 1.91,
          "runner_pressure": 3.53
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "京东东路": {
        "coffer": 1207433,
        "coffer_surplus": 1198597,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.55,
          "official_pressure": 1.99,
          "runner_pressure": 3.55
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "京东西路": {
        "coffer": 1017329,
        "coffer_surplus": 1009694,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.57,
          "official_pressure": 1.78,
          "runner_pressure": 3.57
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "河北路": {
        "coffer": 2029849,
        "coffer_surplus": 2014896,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.55,
          "official_pressure": 2.87,
          "runner_pressure": 3.55
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "河东路": {
        "coffer": 1405032,
        "coffer_surplus": 1394740,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.56,
          "official_pressure": 2.88,
          "runner_pressure": 3.56
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "陕西路": {
        "coffer": 1578761,
        "coffer_surplus": 1559625,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.54,
          "official_pressure": 3.98,
          "runner_pressure": 3.54
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "两浙路": {
        "coffer": 2103037,
        "coffer_surplus": 2081983,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.43,
          "official_pressure": 0.11,
          "runner_pressure": 3.43
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "江南东路": {
        "coffer": 1457558,
        "coffer_surplus": 1442689,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.45,
          "official_pressure": 0.13,
          "runner_pressure": 3.45
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "江南西路": {
        "coffer": 1555472,
        "coffer_surplus": 1539695,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.46,
          "official_pressure": 0.14,
          "runner_pressure": 3.46
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "淮南东路": {
        "coffer": 394283,
        "coffer_surplus": 386410,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.59,
          "official_pressure": 0.27,
          "runner_pressure": 3.59
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "淮南西路": {
        "coffer": 643703,
        "coffer_surplus": 636364,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.6,
          "official_pressure": 0.7,
          "runner_pressure": 3.6
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "荆湖北路": {
        "coffer": 211534,
        "coffer_surplus": 203373,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.56,
          "official_pressure": 0.69,
          "runner_pressure": 3.56
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "荆湖南路": {
        "coffer": 419239,
        "coffer_surplus": 409571,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.53,
          "official_pressure": 1.01,
          "runner_pressure": 3.53
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "福建路": {
        "coffer": 1097364,
        "coffer_surplus": 1084474,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.56,
          "official_pressure": 1.25,
          "runner_pressure": 3.56
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "成都府路": {
        "coffer": 905165,
        "coffer_surplus": 894640,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.59,
          "official_pressure": 1.44,
          "runner_pressure": 3.59
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "利州路": {
        "coffer": 349781,
        "coffer_surplus": 345406,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.54,
          "official_pressure": 1.85,
          "runner_pressure": 3.54
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "夔州路": {
        "coffer": 321465,
        "coffer_surplus": 317505,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.59,
          "official_pressure": 1.62,
          "runner_pressure": 3.59
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "广南东路": {
        "coffer": 679399,
        "coffer_surplus": 670431,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.53,
          "official_pressure": 0.81,
          "runner_pressure": 3.53
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      },
      "广南西路": {
        "coffer": 356063,
        "coffer_surplus": 351428,
        "treasury_available": 0,
        "arrears_by_kind": {
          "official_salary": 0,
          "clerk_pay": 0,
          "runner_pay": 0,
          "public_supply": 0
        },
        "arrears_total": 0,
        "months": {
          "official_salary": 0.0,
          "clerk_pay": 0.0,
          "runner_pay": 0.0,
          "public_supply": 0.0
        },
        "pressure": {
          "clerk_pressure": 3.59,
          "official_pressure": 1.54,
          "runner_pressure": 3.59
        },
        "priority": [
          "clerk_pay",
          "runner_pay",
          "public_supply",
          "official_salary"
        ]
      }
    }
  },
  "local_arrears_repaid": 0,
  "rumor_tier": 1,
  "rumor": {
    "tier": 1,
    "label": "钱粮迟滞",
    "signals": {
      "routes_tier_ge1": 8,
      "routes_tier_ge2": 0,
      "routes_tier_ge3": 0,
      "routes_tier_ge4": 0
    },
    "by_route": {
      "京畿路": {
        "tier": 1,
        "label": "钱粮迟滞",
        "signals": {
          "months": 0.0,
          "pressure": 3.51,
          "grip": 0.1662,
          "grain_price": 2.1375,
          "unrest": 0.0
        }
      },
      "京西路": {
        "tier": 1,
        "label": "钱粮迟滞",
        "signals": {
          "months": 0.0,
          "pressure": 3.53,
          "grip": 0.1662,
          "grain_price": 2.0649,
          "unrest": 10.81
        }
      },
      "京东东路": {
        "tier": 1,
        "label": "钱粮迟滞",
        "signals": {
          "months": 0.0,
          "pressure": 3.55,
          "grip": 0.1662,
          "grain_price": 2.3131,
          "unrest": 15.0
        }
      },
      "京东西路": {
        "tier": 1,
        "label": "钱粮迟滞",
        "signals": {
          "months": 0.0,
          "pressure": 3.57,
          "grip": 0.1662,
          "grain_price": 2.2358,
          "unrest": 15.0
        }
      },
      "河北路": {
        "tier": 1,
        "label": "钱粮迟滞",
        "signals": {
          "months": 0.0,
          "pressure": 3.55,
          "grip": 0.1662,
          "grain_price": 2.0655,
          "unrest": 11.74
        }
      },
      "河东路": {
        "tier": 1,
        "label": "钱粮迟滞",
        "signals": {
          "months": 0.0,
          "pressure": 3.56,
          "grip": 0.1662,
          "grain_price": 2.1324,
          "unrest": 15.66
        }
      },
      "陕西路": {
        "tier": 1,
        "label": "钱粮迟滞",
        "signals": {
          "months": 0.0,
          "pressure": 3.98,
          "grip": 0.1662,
          "grain_price": 1.9875,
          "unrest": 0.0
        }
      },
      "两浙路": {
        "tier": 0,
        "label": "无异常",
        "signals": {
          "months": 0.0,
          "pressure": 3.43,
          "grip": 0.1662,
          "grain_price": 1.1226,
          "unrest": 0.0
        }
      },
      "江南东路": {
        "tier": 0,
        "label": "无异常",
        "signals": {
          "months": 0.0,
          "pressure": 3.45,
          "grip": 0.1662,
          "grain_price": 1.0628,
          "unrest": 3.86
        }
      },
      "江南西路": {
        "tier": 0,
        "label": "无异常",
        "signals": {
          "months": 0.0,
          "pressure": 3.46,
          "grip": 0.1662,
          "grain_price": 1.0695,
          "unrest": 3.85
        }
      },
      "淮南东路": {
        "tier": 0,
        "label": "无异常",
        "signals": {
          "months": 0.0,
          "pressure": 3.59,
          "grip": 0.1662,
          "grain_price": 0.9861,
          "unrest": 15.0
        }
      },
      "淮南西路": {
        "tier": 0,
        "label": "无异常",
        "signals": {
          "months": 0.0,
          "pressure": 3.6,
          "grip": 0.1662,
          "grain_price": 1.1505,
          "unrest": 15.0
        }
      },
      "荆湖北路": {
        "tier": 0,
        "label": "无异常",
        "signals": {
          "months": 0.0,
          "pressure": 3.56,
          "grip": 0.1662,
          "grain_price": 0.9079,
          "unrest": 15.0
        }
      },
      "荆湖南路": {
        "tier": 0,
        "label": "无异常",
        "signals": {
          "months": 0.0,
          "pressure": 3.53,
          "grip": 0.1662,
          "grain_price": 1.0041,
          "unrest": 10.69
        }
      },
      "福建路": {
        "tier": 0,
        "label": "无异常",
        "signals": {
          "months": 0.0,
          "pressure": 3.56,
          "grip": 0.1662,
          "grain_price": 1.3047,
          "unrest": 10.74
        }
      },
      "成都府路": {
        "tier": 0,
        "label": "无异常",
        "signals": {
          "months": 0.0,
          "pressure": 3.59,
          "grip": 0.1662,
          "grain_price": 1.0926,
          "unrest": 9.57
        }
      },
      "利州路": {
        "tier": 0,
        "label": "无异常",
        "signals": {
          "months": 0.0,
          "pressure": 3.54,
          "grip": 0.1662,
          "grain_price": 1.5892,
          "unrest": 24.0
        }
      },
      "夔州路": {
        "tier": 1,
        "label": "钱粮迟滞",
        "signals": {
          "months": 0.0,
          "pressure": 3.59,
          "grip": 0.1662,
          "grain_price": 1.6073,
          "unrest": 15.0
        }
      },
      "广南东路": {
        "tier": 0,
        "label": "无异常",
        "signals": {
          "months": 0.0,
          "pressure": 3.53,
          "grip": 0.1662,
          "grain_price": 1.2768,
          "unrest": 10.69
        }
      },
      "广南西路": {
        "tier": 0,
        "label": "无异常",
        "signals": {
          "months": 0.0,
          "pressure": 3.59,
          "grip": 0.1662,
          "grain_price": 1.2376,
          "unrest": 24.0
        }
      }
    }
  },
  "population_breakdown": {
    "pop_classes": {
      "农": 90764744,
      "士绅": 1397695,
      "工匠": 5000000,
      "商人": 3000000,
      "官僚": 248420,
      "兵": 750000
    },
    "occupations": {
      "runner": 0
    },
    "size_total": 101160859,
    "occupation_total": 0,
    "in_registry_total": 101160859,
    "refugees": 19960,
    "population_field": 101180819
  },
  "fiscal_gap_report": {
    "viewer": "player",
    "allow_real": false,
    "by_route": {
      "京畿路": {
        "route": "京畿路",
        "loss_report_total": 128185
      },
      "京西路": {
        "route": "京西路",
        "loss_report_total": 128185
      },
      "京东东路": {
        "route": "京东东路",
        "loss_report_total": 128185
      },
      "京东西路": {
        "route": "京东西路",
        "loss_report_total": 128185
      },
      "河北路": {
        "route": "河北路",
        "loss_report_total": 128185
      },
      "河东路": {
        "route": "河东路",
        "loss_report_total": 128185
      },
      "陕西路": {
        "route": "陕西路",
        "loss_report_total": 128185
      },
      "两浙路": {
        "route": "两浙路",
        "loss_report_total": 128185
      },
      "江南东路": {
        "route": "江南东路",
        "loss_report_total": 128185
      },
      "江南西路": {
        "route": "江南西路",
        "loss_report_total": 128185
      },
      "淮南东路": {
        "route": "淮南东路",
        "loss_report_total": 128185
      },
      "淮南西路": {
        "route": "淮南西路",
        "loss_report_total": 128185
      },
      "荆湖北路": {
        "route": "荆湖北路",
        "loss_report_total": 128185
      },
      "荆湖南路": {
        "route": "荆湖南路",
        "loss_report_total": 128185
      },
      "福建路": {
        "route": "福建路",
        "loss_report_total": 128185
      },
      "成都府路": {
        "route": "成都府路",
        "loss_report_total": 128185
      },
      "利州路": {
        "route": "利州路",
        "loss_report_total": 128185
      },
      "夔州路": {
        "route": "夔州路",
        "loss_report_total": 128185
      },
      "广南东路": {
        "route": "广南东路",
        "loss_report_total": 128185
      },
      "广南西路": {
        "route": "广南西路",
        "loss_report_total": 128185
      }
    },
    "totals": {
      "loss_report_total": 2563700
    },
    "identities": {
      "note": "需监察权限（只读复核）"
    }
  },
  "inspection_backlash": {
    "actions": 0,
    "grievance_added": 0.0,
    "unrest_added": 0.0,
    "by_route": {
      "京畿路": {
        "grievance": 12.054,
        "unrest": 0.0
      },
      "京西路": {
        "grievance": 14.219,
        "unrest": 10.81
      },
      "京东东路": {
        "grievance": 14.292,
        "unrest": 15.0
      },
      "京东西路": {
        "grievance": 13.997,
        "unrest": 15.0
      },
      "河北路": {
        "grievance": 15.408,
        "unrest": 11.74
      },
      "河东路": {
        "grievance": 15.41,
        "unrest": 15.66
      },
      "陕西路": {
        "grievance": 16.843,
        "unrest": 0.0
      },
      "两浙路": {
        "grievance": 12.053,
        "unrest": 0.0
      },
      "江南东路": {
        "grievance": 12.054,
        "unrest": 3.86
      },
      "江南西路": {
        "grievance": 12.054,
        "unrest": 3.85
      },
      "淮南东路": {
        "grievance": 12.054,
        "unrest": 15.0
      },
      "淮南西路": {
        "grievance": 12.584,
        "unrest": 15.0
      },
      "荆湖北路": {
        "grievance": 12.628,
        "unrest": 15.0
      },
      "荆湖南路": {
        "grievance": 13.072,
        "unrest": 10.69
      },
      "福建路": {
        "grievance": 13.344,
        "unrest": 10.74
      },
      "成都府路": {
        "grievance": 13.539,
        "unrest": 9.57
      },
      "利州路": {
        "grievance": 14.129,
        "unrest": 24.0
      },
      "夔州路": {
        "grievance": 13.774,
        "unrest": 15.0
      },
      "广南东路": {
        "grievance": 12.816,
        "unrest": 10.69
      },
      "广南西路": {
        "grievance": 13.663,
        "unrest": 24.0
      }
    }
  },
  "inspection": {
    "capacity": {
      "tier": "正常",
      "max_active_tasks": 5,
      "created": 0,
      "active": 0,
      "occupied": 0,
      "free": 5,
      "by_route": {},
      "tiers": {
        "小朝廷": 3,
        "正常": 5,
        "强监察": 8
      }
    },
    "candidates_total": 2176,
    "candidates_by_route": {
      "京畿路": {
        "waiting": 282,
        "sinecure": 0,
        "on_post": 1835,
        "candidates": 282
      },
      "京西路": {
        "waiting": 78,
        "sinecure": 0,
        "on_post": 1280,
        "candidates": 78
      },
      "京东东路": {
        "waiting": 101,
        "sinecure": 0,
        "on_post": 1333,
        "candidates": 101
      },
      "京东西路": {
        "waiting": 44,
        "sinecure": 0,
        "on_post": 1164,
        "candidates": 44
      },
      "河北路": {
        "waiting": 302,
        "sinecure": 0,
        "on_post": 1963,
        "candidates": 302
      },
      "河东路": {
        "waiting": 201,
        "sinecure": 0,
        "on_post": 1309,
        "candidates": 201
      },
      "陕西路": {
        "waiting": 262,
        "sinecure": 0,
        "on_post": 1702,
        "candidates": 262
      },
      "两浙路": {
        "waiting": 0,
        "sinecure": 0,
        "on_post": 3457,
        "candidates": 0
      },
      "江南东路": {
        "waiting": 0,
        "sinecure": 0,
        "on_post": 2444,
        "candidates": 0
      },
      "江南西路": {
        "waiting": 0,
        "sinecure": 0,
        "on_post": 2614,
        "candidates": 0
      },
      "淮南东路": {
        "waiting": 62,
        "sinecure": 0,
        "on_post": 1146,
        "candidates": 62
      },
      "淮南西路": {
        "waiting": 81,
        "sinecure": 0,
        "on_post": 1052,
        "candidates": 81
      },
      "荆湖北路": {
        "waiting": 171,
        "sinecure": 0,
        "on_post": 1112,
        "candidates": 171
      },
      "荆湖南路": {
        "waiting": 191,
        "sinecure": 0,
        "on_post": 1243,
        "candidates": 191
      },
      "福建路": {
        "waiting": 0,
        "sinecure": 0,
        "on_post": 2024,
        "candidates": 0
      },
      "成都府路": {
        "waiting": 0,
        "sinecure": 0,
        "on_post": 1685,
        "candidates": 0
      },
      "利州路": {
        "waiting": 84,
        "sinecure": 0,
        "on_post": 550,
        "candidates": 84
      },
      "夔州路": {
        "waiting": 74,
        "sinecure": 0,
        "on_post": 485,
        "candidates": 74
      },
      "广南东路": {
        "waiting": 153,
        "sinecure": 0,
        "on_post": 1127,
        "candidates": 153
      },
      "广南西路": {
        "waiting": 90,
        "sinecure": 0,
        "on_post": 589,
        "candidates": 90
      }
    },
    "status_counts": {
      "created": 0,
      "active": 0,
      "completed": 0,
      "expired": 0
    },
    "identity": {
      "era": "宋",
      "term": "察访",
      "dispatch": "差遣",
      "agency": "御史台・监司（转运使／提点刑狱／提举常平）",
      "actors": [
        "察访官",
        "监司官",
        "御史",
        "勾当公事官"
      ],
      "task_office": {
        "查粮": "转运司・提举常平（仓司）",
        "查赋": "转运司",
        "查吏治": "御史台・提点刑狱",
        "查民情": "御史察访・监司",
        "查刑狱": "提点刑狱（提刑司）"
      },
      "era_requested": "宋",
      "note": "本朝（宋）用语以 term／dispatch／agency／actors 为准：中央监察在御史台、地方按察在监司、出使以**差遣**；技术层接口名保持 `inspection_*`，以便跨朝代（明／清）复用同一套接口。"
    },
    "suspicion_pending": [],
    "tasks": []
  },
  "inspection_feedback": {
    "observables": {
      "exposure": 0.0,
      "local_caution": 0.0,
      "official_pressure": 0.0,
      "rumor_change": 0.0
    },
    "events": 0,
    "by_route": {},
    "recent": [],
    "context": {
      "grip_by_route": {
        "京畿路": 0.166,
        "京西路": 0.166,
        "京东东路": 0.166,
        "京东西路": 0.166,
        "河北路": 0.166,
        "河东路": 0.166,
        "陕西路": 0.166,
        "两浙路": 0.166,
        "江南东路": 0.166,
        "江南西路": 0.166,
        "淮南东路": 0.166,
        "淮南西路": 0.166,
        "荆湖北路": 0.166,
        "荆湖南路": 0.166,
        "福建路": 0.166,
        "成都府路": 0.166,
        "利州路": 0.166,
        "夔州路": 0.166,
        "广南东路": 0.166,
        "广南西路": 0.166
      },
      "rumor_tier": {
        "tier": 1,
        "label": "钱粮迟滞",
        "signals": {
          "routes_tier_ge1": 8,
          "routes_tier_ge2": 0,
          "routes_tier_ge3": 0,
          "routes_tier_ge4": 0
        },
        "by_route": {
          "京畿路": {
            "tier": 1,
            "label": "钱粮迟滞",
            "signals": {
              "months": 0.0,
              "pressure": 3.51,
              "grip": 0.1662,
              "grain_price": 2.1375,
              "unrest": 0.0
            }
          },
          "京西路": {
            "tier": 1,
            "label": "钱粮迟滞",
            "signals": {
              "months": 0.0,
              "pressure": 3.53,
              "grip": 0.1662,
              "grain_price": 2.0649,
              "unrest": 10.81
            }
          },
          "京东东路": {
            "tier": 1,
            "label": "钱粮迟滞",
            "signals": {
              "months": 0.0,
              "pressure": 3.55,
              "grip": 0.1662,
              "grain_price": 2.3131,
              "unrest": 15.0
            }
          },
          "京东西路": {
            "tier": 1,
            "label": "钱粮迟滞",
            "signals": {
              "months": 0.0,
              "pressure": 3.57,
              "grip": 0.1662,
              "grain_price": 2.2358,
              "unrest": 15.0
            }
          },
          "河北路": {
            "tier": 1,
            "label": "钱粮迟滞",
            "signals": {
              "months": 0.0,
              "pressure": 3.55,
              "grip": 0.1662,
              "grain_price": 2.0655,
              "unrest": 11.74
            }
          },
          "河东路": {
            "tier": 1,
            "label": "钱粮迟滞",
            "signals": {
              "months": 0.0,
              "pressure": 3.56,
              "grip": 0.1662,
              "grain_price": 2.1324,
              "unrest": 15.66
            }
          },
          "陕西路": {
            "tier": 1,
            "label": "钱粮迟滞",
            "signals": {
              "months": 0.0,
              "pressure": 3.98,
              "grip": 0.1662,
              "grain_price": 1.9875,
              "unrest": 0.0
            }
          },
          "两浙路": {
            "tier": 0,
            "label": "无异常",
            "signals": {
              "months": 0.0,
              "pressure": 3.43,
              "grip": 0.1662,
              "grain_price": 1.1226,
              "unrest": 0.0
            }
          },
          "江南东路": {
            "tier": 0,
            "label": "无异常",
            "signals": {
              "months": 0.0,
              "pressure": 3.45,
              "grip": 0.1662,
              "grain_price": 1.0628,
              "unrest": 3.86
            }
          },
          "江南西路": {
            "tier": 0,
            "label": "无异常",
            "signals": {
              "months": 0.0,
              "pressure": 3.46,
              "grip": 0.1662,
              "grain_price": 1.0695,
              "unrest": 3.85
            }
          },
          "淮南东路": {
            "tier": 0,
            "label": "无异常",
            "signals": {
              "months": 0.0,
              "pressure": 3.59,
              "grip": 0.1662,
              "grain_price": 0.9861,
              "unrest": 15.0
            }
          },
          "淮南西路": {
            "tier": 0,
            "label": "无异常",
            "signals": {
              "months": 0.0,
              "pressure": 3.6,
              "grip": 0.1662,
              "grain_price": 1.1505,
              "unrest": 15.0
            }
          },
          "荆湖北路": {
            "tier": 0,
            "label": "无异常",
            "signals": {
              "months": 0.0,
              "pressure": 3.56,
              "grip": 0.1662,
              "grain_price": 0.9079,
              "unrest": 15.0
            }
          },
          "荆湖南路": {
            "tier": 0,
            "label": "无异常",
            "signals": {
              "months": 0.0,
              "pressure": 3.53,
              "grip": 0.1662,
              "grain_price": 1.0041,
              "unrest": 10.69
            }
          },
          "福建路": {
            "tier": 0,
            "label": "无异常",
            "signals": {
              "months": 0.0,
              "pressure": 3.56,
              "grip": 0.1662,
              "grain_price": 1.3047,
              "unrest": 10.74
            }
          },
          "成都府路": {
            "tier": 0,
            "label": "无异常",
            "signals": {
              "months": 0.0,
              "pressure": 3.59,
              "grip": 0.1662,
              "grain_price": 1.0926,
              "unrest": 9.57
            }
          },
          "利州路": {
            "tier": 0,
            "label": "无异常",
            "signals": {
              "months": 0.0,
              "pressure": 3.54,
              "grip": 0.1662,
              "grain_price": 1.5892,
              "unrest": 24.0
            }
          },
          "夔州路": {
            "tier": 1,
            "label": "钱粮迟滞",
            "signals": {
              "months": 0.0,
              "pressure": 3.59,
              "grip": 0.1662,
              "grain_price": 1.6073,
              "unrest": 15.0
            }
          },
          "广南东路": {
            "tier": 0,
            "label": "无异常",
            "signals": {
              "months": 0.0,
              "pressure": 3.53,
              "grip": 0.1662,
              "grain_price": 1.2768,
              "unrest": 10.69
            }
          },
          "广南西路": {
            "tier": 0,
            "label": "无异常",
            "signals": {
              "months": 0.0,
              "pressure": 3.59,
              "grip": 0.1662,
              "grain_price": 1.2376,
              "unrest": 24.0
            }
          }
        }
      },
      "backlash": {
        "actions": 0,
        "grievance_added": 0.0,
        "unrest_added": 0.0,
        "by_route": {
          "京畿路": {
            "grievance": 12.054,
            "unrest": 0.0
          },
          "京西路": {
            "grievance": 14.219,
            "unrest": 10.81
          },
          "京东东路": {
            "grievance": 14.292,
            "unrest": 15.0
          },
          "京东西路": {
            "grievance": 13.997,
            "unrest": 15.0
          },
          "河北路": {
            "grievance": 15.408,
            "unrest": 11.74
          },
          "河东路": {
            "grievance": 15.41,
            "unrest": 15.66
          },
          "陕西路": {
            "grievance": 16.843,
            "unrest": 0.0
          },
          "两浙路": {
            "grievance": 12.053,
            "unrest": 0.0
          },
          "江南东路": {
            "grievance": 12.054,
            "unrest": 3.86
          },
          "江南西路": {
            "grievance": 12.054,
            "unrest": 3.85
          },
          "淮南东路": {
            "grievance": 12.054,
            "unrest": 15.0
          },
          "淮南西路": {
            "grievance": 12.584,
            "unrest": 15.0
          },
          "荆湖北路": {
            "grievance": 12.628,
            "unrest": 15.0
          },
          "荆湖南路": {
            "grievance": 13.072,
            "unrest": 10.69
          },
          "福建路": {
            "grievance": 13.344,
            "unrest": 10.74
          },
          "成都府路": {
            "grievance": 13.539,
            "unrest": 9.57
          },
          "利州路": {
            "grievance": 14.129,
            "unrest": 24.0
          },
          "夔州路": {
            "grievance": 13.774,
            "unrest": 15.0
          },
          "广南东路": {
            "grievance": 12.816,
            "unrest": 10.69
          },
          "广南西路": {
            "grievance": 13.663,
            "unrest": 24.0
          }
        }
      }
    },
    "interpretation": "record-only",
    "note": "累计**反馈观察量**（非即时身份压力）：只记录监察行为造成的环境反馈，不判断查出与否、不产生证据/案卷、不写财政/POP/吏治状态。"
  },
  "land_tax": {
    "assessed": 8986404,
    "collected": 6591187,
    "central": 4874028,
    "local": 1588974,
    "diverted": 128185
  },
  "tax_loss": {
    "report": {
      "运输损耗": 32044,
      "地方耗费": 12816,
      "火耗": 76919,
      "杂费": 6406,
      "total": 128185
    },
    "total": 128185,
    "share": 0.0143,
    "status": "正常"
  },
  "discovery": {
    "level": 0,
    "anomalies": [],
    "suspicions": [],
    "evidence": [],
    "truths": []
  },
  "monthly_in": 3570340.0416666665,
  "expenditure": 880000,
  "army_cash": 1124462.25,
  "official_cash": 931825.6079999999,
  "clerk_cash": 481568.08653592004,
  "corruption_ded": 50836.16959999999,
  "cash_out": 1000000,
  "sui_gong": 0,
  "payraise_disbursed": 0,
  "payraise_pool": 0,
  "total_out": 3468691,
  "net": 101649.04166666651,
  "imperial_treasury": 3976917,
  "wine_coin": 600000,
  "granary": 18920474,
  "granary_cap": 20000000,
  "rate": 0.06,
  "shortage_desc": "钱荒渐显",
  "tax_rate_desc": "工商薄征（不足一成）",
  "price_trend": "米价平，市侩安和"
};
