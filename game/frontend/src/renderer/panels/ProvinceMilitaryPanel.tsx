import { useEffect, useMemo, useState } from "react";
import { getApiClient } from "../api/client";
import { useGameStore } from "../store/gameStore";
import { wan } from "../utils/format";

// 省级军政 —— 点击舆图的路（省），或由「地方档案」跳入。
// 数据来源：/api/readouts::regions.military（core/region_brief.py::route_military_summary，**只读派生**）
//   · 兵额唯一真账 = ArmyUnit.troops（= Σbranches）；军饷/军粮复用 region_brief 逐路派生（口径同源）
// 军令（八按钮）现状：**置灰**。原因（方案 §3.2，已核实）：
//   后端无军事端点，前端命令里军令只有 `approve_ai_action`（批红 AI 提议）
//   → "点一下就执行"需要先定：A 准/驳既有提议（零新写路径）｜B 新增玩家主动军令通道（触铁律边界）。
//   一旦定案，按钮只需把 payload 换成 {army, action, unit_id, scale|target} 即可接入既有通道。
type Dict = Record<string, unknown>;

interface MUnit {
  unit_id: string; name: string; army_name: string; tier: string; station: string;
  defense_line: string; troops: number; morale: number; training: number; arrears: number;
  org_arm: string;
  branches: Record<string, number>;
}
interface MRoute {
  route: string; units: number; troops: number; morale_weighted: number; arrears: number;
  cash_month: number | null; grain_month: number | null;
  city_defense: number | null; security: number | null; security_label: string | null;
  controlled_by: string | null;
}
interface MNation { routes: number; units: number; troops: number; arrears: number; cash_month: number; grain_month: number }
interface Military { route: string | null; routes?: MRoute[]; nation: MNation }

// **参考图的 8 个按钮**（严格对齐，不自行增减）：
//   地图调度 / 扩编 / 拆分 / 合并 ｜ 整编 / 换帅 / 裁撤 / 改名
// 注：命令层另有 `act="操练"`（`_apply_military_dispatch` 支持），但**参考图没有这个按钮**，
//     故不在此暴露（避免"我改了需求"——2026-09-27 用户指出此处多加了一键，已改回 8 个）。
const ACTIONS = ["地图调度", "扩编", "拆分", "合并", "整编", "换帅", "裁撤", "改名"];

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}

export default function ProvinceMilitaryPanel({ props }: { props?: Dict }) {
  const initial = String(props?.route ?? props?.name ?? "");
  const state = useGameStore((s) => s.state);
  const [mil, setMil] = useState<Military | null>(null);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState<"route" | "nation">("route");
  const [route, setRoute] = useState(initial);
  const [picked, setPicked] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [dest, setDest] = useState("");
  const [newName, setNewName] = useState("");
  const [mergePick, setMergePick] = useState("");
  const [commander, setCommander] = useState("");

  useEffect(() => {
    let alive = true;
    getApiClient()
      .readouts()
      .then((r) => {
        if (!alive) return;
        const m = ((r as { regions?: { military?: Military } } | null)?.regions?.military) ?? null;
        setMil(m);
        if (!m) setErr("（军政读数不可用）");
        else if (!route && m.routes?.length) setRoute(m.routes[0].route);
      })
      .catch((e) => alive && setErr(`（军政读数不可用：${String((e as Error)?.message ?? e)}）`));
    return () => { alive = false; };
  }, []);

  const routes = mil?.routes ?? [];
  const routeRow = useMemo(() => routes.find((r) => r.route === route), [routes, route]);
  const routeUnits: MUnit[] = useMemo(() => {
    // 由 state.army_units 投影（快照含 army_units；字段与 ArmyUnit 对齐）
    const list = (state as unknown as { army_units?: Dict[] })?.army_units ?? [];
    return list
      .map(asDict)
      .filter((u) => String(u.station ?? "") === route)
      .map((u) => ({
        unit_id: String(u.unit_id ?? ""),
        name: String(u.name ?? ""),
        army_name: String(u.army_name ?? ""),
        tier: String(u.tier ?? ""),
        station: String(u.station ?? ""),
        defense_line: String(u.defense_line ?? ""),
        org_arm: String(u.org_arm ?? ""),
        troops: Object.values(asDict(u.branches)).reduce<number>((a, b) => a + (Number(b) || 0), 0),
        morale: Number(u.morale ?? 0) || 0,
        training: Number(u.training ?? 0) || 0,
        arrears: Number(u.arrears ?? 0) || 0,
        branches: Object.fromEntries(Object.entries(asDict(u.branches)).map(([k, v]) => [k, Number(v) || 0]))
      }))
      .sort((a, b) => b.troops - a.troops);
  }, [state, route]);

  const sel = routeUnits.find((u) => u.unit_id === picked) ?? routeUnits[0];

  // **参考图 8 键全部已实现**（2026-09-27）：与 `core/commands.py::_MILITARY_BUTTON_ACTS` 严格一致。
  // 「合并」的可行性是**数据相关**的：须本路同军籍 ≥2 支（通常先「拆分」出一支）。
  const mergeOptions = routeUnits.filter((u) => u.unit_id !== sel?.unit_id && u.tier === sel?.tier);
  const CAN_ORDER: Record<string, boolean> = {
    "整编": true, "扩编": true, "地图调度": true, "拆分": true,
    "合并": mergeOptions.length > 0, "换帅": true, "裁撤": true, "改名": true
  };
  const destOptions = routes.map((r) => r.route).filter((n) => n !== route);

  async function doOrder(button: string) {
    if (!sel || busy) return;
    setBusy(true);
    try {
      const r = await getApiClient().action("issue_military_order", {
        unit_id: sel.unit_id, button, scale: 3,
        target: button === "地图调度" ? (dest || destOptions[0] || "") : "",
        new_name: (button === "改名" || button === "拆分") ? newName : "",
        merge_unit_id: button === "合并" ? (mergePick || mergeOptions[0]?.unit_id || "") : "",
        commander: button === "换帅" ? commander : ""
      });
      setMsg(String((r as { message?: string })?.message ?? "已饬行。"));
      const rr = await getApiClient().readouts();
      const m = ((rr as { regions?: { military?: Military } } | null)?.regions?.military) ?? null;
      if (m) setMil(m);
    } catch (e) {
      setMsg(`未成：${String((e as Error)?.message ?? e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between border-b border-border pb-2">
        <div>
          <div className="font-kai text-[19px] font-bold tracking-[0.28em] text-ink">地方军政</div>
          <div className="mt-1 text-[12px] text-dim">
            路（省）级 · 编制单位 {routeUnits.length} · {err}
          </div>
        </div>
        <div className="flex gap-2 text-[13px]">
          {(["route", "nation"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded border px-2 py-0.5 ${tab === t ? "border-gold bg-card text-ink" : "border-border text-dim"}`}
            >
              {t === "route" ? "本路军政" : "全国总览"}
            </button>
          ))}
        </div>
      </div>

      {tab === "nation" ? (
        <section>
          <div className="mb-1 font-kai text-[13.5px] font-bold text-gold-dark">全国军政总览</div>
          <div className="grid grid-cols-4 gap-2">
            {[
              { k: "路数", v: mil?.nation.routes ?? "—" },
              { k: "编制单位", v: mil?.nation.units ?? "—" },
              { k: "兵额", v: mil ? wan(mil.nation.troops, "人") : "—" },
              { k: "欠饷", v: mil ? wan(mil.nation.arrears, "贯") : "—" }
            ].map((it) => (
              <div key={it.k} className="rounded border border-border/60 bg-card/60 px-2 py-1.5">
                <div className="text-[11.5px] text-dim">{it.k}</div>
                <div className="font-kai text-[15px]">{it.v}</div>
              </div>
            ))}
          </div>
          <div className="mt-2 max-h-72 overflow-y-auto rounded border border-border/60">
            <table className="w-full text-[12.5px]">
              <thead className="sticky top-0 bg-card/95 text-dim">
                <tr>
                  <th className="px-2 py-1 text-left">路</th>
                  <th className="px-2 py-1 text-right">单位</th>
                  <th className="px-2 py-1 text-right">兵额</th>
                  <th className="px-2 py-1 text-right">士气</th>
                  <th className="px-2 py-1 text-right">欠饷</th>
                  <th className="px-2 py-1 text-right">月饷</th>
                  <th className="px-2 py-1 text-right">治安</th>
                </tr>
              </thead>
              <tbody>
                {routes.map((r) => (
                  <tr
                    key={r.route}
                    className="cursor-pointer border-t border-border/40 hover:bg-card/60"
                    onClick={() => { setRoute(r.route); setTab("route"); }}
                  >
                    <td className="px-2 py-0.5">{r.route}</td>
                    <td className="px-2 py-0.5 text-right">{r.units}</td>
                    <td className="px-2 py-0.5 text-right">{wan(r.troops, "")}</td>
                    <td className="px-2 py-0.5 text-right">{r.morale_weighted}</td>
                    <td className="px-2 py-0.5 text-right">{wan(r.arrears, "")}</td>
                    <td className="px-2 py-0.5 text-right">{r.cash_month === null ? "—" : wan(r.cash_month, "")}</td>
                    <td className="px-2 py-0.5 text-right">{r.security ?? "—"}{r.security_label ? `（${r.security_label}）` : ""}</td>
                  </tr>
                ))}
                {routes.length === 0 ? (
                  <tr><td className="px-2 py-2 text-dim" colSpan={7}>（读数未就绪）</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[12.5px] text-dim">路</span>
            <select
              value={route}
              onChange={(e) => { setRoute(e.target.value); setPicked(""); }}
              className="rounded border border-border bg-card px-2 py-1 text-[13px]"
            >
              {routes.map((r) => <option key={r.route} value={r.route}>{r.route}</option>)}
            </select>
            {routeRow ? (
              <span className="text-[12px] text-dim">
                单位 {routeRow.units} · 兵 {wan(routeRow.troops, "人")} · 士气 {routeRow.morale_weighted} ·
                欠饷 {wan(routeRow.arrears, "贯")} · 城防 {routeRow.city_defense ?? "—"} · 治安 {routeRow.security ?? "—"}
                {routeRow.security_label ? `（${routeRow.security_label}）` : ""}
              </span>
            ) : null}
          </div>

          {/* 编制单位选择器（对应参考图「北直隶野战军·63700人 ▾」） */}
          <section>
            <div className="mb-1 font-kai text-[13.5px] font-bold text-gold-dark">
              编制单位 · {routeUnits.length} <span className="text-[11px] text-dim">（军令对象＝编制单位，非兵种）</span>
            </div>
            <div className="max-h-56 overflow-y-auto rounded border border-border/60">
              <table className="w-full text-[12.5px]">
                <thead className="sticky top-0 bg-card/95 text-dim">
                  <tr>
                    <th className="px-2 py-1 text-left">番号</th>
                    <th className="px-2 py-1 text-left">军籍</th>
                    <th className="px-2 py-1 text-right">兵额</th>
                    <th className="px-2 py-1 text-right">士气</th>
                    <th className="px-2 py-1 text-right">欠饷</th>
                    <th className="px-2 py-1 text-left">所属司</th>
                  </tr>
                </thead>
                <tbody>
                  {routeUnits.map((u) => (
                    <tr
                      key={u.unit_id}
                      onClick={() => setPicked(u.unit_id)}
                      className={`cursor-pointer border-t border-border/40 hover:bg-card/60 ${sel?.unit_id === u.unit_id ? "bg-card" : ""}`}
                    >
                      <td className="px-2 py-0.5">{u.army_name || u.name}</td>
                      <td className="px-2 py-0.5">{u.tier}</td>
                      <td className="px-2 py-0.5 text-right">{wan(u.troops, "")}</td>
                      <td className="px-2 py-0.5 text-right">{u.morale}</td>
                      <td className="px-2 py-0.5 text-right">{wan(u.arrears, "")}</td>
                      <td className="px-2 py-0.5">{u.org_arm || "—"}</td>
                    </tr>
                  ))}
                  {routeUnits.length === 0 ? (
                    <tr><td className="px-2 py-2 text-dim" colSpan={6}>（本路暂无可列编制单位）</td></tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            {sel ? (
              <div className="mt-1 text-[11.5px] leading-relaxed text-dim">
                选中：<span className="text-ink">{sel.army_name || sel.name}</span>（{sel.tier}·{sel.station}）｜
                兵种构成：{Object.entries(sel.branches).map(([k, v]) => `${k} ${wan(v, "")}`).join("｜") || "—"}｜
                训练 {sel.training}｜防区 {sel.defense_line || "—"}
              </div>
            ) : null}
          </section>

          {/* 军令按钮：渲染但置灰 —— 发起通道未定（方案 §3.2） */}
          <section>
            <div className="mb-1 font-kai text-[13.5px] font-bold text-gold-dark">驻地施令</div>
            <div className="mb-1 flex items-center gap-2 text-[12.5px]">
              <span className="text-dim">新番号</span>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="1–12 字（拆分/改名）"
                className="w-40 rounded border border-border bg-card px-2 py-0.5 text-[13px]"
              />
            </div>
            <div className="mb-1 flex items-center gap-2 text-[12.5px]">
              <span className="text-dim">统帅（换帅）</span>
              <input
                value={commander}
                onChange={(e) => setCommander(e.target.value)}
                placeholder="在朝大臣姓名"
                className="w-40 rounded border border-border bg-card px-2 py-0.5 text-[13px]"
              />
            </div>
            {mergeOptions.length > 0 ? (
              <div className="mb-1 flex items-center gap-2 text-[12.5px]">
                <span className="text-dim">并入（合并）</span>
                <select
                  value={mergePick || mergeOptions[0].unit_id}
                  onChange={(e) => setMergePick(e.target.value)}
                  className="rounded border border-border bg-card px-2 py-0.5 text-[13px]"
                >
                  {mergeOptions.map((u) => (
                    <option key={u.unit_id} value={u.unit_id}>{u.army_name || u.name}</option>
                  ))}
                </select>
              </div>
            ) : null}
            {destOptions.length > 0 ? (
              <div className="mb-1 flex items-center gap-2 text-[12.5px]">
                <span className="text-dim">调赴目的地</span>
                <select
                  value={dest || destOptions[0]}
                  onChange={(e) => setDest(e.target.value)}
                  className="rounded border border-border bg-card px-2 py-0.5 text-[13px]"
                >
                  {destOptions.map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
            ) : null}
            <div className="grid grid-cols-4 gap-2">
              {ACTIONS.map((a) => {
                const ok = !!CAN_ORDER[a] && !!sel && !busy;
                return (
                  <button
                    key={a}
                    disabled={!ok}
                    onClick={() => void doOrder(a)}
                    title={CAN_ORDER[a]
                      ? `对选中编制单位「${sel?.army_name || sel?.name || ""}」施行${a}（走既有批红通道，留审计）`
                      : (a === "合并"
                        ? "合并需本路同军籍 ≥2 支编制单位（可先「拆分」出一支）"
                        : `${a} 尚无契约`)}
                    className={ok
                      ? "rounded border border-gold/60 bg-card/70 px-2 py-1 text-[13px] text-ink hover:bg-card"
                      : "cursor-not-allowed rounded border border-border/60 bg-card/40 px-2 py-1 text-[13px] text-dim"}
                  >
                    {a}
                  </button>
                );
              })}
            </div>
            {msg ? <div className="mt-1 text-[12px] text-ink">{msg}</div> : null}
            <div className="mt-1 text-[11.5px] leading-relaxed text-dim">
              玩家亲裁：经 `issue_military_order` 入待批队列（`proposer="玩家"`）后**即时批红**，
              执行落在既有 `_apply_military_dispatch`（校验/档位封顶/POP 守恒同一处）；
              **参考图 8 键全部可施行**：整编／扩编／地图调度／拆分／合并／换帅／裁撤／改名。
              守恒口径：拆分为兵种对半（Σ兵额不变、兵 POP 不变）、合并相加（欠饷随存续番号）、
              裁撤复员归农（ΣPOP 不变）、改名与换帅只动展示层。
            </div>
          </section>
        </>
      )}
    </div>
  );
}
