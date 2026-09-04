import { Map, Warehouse, Calculator, Shield, FlaskConical, Hammer, BookOpen, Scale } from "lucide-react";
import { useGameStore } from "../store/gameStore";

// 右侧竖排功能钮：州县/仓廪/会计/军政/科技/工程
const ITEMS: { key: string; label: string; icon: React.ReactNode }[] = [
  { key: "prefecture", label: "州县", icon: <Map size={20} /> },
  { key: "granary", label: "仓廪", icon: <Warehouse size={20} /> },
  { key: "accounting", label: "会计", icon: <Calculator size={20} /> },
  { key: "military", label: "军政", icon: <Shield size={20} /> },
  { key: "tech", label: "科技", icon: <FlaskConical size={20} /> },
  { key: "focus", label: "国策", icon: <Scale size={20} /> },
  { key: "engineering", label: "工程", icon: <Hammer size={20} /> },
  { key: "codex", label: "典籍", icon: <BookOpen size={20} /> }
];

export default function RightStrip() {
  const pushOverlay = useGameStore((s) => s.pushOverlay);

  return (
    <div className="pointer-events-auto absolute right-4 top-1/2 z-20 flex -translate-y-1/2 flex-col items-center gap-3">
      {ITEMS.map((it) => (
        <button
          key={it.key}
          onClick={() => pushOverlay({ kind: it.key as never, title: it.label })}
          className="group flex h-13 w-13 p-1.5 flex-col items-center justify-center rounded-full bg-card/95 shadow-paper backdrop-blur-sm transition hover:bg-gold-light hover:shadow-card border border-gold/40"
        >
          <span className="text-red transition group-hover:scale-110">{it.icon}</span>
          <span className="mt-0.5 text-[11px] font-bold text-ink">{it.label}</span>
        </button>
      ))}
    </div>
  );
}