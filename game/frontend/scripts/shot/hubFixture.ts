// 截图台 hub fixture（**仅 dev 用**）——由**真实后端**产出，非手写：
//   `python` 跑 `readout_hub.collect(commands.new_game())`（seed=20261013，先跑 6 个月结算）
//   ⇒ 导出 `GET /api/readouts::hub` 的**真实 payload**（21 项读数，ok=20/undefined=1）。
//   ⚠️ 重新生成：见本目录 README「hub fixture 再生成」；**不要手改数字**（口径单点）。
//   生成日期：2026-10-14（M266）

export const HUB = {
  "schema_version": 1,
  "readouts": {
    "money_total": {
      "label": "货币总量（M_ALL）",
      "unit": "贯",
      "value": 337809725.0,
      "display": "337809725.0",
      "source": "core.foundation.ledger.money:m_all",
      "drill_down": {
        "note": "core.foundation.ledger.money.m_all(state)",
        "source": "core.foundation.ledger.money:m_all"
      },
      "reason": null
    },
    "money_residual": {
      "label": "货币恒等式残差（M_ALL − Σ账户）",
      "unit": "贯",
      "value": 0.0,
      "display": "0.0",
      "source": "core.domains.economy.stock_identity:money_identity",
      "drill_down": {
        "note": "core.domains.economy.stock_identity.money_identity(state)['residual']",
        "source": "core.domains.economy.stock_identity:money_identity"
      },
      "reason": null
    },
    "stock_dims": {
      "label": "库存可读维数",
      "unit": "维",
      "value": 20,
      "display": "20",
      "source": "core.domains.economy.stock_identity:stock_snapshot",
      "drill_down": {
        "note": "core.domains.economy.stock_identity.stock_snapshot(state)['dims']",
        "source": "core.domains.economy.stock_identity:stock_snapshot"
      },
      "reason": null
    },
    "flow_dim_count": {
      "label": "流量账已登记维数（全月桶）",
      "unit": "维",
      "value": 10,
      "display": "10",
      "source": "core.domains.economy.stock_flow:coverage",
      "drill_down": {
        "note": "core.domains.economy.stock_flow.coverage(state, all_months=True)",
        "source": "core.domains.economy.stock_flow:coverage"
      },
      "reason": null
    },
    "seat_goods_consistent": {
      "label": "州府商品真账↔镜像一致",
      "unit": "是/否",
      "value": true,
      "display": "True",
      "source": "core.domains.economy.seat_goods_readout:seat_consistency",
      "drill_down": {
        "note": "core.domains.economy.seat_goods_readout.seat_consistency(state)",
        "source": "core.domains.economy.seat_goods_readout:seat_consistency"
      },
      "reason": null
    },
    "workshop_undefined": {
      "label": "工坊资金未定义数（无货主）",
      "unit": "座",
      "value": 0,
      "display": "0",
      "source": "core.domains.economy.workshop_fund_shadow:survey_workshop_fund_shadow",
      "drill_down": {
        "note": "core.domains.economy.workshop_fund_shadow.survey_workshop_fund_shadow(state)",
        "source": "core.domains.economy.workshop_fund_shadow:survey_workshop_fund_shadow"
      },
      "reason": null
    },
    "livelihood_computable": {
      "label": "家计可计算 POP 行数",
      "unit": "行",
      "value": 0,
      "display": "0",
      "source": "core.domains.economy.livelihood_shadow:survey_livelihood_shadow",
      "drill_down": {
        "note": "core.domains.economy.livelihood_shadow.survey_livelihood_shadow(state)",
        "source": "core.domains.economy.livelihood_shadow:survey_livelihood_shadow"
      },
      "reason": null
    },
    "seat_market_pairs": {
      "label": "有货的（治所×商品）对数",
      "unit": "对",
      "value": 285,
      "display": "285",
      "source": "core.domains.economy.seat_market_shadow:survey_seat_market_shadow",
      "drill_down": {
        "note": "core.domains.economy.seat_market_shadow.survey_seat_market_shadow(state)",
        "source": "core.domains.economy.seat_market_shadow:survey_seat_market_shadow"
      },
      "reason": null
    },
    "labor_tight_routes": {
      "label": "缺工路数（岗位闸门乘数<1）",
      "unit": "路",
      "value": 0,
      "display": "0",
      "source": "core.domains.economy.wage_gate_readout:survey_wage_gate",
      "drill_down": {
        "note": "core.domains.economy.wage_gate_readout.survey_wage_gate(state)['routes_labor_tight']",
        "source": "core.domains.economy.wage_gate_readout:survey_wage_gate"
      },
      "reason": null
    },
    "pilot_chain_gap": {
      "label": "P1 试点链条缺口（绸）",
      "unit": "匹",
      "value": 4545108,
      "display": "4545108",
      "source": "core.domains.economy.p1_pilot_chain:survey_pilot_chain",
      "drill_down": {
        "成品": 11071,
        "需求": 4556179,
        "作坊数": 28,
        "样本路": "两浙路",
        "drill": "core.domains.economy.p1_pilot_chain:survey_pilot_chain"
      },
      "reason": null
    },
    "jobs_capacity": {
      "label": "岗位容量合计（建筑岗位）",
      "unit": "岗",
      "value": null,
      "display": "undefined",
      "source": "core.domains.economy.jobs_readout:survey_jobs",
      "drill_down": {
        "实到（建筑岗位）": 0,
        "有实到读数的路": 20,
        "drill": "core.domains.economy.jobs_readout:survey_jobs",
        "note": "容量与**实到**均**只读可算**（口径见 `seat_jobs`）；⚠️ 开局各路的 buildings 只有水利/常平仓（**非岗位建筑**）⇒ 实到为 **0**（真值：无岗可上），但**非岗位建筑上的人不得被默认补进来**"
      },
      "reason": "无岗位建筑（开局 buildings 只有 水利/常平仓）⇒ 容量不可定义（不填 0）"
    },
    "pilot_bottleneck": {
      "label": "P1 试点主瓶颈（绸）",
      "unit": "类",
      "value": "capacity_shortage",
      "display": "capacity_shortage",
      "source": "core.domains.economy.p1_pilot_chain:survey_diagnosis",
      "drill_down": {
        "分布": {
          "capacity_shortage": 17
        },
        "路数": 17,
        "样本": {
          "路": "两浙路",
          "verdict": "capacity_shortage",
          "覆盖": 0.004002
        },
        "drill": "core.domains.economy.p1_pilot_chain:survey_diagnosis"
      },
      "reason": null
    },
    "p2_readiness": {
      "label": "P2 字段已就绪数（共 14 项）",
      "unit": "项",
      "value": 8,
      "display": "8",
      "source": "core.domains.economy.entity_projection:survey_entity_projection",
      "drill_down": {
        "已就绪字段": [
          "blueprint",
          "income_to",
          "level",
          "maintenance",
          "operation_mode",
          "operator",
          "owner",
          "seat"
        ],
        "逐字段率": {
          "blueprint": 1.0,
          "seat": 1.0,
          "level": 1.0,
          "completed_month": 0.0,
          "owner": 1.0,
          "operator": 1.0,
          "maintenance": 1.0,
          "operation_mode": 1.0,
          "methods": 0.0,
          "jobs_capacity": 0.0,
          "jobs_filled": 0.0,
          "recipe": 0.0,
          "io_stock": 0.0,
          "income_to": 1.0
        },
        "建筑数": null,
        "未就绪样本原因": {
          "field": "completed_month",
          "route": "京畿路",
          "seat": "京畿路|开封府",
          "building": "水利",
          "reason": "该建筑以**标量**登记（岗位类写法）或为开局建筑（无 built_month）⇒ 无建成月（缺失≠0，**不臆造**）"
        },
        "drill": "core.domains.economy.entity_projection:survey_entity_projection"
      },
      "reason": null
    },
    "building_owned": {
      "label": "建筑归属已登记率",
      "unit": "比",
      "value": 1.0,
      "display": "1.0",
      "source": "core.domains.economy.building_owner:survey_building_owners",
      "drill_down": {
        "total": 40,
        "with_owner": 40,
        "missing": 0,
        "undefined_rule": 0,
        "已登记率": 1.0,
        "drill": "core.domains.economy.building_owner:survey_building_owners"
      },
      "reason": null
    },
    "workshop_readiness": {
      "label": "作坊（经营记录）字段已就绪数（共 14 项）",
      "unit": "项",
      "value": 8,
      "display": "8",
      "source": "core.domains.economy.entity_projection:survey_workshop_projection",
      "drill_down": {
        "已就绪字段": [
          "income_to",
          "maintenance",
          "methods",
          "operation_mode",
          "operator",
          "owner",
          "recipe",
          "seat"
        ],
        "逐字段率": {
          "blueprint": 0.0,
          "seat": 1.0,
          "level": 0.0,
          "completed_month": 0.0,
          "owner": 1.0,
          "operator": 1.0,
          "maintenance": 1.0,
          "operation_mode": 1.0,
          "methods": 1.0,
          "jobs_capacity": 0.0,
          "jobs_filled": 0.0,
          "recipe": 1.0,
          "io_stock": 0.0,
          "income_to": 1.0
        },
        "作坊数": 128,
        "drill": "core.domains.economy.entity_projection:survey_workshop_projection"
      },
      "reason": null
    },
    "p2_gaps": {
      "label": "P2 未就绪原因条数（去重）",
      "unit": "条",
      "value": 12,
      "display": "12",
      "source": "core.domains.economy.entity_projection（建筑+作坊）",
      "drill_down": {
        "原因数": 12,
        "已扫描实体": 96,
        "采样上限": 48,
        "扫描路数": 20,
        "逐原因": {
          "该建筑以**标量**登记（岗位类写法）或为开局建筑（无 built_month）⇒ 无建成月（缺失≠0，**不臆造**）": {
            "fields": [
              "completed_month"
            ],
            "count": 40
          },
          "无可选生产方法字段": {
            "fields": [
              "methods"
            ],
            "count": 40
          },
          "该建筑非岗位建筑（`JOBS_PER_LEVEL` 未登记）": {
            "fields": [
              "jobs_capacity"
            ],
            "count": 40
          },
          "实到不可算（该建筑非岗位建筑或无池）": {
            "fields": [
              "jobs_filled"
            ],
            "count": 40
          },
          "建筑无配方（配方在**作坊**上）": {
            "fields": [
              "recipe"
            ],
            "count": 40
          },
          "库存**不在建筑上**：货由 POP 持有（治所级）或入 `resources`/工匠 `goods` 池 ⇒ 本字段不": {
            "fields": [
              "io_stock"
            ],
            "count": 40
          },
          "无「蓝图版本」字段（作坊只有名称/配方/产出）": {
            "fields": [
              "blueprint"
            ],
            "count": 56
          },
          "作坊无等级字段（等级在建筑上）": {
            "fields": [
              "level"
            ],
            "count": 56
          },
          "无完工月字段": {
            "fields": [
              "completed_month"
            ],
            "count": 56
          },
          "作坊**不在 `JOBS_PER_LEVEL`**（M67：作坊岗位数无权威来源）": {
            "fields": [
              "jobs_capacity"
            ],
            "count": 56
          },
          "同上（M67）——**不按人口均分、不默认满员**": {
            "fields": [
              "jobs_filled"
            ],
            "count": 56
          },
          "作坊的投入/产出**不单独分栏**：原料/成品由 POP 持有（治所级 `goods`）或入 `resources`/工": {
            "fields": [
              "io_stock"
            ],
            "count": 56
          }
        },
        "drill": "core.domains.economy.entity_projection（建筑+作坊逐项投影）"
      },
      "reason": null
    },
    "d_funding_best": {
      "label": "营运资金最佳候选到位率（D 线影子）",
      "unit": "比",
      "value": 1.0,
      "display": "1.0",
      "source": "core.domains.economy.owner_candidates_shadow:survey_owner_candidates",
      "drill_down": {
        "最佳候选": "本路士绅",
        "逐候选到位率": {
          "本路士绅": 1.0,
          "路级官府（地方府库）": 0.3004,
          "内帑": 0.0565,
          "本路商人": 0.0541,
          "国库（中央）": 0.0012
        },
        "逐候选工资到位率": {
          "本路士绅": null,
          "路级官府（地方府库）": null,
          "内帑": null,
          "本路商人": null,
          "国库（中央）": null
        },
        "逐候选资金池": {
          "本路士绅": 196556711,
          "路级官府（地方府库）": 21151466,
          "内帑": 3976917,
          "本路商人": 3807811,
          "国库（中央）": 81936
        },
        "采购需求": {
          "value": 70400000,
          "unreadable": [],
          "unreadable_count": 0,
          "reason": null
        },
        "工资需求": {
          "value": null,
          "reason": "作坊维度无工资单点：`JOBS_PER_LEVEL` 只登记建筑（农田/庄园/工坊/商铺…），`WAGE_RATE` 只登记 牧场/工坊/矿场 ⇒ 作坊工资义务不可定义；**不拿建筑口径硬套**（缺失≠0）",
          "source": "core.building_jobs.song_job_cfg"
        },
        "drill": "core.domains.economy.owner_candidates_shadow:survey_owner_candidates"
      },
      "reason": null
    },
    "trade_line_status": {
      "label": "外贸素材就绪项数（主线 F）",
      "unit": "项",
      "value": 4,
      "display": "4",
      "source": "core.domains.economy.trade_shadow（纯函数影子）",
      "drill_down": {
        "REGIME_IMPORTS": 6,
        "SEA_TRADERS": 2,
        "ABSTRACT_TRADERS": 2,
        "ROUTE_WATERWAY": 3,
        "纯函数可算": {
          "land_freight": true,
          "sea_freight": true,
          "tax_split": true,
          "condition_mult": true
        },
        "真账_笔数": 0,
        "真账_来源": "`state.trade_journal` 为空 ⇒ 市舶未开（`state.maritime['open']`）或本局未产生外贸 ⇒ **不臆造外贸账**（缺失≠0）",
        "真账现状": "**逐笔真账已接线**（M176 容器 / M177 纯函数 / M179 接线）：可回答「哪一路、哪一货、跟谁、多少」；旧描述『无逐笔容器』**已作废**",
        "drill": "core.domains.economy.trade_shadow（**纯函数影子，未接结算**）"
      },
      "reason": null
    },
    "fiscal_structure": {
      "label": "财政结构：内帑/国库比",
      "unit": "倍",
      "value": 48.5369,
      "display": "48.5369",
      "source": "state.treasury / state.imperial_treasury",
      "drill_down": {
        "国库": 81936,
        "内帑": 3976917,
        "drill": "state.treasury / state.imperial_treasury（既有单点，无旁路）",
        "内帑/国库": 48.5369,
        "注": "结构性事实（M147 实测）：内帑 0/6/12 月 = 1.0M/3.85M/5.93M（**持续增长**），国库 = 5.0M/8.2万/12.4万（**长期低位**）⇒ 钱在沉淀进内帑"
      },
      "reason": null
    },
    "tax_scope_contrast": {
      "label": "税收口径差额（全口径 − tax_breakdown 4 目）",
      "unit": "贯",
      "value": 9834320.67,
      "display": "9834320.67",
      "source": "state.tax_breakdown + state.tax_base_summary()",
      "drill_down": {
        "tax_breakdown_4目": {
          "commerce": 1116720,
          "poll": 390470,
          "maritime": 0,
          "official_service": 70660
        },
        "tax_breakdown_合计": 1577850.0,
        "drill": "state.tax_breakdown + state.tax_base_summary()（既有读口）",
        "额外科目（已可读）": {
          "calc_salt_coin（月盐课）": 847916.67,
          "land_tax_assessed（二税折色·应征）": 8986404.0
        },
        "额外科目（仍缺读口）": null,
        "partial": false,
        "全税收口径合计（可读部分）": 11412170.67,
        "警示": "**两套口径不可混用**：`tax_breakdown` 仅 4 目；任何「税收占比/到账率」结论必须注明用哪套（M151 取证；历史误判见 `game_state_econ` 注释）。另：**二税折色有地方分成**（`statistics.land_tax_local` 留州），而 4 目**无**（M156 更正 M149/M150）",
        "二税折色·三率三分": {
          "land_tax_assessed": 8986404,
          "land_tax_collected": 6591187,
          "land_tax_central": 4874028,
          "land_tax_local": 1588974,
          "land_tax_diverted": 128185,
          "land_tax_required": 1321809
        },
        "归属落点": {
          "上供 → 中央": 4874028,
          "留州 → **地方**（地方确有分成）": 1588974,
          "侵渔 → 吏（账实落差）": 128185
        }
      },
      "reason": null
    },
    "market_chain_diagnosis": {
      "label": "市场切片·链级诊断可读环数（产地→运输→成交→到货→加工）",
      "unit": "环",
      "value": 4,
      "display": "4",
      "source": "core.domains.economy.stock_identity（stock_snapshot 等）",
      "drill_down": {
        "drill": "core.domains.economy.stock_identity（stock_snapshot / in_transit_by_dim / pending_stock_by_dim / pop_goods_by_dim / residual_report）",
        "产地（丝存量）": 10866021.0,
        "运输（绸在途）": 0,
        "到货（绸待入库）": 0,
        "到货（绸成品存量）": 11071.0,
        "成交环": "见 `seat_market_shadow.seat_supply/seat_purchasing_power`（本读数不重算）",
        "加工环": "见 `readout_hub.pilot_chain_gap`（成品/需求/缺口）",
        "odometer_readable": true,
        "端到端残差方法": "跨月两次 `stock_snapshot(state)` 得 prev/curr ⇒ `stock_identity.residual_report(prev, curr)` 给**逐维残差**；本读数**单时点** ⇒ **不假造残差**（缺失≠0）",
        "快照": {
          "schema_version": 1,
          "by_custody": {
            "pop_goods": {
              "丝": 10866021.0,
              "麻": 8566935.0,
              "果": 7801462.0,
              "绸": 11071.0,
              "meat": 402373.0,
              "布": 0.0,
              "蔗": 6836793.0
            },
            "national_resources": {
              "盐": 3000000.0,
              "茶": 3000000.0,
              "丝": 0.0,
              "麻": 3.0,
              "蔗": 0.0,
              "果": 0.0,
              "木": 3000000.0,
              "石": 3000000.0,
              "铁": 3000000.0,
              "金": 0.0,
              "铜": 0.0,
              "银": 0.0,
              "牲畜": 0.0,
              "马": 0.0,
              "药材": 0.0,
              "绸": 15064.0,
              "布": 20.0,
              "纸": 0.0,
              "糖": 0.0,
              "meat": 480000.0
            },
            "in_transit": {},
            "pending_stock": {}
          },
          "dims": [
            "meat",
            "丝",
            "布",
            "木",
            "果",
            "牲畜",
            "盐",
            "石",
            "糖",
            "纸",
            "绸",
            "茶",
            "药材",
            "蔗",
            "金",
            "铁",
            "铜",
            "银",
            "马",
            "麻"
          ],
          "totals": {
            "meat": 882373.0,
            "丝": 10866021.0,
            "布": 20.0,
            "木": 3000000.0,
            "果": 7801462.0,
            "牲畜": 0.0,
            "盐": 3000000.0,
            "石": 3000000.0,
            "糖": 0.0,
            "纸": 0.0,
            "绸": 26135.0,
            "茶": 3000000.0,
            "药材": 0.0,
            "蔗": 6836793.0,
            "金": 0.0,
            "铁": 3000000.0,
            "铜": 0.0,
            "银": 0.0,
            "马": 0.0,
            "麻": 8566938.0
          },
          "all_readable": true,
          "warnings": [],
          "note": "totals 只含 民间POP + 全国仓 + 在途；**不含**归属待定（裁定 6.33：不并入 resources）"
        },
        "快照警告": null,
        "快照合计": {
          "meat": 882373.0,
          "丝": 10866021.0,
          "布": 20.0,
          "木": 3000000.0,
          "果": 7801462.0,
          "牲畜": 0.0,
          "盐": 3000000.0,
          "石": 3000000.0,
          "糖": 0.0,
          "纸": 0.0,
          "绸": 26135.0,
          "茶": 3000000.0,
          "药材": 0.0,
          "蔗": 6836793.0,
          "金": 0.0,
          "铁": 3000000.0,
          "铜": 0.0,
          "银": 0.0,
          "马": 0.0,
          "麻": 8566938.0
        },
        "可读环数": 4,
        "缺失环": []
      },
      "reason": null
    }
  },
  "ok_count": 20,
  "undefined_count": 1,
  "frontend_wired": false,
  "note": "只读索引；**前端面板未接**（本批只做后端）；缺失一律 undefined，不显示 0"
};
