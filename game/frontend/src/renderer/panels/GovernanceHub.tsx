import { useState } from "react";
import { useGameStore, pick, getTreasuryDetail } from "../store/gameStore";
import { getApiClient } from "../api/client";

// 治务枢纽 —— 聚合 Tk 尚未迁至 Electron 的治理数据（只读展示）：
//   资金流/税制 · 灾荒·时代·危机 · 帝国机制 · 纪事/奏折 · 条约/外交纪事 · AI计量
type Dict = Record<string, unknown>;

function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}
function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}
function asDict(v: unknown): Dict {
  return v && typeof v === "object" ? (v as Dict) : {};
}
function asArr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}
function wan(n: number): string {
  if (n >= 1e8) return `${(n / 1e8).toFixed(1)}亿`;
  if (n >= 1e4) return `${(n / 1e4).toFixed(0)}万`;
  return `${n}`;
}

const TABS = [
  ["fund", "资 金 流"],
  ["crisis", "危 机 · 时 代"],
  ["mechanism", "帝 国 机 制"],
  ["chronicle", "纪 事 · 奏 折"],
  ["treaty", "条 约 · 邦 交"],
  ["meter", "AI 计 量"],
] as const;

export default function GovernanceHub() {
  const [tab, setTab] = useState<string>("fund");
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded-lg px-3.5 py-1.5 font-kai text-[13px] tracking-wider transition ${
              tab === key ? "bg-red text-paper" : "bg-paper/60 text-red hover:bg-gold-light"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "fund" && <FundTab />}
      {tab === "crisis" && <CrisisTab />}
      {tab === "mechanism" && <MechanismTab />}
      {tab === "chronicle" && <ChronicleTab />}
      {tab === "treaty" && <TreatyTab />}
      {tab === "meter" && <MeterTab />}
    </div>
  );
}

/** 内部键 → 中文（与 utils/effects.ts 同规：未登记键不得直出英文键名）。

 * 未登记者以「其他」归并 —— 既不漏数据，也不把 snake_case 键名当文案显示。
 */
const ERA_LABELS: Record<string, string> = {
  economy_center: "经济重心", culture: "文教", commerce: "商贸",
  military: "军事", urban: "城市",
};
const GRANARY_LABELS: Record<string, string> = {
  canal_in: "漕运入仓", military: "军需支拨", converted: "折色转换",
  harvest: "田赋入仓", relief: "赈济出仓", seed: "留种",
};

function FundTab() {
  const state = useGameStore((s) => s.state);
  const readouts = useGameStore((s) => s.readouts);
  // 🔴 M282（修 M275）：税入四项改从**权威分项**取 —— `getTreasuryDetail(...).incomes`
  //   （来源＝`finance_readout`，store 注释明写「GUI 与终端共用，避免两处口径漂移」）。
  //   ⚠️ 旧写法读 `state.tax_breakdown`：该 dict 由 `_settle_finance` 写入，**只有**
  //   `commerce`/`poll`/`maritime`/`official_service` ⇒ 读 `tax_color`/`salt` 两键**永不存在**
  //   ⇒ 恒显示 0（**把缺失显示成 0**，违 §3-3）。
  const finance = readouts ? (readouts.finance ?? null) : null;
  const incomeBy = new Map(
    getTreasuryDetail(state, finance).incomes.map((it) => [it.name, it.amount] as const),
  );
  const st = asDict(pick<Dict>(state, "statistics", {}));
  const gs = asDict(pick<Dict>(state, "granary_stats", {}));
  // 面板行名 → `incomes` 里的权威科目名；**不在列表 ⇒ null**（显示「未定义」，**不回落 0**）
  const rows: Array<[string, number | null]> = [
    ["工商", incomeBy.get("工商榷税") ?? null],
    ["役钱", incomeBy.get("身丁役钱") ?? null],
    ["二税折色", incomeBy.get("两税折色") ?? null],
    ["盐课", incomeBy.get("盐铁官榷") ?? null],
  ];
  return (
    <div className="space-y-3">
      <Section title="税 入 构 成">
        {rows.map(([k, v]) => (
          <p key={k} className="text-sm text-ink">
            {k}　
            {v === null
              ? <span className="text-dim" title="读数未就绪（后端未返回该科目）">未定义</span>
              : wan(v) + " 贯"}
          </p>
        ))}
      </Section>
      <Section title="累 计 统 计">
        <p className="text-sm text-ink">入　{wan(asNum(st.total_income))} 贯（行）</p>
        <p className="text-sm text-ink">出　{wan(asNum(st.total_expenditure))} 贯</p>
        <p className="text-sm text-ink">诏令 {asNum(st.total_decrees)}　战事 {asNum(st.total_wars)}　灾荒 {asNum(st.total_disasters)}</p>
      </Section>
      <Section title="仓 廪 统 计">
        {Object.keys(gs).length === 0 ? (
          <p className="text-sm text-dim">— 暂无仓廪收支统计 —</p>
        ) : (
          Object.keys(gs).map((k) => (
            <p key={k} className="text-sm text-ink-light">{GRANARY_LABELS[k] ?? "其他"}　{wan(asNum(gs[k]))}</p>
          ))
        )}
      </Section>
    </div>
  );
}

function CrisisTab() {
  const state = useGameStore((s) => s.state);
  const era = asDict(pick<Dict>(state, "era_state", {}));
  const ep = asDict(pick<Dict>(state, "event_pressure", {}));
  const history = asArr(pick<unknown[]>(state, "event_history", []));
  const region = asStr(pick<Dict>(state, "disaster_region", {}).value ?? (state as Dict).disaster_region, "") || asStr(pick<unknown>(state, "disaster_region", ""), "");
  const sever = asNum(pick<unknown>(state, "disaster_severity", 0));

  return (
    <div className="space-y-3">
      <Section title="时 代 五 维">
        {Object.keys(era).map((k) => (
          <div key={k} className="mb-1 flex items-center gap-2">
            <span className="w-28 font-kai text-[13px] text-ink-light">{ERA_LABELS[k] ?? "其他"}</span>
            <div className="flex-1 h-2.5 overflow-hidden rounded-full border border-gold/50 bg-[#e0d3b3]">
              <div className="h-full rounded-full bg-red" style={{ width: `${Math.round(Math.max(0, Math.min(100, asNum(era[k]))))}%` }} />
            </div>
            <span className="w-8 text-xs text-dim">{Math.round(asNum(era[k]))}</span>
          </div>
        ))}
      </Section>
      <Section title="当 前 灾 荒">
        <p className="text-sm text-ink">{sever > 0 ? `「${region || "?路"}」受灾　等级 ${sever}` : "— 无灾荒 —"}</p>
      </Section>
      <Section title="危 机 压 力">
        {Object.keys(ep).length === 0 ? (
          <p className="text-sm text-dim">— 暂无压力线索 —</p>
        ) : (
          Object.keys(ep).map((k) => <p key={k} className="text-sm text-ink-light">{k}：{asNum(ep[k])}</p>)
        )}
      </Section>
      <Section title="历 史 事 件">
        {history.length === 0 ? (
          <p className="text-sm text-dim">— 暂无事件史 —</p>
        ) : (
          <div className="max-h-36 overflow-y-auto">
            {history.map((e, i) => <p key={i} className="text-xs text-ink-light">{e && typeof e === "object" ? asStr(asDict(e).title, asStr(asDict(e).message, String(e))) : String(e)}</p>)}
          </div>
        )}
      </Section>
    </div>
  );
}

function MechanismTab() {
  const state = useGameStore((s) => s.state);
  const legacies = asDict(pick<Dict>(state, "legacies", {}));
  const mechs = asDict(pick<Dict>(state, "mechanisms", {}));
  const wr = asDict(pick<Dict>(state, "waste_reform", {}));
  const pay = asDict(pick<Dict>(state, "pay_system", {}));
  // 审查修复：active_focus 是对象（{branch,node_key,name,status,progress,…}）或 null，
  // completed_focuses 元素亦为对象；原按字符串 / 字符串数组读取 → 「施行」「已竟」
  // 两项恒显示空白（asStr 对对象返回 ""、asStr(dict) 亦然）。
  const focusObj = asDict(pick<Dict>(state, "active_focus", {}));
  const completed = asArr(pick<unknown[]>(state, "completed_focuses", []));

  return (
    <div className="space-y-3">
      <Section title="帝 国 修 正（legacies）">
        {Object.keys(legacies).length === 0 ? (
          <p className="text-sm text-dim">— 暂无生效修正 —</p>
        ) : (
          Object.keys(legacies).map((k) => {
            const L = asDict(legacies[k]);
            // 键名为内部标识，须显示 name（同 CourtPanel 帝国修正的取法）
            return (
              <p key={k} className="text-sm text-ink-light">
                {asStr(L.name, "帝国修正")}（{L.active ? "生效中" : "待触发"}）
              </p>
            );
          })
        )}
      </Section>
      <Section title="机 制 槽">
        {Object.keys(mechs).length === 0 ? (
          <p className="text-sm text-dim">— 未设机制 —</p>
        ) : (
          // 同上：不得直出内部键名；有 name 用 name，无则以「已设机制」归并
          Object.keys(mechs).map((k) => (
            <p key={k} className="text-sm text-ink-light">
              {asStr(asDict(mechs[k]).name, "已设机制")}
            </p>
          ))
        )}
      </Section>
      <Section title="宰 省 与 俸 禄">
        <p className="text-sm text-ink">俸禄：{asStr(pay.mode)}（本色 {Math.round(asNum(pay.grain_ratio) * 100)}% / 折银 {Math.round(asNum(pay.cash_ratio) * 100)}%）</p>
        <p className="text-sm text-ink-light">
          {wr.active ? `宰省浮费进行中：目标 ${wan(asNum(wr.target))}，已省 ${wan(asNum(wr.savings))}，余 ${asNum(wr.months_left)} 月` : "— 未行宰省浮费 —"}
        </p>
      </Section>
      <Section title="国 策">
        <p className="text-sm text-ink">
          施行：{asStr(focusObj.name) || asStr(focusObj.node_key, "—")}
          {asStr(focusObj.status) && <span className="text-dim">（{asStr(focusObj.status)}）</span>}
          {asNum(focusObj.progress) > 0 && (
            <span className="text-dim">　进度 {Math.round(asNum(focusObj.progress))}%</span>
          )}
        </p>
        {completed.length > 0 && (
          <p className="text-sm text-dim">
            已竟：{completed
              .map((v) => asStr(asDict(v).name, asStr(asDict(v).node_key, "")))
              .filter(Boolean)
              .join(" / ") || "—"}
          </p>
        )}
      </Section>
    </div>
  );
}

function ChronicleTab() {
  const state = useGameStore((s) => s.state);
  const setState = useGameStore((s) => s.setState);
  const pushUiLog = useGameStore((s) => s.pushUiLog);
  const dial = asArr(pick<unknown[]>(state, "dialogue_history", []));
  const memos = asArr(pick<unknown[]>(state, "memorials", []));
  const short = asArr(pick<unknown[]>(state, "short_term_log", []));
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [busyIndex, setBusyIndex] = useState<number | null>(null);

  /** 准奏/留中共用：失败必须在界面可见，且**不得**改动本地 state（避免失败被当成成功）。 */
  async function handleMemorial(index: number, action: "accept_memorial" | "dismiss_memorial", label: string) {
    if (busyIndex !== null) return;
    setBusyIndex(index);
    setNotice(null);
    try {
      const res = await getApiClient().action(action, { index });
      if (res.state) setState(res.state);
      if (res.message) pushUiLog(res.message);
      setNotice({ kind: "ok", text: res.message || `${label}已办` });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setNotice({ kind: "error", text: `${label}未成：${msg}` });
    } finally {
      setBusyIndex(null);
    }
  }

  function handleAccept(index: number) {
    return handleMemorial(index, "accept_memorial", "准奏");
  }

  function handleDismiss(index: number) {
    return handleMemorial(index, "dismiss_memorial", "留中");
  }

  return (
    <div className="space-y-3">
      {notice && (
        <p
          role="alert"
          className={`rounded border px-3 py-1.5 text-sm ${
            notice.kind === "error"
              ? "border-red/50 bg-red/5 text-red"
              : "border-emerald-700/50 bg-emerald-50 text-emerald-800"
          }`}
        >
          {notice.text}
        </p>
      )}
      <Section title="君 臣 纪 事（奏对）">
        {dial.length === 0 ? <p className="text-sm text-dim">— 暂无奏对 —</p> : (
          <div className="max-h-32 overflow-y-auto">
            {dial.map((d, i) => {
              // 后端 dialogue_history = [(说话人, 内容), ...]，JSON 化后即二元数组
              const pair = asArr(d);
              const text = asStr(pair[1]);
              if (!text) return null;
              return (
                <p key={i} className="text-xs leading-relaxed text-ink-light">
                  <span className="font-kai text-ink">{asStr(pair[0], "？")}：</span>{text}
                </p>
              );
            })}
          </div>
        )}
      </Section>
      <Section title="奏 折 / 疏">{
        memos.length === 0 ? <p className="text-sm text-dim">— 案上无事 —</p> : (
          <div className="space-y-2">
            {memos.map((m, i) => {
              const d = asDict(m);
              const title = asStr(d.title) || asStr(d.text, "（无题）");
              const body = asStr(d.body) || asStr(d.content);
              const sourceTag = asStr(d.source_tag, "通进银台司进呈");
              const official = asDict(d.official);
              const offRole = asStr(official.role);
              const offName = asStr(official.name);
              const guarantor = asStr(d.guarantor);

              return (
                <div key={i} className="rounded border border-gold/40 bg-paper/40 p-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-kai font-bold text-red">
                      〔{sourceTag}〕{title}
                    </span>
                    <div className="flex space-x-1">
                      <button
                        onClick={() => handleAccept(i)}
                        disabled={busyIndex !== null}
                        className="rounded bg-red px-2 py-0.5 font-kai text-[11px] text-paper shadow-sm hover:bg-red/80 transition disabled:opacity-50"
                      >
                        准 奏
                      </button>
                      <button
                        onClick={() => handleDismiss(i)}
                        disabled={busyIndex !== null}
                        className="rounded border border-gold/60 bg-paper px-2 py-0.5 font-kai text-[11px] text-dim hover:text-ink transition disabled:opacity-50"
                      >
                        留 中
                      </button>
                    </div>
                  </div>
                  {body && <p className="mt-1 leading-relaxed text-ink-light">{body}</p>}
                  <div className="mt-1 flex items-center justify-between text-[11px] text-dim font-kai">
                    <span>
                      {offName ? `具奏人：${offRole ? offRole + " " : ""}${offName}` : "具奏：有司"}
                    </span>
                    {guarantor && <span className="text-dim/80">举主保任：{guarantor}</span>}
                  </div>
                </div>
              );
            })}
          </div>
        )
      }</Section>
      <Section title="决 策 日 志">{
        short.length === 0 ? <p className="text-sm text-dim">— 暂无决策日志 —</p> : (
          <div className="max-h-32 overflow-y-auto">
            {short.map((e, i) => {
              const d = asDict(e);
              const mark = { decree: "诏", edict: "谕" }[asStr(d.kind)] ?? "政";
              const when = asNum(d.year) ? `${asNum(d.year)}年${asNum(d.month, 1)}月　` : "";
              return (
                <p key={i} className="text-xs leading-relaxed text-ink-light">
                  {when}
                  <span className="text-red">〔{mark}〕</span>
                  {asStr(d.title, "（无题）")}
                  {asStr(d.note) && <span className="text-dim">　—— {asStr(d.note)}</span>}
                </p>
              );
            })}
          </div>
        )
      }</Section>
    </div>
  );
}

/** 条约「条款」→ 中文短语。terms 形状随协议类型而异（core/diplomacy_treaty.py）：
 *  和亲 / 岁币 / 榷场 / 战争 → {tier: 档位词}；盟约 → {结: bool}。 */
function treatyTerm(t: Dict): string {
  const terms = asDict(t.terms);
  if (typeof terms["结"] === "boolean") return terms["结"] ? "已结" : "未结";
  return asStr(terms.tier, "已立");
}

function TreatyTab() {
  const state = useGameStore((s) => s.state);
  const treaties = asDict(pick<Dict>(state, "treaties", {}));
  const dlog = asArr(pick<unknown[]>(state, "diplomacy_log", []));

  return (
    <div className="space-y-3">
      <Section title="条 约">
        {Object.keys(treaties).length === 0 ? <p className="text-sm text-dim">— 暂无条约 —</p> : (
          Object.keys(treaties).map((k) => (
            <div key={k} className="mb-1">
              <p className="font-kai text-sm font-bold text-ink">{asStr(k)}</p>
              {asArr(treaties[k]).map((t, i) => {
                const d = asDict(t);
                return (
                  <p key={i} className="text-xs leading-relaxed text-ink-light">
                    　{asStr(d.type, "盟约")}（{treatyTerm(d)}）
                    {asNum(d.year) ? <span className="text-dim">　{asNum(d.year)}年{asNum(d.month, 1)}月</span> : null}
                  </p>
                );
              })}
            </div>
          ))
        )}
      </Section>
      <Section title="外 交 纪 事">{
        dlog.length === 0 ? <p className="text-sm text-dim">— 暂无外交纪事 —</p> : (
          <div className="max-h-32 overflow-y-auto">
            {dlog.map((d, i) => {
              if (typeof d === "string") {
                return <p key={i} className="text-xs leading-relaxed text-ink-light">{d}</p>;
              }
              const o = asDict(d);
              return (
                <p key={i} className="text-xs leading-relaxed text-ink-light">
                  {asStr(o.text) || asStr(o.note) || asStr(o.title, "（纪事阙文）")}
                </p>
              );
            })}
          </div>
        )
      }</Section>
    </div>
  );
}

function MeterTab() {
  const state = useGameStore((s) => s.state);
  const rows = asArr(pick<unknown[]>(state, "ai_token_log", []));
  // 本月未成的推演 Agent（后端 _ai_failures 以公开名 ai_failures 下发，仅含 agent 名）
  const aiFail = asArr(pick<unknown[]>(state, "ai_failures", [])).map((x) => String(x));
  const sum = rows.reduce(
    (a: { calls: number; p: number; cp: number }, r) => {
      const d = asDict(r);
      a.calls += asNum(d.calls);
      a.p += asNum(d.prompt_tokens);
      a.cp += asNum(d.completion_tokens);
      return a;
    },
    { calls: 0, p: 0, cp: 0 },
  );
  return (
    <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
      <div className="mb-2 flex items-baseline justify-between">
        <p className="font-kai text-[14px] font-bold tracking-widest text-red">AI 词元用量（每回合格）</p>
        <p className="text-xs text-dim">累计 {sum.calls} 次　输入 {sum.p.toLocaleString()}　输出 {sum.cp.toLocaleString()}　合计 {(sum.p + sum.cp).toLocaleString()}</p>
        {/* 审查补齐：AI 失败原对玩家完全静默（只写 _ai_failures，无消费方） */}
        {aiFail.length > 0 && (
          <p className="text-xs text-red-dark">
            本月有 {aiFail.length} 项推演未成（{aiFail.join("、")}），相关事项已走本地兜底
          </p>
        )}
      </div>
      {rows.length === 0 ? (
        <p className="py-4 text-center font-kai text-sm text-dim">— 暂无用量记录（推演后生成）—</p>
      ) : (
        <div className="max-h-[52vh] overflow-auto">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="text-dim">
                <th className="border border-gold/30 bg-gold-light px-2 py-1 text-left font-kai">回 合</th>
                <th className="border border-gold/30 bg-gold-light px-2 py-1 text-right font-kai">调 用</th>
                <th className="border border-gold/30 bg-gold-light px-2 py-1 text-right font-kai">输 入</th>
                <th className="border border-gold/30 bg-gold-light px-2 py-1 text-right font-kai">输 出</th>
                <th className="border border-gold/30 bg-gold-light px-2 py-1 text-right font-kai">合 计</th>
                <th className="border border-gold/30 bg-gold-light px-2 py-1 text-left font-kai">时 间</th>
              </tr>
            </thead>
            <tbody>
              {[...rows].reverse().map((r, i) => {
                const d = asDict(r);
                return (
                  <tr key={i} className="text-ink-light even:bg-gold-light/30">
                    <td className="border border-gold/30 px-2 py-1 font-kai">{asStr(d.label, `#${asNum(d.turn)}`)}</td>
                    <td className="border border-gold/30 px-2 py-1 text-right">{asNum(d.calls)}</td>
                    <td className="border border-gold/30 px-2 py-1 text-right">{asNum(d.prompt_tokens).toLocaleString()}</td>
                    <td className="border border-gold/30 px-2 py-1 text-right">{asNum(d.completion_tokens).toLocaleString()}</td>
                    <td className="border border-gold/30 px-2 py-1 text-right font-bold">{asNum(d.total_tokens).toLocaleString()}</td>
                    <td className="border border-gold/30 px-2 py-1">{asStr(d.ts, "—")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
      <p className="mb-2 font-kai text-[14px] font-bold tracking-widest text-red">{title}</p>
      <div className="space-y-1">{children}</div>
    </div>
  );
}