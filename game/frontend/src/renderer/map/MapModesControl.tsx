import React from "react";
import { Compass, Wheat, Flame, Shield, Map as MapIcon } from "lucide-react";
import { audioEngine } from "../audio/engine";

export type MapMode = "political" | "climate" | "unrest" | "military";

export interface MapModeOption {
  id: MapMode;
  name: string;
  sub: string;
  desc: string;
  icon: React.ReactNode;
}

export const MAP_MODES: MapModeOption[] = [
  {
    id: "political",
    name: "中原疆宇",
    sub: "政区",
    desc: "北宋二十一路疆界与周边辽、夏、大理、交趾天下大势",
    icon: <MapIcon size={14} />,
  },
  {
    id: "climate",
    name: "九州物候",
    sub: "丰歉",
    desc: "二十一路四价一荒、丰稔水旱与粮绢市井物候",
    icon: <Wheat size={14} />,
  },
  {
    id: "unrest",
    name: "海内生计",
    sub: "民怨",
    desc: "各路微观家计赤字、流民涌现与方腊/宋江内生民变起义池",
    icon: <Flame size={14} />,
  },
  {
    id: "military",
    name: "关防烽燧",
    sub: "边备",
    desc: "安抚使司（帅司）边防经略、沿边禁厢军驻泊与烽燧戒备",
    icon: <Shield size={14} />,
  },
];

interface MapModesControlProps {
  currentMode: MapMode;
  onSelectMode: (mode: MapMode) => void;
}

export default function MapModesControl({ currentMode, onSelectMode }: MapModesControlProps) {
  return (
    <aside
      aria-label="舆图四态"
      className="pointer-events-auto absolute right-5 top-[5.2rem] z-10 flex flex-col gap-1.5 rounded-sm border border-[#8f6e28]/50 bg-[#f6ecd6]/92 p-1.5 shadow-[0_8px_24px_rgba(28,18,12,.22)] backdrop-blur-md"
    >
      <div className="flex items-center gap-1.5 border-b border-[#caa24a]/30 px-2 py-1">
        <Compass size={13} className="text-[#8a2b22]" />
        <span className="font-kai text-[11px] font-bold tracking-[.18em] text-[#2b1d12]">舆 图 四 态</span>
      </div>
      <div className="flex flex-col gap-1">
        {MAP_MODES.map((m) => {
          const isActive = currentMode === m.id;
          return (
            <button
              key={m.id}
              onClick={() => {
                audioEngine.playClick();
                onSelectMode(m.id);
              }}
              title={m.desc}
              className={`group flex items-center justify-between gap-3 rounded-sm px-2.5 py-1.5 text-left transition-all ${
                isActive
                  ? "border border-[#caa24a] bg-[#8a2b22] text-[#f6ecd6] shadow-sm"
                  : "border border-transparent text-[#2b1d12] hover:border-[#caa24a]/40 hover:bg-[#ebd9b5]/60"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className={isActive ? "text-[#e8d49c]" : "text-[#8a2b22]"}>
                  {m.icon}
                </span>
                <span className="font-kai text-[12px] font-bold tracking-[.1em]">
                  {m.name}
                </span>
              </div>
              <span
                className={`font-kai text-[9px] tracking-widest px-1 py-0.5 rounded ${
                  isActive ? "bg-[#caa24a]/30 text-[#f6ecd6]" : "text-[#8f6e28] bg-[#caa24a]/15"
                }`}
              >
                {m.sub}
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
