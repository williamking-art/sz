import { useState } from "react";
import { Settings } from "lucide-react";
import { useGameStore, hudEra, hudPrestige, hudPopular, hudTreasury, hudPrivy, hudToken, hudTreasuryFlow, hudPrivyFlow } from "../store/gameStore";
import { humanizeCoin } from "../utils/format";

// 顶部状态条：朱红徽章「宋」+ 古意纪年 + 四枚数值胶囊 + 词元计数
// 呈现格式对齐 game/ui/panels_core.py::_build_hud / _refresh_hud（双轨一致）
export default function TopBar() {
  const state = useGameStore((s) => s.state);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const [open, setOpen] = useState<"treasury" | "privy" | null>(null);

  const era = hudEra(state);
  const prestige = hudPrestige(state);
  const popular = hudPopular(state);
  const treasury = hudTreasury(state);
  const privy = hudPrivy(state);
  const token = hudToken(state);

  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex items-start justify-between px-4 pt-3">
      {/* 左：纯正大宋皇室徽标 + 纪元（庄严只读展示，不做按钮） */}
      <div className="pointer-events-auto flex items-center gap-3 rounded-[3px] border border-gold bg-card px-2.5 py-1.5 shadow-paper">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red ring-2 ring-gold shadow-sm">
          <span className="font-kai text-[20px] font-bold leading-none text-[#f3e6c4]">宋</span>
        </div>
        <span className="whitespace-nowrap font-kai text-[15px] font-bold tracking-wide text-ink">
          {era || "建中靖国元年正月"}
        </span>
      </div>

      {/* 右：数值胶囊 + 词元 */}
      <div className="pointer-events-auto flex items-center gap-2 rounded-[3px] border border-gold bg-card px-2.5 py-2 shadow-paper">
        <span className="whitespace-nowrap rounded-[2px] border border-border px-2 py-1 text-[13px] font-bold text-ink">
          ◆威望 {Math.round(prestige)}
        </span>
        <span className="whitespace-nowrap rounded-[2px] border border-border px-2 py-1 text-[13px] font-bold text-ink">
          ♥民心 {Math.round(popular)}
        </span>
        <HoverCapsule
          text={`◈国库 ${humanizeCoin(treasury)}`}
          open={open === "treasury"}
          onToggle={() => setOpen(open === "treasury" ? null : "treasury")}
          onClose={() => setOpen(null)}
          rows={hudTreasuryFlow(state)}
        />
        <HoverCapsule
          text={`⛃内帑 ${humanizeCoin(privy)}`}
          open={open === "privy"}
          onToggle={() => setOpen(open === "privy" ? null : "privy")}
          onClose={() => setOpen(null)}
          rows={hudPrivyFlow(state)}
        />
        {token !== null && (
          <span className="whitespace-nowrap px-1 text-[12px] font-bold text-dim">
            词元 ▸ {token.toLocaleString("en-US")}
          </span>
        )}

        {/* 右上角新设专属齿轮设置入口（主菜单 / 存档 / AI配置） */}
        <button
          onClick={() => pushOverlay({ kind: "settings", title: "机务设置" })}
          title="系统机务设置 / 返回主菜单"
          className="group flex h-7 w-7 items-center justify-center rounded-[2px] border border-border bg-paper/60 text-ink-light transition hover:border-gold hover:bg-gold-light hover:text-red"
        >
          <Settings size={15} className="transition group-hover:rotate-45" />
        </button>
      </div>
    </div>
  );
}

/** 国库/内帑胶囊：鼠标进入展开收支悬浮栏，离开收起。 */
function HoverCapsule({
  text, open, onToggle, onClose, rows
}: {
  text: string;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
  rows: [string, string][];
}) {
  return (
    <div className="relative" onMouseLeave={onClose}>
      <button
        onMouseEnter={onToggle}
        onFocus={onToggle}
        className="whitespace-nowrap rounded-[2px] border border-border px-2 py-1 text-[13px] font-bold text-ink transition hover:bg-gold-light"
      >
        {text}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-30 mt-1 w-52 rounded-[3px] border border-gold bg-card p-2.5 shadow-card">
          <div className="mb-1.5 border-b border-border pb-1 font-kai text-[13px] tracking-widest text-red-dark">
            {text.startsWith("◈") ? "国 库 收 支" : "内 帑 收 支"}
          </div>
          {rows.length === 0 ? (
            <div className="py-0.5 text-xs text-dim">（本月无收支项）</div>
          ) : (
            rows.map(([k, v]) => (
              <div key={k} className="flex justify-between py-0.5 text-xs">
                <span className="text-dim">{k}</span>
                <span className="text-ink">{v}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}