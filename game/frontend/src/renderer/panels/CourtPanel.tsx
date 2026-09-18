import { useState } from "react";
import { useGameStore, pick, type PanelKind } from "../store/gameStore";
import { getApiClient } from "../api/client";
import { wan, humanizeCoin } from "../utils/format";
import constants from "../data/constants.json";

/** 朝局简报跳转语义（core.briefing 的 goto）→ 浮层目标（迁移补齐：Tk `_render_briefing`） */
const BRIEFING_GOTO: Record<string, { kind: PanelKind; title: string }> = {
  decree: { kind: "decree", title: "拟旨" },
  audience: { kind: "ministers", title: "群臣" },
  tech: { kind: "tech", title: "科技" },
  army: { kind: "military", title: "军政机务" },
  todo: { kind: "todo", title: "在办事务" }
};

// 朝堂总览 —— 对齐 game/ui/panels_core.py::_panel_overview（L743）
// 纯展示面板：Tk 版无后端交互动作，数据全部取自 state 快照与 constants.json。
// 御容立绘：Tk 版按年号时节切换本地图片（ui/assets.emperor_portrait），
// HTTP 契约无图片端点，以金框御容牌位等价呈现；文字字段与 Tk 版 1:1。
type Dict = Record<string, unknown>;

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}
function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}

/** 仪表条：对齐 theme.progress_bar 取色（ratio 分段）。 */
function Meter({ value, max = 100, label }: { value: number; max?: number; label?: string }) {
  const ratio = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  const fill =
    ratio >= 0.75 ? "#3f6655" : ratio >= 0.4 ? "#5a5240" : ratio >= 0.2 ? "#8a671e" : "#a24332";
  return (
    <div className="flex items-center gap-3 py-1">
      {label && <span className="w-28 shrink-0 text-sm text-ink-light">{label}</span>}
      <div className="h-3 flex-1 overflow-hidden rounded-full border border-gold/60 bg-[#efe2c4]">
        <div className="h-full rounded-full transition-all" style={{ width: `${ratio * 100}%`, background: fill }} />
      </div>
      <span className="w-24 shrink-0 text-right text-xs text-dim">
        {Math.round(value)} / {max} ({Math.round(ratio * 100)}%)
      </span>
    </div>
  );
}

function SectionTitle({ text }: { text: string }) {
  return <p className="font-kai text-[15px] font-bold tracking-[0.3em] text-red">{text}</p>;
}

export default function CourtPanel() {
  const state = useGameStore((s) => s.state);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const readouts = useGameStore((s) => s.readouts);
  // 月折（奏报摘要）：按需生成，避免每次开面板都耗 AI
  const [monthly, setMonthly] = useState<string | null>(null);
  const [monthlyBusy, setMonthlyBusy] = useState(false);
  async function genMonthly() {
    if (monthlyBusy) return;
    setMonthlyBusy(true);
    try {
      const res = await getApiClient().monthlyReport();
      setMonthly(res.report || "（本回合无月折）");
    } catch (e) {
      console.error("[monthly_report]", e);
      setMonthly("月折生成失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setMonthlyBusy(false);
    }
  }
  if (!state) {
    return <p className="py-10 text-center text-dim">尚未开局，无朝堂可览。</p>;
  }

  // ---- 御容信息（对齐 Tk：年龄段按年份、常服按月份） ----
  const eraName = asStr(pick(state, "era_name", ""));
  const year = asNum(pick(state, "year", 0));
  const month = asNum(pick(state, "month", 1));
  const health = asNum(pick(state, "emperor_health", 0));
  const prestige = asNum(pick(state, "prestige", 0));
  const emperorName = asStr(pick(state, "emperor_name", "赵佶"));
  const ageTxt = year <= 1115 ? "青年" : year <= 1125 ? "壮年" : "暮年";
  const seasonTxt = [11, 12, 1, 2, 3].includes(month) ? "冬常服" : "夏常服";

  // ---- 中枢六部均效 ----
  const yamen = asDict(pick(state, "yamen", {}));
  const effs = Object.values(yamen).map((y) => asNum(asDict(y).efficiency));
  const effY = effs.length ? effs.reduce((a, b) => a + b, 0) / effs.length : 0;

  // ---- 外患态度（真值在 state.external；external_regimes 仅静态兜底）----
  // 审查修复：原只读 external_regimes.attitude，而全部玩法写入（诏令效果
  // external_jin/liao/xixia、事件、岁币结算、金入侵）都落在 state.external →
  // 玩家下诏改态度后本仪表数字不变（external_regimes 只做 ±2 月随机游走）。
  const extLive = asDict(pick(state, "external", {}));
  const extRegimes = asDict(pick(state, "external_regimes", {}));
  const extAtt = (key: string): number =>
    Math.round(asNum(
      asDict(extLive[key]).attitude ?? asDict(extRegimes[key]).attitude, 50));

  // ---- 派系 ----
  const factions = asDict(pick(state, "factions", {}));
  const factionRows = (constants.faction_names as string[])
    .map((name) => ({ name, f: asDict(factions[name]) }))
    .filter((r) => Object.keys(r.f).length > 0);

  // ---- 国力概览六卡 ----
  const land = asDict(pick(state, "land", {}));
  const jiaozi = asDict(pick(state, "jiaozi", {}));
  const maritime = asDict(pick(state, "maritime", {}));
  const exam = asDict(pick(state, "exam", {}));
  const tech = asDict(pick(state, "tech", {}));
  const alliance = Boolean(pick<boolean>(state, "alliance_jin_liao", false));
  const bw = asNum(pick(state, "decree_bandwidth", 0));
  // D 修复：pending_decrees 若为非数组（异常快照/旧档）时 `.length` 为 undefined，
  // `bw - pending` 变 NaN。此处先做数组守卫。
  const pendingRaw = pick<unknown>(state, "pending_decrees", []);
  const pending = Array.isArray(pendingRaw) ? pendingRaw.length : 0;

  // 岁币口径（审查修复）：treaties 形状为 {势力: [{type, terms, turn, year, month}]}，
  // 原读 treaties.岁币（该键不存在）→ 恒显示 0，与国库实际岁币支出相矛盾。
  // 现按 type=="岁币" 条目取其 terms.tier（增/减/停）；无此类条约即"未纳"。
  // 注：实际支出金额见户部会计（/api/readouts::finance.sui_gong，AccountingPanel 已用）。
  const suiGongText = (() => {
    const parts: string[] = [];
    for (const [regime, list] of Object.entries(asDict(pick(state, "treaties", {})))) {
      for (const t of (Array.isArray(list) ? list : [])) {
        const d = asDict(t);
        if (asStr(d.type) === "岁币") {
          parts.push(`${regime}${asStr(asDict(d.terms).tier, "已立")}`);
        }
      }
    }
    return parts.length ? parts.join("、") : "未纳";
  })();

  const cells: [string, string[]][] = [
    ["田亩户籍", [
      `垦田 ${wan(asNum(land.cultivated), "亩")}`,
      `隐漏 ${Math.round(asNum(land.hidden_rate) * 100)}%`,
      `在籍 ${wan(asNum(land.households), "户")}`
    ]],
    ["金融货币", [
      `交子 ${humanizeCoin(asNum(jiaozi.issued))}`,
      `信用 ${Math.round(asNum(jiaozi.trust))}`,
      `海贸 ${asNum(maritime.open) ? "开" : "禁"}`
    ]],
    ["科举学校", [
      `科举 ${asNum(exam.open) ? "开" : "停"}`,
      `取士 ${asStr(exam.mode, "词学")}`,
      `庠序 ${Math.round(asNum(exam.schools))}`
    ]],
    ["科技工技", [
      `总纲 ${Math.round(asNum(tech.level))}`,
      `火药 ${Math.round(asNum(tech.gunpowder))}`,
      `水利 ${Math.round(asNum(tech.hydraulics))}`
    ]],
    ["外交", [
      `辽 ${extAtt("辽")} · 夏 ${extAtt("西夏")}`,
      alliance ? "海上之盟：缔结" : "海上之盟：未缔",
      `岁币 ${suiGongText}`
    ]],
    ["龙体·皇威", [
      `御体 ${Math.round(health)}`,
      `皇威 ${Math.round(prestige)}`,
      `诏令 ${bw - pending}/${bw}`
    ]]
  ];

  // ---- 开局邸报 / 帝国修正 / 当前事件 ----
  const gazette = asDict(pick(state, "opening_gazette", {}));
  const legacies = asDict(pick(state, "legacies", {}));
  const activeEvents = pick<Dict[]>(state, "active_events", []);

  // 动态匹配宋徽宗四时御容画像 (青年/中年/老年 × 冬夏)
  const ageKey = year <= 1115 ? "young" : year <= 1125 ? "middle" : "old";
  const seasonKey = [11, 12, 1, 2, 3].includes(month) ? "winter" : "summer";
  const portraitUrl = `./portraits/emperor_${ageKey}_${seasonKey}.png`;

  return (
    <div className="space-y-5">
      {/* 御容卡 */}
      <div className="sz-card flex gap-4 p-4">
        <div className="relative h-36 w-28 shrink-0 overflow-hidden rounded border-2 border-gold bg-paper/70 shadow-sm">
          <img
            src={portraitUrl}
            alt="大宋皇帝御容"
            className="h-full w-full object-cover object-top"
          />
          <img
            src="/images/seal.png"
            alt=""
            className="absolute bottom-1 right-1 h-6 w-6 opacity-90"
          />
        </div>
        <div className="flex flex-col justify-center gap-1.5">
          <p className="font-kai text-lg tracking-[0.2em] text-ink">
            御 容 · 奉天承运
          </p>
          <p className="text-sm text-ink">
            {eraName}{year}年{month}月 · 皇帝{emperorName}
          </p>
          <p className="text-sm text-ink">
            御体：{Math.round(health)}　皇威：{Math.round(prestige)}
          </p>
          <p className="text-sm text-dim">
            天潢：{ageTxt}天子 · 御着{seasonTxt}
          </p>
          <div className="mt-2 flex items-center gap-2">
            <button
              onClick={() => pushOverlay({ kind: "ministers", title: "中枢群臣 · 列位卿僚" })}
              className="sz-btn-ghost rounded px-3 py-1 text-xs font-bold"
            >
              御览中枢班列
            </button>
            <button
              onClick={() => pushOverlay({ kind: "audience", title: "御前召对", props: { minister: "韩忠彦", role: "尚书左仆射兼门下侍郎" } })}
              className="sz-btn-primary rounded px-3 py-1 text-xs font-bold"
            >
              召宰执入对
            </button>
          </div>
        </div>
      </div>

      {/* 中枢六部 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="中 枢 六 部" />
        <div className="mt-1.5">
          <Meter value={effY} label="衙门均效" />
        </div>
      </div>

      {/* 外患态度 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="外 患 态 度" />
        <div className="mt-1.5">
          <Meter value={extAtt("辽")} label="辽" />
          <Meter value={extAtt("西夏")} label="西夏" />
          <Meter value={extAtt("大理")} label="大理" />
        </div>
      </div>

      {/* 派系 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="派 系" />
        <div className="mt-1.5">
          {factionRows.map((r) => (
            <Meter
              key={r.name}
              value={asNum(r.f.influence)}
              label={`${r.name}·${asStr(r.f.leader, "—")}`}
            />
          ))}
        </div>
      </div>

      {/* 国力概览 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="国 力 概 览" />
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {cells.map(([title, lines]) => (
            <div key={title} className="rounded border border-gold/30 bg-card p-2.5">
              <p className="font-kai text-sm font-bold text-ink">{title}</p>
              {lines.map((l, i) => (
                <p key={i} className="text-xs leading-relaxed text-dim">{l}</p>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* 开局邸报 */}
      {Object.keys(gazette).length > 0 && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
          <SectionTitle text="开 局 邸 报" />
          <p className="mt-1.5 text-center font-kai text-base tracking-widest text-ink">
            {asStr(gazette.header)} · {asStr(gazette.era)}
          </p>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-ink">
            {asStr(gazette.body)}
          </p>
          {(gazette.tasks as Dict[] | undefined)?.map((t, i) => (
            <p key={i} className="py-0.5 text-sm text-ink">
              {t.urgent ? "●" : "○"} {asStr(t.title)}：{asStr(t.desc)}
            </p>
          ))}
          {/* 邸报按语（迁移补齐：Tk `panels_core.py:902` 的 gz.hint 此前未渲染） */}
          {asStr(gazette.hint) && (
            <p className="mt-1.5 border-t border-gold/20 pt-1.5 font-kai text-xs leading-relaxed text-dim">
              〔按语〕{asStr(gazette.hint)}
            </p>
          )}
        </div>
      )}

      {/* 朝局简报 · 可行动项（迁移补齐：原 Tk `_render_briefing`；数据 readouts.briefing，
          纯程序派生零 AI，点「前往」跳对应面板） */}
      {(readouts?.briefing ?? []).length > 0 && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
          <SectionTitle text="朝 局 简 报" />
          <div className="mt-1.5 space-y-1.5">
            {(readouts?.briefing ?? []).map((b) => (
              <div
                key={b.key}
                className={`rounded border p-2.5 ${
                  b.urgent ? "border-red/50 bg-red/5" : "border-gold/30 bg-card"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className={`font-kai text-sm font-bold ${b.urgent ? "text-red" : "text-ink"}`}>
                    {b.urgent ? "●" : "○"} {b.title}
                  </p>
                  {BRIEFING_GOTO[b.goto] && (
                    <button
                      onClick={() => pushOverlay(BRIEFING_GOTO[b.goto])}
                      className="shrink-0 rounded border border-gold/50 bg-paper px-2 py-0.5 font-kai text-xs text-ink transition hover:bg-gold-light/40"
                    >
                      前往 ▸
                    </button>
                  )}
                </div>
                <p className="mt-1 text-xs leading-relaxed text-dim">{b.desc}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 奏报摘要（月折）——迁移补齐：原 Tk 拟旨面板「奏报摘要」tab 的月折正文 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <div className="flex items-center justify-between">
          <SectionTitle text="奏 报 摘 要" />
          <button
            onClick={genMonthly}
            disabled={monthlyBusy}
            className="rounded border border-gold/50 bg-paper/70 px-2.5 py-0.5 font-kai text-xs text-ink transition hover:bg-gold-light/40 disabled:opacity-60"
          >
            {monthlyBusy ? "推演中…" : "生成月折"}
          </button>
        </div>
        {monthly ? (
          <p className="mt-1.5 whitespace-pre-wrap font-kai text-sm leading-relaxed text-ink">
            {monthly}
          </p>
        ) : (
          <p className="mt-1.5 text-xs text-dim">
            点「生成月折」请知制诰综叙本月朝局（AI 未接入时走本地模板，不伪造）。
          </p>
        )}
      </div>

      {/* 帝国修正 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="帝 国 修 正" />
        <div className="mt-1.5 space-y-1.5">
          {Object.values(legacies).map((lv) => {
            const l = asDict(lv);
            const active = l.active === true && l.cleared !== true;
            return (
              <div key={asStr(l.key)} className="rounded border border-gold/30 bg-card p-2.5">
                <p className="font-kai text-sm font-bold text-ink">
                  {active ? "◆" : "✓"} {asStr(l.name)}
                </p>
                <p className="text-xs leading-relaxed text-dim">
                  {active ? asStr(l.desc) : `已消除：${asStr(l.clear_desc)}`}
                </p>
                {/* 后端 legacies[*].progress 为 0~1 小数（core/legacy_mechanic.py），
                    而 Meter 按 0~100 计比值 → 原样传入使进度条恒贴底（误导为"毫无进展"）。
                    此处换算为百分数。 */}
                {active && asNum(l.progress) > 0 && (
                  <Meter value={asNum(l.progress) * 100} label="消除进度" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 当前事件 */}
      {activeEvents.length > 0 && (
        <div className="rounded-lg border border-red/40 bg-paper/60 p-3">
          <SectionTitle text="边 报 急 务" />
          {activeEvents.map((ev, i) => (
            <p key={i} className="py-0.5 text-sm text-ink">● {asStr(ev.message ?? ev.title)}</p>
          ))}
        </div>
      )}
    </div>
  );
}
