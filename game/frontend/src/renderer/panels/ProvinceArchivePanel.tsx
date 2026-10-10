import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { getApiClient, type RegionBriefResult, type RegionRoute, type ArmyUnitReadout } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import ArmyDossier from "../components/ArmyDossier";
import { wan } from "../utils/format";

// 州路档案（左侧多页面抽屉）—— 地图仍可见，选中的**路**在抽屉里分页查阅。
//
// 为什么是「多页面」而不是一页堆完：路级信息天然分域（户口/民情/施政/军政/营建/财赋），
// 一页铺开会把最重要的读数淹掉；参考外部省份面板的成熟做法——**同一选中对象 + 页签切换**。
//
// 数据来源（**口径单点，前端不复制算法**）：
//   · /api/readouts::regions.routes     → 路级派生读数（core/region_brief.py 唯一权威）
//   · /api/readouts::regions.prefectures→ 州府级底盘（Σ府 == 路级，同一个 build_prefecture_brief）
//   · /api/readouts::regions.military   → 本路驻军汇总（route_military_summary）
//   · /api/readouts::army               → 编制单位（含月饷/月粮，unit_cost_readout）
//   · /api/readouts::plan.projects      → 本路在办工程（core/plan_readout.py）
//   · state.prefectures[路]             → 六类 POP / buildings / local_treasury（**读**快照字段）
//
// 层级纪律：**路 ≠ 州府**。本抽屉只声称「路的读数」；州府详情由既有「地方档案」承担，
// 点州府名即下钻到那里（不在这里把路级动态量（治安/城防/民心）冒充成府级值）。

type Dict = Record<string, unknown>;

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function numOrNull(v: unknown): number | null {
  const n = Number(v);
  return v === null || v === undefined || !Number.isFinite(n) ? null : n;
}
function num(v: unknown, dflt = 0): number {
  return numOrNull(v) ?? dflt;
}

/** 缺失呈现：统一「未定义」，不用空白或 0 冒充（AGENTS.md §3-3）。 */
function Undef() {
  return <span className="text-xs italic text-dim">未定义</span>;
}

function NumText({ v, unit = "", scale = 1 }: { v: number | null; unit?: string; scale?: number }) {
  if (v === null) return <Undef />;
  return <span>{wan(v * scale, unit)}</span>;
}

function Line({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-[13px]">
      <span className="shrink-0 text-dim">{label}</span>
      <span className="min-w-0 text-right text-ink">{children}</span>
    </div>
  );
}

function BlockTitle({ text, note }: { text: string; note?: string }) {
  return (
    <p className="mt-3 mb-1 font-kai text-[14px] font-bold tracking-[0.24em] text-red">
      {text}
      {note ? <span className="ml-2 text-[11px] font-normal tracking-normal text-dim">{note}</span> : null}
    </p>
  );
}

const POP_ORDER = ["农", "士绅", "工匠", "商人", "官僚", "兵"];

type PageKey = "overview" | "population" | "mood" | "governance" | "military" | "works" | "finance";

const PAGES: { key: PageKey; label: string }[] = [
  { key: "overview", label: "概览" },
  { key: "population", label: "人口" },
  { key: "mood", label: "民情" },
  { key: "governance", label: "施政" },
  { key: "military", label: "军政" },
  { key: "works", label: "营建" },
  { key: "finance", label: "财赋" },
];

/** buildings 有两种历史写法：扁平 {农田: 2} 与 {工坊: {lv: 2}}，此处只做归一展示。 */
function buildingRows(buildings: Dict): [string, number][] {
  return Object.entries(buildings)
    .map(([k, v]) => {
      const d = asDict(v);
      const lv = numOrNull(v) ?? numOrNull(d.lv) ?? numOrNull(d.level);
      return { k, lv };
    })
    .filter((x) => x.lv !== null && (x.lv as number) > 0)
    .map((x) => [x.k, x.lv as number] as [string, number])
    .sort((a, b) => b[1] - a[1]);
}

interface MilitaryRouteRow {
  route: string; units: number; troops: number; morale_weighted: number; arrears: number;
  cash_month: number | null; grain_month: number | null;
  city_defense: number | null; security: number | null; security_label: string | null;
  controlled_by: string | null;
}
interface MilitaryReadout { route: string | null; routes?: MilitaryRouteRow[] }

interface PlanProject {
  pid: string; name: string; route: string; status: string; status_label?: string;
  progress?: number; capacity?: number;
}

export default function ProvinceArchivePanel({ props }: { props?: Dict }) {
  const state = useGameStore((s) => s.state);
  const selected = useGameStore((s) => s.selected);
  const setSelected = useGameStore((s) => s.setSelected);
  const pushOverlay = useGameStore((s) => s.pushOverlay);

  // 选中对象：优先显式 props（从别的面板跳入）；否则只认舆图上的**路**选中
  // （州府选中走既有「地方档案」浮层，不在此重复一套府级口径）。
  const selRoute = selected && selected.kind === "circuit" ? selected.name : "";
  const route = String(props?.name ?? props?.route ?? selRoute);
  const [page, setPage] = useState<PageKey>("overview");
  const [brief, setBrief] = useState<RegionBriefResult | null>(null);
  const [mil, setMil] = useState<MilitaryReadout | null>(null);
  const [army, setArmy] = useState<ArmyUnitReadout[]>([]);
  const [projects, setProjects] = useState<PlanProject[]>([]);
  const [err, setErr] = useState("");
  const [dossier, setDossier] = useState<ArmyUnitReadout | null>(null);

  useEffect(() => {
    let alive = true;
    getApiClient()
      .readouts()
      .then((r) => {
        if (!alive) return;
        const rr = r as unknown as Dict;
        const regions = asDict(rr.regions);
        if (Array.isArray(regions.routes) && (regions.routes as unknown[]).length) {
          setBrief(regions as unknown as RegionBriefResult);
        } else {
          setErr("州路读数为空");
        }
        setMil((regions.military as MilitaryReadout | undefined) ?? null);
        setArmy(Array.isArray(rr.army) ? (rr.army as ArmyUnitReadout[]) : []);
        const plan = asDict(rr.plan);
        setProjects(Array.isArray(plan.projects) ? (plan.projects as PlanProject[]) : []);
      })
      .catch((e) => { if (alive) setErr(String((e as Error)?.message ?? e)); });
    return () => { alive = false; };
  }, []);

  const row: RegionRoute | null = useMemo(() => {
    const hit = brief?.routes?.find((x) => x.name === route);
    return hit ?? null;
  }, [brief, route]);

  const seats = useMemo(
    () => (brief?.prefectures ?? []).filter((x) => x.route === route),
    [brief, route]
  );
  const routeUnits = useMemo(
    () => army.filter((u) => u.station === route),
    [army, route]
  );
  const routeProjects = useMemo(
    () => projects.filter((x) => x.route === route),
    [projects, route]
  );
  const routeMil = mil?.routes?.find((x) => x.route === route) ?? null;

  const pref = asDict(asDict(pick(state, "prefectures", {}))[route]);
  const pops = asDict(pref.pops);
  const buildings = asDict(pref.buildings);

  if (!route) {
    return null;
  }

  function close() {
    setSelected(null);
  }

  function openSeat(name: string) {
    pushOverlay({ kind: "localarchive", title: name, props: { kind: "city", name, route } });
  }

  /** 顶部四个关键格（对应参考图：人口 / 民心 / 动乱 / 月税实收）。 */
  const metrics: { k: string; v: React.ReactNode }[] = [
    { k: "人口", v: <NumText v={row ? row.population : null} unit="口" /> },
    { k: "民心", v: <NumText v={row ? row.public_support : null} /> },
    { k: "动乱", v: <NumText v={row ? row.unrest : null} /> },
    { k: "月税实收", v: row && row.tax_month > 0 ? <span>{wan(row.tax_month, "贯")}</span> : <Undef /> }
  ];

  const pageBody = (() => {
    if (!row) {
      return <p className="py-6 text-center text-[13px] text-dim">该路读数不可用（后端 /api/readouts 未就绪）{err ? "：" + err : ""}</p>;
    }
    if (page === "overview") {
      return (
        <>
          <BlockTitle text="区域概述" />
          <Line label="所属政权">{row.controlled_by || "未定义"}</Line>
          <Line label="风险评定">
            <span>{row.risk_label}（{Math.round(row.risk_score)}）</span>
          </Line>
          {row.risk_hints.length ? (
            <ul className="mt-1 space-y-0.5 text-[12px] text-dim">
              {row.risk_hints.map((h, i) => <li key={i}>· {h}</li>)}
            </ul>
          ) : <p className="text-[12px] text-dim">· 未见风险提示</p>}
          <BlockTitle text="所属州府" note={"Σ府 == 路级（" + seats.length + " 席）"} />
          <div className="max-h-64 overflow-y-auto rounded border border-border/60">
            <table className="w-full text-[12.5px]">
              <thead className="sticky top-0 bg-card/95 text-dim">
                <tr>
                  <th className="px-2 py-1 text-left">州府</th>
                  <th className="px-2 py-1 text-right">人口</th>
                  <th className="px-2 py-1 text-right">户数</th>
                  <th className="px-2 py-1 text-right">月税</th>
                </tr>
              </thead>
              <tbody>
                {seats.map((s) => (
                  <tr key={s.name} onClick={() => openSeat(s.name)}
                    className="cursor-pointer border-t border-border/40 hover:bg-card/60">
                    <td className="px-2 py-0.5 text-ink">{s.name}</td>
                    <td className="px-2 py-0.5 text-right">{wan(s.population, "")}</td>
                    <td className="px-2 py-0.5 text-right">{wan(s.households, "")}</td>
                    <td className="px-2 py-0.5 text-right">{wan(s.tax_month, "")}</td>
                  </tr>
                ))}
                {seats.length === 0 ? (
                  <tr><td className="px-2 py-2 text-dim" colSpan={4}>（州府级读数不可用）</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <p className="mt-1 text-[11.5px] text-dim">点州府名下钻到「地方档案」（府级详情在那一处维护，避免两套口径）。</p>
        </>
      );
    }

    if (page === "population") {
      const hiddenEst = numOrNull(row.hidden_pop_est);
      // 已清丈 → 可读真值；未清丈 → 只用后端下发的**约值**（M9 脱敏口径）
      const hiddenReal = row.surveyed ? numOrNull(asDict(pops["农"]).hidden) : null;
      return (
        <>
          <BlockTitle text="户口" />
          <Line label="在籍人口">{wan(row.population, "口")}</Line>
          <Line label="在籍户数">{wan(row.households, "户")}</Line>
          <Line label={row.surveyed ? "隐户（已清丈）" : "隐户（约值）"}>
            {hiddenReal !== null ? <span>{wan(hiddenReal, "口")}</span>
              : hiddenEst !== null ? <span>{wan(hiddenEst, "口")}</span>
              : <Undef />}
          </Line>
          <Line label="垦田">{wan(row.land, "亩")}</Line>
          <BlockTitle text="六类 POP" note="路级派生镜像（真账在州府 seats）" />
          {(() => {
            const rows = POP_ORDER.map((cls) => {
              const slot = asDict(pops[cls]);
              return { cls, size: numOrNull(slot.size) };
            }).filter((x) => x.size !== null);
            if (!rows.length) return <Undef />;
            return (
              <div className="text-[13px]">
                {rows.map((x) => (
                  <Line key={x.cls} label={x.cls}><NumText v={x.size} unit="口" /></Line>
                ))}
              </div>
            );
          })()}
        </>
      );
    }

    if (page === "mood") {
      return (
        <>
          <BlockTitle text="民情读数" note="全部为路级量，不分摊到府" />
          <Line label="民情">{Math.round(row.mood)}</Line>
          <Line label="治理">{Math.round(row.govern)}</Line>
          <Line label="民心">{Math.round(row.public_support)}</Line>
          <Line label="士绅阻力">{Math.round(row.gentry_resistance)}</Line>
          <Line label="城防">{Math.round(row.city_defense)}</Line>
          <Line label="动乱">{Math.round(row.unrest)}</Line>
          <Line label="治安">
            {row.security === undefined || row.security === null ? <Undef /> : (
              <span>{Math.round(row.security)}{row.security_label ? "（" + row.security_label + "）" : ""}</span>
            )}
          </Line>
          <Line label="识字率">
            {row.literacy === null || row.literacy === undefined ? <Undef /> : <span>{Math.round(row.literacy)}</span>}
          </Line>
          <Line label="财政档">{Math.round(row.fiscal)}</Line>
        </>
      );
    }

    if (page === "governance") {
      const d = row.departments;
      const localTreasury = numOrNull(pref.local_treasury);
      return (
        <>
          <BlockTitle text="地方府库" />
          <Line label="本路府库">{localTreasury === null ? <Undef /> : <span>{wan(localTreasury, "贯")}</span>}</Line>
          <BlockTitle text="营造部门" note={d && d.mode ? (d.mode === "truth" ? "州府级真账" : "按人口权重派生") : ""} />
          {!d || d.mode === null ? (
            <Undef />
          ) : (
            <div className="text-[13px]">
              {d.departments.length === 0 ? <Undef /> : d.departments.map((x) => (
                <Line key={x.dept_id} label={(x.official ? "官有·" : "民间·") + (x.label || x.dept_id)}>
                  <span>劳力 {wan(numOrNull(x.labor) ?? 0, "")}　匠人 {wan(numOrNull(x.artisans) ?? 0, "")}</span>
                </Line>
              ))}
            </div>
          )}
        </>
      );
    }

    if (page === "military") {
      return (
        <>
          <BlockTitle text="本路驻军" note="兵额唯一真账 = Σ编制单位 Σbranches" />
          <Line label="编制单位">{routeMil ? String(routeMil.units) : <Undef />}</Line>
          <Line label="总兵力">{routeMil ? wan(routeMil.troops, "人") : <Undef />}</Line>
          <Line label="兵额加权士气">{routeMil ? String(routeMil.morale_weighted) : <Undef />}</Line>
          <Line label="累计欠饷">{routeMil ? wan(routeMil.arrears, "贯") : <Undef />}</Line>
          <Line label="月军饷">
            {routeMil && routeMil.cash_month !== null ? <span>{wan(routeMil.cash_month, "贯")}</span> : <Undef />}
          </Line>
          <Line label="月军粮">
            {routeMil && routeMil.grain_month !== null ? <span>{wan(routeMil.grain_month, "石")}</span> : <Undef />}
          </Line>
          <Line label="城防">{routeMil && routeMil.city_defense !== null ? String(routeMil.city_defense) : <Undef />}</Line>
          <BlockTitle text="编制单位" note="点「档案」看兵种/人员/粮饷/士气/训练" />
          <div className="max-h-72 overflow-y-auto rounded border border-border/60">
            <table className="w-full text-[12.5px]">
              <thead className="sticky top-0 bg-card/95 text-dim">
                <tr>
                  <th className="px-2 py-1 text-left">番号</th>
                  <th className="px-2 py-1 text-left">军籍</th>
                  <th className="px-2 py-1 text-right">兵额</th>
                  <th className="px-2 py-1 text-right">欠饷</th>
                  <th className="px-2 py-1 text-right">档案</th>
                </tr>
              </thead>
              <tbody>
                {routeUnits.map((u) => (
                  <tr key={u.unit_id} className="border-t border-border/40 hover:bg-card/60">
                    <td className="px-2 py-0.5 text-ink">{u.army_name || u.name}</td>
                    <td className="px-2 py-0.5">{u.tier}</td>
                    <td className="px-2 py-0.5 text-right">{wan(u.troops, "")}</td>
                    <td className="px-2 py-0.5 text-right">{wan(numOrNull(u.arrears) ?? 0, "")}</td>
                    <td className="px-2 py-0.5 text-right">
                      <button type="button"
                        aria-label={"查看" + (u.army_name || u.name) + "档案"}
                        onClick={() => setDossier(u)}
                        className="rounded border border-gold/40 px-1.5 py-0.5 text-[11.5px] text-dim hover:bg-gold/10 hover:text-ink">
                        档案
                      </button>
                    </td>
                  </tr>
                ))}
                {routeUnits.length === 0 ? (
                  <tr><td className="px-2 py-2 text-dim" colSpan={5}>（本路无驻军）</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </>
      );
    }

    if (page === "works") {
      const brows = buildingRows(buildings);
      return (
        <>
          <BlockTitle text="本路营造" note={brows.length + " 项"} />
          {brows.length === 0 ? <Undef /> : (
            <div className="text-[13px]">
              {brows.map(([n, lv]) => (
                <Line key={n} label={n}><span>Lv{lv}</span></Line>
              ))}
            </div>
          )}
          <BlockTitle text="在办工程" note={routeProjects.length + " 项"} />
          {routeProjects.length === 0 ? <Undef /> : (
            <div className="text-[13px]">
              {routeProjects.map((p) => (
                <Line key={p.pid} label={p.name}>
                  <span>{p.status_label || p.status}
                    {typeof p.progress === "number" ? "　" + Math.round(p.progress) + "%" : ""}</span>
                </Line>
              ))}
            </div>
          )}
        </>
      );
    }

    return (
      <>
        <BlockTitle text="财赋" />
        <Line label="月税实收">{row.tax_month > 0 ? <span>{wan(row.tax_month, "贯")}</span> : <Undef />}</Line>
        <Line label="占全国月税">{row.tax_share > 0 ? <span>{(row.tax_share * 100).toFixed(1) + "%"}</span> : <Undef />}</Line>
        <Line label="驻军月饷">
          {row.army_cash_month > 0 ? <span>{wan(row.army_cash_month, "贯")}</span> : <Undef />}
        </Line>
        <Line label="驻军月粮">
          {row.army_grain_month > 0 ? <span>{wan(row.army_grain_month, "石")}</span> : <Undef />}
        </Line>
        <BlockTitle text="粮储" />
        <Line label="粮产">{wan(row.grain_year, "石")}/年</Line>
        <Line label="存粮">{wan(row.grain_stock, "石")}</Line>
        <Line label="粮储安全垫">
          {row.grain_months === null || row.grain_months === undefined ? <Undef /> : (
            <span>{row.grain_months.toFixed(2)} 月</span>
          )}
        </Line>
      </>
    );
  })();

  return (
    <>
      <aside
        role="complementary"
        aria-label={"州路档案 " + route}
        className="pointer-events-auto fixed bottom-3 left-3 top-16 z-40 flex w-[min(440px,92vw)] overflow-hidden rounded-lg border border-gold/50 bg-paper/95 shadow-2xl backdrop-blur"
      >
        {/* 左导航：同一选中对象下的**多页面**切换（参考图做法） */}
        <nav className="flex w-[76px] shrink-0 flex-col gap-1 border-r border-border/60 bg-card/40 p-2">
          <p className="mb-1 text-[11px] tracking-widest text-dim">查阅</p>
          {PAGES.map((pg) => (
            <button
              key={pg.key}
              type="button"
              onClick={() => setPage(pg.key)}
              aria-pressed={pg.key === page}
              className={pg.key === page
                ? "rounded bg-card px-2 py-1.5 text-left text-[12.5px] text-ink"
                : "rounded px-2 py-1.5 text-left text-[12.5px] text-dim hover:bg-card/60"}
            >
              {pg.label}
            </button>
          ))}
        </nav>

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-start justify-between gap-2 border-b border-border/60 px-3 py-2">
            <div className="min-w-0">
              <p className="text-[11px] tracking-widest text-dim">州路档案</p>
              <p className="truncate font-kai text-[17px] font-bold text-ink">{route}</p>
              <p className="text-[11.5px] text-dim">{row ? row.controlled_by : "读数未就绪"}</p>
            </div>
            <button
              type="button"
              onClick={close}
              aria-label="关闭州路档案"
              className="shrink-0 rounded p-1 text-ink-light transition hover:bg-gold-light hover:text-ink"
            >
              <X size={18} />
            </button>
          </div>

          <div className="grid grid-cols-4 border-b border-border/60">
            {metrics.map((m) => (
              <div key={m.k} className="border-r border-border/40 px-2 py-1.5 last:border-r-0">
                <p className="text-[11px] text-dim">{m.k}</p>
                <p className="text-[13px] text-ink">{m.v}</p>
              </div>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto px-3 pb-3">{pageBody}</div>
        </div>
      </aside>



      {/* 单军档案：与全军面板、地方军政面板**共用同一实现** */}
      <ArmyDossier unit={dossier} onClose={() => setDossier(null)} />
    </>
  );
}
