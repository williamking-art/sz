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
  army_name: string;
  org_arm: string;
  scale: string;
  serial: string;
}

export interface ReadoutsResult {
  army: ArmyUnitReadout[];
  arsenal: Record<string, unknown>;
  finance: Record<string, unknown>;
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
  source: "legacy" | "focus" | "free_effect" | "event";
  status: "active" | "resolved" | "failed" | "cancelled";
  /** 0–100；无进度来源为 null（前端显示"未定义"，不得当 0） */
  bar_value: number | null;
  resolve_condition_text: string | null;
  fail_condition_text: string | null;
  ongoing_text: string | null;
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

/** 州路简报单条（对齐 core/region_brief.py::build_region_brief） */
export interface RegionRoute {
  name: string;
  display_name: string;
  controlled_by: string;
  households: number;
  population: number;
  land: number;
  hidden_land: number;
  mood: number;
  govern: number;
  public_support: number;
  gentry_resistance: number;
  city_defense: number;
  unrest: number;
  fiscal: number;
  /** 识字率（该路各地 POP 自有值按人口加权派生；未初始化时 null） */
  literacy: number | null;
  grain_year: number;
  grain_stock: number;
  /** 粮储安全垫（月）；无口粮需求时为 null */
  grain_months: number | null;
  /** 本路到账后月税（贯/月，二税折色实收口径） */
  tax_month: number;
  /** 占全国月税比 0~1 */
  tax_share: number;
  /** 驻军月饷（贯/月） */
  army_cash_month: number;
  /** 驻军月粮（石/月） */
  army_grain_month: number;
  risk_score: number;
  risk_label: "安" | "警" | "危";
  risk_hints: string[];
}

export interface RegionBriefResult {
  routes: RegionRoute[];
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
  | "approve_ai_action"
  | "reject_ai_action"
  | "issue_kouyu"
  | "propose_inner_transfer"
  | "confirm_inner_transfer"
  | "cancel_inner_transfer";

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

/** 构造「调用方主动取消」错误（name=AbortError），供调用方识别并静默丢弃回执。 */
function abortRequestError(): Error {
  const err = new Error("请求已取消");
  err.name = "AbortError";
  return err;
}

export class ApiClient {
  private base: string;

  constructor(base: string) {
    this.base = base.replace(/\/+$/, "");
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
          headers: { "Content-Type": "application/json" },
          ...init,
          signal: controller.signal
        });
        if (!res.ok) {
          let detail = `HTTP ${res.status}`;
          try {
            const body = await res.json();
            if (body && typeof body.detail === "string") detail = body.detail;
          } catch {
            /* ignore */
          }
          console.error("[api] 非 2xx", path, res.status, detail);
          const msg =
            res.status >= 500
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
          throw new Error("未能接通本地政务后端（服务未就绪或已断开），请稍后再试。");
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

  async action(action: ActionName, params: Record<string, unknown> = {}): Promise<ActionResult> {
    return this.request("/api/action", {
      method: "POST",
      body: JSON.stringify({ action, params })
    });
  }

  async resolveEvent(title: string, choice: number): Promise<ResolveResult> {
    return this.request("/api/resolve_event", {
      method: "POST",
      body: JSON.stringify({ title, choice })
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

  /** 润色稿入待签队列（三省会签用） */
  async saveDecreeDraft(
    draft: Record<string, unknown>
  ): Promise<{ draft_id: string; state?: GameState }> {
    return this.request("/api/decree/draft", {
      method: "POST",
      body: JSON.stringify({ draft })
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