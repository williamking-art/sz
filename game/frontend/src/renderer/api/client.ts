// 类型化 /api/* HTTP 客户端 —— 对齐 game/backend/server.py 契约
// 后端零改动，前端只消费 HTTP。

export interface GameState {
  [key: string]: unknown;
}

export interface AdvanceResult {
  events: unknown[];
  log: string[];
  report: string;
  state: GameState;
}

export interface ActionResult {
  message: string;
  state: GameState;
}

export interface ResolveResult {
  message: string;
  state: GameState;
}

export interface SaveSlotsResult {
  slots: unknown[];
}

export interface ConcludeResult {
  eval: unknown;
  ai_eval: unknown;
}

/** /api/council_review：三省会签推演（票拟批红用） */
export interface CouncilReviewResult {
  review: {
    memo: string;
    objections: string;
    executions: string;
    verdict: string;
    revised_effects?: unknown[];
  };
  cached: boolean;
}

/** /api/readouts：只读派生读数（军政/会计/仓廪面板用） */
export interface ArmyUnitReadout {
  unit_id: string;
  name: string;
  tier: string;
  branches: Record<string, unknown>;
  troops: number;
  station: string;
  defense_line: string;
  morale: number;
  training: number;
  equip_rate: number;
  /** 装备实物明细（7 项：枪刀/弓弩/火器/战马/盔甲/舟船/器械）— 阶段 B-3 新增 */
  equip?: Record<string, number>;
  /** 该军**累计欠饷**（贯）— 阶段 B-3 新增；国库不足时按月分摊累加 */
  arrears?: number;
  /**
   * 该军**应发月饷**（贯/月）。来源 core/region_brief.unit_cost_readout：
   * 与 calc_army_cash 用同一张 branch_std 权威表，只是按军取明细。
   * 读不到 → 缺省（前端显示「未定义」，**不回落 0**）。
   */
  monthly_pay?: number | null;
  /** 该军**月粮消耗**（石/月）。来源同上，与 calc_army_grain 同源。 */
  monthly_grain?: number | null;
  army_name: string;
  org_arm: string;
  scale: string;
  serial: string;
}

/**
 * 计划/工程读数（core/plan_readout.py 的镜像；字段与后端一一对应）。
 * 四层级**分开**列出：accepted 旨意受理 / advancing 执行推进 /
 * completed 工程告成 / effective 效果生效。
 */
export interface PlanReadout {
  phases: {
    accepted: PlanPhaseItem[];
    advancing: PlanPhaseItem[];
    completed: PlanPhaseItem[];
    effective: PlanPhaseItem[];
  };
  /** 层级标签（由后端单点下发，前端**不得**自造文案） */
  phase_labels: Record<string, string>;
  projects: {
    pid: string;
    name: string;
    route: string;
    status: string;
    status_label: string;
    progress: number;
    capacity: number;
    dynamic: boolean;
    output: Record<string, number>;
    runtime: Record<string, number>;
    effects: { op: string; params: Record<string, number> }[];
    source_blueprint: string;
  }[];
  /** 议毕但无程序侧落点的事务（**不得**展示为"已告成"） */
  unsupported_tasks: { name?: string; turn?: number; reason?: string }[];
  counts: Record<string, number>;
}

export interface PlanPhaseItem {
  kind: string;
  title: string;
  pid?: string;
  route?: string;
  progress?: number;
  outcome?: string | null;
  note?: string;
}

export interface ReadoutsResult {
  army: ArmyUnitReadout[];
  arsenal: Record<string, unknown>;
  finance: Record<string, unknown>;
  /** 统一读数索引（M83；后端 `core/domains/economy/readout_hub.collect`）——
   *  **12 项**只读读数（含 P1 试点链条缺口/主瓶颈、岗位容量）。
   *  🔴 契约：**不可读项的 `display` 恒为字符串 `"undefined"`（绝不显示 0）**；
   *  每项带 `source` 与 `drill_down`（读数**能下钻到来源**）。面板只渲染，不重算。 */
  hub?: {
    schema_version?: number;
    readouts?: Record<string, {
      label: string;
      value: unknown;
      /** 有值 ⇒ 数值字符串；不可读 ⇒ 恒为 `"undefined"` */
      display: string;
      unit: string;
      source: string;
      drill_down?: unknown;
      reason?: string | null;
    }>;
    ok_count?: number;
    undefined_count?: number;
    frontend_wired?: boolean;
    note?: string;
  };
  /** 国库/内帑收支明细（core.flow_summary.build_flow_summary） */
  flow?: {
    treasury?: {
      regular_in?: [string, number][];
      one_off?: [string, number, string][];
      month_in?: number;
      month_out?: number;
      total_in?: number;
      total_out?: number;
    };
    imperial?: {
      // 后端 core/flow_summary.py 实际只下发 regular_in / one_off / balance
      // （内帑收支不入 statistics，故无 month_in / total_in —— 原类型声明漂移，
      //  面板据此读 im.total_in 恒为 0）
      regular_in?: [string, number][];
      one_off?: [string, number, string][];
      balance?: number;
    };
  };
  granary: {
    monthly?: number;
    army?: number;
    official?: number;
    clerk?: number;
    capacity_used?: number;
  };
  /** 朝局简报可行动项（core.briefing.build_briefing_actions；goto 为跳转语义） */
  briefing?: { key: string; title: string; desc: string; goto: string; urgent?: boolean }[];
  /**
   * 计划/工程实际状态读数（core/plan_readout.build_plan_readout）。
   * 与 AI 推演**同源**——前端只渲染，**不得**自行计算状态/进度/产出。
   * `phases` 四个层级（旨意受理／执行推进／工程告成／效果生效）**必须分开展示**。
   */
  plan?: PlanReadout;
  /** 群臣档案（年龄/职衔/派系/性格一句话/生平）；迁移补齐原 Tk 大臣卡片信息密度 */
  ministers?: Record<string, {
    age?: number | null;
    role?: string;
    faction?: string;
    style?: string;
    bio?: string;
    /** 合成立绘（头部层+按品级官服层）：前端相对 URL，如 ministers/韩忠彦_zi.png */
    portrait?: string;
    /** 服色档：zi/fei/lv/qing/shi/qinwang */
    tier?: string;
  }>;
  /** 州路简报（core/region_brief.py，**只读派生**）：民生/粮储/到账月税/驻军月饷/风险分 */
  regions?: RegionBriefResult;
  /** 局势投影（core/situations.py，**只读派生**）：进度/达成条件/执行三通道/六类 POP 心气/集团⊆POP */
  situations?: SituationReadoutResult;
  defense_lines: Record<string, { fortification: number; garrison: number }>;
}

/** 诏令实际效果通道（口径单点 core/decree_effect.py）。
 *
 *  吏治 = **唯一强关联**（会签执行率本身即吏治的表达 × 吏胥折扣）；
 *  民心/文书 = 弱关联（0.85–1.0）；
 *  军队 = **条件加成，不是必须**——仅军政/边事类诏令参与（military_applies）。
 */
export interface ExecutionChannels {
  /** 唯一强关联通道（恒为 "clerks"） */
  strong: string;
  /** 吏治折扣（core/clerks.decree_execution_mult） */
  clerks_mult: number | null;
  clerks_grievance: number | null;
  clerks_grip: number | null;
  clerks_quality: string | null;
  /** 官场配合度**代理**（会签执行率的盘面近似；proxy=true 表示非执行率本体） */
  official_support: {
    proxy: boolean;
    weighted: number | null;
    min: number | null;
    min_faction: string | null;
  } | null;
  /** 民心 / 识字率（弱关联；识字率由该路各地 POP 自有值按人口加权派生） */
  civil_mult: number | null;
  literacy: number | null;
  /** 诏令类别：军政吃军队督行，民政与之无关 */
  kind: "军政" | "民政";
  military_mult: number | null;
  military_applies: boolean;
  military_route: string | null;
  military_reason: string | null;
  /** 实际效果系数（吏治 × 民事；军政类再叠军队） */
  combined_mult: number | null;
  faction_min: number | null;
  faction_min_name: string | null;
  note: string;
}

export interface SituationItem {
  id: string;
  title: string;
  source: "legacy" | "focus" | "free_effect" | "event" | "record";
  status: "active" | "resolved" | "failed" | "cancelled";
  /** 0–100；无进度来源为 null（前端显示"未定义"，不得当 0） */
  bar_value: number | null;
  /** bar=进度条；goal=只判进行/达成/失败 */
  progress_mode?: "bar" | "goal";
  resolve_condition_text: string | null;
  fail_condition_text: string | null;
  ongoing_text: string | null;
  /** 推进=什么好 / 恶化=什么坏（明末 §3.4 双向语义标签） */
  bar_good_meaning?: string | null;
  bar_bad_meaning?: string | null;
  progress_text: string | null;
  severity: number;
  phase: "起" | "中" | "终前" | null;
  region_hint: string | null;
  faction_hint: string | null;
  /** 经济维度：该路最窘/最丰阶级 */
  pop_highlights: string[] | null;
  /** 非经济维度：吏怨/军心/士绅抵抗 */
  channel_highlights: string[] | null;
  execution_channels: ExecutionChannels | null;
  timeline: { turn: number; kind: string; text: string; source: string }[];
}

/** 六类 POP 的非经济通道（含"吏"子池，单列不另设第 7 类 POP） */
export interface PopSentimentChannel {
  label: string;
  primary: string;
  secondary?: string;
  source: string;
}

export interface PopChannels {
  channels: Record<string, PopSentimentChannel>;
  nation: Record<string, Record<string, number | null | { 最低: number; 均: number }>>;
  by_route: Record<string, Record<string, number | null>>;
}

/** 利益集团 ⊆ POP 阶级（不是与 POP 并列的实体） */
export interface FactionBasisRow {
  influence: number | null;
  satisfaction: number | null;
  cohesion: number | null;
  leader: string | null;
  pop_basis: {
    pop_classes: string[];
    subset_of: string[];
    subset_kind: "national" | "pool" | "route" | "pool+route";
    pool: string | null;
    routes: string[] | null;
    desc: string;
  } | null;
  basis_readout: {
    subset_note: string;
    share: number | null;
    pop_size: number;
    parent_pop_size: number;
    pool_size: number;
    parent_total: number;
    routes: string[] | null;
    troops: number;
    morale: number | null;
    public_support_avg: number | null;
    gentry_resistance_avg: number | null;
  } | null;
  basis_errors: string[];
}

export interface FactionChannels {
  factions: Record<string, FactionBasisRow>;
  emerging: {
    reform: string;
    label: string;
    gain: { class: string; why: string; pool?: string }[];
    lose: { class: string; why: string; pool?: string }[];
    emergent: {
      name: string | null;
      desc: string | null;
      pop_basis: Record<string, unknown>;
      basis_errors: string[];
    }[];
  }[];
  declared: boolean;
  basis_errors: string[];
}

export interface SituationReadoutResult {
  items: SituationItem[];
  by_status: Record<string, number>;
  pop_channels?: PopChannels;
  faction_channels?: FactionChannels;
  readout_status?: "ok" | "partial";
  readout_errors?: string[];
}

/** 州府级营造部门实体（对齐 core/construction_shadow.py::dept_entity） */
export interface RegionDepartment {
  /** 部门 id：民间营造 / 官有营造 */
  dept_id: string;
  /** 显示名 */
  label: string;
  /** 归属：pop（民产）/ local_gov（地方公产）/ state（国家公产） */
  owner_kind: string;
  /** **劳力**（营造主力，取自「农」；缺失为 null —— **不是 0**） */
  labor?: number | null;
  /** **匠人**（工坊手工业者，取自「工匠」；缺失为 null） */
  artisans?: number | null;
  /** **劳役基**（官有营造才有；应役丁。缺失为 null） */
  corvee_base?: number | null;
  /** 是否官有部门（UI 分组用） */
  official?: boolean;
  /** 本月产出；未实现/缺失为 null（**不得显示成 0**） */
  monthly?: {
    built?: number | null;
    hired_hours?: number | null;
    corvee_days?: number | null;
    coin?: number | null;
    mood_cost?: number | null;
    /** 归属基准标注（如 labor_share） */
    attribution?: string;
  } | null;
  /** 治所坐标 */
  route?: string;
  seat?: string;
  level?: string;
  /** 口径：truth（真账）/ derived（派生） */
  mode?: string | null;
  derived?: boolean;
}

export interface RegionDepartments {
  mode: string | null;
  seats_covered: number | null;
  departments: RegionDepartment[];
}

/** 州路简报单条（对齐 core/region_brief.py::build_region_brief） */
export interface RegionRoute {
  name: string;
  display_name: string;
  controlled_by: string;
  households: number;
  population: number;
  land: number;
  /** ⚠️ 2026-09-27 起：**未清丈不下发真值**，仅 `surveyed === true` 时出现 */
  hidden_land?: number;
  /** 隐田是否已清丈（隐匿率 < 0.2）；前端回落行可不填 */
  surveyed?: boolean;
  /** 未清丈时的隐田**约值**（粗化 50 万亩，不可反推真值） */
  hidden_land_est?: number;
  /** 未清丈时的隐田档位词 */
  hidden_land_band?: string;
  /** **隐户口数约值**（粗化 5 万；未清丈时快照不含 `pops.农.hidden` 真值） */
  hidden_pop_est?: number;
  mood: number;
  govern: number;
  public_support: number;
  gentry_resistance: number;
  city_defense: number;
  unrest: number;
  /** **治安 = 100 − 动乱**（正极性：越高越好；后端单点派生） */
  security?: number;
  /** 治安档位词：太平 / 尚可 / 多事 / 不靖 */
  security_label?: string;
  fiscal: number;
  /** 识字率（该路各地 POP 自有值按人口加权派生；未初始化时 null） */
  literacy: number | null;
  grain_year: number;
  grain_stock: number;
  /** 粮储安全垫（月）；无口粮需求时为 null */
  grain_months: number | null;
  /** 本路到账后月税（贯/月，二税折色实收口径） */
  tax_month: number;
  /** 州府级**营造部门**（承 core/construction_shadow；2026-10-05）
   *  - `mode="truth"` 州府级真账 / `"derived"` 按人口权重派生；前端须显示口径
   *  - 缺失时 `mode=null`、`departments=[]`（**缺失≠0**，不得显示成「无部门」）*/
  departments?: RegionDepartments;
  /** 占全国月税比 0~1 */
  tax_share: number;
  /** 驻军月饷（贯/月） */
  army_cash_month: number;
  /** 驻军月粮（石/月） */
  army_grain_month: number;
  /** 省路级主要官员（四监司 + 路府知通，M303） */
  officials?: {
    circuit: string;
    capital: string;
    is_border: boolean;
    officials: Record<string, {
      role_key: string;
      role_name: string;
      official_title: string;
      name: string;
      faction: string;
      rank: string;
      domain: string;
      integrity: number;
      ability: number;
      traits: string[];
      term_months: number;
      effectiveness: number;
      historical?: boolean;
      vacant?: boolean;
    }>;
  };
  risk_score: number;
  risk_label: "安" | "警" | "危";
  risk_hints: string[];
}

/** 州府级底盘（对齐 core/region_brief.py::build_prefecture_brief；**Σ府 == 路级**） */
export interface RegionPrefecture {
  name: string;
  /** 行政路（CIRCUIT_INFO 键） */
  circuit: string;
  /** 游戏单位路（state.prefectures 键） */
  route: string;
  population: number;
  households: number;
  land: number;
  grain_year: number;
  tax_month: number;
  /** 占本路人口比 0~1 */
  share: number;
}

export interface RegionBriefResult {
  routes: RegionRoute[];
  /** 州府级底盘（P0，2026-09-27）；不可用时缺省 */
  prefectures?: RegionPrefecture[];
  prefecture_audit?: { routes: number; prefectures: number; violations: string[] };
  top_risk: RegionRoute[];
  nation: {
    routes: number;
    /** 宋控路数（内政预警与全国加权只统计本方，避免敌占区失真） */
    routes_mine: number;
    /** 非宋控路数 */
    routes_foreign: number;
    population: number;
    households: number;
    land: number;
    grain_stock: number;
    /** 全国税额（核心派生值，权威） */
    tax_month: number;
    /** 逐路展示值之和（诊断用，与上一项可能存在舍入差） */
    tax_month_routes_sum: number;
    army_cash_month: number;
    army_cash_routes_sum: number;
    army_grain_month: number;
    army_grain_routes_sum: number;
    /** 全国民心＝宋控路按人口加权（与 metrics 口径一致） */
    public_support_weighted: number;
    risk_counts: { 安: number; 警: number; 危: number };
  };
  /** ok=读数完整；partial=某个核心派生失败（面板应提示"读数不完整"，切勿当作 0 解读） */
  readout_status?: "ok" | "partial";
  readout_errors?: string[];
}

/** /api/meter：Token 计量表（含召对命中与合计行） */
export interface MeterRow {
  type: string;
  calls: number;
  prompt: number;
  completion: number;
  hit: number | string;
}

export interface MeterResult {
  rows: MeterRow[];
  total: { calls?: number; prompt?: number; completion?: number };
  token_log?: unknown[];
}

/** /api/memory：记忆库只读视图（玩家可见「AI 记住了什么」） */
export interface MemorySummary {
  eid: string;
  kind: string;
  period: number | null;
  name: string;
  turn: number;
  relation_count: number;
  decision_count: number;
  event_count: number;
  highlights: string[];
}

export interface MemoryRelation {
  src: string;
  dst: string;
  rtype: string;
  weight: number;
  note: string;
}

export interface MemoryDialogueSummary {
  period: number;
  minister: string;
  start_turn: number;
  end_turn: number;
  content: string;
  ref_count: number;
}

export interface MemoryChangeLogRow {
  turn: number | null;
  action: string | null;
  detail: string;
  ts: string | null;
}

/** 召对会话流单条（含两侧：speaker="朕" 为陛下之言，其余为大臣回奏） */
export interface MemoryDialogueRow {
  id: number;
  minister: string;
  turn: number;
  speaker: string;
  text: string;
  intent: string;
  stance: string;
  topic: string;
  summarized: boolean;
}

/** 会话列表一条（每个大臣）：末条预览 + 条数 + 末次回合 */
export interface MemorySession {
  minister: string;
  count: number;
  last_turn: number;
  last_text: string;
  last_speaker: string;
}

export interface MemoryResult {
  turn: number;
  state_turn: number;
  entity_counts: Record<string, number>;
  relation_total: number;
  relation_archived: number;
  summaries: MemorySummary[];
  recent: MemoryRelation[];
  dialogue_summaries: MemoryDialogueSummary[];
  change_log: MemoryChangeLogRow[];
  /** 会话视图回显（未指定 minister 时为空串） */
  minister?: string;
  /** 每个大臣的会话摘要（用于召对面板左侧会话列表） */
  sessions?: MemorySession[];
  /** 该大臣的完整会话流（仅 minister 非空时返回；含陛下之言） */
  dialogues?: MemoryDialogueRow[];
  /** 涉该大臣的近关系（仅 minister 非空时返回） */
  minister_relations?: MemoryRelation[];
}

export interface AiConfigResult {
  configured: boolean;
  /** 服务端生成的稳定 Key 指纹（sha256 前 8 位）；**不含任何 Key 片段**（审查 P2-15）。 */
  key_id: string;
  base_url: string;
  model: string;
  has_key?: boolean;
  message?: string;
  available?: boolean;
  /** 大臣办差工具（function calling）三档：auto/on/off */
  enable_tools?: string;
}

export type ActionName =
  | "issue_decree"
  | "issue_secret_decree"
  | "unlock_focus"
  | "start_focus"
  | "cancel_focus"
  | "issue_edict_from_review"
  | "reject_edict_draft"
  | "issue_free_decree"
  | "merge_drafts"
  | "do_personal_action"
  | "choose_imperial_action"
  | "audience_dialogue"
  | "envoy_diplomacy"
  | "allocate_payraise"
  | "start_tech_research"
  | "approve_invention"
  | "reject_invention"
  | "issue_military_order"
  | "approve_ai_action"
  | "reject_ai_action"
  | "issue_task_decree"
  | "issue_kouyu"
  | "propose_inner_transfer"
  | "confirm_inner_transfer"
  | "cancel_inner_transfer"
  // 2026-10-17 全审 A-3：后端分派表已有、前端类型此前漏登记的 3 个动作
  | "accept_memorial"
  | "dismiss_memorial"
  | "bestow_imperial_favor";

/**
 * 非幂等端点前缀（安全审查 C4）：这些端点的 5xx/超时重试会造成重复副作用
 * —— `/api/advance` 凭空多推演一回合、`issue_decree` 同一诏令发两道。
 * 对它们一律不自动重试，如实上报，由玩家自行决定是否再下。
 */
const NON_IDEMPOTENT_PATHS = [
  "/api/advance",
  "/api/action",
  "/api/resolve_event",
  "/api/save",
  "/api/decree/"
];

/**
 * 云托管冷启动参数（服务按需拉起、不常驻：MinNum=0）。
 *
 * **503 的来源必须区分，不能一律重放**（2026-09-23 两次核对后的结论）：
 *   - **平台网关**：实例缩容到 0 时网关直接回 503，响应体**不是 JSON**
 *     → 请求根本没到达应用 → 等待就绪后重放安全，非幂等端点亦然；
 *   - **应用自身**：`game/backend/server.py` 在 AI 拒绝式失败时回
 *     503 + `{"detail":{"error_code":...,"message":...}}`，而 `/api/advance`、
 *     `/api/action` 都在其中 → 可能已进入处理流程 → **绝不重放**（C4 要防的
 *     「副作用可能已发生」正是这一种）。
 * 故判据取「响应体是否为 JSON」，而不是「状态码是否为 503」。
 * Rust 端 `songzuo_server/src` 本身不含 503，走的也是同一条保守判据。
 * 其余 5xx 与超时仍严格不重试非幂等端点，C4 行为不变。
 *
 * 代价提示：这是「不保持常驻实例」的必然代价 —— 闲置一段时间后首次操作
 * 需等待实例唤起（实测约 1~2 分钟）。若日后改为常驻（MinNum>=1），
 * 本机制自然不再触发。
 */
export const COLD_START_WAIT_MS = 150_000; // 冷启动等待上限（与 App 首屏等待对齐）
const IDLE_BEFORE_WARMUP_MS = 45_000; // 距上次成功超过此时长 → 疑似已缩容到 0
const WARMUP_POLL_MS = 2_000; // 就绪轮询间隔
const COLD_START_MSG =
  "政务后端正在唤起（云端实例按需启动，未保持常驻）：首次约需一两分钟，请稍候再试。";

/** 构造「调用方主动取消」错误（name=AbortError），供调用方识别并静默丢弃回执。 */
function abortRequestError(): Error {
  const err = new Error("请求已取消");
  err.name = "AbortError";
  return err;
}

export class ApiClient {
  private base: string;
  /**
   * Bearer token。服务端启用 SONGZUO_SERVER_TOKEN 时必需（远程 / 云托管部署即此情形）；
   * 为空则不发 Authorization 头（本地回环模式不受影响，保持原有行为）。
   */
  private token: string;
  /** 上次「确证后端在线」的时刻（收到任何非 503 响应即算），用于判断是否可能已缩容到 0。 */
  private lastOkAt = 0;

  constructor(base: string, token = "") {
    this.base = base.replace(/\/+$/, "");
    this.token = token.trim();
  }

  /**
   * 等待后端就绪（**无副作用**）：轮询 `/health`（幂等、免鉴权）直到 2xx 或超时。
   *
   * 用途：云端实例按需启动（不常驻）时，网关会先返回 503，此时直接下发动作必然失败；
   * 先等就绪再发，就不会把动作打进冷启动窗口。
   *
   * @returns 就绪返回 true；超时返回 false（由调用方决定如何上报）
   */
  private async waitReady(timeoutMs: number): Promise<boolean> {
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      try {
        const res = await fetch(`${this.base}/health`, {
          signal: AbortSignal.timeout(10_000)
        });
        if (res.ok) {
          this.lastOkAt = Date.now();
          return true;
        }
      } catch {
        /* 冷启动期：网络错误 / 超时 / 503 一律视为尚未就绪 */
      }
      if (Date.now() >= deadline) return false;
      await new Promise((r) => setTimeout(r, WARMUP_POLL_MS));
      if (Date.now() >= deadline) return false;
    }
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    // 可靠性策略：单次请求 30s 超时（AbortController）；服务端 5xx（含 503）退避重试
    // （≈1s/2s/4s，最多 3 次）；超时/网络失败/终态错误一律抛带中文详情的 Error。
    const TIMEOUT_MS = 30_000;
    const MAX_ATTEMPTS = 4; // 首次请求 + 最多 3 次 5xx 重试
    const BACKOFF_MS = [1_000, 2_000, 4_000];
    let lastErr: Error | null = null;
    // 调用方外部取消信号（如切换召对会话时 abort 在途记忆库请求）。
    // 未传 signal 的旧调用完全保持原有行为。
    const externalSignal = init?.signal ?? null;
    // `/health` 本身即就绪探针：不可在其内部再触发「等待就绪」，否则自我嵌套。
    const isHealthProbe = path === "/health";
    const isNonIdempotent = NON_IDEMPOTENT_PATHS.some((p) => path.startsWith(p));
    // 冷启动重放只做一次，避免边界情况下反复重放非幂等动作。
    let coldStartReplayed = false;

    // 冷启动前置防护：非幂等端点若距上次成功已久（疑似实例已缩容到 0），先做
    // 无副作用的就绪等待，免得把「推演 / 下诏 / 存档」白白打进冷启动窗口。
    if (
      isNonIdempotent &&
      !isHealthProbe &&
      Date.now() - this.lastOkAt > IDLE_BEFORE_WARMUP_MS &&
      !(await this.waitReady(COLD_START_WAIT_MS))
    ) {
      throw new Error(COLD_START_MSG);
    }

    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      if (externalSignal?.aborted) throw abortRequestError();
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS);
      // 外部取消 → 联动内部超时控制器；网络层只认内部 controller.signal
      const onExternalAbort = () => controller.abort();
      if (externalSignal) {
        if (externalSignal.aborted) controller.abort();
        else externalSignal.addEventListener("abort", onExternalAbort, { once: true });
      }
      try {
        const res = await fetch(`${this.base}${path}`, {
          ...init,
          headers: {
            "Content-Type": "application/json",
            // 服务端启用 SONGZUO_SERVER_TOKEN 时必须携带（否则 /api/* 一律 401，
            // 而 /healthz 仍 200，表现为「服务健康但功能全废」）。
            ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
            // 调用方显式传入的 headers 仍具最高优先级（保持原有语义）
            ...((init?.headers as Record<string, string> | undefined) ?? {})
          },
          signal: controller.signal
        });
        // 收到任何非 503 响应都证明后端实例在线（连 401/4xx 也算：应用已应答），
        // 据此刷新「最后在线时刻」，供上面的冷启动前置防护判断。
        if (res.status !== 503) this.lastOkAt = Date.now();
        if (!res.ok) {
          // 响应体只解析一次，并记录「是否为 JSON」—— 这正是区分 503 来源的判据。
          let detail = `HTTP ${res.status}`;
          let jsonBody: unknown = null;
          try {
            jsonBody = await res.json();
          } catch {
            /* 非 JSON：平台网关的错误响应（如缩容到 0 的 503）即此形态 */
          }
          if (jsonBody && typeof jsonBody === "object") {
            const d = (jsonBody as { detail?: unknown }).detail;
            if (typeof d === "string") {
              detail = d;
            } else if (d && typeof d === "object") {
              // server.py 的 503 形状：{"detail":{"error_code":...,"message":...}}
              const dm = d as { error_code?: string; message?: string };
              detail =
                [dm.error_code, dm.message].filter(Boolean).join(" ") || JSON.stringify(d);
            }
          }
          // 503 的来源必须区分（见文件头常量注释）：
          //   响应体非 JSON = 平台网关 → 请求未到应用 → 重放安全，非幂等端点亦然；
          //   响应体是 JSON = 应用自身（AI 拒绝式失败）→ 可能已进入处理流程 → 不重放。
          const fromGateway = jsonBody === null;
          console.error("[api] 非 2xx", path, res.status, detail);
          if (res.status === 503 && fromGateway && !isHealthProbe && !coldStartReplayed) {
            coldStartReplayed = true;
            if (await this.waitReady(COLD_START_WAIT_MS)) continue;
            throw new Error(COLD_START_MSG);
          }
          // 401/403：服务端启用了 SONGZUO_SERVER_TOKEN，而客户端未携带或携带错误。
          // 若不加这层，玩家只会看到「此令未获准：HTTP 401」而无从下手。
          if (res.status === 401 || res.status === 403) {
            throw new Error(
              "政务后端拒收此令（未授权）：请设置环境变量 SONGZUO_SERVER_TOKEN，" +
                "或在本机 backend_config.json 中补上 token 字段。"
            );
          }
          const msg =
            res.status === 503 && fromGateway
              ? COLD_START_MSG
              : res.status >= 500
                ? `政务后端一时失序：${detail}`
                : `此令未获准：${detail}`;
          // 5xx（含 503 服务暂不可用）→ 退避后重试；其余（4xx 等）终态错误直接抛。
          // C4 修复：非幂等端点不重试（5xx-after-commit / 读超时会造成重复副作用）。
          const retryable =
            res.status >= 500 && res.status < 600 && attempt < MAX_ATTEMPTS &&
            !NON_IDEMPOTENT_PATHS.some((p) => path.startsWith(p));
          if (retryable) {
            lastErr = new Error(msg);
            await new Promise((r) => setTimeout(r, BACKOFF_MS[attempt - 1] ?? 4_000));
            continue;
          }
          throw new Error(msg);
        }
        return (await res.json()) as T;
      } catch (e) {
        // 技术细节（接口路径、原生英文报错）只进控制台，玩家可见文案一律中文、
        // 不含路径/状态机内部信息。
        if (e instanceof Error && e.name === "AbortError") {
          // 调用方主动取消（如切换召对会话）：原样上抛 AbortError 由调用方静默丢弃；
          // 仅内部超时才译成玩家可见的中文提示。
          if (externalSignal?.aborted) throw abortRequestError();
          console.error("[api] 超时", path, e);
          throw new Error(`驿传迟滞：逾 ${TIMEOUT_MS / 1000} 息未得回音，请稍后再试。`);
        }
        if (e instanceof TypeError) {
          console.error("[api] 网络失败", path, e);
          // 2026-09-27（⑦ 支持远端）：原文案写死"**本地**政务后端"，而 SONGZUO_BACKEND 可指向云端
          // ——远端不通时会误导玩家去查本机服务。改为不假设部署形态。
          throw new Error("未能接通政务后端（服务未就绪或已断开，本地/云端皆可能），请稍后再试。");
        }
        // D 修复：2xx 但响应体非 JSON 时 `res.json()` 抛 SyntaxError，原先直接
        // `throw e` 会把原生英文错误漏到界面，违反「玩家可见文案一律中文」契约。
        if (e instanceof SyntaxError) {
          console.error("[api] 回文非 JSON", path, e);
          throw new Error("政务后端回文失格（非 JSON），请稍后再试。");
        }
        throw e;
      } finally {
        window.clearTimeout(timer);
        externalSignal?.removeEventListener("abort", onExternalAbort);
      }
    }
    console.error("[api] 重试耗尽", path, lastErr);
    throw lastErr ?? new Error(`数次传旨皆无回音，请稍后再试。`);
  }

  async health(): Promise<{ ok: boolean; backend: string; has_state: boolean }> {
    return this.request("/health");
  }

  async newGame(difficulty = "史实"): Promise<{ state: GameState }> {
    return this.request("/api/new_game", {
      method: "POST",
      body: JSON.stringify({ difficulty })
    });
  }

  async advance(): Promise<AdvanceResult> {
    return this.request("/api/advance", { method: "POST" });
  }

  /** 朝情富化轮询（两段式回合推进 round2；GET 幂等可重复拉）。
   *  `rich_civilian`＝AI 民间反应富版；`rich_report`＝官方月报（结算总结）；
   *  `settle_error`＝后台结算失败（前端弹"推演失败"）；`log`＝结算朝报；
   *  `state`＝结算完成后的**最新快照**（供回合报告弹窗 before/after 差值）。 */
  async pollRich(): Promise<{
    ready: boolean;
    rich_report: string;
    /** 众生相分幕（AI 月报 6~10 幕场景） */
    rich_report_scenes?: { scene: string; text: string }[];
    rich_civilian: string;
    /** ④ 民间反应分幕（农人/士绅/商贾） */
    rich_civilian_scenes?: { scene: string; text: string }[];
    settle_error: string;
    log: string[];
    state: GameState;
  }> {
    return this.request("/api/advance/round2", { method: "GET" });
  }

  async action(action: ActionName, params: Record<string, unknown> = {}): Promise<ActionResult> {
    return this.request("/api/action", {
      method: "POST",
      body: JSON.stringify({ action, params })
    });
  }

  /** 事件抉择：优先传 eventId（同名事件/标题改写可精确定位），title 作兼容回退 */
  async resolveEvent(title: string, choice: number, eventId?: string): Promise<ResolveResult> {
    return this.request("/api/resolve_event", {
      method: "POST",
      body: JSON.stringify({ title: eventId || title, choice })
    });
  }

  /** 营建立项（工程面板）：蓝图/政府建筑 → state.projects；失败抛带中文原因的 Error。 */
  async proposeProject(
    route: string,
    name: string,
    key = "",
    levels = 1
  ): Promise<{ message: string; project_id?: string; state?: GameState }> {
    return this.request("/api/project/propose", {
      method: "POST",
      body: JSON.stringify({ route, name, key, levels })
    });
  }

  async save(slot = 1): Promise<{ ok: boolean; slot: number }> {
    return this.request("/api/save", {
      method: "POST",
      body: JSON.stringify({ slot })
    });
  }

  async load(slot = 1): Promise<{ state: GameState }> {
    return this.request("/api/load", {
      method: "POST",
      body: JSON.stringify({ slot })
    });
  }

  async saveSlots(): Promise<SaveSlotsResult> {
    return this.request("/api/save_slots");
  }

  async conclude(): Promise<ConcludeResult> {
    return this.request("/api/conclude", { method: "POST" });
  }

  async readouts(): Promise<ReadoutsResult> {
    return this.request("/api/readouts");
  }

  /** Token 计量表（迁移补齐：对齐 Tk panels_meta `_panel_token_meter`） */
  async meter(): Promise<MeterResult> {
    return this.request("/api/meter");
  }

  /** 记忆库只读视图：主库概要/近期关系 + 对话概要 + 变更日志。
   *  传 minister 则取「会话视图」：该大臣完整会话流 + 其按期纪要 + 涉其近关系。 */
  async memory(
    minister?: string,
    init: { signal?: AbortSignal } = {}
  ): Promise<MemoryResult> {
    const name = (minister || "").trim();
    return this.request(
      name ? `/api/memory?minister=${encodeURIComponent(name)}` : "/api/memory",
      init
    );
  }

  async resetMeter(): Promise<{ ok: boolean }> {
    return this.request("/api/meter/reset", { method: "POST" });
  }

  /** 圣旨润色 / 批改诏草（迁移补齐：原 Tk 拟旨面板润色与诏草批改） */
  async polishDecree(
    rawIntent: string,
    draftId = ""
  ): Promise<{ draft: Record<string, unknown>; state?: GameState }> {
    return this.request("/api/decree/polish", {
      method: "POST",
      body: JSON.stringify({ raw_intent: rawIntent, draft_id: draftId })
    });
  }

  /** 弃删诏草 */
  async discardDecreeDraft(
    draftId: string
  ): Promise<{ ok: boolean; title?: string; state?: GameState }> {
    return this.request("/api/decree/discard", {
      method: "POST",
      body: JSON.stringify({ draft_id: draftId })
    });
  }

  /** 月折（奏报摘要） */
  async monthlyReport(): Promise<{ report: string }> {
    return this.request("/api/monthly_report", { method: "POST" });
  }

  async councilReview(draftId: string): Promise<CouncilReviewResult> {
    return this.request("/api/council_review", {
      method: "POST",
      body: JSON.stringify({ draft_id: draftId })
    });
  }

  async getAiConfig(): Promise<AiConfigResult> {
    return this.request("/api/ai_config");
  }

  async setAiConfig(
    api_key: string,
    base_url: string,
    model: string,
    enable_tools = "auto"
  ): Promise<{ ok: boolean; available: boolean; message?: string }> {
    return this.request("/api/ai_config", {
      method: "POST",
      body: JSON.stringify({ api_key, base_url, model, enable_tools })
    });
  }

  async fetchModels(api_key: string, base_url: string): Promise<{ ok: boolean; models: string[]; error?: string }> {
    try {
      return await this.request("/api/fetch_models", {
        method: "POST",
        body: JSON.stringify({ api_key, base_url })
      });
    } catch (e) {
      // D 修复：原实现失败时「静默返回硬编码常用列表」，会引导玩家选中该端点
      // 并不存在的模型（保存/调用时才报错，且来源难辨）。现如实返回空列表 + 错误。
      console.warn("[fetchModels] 接口探测失败:", e);
      return {
        ok: false,
        models: [],
        error: e instanceof Error ? e.message : String(e)
      };
    }
  }
}

// 全局单例（由 App 初始化时注入 base）
let _client: ApiClient | null = null;

export function setApiClient(c: ApiClient): void {
  _client = c;
}

export function getApiClient(): ApiClient {
  if (!_client) throw new Error("ApiClient 尚未初始化");
  return _client;
}


// ============================================================
// 共享朝情富化轮询器（P2-37：Dock 与 AdvancePanel 原各起一条 setInterval
// 同时打 /api/advance/round2，互相覆盖弹窗/富文本时机）。
// 现收敛为**单 interval + 多订阅者**，谁在听谁收，互不抢跑。
// ============================================================
export type RichPollResult = {
  ready: boolean;
  rich_report: string;
  /** 众生相分幕（AI 月报 6~10 幕场景） */
  rich_report_scenes?: { scene: string; text: string }[];
  rich_civilian: string;
  /** ④ 民间反应分幕（农人/士绅/商贾） */
  rich_civilian_scenes?: { scene: string; text: string }[];
  settle_error: string;
  log: string[];
  state: GameState;
};
type RichPollSub = (r: RichPollResult) => void;
const _richSubs = new Set<RichPollSub>();
let _richTimer: number | null = null;

function _richTick(): void {
  void getApiClient().pollRich().then((r) => {
    // 订阅者各自决定是否消费（ready/settle_error 等语义在调用方）
    for (const cb of [..._richSubs]) {
      try { cb(r); } catch (e) { console.error("[richPoll] 订阅者异常", e); }
    }
  }).catch(() => { /* 轮询失败静默——调用方有各自兜底 */ });
}

/** 订阅共享富化轮询（首个订阅者启动 timer，返回退订函数）。 */
export function subscribeRichPoll(cb: RichPollSub, intervalMs = 4000): () => void {
  _richSubs.add(cb);
  if (_richTimer === null) {
    _richTimer = window.setInterval(_richTick, intervalMs);
  }
  return () => {
    _richSubs.delete(cb);
    if (_richSubs.size === 0 && _richTimer !== null) {
      window.clearInterval(_richTimer);
      _richTimer = null;
    }
  };
}
