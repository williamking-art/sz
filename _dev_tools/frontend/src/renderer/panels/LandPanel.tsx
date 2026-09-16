import { useGameStore, pick } from "../store/gameStore";

// 田亩户籍总览 —— 对齐 game/ui/panels_economy.py::_panel_land（只读展示）
// 全国垦田/隐漏/荒田 + 诸路田亩粮产民情 + 诸路六阶 POP 万口。
type Dict = Record<string, unknown>;
type StateDict = Dict | null;

function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}
function asDict(v: unknown): Dict {
  return v && typeof v === "object" ? (v as Dict) : {};
}
function humanN(n: number): string {
  if (n >= 100000000) return `${(n / 100000000).toFixed(1)}亿`;
  if (n >= 10000) return `${(n / 10000).toFixed(0)}万`;
  return `${n}`;
}
function popWan(n: number): string {
  return n >= 10000 ? `${(n / 10000).toFixed(0)}万` : `${n}`;
}
const pW = popWan;

export default function LandPanel() {
  const state = useGameStore((s) => s.state);
  const land = asDict(state && (state as Dict).land);
  const prefectures = asDict(state && (state as StateDict) && (state as Dict).prefectures);
  const prefList = Object.keys(prefectures).map((name) => ({ name, p: asDict(prefectures[name]) }));

  const cultivated = asNum(land.cultivated);
  const hidden = asNum(land.hidden_rate);
  const wasteland = asNum(land.wasteland);
  const households = asNum(land.households);
  const yieldK = asNum(land.yield);

  const lines = prefList.map(({ name, p }) => {
    const pops = asDict(p.pops);
    const cls: Record<string, number> = {};
    for (const k of ["农", "士绅", "工匠", "商人", "官僚", "兵"]) {
      cls[k] = asNum(asDict(pops[k]).size);
    }
    return {
      name,
      households: asNum(p.households),
      land: asNum(p.land),
      grain: asNum(p.grain),
      mood: asNum(p.mood, asNum(p.public_support, asNum(p.govern, 0))),
      cls,
    };
  });

  const totH = lines.reduce((a, x) => a + x.households, 0);
  const totW = lines.reduce((a, x) => a + (x.cls["农"] || 0) + (x.cls["士绅"] || 0) + (x.cls["工匠"] || 0) + (x.cls["商人"] || 0) + (x.cls["官僚"] || 0) + (x.cls["兵"] || 0), 0);

  return (
    <div className="space-y-4">
      {/* 全国概要 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
        <p className="font-kai text-[15px] font-bold tracking-widest text-red">全 国 概 要</p>
        <p className="mt-2 text-sm leading-relaxed text-ink">
          垦田：{humanN(cultivated)} 亩　隐漏率：{Math.round(hidden * 100)}%　荒田：{humanN(wasteland)} 亩
        </p>
        <p className="mt-1 text-sm leading-relaxed text-ink">
          在籍户：{humanN(households)}　六阶人口合计：{popWan(totW)} 口
        </p>
        <p className="mt-1 text-sm text-dim">亩产系数：{yieldK.toFixed(2)}</p>
      </div>

      {/* 诸路 */}
      <div className="max-h-[46vh] space-y-2 overflow-y-auto pr-1">
        {lines.map((r) => (
          <div key={r.name} className="rounded-lg border border-gold/40 bg-paper/60 p-3">
            <p className="font-kai text-[14px] font-bold text-ink">
              {r.name}　户 {humanN(r.households)}　垦 {humanN(r.land)}
            </p>
            <p className="mt-0.5 text-xs text-dim">
              粮产 {humanN(r.grain)}　民情 {r.mood}　（农{pW(r.cls["农"])} 绅{pW(r.cls["士绅"])} 工{pW(r.cls["工匠"])} 商{pW(r.cls["商人"])} 官{pW(r.cls["官僚"])} 兵{pW(r.cls["兵"])}）
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}