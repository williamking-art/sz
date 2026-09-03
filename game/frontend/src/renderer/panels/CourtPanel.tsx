import { useGameStore, pick } from "../store/gameStore";
import { wan, humanizeCoin } from "../utils/format";
import constants from "../data/constants.json";

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

  // ---- 外患态度（对齐 Tk _ext_att：external_regimes.attitude，缺省 50） ----
  const extRegimes = asDict(pick(state, "external_regimes", {}));
  const extAtt = (key: string): number =>
    Math.round(asNum(asDict(extRegimes[key]).attitude, 50));

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
  const alliance = pick(state, "alliance_jin_liao", false) === true;
  const bw = asNum(pick(state, "decree_bandwidth", 0));
  const pending = pick<unknown[]>(state, "pending_decrees", []).length;

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
      `岁币 ${humanizeCoin(asNum(asDict(pick(state, "treaties", {})).岁币))}`
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

  return (
    <div className="space-y-5">
      {/* 御容卡 */}
      <div className="flex gap-4 rounded-lg border border-gold/50 bg-card p-4">
        <div className="flex h-28 w-24 shrink-0 items-center justify-center rounded border-2 border-gold bg-paper/70">
          <span className="font-kai text-2xl tracking-widest text-red">御容</span>
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
        </div>
      )}

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
                {active && asNum(l.progress) > 0 && (
                  <Meter value={asNum(l.progress)} label="消除进度" />
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
