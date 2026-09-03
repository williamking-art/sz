import { Map, Warehouse, Calculator, Shield, FlaskConical, Hammer } from "lucide-react";
import { useGameStore } from "../store/gameStore";

// 右侧竖排功能钮：州县/仓廪/会计/军政/科技/工程
const ITEMS: { key: string; label: string; icon: React.ReactNode }[] = [
  { key: "prefecture", label: "州县", icon: <Map size={20} /> },
  { key: "granary", label: "仓廪", icon: <Warehouse size={20} /> },
  { key: "accounting", label: "会计", icon: <Calculator size={20} /> },
  { key: "military", label: "军政", icon: <Shield size={20} /> },
  { key: "tech", label: "科技", icon: <FlaskConical size={20} /> },
  { key: "engineering", label: "工程", icon: <Hammer size={20} /> }
];

export default function RightStrip() {
  const pushOverlay = useGameStore((s) => s.pushOverlay);

  return (
    <div className="pointer-events-auto absolute right-4 top-1/2 z-20 flex -translate-y-1/2 flex-col items-center gap-3">
      {ITEMS.map((it) => (
        <button
          key={it.key}
          onClick={() => pushOverlay({ kind: it.key as never, title: it.label })}
          className="group flex h-12 w-12 flex-col items-center justify-center rounded-full bg-card/90 shadow-paper backdrop-blur-sm transition hover:bg-gold-light hover:shadow-card"
        >
          <span className="text-red transition group-hover:scale-110">{it.icon}</span>
          <span className="mt-0.5 text-[10px] text-ink-light">{it.label}</span>
        </button>
      ))}
    </div>
  );
}