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
}

export type ActionName =
  | "issue_decree"
  | "issue_secret_decree"
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
    const res = await fetch(`${this.base}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        if (body && typeof body.detail === "string") detail = body.detail;
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    return (await res.json()) as T;
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

  async getAiConfig(): Promise<AiConfigResult> {
    return this.request("/api/ai_config");
  }

  async setAiConfig(api_key: string, base_url: string, model: string): Promise<{ ok: boolean; available: boolean }> {
    return this.request("/api/ai_config", {
      method: "POST",
      body: JSON.stringify({ api_key, base_url, model })
    });
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