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
  defense_lines: Record<string, { fortification: number; garrison: number }>;
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

export interface AiConfigResult {
  configured: boolean;
  api_key_masked: string;
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

    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS);
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