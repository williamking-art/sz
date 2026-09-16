import { useState } from "react";
import { useGameStore, pick } from "../store/gameStore";

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

function FundTab() {
  const state = useGameStore((s) => s.state);
  const tax = asDict(pick<Dict>(state, "tax_breakdown", {}));
  const st = asDict(pick<Dict>(state, "statistics", {}));
  const gs = asDict(pick<Dict>(state, "granary_stats", {}));
  const rows = [
    ["工商", asNum(tax.commerce)], ["役钱", asNum(tax.poll)],
    ["二税折色", asNum(tax.tax_color)], ["盐课", asNum(tax.salt)],
  ];
  return (
    <div className="space-y-3">
      <Section title="税 入 构 成">
        {rows.map(([k, v]) => (
          <p key={k as string} className="text-sm text-ink">{k}　{wan(v as number)} 贯</p>
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
            <p key={k} className="text-sm text-ink-light">{k}　{wan(asNum(gs[k]))}</p>
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
            <span className="w-28 font-kai text-[13px] text-ink-light">{k}</span>
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
  const focus = asStr(pick<unknown>(state, "active_focus", ""), "");
  const completed = asArr(pick<unknown[]>(state, "completed_focuses", []));

  return (
    <div className="space-y-3">
      <Section title="帝 国 修 正（legacies）">
        {Object.keys(legacies).length === 0 ? (
          <p className="text-sm text-dim">— 暂无生效修正 —</p>
        ) : (
          Object.keys(legacies).map((k) => {
            const L = asDict(legacies[k]);
            return <p key={k} className="text-sm text-ink-light">{k}（{L.active ? "生效中" : "待触发"}）</p>;
          })
        )}
      </Section>
      <Section title="机 制 槽">
        {Object.keys(mechs).length === 0 ? (
          <p className="text-sm text-dim">— 未设机制 —</p>
        ) : (
          Object.keys(mechs).map((k) => <p key={k} className="text-sm text-ink-light">{k}</p>)
        )}
      </Section>
      <Section title="宰 省 与 俸 禄">
        <p className="text-sm text-ink">俸禄：{asStr(pay.mode)}（本色 {Math.round(asNum(pay.grain_ratio) * 100)}% / 折银 {Math.round(asNum(pay.cash_ratio) * 100)}%）</p>
        <p className="text-sm text-ink-light">
          {wr.active ? `宰省浮费进行中：目标 ${wan(asNum(wr.target))}，已省 ${wan(asNum(wr.savings))}，余 ${asNum(wr.months_left)} 月` : "— 未行宰省浮费 —"}
        </p>
      </Section>
      <Section title="国 策">
        <p className="text-sm text-ink">施行：{focus || "—"}</p>
        {completed.length > 0 && <p className="text-sm text-dim">已竟：{completed.map((v) => asStr(v)).join(" / ")}</p>}
      </Section>
    </div>
  );
}

function ChronicleTab() {
  const state = useGameStore((s) => s.state);
  const dial = asArr(pick<unknown[]>(state, "dialogue_history", []));
  const memos = asArr(pick<unknown[]>(state, "memorials", []));
  const short = asArr(pick<unknown[]>(state, "short_term_log", []));

  return (
    <div className="space-y-3">
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
        memos.length === 0 ? <p className="text-sm text-dim">— 案上无事 —</p> : memos.map((m, i) => {
          const d = asDict(m);
          const title = asStr(d.title) || asStr(d.text, "（无题）");
          const body = asStr(d.body) || asStr(d.content);
          return (
            <p key={i} className="text-xs leading-relaxed text-ink-light">
              <span className="font-kai text-ink">{title}</span>
              {body && <span>　{body}</span>}
            </p>
          );
        })
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