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
  army_name: string;
  org_arm: string;
  scale: string;
  serial: string;
}

export interface ReadoutsResult {
  army: ArmyUnitReadout[];
  arsenal: Record<string, unknown>;
  finance: Record<string, unknown>;
  granary: {
    monthly?: number;
    army?: number;
    official?: number;
    clerk?: number;
    capacity_used?: number;
  };
  defense_lines: Record<string, { fortification: number; garrison: number }>;
}

export interface AiConfigResult {
  configured: boolean;
  api_key_masked: string;
  base_url: string;
  model: string;
  has_key?: boolean;
  message?: string;
  available?: boolean;
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
  | "start_tech_research"
  | "approve_invention"
  | "reject_invention";

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
          const msg =
            res.status >= 500
              ? `服务端错误（HTTP ${res.status}）：${detail}`
              : `请求失败（HTTP ${res.status}）：${detail}`;
          // 5xx（含 503 服务暂不可用）→ 退避后重试；其余（4xx 等）终态错误直接抛
          if (res.status >= 500 && res.status < 600 && attempt < MAX_ATTEMPTS) {
            lastErr = new Error(msg);
            await new Promise((r) => setTimeout(r, BACKOFF_MS[attempt - 1] ?? 4_000));
            continue;
          }
          throw new Error(msg);
        }
        return (await res.json()) as T;
      } catch (e) {
        if (e instanceof Error && e.name === "AbortError") {
          throw new Error(`请求超时（${TIMEOUT_MS / 1000} 秒）：${path}`);
        }
        // fetch 网络层失败（后端未就绪/断连），保留原生原因并附中文上下文
        if (e instanceof TypeError) {
          throw new Error(`网络请求失败：${path}（${e.message}）`);
        }
        throw e;
      } finally {
        window.clearTimeout(timer);
      }
    }
    throw lastErr ?? new Error(`请求失败（已重试 ${MAX_ATTEMPTS - 1} 次仍无果）：${path}`);
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

  async councilReview(draftId: string): Promise<CouncilReviewResult> {
    return this.request("/api/council_review", {
      method: "POST",
      body: JSON.stringify({ draft_id: draftId })
    });
  }

  async getAiConfig(): Promise<AiConfigResult> {
    return this.request("/api/ai_config");
  }

  async setAiConfig(api_key: string, base_url: string, model: string): Promise<{ ok: boolean; available: boolean; message?: string }> {
    return this.request("/api/ai_config", {
      method: "POST",
      body: JSON.stringify({ api_key, base_url, model })
    });
  }

  async fetchModels(api_key: string, base_url: string): Promise<{ ok: boolean; models: string[]; error?: string }> {
    try {
      return await this.request("/api/fetch_models", {
        method: "POST",
        body: JSON.stringify({ api_key, base_url })
      });
    } catch (e) {
      console.warn("[fetchModels] 接口探测异常，降级返回常用列表:", e);
      return {
        ok: false,
        models: ["deepseek-chat", "deepseek-reasoner", "gpt-4o", "gpt-4o-mini", "qwen-plus", "qwen-turbo"],
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