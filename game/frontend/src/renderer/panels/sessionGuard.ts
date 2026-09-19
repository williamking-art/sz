/**
 * 召对会话守卫（纯逻辑，不依赖 React / DOM，可独立自测）
 *
 * 背景（P1-8 / P1-9）：召对面板的「拉取记忆库」「发起奏对」「内帑调拨」都是异步请求，
 * 而 UI 状态（消息列 / 记忆库快照 / 会话名录）只对应「当前大臣」。快速切换大臣或在
 * 切换瞬间收到旧请求回执时，旧数据会覆盖新会话的消息列（串台）。
 *
 * 隔离模型（三层身份）：
 *   1. minister —— 会话对象（大臣 ID）。回执归属的大臣必须仍是 current。
 *   2. epoch    —— 会话纪元（等价于 session id）。切换/重载该大臣会话时递增，
 *                  旧纪元的所有在途请求立即失效；同名大臣「离开再回来」也会换纪元。
 *   3. seq      —— 全局单调请求序号，按 (用途, 大臣) 通道记录「最新」。同通道内
 *                  只有最新一次请求有权写状态（后发制人），不同用途互不抢占
 *                  （例如侧栏刷新不得吞掉在途的奏对回奏）。
 *
 * 典型时序：
 *   A 加载中 → 切到 B（invalidate A）→ A 的回执到达 → isFresh 为 false → 丢弃。
 *   A 奏对中 → 侧栏刷新 A（另开通道）→ 奏对回执到达 → 仍 isFresh → 正常写入。
 */

/** 请求用途：不同用途各自持有 (用途,大臣) 通道内的「最新序号」，互不抢占。 */
export type RequestPurpose = "session" | "sidebar" | "dialogue" | "transfer";

/** 发起请求时冻结的身份凭据；写状态前必须拿它复核。 */
export interface RequestTicket {
  /** 发起时的大臣（会话对象）ID */
  readonly minister: string;
  /** 请求用途 */
  readonly purpose: RequestPurpose;
  /** 发起时的会话纪元（session id 的本地等价物） */
  readonly epoch: number;
  /** 该通道内本次请求的单调序号 */
  readonly seq: number;
}

/** 会话加载三态：加载中 / 就绪 / 失败 */
export type SessionPhase = "loading" | "ready" | "error";
/** 消息列展示态：加载中 / 失败 / 空档 / 就绪（四者互斥，替代单一 loading 布尔） */
export type SessionDisplay = "loading" | "error" | "empty" | "ready";

function scopeKey(purpose: RequestPurpose, minister: string): string {
  return purpose + "\u0000" + minister;
}

export class SessionGuard {
  private seqCounter = 0;
  private readonly latest = new Map<string, number>();
  private readonly epochs = new Map<string, number>();

  /** 读取某大臣当前会话纪元（默认为 0）。 */
  epochOf(minister: string): number {
    return this.epochs.get(minister) ?? 0;
  }

  /**
   * 作废某大臣当前所有在途请求（切换大臣、显式重载会话时调用）。
   * 该大臣已发出的凭据 epoch 不再匹配，isFresh 一律返回 false。
   */
  invalidate(minister: string): void {
    this.epochs.set(minister, this.epochOf(minister) + 1);
  }

  /** 发起一次异步请求前冻结身份凭据。 */
  issue(minister: string, purpose: RequestPurpose): RequestTicket {
    this.seqCounter += 1;
    const seq = this.seqCounter;
    this.latest.set(scopeKey(purpose, minister), seq);
    return { minister, purpose, epoch: this.epochOf(minister), seq };
  }

  /**
   * 写状态前校验：对象未变（仍旧是当前大臣）、会话纪元未变（未切换/重载）、
   * 且本通道内仍是最新请求。任一不符即视为过期回执，不得写入 UI。
   */
  isFresh(ticket: RequestTicket, currentMinister: string): boolean {
    if (ticket.minister !== currentMinister) return false;
    if (ticket.epoch !== this.epochOf(ticket.minister)) return false;
    return this.latest.get(scopeKey(ticket.purpose, ticket.minister)) === ticket.seq;
  }
}

/** 识别「调用方主动取消」错误（AbortController.abort() 触发）。 */
export function isAbortError(e: unknown): boolean {
  return (
    !!e &&
    typeof e === "object" &&
    (e as { name?: unknown }).name === "AbortError"
  );
}

/**
 * 消息列展示态：区分 loading / error / empty / ready，不再混用一个布尔量。
 * empty 专指「拉取成功但无留档」（此时消息列只有回落开场白），
 * 与「加载中」「读取失败」在 UI 上各有独立呈现。
 */
export function classifySessionView(v: {
  phase: SessionPhase;
  archivedCount: number;
}): SessionDisplay {
  if (v.phase === "loading") return "loading";
  if (v.phase === "error") return "error";
  if (v.archivedCount <= 0) return "empty";
  return "ready";
}