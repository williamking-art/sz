import { useGameStore, pick } from "../store/gameStore";

// 密旨与御笔 —— 对齐 game/ui/panels_govern.py::_panel_secret_decree（只读展示）
// 展示：待下密谕清单 / 御笔直发剩余额度 / 生效中密令。狼来了机制已取消，不再显示公信惩罚。
type Dict = Record<string, unknown>;

function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}
function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}

function entryText(e: Dict): { title: string; target: string; log: string } {
  const title = asStr(e.title, "密谕");
  const target = asStr(e.target || e.minister, "");
  const body = asStr(e.desc || e.content || e.summary, "");
  return { title, target, log: asStr(e.note, body) };
}

export default function SecretDecreePanel() {
  const state = useGameStore((s) => s.state);
  const secret = pick<Dict[]>(state, "pending_secret_decrees", []);
  const active = pick<Dict[]>(state, "active_decrees", []);
  const secretActives = active.filter(
    (d) => d.is_secret === true || asStr(d.category) === "密旨",
  );
  const used = asNum(state && (state as Dict).direct_decree_used, 0);
  const band = asNum(state && (state as Dict).decree_bandwidth, 6);

  return (
    <div className="space-y-5">
      {/* 额度 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
        <p className="font-kai text-sm tracking-widest text-dim">御笔直发（本月已用 {used} / 上限 2）　圣旨带宽余 {band}</p>
      </div>

      {/* 待下密谕 */}
      <div>
        <p className="mb-2 font-kai text-[15px] font-bold tracking-widest text-red">待 下 密 谕</p>
        {secret.length === 0 ? (
          <p className="py-4 text-center font-kai text-base text-dim">— 暂无待下密谕 —</p>
        ) : (
          <div className="space-y-2">
            {secret.map((e, i) => {
              const { title, target, log } = entryText(e);
              return (
                <div key={i} className="rounded-lg border border-[#6b4e16] bg-paper/60 p-3">
                  <p className="font-kai text-[15px] font-bold text-ink">{title}</p>
                  <p className="mt-1 text-xs text-dim">
                    {target ? `目标：${target}　` : ""}密旨上限 3 道
                  </p>
                  {log && <p className="mt-1 text-xs leading-relaxed text-ink-light">{log}</p>}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 生效密令 */}
      <div>
        <p className="mb-2 font-kai text-[15px] font-bold tracking-widest text-red">奉 行 中 密 令</p>
        {secretActives.length === 0 ? (
          <p className="py-4 text-center font-kai text-base text-dim">— 无奉行中密令 —</p>
        ) : (
          <div className="space-y-2">
            {secretActives.map((e, i) => {
              const { title } = entryText(e);
              return (
                <div key={i} className="rounded-lg border border-gold/40 bg-paper/60 p-3">
                  <p className="font-kai text-sm font-bold text-ink">{title}</p>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}